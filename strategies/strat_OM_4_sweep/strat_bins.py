"""
Estrategia basada en BINS - Inversión de señales de frecuencia
================================================================

Lógica de inversión contraria:
- Si price_tag == 'up' en el bin → ENTRA SHORT (venta) al final del bin
- Si price_tag == 'down' en el bin → ENTRA LONG (compra) al final del bin

El precio de entrada es el close_price_end del bin.
TP/SL se evalúan tick-by-tick con datos del T&S.
"""

import os
import sys
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

import numpy as np
import pandas as pd

# ========= RUTAS DEL PROYECTO =========
THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
STRAT_SWEEP_DIR = PROJECT_ROOT / "strat_sweep"

TNS_FILE = DATA_DIR / "historic" / "time_and_sales_nq_20251022.csv"
BINS_FILE = STRAT_SWEEP_DIR / "db_mushroom_bins.csv"
OUTPUT_FILE = OUTPUTS_DIR / "sweep" / "bins_TR_20251022.csv"

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
class PendingOrder:
    """Represents a limit order waiting to be triggered."""
    side: str
    signal_tag: str
    signal_time: pd.Timestamp
    signal_price: float
    entry_price: float
    signal_data: dict = None
    force_fill: bool = True  # Force entry on next tick (MARKET ORDER)
    bin_number: int = None

# ========= BACKTEST =========
def run_backtest_bins(df_bins: pd.DataFrame, df_base: pd.DataFrame) -> pd.DataFrame:
    """
    Backtest basado en bins con lógica inversa (RESET ENTRY):
    - price_tag='up' → SHORT (contrarian: price above SMA, expect reversal down)
    - price_tag='down' → LONG (contrarian: price below SMA, expect reversal up)

    NUEVA LÓGICA CON RESET:
    - Entra en el RESET (reset_timestamp, reset_price)
    - Cada reset representa fin de acumulación de volumen
    - Entry basado en price_tag (contrarian logic)

    df_bins: columnas ['reset_timestamp','reset_price','price_tag', etc.]
    df_base: columnas ['timestamp','price'] (derivado de T&S)
    """
    # Preparar datos de bins (señales) - ORDENAR POR RESET_TIMESTAMP
    # ELIMINAR DUPLICADOS: Solo tomar la primera señal por cada reset_timestamp único
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
    pending_orders: list[PendingOrder] = []
    entered_bin_timestamps = set()  # Track entered bin timestamps (prevent duplicate entries for same peak_timestamp)

    def attempt_fill_pending_orders(current_time: pd.Timestamp, current_price: float) -> None:
        """Convert pending orders into open positions (MARKET ORDER - force fill)."""
        remaining_orders: list[PendingOrder] = []
        for order in pending_orders:
            # Enforce capacity
            if len(open_positions) >= NUM_MAX_OPEN_CONTRACTS:
                remaining_orders.append(order)
                continue

            # MARKET ORDER: fill immediately at entry_price
            entry_price = order.entry_price
            tp_price = entry_price + TP_POINTS if order.side == "LONG" else entry_price - TP_POINTS
            sl_price = entry_price - SL_POINTS if order.side == "LONG" else entry_price + SL_POINTS

            open_positions.append(
                OpenPosition(
                    side=order.side,
                    entry_time=current_time,
                    entry_price=entry_price,
                    entry_signal=order.signal_tag,
                    tp_price=tp_price,
                    sl_price=sl_price,
                    signal_data=order.signal_data,
                    bin_number=order.bin_number,
                )
            )
        pending_orders[:] = remaining_orders

    print(f"\n  Processing {len(base):,} ticks with {len(bins):,} bin signals...")

    for i, row in base.iterrows():
        if i % 50000 == 0:
            print(f"    Tick {i:,}/{len(base):,} | Open positions: {len(open_positions)} | Completed trades: {len(trades)}")

        current_time = row['timestamp']
        current_price = row['price']

        # 1. Check for exits FIRST
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

        # Try to fill pending orders
        attempt_fill_pending_orders(current_time, current_price)

        # 2. Check for new bin RESET signals (reset_timestamp reached)
        while (
            next_signal_idx < total_signals
            and signals_list[next_signal_idx]["reset_timestamp"] <= current_time
        ):
            signal_data = signals_list[next_signal_idx]
            next_signal_idx += 1

            price_tag = str(signal_data.get('price_tag', '')).strip().lower()

            # Ignorar señales 'flat' (aunque no deberían existir en este CSV)
            if price_tag == 'flat':
                continue

            # LÓGICA CONTRARIAN: Determinar el tipo de entrada según price_tag
            # - price_tag='up' → precio encima de SMA, esperamos reversión → SHORT
            # - price_tag='down' → precio debajo de SMA, esperamos reversión → LONG
            if price_tag == 'up':
                side = "SHORT"
            elif price_tag == 'down':
                side = "LONG"
            else:
                # Skip unknown tags
                continue

            # NUEVA LÓGICA: Solo entrar si este reset_timestamp NO ha sido usado antes
            # Esto previene duplicados basándose en el TIEMPO del reset
            reset_ts = signal_data['reset_timestamp']
            if reset_ts in entered_bin_timestamps:
                # Ya entramos en este reset timestamp → NO entrar de nuevo
                continue

            # Crear nueva orden para entrar en el RESET actual
            reset_price = float(signal_data['reset_price'])  # USAR RESET PRICE
            cum_vol = float(signal_data.get('cumulative_volume_before_reset', 0))

            pending_orders.append(
                PendingOrder(
                    side=side,
                    signal_tag=price_tag,
                    signal_time=reset_ts,  # USAR RESET TIMESTAMP
                    signal_price=reset_price,
                    entry_price=reset_price,  # ENTRAR EN EL RESET
                    signal_data=signal_data,
                    force_fill=True,
                    bin_number=int(cum_vol),  # Use cumulative volume as bin identifier
                )
            )

            # Marcar este timestamp como usado
            entered_bin_timestamps.add(reset_ts)

            # IMPORTANTE: Llenar la orden INMEDIATAMENTE para que open_positions se actualice
            # antes de procesar la siguiente señal (permite que has_same_side_position funcione)
            attempt_fill_pending_orders(current_time, current_price)

        # Re-attempt fills after all signals (por si quedó alguna pendiente)
        attempt_fill_pending_orders(current_time, current_price)

    # 3. Close remaining positions at EOD
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

    return pd.DataFrame(trades)


def main() -> pd.DataFrame:
    """Ejecuta el backtest con bins."""
    print("=" * 80)
    print("BACKTEST - BIN RESET REVERSAL STRATEGY (CONTRARIAN)")
    print("=" * 80)
    print(f"\n[INFO] Loading bin reset signals from: {BINS_FILE}")
    print(f"[INFO] Loading T&S data from: {TNS_FILE}")

    # Load bins (signals) - NEW CSV STRUCTURE
    df_bins_raw = _read_csv_semicolon_decimal(BINS_FILE)
    df_bins = pd.DataFrame({
        # Reset data (momento del reset de acumulación)
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
    print(f"     - UP signals: {(df_bins['price_tag']=='up').sum()} -> will generate SHORT trades (contrarian: entry at RESET)")
    print(f"     - DOWN signals: {(df_bins['price_tag']=='down').sum()} -> will generate LONG trades (contrarian: entry at RESET)")
    print(f"\n[INFO] RESET ENTRY LOGIC (CONTRARIAN):")
    print(f"     - Entry Price: reset_price (when cumulative volume resets)")
    print(f"     - Entry Time: reset_timestamp (moment of volume reset)")
    print(f"     - Entry Logic: UP tag (price>SMA) -> SHORT | DOWN tag (price<SMA) -> LONG")
    print(f"     - Exit: TP/SL only")

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

    df_trades = run_backtest_bins(df_bins, df_base)

    # Save results
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df_trades.to_csv(OUTPUT_FILE, sep=';', decimal=',', index=False)

    print(f"\n[OK] Results saved to: {OUTPUT_FILE}")
    print(f"[OK] Total trades: {len(df_trades)}")

    if len(df_trades) > 0:
        wins = (df_trades['exit_reason'] == 'TARGET').sum()
        losses = (df_trades['exit_reason'] == 'STOP').sum()
        total_pnl = df_trades['profit_dollars'].sum()

        print(f"\n[INFO] Quick Stats:")
        print(f"  - Wins: {wins} ({wins/len(df_trades)*100:.1f}%)")
        print(f"  - Losses: {losses} ({losses/len(df_trades)*100:.1f}%)")
        print(f"  - Total P&L: ${total_pnl:,.2f}")

    return df_trades


if __name__ == "__main__":
    main()
