# Trinchera - NinjaTrader Live Trading Integration

## Overview

This guide explains how to integrate the Trinchera strategy with NinjaTrader for live trading.

---

## Architecture

```
┌─────────────────┐         ┌──────────────────────────────┐
│  NINJATRADER    │         │  PYTHON (tick_server_        │
│                 │         │  trinchera_bidirect.py)      │
│  AAStrategyBi-  │ Port    │                              │
│  derect.cs      │ 5555    │  • Big Volume Detection      │
│                 │────────→│  • SMA Calculation           │
│  Sends:         │  TICKS  │  • Mean Reversion Levels     │
│  - Timestamp    │         │  • Entry Signal Detection    │
│  - Price        │         │  • Position Management       │
│  - Volume       │         │                              │
│  - Bid/Ask      │         │                              │
│                 │ Port    │                              │
│  Receives:      │ 5556    │                              │
│  - Entry Orders │←────────│  • Entry Orders (LONG/SHORT) │
│  - Exit Orders  │ ORDERS  │  • Exit Orders (TP/SL)       │
│                 │         │                              │
└─────────────────┘         └──────────────────────────────┘
```

---

## Setup Instructions

### 1. NinjaTrader Configuration

#### Option A: Reuse Existing `AAStrategyBiderect.cs` (Recommended ⭐)

**You can reuse your existing NinjaTrader strategy with minor modifications:**

1. Open `AAStrategyBiderect.cs` in NinjaTrader
2. Change the port numbers (lines ~50-55):

```csharp
// OLD (Absorption Strategy)
private const int TICK_SEND_PORT = 5553;
private const int ORDER_RECEIVE_PORT = 5554;

// NEW (Trinchera Strategy)
private const int TICK_SEND_PORT = 5555;  // ← Change to 5555
private const int ORDER_RECEIVE_PORT = 5556;  // ← Change to 5556
```

3. Compile and apply to your chart
4. **That's it!** The same strategy works for Trinchera because all signal logic is in Python.

**Why this works:**
- NinjaTrader just sends raw tick data (Price, Volume, Bid, Ask)
- Python does all the strategy logic (big volume detection, SMA, mean reversion)
- No need to duplicate code in C#

#### Option B: Create New Strategy (Advanced)

If you want NinjaTrader to do big volume detection in C#:

1. Create `AAStrategyTrinchera.cs` based on `AAStrategyBiderect.cs`
2. Add big volume detection logic
3. Add SMA calculation
4. Send "orange dot" signals instead of raw ticks

**Not recommended** - Python is more flexible for strategy modifications.

---

### 2. Python Setup

#### Install Requirements (if not already installed)
```bash
pip install numpy
```

#### File Structure
```
strat_trinchera/
├── config_trinchera_live.py          ← Live trading config
├── tick_server_trinchera_bidirect.py ← Main live trading script
├── live_trades/                       ← Trade logs (auto-created)
│   └── trinchera_trades_YYYYMMDD.csv
└── NINJATRADER_INTEGRATION.md         ← This file
```

---

## Usage

### Step 1: Configure Settings

Edit `config_trinchera_live.py`:

```python
# CRITICAL SAFETY SETTINGS
PAPER_TRADING_MODE = True        # Set to False for REAL trading
REQUIRE_CONFIRMATION = True      # Set to False to disable confirmations

# STRATEGY PARAMETERS
TP_POINTS = 5.0                  # Take profit
SL_POINTS = 9.0                  # Stop loss
MEAN_REVERS_EXPAND = 10          # Entry distance (±10 pts from orange dot)
BIG_VOLUME_TRIGGER = 200         # Big volume threshold
SMA_PERIOD = 200                 # SMA period

# RISK MANAGEMENT
MAX_CONTRACTS = 1                # Max contracts per trade
MAX_DAILY_LOSS = 1000.0         # Circuit breaker ($)
MAX_DAILY_TRADES = 50           # Circuit breaker (trades)
```

### Step 2: Start NinjaTrader

1. Open NinjaTrader
2. Apply `AAStrategyBiderect` to your NQ chart
3. Verify it shows "Waiting for Python connection..." in output window

### Step 3: Start Python

```bash
cd d:\PYTHON\ALGOS\fabio_valentini\strat_trinchera
python tick_server_trinchera_bidirect.py
```

You should see:
```
================================================================================
TRINCHERA LIVE TRADING - BIDIRECTIONAL NINJATRADER INTEGRATION
================================================================================

📋 Configuration:
   TP: 5.0 pts | SL: 9.0 pts
   Big Volume Trigger: 200
   Entry Distance: ±10 pts
   SMA Period: 200
   SMA Filter: OFF
   Time Filter: OFF
   Trailing Stop: ON

🔌 Network:
   Receiving ticks on: 127.0.0.1:5555
   Sending orders to: localhost:5556

⚠️  Safety:
   Paper Trading: True
   Require Confirmation: True
   Max Daily Loss: $1000.0
   Max Daily Trades: 50

✅ Connected to NinjaTrader order handler
✅ Waiting for NinjaTrader connection...
✅ NinjaTrader connected from ('127.0.0.1', 12345)

✅ LIVE TRADING STARTED - Press Ctrl+C to stop

📊 Initializing SMA: 20/200 ticks
📊 Initializing SMA: 40/200 ticks
...
📊 Initializing SMA: 200/200 ticks
```

---

## Live Trading Workflow

### 1. SMA Initialization
```
📊 Initializing SMA: 20/200 ticks
📊 Initializing SMA: 40/200 ticks
...
📊 Initializing SMA: 200/200 ticks
```
- Collects first 200 ticks to calculate SMA
- No trading until SMA is ready

### 2. Orange Dot Detection
```
🟠 BIG VOLUME DETECTED: 250 contracts at 20500.25 (Threshold: 200)
📈 Current SMA: 20495.50
🟠 ORANGE DOT at 20500.25 | BUY: 20490.25 | SELL: 20510.25
```
- Detects big volume (≥200 contracts)
- Calculates entry levels (±10 pts from orange dot)
- Timeout: 10 minutes (won't trigger again during this period)

### 3. Entry Signal
```
🟢 BUY SIGNAL at 20490.25 (Level: 20490.25)
📤 Order sent: {'action': 'ENTRY', 'side': 'LONG', 'contracts': 1, ...}
💼 Position opened: LONG @ 20490.25 | TP: 20495.25 | SL: 20481.25
```
- Price touches buy level → LONG entry
- Price touches sell level → SHORT entry
- Only one position at a time

### 4. Exit Signal
```
💰 Position closed: TARGET @ 20495.25 | P&L: $100.00 (+5.00 pts)
📊 Daily P&L: $100.00 | Trades: 1
```
- TP hit: +5 pts = $100 profit
- SL hit: -9 pts = $180 loss

---

## Safety Features

### 1. Paper Trading Mode (Default)
```python
PAPER_TRADING_MODE = True
```
- Orders are logged but NOT sent to NinjaTrader
- Test strategy risk-free
- Set to `False` for real trading

### 2. Manual Confirmation (Default)
```python
REQUIRE_CONFIRMATION = True
```
- Prompts for confirmation before each order:
```
⚠️  CONFIRM ORDER: {'action': 'ENTRY', 'side': 'LONG', ...} (yes/no):
```
- Type `yes` to approve, anything else cancels

### 3. Circuit Breakers
```python
MAX_DAILY_LOSS = 1000.0     # Stop trading if loss exceeds $1000
MAX_DAILY_TRADES = 50       # Stop trading after 50 trades
```
- Automatic shutdown if limits exceeded
```
🚨 CIRCUIT BREAKER: Daily loss limit $1000.00 >= $1000.0
```

### 4. Time Filter (Optional)
```python
FILTER_TIME_OF_DAY = True
START_TRADING_TIME = "18:50:00"
END_TRADING_TIME = "22:50:00"
```
- Only trades during specified hours
- Useful for avoiding low-liquidity periods

---

## Trade Logging

All trades are automatically saved to CSV:
```
live_trades/trinchera_trades_20251201.csv
```

Format:
```csv
entry_time;exit_time;side;entry_price;exit_price;exit_reason;pnl_points;pnl_dollars;contracts
2025-12-01T14:30:25;2025-12-01T14:32:10;LONG;20490.25;20495.25;TARGET;5.00;100.00;1
```

---

## Monitoring & Debugging

### Real-Time Logs

#### Normal Operation
```
🟠 BIG VOLUME DETECTED: 250 contracts at 20500.25
🟠 ORANGE DOT at 20500.25 | BUY: 20490.25 | SELL: 20510.25
🟢 BUY SIGNAL at 20490.25
💼 Position opened: LONG @ 20490.25 | TP: 20495.25 | SL: 20481.25
💰 Position closed: TARGET @ 20495.25 | P&L: $100.00
📊 Daily P&L: $100.00 | Trades: 1
```

#### No Signal (Levels Expired)
```
🟠 ORANGE DOT at 20500.25 | BUY: 20490.25 | SELL: 20510.25
(3 minutes pass, no price touches levels)
(Next big volume creates new levels)
```

#### SMA Filter Active
```
🟠 BIG VOLUME DETECTED: 250 contracts at 20490.00
📈 Current SMA: 20495.50
✅ SMA Filter: Orange dot BELOW SMA → SHORT only
```

---

## Troubleshooting

### "Failed to connect to NinjaTrader order handler"
**Cause**: NinjaTrader not running or wrong port
**Fix**:
1. Verify `AAStrategyBiderect` is running in NinjaTrader
2. Check port numbers match:
   - NinjaTrader: `ORDER_RECEIVE_PORT = 5556`
   - Python: `ORDER_SERVER_PORT = 5556`

### "NinjaTrader disconnected. Reconnecting..."
**Cause**: NinjaTrader strategy stopped
**Fix**: Restart strategy in NinjaTrader, Python will auto-reconnect

### "No trades being generated"
**Possible causes**:
1. **SMA not initialized**: Wait for 200 ticks
2. **No big volume**: Volume below threshold (200 contracts)
3. **Levels expired**: 3-minute timeout, waiting for next big volume
4. **Time filter**: Outside trading hours (if enabled)
5. **Circuit breaker**: Daily loss/trade limit reached

### "Orders not executing in NinjaTrader"
**Check**:
1. Paper Trading Mode: Set `PAPER_TRADING_MODE = False`
2. NinjaTrader receiving orders: Check NT output window for incoming messages
3. Order syntax: Verify JSON format matches NT expectations

---

## Differences from Backtesting

| Feature | Backtest (main_trinchera.py) | Live (tick_server_trinchera_bidirect.py) |
|---------|------------------------------|-------------------------------------------|
| **Data Source** | CSV files (historical) | NinjaTrader (real-time) |
| **Big Volume** | Pre-calculated bins file | Real-time detection (Python) |
| **SMA** | Pre-calculated | Real-time rolling buffer (200 ticks) |
| **Entry** | Simulated fills | Actual orders to NinjaTrader |
| **Risk** | None (historical) | Real money (if PAPER_TRADING_MODE=False) |
| **Slippage** | Idealized | Real market slippage |
| **Speed** | Fast (vectorized) | Real-time (sequential) |

---

## Advanced: Enabling Real Trading

**⚠️ CRITICAL: Only do this when ready!**

1. **Test thoroughly in paper trading mode first**
2. Edit `config_trinchera_live.py`:
```python
PAPER_TRADING_MODE = False      # Enable real trading
REQUIRE_CONFIRMATION = True     # Keep confirmations ON for safety
```
3. Start Python - you'll see:
```
🚨 REAL TRADING MODE! Type 'START' to continue:
```
4. Type `START` to begin
5. Each order will still require confirmation:
```
⚠️  CONFIRM ORDER: {...} (yes/no): yes
```

6. **After gaining confidence**, disable confirmations:
```python
REQUIRE_CONFIRMATION = False    # Fully automated
```

---

## Ports Summary

| Component | Port | Purpose |
|-----------|------|---------|
| Python Receiver | 5555 | Receives tick data FROM NinjaTrader |
| Python Sender | 5556 | Sends orders TO NinjaTrader |

**Conflict Check**: Make sure these ports aren't used by other applications

---

## Performance Tips

1. **SMA Buffer**: Uses `deque(maxlen=200)` for efficient rolling calculation
2. **Memory**: Minimal overhead (~10MB for state management)
3. **Latency**: <1ms signal detection after tick received
4. **Concurrent**: Threading for tick receiver (non-blocking)

---

## Next Steps

1. ✅ Configure `config_trinchera_live.py`
2. ✅ Start NinjaTrader with `AAStrategyBiderect`
3. ✅ Run `python tick_server_trinchera_bidirect.py`
4. ✅ Monitor logs and verify signals
5. ✅ Test in paper mode for several days
6. ✅ Enable real trading (when confident)

---

## Support

For issues or questions:
1. Check logs in Python console
2. Check NinjaTrader output window
3. Verify port connections
4. Review configuration settings

---

*Last updated: 2025-12-01*
*Version: 1.0 (Initial Live Trading Release)*
