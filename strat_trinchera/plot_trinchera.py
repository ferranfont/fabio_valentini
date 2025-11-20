"""
Plot Trinchera Data
Simple line chart showing close price over time from db_trinchera_all_data.csv
"""

import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from pathlib import Path
import webbrowser
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
PROJECT_ROOT = CURRENT_DIR.parent
DATA_FILE = CURRENT_DIR / "db_trinchera_all_data.csv"
CHARTS_DIR = PROJECT_ROOT / "charts" / "trinchera"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = CHARTS_DIR / "chart_trinchera.html"

print("="*80)
print("TRINCHERA DATA PLOTTER")
print("="*80)

# Load data
print(f"\n[INFO] Loading data from: {DATA_FILE.name}")
df = pd.read_csv(DATA_FILE, sep=';', decimal=',', low_memory=False)
# Strip whitespace from column names
df.columns = df.columns.str.strip()
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.sort_values('timestamp')

print(f"[OK] Loaded {len(df):,} frames (total)")

# Apply time filter if enabled
if FILTER_FROM_14H:
    # Filter by time of day (14:00:00 onwards)
    df = df[df['timestamp'].dt.time >= pd.to_datetime(START_TIME).time()].copy()
    print(f"[INFO] Filter applied: showing only from {START_TIME} onwards")
    print(f"[OK] Filtered to {len(df):,} frames")

print(f"[INFO] Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
print(f"[INFO] Price range: {df['close'].min():.2f} to {df['close'].max():.2f}")

# Load big volume events
BINS_FILE = CURRENT_DIR / "db_trinchera_bins.csv"
big_volume_events = []
df_bins = None
if BINS_FILE.exists():
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
else:
    print(f"\n[WARN] Big volume events file not found: {BINS_FILE.name}")

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
    # Filter df to get only big volume timestamps
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

# Add vertical lines and horizontal timeout lines for big volume events
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

    # Add horizontal timeout lines (orange solid with alpha 0.3)
    for _, row in df_bins.iterrows():
        start_ts = row['start_timestamp']
        end_ts_bigvolume = row['end_timeout_bigvolume']
        end_ts_mean_reversion = row['end_timeout_mean_reversion']
        close_price = row['close']
        mean_level_up = row['mean_level_up']
        mean_level_down = row['mean_level_down']

        # Orange line at close price (uses BIG_VOLUME_TIMEOUT)
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

        # Red line at mean_level_up (above orange line, uses MEAN_REVERSE_TIMEOUT_ORDER)
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

        # Green line at mean_level_down (below orange line, uses MEAN_REVERSE_TIMEOUT_ORDER)
        shapes.append(
            dict(
                type='line',
                x0=start_ts,
                x1=end_ts_mean_reversion,
                y0=mean_level_down,
                y1=mean_level_down,
                yref='y',
                line=dict(color='rgba(0,255,0,0.7)', width=1),
                layer='below'
            )
        )

    print(f"[INFO] Added {len(big_volume_events)} vertical lines for big volume events")
    print(f"[INFO] Added {len(df_bins)} horizontal timeout lines (orange)")
    print(f"[INFO] Added {len(df_bins)} red mean reversion lines (mean_level_up)")
    print(f"[INFO] Added {len(df_bins)} green mean reversion lines (mean_level_down)")

# Update layout
fig.update_layout(
    title='Trinchera - Close Price',
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

# Update x-axis format (no vertical grid, with border)
fig.update_xaxes(
    tickformat='%H:%M:%S',
    showgrid=False,
    showline=True,
    linewidth=1,
    linecolor='rgba(211,211,211,0.6)',
    mirror=True
)

# Update primary y-axis (left - price, horizontal grid only, with border)
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

# Update secondary y-axis (right - volume, no grid, with border)
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
print("[SUCCESS] Chart generation completed!")
print("="*80)
