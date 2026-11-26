"""StockPulse Midnight: local Flask research application."""
import os, re, math, secrets, json, uuid, threading, time
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit
from flask import Flask,render_template,request,jsonify,redirect,url_for,flash,session,abort
from flask_login import LoginManager,login_user,logout_user,login_required,current_user
from sqlalchemy.exc import IntegrityError
from config import Config
from database.models import db,User,Portfolio,Watchlist

app=Flask(__name__)
app.config.from_object(Config)
DEMO=os.getenv('STOCKPULSE_DEMO','0')=='1'
db.init_app(app)
login_manager=LoginManager(app)
login_manager.login_view='login'
login_manager.login_message_category='info'
training_lock=threading.Lock()

@login_manager.user_loader
def load_user(uid):
    try:return db.session.get(User,int(uid))
    except (ValueError,TypeError):return None

@login_manager.unauthorized_handler
def unauthorized():
    if request.path.startswith('/api/'):
        return jsonify(error='Please sign in again to continue.'),401
    return redirect(url_for('login',next=request.path))

def csrf_token():
    if '_csrf' not in session:session['_csrf']=secrets.token_urlsafe(32)
    return session['_csrf']

@app.before_request
def check_csrf():
    if request.method=='POST':
        expected=session.get('_csrf','')
        supplied=request.headers.get('X-CSRF-Token') or request.form.get('csrf_token','')
        if not expected or not secrets.compare_digest(expected,supplied):
            if request.path.startswith('/api/'):return jsonify(error='Your session expired. Refresh the page and try again.'),400
            flash('Your session expired. Please try again.','warning')
            return redirect(url_for('login') if not current_user.is_authenticated else url_for('dashboard'))

@app.after_request
def response_headers(response):
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='SAMEORIGIN'
    response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
    if request.endpoint!='static':response.headers['Cache-Control']='no-store'
    return response

@app.context_processor
def shared():
    return dict(can_train=can_train(),csrf_token=csrf_token,demo=DEMO,fetched_at=datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%d %b %Y, %I:%M %p'))

def finite(v):
    try:return math.isfinite(float(v))
    except (ValueError,TypeError):return False

def indian(v,decimals=2):
    s=f'{abs(float(v)):.{decimals}f}'
    whole,_,fraction=s.partition('.')
    if len(whole)>3:
        front=whole[:-3];groups=[]
        while front:groups.insert(0,front[-2:]);front=front[:-2]
        whole=','.join(groups)+','+whole[-3:]
    return ('−' if float(v)<0 else '')+whole+('.'+fraction if decimals else '')

@app.template_filter('number')
def number(v,decimals=2):return indian(v,decimals) if finite(v) else 'Unavailable'
@app.template_filter('inr')
def inr(v):return ('−₹' if float(v)<0 else '₹')+indian(abs(float(v))) if finite(v) else 'Unavailable'
@app.template_filter('compact_inr')
def compact(v):
    if not finite(v):return 'Unavailable'
    n=float(v)
    if abs(n)>=1e7:return inr(n/1e7)+' Cr'
    if abs(n)>=1e5:return inr(n/1e5)+' L'
    return inr(n)
@app.template_filter('symbol')
def symbol(v):return re.sub(r'\.(NS|BO)$','',str(v))

def ticker_symbol(raw,exchange='NSE'):
    raw=str(raw).strip().upper()
    if not re.fullmatch(r'[A-Z0-9&^][A-Z0-9&.\-^]{0,23}',raw):raise ValueError('Enter a valid exchange ticker, such as RELIANCE or INFY.')
    return raw if raw.endswith(('.NS','.BO')) else raw+('.BO' if exchange=='BSE' else '.NS')

def positive(raw,label,maximum=1e12,minimum=0):
    try:value=float(raw)
    except (ValueError,TypeError):raise ValueError(f'Enter a valid {label}.')
    if not math.isfinite(value) or value<=minimum or value>maximum:raise ValueError(f'{label.capitalize()} must be greater than {minimum:g} and at most {maximum:g}.')
    return value

def can_train():
    return bool(current_user.is_authenticated and app.config['ENABLE_WEB_TRAINING'] and current_user.id in app.config['ADMIN_USER_IDS'])

def models_ready():
    base=Path(Config.MODEL_DIR)
    return {'rf':all((base/n).exists() for n in ['rf_model.pkl','rf_scaler.pkl']), 'lstm':all((base/n).exists() for n in ['lstm_model.keras','lstm_scaler.pkl'])}

def prices(ticker,period='1y'):
    if DEMO:
        from demo_data import stock
        return stock(ticker,period)
    from data.fetcher import fetch_stock
    return fetch_stock(ticker,period)

def latest(ticker):
    frame=prices(ticker,'5d')
    return float(frame.Close.iloc[-1]) if not frame.empty else None

def chart_spec(data,**layout):return {'data':data,'layout':layout}

def line_spec(frame,column='Close',name='Price'):
    return chart_spec([{'type':'scatter','mode':'lines','name':name,'x':[str(x.date()) for x in frame.index],'y':frame[column].tolist(),'line':{'color':'#43dcc3','width':2}}],height=340)

def normal_spec(serialized):return json.loads(serialized) if isinstance(serialized,str) else serialized

@app.route('/')
def index():return redirect(url_for('dashboard')) if current_user.is_authenticated else render_template('index.html')

@app.route('/register',methods=['GET','POST'])
def register():
    if current_user.is_authenticated:return redirect(url_for('dashboard'))
    if request.method=='POST':
        username=request.form.get('username','').strip();email=request.form.get('email','').strip().lower();password=request.form.get('password','')
        if not re.fullmatch(r'[A-Za-z0-9_]{3,40}',username):flash('Use 3–40 letters, numbers or underscores for your username.','danger')
        elif len(email)>120 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):flash('Enter a valid email address.','danger')
        elif len(password)<8:flash('Use at least 8 characters for your password.','danger')
        elif password!=request.form.get('confirm_password'):flash('The passwords do not match.','danger')
        elif User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first():flash('That username or email is already registered. Try signing in.','warning')
        else:
            user=User(username=username,email=email);user.set_password(password);db.session.add(user)
            try:db.session.commit()
            except IntegrityError:db.session.rollback();flash('That username or email is already registered.','warning')
            else:flash('Account created. Sign in to open your workspace.','success');return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login',methods=['GET','POST'])
def login():
    if current_user.is_authenticated:return redirect(url_for('dashboard'))
    if request.method=='POST':
        attempts=session.get('login_attempts',[]);now=time.time();attempts=[t for t in attempts if now-t<300]
        if len(attempts)>=10:flash('Too many attempts in this browser session. Wait five minutes and try again.','warning')
        else:
            user=User.query.filter_by(username=request.form.get('username','').strip()).first()
            if user and user.check_password(request.form.get('password','')):
                session.clear();login_user(user);csrf_token()
                next_url=request.args.get('next','')
                parsed=urlsplit(next_url)
                safe=next_url.startswith('/') and not next_url.startswith('//') and not parsed.netloc and not parsed.scheme and '\\' not in next_url
                return redirect(next_url if safe else url_for('dashboard'))
            attempts.append(now);session['login_attempts']=attempts;flash('Username or password is incorrect. Please try again.','danger')
    return render_template('login.html')

@app.post('/logout')
@login_required
def logout():logout_user();session.clear();return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    if DEMO:
        from demo_data import overview,movers as demo_movers
        market=overview();movers=demo_movers()
    else:
        from data.fetcher import get_market_overview
        market=get_market_overview()
        from concurrent.futures import ThreadPoolExecutor
        def move(t):
            frame=prices(t,'5d')
            if len(frame)<2:return None
            return dict(ticker=t,close=float(frame.Close.iloc[-1]),change_pct=round((float(frame.Close.iloc[-1])/float(frame.Close.iloc[-2])-1)*100,2))
        with ThreadPoolExecutor(max_workers=3) as pool:records=[r for r in pool.map(move,Config.NSE_STOCKS[:30]) if r]
        movers={'gainers':sorted([r for r in records if r['change_pct']>0],key=lambda r:r['change_pct'],reverse=True)[:5],'losers':sorted([r for r in records if r['change_pct']<0],key=lambda r:r['change_pct'])[:5]}
    watch=Watchlist.query.filter_by(user_id=current_user.id).all();alerts=[]
    for w in watch:
        if w.alert_price and w.alert_price>0:
            value=latest(w.ticker)
            if value and abs(value-w.alert_price)/w.alert_price<.005:alerts.append(dict(ticker=w.ticker,message=f'Latest close {inr(value)} is near your target {inr(w.alert_price)}.'))
    overview_frame=prices('^NSEI','6mo')
    market_chart=line_spec(overview_frame,name='NIFTY 50') if not overview_frame.empty else None
    market_as_of=str(overview_frame.index[-1].date()) if not overview_frame.empty else None
    return render_template('dashboard.html',market=market,movers=movers,watchlist=watch,alerts=alerts,market_chart=market_chart,market_as_of=market_as_of)

@app.route('/analyze',methods=['GET','POST'])
@login_required
def analyze():
    source=request.form if request.method=='POST' else request.args
    form=dict(ticker=source.get('ticker','').strip().upper(),exchange=source.get('exchange','NSE'),period=source.get('period','1y'),use_lstm=source.get('use_lstm')=='on')
    result=None
    if form['ticker']:
        try:
            ticker=ticker_symbol(form['ticker'],form['exchange']);form['exchange']='BSE' if ticker.endswith('.BO') else 'NSE';form['ticker']=symbol(ticker)
            if form['period'] not in ['6mo','1y','2y']:raise ValueError('Choose a supported history period.')
            df=prices(ticker,form['period'])
            if df.empty:raise ValueError(f'No price history was returned for {symbol(ticker)}. Check the ticker or try again later.')
            from data.indicators import compute_all
            enriched=compute_all(df)
            if 'RSI' not in enriched:raise ValueError('At least 30 daily bars are needed for analysis.')
            rf={};lstm=None;importance={}
            sentiment={'score':0,'label':'Unavailable','details':[],'confidence':0}
            if DEMO:
                from demo_data import analysis
                info,rf,lstm,sentiment,importance=analysis(ticker,form['use_lstm'])
            else:
                from data.fetcher import fetch_stock_info,fetch_news
                info=fetch_stock_info(ticker)
                ready=models_ready()
                if ready['rf']:
                    try:
                        from models.random_forest import predict_breakout,get_feature_importance
                        rf=predict_breakout(df);importance=dict(list(get_feature_importance().items())[:8])
                    except Exception:app.logger.exception('RF inference failed');flash('Random Forest could not score this stock. Price charts are still available.','warning')
                else:flash('Train Random Forest in Model settings to enable the combined model score.','info')
                if form['use_lstm']:
                    if ready['lstm']:
                        try:
                            from models.lstm_model import predict_breakout
                            lstm=predict_breakout(df)
                            if lstm.get('signal')=='INSUFFICIENT DATA':lstm=None;flash('Not enough valid bars for LSTM. Using available RF output.','warning')
                        except Exception:app.logger.exception('LSTM inference failed');flash('LSTM is unavailable. Using available RF output.','warning')
                    else:flash('LSTM is not trained. It was excluded from the score.','warning')
                headlines=fetch_news(ticker,8)
                if headlines:
                    try:
                        from models.sentiment import analyze_headlines
                        sentiment=analyze_headlines(headlines)
                    except Exception:app.logger.exception('Sentiment unavailable');flash('Headline sentiment is unavailable. No sentiment adjustment was applied.','warning')
            final=None
            if rf.get('breakout_probability') is not None:
                r=rf['breakout_probability']/100;l=lstm['breakout_probability']/100 if lstm else r
                final=round(min(1,max(0,.6*r+.4*l+.1*sentiment['score']))*100,2)
            signal='Unavailable' if final is None else 'STRONG BUY' if final>70 else 'BUY' if final>55 else 'NEUTRAL' if final>40 else 'SELL'
            from charts import build_candlestick,build_indicator_chart
            result=dict(ticker=ticker,info=info,rf=rf,lstm=lstm,sentiment=sentiment,final_prob=final,signal=signal,importance=importance,last=enriched.iloc[-1].to_dict(),close=float(df.Close.iloc[-1]),as_of=str(df.index[-1].date()),candle_json=normal_spec(build_candlestick(enriched.tail(120),ticker)),indicator_json=normal_spec(build_indicator_chart(enriched.tail(120))))
        except ValueError as e:flash(str(e),'warning')
        except Exception:app.logger.exception('Stock analysis failed');flash('Analysis could not finish. Try again; check the server log if the problem continues.','danger')
    return render_template('analyze.html',form=form,result=result)

@app.route('/screener',methods=['GET','POST'])
@login_required
def screener():
    form=dict(exchange=request.form.get('exchange','NSE'),signal=request.form.get('signal','ALL'),min_prob=request.form.get('min_prob','0'));results=[];submitted=request.method=='POST'
    if submitted:
        try:
            score=float(form['min_prob'])
            if not math.isfinite(score) or not 0<=score<=100:raise ValueError('Minimum score must be between 0 and 100.')
            if DEMO:
                from demo_data import screened
                results=[r for r in screened(form['exchange']) if r['breakout_prob']>=score and (form['signal']=='ALL' or r['signal']==form['signal'])]
            elif not models_ready()['rf']:flash('Train Random Forest in Model settings before running a scan.','warning')
            else:
                from engine.screener import scan_market
                results=scan_market(Config.BSE_STOCKS if form['exchange']=='BSE' else Config.NSE_STOCKS,top_n=30,min_prob=score,signal_filter=form['signal'],max_workers=2)
        except ValueError as e:flash(str(e),'warning')
        except Exception:app.logger.exception('Screening failed');flash('The scan could not finish. Check the data feed and model files, then try again.','danger')
    return render_template('screener.html',form=form,results=results,submitted=submitted,nse_count=len(Config.NSE_STOCKS),bse_count=len(Config.BSE_STOCKS))

@app.post('/watchlist')
@login_required
def watchlist():
    try:
        if request.form.get('action')=='add':
            ticker=ticker_symbol(request.form.get('ticker',''),request.form.get('exchange','NSE'));raw=request.form.get('alert_price','').strip();price=positive(raw,'target price') if raw else None
            if Watchlist.query.filter_by(user_id=current_user.id,ticker=ticker).first():raise ValueError('That stock is already in your watchlist.')
            db.session.add(Watchlist(user_id=current_user.id,ticker=ticker,alert_price=price));db.session.commit();flash(f'{symbol(ticker)} added to your watchlist.','success')
        elif request.form.get('action')=='delete':
            item=Watchlist.query.filter_by(id=request.form.get('watchlist_id'),user_id=current_user.id).first_or_404();db.session.delete(item);db.session.commit();flash('Stock removed from your watchlist.','success')
    except ValueError as e:flash(str(e),'warning')
    return redirect(url_for('dashboard'))

@app.route('/portfolio',methods=['GET','POST'])
@login_required
def portfolio():
    if request.method=='POST':
        try:
            if request.form.get('action')=='add':
                t=ticker_symbol(request.form.get('ticker',''),request.form.get('exchange','NSE'));price=positive(request.form.get('buy_price'),'purchase price');qty=positive(request.form.get('quantity'),'quantity')
                db.session.add(Portfolio(user_id=current_user.id,ticker=t,buy_price=price,quantity=qty,company=request.form.get('company','').strip()[:100] or symbol(t),notes=request.form.get('notes','')[:500]));db.session.commit();flash('Holding saved to your portfolio.','success')
            elif request.form.get('action')=='delete':
                h=Portfolio.query.filter_by(id=request.form.get('portfolio_id'),user_id=current_user.id).first_or_404();db.session.delete(h);db.session.commit();flash('Holding removed.','success')
        except ValueError as e:flash(str(e),'warning')
        return redirect(url_for('portfolio'))
    holdings=Portfolio.query.filter_by(user_id=current_user.id).all();rows=[];price_cache={}
    for h in holdings:
        if h.ticker not in price_cache:price_cache[h.ticker]=latest(h.ticker)
        value=price_cache[h.ticker];invested=h.buy_price*h.quantity;current=value*h.quantity if value is not None else None;pnl=current-invested if current is not None else None
        rows.append(dict(id=h.id,ticker=h.ticker,company=h.company,qty=h.quantity,buy_price=h.buy_price,cur_price=value,invested=invested,cur_value=current,pnl=pnl,pnl_pct=pnl/invested*100 if pnl is not None and invested>0 else None,weight_pct=None))
    missing=any(h['cur_value'] is None for h in rows);invested=sum(h['invested'] for h in rows);value=sum(h['cur_value'] for h in rows) if not missing else None;pnl=value-invested if value is not None else None
    if value and not missing:
        for row in rows:row['weight_pct']=row['cur_value']/value*100
    summary=dict(holdings=rows,total_invested=invested,current_value=value,total_pnl=pnl,total_pnl_pct=pnl/invested*100 if pnl is not None and invested else None,missing_prices=missing)
    chart={}
    if rows and not missing:
        allocation={}
        for r in rows:allocation[r['ticker']]=allocation.get(r['ticker'],0)+r['cur_value']
        chart['pie']=chart_spec([dict(type='pie',labels=[symbol(t) for t in allocation],values=list(allocation.values()),hole=.65,textinfo='percent',hovertemplate='%{label}: ₹%{value:,.2f}<extra></extra>')],height=320,showlegend=True)
        chart['bar']=chart_spec([dict(type='bar',x=[f"{symbol(r['ticker'])} · lot {r['id']}" for r in rows],y=[r['pnl_pct'] for r in rows],marker=dict(color=['#43dcc3' if r['pnl_pct']>=0 else '#ff8d9b' for r in rows]))],height=320,yaxis=dict(ticksuffix='%'))
    return render_template('portfolio.html',summary=summary,chart=chart)

@app.route('/backtest',methods=['GET','POST'])
@login_required
def backtest_view():
    strategies=['RSI','MACD','Bollinger','SuperTrend','Combined'];defaults=dict(ticker='',exchange='NSE',strategy='Combined',period='2y',capital='100000',stop_loss='5',take_profit='10')
    form={key:request.form.get(key,val) for key,val in defaults.items()};form['compare']=request.form.get('compare')=='on';result=None;comparison=None
    if request.method=='POST':
        try:
            ticker=ticker_symbol(form['ticker'],form['exchange']);capital=positive(form['capital'],'starting capital',1e9,99);sl=positive(form['stop_loss'],'stop loss',99)/100;tp=positive(form['take_profit'],'take profit',1000)/100
            if form['strategy'] not in strategies or form['period'] not in ['1y','2y','3y','5y']:raise ValueError('Choose a supported strategy and history period.')
            frame=prices(ticker,form['period'])
            if frame.empty:raise ValueError('No historical prices were returned. Check the ticker or try again later.')
            from engine.backtester import backtest,compare_strategies
            result=backtest(frame,strategy_name=form['strategy'],initial_capital=capital,stop_loss_pct=sl,take_profit_pct=tp)
            if 'error' in result:raise ValueError(result['error'])
            result['ticker']=ticker;eq=result['equity_curve'];result['equity_chart']=chart_spec([dict(type='scatter',mode='lines',name='Portfolio equity',x=[d['date'] for d in eq],y=[d['equity'] for d in eq],line=dict(color='#43dcc3'),fill='tozeroy',fillcolor='rgba(67,220,195,.08)')],height=350,yaxis=dict(title='Equity (₹)'))
            if form['compare']:comparison=compare_strategies(frame,initial_capital=capital,stop_loss_pct=sl,take_profit_pct=tp)
        except ValueError as e:flash(str(e),'warning');result=None
        except Exception:app.logger.exception('Backtest failed');flash('The simulation could not finish. Try another stock or history period.','danger');result=None
    return render_template('backtest.html',form=form,result=result,comparison=comparison,strategies=strategies)

@app.get('/chatbot')
@login_required
def chatbot():
    session.setdefault('chat_session_id',str(uuid.uuid4()))
    questions=['What is RSI and how should I use it?','Explain MACD crossover strategy','What does a high ADX value mean?','How does SuperTrend work?','How should I interpret a model score?','How should I manage portfolio risk?']
    return render_template('chatbot.html',quick_questions=questions)

@app.post('/api/chat')
@login_required
def api_chat():
    data=request.get_json(silent=True)
    if not isinstance(data,dict) or not isinstance(data.get('message'),str):return jsonify(error='Enter a text question.'),400
    message=data['message'].strip()
    if not 1<=len(message)<=4000:return jsonify(error='Use between 1 and 4,000 characters.'),400
    now=time.time()
    if now-session.get('last_chat',0)<2:return jsonify(error='Wait a moment before sending another question.'),429
    session['last_chat']=now;session.setdefault('chat_session_id',str(uuid.uuid4()))
    if DEMO:return jsonify(reply='Preview response: RSI describes the balance of recent price gains and losses on a 0–100 scale. Read it alongside trend, volatility and your time horizon. This is illustrative content; live AI replies require Gemini configuration.')
    try:
        from chatbot.assistant import chat
        return jsonify(reply=chat(message,session_id=f'{current_user.id}:{session["chat_session_id"]}'))
    except RuntimeError as e:return jsonify(error=str(e)),503
    except Exception:app.logger.exception('Chat request failed');return jsonify(error='The AI service is unavailable. Try again later.'),503

@app.post('/api/chat/clear')
@login_required
def api_chat_clear():
    sid=f'{current_user.id}:{session.get("chat_session_id","")}'
    if not DEMO:
        from chatbot.assistant import clear_history
        clear_history(sid)
    return jsonify(status='cleared')

@app.route('/train',methods=['GET','POST'])
@login_required
def train_model():
    if request.method=='POST':return run_training('rf')
    return render_template('train.html',model_status=models_ready())

@app.post('/train_lstm')
@login_required
def train_lstm():return run_training('lstm')

def run_training(kind):
    if not can_train():abort(403)
    if DEMO:flash('Training is disabled in preview mode.','info');return redirect(url_for('train_model'))
    if not training_lock.acquire(blocking=False):flash('A training job is already running. Try again after it finishes.','warning');return redirect(url_for('train_model'))
    try:
        if kind=='rf':
            from models.random_forest import train_on_multiple
            model,scaler,metrics=train_on_multiple(Config.NSE_STOCKS[:25],period='2y')
            if model is None:raise ValueError('No training data was collected. Check the price feed.')
            flash(f'Random Forest trained. Held-out accuracy: {metrics["accuracy"]:.1%}; AUC: {metrics["auc_roc"]:.3f}.','success')
        else:
            import pandas as pd
            from models.lstm_model import train
            frames=[]
            for t in Config.NSE_STOCKS[:25]:
                df=prices(t,'2y')
                if not df.empty:df=df.copy();df['Ticker']=t;frames.append(df)
            if not frames:raise ValueError('No training data was collected. Check the price feed.')
            _,_,metrics=train(pd.concat(frames))
            flash(f'LSTM trained. Best held-out validation AUC: {metrics["val_auc"]:.3f}.','success')
    except ValueError as e:flash(str(e),'warning')
    except Exception:app.logger.exception('Training failed');flash('Training failed. Check the server log and installed model dependencies.','danger')
    finally:training_lock.release()
    return redirect(url_for('train_model'))

@app.errorhandler(403)
def forbidden(error):
    return render_template('error.html',code=403,title='This action is restricted.',description='Model training is available only to an explicitly authorised administrator when enabled by the operator.'),403

@app.errorhandler(404)
def not_found(error):
    return render_template('error.html',code=404,title='This page could not be found.',description='The link may be outdated, or this record may not belong to your account.'),404

@app.errorhandler(500)
def unexpected_error(error):
    db.session.rollback()
    if request.path.startswith('/api/'):return jsonify(error='Something went wrong. Please try again.'),500
    return render_template('error.html',code=500,title='Something interrupted this request.',description='Try again in a moment. Your existing records are still stored locally.'),500

@app.errorhandler(413)
def too_large(error):
    if request.path.startswith('/api/'):return jsonify(error='This request is too large. Shorten your question and try again.'),413
    return render_template('error.html',code=413,title='That request was too large.',description='Shorten the information in the form and try again.'),413

with app.app_context():db.create_all()
if __name__=='__main__':app.run(host='127.0.0.1',port=int(os.getenv('PORT',5000)),debug=False,threaded=True)
