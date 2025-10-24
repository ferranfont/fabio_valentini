"""
MAIN SCRIPT - d-Shape & p-Shape Absorption Strategy
====================================================

Ejecuta la estrategia completa en orden:
1. Backtest con strat_absortion_shape.py
2. Visualización de trades con plot_trades_chart.py
3. Gráficos de resultados con plot_backtest_results.py
4. Resumen estadístico con summary.py

Configuración centralizada de todos los parámetros.
"""

from pathlib import Path
import sys
import time

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

# Archivos de entrada
TNS_FILE = DATA_DIR / "time_and_sales_nq.csv"
# TNS_FILE = DATA_DIR / "time_and_sales_nq_30min.csv"  # Alternativa: 30 minutos

SIGNALS_FILE = OUTPUTS_DIR / "db_shapes_20251024_003251.csv"
# SIGNALS_FILE = OUTPUTS_DIR / "db_shapes.csv"  # Alternativa: señales genéricas

# Archivos de salida
TRACKING_RECORD_FILE = OUTPUTS_DIR / "tracking_record_absortion_shape_all_day.csv"
TRADES_CHART_FILE = CHARTS_DIR / "trades_visualization_absortion_shape_all_day.html"
BACKTEST_CHART_FILE = CHARTS_DIR / "backtest_results_absortion_shape_all_day.html"
SUMMARY_REPORT_FILE = CHARTS_DIR / "summary_report_absortion_shape_all_day.html"

# ========= PARÁMETROS DE ESTRATEGIA =========
SYMBOL = "NQ"
TP_POINTS = 4.0                     # Take Profit en puntos
SL_POINTS = 3.0                     # Stop Loss en puntos
POINT_VALUE = 20.0                  # Valor del punto en dólares
CONTRACTS = 1                       # Número de contratos por trade
NUM_MAX_OPEN_CONTRACTS = 1          # Máximo de posiciones abiertas simultáneamente

# ========= PARÁMETROS DE VISUALIZACIÓN =========
# Filtros para plot_trades_chart.py
USE_INDEX_RANGE = False             # True: filtrar por índice, False: mostrar todos
START_INDEX = 0                     # Índice inicial (si USE_INDEX_RANGE = True)
END_INDEX = 50                      # Índice final (si USE_INDEX_RANGE = True)

# ==============================================================================
# FUNCIONES
# ==============================================================================

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
    """Ejecuta el backtest de la estrategia."""
    print_step(1, "EJECUTANDO BACKTEST")

    # Importar función main de strat_absortion_shape.py
    import strat_absortion_shape

    # Configurar parámetros globales
    strat_absortion_shape.TNS_FILE = TNS_FILE
    strat_absortion_shape.SIGNALS_FILE = SIGNALS_FILE
    strat_absortion_shape.OUTPUT_FILE = TRACKING_RECORD_FILE
    strat_absortion_shape.SYMBOL = SYMBOL
    strat_absortion_shape.TP_POINTS = TP_POINTS
    strat_absortion_shape.SL_POINTS = SL_POINTS
    strat_absortion_shape.POINT_VALUE = POINT_VALUE
    strat_absortion_shape.CONTRACTS = CONTRACTS
    strat_absortion_shape.NUM_MAX_OPEN_CONTRACTS = NUM_MAX_OPEN_CONTRACTS

    # Ejecutar backtest
    trades_df = strat_absortion_shape.main()

    print(f"\n[OK] Backtest completado: {len(trades_df)} trades generados")
    print(f"[OK] Resultados guardados en: {TRACKING_RECORD_FILE}")

    return trades_df


def plot_trades():
    """Visualiza los trades en el gráfico."""
    print_step(2, "GENERANDO VISUALIZACIÓN DE TRADES")

    # Importar función de plot_trades_chart.py
    import plot_trades_chart

    # Configurar rutas y parámetros
    plot_trades_chart.TRADES_FILE = TRACKING_RECORD_FILE
    plot_trades_chart.SIGNALS_FILE = SIGNALS_FILE
    plot_trades_chart.BASE_TNS_FILE = TNS_FILE
    plot_trades_chart.OUTPUT_HTML = TRADES_CHART_FILE
    plot_trades_chart.USE_INDEX_RANGE = USE_INDEX_RANGE
    plot_trades_chart.DEFAULT_START_INDEX = START_INDEX
    plot_trades_chart.DEFAULT_END_INDEX = END_INDEX

    # Ejecutar visualización
    try:
        plot_trades_chart.plot_trades_on_chart(
            start_idx=START_INDEX,
            end_idx=END_INDEX if USE_INDEX_RANGE else None
        )
        print(f"\n[OK] Grafico de trades generado: {TRADES_CHART_FILE}")
    except Exception as e:
        print(f"\n[ERROR] Error al generar grafico de trades: {e}")


def generate_summary():
    """Genera resumen estadístico completo (incluye gráficos internamente)."""
    print_step(3, "GENERANDO RESUMEN ESTADISTICO Y GRAFICOS")

    # Importar función de summary.py
    import summary

    # Configurar rutas
    summary.TRADES_FILE = TRACKING_RECORD_FILE
    summary.OUTPUT_HTML = SUMMARY_REPORT_FILE

    # Ejecutar
    try:
        summary.main()
        print(f"\n[OK] Resumen estadistico generado: {SUMMARY_REPORT_FILE}")
    except Exception as e:
        print(f"\n[ERROR] Error al generar resumen: {e}")


def main():
    """Función principal que ejecuta todos los pasos."""
    start_time = time.time()

    print_header("ESTRATEGIA d-SHAPE & p-SHAPE ABSORPTION - EJECUCIÓN COMPLETA")

    print("CONFIGURACIÓN:")
    print(f"  Símbolo: {SYMBOL}")
    print(f"  Take Profit: {TP_POINTS} puntos")
    print(f"  Stop Loss: {SL_POINTS} puntos")
    print(f"  Contratos: {CONTRACTS}")
    print(f"  Max posiciones abiertas: {NUM_MAX_OPEN_CONTRACTS}")
    print(f"\n  Datos T&S: {TNS_FILE.name}")
    print(f"  Señales: {SIGNALS_FILE.name}")
    print(f"  Salida: {TRACKING_RECORD_FILE.name}")

    if USE_INDEX_RANGE:
        print(f"\n  Filtro de visualización: Índices {START_INDEX} a {END_INDEX}")
    else:
        print(f"\n  Filtro de visualización: TODO EL DÍA (sin límite)")

    try:
        # Paso 1: Ejecutar backtest
        trades_df = run_backtest()

        # Paso 2: Visualizar trades
        plot_trades()

        # Paso 3: Resumen estadístico (incluye gráficos de resultados internamente)
        generate_summary()

        # Resumen final
        elapsed_time = time.time() - start_time
        print_header("EJECUCION COMPLETADA")
        print(f"[OK] Todos los pasos completados exitosamente")
        print(f"[OK] Tiempo total: {elapsed_time:.1f} segundos")
        print(f"\nARCHIVOS GENERADOS:")
        print(f"  1. Trades CSV: {TRACKING_RECORD_FILE}")
        print(f"  2. Grafico de trades: {TRADES_CHART_FILE}")
        print(f"  3. Resumen estadistico: {SUMMARY_REPORT_FILE}")
        print(f"  4. Graficos de equity/drawdown: charts/backtest_results_absortion_shape_all_day_*.html")
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
