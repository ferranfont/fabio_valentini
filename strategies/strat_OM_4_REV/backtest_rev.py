from __future__ import annotations

"""
Backtest para la estrategia REV basada en señales d_shape / p_shape.

Características:
- Usa el tape tick-by-tick `time_and_sales_20251031_074530.csv`.
- Filtra las señales con el contexto de 1 minuto (EMA/VWAP/ATR).
- Ejecuta reglas específicas de TP/SL/time-stop.
- Opcionalmente evalúa segmentos para walk-forward.

Ejecución:
    python backtest_rev.py                   -> backtest completo
    python backtest_rev.py --walk-forward    -> además ejecuta walk-forward semanal
"""

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd

from analyze_shapes import (
    _choose_signals_file,
    _choose_tns_file,
    attach_context,
    build_minute_bars,
    load_signals,
    load_ticks,
)


# =============================================================================
# Parámetros y rutas
# =============================================================================
THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
REPORT_DIR = OUTPUTS_DIR / "rev_diagnostics"

POINT_VALUE = 20.0
CONTRACTS = 1

# Offsets específicos para cada tipo de señal
D_SHAPE_RULES = {
    "tp_points": 6.0,
    "sl_points": 4.0,
    "be_trigger": 4.0,
    "time_stop_minutes": 15,
    "cooldown_minutes": 10,
}

P_SHAPE_RULES = {
    "tp_points": 8.0,
    "sl_points": 5.0,
    "be_trigger": 5.0,
    "time_stop_minutes": 20,
    "cooldown_minutes": 8,
}

MAX_POSITIONS_PER_SIDE = 1
MAX_TOTAL_POSITIONS = 2


# =============================================================================
# Helpers
# =============================================================================
def _slice_ticks(
    df_ticks: pd.DataFrame,
    start: pd.Timestamp | None,
    end: pd.Timestamp | None,
    buffer_minutes: int = 30,
) -> pd.DataFrame:
    idx_start = start if start is not None else df_ticks.index.min()
    idx_end = end if end is not None else df_ticks.index.max()

    buffer = pd.Timedelta(minutes=buffer_minutes)
    idx_end_with_buffer = idx_end + buffer

    return df_ticks.loc[idx_start:idx_end_with_buffer].copy()


def _slice_events(
    df_events: pd.DataFrame, start: pd.Timestamp | None, end: pd.Timestamp | None
) -> pd.DataFrame:
    mask = pd.Series(True, index=df_events.index)
    if start is not None:
        mask &= df_events["timestamp"] >= start
    if end is not None:
        mask &= df_events["timestamp"] <= end
    return df_events.loc[mask].copy()


def _precompute_next_minute(df_minute: pd.DataFrame, df_events: pd.DataFrame) -> pd.DataFrame:
    """Agrega columnas con la información de la barra siguiente."""
    next_cols = df_minute[["close", "ema30"]].rename(
        columns={"close": "close_next", "ema30": "ema30_next"}
    )
    next_cols = next_cols.shift(-1)
    df_events = df_events.join(next_cols, on="minute")
    return df_events


def _flag_setups(df_events: pd.DataFrame) -> pd.DataFrame:
    """Aplica las reglas de filtrado para longs y shorts."""
    df = df_events.copy()

    # Condiciones básicas
    vwap_z = df["vwap_z"]
    atr = df["atr30_pts"]
    slope = df["ema30_slope"]

    long_mask = (
        (df["shape"] == "d_shape")
        & df["trend_regime"].isin(["bear", "neutral"])
        & (vwap_z <= -1.0)
        & atr.between(2.0, 7.0, inclusive="both")
        & (slope > -0.5)
    )

    short_mask = (
        (df["shape"] == "p_shape")
        & df["trend_regime"].isin(["bear", "neutral"])
        & (vwap_z > 0.25)
        & (vwap_z <= 1.5)
        & atr.between(2.5, 7.0, inclusive="both")
    )

    # Confirmación adicional para p_shape en tendencia neutral
    neutral_mask = (df["shape"] == "p_shape") & (df["trend_regime"] == "neutral")
    confirm_mask = neutral_mask & (df["close_next"] < df["ema30_next"])
    short_mask &= (~neutral_mask) | confirm_mask

    df["qualifies_long"] = long_mask
    df["qualifies_short"] = short_mask
    df["entry_side"] = np.select(
        [df["qualifies_long"], df["qualifies_short"]],
        ["LONG", "SHORT"],
        default=None,
    )

    return df


@dataclass
class Position:
    side: str
    entry_time: pd.Timestamp
    entry_price: float
    entry_signal: str
    tp_price: float
    sl_price: float
    be_trigger: float
    max_hold: pd.Timedelta
    atr30: float
    vwap_z: float
    trend_regime: str
    break_even_active: bool = False


def _profit_points(side: str, entry_price: float, exit_price: float) -> float:
    if side == "LONG":
        return exit_price - entry_price
    return entry_price - exit_price


def _summarize_trades(trades: pd.DataFrame) -> Dict[str, float]:
    if trades.empty:
        return {
            "trades": 0,
            "net_points": 0.0,
            "net_dollars": 0.0,
            "win_rate": np.nan,
            "avg_points": 0.0,
            "max_dd_points": 0.0,
        }

    trades = trades.copy()
    trades["cum_points"] = trades["profit_points"].cumsum()
    cummax = trades["cum_points"].cummax()
    drawdown = trades["cum_points"] - cummax
    max_dd = drawdown.min()

    wins = (trades["profit_points"] > 0).sum()
    summary = {
        "trades": len(trades),
        "net_points": trades["profit_points"].sum(),
        "net_dollars": trades["profit_dollars"].sum(),
        "win_rate": wins / len(trades) if len(trades) else np.nan,
        "avg_points": trades["profit_points"].mean(),
        "max_dd_points": max_dd,
    }
    return summary


# =============================================================================
# Núcleo del backtest
# =============================================================================
def run_backtest(
    df_ticks: pd.DataFrame,
    df_events: pd.DataFrame,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
    verbose: bool = True,
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    ticks = _slice_ticks(df_ticks, start, end)
    events = _slice_events(df_events, start, end)
    events = events[events["entry_side"].notna()].copy()

    if ticks.empty or events.empty:
        return pd.DataFrame(), _summarize_trades(pd.DataFrame())

    base = ticks.reset_index().rename(columns={"index": "timestamp"})
    base["timestamp"] = pd.to_datetime(base["timestamp"])

    events = events.sort_values("timestamp").reset_index(drop=True)
    events["timestamp"] = pd.to_datetime(events["timestamp"])

    # Agrupar señales por timestamp
    signals_by_time: Dict[pd.Timestamp, List[pd.Series]] = {}
    for _, row in events.iterrows():
        ts = row["timestamp"]
        signals_by_time.setdefault(ts, []).append(row)

    open_positions: List[Position] = []
    trades: List[Dict[str, object]] = []
    processed_signal_ids: set[int] = set()
    last_entry_time: Dict[str, pd.Timestamp | None] = {"LONG": None, "SHORT": None}

    timestamps = base["timestamp"].to_numpy()
    prices = base["price"].to_numpy()

    for i in range(len(base)):
        ts = pd.Timestamp(timestamps[i])
        price = float(prices[i])

        # ========== Gestionar posiciones abiertas ==========
        exits: List[Tuple[int, Dict[str, object]]] = []
        for idx, pos in enumerate(open_positions):
            # Break-even
            if not pos.break_even_active:
                if pos.side == "LONG" and price >= pos.entry_price + pos.be_trigger:
                    pos.sl_price = pos.entry_price
                    pos.break_even_active = True
                elif pos.side == "SHORT" and price <= pos.entry_price - pos.be_trigger:
                    pos.sl_price = pos.entry_price
                    pos.break_even_active = True

            exit_reason = None
            exit_price = price

            # TP / SL
            if pos.side == "LONG":
                if price >= pos.tp_price:
                    exit_price = pos.tp_price
                    exit_reason = "TP"
                elif price <= pos.sl_price:
                    exit_price = pos.sl_price
                    exit_reason = "SL" if pos.sl_price < pos.entry_price else "BE_STOP"
            else:  # SHORT
                if price <= pos.tp_price:
                    exit_price = pos.tp_price
                    exit_reason = "TP"
                elif price >= pos.sl_price:
                    exit_price = pos.sl_price
                    exit_reason = "SL" if pos.sl_price > pos.entry_price else "BE_STOP"

            # Time stop
            if exit_reason is None:
                if ts - pos.entry_time >= pos.max_hold:
                    exit_reason = "TIME_STOP"
                    exit_price = price

            if exit_reason is not None:
                profit_pts = _profit_points(pos.side, pos.entry_price, exit_price)
                trades.append(
                    {
                        "entry_time": pos.entry_time,
                        "exit_time": ts,
                        "entry_price": pos.entry_price,
                        "exit_price": exit_price,
                        "side": pos.side,
                        "entry_signal": pos.entry_signal,
                        "exit_reason": exit_reason,
                        "profit_points": profit_pts,
                        "profit_dollars": profit_pts * POINT_VALUE * CONTRACTS,
                        "atr30": pos.atr30,
                        "vwap_z": pos.vwap_z,
                        "trend_regime": pos.trend_regime,
                    }
                )
                exits.append((idx, trades[-1]))

        # Remove exited positions
        for idx, _ in reversed(exits):
            open_positions.pop(idx)

        # ========== Procesar nuevas señales ==========
        if ts in signals_by_time:
            for signal in signals_by_time[ts]:
                signal_idx = int(signal.name) if hasattr(signal, "name") else None
                if signal_idx is not None and signal_idx in processed_signal_ids:
                    continue

                side = signal["entry_side"]
                if side not in {"LONG", "SHORT"}:
                    continue

                # Cooldown por lado
                cooldown = (
                    D_SHAPE_RULES["cooldown_minutes"]
                    if side == "LONG"
                    else P_SHAPE_RULES["cooldown_minutes"]
                )
                last_time = last_entry_time[side]
                if last_time is not None and ts - last_time < pd.Timedelta(minutes=cooldown):
                    continue

                # Restricciones por n° de posiciones
                if len(open_positions) >= MAX_TOTAL_POSITIONS:
                    continue
                if sum(1 for pos in open_positions if pos.side == side) >= MAX_POSITIONS_PER_SIDE:
                    continue

                entry_price = float(signal["close_price"])
                if side == "LONG":
                    rules = D_SHAPE_RULES
                    tp_price = entry_price + rules["tp_points"]
                    sl_price = entry_price - rules["sl_points"]
                else:
                    rules = P_SHAPE_RULES
                    tp_price = entry_price - rules["tp_points"]
                    sl_price = entry_price + rules["sl_points"]

                pos = Position(
                    side=side,
                    entry_time=ts,
                    entry_price=entry_price,
                    entry_signal=signal["shape"],
                    tp_price=tp_price,
                    sl_price=sl_price,
                    be_trigger=rules["be_trigger"],
                    max_hold=pd.Timedelta(minutes=rules["time_stop_minutes"]),
                    atr30=float(signal["atr30_pts"]),
                    vwap_z=float(signal["vwap_z"]),
                    trend_regime=signal["trend_regime"],
                )
                open_positions.append(pos)
                last_entry_time[side] = ts
                if signal_idx is not None:
                    processed_signal_ids.add(signal_idx)

        if verbose and i % 200000 == 0:
            print(
                f"[{ts}] Tick {i:,}/{len(base):,} | Open: {len(open_positions)} | Trades: {len(trades)}"
            )

    trades_df = pd.DataFrame(trades)
    summary = _summarize_trades(trades_df)
    return trades_df, summary


# =============================================================================
# Walk-forward
# =============================================================================
def run_walk_forward(
    df_ticks: pd.DataFrame,
    df_events: pd.DataFrame,
    segments: Iterable[Tuple[str, str, str]],
) -> pd.DataFrame:
    records = []
    for label, start_str, end_str in segments:
        start = pd.Timestamp(start_str)
        end = pd.Timestamp(end_str)
        print(f"\n[Walk-forward] Segmento {label}: {start} -> {end}")
        trades, summary = run_backtest(df_ticks, df_events, start, end, verbose=False)
        summary.update({"segment": label, "start": start, "end": end})
        records.append(summary)
        if trades.empty:
            print("  Sin operaciones.")
        else:
            net = summary["net_dollars"]
            wr = summary["win_rate"] * 100 if summary["win_rate"] == summary["win_rate"] else float("nan")
            print(
                f"  Trades: {summary['trades']} | P&L: {net:,.2f} USD | Win%: {wr:.1f} | MaxDD pts: {summary['max_dd_points']:.2f}"
            )

    return pd.DataFrame(records)


# =============================================================================
# Entrypoint
# =============================================================================
def prepare_data(signals_path: Path | None = None, tns_path: Path | None = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
    signals_path = signals_path or _choose_signals_file()
    tns_path = tns_path or _choose_tns_file()

    print("Cargando señales y tape...")
    df_signals = load_signals(signals_path)
    df_ticks = load_ticks(tns_path)

    print("Construyendo barras de 1 minuto...")
    df_minute = build_minute_bars(df_ticks)

    print("Enlazando contexto a señales...")
    df_events = attach_context(df_signals, df_minute)
    df_events = _precompute_next_minute(df_minute, df_events)
    df_events = _flag_setups(df_events)

    # Guardar dataset enriquecido para depurar
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    df_events.to_csv(REPORT_DIR / "rev_events_with_filters.csv", index=False)

    return df_ticks, df_events


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest de la estrategia REV")
    parser.add_argument("--walk-forward", action="store_true", help="Ejecuta walk-forward por segmentos predefinidos")
    args = parser.parse_args()

    df_ticks, df_events = prepare_data()

    print("\n========== BACKTEST COMPLETO ==========")
    trades, summary = run_backtest(df_ticks, df_events)
    if trades.empty:
        print("No se generaron operaciones.")
        return

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    trades_path = OUTPUTS_DIR / "tracking_record_rev.csv"
    trades.to_csv(trades_path, index=False)

    win_rate_pct = summary["win_rate"] * 100 if summary["win_rate"] == summary["win_rate"] else float("nan")
    print(f"Trades totales: {summary['trades']}")
    print(f"PnL neto: {summary['net_dollars']:,.2f} USD ({summary['net_points']:.2f} pts)")
    print(f"Win rate: {win_rate_pct:.1f}% | Avg pts: {summary['avg_points']:.2f} | Max DD: {summary['max_dd_points']:.2f} pts")
    print(f"Resultados guardados en {trades_path}")

    if args.walk_forward:
        segments = [
            ("S1_2025-08-29_2025-09-05", "2025-08-29", "2025-09-05"),
            ("S2_2025-09-06_2025-09-13", "2025-09-06", "2025-09-13"),
            ("S3_2025-09-14_2025-09-21", "2025-09-14", "2025-09-21"),
            ("S4_2025-09-22_2025-09-30", "2025-09-22", "2025-09-30"),
        ]
        wf_df = run_walk_forward(df_ticks, df_events, segments)
        wf_path = REPORT_DIR / "rev_walk_forward.csv"
        wf_df.to_csv(wf_path, index=False)
        print(f"\nWalk-forward guardado en {wf_path}")


if __name__ == "__main__":
    main()
