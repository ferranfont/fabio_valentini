"""
Iterate over all CSV files in data/historic and execute main.py for each one.

This script processes each time_and_sales_nq_YYYYMMDD.csv file found in data/historic/,
generating db_shapes_dom_YYYYMMDD.csv output files in outputs/absortion_shape/.

Usage:
    python strat_absortion/iterate_on_main_to_sb_shapes.py
"""

import os
import sys
import subprocess
from pathlib import Path
import re

# Directories
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data" / "historic"
OUTPUT_DIR = BASE_DIR.parent / "outputs" / "absortion_shape"
MAIN_SCRIPT = BASE_DIR / "main.py"

# Ensure output directory exists
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def extract_date_from_filename(filename):
    """
    Extract YYYYMMDD date from filename like time_and_sales_nq_20250918.csv

    Args:
        filename: CSV filename

    Returns:
        str: Date in YYYYMMDD format or None if not found
    """
    match = re.search(r'(\d{8})', filename)
    return match.group(1) if match else None


def get_csv_files():
    """
    Get all time_and_sales CSV files from data/historic directory.

    Returns:
        list: List of Path objects for CSV files, sorted by date
    """
    if not DATA_DIR.exists():
        print(f"[ERROR] Data directory not found: {DATA_DIR}")
        return []

    # Find all CSV files matching the pattern
    csv_files = sorted(DATA_DIR.glob("time_and_sales_nq_*.csv"))

    return csv_files


def check_output_exists(date_str):
    """
    Check if output file already exists for this date.

    Args:
        date_str: Date in YYYYMMDD format

    Returns:
        bool: True if output exists
    """
    output_file = OUTPUT_DIR / f"db_shapes_dom_{date_str}.csv"
    return output_file.exists()


def process_csv_file(csv_file, force_reprocess=False):
    """
    Process a single CSV file by running main.py with it.

    Args:
        csv_file: Path to CSV file
        force_reprocess: If True, process even if output exists

    Returns:
        bool: True if successful
    """
    date_str = extract_date_from_filename(csv_file.name)

    if not date_str:
        print(f"[SKIP] Could not extract date from: {csv_file.name}")
        return False

    print(f"\n{'='*80}")
    print(f"Processing: {csv_file.name} (Date: {date_str})")
    print(f"{'='*80}")

    # Set environment variable to point main.py to this CSV file
    env = os.environ.copy()
    env['ABSORTION_SOURCE_CSV'] = str(csv_file)

    try:
        # Run main.py as a subprocess
        result = subprocess.run(
            [sys.executable, str(MAIN_SCRIPT)],
            env=env,
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=2700  # 45 minute timeout (some files are 40MB+)
        )

        # Print output
        if result.stdout:
            print(result.stdout)

        if result.stderr:
            print("STDERR:", result.stderr, file=sys.stderr)

        if result.returncode == 0:
            print(f"[OK] Successfully processed {csv_file.name}")
            return True
        else:
            print(f"[ERROR] main.py exited with code {result.returncode}")
            return False

    except subprocess.TimeoutExpired:
        print(f"[ERROR] Processing timed out after 45 minutes")
        return False
    except Exception as e:
        print(f"[ERROR] Exception during processing: {e}")
        return False


def main():
    """Main execution function."""
    print("="*80)
    print("ITERATE ON MAIN.PY TO GENERATE DB_SHAPES FILES")
    print("="*80)

    # Get all CSV files
    csv_files = get_csv_files()

    if not csv_files:
        print("\n[ERROR] No time_and_sales_nq_*.csv files found in data/historic/")
        return

    print(f"\nFound {len(csv_files)} CSV files in {DATA_DIR}")

    # Check which files already have outputs
    files_to_process = []
    files_already_done = []

    for csv_file in csv_files:
        date_str = extract_date_from_filename(csv_file.name)
        if date_str and check_output_exists(date_str):
            files_already_done.append(csv_file.name)
        else:
            files_to_process.append(csv_file)

    print(f"\nFiles already processed (will be SKIPPED): {len(files_already_done)}")
    if files_already_done:
        for fname in files_already_done:
            print(f"  {fname}")

    print(f"\nFiles to process (NEW or MISSING outputs): {len(files_to_process)}")
    if files_to_process:
        for csv_file in files_to_process:
            print(f"  {csv_file.name}")
    else:
        print("  (none - all files already processed)")

    # Ask for confirmation
    print("\n" + "="*80)
    print("NOTE: Only files WITHOUT existing outputs will be processed.")
    response = input("Proceed with processing? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled by user.")
        return

    # Process each file
    success_count = 0
    fail_count = 0
    skipped_count = 0

    for i, csv_file in enumerate(csv_files, 1):
        date_str = extract_date_from_filename(csv_file.name)

        # Skip if already exists
        if date_str and check_output_exists(date_str):
            print(f"\n[{i}/{len(csv_files)}] SKIPPED (already exists): {csv_file.name}")
            skipped_count += 1
            continue

        print(f"\n[{i}/{len(csv_files)}] Processing: {csv_file.name}")

        if process_csv_file(csv_file, force_reprocess=False):
            success_count += 1
        else:
            fail_count += 1

    # Summary
    print("\n" + "="*80)
    print("PROCESSING COMPLETE")
    print("="*80)
    print(f"Total files: {len(csv_files)}")
    print(f"Skipped (already exist): {skipped_count}")
    print(f"Processed successfully: {success_count}")
    print(f"Failed: {fail_count}")
    print(f"\nOutput directory: {OUTPUT_DIR}")
    print("="*80)


if __name__ == "__main__":
    main()
