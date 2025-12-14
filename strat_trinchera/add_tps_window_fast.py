"""
Add TPS Window column to existing tick_record CSV (OPTIMIZED VERSION)
Uses pandas rolling window for ultra-fast calculation
"""
import pandas as pd
import numpy as np

# File paths
input_file = r'd:\PYTHON\ALGOS\fabio_valentini\strat_trinchera\outputs\tick_record_20251212_132509.csv'
output_file = r'd:\PYTHON\ALGOS\fabio_valentini\strat_trinchera\outputs\tick_record_20251212_132509_with_window.csv'

print(f"Reading: {input_file}")

# Read CSV
df = pd.read_csv(input_file, sep=';', decimal=',')
df.columns = df.columns.str.strip()

print(f"Total records: {len(df):,}")
print(f"Columns: {list(df.columns)}")

# Convert timestamp to datetime
df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
df = df.dropna(subset=['timestamp'])

# Rename existing tps to tps_avg if needed
if 'tps' in df.columns and 'tps_avg' not in df.columns:
    df.rename(columns={'tps': 'tps_avg'}, inplace=True)

# Sort by timestamp
df = df.sort_values('timestamp').reset_index(drop=True)

print("\nCalculating TPS window (10s rolling) - FAST METHOD...")

# Set timestamp as index
df.set_index('timestamp', inplace=True)

# Create a rolling window counter (count rows in 10-second window)
# Use rolling with time-based window
window_size = '10s'

# Method: Count non-null values in rolling window, then divide by window duration
rolling_count = df.rolling(window_size, on=df.index).size()

# Calculate TPS: ticks per second in the window
# For each row, calculate the actual duration of the window
tps_window_list = []

for i in range(len(df)):
    # Get current timestamp
    current_time = df.index[i]

    # Define window start (10 seconds ago)
    window_start = current_time - pd.Timedelta(seconds=10)

    # Count ticks in window
    mask = (df.index > window_start) & (df.index <= current_time)
    ticks_in_window = mask.sum()

    # Calculate duration
    if ticks_in_window > 1:
        # Get first timestamp in window
        first_time = df.index[mask][0]
        duration_sec = (current_time - first_time).total_seconds()

        if duration_sec > 0:
            tps = ticks_in_window / duration_sec
        else:
            tps = float(ticks_in_window)
    else:
        tps = 1.0

    tps_window_list.append(tps)

    # Progress
    if (i + 1) % 50000 == 0:
        print(f"  Processed {i+1:,} / {len(df):,} ({(i+1)/len(df)*100:.1f}%)")

df['tps_window'] = tps_window_list

# Reset index
df.reset_index(inplace=True)

print(f"\nTPS Window range: {df['tps_window'].min():.2f} - {df['tps_window'].max():.2f}")

# Save
df.to_csv(output_file, sep=';', decimal=',', index=False)

print(f"\nSaved: {output_file}")
print(f"Columns: {list(df.columns)}")
