import pandas as pd
from pathlib import Path

# Load both CSV files
csv_30min = Path("data/time_and_sales_nq_30min.csv")
csv_full = Path("data/time_and_sales_nq.csv")

print("=" * 80)
print("COMPARING CSV FILES: 30min vs Full Dataset")
print("=" * 80)

# Read with European format (semicolon separator, comma decimal)
print("\nLoading 30min dataset...")
df_30min = pd.read_csv(csv_30min, sep=";", decimal=",")
df_30min['Timestamp'] = pd.to_datetime(df_30min['Timestamp'])

print(f"  Rows: {len(df_30min):,}")
print(f"  Time range: {df_30min['Timestamp'].min()} to {df_30min['Timestamp'].max()}")

print("\nLoading full dataset...")
df_full = pd.read_csv(csv_full, sep=";", decimal=",")
df_full['Timestamp'] = pd.to_datetime(df_full['Timestamp'])

print(f"  Rows: {len(df_full):,}")
print(f"  Time range: {df_full['Timestamp'].min()} to {df_full['Timestamp'].max()}")

# Find the common time range
min_time_30min = df_30min['Timestamp'].min()
max_time_30min = df_30min['Timestamp'].max()

print("\n" + "=" * 80)
print(f"EXTRACTING COMMON TIME RANGE FROM FULL DATASET")
print(f"Time range: {min_time_30min} to {max_time_30min}")
print("=" * 80)

# Extract the same time range from full dataset
df_full_subset = df_full[(df_full['Timestamp'] >= min_time_30min) &
                          (df_full['Timestamp'] <= max_time_30min)].copy()

print(f"\nFull dataset subset rows: {len(df_full_subset):,}")
print(f"30min dataset rows:       {len(df_30min):,}")

# Check if row counts match
print("\n" + "-" * 80)
print("ROW COUNT COMPARISON:")
print("-" * 80)
if len(df_full_subset) == len(df_30min):
    print("[OK] ROW COUNTS MATCH")
else:
    print(f"[ERROR] ROW COUNTS DIFFER by {abs(len(df_full_subset) - len(df_30min)):,} rows")
    if len(df_full_subset) > len(df_30min):
        print(f"  Full dataset has {len(df_full_subset) - len(df_30min):,} MORE rows")
    else:
        print(f"  30min dataset has {len(df_30min) - len(df_full_subset):,} MORE rows")

# Reset indices for comparison
df_30min_reset = df_30min.reset_index(drop=True)
df_full_subset_reset = df_full_subset.reset_index(drop=True)

# Compare row by row
print("\n" + "=" * 80)
print("ROW-BY-ROW COMPARISON:")
print("=" * 80)

differences = []
max_rows_to_check = min(len(df_30min_reset), len(df_full_subset_reset))

for i in range(max_rows_to_check):
    row_30min = df_30min_reset.iloc[i]
    row_full = df_full_subset_reset.iloc[i]

    # Compare all columns
    is_different = False
    diff_details = []

    for col in df_30min_reset.columns:
        val_30min = row_30min[col]
        val_full = row_full[col]

        # For timestamps, compare as strings
        if col == 'Timestamp':
            if pd.to_datetime(val_30min) != pd.to_datetime(val_full):
                is_different = True
                diff_details.append(f"{col}: {val_30min} vs {val_full}")
        else:
            # For numeric values, use close comparison for floats
            if isinstance(val_30min, float) and isinstance(val_full, float):
                if abs(val_30min - val_full) > 0.001:  # Allow tiny floating point errors
                    is_different = True
                    diff_details.append(f"{col}: {val_30min} vs {val_full}")
            elif val_30min != val_full:
                is_different = True
                diff_details.append(f"{col}: {val_30min} vs {val_full}")

    if is_different:
        differences.append({
            'row': i,
            'timestamp_30min': row_30min['Timestamp'],
            'timestamp_full': row_full['Timestamp'],
            'details': diff_details
        })

if len(differences) == 0:
    print("[OK] ALL ROWS ARE IDENTICAL")
else:
    print(f"[ERROR] FOUND {len(differences)} DIFFERENT ROWS")
    print("\nFirst 10 differences:")
    print("-" * 80)
    for i, diff in enumerate(differences[:10]):
        print(f"\nRow {diff['row']}:")
        print(f"  30min timestamp: {diff['timestamp_30min']}")
        print(f"  Full timestamp:  {diff['timestamp_full']}")
        print(f"  Differences:")
        for detail in diff['details']:
            print(f"    - {detail}")

# Sample comparison: show first 5 rows from each
print("\n" + "=" * 80)
print("SAMPLE DATA (First 5 rows):")
print("=" * 80)

print("\n30min dataset:")
print(df_30min_reset.head())

print("\nFull dataset (same time range):")
print(df_full_subset_reset.head())

# Check for duplicate timestamps
print("\n" + "=" * 80)
print("DUPLICATE TIMESTAMP CHECK:")
print("=" * 80)

duplicates_30min = df_30min['Timestamp'].duplicated().sum()
duplicates_full = df_full_subset['Timestamp'].duplicated().sum()

print(f"30min dataset duplicates: {duplicates_30min}")
print(f"Full dataset duplicates:  {duplicates_full}")

# Summary
print("\n" + "=" * 80)
print("SUMMARY:")
print("=" * 80)
print(f"Row count match:    {'YES' if len(df_full_subset) == len(df_30min) else 'NO'}")
print(f"Data identical:     {'YES' if len(differences) == 0 else 'NO'}")
print(f"Differences found:  {len(differences)}")
print("=" * 80)
