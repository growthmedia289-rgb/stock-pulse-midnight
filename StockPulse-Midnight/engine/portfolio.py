"""
Portfolio tracking and analytics module.
"""
import pandas as pd
import numpy as np
from data.fetcher import fetch_stock


def get_current_price(ticker: str) -> float:
    """Fetch latest close price for a ticker."""
    df = fetch_stock(ticker, period='5d', interval='1d')
    if df.empty:
        return None
    return float(df['Close'].iloc[-1])


def get_portfolio_summary(holdings: list) -> dict:
    """
    holdings: list of dicts with keys:
        ticker, buy_price, quantity, company
    Returns comprehensive portfolio summary.
    """
    if not holdings:
        return {
            'total_invested': 0, 'current_value': 0,
            'total_pnl': 0, 'total_pnl_pct': 0,
            'holdings': []
        }

    enriched    = []
    total_invested = 0.0
    current_value  = 0.0

    for h in holdings:
        ticker     = h['ticker']
        buy_price  = float(h['buy_price'])
        qty        = float(h['quantity'])
        cur_price  = get_current_price(ticker)

        invested   = buy_price * qty
        if cur_price is None:
            raise ValueError(f'Latest price unavailable for {ticker}; no valuation was calculated.')
        cur_val    = cur_price * qty
        pnl        = cur_val - invested
        pnl_pct    = (pnl / invested * 100) if invested > 0 else 0.0

        total_invested += invested
        current_value  += cur_val

        enriched.append({
            'ticker':      ticker,
            'company':     h.get('company', ticker),
            'qty':         qty,
            'buy_price':   round(buy_price, 2),
            'cur_price':   round(cur_price, 2),
            'invested':    round(invested, 2),
            'cur_value':   round(cur_val, 2),
            'pnl':         round(pnl, 2),
            'pnl_pct':     round(pnl_pct, 2),
            'weight_pct':  0.0,   # will be filled below
        })

    total_pnl     = current_value - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0

    # Portfolio weights
    for h in enriched:
        h['weight_pct'] = round(h['cur_value'] / current_value * 100, 1) \
                          if current_value > 0 else 0.0

    # Sort by allocation
    enriched.sort(key=lambda x: x['cur_value'], reverse=True)

    return {
        'total_invested':  round(total_invested, 2),
        'current_value':   round(current_value, 2),
        'total_pnl':       round(total_pnl, 2),
        'total_pnl_pct':   round(total_pnl_pct, 2),
        'holdings':        enriched,
        'num_holdings':    len(enriched),
        'best_performer':  max(enriched, key=lambda x: x['pnl_pct'])['ticker'] if enriched else '',
        'worst_performer': min(enriched, key=lambda x: x['pnl_pct'])['ticker'] if enriched else '',
    }


def get_portfolio_chart_data(holdings: list) -> dict:
    """Return allocation pie chart data and 30-day PnL line data."""
    labels  = [h['ticker'] for h in holdings]
    values  = [h['cur_value'] for h in holdings]
    pnls    = [h['pnl_pct'] for h in holdings]

    return {
        'pie': {'labels': labels, 'values': values},
        'bar': {'labels': labels, 'pnl_pcts': pnls},
    }


def check_watchlist_alerts(watchlist: list) -> list:
    """
    Check if any watchlist stocks have hit their alert prices.
    watchlist: list of {ticker, alert_price}
    """
    alerts = []
    for item in watchlist:
        ticker      = item['ticker']
        alert_price = item.get('alert_price')
        if alert_price is None or alert_price <= 0:
            continue
        cur = get_current_price(ticker)
        if cur is not None and cur > 0 and abs(cur - alert_price) / alert_price < 0.005:
            alerts.append({
                'ticker':      ticker,
                'alert_price': alert_price,
                'cur_price':   round(cur, 2),
                'message':     f"{ticker} is near your alert price ₹{alert_price:.2f}!",
            })
    return alerts
