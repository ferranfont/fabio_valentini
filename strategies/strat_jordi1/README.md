# Strategy Jordi1 - Cumulative Delta & Absorption Analysis

## Overview
This strategy analyzes NQ (Nasdaq-100 E-mini) futures order flow using cumulative delta and volume absorption metrics. It provides visual insights into buying/selling pressure and identifies periods where large volumes are absorbed without significant price movement.

## Features
- **Price Chart**: Visualizes NQ price movements over time
- **Cumulative Delta**: Tracks net buying/selling pressure (ASK volume - BID volume)
- **Absorption Analysis**: Identifies volume absorption by calculating volume divided by price variation squared

## Data Requirements
- **Input File**: `data/time_and_sales_nq.csv`
- **Format**: European CSV (semicolon separator, comma decimal)
- **Required Columns**:
  - `Timestamp`: Trade timestamp
  - `Precio`: Trade price
  - `Volumen`: Trade volume
  - `Lado`: Trade side (ASK or BID)
  - `Bid`: Bid price
  - `Ask`: Ask price

## Installation
Ensure all dependencies are installed:
```bash
pip install -r requirements.txt
```

Required packages:
- pandas >= 2.0.0
- plotly >= 5.0.0

## Usage
Run the script from the project root directory:
```bash
python strat_jordi1/plot_cumulative_delta.py
```

The script will:
1. Load tick data from `data/time_and_sales_nq.csv`
2. Resample to 10-second bins (configurable)
3. Calculate delta and absorption metrics
4. Generate an interactive HTML chart
5. Automatically open the chart in your browser

## Configuration
Edit the following variables in `plot_cumulative_delta.py`:

```python
TIMEFRAME_SECONDS = 10   # Aggregation period (default: 10 seconds)
CHART_HEIGHT = 1100      # Chart height in pixels
CHART_WIDTH = 1400       # Chart width in pixels
```

## Output
- **File**: `charts/cumulative_delta_chart.html`
- **Format**: Interactive Plotly chart with 3 subplots
- **Size**: Automatically opens in default browser

## Chart Components

### 1. Price Chart (Top - 40%)
- **Blue line**: NQ closing price per period
- **Purpose**: Shows price movements and trends
- **Hover**: Displays timestamp and price

### 2. Cumulative Delta (Middle - 30%)
- **Purple line**: Running sum of (ASK volume - BID volume)
- **Purple fill**: Area fill to zero line
- **Gray dashed line**: Zero reference
- **Purpose**: Identifies net buying/selling pressure over time

**Interpretation**:
- **Rising**: Net buying pressure (more ASK volume)
- **Falling**: Net selling pressure (more BID volume)
- **Above zero**: Cumulative buying dominance
- **Below zero**: Cumulative selling dominance

### 3. Absorption Analysis (Bottom - 30%)
- **Red line**: BID Absorption = BID Volume / (Price Range)²
- **Green line**: ASK Absorption = ASK Volume / (Price Range)²
- **Purpose**: Identifies periods where large volumes don't move price

**Interpretation**:
- **High BID Absorption (Red spikes)**: Heavy selling absorbed by buyers (support)
- **High ASK Absorption (Green spikes)**: Heavy buying absorbed by sellers (resistance)
- **Low values**: Normal price discovery
- **High values**: Potential turning points or strong levels

## Methodology

### Delta Calculation
For each trade:
- ASK trade: `delta = +volume` (buying pressure)
- BID trade: `delta = -volume` (selling pressure)

Per period (10 seconds):
```
period_delta = sum(ASK volumes) - sum(BID volumes)
cumulative_delta = cumulative_sum(period_delta)
```

### Absorption Calculation
Per period (10 seconds):
```
price_range = high_price - low_price
bid_absorption = bid_volume / (price_range + epsilon)²
ask_absorption = ask_volume / (price_range + epsilon)²
```

Where `epsilon = 0.01` prevents division by zero.

**Logic**:
- Large volume + small price movement = high absorption
- Small volume + large price movement = low absorption

## Example Output Statistics
```
Loaded 448,332 records
Date range: 2025-10-09 06:00:04 to 2025-10-10 05:59:55
Resampled to 7,885 10-second bars

Delta Statistics:
  Total Delta: 75,704
  Max Delta (10s): 846
  Min Delta (10s): -379
  Final Cumulative Delta: 75,704

Absorption Statistics:
  Max BID Absorption: 80,000.00
  Max ASK Absorption: 80,000.00
  Avg BID Absorption: 548.46
  Avg ASK Absorption: 742.84
```

## Trading Insights

### Cumulative Delta Divergences
- **Price up + Cumulative Delta down**: Weak rally, potential reversal
- **Price down + Cumulative Delta up**: Weak selloff, potential bounce
- **Price & Delta aligned**: Strong trend confirmation

### Absorption Signals
- **High BID Absorption at support**: Strong buyers defending level
- **High ASK Absorption at resistance**: Strong sellers capping rally
- **Absorption spikes before reversals**: Exhaustion signal
- **Low absorption in trends**: Healthy price discovery

## Performance Notes
- **Processing Time**: ~2-3 seconds for 448K records
- **Memory Usage**: ~50-100 MB peak
- **Chart File Size**: ~5-10 MB (HTML with embedded data)

## Customization Ideas
1. Add volume bars to price chart
2. Highlight absorption spikes with markers
3. Add moving averages to cumulative delta
4. Create alerts for extreme absorption values
5. Export signals to CSV for backtesting

## Troubleshooting

### Chart not opening
- Manually open `charts/cumulative_delta_chart.html` in browser
- Check that `charts/` directory exists

### Import errors
- Verify all dependencies installed: `pip list | grep -E "pandas|plotly"`
- Re-install requirements: `pip install -r requirements.txt`

### Data loading errors
- Confirm `data/time_and_sales_nq.csv` exists
- Check CSV format (semicolon separator, comma decimal)
- Verify columns: Timestamp, Precio, Volumen, Lado, Bid, Ask

### Memory issues
- Reduce dataset size for testing
- Increase `TIMEFRAME_SECONDS` to reduce resampled bars

## File Structure
```
strat_jordi1/
├── README.md                    # This file
└── plot_cumulative_delta.py     # Main analysis script

Project root:
├── data/
│   └── time_and_sales_nq.csv   # Input tick data
└── charts/
    └── cumulative_delta_chart.html  # Generated output
```

## Future Enhancements
- [ ] Add real-time streaming support
- [ ] Implement automated signal detection
- [ ] Create backtesting framework
- [ ] Add multiple timeframe analysis
- [ ] Export signals to trading platform
- [ ] Add statistical significance tests
- [ ] Create dashboard with multiple instruments

## References
- **Order Flow Trading**: Study of volume at different price levels
- **Cumulative Delta**: Net buying/selling pressure indicator
- **Volume Absorption**: Concept from auction market theory
- **Market Profile**: Framework for understanding market structure

## License
Part of the Fabio Valentini trading analysis toolkit.

## Author
Strategy developed for NQ futures order flow analysis.

---

**Note**: This is an analytical tool for research purposes. Always perform your own analysis and risk management before trading.
