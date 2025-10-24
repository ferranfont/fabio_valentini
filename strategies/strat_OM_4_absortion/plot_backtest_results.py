"""
Visualización de resultados del backtest para d-Shape & p-Shape Strategy.

Genera gráficos de equity curve, drawdown, y distribuciones.
"""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import webbrowser
import sys
from pathlib import Path

# Add strategies folder to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from path_helper import get_output_path, get_charts_path

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
TRADES_FILE = get_output_path('tracking_record_absortion_shape_all_day.csv')
OUTPUT_FILE = get_charts_path('backtest_results_absortion_shape_all_day.html')


def load_trades(filepath):
    """Carga archivo de trades."""
    print(f"Cargando {filepath}...")
    df = pd.read_csv(filepath, sep=';', decimal=',')
    df.columns = df.columns.str.strip()

    df['entry_time'] = pd.to_datetime(df['entry_time'])
    df['exit_time'] = pd.to_datetime(df['exit_time'])

    print(f"  Trades cargados: {len(df):,}")
    return df


def create_equity_curve(df):
    """Crea curva de equity con 3 subplots."""
    fig = make_subplots(
        rows=3, cols=1,
        row_heights=[0.5, 0.25, 0.25],
        shared_xaxes=True,
        subplot_titles=("Curva de Equity", "Profit por Trade", "Drawdown"),
        vertical_spacing=0.08
    )

    # Calcular cumulative profit
    df['cumulative_profit'] = df['profit_dollars'].cumsum()

    # Curva de equity con colores verde/rojo según profit
    equity_color = 'green' if df['cumulative_profit'].iloc[-1] > 0 else 'red'
    fill_color = 'rgba(0,200,0,0.2)' if df['cumulative_profit'].iloc[-1] > 0 else 'rgba(200,0,0,0.2)'

    fig.add_trace(
        go.Scatter(
            x=list(range(len(df))),
            y=df['cumulative_profit'],
            mode='lines',
            name='Equity',
            line=dict(color=equity_color, width=2),
            fill='tozeroy',
            fillcolor=fill_color
        ),
        row=1, col=1
    )

    # Profit por trade con colores
    colors = ['green' if p > 0 else 'red' for p in df['profit_dollars']]
    fig.add_trace(
        go.Bar(
            x=list(range(len(df))),
            y=df['profit_dollars'],
            name='Profit/Loss',
            marker_color=colors,
            opacity=0.6
        ),
        row=2, col=1
    )

    # Drawdown
    max_equity = df['cumulative_profit'].cummax()
    drawdown = df['cumulative_profit'] - max_equity

    fig.add_trace(
        go.Scatter(
            x=list(range(len(df))),
            y=drawdown,
            mode='lines',
            name='Drawdown',
            line=dict(color='red', width=2),
            fill='tozeroy',
            fillcolor='rgba(200,0,0,0.2)'
        ),
        row=3, col=1
    )

    # Layout
    fig.update_xaxes(title_text="Trade #", row=3, col=1)
    fig.update_yaxes(title_text="Equity ($)", row=1, col=1)
    fig.update_yaxes(title_text="P/L ($)", row=2, col=1)
    fig.update_yaxes(title_text="DD ($)", row=3, col=1)

    fig.update_layout(
        height=900,
        showlegend=True,
        hovermode='x unified',
        title_text=f"Backtest Results - {len(df):,} trades"
    )

    return fig


def create_distribution_charts(df):
    """Crea gráficos de distribución."""
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            "Distribución de Profit/Loss",
            "Trades por Resultado",
            "Trades por Señal de Entrada",
            "Duración de Trades"
        ),
        specs=[[{"type": "histogram"}, {"type": "bar"}],
               [{"type": "bar"}, {"type": "histogram"}]]
    )

    # 1. Histograma de P/L
    fig.add_trace(
        go.Histogram(
            x=df['profit_dollars'],
            nbinsx=30,
            name='P/L',
            marker_color='steelblue'
        ),
        row=1, col=1
    )

    # 2. Bar chart de resultados
    resultado_counts = df['exit_reason'].value_counts()
    fig.add_trace(
        go.Bar(
            x=resultado_counts.index,
            y=resultado_counts.values,
            name='Resultado',
            marker_color='lightcoral'
        ),
        row=1, col=2
    )

    # 3. Trades por señal de entrada (d-shape vs p-shape)
    signal_counts = df['entry_signal'].value_counts()
    colors_signals = ['red' if sig == 'd_shape' else 'lime' for sig in signal_counts.index]

    fig.add_trace(
        go.Bar(
            x=signal_counts.index,
            y=signal_counts.values,
            name='Señal',
            marker_color=colors_signals
        ),
        row=2, col=1
    )

    # 4. Duración de trades
    df['duration_minutes'] = (df['exit_time'] - df['entry_time']).dt.total_seconds() / 60

    fig.add_trace(
        go.Histogram(
            x=df['duration_minutes'],
            nbinsx=30,
            name='Duración',
            marker_color='purple'
        ),
        row=2, col=2
    )

    # Layout
    fig.update_xaxes(title_text="Profit ($)", row=1, col=1)
    fig.update_xaxes(title_text="Señal Entrada", row=2, col=1)
    fig.update_xaxes(title_text="Duración (min)", row=2, col=2)

    fig.update_yaxes(title_text="Frecuencia", row=1, col=1)
    fig.update_yaxes(title_text="Trades", row=2, col=1)
    fig.update_yaxes(title_text="Frecuencia", row=2, col=2)

    fig.update_layout(
        height=800,
        showlegend=False,
        title_text="Análisis de Distribuciones"
    )

    return fig


def print_summary(df):
    """Imprime resumen estadístico."""
    print("\n" + "="*70)
    print("RESUMEN DEL BACKTEST")
    print("="*70)

    total = len(df)
    winners = df[df['profit_dollars'] > 0]
    losers = df[df['profit_dollars'] < 0]

    print(f"\nTrades totales: {total:,}")
    print(f"  Ganadores: {len(winners):,} ({len(winners)/total*100:.1f}%)")
    print(f"  Perdedores: {len(losers):,} ({len(losers)/total*100:.1f}%)")

    print(f"\nProfit:")
    print(f"  Total: ${df['profit_dollars'].sum():,.2f}")
    print(f"  Promedio: ${df['profit_dollars'].mean():,.2f}")
    print(f"  Mediana: ${df['profit_dollars'].median():,.2f}")

    if len(winners) > 0:
        print(f"\nGanadores:")
        print(f"  Promedio: ${winners['profit_dollars'].mean():,.2f}")
        print(f"  Máximo: ${winners['profit_dollars'].max():,.2f}")

    if len(losers) > 0:
        print(f"\nPerdedores:")
        print(f"  Promedio: ${losers['profit_dollars'].mean():,.2f}")
        print(f"  Máximo: ${losers['profit_dollars'].min():,.2f}")

    print(f"\nResultados:")
    print(df['exit_reason'].value_counts())

    print(f"\nSeñales de entrada:")
    print(df['entry_signal'].value_counts())

    print(f"\nDirección:")
    print(df['side'].value_counts())

    print("\n" + "="*70)


def main():
    """Función principal."""
    df = load_trades(TRADES_FILE)

    print_summary(df)

    print(f"\nCreando gráfico de equity...")
    fig1 = create_equity_curve(df)
    equity_path = OUTPUT_FILE.replace('.html', '_equity.html')
    fig1.write_html(equity_path)

    print(f"Creando gráficos de distribución...")
    fig2 = create_distribution_charts(df)
    dist_path = OUTPUT_FILE.replace('.html', '_distributions.html')
    fig2.write_html(dist_path)

    print(f"\nGráficos guardados:")
    print(f"  - {equity_path}")
    print(f"  - {dist_path}")

    print(f"\nAbriendo en navegador...")
    webbrowser.open(equity_path)

    print("\nCompletado!")


if __name__ == "__main__":
    main()
