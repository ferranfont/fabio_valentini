from __future__ import annotations

"""
Estrategia d-Shape & p-Shape (Absorption) – backtest con evaluación tick-by-tick
- Señales:          outputs/db_shapes.csv
- Precio base T&S:  data/time_and_sales_nq_30min.csv
- Resultados:       outputs/tracking_record_absortion_shape.csv

Cambia respecto a versiones previas:
- El TP/SL se evalúa con TODOS los eventos del T&S (no sólo en las filas de señales).
- SL configurable a 3 puntos, TP a 4 puntos.
- Control de posiciones máximas abiertas simultáneamente (NUM_MAX_OPEN_CONTRACTS).
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
PROJECT_ROOT = THIS_FILE.parents[2]  # .../strategies/strat_OM_4_absortion -> strategies -> root
DATA_DIR = PROJECT_ROOT / "data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

TNS_FILE = DATA_DIR / "time_and_sales_nq.csv"
#TNS_FILE = DATA_DIR / "time_and_sales_nq_30min.csv"    # precio base

def _resolve_signals_file() -> Path:
    override = os.getenv("ABSORTION_SIGNALS_CSV")
    if override:
        return Path(override).expanduser()

    candidates: list[tuple[float, Path]] = []
    for pattern in ("db_shapes_dom_*.csv", "db_shapes_*.csv"):
        for path in OUTPUTS_DIR.glob(pattern):
            try:
                candidates.append((path.stat().st_mtime, path))
            except FileNotFoundError:
                continue

    if candidates:
        _, latest = max(candidates, key=lambda item: item[0])
        return latest

    return OUTPUTS_DIR / "db_shapes.csv"


SIGNALS_FILE = _resolve_signals_file().resolve()
#SIGNALS_FILE = OUTPUTS_DIR / "db_shapes.csv"    # señales
OUTPUT_FILE = OUTPUTS_DIR / "tracking_record_absortion_shape_all_day.csv"

# ========= PARÁMETROS =========
SYMBOL = "NQ"
TP_POINTS = 4.0
SL_POINTS = 3.0
POINT_VALUE = 20.0
THRESHOLD_EXTRA = 0.0
CONTRACTS = 1         # Número de contratos por trade
NUM_MAX_OPEN_CONTRACTS = 3  # Máximo número de posiciones abiertas simultáneamente
BREAK_EVEN_POINTS = 4.0  # Desplaza el stop a precio de entrada al avanzar X puntos

# ========= ESTADÍSTICAS DE EJECUCIÓN =========
LAST_NOT_TRIGGERED_SIGNALS: list[dict] = []

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
    # Market Profile signal data
    signal_data: dict = None  # Store all signal columns


@dataclass
class PendingOrder:
    """Represents a limit order waiting to be triggered."""
    side: str
    shape: str
    signal_idx: int
    signal_time: pd.Timestamp
    signal_price: float
    entry_price: float
    # Market Profile signal data
    signal_data: dict = None  # Store all signal columns

# ========= BACKTEST =========
def run_backtest_tickdriven(df_signals: pd.DataFrame, df_base: pd.DataFrame) -> pd.DataFrame:
    """
    Backtest tick-driven con control de posiciones máximas abiertas.
    df_signals: columnas ['timestamp','shape','close_price']
    df_base:    columnas ['timestamp','price'] (derivado de T&S)
    """
    # Preparar datos
    sig = df_signals.copy().sort_values("timestamp").reset_index(drop=True)
    sig['signal_idx'] = range(len(sig))  # Para tracking

    base = df_base.copy().sort_values("timestamp").reset_index(drop=True)

    # Crear diccionario de señales por timestamp (permite múltiples señales por timestamp)
    signals_by_time = {}
    for _, signal_row in sig.iterrows():
        ts = signal_row['timestamp']
        if ts not in signals_by_time:
            signals_by_time[ts] = []

        # Store ALL signal data (all columns from db_shapes)
        signal_dict = signal_row.to_dict()
        signals_by_time[ts].append(signal_dict)

    trades = []
    open_positions: list[OpenPosition] = []
    pending_orders: list[PendingOrder] = []
    processed_signals = set()  # Track which signals have been processed (by signal_idx)

    def attempt_fill_pending_orders(current_time: pd.Timestamp, current_price: float) -> None:
        """Try to convert pending limit orders into open positions with the current price."""
        remaining_orders: list[PendingOrder] = []
        for order in pending_orders:
            # Enforce capacity: keep order pending if we already reached the limit
            if len(open_positions) >= NUM_MAX_OPEN_CONTRACTS:
                remaining_orders.append(order)
                continue

            if order.side == "LONG":
                should_fill = current_price <= order.entry_price
            else:  # SHORT
                should_fill = current_price >= order.entry_price

            if not should_fill:
                remaining_orders.append(order)
                continue

            entry_price = order.entry_price
            tp_price = entry_price + TP_POINTS if order.side == "LONG" else entry_price - TP_POINTS
            sl_price = entry_price - SL_POINTS if order.side == "LONG" else entry_price + SL_POINTS

            open_positions.append(
                OpenPosition(
                    side=order.side,
                    entry_time=current_time,
                    entry_price=entry_price,
                    entry_signal=order.shape,
                    tp_price=tp_price,
                    sl_price=sl_price,
                    signal_data=order.signal_data
                )
            )
        pending_orders[:] = remaining_orders

    print(f"\n  Processing {len(base):,} ticks with {len(sig):,} signals...")

    for i, row in base.iterrows():
        if i % 50000 == 0:
            print(f"    Tick {i:,}/{len(base):,} | Open positions: {len(open_positions)} | Completed trades: {len(trades)}")

        current_time = row['timestamp']
        current_price = row['price']

        # 1. Check for exits FIRST (before processing new signals)
        positions_to_close = []
        for pos in open_positions:
            exit_reason = None
            exit_price = None

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

                # Build trade record with all signal data
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
                    "contracts": CONTRACTS
                }

                # Add all Market Profile signal data with "signal_" prefix
                if pos.signal_data:
                    for key, value in pos.signal_data.items():
                        # Skip timestamp and signal_idx as they're redundant
                        if key not in ['timestamp', 'signal_idx']:
                            trade_record[f"signal_{key}"] = value

                trades.append(trade_record)
                positions_to_close.append(pos)

        # Remove closed positions
        for pos in positions_to_close:
            open_positions.remove(pos)

        # Try to fill any pending orders with the current price before considering new signals
        attempt_fill_pending_orders(current_time, current_price)

        # 2. Check for new signals at current timestamp (process ALL signals, up to max limit)
        if current_time in signals_by_time:
            signals_at_time = signals_by_time[current_time]

            for signal_data in signals_at_time:
                signal_idx = signal_data['signal_idx']

                # Skip if this signal was already processed
                if signal_idx in processed_signals:
                    continue

                # Only accept if we have room considering pending orders too
                if len(open_positions) + len(pending_orders) >= NUM_MAX_OPEN_CONTRACTS:
                    continue  # keep processing remaining signals at this timestamp

                shape = str(signal_data['shape']).strip().lower()
                signal_price = float(signal_data['close_price'])

                if shape == "d_shape":
                    entry_price = signal_price - THRESHOLD_EXTRA
                    pending_orders.append(
                        PendingOrder(
                            side="LONG",
                            shape="d_shape",
                            signal_idx=signal_idx,
                            signal_time=current_time,
                            signal_price=signal_price,
                            entry_price=entry_price,
                            signal_data=signal_data
                        )
                    )
                    processed_signals.add(signal_idx)
                elif shape == "p_shape":
                    entry_price = signal_price + THRESHOLD_EXTRA
                    pending_orders.append(
                        PendingOrder(
                            side="SHORT",
                            shape="p_shape",
                            signal_idx=signal_idx,
                            signal_time=current_time,
                            signal_price=signal_price,
                            entry_price=entry_price,
                            signal_data=signal_data
                        )
                    )
                    processed_signals.add(signal_idx)

        # After evaluating new signals, re-attempt fills in case price already meets the new orders
        attempt_fill_pending_orders(current_time, current_price)

    # 3. Close any remaining open positions at END_OF_DATA
    if open_positions:
        last_time = base.iloc[-1]['timestamp']
        last_price = base.iloc[-1]['price']

        for pos in open_positions:
            if pos.side == "LONG":
                profit_points = last_price - pos.entry_price
            else:  # SHORT
                profit_points = pos.entry_price - last_price

            # Build trade record with all signal data
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
                "contracts": CONTRACTS
            }

            # Add all Market Profile signal data with "signal_" prefix
            if pos.signal_data:
                for key, value in pos.signal_data.items():
                    # Skip timestamp and signal_idx as they're redundant
                    if key not in ['timestamp', 'signal_idx']:
                        trade_record[f"signal_{key}"] = value

            trades.append(trade_record)

    # Persist pending orders for reporting
    global LAST_NOT_TRIGGERED_SIGNALS
    LAST_NOT_TRIGGERED_SIGNALS = [
        {
            "side": order.side,
            "shape": order.shape,
            "signal_time": order.signal_time,
            "signal_price": order.signal_price,
            "entry_price": order.entry_price,
        }
        for order in pending_orders
    ]

    print(f"    Completed: {len(trades):,} trades")
    return pd.DataFrame(trades)

# ========= MAIN =========
def main() -> pd.DataFrame:
    print("=" * 70)
    print("ESTRATEGIA: d-Shape & p-Shape (Absorption) — Tick-driven")
    print("=" * 70)
    print(f"  Rutas:\n    Señales: {SIGNALS_FILE}\n    T&S:     {TNS_FILE}\n    Out:     {OUTPUT_FILE}")
    print(f"  Parámetros: TP={TP_POINTS} pts, SL={SL_POINTS} pts, {CONTRACTS} contratos, ${POINT_VALUE}/pt")
    print(f"  Break-even activacion: {BREAK_EVEN_POINTS} pts")
    print(f"  Max posiciones abiertas simultáneamente: {NUM_MAX_OPEN_CONTRACTS}\n")

    # Cargar señales
    if not SIGNALS_FILE.exists():
        raise FileNotFoundError(f"No existe {SIGNALS_FILE}")
    df_sig = _read_csv_semicolon_decimal(SIGNALS_FILE)
    df_sig.columns = df_sig.columns.str.strip().str.lower()
    for must in ("timestamp", "shape", "close_price"):
        if must not in df_sig.columns:
            raise ValueError(f"Falta columna en señales: {must}")
    df_sig["timestamp"] = pd.to_datetime(df_sig["timestamp"])
    df_sig["shape"] = df_sig["shape"].str.strip().str.lower()
    df_sig["close_price"] = _to_float(df_sig["close_price"])

    # Cargar precio base T&S
    if not TNS_FILE.exists():
        raise FileNotFoundError(f"No existe {TNS_FILE}")
    base = _read_csv_semicolon_decimal(TNS_FILE)
    base.columns = base.columns.str.strip()
    ts_col = next((c for c in base.columns if c.lower().startswith("timestamp")), "Timestamp")
    px_col = next((c for c in base.columns if c.lower().startswith("precio")), "Precio")
    base["timestamp"] = pd.to_datetime(base[ts_col])
    base["price"] = _to_float(base[px_col])
    base = base[["timestamp", "price"]].sort_values("timestamp").reset_index(drop=True)

    print(f"  Señales: {len(df_sig):,} | Base T&S: {len(base):,}\n")

    trades = run_backtest_tickdriven(df_sig, base)

    # Estadísticas rápidas
    if trades.empty:
        print("Sin trades generados.")
    else:
        trades["equity"] = trades["profit_dollars"].cumsum()
        total = trades["profit_dollars"].sum()
        wr = (trades["profit_dollars"] > 0).mean() * 100
        print(f"\n  Trades: {len(trades):,} | P&L total: ${total:,.2f} | Win rate: {wr:.1f}%")
        dd = (trades["equity"] - trades["equity"].cummax()).min()
        print(f"  Max DD: ${dd:,.2f}")

    pending_entries = LAST_NOT_TRIGGERED_SIGNALS
    if pending_entries:
        print("\nEntradas db-shape no ejecutadas:")
        for entry in pending_entries:
            ts_str = pd.Timestamp(entry["signal_time"]).strftime("%Y-%m-%d %H:%M:%S")
            print(
                f"  {ts_str} | {entry['shape']} | señal={entry['signal_price']:.2f} | entrada limite={entry['entry_price']:.2f}"
            )
        print(f"Total entradas no ejecutadas: {len(pending_entries)}")
    else:
        print("\nTodas las entradas db-shape fueron ejecutadas.")

    # Guardar
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    trades.to_csv(OUTPUT_FILE, sep=";", decimal=",", index=False)
    print(f"\nResultados guardados en {OUTPUT_FILE}\n")
    print("=" * 70)
    return trades

if __name__ == "__main__":
    _ = main()
