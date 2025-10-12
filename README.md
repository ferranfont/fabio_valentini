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

### Visualization
- **Real-Time Streaming**: Streamlit app simulating tick-by-tick data replay
- **Absorption Chart**: Interactive Plotly charts marking absorption events
- **Footprint Charts**: Volume profile with BID/ASK intensity gradients
- **Time & Sales**: Tick data table with price level visualization

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

### 4. Other Visualizations

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
│   ├── time_and_sales_nq.csv             # Raw NQ tick data
│   ├── time_and_sales_absorption.csv     # With absorption detection
│   ├── es_1min_data_2015_2025.csv        # ES 1-min bars
│   └── es_1D_data.csv                    # ES daily data
├── charts/                                # Output charts
│   └── absorption_chart.html
├── stat_quant/                            # Statistical analysis
│   └── find_absortion_vol_efford.py      # Absorption detector
├── utils/                                 # Utilities
│   ├── read_tick_data.py
│   └── clean_data_*.py
├── plot_absortion_chart.py               # Static absorption chart
├── plot_real_time_streamlit.py           # Real-time Streamlit app
├── plot_footprint_chart.py               # Volume footprint
├── plot_time_and_sales.py                # Time & sales table
├── plot_tick_data.py                     # Candlestick charts
├── config.py                             # Global config
├── CLAUDE.md                             # Development instructions
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
