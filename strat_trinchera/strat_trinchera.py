"""
Trinchera Mean Reversion Strategy
Trades based on price touching mean reversion levels (red/green lines)
- SELL at red line (mean_level_up) with TP=5, SL=10
- BUY at green line (mean_level_down) with TP=5, SL=10
"""

import pandas as pd
from pathlib import Path
from datetime import datetime, time
from config_trinchera import MEAN_REVERS_EXPAND, TP_POINTS, SL_POINTS, FILTER_BY_SMA, FILTER_TIME_OF_DAY, START_TRADING_TIME, END_TRADING_TIME, FILTER_USE_GRID, GRID_MEAN_REVERS_EXPAND, GRID_TP_POINTS, GRID_SL_POINTS, SMA_TRAILING_STOP, TRAILING_STOP_ATR_MULT

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

# Parse trading time range
if FILTER_TIME_OF_DAY:
    start_time = datetime.strptime(START_TRADING_TIME, "%H:%M:%S").time()
    end_time = datetime.strptime(END_TRADING_TIME, "%H:%M:%S").time()

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
    if SMA_TRAILING_STOP:
        print(f"    * SMA Trailing Stop: ENABLED (follows SMA)")
    else:
        print(f"    * SMA Trailing Stop: DISABLED")
print(f"  - Time Filter: {'ENABLED' if FILTER_TIME_OF_DAY else 'DISABLED'}")
if FILTER_TIME_OF_DAY:
    print(f"    * Trading hours: {START_TRADING_TIME} to {END_TRADING_TIME}")
print(f"  - GRID System: {'ENABLED' if FILTER_USE_GRID else 'DISABLED'}")
if FILTER_USE_GRID:
    print(f"    * Second entry distance: {GRID_MEAN_REVERS_EXPAND} points")
    print(f"    * GRID TP: {GRID_TP_POINTS} points (${GRID_TP_POINTS * POINT_VALUE:.0f}) from average entry")
    print(f"    * GRID SL: {GRID_SL_POINTS} points (${GRID_SL_POINTS * POINT_VALUE:.0f}) beyond second entry")
    print(f"    * TP from average, SL from second entry + {GRID_SL_POINTS} pts")

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
    # If FILTER_USE_GRID, first entry at MEAN_REVERS_EXPAND, second at MEAN_REVERS_EXPAND + GRID_MEAN_REVERS_EXPAND
    if FILTER_USE_GRID:
        first_entry_level = event_close + MEAN_REVERS_EXPAND
        second_entry_level = event_close + MEAN_REVERS_EXPAND + GRID_MEAN_REVERS_EXPAND
    else:
        first_entry_level = mean_level_up
        second_entry_level = None

    sell_touches = window_data[window_data['high'] >= first_entry_level]
    if len(sell_touches) > 0:
        entry_time = sell_touches.iloc[0]['timestamp']
        entry_price = first_entry_level
        entry_sma = sell_touches.iloc[0]['sma']

        # Check filters (both are independent)
        sma_filter_passed = True
        time_filter_passed = True

        # SMA filter: SELL only if orange dot was BELOW SMA at event
        if FILTER_BY_SMA:
            sma_filter_passed = event_close < event_sma

        # Time filter: Check if entry time is within trading hours
        if FILTER_TIME_OF_DAY:
            entry_time_only = entry_time.time()
            time_filter_passed = start_time <= entry_time_only <= end_time

        # Both filters must pass (if enabled)
        filter_passed = sma_filter_passed and time_filter_passed

        # GRID: Look for second entry OR TP from first entry (whichever comes first)
        second_entry_time = None
        second_entry_price = None
        has_second_entry = False
        early_tp_exit = False

        # Calculate TP from first entry
        first_entry_tp = entry_price - TP_POINTS  # SELL: TP is below entry
        first_entry_sl = entry_price + SL_POINTS  # SELL: SL is above entry

        if FILTER_USE_GRID and second_entry_level is not None:
            # Search for second entry OR TP from first entry (whichever comes first)
            # BUT: Skip TP check if trailing stop is enabled (let profits run)
            trailing_enabled = FILTER_BY_SMA and SMA_TRAILING_STOP
            second_entry_data = df_data[(df_data['timestamp'] > entry_time) & (df_data['timestamp'] <= end_ts)].copy()

            for _, bar in second_entry_data.iterrows():
                # Check if first entry TP is reached BEFORE second entry (only if NO trailing stop)
                if not trailing_enabled and bar['low'] <= first_entry_tp:
                    # TP from first entry reached before second entry
                    early_tp_exit = True
                    exit_reason = 'profit'
                    exit_time = bar['timestamp']
                    exit_price = first_entry_tp
                    exit_sma = bar['sma']
                    avg_entry_price = entry_price
                    tp_price = first_entry_tp
                    sl_price = first_entry_sl
                    break
                # Check if first entry SL is reached BEFORE second entry
                elif bar['high'] >= first_entry_sl:
                    # SL from first entry reached before second entry
                    early_tp_exit = True  # Use same flag to skip further processing
                    exit_reason = 'stop'
                    exit_time = bar['timestamp']
                    exit_price = first_entry_sl
                    exit_sma = bar['sma']
                    avg_entry_price = entry_price
                    tp_price = first_entry_tp
                    sl_price = first_entry_sl
                    break
                # Check if second entry is triggered
                elif bar['high'] >= second_entry_level:
                    second_entry_time = bar['timestamp']
                    second_entry_price = second_entry_level
                    has_second_entry = True
                    # Calculate average entry price for TP/SL
                    avg_entry_price = (entry_price + second_entry_price) / 2
                    break

            # If no early exit and no second entry, use first entry price
            if not early_tp_exit and not has_second_entry:
                avg_entry_price = entry_price
        else:
            avg_entry_price = entry_price

        # Calculate TP and SL for SELL (only if not early exit)
        if not early_tp_exit:
            if FILTER_USE_GRID and has_second_entry:
                tp_price = avg_entry_price - GRID_TP_POINTS
                sl_price = event_close + MEAN_REVERS_EXPAND + GRID_MEAN_REVERS_EXPAND + GRID_SL_POINTS
            else:
                tp_price = avg_entry_price - TP_POINTS
                sl_price = avg_entry_price + SL_POINTS

            # Find exit from entry time (or second entry if exists) onwards
            exit_search_start = second_entry_time if has_second_entry else entry_time
            exit_data = df_data[df_data['timestamp'] > exit_search_start].copy()

            exit_reason = None
            exit_time = None
            exit_price = None
            exit_sma = None

            # Trailing stop tracking (only for SELL when FILTER_BY_SMA and SMA_TRAILING_STOP are both True)
            trailing_enabled = FILTER_BY_SMA and SMA_TRAILING_STOP
            trailing_distance = TRAILING_STOP_ATR_MULT  # Distance in points from SMA
            initial_sl = sl_price  # Store initial stop loss
            trailing_has_moved = False  # Track if trailing stop actually moved

            for _, bar in exit_data.iterrows():
                # Update trailing stop if enabled (SELL: SL moves DOWN following SMA + distance, never UP)
                if trailing_enabled:
                    current_sma = bar['sma']
                    # For SHORT: SL is above SMA by trailing_distance
                    new_sl = current_sma + trailing_distance
                    # Only move SL down (never up for SHORT)
                    if new_sl < sl_price:
                        sl_price = new_sl
                        trailing_has_moved = True  # Mark that trailing has taken over

                # Check TP (only if trailing stop is NOT active - let profits run with trailing stop)
                if not trailing_enabled and bar['low'] <= tp_price:
                    exit_reason = 'profit'
                    exit_time = bar['timestamp']
                    exit_price = tp_price
                    exit_sma = bar['sma']
                    break
                # Check SL (price goes up to SL)
                elif bar['high'] >= sl_price:
                    # Only mark as trailing_stop if trailing actually moved, otherwise it's initial stop
                    exit_reason = 'trailing_stop' if (trailing_enabled and trailing_has_moved) else 'stop'
                    exit_time = bar['timestamp']
                    exit_price = sl_price
                    exit_sma = bar['sma']
                    break

        if exit_reason and filter_passed:
            pnl = avg_entry_price - exit_price  # SELL: profit when price goes down
            pnl_usd = pnl * POINT_VALUE
            trades.append({
                'entry_time': entry_time,
                'entry_time_2': second_entry_time if has_second_entry else None,
                'exit_time': exit_time,
                'direction': 'SELL',
                'entry_price': entry_price,
                'entry_price_2': second_entry_price if has_second_entry else None,
                'avg_entry_price': avg_entry_price,
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
                'event_timestamp': event['timestamp'],
                'has_grid_entry': has_second_entry
            })

    # Check for BUY opportunity (price touches green line - mean_level_down)
    # If FILTER_USE_GRID, first entry at MEAN_REVERS_EXPAND, second at MEAN_REVERS_EXPAND + GRID_MEAN_REVERS_EXPAND
    if FILTER_USE_GRID:
        first_entry_level = event_close - MEAN_REVERS_EXPAND
        second_entry_level = event_close - MEAN_REVERS_EXPAND - GRID_MEAN_REVERS_EXPAND
    else:
        first_entry_level = mean_level_down
        second_entry_level = None

    buy_touches = window_data[window_data['low'] <= first_entry_level]
    if len(buy_touches) > 0:
        entry_time = buy_touches.iloc[0]['timestamp']
        entry_price = first_entry_level
        entry_sma = buy_touches.iloc[0]['sma']

        # Check filters (both are independent)
        sma_filter_passed = True
        time_filter_passed = True

        # SMA filter: BUY only if orange dot was ABOVE SMA at event
        if FILTER_BY_SMA:
            sma_filter_passed = event_close > event_sma

        # Time filter: Check if entry time is within trading hours
        if FILTER_TIME_OF_DAY:
            entry_time_only = entry_time.time()
            time_filter_passed = start_time <= entry_time_only <= end_time

        # Both filters must pass (if enabled)
        filter_passed = sma_filter_passed and time_filter_passed

        # GRID: Look for second entry OR TP from first entry (whichever comes first)
        second_entry_time = None
        second_entry_price = None
        has_second_entry = False
        early_tp_exit = False

        # Calculate TP from first entry
        first_entry_tp = entry_price + TP_POINTS  # BUY: TP is above entry
        first_entry_sl = entry_price - SL_POINTS  # BUY: SL is below entry

        if FILTER_USE_GRID and second_entry_level is not None:
            # Search for second entry OR TP from first entry (whichever comes first)
            # BUT: Skip TP check if trailing stop is enabled (let profits run)
            trailing_enabled = FILTER_BY_SMA and SMA_TRAILING_STOP
            second_entry_data = df_data[(df_data['timestamp'] > entry_time) & (df_data['timestamp'] <= end_ts)].copy()

            for _, bar in second_entry_data.iterrows():
                # Check if first entry TP is reached BEFORE second entry (only if NO trailing stop)
                if not trailing_enabled and bar['high'] >= first_entry_tp:
                    # TP from first entry reached before second entry
                    early_tp_exit = True
                    exit_reason = 'profit'
                    exit_time = bar['timestamp']
                    exit_price = first_entry_tp
                    exit_sma = bar['sma']
                    avg_entry_price = entry_price
                    tp_price = first_entry_tp
                    sl_price = first_entry_sl
                    break
                # Check if first entry SL is reached BEFORE second entry
                elif bar['low'] <= first_entry_sl:
                    # SL from first entry reached before second entry
                    early_tp_exit = True  # Use same flag to skip further processing
                    exit_reason = 'stop'
                    exit_time = bar['timestamp']
                    exit_price = first_entry_sl
                    exit_sma = bar['sma']
                    avg_entry_price = entry_price
                    tp_price = first_entry_tp
                    sl_price = first_entry_sl
                    break
                # Check if second entry is triggered
                elif bar['low'] <= second_entry_level:
                    second_entry_time = bar['timestamp']
                    second_entry_price = second_entry_level
                    has_second_entry = True
                    # Calculate average entry price for TP/SL
                    avg_entry_price = (entry_price + second_entry_price) / 2
                    break

            # If no early exit and no second entry, use first entry price
            if not early_tp_exit and not has_second_entry:
                avg_entry_price = entry_price
        else:
            avg_entry_price = entry_price

        # Calculate TP and SL for BUY (only if not early exit)
        if not early_tp_exit:
            if FILTER_USE_GRID and has_second_entry:
                tp_price = avg_entry_price + GRID_TP_POINTS
                sl_price = event_close - MEAN_REVERS_EXPAND - GRID_MEAN_REVERS_EXPAND - GRID_SL_POINTS
            else:
                tp_price = avg_entry_price + TP_POINTS
                sl_price = avg_entry_price - SL_POINTS

            # Find exit from entry time (or second entry if exists) onwards
            exit_search_start = second_entry_time if has_second_entry else entry_time
            exit_data = df_data[df_data['timestamp'] > exit_search_start].copy()

            exit_reason = None
            exit_time = None
            exit_price = None
            exit_sma = None

            # Trailing stop tracking (only for BUY when FILTER_BY_SMA and SMA_TRAILING_STOP are both True)
            trailing_enabled = FILTER_BY_SMA and SMA_TRAILING_STOP
            trailing_distance = TRAILING_STOP_ATR_MULT  # Distance in points from SMA
            initial_sl = sl_price  # Store initial stop loss
            trailing_has_moved = False  # Track if trailing stop actually moved

            for _, bar in exit_data.iterrows():
                # Update trailing stop if enabled (BUY: SL moves UP following SMA - distance, never DOWN)
                if trailing_enabled:
                    current_sma = bar['sma']
                    # For LONG: SL is below SMA by trailing_distance
                    new_sl = current_sma - trailing_distance
                    # Only move SL up (never down for LONG)
                    if new_sl > sl_price:
                        sl_price = new_sl
                        trailing_has_moved = True  # Mark that trailing has taken over

                # Check TP (only if trailing stop is NOT active - let profits run with trailing stop)
                if not trailing_enabled and bar['high'] >= tp_price:
                    exit_reason = 'profit'
                    exit_time = bar['timestamp']
                    exit_price = tp_price
                    exit_sma = bar['sma']
                    break
                # Check SL (price goes down to SL)
                elif bar['low'] <= sl_price:
                    # Only mark as trailing_stop if trailing actually moved, otherwise it's initial stop
                    exit_reason = 'trailing_stop' if (trailing_enabled and trailing_has_moved) else 'stop'
                    exit_time = bar['timestamp']
                    exit_price = sl_price
                    exit_sma = bar['sma']
                    break

        if exit_reason and filter_passed:
            pnl = exit_price - avg_entry_price  # BUY: profit when price goes up
            pnl_usd = pnl * POINT_VALUE
            trades.append({
                'entry_time': entry_time,
                'entry_time_2': second_entry_time if has_second_entry else None,
                'exit_time': exit_time,
                'direction': 'BUY',
                'entry_price': entry_price,
                'entry_price_2': second_entry_price if has_second_entry else None,
                'avg_entry_price': avg_entry_price,
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
                'event_timestamp': event['timestamp'],
                'has_grid_entry': has_second_entry
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
    trailing_stop_trades = df_trades[df_trades['exit_reason'] == 'trailing_stop']

    total_pnl = df_trades['pnl'].sum()
    total_pnl_usd = df_trades['pnl_usd'].sum()

    print("\n" + "="*80)
    print("STRATEGY STATISTICS")
    print("="*80)
    print(f"Total trades: {len(df_trades)}")
    print(f"  - PROFIT exits: {len(profit_trades)} ({len(profit_trades)/len(df_trades)*100:.1f}%)")
    print(f"  - STOP exits: {len(stop_trades)} ({len(stop_trades)/len(df_trades)*100:.1f}%)")
    if len(trailing_stop_trades) > 0:
        print(f"  - TRAILING STOP exits: {len(trailing_stop_trades)} ({len(trailing_stop_trades)/len(df_trades)*100:.1f}%)")

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
        if len(buy_trades[buy_trades['exit_reason']=='trailing_stop']) > 0:
            print(f"  - Trailing stop exits: {len(buy_trades[buy_trades['exit_reason']=='trailing_stop'])}")

    print(f"\nSELL trades: {len(sell_trades)}")
    if len(sell_trades) > 0:
        sell_pnl = sell_trades['pnl'].sum()
        sell_pnl_usd = sell_trades['pnl_usd'].sum()
        print(f"  - P&L: {sell_pnl:.2f} points (${sell_pnl_usd:,.2f})")
        print(f"  - Profit exits: {len(sell_trades[sell_trades['exit_reason']=='profit'])}")
        print(f"  - Stop exits: {len(sell_trades[sell_trades['exit_reason']=='stop'])}")
        if len(sell_trades[sell_trades['exit_reason']=='trailing_stop']) > 0:
            print(f"  - Trailing stop exits: {len(sell_trades[sell_trades['exit_reason']=='trailing_stop'])}")

else:
    print("\n[WARN] No trades executed")

print("\n" + "="*80)
print("[SUCCESS] Strategy execution completed!")
print("="*80)
