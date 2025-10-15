# OrderFlowCharts

Advanced order flow analysis and visualization system for NQ (Nasdaq-100 E-mini) futures trading. Features real-time footprint charts with tick-by-tick data streaming and playback control.

## Overview

OrderFlowCharts is a professional-grade order flow analysis toolkit that provides:

- **Footprint Charts**: Volume-at-price visualization with bid/ask imbalance heatmaps
- **Real-Time Streaming**: Server-client architecture for live tick data visualization
- **Playback Control**: Variable speed replay (1x to 100x) for historical analysis
- **Interactive Analysis**: Pan, zoom, draw on charts with Plotly controls
- **Time Window Management**: Configurable time windows with range slider navigation

## Features

### Order Flow Analysis
- Bid/Ask volume aggregation by price level
- Volume imbalance calculation and visualization
- Delta and cumulative delta tracking
- Rate of change (ROC) metrics
- 1-minute candle aggregation (configurable)

### Visualization
- Interactive footprint heatmaps
- Candlestick overlays (bullish/bearish)
- Volume profile visualization
- Customizable color schemes and opacity
- Dark theme optimized for trading

### Data Management
- In-memory processing (no intermediate files)
- Thread-safe tick buffering
- Automatic candle aggregation
- Configurable data limits (500 candles default)
- 30-minute initial view window

## Architecture

### Client-Server Design

```
┌─────────────┐         HTTP POST          ┌─────────────┐
│             │      /tick endpoint         │             │
│   Client    ├───────────────────────────>│   Server    │
│  (Python)   │   Tick data (JSON)          │ (Flask/Dash)│
│             │                             │             │
└─────────────┘                             └──────┬──────┘
                                                   │
      CSV File                                     │ In-memory
      ┌──────────┐                                 │ Processing
      │ Time &   │                                 │
      │ Sales    │                                 ▼
      │ Tick Data│                          ┌─────────────┐
      └──────────┘                          │  OrderFlow  │
                                            │   Chart     │
                                            │ (Plotly)    │
                                            └──────┬──────┘
                                                   │
                                                   │ Updates
                                                   ▼ every 500ms
                                            ┌─────────────┐
                                            │   Browser   │
                                            │ localhost:  │
                                            │   8765      │
                                            └─────────────┘
```

### Components

1. **Server (`server.py`)**
   - Flask HTTP server for receiving tick data
   - Dash web application for real-time visualization
   - Thread-safe data buffer with mutex locks
   - Automatic OHLC and orderflow aggregation
   - 500ms chart update interval

2. **Client (`client.py`)**
   - CSV file reader with European format support
   - Velocity-controlled streaming engine
   - Time delta calculation and adjustment
   - HTTP POST communication with server
   - Progress monitoring and statistics

3. **OrderFlow Engine (`OrderFlow/__init__.py`)**
   - Volume-by-price aggregation
   - Bid/Ask imbalance calculation
   - Heatmap generation with color gradients
   - Candlestick overlay rendering
   - Plotly figure composition

## Installation

### Prerequisites
- Python 3.8+
- pip package manager

### Install Dependencies

```bash
cd /home/idroji/trading/workspace/fabio_valentini/OrderFlowCharts
pip install -r requirements.txt
```

### Required Packages
- `numpy>=1.26.0` - Numerical computing
- `pandas>=2.0.0` - Data manipulation
- `plotly>=5.9.0` - Interactive charts
- `flask>=2.3.0` - HTTP server
- `dash>=2.14.0` - Real-time web apps
- `requests>=2.31.0` - HTTP client

## Quick Start

### 1. Start the Server

Open a terminal:

```bash
cd /home/idroji/trading/workspace/fabio_valentini/OrderFlowCharts
python server.py
```

**Expected Output:**
```
OrderFlow Server starting on port 8765...
Chart will be available at: http://localhost:8765/chart/
Send ticks to: http://localhost:8765/tick
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:8765
```

**Open Browser:**
Navigate to http://localhost:8765/chart/ to see the live chart

### 2. Stream Data with Client

Open a **second** terminal:

```bash
cd /home/idroji/trading/workspace/fabio_valentini/OrderFlowCharts
python client.py ../data/time_and_sales_nq.csv
```

**Expected Output:**
```
====================================================
OrderFlow Client
====================================================
Loading tick data from ../data/time_and_sales_nq.csv...
Loaded 448,332 ticks
Date range: 2025-10-09 06:00:04.268000 to 2025-10-10 05:59:55.424000
Velocity: 10x
Starting from row: 0

Connecting to server at http://localhost:8765...
Connected to server successfully!

Starting data stream...
Press Ctrl+C to stop

Sent 100 ticks | Rate: 158.3 ticks/sec | Time: 2025-10-09 06:00:14 | Price: 25327.5
Sent 200 ticks | Rate: 163.1 ticks/sec | Time: 2025-10-09 06:00:27 | Price: 25328.25
...
```

### 3. View Real-Time Chart

The browser at http://localhost:8765/chart/ will now display:
- Real-time footprint chart updating every 500ms
- Statistics: Total ticks, candles, orderflow records
- Interactive controls: pan, zoom, draw
- Range slider for time navigation

## Usage

### Basic Commands

```bash
# Default: 10x speed, full file
python client.py ../data/time_and_sales_nq.csv

# Faster: 50x speed
python client.py ../data/time_and_sales_nq.csv --velocity 50

# Real-time: 1x speed
python client.py ../data/time_and_sales_nq.csv --velocity 1

# Ultra-fast loading: 100x speed
python client.py ../data/time_and_sales_nq.csv --velocity 100
```

### Advanced Options

```bash
# Reset server data before streaming
python client.py ../data/time_and_sales_nq.csv --reset

# Stream only 5000 ticks
python client.py ../data/time_and_sales_nq.csv --max-ticks 5000

# Start from row 10000 (skip first 10k ticks)
python client.py ../data/time_and_sales_nq.csv --start-from 10000

# Combine options
python client.py ../data/time_and_sales_nq.csv --velocity 20 --reset --max-ticks 10000
```

### Client Arguments

| Argument | Short | Default | Description |
|----------|-------|---------|-------------|
| `csv_file` | - | (required) | Path to CSV file with tick data |
| `--velocity` | `-v` | 10 | Playback speed multiplier (1-100+) |
| `--start-from` | `-s` | 0 | Skip first N rows of CSV |
| `--max-ticks` | `-m` | None | Maximum ticks to send (all if not specified) |
| `--reset` | `-r` | False | Reset server data before streaming |
| `--server` | - | http://localhost:8765 | Server URL |

## Data Format

### Input CSV Format (European)

```csv
Timestamp;Precio;Volumen;Lado;Bid;Ask
2025-10-09 06:00:04.268;25327;1;BID;25327;25327,5
2025-10-09 06:00:04.268;25327,5;2;ASK;25327;25327,5
```

- **Separator**: Semicolon (`;`)
- **Decimal**: Comma (`,`)
- **Timestamp**: ISO format with milliseconds
- **Precio**: Trade price
- **Volumen**: Trade volume (contracts)
- **Lado**: Side (`BID` or `ASK`)
- **Bid/Ask**: Current market bid/ask prices

## Configuration

### Server Configuration (`server.py`)

```python
PORT = 8765                      # HTTP server port
CANDLE_INTERVAL = '1min'         # Candle aggregation period
MAX_CANDLES = 500                # Maximum candles to retain
INITIAL_WINDOW_MINUTES = 30      # Initial chart view window
```

### Client Configuration (`client.py`)

```python
SERVER_URL = 'http://localhost:8765'  # Server address
DEFAULT_VELOCITY = 10                  # Default playback speed
```

## Chart Controls

### Mouse Controls
- **Pan**: Click and drag on chart
- **Zoom**: Scroll wheel or box select
- **Reset**: Double-click or home button

### Toolbar
- **Drawing Tools**: Line, rectangle, circle, free draw
- **Pan/Zoom**: Toggle pan or zoom mode
- **Download**: Save chart as PNG
- **Autoscale**: Reset axes to fit data

### Range Slider
- Bottom slider shows full time range
- Drag handles to adjust visible window
- Click bar to jump to time period

## API Endpoints

### Server Endpoints

#### POST `/tick`
Send a single tick to the server

**Request Body (JSON):**
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

**Response:**
```json
{
  "status": "ok",
  "ticks_received": 1523
}
```

#### POST `/reset`
Reset all server data

**Response:**
```json
{
  "status": "ok",
  "message": "Data reset"
}
```

#### GET `/stats`
Get current statistics

**Response:**
```json
{
  "ticks_received": 1523,
  "candles": 31
}
```

## Performance

### Typical Performance
- **Streaming Rate**: 150-200 ticks/sec at 10x velocity
- **Chart Update**: Every 500ms (2 Hz)
- **Memory Usage**: ~500MB for 500 candles
- **Browser Load**: Minimal, GPU-accelerated rendering

### Optimization Tips
1. **Higher Velocity**: Use `--velocity 100` for fast loading
2. **Limit Candles**: Reduce `MAX_CANDLES` in server.py
3. **Smaller Window**: Adjust `INITIAL_WINDOW_MINUTES`
4. **Batch Processing**: Use `--max-ticks` for testing

## Troubleshooting

### Client Can't Connect

**Error:**
```
ERROR: Cannot connect to server
```

**Solution:**
1. Ensure server is running: `python server.py`
2. Check port 8765 is not in use: `lsof -i :8765`
3. Verify firewall settings

### Chart Not Updating

**Symptoms:** Chart shows "Waiting for data..."

**Solutions:**
1. Check client is streaming (watch terminal output)
2. Verify server terminal shows no errors
3. Refresh browser page
4. Reset server: `python client.py --reset`

### Slow Performance

**Symptoms:** Lag, slow chart updates

**Solutions:**
1. Reduce velocity: Lower `--velocity` value
2. Limit data: Use `--max-ticks`
3. Close other browser tabs
4. Restart server to clear memory

### CSV Reading Errors

**Error:**
```
ValueError: could not convert string to float
```

**Solution:**
- Verify CSV uses semicolon separator and comma decimals
- Check for malformed rows
- Ensure European number format (25327,5 not 25327.5)

## Examples

### Quick Test (30 minutes of data)

```bash
# Terminal 1: Start server
python server.py

# Terminal 2: Stream 30-min file at 20x speed
python client.py ../data/time_and_sales_nq_30min.csv --velocity 20 --reset
```

### Full Day Analysis (High Speed)

```bash
# Terminal 1: Start server
python server.py

# Terminal 2: Stream full file at 100x speed
python client.py ../data/time_and_sales_nq.csv --velocity 100 --reset
```

### Replay Specific Period

```bash
# Stream starting from row 100,000 for 10,000 ticks
python client.py ../data/time_and_sales_nq.csv --start-from 100000 --max-ticks 10000 --velocity 50
```

### Real-Time Simulation

```bash
# Stream at actual market speed (1x)
python client.py ../data/time_and_sales_nq.csv --velocity 1
```

## Project Structure

```
OrderFlowCharts/
├── README.md                    # This file
├── SERVER_CLIENT_README.md      # Detailed client-server docs
├── requirements.txt             # Python dependencies
├── server.py                    # OrderFlow server
├── client.py                    # Data streaming client
├── main.py                      # Standalone plotter (legacy)
├── OrderFlow/
│   └── __init__.py             # OrderFlowChart class
├── __pycache__/                # Python bytecode
└── LICENSE                      # License information
```

## Development

### Standalone Mode (No Server)

For static analysis without streaming:

```bash
python main.py
```

This loads data from CSV, processes in memory, and opens chart in browser (no server/client needed).

### Extending the System

**Add Custom Indicators:**
Edit `OrderFlow/__init__.py` to add calculations and visualizations

**Change Candle Intervals:**
Modify `CANDLE_INTERVAL` in `server.py` (e.g., `'5min'`, `'15min'`)

**Custom Data Sources:**
Implement your own client that POSTs to `/tick` endpoint

**Multiple Instruments:**
Run multiple server instances on different ports

## License

See LICENSE file for details.

## Support

For issues, questions, or contributions:
- Check troubleshooting section above
- Review SERVER_CLIENT_README.md for detailed documentation
- Examine example commands and configurations

## Technical Notes

- **Time Zone**: All timestamps in Madrid time (CET/CEST)
- **Tick Size**: NQ = 0.25 points
- **Point Value**: $20 per point
- **Threading**: Server uses thread-safe locks for data access
- **Memory**: Data clears on server restart
- **Browser**: Chrome/Firefox recommended for best performance

---

**Version**: 1.0
**Last Updated**: 2025-10-15
**Target Instrument**: NQ Futures (Nasdaq-100 E-mini)
