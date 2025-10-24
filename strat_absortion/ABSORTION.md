# Market Profile d-Shape & p-Shape Detection

## Overview

Advanced real-time Market Profile analysis system for NQ futures that detects volume absorption patterns (d-Shape and p-Shape) using rolling 60-second windows and 500ms timestamp aggregation.

**Current Version:** 2.0 (Tick-Driven Architecture with 500ms aggregation)

---

## Quick Start

```bash
# Run pattern detection on full 2-day dataset
python strat_absortion/plot_deep.py
```

**What it does:**
1. Loads 448,332 NQ tick records
2. Aggregates to 172,783 timestamps (500ms intervals)
3. Computes rolling Market Profile (60-second window)
4. Detects d-Shape and p-Shape patterns
5. Saves signals to `outputs/db_shapes_YYYYMMDD_HHMMSS.csv`
6. Opens interactive matplotlib visualization with mplcursors tooltips

**Performance:**
- Duration: ~3-4 minutes
- Patterns detected: ~1,000 (422 d-shapes, 582 p-shapes)
- Memory peak: ~500MB

---

## Pattern Definitions

### d-Shape (BID Absorption) - BULLISH Signal

**Concept:** Large BID volume in lower prices indicates buyers defending a level by absorbing selling pressure.

**Visual Characteristics:**
- Concentrated BID volume (red bars) in lower half of profile
- Price positioned in lower portion of profile range
- Strong absorption indicates potential reversal to upside

**Detection Criteria (ALL must be met):**
1. **Minimum 10 active price levels** (`MIN_PRICE_LEVELS`)
2. **At least one BID bar ≥ 20** in lower half (`MIN_BID_ASK_SIZE`)
3. **≥70% of total BID volume in lower half** (`DENSITY_SHAPE`)
4. **Total profile size ≥ 20 contracts** (`MIN_SIZE`)
5. **Price in LOWER 25% of profile range** (`PRICE_POSITION_THRESHOLD`)

**Interpretation:**
- Buyers are actively defending lower prices
- Despite selling pressure, price is not collapsing
- Potential bullish reversal setup

---

### p-Shape (ASK Absorption) - BEARISH Signal

**Concept:** Large ASK volume in upper prices indicates sellers defending a level by absorbing buying pressure.

**Visual Characteristics:**
- Concentrated ASK volume (green bars) in upper half of profile
- Price positioned in upper portion of profile range
- Strong absorption indicates potential reversal to downside

**Detection Criteria (ALL must be met):**
1. **Minimum 10 active price levels** (`MIN_PRICE_LEVELS`)
2. **At least one ASK bar ≥ 20** in upper half (`MIN_BID_ASK_SIZE`)
3. **≥70% of total ASK volume in upper half** (`DENSITY_SHAPE`)
4. **Total profile size ≥ 20 contracts** (`MIN_SIZE`)
5. **Price in UPPER 25% of profile range** (1 - `PRICE_POSITION_THRESHOLD`)

**Interpretation:**
- Sellers are actively defending upper prices
- Despite buying pressure, price is not breaking higher
- Potential bearish reversal setup

---

## Configuration

### File: `strat_absortion/plot_deep.py`

**Lines 19-29:**
```python
# Starting position
STARTING_INDEX = 0                    # Frame to start visualization
STARTING_TIME = None                  # Or set specific time: "2025-10-09 18:02:25"
PROFILE_FREQUENCY = 5                 # NOT USED (legacy, now uses 60s fixed)

# Pattern detection parameters
DENSITY_SHAPE = 0.70                  # 70% volume concentration required
MIN_PRICE_LEVELS = 10                 # Minimum active price levels
MIN_BID_ASK_SIZE = 20                 # Minimum size of largest bar
PRICE_POSITION_THRESHOLD = 0.25       # Price must be in lower/upper 25%
```

**Lines 33-34:**
```python
# Data file selection
csv_path = "data/time_and_sales_nq.csv"         # Full 2-day dataset (default)
# csv_path = "data/time_and_sales_nq_30min.csv"  # 30-minute subset for testing
```

**Lines 46-48:**
```python
# Timestamp aggregation (FIXED in code)
timestamps = pd.date_range(start=start_time, end=end_time, freq="500ms")
```

**Lines in RollingMarketProfile (rolling_profile.py):**
```python
window_duration = timedelta(seconds=60)  # FIXED: 60-second rolling window
```

---

## Parameter Tuning

### More Strict Detection (Fewer, Higher Quality Signals)

```python
DENSITY_SHAPE = 0.75                  # Increase to 75%
MIN_PRICE_LEVELS = 12                 # Increase to 12
MIN_BID_ASK_SIZE = 25                 # Increase to 25
PRICE_POSITION_THRESHOLD = 0.20       # Reduce to 20% (more extreme)
```

**Expected Result:**
- Fewer patterns detected (~500-700)
- Higher concentration of volume
- More extreme price positioning

---

### More Lenient Detection (More Signals)

```python
DENSITY_SHAPE = 0.65                  # Reduce to 65%
MIN_PRICE_LEVELS = 8                  # Reduce to 8
MIN_BID_ASK_SIZE = 15                 # Reduce to 15
PRICE_POSITION_THRESHOLD = 0.33       # Increase to 33%
```

**Expected Result:**
- More patterns detected (~1,500-2,000)
- Lower quality signals
- Less strict volume concentration

---

## Algorithm Details

### 1. Timestamp Aggregation (500ms)

**Purpose:** Balance between precision and performance

```python
# Generate timestamps every 500ms
start_time = df["Timestamp"].min()
end_time = df["Timestamp"].max()
timestamps = pd.date_range(start=start_time, end=end_time, freq="500ms")

# Result: 448,332 ticks → 172,783 timestamps
```

**Why 500ms?**
- **Tick-level** (no aggregation): Maximum precision, but 448K frames makes UI slow
- **500ms aggregation**: Balanced precision/performance, ~173K frames
- **10s aggregation** (old): Too coarse, loses detail

---

### 2. Rolling Market Profile (60-second window)

**Implementation:** Single `RollingMarketProfile` instance processes ticks sequentially

```python
profile_calculator = RollingMarketProfile()

for ts in timestamps:
    # Get ticks in this 500ms window
    window_ticks = df[
        (df["Timestamp"] >= ts) &
        (df["Timestamp"] < ts + timedelta(milliseconds=500))
    ]

    # Update profile with each tick
    for _, tick in window_ticks.iterrows():
        profile_calculator.add_tick(
            timestamp=tick["Timestamp"],
            price=tick["Precio"],
            volume=tick["Volumen"],
            side=tick["Lado"]
        )

    # Get current 60-second profile snapshot
    profile = profile_calculator.get_profile()
```

**Key Fix:** Uses ONE profile calculator instance, not recreating for each window (critical performance bug fixed).

---

### 3. Volume Concentration Calculation

```python
# Get all active price levels sorted
price_levels = sorted(profile.keys())
mid_point = len(price_levels) // 2

# Split into lower and upper halves
lower_prices = price_levels[:mid_point]
upper_prices = price_levels[mid_point:]

# Calculate concentrations
lower_bid_volume = sum(profile[p]["bid_volume"] for p in lower_prices)
upper_ask_volume = sum(profile[p]["ask_volume"] for p in upper_prices)

total_bid = sum(profile[p]["bid_volume"] for p in price_levels)
total_ask = sum(profile[p]["ask_volume"] for p in price_levels)

bid_concentration = lower_bid_volume / total_bid if total_bid > 0 else 0
ask_concentration = upper_ask_volume / total_ask if total_ask > 0 else 0
```

---

### 4. Price Position Calculation

```python
# Calculate where price is in the profile range (0 = bottom, 1 = top)
min_price = min(price_levels)
max_price = max(price_levels)
price_range = max_price - min_price

if price_range > 0:
    price_position = (current_close - min_price) / price_range
else:
    price_position = 0.5  # Center if no range

# For d-Shape: price_position <= 0.25 (lower 25%)
# For p-Shape: price_position >= 0.75 (upper 25%)
```

---

### 5. Pattern Detection Logic

```python
# Find largest bars in each half
max_lower_bid = max([profile[p]["bid_volume"] for p in lower_prices], default=0)
max_upper_ask = max([profile[p]["ask_volume"] for p in upper_prices], default=0)

# Calculate total profile size
total_size = total_bid + total_ask

# d-Shape detection (LONG signal)
is_d_shape = (
    len(price_levels) >= MIN_PRICE_LEVELS and           # Enough levels
    max_lower_bid >= MIN_BID_ASK_SIZE and               # Large BID bar exists
    bid_concentration >= DENSITY_SHAPE and              # 70% concentration
    total_size >= MIN_SIZE and                          # Minimum total volume
    price_position <= PRICE_POSITION_THRESHOLD          # Price in lower 25%
)

# p-Shape detection (SHORT signal)
is_p_shape = (
    len(price_levels) >= MIN_PRICE_LEVELS and           # Enough levels
    max_upper_ask >= MIN_BID_ASK_SIZE and               # Large ASK bar exists
    ask_concentration >= DENSITY_SHAPE and              # 70% concentration
    total_size >= MIN_SIZE and                          # Minimum total volume
    price_position >= (1 - PRICE_POSITION_THRESHOLD)    # Price in upper 25%
)
```

---

## Data Files

### Input

**Primary:**
- **Location:** `data/time_and_sales_nq.csv`
- **Size:** 448,332 tick records (2 days: Oct 9-10, 2025)
- **Format:** European CSV (`;` separator, `,` decimal)
- **Columns:** Timestamp, Precio, Volumen, Lado, Bid, Ask

**Testing:**
- **Location:** `data/time_and_sales_nq_30min.csv`
- **Size:** 19,794 records (30-minute subset)
- **Purpose:** Quick testing and validation

---

### Output

**Signal CSV:**
- **Location:** `outputs/db_shapes_YYYYMMDD_HHMMSS.csv`
- **Format:** European CSV (`;` separator, `,` decimal)
- **Purpose:** Trading signal database for backtesting

**CSV Columns:**

| Column | Description |
|--------|-------------|
| `timestamp` | Date and time of pattern detection |
| `shape` | Pattern type: `d_shape` or `p_shape` |
| `close_price` | Current close price at detection |
| `bid_ask_ratio` | BID/ASK volume ratio |
| `num_price_levels` | Number of active price levels |
| `max_lower_bid` | Largest BID bar in lower half |
| `max_upper_ask` | Largest ASK bar in upper half |
| `bid_concentration` | % of BID volume in lower half (0.0-1.0) |
| `ask_concentration` | % of ASK volume in upper half (0.0-1.0) |
| `lower_bid_volume` | Total BID volume in lower half |
| `upper_ask_volume` | Total ASK volume in upper half |
| `total_bid` | Total BID volume in profile |
| `total_ask` | Total ASK volume in profile |
| `total_size` | Total volume (BID + ASK) |
| `price_position` | Price position in profile range (0.0-1.0) |
| `min_price` | Lowest price in profile |
| `max_price` | Highest price in profile |

**Example Row:**
```csv
2025-10-09 18:45:32.500;d_shape;25328.75;1.15;12;35;8;0.72;0.45;280;120;390;170;560;0.24;25326.50;25330.25
```

---

## Interactive Visualization

### Controls

**Slider:**
- Navigate to any frame (0 to total_frames-1)
- Real-time profile update

**Buttons:**
- **Previous:** Move back one frame
- **Next:** Move forward one frame
- **Play:** Auto-advance at 500ms per frame
- **Pause:** Stop animation

**Tooltips (mplcursors):**
- Hover over any BID/ASK bar to see:
  - Price level
  - Volume
  - Percentage of total

---

### Visual Elements

**Market Profile Panels:**
- Red bars (left): BID volume by price level
- Green bars (right): ASK volume by price level
- Blue dot (center): Current close price
- Info box: Total BID, total ASK, ratio, pattern type

**Price Chart:**
- Grey line: Price evolution over time
- Blue dot: Current price
- Horizontal grid only (no vertical)
- Info box: Close price

---

## Using Signals for Trading

### Loading Signals

```python
import pandas as pd

# Load signals
df = pd.read_csv('outputs/db_shapes_20251024_003251.csv', sep=';', decimal=',')

# Filter by pattern type
d_shapes = df[df['shape'] == 'd_shape']
p_shapes = df[df['shape'] == 'p_shape']

print(f"d-Shape signals: {len(d_shapes)}")
print(f"p-Shape signals: {len(p_shapes)}")
```

---

### Quality Filtering

```python
# High-quality d-Shapes: strong concentration + large bar
quality_d_shapes = df[
    (df['shape'] == 'd_shape') &
    (df['bid_concentration'] >= 0.75) &        # Very strong concentration
    (df['max_lower_bid'] >= 30) &              # Very large bar
    (df['num_price_levels'] >= 12) &           # Wide profile
    (df['total_size'] >= 50)                   # High total volume
]

print(f"High-quality d-Shapes: {len(quality_d_shapes)}")
```

---

### Backtesting Integration

**See:** `strategies/strat_OM_4_absortion/` folder for complete backtesting engine

```python
# The backtest engine uses this CSV:
SIGNALS_FILE = "outputs/db_shapes_20251024_003251.csv"

# Strategy logic:
# - LONG on d_shape detection
# - SHORT on p_shape detection
# - TP: 4.0 points
# - SL: 3.0 points
# - Position control: NUM_MAX_OPEN_CONTRACTS = 1
```

**Results (2-day dataset):**
- Trades: 589
- Win Rate: 50.9%
- Total P&L: $6,660
- Max DD: -$720

---

## Troubleshooting

### Issue: No patterns detected

**Cause:** Parameters too strict for current data

**Solutions:**
```python
# Option 1: Lower thresholds
DENSITY_SHAPE = 0.60              # From 0.70
MIN_BID_ASK_SIZE = 15             # From 20

# Option 2: Adjust price position
PRICE_POSITION_THRESHOLD = 0.33   # From 0.25

# Option 3: Reduce minimum levels
MIN_PRICE_LEVELS = 8              # From 10
```

---

### Issue: Too many patterns detected (>2,000)

**Cause:** Parameters too lenient

**Solutions:**
```python
# Option 1: Increase concentration
DENSITY_SHAPE = 0.75              # From 0.70

# Option 2: Increase minimum bar size
MIN_BID_ASK_SIZE = 25             # From 20

# Option 3: More extreme price position
PRICE_POSITION_THRESHOLD = 0.20   # From 0.25
```

---

### Issue: Visualization window doesn't open

**Cause:** Matplotlib backend issue

**Fix:** Script uses TkAgg backend (should work on Windows)

**Alternative:** If still fails, comment out visualization and check CSV output:
```python
# Comment out the entire "# Interactive visualization" section
# Just run detection and check outputs/db_shapes_*.csv
```

---

### Issue: Slow performance / Memory error

**Cause:** Processing 448K ticks on full dataset

**Solutions:**
```python
# Solution 1: Use 30-minute subset
csv_path = "data/time_and_sales_nq_30min.csv"  # Only 19K records

# Solution 2: Increase aggregation to 1 second
timestamps = pd.date_range(start=start_time, end=end_time, freq="1s")
```

---

### Issue: CSV not generating

**Cause 1:** No patterns detected (see above)

**Cause 2:** Permissions error

**Fix:** Ensure `outputs/` folder exists:
```bash
mkdir outputs
```

---

## File Structure

```
strat_absortion/
├── plot_deep.py              # Main detection script (500ms aggregation)
├── plot_deep_tick.py         # Tick-level backup (no aggregation, slow)
├── rolling_profile.py        # RollingMarketProfile class
├── ABSORTION.md             # This documentation
└── ...

data/
├── time_and_sales_nq.csv         # Full 2-day dataset (448K ticks)
└── time_and_sales_nq_30min.csv   # 30-minute subset (19K ticks)

outputs/
└── db_shapes_YYYYMMDD_HHMMSS.csv   # Generated signals (timestamped)
```

---

## Performance Benchmarks

### Full 2-Day Dataset

**Input:**
- File: `time_and_sales_nq.csv`
- Ticks: 448,332

**Processing:**
- Timestamps: 172,783 (500ms aggregation)
- Duration: ~3-4 minutes
- Memory peak: ~500MB

**Output:**
- Patterns: ~1,000
- d-Shapes: ~422 (42%)
- p-Shapes: ~582 (58%)
- CSV size: ~150 KB

---

### 30-Minute Subset

**Input:**
- File: `time_and_sales_nq_30min.csv`
- Ticks: 19,794

**Processing:**
- Timestamps: ~3,600
- Duration: ~10-15 seconds
- Memory peak: ~100MB

**Output:**
- Patterns: ~20-40
- CSV size: ~5 KB

---

## Development Notes

### Key Improvements vs Legacy

**Before (Old ABSORTION.md):**
- 5-second rolling window
- Manual panel navigation
- No CSV export
- Parameters in multiple places

**After (Current Version 2.0):**
- 60-second rolling window (more stable)
- 500ms timestamp aggregation (balanced performance)
- Automatic CSV export with timestamps
- Centralized configuration
- mplcursors professional tooltips
- Integration with tick-driven backtest engine

---

### Critical Bug Fixed

**Problem:** Old version recreated `RollingMarketProfile` for each timestamp window, losing historical tick data.

**Symptom:** Profiles showed only current 500ms window, not rolling 60s.

**Fix:** Create ONE `profile_calculator` instance and reuse for all timestamps.

```python
# WRONG (old code):
for ts in timestamps:
    profile_calculator = RollingMarketProfile()  # ❌ Recreates, loses history
    # ...

# CORRECT (current code):
profile_calculator = RollingMarketProfile()  # ✅ Create once
for ts in timestamps:
    # Reuse same instance
```

---

## Integration with Trading Strategy

### Workflow

1. **Generate Signals:**
   ```bash
   python strat_absortion/plot_deep.py
   ```
   Output: `outputs/db_shapes_YYYYMMDD_HHMMSS.csv`

2. **Run Backtest:**
   ```bash
   cd strategies/strat_OM_4_absortion
   python main_start.py
   ```
   Uses signals CSV for LONG/SHORT entries

3. **Analyze Results:**
   - Trade visualization: `charts/trades_visualization_absortion_shape_all_day.html`
   - Summary statistics: `charts/summary_report_absortion_shape_all_day.html`
   - Equity curves: `charts/backtest_results_absortion_shape_all_day_*.html`

---

## Future Enhancements

### Planned Features

1. **Real-time streaming:** Connect to live market data feed
2. **Alert system:** Sound/visual alerts when patterns detected
3. **Pattern quality score:** Rate patterns 1-10 based on strength metrics
4. **Multi-timeframe:** Detect patterns on 30s, 60s, 120s windows simultaneously
5. **Historical success rate:** Track which patterns led to profitable moves

### Advanced Analysis

1. **Volume profile clustering:** Identify value areas and POC
2. **Order flow imbalance:** Delta calculations per price level
3. **Time-of-day analysis:** Best times for d-Shape/p-Shape signals
4. **Pattern lifecycle:** Track pattern evolution over next 5-10 minutes

---

## Technical Specifications

**Data Format:**
- CSV separator: `;` (semicolon)
- Decimal: `,` (comma, European)
- Timestamps: Madrid time (CET/CEST)
- Price precision: 2 decimals (0.25 tick size)

**Dependencies:**
- pandas >= 1.3.0
- numpy >= 1.20.0
- matplotlib >= 3.4.0
- mplcursors >= 0.5.0

**Platform:**
- Windows (TkAgg backend)
- Python 3.8+

---

## Version History

### Version 2.0 (Current) - Tick-Driven Architecture
- **500ms timestamp aggregation** (172,783 frames from 448K ticks)
- **60-second rolling window** (fixed in rolling_profile.py)
- **Critical bug fix:** Reuse single RollingMarketProfile instance
- **mplcursors integration:** Professional hover tooltips
- **Automatic CSV export:** Timestamped output files
- **Centralized configuration:** All parameters in one section
- **Integration with backtest engine:** Seamless workflow

### Version 1.0 (Legacy) - Original Implementation
- 5-second rolling window
- Manual frame-by-frame navigation
- No CSV export
- Parameters scattered across code

---

## Credits

**Developed for:** Fabio Valentini NQ Futures Trading Analysis
**Base concept:** Market Profile Theory + Order Flow Absorption
**Data source:** NQ (Nasdaq-100 E-mini) tick data
**Documentation version:** 2.0 (2025-10-24)

---

## Support

For questions or issues:
1. Check the Troubleshooting section
2. Review parameter settings in plot_deep.py (lines 19-29)
3. Verify data file format (European CSV)
4. Check console output for errors

**Remember:** Absorption patterns are one tool in a larger trading system. Always combine with:
- Price action context
- Support/resistance levels
- Overall market structure
- Risk management principles

---

*Last updated: 2025-10-24*
*Version: 2.0 (Tick-Driven Architecture)*
