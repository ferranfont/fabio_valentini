"""
Visualización de trades para estrategia d-Shape & p-Shape Absorption
usando como SERIE BASE **todos los eventos** del fichero:
    data/time_and_sales_nq.csv (FULL DAY)
(semicolumnas y coma decimal)

Lee:
  • outputs/tracking_record_absortion_shape_all_day.csv  (trades TODO EL DÍA)
  • outputs/db_shapes_20251024_003251.csv               (señales d/p-shape TODO EL DÍA)
  • data/time_and_sales_nq.csv                          (precio base COMPLETO)

Guarda:
  • charts/trades_visualization_absortion_shape_all_day.html

MODOS DE VISUALIZACIÓN:
========================
1. TODO EL DÍA (recomendado):
   - Cambiar USE_INDEX_RANGE = False
   - Muestra TODOS los 5,367 trades del día completo (9:00h - 22:00h+)

2. RANGO DE ÍNDICES:
   - Cambiar USE_INDEX_RANGE = True
   - Ajustar DEFAULT_START_INDEX y DEFAULT_END_INDEX
   - Ejemplo: 0 a 50 para ver solo los primeros 50 trades

Características Visuales:
- NO muestra señales d-shape/p-shape (solo trades ejecutados)
- ENTRADAS: Triangle-up verde (LONG), Triangle-down rojo (SHORT)
- SALIDAS TARGET: Cuadrado sin relleno VERDE + línea discontinua verde
- SALIDAS STOP: Cuadrado sin relleno ROJO + línea discontinua roja
- Solo GRID horizontal (sin grid vertical)
- Equity: Área verde sin línea (sin outliers)
"""

import webbrowser
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots

# ============================================================
# RUTAS (helpers del proyecto)
# ============================================================
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import CHART_WIDTH, CHART_HEIGHT, SYMBOL
from path_helper import get_output_path, get_charts_path

try:
    from path_helper import get_data_path  # opcional
except Exception:
    get_data_path = None

TRADES_FILE = get_output_path("tracking_record_absortion_shape_all_day.csv")
SIGNALS_FILE = get_output_path("db_shapes_20251024_003251.csv")
if get_data_path:
    BASE_TNS_FILE = get_data_path("time_and_sales_nq.csv")
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    BASE_TNS_FILE = PROJECT_ROOT / "data" / "time_and_sales_nq.csv"

OUTPUT_HTML = get_charts_path("trades_visualization_absortion_shape_all_day.html")

# ============================================================
# CONFIGURACIÓN DE VISUALIZACIÓN
# ============================================================
# Set USE_INDEX_RANGE to True to limit trades by index range
# Set USE_INDEX_RANGE to False to show ALL trades
USE_INDEX_RANGE = False

DEFAULT_START_INDEX = 0
DEFAULT_END_INDEX = 50  # Only used if USE_INDEX_RANGE = True


# ============================================================
# UTILIDADES
# ============================================================
def _read_csv_semicolon_decimal(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep=";", decimal=",", dtype=str, keep_default_na=False, engine="python")


def _to_float(s: pd.Series) -> pd.Series:
    return (
        s.astype(str)
         .str.replace(".", "", regex=False)   # separador de miles europeo
         .str.replace(",", ".", regex=False)  # coma -> punto
         .replace({"": None})
         .astype(float)
    )


# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================
def plot_trades_on_chart(start_idx: int = DEFAULT_START_INDEX, end_idx: int = DEFAULT_END_INDEX) -> None:
    print("\n" + "=" * 70)

    # Check if we should use index range or show all
    if USE_INDEX_RANGE:
        print(f"VISUALIZACIÓN DE TRADES — Índices {start_idx} a {end_idx}")
    else:
        print(f"VISUALIZACIÓN DE TRADES — TODO EL DÍA")

    print("=" * 70 + "\n")

    # --------- Cargar TRADES ----------
    if not Path(TRADES_FILE).exists():
        raise FileNotFoundError(f"No se encuentra el archivo de trades: {TRADES_FILE}")

    df_trades = _read_csv_semicolon_decimal(Path(TRADES_FILE))
    df_trades.columns = df_trades.columns.str.strip().str.lower()

    df_trades["entry_time"] = pd.to_datetime(df_trades["entry_time"])
    df_trades["exit_time"] = pd.to_datetime(df_trades["exit_time"])
    for c in ("entry_price", "exit_price", "profit_dollars"):
        df_trades[c] = _to_float(df_trades[c])

    print(f"  Total trades en archivo: {len(df_trades):,}")

    # Apply index range filter ONLY if USE_INDEX_RANGE is True
    if USE_INDEX_RANGE:
        df_trades = df_trades.iloc[start_idx:end_idx].copy()
        print(f"  Trades a visualizar (rango {start_idx}-{end_idx}): {len(df_trades):,}")
    else:
        # Show ALL trades
        print(f"  Trades a visualizar (TODOS): {len(df_trades):,}")

    if df_trades.empty:
        print("No hay trades en el rango especificado.")
        return

    # --------- Cargar SEÑALES ----------
    if not Path(SIGNALS_FILE).exists():
        raise FileNotFoundError(f"No se encuentra el archivo de señales: {SIGNALS_FILE}")

    df_signals = _read_csv_semicolon_decimal(Path(SIGNALS_FILE))
    df_signals.columns = df_signals.columns.str.strip().str.lower()
    df_signals["timestamp"]   = pd.to_datetime(df_signals["timestamp"])
    df_signals["close_price"] = _to_float(df_signals["close_price"])
    df_signals["shape"]       = df_signals["shape"].str.strip().str.lower()

    # --------- Cargar SERIE BASE (TODOS los eventos) ----------
    if not Path(BASE_TNS_FILE).exists():
        raise FileNotFoundError(f"No se encuentra el fichero base de T&S: {BASE_TNS_FILE}")

    base = _read_csv_semicolon_decimal(Path(BASE_TNS_FILE))
    base.columns = base.columns.str.strip()

    ts_col = next((c for c in base.columns if c.lower().startswith("timestamp")), "Timestamp")
    px_col = next((c for c in base.columns if c.lower().startswith("precio")), "Precio")

    base[ts_col] = pd.to_datetime(base[ts_col])
    base[px_col] = _to_float(base[px_col])

    # ---- Ventana temporal basada en trades seleccionados ----
    time_start = df_trades["entry_time"].min() - pd.Timedelta(minutes=5)
    time_end   = df_trades["exit_time"].max()  + pd.Timedelta(minutes=5)

    base_win = base[(base[ts_col] >= time_start) & (base[ts_col] <= time_end)].copy()
    sig_win  = df_signals[(df_signals["timestamp"] >= time_start) & (df_signals["timestamp"] <= time_end)].copy()

    print(f"\nSerie base T&S en ventana: {len(base_win):,} filas")
    print(f"Señales en ventana: {len(sig_win):,}")
    print(f"Ventana: {time_start} — {time_end}")

    # ========================================================
    # PLOT
    # ========================================================
    fig = make_subplots(
        rows=2,
        cols=1,
        row_heights=[0.7, 0.3],
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=("", "P&L Acumulado"),  # Sin subtítulo en el panel superior
    )

    # Panel 1: Precio base T&S
    fig.add_trace(
        go.Scatter(
            x=base_win[ts_col],
            y=base_win[px_col],
            mode="lines",
            line=dict(width=1),
            opacity=0.7,
            name="Precio (T&S)",
            hovertemplate="<b>%{x}</b><br>Precio: %{y:.2f}<extra></extra>",
        ),
        row=1, col=1
    )

    # NO mostrar señales d_shape / p_shape (comentado)
    # df_d = sig_win[sig_win["shape"].eq("d_shape")]
    # df_p = sig_win[sig_win["shape"].eq("p_shape")]

    # Entradas/salidas con REGLA: cierre = triángulo opuesto a la dirección de entrada
    for _, tr in df_trades.iterrows():
        side = tr["side"].upper()
        entry_t, exit_t = tr["entry_time"], tr["exit_time"]
        entry_px, exit_px = tr["entry_price"], tr["exit_price"]
        pl = tr["profit_dollars"]
        reason = tr.get("exit_reason", "")

        entry_symbol = "triangle-up" if side == "LONG" else "triangle-down"
        entry_color  = "green" if side == "LONG" else "red"

        fig.add_trace(
            go.Scatter(
                x=[entry_t], y=[entry_px],
                mode="markers",
                marker=dict(
                    symbol=entry_symbol,
                    size=11,
                    color=entry_color,
                    line=dict(width=2, color=entry_color)  # Contorno del mismo color: verde para LONG, rojo para SHORT
                ),
                name=f"{side} Entry",
                showlegend=False,
                hovertemplate=f"<b>ENTRY {side}</b><br>%{{x}}<br>Precio: %{{y:.2f}}<extra></extra>",
            ),
            row=1, col=1
        )

        # Salida: cuadrado sin relleno
        # Verde si TARGET, Rojo si STOP
        if reason.upper() == "TARGET":
            exit_color = "green"
            line_color = "green"
        else:  # STOP
            exit_color = "red"
            line_color = "red"

        # Cuadrado sin relleno (square-open)
        fig.add_trace(
            go.Scatter(
                x=[exit_t], y=[exit_px],
                mode="markers+text",
                marker=dict(
                    symbol="square-open",  # cuadrado sin relleno
                    size=10,
                    color=exit_color,
                    line=dict(width=2, color=exit_color)
                ),
                text=[f"${pl:.0f}"],
                textposition="top center",
                textfont=dict(size=9, color=exit_color),
                name=f"{side} Exit {reason}",
                showlegend=False,
                hovertemplate=f"<b>EXIT {reason}</b><br>%{{x}}<br>Precio: %{{y:.2f}}<br>P/L: ${pl:.2f}<extra></extra>",
            ),
            row=1, col=1
        )

        # Línea conectando entrada y salida (color según exit_reason)
        fig.add_trace(
            go.Scatter(
                x=[entry_t, exit_t],
                y=[entry_px, exit_px],
                mode="lines",
                line=dict(width=1, dash="dot", color=line_color),  # dot (puntos pequeños), color según reason
                opacity=0.3,  # Mayor transparencia para que no moleste
                showlegend=False,
                hoverinfo="skip",
            ),
            row=1, col=1
        )

    # Panel 2: P&L acumulado (SOLO área verde, sin línea)
    df_trades = df_trades.sort_values("exit_time").reset_index(drop=True)
    df_trades["cumulative_pnl"] = df_trades["profit_dollars"].cumsum()

    fig.add_trace(
        go.Scatter(
            x=df_trades["exit_time"],
            y=df_trades["cumulative_pnl"],
            mode="lines",
            line=dict(width=0, color="rgba(0,0,0,0)"),   # sin línea visible
            fill="tozeroy",
            fillcolor="rgba(0, 200, 0, 0.20)",          # solo área verde
            name="P&L Acumulado",
            hovertemplate="<b>%{x}</b><br>P&L: $%{y:.2f}<extra></extra>",
        ),
        row=2, col=1
    )

    # ===== Layout: SOLO GRID HORIZONTAL =====
    fig.update_xaxes(showgrid=False, row=1, col=1)
    fig.update_xaxes(showgrid=False, row=2, col=1)
    fig.update_yaxes(showgrid=True, gridcolor="rgba(0,0,0,0.08)", row=1, col=1)
    fig.update_yaxes(showgrid=True, gridcolor="rgba(0,0,0,0.08)", row=2, col=1)

    # Title: Show index range or "ALL DAY" based on USE_INDEX_RANGE flag
    if USE_INDEX_RANGE:
        title_text = f"{SYMBOL} — Trades d-Shape & p-Shape (T&S completo) idx {start_idx}-{end_idx}"
    else:
        title_text = f"{SYMBOL} — Trades d-Shape & p-Shape (T&S completo) TODO EL DÍA ({len(df_trades)} trades)"

    fig.update_layout(
        title=title_text,
        width=CHART_WIDTH if isinstance(CHART_WIDTH, int) else None,
        height=CHART_HEIGHT if isinstance(CHART_HEIGHT, int) else 900,
        showlegend=True,
        hovermode="closest",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    # Guardar y abrir
    Path(OUTPUT_HTML).parent.mkdir(parents=True, exist_ok=True)
    print(f"\nGuardando gráfico en: {OUTPUT_HTML}")
    fig.write_html(str(OUTPUT_HTML))

    print("Abriendo en el navegador...")
    try:
        webbrowser.open(str(OUTPUT_HTML))
    except Exception:
        pass

    print("\n¡Gráfico generado correctamente!")
    print("=" * 70)


if __name__ == "__main__":
    plot_trades_on_chart(start_idx=DEFAULT_START_INDEX, end_idx=DEFAULT_END_INDEX)
