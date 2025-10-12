# Fabio Valentini - NQ Futures Analysis

Advanced trading analysis toolkit for NQ (Nasdaq-100 E-mini) futures featuring order flow analysis, absorption detection, and real-time visualization.

## Installation

```bash
pip install -r requirements.txt
```

## Data Source

The project uses tick-by-tick futures data from the local `data/` folder:
- `time_and_sales_nq.csv` - Raw NQ tick data (448K records, BID/ASK/Volume)
- `time_and_sales_absorption_NQ.csv` - NQ processed data with absorption detection
- `time_and_sales_absorption_ES.csv` - ES processed data (if available)
- `es_1min_data_2015_2025.csv` - ES 1-minute data (2015-2025)
- `es_1D_data.csv` - ES daily data

## Features

### Core Analysis
- **Absorption Detection**: Identifies volume imbalances where price doesn't move as expected
- **Order Flow Analysis**: BID/ASK volume tracking with statistical anomaly detection
- **Rolling Window Statistics**: 5-minute windows for volume aggregation by price level
- **Z-Score Calculation**: Identifies abnormal volume (threshold: 1.5 std deviations)

### Trading Strategy (NEW)
- **ATR-Based Strategy**: Automated trading based on absorption signals
- **Backtesting Engine**: Test strategies on historical tick data
- **Risk Management**: Fixed TP/SL levels with ATR calculation support
- **Trade Visualization**: Plot entries, exits, and P&L on price charts
- **Performance Summary**: Win rate, profit factor, Sharpe ratio, and detailed metrics

### Visualization
- **Real-Time Streaming**: Streamlit app simulating tick-by-tick data replay
- **Absorption Chart**: Interactive Plotly charts marking absorption events
- **Footprint Charts**: Volume profile with BID/ASK intensity gradients
- **Time & Sales**: Tick data table with price level visualization
- **Trade Overlay**: Visualize trade entries/exits with P&L markers

## Usage

### 1. Detect Absorption (Run Once)

Analyzes raw tick data and generates absorption events:

```bash
python stat_quant/find_absortion_vol_efford.py
```

**Configuration:** Edit `SYMBOL = 'NQ'` in the script to change between NQ/ES.

**Output:** `data/time_and_sales_absorption_{SYMBOL}.csv` with columns:
- `bid_abs` / `ask_abs`: Absorption detected (True/False)
- `bid_vol` / `ask_vol`: Abnormal volume (True/False)
- `vol_zscore`: Statistical z-score
- `price_move_ticks`: Actual price movement

**Results:**
- Processes 448K → 103K records (5-second resampling)
- BID absorption: ~1,263 events (1.22%)
- ASK absorption: ~1,492 events (1.44%)

### 2. Visualize in Real-Time (Interactive)

Launches Streamlit app for tick-by-tick replay:

```bash
streamlit run plot_real_time_streamlit.py
```

**Important:** Must use `streamlit run`, NOT `python`. Opens browser at `localhost:8501`.

**Features:**
- Play/Pause/Reset controls
- Speed: 1-500 records/second
- Buffer size: 50-5000 records
- Absorption markers (triangles with yellow borders)
- Live statistics and absorption details

### 3. Static Absorption Chart

Generates HTML chart with all absorption events:

```bash
python plot_absortion_chart.py
```

**Output:** `charts/absorption_chart.html` (auto-opens in browser)

### 4. Run Trading Strategy (Backtest)

Execute the absorption-based trading strategy with ATR risk management:

```bash
python strat/strat_fabio_ATR.py
```

**Strategy Logic:**
- **LONG Entry**: When `bid_abs = True` (absorption on BID side)
- **SHORT Entry**: When `ask_abs = True` (absorption on ASK side)
- **Take Profit**: 2.5 points (configurable)
- **Stop Loss**: 2.0 points (configurable)
- **EOD Close**: Automatic position close at 16:00

**Output:** `outputs/tracking_record.csv` with all trade details

### 5. Visualize Backtest Results

After running the strategy, visualize trades on the price chart:

```bash
# View performance summary
python strat/summary.py

# Plot trades on chart (first 500 trades by default)
python strat/plot_trades_chart.py
```

**Features:**
- Entry/Exit markers on price chart
- P&L annotations for each trade
- Separate subplot showing cumulative P&L
- Configurable trade range (edit `start_idx`, `end_idx` in script)

**Output:** `charts/trades_visualization.html`

### 6. Other Visualizations

```bash
# Footprint chart with volume intensity
python plot_footprint_chart.py

# Time & Sales table display
python plot_time_and_sales.py

# Tick data candlestick charts
python plot_tick_data.py
```

## Absorption Detection Methodology

### Concept
**Absorption** = Large volume that fails to move price proportionally.

- **BID Absorption**: Heavy selling (abnormal BID volume) but price doesn't fall → Buyers absorbing supply
- **ASK Absorption**: Heavy buying (abnormal ASK volume) but price doesn't rise → Sellers absorbing demand

### Algorithm

1. **Resample to 5-second bins** (reduces data 80% for speed)
2. **Rolling window of 5 minutes**:
   - Group volume by price level
   - Calculate mean and std deviation
3. **Detect anomalies**: `z_score = (vol_at_price - mean) / std`
   - If `z_score >= 1.5`: Abnormal volume
4. **Check price response** (next 60 seconds):
   - BID: If price drop < 2 ticks (0.50 pts) → Absorption
   - ASK: If price rise < 2 ticks (0.50 pts) → Absorption

### Parameters (configurable in code)

```python
WINDOW_MINUTES = 5          # Rolling window
ANOMALY_THRESHOLD = 1.5     # Z-score threshold
PRICE_MOVE_TICKS = 2        # Expected movement (NQ tick = 0.25)
TICK_SIZE = 0.25            # NQ tick size
FUTURE_WINDOW_SEC = 60      # Time to measure price reaction
```

## Project Structure

```
fabio_valentini/
├── data/                                  # Data files
│   ├── time_and_sales_nq.csv             # Raw NQ tick data (448K records)
│   ├── time_and_sales_absorption_NQ.csv  # NQ with absorption detection
│   ├── time_and_sales_absorption_ES.csv  # ES with absorption detection
│   ├── es_1min_data_2015_2025.csv        # ES 1-min bars (2015-2025)
│   ├── es_1D_data.csv                    # ES daily data
│   └── DATA_DOCUMENTATION.md             # Data files reference
├── charts/                                # Output charts
│   ├── absorption_chart.html             # Static absorption view
│   └── trades_visualization.html         # Backtest results chart
├── outputs/                               # Trading results (NEW)
│   └── tracking_record.csv               # Trade log from backtest
├── stat_quant/                            # Statistical analysis
│   ├── find_absortion_vol_efford.py      # Absorption detector
│   └── plot_absorption_chart.py          # Legacy chart script
├── strat/                                 # Trading strategies (NEW)
│   ├── strat_fabio_ATR.py                # Main strategy backtest engine
│   ├── plot_trades_chart.py              # Visualize trades on chart
│   ├── summary.py                        # Performance metrics summary
│   └── plot_backtest_results.py          # Alternative results plotter
├── utils/                                 # Utilities
│   ├── read_tick_data.py                 # Tick data loader
│   ├── clean_data_*.py                   # Data processing scripts
│   └── CLEAN_DATA.md                     # Utils documentation
├── plot_absortion_chart.py               # Static absorption chart
├── plot_real_time_streamlit.py           # Real-time Streamlit app
├── plot_footprint_chart.py               # Volume footprint
├── plot_time_and_sales.py                # Time & sales table
├── plot_tick_data.py                     # Candlestick charts
├── config.py                             # Global config
├── CLAUDE.md                             # AI assistant instructions
└── README.md                             # This file
```

## Troubleshooting

### Streamlit Warning: "missing ScriptRunContext"

**Problem:** Running with `python plot_real_time_streamlit.py`

**Solution:** Always use:
```bash
streamlit run plot_real_time_streamlit.py
```

### No absorptions detected

Adjust parameters in `stat_quant/find_absortion_vol_efford.py`:
- Lower `ANOMALY_THRESHOLD` (try 1.0)
- Increase `PRICE_MOVE_TICKS` (try 3)
- Adjust `WINDOW_MINUTES` (try 3 or 10)

## Technical Notes

- **CSV Format**: European (`;` separator, `,` decimal)
- **Timezone**: Madrid time (CET/CEST)
- **Performance**: ~2-3 min for 448K records
- **Memory**: ~500MB peak usage

## License

Private project - Fabio Valentini
