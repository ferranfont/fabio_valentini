"""
Visualización de entradas/salidas del backtest REV.

Genera un HTML interactivo (`charts/rev_trades.html`) con:
- Precio resampleado a 1 minuto.
- Marcadores de entrada (verde para long, rojo para short).
- Marcadores de salida coloreados por razón (TP/SL/BE).
- Líneas conectando entrada y salida.

Uso:
    python plot_rev_trades.py
    python plot_rev_trades.py --trades <csv> --tape <csv>
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
CHARTS_DIR = PROJECT_ROOT / "charts"

DEFAULT_TRADES = OUTPUTS_DIR / "tracking_record_rev.csv"
DEFAULT_TAPE = PROJECT_ROOT / "data" / "time_and_sales_20251031_074530.csv"


def read_trades(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"No se encuentra el archivo de trades: {path}")
    df = pd.read_csv(path, parse_dates=["entry_time", "exit_time"])
    if df.empty:
        raise ValueError("El CSV de trades está vacío.")
    df["id"] = range(len(df))
    return df


def build_price_series(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"No se encuentra el tape: {path}")
    df = pd.read_csv(path, sep=";", decimal=",")
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    df = df.set_index("Timestamp")
    price = df["Precio"].resample("1min").last().dropna()
    return price.reset_index().rename(columns={"Timestamp": "timestamp", "Precio": "price"})


def make_plot(price_df: pd.DataFrame, trades: pd.DataFrame) -> go.Figure:
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=price_df["timestamp"],
            y=price_df["price"],
            mode="lines",
            line=dict(color="royalblue", width=1.2),
            name="Precio (1min)",
        )
    )

    entry_colors = {"LONG": "green", "SHORT": "firebrick"}
    for side, color in entry_colors.items():
        subset = trades[trades["side"] == side]
        if subset.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=subset["entry_time"],
                y=subset["entry_price"],
                mode="markers",
                marker=dict(color=color, size=9, symbol="triangle-up"),
                name=f"Entrada {side}",
                customdata=subset["id"],
                hovertemplate=(
                    f"<b>Entrada {side}</b><br>"
                    "Id: %{customdata}<br>"
                    "Hora: %{x}<br>"
                    "Precio: %{y:.2f}<extra></extra>"
                ),
            )
        )

    exit_colors = {"TP": "mediumseagreen", "SL": "red", "BE_STOP": "gray", "TIME_STOP": "orange", "END_OF_DATA": "black"}
    for reason, group in trades.groupby("exit_reason"):
        color = exit_colors.get(reason, "purple")
        fig.add_trace(
            go.Scatter(
                x=group["exit_time"],
                y=group["exit_price"],
                mode="markers",
                marker=dict(color=color, size=8, symbol="x"),
                name=f"Salida {reason}",
                customdata=group[["id", "profit_points"]],
                hovertemplate=(
                    "<b>Salida " + reason + "</b><br>"
                    "Id: %{customdata[0]}<br>"
                    "Hora: %{x}<br>"
                    "Precio: %{y:.2f}<br>"
                    "PnL pts: %{customdata[1]:.2f}<extra></extra>"
                ),
            )
        )

    # Líneas de trade
    for _, row in trades.iterrows():
        fig.add_trace(
            go.Scatter(
                x=[row["entry_time"], row["exit_time"]],
                y=[row["entry_price"], row["exit_price"]],
                mode="lines",
                line=dict(color="rgba(0,0,0,0.25)", width=1, dash="dot"),
                showlegend=False,
                hoverinfo="skip",
            )
        )

    fig.update_layout(
        title="Estrategia REV - Entradas y Salidas",
        xaxis_title="Tiempo",
        yaxis_title="Precio",
        template="plotly_white",
        width=1600,
        height=900,
        legend=dict(orientation="h", x=0.5, y=-0.1, xanchor="center"),
        hovermode="x unified",
    )

    return fig


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualización de trades REV")
    parser.add_argument("--trades", type=str, default=str(DEFAULT_TRADES), help="CSV de trades")
    parser.add_argument("--tape", type=str, default=str(DEFAULT_TAPE), help="CSV de T&S usado en el backtest")
    args = parser.parse_args()

    trades = read_trades(Path(args.trades))
    price_df = build_price_series(Path(args.tape))
    fig = make_plot(price_df, trades)

    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = CHARTS_DIR / "rev_trades.html"
    fig.write_html(output_path)
    print(f"[OK] Visualización guardada en {output_path}")


if __name__ == "__main__":
    main()

