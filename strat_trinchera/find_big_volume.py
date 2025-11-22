"""
Find Big Volume Events
Detects frames with volume above threshold and creates db_trinchera_bins.csv
"""

import pandas as pd
from pathlib import Path
import sys

# Get BIG_VOLUME_TRIGGER from command line argument or use default from config
try:
    from config_trinchera import BIG_VOLUME_TRIGGER as DEFAULT_TRIGGER, BIG_VOLUME_TIMEOUT, MEAN_REVERS_EXPAND, MEAN_REVERSE_TIMEOUT_ORDER, FILTER_USE_GRID, GRID_MEAN_REVERS_EXPAND, GRID_TP_POINTS, GRID_SL_POINTS, DATE
except ImportError:
    DEFAULT_TRIGGER = 300
    BIG_VOLUME_TIMEOUT = 10
    MEAN_REVERS_EXPAND = 10
    MEAN_REVERSE_TIMEOUT_ORDER = 1
    FILTER_USE_GRID = False
    GRID_MEAN_REVERS_EXPAND = 5.0
    GRID_TP_POINTS = 10.0
    GRID_SL_POINTS = 3.0
    DATE = "20251104"

# Check if BIG_VOLUME_TRIGGER was passed as command line argument
if len(sys.argv) > 1:
    BIG_VOLUME_TRIGGER = int(sys.argv[1])
else:
    BIG_VOLUME_TRIGGER = DEFAULT_TRIGGER

# ============================================================================
# CONFIGURATION
# ============================================================================
CURRENT_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = CURRENT_DIR / "outputs"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# Use DATE from config
DATA_FILE = OUTPUTS_DIR / f"db_trinchera_all_data_{DATE}.csv"
OUTPUT_FILE = OUTPUTS_DIR / f"db_trinchera_bins_{DATE}.csv"

print("="*80)
print("BIG VOLUME DETECTOR")
print("="*80)
print(f"\nConfiguration:")
print(f"  - Big Volume Trigger: {BIG_VOLUME_TRIGGER}")
print(f"  - Big Volume Timeout: {BIG_VOLUME_TIMEOUT} minutes")
print(f"  - Mean Reversion Expand: {MEAN_REVERS_EXPAND} points")
print(f"  - Mean Reversion Timeout Order: {MEAN_REVERSE_TIMEOUT_ORDER} minutes")

# Load data
print(f"\n[INFO] Loading data from: {DATA_FILE.name}")
df = pd.read_csv(DATA_FILE, sep=';', decimal=',', low_memory=False)
# Strip whitespace from column names
df.columns = df.columns.str.strip()
df['timestamp'] = pd.to_datetime(df['timestamp'])

print(f"[OK] Loaded {len(df):,} frames")
print(f"[INFO] Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")

# Detect big volume events
print(f"\n[INFO] Detecting big volume events (volume > {BIG_VOLUME_TRIGGER})...")
df['big_volume'] = df['total_volume'] > BIG_VOLUME_TRIGGER

# Filter only big volume events
big_volume_df = df[df['big_volume'] == True].copy()

print(f"[OK] Detected {len(big_volume_df):,} big volume events ({len(big_volume_df)/len(df)*100:.2f}% of all frames)")

# Calculate end_timeout_bigvolume (start_timestamp + BIG_VOLUME_TIMEOUT minutes)
from datetime import timedelta
big_volume_df['start_timestamp'] = big_volume_df['timestamp']
big_volume_df['end_timeout_bigvolume'] = big_volume_df['start_timestamp'] + timedelta(minutes=BIG_VOLUME_TIMEOUT)

print(f"[INFO] Added timeout window: {BIG_VOLUME_TIMEOUT} minutes per event")

# Calculate mean reversion levels (close price +/- MEAN_REVERS_EXPAND)
# If GRID is enabled, adjust levels to account for second entry distance
if FILTER_USE_GRID:
    # Lines should be drawn at MEAN_REVERS_EXPAND + GRID_MEAN_REVERS_EXPAND
    big_volume_df['mean_level_up'] = big_volume_df['close'] + MEAN_REVERS_EXPAND + GRID_MEAN_REVERS_EXPAND
    big_volume_df['mean_level_down'] = big_volume_df['close'] - MEAN_REVERS_EXPAND - GRID_MEAN_REVERS_EXPAND
    print(f"[INFO] GRID ENABLED: Lines drawn at {MEAN_REVERS_EXPAND} + {GRID_MEAN_REVERS_EXPAND} = {MEAN_REVERS_EXPAND + GRID_MEAN_REVERS_EXPAND} points from close price")
else:
    big_volume_df['mean_level_up'] = big_volume_df['close'] + MEAN_REVERS_EXPAND
    big_volume_df['mean_level_down'] = big_volume_df['close'] - MEAN_REVERS_EXPAND
    print(f"[INFO] Added mean reversion levels: +/- {MEAN_REVERS_EXPAND} points from close price")

big_volume_df['end_timeout_mean_reversion'] = big_volume_df['start_timestamp'] + timedelta(minutes=MEAN_REVERSE_TIMEOUT_ORDER)
print(f"[INFO] Added mean reversion timeout: {MEAN_REVERSE_TIMEOUT_ORDER} minutes per event")

# Select relevant columns for output
output_columns = [
    'timestamp',
    'start_timestamp',
    'end_timeout_bigvolume',
    'end_timeout_mean_reversion',
    'big_volume',
    'total_volume',
    'total_bid',
    'total_ask',
    'bid_ask_ratio',
    'num_levels_moved',
    'close',
    'mean_level_up',
    'mean_level_down',
    'open',
    'high',
    'low',
    'price_change',
    'price_change_pct',
    'num_price_levels',
    'price_range',
    'poc_price',
    'poc_volume',
    'profile_bid_volume',
    'profile_ask_volume',
    'profile_total_volume',
    'profile_bid_ask_ratio',
    'tick_count',
    'sma'
]

# Create output DataFrame with selected columns
bins_df = big_volume_df[output_columns].copy()

# Save to CSV
bins_df.to_csv(OUTPUT_FILE, index=False, sep=';', decimal=',')

print(f"\n[OK] Big volume events saved to: {OUTPUT_FILE.name}")
print(f"[INFO] Exported {len(bins_df)} events")

# Statistics
print("\n" + "="*80)
print("BIG VOLUME STATISTICS")
print("="*80)
print(f"Total events detected: {len(bins_df):,}")
print(f"Average volume: {bins_df['total_volume'].mean():.2f}")
print(f"Max volume: {bins_df['total_volume'].max():.2f}")
print(f"Min volume: {bins_df['total_volume'].min():.2f}")
print(f"Average BID: {bins_df['total_bid'].mean():.2f}")
print(f"Average ASK: {bins_df['total_ask'].mean():.2f}")
print(f"Average BID/ASK ratio: {bins_df['bid_ask_ratio'].mean():.2f}")
print(f"Average price change: {bins_df['price_change'].mean():.2f} points")
print(f"Average num levels moved: {bins_df['num_levels_moved'].mean():.2f}")
print(f"Average price levels: {bins_df['num_price_levels'].mean():.2f}")

# Volume distribution
print(f"\n[INFO] Volume distribution:")
volume_ranges = [
    (300, 500),
    (500, 1000),
    (1000, 2000),
    (2000, 5000),
    (5000, float('inf'))
]

for min_vol, max_vol in volume_ranges:
    if max_vol == float('inf'):
        count = len(bins_df[bins_df['total_volume'] >= min_vol])
        label = f"  - {min_vol}+"
    else:
        count = len(bins_df[(bins_df['total_volume'] >= min_vol) & (bins_df['total_volume'] < max_vol)])
        label = f"  - {min_vol}-{max_vol}"

    pct = count / len(bins_df) * 100 if len(bins_df) > 0 else 0
    print(f"{label}: {count:,} events ({pct:.1f}%)")

# BID vs ASK dominance
bid_dominant = len(bins_df[bins_df['bid_ask_ratio'] > 1])
ask_dominant = len(bins_df[bins_df['bid_ask_ratio'] < 1])
balanced = len(bins_df[bins_df['bid_ask_ratio'] == 1])

print(f"\n[INFO] BID/ASK dominance:")
print(f"  - BID dominant (ratio > 1): {bid_dominant:,} events ({bid_dominant/len(bins_df)*100:.1f}%)")
print(f"  - ASK dominant (ratio < 1): {ask_dominant:,} events ({ask_dominant/len(bins_df)*100:.1f}%)")
print(f"  - Balanced (ratio = 1): {balanced:,} events ({balanced/len(bins_df)*100:.1f}%)")

# Price movement analysis
price_up = len(bins_df[bins_df['price_change'] > 0])
price_down = len(bins_df[bins_df['price_change'] < 0])
price_flat = len(bins_df[bins_df['price_change'] == 0])

print(f"\n[INFO] Price movement during big volume:")
print(f"  - Price UP: {price_up:,} events ({price_up/len(bins_df)*100:.1f}%)")
print(f"  - Price DOWN: {price_down:,} events ({price_down/len(bins_df)*100:.1f}%)")
print(f"  - Price FLAT: {price_flat:,} events ({price_flat/len(bins_df)*100:.1f}%)")

print("\n" + "="*80)
print("[SUCCESS] Big volume detection completed!")
print("="*80)
