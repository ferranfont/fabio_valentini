"""
Visualizador rápido de `rev_events_with_filters.csv`.

- Genera un HTML con tabla interactiva (Plotly Table) en `charts/rev_events_table.html`.
- Muestra en terminal un resumen compacto y las primeras filas.

Ejecución:
    python view_events.py  [--limit 100]
"""

from __future__ import annotations

import argparse
import webbrowser
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go


THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
CHARTS_DIR = PROJECT_ROOT / "charts"

DEFAULT_EVENTS_CSV = OUTPUTS_DIR / "rev_diagnostics" / "rev_events_with_filters.csv"


def load_events(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {path}")
    df = pd.read_csv(path, parse_dates=["timestamp", "minute"])
    return df


def build_table(df: pd.DataFrame, max_rows: int | None = None) -> go.Figure:
    table_df = df.copy()
    if max_rows is not None:
        table_df = table_df.head(max_rows)

    header_colors = ["rgba(30,30,30,0.9)"] * len(table_df.columns)
    cell_colors = [["rgba(245,245,245,1)"] * len(table_df) for _ in table_df.columns]

    fig = go.Figure(
        data=[
            go.Table(
                header=dict(
                    values=[f"<b>{c}</b>" for c in table_df.columns],
                    fill_color=header_colors,
                    font=dict(color="white", size=12),
                    align="left",
                ),
                cells=dict(
                    values=[table_df[col] for col in table_df.columns],
                    fill_color=cell_colors,
                    align="left",
                    height=24,
                ),
            )
        ]
    )

    fig.update_layout(
        template="plotly_white",
        width=1600,
        height=900,
        margin=dict(l=30, r=30, t=40, b=30),
        title="rev_events_with_filters.csv",
    )
    return fig


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualizador de eventos REV")
    parser.add_argument("--csv", type=str, default=str(DEFAULT_EVENTS_CSV), help="Ruta al CSV de eventos")
    parser.add_argument("--limit", type=int, default=None, help="Número máximo de filas a mostrar (HTML/terminal)")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    df = load_events(csv_path)

    row_count = len(df)
    print(f"[OK] {row_count} filas cargadas desde {csv_path}")
    print(f"Columnas ({len(df.columns)}): {', '.join(df.columns)}\n")

    preview_rows = args.limit or 20
    preview = df.head(preview_rows)
    print("=== Preview (primeras filas) ===")
    print(preview.to_string(index=False))
    print()

    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    fig = build_table(df, max_rows=args.limit)
    output_html = CHARTS_DIR / "rev_events_table.html"
    fig.write_html(output_html)
    print(f"[OK] Tabla HTML guardada en {output_html}")
    webbrowser.open(output_html.as_uri())


if __name__ == "__main__":
    main()

