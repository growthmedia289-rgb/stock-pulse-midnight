
import pandas as pd
import numpy as np

# ─── Individual Indicators ───────────────────────────────────────────────────

def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=1).mean()

def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta  = series.diff()
    gain   = delta.clip(lower=0).rolling(period).mean()
    loss   = (-delta.clip(upper=0)).rolling(period).mean()
    rs     = gain / loss.replace(0, np.nan)
    result = 100 - (100 / (1 + rs))
    result = result.mask((loss == 0) & (gain > 0), 100.0)
    result = result.mask((gain == 0) & (loss > 0), 0.0)
    return result.mask((gain == 0) & (loss == 0), 50.0)

def macd(series: pd.Series, fast=12, slow=26, signal=9):
    ema_fast   = ema(series, fast)
    ema_slow   = ema(series, slow)
    macd_line  = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram  = macd_line - signal_line
    return macd_line, signal_line, histogram

def bollinger_bands(series: pd.Series, window=20, num_std=2):
    mid  = sma(series, window)
    std  = series.rolling(window).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return upper, mid, lower

def atr(high: pd.Series, low: pd.Series, close: pd.Series, period=14) -> pd.Series:
    hl  = high - low
    hpc = (high - close.shift()).abs()
    lpc = (low  - close.shift()).abs()
    tr  = pd.concat([hl, hpc, lpc], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def stochastic(high: pd.Series, low: pd.Series, close: pd.Series, k=14, d=3):
    low_min  = low.rolling(k).min()
    high_max = high.rolling(k).max()
    stoch_k  = 100 * (close - low_min) / (high_max - low_min).replace(0, np.nan)
    stoch_d  = stoch_k.rolling(d).mean()
    return stoch_k, stoch_d

def adx(high: pd.Series, low: pd.Series, close: pd.Series, period=14) -> pd.Series:
    up_move   = high.diff()
    down_move = -low.diff()

    plus_dm  = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    atr_val  = atr(high, low, close, period)
    plus_di  = 100 * pd.Series(plus_dm,  index=high.index).rolling(period).mean() / atr_val
    minus_di = 100 * pd.Series(minus_dm, index=high.index).rolling(period).mean() / atr_val

    dx   = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    adx_ = dx.rolling(period).mean()
    return adx_, plus_di, minus_di

def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
    typical = (high + low + close) / 3
    return (typical * volume).cumsum() / volume.cumsum()

def supertrend(high: pd.Series, low: pd.Series, close: pd.Series,
               period=10, multiplier=3.0):
    atr_val = atr(high, low, close, period)
    hl2     = (high + low) / 2

    upper_band = hl2 + multiplier * atr_val
    lower_band = hl2 - multiplier * atr_val

    supertrend_arr = [True] * len(close)
    for i in range(1, len(close)):
        if close.iloc[i] > upper_band.iloc[i-1]:
            supertrend_arr[i] = True
        elif close.iloc[i] < lower_band.iloc[i-1]:
            supertrend_arr[i] = False
        else:
            supertrend_arr[i] = supertrend_arr[i-1]

    st_series = pd.Series(supertrend_arr, index=close.index)
    st_line   = pd.Series(
        [lower_band.iloc[i] if supertrend_arr[i] else upper_band.iloc[i]
         for i in range(len(close))],
        index=close.index
    )
    return st_series, st_line

def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = close.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    return (volume * direction).cumsum()

def williams_r(high: pd.Series, low: pd.Series, close: pd.Series, period=14) -> pd.Series:
    highest = high.rolling(period).max()
    lowest  = low.rolling(period).min()
    return -100 * (highest - close) / (highest - lowest).replace(0, np.nan)

# ─── Master Computation ──────────────────────────────────────────────────────

def compute_all(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or len(df) < 30:
        return df

    df = df.copy()

    # ✅ FIX: force Series
    close = df['Close'].squeeze()

    df['SMA_20']  = sma(close, 20)
    df['SMA_50']  = sma(close, 50)
    df['SMA_200'] = sma(close, 200)
    df['EMA_9']   = ema(close, 9)
    df['EMA_21']  = ema(close, 21)

    df['RSI'] = rsi(close, 14)

    df['MACD'], df['MACD_Signal'], df['MACD_Hist'] = macd(close)

    df['BB_Upper'], df['BB_Mid'], df['BB_Lower'] = bollinger_bands(close)
    df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / df['BB_Mid']

    bb_denom = (df['BB_Upper'] - df['BB_Lower']).replace(0, np.nan)
    df['BB_Pct'] = (close - df['BB_Lower']) / bb_denom

    df['ATR'] = atr(df['High'], df['Low'], close)
    df['ATR_Pct'] = df['ATR'] / close * 100

    df['Stoch_K'], df['Stoch_D'] = stochastic(df['High'], df['Low'], close)

    df['ADX'], df['Plus_DI'], df['Minus_DI'] = adx(df['High'], df['Low'], close)

    df['VWAP'] = vwap(df['High'], df['Low'], close, df['Volume'])

    df['ST_Bull'], df['ST_Line'] = supertrend(df['High'], df['Low'], close)

    df['OBV'] = obv(close, df['Volume'])

    df['Williams_R'] = williams_r(df['High'], df['Low'], close)

    df['Vol_SMA_20']  = sma(df['Volume'], 20)
    df['Vol_Ratio']   = df['Volume'] / df['Vol_SMA_20']

    df['Return_1d']  = close.pct_change(1)
    df['Return_5d']  = close.pct_change(5)
    df['Return_20d'] = close.pct_change(20)
    df['High_Low_Pct'] = (df['High'] - df['Low']) / df['Low'] * 100

    df['Dist_SMA20']  = (close - df['SMA_20'])  / df['SMA_20'] * 100
    df['Dist_SMA50']  = (close - df['SMA_50'])  / df['SMA_50'] * 100
    df['Dist_SMA200'] = (close - df['SMA_200']) / df['SMA_200'] * 100

    df['Above_SMA20']  = (close > df['SMA_20']).astype(int)
    df['Above_SMA50']  = (close > df['SMA_50']).astype(int)
    df['Golden_Cross'] = ((df['SMA_50'] > df['SMA_200']) &
                          (df['SMA_50'].shift(1) <= df['SMA_200'].shift(1))).astype(int)
    df['Death_Cross']  = ((df['SMA_50'] < df['SMA_200']) &
                          (df['SMA_50'].shift(1) >= df['SMA_200'].shift(1))).astype(int)

    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    return df


ML_FEATURES = [
    'RSI', 'MACD', 'MACD_Hist', 'MACD_Signal',
    'BB_Pct', 'BB_Width',
    'Stoch_K', 'Stoch_D',
    'ADX', 'Plus_DI', 'Minus_DI',
    'ATR_Pct',
    'Vol_Ratio',
    'Dist_SMA20', 'Dist_SMA50',
    'Return_1d', 'Return_5d',
    'Williams_R',
    'Above_SMA20', 'Above_SMA50',
]