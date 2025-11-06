"""
Análisis agregados multi-día para la estrategia d-Shape & p-Shape.

Lee todos los CSV de tracking ubicados en `outputs/absortion_shape/tracking_record`
además del archivo consolidado `tracking_record_strat_abs_4_all_days.csv`.
Calcula métricas avanzadas (Sharpe, Sortino, Profit Factor, etc.) y genera
visualizaciones interactivas (equity, histogramas, distribuciones por día/hora),
publicándolas en un informe HTML que se abre en el navegador.
"""

from __future__ import annotations

import argparse
import webbrowser
from pathlib import Path
from typing import Iterable, List

import numpy as np
import pandas as pd
import plotly.graph_objects as go


# ==============================================================================
# RUTAS BÁSICAS
# ==============================================================================
THIS_FILE = Path(__file__).resolve()
STRATEGY_DIR = THIS_FILE.parent
PROJECT_ROOT = STRATEGY_DIR.parents[1]
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
TRACKING_DIR_FIXED = OUTPUTS_DIR / "absortion_shape" / "tracking_record"
TRACKING_DIR_VIX = OUTPUTS_DIR / "absortion_shape" / "tracking_record_vix"
CONSOLIDATED_FILE = OUTPUTS_DIR / "tracking_record_strat_abs_4_all_days.csv"
CHARTS_DIR = PROJECT_ROOT / "charts"

# Will be set by command line argument or user prompt
TRACKING_DIR = None
REPORT_FILE = None
STRATEGY_TYPE = None


# ==============================================================================
# PARÁMETROS CLAVE (para mostrar en título)
# ==============================================================================
# Estos deberían coincidir con los usados durante el trading
PROFILE_WINDOW = 20  # segundos
MIN_PRICE_LEVELS = 20
MIN_BID_ASK_SIZE = 30
EXTREME_VOLUME_MULTIPLIER = 2


# ==============================================================================
# UTILIDADES
# ==============================================================================
def read_tracking_csv(path: Path) -> pd.DataFrame:
    """Carga un archivo de tracking usando separador punto y coma."""
    df = pd.read_csv(path, sep=";", decimal=",")
    df["entry_time"] = pd.to_datetime(df["entry_time"])
    df["exit_time"] = pd.to_datetime(df["exit_time"])
    numeric_cols = [
        "entry_price",
        "exit_price",
        "tp_price",
        "sl_price",
        "profit_points",
        "profit_dollars",
        "contracts",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["source_file"] = path.name
    return df


def load_all_trades(include_consolidated: bool = True) -> pd.DataFrame:
    """Lee todos los trades disponibles en la carpeta configurada."""
    frames: List[pd.DataFrame] = []

    if TRACKING_DIR.exists():
        for csv_path in sorted(TRACKING_DIR.glob("*.csv")):
            try:
                frames.append(read_tracking_csv(csv_path))
            except Exception as exc:  # pragma: no cover - logging informativo
                print(f"[WARN] No se pudo cargar {csv_path}: {exc}")

    if include_consolidated and CONSOLIDATED_FILE.exists():
        frames.append(read_tracking_csv(CONSOLIDATED_FILE))

    if not frames:
        raise FileNotFoundError(
            f"No se encontraron archivos de tracking en {TRACKING_DIR} "
            f"ni el consolidado {CONSOLIDATED_FILE}"
        )

    df = pd.concat(frames, ignore_index=True)
    df.sort_values("entry_time", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def downside_std(returns: pd.Series) -> float:
    losses = returns[returns < 0]
    if losses.empty:
        return 0.0
    return np.sqrt(np.mean(np.square(losses)))


def calc_metrics(df: pd.DataFrame) -> dict:
    """Computa todas las métricas igual que summary.py."""
    if df.empty:
        raise ValueError("No hay trades para analizar.")

    returns = df["profit_dollars"]
    cumulative = returns.cumsum()
    rolling_max = cumulative.cummax()
    drawdown = cumulative - rolling_max
    max_dd = drawdown.min()

    trade_duration = (df["exit_time"] - df["entry_time"]).dt.total_seconds() / 60
    trade_days = df["entry_time"].dt.date.nunique()

    wins = returns[returns > 0]
    losses = returns[returns < 0]

    # Métricas avanzadas
    sharpe = returns.mean() / returns.std(ddof=0) if returns.std(ddof=0) > 0 else 0.0
    sortino = (
        returns.mean() / downside_std(returns) if downside_std(returns) > 0 else 0.0
    )
    profit_factor = (
        wins.sum() / abs(losses.sum()) if losses.sum() != 0 else np.inf
    )
    expectancy = returns.mean()
    ulcer_index = np.sqrt(np.mean(np.square(drawdown)))
    recovery_factor = returns.sum() / abs(max_dd) if max_dd != 0 else np.inf

    # Streak analysis
    df_copy = df.copy()
    df_copy['is_win'] = df_copy['profit_dollars'] > 0
    streaks = []
    current_streak = 0
    current_type = None

    for is_win in df_copy['is_win']:
        if is_win == current_type:
            current_streak += 1
        else:
            if current_streak > 0:
                streaks.append((current_type, current_streak))
            current_streak = 1
            current_type = is_win

    if current_streak > 0:
        streaks.append((current_type, current_streak))

    win_streaks = [s[1] for s in streaks if s[0]]
    loss_streaks = [s[1] for s in streaks if not s[0]]

    max_winning_streak = max(win_streaks) if win_streaks else 0
    max_losing_streak = max(loss_streaks) if loss_streaks else 0

    # Exit reasons and signal breakdown
    targets = len(df[df['exit_reason'] == 'TARGET']) if 'exit_reason' in df.columns else 0
    stops = len(df[df['exit_reason'] == 'STOP']) if 'exit_reason' in df.columns else 0
    eods = len(df[df['exit_reason'] == 'END_OF_DATA']) if 'exit_reason' in df.columns else 0

    d_shape_trades = df[df['shape'] == 'd_shape'] if 'shape' in df.columns else pd.DataFrame()
    p_shape_trades = df[df['shape'] == 'p_shape'] if 'shape' in df.columns else pd.DataFrame()

    d_shape_count = len(d_shape_trades)
    p_shape_count = len(p_shape_trades)
    d_shape_profit = d_shape_trades['profit_dollars'].sum() if not d_shape_trades.empty else 0
    p_shape_profit = p_shape_trades['profit_dollars'].sum() if not p_shape_trades.empty else 0

    metrics = {
        # GENERAL
        'total_trades': len(df),
        'start_time': df['entry_time'].min().strftime('%Y-%m-%d %H:%M:%S'),
        'end_time': df['exit_time'].max().strftime('%Y-%m-%d %H:%M:%S'),
        'exposure_days': trade_days,
        'trades_per_day': len(df) / trade_days if trade_days else 0,
        'avg_duration': trade_duration.mean(),
        'median_duration': trade_duration.median(),

        # PERFORMANCE
        'total_profit': returns.sum(),
        'avg_profit': returns.mean(),
        'median_profit': returns.median(),
        'std_profit': returns.std(),
        'profit_factor': profit_factor,
        'expectancy': expectancy,

        # WIN/LOSS
        'win_rate': (returns > 0).mean() * 100,
        'win_count': len(wins),
        'loss_count': len(losses),
        'gross_profit': wins.sum(),
        'gross_loss': losses.sum(),
        'avg_winner': wins.mean() if len(wins) > 0 else 0,
        'avg_loser': losses.mean() if len(losses) > 0 else 0,
        'largest_winner': returns.max(),
        'largest_loser': returns.min(),

        # RISK METRICS
        'max_drawdown': max_dd,
        'ulcer_index': ulcer_index,
        'recovery_factor': recovery_factor,
        'sharpe_ratio': sharpe,
        'sortino_ratio': sortino,
        'max_winning_streak': max_winning_streak,
        'max_losing_streak': max_losing_streak,

        # DISTRIBUTION
        'skewness': returns.skew(),
        'kurtosis': returns.kurtosis(),

        # EXIT REASONS
        'targets': targets,
        'stops': stops,
        'eods': eods,

        # SIGNAL BREAKDOWN
        'd_shape_count': d_shape_count,
        'p_shape_count': p_shape_count,
        'd_shape_profit': d_shape_profit,
        'p_shape_profit': p_shape_profit,
    }

    return metrics


def build_figures(df: pd.DataFrame) -> list[go.Figure]:
    """Crea todas las figuras interactivas requeridas."""
    df = df.copy()
    df["equity"] = df["profit_dollars"].cumsum()
    df["entry_date"] = df["entry_time"].dt.date
    df["day_of_week"] = df["entry_time"].dt.day_name()
    df["entry_hour"] = df["entry_time"].dt.hour

    figs: list[go.Figure] = []

    # 1. Equity curve (área verde pastel con alpha)
    fig_equity = go.Figure()
    fig_equity.add_trace(go.Scatter(
        x=df['entry_time'],
        y=df['equity'],
        fill='tozeroy',
        fillcolor='rgba(144, 238, 144, 0.3)',  # verde pastel con alpha
        line=dict(color='rgba(60, 179, 113, 0.8)', width=2),
        name='Equity',
        mode='lines'
    ))
    fig_equity.update_layout(
        title='Curva de Equity Acumulada',
        xaxis_title='Fecha',
        yaxis_title='Equity ($)',
        hovermode='x unified',
        template='plotly_white'
    )
    figs.append(fig_equity)

    # 2. Histograma de Profit en $
    fig_profit_hist = go.Figure()
    fig_profit_hist.add_trace(go.Histogram(
        x=df['profit_dollars'],
        nbinsx=50,
        marker_color='rgba(100, 149, 237, 0.7)',
        name='Profit Distribution'
    ))
    fig_profit_hist.update_layout(
        title='Distribución de Ganancias por Trade',
        xaxis_title='Profit ($)',
        yaxis_title='Frecuencia',
        template='plotly_white'
    )
    figs.append(fig_profit_hist)

    # 3. Profit por hora del día
    hourly_profit = df.groupby('entry_hour')['profit_dollars'].sum().reset_index()
    fig_hourly = go.Figure()
    fig_hourly.add_trace(go.Bar(
        x=hourly_profit['entry_hour'],
        y=hourly_profit['profit_dollars'],
        marker_color='rgba(255, 159, 64, 0.7)',
        name='Profit by Hour'
    ))
    fig_hourly.update_layout(
        title='Profit Acumulado por Hora del Día',
        xaxis_title='Hora (24h)',
        yaxis_title='Profit ($)',
        xaxis=dict(tickmode='linear', tick0=0, dtick=1),
        template='plotly_white'
    )
    figs.append(fig_hourly)

    # 4. Profit por día de la semana
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    day_profit = df.groupby('day_of_week')['profit_dollars'].sum().reindex(day_order).dropna()
    fig_daily = go.Figure()
    fig_daily.add_trace(go.Bar(
        x=day_profit.index,
        y=day_profit.values,
        marker_color='rgba(153, 102, 255, 0.7)',
        name='Profit by Day'
    ))
    fig_daily.update_layout(
        title='Profit Acumulado por Día de la Semana',
        xaxis_title='Día',
        yaxis_title='Profit ($)',
        template='plotly_white'
    )
    figs.append(fig_daily)

    return figs


def build_html_report(metrics: dict, figures: Iterable[go.Figure]) -> str:
    """Compone el HTML completo con tabla de 2 columnas (estilo summary.py) y gráficos."""

    # Construir tabla HTML de 2 columnas
    html_table = f"""
    <div class="two-column-layout">
        <!-- LEFT COLUMN -->
        <div class="column">
            <table>
                <tr class="section-title">
                    <td colspan="2">GENERAL</td>
                </tr>
                <tr>
                    <td class="metric-label">Total Trades</td>
                    <td class="metric-value">{metrics['total_trades']:,}</td>
                </tr>
                <tr>
                    <td class="metric-label">Periodo</td>
                    <td class="metric-value" style="font-size: 11px;">{metrics['start_time']}<br>{metrics['end_time']}</td>
                </tr>
                <tr>
                    <td class="metric-label">Exposure Days</td>
                    <td class="metric-value">{metrics['exposure_days']}</td>
                </tr>
                <tr>
                    <td class="metric-label">Trades per Day</td>
                    <td class="metric-value">{metrics['trades_per_day']:.1f}</td>
                </tr>
                <tr>
                    <td class="metric-label">Avg Duration</td>
                    <td class="metric-value">{metrics['avg_duration']:.1f} min</td>
                </tr>
                <tr>
                    <td class="metric-label">Median Duration</td>
                    <td class="metric-value">{metrics['median_duration']:.1f} min</td>
                </tr>

                <tr class="section-title">
                    <td colspan="2">PERFORMANCE</td>
                </tr>
                <tr>
                    <td class="metric-label">Total Profit</td>
                    <td class="metric-value {'positive' if metrics['total_profit'] > 0 else 'negative'}">${metrics['total_profit']:,.2f}</td>
                </tr>
                <tr>
                    <td class="metric-label">Avg Profit</td>
                    <td class="metric-value {'positive' if metrics['avg_profit'] > 0 else 'negative'}">${metrics['avg_profit']:,.2f}</td>
                </tr>
                <tr>
                    <td class="metric-label">Median Profit</td>
                    <td class="metric-value {'positive' if metrics['median_profit'] > 0 else 'negative'}">${metrics['median_profit']:,.2f}</td>
                </tr>
                <tr>
                    <td class="metric-label">Std Profit</td>
                    <td class="metric-value">${metrics['std_profit']:,.2f}</td>
                </tr>
                <tr>
                    <td class="metric-label">Profit Factor</td>
                    <td class="metric-value">{metrics['profit_factor']:.2f}</td>
                </tr>
                <tr>
                    <td class="metric-label">Expectancy</td>
                    <td class="metric-value {'positive' if metrics['expectancy'] > 0 else 'negative'}">${metrics['expectancy']:,.2f}</td>
                </tr>

                <tr class="section-title">
                    <td colspan="2">WIN/LOSS</td>
                </tr>
                <tr>
                    <td class="metric-label">Win Rate</td>
                    <td class="metric-value">{metrics['win_rate']:.1f}%</td>
                </tr>
                <tr>
                    <td class="metric-label">Winners / Losers</td>
                    <td class="metric-value">{metrics['win_count']} / {metrics['loss_count']}</td>
                </tr>
                <tr>
                    <td class="metric-label">Gross Profit</td>
                    <td class="metric-value positive">${metrics['gross_profit']:,.2f}</td>
                </tr>
                <tr>
                    <td class="metric-label">Gross Loss</td>
                    <td class="metric-value negative">${metrics['gross_loss']:,.2f}</td>
                </tr>
                <tr>
                    <td class="metric-label">Avg Winner</td>
                    <td class="metric-value positive">${metrics['avg_winner']:,.2f}</td>
                </tr>
                <tr>
                    <td class="metric-label">Avg Loser</td>
                    <td class="metric-value negative">${metrics['avg_loser']:,.2f}</td>
                </tr>
                <tr>
                    <td class="metric-label">Largest Winner</td>
                    <td class="metric-value positive">${metrics['largest_winner']:,.2f}</td>
                </tr>
                <tr>
                    <td class="metric-label">Largest Loser</td>
                    <td class="metric-value negative">${metrics['largest_loser']:,.2f}</td>
                </tr>
            </table>
        </div>

        <!-- RIGHT COLUMN -->
        <div class="column">
            <table>
                <tr class="section-title">
                    <td colspan="2">RISK METRICS</td>
                </tr>
                <tr>
                    <td class="metric-label">Max Drawdown</td>
                    <td class="metric-value negative">${metrics['max_drawdown']:,.2f}</td>
                </tr>
                <tr>
                    <td class="metric-label">Ulcer Index</td>
                    <td class="metric-value">{metrics['ulcer_index']:.2f}</td>
                </tr>
                <tr>
                    <td class="metric-label">Recovery Factor</td>
                    <td class="metric-value">{metrics['recovery_factor']:.2f}</td>
                </tr>
                <tr>
                    <td class="metric-label">Sharpe Ratio</td>
                    <td class="metric-value">{metrics['sharpe_ratio']:.2f}</td>
                </tr>
                <tr>
                    <td class="metric-label">Sortino Ratio</td>
                    <td class="metric-value">{metrics['sortino_ratio']:.2f}</td>
                </tr>
                <tr>
                    <td class="metric-label">Max Winning Streak</td>
                    <td class="metric-value">{metrics['max_winning_streak']}</td>
                </tr>
                <tr>
                    <td class="metric-label">Max Losing Streak</td>
                    <td class="metric-value">{metrics['max_losing_streak']}</td>
                </tr>

                <tr class="section-title">
                    <td colspan="2">DISTRIBUTION</td>
                </tr>
                <tr>
                    <td class="metric-label">Skewness</td>
                    <td class="metric-value">{metrics['skewness']:.3f}</td>
                </tr>
                <tr>
                    <td class="metric-label">Kurtosis</td>
                    <td class="metric-value">{metrics['kurtosis']:.3f}</td>
                </tr>

                <tr class="section-title">
                    <td colspan="2">EXIT REASONS</td>
                </tr>
                <tr>
                    <td class="metric-label">TARGET exits</td>
                    <td class="metric-value">{metrics['targets']} ({metrics['targets']/metrics['total_trades']*100:.1f}%)</td>
                </tr>
                <tr>
                    <td class="metric-label">STOP exits</td>
                    <td class="metric-value">{metrics['stops']} ({metrics['stops']/metrics['total_trades']*100:.1f}%)</td>
                </tr>
                <tr>
                    <td class="metric-label">EOD exits</td>
                    <td class="metric-value">{metrics['eods']} ({metrics['eods']/metrics['total_trades']*100:.1f}%)</td>
                </tr>

                <tr class="section-title">
                    <td colspan="2">SIGNAL BREAKDOWN</td>
                </tr>
                <tr>
                    <td class="metric-label">d-Shape (LONG)</td>
                    <td class="metric-value">{metrics['d_shape_count']} ({metrics['d_shape_count']/metrics['total_trades']*100:.1f}%)</td>
                </tr>
                <tr>
                    <td class="metric-label">d-Shape Profit</td>
                    <td class="metric-value {'positive' if metrics['d_shape_profit'] > 0 else 'negative'}">${metrics['d_shape_profit']:,.2f}</td>
                </tr>
                <tr>
                    <td class="metric-label">p-Shape (SHORT)</td>
                    <td class="metric-value">{metrics['p_shape_count']} ({metrics['p_shape_count']/metrics['total_trades']*100:.1f}%)</td>
                </tr>
                <tr>
                    <td class="metric-label">p-Shape Profit</td>
                    <td class="metric-value {'positive' if metrics['p_shape_profit'] > 0 else 'negative'}">${metrics['p_shape_profit']:,.2f}</td>
                </tr>
            </table>
        </div>
    </div>
    """

    plot_html_parts = [
        fig.to_html(full_html=False, include_plotlyjs="cdn") for fig in figures
    ]
    plots_section = "".join(
        f'<div class="chart-container">{html}</div>' for html in plot_html_parts
    )

    # Título con parámetros
    params_text = f"ProfWin: {PROFILE_WINDOW}s | MinLevels: {MIN_PRICE_LEVELS} | MinSize: {MIN_BID_ASK_SIZE} | VolMult: {EXTREME_VOLUME_MULTIPLIER}x"

    template = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="utf-8">
        <title>Multi-Day Analysis - d-Shape & p-Shape</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 20px;
                background: #f4f6f9;
            }}
            h1 {{
                text-align: center;
                font-size: 22px;
                margin-bottom: 5px;
            }}
            h2 {{
                text-align: center;
                color: #666;
                font-size: 14px;
                margin-top: 0;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background-color: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 0 10px rgba(0,0,0,0.1);
            }}
            .two-column-layout {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 15px;
                margin: 10px 0;
            }}
            .column {{
                background-color: white;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 0;
            }}
            th, td {{
                padding: 6px 10px;
                text-align: left;
                border-bottom: 1px solid #ddd;
                font-size: 13px;
            }}
            th {{
                background-color: #f8f9fa;
                font-weight: bold;
            }}
            .section-title {{
                background-color: #e9ecef !important;
                font-weight: bold;
                color: #495057;
            }}
            .metric-label {{
                color: #6c757d;
            }}
            .metric-value {{
                font-weight: 500;
                text-align: right;
            }}
            .positive {{
                color: #28a745;
            }}
            .negative {{
                color: #dc3545;
            }}
            tr:hover {{
                background-color: #f1f3f5;
            }}
            .section-title:hover {{
                background-color: #e9ecef !important;
            }}
            .section-title td {{
                padding: 4px 10px;
            }}
            .footer {{
                text-align: center;
                margin-top: 15px;
                color: #666;
                font-size: 11px;
            }}
            .full-width-section {{
                grid-column: 1 / -1;
            }}
            .chart-container {{
                margin: 30px auto;
                max-width: 1100px;
                background: white;
                padding: 15px 20px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                border-radius: 8px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Multi-Day Backtest Summary Report - {STRATEGY_TYPE}</h1>
            <h2>d-Shape & p-Shape Absorption Strategy | {params_text}</h2>

            {html_table}

            <div class="footer">
                Generated by d-Shape & p-Shape Absorption Strategy | {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
            </div>
        </div>

        {plots_section}
    </body>
    </html>
    """
    return template


def select_strategy_type():
    """
    Ask user to select which strategy type to analyze.

    Returns:
        str: "FIXED" or "VIX"
    """
    print("\n" + "="*80)
    print("SELECT STRATEGY TYPE TO ANALYZE:")
    print("="*80)
    print("  1. FIXED   - Fixed TP/SL (tracking_record/)")
    print("  2. VIX     - ATR + Trailing Stop (tracking_record_vix/)")
    print()

    while True:
        choice = input("Enter choice (1 or 2): ").strip()
        if choice in ['1', '2']:
            break
        print("[ERROR] Invalid choice. Enter 1 or 2.")

    return "FIXED" if choice == '1' else "VIX"


def main(open_browser: bool = True, strategy_type: str = None) -> Path:
    global TRACKING_DIR, REPORT_FILE, STRATEGY_TYPE

    # If strategy_type not provided, ask user
    if strategy_type is None:
        strategy_type = select_strategy_type()

    STRATEGY_TYPE = strategy_type

    # Set tracking directory and output file based on strategy type
    if STRATEGY_TYPE == "FIXED":
        TRACKING_DIR = TRACKING_DIR_FIXED
        REPORT_FILE = CHARTS_DIR / "absortion_shape_stats_all_days_FIXED.html"
    else:
        TRACKING_DIR = TRACKING_DIR_VIX
        REPORT_FILE = CHARTS_DIR / "absortion_shape_stats_all_days_VIX.html"

    print(f"\n[OK] Analyzing {STRATEGY_TYPE} strategy from: {TRACKING_DIR}")

    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    trades = load_all_trades()
    print(f"[INFO] Trades cargados: {len(trades):,} provenientes de {trades['source_file'].nunique()} archivos")

    metrics = calc_metrics(trades)
    figures = build_figures(trades)
    report_html = build_html_report(metrics, figures)

    REPORT_FILE.write_text(report_html, encoding="utf-8")
    print(f"[OK] Reporte generado en {REPORT_FILE}")

    if open_browser:
        webbrowser.open(REPORT_FILE.as_uri())

    return REPORT_FILE


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Genera un informe multi-día para la estrategia d-Shape & p-Shape."
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Genera el informe sin abrir automáticamente el navegador.",
    )
    parser.add_argument(
        "--strategy",
        type=str,
        choices=["FIXED", "VIX"],
        help="Strategy type to analyze (FIXED or VIX). If not provided, will prompt user.",
    )
    args = parser.parse_args()
    main(open_browser=not args.no_open, strategy_type=args.strategy)
