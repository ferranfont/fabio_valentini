"""
MAIN SCRIPT - Bin Frequency Bounce Strategy
============================================

Estrategia basada en seguimiento de señales de bins:
- Bins con price_tag='up' → Entra LONG (sigue la tendencia alcista)
- Bins con price_tag='down' → Entra SHORT (sigue la tendencia bajista)

Ejecuta la estrategia completa en orden:
1. Backtest con strat_bins.py
2. Visualización de trades con plot_trades_chart.py
3. Gráficos de resultados con plot_backtest_results.py
4. Resumen estadístico con summary.py

Configuración centralizada de todos los parámetros.
"""

from pathlib import Path
import sys
import time
import platform
import os
import webbrowser

# Add parent folder to path for imports
THIS_FILE = Path(__file__).resolve()
STRATEGY_DIR = THIS_FILE.parent
PROJECT_ROOT = STRATEGY_DIR.parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(STRATEGY_DIR.parent))

# ==============================================================================
# CONFIGURACIÓN CENTRALIZADA
# ==============================================================================

# ========= RUTAS =========
DATA_DIR = PROJECT_ROOT / "data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
CHARTS_DIR = PROJECT_ROOT / "charts"
STRAT_SWEEP_DIR = PROJECT_ROOT / "strat_sweep"

# Archivos de entrada
TNS_FILE = DATA_DIR / "historic" / "time_and_sales_nq_20251022.csv"
BINS_FILE = STRAT_SWEEP_DIR / "db_mushroom_bins.csv"

# Archivos de salida
_sweep_dir = OUTPUTS_DIR / "sweep"
_sweep_dir.mkdir(parents=True, exist_ok=True)

TRACKING_RECORD_FILE = _sweep_dir / "bounce_TR_20251022.csv"
TRADES_CHART_FILE = CHARTS_DIR / "trades_visualization_bounce_20251022.html"
BACKTEST_CHART_FILE = CHARTS_DIR / "backtest_results_bounce_20251022.html"
SUMMARY_REPORT_FILE = CHARTS_DIR / "summary_report_bounce_20251022.html"

# ========= PARÁMETROS DE ESTRATEGIA =========
SYMBOL = "NQ"
TP_POINTS = 5               # Take Profit en puntos
SL_POINTS = 5               # Stop Loss en puntos
POINT_VALUE = 20.0          # Valor del punto en dolares ($20 por punto para NQ)
CONTRACTS = 1               # Número de contratos por trade
BREAK_EVEN_POINTS = 10.0    # Avance necesario para mover el stop a precio de entrada
NUM_MAX_OPEN_CONTRACTS = 20 # Máximo de posiciones abiertas simultáneamente

# ========= PARÁMETROS DE BOUNCE =========
EXTENDED_LINE_MINUTES = 5  #Tiempo límite para observar bounce y cruce
MIN_BOUNCE = 7           # Mínimo movimiento en puntos para considerar bounce válido

# ========= PARÁMETROS DE VISUALIZACIÓN =========
USE_INDEX_RANGE = False     # True: filtrar por índice, False: mostrar todos
START_INDEX = 0             # Índice inicial (si USE_INDEX_RANGE = True)
END_INDEX = 50              # Índice final (si USE_INDEX_RANGE = True)
EMA_PERIOD = 200            # SMA200 verde en el gráfico

# ==============================================================================
# FUNCIONES
# ==============================================================================

def open_in_browser(path: Path):
    """Abre un archivo HTML en el navegador por defecto."""
    try:
        if platform.system() == "Windows":
            os.startfile(str(path))
        else:
            webbrowser.open(f"file://{path.resolve()}")
        print(f"[OK] Abriendo en navegador: {path}")
    except Exception as exc:
        print(f"[WARN] No se pudo abrir {path}: {exc}")
        print(f"       Ábrelo manualmente desde el explorador.")

def print_header(title):
    """Imprime un encabezado visual."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def print_step(step_num, title):
    """Imprime el número de paso."""
    print(f"\n{'-' * 80}")
    print(f"PASO {step_num}: {title}")
    print('-' * 80)


def run_backtest():
    """Ejecuta el backtest de la estrategia de bounce."""
    print_step(1, "EJECUTANDO BACKTEST - BIN BOUNCE STRATEGY")

    # Importar función main de strat_bounce.py
    import strat_bounce

    # Configurar parámetros globales
    strat_bounce.TNS_FILE = TNS_FILE
    strat_bounce.BINS_FILE = BINS_FILE
    strat_bounce.OUTPUT_FILE = TRACKING_RECORD_FILE
    strat_bounce.SYMBOL = SYMBOL
    strat_bounce.TP_POINTS = TP_POINTS
    strat_bounce.SL_POINTS = SL_POINTS
    strat_bounce.POINT_VALUE = POINT_VALUE
    strat_bounce.BREAK_EVEN_POINTS = BREAK_EVEN_POINTS
    strat_bounce.CONTRACTS = CONTRACTS
    strat_bounce.NUM_MAX_OPEN_CONTRACTS = NUM_MAX_OPEN_CONTRACTS
    strat_bounce.EXTENDED_LINE_MINUTES = EXTENDED_LINE_MINUTES
    strat_bounce.MIN_BOUNCE = MIN_BOUNCE

    # Ejecutar backtest
    trades_df = strat_bounce.main()

    print(f"\n[OK] Backtest completado: {len(trades_df)} trades generados")
    print(f"[OK] Resultados guardados en: {TRACKING_RECORD_FILE}")

    return trades_df


def plot_trades():
    """Visualiza los trades en el gráfico."""
    print_step(2, "GENERANDO VISUALIZACIÓN DE TRADES")

    # Crear CSV temporal con formato compatible para plot_trades_chart
    # (renombrar timestamp_end -> timestamp, close_price_end -> close_price)
    import pandas as pd

    temp_signals_file = _sweep_dir / "bounce_signals_temp.csv"

    try:
        # Leer bins CSV (nueva estructura con reset_timestamp y reset_price)
        df_bins_raw = pd.read_csv(BINS_FILE, sep=';', decimal=',')

        # Crear DataFrame compatible renombrando columnas
        # USAR RESET DATA (nueva lógica de entrada en el reset)
        df_signals_compatible = pd.DataFrame({
            'timestamp': pd.to_datetime(df_bins_raw['reset_timestamp']),  # Usar reset_timestamp
            'close_price': df_bins_raw['reset_price'].astype(str).str.replace(',', '.').astype(float),  # Usar reset_price
            'shape': df_bins_raw['price_tag']  # up/down como "shape"
        })

        # Guardar CSV temporal con formato europeo
        df_signals_compatible.to_csv(temp_signals_file, sep=';', decimal=',', index=False)
        print(f"[OK] CSV temporal de señales creado: {temp_signals_file.name}")

    except Exception as e:
        print(f"[WARN] Error al crear CSV temporal: {e}")
        import traceback
        traceback.print_exc()
        temp_signals_file = BINS_FILE

    # Importar función de plot_trades_chart.py
    import plot_trades_chart

    # Configurar rutas y parámetros
    plot_trades_chart.TRADES_FILE = str(TRACKING_RECORD_FILE)
    plot_trades_chart.SIGNALS_FILE = str(temp_signals_file)  # Usar CSV temporal compatible
    plot_trades_chart.BASE_TNS_FILE = str(TNS_FILE)
    plot_trades_chart.OUTPUT_HTML = str(TRADES_CHART_FILE)
    plot_trades_chart.USE_INDEX_RANGE = USE_INDEX_RANGE
    plot_trades_chart.DEFAULT_START_INDEX = START_INDEX
    plot_trades_chart.DEFAULT_END_INDEX = END_INDEX
    plot_trades_chart.EMA_PERIOD = EMA_PERIOD
    plot_trades_chart.USE_EMA_FOR_SIDE_OVERRIDE = False
    plot_trades_chart.SYMBOL = f"{SYMBOL} - BIN BOUNCE (UP->LONG, DOWN->SHORT)"

    # Ejecutar visualización
    try:
        plot_trades_chart.plot_trades_on_chart(
            start_idx=START_INDEX,
            end_idx=END_INDEX if USE_INDEX_RANGE else None
        )
        print(f"\n[OK] Grafico de trades generado: {TRADES_CHART_FILE}")
    except Exception as e:
        print(f"\n[ERROR] Error al generar grafico de trades: {e}")
        import traceback
        traceback.print_exc()
    else:
        open_in_browser(TRADES_CHART_FILE)


def plot_backtest_results():
    """Genera los gráficos de resultados del backtest."""
    print_step(3, "GENERANDO WEB DE RESULTADOS DEL BACKTEST")

    import plot_backtest_results

    plot_backtest_results.TRADES_FILE = str(TRACKING_RECORD_FILE)
    plot_backtest_results.OUTPUT_FILE = str(BACKTEST_CHART_FILE)

    # Inyectar título personalizado modificando create_equity_curve
    original_create_equity = plot_backtest_results.create_equity_curve
    def custom_create_equity(df):
        fig = original_create_equity(df)
        fig.update_layout(title_text=f"BIN BOUNCE Strategy - Backtest Results - {len(df):,} trades (TP:{TP_POINTS}pts, SL:{SL_POINTS}pts)")
        return fig
    plot_backtest_results.create_equity_curve = custom_create_equity

    original_create_dist = plot_backtest_results.create_distribution_charts
    def custom_create_dist(df):
        fig = original_create_dist(df)
        fig.update_layout(title_text="BIN BOUNCE Strategy - Distribution Analysis")
        return fig
    plot_backtest_results.create_distribution_charts = custom_create_dist

    try:
        plot_backtest_results.main()
        equity_file = BACKTEST_CHART_FILE.with_name(BACKTEST_CHART_FILE.stem + "_equity.html")
        dist_file = BACKTEST_CHART_FILE.with_name(BACKTEST_CHART_FILE.stem + "_distributions.html")
        print(f"\n[OK] Gráficos de equity/drawdown listos en: {equity_file} y {dist_file}")
        open_in_browser(equity_file)
        open_in_browser(dist_file)
    except Exception as e:
        print(f"\n[ERROR] Error al generar resultados del backtest: {e}")
        import traceback
        traceback.print_exc()


def generate_summary():
    """Genera resumen estadístico completo (incluye gráficos internamente)."""
    print_step(4, "GENERANDO RESUMEN ESTADISTICO Y GRAFICOS")

    # Importar función de summary.py
    import summary

    # Configurar rutas
    summary.TRADES_FILE = str(TRACKING_RECORD_FILE)
    summary.OUTPUT_HTML = str(SUMMARY_REPORT_FILE)

    # Inyectar título personalizado
    original_main = summary.main
    def custom_main():
        # Llamar original
        result = original_main()
        # Leer HTML y reemplazar título
        try:
            with open(SUMMARY_REPORT_FILE, 'r', encoding='utf-8') as f:
                html_content = f.read()
            html_content = html_content.replace(
                '<title>Backtest Summary - d-Shape & p-Shape Strategy</title>',
                '<title>BIN BOUNCE Strategy - Summary Report</title>'
            )
            html_content = html_content.replace(
                '<h1>Backtest Summary Report</h1>',
                f'<h1>BIN BOUNCE Strategy - Summary Report</h1><p style="text-align:center;color:#666;">UP-&gt;LONG | DOWN-&gt;SHORT | TP:{TP_POINTS}pts | SL:{SL_POINTS}pts | Max Positions:{NUM_MAX_OPEN_CONTRACTS}</p>'
            )
            with open(SUMMARY_REPORT_FILE, 'w', encoding='utf-8') as f:
                f.write(html_content)
        except Exception as e:
            print(f"[WARN] No se pudo personalizar título del resumen: {e}")
        return result
    summary.main = custom_main

    # Ejecutar
    try:
        summary.main()
        print(f"\n[OK] Resumen estadistico generado: {SUMMARY_REPORT_FILE}")
        open_in_browser(SUMMARY_REPORT_FILE)
    except Exception as e:
        print(f"\n[ERROR] Error al generar resumen: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Función principal que ejecuta todos los pasos."""
    start_time = time.time()

    print_header("BIN FREQUENCY BOUNCE STRATEGY - EJECUCIÓN COMPLETA")

    print("CONFIGURACIÓN:")
    print(f"  Símbolo: {SYMBOL}")
    print(f"  Take Profit: {TP_POINTS} puntos")
    print(f"  Stop Loss: {SL_POINTS} puntos")
    print(f"  Contratos: {CONTRACTS}")
    print(f"  Max posiciones abiertas: {NUM_MAX_OPEN_CONTRACTS}")
    print(f"  Break-even a favor: {BREAK_EVEN_POINTS} puntos")
    print(f"\n  BOUNCE PARAMETERS:")
    print(f"  - Observation window: {EXTENDED_LINE_MINUTES} minutes")
    print(f"  - Min bounce movement: {MIN_BOUNCE} points")
    print(f"\n  Datos T&S: {TNS_FILE.name}")
    print(f"  Señales (Bins): {BINS_FILE.name}")
    print(f"  Salida: {TRACKING_RECORD_FILE.name}")
    print(f"\n  LOGICA: Bounce UP + cross reset -> LONG | Bounce DOWN + cross reset -> SHORT")

    if USE_INDEX_RANGE:
        print(f"\n  Filtro de visualización: Índices {START_INDEX} a {END_INDEX}")
    else:
        print(f"\n  Filtro de visualización: TODO EL DÍA (sin límite)")

    try:
        # Paso 1: Ejecutar backtest
        trades_df = run_backtest()

        # Paso 2: Visualizar trades
        plot_trades()

        # Paso 3: Web de resultados
        plot_backtest_results()

        # Paso 4: Resumen estadístico
        generate_summary()

        # Resumen final
        elapsed_time = time.time() - start_time
        print_header("EJECUCION COMPLETADA")
        print(f"[OK] Todos los pasos completados exitosamente")
        print(f"[OK] Tiempo total: {elapsed_time:.1f} segundos")
        equity_file = BACKTEST_CHART_FILE.with_name(BACKTEST_CHART_FILE.stem + "_equity.html")
        dist_file = BACKTEST_CHART_FILE.with_name(BACKTEST_CHART_FILE.stem + "_distributions.html")
        print(f"\nARCHIVOS GENERADOS:")
        print(f"  1. Trades CSV: {TRACKING_RECORD_FILE}")
        print(f"  2. Grafico de trades: {TRADES_CHART_FILE}")
        print(f"  3. Web de resultados: {equity_file} y {dist_file}")
        print(f"  4. Resumen estadistico: {SUMMARY_REPORT_FILE}")
        print("\nLos reportes HTML se han abierto automaticamente en tu navegador.")

    except KeyboardInterrupt:
        print("\n\n[ERROR] Ejecucion interrumpida por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[ERROR] Error durante la ejecucion: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
