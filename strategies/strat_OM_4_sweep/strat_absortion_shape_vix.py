from __future__ import annotations

"""
Estrategia d-Shape & p-Shape (Absorption) – backtest con ATR y Trailing Stop
- Señales:          outputs/db_shapes.csv
- Precio base T&S:  data/time_and_sales_nq.csv
- Resultados:       outputs/tracking_record_absortion_shape_vix.csv

DIFERENCIAS con versión estándar:
- SL/TP dinámicos basados en ATR (Average True Range) de volatilidad
- Trailing Stop: mueve el SL cuando el precio avanza a favor
- ATR calculado sobre ventanas móviles de N periodos
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
OUTPUT_FILE = OUTPUTS_DIR / "tracking_record_absortion_shape_vix.csv"

# ========= PARÁMETROS ATR Y TRAILING STOP =========
SYMBOL = "NQ"
ATR_PERIOD = 14                 # Periodo para calcular ATR (en minutos si agregamos datos)
ATR_MULTIPLIER_SL = 1.5         # Multiplicador ATR para Stop Loss (1.5 x ATR)
ATR_MULTIPLIER_TP = 2.5         # Multiplicador ATR para Take Profit (2.5 x ATR)
TRAILING_STOP_ATR_MULT = 0.75   # Multiplicador ATR para trailing stop distance (0.75 x ATR)
POINT_VALUE = 20.0              # Valor del punto en dólares
THRESHOLD_EXTRA = 0.0           # Margen adicional para entrada
CONTRACTS = 1                   # Número de contratos por trade
NUM_MAX_OPEN_CONTRACTS = 3      # Máximo número de posiciones abiertas simultáneamente
USE_TRAILING_STOP = True        # Activar/desactivar trailing stop

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

def calculate_atr(df_price: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calcula ATR (Average True Range) para datos de precio tick-by-tick.

    Args:
        df_price: DataFrame con columnas ['timestamp', 'price']
        period: Periodo de ventana para calcular ATR

    Returns:
        Serie con valores de ATR
    """
    # Agregar datos a periodos de 1 minuto para tener OHLC
    df_price = df_price.copy()
    df_price['timestamp'] = pd.to_datetime(df_price['timestamp'])
    df_price = df_price.set_index('timestamp')

    # Resample a 1 minuto para crear OHLC
    ohlc = df_price['price'].resample('1T').ohlc()

    # Calcular True Range
    high_low = ohlc['high'] - ohlc['low']
    high_close = np.abs(ohlc['high'] - ohlc['close'].shift())
    low_close = np.abs(ohlc['low'] - ohlc['close'].shift())

    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

    # ATR = EMA del True Range
    atr = true_range.ewm(span=period, adjust=False).mean()

    # Forward fill para tener un valor de ATR para cada tick
    atr_series = atr.reindex(df_price.index, method='ffill').fillna(atr.iloc[0] if len(atr) > 0 else 1.0)

    return atr_series.reset_index(drop=True)


@dataclass
class OpenPosition:
    """Represents an open position with trailing stop capability."""
    side: str  # "LONG" or "SHORT"
    entry_time: pd.Timestamp
    entry_price: float
    entry_signal: str
    tp_price: float
    sl_price: float
    trailing_stop_distance: float  # Distance from current price for trailing stop
    highest_price: float = None  # Track highest price for LONG trailing
    lowest_price: float = None   # Track lowest price for SHORT trailing
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
    atr_value: float  # ATR at signal time for dynamic SL/TP calculation
    signal_data: dict = None  # Store all signal columns

# ========= BACKTEST =========
def run_backtest_tickdriven_vix(df_signals: pd.DataFrame, df_base: pd.DataFrame) -> pd.DataFrame:
    """
    Backtest tick-driven con ATR y trailing stop.
    df_signals: columnas ['timestamp','shape','close_price']
    df_base:    columnas ['timestamp','price'] (derivado de T&S)
    """
    # Preparar datos
    sig = df_signals.copy().sort_values("timestamp").reset_index(drop=True)
    sig['signal_idx'] = range(len(sig))  # Para tracking

    base = df_base.copy().sort_values("timestamp").reset_index(drop=True)

    # Calcular ATR para todo el dataset
    print("  Calculando ATR...")
    base['atr'] = calculate_atr(base[['timestamp', 'price']].copy(), period=ATR_PERIOD)
    print(f"  ATR calculado. Promedio: {base['atr'].mean():.2f}, Min: {base['atr'].min():.2f}, Max: {base['atr'].max():.2f}")

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

    def get_atr_at_time(current_time: pd.Timestamp) -> float:
        """Get ATR value at specific timestamp."""
        mask = base['timestamp'] <= current_time
        if mask.any():
            return base.loc[mask, 'atr'].iloc[-1]
        return base['atr'].iloc[0]

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

            # Calculate dynamic SL/TP based on ATR
            atr = order.atr_value
            sl_distance = atr * ATR_MULTIPLIER_SL
            tp_distance = atr * ATR_MULTIPLIER_TP
            trailing_distance = atr * TRAILING_STOP_ATR_MULT

            entry_price = order.entry_price
            if order.side == "LONG":
                tp_price = entry_price + tp_distance
                sl_price = entry_price - sl_distance
                highest_price = entry_price
                lowest_price = None
            else:  # SHORT
                tp_price = entry_price - tp_distance
                sl_price = entry_price + sl_distance
                highest_price = None
                lowest_price = entry_price

            open_positions.append(
                OpenPosition(
                    side=order.side,
                    entry_time=current_time,
                    entry_price=entry_price,
                    entry_signal=order.shape,
                    tp_price=tp_price,
                    sl_price=sl_price,
                    trailing_stop_distance=trailing_distance,
                    highest_price=highest_price,
                    lowest_price=lowest_price,
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

        # 1. Update trailing stops and check for exits
        positions_to_close = []
        for pos in open_positions:
            exit_reason = None
            exit_price = None

            # Update trailing stop logic
            if USE_TRAILING_STOP:
                if pos.side == "LONG":
                    # Track highest price for LONG
                    if pos.highest_price is None or current_price > pos.highest_price:
                        pos.highest_price = current_price
                        # Move SL up (trailing)
                        new_sl = pos.highest_price - pos.trailing_stop_distance
                        if new_sl > pos.sl_price:
                            pos.sl_price = new_sl

                elif pos.side == "SHORT":
                    # Track lowest price for SHORT
                    if pos.lowest_price is None or current_price < pos.lowest_price:
                        pos.lowest_price = current_price
                        # Move SL down (trailing)
                        new_sl = pos.lowest_price + pos.trailing_stop_distance
                        if new_sl < pos.sl_price:
                            pos.sl_price = new_sl

            # Check exit conditions
            if pos.side == "LONG":
                if current_price >= pos.tp_price:
                    exit_reason = "TARGET"
                    exit_price = pos.tp_price
                elif current_price <= pos.sl_price:
                    exit_reason = "STOP" if not USE_TRAILING_STOP else "TRAILING_STOP"
                    exit_price = pos.sl_price

            elif pos.side == "SHORT":
                if current_price <= pos.tp_price:
                    exit_reason = "TARGET"
                    exit_price = pos.tp_price
                elif current_price >= pos.sl_price:
                    exit_reason = "STOP" if not USE_TRAILING_STOP else "TRAILING_STOP"
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
                    "contracts": CONTRACTS,
                    "trailing_stop_distance": round(pos.trailing_stop_distance, 2)
                }

                # Add tracking for trailing stop effectiveness
                if pos.side == "LONG" and pos.highest_price:
                    trade_record["highest_price_reached"] = round(pos.highest_price, 2)
                elif pos.side == "SHORT" and pos.lowest_price:
                    trade_record["lowest_price_reached"] = round(pos.lowest_price, 2)

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

                # Get ATR at signal time
                atr_at_signal = get_atr_at_time(current_time)

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
                            atr_value=atr_at_signal,
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
                            atr_value=atr_at_signal,
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
                "contracts": CONTRACTS,
                "trailing_stop_distance": round(pos.trailing_stop_distance, 2)
            }

            # Add tracking for trailing stop effectiveness
            if pos.side == "LONG" and pos.highest_price:
                trade_record["highest_price_reached"] = round(pos.highest_price, 2)
            elif pos.side == "SHORT" and pos.lowest_price:
                trade_record["lowest_price_reached"] = round(pos.lowest_price, 2)

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
            "atr_value": order.atr_value,
        }
        for order in pending_orders
    ]

    print(f"    Completed: {len(trades):,} trades")
    return pd.DataFrame(trades)

# ========= MAIN =========
def main() -> pd.DataFrame:
    print("=" * 70)
    print("ESTRATEGIA: d-Shape & p-Shape (Absorption) — ATR + Trailing Stop")
    print("=" * 70)
    print(f"  Rutas:\n    Señales: {SIGNALS_FILE}\n    T&S:     {TNS_FILE}\n    Out:     {OUTPUT_FILE}")
    print(f"  Parámetros ATR:")
    print(f"    ATR Period: {ATR_PERIOD} periodos")
    print(f"    SL Multiplier: {ATR_MULTIPLIER_SL}x ATR")
    print(f"    TP Multiplier: {ATR_MULTIPLIER_TP}x ATR")
    print(f"    Trailing Stop: {'ENABLED' if USE_TRAILING_STOP else 'DISABLED'} ({TRAILING_STOP_ATR_MULT}x ATR)")
    print(f"  Trading: {CONTRACTS} contratos, ${POINT_VALUE}/pt")
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

    trades = run_backtest_tickdriven_vix(df_sig, base)

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

        # Trailing stop statistics
        if USE_TRAILING_STOP and 'exit_reason' in trades.columns:
            trailing_stops = len(trades[trades['exit_reason'] == 'TRAILING_STOP'])
            print(f"  Trailing Stop exits: {trailing_stops} ({trailing_stops/len(trades)*100:.1f}%)")

    pending_entries = LAST_NOT_TRIGGERED_SIGNALS
    if pending_entries:
        print("\nEntradas db-shape no ejecutadas:")
        for entry in pending_entries:
            ts_str = pd.Timestamp(entry["signal_time"]).strftime("%Y-%m-%d %H:%M:%S")
            print(
                f"  {ts_str} | {entry['shape']} | señal={entry['signal_price']:.2f} | entrada limite={entry['entry_price']:.2f} | ATR={entry['atr_value']:.2f}"
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
