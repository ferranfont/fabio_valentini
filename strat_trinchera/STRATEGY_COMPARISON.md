# Strategy Comparison: Absorption vs Trinchera

## Overview

You now have **TWO separate NinjaTrader strategies** that can run simultaneously:

---

## Strategy #1: Absorption (Market Profile)

### NinjaTrader
- **File**: `AAStrategyBiderect.cs` *(existing)*
- **Ports**:
  - Send ticks: 5553
  - Receive orders: 5554

### Python
- **File**: `tick_server_bidirect.py` *(existing)*
- **Strategy**: Market Profile pattern detection (d-shape/p-shape)
- **Signals**: Pre-calculated from `plot_deep.py`

### Use Case
- Mean reversion based on volume distribution patterns
- Requires historical signal generation first

---

## Strategy #2: Trinchera (Big Volume + Mean Reversion)

### NinjaTrader
- **File**: `AAStrategyTrinchera.cs` *(NEW - copy to NinjaTrader)*
- **Ports**:
  - Send ticks: 5555
  - Receive orders: 5556

### Python
- **File**: `tick_server_trinchera_bidirect.py` *(NEW)*
- **Config**: `config_trinchera_live.py` *(NEW)*
- **Strategy**: Real-time big volume detection + mean reversion
- **Signals**: Generated on-the-fly (no pre-calculation needed)

### Use Case
- Orange dot (big volume) detection in real-time
- Mean reversion levels ±10 pts from orange dot
- SMA filter (optional)
- Trailing stops (optional)

---

## Port Assignment Table

| Strategy | NinjaTrader File | NT Tick Port | NT Order Port | Python File |
|----------|-----------------|--------------|---------------|-------------|
| **Absorption** | AAStrategyBiderect.cs | 5553 | 5554 | tick_server_bidirect.py |
| **Trinchera** | AAStrategyTrinchera.cs | 5555 | 5556 | tick_server_trinchera_bidirect.py |

---

## Can You Run Both Simultaneously?

### ✅ YES! Here's How:

1. **NinjaTrader Setup**:
   - Chart #1: Apply `AAStrategyBiderect` (Absorption)
   - Chart #2: Apply `AAStrategyTrinchera` (Trinchera)

2. **Python Setup**:
   - Terminal #1: `python tick_server_bidirect.py` (Absorption)
   - Terminal #2: `python tick_server_trinchera_bidirect.py` (Trinchera)

3. **Result**:
   - Both strategies run independently
   - No port conflicts (different port numbers)
   - Each generates its own signals
   - Each manages its own positions

---

## Installation Steps for Trinchera

### Step 1: Copy C# File to NinjaTrader

```
1. Copy: d:\PYTHON\ALGOS\fabio_valentini\strat_trinchera\AAStrategyTrinchera.cs
2. Paste to: Documents\NinjaTrader 8\bin\Custom\Strategies\
3. Open NinjaTrader
4. Tools → Compile → Compile All (F5)
5. Check for errors in output window
6. If successful, strategy is ready to use
```

### Step 2: Apply Strategy to Chart

```
1. Open NQ chart in NinjaTrader
2. Right-click chart → Strategies
3. Click "Add..."
4. Select "AAStrategyTrinchera" from list
5. Click "OK"
6. Strategy will show "Waiting for Python connection..." in output
```

### Step 3: Start Python

```bash
cd d:\PYTHON\ALGOS\fabio_valentini\strat_trinchera
python tick_server_trinchera_bidirect.py
```

---

## Key Differences in Code

### AAStrategyBiderect.cs (Absorption)
```csharp
private const int TICK_SEND_PORT = 5553;
private const int ORDER_RECEIVE_PORT = 5554;
Description = @"Absorption Strategy - Market Profile";
Name = "AAStrategyBiderect";
```

### AAStrategyTrinchera.cs (Trinchera)
```csharp
private const int TICK_SEND_PORT = 5555;      // ← Different port
private const int ORDER_RECEIVE_PORT = 5556;  // ← Different port
Description = @"Trinchera Live Trading - Bidirectional";
Name = "AAStrategyTrinchera";                 // ← Different name
```

**Everything else is identical!** Both send the same tick data format.

---

## Python Strategy Logic Comparison

### Absorption (tick_server_bidirect.py)
- Reads pre-generated signals from CSV
- Looks for d-shape/p-shape patterns
- Entry based on pattern detection

### Trinchera (tick_server_trinchera_bidirect.py)
- Real-time big volume detection (≥200 contracts)
- Real-time SMA calculation (200-tick buffer)
- Orange dot → Mean reversion levels (±10 pts)
- Entry when price touches levels

---

## Which Strategy Should You Use?

### Use Absorption When:
- You have historical data with pre-calculated patterns
- You want to backtest Market Profile signals
- You prefer volume distribution analysis

### Use Trinchera When:
- You want real-time big volume detection
- You prefer mean reversion from volume spikes
- You want simpler, faster signal generation
- You want to use SMA filters

### Use Both When:
- You want to diversify strategies
- You want to compare live performance
- You have enough capital for multiple positions
- You want redundancy (if one fails, other continues)

---

## Configuration Files

### Absorption
```
config_absortion.py (if exists) - Historical backtest config
```

### Trinchera
```
config_trinchera.py        - Historical backtest config
config_trinchera_live.py   - Live trading config (NEW)
```

**Important**: Live config is separate to avoid accidentally using backtest parameters in real trading!

---

## Safety Checklist

Before going live with either strategy:

- [ ] Test in paper trading mode (`PAPER_TRADING_MODE = True`)
- [ ] Verify port connections working
- [ ] Check circuit breakers set correctly
- [ ] Confirm max position size appropriate
- [ ] Test manual order confirmation
- [ ] Run for several days in paper mode
- [ ] Review trade logs
- [ ] Verify P&L calculations match NinjaTrader
- [ ] Only then enable real trading

---

## Troubleshooting

### "Port already in use" Error

**Cause**: Another application using the port

**Fix**:
```bash
# Windows - Check what's using port
netstat -ano | findstr :5555
```

If another strategy is using it, close that strategy first.

### Both Strategies Connected to Same Python Script

**Cause**: Forgot to change ports in one of them

**Fix**: Verify each strategy has unique port numbers as shown in table above

---

## File Locations Summary

```
NinjaTrader Strategies:
  Documents\NinjaTrader 8\bin\Custom\Strategies\
    ├── AAStrategyBiderect.cs     (Absorption - Existing)
    └── AAStrategyTrinchera.cs    (Trinchera - NEW)

Python Files:
  d:\PYTHON\ALGOS\fabio_valentini\
    ├── strategies\strat_OM_4_absortion\
    │   └── tick_server_bidirect.py       (Absorption - Existing)
    └── strat_trinchera\
        ├── tick_server_trinchera_bidirect.py  (Trinchera - NEW)
        ├── config_trinchera_live.py           (Trinchera - NEW)
        └── AAStrategyTrinchera.cs             (Copy to NinjaTrader)
```

---

## Recommendation

**🎯 Keep both strategies separate!**

**Advantages:**
1. ✅ No conflicts - run simultaneously
2. ✅ Easy switching - just apply different strategy
3. ✅ No code modification needed
4. ✅ Safer - if one breaks, other unaffected
5. ✅ Future-proof - can add Strategy #3, #4, etc.

**The 5 minutes to copy and compile a new C# file is worth the flexibility!**

---

*Last updated: 2025-12-01*
*Version: 1.0*
