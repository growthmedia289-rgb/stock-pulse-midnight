import json
import plotly.graph_objects as go
import plotly.utils

def build_candlestick(df, ticker='Stock'):
    """Build Plotly candlestick chart JSON."""
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df.index.astype(str),
        open=df['Open'], high=df['High'],
        low=df['Low'],   close=df['Close'],
        name=ticker, increasing_line_color='#26a69a',
        decreasing_line_color='#ef5350'
    ))
    if 'SMA_20' in df.columns:
        fig.add_trace(go.Scatter(x=df.index.astype(str), y=df['SMA_20'],
                                  name='SMA 20', line=dict(color='#ffa726', width=1)))
    if 'SMA_50' in df.columns:
        fig.add_trace(go.Scatter(x=df.index.astype(str), y=df['SMA_50'],
                                  name='SMA 50', line=dict(color='#42a5f5', width=1)))
    if 'BB_Upper' in df.columns:
        fig.add_trace(go.Scatter(x=df.index.astype(str), y=df['BB_Upper'],
                                  name='BB Upper', line=dict(color='rgba(150,150,150,0.5)',
                                  width=1, dash='dot')))
        fig.add_trace(go.Scatter(x=df.index.astype(str), y=df['BB_Lower'],
                                  name='BB Lower', line=dict(color='rgba(150,150,150,0.5)',
                                  width=1, dash='dot'),
                                  fill='tonexty', fillcolor='rgba(150,150,150,0.05)'))

    fig.update_layout(
        template='plotly_dark', xaxis_rangeslider_visible=False,
        height=450, margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation='h', y=1.02)
    )
    return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)


def build_indicator_chart(df):
    """Build RSI + MACD subplot chart."""
    from plotly.subplots import make_subplots
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.6, 0.4])

    fig.add_trace(go.Scatter(x=df.index.astype(str), y=df['RSI'],
                              name='RSI', line=dict(color='#ab47bc')), row=1, col=1)
    fig.add_hline(y=70, line_color='red',   line_dash='dash', row=1, col=1)
    fig.add_hline(y=30, line_color='green', line_dash='dash', row=1, col=1)

    fig.add_trace(go.Bar(x=df.index.astype(str), y=df['MACD_Hist'],
                          name='MACD Hist',
                          marker_color=['#26a69a' if v >= 0 else '#ef5350'
                                        for v in df['MACD_Hist'].fillna(0)]),
                  row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index.astype(str), y=df['MACD'],
                              name='MACD', line=dict(color='#42a5f5')), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index.astype(str), y=df['MACD_Signal'],
                              name='Signal', line=dict(color='#ffa726')), row=2, col=1)

    fig.update_layout(template='plotly_dark', height=380,
                      margin=dict(l=10, r=10, t=20, b=10),
                      legend=dict(orientation='h', y=1.05))
    return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)


