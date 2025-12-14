"""
Add TPS Window column to existing tick_record CSV
Calculates instantaneous TPS in 10-second rolling window
"""
import pandas as pd
from datetime import timedelta

# File paths
input_file = r'd:\PYTHON\ALGOS\fabio_valentini\strat_trinchera\outputs\tick_record_20251212_132509.csv'
output_file = r'd:\PYTHON\ALGOS\fabio_valentini\strat_trinchera\outputs\tick_record_20251212_132509_with_window.csv'

print(f"Reading: {input_file}")

# Read CSV
df = pd.read_csv(input_file, sep=';', decimal=',')
df.columns = df.columns.str.strip()

print(f"Total records: {len(df):,}")
print(f"Columns: {list(df.columns)}")

# Convert timestamp to datetime (UTC to avoid timezone issues)
df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed', errors='coerce', utc=True)
df = df.dropna(subset=['timestamp'])

# Convert to timezone-naive
df['timestamp'] = df['timestamp'].dt.tz_localize(None)

# Rename existing tps to tps_avg if needed
if 'tps' in df.columns and 'tps_avg' not in df.columns:
    df.rename(columns={'tps': 'tps_avg'}, inplace=True)

# Sort by timestamp (important for rolling window)
df = df.sort_values('timestamp').reset_index(drop=True)

print("\nCalculating TPS window (10s rolling)...")

# Calculate tps_window using rolling time window
window_size = timedelta(seconds=10)
tps_window_values = []

for i, row in df.iterrows():
    current_time = row['timestamp']

    # Get all ticks within the last 10 seconds
    start_time = current_time - window_size

    # Count ticks in window (including current tick)
    mask = (df['timestamp'] > start_time) & (df['timestamp'] <= current_time)
    ticks_in_window = mask.sum()

    # Calculate duration
    if ticks_in_window > 1:
        # Find first tick in window
        first_tick_idx = df[mask].index[0]
        first_tick_time = df.loc[first_tick_idx, 'timestamp']
        duration = (current_time - first_tick_time).total_seconds()

        if duration > 0:
            tps_window = ticks_in_window / duration
        else:
            tps_window = ticks_in_window
    else:
        tps_window = 1.0

    tps_window_values.append(tps_window)

    # Progress indicator
    if (i + 1) % 10000 == 0:
        print(f"  Processed {i+1:,} / {len(df):,} ticks ({(i+1)/len(df)*100:.1f}%)")

# Add tps_window column
df['tps_window'] = tps_window_values

print(f"\nTPS Window range: {df['tps_window'].min():.2f} - {df['tps_window'].max():.2f}")

# Save to new CSV
df.to_csv(output_file, sep=';', decimal=',', index=False)

print(f"\nSaved: {output_file}")
print(f"Columns: {list(df.columns)}")
