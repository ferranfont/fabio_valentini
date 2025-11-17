"""
Estrategia basada en BINS - Bounce (rebote) desde reset level
==============================================================

Lógica de bounce/rebote:
- Detecta punto naranja (reset_timestamp, reset_price)
- Durante EXTENDED_LINE_MINUTES (10 min):
  * Observa si precio se mueve MIN_BOUNCE puntos hacia arriba o abajo
  * Espera a que precio vuelva a cruzar el nivel reset_price
- Si cruza después de movimiento UP → ENTRA LONG
- Si cruza después de movimiento DOWN → ENTRA SHORT
- Si no cruza en tiempo límite → cancela señal

Entry timing: cuando precio cruza reset_price viniendo del rebote
TP/SL se evalúan tick-by-tick con datos del T&S.
"""

import os
import sys
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from datetime import timedelta

import numpy as np
import pandas as pd

# ========= PARÁMETROS DE BOUNCE (ARRIBA, DESPUÉS DE LIBRERÍAS) =========
EXTENDED_LINE_MINUTES = 5  # Tiempo límite para observar bounce y cruce
MIN_BOUNCE = 5  # Mínimo movimiento en puntos para considerar bounce válido

# ========= RUTAS DEL PROYECTO =========
THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
STRAT_SWEEP_DIR = PROJECT_ROOT / "strat_sweep"

TNS_FILE = DATA_DIR / "historic" / "time_and_sales_nq_20251022.csv"
BINS_FILE = STRAT_SWEEP_DIR / "db_mushroom_bins.csv"
OUTPUT_FILE = OUTPUTS_DIR / "sweep" / "bounce_TR_20251022.csv"

# ========= PARÁMETROS =========
SYMBOL = "NQ"
TP_POINTS = 12.0
SL_POINTS = 10.0
POINT_VALUE = 20.0
CONTRACTS = 1
NUM_MAX_OPEN_CONTRACTS = 20
BREAK_EVEN_POINTS = 10.0

# ========= HELPERS =========
def _read_csv_semicolon_decimal(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep=";", decimal=",", dtype=str, keep_default_na=False, engine="python")

def _to_float(s: pd.Series) -> pd.Series:
    return (
        s.astype(str)
         .str.replace(".", "", regex=False)       # miles europeo
         .str.replace(",", ".", regex=False)      # coma -> punto
         .replace({"": None})
         .astype(float)
    )

@dataclass
class OpenPosition:
    """Represents an open position."""
    side: str  # "LONG" or "SHORT"
    entry_time: pd.Timestamp
    entry_price: float
    entry_signal: str
    tp_price: float
    sl_price: float
    break_even_active: bool = False
    signal_data: dict = None
    bin_number: int = None

@dataclass
class PendingBounceSignal:
    """Represents a bounce signal waiting for confirmation."""
    reset_timestamp: pd.Timestamp
    reset_price: float
    expiry_time: pd.Timestamp  # reset_timestamp + EXTENDED_LINE_MINUTES
    max_price_up: float  # Máximo precio alcanzado hacia arriba
    max_price_down: float  # Mínimo precio alcanzado hacia abajo
    bounce_tag: Optional[str] = None  # 'up' o 'down' cuando se confirma bounce
    signal_data: dict = None
    signal_idx: int = None

# ========= BACKTEST =========
def run_backtest_bounce(
    df_bins: pd.DataFrame,
    df_base: pd.DataFrame,
    extended_line_minutes: int = EXTENDED_LINE_MINUTES,
    min_bounce: float = MIN_BOUNCE
) -> pd.DataFrame:
    """
    Backtest basado en bounce/rebote desde reset level:
    1. Detecta reset (punto naranja)
    2. Durante extended_line_minutes, observa si precio se mueve min_bounce pts
    3. Espera a que precio cruce reset_price viniendo del rebote
    4. Si cruza después de bounce UP → LONG
    5. Si cruza después de bounce DOWN → SHORT

    df_bins: columnas ['reset_timestamp','reset_price', etc.]
    df_base: columnas ['timestamp','price'] (derivado de T&S)
    extended_line_minutes: Tiempo límite de observación (default: EXTENDED_LINE_MINUTES)
    min_bounce: Mínimo movimiento en puntos (default: MIN_BOUNCE)
    """
    # Preparar datos de bins (señales) - ORDENAR POR RESET_TIMESTAMP
    bins = df_bins.copy().sort_values("reset_timestamp").drop_duplicates("reset_timestamp", keep="first").reset_index(drop=True)
    bins['signal_idx'] = range(len(bins))

    print(f"  [INFO] Removed {len(df_bins) - len(bins)} duplicate reset timestamps")
    print(f"  [INFO] Using {len(bins)} unique reset signals for backtest")

    base = df_base.copy().sort_values("timestamp").reset_index(drop=True)

    signals_list = bins.to_dict("records")
    total_signals = len(signals_list)
    next_signal_idx = 0

    trades = []
    open_positions: list[OpenPosition] = []
    pending_bounce_signals: list[PendingBounceSignal] = []

    print(f"\n  Processing {len(base):,} ticks with {len(bins):,} bin signals...")
    print(f"  Bounce parameters: MIN_BOUNCE={min_bounce}pts, EXTENDED_LINE_MINUTES={extended_line_minutes}min")

    for i, row in base.iterrows():
        if i % 50000 == 0:
            print(f"    Tick {i:,}/{len(base):,} | Open positions: {len(open_positions)} | Pending bounces: {len(pending_bounce_signals)} | Completed trades: {len(trades)}")

        current_time = row['timestamp']
        current_price = row['price']

        # 1. Check for exits on open positions
        positions_to_close = []
        for pos in open_positions:
            exit_reason = None
            exit_price = None

            # Break-even logic
            if (
                not pos.break_even_active
                and BREAK_EVEN_POINTS is not None
                and BREAK_EVEN_POINTS > 0
            ):
                if pos.side == "LONG" and current_price >= pos.entry_price + BREAK_EVEN_POINTS:
                    pos.sl_price = pos.entry_price
                    pos.break_even_active = True
                elif pos.side == "SHORT" and current_price <= pos.entry_price - BREAK_EVEN_POINTS:
                    pos.sl_price = pos.entry_price
                    pos.break_even_active = True

            # Check TP/SL
            if pos.side == "LONG":
                if current_price >= pos.tp_price:
                    exit_reason = "TARGET"
                    exit_price = pos.tp_price
                elif current_price <= pos.sl_price:
                    exit_reason = "STOP"
                    exit_price = pos.sl_price

            elif pos.side == "SHORT":
                if current_price <= pos.tp_price:
                    exit_reason = "TARGET"
                    exit_price = pos.tp_price
                elif current_price >= pos.sl_price:
                    exit_reason = "STOP"
                    exit_price = pos.sl_price

            if exit_reason:
                # Close position
                if pos.side == "LONG":
                    profit_points = exit_price - pos.entry_price
                else:  # SHORT
                    profit_points = pos.entry_price - exit_price

                trade_record = {
                    "entry_time": pos.entry_time,
                    "entry_price": pos.entry_price,
                    "exit_time": current_time,
                    "exit_price": float(exit_price),
                    "side": pos.side,
                    "entry_signal": pos.entry_signal,
                    "tp_price": float(pos.tp_price),
                    "sl_price": float(pos.sl_price),
                    "exit_reason": exit_reason,
                    "profit_points": round(float(profit_points), 2),
                    "profit_dollars": round(float(profit_points * POINT_VALUE * CONTRACTS), 2),
                    "contracts": CONTRACTS,
                    "bin_number": pos.bin_number
                }

                # Add bin signal data
                if pos.signal_data:
                    for key, value in pos.signal_data.items():
                        if key not in ['reset_timestamp', 'signal_idx']:
                            trade_record[f"bin_{key}"] = value

                trades.append(trade_record)
                positions_to_close.append(pos)

        # Remove closed positions
        for pos in positions_to_close:
            open_positions.remove(pos)

        # 2. Update pending bounce signals
        expired_signals = []
        for bounce_signal in pending_bounce_signals:
            # Update max prices
            if current_price > bounce_signal.max_price_up:
                bounce_signal.max_price_up = current_price
            if current_price < bounce_signal.max_price_down:
                bounce_signal.max_price_down = current_price

            # Check if bounce condition met (moved min_bounce away from reset_price)
            if bounce_signal.bounce_tag is None:
                movement_up = bounce_signal.max_price_up - bounce_signal.reset_price
                movement_down = bounce_signal.reset_price - bounce_signal.max_price_down

                if movement_up >= min_bounce:
                    bounce_signal.bounce_tag = 'up'
                    # print(f"    [BOUNCE UP] Reset: {bounce_signal.reset_price:.2f} -> Max: {bounce_signal.max_price_up:.2f} (+{movement_up:.2f}pts)")
                elif movement_down >= min_bounce:
                    bounce_signal.bounce_tag = 'down'
                    # print(f"    [BOUNCE DOWN] Reset: {bounce_signal.reset_price:.2f} -> Min: {bounce_signal.max_price_down:.2f} (-{movement_down:.2f}pts)")

            # Check if price crosses reset_price after bounce
            if bounce_signal.bounce_tag is not None:
                crossed = False
                side = None

                if bounce_signal.bounce_tag == 'up':
                    # Bounce UP confirmed, waiting for price to cross reset_price downward (buy on support)
                    if current_price <= bounce_signal.reset_price:
                        crossed = True
                        side = "LONG"
                elif bounce_signal.bounce_tag == 'down':
                    # Bounce DOWN confirmed, waiting for price to cross reset_price upward (sell on resistance)
                    if current_price >= bounce_signal.reset_price:
                        crossed = True
                        side = "SHORT"

                if crossed and len(open_positions) < NUM_MAX_OPEN_CONTRACTS:
                    # ENTRY: Price crossed reset_price after bounce
                    entry_price = current_price
                    tp_price = entry_price + TP_POINTS if side == "LONG" else entry_price - TP_POINTS
                    sl_price = entry_price - SL_POINTS if side == "LONG" else entry_price + SL_POINTS

                    cum_vol = float(bounce_signal.signal_data.get('cumulative_volume_before_reset', 0))

                    open_positions.append(
                        OpenPosition(
                            side=side,
                            entry_time=current_time,
                            entry_price=entry_price,
                            entry_signal=f"bounce_{bounce_signal.bounce_tag}",
                            tp_price=tp_price,
                            sl_price=sl_price,
                            signal_data=bounce_signal.signal_data,
                            bin_number=int(cum_vol),
                        )
                    )

                    # Remove this signal (entry executed)
                    expired_signals.append(bounce_signal)

            # Check if signal expired (timeout)
            if current_time >= bounce_signal.expiry_time:
                expired_signals.append(bounce_signal)

        # Remove expired/executed signals
        for sig in expired_signals:
            pending_bounce_signals.remove(sig)

        # 3. Check for new bin RESET signals (reset_timestamp reached)
        while (
            next_signal_idx < total_signals
            and signals_list[next_signal_idx]["reset_timestamp"] <= current_time
        ):
            signal_data = signals_list[next_signal_idx]
            next_signal_idx += 1

            reset_ts = signal_data['reset_timestamp']
            reset_price = float(signal_data['reset_price'])
            expiry_time = reset_ts + timedelta(minutes=extended_line_minutes)

            # Create new pending bounce signal
            pending_bounce_signals.append(
                PendingBounceSignal(
                    reset_timestamp=reset_ts,
                    reset_price=reset_price,
                    expiry_time=expiry_time,
                    max_price_up=reset_price,  # Initialize to reset_price
                    max_price_down=reset_price,
                    signal_data=signal_data,
                    signal_idx=signal_data.get('signal_idx')
                )
            )

    # 4. Close remaining positions at EOD
    if open_positions:
        last_time = base.iloc[-1]['timestamp']
        last_price = base.iloc[-1]['price']

        for pos in open_positions:
            if pos.side == "LONG":
                profit_points = last_price - pos.entry_price
            else:
                profit_points = pos.entry_price - last_price

            trade_record = {
                "entry_time": pos.entry_time,
                "entry_price": pos.entry_price,
                "exit_time": last_time,
                "exit_price": float(last_price),
                "side": pos.side,
                "entry_signal": pos.entry_signal,
                "tp_price": float(pos.tp_price),
                "sl_price": float(pos.sl_price),
                "exit_reason": "END_OF_DATA",
                "profit_points": round(float(profit_points), 2),
                "profit_dollars": round(float(profit_points * POINT_VALUE * CONTRACTS), 2),
                "contracts": CONTRACTS,
                "bin_number": pos.bin_number
            }

            if pos.signal_data:
                for key, value in pos.signal_data.items():
                    if key not in ['reset_timestamp', 'signal_idx']:
                        trade_record[f"bin_{key}"] = value

            trades.append(trade_record)

    print(f"\n  Backtest completed: {len(trades)} trades generated")
    print(f"  Pending bounces not executed: {len(pending_bounce_signals)}")

    return pd.DataFrame(trades)


def main() -> pd.DataFrame:
    """Ejecuta el backtest con bounce logic."""
    print("=" * 80)
    print("BACKTEST - BIN BOUNCE STRATEGY (RESET LEVEL BOUNCE)")
    print("=" * 80)
    print(f"\n[INFO] Loading bin reset signals from: {BINS_FILE}")
    print(f"[INFO] Loading T&S data from: {TNS_FILE}")

    # Load bins (signals) - CSV STRUCTURE
    df_bins_raw = _read_csv_semicolon_decimal(BINS_FILE)
    df_bins = pd.DataFrame({
        # Reset data
        'reset_timestamp': pd.to_datetime(df_bins_raw['reset_timestamp'], errors='coerce'),
        'reset_price': _to_float(df_bins_raw['reset_price']),
        'cumulative_volume_before_reset': _to_float(df_bins_raw['cumulative_volume_before_reset']),

        # Volume data at reset moment
        'total_bid': _to_float(df_bins_raw['total_bid']),
        'total_ask': _to_float(df_bins_raw['total_ask']),
        'total_bid_ask': _to_float(df_bins_raw['total_bid_ask']),
        'total_volume': _to_float(df_bins_raw['total_volume']),

        # SMA and price direction
        'sma': _to_float(df_bins_raw['sma']),
        'price_tag': df_bins_raw['price_tag'].str.strip().str.lower()
    })

    print(f"[OK] Loaded {len(df_bins)} bin reset signals")
    print(f"\n[INFO] BOUNCE ENTRY LOGIC:")
    print(f"     - Entry Trigger: Price crosses reset_price after bouncing MIN_BOUNCE={MIN_BOUNCE}pts")
    print(f"     - Observation Window: {EXTENDED_LINE_MINUTES} minutes from reset_timestamp")
    print(f"     - Bounce UP (price moved up {MIN_BOUNCE}+ pts) -> crosses reset_price -> LONG")
    print(f"     - Bounce DOWN (price moved down {MIN_BOUNCE}+ pts) -> crosses reset_price -> SHORT")
    print(f"     - Exit: TP={TP_POINTS}pts / SL={SL_POINTS}pts")
    print(f"\n[INFO] Orange dots represent reset points with {EXTENDED_LINE_MINUTES}min observation lines")

    # Load T&S base data
    df_tns_raw = _read_csv_semicolon_decimal(TNS_FILE)
    df_base = pd.DataFrame({
        'timestamp': pd.to_datetime(df_tns_raw['Timestamp'], errors='coerce'),
        'price': _to_float(df_tns_raw['Precio'])
    }).dropna()

    print(f"[OK] Loaded {len(df_base):,} ticks from T&S")

    # Run backtest
    print(f"\n[INFO] Starting backtest...")
    print(f"  TP: {TP_POINTS} points | SL: {SL_POINTS} points")
    print(f"  Max positions: {NUM_MAX_OPEN_CONTRACTS} | Break-even: {BREAK_EVEN_POINTS} points")

    df_trades = run_backtest_bounce(
        df_bins,
        df_base,
        extended_line_minutes=EXTENDED_LINE_MINUTES,
        min_bounce=MIN_BOUNCE
    )

    # Save results
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df_trades.to_csv(OUTPUT_FILE, sep=';', decimal=',', index=False)

    print(f"\n[OK] Results saved to: {OUTPUT_FILE}")
    print(f"[OK] Total trades: {len(df_trades)}")

    if len(df_trades) > 0:
        wins = (df_trades['exit_reason'] == 'TARGET').sum()
        losses = (df_trades['exit_reason'] == 'STOP').sum()
        total_pnl = df_trades['profit_dollars'].sum()

        # Breakdown by bounce type
        bounce_up = (df_trades['entry_signal'] == 'bounce_up').sum()
        bounce_down = (df_trades['entry_signal'] == 'bounce_down').sum()

        print(f"\n[INFO] Quick Stats:")
        print(f"  - Wins: {wins} ({wins/len(df_trades)*100:.1f}%)")
        print(f"  - Losses: {losses} ({losses/len(df_trades)*100:.1f}%)")
        print(f"  - Total P&L: ${total_pnl:,.2f}")
        print(f"\n[INFO] Entry breakdown:")
        print(f"  - Bounce UP -> LONG: {bounce_up} trades")
        print(f"  - Bounce DOWN -> SHORT: {bounce_down} trades")

    return df_trades


if __name__ == "__main__":
    main()
