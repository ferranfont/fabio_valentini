"""
Split time and sales CSV file into multiple files, one per date.

Usage:
    python strat_absortion/split_by_date.py

Input:  data/time_and_sales_20251031_074530.csv (or any file specified)
Output: data/time_and_sales_nq_YYYYMMDD.csv (one file per unique date)
"""

import pandas as pd
from pathlib import Path
from datetime import datetime

# Configuration
INPUT_FILE = Path(__file__).parent.parent / "data" / "time_and_sales_20251031_074530.csv"
OUTPUT_DIR = Path(__file__).parent.parent / "data"

def split_by_date(input_file, output_dir):
    """
    Split time and sales file by date.

    Args:
        input_file: Path to input CSV file
        output_dir: Directory to save output files
    """
    print(f"Loading data from: {input_file}")

    # Read CSV with European format
    df = pd.read_csv(input_file, sep=';', decimal=',')

    print(f"Total records: {len(df):,}")

    # Convert Timestamp to datetime
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])

    # Extract date (YYYY-MM-DD)
    df['Date'] = df['Timestamp'].dt.date

    # Get unique dates
    unique_dates = sorted(df['Date'].unique())
    print(f"\nFound {len(unique_dates)} unique dates:")
    for date in unique_dates:
        count = len(df[df['Date'] == date])
        print(f"  - {date}: {count:,} records")

    # Split and save by date
    print("\nSplitting files...")
    for date in unique_dates:
        # Filter data for this date
        date_df = df[df['Date'] == date].copy()

        # Drop the temporary Date column
        date_df = date_df.drop(columns=['Date'])

        # Create output filename: time_and_sales_nq_YYYYMMDD.csv
        date_str = date.strftime('%Y%m%d')
        output_file = output_dir / f"time_and_sales_nq_{date_str}.csv"

        # Save with European format
        date_df.to_csv(output_file, sep=';', decimal=',', index=False)

        print(f"  [OK] Saved {len(date_df):,} records to: {output_file.name}")

    print("\nSplit complete!")

if __name__ == "__main__":
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Check if input file exists
    if not INPUT_FILE.exists():
        print(f"[ERROR] Input file not found: {INPUT_FILE}")
        exit(1)

    # Split the file
    split_by_date(INPUT_FILE, OUTPUT_DIR)
