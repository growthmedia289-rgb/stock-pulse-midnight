"""RF-based screening with optional pre-trained LSTM and available sentiment."""
from concurrent.futures import ThreadPoolExecutor
import threading
from pathlib import Path
from data.fetcher import fetch_stock,fetch_news
from models.random_forest import predict_breakout,load_model
from config import Config
_inference_lock=threading.Lock()

def _score_ticker(ticker,model=None,scaler=None):
    try:
        df=fetch_stock(ticker,period='6mo')
        if len(df)<60:return None
        from data.indicators import compute_all
        enriched=compute_all(df);rf=predict_breakout(df);rf_prob=rf['breakout_probability']/100;lstm_prob=rf_prob
        with _inference_lock:
            if all((Path(Config.MODEL_DIR)/name).exists() for name in ['lstm_model.keras','lstm_scaler.pkl']):
                try:
                    from models.lstm_model import predict_breakout as lstm_predict
                    output=lstm_predict(df)
                    if output.get('breakout_probability') is not None:lstm_prob=output['breakout_probability']/100
                except Exception:pass
            sentiment={'score':0,'label':'Unavailable'}
            try:
                headlines=fetch_news(ticker,5)
                if headlines:
                    from models.sentiment import analyze_headlines
                    sentiment=analyze_headlines(headlines)
            except Exception:pass
        percent=round(min(1,max(0,.6*rf_prob+.4*lstm_prob+.1*sentiment['score']))*100,2);last=enriched.iloc[-1]
        return dict(ticker=ticker,breakout_prob=percent,signal='STRONG BUY' if percent>70 else 'BUY' if percent>55 else 'NEUTRAL' if percent>40 else 'SELL',rsi=round(float(last['RSI']),1),macd=round(float(last['MACD']),4),adx=round(float(last['ADX']),1),vol_ratio=round(float(last['Vol_Ratio']),2),sentiment=sentiment['label'],sentiment_score=sentiment['score'],close=round(float(df.Close.iloc[-1]),2),change_pct=round(float(df.Close.pct_change().iloc[-1])*100,2))
    except Exception as e:
        print(f'[Screener] Skipping {ticker}: {type(e).__name__}')
        return None

def scan_market(tickers=None,top_n=20,min_prob=0.,signal_filter='ALL',max_workers=2):
    model,scaler=load_model()
    if model is None:raise ValueError('Train Random Forest in Model settings before scanning.')
    with ThreadPoolExecutor(max_workers=max_workers) as pool:rows=[r for r in pool.map(_score_ticker,tickers or Config.NSE_STOCKS) if r]
    return sorted([r for r in rows if r['breakout_prob']>=min_prob and (signal_filter=='ALL' or r['signal']==signal_filter)],key=lambda r:r['breakout_prob'],reverse=True)[:top_n]

def get_top_movers(period='1d',n=10):
    rows=[]
    for t in Config.NSE_STOCKS[:30]:
        df=fetch_stock(t,'5d')
        if len(df)>1:rows.append(dict(ticker=t,close=float(df.Close.iloc[-1]),change_pct=round((float(df.Close.iloc[-1])/float(df.Close.iloc[-2])-1)*100,2)))
    return dict(gainers=sorted([r for r in rows if r['change_pct']>0],key=lambda r:r['change_pct'],reverse=True)[:n],losers=sorted([r for r in rows if r['change_pct']<0],key=lambda r:r['change_pct'])[:n])
