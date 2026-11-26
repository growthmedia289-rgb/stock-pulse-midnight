"""Audit the exact delivered ZIP, using controlled provider failures."""
import sys,os,unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch,Mock
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'tests'));sys.path.insert(0,str(root))
import test_flows as original
import app as web
from demo_data import stock
from database.models import Watchlist
import pandas as pd

class ExtendedChecks(unittest.TestCase):
    def setUp(self):
        self.helper=original.Flows();self.helper.setUp();self.c=self.helper.c
        self.helper.auth();self.real=patch.object(web,'DEMO',False);self.real.start()
        self.addCleanup(self.real.stop)
    def post(self,url,data=None,**kw):return self.helper.post(url,data,**kw)
    def test_dashboard_provider_outage(self):
        with patch('data.fetcher.get_market_overview',return_value={}),patch('app.prices',return_value=pd.DataFrame()):
            r=self.c.get('/dashboard');self.assertEqual(r.status_code,200);self.assertIn(b'Unavailable',r.data)
    def test_analysis_empty_prices(self):
        with patch('app.prices',return_value=pd.DataFrame()):
            r=self.c.get('/analyze?ticker=INFY');self.assertEqual(r.status_code,200);self.assertIn(b'No price history',r.data)
    def test_analysis_untrained_models(self):
        with patch('app.prices',return_value=stock('INFY.NS')),patch('app.models_ready',return_value={'rf':False,'lstm':False}),patch('data.fetcher.fetch_stock_info',return_value={'name':'Infosys'}),patch('data.fetcher.fetch_news',return_value=[]):
            r=self.post('/analyze',{'ticker':'INFY','period':'1y','use_lstm':'on'});self.assertEqual(r.status_code,200);self.assertIn(b'not trained',r.data);self.assertIn(b'Price action',r.data)
    def test_analysis_corrupt_rf_model_graceful(self):
        with patch('app.prices',return_value=stock('INFY.NS')),patch('app.models_ready',return_value={'rf':True,'lstm':False}),patch('models.random_forest.predict_breakout',side_effect=ValueError('corrupt model')),patch('data.fetcher.fetch_stock_info',return_value={}),patch('data.fetcher.fetch_news',return_value=[]):
            r=self.c.get('/analyze?ticker=INFY');self.assertEqual(r.status_code,200);self.assertIn(b'could not score',r.data);self.assertIn(b'Price action',r.data)
    def test_analysis_bad_ticker(self):
        r=self.c.get('/analyze?ticker=<script>alert(1)</script>');self.assertEqual(r.status_code,200);self.assertNotIn(b'<script>alert(1)</script>',r.data)
    def test_analysis_bad_history(self):
        r=self.c.get('/analyze?ticker=INFY&period=100y');self.assertEqual(r.status_code,200);self.assertIn(b'supported history',r.data)
    def test_screener_missing_rf(self):
        with patch('app.models_ready',return_value={'rf':False,'lstm':False}):
            r=self.post('/screener',{'exchange':'NSE','min_prob':'0','signal':'ALL'});self.assertEqual(r.status_code,200);self.assertIn(b'Train Random Forest',r.data)
    def test_screener_nan_rejected(self):
        r=self.post('/screener',{'min_prob':'NaN'});self.assertEqual(r.status_code,200);self.assertIn(b'between 0 and 100',r.data)
    def test_portfolio_nonfinite_rejected(self):
        for value in ['NaN','inf','-1','0','not-a-number']:
            self.post('/portfolio',{'action':'add','ticker':'INFY','quantity':value,'buy_price':'100'})
        with web.app.app_context():self.assertEqual(web.Portfolio.query.count(),0)
    def test_watchlist_zero_target_rejected(self):
        self.post('/watchlist',{'action':'add','ticker':'INFY','alert_price':'0'})
        with web.app.app_context():self.assertEqual(Watchlist.query.count(),0)
    def test_watchlist_foreign_delete_denied(self):
        self.post('/watchlist',{'action':'add','ticker':'INFY'})
        with web.app.app_context():wid=Watchlist.query.first().id
        self.post('/logout');self.helper.auth('other')
        self.assertEqual(self.post('/watchlist',{'action':'delete','watchlist_id':str(wid)}).status_code,404)
    def test_bad_backtest_capital(self):
        r=self.post('/backtest',{'ticker':'INFY','capital':'0'});self.assertEqual(r.status_code,200);self.assertIn(b'Starting capital',r.data)
    def test_backtest_provider_outage(self):
        with patch('app.prices',return_value=pd.DataFrame()):
            r=self.post('/backtest',{'ticker':'INFY'});self.assertEqual(r.status_code,200);self.assertIn(b'No historical prices',r.data)
    def test_chat_missing_key(self):
        with patch.dict(os.environ,{'GEMINI_API_KEY':'','GEMINI_MODEL':''}):
            r=self.c.post('/api/chat',json={'message':'Explain RSI'},headers={'X-CSRF-Token':self.helper.token()});self.assertEqual(r.status_code,503);self.assertIn('not configured',r.json['error'])
    def test_chat_invalid_payload(self):
        token=self.helper.token()
        for data in [None,[],{'message':3},{'message':' '},{'message':'x'*4001}]:
            r=self.c.post('/api/chat',json=data,headers={'X-CSRF-Token':token});self.assertEqual(r.status_code,400)
    def test_api_requires_login(self):
        self.post('/logout');token=self.helper.token()
        self.assertEqual(self.c.post('/api/chat',json={'message':'Hi'},headers={'X-CSRF-Token':token}).status_code,401)
    def test_logout_requires_csrf(self):
        self.assertEqual(self.c.get('/logout').status_code,405)
        self.c.post('/logout',data={})
        self.assertEqual(self.c.get('/portfolio').status_code,200)
    def test_open_redirect_blocked(self):
        self.post('/logout');r=self.post('/login?next=https://evil.example',{'username':'tester','password':'testpass123'});self.assertEqual(r.location,'/dashboard')
    def test_404_uses_branded_page(self):
        r=self.c.get('/no-such-page');self.assertEqual(r.status_code,404);self.assertIn(b'StockPulse',r.data)
    def test_archived_assets_exist(self):
        for url in ['/static/css/style.css','/static/js/main.js','/static/vendor/plotly.min.js','/static/favicon.svg']:self.assertEqual(self.c.get(url).status_code,200)
    def test_cache_preserves_indian_trading_date(self):
        import data.fetcher as fetcher
        idx=pd.date_range('2026-10-20',periods=5,tz='Asia/Kolkata')
        frame=pd.DataFrame({'Open':100.,'High':101.,'Low':99.,'Close':100.,'Volume':1000},index=idx)
        with tempfile.TemporaryDirectory() as tmp,patch.object(fetcher,'CACHE_DIR',tmp),patch.object(fetcher.yf,'Ticker') as ticker:
            ticker.return_value.history.return_value=frame
            first=fetcher.fetch_stock('INFY.NS','5d');cached=fetcher.fetch_stock('INFY.NS','5d')
            self.assertEqual(list(first.index.date),list(cached.index.date))
    def test_training_is_restricted_to_authorised_operators(self):
        # A public deployment must not let every new user overwrite global models.
        sentinel=Mock(return_value=(object(),object(),{'accuracy':.6,'auc_roc':.65}))
        with patch('models.random_forest.train_on_multiple',sentinel):
            r=self.post('/train')
            self.assertEqual(r.status_code,403,'Any registered account can launch global training; admin-only protection is missing.')
            sentinel.assert_not_called()

    def test_authorised_training_requires_both_flags(self):
        with web.app.app_context():uid=web.User.query.filter_by(username='tester').first().id
        sentinel=Mock(return_value=(object(),object(),{'accuracy':.6,'auc_roc':.65}))
        with patch.dict(web.app.config,{'ENABLE_WEB_TRAINING':True,'ADMIN_USER_IDS':{uid}}),patch('models.random_forest.train_on_multiple',sentinel):
            self.assertEqual(self.post('/train').status_code,302)
            sentinel.assert_called_once()
        with patch.dict(web.app.config,{'ENABLE_WEB_TRAINING':False,'ADMIN_USER_IDS':{uid}}),patch('models.random_forest.train_on_multiple',sentinel):
            self.assertEqual(self.post('/train').status_code,403)
    def test_lstm_training_ordinary_user_denied(self):
        self.assertEqual(self.post('/train_lstm').status_code,403)

if __name__=='__main__':unittest.main(verbosity=2)
