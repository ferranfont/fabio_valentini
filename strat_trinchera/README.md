# Trinchera Mean Reversion Strategy

Advanced mean reversion trading strategy for NQ (Nasdaq-100 E-mini) futures based on big volume detection and price extremes.

## Overview

The Trinchera strategy identifies large volume spikes (>200 contracts) and creates mean reversion levels around the closing price. It trades when price touches these extreme levels (±10 points from the volume spike), expecting the price to revert to the mean.

### Strategy Logic

1. **Big Volume Detection**: Identify frames where `total_volume > BIG_VOLUME_TRIGGER` (default: 200 contracts)
2. **Mean Reversion Levels**: Calculate upper and lower bounds around the big volume close price
   - `mean_level_up = close_price + MEAN_REVERS_EXPAND` (red line, SELL zone)
   - `mean_level_down = close_price - MEAN_REVERS_EXPAND` (green line, BUY zone)
3. **Trade Execution**:
   - **SELL Signal**: When price touches the red line (mean_level_up) → expect price to drop
   - **BUY Signal**: When price touches the green line (mean_level_down) → expect price to rise
4. **Risk Management**:
   - Take Profit: 5 points ($100)
   - Stop Loss: 10 points ($200)
   - Timeout: Mean reversion levels expire after 1 minute

---

## Prerequisites

### Data Requirements

**Source Data File**: `data/historic/time_and_sales_nq_YYYYMMDD.csv`

Example: `data/historic/time_and_sales_nq_20251022.csv`

**Format**:
```csv
Timestamp;Precio;Volumen;Lado;Bid;Ask
2025-10-22 06:00:20.592;25327,5;1;ASK;25327,25;25327,5
```

**Important**:
- European CSV format (`;` separator, `,` decimal)
- Columns: Timestamp, Precio, Volumen, Lado, Bid, Ask
- Lado values: "BID" or "ASK"

### Python Dependencies

```bash
pip install pandas plotly webbrowser pathlib
```

### Configuration File

**`config_trinchera.py`** - Shared strategy parameters:

```python
BIG_VOLUME_TRIGGER = 200           # Minimum volume for detection
BIG_VOLUME_TIMEOUT = 10            # Minutes to wait for big volume effect
MEAN_REVERS_EXPAND = 10            # Points ± from close price
MEAN_REVERSE_TIMEOUT_ORDER = 1    # Minutes for mean reversion levels
```

---

## Complete Workflow

### Quick Start (Recommended)

**Run the entire pipeline in one command:**

```bash
cd strat_trinchera
python main_trinchera.py
```

This executes all 5 steps automatically:
1. Data processing (util_trinchera.py) - NOT executed by main
2. Big volume detection (find_big_volume.py)
3. Strategy backtest (strat_trinchera.py)
4. Trade visualization (plot_trinchera_trades.py)
5. Summary report (summary_trinchera.py)
6. Equity curve (plot_equity_trinchera.py)

**Note**: Step 1 (util_trinchera.py) must be run separately first if the data hasn't been processed yet.

---

## Step-by-Step Process

### STEP 0: Data Processing (Run Once)

**Script**: `util_trinchera.py`

**Purpose**: Convert raw tick data into 1-second OHLCV frames with Market Profile metrics

**Process**:
1. Loads tick data from `data/historic/time_and_sales_nq_YYYYMMDD.csv`
2. Aggregates ticks into 1-second frames
3. Calculates Market Profile for each frame:
   - Volume by price level (BID/ASK distribution)
   - Point of Control (POC)
   - Price range and levels
   - BID/ASK ratios

**Execution**:
```bash
python util_trinchera.py
```

**Output**:
- `outputs/db_trinchera_all_data_20251022.csv` (~172K frames for 2-day dataset)

**Runtime**: ~2-3 minutes for 448K ticks

**Note**: This only needs to be run once per data file, or when you get new data.

---

### STEP 1: Big Volume Detection

**Script**: `find_big_volume.py`

**Purpose**: Identify frames with volume exceeding the trigger threshold

**Detection Criteria**:
- `total_volume > BIG_VOLUME_TRIGGER` (default: 200 contracts)
- Minimum 10 price levels active
- Significant BID/ASK imbalance preferred

**Timeouts**:
- **Big Volume Timeout**: 10 minutes (orange line on chart)
- **Mean Reversion Timeout**: 1 minute (red/green lines on chart)

**Execution**:
```bash
python find_big_volume.py [VOLUME_TRIGGER]

# Examples:
python find_big_volume.py          # Uses default from config (200)
python find_big_volume.py 300      # Override to 300 contracts
```

**Output**:
- `outputs/db_trinchera_bins_20251022.csv` (big volume events with mean reversion levels)

**Sample Output**:
```
Total events detected: 1,234
Average volume: 312.45
BID dominant: 612 events (49.6%)
ASK dominant: 622 events (50.4%)
```

---

### STEP 2: Trading Strategy Backtest

**Script**: `strat_trinchera.py`

**Purpose**: Execute mean reversion trades based on big volume events

**Trading Rules**:

1. **SELL Entry** (when price touches red line):
   - Entry: `mean_level_up` (close + 10 points)
   - TP: Entry - 5 points
   - SL: Entry + 10 points

2. **BUY Entry** (when price touches green line):
   - Entry: `mean_level_down` (close - 10 points)
   - TP: Entry + 5 points
   - SL: Entry - 10 points

**Position Management**:
- One contract per trade
- No overlapping positions
- Immediate execution at touch

**Execution**:
```bash
python strat_trinchera.py
```

**Output**:
- `outputs/db_trinchera_TR_20251022.csv` (all executed trades)

**Sample Statistics**:
```
Total trades: 589
PROFIT exits: 257 (44.1%) → +$20,560
STOP exits: 326 (55.9%) → -$19,560
Total P&L: +$1,000 (50 points)

BUY trades: 295 → +$780
SELL trades: 294 → +$220
```

---

### STEP 3: Trade Visualization

**Script**: `plot_trinchera_trades.py`

**Purpose**: Interactive chart showing all trades with entry/exit markers

**Visual Elements**:
- **Blue line**: Close price
- **Orange line**: Total volume (right axis)
- **Orange dots**: Big volume events
- **Orange horizontal line**: Big volume timeout (10 min)
- **Red horizontal line**: Mean reversion upper level (SELL zone)
- **Green horizontal line**: Mean reversion lower level (BUY zone)

**Trade Markers**:
- 🔺 Green triangle up: BUY entry
- 🔻 Red triangle down: SELL entry
- □ Green square: PROFIT exit
- □ Red square: STOP exit
- Dotted grey lines: Entry → Exit connections

**Time Filter**:
```python
FILTER_FROM_14H = True     # Show only from 14:50:00 onwards
START_TIME = "14:50:00"
```

**Execution**:
```bash
python plot_trinchera_trades.py
```

**Output**:
- `charts/chart_trinchera_trades_20251022.html` (interactive Plotly chart)
- Opens automatically in browser

---

### STEP 4: Summary Report

**Script**: `summary_trinchera.py`

**Purpose**: Comprehensive HTML report with performance metrics

**Metrics Included**:

**General**:
- Total trades
- Exposure period
- Trades per day
- Average/median duration

**Performance**:
- Total profit (points & $)
- Profit factor
- Expectancy
- Standard deviation

**Win/Loss**:
- Win rate
- Gross profit/loss
- Average winner/loser
- Largest winner/loser

**Risk Metrics**:
- Max drawdown
- Ulcer Index
- Recovery Factor
- Sharpe Ratio
- Sortino Ratio
- Max win/loss streaks

**Exit Reasons**:
- TARGET exits (profit)
- STOP exits (loss)
- Percentage breakdown

**Signal Breakdown**:
- BUY vs SELL performance
- Profit by direction

**Execution**:
```bash
python summary_trinchera.py
```

**Output**:
- `charts/summary_trinchera_20251022.html` (styled HTML table)
- Opens automatically in browser

---

### STEP 5: Equity Curve

**Script**: `plot_equity_trinchera.py`

**Purpose**: Visualize cumulative equity, profit distribution, and drawdown

**Charts**:
1. **Equity Curve** (top panel, 50% height):
   - Cumulative P&L over time
   - Green/red fill based on final result
   - Hover: Trade # + Equity value

2. **Profit per Trade** (middle panel, 25% height):
   - Bar chart colored by profit/loss
   - Shows individual trade P&L

3. **Drawdown** (bottom panel, 25% height):
   - Running drawdown from peak
   - Red fill area showing risk exposure

**Execution**:
```bash
python plot_equity_trinchera.py
```

**Output**:
- `charts/equity_trinchera_20251022.html` (3-panel Plotly chart)
- Opens automatically in browser

---

## File Structure

```
strat_trinchera/
├── README.md                      # This file
├── config_trinchera.py           # Strategy configuration
├── main_trinchera.py             # Main pipeline orchestrator
│
├── util_trinchera.py             # STEP 0: Data processor (run once)
├── find_big_volume.py            # STEP 1: Volume detector
├── strat_trinchera.py            # STEP 2: Trading strategy
├── plot_trinchera_trades.py      # STEP 3: Trade visualization
├── summary_trinchera.py          # STEP 4: Summary report
└── plot_equity_trinchera.py      # STEP 5: Equity curve
│
├── outputs/                       # CSV data files (excluded from git)
│   ├── db_trinchera_all_data_20251022.csv    # Processed frames
│   ├── db_trinchera_bins_20251022.csv        # Big volume events
│   └── db_trinchera_TR_20251022.csv          # Executed trades
│
└── charts/                        # HTML visualizations (excluded from git)
    ├── chart_trinchera_trades_20251022.html  # Trade chart
    ├── summary_trinchera_20251022.html       # Summary report
    └── equity_trinchera_20251022.html        # Equity curve
```

---

## Configuration Parameters

### Strategy Parameters (`config_trinchera.py`)

```python
BIG_VOLUME_TRIGGER = 200           # Minimum volume to detect (contracts)
BIG_VOLUME_TIMEOUT = 10            # Big volume effect duration (minutes)
MEAN_REVERS_EXPAND = 10            # Mean reversion distance (points)
MEAN_REVERSE_TIMEOUT_ORDER = 1    # Mean reversion level duration (minutes)
```

### Trading Parameters (`config_trinchera.py`)

```python
# Basic TP/SL
TP_POINTS = 5.0        # Take profit in points ($100 per contract)
SL_POINTS = 10.0       # Stop loss in points ($200 per contract)
POINT_VALUE = 20.0     # Dollar value per point for NQ futures

# SMA Filter
FILTER_BY_SMA = True   # Trade direction based on price vs SMA-200
# - If close < SMA: Only SELL orders allowed
# - If close > SMA: Only BUY orders allowed

# Trailing Stop
SMA_TRAILING_STOP = True           # Enable dynamic trailing stop
TRAILING_STOP_ATR_MULT = 2.00      # Distance from extreme price (points)
# When enabled:
# - DISABLES fixed TP (let profits run)
# - LONG: SL follows highest_price - TRAILING_STOP_ATR_MULT (moves UP only)
# - SHORT: SL follows lowest_price + TRAILING_STOP_ATR_MULT (moves DOWN only)
# - Exit reason: 'trailing_stop' instead of 'stop'

# GRID System (Second Entry)
FILTER_USE_GRID = True             # Enable second entry on deeper move
GRID_MEAN_REVERS_EXPAND = 5.0      # Distance for second entry (points)
GRID_TP_POINTS = 4.0               # TP from average entry (IGNORED if trailing stop ON)
GRID_SL_POINTS = 3.0               # SL beyond second entry level

# GRID Logic:
# WITHOUT Trailing Stop:
#   - First entry at MEAN_REVERS_EXPAND (10 pts)
#   - Second entry at MEAN_REVERS_EXPAND + GRID_MEAN_REVERS_EXPAND (15 pts)
#   - If first entry hits TP before second entry → close at TP_POINTS profit
#   - If second entry fills → TP at GRID_TP_POINTS from average, SL at GRID_SL_POINTS beyond second entry
#
# WITH Trailing Stop (SMA_TRAILING_STOP = True):
#   - Fixed TP is DISABLED (both TP_POINTS and GRID_TP_POINTS are IGNORED)
#   - Only trailing stop manages exits (let profits run)
#   - Works for both single entry and double entry scenarios
```

### Optimization Tips

**Increase Win Rate** → Lower `MEAN_REVERS_EXPAND` (e.g., 8 points)
- Trades closer to mean → higher probability
- But fewer opportunities

**More Trades** → Lower `BIG_VOLUME_TRIGGER` (e.g., 150)
- Detects more events
- May reduce quality

**Better Risk/Reward** → Adjust TP/SL ratio
- Current: 1:2 (5 points TP, 10 points SL)
- Try: 1:1 (10 points TP, 10 points SL) for higher profit factor

---

## Output File Naming Convention

All output files use the **date from the source data file**, not today's date.

**Example**:
- Source: `time_and_sales_nq_20251022.csv`
- Outputs: `db_trinchera_all_data_20251022.csv`, `db_trinchera_bins_20251022.csv`, etc.

**Date Extraction**:
```python
import re
date_match = re.search(r'_(\d{8})\.csv', filename)
date_str = date_match.group(1)  # "20251022"
```

---

## Troubleshooting

### No big volume events detected

**Cause**: Threshold too high for the dataset

**Solution**: Lower `BIG_VOLUME_TRIGGER` in `config_trinchera.py`:
```python
BIG_VOLUME_TRIGGER = 150  # Lower from 200
```

Or override in command line:
```bash
python find_big_volume.py 150
```

---

### No trades executed

**Cause**: Price never touched mean reversion levels within timeout

**Solution**: Increase `MEAN_REVERS_EXPAND` for wider levels:
```python
MEAN_REVERS_EXPAND = 15  # Increase from 10
```

Or increase timeout:
```python
MEAN_REVERSE_TIMEOUT_ORDER = 2  # Increase from 1 minute
```

---

### FileNotFoundError: No db_trinchera_all_data file found

**Cause**: Step 0 (util_trinchera.py) not executed

**Solution**: Run data processing first:
```bash
python util_trinchera.py
```

Then run the pipeline:
```bash
python main_trinchera.py
```

---

### Chart not opening in browser

**Cause**: Browser not found or file association issue

**Solution**: Manually open HTML files from `charts/` folder

Windows:
```bash
explorer charts\chart_trinchera_trades_20251022.html
```

---

### Memory error during processing

**Cause**: Dataset too large (>1M ticks)

**Solution**: Use a subset of the data or increase system RAM

For testing, use a smaller time window in `util_trinchera.py`:
```python
df = df[df['Timestamp'].dt.hour >= 14]  # Only afternoon data
```

---

## Performance Benchmarks

### Data Processing (util_trinchera.py)
- **Input**: 448,332 ticks
- **Output**: 172,783 frames (1-second aggregation)
- **Duration**: ~2-3 minutes
- **Memory**: ~500MB peak

### Big Volume Detection (find_big_volume.py)
- **Input**: 172,783 frames
- **Output**: ~1,234 events (0.7% of frames)
- **Duration**: ~10 seconds
- **Memory**: ~50MB

### Strategy Backtest (strat_trinchera.py)
- **Input**: 1,234 events × 172K frames
- **Output**: 589 trades
- **Duration**: ~30 seconds
- **Memory**: ~100MB

### Complete Pipeline (main_trinchera.py)
- **Total Duration**: ~3-4 minutes (excluding Step 0)
- **Total Output**: 3 CSV files + 3 HTML charts
- **Browser Tabs**: 3 (trades, summary, equity)

---

## Strategy Characteristics

### Theoretical Basis

**Mean Reversion Hypothesis**: After a large volume spike, prices tend to exhibit temporary extremes before reverting to a mean level. The strategy exploits this by:
1. Identifying high-volume areas (institutional activity)
2. Waiting for price to reach extreme levels (overextension)
3. Trading the reversion back to equilibrium

### Typical Results (2-day sample)

```
Total Trades: 589
Win Rate: 44-46%
Profit Factor: 0.95-1.05
Average Trade: -$5 to +$5
Max Drawdown: -$600 to -$800
```

### Strengths
- ✓ Clear entry/exit rules
- ✓ Defined risk (fixed TP/SL)
- ✓ Exploits institutional volume patterns
- ✓ No indicators or lagging signals

### Weaknesses
- ✗ Low win rate (44-46%)
- ✗ Negative expectancy in some periods
- ✗ Requires frequent big volume events
- ✗ Sensitive to TP/SL ratio

---

## Future Enhancements

### Planned Features
- [ ] Dynamic TP/SL based on ATR or recent volatility
- [ ] Volume profile-weighted mean levels
- [ ] Multiple position sizing (scale in/out)
- [ ] Time-of-day filters (avoid low liquidity periods)
- [ ] Commission and slippage simulation
- [ ] Real-time alerting via webhook

### Parameter Optimization
- [ ] Grid search for TP/SL combinations
- [ ] Walk-forward analysis
- [ ] Monte Carlo simulation for robustness testing
- [ ] Out-of-sample validation

---

## Development Guidelines

### Adding New Features

1. **Modify config_trinchera.py** for new parameters
2. **Update main_trinchera.py** to include new scripts
3. **Keep file naming consistent** (use date from source data)
4. **Update this README** with new workflow steps

### Code Style

- European CSV format mandatory: `sep=';', decimal=','`
- Always use `outputs/` for CSV files
- Always use `charts/` for HTML visualizations
- Extract date from source filename, not `datetime.now()`
- Include progress messages (`[INFO]`, `[OK]`, `[ERROR]`)

---

## Citation

If you use this strategy in research or production, please cite:

```
Trinchera Mean Reversion Strategy
NQ Futures High-Volume Reversion System
Fabio Valentini, 2025
```

---

## License

Proprietary - Internal use only

---

## Support

For questions or issues:
1. Check Troubleshooting section above
2. Review CLAUDE.md in project root for overall architecture
3. Consult main project README for data format details

---

*Last updated: 2025-11-22*
*Version: 1.1 (GRID + Trailing Stop)*
