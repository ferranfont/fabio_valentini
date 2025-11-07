"""
Main entry point for Absorption Strategy
Detects d-shape and p-shape absorption patterns using rolling market profiles.
"""

from pathlib import Path
from absorption_strategy import AbsorptionStrategy


# Configuration - modify these parameters as needed
FICHERO_ORIGEN = "time_and_sales_nq_20250915_redux"

# Profile shape detection configuration
PROFILE_WINDOW = 20  # Rolling window size in seconds
EXTREME_VOLUME_MULTIPLIER = 2  # Extreme bar must be N times the second-largest overall
MIN_PRICE_LEVELS = 20  # Minimum number of active price levels
MIN_BID_ASK_SIZE = 30  # Minimum absolute size of largest BID/ASK bar
PRICE_POSITION_THRESHOLD = 0.3  # Price must be in lower/upper 30% of the profile range
DIFF_DISTANCE = 0  # Minimum absolute price difference between current and previous close
MIN_VOLUME = 10  # Minimum total volume (BID + ASK) in the profile

# Time filtering configuration
FILTER_NY_HOURS = False  # Set to True to filter for NY hours only
FILTER_EUROPEAN_HOURS = False  # Set to True to filter for European hours only

# Detection timing configuration
COOLDOWN_PERIOD = 60  # Cooldown period in seconds between detections
WARMUP_PERIOD = 60  # Warmup period in seconds before starting detection

# Paths (optional - will use defaults if None)
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"
CSV_PATH = DATA_DIR / f"historic/{FICHERO_ORIGEN}.csv"


if __name__ == "__main__":
    print("mpld3 disabled; using static HTML export without interactivity.")

    # Create strategy instance with configuration
    strategy = AbsorptionStrategy(
        csv_path=CSV_PATH,
        profile_window=PROFILE_WINDOW,
        extreme_volume_multiplier=EXTREME_VOLUME_MULTIPLIER,
        min_price_levels=MIN_PRICE_LEVELS,
        min_bid_ask_size=MIN_BID_ASK_SIZE,
        price_position_threshold=PRICE_POSITION_THRESHOLD,
        diff_distance=DIFF_DISTANCE,
        min_volume=MIN_VOLUME,
        filter_ny_hours=FILTER_NY_HOURS,
        filter_european_hours=FILTER_EUROPEAN_HOURS,
        cooldown_period=COOLDOWN_PERIOD,
        warmup_period=WARMUP_PERIOD,
    )

    # Run the strategy
    results = strategy.run()

    # Results are available in the returned dictionary
    # results contains: detection_count, html_path, csv_path, signal_records
