"""
Historical backtesting engine.
Tests RF + threshold-based strategies on past data.
"""
import pandas as pd
import numpy as np
from data.indicators import compute_all


# ─── Strategy Definitions ────────────────────────────────────────────────────

def strategy_rsi(df: pd.DataFrame, oversold=30, overbought=70) -> pd.Series:
    """RSI mean-reversion strategy."""
    sig = pd.Series(0, index=df.index)
    sig[df['RSI'] < oversold]  =  1   # buy
    sig[df['RSI'] > overbought] = -1  # sell
    return sig


def strategy_macd(df: pd.DataFrame) -> pd.Series:
    """MACD crossover strategy."""
    sig = pd.Series(0, index=df.index)
    cross_up   = (df['MACD'] > df['MACD_Signal']) & (df['MACD'].shift(1) <= df['MACD_Signal'].shift(1))
    cross_down = (df['MACD'] < df['MACD_Signal']) & (df['MACD'].shift(1) >= df['MACD_Signal'].shift(1))
    sig[cross_up]   =  1
    sig[cross_down] = -1
    return sig


def strategy_bb(df: pd.DataFrame) -> pd.Series:
    """Bollinger Band breakout strategy."""
    sig = pd.Series(0, index=df.index)
    sig[df['Close'] < df['BB_Lower']] =  1
    sig[df['Close'] > df['BB_Upper']] = -1
    return sig


def strategy_supertrend(df: pd.DataFrame) -> pd.Series:
    """SuperTrend trend-following strategy."""
    sig = pd.Series(0, index=df.index)
    sig[df['ST_Bull'] == True]  =  1
    sig[df['ST_Bull'] == False] = -1
    return sig


def strategy_combined(df: pd.DataFrame) -> pd.Series:
    """Multi-indicator combined strategy."""
    rsi_sig = strategy_rsi(df)
    macd_sig = strategy_macd(df)
    st_sig   = strategy_supertrend(df)
    combined = rsi_sig + macd_sig + st_sig
    sig = pd.Series(0, index=df.index)
    sig[combined >= 2]  =  1
    sig[combined <= -2] = -1
    return sig


STRATEGIES = {
    'RSI':         strategy_rsi,
    'MACD':        strategy_macd,
    'Bollinger':   strategy_bb,
    'SuperTrend':  strategy_supertrend,
    'Combined':    strategy_combined,
}


# ─── Core Backtest Engine ────────────────────────────────────────────────────

def backtest(df,strategy_name='Combined',initial_capital=100000.0,position_size=.95,stop_loss_pct=.05,take_profit_pct=.10,commission=.001):
    if initial_capital<=0 or not 0<position_size<=1 or not 0<stop_loss_pct<1 or take_profit_pct<=0 or not 0<=commission<1:return {'error':'Invalid simulation settings.'}
    df=compute_all(df.copy())
    if df.empty or len(df)<50:return {'error':'At least 50 daily bars are needed for backtesting.'}
    if strategy_name not in STRATEGIES:return {'error':'Unknown strategy.'}
    signals=STRATEGIES[strategy_name](df);signals.iloc[:29]=0;cash=float(initial_capital);shares=0.;entry=0.;entry_fee=0.;stop=0.;target=0.;trades=[];equity=[cash]
    def exit_position(i,action):
        nonlocal cash,shares
        price=float(df.Close.iloc[i]);fee=commission*price*shares;pnl=(price-entry)*shares-fee-entry_fee;cash+=shares*price-fee
        trades.append(dict(date=str(df.index[i].date()),action=action,price=round(price,2),pnl=round(pnl,2)))
        shares=0.
    for i in range(1,len(df)):
        price=float(df.Close.iloc[i]);signal=signals.iloc[i-1];exited=False
        if shares>0:
            action='STOP LOSS' if price<=stop else 'TAKE PROFIT' if price>=target else 'SELL' if signal==-1 else None
            if action:exit_position(i,action);exited=True
        if signal==1 and shares==0 and not exited:
            investment=cash*position_size;shares=investment/(price*(1+commission));entry=price;entry_fee=shares*price*commission;cash-=investment;stop=price*(1-stop_loss_pct);target=price*(1+take_profit_pct)
            trades.append(dict(date=str(df.index[i].date()),action='BUY',price=round(price,2),pnl=None))
        equity.append(cash+shares*price)
    if shares>0:exit_position(len(df)-1,'FINAL EXIT');equity[-1]=cash
    closed=[t for t in trades if t['pnl'] is not None];wins=sum(t['pnl']>0 for t in closed);losses=sum(t['pnl']<0 for t in closed)
    series=pd.Series(equity,dtype=float);returns=series.pct_change().dropna();std=returns.std();sharpe=float(returns.mean()/std*np.sqrt(252)) if std>0 else 0.
    return dict(strategy=strategy_name,initial_capital=initial_capital,final_capital=round(cash,2),total_return_pct=round((cash/initial_capital-1)*100,2),buy_hold_return=round((float(df.Close.iloc[-1])/float(df.Close.iloc[0])-1)*100,2),sharpe_ratio=round(sharpe,3),max_drawdown_pct=round(float(((series-series.cummax())/series.cummax()*100).min()),2),total_trades=len(closed),win_rate=round(wins/len(closed)*100,1) if closed else 0.,winning_trades=wins,losing_trades=losses,equity_curve=[dict(date=str(df.index[i].date()),equity=round(float(e),2)) for i,e in enumerate(equity)],trades=trades)

def compare_strategies(df,initial_capital=100000,**settings):
    results=[]
    for name in STRATEGIES:
        result=backtest(df,strategy_name=name,initial_capital=initial_capital,**settings)
        if 'error' not in result:results.append({key:result[key] for key in ['strategy','total_return_pct','sharpe_ratio','max_drawdown_pct','win_rate','total_trades']})
    return sorted(results,key=lambda r:r['total_return_pct'],reverse=True)
