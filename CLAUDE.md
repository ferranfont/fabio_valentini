# CLAUDE.md - Fabio Valentini Project

## Project Overview
Advanced NQ (Nasdaq-100 E-mini) futures order flow analysis toolkit featuring:
- **Absorption Detection**: Statistical analysis of volume vs price movement
- **Real-Time Streaming**: Streamlit app with tick-by-tick replay
- **Footprint Charts**: Volume intensity gradients by price level
- **Time & Sales**: Tick-by-tick visualization
- **Interactive Plotly Charts**: Web-based interactive visualizations

## Data Sources

### Available Data Files
The project uses tick data and time series from the `data/` folder:

#### NQ Data (Primary)
- `time_and_sales_nq.csv` - Raw NQ tick data (448,332 records)
  - 2 days of data (Oct 9-10, 2025)
  - Columns: Timestamp, Precio, Volumen, Lado, Bid, Ask
- `time_and_sales_absorption.csv` - Processed with absorption detection (103,527 records after resampling)
  - Additional columns: bid_abs, ask_abs, bid_vol, ask_vol, vol_zscore, price_move_ticks

#### ES Data (Legacy)
- `time_and_sales.csv` - ES tick data with BID/ASK/Volume
- `es_1D_data.csv` - Daily ES data (207 KB)
- `es_1min_data_2015_2025.csv` - 1-minute ES data (358 MB)

### Data Format
Time & sales CSV format (European):
```
Timestamp;Precio;Volumen;Lado;Bid;Ask
2025-10-09 06:00:20.592;25327,5;1;ASK;25327,25;25327,5
```

**Important:** Semicolon separator, comma decimal (European format)

## Key Analysis Scripts

### 1. Absorption Detection (`stat_quant/find_absortion_vol_efford.py`)
**Purpose:** Detect volume absorption events in NQ tick data

**Algorithm:**
1. Resample to 5-second bins (reduces 448K → 103K records)
2. Rolling 5-minute window:
   - Aggregate volume by price level
   - Calculate mean and std deviation
3. Detect anomalies: Z-score >= 1.5 standard deviations
4. Verify absorption:
   - BID: Heavy selling but price doesn't drop >= 2 ticks
   - ASK: Heavy buying but price doesn't rise >= 2 ticks

**Configuration:**
```python
WINDOW_MINUTES = 5          # Rolling window size
ANOMALY_THRESHOLD = 1.5     # Z-score threshold
PRICE_MOVE_TICKS = 2        # Expected movement (0.5 points)
TICK_SIZE = 0.25            # NQ tick size
FUTURE_WINDOW_SEC = 60      # Time to measure price reaction
```

**Output:** `data/time_and_sales_absorption.csv` with columns:
- `bid_abs` / `ask_abs`: Absorption detected (True/False)
- `bid_vol` / `ask_vol`: Abnormal volume (True/False)
- `vol_zscore`: Statistical significance
- `price_move_ticks`: Actual price movement

**Execution:** `python stat_quant/find_absortion_vol_efford.py`

**Performance:** ~2-3 minutes for 448K records

**Results:**
- BID absorption: 1,263 events (1.22%)
- ASK absorption: 1,492 events (1.44%)

---

## Key Visualization Scripts

### 1. Real-Time Streaming (`plot_real_time_streamlit.py`)
**Purpose:** Simulate tick-by-tick replay with absorption visualization

**Features:**
- Play/Pause/Reset controls
- Speed: 1-500 records/second (configurable)
- Buffer size: 50-5000 records
- Dual charts: Price + Volume
- Absorption markers: Triangles with yellow borders
- Live statistics: Vol total, BID/ASK counts, absorption events
- Three tabs: Table / Statistics / Absorption Details

**How to run:**
```bash
streamlit run plot_real_time_streamlit.py
```

**IMPORTANT:** Must use `streamlit run`, NOT `python`. Opens at `localhost:8501`.

**Common Error:**
```
missing ScriptRunContext! This warning can be ignored when running in bare mode.
```
**Solution:** Use `streamlit run` instead of `python`

**Input:** `data/time_and_sales_absorption.csv` (auto-detected)

**Visualization:**
- Red points: BID trades
- Green points: ASK trades
- Large red triangles (down): BID absorption
- Large green triangles (up): ASK absorption
- Blue line: 20-period moving average

### 2. Static Absorption Chart (`plot_absortion_chart.py`)
**Purpose:** Generate HTML chart showing all absorption events

**Features:**
- Timeline view with all ticks
- Small points: Normal BID/ASK (opacity 0.3)
- Large points: Absorption events (size 15, alpha 0.5, dark borders)
- Hover tooltips: Timestamp, Price, Volume, Z-score, Price movement
- Statistics box in corner

**Execution:** `python plot_absortion_chart.py`

**Output:** `charts/absorption_chart.html` (auto-opens in browser)

### 3. Footprint Chart (`plot_footprint_chart.py`)
- Aggregates volume by price level
- Shows BID (red) and ASK (green) with intensity gradients
- Alpha transparency based on volume (0.45 to 0.85)
- Configurable via `n_temp` variable (number of rows to analyze)

### 4. Time & Sales Table (`plot_time_and_sales.py`)
- Table-style visualization of tick data
- Color-coded: ASK (green), BID (red)
- Displays: Time, Price, Volume, Side, Bid, Ask
- Configurable via `limit_rows` variable

### 5. Tick Data Charts (`plot_tick_data.py`)
- Resamples tick data to candlestick charts
- Volume bars with color intensity
- Multiple timeframe support

## Configuration (`config.py`)
Central configuration for:
- Chart dimensions: `CHART_WIDTH`, `CHART_HEIGHT`
- Data directories: `DATA_DIR = 'data/'`
- Symbol settings: `SYMBOL = 'ES'` (legacy, NQ used in absorption scripts)

## Workflow: Detecting and Visualizing Absorption

### Step 1: Generate Absorption Data (Run Once)
```bash
python stat_quant/find_absortion_vol_efford.py
```
- **Input:** `data/time_and_sales_nq.csv` (raw ticks)
- **Output:** `data/time_and_sales_absorption_NQ.csv` (with bid_abs, ask_abs columns)
- **Duration:** ~2-3 minutes
- **Run when:** New data available or parameter changes

### Step 2: Visualize (Run Multiple Times)
```bash
# Option A: Real-time streaming (interactive)
streamlit run plot_real_time_streamlit.py

# Option B: Static chart (quick overview)
python plot_absortion_chart.py
```

### Step 3: Backtest Trading Strategy (Optional)
```bash
# Run strategy backtest
python strat/strat_fabio_ATR.py

# View performance summary
python strat/summary.py

# Visualize trades on chart
python strat/plot_trades_chart.py
```

### Scripts are NOT Automatic
You must run them **sequentially**:
1. Detection script generates CSV with absorption signals
2. Visualization scripts read that CSV to display data
3. Strategy script reads absorption CSV to execute trades
4. Summary and plotting scripts read trade results

## Important Notes
- **Timestamps:** Madrid time (CET/CEST)
- **CSV Format:** European (`;` separator, `,` decimal)
- **Charts:** Saved to `charts/` directory and auto-open in browser
- **Console:** No emojis (Windows compatibility)
- **NQ Tick Size:** 0.25 points
- **Memory Usage:** ~500MB peak during absorption detection

## Development Guidelines
- Always use the local `data/` folder for data sources
- Maintain European CSV format (`sep=';', decimal=','`)
- Keep chart width minimal for footprint (400px)
- Use alpha gradients for volume intensity visualization
- For Streamlit apps: Always run with `streamlit run`, never `python`
- When modifying absorption parameters, re-run detection script

## Troubleshooting

### "missing ScriptRunContext" error
**Cause:** Running Streamlit with `python` instead of `streamlit run`
**Fix:** `streamlit run plot_real_time_streamlit.py`

### No absorptions detected
**Cause:** Threshold too high or data characteristics
**Fix:** In `find_absortion_vol_efford.py`, adjust:
- Lower `ANOMALY_THRESHOLD` (try 1.0 or 1.2)
- Increase `PRICE_MOVE_TICKS` (try 3)
- Change `WINDOW_MINUTES` (try 3 or 10)

### Streamlit app slow/laggy
**Cause:** Buffer too large or speed too fast
**Fix:** In sidebar, reduce buffer size or lower speed

### Charts not opening
**Cause:** Browser not found or default handler issue
**Fix:** Manually open `charts/absorption_chart.html`

## Code Architecture

### Absorption Detection Logic
```python
# Simplified pseudocode
for each_tick in window:
    vol_by_price = aggregate_volume_by_price(last_5_minutes)
    z_score = (current_vol - mean_vol) / std_vol

    if z_score >= 1.5:  # Abnormal volume
        future_prices = get_prices(next_60_seconds)

        if side == BID:
            price_drop = (current_price - min(future_prices)) / 0.25
            if price_drop < 2:  # Didn't fall enough
                bid_abs = True  # ABSORPTION

        elif side == ASK:
            price_rise = (max(future_prices) - current_price) / 0.25
            if price_rise < 2:  # Didn't rise enough
                ask_abs = True  # ABSORPTION
```

### Streamlit Real-Time Logic
```python
# Simplified pseudocode
while streaming and index < len(df):
    row = df.iloc[index]
    buffer.append(row)

    # Draw chart with buffer data
    plot_price_line(buffer)
    plot_bid_ask_points(buffer)

    # Highlight absorptions
    if row['bid_abs']:
        plot_large_triangle_down(red, alpha=0.5)
    if row['ask_abs']:
        plot_large_triangle_up(green, alpha=0.5)

    time.sleep(delay)
    index += 1
    st.rerun()  # Refresh UI
```

---

## Trading Strategy Module (`strat/` folder)

### Overview
The `strat/` folder contains scripts for backtesting absorption-based trading strategies and visualizing results.

### 1. Strategy Engine (`strat_fabio_ATR.py`)
**Purpose:** Execute backtests using absorption signals with ATR-based risk management

**Strategy Logic:**
- **LONG Entry:** `bid_abs = True` (heavy selling absorbed → bullish)
- **SHORT Entry:** `ask_abs = True` (heavy buying absorbed → bearish)
- **Take Profit:** Fixed 2.5 points (configurable via `TP_POINTS`)
- **Stop Loss:** Fixed 2.0 points (configurable via `SL_POINTS`)
- **EOD Management:** Close all positions at 16:00

**Configuration (Lines 22-41):**
```python
SYMBOL = 'NQ'
ATR_PERIOD = 14         # ATR calculation period (not used for TP/SL currently)
TP_POINTS = 2.5         # Fixed Take Profit in points
SL_POINTS = 2.0         # Fixed Stop Loss in points
TICK_SIZE = 0.25        # NQ tick size
POINT_VALUE = 20        # $20 per point
CONTRACTS = 1           # Position size
EOD_TIME = time(16, 00) # End-of-day close time
```

**Process:**
1. Loads `data/time_and_sales_absorption_NQ.csv`
2. Calculates ATR for reference (not currently used for TP/SL)
3. Iterates through each tick:
   - Opens LONG on `bid_abs = True`
   - Opens SHORT on `ask_abs = True`
   - Tracks TP/SL levels for open positions
   - Closes positions at TP, SL, or EOD
4. Saves all trades to `outputs/tracking_record.csv`

**Output CSV Columns:**
- `entry_time` / `exit_time`: Trade timestamps
- `side`: LONG / SHORT
- `entry_price` / `exit_price`: Execution prices
- `tp_level` / `sl_level`: Target levels
- `exit_reason`: TP / SL / EOD
- `points`: P&L in points
- `profit_usd`: P&L in dollars
- `cumulative_pnl`: Running total

**Execution:** `python strat/strat_fabio_ATR.py`

---

### 2. Performance Summary (`summary.py`)
**Purpose:** Display comprehensive backtest statistics

**Metrics Calculated:**
- Total trades, Win/Loss counts
- Win Rate (%)
- Total P&L (points and USD)
- Average Win / Average Loss
- Largest Win / Largest Loss
- Profit Factor (gross profit / gross loss)
- Sharpe Ratio (requires daily returns)
- Maximum Drawdown
- Average trade duration

**Execution:** `python strat/summary.py`

**Output:** Console table with all performance metrics

---

### 3. Trade Visualization (`plot_trades_chart.py`)
**Purpose:** Overlay trades on price chart with P&L visualization

**Features:**
- Price chart with BID/ASK points
- Entry markers: Green circles (LONG), Red circles (SHORT)
- Exit markers: Triangles (color-coded by P&L)
  - Green triangle up: Profitable exit
  - Red triangle down: Losing exit
- Annotations: P&L in USD for each trade
- Separate subplot: Cumulative P&L line chart
- Configurable range: `DEFAULT_START_INDEX`, `DEFAULT_END_INDEX`

**Configuration (Lines 18-20):**
```python
DEFAULT_START_INDEX = 0      # First trade to display
DEFAULT_END_INDEX = 500      # Last trade to display
```

**Execution:** `python strat/plot_trades_chart.py`

**Output:** `charts/trades_visualization.html` (auto-opens in browser)

**Usage Tips:**
- To view specific trade range, edit indices in script
- Large ranges (>1000 trades) may slow rendering
- Hover over markers to see details

---

### 4. Alternative Plotter (`plot_backtest_results.py`)
**Purpose:** Legacy/alternative visualization script

**Execution:** `python strat/plot_backtest_results.py`

---

## Trading Strategy Best Practices

### Parameter Tuning
To modify strategy behavior, edit `strat/strat_fabio_ATR.py`:

**More Conservative (fewer trades, higher quality):**
```python
# In stat_quant/find_absortion_vol_efford.py
ANOMALY_THRESHOLD = 2.0    # Increase from 1.5
PRICE_MOVE_TICKS = 3       # Increase from 2
```

**More Aggressive (more trades, lower threshold):**
```python
ANOMALY_THRESHOLD = 1.0    # Decrease from 1.5
PRICE_MOVE_TICKS = 1       # Decrease from 2
```

**Risk Management Adjustments:**
```python
# In strat/strat_fabio_ATR.py
TP_POINTS = 3.0            # Wider target
SL_POINTS = 1.5            # Tighter stop
# Result: Higher risk/reward ratio (2:1)
```

### Workflow for Strategy Development
1. **Detect absorptions** with different parameters
2. **Run backtest** with strategy script
3. **Analyze summary** for win rate, profit factor
4. **Visualize trades** to identify patterns
5. **Iterate:** Adjust parameters and repeat

### Important Notes
- **No Position Sizing:** Currently fixed at 1 contract
- **No Slippage:** Assumes perfect execution at signal price
- **EOD Risk:** Positions auto-close at 16:00 regardless of P&L
- **Single Instrument:** Designed for NQ futures only
- **Tick Precision:** Uses NQ tick size of 0.25 points
