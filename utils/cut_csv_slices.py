"""
Cut a large CSV file into n equal slices.

This script splits a large CSV file into multiple smaller files,
preserving the header in each slice.
"""

import pandas as pd
from pathlib import Path
import sys

# Configuration
FICHERO_CSV_A_CORTAR = "ts_and_dom_24_oct.csv"
N_SLICES = 10  # Number of slices to create

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
INPUT_FILE = DATA_DIR / FICHERO_CSV_A_CORTAR
OUTPUT_DIR = DATA_DIR


def cut_csv_into_slices(input_file, output_dir, n_slices=10):
    """
    Cut a CSV file into n equal slices.

    Parameters:
    -----------
    input_file : Path
        Path to the input CSV file
    output_dir : Path
        Directory where the slices will be saved
    n_slices : int
        Number of slices to create (default: 10)
    """
    print(f"[INFO] Loading CSV file: {input_file}")
    print(f"[INFO] Reading with European format (sep=';', decimal=',')")

    # Check if file exists
    if not input_file.exists():
        print(f"[ERROR] File not found: {input_file}")
        return

    # Get file size
    file_size_mb = input_file.stat().st_size / (1024 * 1024)
    print(f"[INFO] File size: {file_size_mb:.2f} MB")

    # Read the CSV file
    try:
        df = pd.read_csv(input_file, sep=';', decimal=',')
        print(f"[OK] File loaded successfully")
        print(f"[INFO] Total rows: {len(df):,}")
        print(f"[INFO] Columns: {list(df.columns)}")
    except Exception as e:
        print(f"[ERROR] Failed to load CSV: {e}")
        return

    # Calculate rows per slice
    total_rows = len(df)
    rows_per_slice = total_rows // n_slices

    print(f"\n[INFO] Creating {n_slices} slices...")
    print(f"[INFO] Rows per slice: ~{rows_per_slice:,}")

    # Create slices
    base_name = input_file.stem  # Get filename without extension

    for i in range(n_slices):
        start_idx = i * rows_per_slice

        # Last slice gets all remaining rows
        if i == n_slices - 1:
            end_idx = total_rows
        else:
            end_idx = (i + 1) * rows_per_slice

        # Extract slice
        slice_df = df.iloc[start_idx:end_idx]

        # Generate output filename
        output_file = output_dir / f"{base_name}_slice_{i+1:02d}_of_{n_slices:02d}.csv"

        # Save slice with European format
        slice_df.to_csv(output_file, sep=';', decimal=',', index=False)

        slice_size_mb = output_file.stat().st_size / (1024 * 1024)
        print(f"[OK] Slice {i+1}/{n_slices}: {output_file.name} ({len(slice_df):,} rows, {slice_size_mb:.2f} MB)")

    print(f"\n[SUCCESS] All {n_slices} slices created successfully!")
    print(f"[INFO] Output directory: {output_dir}")


if __name__ == "__main__":
    print("="*70)
    print("CSV SLICER - Cut large CSV files into smaller pieces")
    print("="*70)
    print(f"\nInput file: {INPUT_FILE.name}")
    print(f"Number of slices: {N_SLICES}")
    print(f"Input directory: {DATA_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")
    print("-"*70)

    # Execute the slicing
    cut_csv_into_slices(INPUT_FILE, OUTPUT_DIR, N_SLICES)

    print("\n" + "="*70)
    print("DONE")
    print("="*70)
