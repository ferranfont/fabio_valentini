import os
import webbrowser
import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))
from config import CHART_WIDTH, CHART_HEIGHT, get_chart_path, DATA_DIR

# ============ CONFIGURATION ============
RESAMPLE_SECONDS = 3  # Resample timeframe: 30, 60, 300, etc. (in seconds)
# =======================================

def plot_30min_data(symbol, timeframe, df):
    """
    Plot 30-minute NQ tick data with candlesticks and volume
    """
    html_path = get_chart_path(symbol, f'30min_{timeframe}')

    # Ensure datetime index
    if not isinstance(df.index, pd.DatetimeIndex):
        df = df.set_index('datetime')

    # Resample tick data to OHLC
    resample_str = f'{RESAMPLE_SECONDS}s' if RESAMPLE_SECONDS < 60 else f'{RESAMPLE_SECONDS//60}min'

    df_resampled = df.resample(resample_str).agg({
        'precio': 'ohlc',
        'volumen': 'sum'
    })

    # Flatten column names
    df_resampled.columns = ['open', 'high', 'low', 'close', 'volume']
    df_resampled = df_resampled.dropna().reset_index()
    df_resampled = df_resampled.rename(columns={'datetime': 'date'})

    df_resampled = df_resampled.sort_values('date')

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.80, 0.20],
        vertical_spacing=0.03,
    )

    # Candlestick chart with black outline
    fig.add_trace(go.Candlestick(
        x=df_resampled['date'],
        open=df_resampled['open'],
        high=df_resampled['high'],
        low=df_resampled['low'],
        close=df_resampled['close'],
        increasing_line_color='rgba(0,0,0,0.95)',
        decreasing_line_color='rgba(0,0,0,0.95)',
        increasing_fillcolor='lime',
        decreasing_fillcolor='red',
        line=dict(width=1),
        name='OHLC'
    ), row=1, col=1)

    # Volume bars
    fig.add_trace(go.Bar(
        x=df_resampled['date'],
        y=df_resampled['volume'],
        marker_color='royalblue',
        marker_line_color='blue',
        marker_line_width=0.4,
        opacity=0.95,
        name='Volume'
    ), row=2, col=1)

    # Determine time format based on resample
    if RESAMPLE_SECONDS < 60:
        tick_format = "%H:%M:%S"
    else:
        tick_format = "%H:%M"

    fig.update_layout(
        dragmode='pan',
        title=f'{symbol} - {resample_str} - 30min session',
        width=CHART_WIDTH,
        height=CHART_HEIGHT,
        margin=dict(l=20, r=20, t=40, b=20),
        font=dict(size=12, color="black"),
        plot_bgcolor='white',
        paper_bgcolor='white',
        showlegend=False,
        template='plotly_white',
        xaxis=dict(
            type='date',
            tickformat=tick_format,
            tickangle=0,
            showgrid=False,
            linecolor='black',
            linewidth=1,
            range=[df_resampled['date'].min(), df_resampled['date'].max()],
            rangeslider=dict(visible=False)
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(128,128,128,0.2)',
            gridwidth=1,
            linecolor='black',
            linewidth=1
        ),
        xaxis2=dict(
            type='date',
            tickformat=tick_format,
            tickangle=45,
            showgrid=False,
            linecolor='black',
            linewidth=1,
            range=[df_resampled['date'].min(), df_resampled['date'].max()]
        ),
        yaxis2=dict(
            showgrid=True,
            gridcolor='rgba(128,128,128,0.1)',
            gridwidth=1,
            linecolor='black',
            linewidth=1
        ),
    )

    fig.write_html(html_path, config={
        "scrollZoom": True,
        "displayModeBar": True,
        "staticPlot": False,
        "toImageButtonOptions": {
            "format": "png",
            "filename": "chart",
            "height": 500,
            "width": 700,
            "scale": 1
        }
    })
    print(f"Chart saved as HTML: '{html_path}'")

    webbrowser.open('file://' + os.path.realpath(html_path))


if __name__ == "__main__":
    symbol = 'NQ'

    # Load tick data
    csv_path = os.path.join(DATA_DIR, 'time_and_sales_nq_30min.csv')

    print(f"\n======================== Loading NQ 30min tick data ===========================")
    print(f"File: {csv_path}")

    # Read CSV with European format
    df = pd.read_csv(csv_path, sep=';', decimal=',')

    # Normalize column names
    df.columns = [col.strip().lower() for col in df.columns]

    # Rename timestamp to datetime
    df = df.rename(columns={'timestamp': 'datetime'})
    df['datetime'] = pd.to_datetime(df['datetime'])

    print(f"Loaded {len(df)} ticks")
    print(f"Period: {df['datetime'].min()} to {df['datetime'].max()}")

    # Show first rows
    print("\nFirst rows:")
    print(df.head())

    # Resample string for display
    resample_str = f'{RESAMPLE_SECONDS}s' if RESAMPLE_SECONDS < 60 else f'{RESAMPLE_SECONDS//60}min'

    print(f"\nGenerating {resample_str} chart...")
    plot_30min_data(symbol, resample_str, df)
