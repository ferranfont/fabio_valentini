"""
Visualización de trades para estrategia BIN FREQUENCY REVERSAL
usando como SERIE BASE **todos los eventos** del fichero:
    data/historic/time_and_sales_nq_20251022.csv (FULL DAY)
(semicolumnas y coma decimal)

Lee:
  • outputs/sweep/bins_TR_20251022.csv           (trades ejecutados)
  • outputs/sweep/bins_signals_temp.csv          (señales de bins)
  • data/historic/time_and_sales_nq_20251022.csv (precio base COMPLETO)
  • strat_sweep/db_mushroom_all_data.csv         (indicador naranja continuo)

Guarda:
  • charts/trades_visualization_bins_20251022.html

MODOS DE VISUALIZACIÓN:
========================
1. TODO EL DÍA (recomendado):
   - Cambiar USE_INDEX_RANGE = False
   - Muestra TODOS los trades del día completo (9:00h - 22:00h+)

2. RANGO DE ÍNDICES:
   - Cambiar USE_INDEX_RANGE = True
   - Ajustar DEFAULT_START_INDEX y DEFAULT_END_INDEX
   - Ejemplo: 0 a 50 para ver solo los primeros 50 trades

Características Visuales:
- Muestra señales bin (dots) en el gráfico
- ENTRADAS: Triángulos (verde=LONG, rojo=SHORT)
- SALIDAS TARGET: Cuadrado sin relleno VERDE + línea discontinua verde
- SALIDAS STOP: Cuadrado sin relleno ROJO + línea discontinua roja
- Indicador naranja continuo (bin frequency rolling)
- BINS START: Línea vertical naranja (width=1, alpha=0.5) + círculo naranja relleno
- BINS END: Línea vertical naranja (width=1, alpha=0.5) + círculo naranja hueco
- SMA200: Línea verde fina (width=1, opacity=0.5)
- Solo GRID horizontal (sin grid vertical)
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
from config import CHART_WIDTH, CHART_HEIGHT

# Default paths for bins strategy
PROJECT_ROOT = Path(__file__).resolve().parents[2]
STRAT_SWEEP_DIR = PROJECT_ROOT / "strat_sweep"
OUTPUTS_SWEEP_DIR = PROJECT_ROOT / "outputs" / "sweep"
CHARTS_DIR = PROJECT_ROOT / "charts"

TRADES_FILE = OUTPUTS_SWEEP_DIR / "bins_TR_20251022.csv"
SIGNALS_FILE = OUTPUTS_SWEEP_DIR / "bins_signals_temp.csv"  # Created by main_strat_bins.py
BASE_TNS_FILE = PROJECT_ROOT / "data" / "historic" / "time_and_sales_nq_20251022.csv"
OUTPUT_HTML = CHARTS_DIR / "trades_visualization_bins_20251022.html"

SYMBOL = "NQ - BIN REVERSAL (UP->SHORT, DOWN->LONG)"

# ============================================================
# CONFIGURACIÓN DE VISUALIZACIÓN
# ============================================================
# Set USE_INDEX_RANGE to True to limit trades by index range
# Set USE_INDEX_RANGE to False to show ALL trades
USE_INDEX_RANGE = False

DEFAULT_START_INDEX = 0
DEFAULT_END_INDEX = 50  # Only used if USE_INDEX_RANGE = True
EMA_PERIOD = 200


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
    if "signal_close_price" in df_trades.columns:
        df_trades["signal_close_price"] = _to_float(df_trades["signal_close_price"])
    if "visual_side" in df_trades.columns:
        df_trades["visual_side"] = (
            df_trades["visual_side"]
            .astype(str)
            .str.strip()
            .str.upper()
            .replace({"": None})
        )

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

    if "timestamp" not in df_signals.columns or "close_price" not in df_signals.columns:
        raise ValueError("El archivo de señales debe contener 'timestamp' y 'close_price'")

    df_signals["timestamp"] = pd.to_datetime(df_signals["timestamp"]).dt.floor("s")
    df_signals["close_price"] = _to_float(df_signals["close_price"])

    if "mushroom" in df_signals.columns:
        df_signals["mushroom"] = (
            df_signals["mushroom"]
            .astype(str)
            .str.strip()
            .str.lower()
            .isin({"true", "1", "yes", "y"})
        )
        df_signals = df_signals[df_signals["mushroom"]]

    if "shape" in df_signals.columns:
        df_signals["shape"] = df_signals["shape"].str.strip().str.lower()
    else:
        df_signals["shape"] = "mushroom_short"

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
    # LOAD BIN FREQUENCY DATA (CONTINUOUS INDICATOR)
    # ========================================================
    # Load continuous frequency indicator from db_mushroom_all_data.csv
    bins_continuous = None
    try:
        PROJECT_ROOT = Path(__file__).resolve().parents[2]
        BINS_ALL_DATA_FILE = PROJECT_ROOT / "strat_sweep" / "db_mushroom_all_data.csv"

        if BINS_ALL_DATA_FILE.exists():
            print(f"[INFO] Loading continuous bin frequency from: {BINS_ALL_DATA_FILE.name}")

            # Load full resampled data
            df_all = pd.read_csv(BINS_ALL_DATA_FILE, sep=';', decimal=',')
            df_all.columns = df_all.columns.str.strip()
            df_all['timestamp'] = pd.to_datetime(df_all['timestamp'])

            # Convert numeric columns (European format)
            df_all['close_price'] = df_all['close_price'].astype(str).str.replace(',', '.').astype(float)
            df_all['total_bid'] = df_all['total_bid'].fillna(0).astype(str).str.replace(',', '.').astype(float)
            df_all['total_ask'] = df_all['total_ask'].fillna(0).astype(str).str.replace(',', '.').astype(float)

            # Calculate rolling frequency (same as plot_resample_sweep.py)
            VOLUME_THRESHOLD = 50
            BIN_SIZE = 10
            window_frames = int(BIN_SIZE / 0.5)  # 10s / 0.5s = 20 frames

            df_all['is_bid_signal'] = (df_all['total_bid'] > VOLUME_THRESHOLD).astype(int)
            df_all['is_ask_signal'] = (df_all['total_ask'] > VOLUME_THRESHOLD).astype(int)
            df_all['freq_bid_rolling'] = df_all['is_bid_signal'].rolling(window=window_frames, min_periods=1).sum()
            df_all['freq_ask_rolling'] = df_all['is_ask_signal'].rolling(window=window_frames, min_periods=1).sum()
            df_all['freq_total_rolling'] = df_all['freq_bid_rolling'] + df_all['freq_ask_rolling']

            # Filter to time window
            bins_continuous = df_all[(df_all['timestamp'] >= time_start) & (df_all['timestamp'] <= time_end)].copy()
            print(f"[OK] Continuous bin frequency loaded: {len(bins_continuous):,} frames (max freq: {bins_continuous['freq_total_rolling'].max():.0f})")
        else:
            print(f"[WARN] {BINS_ALL_DATA_FILE} not found - bin indicator will not be shown")
    except Exception as e:
        print(f"[ERROR] Could not load continuous bin frequency data: {e}")
        import traceback
        traceback.print_exc()

    # ========================================================
    # PLOT (with secondary Y-axis for bin frequency)
    # ========================================================
    fig = make_subplots(rows=1, cols=1, specs=[[{"secondary_y": True}]])

    # Precio base T&S (línea azul) - PRIMARY Y-AXIS
    fig.add_trace(
        go.Scatter(
            x=base_win[ts_col],
            y=base_win[px_col],
            mode="lines",
            line=dict(width=1, color='blue'),
            opacity=0.7,
            name="Precio (T&S)",
            hovertemplate="<b>%{x}</b><br>Precio: %{y:.2f}<extra></extra>",
        ),
        secondary_y=False
    )

    ema_series = None
    ema_lookup = None
    if EMA_PERIOD:
        ema_series = base_win[px_col].rolling(window=EMA_PERIOD, min_periods=1).mean()
        fig.add_trace(
            go.Scatter(
                x=base_win[ts_col],
                y=ema_series,
                mode="lines",
                line=dict(width=1, color='green'),
                opacity=0.5,
                name=f"SMA {EMA_PERIOD}",
                hovertemplate="<b>SMA</b><br>%{x}<br>Valor: %{y:.2f}<extra></extra>",
            ),
            secondary_y=False
        )
        ema_lookup = (
            pd.DataFrame(
                {
                    "timestamp": base_win[ts_col].values,
                    "ema": ema_series.values,
                }
            )
            .dropna(subset=["ema"])
            .sort_values("timestamp")
        )

    if ema_lookup is not None and not df_trades.empty:
        trades_for_merge = df_trades.sort_values("entry_time").copy()
        trades_for_merge = pd.merge_asof(
            trades_for_merge,
            ema_lookup,
            left_on="entry_time",
            right_on="timestamp",
            direction="backward",
        )
        trades_for_merge.rename(columns={"ema": "ema_at_entry"}, inplace=True)
        trades_for_merge.drop(columns=["timestamp"], inplace=True)
        df_trades = trades_for_merge
    else:
        df_trades = df_trades.copy()
        df_trades["ema_at_entry"] = None

    # Entradas/salidas con triángulos para las entradas (ventas) y cuadrados para salidas
    for _, tr in df_trades.iterrows():
        actual_side = str(tr["side"]).upper()
        visual_override = str(tr.get("visual_side", "") or "").upper()
        ema_value = tr.get("ema_at_entry")
        entry_t, exit_t = tr["entry_time"], tr["exit_time"]
        entry_px, exit_px = tr["entry_price"], tr["exit_price"]
        pl = tr["profit_dollars"]
        reason = tr.get("exit_reason", "")

        ref_price = tr.get("signal_close_price", entry_px)
        if ref_price is None or pd.isna(ref_price):
            ref_price = entry_px

        if visual_override in ("LONG", "SHORT"):
            visual_side = visual_override
        elif ema_value is not None and not pd.isna(ema_value):
            visual_side = "LONG" if ref_price >= ema_value else "SHORT"
        else:
            visual_side = actual_side

        entry_symbol = "triangle-up" if visual_side == "LONG" else "triangle-down"
        entry_color = "green" if visual_side == "LONG" else "red"
        fig.add_trace(
            go.Scatter(
                x=[entry_t], y=[entry_px],
                mode="markers",
                marker=dict(
                    symbol=entry_symbol,
                    size=12,
                    color=entry_color,
                    line=dict(width=1, color="black"),
                ),
                name=f"{visual_side} Entry",
                showlegend=False,
                hovertemplate=f"<b>{visual_side} ENTRY</b><br>%{{x}}<br>Precio: %{{y:.2f}}<extra></extra>",
            ),
            secondary_y=False
        )

        # Salida: cuadrado sin relleno
        # Verde si TARGET, Rojo si STOP
        if pl >= 0:
            exit_color = "green"
        else:
            exit_color = "red"
        line_color = "lightgrey"
        is_short = visual_side == "SHORT"
        connector_line = dict(width=1, dash="dot", color=line_color)
        connector_opacity = 0.3
        if is_short:
            connector_line = dict(
                width=1.5,
                dash="solid",
                color="rgba(180, 180, 180, 0.55)",
            )
            connector_opacity = 1.0  # keep alpha via RGBA so it stays visible for shorts

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
                name=f"{visual_side} Exit {reason}",
                showlegend=False,
                hovertemplate=f"<b>EXIT {reason}</b><br>%{{x}}<br>Precio: %{{y:.2f}}<br>P/L: ${pl:.2f}<extra></extra>",
            ),
            secondary_y=False
        )

        # Línea conectando entrada y salida (siempre visible para cortos incluso con TARGET/STOP)
        fig.add_trace(
            go.Scatter(
                x=[entry_t, exit_t],
                y=[entry_px, exit_px],
                mode="lines",
                line=connector_line,
                opacity=connector_opacity,
                showlegend=False,
                hoverinfo="skip",
            ),
            secondary_y=False
        )

    # ========================================================
    # BIN FREQUENCY INDICATOR (SECONDARY Y-AXIS - RIGHT)
    # ========================================================
    if bins_continuous is not None and not bins_continuous.empty:
        fig.add_trace(
            go.Scatter(
                x=bins_continuous["timestamp"],  # Continuous timestamps
                y=bins_continuous["freq_total_rolling"],  # Continuous rolling frequency
                mode="lines",
                name=f"Volume Frequency (Rolling 10s)",
                line=dict(color="orange", width=2),  # Smooth line (no steps)
                fill="tozeroy",
                fillcolor="rgba(255,165,0,0.1)",
                hovertemplate="<b>Bin Frequency</b><br>%{x}<br>Freq: %{y:.0f}<extra></extra>",
            ),
            secondary_y=True
        )

    # ========================================================
    # ADD VERTICAL ORANGE LINES AT BIN PEAKS + MARKERS
    # ========================================================
    # Load bin peaks from db_mushroom_bins.csv
    shapes = []
    bin_start_times = []
    bin_start_freqs = []
    bin_end_times = []
    bin_end_freqs = []

    try:
        BINS_FILE = PROJECT_ROOT / "strat_sweep" / "db_mushroom_bins.csv"
        if BINS_FILE.exists():
            print(f"[INFO] Loading bin peaks for vertical lines from: {BINS_FILE.name}")
            df_bins = pd.read_csv(BINS_FILE, sep=';', decimal=',')
            df_bins['peak_timestamp'] = pd.to_datetime(df_bins['peak_timestamp'])
            df_bins['signal_timestamp'] = pd.to_datetime(df_bins['signal_timestamp'])

            # Convert frequency columns (European format)
            df_bins['peak_freq'] = df_bins['peak_freq'].astype(str).str.replace(',', '.').astype(float)

            # Filter to time window
            bins_in_window = df_bins[
                (df_bins['peak_timestamp'] >= time_start) &
                (df_bins['peak_timestamp'] <= time_end)
            ]

            print(f"[INFO] Adding {len(bins_in_window)} bin markers (start/end) and vertical lines")

            # Collect bin start/end positions for scatter markers
            for _, bin_row in bins_in_window.iterrows():
                peak_time = bin_row['peak_timestamp']
                signal_time = bin_row['signal_timestamp']
                peak_freq = bin_row['peak_freq']

                # Store peak (start) marker positions
                bin_start_times.append(peak_time)
                bin_start_freqs.append(peak_freq)

                # Find frequency at signal_timestamp (end) by looking up in bins_continuous
                if bins_continuous is not None:
                    signal_freq_row = bins_continuous[bins_continuous['timestamp'] == signal_time]
                    if not signal_freq_row.empty:
                        signal_freq = signal_freq_row['freq_total_rolling'].iloc[0]
                    else:
                        # If exact timestamp not found, use nearest
                        idx = (bins_continuous['timestamp'] - signal_time).abs().idxmin()
                        signal_freq = bins_continuous.loc[idx, 'freq_total_rolling']

                    bin_end_times.append(signal_time)
                    bin_end_freqs.append(signal_freq)

                # Add vertical orange line at peak_timestamp (bin START)
                shapes.append(
                    dict(
                        type='line',
                        x0=peak_time,
                        x1=peak_time,
                        y0=0,
                        y1=1,
                        yref='paper',
                        line=dict(color='rgba(255,165,0,0.5)', width=1),
                        layer='below'
                    )
                )

                # Add vertical orange line at signal_timestamp (bin END)
                shapes.append(
                    dict(
                        type='line',
                        x0=signal_time,
                        x1=signal_time,
                        y0=0,
                        y1=1,
                        yref='paper',
                        line=dict(color='rgba(255,165,0,0.5)', width=1),
                        layer='below'
                    )
                )
        else:
            print(f"[WARN] {BINS_FILE} not found - vertical lines will not be shown")
    except Exception as e:
        print(f"[ERROR] Could not load bin peaks: {e}")
        import traceback
        traceback.print_exc()

    # ========================================================
    # ADD SCATTER MARKERS ON ORANGE LINE (START=ORANGE FILLED, END=ORANGE HOLLOW)
    # ========================================================
    # Bin START markers (orange filled circles at peak - smaller)
    if bin_start_times and bins_continuous is not None:
        fig.add_trace(
            go.Scatter(
                x=bin_start_times,
                y=bin_start_freqs,
                mode="markers",
                name="Bin START (Peak)",
                marker=dict(
                    symbol="circle",
                    size=8,
                    color="orange",
                    line=dict(width=1, color="darkorange")
                ),
                hovertemplate="<b>BIN START</b><br>%{x}<br>Peak Freq: %{y:.0f}<extra></extra>",
            ),
            secondary_y=True
        )

    # Bin END markers (orange hollow circles at signal)
    if bin_end_times and bins_continuous is not None:
        fig.add_trace(
            go.Scatter(
                x=bin_end_times,
                y=bin_end_freqs,
                mode="markers",
                name="Bin END (Signal)",
                marker=dict(
                    symbol="circle-open",
                    size=8,
                    color="orange",
                    line=dict(width=2, color="orange")
                ),
                hovertemplate="<b>BIN END</b><br>%{x}<br>Freq: %{y:.0f}<extra></extra>",
            ),
            secondary_y=True
        )

    # Panel 2: P&L acumulado (SOLO área verde, sin línea)
    # ===== Layout: SOLO GRID HORIZONTAL =====
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="rgba(0,0,0,0.08)", secondary_y=False)
    fig.update_yaxes(showgrid=False, secondary_y=True)

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
        shapes=shapes  # Add vertical lines at bin peaks
    )

    # Configure Y-axis titles
    fig.update_yaxes(title_text="Price (NQ)", secondary_y=False)
    fig.update_yaxes(title_text="Bin Frequency", secondary_y=True, showgrid=False)

    # Guardar y abrir
    Path(OUTPUT_HTML).parent.mkdir(parents=True, exist_ok=True)
    print(f"\nGuardando gráfico en: {OUTPUT_HTML}")
    fig.write_html(str(OUTPUT_HTML))

    print("Abriendo en el navegador...")
    try:
        import os
        import platform
        if platform.system() == 'Windows':
            os.startfile(str(OUTPUT_HTML))
        else:
            webbrowser.open(f'file://{Path(OUTPUT_HTML).resolve()}')
    except Exception as e:
        print(f"  No se pudo abrir automaticamente: {e}")
        print(f"  Abre manualmente: {OUTPUT_HTML}")

    print("\n¡Gráfico generado correctamente!")
    print("=" * 70)


if __name__ == "__main__":
    plot_trades_on_chart(start_idx=DEFAULT_START_INDEX, end_idx=DEFAULT_END_INDEX)
