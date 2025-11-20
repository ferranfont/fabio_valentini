"""
Plot Trinchera Data with Trade Markers
Shows close price with trade entry/exit markers:
- Triangle down (red) = SHORT entry
- Triangle up (green) = LONG entry
- Square open (red) = STOP exit
- Square open (green) = PROFIT exit
- Light grey alpha lines connecting entry to exit
"""

import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from pathlib import Path
import webbrowser
from datetime import datetime
from config_trinchera import BIG_VOLUME_TRIGGER

# ============================================================================
# FILTER CONFIGURATION
# ============================================================================
FILTER_FROM_14H = True  # Set to True to show only data from 14:00:00 onwards
START_TIME = "14:50:00"  # Start time for filtering

# ============================================================================
# CONFIGURATION
# ============================================================================
CURRENT_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = CURRENT_DIR / "outputs"
CHARTS_DIR = CURRENT_DIR / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

# Find most recent all_data file
all_data_files = sorted(OUTPUTS_DIR.glob("db_trinchera_all_data*.csv"))
if not all_data_files:
    raise FileNotFoundError(f"No db_trinchera_all_data file found in {OUTPUTS_DIR}")
DATA_FILE = all_data_files[-1]  # Get most recent

# Find most recent trades file
trades_files = sorted(OUTPUTS_DIR.glob("db_trinchera_TR_*.csv"))
if not trades_files:
    raise FileNotFoundError(f"No trades file found in {OUTPUTS_DIR}")
TRADES_FILE = trades_files[-1]  # Get most recent

# Extract date from trades filename (e.g., db_trinchera_TR_20251022.csv -> 20251022)
import re
date_match = re.search(r'_(\d{8})\.csv', TRADES_FILE.name)
date_str = date_match.group(1) if date_match else datetime.now().strftime("%Y%m%d")
OUTPUT_FILE = CHARTS_DIR / f"chart_trinchera_trades_{date_str}.html"

print("="*80)
print("TRINCHERA TRADES PLOTTER")
print("="*80)

# Load data
print(f"\n[INFO] Loading data from: {DATA_FILE.name}")
df = pd.read_csv(DATA_FILE, sep=';', decimal=',', low_memory=False)
df.columns = df.columns.str.strip()
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.sort_values('timestamp')

print(f"[OK] Loaded {len(df):,} frames (total)")

# Apply time filter if enabled
if FILTER_FROM_14H:
    df = df[df['timestamp'].dt.time >= pd.to_datetime(START_TIME).time()].copy()
    print(f"[INFO] Filter applied: showing only from {START_TIME} onwards")
    print(f"[OK] Filtered to {len(df):,} frames")

print(f"[INFO] Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
print(f"[INFO] Price range: {df['close'].min():.2f} to {df['close'].max():.2f}")

# Load trades
df_trades = None
if TRADES_FILE.exists():
    print(f"\n[INFO] Loading trades from: {TRADES_FILE.name}")
    df_trades = pd.read_csv(TRADES_FILE, sep=';', decimal=',', low_memory=False)
    df_trades.columns = df_trades.columns.str.strip()
    df_trades['entry_time'] = pd.to_datetime(df_trades['entry_time'])
    df_trades['exit_time'] = pd.to_datetime(df_trades['exit_time'])

    print(f"[OK] Loaded {len(df_trades)} trades (total)")

    # Apply time filter to trades if enabled
    if FILTER_FROM_14H:
        df_trades = df_trades[df_trades['entry_time'].dt.time >= pd.to_datetime(START_TIME).time()].copy()
        print(f"[INFO] Filtered trades from {START_TIME} onwards: {len(df_trades)} trades")
else:
    print(f"\n[WARN] Trades file not found: {TRADES_FILE.name}")

# Load big volume events
bins_files = sorted(OUTPUTS_DIR.glob("db_trinchera_bins_*.csv"))
BINS_FILE = bins_files[-1] if bins_files else None
big_volume_events = []
df_bins = None
if BINS_FILE and BINS_FILE.exists():
    print(f"\n[INFO] Loading big volume events from: {BINS_FILE.name}")
    df_bins = pd.read_csv(BINS_FILE, sep=';', decimal=',', low_memory=False)
    df_bins.columns = df_bins.columns.str.strip()
    df_bins['timestamp'] = pd.to_datetime(df_bins['timestamp'])
    df_bins['start_timestamp'] = pd.to_datetime(df_bins['start_timestamp'])
    df_bins['end_timeout_bigvolume'] = pd.to_datetime(df_bins['end_timeout_bigvolume'])
    df_bins['end_timeout_mean_reversion'] = pd.to_datetime(df_bins['end_timeout_mean_reversion'])

    print(f"[OK] Loaded {len(df_bins)} big volume events (total)")

    # Apply time filter to big volume events if enabled
    if FILTER_FROM_14H:
        df_bins = df_bins[df_bins['timestamp'].dt.time >= pd.to_datetime(START_TIME).time()].copy()
        print(f"[INFO] Filtered big volume events from {START_TIME} onwards: {len(df_bins)} events")

    big_volume_events = df_bins['timestamp'].tolist()

# Create figure with secondary y-axis
fig = make_subplots(specs=[[{"secondary_y": True}]])

# Add close price line (blue) on primary y-axis (left)
fig.add_trace(go.Scatter(
    x=df['timestamp'],
    y=df['close'],
    mode='lines',
    name='Close Price',
    line=dict(color='blue', width=1),
    hovertemplate='<b>%{x}</b><br>Close: %{y:.2f}<extra></extra>',
    showlegend=True
), secondary_y=False)

# Add total volume line (orange) on secondary y-axis (right)
fig.add_trace(go.Scatter(
    x=df['timestamp'],
    y=df['total_volume'],
    mode='lines',
    name='Total Volume',
    line=dict(color='orange', width=1),
    hovertemplate='<b>%{x}</b><br>Volume: %{y:.0f}<extra></extra>',
    showlegend=True
), secondary_y=True)

# Add horizontal line for BIG_VOLUME_TRIGGER on secondary y-axis (right)
fig.add_trace(go.Scatter(
    x=[df['timestamp'].min(), df['timestamp'].max()],
    y=[BIG_VOLUME_TRIGGER, BIG_VOLUME_TRIGGER],
    mode='lines',
    name=f'Trigger ({BIG_VOLUME_TRIGGER})',
    line=dict(color='orange', width=1, dash='dot'),
    showlegend=True
), secondary_y=True)

# Add orange dots at big volume events on the close price line
if len(big_volume_events) > 0:
    df_big_volume = df[df['timestamp'].isin(big_volume_events)]

    fig.add_trace(go.Scatter(
        x=df_big_volume['timestamp'],
        y=df_big_volume['close'],
        mode='markers',
        name='Big Volume',
        marker=dict(
            color='orange',
            size=10,
            symbol='circle'
        ),
        showlegend=True
    ), secondary_y=False)

    print(f"[INFO] Added {len(df_big_volume)} orange dots for big volume events")

# Add shapes for big volume events
shapes = []
if len(big_volume_events) > 0 and df_bins is not None:
    # Add vertical lines at big volume events
    for timestamp in big_volume_events:
        shapes.append(
            dict(
                type='line',
                x0=timestamp,
                x1=timestamp,
                y0=0,
                y1=1,
                yref='paper',
                line=dict(color='rgba(211,211,211,0.6)', width=1),
                layer='below'
            )
        )

    # Add horizontal timeout lines
    for _, row in df_bins.iterrows():
        start_ts = row['start_timestamp']
        end_ts_bigvolume = row['end_timeout_bigvolume']
        end_ts_mean_reversion = row['end_timeout_mean_reversion']
        close_price = row['close']
        mean_level_up = row['mean_level_up']
        mean_level_down = row['mean_level_down']

        # Orange line at close price
        shapes.append(
            dict(
                type='line',
                x0=start_ts,
                x1=end_ts_bigvolume,
                y0=close_price,
                y1=close_price,
                yref='y',
                line=dict(color='rgba(255,165,0,0.3)', width=10),
                layer='below'
            )
        )

        # Red line at mean_level_up
        shapes.append(
            dict(
                type='line',
                x0=start_ts,
                x1=end_ts_mean_reversion,
                y0=mean_level_up,
                y1=mean_level_up,
                yref='y',
                line=dict(color='rgba(255,0,0,0.7)', width=1),
                layer='below'
            )
        )

        # Green line at mean_level_down
        shapes.append(
            dict(
                type='line',
                x0=start_ts,
                x1=end_ts_mean_reversion,
                y0=mean_level_down,
                y1=mean_level_down,
                yref='y',
                line=dict(color='rgba(34,139,34,0.7)', width=1),
                layer='below'
            )
        )

# Add trade markers and connection lines
if df_trades is not None and len(df_trades) > 0:
    # Separate trades by direction and exit reason
    buy_trades = df_trades[df_trades['direction'] == 'BUY']
    sell_trades = df_trades[df_trades['direction'] == 'SELL']

    # BUY entries (triangle up, green)
    if len(buy_trades) > 0:
        fig.add_trace(go.Scatter(
            x=buy_trades['entry_time'],
            y=buy_trades['entry_price'],
            mode='markers',
            name='BUY Entry',
            marker=dict(
                color='green',
                size=12,
                symbol='triangle-up',
                line=dict(color='green', width=1)
            ),
            showlegend=True
        ), secondary_y=False)

    # SELL entries (triangle down, red)
    if len(sell_trades) > 0:
        fig.add_trace(go.Scatter(
            x=sell_trades['entry_time'],
            y=sell_trades['entry_price'],
            mode='markers',
            name='SELL Entry',
            marker=dict(
                color='red',
                size=12,
                symbol='triangle-down',
                line=dict(color='red', width=1)
            ),
            showlegend=True
        ), secondary_y=False)

    # Profit exits (square open, green)
    profit_exits = df_trades[df_trades['exit_reason'] == 'profit']
    if len(profit_exits) > 0:
        fig.add_trace(go.Scatter(
            x=profit_exits['exit_time'],
            y=profit_exits['exit_price'],
            mode='markers',
            name='PROFIT Exit',
            marker=dict(
                color='rgba(0,0,0,0)',  # Transparent fill
                size=10,
                symbol='square',
                line=dict(color='green', width=2)
            ),
            showlegend=True
        ), secondary_y=False)

    # Stop exits (square open, red)
    stop_exits = df_trades[df_trades['exit_reason'] == 'stop']
    if len(stop_exits) > 0:
        fig.add_trace(go.Scatter(
            x=stop_exits['exit_time'],
            y=stop_exits['exit_price'],
            mode='markers',
            name='STOP Exit',
            marker=dict(
                color='rgba(0,0,0,0)',  # Transparent fill
                size=10,
                symbol='square',
                line=dict(color='red', width=2)
            ),
            showlegend=True
        ), secondary_y=False)

    # Add connection lines from entry to exit
    for _, trade in df_trades.iterrows():
        # Grey line connecting entry to exit
        shapes.append(
            dict(
                type='line',
                x0=trade['entry_time'],
                x1=trade['exit_time'],
                y0=trade['entry_price'],
                y1=trade['exit_price'],
                yref='y',
                line=dict(color='rgba(128,128,128,0.8)', width=1, dash='dot'),
                layer='below'
            )
        )

    print(f"[INFO] Added {len(buy_trades)} BUY entry markers")
    print(f"[INFO] Added {len(sell_trades)} SELL entry markers")
    print(f"[INFO] Added {len(profit_exits)} PROFIT exit markers")
    print(f"[INFO] Added {len(stop_exits)} STOP exit markers")
    print(f"[INFO] Added {len(df_trades)} connection lines")

# Update layout with shapes
fig.update_layout(
    title='Trinchera - Trades Visualization',
    xaxis_title='',
    yaxis_title='',
    hovermode=False,
    width=1800,
    height=900,
    template='plotly_white',
    showlegend=True,
    legend=dict(
        yanchor="top",
        y=0.99,
        xanchor="left",
        x=0.01
    ),
    shapes=shapes
)

# Update x-axis format
fig.update_xaxes(
    tickformat='%H:%M:%S',
    showgrid=False,
    showline=True,
    linewidth=1,
    linecolor='rgba(211,211,211,0.6)',
    mirror=True
)

# Update primary y-axis (left - price)
fig.update_yaxes(
    showgrid=True,
    gridcolor='rgba(211,211,211,0.1)',
    tickformat='.2f',
    showline=True,
    linewidth=1,
    linecolor='rgba(211,211,211,0.6)',
    mirror=True,
    secondary_y=False
)

# Update secondary y-axis (right - volume)
fig.update_yaxes(
    showgrid=False,
    tickformat='.0f',
    showline=True,
    linewidth=1,
    linecolor='rgba(211,211,211,0.6)',
    mirror=True,
    secondary_y=True
)

# Save to HTML
fig.write_html(str(OUTPUT_FILE))
print(f"\n[OK] Chart saved to: {OUTPUT_FILE.name}")

# Open in browser
webbrowser.open('file://' + str(OUTPUT_FILE.absolute()))
print(f"[OK] Opening chart in browser...")

print("\n" + "="*80)
print("[SUCCESS] Trades visualization completed!")
print("="*80)
