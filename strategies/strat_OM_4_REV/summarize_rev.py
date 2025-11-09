"""
Resumen del backtest REV.

- Lee `outputs/tracking_record_rev.csv`.
- Imprime métricas globales y tablas por lado / razón de salida / hora.
- Opcional: exporta CSV con estadísticas agregadas.

Uso:
    python summarize_rev.py [--trades outputs/tracking_record_rev.csv]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]
DEFAULT_TRADES = PROJECT_ROOT / "outputs" / "tracking_record_rev.csv"
SUMMARY_DIR = PROJECT_ROOT / "outputs" / "rev_diagnostics"


def load_trades(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de trades: {path}")
    df = pd.read_csv(path, parse_dates=["entry_time", "exit_time"])
    if df.empty:
        raise ValueError(f"El archivo {path} no contiene trades.")
    return df


def compute_overall(df: pd.DataFrame) -> pd.Series:
    total_pts = df["profit_points"].sum()
    total_usd = df["profit_dollars"].sum()
    wins = (df["profit_points"] > 0).sum()
    losses = (df["profit_points"] < 0).sum()
    break_evens = len(df) - wins - losses
    wr = wins / len(df)
    avg_pts = df["profit_points"].mean()
    std_pts = df["profit_points"].std(ddof=1)
    pf = df.loc[df["profit_points"] > 0, "profit_points"].sum() / abs(
        df.loc[df["profit_points"] < 0, "profit_points"].sum()
    )
    # equity curve for DD
    equity = df["profit_points"].cumsum()
    drawdown = equity - equity.cummax()
    max_dd = drawdown.min()
    expectancy = total_pts / len(df)

    return pd.Series(
        {
            "trades": len(df),
            "wins": wins,
            "losses": losses,
            "break_evens": break_evens,
            "win_rate_pct": wr * 100,
            "net_points": total_pts,
            "net_usd": total_usd,
            "avg_points": avg_pts,
            "std_points": std_pts,
            "expectancy_pts": expectancy,
            "profit_factor": pf,
            "max_drawdown_pts": max_dd,
        }
    )


def display_table(title: str, df: pd.DataFrame) -> None:
    print(f"\n=== {title} ===")
    if df.empty:
        print("Sin datos.")
        return
    print(df.to_string(index=True))


def main() -> None:
    parser = argparse.ArgumentParser(description="Resumen de trades REV")
    parser.add_argument("--trades", type=str, default=str(DEFAULT_TRADES), help="Ruta al CSV de trades")
    parser.add_argument("--export", action="store_true", help="Exporta tablas de resumen a CSV")
    args = parser.parse_args()

    trades_path = Path(args.trades)
    trades = load_trades(trades_path)

    overall = compute_overall(trades)
    print("Resumen general:")
    print(overall.round(2).to_string())

    by_side = (
        trades.groupby("side")["profit_points"]
        .agg(["count", "sum", "mean", "std"])
        .rename(columns={"sum": "net_points", "mean": "avg_points", "std": "std_points"})
    )
    display_table("Resultados por lado", by_side.round(2))

    by_reason = (
        trades.groupby("exit_reason")["profit_points"]
        .agg(["count", "sum", "mean"])
        .rename(columns={"sum": "net_points", "mean": "avg_points"})
        .sort_values("count", ascending=False)
    )
    display_table("Resultados por razón de salida", by_reason.round(2))

    trades["entry_hour"] = trades["entry_time"].dt.hour
    by_hour = (
        trades.groupby("entry_hour")["profit_points"]
        .agg(["count", "sum", "mean"])
        .rename(columns={"sum": "net_points", "mean": "avg_points"})
        .sort_index()
    )
    display_table("Resultados por hora de entrada", by_hour.round(2))

    by_signal = (
        trades.groupby("entry_signal")["profit_points"]
        .agg(["count", "sum", "mean"])
        .rename(columns={"sum": "net_points", "mean": "avg_points"})
    )
    display_table("Resultados por tipo de señal", by_signal.round(2))

    if args.export:
        SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
        by_side.to_csv(SUMMARY_DIR / "rev_summary_by_side.csv")
        by_reason.to_csv(SUMMARY_DIR / "rev_summary_by_exit.csv")
        by_hour.to_csv(SUMMARY_DIR / "rev_summary_by_hour.csv")
        by_signal.to_csv(SUMMARY_DIR / "rev_summary_by_signal.csv")
        print(f"\n[OK] Tablas exportadas en {SUMMARY_DIR}")


if __name__ == "__main__":
    main()

