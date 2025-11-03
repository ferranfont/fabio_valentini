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

TNS_FILE = DATA_DIR / "time_and_sales_20251031_074530.csv"
#TNS_FILE = DATA_DIR / "time_and_sales_nq.csv"    # Alternativa: octubre
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
OUTPUT_FILE = OUTPUTS_DIR / "tracking_record_absortion_shape_INV_all_day.csv"

# ========= PARÁMETROS =========
SYMBOL = "NQ"
TP_POINTS = 4.0
SL_POINTS = 3.0
POINT_VALUE = 20.0
CONTRACTS = 1         # Número de contratos por trade
NUM_MAX_OPEN_CONTRACTS = 3  # Máximo número de posiciones abiertas simultáneamente
BREAK_EVEN_POINTS = 4.0  # Desplaza el stop a precio de entrada al avanzar X puntos

# ========= PARÁMETROS EMA =========
EMA_FAST_PERIOD = 20   # Período de la EMA rápida (en minutos)
EMA_SLOW_PERIOD = 100  # Período de la EMA lenta (en minutos)

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
    signal_category: str = ""  # "p_above_green", "d_inside_green", "d_below_red", "p_inside_red"
    break_even_active: bool = False

# ========= BACKTEST =========
def run_backtest_tickdriven(df_signals: pd.DataFrame, df_base: pd.DataFrame) -> pd.DataFrame:
    """
    Backtest tick-driven con control de posiciones máximas abiertas.
    Estrategia basada en EMAs:
    - Si EMA_FAST < EMA_SLOW: Solo SHORT (tanto d_shape como p_shape)
    - Si EMA_FAST > EMA_SLOW: Solo LONG (tanto d_shape como p_shape)

    df_signals: columnas ['timestamp','shape','close_price']
    df_base:    columnas ['timestamp','price'] (derivado de T&S)
    """
    # Preparar datos
    sig = df_signals.copy().sort_values("timestamp").reset_index(drop=True)
    sig['signal_idx'] = range(len(sig))  # Para tracking

    base = df_base.copy().sort_values("timestamp").reset_index(drop=True)

    # Calcular EMAs en base de datos de 1 minuto
    print(f"\n  Calculando EMAs (Fast={EMA_FAST_PERIOD}min, Slow={EMA_SLOW_PERIOD}min)...")
    base_resampled = base.set_index('timestamp').resample('1min')['price'].last().dropna().reset_index()
    base_resampled.columns = ['timestamp', 'price']

    base_resampled['ema_fast'] = base_resampled['price'].ewm(span=EMA_FAST_PERIOD, adjust=False).mean()
    base_resampled['ema_slow'] = base_resampled['price'].ewm(span=EMA_SLOW_PERIOD, adjust=False).mean()

    # Merge EMAs back to tick data (forward fill)
    base = base.merge(base_resampled[['timestamp', 'ema_fast', 'ema_slow']], on='timestamp', how='left')
    base['ema_fast'] = base['ema_fast'].ffill()
    base['ema_slow'] = base['ema_slow'].ffill()

    # Crear diccionario de señales por timestamp (permite múltiples señales por timestamp)
    signals_by_time = {}
    for _, signal_row in sig.iterrows():
        ts = signal_row['timestamp']
        if ts not in signals_by_time:
            signals_by_time[ts] = []
        signals_by_time[ts].append({
            'shape': signal_row['shape'],
            'close_price': signal_row['close_price'],
            'signal_idx': signal_row['signal_idx']
        })

    trades = []
    open_positions = []  # List of OpenPosition objects
    processed_signals = set()  # Track which signals have been processed (by signal_idx)

    print(f"\n  Processing {len(base):,} ticks with {len(sig):,} signals...")

    for i, row in base.iterrows():
        if i % 50000 == 0:
            print(f"    Tick {i:,}/{len(base):,} | Open positions: {len(open_positions)} | Completed trades: {len(trades)}")

        current_time = row['timestamp']
        current_price = row['price']
        ema_fast = row.get('ema_fast', None)
        ema_slow = row.get('ema_slow', None)

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

                trades.append({
                    "entry_time": pos.entry_time,
                    "entry_price": pos.entry_price,
                    "exit_time": current_time,
                    "exit_price": float(exit_price),
                    "side": pos.side,
                    "entry_signal": pos.entry_signal,
                    "signal_category": pos.signal_category,
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

        # 2. Check for new signals at current timestamp (process ALL signals, up to max limit)
        if current_time in signals_by_time:
            signals_at_time = signals_by_time[current_time]

            for signal_data in signals_at_time:
                signal_idx = signal_data['signal_idx']

                # Skip if this signal was already processed
                if signal_idx in processed_signals:
                    continue

                # Only open if we have room for more positions
                if len(open_positions) >= NUM_MAX_OPEN_CONTRACTS:
                    continue

                # Skip if EMAs are not available yet
                if pd.isna(ema_fast) or pd.isna(ema_slow):
                    continue

                shape = str(signal_data['shape']).strip().lower()
                signal_price = float(signal_data['close_price'])

                new_pos = None

                # ESTRATEGIA HÍBRIDA:
                # 1. Filtro de Tendencia (EMA)
                # 2. Detección de Clustering (señales recientes del mismo tipo)
                # 3. Detección de Rangos (ATR bajo)
                # 4. Targets dinámicos según contexto

                # Check for clustering: look for same signal type in last 30 minutes
                clustering_window_minutes = 30
                time_window_start = current_time - pd.Timedelta(minutes=clustering_window_minutes)
                recent_signals = df_signals[(df_signals['timestamp'] > time_window_start) &
                                           (df_signals['timestamp'] < current_time) &
                                           (df_signals['shape'] == shape)]
                has_clustering = len(recent_signals) > 0

                # Calculate ATR for range detection (simple approximation)
                # Use last 14 1-minute bars for ATR
                lookback_time = current_time - pd.Timedelta(minutes=14)
                recent_prices = base[(base['timestamp'] >= lookback_time) & (base['timestamp'] < current_time)]['price']
                if len(recent_prices) > 1:
                    price_range = recent_prices.max() - recent_prices.min()
                    avg_price = recent_prices.mean()
                    atr_pct = (price_range / avg_price) * 100 if avg_price > 0 else 999
                    is_ranging = atr_pct < 0.15  # Less than 0.15% range = ranging market

                    # Calculate range center for ranging markets
                    range_high = recent_prices.max()
                    range_low = recent_prices.min()
                    range_center = (range_high + range_low) / 2
                else:
                    is_ranging = False
                    range_center = signal_price

                # Determine signal category
                market_context = "range" if is_ranging else "trend"
                cluster_suffix = "cluster" if has_clustering else "single"

                # ESTRATEGIA CORREGIDA: SOLO OPERA A FAVOR DE LA TENDENCIA
                # Tendencia BAJISTA: Solo SHORT
                # Tendencia ALCISTA: Solo LONG

                if ema_fast < ema_slow:
                    # ============================================
                    # ZONA BAJISTA: EMA20 < EMA100 → SOLO SHORT
                    # ============================================

                    if shape == "d_shape" and signal_price < ema_fast:
                        # d_shape por debajo de EMA20: SHORT
                        # (precio cayendo, BID absorbiendo en zona baja)
                        if not is_ranging:  # Solo en tendencia, no en rango
                            tp_price = signal_price - TP_POINTS
                            new_pos = OpenPosition(
                                side="SHORT",
                                entry_time=current_time,
                                entry_price=signal_price,
                                entry_signal=shape,
                                tp_price=tp_price,
                                sl_price=signal_price + SL_POINTS,
                                signal_category=f"{market_context}_{cluster_suffix}_d_below_red"
                            )

                    elif shape == "p_shape" and ema_fast < signal_price < ema_slow:
                        # p_shape ENTRE las EMAs (zona roja): SHORT
                        # (compradores siendo absorbidos en zona de resistencia)
                        if is_ranging:
                            # En rango: target al centro del rango
                            tp_price = range_center if signal_price > range_center else signal_price - TP_POINTS
                        else:
                            tp_price = signal_price - TP_POINTS
                        new_pos = OpenPosition(
                            side="SHORT",
                            entry_time=current_time,
                            entry_price=signal_price,
                            entry_signal=shape,
                            tp_price=tp_price,
                            sl_price=signal_price + SL_POINTS,
                            signal_category=f"{market_context}_{cluster_suffix}_p_inside_red"
                        )

                    # IMPORTANTE: Si p_shape está por DEBAJO de ambas EMAs en bajista
                    # NO operamos (precio ya cayó demasiado, no perseguir)
                    # Si d_shape está DENTRO o ARRIBA de EMAs en bajista
                    # NO operamos (contra-tendencia, compraría en bajista)

                elif ema_fast > ema_slow:
                    # ============================================
                    # ZONA ALCISTA: EMA20 > EMA100 → SOLO LONG
                    # ============================================

                    if shape == "d_shape" and ema_slow < signal_price < ema_fast:
                        # d_shape ENTRE las EMAs (zona verde): LONG
                        # (vendedores siendo absorbidos en zona de soporte)
                        if is_ranging:
                            # En rango: target al centro del rango
                            tp_price = range_center if signal_price < range_center else signal_price + TP_POINTS
                        else:
                            tp_price = signal_price + TP_POINTS
                        new_pos = OpenPosition(
                            side="LONG",
                            entry_time=current_time,
                            entry_price=signal_price,
                            entry_signal=shape,
                            tp_price=tp_price,
                            sl_price=signal_price - SL_POINTS,
                            signal_category=f"{market_context}_{cluster_suffix}_d_inside_green"
                        )

                    elif shape == "p_shape" and signal_price > ema_fast:
                        # p_shape por ENCIMA de EMA20: LONG
                        # (precio subiendo, ASK absorbiendo en zona alta)
                        if not is_ranging:  # Solo en tendencia, no en rango
                            tp_price = signal_price + TP_POINTS
                            new_pos = OpenPosition(
                                side="LONG",
                                entry_time=current_time,
                                entry_price=signal_price,
                                entry_signal=shape,
                                tp_price=tp_price,
                                sl_price=signal_price - SL_POINTS,
                                signal_category=f"{market_context}_{cluster_suffix}_p_above_green"
                            )

                    # IMPORTANTE: Si d_shape está por ARRIBA de ambas EMAs en alcista
                    # NO operamos (precio ya subió demasiado, no perseguir)
                    # Si p_shape está DENTRO o DEBAJO de EMAs en alcista
                    # NO operamos (contra-tendencia, vendería en alcista)

                if new_pos:
                    open_positions.append(new_pos)
                    processed_signals.add(signal_idx)

    # 3. Close any remaining open positions at END_OF_DATA
    if open_positions:
        last_time = base.iloc[-1]['timestamp']
        last_price = base.iloc[-1]['price']

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

    # Guardar
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    trades.to_csv(OUTPUT_FILE, sep=";", decimal=",", index=False)
    print(f"\nResultados guardados en {OUTPUT_FILE}\n")
    print("=" * 70)
    return trades

if __name__ == "__main__":
    _ = main()
