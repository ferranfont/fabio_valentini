# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OrderFlowCharts is a real-time order flow visualization system for NQ (Nasdaq-100 E-mini) futures trading. It features a client-server architecture that streams tick-by-tick data and displays interactive footprint charts using Plotly. The system processes order flow data (bid/ask volumes at price levels) and OHLC (candlestick) data to create heatmap-based footprint charts showing market microstructure.

## Running the Code

### Dependencies Installation
```bash
pip install -r requirements.txt
```

Required packages: numpy>=1.26.0, pandas>=2.0.0, plotly>=5.9.0, flask>=2.3.0, dash>=2.14.0, requests>=2.31.0

### Primary Usage: Client-Server Architecture

**1. Start the Server:**
```bash
python server.py
```
- Server listens on port 8765
- Chart available at: http://localhost:8765/chart/
- Logs written to `logs/server_YYYYMMDD_HHMMSS.log`
- Updates chart every 500ms

**2. Stream Data with Client:**
```bash
# Default: 10x speed
python client.py ../data/time_and_sales_nq.csv

# Custom velocity (1x = real-time, 100x = very fast)
python client.py ../data/time_and_sales_nq.csv --velocity 50

# Reset server data before streaming
python client.py ../data/time_and_sales_nq.csv --reset

# Stream specific range
python client.py ../data/time_and_sales_nq.csv --start-from 10000 --max-ticks 5000
```

**3. View Real-Time Chart:**
- Open browser to http://localhost:8765/chart/
- Chart shows last 30 minutes initially (configurable)
- Pan/zoom to navigate through data
- Y-axis (price scale) remains fixed during streaming

### Legacy Usage: Standalone Mode
```bash
python main.py
```
This generates a static orderflow chart from sample data (no server/client needed).

## Code Architecture

### System Components

1. **Server (`server.py`)** - Real-time visualization server
   - Flask HTTP server for receiving tick data (POST /tick endpoint)
   - Dash web application for interactive charting
   - Thread-safe tick buffer with mutex locks
   - Automatic OHLC and orderflow aggregation
   - 500ms chart update interval
   - Logging to `logs/server_*.log`
   - Fixed y-axis range (set on first data arrival)
   - Configuration: PORT (8765), CANDLE_INTERVAL (1min), MAX_CANDLES (500), INITIAL_WINDOW_MINUTES (30)

2. **Client (`client.py`)** - Data streaming client
   - Reads CSV files with European format (`;` separator, `,` decimal)
   - Velocity-controlled playback (1x to 100x speed)
   - Time delta calculation and adjustment
   - HTTP POST communication with server
   - Progress monitoring and statistics
   - Properly exits when file completes

3. **OrderFlowChart Class (`OrderFlow/__init__.py`)** - Visualization engine
   - Single-class design containing all visualization logic (~469 lines)
   - Processes orderflow data (bid/ask volumes) and OHLC data
   - Creates 2-row subplot with footprint heatmap and parameters
   - Automatic tick size detection

### Two Data Input Methods

1. **Raw CSV Data** (via constructor):
   - Requires two CSV files: orderflow data and OHLC data
   - Orderflow data columns: `['bid_size', 'price', 'ask_size', 'identifier']`
   - OHLC data columns: `['open', 'high', 'low', 'close', 'identifier']`
   - Both should have datetime index
   - The `identifier` column links orderflow data to specific candles

2. **Preprocessed JSON Data** (via `from_preprocessed_data` classmethod):
   - Accepts a dictionary with 8 processed datasets: `orderflow`, `labels`, `green_hl`, `red_hl`, `green_oc`, `red_oc`, `orderflow2`, `ohlc`
   - Each dataset includes a `dtypes` dictionary for type preservation
   - See `data/preprocessed_data.json` for format example

### Key Processing Pipeline

The `process_data()` method (OrderFlow/__init__.py:160) orchestrates the entire data transformation:

1. **Identifier Creation**: If no identifier column provided, generates random strings to link orderflow data to candles
2. **Imbalance Calculation** (OrderFlow/__init__.py:60): Computes bid-ask imbalance using `(bid_size - ask_size.shift()) / (bid_size + ask_size.shift())`
3. **Candle Separation**: Splits OHLC data into green (bullish) and red (bearish) candles based on close vs open
4. **Range Processing** (OrderFlow/__init__.py:99): Transforms high-low and open-close ranges for plotting as line segments
5. **Parameter Calculation** (OrderFlow/__init__.py:126): Computes delta, cumulative delta, rate of change, and volume metrics

### Visualization Structure

The `plot()` method (OrderFlow/__init__.py:306) creates a 2-row subplot:
- **Row 1**: Main footprint chart with heatmap showing bid/ask imbalance, candlestick overlays, and volume profile
- **Row 2**: Heatmap showing delta, cumulative delta, ROC, and volume metrics

Uses Plotly's dark theme with custom pan mode, crosshair spikes, and drawing tools enabled.

### Data Granularity

The class automatically detects price granularity (tick size) from the first two rows of orderflow data: `abs(orderflow_data.iloc[0]['price'] - orderflow_data.iloc[1]['price'])` (OrderFlow/__init__.py:42)

## Sample Data

The `../data/` directory (parent folder) contains NQ futures tick data:

### Primary Data File
- **`time_and_sales_nq.csv`** - Raw NQ tick data (~448,332 records)
  - Date range: 2025-10-09 to 2025-10-10 (2 days)
  - Format: European CSV (`;` separator, `,` decimal)
  - Columns: `Timestamp`, `Precio`, `Volumen`, `Lado` (BID/ASK), `Bid`, `Ask`
  - Example: `2025-10-09 06:00:04.268;25327;1;BID;25327;25327,5`
  - Used with client-server architecture

### Data Format Details
- **Separator**: Semicolon (`;`)
- **Decimal**: Comma (`,`)
- **Timestamp**: ISO format with milliseconds (some timestamps may not have milliseconds)
- **Precio**: Trade price (float)
- **Volumen**: Trade volume in contracts (int)
- **Lado**: Side of trade (`BID` or `ASK`)
- **Bid/Ask**: Current market bid/ask prices
- **Tick Size**: 0.25 points (NQ futures)

### Legacy Sample Data
The `data/` directory in this folder contains legacy example files:
- `range_candles.csv` / `range_ohlc.csv`: Range-based bar data (ES)
- `time_candles.csv` / `time_ohlc.csv`: Time-based bar data (ES)
- `preprocessed_data.json`: Pre-processed data for `from_preprocessed_data()` method

## Key Features

### Real-Time Streaming
- **Velocity Control**: Adjustable playback speed (1x to 100x+)
- **In-Memory Processing**: All data transformations in memory, no intermediate files
- **Thread-Safe**: Mutex locks for concurrent tick buffer access
- **Auto-Aggregation**: Tick data → 1-minute candles → orderflow data

### Visualization Features
- **Fixed Y-Axis**: Price scale remains constant during streaming (set on first data)
- **30-Minute Window**: Shows last 30 minutes initially, full data available via pan/zoom
- **No Range Slider**: Clean interface without bottom slider
- **Dark Theme**: Optimized for trading environment
- **Interactive Controls**: Pan, zoom, drawing tools

### Data Handling
- **Mixed Timestamp Support**: Handles ISO8601 timestamps with/without milliseconds
  - Server uses `pd.to_datetime(format='ISO8601')` for flexible parsing
  - Client uses `.isoformat()` which may drop `.000` milliseconds
- **European CSV Format**: Semicolon separator, comma decimal
- **Automatic Exit**: Client properly exits when file completes

### Logging System
- **Timestamped Log Files**: `logs/server_YYYYMMDD_HHMMSS.log`
- **Dual Output**: Logs written to file and console
- **Comprehensive Logging**: Startup, errors, y-axis calculations, data resets
- **Error Tracebacks**: Full stack traces for debugging

## Key Implementation Details

- **No test suite**: This project has no automated tests
- **No build process**: Direct Python execution, no compilation needed
- **Stateful processing**: The `is_processed` flag tracks whether data has been transformed
- **Type coercion**: Preprocessed data serialization converts all types to strings with dtype metadata for reconstruction

## Common Issues and Solutions

### Timestamp Parsing Errors
**Issue**: `ValueError: time data "2025-10-09T06:17:37" doesn't match format "%Y-%m-%dT%H:%M:%S.%f"`
**Cause**: Mixed timestamp formats (some with milliseconds, some without)
**Solution**: Use `pd.to_datetime(format='ISO8601')` (already implemented in server.py:76)

### Y-Axis Auto-Scaling
**Issue**: Candles change size when new data arrives or during pan operations
**Cause**: Plotly recalculates y-axis range on each update
**Solution**: Fixed y-axis range stored on first data arrival, applied via `fig.update_layout(yaxis=dict(range=y_axis_range, fixedrange=True))` (server.py:211)

### Client Doesn't Stop
**Issue**: Client continues running after file completes
**Status**: Not an issue - client properly exits via natural loop termination with clear "Client exiting normally." message

## Server API Endpoints

### POST /tick
Receive a single tick from client
```json
{
  "Timestamp": "2025-10-09T06:00:04.268",
  "Precio": "25327.5",
  "Volumen": 1,
  "Lado": "ASK",
  "Bid": "25327",
  "Ask": "25327.5"
}
```
Response: `{"status": "ok", "ticks_received": 1523}`

### POST /reset
Reset all server data (tick buffer, OHLC, orderflow, y-axis range)
Response: `{"status": "ok", "message": "Data reset"}`

### GET /stats
Get current statistics
Response: `{"ticks_received": 1523, "candles": 31}`

### GET /
Server status page with endpoints list and live tick counter

### GET /chart/
Dash application with real-time orderflow chart

## Configuration

### Server Configuration (server.py lines 18-21)
```python
PORT = 8765                      # HTTP server port
CANDLE_INTERVAL = '1min'         # Candle aggregation period
MAX_CANDLES = 500                # Maximum candles to retain
INITIAL_WINDOW_MINUTES = 30      # Initial chart view window
```

### Client Configuration (client.py lines 13-14)
```python
SERVER_URL = 'http://localhost:8765'  # Server address
DEFAULT_VELOCITY = 10                  # Default playback speed (10x)
```

### Logging Configuration (server.py lines 25-38)
```python
LOG_DIR = 'logs'                       # Log directory
# Format: YYYY-MM-DD HH:MM:SS,mmm - LEVEL - Message
# Handlers: FileHandler + StreamHandler (console)
```

## File Structure
```
OrderFlowCharts/
├── server.py                    # Flask/Dash server
├── client.py                    # Data streaming client
├── main.py                      # Standalone plotter (legacy)
├── OrderFlow/
│   └── __init__.py             # OrderFlowChart class
├── logs/                        # Server log files (auto-created)
│   └── server_*.log
├── data/                        # Legacy sample data
│   ├── range_candles.csv
│   ├── range_ohlc.csv
│   ├── time_candles.csv
│   ├── time_ohlc.csv
│   └── preprocessed_data.json
├── requirements.txt             # Python dependencies
├── README.md                    # User documentation
├── SERVER_CLIENT_README.md      # Client-server usage
├── CLAUDE.md                    # This file
└── .gitignore                   # Ignores logs/

../data/
└── time_and_sales_nq.csv       # Primary NQ tick data (448K records)
```
