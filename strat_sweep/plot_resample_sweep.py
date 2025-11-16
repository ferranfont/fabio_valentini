"""
Resample Sweep Data Plotter
Creates a line chart showing resampled close price over time from db_mushroom_all_data.csv
"""

import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from pathlib import Path
import webbrowser
import os

# ============================================================================
# CONFIGURATION VARIABLES
# ============================================================================
BIG_VOLUME = 90  # Volume threshold for red dots
WAIT_TIME_CUM_VOL = 15  # Seconds to wait before resetting accumulator
MIN_CUMULATIVE_VOLUME = 300  # Minimum cumulative volume to consider reset event valid
SMA_PERIOD = 200  # Period for moving average to determine price direction

# File paths
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
DATA_FILE = CURRENT_DIR / "db_mushroom_all_data.csv"
OUTPUT_FILE = PROJECT_ROOT / "charts" / "resample_sweep_chart.html"
BINS_OUTPUT_FILE = CURRENT_DIR / "db_mushroom_bins.csv"

print("="*80)
print("RESAMPLE SWEEP DATA PLOTTER")
print("="*80)

# Load data
print(f"\n[INFO] Loading data from: {DATA_FILE.name}")
df = pd.read_csv(DATA_FILE, sep=';', decimal=',')
# Strip whitespace from column names and string values
df.columns = df.columns.str.strip()
df['pattern_tag'] = df['pattern_tag'].str.strip()
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.sort_values('timestamp')

print(f"[OK] Loaded {len(df):,} frames")
print(f"[INFO] Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
print(f"[INFO] Price range: {df['close_price'].min():.2f} to {df['close_price'].max():.2f}")

# Pattern breakdown
pattern_counts = df['pattern_tag'].value_counts()
print(f"\n[INFO] Pattern breakdown:")
for pattern, count in pattern_counts.items():
    print(f"  - {pattern}: {count:,} frames ({count/len(df)*100:.2f}%)")

# Calculate total_bid_ask (sum of BID and ASK volumes)
df['total_bid_ask'] = df['total_bid'] + df['total_ask']

# Calculate SMA for price direction labeling
print(f"\n[INFO] Calculating SMA{SMA_PERIOD} for price direction...")
df['sma'] = df['close_price'].rolling(window=SMA_PERIOD, min_periods=1).mean()

# ============================================================================
# CALCULATE CUMULATIVE BID+ASK VOLUME INDICATOR
# ============================================================================
from datetime import timedelta

cum_vol = 0
last_event_timestamp = None
cum_results = []
reset_events = []  # Track full reset event data

print(f"\n[INFO] Calculating cumulative BID+ASK volume indicator...")
print(f"  - Timeout: {WAIT_TIME_CUM_VOL} seconds")
print(f"  - Big volume threshold: >{BIG_VOLUME}")
print(f"  - Minimum cumulative volume: >={MIN_CUMULATIVE_VOLUME}")

for idx, row in df.iterrows():
    current_time = row['timestamp']
    current_total_bid_ask = row['total_bid_ask']
    current_price = row['close_price']
    is_big_volume = row['total_volume'] > BIG_VOLUME

    # STEP 1: Check for TIMEOUT (reset to 0 immediately when timeout is reached)
    if last_event_timestamp is not None:
        timeout_moment = last_event_timestamp + timedelta(seconds=WAIT_TIME_CUM_VOL)

        if current_time >= timeout_moment:
            # TIMEOUT: Reset immediately
            # Record the reset moment with ALL relevant data (only if cumulative volume >= minimum threshold)
            if cum_vol >= MIN_CUMULATIVE_VOLUME:
                current_sma = row['sma']
                price_tag = 'up' if current_price > current_sma else 'down'

                reset_events.append({
                    'reset_timestamp': current_time,
                    'reset_price': current_price,
                    'cumulative_volume_before_reset': cum_vol,
                    'total_bid': row['total_bid'],
                    'total_ask': row['total_ask'],
                    'total_bid_ask': current_total_bid_ask,
                    'total_volume': row['total_volume'],
                    'pattern_tag': row['pattern_tag'],
                    'sma': current_sma,
                    'price_tag': price_tag
                })

            cum_vol = 0
            last_event_timestamp = None

    # STEP 2: Detect new big volume event (grey vertical line)
    if is_big_volume:
        # ACCUMULATE the BID+ASK volume from this peak
        cum_vol += current_total_bid_ask

        # RENEW the timeout (extends the accumulation window)
        last_event_timestamp = current_time

    # STEP 3: Store current accumulator value for this frame
    cum_results.append(cum_vol)

# Add to dataframe
df['cum_bid_ask_vol'] = cum_results

# Create DataFrame with reset events
df_reset_events = pd.DataFrame(reset_events)

print(f"[OK] Cumulative indicator calculated")
print(f"  - Max accumulated value: {df['cum_bid_ask_vol'].max():.0f}")
print(f"  - Frames with accumulation > 0: {(df['cum_bid_ask_vol'] > 0).sum():,}")
print(f"  - Reset events detected: {len(reset_events)}")

# Save reset events to CSV (European format)
if len(reset_events) > 0:
    df_reset_events.to_csv(BINS_OUTPUT_FILE, sep=';', decimal=',', index=False)
    print(f"\n[OK] Reset events saved to: {BINS_OUTPUT_FILE.name}")
    print(f"  - Columns: {', '.join(df_reset_events.columns)}")
else:
    print(f"\n[WARN] No reset events detected - CSV not created")

# Big volume breakdown
big_volume_count = len(df[df['total_volume'] > BIG_VOLUME])
big_bid_ask_count = len(df[df['total_bid_ask'] > 100])
print(f"\n[INFO] Big Volume (>{BIG_VOLUME}):")
print(f"  - Frames with big volume: {big_volume_count:,} ({big_volume_count/len(df)*100:.2f}%)")
print(f"  - Frames with BID+ASK>100: {big_bid_ask_count:,} ({big_bid_ask_count/len(df)*100:.2f}%)")

# Create figure with 2 subplots (price chart + cumulative indicator)
fig = make_subplots(
    rows=2, cols=1,
    specs=[
        [{"secondary_y": True}],  # Row 1: Price & Volumes
        [{"secondary_y": False}]  # Row 2: Cumulative Indicator
    ],
    vertical_spacing=0.08,
    row_heights=[0.75, 0.25]  # More space for price chart, less for indicator
)

# Add close price line (primary y-axis)
fig.add_trace(go.Scatter(
    x=df['timestamp'],
    y=df['close_price'],
    mode='lines',
    name='Close Price',
    line=dict(color='blue', width=1),
    hovertemplate='<b>%{x}</b><br>Close Price: %{y:.2f}<extra></extra>',
    showlegend=True
), row=1, col=1, secondary_y=False)

# Add big volume markers (VERTICAL LIGHT GREY LINES)
big_volume_df = df[df['total_volume'] > BIG_VOLUME].copy()
shapes = []
if len(big_volume_df) > 0:
    # Create shapes list for all vertical lines (much faster than individual vlines)
    for timestamp in big_volume_df['timestamp']:
        shapes.append(
            dict(
                type='line',
                x0=timestamp,
                x1=timestamp,
                y0=0,
                y1=1,
                yref='paper',  # Use paper coordinates for y (0 to 1 = full height)
                line=dict(color='lightgrey', width=1),
                layer='below'
            )
        )

# Add mushroom pattern markers (MAGENTA dots) (primary y-axis)
mushroom_df = df[df['pattern_tag'] == 'mushroom']
if len(mushroom_df) > 0:
    fig.add_trace(go.Scatter(
        x=mushroom_df['timestamp'],
        y=mushroom_df['close_price'],
        mode='markers',
        name='Mushroom Pattern',
        marker=dict(
            color='magenta',
            size=10,
            symbol='circle',
            line=dict(color='black', width=1)
        ),
        hovertemplate='<b>Mushroom</b><br>%{x}<br>Price: %{y:.2f}<extra></extra>',
        showlegend=True
    ), row=1, col=1, secondary_y=False)

# Add RESET markers (ORANGE dots with DARK ORANGE outline) on price chart when cumulative indicator resets to 0
if len(reset_events) > 0:
    fig.add_trace(go.Scatter(
        x=df_reset_events['reset_timestamp'],
        y=df_reset_events['reset_price'],
        mode='markers',
        name='Cumulative Reset',
        marker=dict(
            color='orange',
            size=8,  # Smaller size
            symbol='circle',
            line=dict(color='darkorange', width=2)  # Dark orange outline
        ),
        hovertemplate='<b>RESET</b><br>%{x}<br>Price: %{y:.2f}<extra></extra>',
        showlegend=True
    ), row=1, col=1, secondary_y=False)

# Add total_bid_ask line (BID + ASK volumes) (secondary y-axis - RIGHT)
fig.add_trace(go.Scatter(
    x=df['timestamp'],
    y=df['total_bid_ask'],
    mode='lines',
    name='BID + ASK Volume',
    line=dict(color='darkorange', width=1.5),
    showlegend=True
), row=1, col=1, secondary_y=True)

# Add total_bid line (RED - secondary y-axis)
fig.add_trace(go.Scatter(
    x=df['timestamp'],
    y=df['total_bid'],
    mode='lines',
    name='Total BID',
    line=dict(color='red', width=1.2),
    hovertemplate='<b>BID</b><br>%{x}<br>Volume: %{y:.0f}<extra></extra>',
    showlegend=True
), row=1, col=1, secondary_y=True)

# Add total_ask line (GREEN - secondary y-axis)
fig.add_trace(go.Scatter(
    x=df['timestamp'],
    y=df['total_ask'],
    mode='lines',
    name='Total ASK',
    line=dict(color='green', width=1.2),
    hovertemplate='<b>ASK</b><br>%{x}<br>Volume: %{y:.0f}<extra></extra>',
    showlegend=True
), row=1, col=1, secondary_y=True)

# ============================================================================
# SUBPLOT 2: CUMULATIVE BID+ASK VOLUME INDICATOR
# ============================================================================
fig.add_trace(go.Scatter(
    x=df['timestamp'],
    y=df['cum_bid_ask_vol'],
    mode='lines',
    name='Cumulative Volume',
    line=dict(color='blueviolet', width=2),
    fill='tozeroy',
    fillcolor='rgba(138,43,226,0.2)',
    hovertemplate='<b>Cumulative Vol</b><br>%{x}<br>Value: %{y:.0f}<extra></extra>',
    showlegend=True
), row=2, col=1)

# Add vertical grey lines to subplot 2 as well
shapes_subplot2 = []
if len(big_volume_df) > 0:
    for timestamp in big_volume_df['timestamp']:
        shapes_subplot2.append(
            dict(
                type='line',
                x0=timestamp,
                x1=timestamp,
                y0=0,
                y1=1,
                yref='y2',  # Reference to subplot 2 y-axis
                xref='x2',  # Reference to subplot 2 x-axis
                line=dict(color='lightgrey', width=1),
                layer='below'
            )
        )

# Update layout
fig.update_layout(
    title=dict(
        text='NQ Resampled Price Chart - Mushroom Sweep Analysis with Cumulative Indicator',
        x=0.5,
        xanchor='center',
        font=dict(size=18, color='black')
    ),
    width=1800,  # Wider
    height=850,  # Less height (more compact)
    plot_bgcolor='white',
    paper_bgcolor='white',
    hovermode=False,
    dragmode='pan',
    showlegend=True,
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="center",
        x=0.5
    ),
    shapes=shapes + shapes_subplot2,  # Combine both shapes lists
    annotations=[]  # Remove subplot titles
)

# Update x-axis for subplot 1 (Price chart)
fig.update_xaxes(
    showgrid=False,
    linecolor='black',
    linewidth=1,
    row=1, col=1
)

# Update x-axis for subplot 2 (Cumulative indicator) - SYNCHRONIZED with subplot 1
fig.update_xaxes(
    showgrid=False,
    linecolor='black',
    linewidth=1,
    matches='x',  # Synchronize with x-axis of subplot 1
    row=2, col=1
)

# Subplot 1 - Primary y-axis (left) - Price
fig.update_yaxes(
    title='Close Price (NQ)',
    showgrid=True,
    gridcolor='rgba(128,128,128,0.2)',
    linecolor='black',
    linewidth=1,
    row=1, col=1,
    secondary_y=False
)

# Subplot 1 - Secondary y-axis (right) - Volume
fig.update_yaxes(
    title='Volume',
    showgrid=False,
    linecolor='black',
    linewidth=1,
    row=1, col=1,
    secondary_y=True
)

# Subplot 2 - Y-axis (Cumulative Volume)
fig.update_yaxes(
    title='Cumulative Volume',
    showgrid=True,
    gridcolor='rgba(128,128,128,0.2)',
    linecolor='black',
    linewidth=1,
    row=2, col=1
)

# Save chart
OUTPUT_FILE.parent.mkdir(exist_ok=True)
fig.write_html(
    str(OUTPUT_FILE),
    config={
        "scrollZoom": True,
        "displayModeBar": True,
        "modeBarButtonsToRemove": ['lasso2d', 'select2d']
    }
)

print(f"\n[OK] Chart saved: {OUTPUT_FILE}")

# Open in browser
webbrowser.open('file://' + os.path.realpath(str(OUTPUT_FILE)))
print(f"[OK] Chart opened in browser")

print("\n" + "="*80)
print("COMPLETED")
print("="*80)
