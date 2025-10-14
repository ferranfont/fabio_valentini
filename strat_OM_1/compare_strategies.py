"""
Script para comparar resultados entre estrategia ORIGINAL y CORREGIDA.

Compara:
- Estrategia ORIGINAL (con look-ahead bias): tracking_record.csv
- Estrategia CORREGIDA (sin look-ahead bias): tracking_record_window.csv
"""

import pandas as pd
import os

# Archivos
FILE_ORIGINAL = 'outputs/tracking_record.csv'
FILE_WINDOW = 'outputs/tracking_record_window.csv'


def load_and_analyze(filepath, label):
    """Carga y analiza un archivo de trades."""
    if not os.path.exists(filepath):
        print(f"\n⚠️  {label}: Archivo no encontrado: {filepath}")
        return None

    df = pd.read_csv(filepath, sep=';', decimal=',')

    total_trades = len(df)
    winners = df[df['profit_dollars'] > 0]
    losers = df[df['profit_dollars'] < 0]

    total_profit = df['profit_dollars'].sum()
    win_rate = len(winners) / total_trades * 100 if total_trades > 0 else 0

    # Por resultado
    targets = len(df[df['resultado'] == 'TARGET'])
    stops = len(df[df['resultado'] == 'STOP'])
    eods = len(df[df['resultado'] == 'EOD'])

    # Max drawdown
    df['cumulative_profit'] = df['profit_dollars'].cumsum()
    max_equity = df['cumulative_profit'].cummax()
    drawdown = df['cumulative_profit'] - max_equity
    max_drawdown = drawdown.min()

    # Profit factor
    gross_profit = winners['profit_dollars'].sum() if len(winners) > 0 else 0
    gross_loss = abs(losers['profit_dollars'].sum()) if len(losers) > 0 else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

    return {
        'label': label,
        'total_trades': total_trades,
        'winners': len(winners),
        'losers': len(losers),
        'win_rate': win_rate,
        'total_profit': total_profit,
        'avg_profit': total_profit / total_trades if total_trades > 0 else 0,
        'targets': targets,
        'stops': stops,
        'eods': eods,
        'max_drawdown': max_drawdown,
        'profit_factor': profit_factor,
        'avg_winner': winners['profit_dollars'].mean() if len(winners) > 0 else 0,
        'avg_loser': losers['profit_dollars'].mean() if len(losers) > 0 else 0,
    }


def print_comparison(stats_original, stats_window):
    """Imprime comparación lado a lado."""
    print("\n" + "="*90)
    print("COMPARACIÓN: ESTRATEGIA ORIGINAL vs CORREGIDA")
    print("="*90)

    if stats_original is None or stats_window is None:
        print("\n⚠️  No se pueden comparar: faltan archivos")
        return

    # Calcular diferencias
    diff_trades = stats_window['total_trades'] - stats_original['total_trades']
    diff_win_rate = stats_window['win_rate'] - stats_original['win_rate']
    diff_profit = stats_window['total_profit'] - stats_original['total_profit']
    pct_trades = (diff_trades / stats_original['total_trades'] * 100) if stats_original['total_trades'] > 0 else 0
    pct_profit = (diff_profit / stats_original['total_profit'] * 100) if stats_original['total_profit'] != 0 else 0

    print(f"\n{'MÉTRICA':<30} {'ORIGINAL':<20} {'CORREGIDA':<20} {'DIFERENCIA':<20}")
    print("-" * 90)

    print(f"{'Total Trades':<30} {stats_original['total_trades']:<20,} {stats_window['total_trades']:<20,} "
          f"{diff_trades:+,} ({pct_trades:+.1f}%)")

    print(f"{'Win Rate':<30} {stats_original['win_rate']:<20.2f}% {stats_window['win_rate']:<20.2f}% "
          f"{diff_win_rate:+.2f}%")

    print(f"{'Total Profit':<30} ${stats_original['total_profit']:<19,.2f} ${stats_window['total_profit']:<19,.2f} "
          f"${diff_profit:+,.2f} ({pct_profit:+.1f}%)")

    print(f"{'Avg Profit/Trade':<30} ${stats_original['avg_profit']:<19,.2f} ${stats_window['avg_profit']:<19,.2f} "
          f"${stats_window['avg_profit'] - stats_original['avg_profit']:+,.2f}")

    print(f"{'Profit Factor':<30} {stats_original['profit_factor']:<20.2f} {stats_window['profit_factor']:<20.2f} "
          f"{stats_window['profit_factor'] - stats_original['profit_factor']:+.2f}")

    print(f"{'Max Drawdown':<30} ${stats_original['max_drawdown']:<19,.2f} ${stats_window['max_drawdown']:<19,.2f} "
          f"${stats_window['max_drawdown'] - stats_original['max_drawdown']:+,.2f}")

    print(f"\n{'Ganadores':<30} {stats_original['winners']:<20,} {stats_window['winners']:<20,} "
          f"{stats_window['winners'] - stats_original['winners']:+,}")

    print(f"{'Perdedores':<30} {stats_original['losers']:<20,} {stats_window['losers']:<20,} "
          f"{stats_window['losers'] - stats_original['losers']:+,}")

    print(f"{'Avg Winner':<30} ${stats_original['avg_winner']:<19,.2f} ${stats_window['avg_winner']:<19,.2f} "
          f"${stats_window['avg_winner'] - stats_original['avg_winner']:+,.2f}")

    print(f"{'Avg Loser':<30} ${stats_original['avg_loser']:<19,.2f} ${stats_window['avg_loser']:<19,.2f} "
          f"${stats_window['avg_loser'] - stats_original['avg_loser']:+,.2f}")

    print(f"\n{'TARGET exits':<30} {stats_original['targets']:<20,} {stats_window['targets']:<20,} "
          f"{stats_window['targets'] - stats_original['targets']:+,}")

    print(f"{'STOP exits':<30} {stats_original['stops']:<20,} {stats_window['stops']:<20,} "
          f"{stats_window['stops'] - stats_original['stops']:+,}")

    print(f"{'EOD exits':<30} {stats_original['eods']:<20,} {stats_window['eods']:<20,} "
          f"{stats_window['eods'] - stats_original['eods']:+,}")

    print("\n" + "="*90)
    print("IMPACTO DEL LOOK-AHEAD BIAS")
    print("="*90)

    print(f"\n>> Trades perdidos: {abs(diff_trades)} ({abs(pct_trades):.1f}%)")
    print(f"   -> Senales que caen fuera de la ventana temporal al desplazarse")

    print(f"\n>> Win Rate: {diff_win_rate:+.2f}%")
    if diff_win_rate < 0:
        print(f"   -> La estrategia original tenia win rate INFLADO por look-ahead bias")
    else:
        print(f"   -> Sorprendentemente, la correccion mejoro el win rate")

    print(f"\n>> Profit: ${diff_profit:+,.2f} ({pct_profit:+.1f}%)")
    if diff_profit < 0:
        print(f"   -> La estrategia original era mas rentable ARTIFICIALMENTE")
        print(f"   -> Perdida de ${abs(diff_profit):,.2f} al corregir el bias")
    else:
        print(f"   -> La correccion mantuvo o mejoro la rentabilidad")

    print(f"\n>> Conclusion:")
    if diff_profit < -1000:
        print(f"   [!] IMPACTO CRITICO: El look-ahead bias inflaba significativamente los resultados")
        print(f"   [!] La estrategia real es MENOS RENTABLE de lo esperado")
        print(f"   [!] Requiere ajustes para ser viable en produccion")
    elif diff_profit < 0:
        print(f"   [!] IMPACTO MODERADO: El bias inflaba los resultados")
        print(f"   [!] La estrategia real tiene menor performance")
    else:
        print(f"   [OK] La correccion mantiene la viabilidad de la estrategia")

    print("\n" + "="*90)


def main():
    """Función principal."""
    print("\n" + "="*90)
    print("ANALIZANDO ESTRATEGIAS")
    print("="*90)

    stats_original = load_and_analyze(FILE_ORIGINAL, "ORIGINAL (con bias)")
    stats_window = load_and_analyze(FILE_WINDOW, "CORREGIDA (sin bias)")

    if stats_original:
        print(f"\n[OK] Estrategia ORIGINAL cargada: {stats_original['total_trades']:,} trades")
    if stats_window:
        print(f"[OK] Estrategia CORREGIDA cargada: {stats_window['total_trades']:,} trades")

    print_comparison(stats_original, stats_window)

    print("\n[FILES] Archivos para visualizacion:")
    print(f"   Original:  {FILE_ORIGINAL}")
    print(f"   Corregida: {FILE_WINDOW}")

    print("\n[CONFIG] Para cambiar que estrategia visualizar:")
    print(f"   1. Edita STRATEGY_VERSION en plot_trades_chart.py")
    print(f"   2. Edita STRATEGY_VERSION en summary.py")
    print(f"   3. Edita STRATEGY_VERSION en plot_backtest_results.py")
    print(f"   4. Opciones: 'original' o 'window'")

    print("\n" + "="*90)


if __name__ == "__main__":
    main()
