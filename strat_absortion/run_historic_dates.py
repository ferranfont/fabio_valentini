"""
Run absorption strategy on specific dates.

Usage:
    # Run on specific dates
    python strat_absortion/run_historic_dates.py 20250917 20250918

    # Run on date range
    python strat_absortion/run_historic_dates.py --range 20250915 20250920

    # Run all without confirmation
    python strat_absortion/run_historic_dates.py --all
"""

import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta
import argparse

# ========= PATHS =========
PROJECT_ROOT = Path(__file__).parent.parent
DATA_HISTORIC_DIR = PROJECT_ROOT / "data" / "historic"
MAIN_SCRIPT = PROJECT_ROOT / "strat_absortion" / "main.py"

def find_file_for_date(date_str):
    """Find CSV file for a specific date (YYYYMMDD format)."""
    pattern = f"time_and_sales_nq_{date_str}.csv"
    file_path = DATA_HISTORIC_DIR / pattern

    if file_path.exists():
        return file_path

    # Try alternative patterns
    alt_patterns = [
        f"time_and_sales_{date_str}.csv",
        f"time_and_sales_nq_{date_str[2:]}.csv",  # Try without century
    ]

    for alt in alt_patterns:
        alt_path = DATA_HISTORIC_DIR / alt
        if alt_path.exists():
            return alt_path

    return None

def run_strategy_on_file(csv_file):
    """Run main.py with the specified CSV file."""
    print(f"\n{'=' * 60}")
    print(f"Processing: {csv_file.name}")
    print(f"{'=' * 60}")

    # Set environment variable for the source CSV
    env = os.environ.copy()
    env['ABSORTION_SOURCE_CSV'] = str(csv_file)

    try:
        # Run the main script
        result = subprocess.run(
            [sys.executable, str(MAIN_SCRIPT)],
            env=env,
            timeout=600  # 10 minute timeout
        )

        if result.returncode == 0:
            print(f"[OK] Successfully processed {csv_file.name}")
            return True
        else:
            print(f"[ERROR] Failed to process {csv_file.name}")
            return False

    except subprocess.TimeoutExpired:
        print(f"[ERROR] Timeout processing {csv_file.name}")
        return False
    except Exception as e:
        print(f"[ERROR] Exception: {e}")
        return False

def generate_date_range(start_date, end_date):
    """Generate list of dates between start and end (YYYYMMDD format)."""
    start = datetime.strptime(start_date, "%Y%m%d")
    end = datetime.strptime(end_date, "%Y%m%d")

    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)

    return dates

def main():
    parser = argparse.ArgumentParser(description="Run absorption strategy on specific dates")
    parser.add_argument('dates', nargs='*', help='Dates in YYYYMMDD format')
    parser.add_argument('--range', nargs=2, metavar=('START', 'END'),
                        help='Process date range (YYYYMMDD YYYYMMDD)')
    parser.add_argument('--all', action='store_true',
                        help='Process all files without confirmation')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show files that would be processed without running')

    args = parser.parse_args()

    # Determine which dates to process
    target_dates = []

    if args.all:
        # Find all files
        all_files = sorted(DATA_HISTORIC_DIR.glob("time_and_sales_*.csv"))
        if not all_files:
            print("[ERROR] No CSV files found in data/historic/")
            return 1

        print(f"Found {len(all_files)} files:")
        for f in all_files:
            print(f"  - {f.name}")

        if args.dry_run:
            return 0

        # Process all
        successful = 0
        failed = 0
        for csv_file in all_files:
            if run_strategy_on_file(csv_file):
                successful += 1
            else:
                failed += 1

        print(f"\n{'=' * 60}")
        print(f"Processed {len(all_files)} files: {successful} successful, {failed} failed")
        print(f"{'=' * 60}")
        return 0 if failed == 0 else 1

    elif args.range:
        # Generate date range
        start_date, end_date = args.range
        target_dates = generate_date_range(start_date, end_date)
        print(f"Processing date range: {start_date} to {end_date}")
        print(f"Generated {len(target_dates)} dates")

    elif args.dates:
        # Use specified dates
        target_dates = args.dates
    else:
        parser.print_help()
        return 1

    # Find files for each date
    files_to_process = []
    missing_dates = []

    for date_str in target_dates:
        csv_file = find_file_for_date(date_str)
        if csv_file:
            files_to_process.append(csv_file)
            print(f"  Found: {csv_file.name}")
        else:
            missing_dates.append(date_str)
            print(f"  Missing: {date_str}")

    if missing_dates:
        print(f"\n[WARNING] {len(missing_dates)} date(s) not found")

    if not files_to_process:
        print("[ERROR] No files found to process")
        return 1

    print(f"\nWill process {len(files_to_process)} file(s)")

    if args.dry_run:
        print("\n[DRY RUN] Exiting without processing")
        return 0

    # Process each file
    successful = 0
    failed = 0

    for i, csv_file in enumerate(files_to_process, 1):
        print(f"\n[{i}/{len(files_to_process)}]")

        if run_strategy_on_file(csv_file):
            successful += 1
        else:
            failed += 1

    # Summary
    print(f"\n{'=' * 60}")
    print(f"SUMMARY: {successful} successful, {failed} failed")
    print(f"{'=' * 60}")

    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
