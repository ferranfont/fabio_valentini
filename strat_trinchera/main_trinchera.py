"""
Main Trinchera Pipeline
Executes the complete workflow:
1. Detect big volume events (find_big_volume.py)
2. Execute trading strategy (strat_trinchera.py)
3. Generate trades visualization chart (plot_trinchera_trades.py)
4. Generate summary report (summary_trinchera.py)
5. Generate equity curve (plot_equity_trinchera.py)
"""

import subprocess
import sys
from pathlib import Path
from config_trinchera import BIG_VOLUME_TRIGGER

# ============================================================================
# CONFIGURATION
# ============================================================================
CURRENT_DIR = Path(__file__).resolve().parent

print("="*80)
print("TRINCHERA MAIN PIPELINE")
print("="*80)
print(f"\nConfiguration:")
print(f"  - Big Volume Trigger: {BIG_VOLUME_TRIGGER}")

# Step 1: Detect big volume events
print("\n" + "="*80)
print("STEP 1: DETECTING BIG VOLUME EVENTS")
print("="*80)

find_big_volume_script = CURRENT_DIR / "find_big_volume.py"
# Pass BIG_VOLUME_TRIGGER as command line argument
result = subprocess.run(
    [sys.executable, str(find_big_volume_script), str(BIG_VOLUME_TRIGGER)],
    cwd=str(CURRENT_DIR)
)

if result.returncode != 0:
    print("\n[ERROR] Big volume detection failed!")
    sys.exit(1)

# Step 2: Execute trading strategy
print("\n" + "="*80)
print("STEP 2: EXECUTING TRADING STRATEGY")
print("="*80)

strat_trinchera_script = CURRENT_DIR / "strat_trinchera.py"
result = subprocess.run([sys.executable, str(strat_trinchera_script)], cwd=str(CURRENT_DIR))

if result.returncode != 0:
    print("\n[ERROR] Strategy execution failed!")
    sys.exit(1)

# Step 3: Generate trades visualization
print("\n" + "="*80)
print("STEP 3: GENERATING TRADES VISUALIZATION")
print("="*80)

plot_trinchera_trades_script = CURRENT_DIR / "plot_trinchera_trades.py"
result = subprocess.run([sys.executable, str(plot_trinchera_trades_script)], cwd=str(CURRENT_DIR))

if result.returncode != 0:
    print("\n[ERROR] Trades visualization generation failed!")
    sys.exit(1)

# Step 4: Generate summary report
print("\n" + "="*80)
print("STEP 4: GENERATING SUMMARY REPORT")
print("="*80)

summary_trinchera_script = CURRENT_DIR / "summary_trinchera.py"
result = subprocess.run([sys.executable, str(summary_trinchera_script)], cwd=str(CURRENT_DIR))

if result.returncode != 0:
    print("\n[ERROR] Summary report generation failed!")
    sys.exit(1)

# Step 5: Generate equity curve
print("\n" + "="*80)
print("STEP 5: GENERATING EQUITY CURVE")
print("="*80)

plot_equity_script = CURRENT_DIR / "plot_equity_trinchera.py"
result = subprocess.run([sys.executable, str(plot_equity_script)], cwd=str(CURRENT_DIR))

if result.returncode != 0:
    print("\n[ERROR] Equity curve generation failed!")
    sys.exit(1)

# Final summary
print("\n" + "="*80)
print("PIPELINE COMPLETED SUCCESSFULLY!")
print("="*80)
print("\nFiles generated:")
print(f"  - outputs/db_trinchera_bins_YYYYMMDD.csv (big volume events)")
print(f"  - outputs/db_trinchera_TR_YYYYMMDD.csv (trades)")
print(f"  - charts/chart_trinchera_trades_YYYYMMDD.html (trades visualization)")
print(f"  - charts/summary_trinchera_YYYYMMDD.html (summary report)")
print(f"  - charts/equity_trinchera_YYYYMMDD.html (equity curve)")
print("\n" + "="*80)
