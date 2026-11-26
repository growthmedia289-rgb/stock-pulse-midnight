import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup
import os, json, hashlib, tempfile, threading
from io import StringIO
_cache_lock = threading.RLock()
from datetime import datetime, timedelta
from config import Config

CACHE_DIR = Config.DATA_CACHE_DIR

def _cache_path(key: str) -> str:
    h = hashlib.md5(key.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{h}.json")

def _load_cache(key: str, max_age_minutes: int = 30):
    try:
        with _cache_lock, open(_cache_path(key)) as handle:
            data = json.load(handle)
        if datetime.utcnow() - datetime.fromisoformat(data['_ts']) < timedelta(minutes=max_age_minutes):
            return data['payload']
    except (OSError,ValueError,KeyError,TypeError):
        pass
    return None

def _save_cache(key: str, payload):
    os.makedirs(CACHE_DIR, exist_ok=True)
    temp_path = None
    try:
        with _cache_lock:
            with tempfile.NamedTemporaryFile(mode='w', dir=CACHE_DIR, delete=False, suffix='.tmp') as handle:
                temp_path = handle.name
                json.dump({'_ts':datetime.utcnow().isoformat(),'payload':payload},handle)
            os.replace(temp_path,_cache_path(key))
    except (OSError, TypeError, ValueError):
        pass
    finally:
        if temp_path and os.path.exists(temp_path):os.unlink(temp_path)

# ─── Stock Data ─────────────────────────────────────────────────────────────

def fetch_stock(ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """Fetch OHLCV data for a single ticker via yFinance."""
    try:
        cache_key = f"prices_{ticker}_{period}_{interval}"
        cached = _load_cache(cache_key, max_age_minutes=5)
        if cached is not None:
            if isinstance(cached, dict) and 'frame' in cached:
                result = pd.read_json(StringIO(cached['frame']), orient="split")
                original_tz = cached.get('timezone')
                if original_tz:
                    result.index = pd.to_datetime(result.index, utc=True).tz_convert(original_tz)
                return result
            # Old caches did not preserve the source timezone. Refetch them.
            cached = None
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval, auto_adjust=True)
        if df.empty:
            raise ValueError(f"No data for {ticker}")
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        df.dropna(inplace=True)
        df.index = pd.to_datetime(df.index)
        _save_cache(cache_key, {"frame": df.to_json(orient="split", date_format="iso"), "timezone": str(df.index.tz) if df.index.tz is not None else None})
        return df
    except Exception as e:
        print(f"[fetcher] Error fetching {ticker}: {e}")
        return pd.DataFrame()

def fetch_stock_info(ticker: str) -> dict:
    """Fetch company info/fundamentals."""
    cache_key = f"info_{ticker}"
    cached = _load_cache(cache_key, max_age_minutes=60)
    if cached is not None:
        return cached
    try:
        info = yf.Ticker(ticker).info
        result = {
            'name':        info.get('longName', ticker),
            'sector':      info.get('sector', 'N/A'),
            'industry':    info.get('industry', 'N/A'),
            'market_cap':  info.get('marketCap', 0),
            'pe_ratio':    info.get('trailingPE', None),
            'pb_ratio':    info.get('priceToBook', None),
            'div_yield':   info.get('dividendYield', None),
            'week52_high': info.get('fiftyTwoWeekHigh', None),
            'week52_low':  info.get('fiftyTwoWeekLow', None),
            'avg_volume':  info.get('averageVolume', None),
            'beta':        info.get('beta', None),
            'eps':         info.get('trailingEps', None),
            'description': info.get('longBusinessSummary', '')[:500],
        }
        _save_cache(cache_key, result)
        return result
    except Exception as e:
        print(f"[fetcher] Info error {ticker}: {e}")
        return {'name': ticker}

def fetch_batch(tickers: list, period: str = "6mo") -> dict:
    """Fetch multiple tickers in batches of 10 to conserve RAM."""
    results = {}
    for i in range(0, len(tickers), 10):
        batch = tickers[i:i+10]
        for t in batch:
            df = fetch_stock(t, period=period)
            if not df.empty:
                results[t] = df
    return results

# ─── News ───────────────────────────────────────────────────────────────────

def fetch_news(ticker: str, max_items: int = 10) -> list:
    """
    Fetch financial news headlines for a ticker.
    Uses Yahoo Finance news API + fallback scraping.
    """
    cache_key = f"news_{ticker}"
    cached = _load_cache(cache_key, max_age_minutes=20)
    if cached is not None:
        return cached[:max_items]

    headlines = []

    # Method 1: yfinance news
    try:
        news = yf.Ticker(ticker).news
        for item in news[:max_items]:
            title = item.get('title') or item.get('content', {}).get('title', '')
            if title:
                headlines.append(title)
    except Exception as e:
        print(f"[fetcher] yfinance news error: {e}")

    # Method 2: Yahoo Finance news scrape (fallback)
    if len(headlines) < 3:
        try:
            base_ticker = ticker.replace('.NS', '').replace('.BO', '')
            url = f"https://finance.yahoo.com/quote/{ticker}/news"
            headers = {'User-Agent': 'Mozilla/5.0'}
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                for h3 in soup.find_all('h3', limit=10):
                    text = h3.get_text(strip=True)
                    if text and len(text) > 20:
                        headlines.append(text)
        except Exception as e:
            print(f"[fetcher] Scrape news error: {e}")

    headlines = list(dict.fromkeys(headlines))[:max_items]  # deduplicate
    _save_cache(cache_key, headlines)
    return headlines

# ─── Market Status ──────────────────────────────────────────────────────────

def get_market_overview() -> dict:
    """Fetch Nifty50, Sensex, and India VIX as market context."""
    indices = {
        'NIFTY50': '^NSEI',
        'SENSEX':  '^BSESN',
        'INDIA_VIX': '^INDIAVIX',
    }
    result = {}
    for name, sym in indices.items():
        try:
            df = fetch_stock(sym, period='5d', interval='1d')
            if not df.empty:
                last   = float(df['Close'].iloc[-1])
                prev   = float(df['Close'].iloc[-2]) if len(df) > 1 else last
                change = round((last - prev) / prev * 100, 2)
                result[name] = {'price': round(last, 2), 'change_pct': change}
            else:
                result[name] = None
        except Exception:
            result[name] = None
    return result
