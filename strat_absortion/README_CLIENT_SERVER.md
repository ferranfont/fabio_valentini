# Client-Server Architecture for Absorption Strategy

## Overview

Real-time streaming architecture for absorption pattern detection with automatic screen recording.

**Architecture:**
```
CSV File → Client → [TCP Socket] → Server → Strategy → Screen Recording
```

## Components

### 1. Client (`client.py`)
- Reads tick data from CSV file
- Streams data to server via TCP socket
- Simulates real-time data feed

### 2. Server (`server.py`)
- Receives tick stream from client
- Processes ticks with `AbsorptionStrategyStreaming`
- Records screen for 10 seconds on pattern detection
- Generates HTML reports and CSV signals

### 3. Streaming Strategy (`absorption_strategy_streaming.py`)
- Real-time tick-by-tick processing
- Pattern detection (d-shape, p-shape)
- Triggers callback on detection

### 4. Configuration
- **Client:** Configuration at top of `client.py` (lines 16-38)
  - Port, data source, streaming speed
- **Server:** Configuration at top of `server.py` (lines 18-51)
  - Port, strategy parameters, screen recording settings
- **Note:** Both always use localhost (127.0.0.1)

## Quick Start

### Prerequisites

Install required libraries:
```bash
pip install pandas mss opencv-python numpy
```

### Step 1: Start the Server

Open a terminal and run:
```bash
cd strat_absortion
python server.py
```

You should see:
```
================================================================================
ABSORPTION STRATEGY SERVER
================================================================================
Host: localhost
Port: 55555

Strategy Configuration:
  Profile Window: 20s
  Min Price Levels: 20
  Min Bid/Ask Size: 30
  Cooldown: 60s

Screen Recording:
  Duration: 10s
  FPS: 10
  Output: C:\trade\ferran\fabio_valentini\recordings
================================================================================

[OK] Server listening on localhost:55555
[OK] Waiting for client connection...
```

### Step 2: Start the Client

Open another terminal and run:
```bash
cd strat_absortion
python client.py
```

You should see:
```
================================================================================
TICK DATA CLIENT
================================================================================
CSV File: C:\trade\ferran\fabio_valentini\data\historic\time_and_sales_nq_20250915_redux.csv
Server: localhost:55555
Tick Delay: 10ms
================================================================================

Loading CSV: ...
Loaded 448332 ticks
Time range: 2025-09-15 06:00:00 to 2025-09-16 22:00:00

Connecting to server at localhost:55555...
[OK] Connected to server

Starting to stream ticks (delay: 10ms between ticks)...
Press Ctrl+C to stop

Progress:   2.2% (1,000/448,332) | Rate: 100 ticks/sec
...
```

### What Happens

1. **Client** reads CSV and sends ticks to server
2. **Server** processes each tick through strategy
3. **When pattern detected:**
   - Console shows detection alert
   - HTML report updated
   - **Screen recording starts for 10 seconds**
4. **On completion:**
   - HTML report finalized
   - CSV signals saved
   - Screen recordings available

## Configuration

Client and server are **completely separate** with their own configuration sections.
Both always use **localhost (127.0.0.1)** for communication.

### Client Configuration (`client.py`, lines 16-38)

```python
# Network Settings
PORT = 55555  # Server port (localhost is always used)

# Data Source
CSV_PATH = DATA_DIR / f"historic/{FICHERO_ORIGEN}.csv"

# Streaming Speed
TICK_DELAY_MS = 10  # Milliseconds between ticks
# 0 = Maximum speed (backtesting)
# 10 = ~100 ticks/sec (realistic)
# 100 = Slower, more observable
```

### Server Configuration (`server.py`, lines 18-51)

```python
# Network Settings
PORT = 55555  # Server port (localhost is always used)

# Strategy Parameters
PROFILE_WINDOW = 20  # Rolling window in seconds
MIN_PRICE_LEVELS = 20  # Minimum price levels
MIN_BID_ASK_SIZE = 30  # Minimum bar size
COOLDOWN_PERIOD = 60  # Seconds between detections

# Screen Recording
SCREEN_RECORD_DURATION = 10  # Recording duration (seconds)
SCREEN_RECORD_FPS = 10  # Frames per second
SCREEN_RECORD_DIR = Path("../recordings")
```

## Output Files

### Screen Recordings
Location: `recordings/`

Format: `detection_{num}_{shape}_{timestamp}.mp4`

Example:
```
recordings/
├── detection_1_d_shape_20250915_143022.mp4
├── detection_2_p_shape_20250915_144510.mp4
└── detection_3_d_shape_20250915_150234.mp4
```

### HTML Report
Location: `charts/detections/`

File: `absorption_report_streaming_{date}.html`

### CSV Signals
Location: `outputs/absortion_shape/`

File: `db_shapes_streaming_{datetime}.csv`

## Advanced Usage

### Custom CSV File

Edit `client.py` (line 29):
```python
CSV_PATH = Path("C:/path/to/your/data.csv")
```

### Disable Screen Recording

If you don't need screen recording, simply don't install the libraries:
```bash
# Server will run without screen recording
# You'll see: [WARNING] Screen recording not available
```

### Fast Backtesting

For maximum speed, edit `client.py` (line 32):
```python
TICK_DELAY_MS = 0  # Maximum speed
```

## Troubleshooting

### Connection Refused
- Make sure server is running before starting client
- Check firewall settings
- Verify HOST and PORT match in both client and server

### Screen Recording Not Working
Install required libraries:
```bash
pip install mss opencv-python numpy
```

If still not working, check:
- Video codec compatibility: Try changing `VIDEO_CODEC` in config
- Permissions: Ensure write access to recordings directory

### Memory Usage
Server keeps 2 hours of tick buffer. For very long streams:
- Monitor memory usage
- Restart server periodically if needed

### CSV Format Issues
Supported formats:
- European CSV (semicolon separator, comma decimal)
- DOM format (auto-detected)

## Performance

### Typical Rates
- **Fast mode** (TICK_DELAY_MS=0): ~10,000 ticks/sec
- **Realistic mode** (TICK_DELAY_MS=10): ~100 ticks/sec
- **Observable mode** (TICK_DELAY_MS=100): ~10 ticks/sec

### Resource Usage
- **CPU**: Low to moderate (depends on tick rate)
- **Memory**: ~200-500 MB (2-hour tick buffer)
- **Disk**: Recordings ~5-10 MB per 10-second video
- **Network**: ~1-5 KB/sec (depends on tick rate)

## Integration Example

### Real-Time Trading System

```python
# custom_server.py
from absorption_strategy_streaming import AbsorptionStrategyStreaming

def on_detection(detection_data):
    """Custom callback for pattern detection."""
    shape = detection_data['shape']
    price = detection_data['price']

    if shape == 'd_shape':
        send_long_order(price)
    elif shape == 'p_shape':
        send_short_order(price)

    # Record screen
    recorder.record(10, f"trade_{shape}")

strategy = AbsorptionStrategyStreaming(
    profile_window=20,
    on_detection_callback=on_detection
)

# Process live feed
for tick in live_data_feed:
    strategy.process_tick(
        tick.timestamp,
        tick.price,
        tick.volume,
        tick.side
    )
```

## Comparison: Batch vs Streaming

### Batch Mode (`main.py`)
- Processes complete CSV file at once
- Generates comprehensive reports
- Future profile analysis (forward-looking)
- Best for backtesting historical data

### Streaming Mode (`server.py`)
- Processes ticks one at a time
- Real-time detection
- Screen recording on detection
- Best for live trading or simulation

## Architecture Diagram

```
┌─────────────────┐
│   CSV File      │
│  (Historical    │
│   Tick Data)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Client.py     │
│  - Read CSV     │
│  - Parse ticks  │
│  - Send via TCP │
└────────┬────────┘
         │ TCP Socket
         │ (JSON messages)
         ▼
┌─────────────────┐       ┌──────────────────────┐
│   Server.py     │───────│ Screen Recorder      │
│  - Receive data │       │  - mss (capture)     │
│  - Process ticks│       │  - opencv (encode)   │
└────────┬────────┘       └──────────────────────┘
         │                         │
         ▼                         │
┌─────────────────┐                │
│  Streaming      │                │
│  Strategy       │                │
│  - Market       │                │
│    Profile      │                │
│  - Pattern      │                │
│    Detection    │                │
└────────┬────────┘                │
         │                         │
         │  On Detection           │
         ├─────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│          Outputs                │
│  1. HTML Report                 │
│  2. CSV Signals                 │
│  3. Screen Recordings (10s MP4) │
└─────────────────────────────────┘
```

## Support

For issues or questions:
1. Check configuration:
   - Client: Edit top of `client.py` (lines 16-38)
   - Server: Edit top of `server.py` (lines 18-51)
2. Review console output for error messages
3. Verify all dependencies are installed
4. Check file paths and permissions
5. Note: Client and server always use localhost (same machine)

## Future Enhancements

Planned features:
- [ ] WebSocket support for browser-based clients
- [ ] Multi-client support (broadcast mode)
- [ ] Real-time web dashboard
- [ ] Configurable recording trigger (before/after detection)
- [ ] Audio alerts on detection
- [ ] Email/SMS notifications
- [ ] Database storage for signals
