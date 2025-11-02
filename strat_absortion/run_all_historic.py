"""
Run absorption detection and trading strategy on all historic data files.

This script iterates through all CSV files in data/historic/ and runs
main.py for each file, collecting results and generating summary reports.

Usage:
    python strat_absortion/run_all_historic.py
"""

import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

# ========= PATHS =========
PROJECT_ROOT = Path(__file__).parent.parent
DATA_HISTORIC_DIR = PROJECT_ROOT / "data" / "historic"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
CHARTS_DIR = PROJECT_ROOT / "charts"

# Main script to run
MAIN_SCRIPT = PROJECT_ROOT / "strat_absortion" / "main.py"

def find_historic_files():
    """Find all CSV files in data/historic directory."""
    if not DATA_HISTORIC_DIR.exists():
        print(f"[ERROR] Historic data directory not found: {DATA_HISTORIC_DIR}")
        return []

    # Find all time_and_sales CSV files
    csv_files = sorted(DATA_HISTORIC_DIR.glob("time_and_sales_*.csv"))

    return csv_files

def run_strategy_on_file(csv_file):
    """Run main.py with the specified CSV file."""
    print(f"\n{'=' * 80}")
    print(f"Processing: {csv_file.name}")
    print(f"{'=' * 80}")

    # Set environment variable for the source CSV
    env = os.environ.copy()
    env['ABSORTION_SOURCE_CSV'] = str(csv_file)

    try:
        # Run the main script
        result = subprocess.run(
            [sys.executable, str(MAIN_SCRIPT)],
            env=env,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
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
            print(f"[ERROR] Failed to process {csv_file.name} (exit code: {result.returncode})")
            return False

    except subprocess.TimeoutExpired:
        print(f"[ERROR] Timeout processing {csv_file.name}")
        return False
    except Exception as e:
        print(f"[ERROR] Exception processing {csv_file.name}: {e}")
        return False

def aggregate_results():
    """Aggregate all trade results from outputs directory."""
    print(f"\n{'=' * 80}")
    print("AGGREGATING RESULTS")
    print(f"{'=' * 80}")

    # Find all trade CSV files
    trade_files = sorted(OUTPUTS_DIR.glob("trades_*.csv"))

    if not trade_files:
        print("No trade files found to aggregate")
        return

    all_trades = []
    for trade_file in trade_files:
        try:
            df = pd.read_csv(trade_file, sep=';', decimal=',')
            df['source_file'] = trade_file.name
            all_trades.append(df)
        except Exception as e:
            print(f"[WARNING] Could not read {trade_file.name}: {e}")

    if not all_trades:
        print("No valid trade data found")
        return

    # Combine all trades
    combined_df = pd.concat(all_trades, ignore_index=True)

    # Calculate summary statistics
    total_trades = len(combined_df)
    winning_trades = len(combined_df[combined_df['profit_dollars'] > 0])
    losing_trades = len(combined_df[combined_df['profit_dollars'] <= 0])
    total_profit = combined_df['profit_dollars'].sum()
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

    print(f"\nAGGREGATED RESULTS:")
    print(f"  Total files processed: {len(trade_files)}")
    print(f"  Total trades: {total_trades}")
    print(f"  Winning trades: {winning_trades}")
    print(f"  Losing trades: {losing_trades}")
    print(f"  Win rate: {win_rate:.1f}%")
    print(f"  Total P&L: ${total_profit:,.2f}")

    # Group by date
    if 'entry_time' in combined_df.columns:
        combined_df['entry_time'] = pd.to_datetime(combined_df['entry_time'])
        combined_df['date'] = combined_df['entry_time'].dt.date

        print(f"\nP&L BY DATE:")
        daily_pnl = combined_df.groupby('date')['profit_dollars'].agg(['sum', 'count'])
        daily_pnl.columns = ['P&L', 'Trades']
        for date, row in daily_pnl.iterrows():
            print(f"  {date}: ${row['P&L']:+,.2f} ({int(row['Trades'])} trades)")

    # Save aggregated results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    aggregated_file = OUTPUTS_DIR / f"all_trades_aggregated_{timestamp}.csv"
    combined_df.to_csv(aggregated_file, sep=';', decimal=',', index=False)
    print(f"\nAggregated trades saved to: {aggregated_file}")

    # Create summary report
    summary_file = OUTPUTS_DIR / f"summary_report_{timestamp}.txt"
    with open(summary_file, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("ABSORPTION STRATEGY - HISTORIC BACKTEST SUMMARY\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"Files processed: {len(trade_files)}\n")
        f.write(f"Total trades: {total_trades}\n")
        f.write(f"Winning trades: {winning_trades}\n")
        f.write(f"Losing trades: {losing_trades}\n")
        f.write(f"Win rate: {win_rate:.1f}%\n")
        f.write(f"Total P&L: ${total_profit:,.2f}\n\n")

        if 'entry_time' in combined_df.columns:
            f.write("DAILY BREAKDOWN:\n")
            f.write("-" * 80 + "\n")
            for date, row in daily_pnl.iterrows():
                f.write(f"{date}: ${row['P&L']:+10,.2f} ({int(row['Trades']):3d} trades)\n")

        f.write("\n" + "=" * 80 + "\n")

    print(f"Summary report saved to: {summary_file}")

def main():
    """Main execution function."""
    print("=" * 80)
    print("ABSORPTION STRATEGY - HISTORIC DATA BATCH PROCESSOR")
    print("=" * 80)

    # Find all historic files
    csv_files = find_historic_files()

    if not csv_files:
        print("[ERROR] No CSV files found in data/historic/")
        return 1

    print(f"\nFound {len(csv_files)} historic data files:")
    for i, f in enumerate(csv_files, 1):
        print(f"  {i}. {f.name}")

    # Confirm before processing
    print(f"\nThis will process {len(csv_files)} files. Continue? [y/N]: ", end='')
    response = input().strip().lower()

    if response != 'y':
        print("Aborted by user")
        return 0

    # Process each file
    successful = 0
    failed = 0

    for i, csv_file in enumerate(csv_files, 1):
        print(f"\n[{i}/{len(csv_files)}] Processing {csv_file.name}...")

        if run_strategy_on_file(csv_file):
            successful += 1
        else:
            failed += 1

    # Summary
    print(f"\n{'=' * 80}")
    print("BATCH PROCESSING COMPLETE")
    print(f"{'=' * 80}")
    print(f"Successful: {successful}/{len(csv_files)}")
    print(f"Failed: {failed}/{len(csv_files)}")

    # Aggregate results
    if successful > 0:
        aggregate_results()

    print(f"{'=' * 80}\n")

    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
