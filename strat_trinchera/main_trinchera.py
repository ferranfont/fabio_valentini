"""
Main Trinchera Pipeline
Executes the complete workflow:
1. Detect big volume events (find_big_volume.py)
2. Generate visualization chart (plot_trinchera.py)
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

# Step 2: Generate visualization
print("\n" + "="*80)
print("STEP 2: GENERATING VISUALIZATION")
print("="*80)

plot_trinchera_script = CURRENT_DIR / "plot_trinchera.py"
result = subprocess.run([sys.executable, str(plot_trinchera_script)], cwd=str(CURRENT_DIR))

if result.returncode != 0:
    print("\n[ERROR] Visualization generation failed!")
    sys.exit(1)

# Final summary
print("\n" + "="*80)
print("PIPELINE COMPLETED SUCCESSFULLY!")
print("="*80)
print("\nFiles generated:")
print(f"  - db_trinchera_bins.csv (big volume events)")
print(f"  - charts/trinchera/chart_trinchera.html (visualization)")
print("\n" + "="*80)
