"""
Find Max/Min/Avg Price Movement After Orange Dots - ALL DATES
Analyzes price displacement in the 3 minutes following each orange dot signal
Processes ALL dates in data/historic/ folder and aggregates results
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys
import re

# Add parent directory to path to import config
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config_trinchera import BIG_VOLUME_TRIGGER, SMA_PERIOD

# ============================================================================
# CONFIGURATION
# ============================================================================
CURRENT_DIR = Path(__file__).resolve().parent
STRAT_DIR = CURRENT_DIR.parent
PROJECT_ROOT = STRAT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data" / "historic"

ANALYSIS_WINDOW_MINUTES = 3  # Analyze 3 minutes after each orange dot

print("=" * 80)
print("ORANGE DOT PRICE MOVEMENT ANALYZER - ALL DATES")
print("=" * 80)
print(f"\nAnalysis window: {ANALYSIS_WINDOW_MINUTES} minutes after each orange dot")
print(f"Big volume trigger: {BIG_VOLUME_TRIGGER} contracts")
print(f"SMA period: {SMA_PERIOD}")
print(f"\nData directory: {DATA_DIR}")

# ============================================================================
# FIND ALL CSV FILES
# ============================================================================
print("\n" + "=" * 80)
print("FINDING CSV FILES")
print("=" * 80)

if not DATA_DIR.exists():
    print(f"\n[ERROR] Data directory not found: {DATA_DIR}")
    exit(1)

# Find all CSV files matching pattern time_and_sales_nq_YYYYMMDD.csv
csv_files = sorted(DATA_DIR.glob("time_and_sales_nq_*.csv"))

if not csv_files:
    print(f"\n[ERROR] No CSV files found in: {DATA_DIR}")
    exit(1)

# Extract dates from filenames
dates = []
for csv_file in csv_files:
    match = re.search(r'time_and_sales_nq_(\d{8})\.csv', csv_file.name)
    if match:
        dates.append(match.group(1))

print(f"\n[OK] Found {len(dates)} dates to process:")
print(f"     From: {min(dates)} to {max(dates)}")

# ============================================================================
# PROCESS EACH DATE
# ============================================================================
print("\n" + "=" * 80)
print("PROCESSING ALL DATES")
print("=" * 80)

all_results = []
dates_processed = 0
dates_skipped = 0

for date in dates:
    print(f"\n[INFO] Processing date: {date}...", end=" ")

    # Look for the bins file in iter/iter summary outputs/{date}/
    bins_file = STRAT_DIR / "iter" / "iter summary outputs" / date / f"db_trinchera_bins_{date}.csv"
    data_file = STRAT_DIR / "iter" / "iter summary outputs" / date / f"db_trinchera_all_data_{date}.csv"

    # If not found in iter outputs, try main outputs folder
    if not bins_file.exists():
        bins_file = STRAT_DIR / "outputs" / f"db_trinchera_bins_{date}.csv"
        data_file = STRAT_DIR / "outputs" / f"db_trinchera_all_data_{date}.csv"

    if not bins_file.exists() or not data_file.exists():
        print(f"[SKIP] Missing files")
        dates_skipped += 1
        continue

    try:
        # Load data
        df = pd.read_csv(data_file, sep=';', decimal=',', low_memory=False)
        df.columns = df.columns.str.strip()
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp').reset_index(drop=True)

        # Load big volume events
        df_bins = pd.read_csv(bins_file, sep=';', decimal=',', low_memory=False)
        df_bins.columns = df_bins.columns.str.strip()
        df_bins['timestamp'] = pd.to_datetime(df_bins['timestamp'])
        df_bins = df_bins.sort_values('timestamp').reset_index(drop=True)

        num_events = len(df_bins)

        # Analyze each orange dot
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

            all_results.append({
                'date': date,
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

        print(f"[OK] {num_events} events")
        dates_processed += 1

    except Exception as e:
        print(f"[ERROR] {e}")
        dates_skipped += 1
        continue

# ============================================================================
# AGGREGATE STATISTICS
# ============================================================================
print("\n" + "=" * 80)
print("OVERALL STATISTICS - ALL DATES COMBINED")
print("=" * 80)

if not all_results:
    print("\n[ERROR] No data to analyze!")
    exit(1)

# Convert to DataFrame
df_results = pd.DataFrame(all_results)

print(f"\nDates processed: {dates_processed}")
print(f"Dates skipped: {dates_skipped}")
print(f"Total orange dot events analyzed: {len(df_results):,}")

avg_upward = df_results['max_upward_points'].mean()
avg_downward = df_results['max_downward_points'].mean()
max_upward = df_results['max_upward_points'].max()
max_downward = df_results['max_downward_points'].max()
min_upward = df_results['max_upward_points'].min()
min_downward = df_results['max_downward_points'].min()
median_upward = df_results['max_upward_points'].median()
median_downward = df_results['max_downward_points'].median()

print(f"\nUPWARD MOVEMENT (price going UP after orange dot):")
print(f"  Average max upward: {avg_upward:.2f} points")
print(f"  Median max upward: {median_upward:.2f} points")
print(f"  Max upward observed: {max_upward:.2f} points")
print(f"  Min upward observed: {min_upward:.2f} points")

print(f"\nDOWNWARD MOVEMENT (price going DOWN after orange dot):")
print(f"  Average max downward: {avg_downward:.2f} points")
print(f"  Median max downward: {median_downward:.2f} points")
print(f"  Max downward observed: {max_downward:.2f} points")
print(f"  Min downward observed: {min_downward:.2f} points")

print(f"\nOVERALL AVERAGE DISPLACEMENT:")
print(f"  Average (upward + downward) / 2: {(avg_upward + avg_downward) / 2:.2f} points")
print(f"  Median (upward + downward) / 2: {(median_upward + median_downward) / 2:.2f} points")

# ============================================================================
# STATISTICS BY SMA POSITION
# ============================================================================
print("\n" + "=" * 80)
print("STATISTICS BY SMA POSITION - ALL DATES")
print("=" * 80)

above_sma = df_results[df_results['position_vs_sma'] == 'ABOVE']
below_sma = df_results[df_results['position_vs_sma'] == 'BELOW']

print(f"\nORANGE DOTS ABOVE SMA ({len(above_sma):,} events, {len(above_sma)/len(df_results)*100:.1f}%):")
if len(above_sma) > 0:
    print(f"  Avg upward movement: {above_sma['max_upward_points'].mean():.2f} points")
    print(f"  Avg downward movement: {above_sma['max_downward_points'].mean():.2f} points")
    print(f"  Median upward movement: {above_sma['max_upward_points'].median():.2f} points")
    print(f"  Median downward movement: {above_sma['max_downward_points'].median():.2f} points")
    print(f"  Avg distance from SMA: {above_sma['distance_from_sma'].mean():.2f} points")

print(f"\nORANGE DOTS BELOW SMA ({len(below_sma):,} events, {len(below_sma)/len(df_results)*100:.1f}%):")
if len(below_sma) > 0:
    print(f"  Avg upward movement: {below_sma['max_upward_points'].mean():.2f} points")
    print(f"  Avg downward movement: {below_sma['max_downward_points'].mean():.2f} points")
    print(f"  Median upward movement: {below_sma['max_upward_points'].median():.2f} points")
    print(f"  Median downward movement: {below_sma['max_downward_points'].median():.2f} points")
    print(f"  Avg distance from SMA: {below_sma['distance_from_sma'].mean():.2f} points")

# ============================================================================
# STATISTICS BY DATE
# ============================================================================
print("\n" + "=" * 80)
print("STATISTICS BY DATE")
print("=" * 80)

stats_by_date = df_results.groupby('date').agg({
    'max_upward_points': ['mean', 'median', 'count'],
    'max_downward_points': ['mean', 'median']
}).round(2)

stats_by_date.columns = ['avg_upward', 'median_upward', 'num_events', 'avg_downward', 'median_downward']
stats_by_date['avg_total'] = ((stats_by_date['avg_upward'] + stats_by_date['avg_downward']) / 2).round(2)

print(f"\n{stats_by_date.to_string()}")

# ============================================================================
# SAVE RESULTS
# ============================================================================
print("\n" + "=" * 80)
print("SAVING RESULTS")
print("=" * 80)

OUTPUTS_DIR = STRAT_DIR / "outputs"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# Save detailed results
output_file = OUTPUTS_DIR / f"orange_dot_movement_analysis_ALL_DATES.csv"
df_results.to_csv(output_file, sep=';', decimal=',', index=False)
print(f"\n[OK] Detailed results saved: {output_file.name}")

# Save summary by date
summary_file = OUTPUTS_DIR / f"orange_dot_movement_summary_by_date.csv"
stats_by_date.to_csv(summary_file, sep=';', decimal=',')
print(f"[OK] Summary by date saved: {summary_file.name}")

# ============================================================================
# RECOMMENDATIONS
# ============================================================================
print("\n" + "=" * 80)
print("RECOMMENDATIONS FOR MEAN_REVERS_EXPAND")
print("=" * 80)

avg_total_displacement = (avg_upward + avg_downward) / 2
median_total_displacement = (median_upward + median_downward) / 2

print(f"\nCurrent MEAN_REVERS_EXPAND: 10 points")
print(f"\nBased on analysis:")
print(f"  Average total displacement: {avg_total_displacement:.2f} points")
print(f"  Median total displacement: {median_total_displacement:.2f} points")
print(f"\nRecommended MEAN_REVERS_EXPAND values:")
print(f"  Conservative (median-based): {int(median_total_displacement)} points")
print(f"  Aggressive (average-based): {int(avg_total_displacement)} points")
print(f"  Balanced (current + 50%): {int(10 * 1.5)} points")

if avg_total_displacement > 10:
    increase = avg_total_displacement - 10
    print(f"\n[SUGGESTION] Consider increasing MEAN_REVERS_EXPAND by ~{increase:.0f} points")
    print(f"             New value: {int(avg_total_displacement)} points")

# ============================================================================
# TOP EVENTS
# ============================================================================
print("\n" + "=" * 80)
print("TOP 10 EVENTS BY MOVEMENT - ALL DATES")
print("=" * 80)

print("\nTOP 10 UPWARD MOVEMENTS:")
top_upward = df_results.nlargest(10, 'max_upward_points')
for idx, row in top_upward.iterrows():
    print(f"  {row['date']} {row['timestamp'].strftime('%H:%M:%S')} | {row['max_upward_points']:.2f} pts | "
          f"Price: {row['orange_price']:.2f} | {row['position_vs_sma']} SMA")

print("\nTOP 10 DOWNWARD MOVEMENTS:")
top_downward = df_results.nlargest(10, 'max_downward_points')
for idx, row in top_downward.iterrows():
    print(f"  {row['date']} {row['timestamp'].strftime('%H:%M:%S')} | {row['max_downward_points']:.2f} pts | "
          f"Price: {row['orange_price']:.2f} | {row['position_vs_sma']} SMA")

print("\n" + "=" * 80)
print("[SUCCESS] Analysis completed!")
print("=" * 80)
