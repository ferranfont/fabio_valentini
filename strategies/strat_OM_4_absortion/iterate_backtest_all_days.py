"""
Iterate backtest execution across all detected db_shapes files.

This script:
1. Scans outputs/absortion_shape/ for all db_shapes_dom_YYYYMMDD.csv files
2. Finds corresponding time_and_sales_nq_YYYYMMDD.csv files in data/historic/
3. Asks user to choose backtest strategy:
   - FIXED: Fixed TP/SL (strat_absortion_shape.py)
   - VIX: ATR + Trailing Stop (strat_absortion_shape_vix.py)
4. Executes backtest for each day, saving to tracking_record folders

Usage:
    cd strategies/strat_OM_4_absortion
    python iterate_backtest_all_days.py
"""

import os
import sys
import re
from pathlib import Path
from datetime import datetime

# Add parent directories to path
THIS_FILE = Path(__file__).resolve()
STRATEGY_DIR = THIS_FILE.parent
PROJECT_ROOT = STRATEGY_DIR.parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(STRATEGY_DIR.parent))

# Directories
DATA_DIR = PROJECT_ROOT / "data" / "historic"
SIGNALS_DIR = PROJECT_ROOT / "outputs" / "absortion_shape"
OUTPUT_DIR_FIXED = SIGNALS_DIR / "tracking_record"
OUTPUT_DIR_VIX = SIGNALS_DIR / "tracking_record_vix"

# Ensure output directories exist
OUTPUT_DIR_FIXED.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR_VIX.mkdir(parents=True, exist_ok=True)


def extract_date_from_filename(filename):
    """
    Extract YYYYMMDD date from filename.

    Args:
        filename: Filename string

    Returns:
        str: Date in YYYYMMDD format or None
    """
    match = re.search(r'(\d{8})', filename)
    return match.group(1) if match else None


def get_db_shapes_files():
    """
    Get all db_shapes_dom_YYYYMMDD.csv files from outputs/absortion_shape/

    Returns:
        list: List of (date_str, signals_file_path) tuples, sorted by date
    """
    if not SIGNALS_DIR.exists():
        print(f"[ERROR] Signals directory not found: {SIGNALS_DIR}")
        return []

    files = []
    for csv_file in SIGNALS_DIR.glob("db_shapes_dom_*.csv"):
        date_str = extract_date_from_filename(csv_file.name)
        if date_str:
            files.append((date_str, csv_file))

    return sorted(files, key=lambda x: x[0])


def find_tns_file(date_str):
    """
    Find corresponding time_and_sales_nq_YYYYMMDD.csv file.

    Args:
        date_str: Date in YYYYMMDD format

    Returns:
        Path or None: Path to T&S file if found
    """
    tns_file = DATA_DIR / f"time_and_sales_nq_{date_str}.csv"
    return tns_file if tns_file.exists() else None


def check_output_exists(date_str, strategy_type):
    """
    Check if output tracking_record already exists for this date and strategy.

    Args:
        date_str: Date in YYYYMMDD format
        strategy_type: "FIXED" or "VIX"

    Returns:
        bool: True if output exists
    """
    if strategy_type == "FIXED":
        output_file = OUTPUT_DIR_FIXED / f"dbshapes_TR_{date_str}.csv"
    else:
        output_file = OUTPUT_DIR_VIX / f"dbshapes_TR_vix_{date_str}.csv"

    return output_file.exists()


def run_backtest_fixed(tns_file, signals_file, date_str):
    """
    Execute backtest with FIXED TP/SL strategy.

    Args:
        tns_file: Path to time_and_sales CSV
        signals_file: Path to db_shapes CSV
        date_str: Date in YYYYMMDD format

    Returns:
        bool: True if successful
    """
    print(f"\n[BACKTEST] Running FIXED strategy for {date_str}...")

    try:
        # Import and configure strat_absortion_shape
        import strat_absortion_shape

        # Configure paths
        strat_absortion_shape.TNS_FILE = tns_file
        strat_absortion_shape.SIGNALS_FILE = signals_file
        strat_absortion_shape.OUTPUT_FILE = OUTPUT_DIR_FIXED / f"dbshapes_TR_{date_str}.csv"

        # Run backtest
        trades_df = strat_absortion_shape.main()

        print(f"[OK] FIXED backtest completed: {len(trades_df)} trades")
        return True

    except Exception as e:
        print(f"[ERROR] FIXED backtest failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_backtest_vix(tns_file, signals_file, date_str):
    """
    Execute backtest with VIX (ATR + Trailing Stop) strategy.

    Args:
        tns_file: Path to time_and_sales CSV
        signals_file: Path to db_shapes CSV
        date_str: Date in YYYYMMDD format

    Returns:
        bool: True if successful
    """
    print(f"\n[BACKTEST] Running VIX strategy for {date_str}...")

    try:
        # Import and configure strat_absortion_shape_vix
        import strat_absortion_shape_vix

        # Configure paths
        strat_absortion_shape_vix.TNS_FILE = tns_file
        strat_absortion_shape_vix.SIGNALS_FILE = signals_file
        strat_absortion_shape_vix.OUTPUT_FILE = OUTPUT_DIR_VIX / f"dbshapes_TR_vix_{date_str}.csv"

        # Run backtest
        trades_df = strat_absortion_shape_vix.main()

        print(f"[OK] VIX backtest completed: {len(trades_df)} trades")
        return True

    except Exception as e:
        print(f"[ERROR] VIX backtest failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main execution function."""
    print("="*80)
    print("ITERATE BACKTEST EXECUTION - ALL DAYS")
    print("="*80)

    # Get all db_shapes files
    db_shapes_files = get_db_shapes_files()

    if not db_shapes_files:
        print(f"\n[ERROR] No db_shapes_dom_*.csv files found in {SIGNALS_DIR}")
        return

    print(f"\nFound {len(db_shapes_files)} db_shapes files:")

    # Check for corresponding T&S files
    valid_pairs = []
    missing_tns = []

    for date_str, signals_file in db_shapes_files:
        tns_file = find_tns_file(date_str)
        if tns_file:
            valid_pairs.append((date_str, tns_file, signals_file))
            print(f"  [OK] {date_str}: Found T&S and signals")
        else:
            missing_tns.append(date_str)
            print(f"  [WARN] {date_str}: Signals exist but T&S file missing")

    if missing_tns:
        print(f"\n[WARNING] {len(missing_tns)} dates have signals but missing T&S files:")
        for date_str in missing_tns:
            print(f"  - {date_str}")

    if not valid_pairs:
        print("\n[ERROR] No valid date pairs found (both T&S and signals required)")
        return

    # Ask user which strategy to use
    print("\n" + "="*80)
    print("SELECT BACKTEST STRATEGY:")
    print("="*80)
    print("  1. FIXED   - Fixed TP/SL (strat_absortion_shape.py)")
    print("  2. VIX     - ATR + Trailing Stop (strat_absortion_shape_vix.py)")
    print()

    while True:
        choice = input("Enter choice (1 or 2): ").strip()
        if choice in ['1', '2']:
            break
        print("[ERROR] Invalid choice. Enter 1 or 2.")

    strategy_type = "FIXED" if choice == '1' else "VIX"

    print(f"\n[OK] Selected strategy: {strategy_type}")

    # Check which files need processing
    to_process = []
    already_done = []

    for date_str, tns_file, signals_file in valid_pairs:
        if check_output_exists(date_str, strategy_type):
            already_done.append(date_str)
        else:
            to_process.append((date_str, tns_file, signals_file))

    print(f"\nFiles already processed (will be SKIPPED): {len(already_done)}")
    if already_done:
        for date_str in already_done:
            print(f"  {date_str}")

    print(f"\nFiles to process (NEW or MISSING outputs): {len(to_process)}")
    if to_process:
        for date_str, _, _ in to_process:
            print(f"  {date_str}")
    else:
        print("  (none - all files already processed)")

    if not to_process:
        print("\n[INFO] Nothing to process. All files already have outputs.")

        # Offer to generate report anyway
        print("\n" + "="*80)
        response = input("Generate consolidated report with existing data? (y/n): ")

        if response.lower() == 'y':
            print("\n" + "="*80)
            print("GENERATING CONSOLIDATED MULTI-DAY REPORT")
            print("="*80)

            try:
                import main_stat_all_days

                print(f"[INFO] Calling main_stat_all_days.py for {strategy_type} strategy...")
                report_file = main_stat_all_days.main(
                    open_browser=True,
                    strategy_type=strategy_type
                )

                print(f"\n[OK] Consolidated report generated: {report_file}")
                print("[OK] Report opened in browser")

            except Exception as e:
                print(f"\n[ERROR] Failed to generate consolidated report: {e}")
                import traceback
                traceback.print_exc()

        return

    # Confirm execution
    print("\n" + "="*80)
    print(f"READY TO PROCESS {len(to_process)} DAYS WITH {strategy_type} STRATEGY")
    print("="*80)
    response = input("Proceed with backtest execution? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled by user.")
        return

    # Execute backtests
    start_time = datetime.now()
    success_count = 0
    fail_count = 0
    skipped_count = len(already_done)

    for i, (date_str, tns_file, signals_file) in enumerate(to_process, 1):
        print(f"\n{'='*80}")
        print(f"[{i}/{len(to_process)}] Processing date: {date_str}")
        print(f"{'='*80}")
        print(f"  T&S file: {tns_file.name}")
        print(f"  Signals file: {signals_file.name}")

        # Run appropriate backtest
        if strategy_type == "FIXED":
            success = run_backtest_fixed(tns_file, signals_file, date_str)
        else:
            success = run_backtest_vix(tns_file, signals_file, date_str)

        if success:
            success_count += 1
        else:
            fail_count += 1

    # Summary
    elapsed_time = datetime.now() - start_time
    print("\n" + "="*80)
    print("BACKTEST PROCESSING COMPLETE")
    print("="*80)
    print(f"Strategy: {strategy_type}")
    print(f"Total valid dates: {len(valid_pairs)}")
    print(f"Skipped (already exist): {skipped_count}")
    print(f"Processed successfully: {success_count}")
    print(f"Failed: {fail_count}")
    print(f"Backtest time: {elapsed_time}")

    if strategy_type == "FIXED":
        print(f"\nOutput directory: {OUTPUT_DIR_FIXED}")
    else:
        print(f"\nOutput directory: {OUTPUT_DIR_VIX}")

    # Auto-generate consolidated report
    print("\n" + "="*80)
    print("GENERATING CONSOLIDATED MULTI-DAY REPORT")
    print("="*80)

    try:
        # Import and run main_stat_all_days
        import main_stat_all_days

        print(f"[INFO] Calling main_stat_all_days.py for {strategy_type} strategy...")
        report_file = main_stat_all_days.main(
            open_browser=True,
            strategy_type=strategy_type
        )

        print(f"\n[OK] Consolidated report generated: {report_file}")
        print("[OK] Report opened in browser")

    except Exception as e:
        print(f"\n[ERROR] Failed to generate consolidated report: {e}")
        import traceback
        traceback.print_exc()
        print("\n[INFO] You can manually run: python main_stat_all_days.py --strategy " + strategy_type)

    # Final summary
    total_time = datetime.now() - start_time
    print("\n" + "="*80)
    print("ALL PROCESSING COMPLETE")
    print("="*80)
    print(f"Total execution time: {total_time}")
    print("="*80)


if __name__ == "__main__":
    main()
