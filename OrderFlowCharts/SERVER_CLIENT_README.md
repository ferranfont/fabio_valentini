# OrderFlow Server-Client System

Real-time OrderFlow visualization with tick-by-tick data streaming.

## Overview

This system consists of:
- **Server**: Listens for tick data and displays real-time OrderFlow charts
- **Client**: Reads CSV files and streams ticks to the server with velocity control

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Start the Server

Open a terminal and run:

```bash
cd /home/idroji/trading/workspace/fabio_valentini/OrderFlowCharts
python server.py
```

The server will start on port 8765. You'll see:
- Server status at: http://localhost:8765/
- Live chart at: http://localhost:8765/chart/

### 3. Start the Client

Open another terminal and stream data:

```bash
cd /home/idroji/trading/workspace/fabio_valentini/OrderFlowCharts
python client.py ../data/time_and_sales_nq.csv
```

## Client Options

### Basic Usage

```bash
# Stream with default 10x speed
python client.py ../data/time_and_sales_nq.csv

# Stream with custom speed (20x faster)
python client.py ../data/time_and_sales_nq.csv --velocity 20

# Stream at real-time speed (1x)
python client.py ../data/time_and_sales_nq.csv --velocity 1

# Stream at half speed (0.5x)
python client.py ../data/time_and_sales_nq.csv --velocity 0.5
```

### Advanced Options

```bash
# Start from row 1000 (skip first 1000 ticks)
python client.py ../data/time_and_sales_nq.csv --start-from 1000

# Send only 5000 ticks
python client.py ../data/time_and_sales_nq.csv --max-ticks 5000

# Reset server data before starting
python client.py ../data/time_and_sales_nq.csv --reset

# Combine options
python client.py ../data/time_and_sales_nq.csv --velocity 50 --reset --max-ticks 10000
```

### Command-Line Arguments

| Argument | Short | Default | Description |
|----------|-------|---------|-------------|
| `csv_file` | - | (required) | Path to CSV file with tick data |
| `--velocity` | `-v` | 10 | Playback speed multiplier |
| `--start-from` | `-s` | 0 | Skip first N rows |
| `--max-ticks` | `-m` | None | Maximum ticks to send |
| `--reset` | `-r` | False | Reset server before starting |
| `--server` | - | http://localhost:8765 | Server URL |

## How It Works

### Velocity Control

The `--velocity` parameter controls how fast data is streamed:

- **velocity=10** (default): 10 times faster than real-time
  - If ticks are 1 second apart in CSV, they're sent 0.1 seconds apart

- **velocity=1**: Real-time speed
  - If ticks are 1 second apart in CSV, they're sent 1 second apart

- **velocity=100**: 100 times faster
  - Useful for quickly loading large datasets

### Data Flow

1. Client reads CSV file
2. Client calculates time differences between ticks
3. Client applies velocity multiplier to delays
4. Client sends ticks to server via HTTP POST
5. Server accumulates ticks in memory
6. Server aggregates ticks into 1-minute candles
7. Server updates chart every 500ms
8. Chart shows last 30 minutes initially (can scroll/zoom)

## Chart Features

- **Real-time updates**: Chart refreshes every 500ms
- **30-minute window**: Shows last 30 minutes by default
- **Range slider**: Navigate through all data
- **Pan/Zoom**: Standard Plotly controls
- **Drawing tools**: Draw lines, shapes on the chart
- **Statistics**: Live display of ticks, candles, price range

## Stopping

- **Client**: Press `Ctrl+C` to stop streaming
- **Server**: Press `Ctrl+C` to stop server
- Data remains in server memory until reset or restart

## Troubleshooting

### Client can't connect to server

```
ERROR: Cannot connect to server
```

**Solution**: Make sure server.py is running first

### Server not updating

- Check if client is sending data (watch terminal output)
- Check server terminal for errors
- Refresh browser page (http://localhost:8765/chart/)

### Chart is too crowded

- Use higher velocity to load data faster
- Adjust `INITIAL_WINDOW_MINUTES` in server.py (line 14)
- Use range slider to zoom to specific time periods

## Configuration

### Server Configuration (server.py)

```python
PORT = 8765                      # Server port
CANDLE_INTERVAL = '1min'         # Candle timeframe
MAX_CANDLES = 500                # Max candles to keep
INITIAL_WINDOW_MINUTES = 30      # Initial view window
```

### Client Configuration (client.py)

```python
SERVER_URL = 'http://localhost:8765'  # Server address
DEFAULT_VELOCITY = 10                  # Default speed
```

## Examples

### Quick test with small dataset

```bash
# Terminal 1: Start server
python server.py

# Terminal 2: Stream 1000 ticks at 50x speed
python client.py ../data/time_and_sales_nq_30min.csv --velocity 50 --max-ticks 1000 --reset
```

### Full dataset at high speed

```bash
# Terminal 1: Start server
python server.py

# Terminal 2: Stream full file at 100x speed
python client.py ../data/time_and_sales_nq.csv --velocity 100 --reset
```

### Replay specific time period

```bash
# Stream starting from row 50000
python client.py ../data/time_and_sales_nq.csv --start-from 50000 --max-ticks 10000 --velocity 20
```

## Architecture

- **Server**: Flask + Dash for HTTP API and real-time visualization
- **Client**: Pandas for CSV reading, requests for HTTP communication
- **Data Flow**: HTTP POST for tick data, Dash callbacks for chart updates
- **Threading**: Thread-safe data buffer with locks
- **Memory**: All data stored in server memory (resets on restart)
