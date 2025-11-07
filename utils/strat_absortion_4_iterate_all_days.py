"""
Batch Processing Tool for Absortion Shape Strategy
===================================================

Executes the strat_OM_4_absortion backtest system for ALL days in data/historic/

Input:
- Scans all time_and_sales_nq_YYYYMMDD.csv files in data/historic/
- Validates corresponding db_shapes_dom_YYYYMMDD.csv signals exist

Output:
- Individual CSV per day: outputs/absortion_shape/tracking_record/tracking_record_YYYYMMDD.csv
- Consolidated global CSV: outputs/absortion_shape/tracking_record/tracking_record_strat_abs_4_all_days.csv

Features:
- Automatic date extraction from filenames
- Signal validation before processing
- Error handling per day (doesn't stop on single failure)
- Progress tracking
- Final summary report with statistics
"""

import sys
from pathlib import Path
import pandas as pd
import re
from datetime import datetime
import traceback

# =============================================================================
# PATH SETUP
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "historic"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
TRACKING_DIR = OUTPUTS_DIR / "absortion_shape" / "tracking_record"

# Add paths for imports
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "strategies"))

# =============================================================================
# STRATEGY CONFIGURATION
# =============================================================================

SYMBOL = "NQ"
TP_POINTS = 3.0                  # Take Profit en puntos
SL_POINTS = 1.5                  # Stop Loss en puntos
POINT_VALUE = 20.0               # Valor del punto en dólares
THRESHOLD_EXTRA = 0.25           # Margen de seguridad adicional
CONTRACTS = 1                    # Número de contratos por trade
BREAK_EVEN_POINTS = 50.0         # Avance para mover stop a breakeven
NUM_MAX_OPEN_CONTRACTS = 3       # Máximo de posiciones simultáneas

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def print_header(title):
    """Print visual header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def scan_historic_files():
    """
    Scan data/historic/ folder and extract dates from time_and_sales_nq_YYYYMMDD.csv files.

    Returns:
        list: List of tuples (date_str, file_path) sorted by date
    """
    print("[INFO] Scanning data/historic/ folder...")

    if not DATA_DIR.exists():
        print(f"[ERROR] Directory not found: {DATA_DIR}")
        return []

    pattern = re.compile(r'time_and_sales_nq_(\d{8})\.csv')
    found_files = []

    for file_path in DATA_DIR.glob("time_and_sales_nq_*.csv"):
        match = pattern.match(file_path.name)
        if match:
            date_str = match.group(1)
            found_files.append((date_str, file_path))

    # Sort by date
    found_files.sort(key=lambda x: x[0])

    print(f"[OK] Found {len(found_files)} time_and_sales files")
    return found_files


def validate_signals_exist(date_str):
    """
    Check if db_shapes_dom_{date}.csv exists for the given date.

    Args:
        date_str (str): Date in YYYYMMDD format

    Returns:
        Path or None: Path to signals file if exists, None otherwise
    """
    # Check in outputs/absortion_shape/ first
    signals_file = OUTPUTS_DIR / "absortion_shape" / f"db_shapes_dom_{date_str}.csv"
    if signals_file.exists():
        return signals_file

    # Check in outputs/ as fallback
    signals_file = OUTPUTS_DIR / f"db_shapes_dom_{date_str}.csv"
    if signals_file.exists():
        return signals_file

    return None


def run_backtest_for_date(date_str, tns_file, signals_file):
    """
    Run backtest for a specific date.

    Args:
        date_str (str): Date in YYYYMMDD format
        tns_file (Path): Path to time_and_sales CSV
        signals_file (Path): Path to db_shapes signals CSV

    Returns:
        pd.DataFrame or None: DataFrame with trade results, None if error
    """
    print(f"\n[INFO] Processing date: {date_str}")
    print(f"  T&S File: {tns_file.name}")
    print(f"  Signals File: {signals_file.name}")

    try:
        # Import backtest module
        from strategies.strat_OM_4_absortion import strat_absortion_shape

        # Configure parameters
        strat_absortion_shape.TNS_FILE = tns_file
        strat_absortion_shape.SIGNALS_FILE = signals_file
        strat_absortion_shape.SYMBOL = SYMBOL
        strat_absortion_shape.TP_POINTS = TP_POINTS
        strat_absortion_shape.SL_POINTS = SL_POINTS
        strat_absortion_shape.POINT_VALUE = POINT_VALUE
        strat_absortion_shape.THRESHOLD_EXTRA = THRESHOLD_EXTRA
        strat_absortion_shape.BREAK_EVEN_POINTS = BREAK_EVEN_POINTS
        strat_absortion_shape.CONTRACTS = CONTRACTS
        strat_absortion_shape.NUM_MAX_OPEN_CONTRACTS = NUM_MAX_OPEN_CONTRACTS

        # Disable file output (we'll handle it here)
        strat_absortion_shape.OUTPUT_FILE = None

        # Run backtest
        trades_df = strat_absortion_shape.main()

        if trades_df is not None and not trades_df.empty:
            # Add date column for global CSV
            trades_df['date'] = date_str

            # Add trade_id column (will be reindexed globally later)
            trades_df['trade_id'] = range(1, len(trades_df) + 1)

            print(f"[OK] Backtest completed: {len(trades_df)} trades generated")
            return trades_df
        else:
            print(f"[WARNING] No trades generated for {date_str}")
            return None

    except Exception as e:
        print(f"[ERROR] Backtest failed for {date_str}: {e}")
        traceback.print_exc()
        return None


def save_daily_csv(trades_df, date_str):
    """
    Save individual CSV for a specific date.

    Args:
        trades_df (pd.DataFrame): Trade results
        date_str (str): Date in YYYYMMDD format
    """
    output_file = TRACKING_DIR / f"tracking_record_{date_str}.csv"

    try:
        trades_df.to_csv(output_file, sep=';', decimal=',', index=False, encoding='utf-8')
        print(f"[OK] Daily CSV saved: {output_file.name}")
    except Exception as e:
        print(f"[ERROR] Failed to save daily CSV for {date_str}: {e}")


def consolidate_all_days(all_trades_list):
    """
    Consolidate all daily DataFrames into a single global DataFrame.

    Args:
        all_trades_list (list): List of DataFrames with daily results

    Returns:
        pd.DataFrame: Consolidated DataFrame with global trade_id
    """
    print("\n[INFO] Consolidating all daily results...")

    if not all_trades_list:
        print("[WARNING] No data to consolidate")
        return None

    # Concatenate all DataFrames
    global_df = pd.concat(all_trades_list, ignore_index=True)

    # Reindex trade_id globally
    global_df['trade_id'] = range(1, len(global_df) + 1)

    # Sort by entry_time
    global_df = global_df.sort_values('entry_time', ignore_index=True)

    # Reorder columns to put date and trade_id first
    cols = ['trade_id', 'date'] + [col for col in global_df.columns if col not in ['trade_id', 'date']]
    global_df = global_df[cols]

    print(f"[OK] Consolidated {len(global_df)} trades from {len(all_trades_list)} days")
    return global_df


def save_global_csv(global_df):
    """
    Save consolidated global CSV.

    Args:
        global_df (pd.DataFrame): Consolidated DataFrame
    """
    output_file = TRACKING_DIR / "tracking_record_strat_abs_4_all_days.csv"

    try:
        global_df.to_csv(output_file, sep=';', decimal=',', index=False, encoding='utf-8')
        print(f"[OK] Global CSV saved: {output_file}")
        print(f"    Total trades: {len(global_df)}")
    except Exception as e:
        print(f"[ERROR] Failed to save global CSV: {e}")


def generate_summary_report(global_df, processed_dates, skipped_dates, failed_dates):
    """
    Generate final summary report.

    Args:
        global_df (pd.DataFrame): Consolidated DataFrame
        processed_dates (list): List of successfully processed dates
        skipped_dates (list): List of dates skipped (no signals)
        failed_dates (list): List of dates that failed during processing
    """
    print_header("BATCH PROCESSING SUMMARY REPORT")

    print("PROCESSING STATISTICS:")
    print(f"  Total dates found: {len(processed_dates) + len(skipped_dates) + len(failed_dates)}")
    print(f"  Successfully processed: {len(processed_dates)}")
    print(f"  Skipped (no signals): {len(skipped_dates)}")
    print(f"  Failed (errors): {len(failed_dates)}")

    if global_df is not None and not global_df.empty:
        print("\nTRADE STATISTICS:")
        print(f"  Total trades: {len(global_df)}")

        # Calculate P&L statistics
        if 'profit_dollars' in global_df.columns:
            total_pnl = global_df['profit_dollars'].sum()
            winning_trades = len(global_df[global_df['profit_dollars'] > 0])
            losing_trades = len(global_df[global_df['profit_dollars'] < 0])
            win_rate = (winning_trades / len(global_df) * 100) if len(global_df) > 0 else 0

            print(f"  Total P&L: ${total_pnl:,.2f}")
            print(f"  Winning trades: {winning_trades} ({win_rate:.1f}%)")
            print(f"  Losing trades: {losing_trades}")

            if winning_trades > 0:
                avg_win = global_df[global_df['profit_dollars'] > 0]['profit_dollars'].mean()
                print(f"  Average win: ${avg_win:.2f}")

            if losing_trades > 0:
                avg_loss = global_df[global_df['profit_dollars'] < 0]['profit_dollars'].mean()
                print(f"  Average loss: ${avg_loss:.2f}")

        # Exit reason breakdown
        if 'exit_reason' in global_df.columns:
            print("\nEXIT REASON BREAKDOWN:")
            exit_counts = global_df['exit_reason'].value_counts()
            for reason, count in exit_counts.items():
                pct = (count / len(global_df) * 100)
                print(f"  {reason}: {count} ({pct:.1f}%)")

        # Signal type breakdown
        if 'entry_signal' in global_df.columns:
            print("\nSIGNAL TYPE BREAKDOWN:")
            signal_counts = global_df['entry_signal'].value_counts()
            for signal, count in signal_counts.items():
                pct = (count / len(global_df) * 100)
                print(f"  {signal}: {count} ({pct:.1f}%)")

    if skipped_dates:
        print(f"\nSKIPPED DATES (no signals):")
        for date in skipped_dates:
            print(f"  - {date}")

    if failed_dates:
        print(f"\nFAILED DATES (errors during processing):")
        for date in failed_dates:
            print(f"  - {date}")

    print("\nOUTPUT FILES:")
    print(f"  Daily CSVs: {TRACKING_DIR}/tracking_record_YYYYMMDD.csv")
    print(f"  Global CSV: {TRACKING_DIR}/tracking_record_strat_abs_4_all_days.csv")
    print("=" * 80 + "\n")


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """Main execution function."""
    start_time = datetime.now()

    print_header("BATCH PROCESSING - ABSORTION SHAPE STRATEGY")

    print("CONFIGURATION:")
    print(f"  Symbol: {SYMBOL}")
    print(f"  Take Profit: {TP_POINTS} points")
    print(f"  Stop Loss: {SL_POINTS} points")
    print(f"  Contracts: {CONTRACTS}")
    print(f"  Max Open Contracts: {NUM_MAX_OPEN_CONTRACTS}")
    print(f"  Break-Even Points: {BREAK_EVEN_POINTS}")

    # Create output directory
    TRACKING_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n[OK] Output directory: {TRACKING_DIR}")

    # Step 1: Scan historic files
    historic_files = scan_historic_files()

    if not historic_files:
        print("[ERROR] No time_and_sales files found in data/historic/")
        return

    # Step 2: Process each date
    all_trades_list = []
    processed_dates = []
    skipped_dates = []
    failed_dates = []

    total_files = len(historic_files)

    for idx, (date_str, tns_file) in enumerate(historic_files, 1):
        print(f"\n{'='*80}")
        print(f"PROCESSING DATE {idx}/{total_files}: {date_str}")
        print(f"{'='*80}")

        # Step 2a: Validate signals exist
        signals_file = validate_signals_exist(date_str)

        if signals_file is None:
            print(f"[WARNING] No signals file found for {date_str} - SKIPPING")
            skipped_dates.append(date_str)
            continue

        # Step 2b: Run backtest
        trades_df = run_backtest_for_date(date_str, tns_file, signals_file)

        if trades_df is None:
            failed_dates.append(date_str)
            continue

        # Step 2c: Save daily CSV
        save_daily_csv(trades_df, date_str)

        # Step 2d: Add to global list
        all_trades_list.append(trades_df)
        processed_dates.append(date_str)

    # Step 3: Consolidate all days
    if all_trades_list:
        global_df = consolidate_all_days(all_trades_list)

        if global_df is not None:
            # Step 4: Save global CSV
            save_global_csv(global_df)

            # Step 5: Generate summary report
            generate_summary_report(global_df, processed_dates, skipped_dates, failed_dates)
        else:
            print("[ERROR] Failed to consolidate data")
    else:
        print("\n[ERROR] No data to consolidate - all dates failed or were skipped")

    # Final timing
    elapsed_time = (datetime.now() - start_time).total_seconds()
    print(f"\n[OK] Batch processing completed in {elapsed_time:.1f} seconds")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[ERROR] Batch processing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[ERROR] Fatal error during batch processing: {e}")
        traceback.print_exc()
        sys.exit(1)
