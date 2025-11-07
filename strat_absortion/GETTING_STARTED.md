# Getting Started with Client-Server Architecture

## Quick Start Guide

### 1. Install Dependencies

```bash
pip install -r requirements_client_server.txt
```

This installs:
- pandas, numpy (required)
- matplotlib (required)
- mss, opencv-python (optional, for screen recording)

### 2. Configure Settings (Optional)

Client and server have **separate configuration sections** at the top of each file.

**Edit `tick_client.py`** (lines 16-38) to customize:
```python
# Network configuration
PORT = 55555  # Server port (localhost is always used)

# Data source
CSV_PATH = DATA_DIR / f"historic/{FICHERO_ORIGEN}.csv"

# Streaming speed
TICK_DELAY_MS = 10  # 10ms = ~100 ticks/sec
```

**Edit `tick_server.py`** (lines 22-52) to customize:
```python
# Network configuration
PORT = 55555  # Server port (localhost is always used)

# Strategy parameters
PROFILE_WINDOW = 20
MIN_PRICE_LEVELS = 20
MIN_BID_ASK_SIZE = 30

# Screen recording
SCREEN_RECORD_DURATION = 10  # seconds
SCREEN_RECORD_FPS = 10
```

### 3. Start the Server

```bash
python tick_server.py
```

Server output:
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

[OK] Screen recording libraries loaded (mss, opencv)
[OK] Server listening on localhost:55555
[OK] Waiting for client connection...
[OK] Press Ctrl+C to stop server
```

### 4. Start the Client (in another terminal)

```bash
python tick_client.py
```

Client output:
```
================================================================================
TICK DATA CLIENT
================================================================================
CSV File: ...time_and_sales_nq_20250915_redux.csv
Server: localhost:55555
Tick Delay: 10ms
================================================================================

Loading CSV: ...
Loaded 448332 ticks

Connecting to server at localhost:55555...
[OK] Connected to server

Starting to stream ticks (delay: 10ms between ticks)...
Press Ctrl+C to stop

Progress:   2.2% (1,000/448,332) | Rate: 100 ticks/sec
...
```

### 5. What Happens When Pattern is Detected

**Server Console:**
```
********************************************************************************
PATTERN DETECTED!
Detection #1
Shape: d_shape
Price: 20125.50
Time: 2025-09-15 14:30:22.142000
********************************************************************************

[RECORDING] Starting screen capture for 10s...
[RECORDING] Completed! Saved to: recordings/detection_1_d_shape_20250915_143022.mp4
```

**Outputs Created:**
1. `recordings/detection_1_d_shape_20250915_143022.mp4` - 10-second screen recording
2. `charts/detections/absorption_report_streaming_20250915.html` - HTML report with comprehensive charts:
   - Market Profile at detection (BID/ASK volume distribution)
   - Price Movement scatter plot (recent history)
   - Bid/Ask Bubble chart (volume-sized bubbles over time)
3. `outputs/absortion_shape/db_shapes_streaming_20250915_143022.csv` - Signal data (on completion)

## File Structure

```
strat_absortion/
├── absorption_strategy_streaming.py   # Streaming strategy class
├── tick_client.py                     # Data streamer (config at top, lines 16-38)
├── tick_server.py                     # Server (config at top, lines 22-52)
│
├── requirements_client_server.txt     # Dependencies
├── GETTING_STARTED.md                 # This file
└── README_CLIENT_SERVER.md            # Complete documentation

Outputs:
../recordings/                         # Screen recordings (MP4)
../charts/detections/                  # HTML reports
../outputs/absortion_shape/            # CSV signals
```

## Usage Modes

### Mode 1: Fast Backtesting (Maximum Speed)

```python
# In tick_client.py (line 30)
TICK_DELAY_MS = 0  # No delay
```

- Processes ~10,000 ticks/second
- Completes 450k ticks in ~45 seconds
- Best for historical analysis

### Mode 2: Realistic Simulation (100 ticks/sec)

```python
# In tick_client.py (line 30)
TICK_DELAY_MS = 10  # 10ms delay
```

- Processes ~100 ticks/second
- Simulates real market speed
- Best for testing trading logic

### Mode 3: Observable Demo (10 ticks/sec)

```python
# In tick_client.py (line 30)
TICK_DELAY_MS = 100  # 100ms delay
```

- Processes ~10 ticks/second
- Easy to observe in real-time
- Best for demonstrations

## Common Tasks

### Change Data Source

Edit `tick_client.py` (line 27):
```python
CSV_PATH = Path("C:/path/to/your/data.csv")
```

### Adjust Detection Sensitivity

Edit `tick_server.py` (lines 26-36):

Make detections more frequent:
```python
MIN_PRICE_LEVELS = 15  # Lower (was 20)
MIN_BID_ASK_SIZE = 20  # Lower (was 30)
COOLDOWN_PERIOD = 30   # Shorter (was 60)
```

Make detections more strict:
```python
MIN_PRICE_LEVELS = 25  # Higher
MIN_BID_ASK_SIZE = 50  # Higher
EXTREME_VOLUME_MULTIPLIER = 3  # Higher (was 2)
```

### Disable Screen Recording

Simply don't install mss and opencv-python:
```bash
pip uninstall mss opencv-python
```

Server will continue working without screen recording.

### Change Recording Duration

Edit `tick_server.py` (line 43):
```python
SCREEN_RECORD_DURATION = 15  # 15 seconds instead of 10
```

### View Results

- **Screen Recordings:** Open `.mp4` files in `recordings/` folder
- **HTML Report:** Open in browser from `charts/detections/`
- **CSV Signals:** Open in Excel from `outputs/absortion_shape/`

## Troubleshooting

### "Connection refused"
→ Start server first, then client

### "CSV file not found"
→ Check `CSV_PATH` in `tick_client.py` (line 27)

### "Screen recording not available"
→ Optional. Install with: `pip install mss opencv-python`

### Server not detecting patterns
→ Check strategy parameters in `tick_server.py` (lines 26-36, might be too strict)

### Client sends data too fast
→ Increase `TICK_DELAY_MS` in `tick_client.py` (line 30)

## Architecture Flow

```
┌──────────────┐
│  CSV File    │  Historical tick data
└──────┬───────┘
       │
       ▼
┌──────────────────┐
│  tick_client.py  │  Reads CSV, streams via TCP
└──────┬───────────┘
       │ JSON over TCP (port 55555)
       ▼
┌──────────────────┐
│  tick_server.py  │  Receives ticks
└──────┬───────────┘
       │
       ▼
┌──────────────────────┐
│ Streaming Strategy   │  Processes tick-by-tick
│ - Market Profile     │  Detects d/p shapes
│ - Pattern Detection  │
└──────┬───────────────┘
       │
       │ On Detection
       ▼
┌──────────────────────┐
│ Callback Handler     │  Triggers actions:
│ - Console alert      │  1. Print detection
│ - HTML report        │  2. Update report
│ - Screen recorder    │  3. Record screen 10s
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│     Outputs          │
│ - MP4 recordings     │
│ - HTML report        │
│ - CSV signals        │
└──────────────────────┘
```

## Next Steps

1. ✅ Install dependencies: `pip install -r requirements_client_server.txt`
2. ✅ Configure settings (optional):
   - Edit `tick_client.py` (lines 16-38) for port and data settings
   - Edit `tick_server.py` (lines 22-52) for strategy and recording settings
3. ✅ Start server: `python tick_server.py`
4. ✅ Start client: `python tick_client.py`
5. ✅ Watch console for detections
6. ✅ Check `recordings/` folder for screen captures
7. ✅ Open HTML report in browser
8. ✅ Review CSV signals

## Support

- **Full Documentation:** See `README_CLIENT_SERVER.md`
- **Client Configuration:** Edit top of `tick_client.py` (lines 16-38)
- **Server Configuration:** Edit top of `tick_server.py` (lines 22-52)

## Tips

💡 **Run server first, client second** - Server must be listening before client connects

💡 **Use fast mode for backtesting** - Set `TICK_DELAY_MS = 0` for maximum speed

💡 **Monitor memory** - Server keeps 2-hour buffer, restart if needed for long streams

💡 **Check recordings folder** - Videos saved automatically on each detection

💡 **Adjust sensitivity** - Modify strategy parameters in config to get more/fewer detections

💡 **Press Ctrl+C to stop** - Both client and server can be interrupted safely

## Real-Time Mode: Using NinjaTrader

Instead of streaming historical CSV data with `tick_client.py`, you can stream **live market data** directly from NinjaTrader!

### Setup Steps

**1. Copy the Indicator to NinjaTrader**

Copy `ninja/AASender.cs` to your NinjaTrader indicators folder:
```
C:\Users\[YourUser]\Documents\NinjaTrader 8\bin\Custom\Indicators\
```

**2. Compile in NinjaTrader**

1. Open NinjaTrader
2. Tools → NinjaScript Editor (F5)
3. Right-click `Indicators` → Compile
4. Check for errors in output window

**3. Start the Python Server**

```bash
python tick_server.py
```

Wait for: `[OK] Server listening on localhost:55555`

**4. Apply AASender Indicator**

1. Open a chart for your instrument (e.g., NQ)
2. Right-click chart → Indicators → AASender
3. Configure properties:
   - **Server Host:** 127.0.0.1
   - **Server Port:** 55555
   - **Max Connection Attempts:** 10
   - **Reconnect Delay:** 5 seconds
4. Click OK

**5. Indicator Status**

On the chart you'll see:
```
[AASender] Connected to 127.0.0.1:55555
Ticks sent: 15,234
```

The counter updates every 1,000 ticks.

### How It Works

```
NinjaTrader Chart
    ↓
AASender Indicator (C#)
    ├─ OnMarketData() captures every tick
    ├─ Formats as JSON: {timestamp, price, volume, side}
    └─ Sends via TCP socket
        ↓
tick_server.py (Python)
    ├─ Receives tick stream
    ├─ Processes through streaming strategy
    └─ On detection:
        ├─ Console alert + beep
        ├─ Records screen 10s
        └─ Updates HTML report
```

### JSON Format Sent

The indicator sends each tick as:
```json
{
  "timestamp": "2025-11-07T09:30:15.234",
  "price": 20125.50,
  "volume": 2,
  "side": "ASK"
}
```

Side determination:
- **ASK**: Price >= Ask price (buyer aggressive)
- **BID**: Price <= Bid price (seller aggressive)
- **BETWEEN**: Price between bid/ask (rare)

### Reconnection Handling

If server disconnects:
1. Indicator detects broken connection
2. Automatically attempts reconnection (up to 10 times)
3. Waits 5 seconds between attempts
4. Continues sending once reconnected

### Stopping the Stream

**Option 1:** Remove indicator from chart
- Right-click indicator → Remove

**Option 2:** Stop NinjaTrader
- Indicator sends `{command: "COMPLETE"}` on shutdown
- Server saves final report and CSV

### Output Files (Real-Time Mode)

Same as CSV streaming mode:
- **Recordings:** `recordings/detection_N_shape_YYYYMMDD_HHMMSS.mp4`
- **HTML Report:** `charts/detections/absorption_report_streaming_YYYYMMDD.html`
- **CSV Signals:** `outputs/absortion_shape/db_shapes_streaming_YYYYMMDD_HHMMSS.csv`

### Troubleshooting

**Indicator won't compile:**
→ Check for syntax errors in NinjaScript Editor output window
→ Ensure you're using NinjaTrader 8 (not version 7)

**Connection failed:**
→ Start `tick_server.py` BEFORE applying indicator to chart
→ Check firewall isn't blocking port 55555
→ Verify server shows "Waiting for client connection..."

**No data received by server:**
→ Ensure chart is in **Realtime** state (not Historical)
→ Check indicator status on chart shows "Connected"
→ Verify market is open (no ticks = no data)

**Ticks sent counter not updating:**
→ Market may be closed or slow
→ Remove and re-add indicator to chart
→ Check NinjaTrader connection status (bottom-right of platform)

### Comparison: CSV vs Live NinjaTrader

| Feature | tick_client.py (CSV) | AASender (NinjaTrader) |
|---------|---------------------|------------------------|
| Data source | Historical CSV files | Live market data |
| Speed control | Configurable delay | Real market speed |
| Instruments | Pre-recorded only | Any NT8 instrument |
| Best for | Backtesting, optimization | Real-time alerts, paper trading |
| Setup | Python script | NinjaScript indicator |

### Real-Time Trading Workflow

1. **Development Phase** - Use `tick_client.py` with historical CSV
   - Fast backtesting (450k ticks in 45 seconds)
   - Parameter optimization
   - Strategy validation

2. **Live Testing Phase** - Use `AASender` with NinjaTrader
   - Paper trading account
   - Real market conditions
   - Screen recording of detections

3. **Production Phase** - Extend `AASender` to execute trades
   - Send orders on detection
   - Position management
   - Risk controls

## Enjoy!

You now have a real-time absorption pattern detection system with automatic screen recording! 🚀

**Two streaming modes:**
- 📊 **Historical CSV** → `tick_client.py` → Fast backtesting
- 📈 **Live NinjaTrader** → `AASender` indicator → Real-time alerts
