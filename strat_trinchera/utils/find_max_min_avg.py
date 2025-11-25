"""
Find Max/Min/Avg Price Movement After Orange Dots (Big Volume Events)
Analyzes price displacement in the 3 minutes following each orange dot signal
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Add parent directory to path to import config
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config_trinchera import DATE, BIG_VOLUME_TRIGGER, SMA_PERIOD

# ============================================================================
# CONFIGURATION
# ============================================================================
CURRENT_DIR = Path(__file__).resolve().parent
STRAT_DIR = CURRENT_DIR.parent
OUTPUTS_DIR = STRAT_DIR / "outputs"

ANALYSIS_WINDOW_MINUTES = 3  # Analyze 3 minutes after each orange dot

# Files
DATA_FILE = OUTPUTS_DIR / f"db_trinchera_all_data_{DATE}.csv"
BINS_FILE = OUTPUTS_DIR / f"db_trinchera_bins_{DATE}.csv"

print("=" * 80)
print("ORANGE DOT PRICE MOVEMENT ANALYZER")
print("=" * 80)
print(f"\nDate: {DATE}")
print(f"Analysis window: {ANALYSIS_WINDOW_MINUTES} minutes after each orange dot")
print(f"Big volume trigger: {BIG_VOLUME_TRIGGER} contracts")
print(f"SMA period: {SMA_PERIOD}")

# ============================================================================
# LOAD DATA
# ============================================================================
print("\n" + "=" * 80)
print("LOADING DATA")
print("=" * 80)

# Load main data (tick aggregated data)
if not DATA_FILE.exists():
    print(f"\n[ERROR] Data file not found: {DATA_FILE}")
    exit(1)

print(f"\n[INFO] Loading data: {DATA_FILE.name}")
df = pd.read_csv(DATA_FILE, sep=';', decimal=',', low_memory=False)
df.columns = df.columns.str.strip()
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.sort_values('timestamp').reset_index(drop=True)

print(f"[OK] Loaded {len(df):,} records")
print(f"[INFO] Time range: {df['timestamp'].min()} to {df['timestamp'].max()}")
print(f"[INFO] Price range: {df['close'].min():.2f} to {df['close'].max():.2f}")

# Load big volume events (orange dots)
if not BINS_FILE.exists():
    print(f"\n[ERROR] Big volume events file not found: {BINS_FILE}")
    exit(1)

print(f"\n[INFO] Loading orange dots: {BINS_FILE.name}")
df_bins = pd.read_csv(BINS_FILE, sep=';', decimal=',', low_memory=False)
df_bins.columns = df_bins.columns.str.strip()
df_bins['timestamp'] = pd.to_datetime(df_bins['timestamp'])
df_bins = df_bins.sort_values('timestamp').reset_index(drop=True)

print(f"[OK] Loaded {len(df_bins)} orange dot events")

# ============================================================================
# ANALYZE PRICE MOVEMENT AFTER EACH ORANGE DOT
# ============================================================================
print("\n" + "=" * 80)
print(f"ANALYZING PRICE MOVEMENT ({ANALYSIS_WINDOW_MINUTES} MIN WINDOW)")
print("=" * 80)

results = []

for idx, event in df_bins.iterrows():
    orange_timestamp = event['timestamp']
    orange_price = event['close']
    orange_sma = event['sma']

    # Calculate time window
    end_timestamp = orange_timestamp + pd.Timedelta(minutes=ANALYSIS_WINDOW_MINUTES)

    # Get data in the window
    window_data = df[(df['timestamp'] > orange_timestamp) &
                     (df['timestamp'] <= end_timestamp)]

    if len(window_data) == 0:
        continue

    # Calculate max upward movement (highest high - orange price)
    max_high = window_data['high'].max()
    max_upward_points = max_high - orange_price

    # Calculate max downward movement (orange price - lowest low)
    min_low = window_data['low'].min()
    max_downward_points = orange_price - min_low

    # Determine position relative to SMA
    position_vs_sma = "ABOVE" if orange_price > orange_sma else "BELOW"
    distance_from_sma = abs(orange_price - orange_sma)

    results.append({
        'timestamp': orange_timestamp,
        'orange_price': orange_price,
        'sma': orange_sma,
        'position_vs_sma': position_vs_sma,
        'distance_from_sma': distance_from_sma,
        'max_upward_points': max_upward_points,
        'max_downward_points': max_downward_points,
        'window_records': len(window_data),
        'max_high': max_high,
        'min_low': min_low
    })

# Convert to DataFrame
df_results = pd.DataFrame(results)

# ============================================================================
# STATISTICS
# ============================================================================
print("\n" + "=" * 80)
print("OVERALL STATISTICS")
print("=" * 80)

total_events = len(df_results)
avg_upward = df_results['max_upward_points'].mean()
avg_downward = df_results['max_downward_points'].mean()
max_upward = df_results['max_upward_points'].max()
max_downward = df_results['max_downward_points'].max()
min_upward = df_results['max_upward_points'].min()
min_downward = df_results['max_downward_points'].min()

print(f"\nTotal orange dot events analyzed: {total_events}")
print(f"\nUPWARD MOVEMENT (price going UP after orange dot):")
print(f"  Average max upward: {avg_upward:.2f} points")
print(f"  Max upward observed: {max_upward:.2f} points")
print(f"  Min upward observed: {min_upward:.2f} points")

print(f"\nDOWNWARD MOVEMENT (price going DOWN after orange dot):")
print(f"  Average max downward: {avg_downward:.2f} points")
print(f"  Max downward observed: {max_downward:.2f} points")
print(f"  Min downward observed: {min_downward:.2f} points")

print(f"\nOVERALL AVERAGE DISPLACEMENT:")
print(f"  Average (upward + downward) / 2: {(avg_upward + avg_downward) / 2:.2f} points")

# ============================================================================
# STATISTICS BY SMA POSITION
# ============================================================================
print("\n" + "=" * 80)
print("STATISTICS BY SMA POSITION")
print("=" * 80)

above_sma = df_results[df_results['position_vs_sma'] == 'ABOVE']
below_sma = df_results[df_results['position_vs_sma'] == 'BELOW']

print(f"\nORANGE DOTS ABOVE SMA ({len(above_sma)} events):")
if len(above_sma) > 0:
    print(f"  Avg upward movement: {above_sma['max_upward_points'].mean():.2f} points")
    print(f"  Avg downward movement: {above_sma['max_downward_points'].mean():.2f} points")
    print(f"  Avg distance from SMA: {above_sma['distance_from_sma'].mean():.2f} points")

print(f"\nORANGE DOTS BELOW SMA ({len(below_sma)} events):")
if len(below_sma) > 0:
    print(f"  Avg upward movement: {below_sma['max_upward_points'].mean():.2f} points")
    print(f"  Avg downward movement: {below_sma['max_downward_points'].mean():.2f} points")
    print(f"  Avg distance from SMA: {below_sma['distance_from_sma'].mean():.2f} points")

# ============================================================================
# SAVE DETAILED RESULTS
# ============================================================================
print("\n" + "=" * 80)
print("SAVING RESULTS")
print("=" * 80)

output_file = OUTPUTS_DIR / f"orange_dot_movement_analysis_{DATE}.csv"
df_results.to_csv(output_file, sep=';', decimal=',', index=False)
print(f"\n[OK] Detailed results saved: {output_file.name}")

# ============================================================================
# TOP/BOTTOM EVENTS
# ============================================================================
print("\n" + "=" * 80)
print("TOP 5 EVENTS BY MOVEMENT")
print("=" * 80)

print("\nTOP 5 UPWARD MOVEMENTS:")
top_upward = df_results.nlargest(5, 'max_upward_points')
for idx, row in top_upward.iterrows():
    print(f"  {row['timestamp']} | {row['max_upward_points']:.2f} pts | "
          f"Price: {row['orange_price']:.2f} | {row['position_vs_sma']} SMA")

print("\nTOP 5 DOWNWARD MOVEMENTS:")
top_downward = df_results.nlargest(5, 'max_downward_points')
for idx, row in top_downward.iterrows():
    print(f"  {row['timestamp']} | {row['max_downward_points']:.2f} pts | "
          f"Price: {row['orange_price']:.2f} | {row['position_vs_sma']} SMA")

print("\n" + "=" * 80)
print("[SUCCESS] Analysis completed!")
print("=" * 80)
