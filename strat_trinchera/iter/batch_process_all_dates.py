"""
Batch Process All Dates
Automatically runs the Trinchera pipeline for all available dates in data/historic/
Stores results in iter/iter_summary/ organized by date
"""

import subprocess
import sys
from pathlib import Path
import re
import shutil
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================
CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parent
DATA_DIR = REPO_ROOT / "data" / "historic"
CONFIG_FILE = REPO_ROOT / "config_trinchera.py"
MAIN_SCRIPT = REPO_ROOT / "main_trinchera.py"

# Output directories
ITER_SUMMARY_DIR = CURRENT_DIR / "iter_summary"
ITER_SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 80)
print("TRINCHERA BATCH PROCESSOR - ALL DATES")
print("=" * 80)
print(f"\nData directory: {DATA_DIR}")
print(f"Output directory: {ITER_SUMMARY_DIR}")

# ============================================================================
# STEP 1: FIND ALL DATES
# ============================================================================
print("\n" + "=" * 80)
print("STEP 1: SCANNING DATA DIRECTORY")
print("=" * 80)

# Find all CSV files matching pattern time_and_sales_nq_YYYYMMDD.csv
csv_files = sorted(DATA_DIR.glob("time_and_sales_nq_????????.csv"))
dates = []

for csv_file in csv_files:
    # Extract date from filename
    match = re.search(r'time_and_sales_nq_(\d{8})\.csv', csv_file.name)
    if match:
        date = match.group(1)
        dates.append(date)

print(f"\n[OK] Found {len(dates)} dates to process:")
for i, date in enumerate(dates, 1):
    print(f"  {i:2d}. {date}")

if not dates:
    print("\n[ERROR] No data files found in data/historic/")
    print("[ERROR] Looking for files matching: time_and_sales_nq_YYYYMMDD.csv")
    sys.exit(1)

# ============================================================================
# STEP 2: PROCESS EACH DATE
# ============================================================================
print("\n" + "=" * 80)
print(f"STEP 2: PROCESSING {len(dates)} DATES")
print("=" * 80)

# Track results
results = []
successful = 0
failed = 0

for idx, date in enumerate(dates, 1):
    print("\n" + "=" * 80)
    print(f"PROCESSING DATE {idx}/{len(dates)}: {date}")
    print("=" * 80)

    # Update config_trinchera.py with current date
    print(f"\n[INFO] Updating config_trinchera.py with DATE = '{date}'")

    try:
        # Read config file
        config_content = CONFIG_FILE.read_text(encoding='utf-8')

        # Replace DATE value
        new_config = re.sub(
            r'DATE = "\d{8}"',
            f'DATE = "{date}"',
            config_content
        )

        # Write updated config
        CONFIG_FILE.write_text(new_config, encoding='utf-8')
        print(f"[OK] Config updated: DATE = '{date}'")

    except Exception as e:
        print(f"[ERROR] Failed to update config: {e}")
        failed += 1
        results.append({
            'date': date,
            'status': 'FAILED',
            'error': f'Config update failed: {e}'
        })
        continue

    # Run main_trinchera.py
    print(f"\n[INFO] Running main_trinchera.py for date {date}...")

    try:
        result = subprocess.run(
            [sys.executable, str(MAIN_SCRIPT)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )

        if result.returncode == 0:
            print(f"\n[OK] Pipeline completed successfully for {date}")

            # Move outputs to iter_summary/{date}/
            date_output_dir = ITER_SUMMARY_DIR / date
            date_output_dir.mkdir(parents=True, exist_ok=True)

            # Copy CSV outputs
            outputs_dir = REPO_ROOT / "outputs"
            for csv_file in outputs_dir.glob(f"*_{date}.csv"):
                dest = date_output_dir / csv_file.name
                shutil.copy2(csv_file, dest)
                print(f"[OK] Copied: {csv_file.name} → iter_summary/{date}/")

            # Copy HTML charts
            charts_dir = REPO_ROOT / "charts"
            for html_file in charts_dir.glob(f"*_{date}.html"):
                dest = date_output_dir / html_file.name
                shutil.copy2(html_file, dest)
                print(f"[OK] Copied: {html_file.name} → iter_summary/{date}/")

            successful += 1
            results.append({
                'date': date,
                'status': 'SUCCESS',
                'error': None
            })

        else:
            print(f"\n[ERROR] Pipeline failed for {date}")
            print(f"[ERROR] Return code: {result.returncode}")
            if result.stderr:
                print(f"[ERROR] Error output:\n{result.stderr[:500]}")

            failed += 1
            results.append({
                'date': date,
                'status': 'FAILED',
                'error': f'Return code {result.returncode}'
            })

    except subprocess.TimeoutExpired:
        print(f"\n[ERROR] Pipeline timeout for {date} (exceeded 10 minutes)")
        failed += 1
        results.append({
            'date': date,
            'status': 'FAILED',
            'error': 'Timeout (>10 min)'
        })

    except Exception as e:
        print(f"\n[ERROR] Exception while processing {date}: {e}")
        failed += 1
        results.append({
            'date': date,
            'status': 'FAILED',
            'error': str(e)
        })

# ============================================================================
# STEP 3: SUMMARY REPORT
# ============================================================================
print("\n" + "=" * 80)
print("BATCH PROCESSING COMPLETED")
print("=" * 80)

print(f"\nTotal dates processed: {len(dates)}")
print(f"Successful: {successful} ({successful/len(dates)*100:.1f}%)")
print(f"Failed: {failed} ({failed/len(dates)*100:.1f}%)")

print("\n" + "-" * 80)
print("DETAILED RESULTS:")
print("-" * 80)

for result in results:
    status_symbol = "✓" if result['status'] == 'SUCCESS' else "✗"
    print(f"{status_symbol} {result['date']}: {result['status']}", end="")
    if result['error']:
        print(f" - {result['error']}")
    else:
        print()

# Save summary to CSV
summary_file = ITER_SUMMARY_DIR / f"batch_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
with open(summary_file, 'w') as f:
    f.write("date;status;error\n")
    for result in results:
        error = result['error'].replace(';', ',') if result['error'] else ''
        f.write(f"{result['date']};{result['status']};{error}\n")

print(f"\n[OK] Summary saved to: {summary_file.name}")

print("\n" + "=" * 80)
print(f"[SUCCESS] Batch processing completed!")
print(f"[SUCCESS] Results stored in: {ITER_SUMMARY_DIR}")
print("=" * 80)
