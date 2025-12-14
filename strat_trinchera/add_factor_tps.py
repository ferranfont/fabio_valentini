"""
Add factor_tps column (window_vol * tps_window) to tick record CSV
"""
import pandas as pd
import os

# Input file
input_file = r'd:\PYTHON\ALGOS\fabio_valentini\strat_trinchera\outputs\tick_record_20251212_132509.csv'

print("Reading CSV...")
df = pd.read_csv(input_file, sep=';', decimal=',')
df.columns = df.columns.str.strip()

print(f"Total records: {len(df):,}")
print(f"Columns: {list(df.columns)}")

# Ensure numeric columns are properly converted
print("\nConverting columns to numeric...")
df['window_vol'] = pd.to_numeric(df['window_vol'], errors='coerce')

# Check which TPS column exists
if 'tps_window' in df.columns:
    tps_col = 'tps_window'
elif 'tps' in df.columns:
    tps_col = 'tps'
else:
    print("[ERROR] No TPS column found!")
    exit(1)

print(f"Using TPS column: {tps_col}")
df[tps_col] = pd.to_numeric(df[tps_col], errors='coerce')

# Drop rows with NaN values
df = df.dropna(subset=['window_vol', tps_col])

print(f"Valid records after cleaning: {len(df):,}")

# Calculate factor_tps = window_vol * tps
print(f"\nCalculating factor_tps = window_vol * {tps_col}...")
df['factor_tps'] = df['window_vol'] * df[tps_col]

print(f"\nFactor TPS statistics:")
print(f"  Mean: {df['factor_tps'].mean():.2f}")
print(f"  Median: {df['factor_tps'].median():.2f}")
print(f"  Min: {df['factor_tps'].min():.2f}")
print(f"  Max: {df['factor_tps'].max():.2f}")
print(f"  Std Dev: {df['factor_tps'].std():.2f}")

# Show sample
print("\nSample rows:")
cols_to_show = ['timestamp', 'price', 'window_vol', tps_col, 'factor_tps']
print(df[cols_to_show].head(10).to_string())

# Save to same file (overwrite)
print(f"\nSaving updated CSV to: {input_file}")
df.to_csv(input_file, sep=';', decimal=',', index=False)

print("\n[OK] factor_tps column added successfully!")
print(f"New columns: {list(df.columns)}")
