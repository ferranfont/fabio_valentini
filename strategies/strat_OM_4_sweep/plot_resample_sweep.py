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
VOLUME_THRESHOLD = 50  # Threshold for frequency indicator, es decir, genera vertical line, y la vertical line se computan para los bins
BIN_SIZE = 10  # Bin size in seconds for frequency calculation (more sensitive)
BIN_FILTER = 4  # Minimum frequency to show in table (filters out low-activity bins)
SUPPRESSION_WINDOW_SECONDS = 30  # Group peaks within this window (seconds) and keep only highest

# TREND DETECTION PARAMETERS (HYBRID METHOD: N-periods lookback + ROC)
LOOKBACK_PERIODS = 10  # Compare price with N frames ago (10 frames = 5 seconds at 0.5s/frame)
MIN_CHANGE_POINTS = 3.0  # Minimum price change in points to detect trend
MIN_ROC_PCT = 0.01  # Minimum Rate of Change in % (0.01% ~ 2.5 points on NQ 25000)

# File paths
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parents[1]  # Up 2 levels (strategies -> fabio_valentini)
STRAT_SWEEP_DIR = PROJECT_ROOT / "strat_sweep"
DATA_FILE = STRAT_SWEEP_DIR / "db_mushroom_all_data.csv"
OUTPUT_FILE = PROJECT_ROOT / "charts" / "resample_sweep_chart.html"

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

# Big volume breakdown
big_volume_count = len(df[df['total_volume'] > BIG_VOLUME])
big_bid_count = len(df[df['total_bid'] > 50])
big_ask_count = len(df[df['total_ask'] > 50])
print(f"\n[INFO] Volume Thresholds:")
print(f"  - Big volume (>{BIG_VOLUME}): {big_volume_count:,} frames ({big_volume_count/len(df)*100:.2f}%) [grey lines]")
print(f"  - Big BID (>50): {big_bid_count:,} frames ({big_bid_count/len(df)*100:.2f}%) [red lines]")
print(f"  - Big ASK (>50): {big_ask_count:,} frames ({big_ask_count/len(df)*100:.2f}%) [green lines]")

# ============================================================================
# CALCULATE FREQUENCY INDICATOR (ROLLING WINDOW - CONTINUOUS)
# ============================================================================
print(f"\n[INFO] Calculating CONTINUOUS frequency indicator (ROLLING WINDOW={BIN_SIZE}s)...")

# Mark signals
df['is_bid_signal'] = (df['total_bid'] > VOLUME_THRESHOLD).astype(int)
df['is_ask_signal'] = (df['total_ask'] > VOLUME_THRESHOLD).astype(int)

# Calculate ROLLING frequency (ventana móvil)
# Window size in number of frames: BIN_SIZE seconds / 0.5 seconds per frame
window_frames = int(BIN_SIZE / 0.5)  # 10s / 0.5s = 20 frames

df['freq_bid_rolling'] = df['is_bid_signal'].rolling(window=window_frames, min_periods=1).sum()
df['freq_ask_rolling'] = df['is_ask_signal'].rolling(window=window_frames, min_periods=1).sum()
df['freq_total_rolling'] = df['freq_bid_rolling'] + df['freq_ask_rolling']

print(f"[OK] Calculated CONTINUOUS rolling frequency")
print(f"  - Window size: {BIN_SIZE}s ({window_frames} frames)")
print(f"  - Max TOTAL frequency: {df['freq_total_rolling'].max():.0f} signals per {BIN_SIZE}s")
print(f"  - Avg TOTAL frequency: {df['freq_total_rolling'].mean():.1f} signals per {BIN_SIZE}s")

# ===========================================================================
# CALCULATE HYBRID TREND DETECTION (N-periods lookback + ROC)
# ===========================================================================
print(f"\n[INFO] Calculating HYBRID trend detection (lookback={LOOKBACK_PERIODS} frames, ~{LOOKBACK_PERIODS * 0.5:.0f}s)...")

# Calculate price N periods ago
df['price_N_ago'] = df['close_price'].shift(LOOKBACK_PERIODS)

# Calculate absolute price change in points
df['price_change'] = df['close_price'] - df['price_N_ago']

# Calculate Rate of Change (ROC) in percentage
df['roc_pct'] = (df['price_change'] / df['price_N_ago']) * 100

print(f"[OK] Hybrid trend detection calculated")
print(f"  - Lookback period: {LOOKBACK_PERIODS} frames ({LOOKBACK_PERIODS * 0.5:.0f} seconds)")
print(f"  - Min change threshold: {MIN_CHANGE_POINTS} points")
print(f"  - Min ROC threshold: {MIN_ROC_PCT}%")

# ===========================================================================
# CALCULATE BINS (for trading signals, kept separate)
# ===========================================================================
print(f"\n[INFO] Calculating BINS for trading signals (BIN_SIZE={BIN_SIZE}s)...")

# Create bins
df['bin'] = (df['timestamp'] - df['timestamp'].min()).dt.total_seconds() // BIN_SIZE

# Calculate frequency per bin (for trading signals)
freq_data = df.groupby('bin').agg({
    'timestamp': ['first', 'last'],
    'is_bid_signal': 'sum',
    'is_ask_signal': 'sum',
    'close_price': ['first', 'last'],
    'total_bid': 'max',
    'total_ask': 'max'
}).reset_index()

freq_data.columns = ['bin', 'timestamp_start', 'timestamp_end', 'freq_bid', 'freq_ask',
                     'close_price_start', 'close_price_end', 'max_total_bid', 'max_total_ask']
freq_data['freq_total'] = freq_data['freq_bid'] + freq_data['freq_ask']

# Calculate price direction tag
freq_data['price_tag'] = freq_data.apply(
    lambda row: 'up' if row['close_price_end'] > row['close_price_start']
                else 'down' if row['close_price_end'] < row['close_price_start']
                else 'flat',
    axis=1
)

# Calculate price change in points
freq_data['price_change'] = freq_data['close_price_end'] - freq_data['close_price_start']

print(f"[OK] Created {len(freq_data)} bins for trading signals")
print(f"  - These bins are for TRADING SIGNALS (step-based entries)")
print(f"  - Chart will show CONTINUOUS frequency (smooth line)")

# ===========================================================================
# DETECT PEAK REVERSALS (for trading signals)
# ===========================================================================
print(f"\n[INFO] Detecting frequency PEAKS (reversal points after maximum)...")

# Shift to get previous value
df['freq_total_rolling_prev'] = df['freq_total_rolling'].shift(1)

# Detect peaks: when frequency starts dropping (current < previous)
df['is_peak_reversal'] = (
    (df['freq_total_rolling'] < df['freq_total_rolling_prev']) &  # Frequency dropping
    (df['freq_total_rolling_prev'] >= BIN_FILTER)  # Previous value was significant
)

# Get reversal points
reversal_points = df[df['is_peak_reversal']].copy()

# For each reversal, find the peak value (maximum in the previous window)
peak_signals = []
for idx, row in reversal_points.iterrows():
    # Look back to find the peak (start of decline)
    lookback_start = max(0, idx - window_frames)
    window_data = df.iloc[lookback_start:idx+1]

    # Find maximum frequency in the window
    peak_idx = window_data['freq_total_rolling'].idxmax()
    peak_row = df.loc[peak_idx]

    # ============================================================
    # DETERMINE PRICE TREND USING HYBRID METHOD (N-periods + ROC)
    # ============================================================
    # Use lookback comparison and ROC to detect trend at peak moment
    peak_price = peak_row['close_price']
    peak_change = peak_row['price_change']  # Change vs N periods ago
    peak_roc = peak_row['roc_pct']          # Rate of Change in %

    # Classify trend based on HYBRID criteria (both conditions must be met)
    if peak_change > MIN_CHANGE_POINTS and peak_roc > MIN_ROC_PCT:
        price_tag = 'up'    # Price rising → uptrend → ENTER SHORT (contratrend)
    elif peak_change < -MIN_CHANGE_POINTS and peak_roc < -MIN_ROC_PCT:
        price_tag = 'down'  # Price falling → downtrend → ENTER LONG (contratrend)
    else:
        price_tag = 'flat'  # No clear trend or insufficient movement

    # Calculate percentage deviation for statistics (vs N-periods ago)
    price_N_ago = peak_row['price_N_ago']
    if pd.notna(price_N_ago) and price_N_ago > 0:
        price_deviation_pct = peak_roc / 100  # Convert ROC% to decimal for compatibility
    else:
        price_deviation_pct = 0.0

    # Calculate price change from peak to signal (for statistics)
    price_change = row['close_price'] - peak_row['close_price']

    peak_signals.append({
        # PEAK DATA (momento del máximo)
        'peak_timestamp': peak_row['timestamp'],          # Timestamp at peak
        'peak_freq': int(peak_row['freq_total_rolling']), # Max frequency value (bin máximo)
        'peak_close_price': peak_row['close_price'],      # Price at peak
        'peak_price_N_ago': round(price_N_ago, 2) if pd.notna(price_N_ago) else 0.0,  # Price N periods ago (for trend detection)

        # ENTRY SIGNAL DATA (siguiente tick tras el pico, cuando freq cae)
        'signal_timestamp': row['timestamp'],              # Entry signal timestamp (SEND ORDER HERE)
        'signal_close_price': row['close_price'],          # Entry price (ORDER ENTRY PRICE)

        # FREQUENCY BREAKDOWN (at signal time)
        'freq_bid': int(row['freq_bid_rolling']),          # BID signals at entry
        'freq_ask': int(row['freq_ask_rolling']),          # ASK signals at entry
        'freq_total': int(row['freq_total_rolling']),      # Total signals at entry

        # VOLUME DATA (at signal time)
        'max_total_bid': int(row['total_bid']),            # BID volume at signal
        'max_total_ask': int(row['total_ask']),            # ASK volume at signal

        # PRICE MOVEMENT AND TREND (HYBRID METHOD)
        'price_change': round(price_change, 2),            # Price movement from peak to signal
        'price_change_lookback': round(peak_change, 2) if pd.notna(peak_change) else 0.0,  # Change vs N periods ago
        'roc_pct': round(peak_roc, 4) if pd.notna(peak_roc) else 0.0,  # Rate of Change %
        'price_tag': price_tag,                            # Direction tag based on HYBRID ('up'/'down'/'flat')
        'price_vs_lookback_pct': round(price_deviation_pct * 100, 4),  # % deviation vs N-ago (same as ROC)
    })

# Create DataFrame
peak_signals_df = pd.DataFrame(peak_signals)

print(f"[OK] Detected {len(peak_signals_df)} initial peak reversal signals")
print(f"  - Minimum frequency threshold: {BIN_FILTER}")

# ===========================================================================
# SUPPRESS DUPLICATE PEAKS (KEEP ONLY HIGHEST PEAK IN TIME WINDOW)
# ===========================================================================
if len(peak_signals_df) > 0:
    print(f"\n[INFO] Applying peak suppression (window={SUPPRESSION_WINDOW_SECONDS}s)...")

    # Sort by peak timestamp
    peak_signals_df = peak_signals_df.sort_values('peak_timestamp').reset_index(drop=True)

    # Group peaks that are close in time and keep only the highest
    filtered_peaks = []
    last_peak_time = None
    current_group = []

    for idx, row in peak_signals_df.iterrows():
        current_time = row['peak_timestamp']

        # If this is the first peak or far from the last group
        if last_peak_time is None or (current_time - last_peak_time).total_seconds() > SUPPRESSION_WINDOW_SECONDS:
            # Save previous group (if exists)
            if current_group:
                # Keep the peak with highest frequency
                best_peak = max(current_group, key=lambda x: x['peak_freq'])
                filtered_peaks.append(best_peak)

            # Start new group
            current_group = [row.to_dict()]
            last_peak_time = current_time
        else:
            # Add to current group
            current_group.append(row.to_dict())
            last_peak_time = current_time

    # Don't forget the last group
    if current_group:
        best_peak = max(current_group, key=lambda x: x['peak_freq'])
        filtered_peaks.append(best_peak)

    # Replace with filtered signals
    peak_signals_df = pd.DataFrame(filtered_peaks)
    print(f"[OK] After suppression: {len(peak_signals_df)} unique peak signals (removed {len(peak_signals) - len(peak_signals_df)} duplicates)")
    print(f"  - Signals occur AFTER frequency peaks (entry at reversal start)")

# Show detailed signal breakdown
if len(peak_signals_df) > 0:
    print(f"\n[INFO] Peak Reversal Signals (showing first 50):")
    print("=" * 200)
    print(f"{'Peak Time':<20} {'Peak Freq':<11} {'Signal Time':<20} {'Entry Price':<13} "
          f"{'Price Chg':<12} {'Tag':<6} {'BID':<5} {'ASK':<5} {'MaxBID':<8} {'MaxASK':<8}")
    print("=" * 200)

    for idx, row in peak_signals_df.head(50).iterrows():
        peak_time = str(row['peak_timestamp']).split()[1]
        signal_time = str(row['signal_timestamp']).split()[1]
        print(f"{peak_time:<20} {int(row['peak_freq']):<11} {signal_time:<20} {row['signal_close_price']:<13.2f} "
              f"{row['price_change']:+11.2f}  {row['price_tag']:<6} "
              f"{int(row['freq_bid']):<5} {int(row['freq_ask']):<5} "
              f"{int(row['max_total_bid']):<8} {int(row['max_total_ask']):<8}")

    print("=" * 200)
    print(f"\n[INFO] HYBRID TREND DETECTION METHOD - Using N-periods lookback + ROC for price_tag:")
    print(f"  - Lookback Period: {LOOKBACK_PERIODS} frames ({LOOKBACK_PERIODS * 0.5:.0f} seconds)")
    print(f"  - Min Change: {MIN_CHANGE_POINTS} points")
    print(f"  - Min ROC: {MIN_ROC_PCT}%")
    print(f"  - Logic: If (price_change > {MIN_CHANGE_POINTS} pts AND roc > {MIN_ROC_PCT}%) => 'up' (ENTER SHORT)")
    print(f"           If (price_change < -{MIN_CHANGE_POINTS} pts AND roc < -{MIN_ROC_PCT}%) => 'down' (ENTER LONG)")
    print(f"           Otherwise => 'flat'")
    print(f"\n[INFO] CSV Structure - Column Descriptions:")
    print(f"  - peak_timestamp: Timestamp when frequency reached MAXIMUM (peak)")
    print(f"  - peak_freq: Maximum frequency value (bin máximo)")
    print(f"  - peak_close_price: Close price at peak moment")
    print(f"  - peak_price_N_ago: Price {LOOKBACK_PERIODS} frames ago (USED FOR TREND DETECTION)")
    print(f"  - signal_timestamp: Entry signal timestamp (NEXT TICK after peak, when freq drops)")
    print(f"  - signal_close_price: ORDER ENTRY PRICE (close price at signal moment)")
    print(f"  - freq_bid/freq_ask/freq_total: Frequency components at signal time")
    print(f"  - max_total_bid/max_total_ask: Volume levels at signal time")
    print(f"  - price_change: Price movement from peak to signal")
    print(f"  - price_change_lookback: Price change vs {LOOKBACK_PERIODS} periods ago (in points)")
    print(f"  - roc_pct: Rate of Change % vs {LOOKBACK_PERIODS} periods ago")
    print(f"  - price_tag: TREND DIRECTION based on HYBRID method ('up'/'down'/'flat')")
    print(f"  - price_vs_lookback_pct: % deviation from price N-ago (same as ROC)")

# Export to CSV
csv_output_path = STRAT_SWEEP_DIR / "db_mushroom_bins.csv"
if len(peak_signals_df) > 0:
    peak_signals_df.to_csv(csv_output_path, sep=';', decimal=',', index=False)
    print(f"\n[OK] Peak reversal signals exported to: {csv_output_path.name}")
    print(f"[INFO] Exported {len(peak_signals_df)} signals")

    # Price direction statistics
    price_tag_counts = peak_signals_df['price_tag'].value_counts()
    print(f"\n[INFO] Price Direction Breakdown:")
    for tag, count in price_tag_counts.items():
        avg_change = peak_signals_df[peak_signals_df['price_tag'] == tag]['price_change'].mean()
        print(f"  - {tag.upper()}: {count} signals ({count/len(peak_signals_df)*100:.1f}%) | Avg change: {avg_change:.2f} points")
else:
    print(f"\n[WARN] No peak reversal signals detected with freq >= {BIN_FILTER}")
    print(f"[WARN] CSV not generated. Try lowering BIN_FILTER parameter.")

# Create figure with single subplot (secondary y-axis for frequency)
fig = make_subplots(
    rows=1, cols=1,
    specs=[[{"secondary_y": True}]]
)

# Add close price line (primary y-axis - LEFT)
fig.add_trace(go.Scatter(
    x=df['timestamp'],
    y=df['close_price'],
    mode='lines',
    name='Close Price',
    line=dict(color='blue', width=1),
    hovertemplate='<b>%{x}</b><br>Close Price: %{y:.2f}<extra></extra>',
    showlegend=True
), secondary_y=False)

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
                line=dict(color='rgba(211,211,211,0.3)', width=1),
                layer='below'
            )
        )

# Add vertical RED lines where total_bid > 50
big_bid_df = df[df['total_bid'] > 50].copy()
if len(big_bid_df) > 0:
    for timestamp in big_bid_df['timestamp']:
        shapes.append(
            dict(
                type='line',
                x0=timestamp,
                x1=timestamp,
                y0=0,
                y1=1,
                yref='paper',
                line=dict(color='rgba(255,0,0,0.3)', width=1, dash='solid'),
                layer='below'
            )
        )

# Add vertical GREEN lines where total_ask > 50
big_ask_df = df[df['total_ask'] > 50].copy()
if len(big_ask_df) > 0:
    for timestamp in big_ask_df['timestamp']:
        shapes.append(
            dict(
                type='line',
                x0=timestamp,
                x1=timestamp,
                y0=0,
                y1=1,
                yref='paper',
                line=dict(color='rgba(0,128,0,0.3)', width=1, dash='solid'),
                layer='below'
            )
        )

# Add vertical ORANGE lines at peak_timestamp of each bin (bin peak moments)
if len(peak_signals_df) > 0:
    for timestamp in peak_signals_df['peak_timestamp']:
        shapes.append(
            dict(
                type='line',
                x0=timestamp,
                x1=timestamp,
                y0=0,
                y1=1,
                yref='paper',
                line=dict(color='rgba(255,165,0,0.5)', width=2, dash='solid'),
                layer='above'
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
    ), secondary_y=False)

# Add CONTINUOUS frequency indicator (ORANGE smooth line) (secondary y-axis - RIGHT)
fig.add_trace(go.Scatter(
    x=df['timestamp'],
    y=df['freq_total_rolling'],
    mode='lines',
    name=f'Volume Frequency (Rolling {BIN_SIZE}s)',
    line=dict(color='orange', width=2),  # Smooth line (no 'hv' shape)
    fill='tozeroy',
    fillcolor='rgba(255,165,0,0.1)',
    showlegend=True
), secondary_y=True)

# Update layout
fig.update_layout(
    title=dict(
        text=f'NQ Resampled Price Chart - Mushroom Sweep Analysis<br><sub>{len(df):,} frames | {len(mushroom_df)} Mushroom patterns | {len(big_volume_df)} Big Volume (>{BIG_VOLUME})</sub>',
        x=0.5,
        xanchor='center',
        font=dict(size=18, color='black')
    ),
    width=2000,
    height=800,
    plot_bgcolor='white',
    paper_bgcolor='white',
    hovermode=False,
    dragmode='pan',
    showlegend=True,
    legend=dict(
        orientation="v",
        yanchor="top",
        y=0.98,
        xanchor="left",
        x=0.01,
        bgcolor='rgba(255,255,255,0.9)',
        bordercolor='black',
        borderwidth=1,
        font=dict(size=11)
    ),
    shapes=shapes  # Add all vertical lines at once
)

# Update x-axis
fig.update_xaxes(
    title='Timestamp',
    showgrid=False,
    linecolor='black',
    linewidth=1
)

# Primary y-axis (LEFT) - Price
fig.update_yaxes(
    title='Close Price (NQ)',
    showgrid=True,
    gridcolor='rgba(128,128,128,0.2)',
    linecolor='black',
    linewidth=1,
    secondary_y=False
)

# Secondary y-axis (RIGHT) - Frequency
fig.update_yaxes(
    title=f'Frequency (signals per {BIN_SIZE}s)',
    showgrid=False,
    linecolor='orange',
    linewidth=1,
    secondary_y=True
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
