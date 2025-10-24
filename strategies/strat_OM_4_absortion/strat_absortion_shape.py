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
SIGNALS_FILE = OUTPUTS_DIR / "db_shapes_20251024_003251.csv"
#SIGNALS_FILE = OUTPUTS_DIR / "db_shapes.csv"    # señales
OUTPUT_FILE = OUTPUTS_DIR / "tracking_record_absortion_shape_all_day.csv"

# ========= PARÁMETROS =========
SYMBOL = "NQ"
TP_POINTS = 4.0
SL_POINTS = 3.0
POINT_VALUE = 20.0
CONTRACTS = 1         # Número de contratos por trade
NUM_MAX_OPEN_CONTRACTS = 1  # Máximo número de posiciones abiertas simultáneamente

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

    # Merge signals into base timeline (outer join to keep all ticks)
    merged = pd.merge(
        base,
        sig[['timestamp', 'shape', 'close_price', 'signal_idx']],
        on='timestamp',
        how='left'
    ).sort_values('timestamp').reset_index(drop=True)

    trades = []
    open_positions = []  # List of OpenPosition objects

    print(f"\n  Processing {len(merged):,} ticks with {len(sig):,} signals...")

    for i, row in merged.iterrows():
        if i % 50000 == 0:
            print(f"    Tick {i:,}/{len(merged):,} | Open positions: {len(open_positions)} | Completed trades: {len(trades)}")

        current_time = row['timestamp']
        current_price = row['price']

        # 1. Check for exits FIRST (before processing new signals)
        positions_to_close = []
        for pos in open_positions:
            exit_reason = None
            exit_price = None

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

                trades.append({
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
                })
                positions_to_close.append(pos)

        # Remove closed positions
        for pos in positions_to_close:
            open_positions.remove(pos)

        # 2. Check for new signal (only if we have room for more positions)
        if pd.notna(row['shape']) and len(open_positions) < NUM_MAX_OPEN_CONTRACTS:
            shape = str(row['shape']).strip().lower()
            signal_price = float(row['close_price'])

            new_pos = None
            if shape == "d_shape":
                new_pos = OpenPosition(
                    side="LONG",
                    entry_time=current_time,
                    entry_price=signal_price,
                    entry_signal="d_shape",
                    tp_price=signal_price + TP_POINTS,
                    sl_price=signal_price - SL_POINTS
                )
            elif shape == "p_shape":
                new_pos = OpenPosition(
                    side="SHORT",
                    entry_time=current_time,
                    entry_price=signal_price,
                    entry_signal="p_shape",
                    tp_price=signal_price - TP_POINTS,
                    sl_price=signal_price + SL_POINTS
                )

            if new_pos:
                open_positions.append(new_pos)

    # 3. Close any remaining open positions at END_OF_DATA
    if open_positions:
        last_time = merged.iloc[-1]['timestamp']
        last_price = merged.iloc[-1]['price']

        for pos in open_positions:
            if pos.side == "LONG":
                profit_points = last_price - pos.entry_price
            else:  # SHORT
                profit_points = pos.entry_price - last_price

            trades.append({
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
            })

    print(f"    Completed: {len(trades):,} trades")
    return pd.DataFrame(trades)

# ========= MAIN =========
def main() -> pd.DataFrame:
    print("=" * 70)
    print("ESTRATEGIA: d-Shape & p-Shape (Absorption) — Tick-driven")
    print("=" * 70)
    print(f"  Rutas:\n    Señales: {SIGNALS_FILE}\n    T&S:     {TNS_FILE}\n    Out:     {OUTPUT_FILE}")
    print(f"  Parámetros: TP={TP_POINTS} pts, SL={SL_POINTS} pts, {CONTRACTS} contratos, ${POINT_VALUE}/pt")
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

    # Guardar
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    trades.to_csv(OUTPUT_FILE, sep=";", decimal=",", index=False)
    print(f"\nResultados guardados en {OUTPUT_FILE}\n")
    print("=" * 70)
    return trades

if __name__ == "__main__":
    _ = main()
