"""
Resumen completo de performance para d-Shape & p-Shape Strategy.

Genera tabla HTML con métricas completas y llama a plot_backtest_results.py.
"""

import pandas as pd
import numpy as np
import webbrowser
import subprocess
import sys
from pathlib import Path

# Add strategies folder to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from path_helper import get_output_path, get_charts_path

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
TRADES_FILE = get_output_path('tracking_record_absortion_shape_all_day.csv')
OUTPUT_HTML = get_charts_path('summary_report_absortion_shape_all_day.html')


def calculate_metrics(df):
    """
    Calcula métricas completas de trading.

    Args:
        df: DataFrame con trades

    Returns:
        dict con todas las métricas
    """
    total_trades = len(df)

    if total_trades == 0:
        return {}

    # Básicas
    winners = df[df['profit_dollars'] > 0]
    losers = df[df['profit_dollars'] < 0]
    breakevens = df[df['profit_dollars'] == 0]

    win_count = len(winners)
    loss_count = len(losers)
    win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0

    # Profit metrics
    total_profit = df['profit_dollars'].sum()
    avg_profit = df['profit_dollars'].mean()

    gross_profit = winners['profit_dollars'].sum() if len(winners) > 0 else 0
    gross_loss = abs(losers['profit_dollars'].sum()) if len(losers) > 0 else 0

    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')

    avg_winner = winners['profit_dollars'].mean() if len(winners) > 0 else 0
    avg_loser = losers['profit_dollars'].mean() if len(losers) > 0 else 0

    largest_winner = winners['profit_dollars'].max() if len(winners) > 0 else 0
    largest_loser = losers['profit_dollars'].min() if len(losers) > 0 else 0

    # Expectancy
    expectancy = (win_rate/100 * avg_winner) + ((1 - win_rate/100) * avg_loser)

    # Drawdown
    df['cumulative_profit'] = df['profit_dollars'].cumsum()
    max_equity = df['cumulative_profit'].cummax()
    drawdown = df['cumulative_profit'] - max_equity
    max_drawdown = drawdown.min()

    # Recovery factor
    recovery_factor = (total_profit / abs(max_drawdown)) if max_drawdown != 0 else float('inf')

    # Sharpe ratio (simplificado - asumiendo risk-free rate = 0)
    returns = df['profit_dollars']
    sharpe_ratio = (returns.mean() / returns.std()) if returns.std() > 0 else 0

    # Consecutive wins/losses
    df['win'] = df['profit_dollars'] > 0
    df['streak'] = (df['win'] != df['win'].shift()).cumsum()
    winning_streaks = df[df['win']].groupby('streak').size()
    losing_streaks = df[~df['win']].groupby('streak').size()

    max_winning_streak = winning_streaks.max() if len(winning_streaks) > 0 else 0
    max_losing_streak = losing_streaks.max() if len(losing_streaks) > 0 else 0

    # Por exit reason
    targets = len(df[df['exit_reason'] == 'TARGET'])
    stops = len(df[df['exit_reason'] == 'STOP'])
    eods = len(df[df['exit_reason'] == 'EOD'])

    # Por señal
    d_shape_trades = df[df['entry_signal'] == 'd_shape']
    p_shape_trades = df[df['entry_signal'] == 'p_shape']

    # Duración promedio
    df['duration_minutes'] = (pd.to_datetime(df['exit_time']) - pd.to_datetime(df['entry_time'])).dt.total_seconds() / 60
    avg_duration = df['duration_minutes'].mean()

    return {
        'total_trades': total_trades,
        'win_count': win_count,
        'loss_count': loss_count,
        'breakeven_count': len(breakevens),
        'win_rate': win_rate,
        'total_profit': total_profit,
        'avg_profit': avg_profit,
        'gross_profit': gross_profit,
        'gross_loss': gross_loss,
        'profit_factor': profit_factor,
        'avg_winner': avg_winner,
        'avg_loser': avg_loser,
        'largest_winner': largest_winner,
        'largest_loser': largest_loser,
        'expectancy': expectancy,
        'max_drawdown': max_drawdown,
        'recovery_factor': recovery_factor,
        'sharpe_ratio': sharpe_ratio,
        'max_winning_streak': max_winning_streak,
        'max_losing_streak': max_losing_streak,
        'targets': targets,
        'stops': stops,
        'eods': eods,
        'd_shape_count': len(d_shape_trades),
        'd_shape_profit': d_shape_trades['profit_dollars'].sum() if len(d_shape_trades) > 0 else 0,
        'p_shape_count': len(p_shape_trades),
        'p_shape_profit': p_shape_trades['profit_dollars'].sum() if len(p_shape_trades) > 0 else 0,
        'avg_duration': avg_duration,
        'start_time': df['entry_time'].min(),
        'end_time': df['exit_time'].max()
    }


def generate_html_report(metrics):
    """
    Genera reporte HTML con las métricas.

    Args:
        metrics: dict con métricas calculadas

    Returns:
        str con HTML
    """
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Backtest Summary - d-Shape & p-Shape Strategy</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 20px;
                background-color: #f5f5f5;
            }}
            h1 {{
                color: #333;
                text-align: center;
                font-size: 22px;
                margin-bottom: 5px;
            }}
            h2 {{
                font-size: 14px;
                margin-top: 0;
            }}
            .container {{
                max-width: 700px;
                margin: 0 auto;
                background-color: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 0 10px rgba(0,0,0,0.1);
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 10px 0;
            }}
            th, td {{
                padding: 6px 10px;
                text-align: left;
                border-bottom: 1px solid #ddd;
                font-size: 13px;
            }}
            th {{
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
            }}
            tr:hover {{
                background-color: #f5f5f5;
            }}
            .metric-label {{
                font-weight: bold;
                width: 60%;
            }}
            .metric-value {{
                text-align: right;
                font-family: monospace;
                font-size: 13px;
            }}
            .positive {{
                color: green;
                font-weight: bold;
            }}
            .negative {{
                color: red;
                font-weight: bold;
            }}
            .section-title {{
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                text-align: center;
                font-size: 12px;
                padding: 4px 10px;
            }}
            .footer {{
                text-align: center;
                margin-top: 15px;
                color: #666;
                font-size: 11px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Backtest Summary Report</h1>
            <h2 style="text-align: center; color: #666;">d-Shape & p-Shape Absorption Strategy</h2>

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
                    <td class="metric-value">{metrics['start_time']} - {metrics['end_time']}</td>
                </tr>
                <tr>
                    <td class="metric-label">Duración Promedio</td>
                    <td class="metric-value">{metrics['avg_duration']:.1f} minutos</td>
                </tr>

                <tr class="section-title">
                    <td colspan="2">PERFORMANCE</td>
                </tr>
                <tr>
                    <td class="metric-label">Total Profit</td>
                    <td class="metric-value {'positive' if metrics['total_profit'] > 0 else 'negative'}">${metrics['total_profit']:,.2f}</td>
                </tr>
                <tr>
                    <td class="metric-label">Avg Profit per Trade</td>
                    <td class="metric-value {'positive' if metrics['avg_profit'] > 0 else 'negative'}">${metrics['avg_profit']:,.2f}</td>
                </tr>
                <tr>
                    <td class="metric-label">Profit Factor</td>
                    <td class="metric-value">{metrics['profit_factor']:.2f}</td>
                </tr>
                <tr>
                    <td class="metric-label">Expectancy</td>
                    <td class="metric-value {'positive' if metrics['expectancy'] > 0 else 'negative'}">${metrics['expectancy']:,.2f}</td>
                </tr>
                <tr>
                    <td class="metric-label">Sharpe Ratio</td>
                    <td class="metric-value">{metrics['sharpe_ratio']:.2f}</td>
                </tr>

                <tr class="section-title">
                    <td colspan="2">WIN/LOSS</td>
                </tr>
                <tr>
                    <td class="metric-label">Win Rate</td>
                    <td class="metric-value">{metrics['win_rate']:.1f}%</td>
                </tr>
                <tr>
                    <td class="metric-label">Winners / Losers / Breakeven</td>
                    <td class="metric-value">{metrics['win_count']} / {metrics['loss_count']} / {metrics['breakeven_count']}</td>
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

                <tr class="section-title">
                    <td colspan="2">RISK METRICS</td>
                </tr>
                <tr>
                    <td class="metric-label">Max Drawdown</td>
                    <td class="metric-value negative">${metrics['max_drawdown']:,.2f}</td>
                </tr>
                <tr>
                    <td class="metric-label">Recovery Factor</td>
                    <td class="metric-value">{metrics['recovery_factor']:.2f}</td>
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
                    <td class="metric-label">d-Shape (LONG) Trades</td>
                    <td class="metric-value">{metrics['d_shape_count']} ({metrics['d_shape_count']/metrics['total_trades']*100:.1f}%)</td>
                </tr>
                <tr>
                    <td class="metric-label">d-Shape Profit</td>
                    <td class="metric-value {'positive' if metrics['d_shape_profit'] > 0 else 'negative'}">${metrics['d_shape_profit']:,.2f}</td>
                </tr>
                <tr>
                    <td class="metric-label">p-Shape (SHORT) Trades</td>
                    <td class="metric-value">{metrics['p_shape_count']} ({metrics['p_shape_count']/metrics['total_trades']*100:.1f}%)</td>
                </tr>
                <tr>
                    <td class="metric-label">p-Shape Profit</td>
                    <td class="metric-value {'positive' if metrics['p_shape_profit'] > 0 else 'negative'}">${metrics['p_shape_profit']:,.2f}</td>
                </tr>
            </table>

            <div class="footer">
                Generated by d-Shape & p-Shape Absorption Strategy | {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
            </div>
        </div>
    </body>
    </html>
    """
    return html


def main():
    """
    Función principal.
    """
    print("="*70)
    print("GENERANDO RESUMEN DE PERFORMANCE")
    print("="*70)

    # Cargar trades
    print(f"\nCargando {TRADES_FILE}...")
    df = pd.read_csv(TRADES_FILE, sep=';', decimal=',')
    df.columns = df.columns.str.strip()
    print(f"  Trades cargados: {len(df):,}")

    if len(df) == 0:
        print("\nNo hay trades para analizar.")
        return

    # Calcular métricas
    print("\nCalculando métricas...")
    metrics = calculate_metrics(df)

    # Imprimir métricas principales en consola
    print("\n" + "="*70)
    print("MÉTRICAS PRINCIPALES")
    print("="*70)
    print(f"\nTotal Trades: {metrics['total_trades']:,}")
    print(f"Win Rate: {metrics['win_rate']:.1f}%")
    print(f"Total Profit: ${metrics['total_profit']:,.2f}")
    print(f"Profit Factor: {metrics['profit_factor']:.2f}")
    print(f"Max Drawdown: ${metrics['max_drawdown']:,.2f}")
    print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
    print(f"\nd-Shape Trades: {metrics['d_shape_count']} (${metrics['d_shape_profit']:,.2f})")
    print(f"p-Shape Trades: {metrics['p_shape_count']} (${metrics['p_shape_profit']:,.2f})")

    # Generar HTML
    print(f"\nGenerando reporte HTML...")
    html_content = generate_html_report(metrics)

    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"  Guardado en: {OUTPUT_HTML}")

    # Llamar a plot_backtest_results.py
    print(f"\nGenerando gráficos detallados...")
    try:
        import plot_backtest_results
        plot_backtest_results.main()
    except Exception as e:
        print(f"  Error al generar gráficos: {e}")
        print("  Puedes ejecutar manualmente: python plot_backtest_results.py")

    # Abrir HTML en navegador
    print(f"\nAbriendo reporte en navegador...")
    webbrowser.open(OUTPUT_HTML)

    print("\n" + "="*70)
    print("RESUMEN COMPLETADO")
    print("="*70)


if __name__ == "__main__":
    main()
