"""Build features and labels within each ticker; split on calendar time."""
import numpy as np
import pandas as pd
from data.indicators import compute_all,ML_FEATURES

def labelled_groups(df,future_days=5,threshold=.03):
    groups=[]
    iterable=df.groupby('Ticker',sort=False) if 'Ticker' in df else [('single',df)]
    for ticker,raw in iterable:
        frame=compute_all(raw.sort_index().copy())
        missing=set(ML_FEATURES)-set(frame.columns)
        if missing:raise ValueError('Not enough history to compute all model features.')
        frame['Future_Max']=frame['Close'].rolling(future_days).max().shift(-future_days)
        frame['Future_Return']=frame['Future_Max']/frame['Close']-1
        frame['Label']=(frame['Future_Return']>threshold).astype(int)
        frame['_target_end']=pd.Series(frame.index,index=frame.index).shift(-future_days)
        frame=frame.replace([np.inf,-np.inf],np.nan).dropna(subset=ML_FEATURES+['Future_Return','_target_end'])
        if not frame.empty:groups.append((ticker,frame))
    if not groups:raise ValueError('No usable training rows. Fetch more price history.')
    return groups

def cutoff_date(groups):
    dates=sorted(set(d for _,f in groups for d in f.index))
    if len(dates)<60:raise ValueError('More historical dates are needed for a time-based evaluation.')
    return dates[int(len(dates)*.8)]
