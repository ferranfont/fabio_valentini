# Absorption Strategy Refactoring

## Overview

The absorption strategy code has been refactored into a reusable class-based architecture, making it easy to integrate with external applications and trading systems.

## File Structure

```
strat_absortion/
├── absorption_strategy.py          # Main strategy class (NEW)
├── main.py                         # Simple entry point using the class (REFACTORED)
├── example_external_usage.py       # Usage examples (NEW)
├── rolling_profile.py              # Market profile calculation (unchanged)
└── README_REFACTORING.md           # This file
```

## Key Changes

### 1. AbsorptionStrategy Class (`absorption_strategy.py`)

All detection logic has been encapsulated into the `AbsorptionStrategy` class:

**Features:**
- Configurable parameters via `__init__`
- Reusable from any Python code
- Returns structured results dictionary
- Self-contained with all dependencies
- Clean separation of concerns

**Main Methods:**
- `__init__(...)` - Configure strategy parameters
- `load_data()` - Load and preprocess tick data
- `run()` - Execute detection and return results
- `evaluate_profile_shape()` - Pattern detection logic
- `plot_detection()` - Generate visualizations

### 2. Simplified main.py

The main.py file is now clean and simple:
```python
from absorption_strategy import AbsorptionStrategy

strategy = AbsorptionStrategy(
    csv_path=CSV_PATH,
    profile_window=20,
    min_price_levels=20,
    # ... other parameters
)

results = strategy.run()
```

## Usage

### Option 1: Run as standalone script

```bash
python strat_absortion/main.py
```

This uses the configuration parameters defined at the top of main.py.

### Option 2: Import and use in your code

```python
from strat_absortion.absorption_strategy import AbsorptionStrategy

# Create strategy instance
strategy = AbsorptionStrategy(
    csv_path="path/to/your/data.csv",
    profile_window=20,
    min_price_levels=20,
    min_bid_ask_size=30,
    filter_ny_hours=True,
)

# Run detection
results = strategy.run()

# Access results
print(f"Found {results['detection_count']} detections")
print(f"HTML report: {results['html_path']}")
print(f"CSV signals: {results['csv_path']}")

# Process signal records
for signal in results['signal_records']:
    if signal['shape'] == 'd_shape':
        print(f"LONG at {signal['close_price']}")
```

### Option 3: Integration with trading system

```python
from strat_absortion.absorption_strategy import AbsorptionStrategy

class MyTradingBot:
    def __init__(self):
        self.detector = AbsorptionStrategy(
            profile_window=20,
            filter_ny_hours=True,
            cooldown_period=60,
        )

    def run_analysis(self):
        results = self.detector.run()

        for signal in results['signal_records']:
            self.process_signal(signal)

    def process_signal(self, signal):
        if signal['shape'] == 'd_shape':
            self.send_long_order(signal['close_price'])
        elif signal['shape'] == 'p_shape':
            self.send_short_order(signal['close_price'])
```

## Configuration Parameters

### Detection Parameters
- `profile_window` (int): Rolling window size in seconds (default: 20)
- `extreme_volume_multiplier` (float): Volume multiplier threshold (default: 2.0)
- `min_price_levels` (int): Minimum active price levels (default: 20)
- `min_bid_ask_size` (int): Minimum BID/ASK bar size (default: 30)
- `price_position_threshold` (float): Price position threshold 0-1 (default: 0.3)
- `diff_distance` (float): Minimum price difference (default: 0.0)
- `min_volume` (int): Minimum total volume (default: 10)

### Time Filtering
- `filter_ny_hours` (bool): Filter for NY trading hours (default: False)
- `filter_european_hours` (bool): Filter for European hours (default: False)

### Detection Timing
- `cooldown_period` (int): Seconds between detections (default: 60)
- `warmup_period` (int): Warmup seconds before detection (default: 60)

### Paths
- `csv_path` (Path): Path to tick data CSV (default: auto-detected)
- `output_dir` (Path): Output directory for CSV (default: outputs/absortion_shape)
- `charts_dir` (Path): Charts directory for HTML (default: charts/detections)

## Return Value

The `run()` method returns a dictionary with:

```python
{
    'detection_count': int,           # Number of patterns detected
    'html_path': Path,                # Path to HTML report
    'csv_path': Path,                 # Path to signals CSV (or None)
    'signal_records': List[Dict],     # List of signal dictionaries
}
```

Each signal record contains:
```python
{
    'timestamp': str,                 # Detection timestamp
    'shape': str,                     # 'd_shape' or 'p_shape'
    'close_price': float,             # Price at detection
    'total_bid': float,               # Total BID volume
    'total_ask': float,               # Total ASK volume
    'bid_ask_ratio': float,           # BID/ASK ratio
    'num_price_levels': int,          # Active price levels
}
```

## Migration Guide

### Old Code (procedural)
```python
# Edit main.py configuration constants
PROFILE_WINDOW = 20
MIN_PRICE_LEVELS = 20
# ... run the entire script
```

### New Code (class-based)
```python
from absorption_strategy import AbsorptionStrategy

strategy = AbsorptionStrategy(
    profile_window=20,
    min_price_levels=20,
)
results = strategy.run()
```

## Benefits

1. **Reusability**: Import and use from any Python code
2. **Testability**: Easy to unit test individual methods
3. **Flexibility**: Configure at runtime, not edit-time
4. **Integration**: Simple to integrate with trading systems
5. **Maintainability**: Clear separation of concerns
6. **Backwards Compatible**: main.py still works the same way

## Examples

See `example_external_usage.py` for complete working examples:
- Basic usage with custom parameters
- Using custom CSV files
- Accessing signal data
- Integration with trading systems

## Notes

- The original main.py functionality is preserved
- All outputs (HTML, CSV) are generated the same way
- matplotlib backend is set to 'Agg' (non-interactive)
- European CSV format is supported (semicolon separator, comma decimal)
- DOM format CSV is also supported (auto-detected)

## Support

For questions or issues with the refactored code, refer to:
- `absorption_strategy.py` - Main class implementation
- `example_external_usage.py` - Usage examples
- Original `CLAUDE.md` - Project documentation
