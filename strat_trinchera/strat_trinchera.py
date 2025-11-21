"""
Trinchera Mean Reversion Strategy
Trades based on price touching mean reversion levels (red/green lines)
- SELL at red line (mean_level_up) with TP=5, SL=10
- BUY at green line (mean_level_down) with TP=5, SL=10
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
from config_trinchera import MEAN_REVERS_EXPAND, TP_POINTS, SL_POINTS, FILTER_BY_SMA

# ============================================================================
# STRATEGY CONFIGURATION
# ============================================================================
CURRENT_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = CURRENT_DIR / "outputs"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
CHARTS_DIR = CURRENT_DIR / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

# Find most recent bins file
bins_files = sorted(OUTPUTS_DIR.glob("db_trinchera_bins_*.csv"))
if not bins_files:
    raise FileNotFoundError(f"No bins file found in {OUTPUTS_DIR}")
BINS_FILE = bins_files[-1]  # Get most recent

# Find most recent all_data file
all_data_files = sorted(OUTPUTS_DIR.glob("db_trinchera_all_data*.csv"))
if not all_data_files:
    raise FileNotFoundError(f"No db_trinchera_all_data file found in {OUTPUTS_DIR}")
ALL_DATA_FILE = all_data_files[-1]  # Get most recent

# Extract date from input filename (e.g., db_trinchera_all_data_20251022.csv -> 20251022)
import re
date_match = re.search(r'_(\d{8})\.csv', ALL_DATA_FILE.name)
date_str = date_match.group(1) if date_match else datetime.now().strftime("%Y%m%d")
OUTPUT_FILE = OUTPUTS_DIR / f"db_trinchera_TR_{date_str}.csv"

POINT_VALUE = 20.0  # USD value per point for NQ futures

print("="*80)
print("TRINCHERA MEAN REVERSION STRATEGY")
print("="*80)
print(f"\nConfiguration:")
print(f"  - Take Profit: {TP_POINTS} points (${TP_POINTS * POINT_VALUE:.0f})")
print(f"  - Stop Loss: {SL_POINTS} points (${SL_POINTS * POINT_VALUE:.0f})")
print(f"  - Mean Reversion Expand: {MEAN_REVERS_EXPAND} points")
print(f"  - Point Value: ${POINT_VALUE:.0f} per point")
print(f"  - SMA Filter: {'ENABLED' if FILTER_BY_SMA else 'DISABLED'}")
if FILTER_BY_SMA:
    print(f"    * Orange dot < SMA at event: ONLY SELL orders")
    print(f"    * Orange dot > SMA at event: ONLY BUY orders")

# Load big volume events (bins)
print(f"\n[INFO] Loading big volume events from: {BINS_FILE.name}")
df_bins = pd.read_csv(BINS_FILE, sep=';', decimal=',', low_memory=False)
df_bins.columns = df_bins.columns.str.strip()
df_bins['timestamp'] = pd.to_datetime(df_bins['timestamp'])
df_bins['start_timestamp'] = pd.to_datetime(df_bins['start_timestamp'])
df_bins['end_timeout_mean_reversion'] = pd.to_datetime(df_bins['end_timeout_mean_reversion'])

print(f"[OK] Loaded {len(df_bins)} big volume events")

# Load all tick data
print(f"\n[INFO] Loading price data from: {ALL_DATA_FILE.name}")
df_data = pd.read_csv(ALL_DATA_FILE, sep=';', decimal=',', low_memory=False)
df_data.columns = df_data.columns.str.strip()
df_data['timestamp'] = pd.to_datetime(df_data['timestamp'])
df_data = df_data.sort_values('timestamp')

print(f"[OK] Loaded {len(df_data):,} frames")

# ============================================================================
# STRATEGY EXECUTION
# ============================================================================
trades = []

print(f"\n[INFO] Processing mean reversion opportunities...")

for idx, event in df_bins.iterrows():
    start_ts = event['start_timestamp']
    end_ts = event['end_timeout_mean_reversion']
    mean_level_up = event['mean_level_up']
    mean_level_down = event['mean_level_down']

    # Get orange dot (close price) and SMA at big volume event timestamp
    event_close = event['close']  # Orange dot price
    event_sma = event['sma']      # SMA at big volume event

    # Get price data within the timeout window
    mask = (df_data['timestamp'] >= start_ts) & (df_data['timestamp'] <= end_ts)
    window_data = df_data[mask].copy()

    if len(window_data) == 0:
        continue

    # Check for SELL opportunity (price touches red line - mean_level_up)
    sell_touches = window_data[window_data['high'] >= mean_level_up]
    if len(sell_touches) > 0:
        entry_time = sell_touches.iloc[0]['timestamp']
        entry_price = mean_level_up
        entry_sma = sell_touches.iloc[0]['sma']

        # Check SMA filter: SELL only if orange dot was BELOW SMA at event
        filter_passed = True
        if FILTER_BY_SMA:
            filter_passed = event_close < event_sma

        # Calculate TP and SL for SELL
        tp_price = entry_price - TP_POINTS
        sl_price = entry_price + SL_POINTS

        # Find exit from entry time onwards
        exit_data = df_data[df_data['timestamp'] > entry_time].copy()

        exit_reason = None
        exit_time = None
        exit_price = None
        exit_sma = None

        for _, bar in exit_data.iterrows():
            # Check TP (price goes down to TP)
            if bar['low'] <= tp_price:
                exit_reason = 'profit'
                exit_time = bar['timestamp']
                exit_price = tp_price
                exit_sma = bar['sma']
                break
            # Check SL (price goes up to SL)
            elif bar['high'] >= sl_price:
                exit_reason = 'stop'
                exit_time = bar['timestamp']
                exit_price = sl_price
                exit_sma = bar['sma']
                break

        if exit_reason and (not FILTER_BY_SMA or filter_passed):
            pnl = entry_price - exit_price  # SELL: profit when price goes down
            pnl_usd = pnl * POINT_VALUE
            trades.append({
                'entry_time': entry_time,
                'exit_time': exit_time,
                'direction': 'SELL',
                'entry_price': entry_price,
                'exit_price': exit_price,
                'entry_sma': entry_sma,
                'exit_sma': exit_sma,
                'event_close': event_close,
                'event_sma': event_sma,
                'tp_price': tp_price,
                'sl_price': sl_price,
                'exit_reason': exit_reason,
                'pnl': pnl,
                'pnl_usd': pnl_usd,
                'filter_passed': filter_passed,
                'event_timestamp': event['timestamp']
            })

    # Check for BUY opportunity (price touches green line - mean_level_down)
    buy_touches = window_data[window_data['low'] <= mean_level_down]
    if len(buy_touches) > 0:
        entry_time = buy_touches.iloc[0]['timestamp']
        entry_price = mean_level_down
        entry_sma = buy_touches.iloc[0]['sma']

        # Check SMA filter: BUY only if orange dot was ABOVE SMA at event
        filter_passed = True
        if FILTER_BY_SMA:
            filter_passed = event_close > event_sma

        # Calculate TP and SL for BUY
        tp_price = entry_price + TP_POINTS
        sl_price = entry_price - SL_POINTS

        # Find exit from entry time onwards
        exit_data = df_data[df_data['timestamp'] > entry_time].copy()

        exit_reason = None
        exit_time = None
        exit_price = None
        exit_sma = None

        for _, bar in exit_data.iterrows():
            # Check TP (price goes up to TP)
            if bar['high'] >= tp_price:
                exit_reason = 'profit'
                exit_time = bar['timestamp']
                exit_price = tp_price
                exit_sma = bar['sma']
                break
            # Check SL (price goes down to SL)
            elif bar['low'] <= sl_price:
                exit_reason = 'stop'
                exit_time = bar['timestamp']
                exit_price = sl_price
                exit_sma = bar['sma']
                break

        if exit_reason and (not FILTER_BY_SMA or filter_passed):
            pnl = exit_price - entry_price  # BUY: profit when price goes up
            pnl_usd = pnl * POINT_VALUE
            trades.append({
                'entry_time': entry_time,
                'exit_time': exit_time,
                'direction': 'BUY',
                'entry_price': entry_price,
                'exit_price': exit_price,
                'entry_sma': entry_sma,
                'exit_sma': exit_sma,
                'event_close': event_close,
                'event_sma': event_sma,
                'tp_price': tp_price,
                'sl_price': sl_price,
                'exit_reason': exit_reason,
                'pnl': pnl,
                'pnl_usd': pnl_usd,
                'filter_passed': filter_passed,
                'event_timestamp': event['timestamp']
            })

# ============================================================================
# SAVE RESULTS
# ============================================================================
if len(trades) > 0:
    df_trades = pd.DataFrame(trades)

    # Add sequential trade ID (starting from 1)
    df_trades.insert(0, 'trade_id', range(1, len(df_trades) + 1))

    # Save to CSV
    df_trades.to_csv(OUTPUT_FILE, index=False, sep=';', decimal=',')

    print(f"\n[OK] Strategy completed: {len(trades)} trades executed")
    print(f"[OK] Trades saved to: {OUTPUT_FILE.name}")

    # Statistics
    profit_trades = df_trades[df_trades['exit_reason'] == 'profit']
    stop_trades = df_trades[df_trades['exit_reason'] == 'stop']

    total_pnl = df_trades['pnl'].sum()
    total_pnl_usd = df_trades['pnl_usd'].sum()

    print("\n" + "="*80)
    print("STRATEGY STATISTICS")
    print("="*80)
    print(f"Total trades: {len(df_trades)}")
    print(f"  - PROFIT exits: {len(profit_trades)} ({len(profit_trades)/len(df_trades)*100:.1f}%)")
    print(f"  - STOP exits: {len(stop_trades)} ({len(stop_trades)/len(df_trades)*100:.1f}%)")

    if FILTER_BY_SMA:
        filtered_trades = df_trades[df_trades['filter_passed'] == True]
        rejected_trades = df_trades[df_trades['filter_passed'] == False]
        print(f"\nSMA Filter:")
        print(f"  - Passed filter: {len(filtered_trades)} ({len(filtered_trades)/len(df_trades)*100:.1f}%)")
        print(f"  - Rejected by filter: {len(rejected_trades)} ({len(rejected_trades)/len(df_trades)*100:.1f}%)")

    print(f"\nTotal P&L: {total_pnl:.2f} points (${total_pnl_usd:,.2f})")
    print(f"Average P&L per trade: {total_pnl/len(df_trades):.2f} points (${total_pnl_usd/len(df_trades):,.2f})")

    # Breakdown by direction
    buy_trades = df_trades[df_trades['direction'] == 'BUY']
    sell_trades = df_trades[df_trades['direction'] == 'SELL']

    print(f"\nBUY trades: {len(buy_trades)}")
    if len(buy_trades) > 0:
        buy_pnl = buy_trades['pnl'].sum()
        buy_pnl_usd = buy_trades['pnl_usd'].sum()
        print(f"  - P&L: {buy_pnl:.2f} points (${buy_pnl_usd:,.2f})")
        print(f"  - Profit exits: {len(buy_trades[buy_trades['exit_reason']=='profit'])}")
        print(f"  - Stop exits: {len(buy_trades[buy_trades['exit_reason']=='stop'])}")

    print(f"\nSELL trades: {len(sell_trades)}")
    if len(sell_trades) > 0:
        sell_pnl = sell_trades['pnl'].sum()
        sell_pnl_usd = sell_trades['pnl_usd'].sum()
        print(f"  - P&L: {sell_pnl:.2f} points (${sell_pnl_usd:,.2f})")
        print(f"  - Profit exits: {len(sell_trades[sell_trades['exit_reason']=='profit'])}")
        print(f"  - Stop exits: {len(sell_trades[sell_trades['exit_reason']=='stop'])}")

else:
    print("\n[WARN] No trades executed")

print("\n" + "="*80)
print("[SUCCESS] Strategy execution completed!")
print("="*80)
