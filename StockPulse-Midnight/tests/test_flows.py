import os,tempfile,unittest,re,sys
from pathlib import Path
from unittest.mock import patch
TMP=tempfile.TemporaryDirectory()
os.environ['DATABASE_URL']='sqlite:///'+str(Path(TMP.name)/'test.db')
os.environ['STOCKPULSE_DEMO']='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import app,db,User,Portfolio

class Flows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):app.config.update(TESTING=True)
    def setUp(self):
        app.config.update(ENABLE_WEB_TRAINING=False,ADMIN_USER_IDS=set(),SESSION_COOKIE_SECURE=False)
        with app.app_context():db.drop_all();db.create_all()
        self.c=app.test_client()
    def token(self):
        self.c.get('/login')
        with self.c.session_transaction() as s:return s['_csrf']
    def post(self,path,data=None,**kw):
        values=dict(data or {});values['csrf_token']=self.token()
        return self.c.post(path,data=values,**kw)
    def auth(self,name='tester'):
        r=self.post('/register',dict(username=name,email=name+'@example.com',password='testpass123',confirm_password='testpass123'))
        self.assertEqual(r.status_code,302)
        r=self.post('/login',dict(username=name,password='testpass123'))
        self.assertEqual(r.status_code,302)
    def test_public_and_auth(self):
        for path in ['/','/login','/register']:self.assertEqual(self.c.get(path).status_code,200)
        self.assertEqual(self.c.get('/portfolio').status_code,302)
        self.auth()
        for path in ['/dashboard','/analyze','/screener','/portfolio','/backtest','/chatbot','/train']:
            r=self.c.get(path);self.assertEqual(r.status_code,200,path)
            self.assertNotIn(b'Traceback',r.data)
    def test_csrf_and_registration_validation(self):
        self.assertEqual(self.c.post('/register',data={}).status_code,302)
        r=self.post('/register',dict(username='a',email='bad',password='short',confirm_password='different'),follow_redirects=True)
        self.assertIn(b'3',r.data)
        with app.app_context():self.assertEqual(User.query.count(),0)
    def test_analysis_get_links_and_scores(self):
        self.auth()
        for ticker in ['RELIANCE','INFY.NS','TCS.BO']:
            r=self.c.get('/analyze',query_string=dict(ticker=ticker));self.assertEqual(r.status_code,200)
            self.assertIn(b'Combined model score',r.data);self.assertIn(b'application/json',r.data)
        r=self.post('/analyze',dict(ticker='INFY',exchange='NSE',period='6mo',use_lstm='on'))
        self.assertIn(b'LSTM',r.data)
    def test_holdings_lots_validation_and_ownership(self):
        self.auth()
        for price in [100,200]:
            self.post('/portfolio',dict(action='add',ticker='INFY',exchange='NSE',quantity='10',buy_price=str(price)))
        with app.app_context():
            rows=Portfolio.query.order_by(Portfolio.id).all();ids=[r.id for r in rows]
            self.assertEqual(len(rows),2)
        response=self.c.get('/portfolio');self.assertEqual(response.status_code,200);self.assertIn(b'allocation_chart',response.data)
        self.post('/portfolio',dict(action='delete',portfolio_id=str(ids[0])))
        with app.app_context():self.assertIsNotNone(db.session.get(Portfolio,ids[1]));self.assertIsNone(db.session.get(Portfolio,ids[0]))
        self.post('/portfolio',dict(action='add',ticker='INFY',quantity='-10',buy_price='100'))
        with app.app_context():self.assertEqual(Portfolio.query.count(),1)
        self.post('/logout');self.auth('other')
        self.assertEqual(self.post('/portfolio',dict(action='delete',portfolio_id=str(ids[1]))).status_code,404)
        with app.app_context():self.assertEqual(Portfolio.query.count(),1)
    def test_missing_price_not_zero(self):
        self.auth();self.post('/portfolio',dict(action='add',ticker='INFY',quantity='10',buy_price='100'))
        with patch('app.latest',return_value=None):
            r=self.c.get('/portfolio');self.assertEqual(r.status_code,200);self.assertIn(b'Some prices could not be fetched',r.data);self.assertIn(b'Unavailable',r.data)
    def test_watchlist(self):
        self.auth();self.post('/watchlist',dict(action='add',ticker='INFY',exchange='BSE',alert_price='100'))
        from database.models import Watchlist
        with app.app_context():self.assertEqual(Watchlist.query.first().ticker,'INFY.BO')
        self.post('/watchlist',dict(action='add',ticker='INFY',exchange='BSE',alert_price='100'))
        with app.app_context():self.assertEqual(Watchlist.query.count(),1)
    def test_screener_filters(self):
        self.auth();r=self.post('/screener',dict(exchange='NSE',signal='ALL',min_prob='50'));self.assertEqual(r.status_code,200);self.assertIn(b'screenerTable',r.data)
        r=self.post('/screener',dict(exchange='NSE',signal='ALL',min_prob='100'));self.assertIn(b'No stocks matched',r.data)
    def test_backtest_all_settings(self):
        self.auth();r=self.post('/backtest',dict(ticker='RELIANCE',exchange='NSE',period='1y',strategy='Combined',capital='100000',stop_loss='5',take_profit='10',compare='on'));self.assertEqual(r.status_code,200);self.assertIn(b'Equity through time',r.data);self.assertIn(b'Strategy comparison',r.data)
    def test_chat_validation_and_csrf(self):
        self.auth();token=self.token()
        r=self.c.post('/api/chat',json={'message':'Explain RSI'},headers={'X-CSRF-Token':token});self.assertEqual(r.status_code,200);self.assertIn('reply',r.json)
        r=self.c.post('/api/chat',json={'message':'Again'},headers={'X-CSRF-Token':token});self.assertEqual(r.status_code,429)
        r=self.c.post('/api/chat',json={'message':'Hi'});self.assertEqual(r.status_code,400)
        self.assertEqual(self.c.post('/api/chat/clear',json={},headers={'X-CSRF-Token':token}).status_code,200)
    def test_backtest_accounting(self):
        from engine.backtester import backtest
        from demo_data import stock
        r=backtest(stock('INFY.NS','1y'),strategy_name='SuperTrend')
        closed=[t for t in r['trades'] if t['pnl'] is not None]
        self.assertEqual(r['total_trades'],len(closed));self.assertEqual(len(r['equity_curve']),260)
        self.assertAlmostEqual(sum(t['pnl'] for t in closed),r['final_capital']-r['initial_capital'],delta=.15)
        expected=round(sum(t['pnl']>0 for t in closed)/len(closed)*100,1) if closed else 0
        self.assertEqual(r['win_rate'],expected)


class TrainingChecks(unittest.TestCase):
    def test_per_ticker_targets_and_calendar_purge(self):
        import pandas as pd
        from demo_data import stock
        from models.training_data import labelled_groups,cutoff_date
        frames=[]
        for t in ['INFY.NS','TCS.NS']:
            df=stock(t,'2y');df['Ticker']=t;frames.append(df)
        groups=labelled_groups(pd.concat(frames));cutoff=cutoff_date(groups)
        self.assertEqual(len(groups),2)
        for ticker,frame in groups:
            self.assertEqual(set(frame.Ticker),{ticker})
            training=frame[frame['_target_end']<cutoff]
            validation=frame[frame.index>=cutoff]
            self.assertLess(training['_target_end'].max(),validation.index.min())
    def test_rf_train_and_predict_roundtrip(self):
        from demo_data import stock
        import models.random_forest as rf
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(rf,'MODEL_PATH',str(Path(tmp)/'rf.pkl')),patch.object(rf,'SCALER_PATH',str(Path(tmp)/'scaler.pkl')):
                model,scaler,metrics=rf.train(stock('INFY.NS','2y'))
                result=rf.predict_breakout(stock('INFY.NS','1y'))
                self.assertTrue(0<=result['breakout_probability']<=100)
                self.assertTrue(0<=metrics['auc_roc']<=1)
    def test_rsi_zero_loss_and_flat(self):
        import pandas as pd
        from data.indicators import rsi
        self.assertEqual(rsi(pd.Series(range(40),dtype=float)).iloc[-1],100)
        self.assertEqual(rsi(pd.Series([1.]*40)).iloc[-1],50)

if __name__=='__main__':unittest.main()
