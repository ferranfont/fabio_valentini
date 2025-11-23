# Trinchera Batch Processing

Automated batch processing for running the Trinchera strategy across multiple dates.

## Overview

The `batch_process_all_dates.py` script automatically:
1. Scans `data/historic/` for all available dates
2. Updates `config_trinchera.py` with each date
3. Runs the complete `main_trinchera.py` pipeline
4. Organizes outputs in `iter/iter_summary/{DATE}/` folders

---

## Quick Start

```bash
cd iter
python batch_process_all_dates.py
```

---

## What It Does

### 1. Automatic Date Detection

Finds all CSV files matching:
```
data/historic/time_and_sales_nq_YYYYMMDD.csv
```

Example:
```
time_and_sales_nq_20250915.csv → DATE = "20250915"
time_and_sales_nq_20251104.csv → DATE = "20251104"
```

### 2. Configuration Update

For each date, updates `config_trinchera.py`:
```python
DATE = "20250915"  # Automatically changed for each iteration
```

### 3. Pipeline Execution

Runs complete workflow for each date:
- ✅ Data processing (`util_trinchera.py`)
- ✅ Big volume detection (`find_big_volume.py`)
- ✅ Strategy execution (`strat_trinchera.py`)
- ✅ Trade visualization (`plot_trinchera_trades.py`)
- ✅ Summary report (`summary_trinchera.py`)
- ✅ Equity curve (`plot_equity_trinchera.py`)

### 4. Output Organization

Results organized by date:
```
iter/iter_summary/
├── 20250915/
│   ├── db_trinchera_all_data_20250915.csv
│   ├── db_trinchera_bins_20250915.csv
│   ├── db_trinchera_TR_20250915.csv
│   ├── chart_trinchera_trades_20250915.html
│   ├── summary_trinchera_20250915.html
│   └── equity_trinchera_20250915.html
├── 20250916/
│   ├── db_trinchera_all_data_20250916.csv
│   └── ...
└── batch_summary_YYYYMMDD_HHMMSS.csv
```

---

## Output Files

### Per-Date Folders (`iter_summary/{DATE}/`)

Each date folder contains:

| File | Description |
|------|-------------|
| `db_trinchera_all_data_{DATE}.csv` | Processed OHLCV + Market Profile data |
| `db_trinchera_bins_{DATE}.csv` | Big volume events detected |
| `db_trinchera_TR_{DATE}.csv` | Executed trades with P&L |
| `chart_trinchera_trades_{DATE}.html` | Interactive trade visualization |
| `summary_trinchera_{DATE}.html` | Performance metrics report |
| `equity_trinchera_{DATE}.html` | Equity curve chart |

### Batch Summary (`batch_summary_YYYYMMDD_HHMMSS.csv`)

CSV file with processing results:
```csv
date;status;error
20250915;SUCCESS;
20250916;FAILED;Timeout (>10 min)
20250917;SUCCESS;
```

---

## Performance

### Processing Time (per date)

- **Typical**: 3-5 minutes per date
- **Total (37 dates)**: ~2-3 hours

### Timeout

- Maximum: 10 minutes per date
- If exceeded, date marked as FAILED and continues with next

---

## Console Output

```
================================================================================
TRINCHERA BATCH PROCESSOR - ALL DATES
================================================================================

Data directory: D:\PYTHON\ALGOS\trinchera_strategy\data\historic
Output directory: D:\PYTHON\ALGOS\trinchera_strategy\iter\iter_summary

================================================================================
STEP 1: SCANNING DATA DIRECTORY
================================================================================

[OK] Found 37 dates to process:
   1. 20250915
   2. 20250916
   ...
  37. 20251104

================================================================================
STEP 2: PROCESSING 37 DATES
================================================================================

================================================================================
PROCESSING DATE 1/37: 20250915
================================================================================

[INFO] Updating config_trinchera.py with DATE = '20250915'
[OK] Config updated: DATE = '20250915'

[INFO] Running main_trinchera.py for date 20250915...

[OK] Pipeline completed successfully for 20250915
[OK] Copied: db_trinchera_all_data_20250915.csv → iter_summary/20250915/
[OK] Copied: db_trinchera_bins_20250915.csv → iter_summary/20250915/
[OK] Copied: db_trinchera_TR_20250915.csv → iter_summary/20250915/
[OK] Copied: chart_trinchera_trades_20250915.html → iter_summary/20250915/
[OK] Copied: summary_trinchera_20250915.html → iter_summary/20250915/
[OK] Copied: equity_trinchera_20250915.html → iter_summary/20250915/

... (continues for all dates)

================================================================================
BATCH PROCESSING COMPLETED
================================================================================

Total dates processed: 37
Successful: 35 (94.6%)
Failed: 2 (5.4%)

--------------------------------------------------------------------------------
DETAILED RESULTS:
--------------------------------------------------------------------------------
✓ 20250915: SUCCESS
✓ 20250916: SUCCESS
✗ 20250917: FAILED - Timeout (>10 min)
✓ 20250918: SUCCESS
...

[OK] Summary saved to: batch_summary_20251122_230045.csv

================================================================================
[SUCCESS] Batch processing completed!
[SUCCESS] Results stored in: D:\PYTHON\ALGOS\trinchera_strategy\iter\iter_summary
================================================================================
```

---

## Error Handling

### Automatic Recovery

- If one date fails, processing continues with next date
- Each failure is logged in batch summary CSV
- Common failures:
  - Timeout (>10 min)
  - Missing data file
  - Configuration update error

### Manual Retry

To reprocess failed dates:

1. Check `batch_summary_*.csv` for failed dates
2. Manually update `config_trinchera.py`:
   ```python
   DATE = "20250917"  # Failed date
   ```
3. Run pipeline:
   ```bash
   cd ..
   python main_trinchera.py
   ```

---

## Customization

### Modify Timeout

Edit `batch_process_all_dates.py`:
```python
timeout=600  # Change from 600 (10 min) to desired seconds
```

### Filter Dates

To process only specific date range:
```python
# Add after line: dates.append(date)
if date < "20251001" or date > "20251031":
    continue  # Skip dates outside October 2025
```

### Change Output Directory

Edit configuration section:
```python
ITER_SUMMARY_DIR = CURRENT_DIR / "custom_output_folder"
```

---

## Troubleshooting

### Issue: Script stops on first error

**Solution**: The script is designed to continue on errors. Check for Python syntax errors in the script itself.

### Issue: Missing output files for a date

**Symptom**: `iter_summary/{DATE}/` folder empty or missing files

**Cause**: Pipeline failed silently

**Solution**:
1. Check `batch_summary_*.csv` for status
2. Run manually for that date:
   ```bash
   # Update config
   DATE = "20250915"

   # Run pipeline
   python main_trinchera.py
   ```

### Issue: All dates fail with config error

**Symptom**:
```
[ERROR] Failed to update config: [Errno 13] Permission denied
```

**Cause**: `config_trinchera.py` is read-only or open in editor

**Solution**: Close any editors with config file open

### Issue: Disk space error

**Symptom**:
```
[ERROR] OSError: [Errno 28] No space left on device
```

**Cause**: Each date generates ~15-20 MB of outputs (37 dates = ~555-740 MB)

**Solution**: Free up disk space before running batch process

---

## Best Practices

### 1. Run Overnight

Batch processing takes ~2-3 hours. Schedule for overnight:
```bash
# Windows Task Scheduler
schtasks /create /tn "Trinchera Batch" /tr "python D:\PYTHON\ALGOS\trinchera_strategy\iter\batch_process_all_dates.py" /sc once /st 23:00
```

### 2. Backup Before Running

```bash
# Backup current outputs
cp -r outputs outputs_backup
cp -r charts charts_backup
```

### 3. Monitor Progress

The script prints progress. To save to log file:
```bash
python batch_process_all_dates.py > batch_log.txt 2>&1
```

### 4. Verify Results

After completion:
1. Check `batch_summary_*.csv` for failures
2. Verify date count: `ls iter_summary/ | wc -l` (should equal number of dates)
3. Spot-check a few HTML reports

---

## Integration with Analysis

### Aggregate Results Across All Dates

Create `aggregate_results.py`:
```python
import pandas as pd
from pathlib import Path

iter_dir = Path("iter_summary")
all_trades = []

for date_folder in sorted(iter_dir.glob("202*")):
    trades_file = date_folder / f"db_trinchera_TR_{date_folder.name}.csv"
    if trades_file.exists():
        df = pd.read_csv(trades_file, sep=';', decimal=',')
        df['date'] = date_folder.name
        all_trades.append(df)

df_all = pd.concat(all_trades, ignore_index=True)
df_all.to_csv("iter_summary/all_trades_combined.csv", sep=';', decimal=',', index=False)

print(f"Total trades across all dates: {len(df_all)}")
print(f"Total P&L: ${df_all['pnl_dollars'].sum():.2f}")
```

---

## Version History

- **v1.0** (2025-11-22): Initial batch processor
  - Automatic date detection
  - Per-date output organization
  - Batch summary CSV

---

**Author**: Ferran Font
**Last Updated**: 2025-11-22
**Status**: Production Ready ✅
