import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / '.env')
BASE_DIR=Path(__file__).resolve().parent
INSTANCE=BASE_DIR/'instance'
INSTANCE.mkdir(exist_ok=True)
# Keep local sessions stable across restarts; never ship an actual secret in a ZIP.
secret_file=INSTANCE/'session.key'
if not os.getenv('SECRET_KEY') and not secret_file.exists():
    import secrets
    secret_file.write_text(secrets.token_hex(32))
class Config:
    SECRET_KEY=os.getenv('SECRET_KEY') or secret_file.read_text().strip()
    SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL','sqlite:///'+str(INSTANCE/'stockpulse.db'))
    SQLALCHEMY_TRACK_MODIFICATIONS=False
    ENABLE_WEB_TRAINING=os.getenv('ENABLE_WEB_TRAINING','0')=='1'
    ADMIN_USER_IDS={int(value.strip()) for value in os.getenv('ADMIN_USER_IDS','').split(',') if value.strip().isdigit()}
    SESSION_COOKIE_SECURE=os.getenv('SESSION_COOKIE_SECURE','0')=='1'
    SESSION_COOKIE_HTTPONLY=True
    SESSION_COOKIE_SAMESITE='Lax'
    MAX_CONTENT_LENGTH=64*1024
    MODEL_DIR=str(BASE_DIR/'saved_models')
    DATA_CACHE_DIR=str(BASE_DIR/'cache')
    NSE_STOCKS=['RELIANCE.NS','TCS.NS','INFY.NS','HDFCBANK.NS','ICICIBANK.NS','HINDUNILVR.NS','BAJFINANCE.NS','SBIN.NS','BHARTIARTL.NS','KOTAKBANK.NS','ITC.NS','WIPRO.NS','HCLTECH.NS','AXISBANK.NS','LT.NS','ASIANPAINT.NS','MARUTI.NS','TITAN.NS','SUNPHARMA.NS','ULTRACEMCO.NS','TECHM.NS','NESTLEIND.NS','POWERGRID.NS','NTPC.NS','ONGC.NS','M&M.NS','TATASTEEL.NS','JSWSTEEL.NS','COALINDIA.NS','DIVISLAB.NS','DRREDDY.NS','CIPLA.NS','APOLLOHOSP.NS','BAJAJFINSV.NS','ADANIPORTS.NS','TATAMOTORS.NS','HEROMOTOCO.NS','EICHERMOT.NS','BPCL.NS','GRASIM.NS','INDUSINDBK.NS','SBILIFE.NS','HDFCLIFE.NS','BRITANNIA.NS','PIDILITIND.NS']
    BSE_STOCKS=['RELIANCE.BO','TCS.BO','INFY.BO','HDFCBANK.BO','ICICIBANK.BO','SBIN.BO','BHARTIARTL.BO','KOTAKBANK.BO','WIPRO.BO','HCLTECH.BO']
for directory in (Config.MODEL_DIR,Config.DATA_CACHE_DIR):
    Path(directory).mkdir(exist_ok=True)
