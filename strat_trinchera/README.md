# Strat Trinchera - Time & Sales Resampling

## Overview
This folder contains data processing tools for NQ futures Time & Sales data, focusing on 1-second aggregation with Market Profile analysis.

## Files

### process_trinchera.py
Main processing script that resamples tick data and generates comprehensive frame-level data.

**Execution:**
```bash
python strat_trinchera/process_trinchera.py
```

## Configuration

```python
FRAME_FREQUENCY = "1s"  # 1-second frame aggregation
PROFILE_FREQUENCY = 1   # 1-second rolling Market Profile window
TICK_SIZE = 0.25        # NQ tick size
```

## Input Data

**Source file:**
```
data/historic/time_and_sales_nq_20251022.csv
```

- **Format:** European CSV (`;` separator, `,` decimal)
- **Columns:** Timestamp, Precio, Volumen, Lado, Bid, Ask
- **Ticks:** ~622,779 ticks (full trading day)

## Output Data

### db_trinchera_all_data.csv

**Location:** `strat_trinchera/db_trinchera_all_data.csv`

**Coverage:** 82,800 frames (100% coverage of all seconds in the trading day)

**Columns:**

#### Timestamps
- `timestamp` - Frame timestamp (1-second intervals)

#### OHLC Data
- `open` - Opening price for the 1-second frame
- `high` - Highest price in the frame
- `low` - Lowest price in the frame
- `close` - Closing price for the frame
- `previous_close` - Previous frame's closing price

#### Price Changes
- `price_change` - Absolute price change from previous close (points)
- `price_change_pct` - Price change percentage
- `num_levels_moved` - Number of price levels moved (in ticks of 0.25)

#### Volume Data (Frame Aggregation)
- `total_bid` - Total BID volume executed in this 1-second frame
- `total_ask` - Total ASK volume executed in this 1-second frame
- `total_volume` - Total volume (BID + ASK) in this frame
- `bid_ask_ratio` - Ratio of BID/ASK volume in frame

#### Market Profile Volumes (Rolling Window)
- `profile_bid_volume` - Total BID volume in rolling 1-second profile
- `profile_ask_volume` - Total ASK volume in rolling 1-second profile
- `profile_total_volume` - Total volume in rolling profile
- `profile_bid_ask_ratio` - BID/ASK ratio in rolling profile

#### Market Profile Structure
- `num_price_levels` - Number of active price levels in the Market Profile
- `price_range` - Price range covered by the profile (max - min)
- `min_price` - Minimum price level in the profile
- `max_price` - Maximum price level in the profile
- `poc_price` - Point of Control (price level with most volume)
- `poc_volume` - Volume at the Point of Control

#### Other Metrics
- `tick_count` - Number of ticks in this 1-second frame

## Statistics

**From 20251022 dataset:**

- **Total frames:** 82,800 (23 hours of data)
- **Average volume per frame:** 8.26 contracts
- **Average BID/ASK ratio:** 0.81 (slightly more ASK volume)
- **Average price levels:** 3.81 levels active per frame
- **Max price range:** 27.75 points (most volatile frame)
- **Bullish frames (price_change > 0):** 21,073 (25.45%)
- **Bearish frames (price_change < 0):** 20,963 (25.32%)
- **Neutral frames (price_change = 0):** 40,764 (49.23%)

## Use Cases

### 1. Market Microstructure Analysis
- Study BID/ASK volume imbalances
- Identify periods of high/low activity
- Analyze Point of Control movements

### 2. Volume Profile Studies
- Track how many price levels are active per second
- Monitor price range expansion/contraction
- Identify volume concentration zones

### 3. Price Action Analysis
- Detect momentum shifts (num_levels_moved)
- Track OHLC patterns at 1-second granularity
- Study price change distributions

### 4. Strategy Development
- Use as input for trinchera (trench) trading strategies
- Filter high-volume vs low-volume periods
- Entry signals based on BID/ASK imbalances

## Data Quality

- **100% temporal coverage** - Every second has a frame
- **No gaps** - Continuous timestamp series
- **Dual volume metrics:**
  - Frame volumes (ticks in THIS second)
  - Profile volumes (rolling window)
- **Consistent pricing** - OHLC calculated from actual tick data

## Technical Details

### Processing Pipeline

1. **Load Time & Sales ticks** (~622k ticks)
2. **Create 1-second timestamp grid** (82,800 frames)
3. **Sequential tick processing:**
   - Update Rolling Market Profile for each tick
   - Track last known price as frame close
4. **Frame-level aggregation:**
   - Calculate OHLC from ticks in [t-1s, t]
   - Aggregate BID/ASK volumes
   - Extract Market Profile metrics
5. **Save to CSV** with European format

### Memory Usage
- **Peak:** ~300 MB during processing
- **Output file:** 12.42 MB

### Processing Time
- **~2-3 minutes** on standard hardware

## Comparison with Other Modules

| Feature | strat_trinchera | find_sweep.py | plot_resample_sweep.py |
|---------|-----------------|---------------|------------------------|
| **Window** | 1 second | 1 second | 15 seconds |
| **Output Type** | CSV only | CSV + Interactive UI | CSV + HTML chart |
| **Focus** | OHLCV + volumes | Mushroom patterns | Reset events |
| **Frames** | 82,800 | 172,783 (500ms) | Variable |
| **Use Case** | Strategy input data | Pattern research | Bounce/Bins signals |

## Future Enhancements

- [ ] Add SMA/EMA calculations
- [ ] Include VWAP per frame
- [ ] Add delta (BID - ASK) metrics
- [ ] Calculate cumulative volume delta (CVD)
- [ ] Add volatility metrics (ATR-like)
- [ ] Multi-timeframe aggregation (5s, 15s, 60s)

---

*Last updated: 2025-11-19*
*Dataset: time_and_sales_nq_20251022.csv*
