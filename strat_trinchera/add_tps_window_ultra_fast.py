"""
Add TPS Window column (ULTRA FAST - Vectorized approach)
Uses numpy for maximum speed
"""
import pandas as pd
import numpy as np

input_file = r'd:\PYTHON\ALGOS\fabio_valentini\strat_trinchera\outputs\tick_record_20251212_132509.csv'
output_file = r'd:\PYTHON\ALGOS\fabio_valentini\strat_trinchera\outputs\tick_record_20251212_132509_with_window.csv'

print("Reading CSV...")
df = pd.read_csv(input_file, sep=';', decimal=',')
df.columns = df.columns.str.strip()

print(f"Records: {len(df):,}")

# Convert timestamp
df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
df = df.dropna(subset=['timestamp'])

# Rename tps to tps_avg
if 'tps' in df.columns:
    df.rename(columns={'tps': 'tps_avg'}, inplace=True)

# Sort
df = df.sort_values('timestamp').reset_index(drop=True)

print("Calculating TPS window (ULTRA FAST)...")

# Convert timestamps to seconds since start
start_time = df['timestamp'].min()
df['seconds'] = (df['timestamp'] - start_time).dt.total_seconds()

# Window size in seconds
window = 10.0

# Vectorized calculation
tps_window = np.zeros(len(df))

for i in range(len(df)):
    current_sec = df.loc[i, 'seconds']
    window_start = current_sec - window

    # Boolean mask for window
    in_window = (df['seconds'] > window_start) & (df['seconds'] <= current_sec)
    count = in_window.sum()

    # Get time range
    if count > 1:
        window_data = df.loc[in_window, 'seconds']
        duration = current_sec - window_data.min()
        if duration > 0:
            tps_window[i] = count / duration
        else:
            tps_window[i] = count
    else:
        tps_window[i] = 1.0

    if (i + 1) % 100000 == 0:
        print(f"  {i+1:,} / {len(df):,} ({(i+1)/len(df)*100:.0f}%)")

df['tps_window'] = tps_window
df = df.drop('seconds', axis=1)

print(f"TPS range: {df['tps_window'].min():.2f} - {df['tps_window'].max():.2f}")

# Save
df.to_csv(output_file, sep=';', decimal=',', index=False)
print(f"\nSaved: {output_file}")
