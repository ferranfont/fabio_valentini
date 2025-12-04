# README - NinjaTrader Integration

## 📡 Communication Architecture: NinjaTrader ↔ Python

### 🏗️ General Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      NINJATRADER (C#)                       │
│                 AAIndicatorTrinchera_Draw                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  📤 TCP SERVER #1 (Port 5555)                              │
│     └─> SENDS ticks to Python                              │
│                                                             │
│  📥 TCP SERVER #2 (Port 5556)                              │
│     └─> RECEIVES signals from Python                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                    ↕                    ↕
                    │                    │
         (Port 5555)          (Port 5556)
                    │                    │
                    ↕                    ↕
┌─────────────────────────────────────────────────────────────┐
│                      PYTHON                                 │
│            main_tick_receiver_client_live.py                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  📥 TCP CLIENT #1 (Port 5555)                              │
│     └─> RECEIVES ticks from NinjaTrader                    │
│                                                             │
│  📤 TCP CLIENT #2 (Port 5556)                              │
│     └─> SENDS signals to NinjaTrader                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔌 What is TCP?

TCP (Transmission Control Protocol) is a communication protocol that:
- ✅ Guarantees data arrives in order without loss
- ✅ Establishes a persistent connection between two programs
- ✅ Acts like a bidirectional "pipe" between applications

---

## 🚦 The Two Communication Channels

### Channel 1: Ticks (Port 5555) 📊

```
NinjaTrader (SERVER) ──────> Python (CLIENT)
         Port 5555
```

**Flow:**
1. NinjaTrader opens a TCP server on port 5555
2. Python connects as a client to that server
3. Each time there's a tick, NinjaTrader sends data:
   ```
   "2025-12-04 17:52:19.000;25634.25;1;TRADE;25634.00;25634.50\n"
   ```
4. Python receives and processes the tick

---

### Channel 2: Signals (Port 5556) 🟠

```
Python (CLIENT) ──────> NinjaTrader (SERVER)
         Port 5556
```

**Flow:**
1. NinjaTrader opens a TCP server on port 5556
2. Python connects as a client to that server
3. When big volume is detected, Python sends a signal:
   ```
   "orange_dot\n"
   ```
4. NinjaTrader receives the signal and draws on the chart

---

## 🔄 Complete Signal Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. TICK OCCURS IN NINJATRADER                              │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. NinjaTrader sends tick via port 5555                    │
│    "2025-12-04 17:52:19;25634.25;..."                     │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Python receives the tick                                │
│    - Aggregates in 500ms window                            │
│    - Counts total volume                                   │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Python detects: volume > BIG_VOLUME_TRIGGER (200)      │
│    ¡Big volume event detected!                            │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. Python sends via port 5556                              │
│    "orange_dot\n"                                          │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. NinjaTrader receives "orange_dot"                       │
│    Listener thread: signalReader.ReadLine()                │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ 7. NinjaTrader executes: DrawOrangeDotSafe()               │
│    - Gets current price                                    │
│    - Draws orange circle on chart                          │
│    - Shows "🟠 Spike" text                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 Technical Details

### In NinjaTrader (C#):

```csharp
// SERVER 1: Send ticks (Port 5555)
tickServer = new TcpListener(IPAddress.Loopback, 5555);
tickServer.Start();
tickSenderClient = tickServer.AcceptTcpClient();  // Wait for connection
tickSenderWriter.WriteLine(tickData);              // Send data

// SERVER 2: Receive signals (Port 5556)
signalServer = new TcpListener(IPAddress.Loopback, 5556);
signalServer.Start();
signalClient = signalServer.AcceptTcpClient();     // Wait for connection
string signal = signalReader.ReadLine();           // Receive signal
if (signal == "orange_dot") DrawOrangeDotSafe();   // Draw
```

### In Python:

```python
# CLIENT 1: Receive ticks (Port 5555)
tick_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
tick_socket.connect(('127.0.0.1', 5555))  # Connect to server
data = tick_socket.recv(4096)              # Receive data

# CLIENT 2: Send signals (Port 5556)
signal_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
signal_socket.connect(('127.0.0.1', 5556))  # Connect to server
signal_socket.sendall("orange_dot\n")       # Send signal
```

---

## 🔑 Key Concepts

| Concept | Explanation |
|---------|-------------|
| **TCP Server** | The one that waits for connections (NinjaTrader) |
| **TCP Client** | The one that initiates the connection (Python) |
| **Port** | Number that identifies the channel (5555, 5556) |
| **127.0.0.1** | Local IP (localhost) - same computer |
| **Thread** | Separate thread to listen without blocking |
| **Dispatcher** | Executes code on UI thread (for drawing) |

---

## ⚡ Why Two Separate Ports?

1. **Simplicity**: Each channel has a clear purpose
2. **Unidirectionality**: Avoids confusion about who sends what
3. **Independence**: One channel can fail without affecting the other
4. **Clarity**: Easy to debug and monitor

---

## 🎨 How the Drawing Works

When NinjaTrader receives `"orange_dot"`:

```csharp
// 1. Get current market price
double price = GetCurrentAsk();
if (price <= 0) price = GetCurrentBid();
if (price <= 0) price = Bars.GetClose(lastIndex);

// 2. Get current bar time
int lastIndex = Bars.Count - 1;
DateTime barTime = Bars.GetTime(lastIndex);

// 3. Draw orange circle using Unicode character
Draw.Text(this,
    tag + "_BigDot",
    false,                  // AutoScale
    "\u25CF",               // Text: Black Circle Unicode
    barTime,                // X: Current time
    price,                  // Y: Price
    0,                      // Y-Offset
    Brushes.Orange,         // Color
    new SimpleFont("Arial", 30),
    TextAlignment.Center,
    Brushes.Transparent,
    Brushes.Transparent,
    100);
```

**Drawing Parameters:**
- `barTime` = Current bar (where signal is received)
- `price` = Y coordinate (price level)
- `"\u25CF"` = Unicode black circle character
- `Brushes.Orange` = Orange color
- `30` = Font size for visibility

---

## 🔧 Setup Instructions

### 1. NinjaTrader Setup

1. Copy `AAIndicatorTrinchera_Draw.cs` to:
   ```
   Documents\NinjaTrader 8\bin\Custom\Indicators\
   ```

2. Open NinjaTrader → Tools → Edit NinjaScript → Indicator

3. Select `AAIndicatorTrinchera_Draw` and compile (F5)

4. Add indicator to your chart:
   - Right-click chart → Indicators
   - Find `AAIndicatorTrinchera_Draw`
   - Set parameters:
     - Tick Send Port: **5555**
     - Signal Receive Port: **5556**

### 2. Python Setup

1. Configure parameters in `config_trinchera_live.py`:
   ```python
   BIG_VOLUME_TRIGGER = 200        # Minimum volume to trigger signal
   BIG_VOLUME_TIMEOUT = 10         # Minutes
   MEAN_REVERS_EXPAND = 14         # Points
   MEAN_REVERSE_TIMEOUT_ORDER = 3  # Minutes
   FILTER_USE_GRID = False
   GRID_MEAN_REVERS_EXPAND = 5.0
   ```

2. Run the Python script:
   ```bash
   python strat_trinchera/main_tick_receiver_client_live.py
   ```

3. Wait for connection messages:
   ```
   [TICK] Connected to NinjaTrader tick server at 127.0.0.1:5555
   [SIGNAL] Connected to NinjaTrader signal server at 127.0.0.1:5556
   ✓✓✓ BOTH CONNECTIONS ESTABLISHED ✓✓✓
   ```

---

## 📊 Signal Detection Logic

### Python Processing:

```python
# 1. Receive tick from NinjaTrader
timestamp, price = parse_tick(tick_data)

# 2. Aggregate in 500ms windows
if (timestamp - window_start) >= 500ms:
    # 3. Check if big volume
    if current_window_volume > BIG_VOLUME_TRIGGER:
        # 4. Send signal
        send_signal("orange_dot")

    # 5. Reset window
    window_start = timestamp
    current_window_volume = 0
```

### Same Logic as Backtest:

This is the **EXACT SAME** detection logic used in `find_big_volume.py`:
- ✅ Same 500ms aggregation window
- ✅ Same `BIG_VOLUME_TRIGGER` parameter
- ✅ Same volume counting logic
- ✅ Same configuration from `config_trinchera_live.py`

**The only difference:**
- `main_tick_receiver_client_live.py` → **LIVE** ticks from NinjaTrader
- `find_big_volume.py` → **HISTORICAL** ticks from CSV file

---

## 🐛 Troubleshooting

### Connection Issues

**Problem**: `[ERROR] Failed to connect to tick server`

**Solutions:**
1. Verify NinjaTrader indicator is running
2. Check NinjaTrader Output window for errors
3. Verify ports are not in use by other programs
4. Restart both NinjaTrader and Python

### No Signals Being Sent

**Problem**: `Big volume events detected: 0`

**Reason**: Volume too low (window volumes < 200)

**Solutions:**
1. Lower `BIG_VOLUME_TRIGGER` in `config_trinchera_live.py`
2. Increase `aggregation_window_ms` (500 → 1000)
3. Check volume chart in NinjaTrader to verify actual volumes

### Drawings Not Visible

**Problem**: Signal sent but no orange dot on chart

**Solutions:**
1. Check NinjaTrader Output window for `[DRAW] Dot at...` messages
2. Zoom out on chart (drawing might be off-screen)
3. Verify indicator is set to `IsOverlay = true`
4. Recompile indicator in NinjaTrader

---

## 📁 File Structure

```
strat_trinchera/
├── AAIndicatorTrinchera_Draw.cs       # NinjaTrader indicator (C#)
├── main_tick_receiver_client_live.py  # Live Python client
├── config_trinchera_live.py           # Live configuration
├── tick_receiver_client.py            # Base client class
└── README_NINJATRADER_INTEGRATION.md  # This file
```

---

## 🔄 Process Comparison

### Live Mode (Real-Time):
```
NinjaTrader → Ticks → Python → Detect Volume → Send Signal → Draw
    ↑                                                           ↓
    └───────────────────────────────────────────────────────────┘
```

### Backtest Mode (Historical):
```
CSV File → util_trinchera.py → find_big_volume.py → db_bins.csv
                                       ↓
                              strat_trinchera.py (backtest)
                                       ↓
                              plot_trades_chart.py (visualize)
```

---

## ✅ System Status Indicators

When running correctly, you should see:

### Python Console:
```
[CONFIG] Loaded configuration from config_trinchera_live.py
[TICK] ✓ CONNECTED to NinjaTrader tick server
[SIGNAL] ✓ CONNECTED to NinjaTrader signal server
✓✓✓ BOTH CONNECTIONS ESTABLISHED ✓✓✓

[TICK #100] 2025-12-04 18:45:24.000 | Price: 25615.50 | Window Vol: 4
[TICK #200] 2025-12-04 18:45:37.000 | Price: 25614.00 | Window Vol: 33
```

### NinjaTrader Output:
```
[TICK SENDER] Server started on port 5555, waiting for Python...
[TICK SENDER] Python connected! Sending ticks...
[SIGNAL RECEIVER] Server started on port 5556, waiting for Python...
[SIGNAL RECEIVER] Python connected! Listening for signals...
[SIGNAL RECEIVER] ✓ SIGNAL #1 - Triggering draw...
[DRAW] ✓✓✓ SIGNAL #1 DRAWN ✓✓✓
[DRAW] Dot at 25634.25 | Time: 17:52:19
```

---

## 📝 Notes

- **Thread Safety**: All drawing operations use `Dispatcher.InvokeAsync()` to ensure thread-safe UI updates
- **BOM Handling**: Python removes Byte Order Mark (`\ufeff`) from timestamps automatically
- **Graceful Shutdown**: Both NinjaTrader and Python handle disconnections gracefully
- **No Strategy Needed**: The indicator handles everything - no separate strategy required
- **Permanent Drawings**: Orange dots never disappear (no auto-removal timers)

---

## 📚 Related Documentation

- **CLAUDE.md** - Complete project documentation
- **config_trinchera_live.py** - Live configuration parameters
- **main_trinchera.py** - Backtest pipeline workflow

---

*Last updated: 2025-12-04*
*System Version: 3.0 (Live NinjaTrader Integration)*
