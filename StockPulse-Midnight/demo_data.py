"""Deterministic illustrative data for interface previews, never used in live mode."""
import hashlib
import numpy as np
import pandas as pd

def stock(ticker,period='1y'):
    count={'5d':5,'6mo':130,'1y':260,'2y':520,'3y':780,'5y':1300}.get(period,260)
    # A stable full history keeps the same latest close across all lookbacks.
    rng=np.random.default_rng(int(hashlib.sha256(ticker.encode()).hexdigest()[:8],16))
    base={'RELIANCE.NS':2450,'TCS.NS':3500,'INFY.NS':1450,'HDFCBANK.NS':1600,'ICICIBANK.NS':1200}.get(ticker,1850)
    n=1300;returns=rng.normal(.00012,.012,n);close=base*np.exp(np.cumsum(returns));opening=close*(1+rng.normal(0,.003,n));high=np.maximum(opening,close)*(1+rng.uniform(.002,.012,n));low=np.minimum(opening,close)*(1-rng.uniform(.002,.012,n))
    if ticker in ['^NSEI','^BSESN','^INDIAVIX']:
        target={'^NSEI':24718.60,'^BSESN':81305.12,'^INDIAVIX':12.48}[ticker]
        scale=target/close[-1]
        close*=scale; opening*=scale; high*=scale; low*=scale
    idx=pd.bdate_range(end='2026-10-27',periods=n)
    return pd.DataFrame(dict(Open=opening,High=high,Low=low,Close=close,Volume=rng.integers(200000,7000000,n)),index=idx).tail(count)

def overview():
    result={}
    for name,ticker in [('NIFTY50','^NSEI'),('SENSEX','^BSESN'),('INDIA_VIX','^INDIAVIX')]:
        frame=stock(ticker,'5d')
        result[name]=dict(price=float(frame.Close.iloc[-1]),change_pct=round((float(frame.Close.iloc[-1])/float(frame.Close.iloc[-2])-1)*100,2))
    return result
def movers():
    rows=[]
    for ticker in ['RELIANCE.NS','TCS.NS','INFY.NS','HDFCBANK.NS','ICICIBANK.NS','SBIN.NS','ITC.NS','WIPRO.NS']:
        df=stock(ticker,'5d');rows.append(dict(ticker=ticker,close=float(df.Close.iloc[-1]),change_pct=round((float(df.Close.iloc[-1])/float(df.Close.iloc[-2])-1)*100,2)))
    return {'gainers':sorted([r for r in rows if r['change_pct']>0],key=lambda r:r['change_pct'],reverse=True)[:5],'losers':sorted([r for r in rows if r['change_pct']<0],key=lambda r:r['change_pct'])[:5]}
def analysis(ticker,use_lstm=False):
    return ({'name':{'RELIANCE.NS':'Reliance Industries Limited','TCS.NS':'Tata Consultancy Services Limited','INFY.NS':'Infosys Limited'}.get(ticker,ticker.replace('.NS','')),'sector':'Illustrative sector','industry':'Illustrative industry','market_cap':18000000000000,'pe_ratio':24.3,'pb_ratio':3.1,'week52_high':3100,'week52_low':2100,'eps':85.2,'beta':.9}, {'breakout_probability':67.4,'signal':'BUY'}, {'breakout_probability':62.8,'signal':'BUY'} if use_lstm else None, {'score':.3333,'label':'Positive','confidence':87.2,'details':[dict(headline='Illustrative headline: company reports quarterly results',sentiment='Positive',confidence=89),dict(headline='Illustrative headline: analysts review sector outlook',sentiment='Neutral',confidence=85)]}, {'Vol_Ratio':.19,'RSI':.16,'MACD_Hist':.14,'Dist_SMA20':.12,'ADX':.10,'Return_5d':.09,'BB_Pct':.08,'ATR_Pct':.06})
def screened(exchange='NSE'):
    rows=[]
    for i,t in enumerate(['RELIANCE','TCS','INFY','HDFCBANK','ICICIBANK','SBIN','ITC','WIPRO']):
        ticker=t+('.BO' if exchange=='BSE' else '.NS');df=stock(ticker,'5d');score=round(78.4-i*5.3,1)
        rows.append(dict(ticker=ticker,close=round(float(df.Close.iloc[-1]),2),change_pct=round((float(df.Close.iloc[-1])/float(df.Close.iloc[-2])-1)*100,2),breakout_prob=score,signal='STRONG BUY' if score>70 else 'BUY' if score>55 else 'NEUTRAL' if score>40 else 'SELL',rsi=round(48+i*3.2,1),sentiment='Neutral' if i%2 else 'Positive'))
    return rows
