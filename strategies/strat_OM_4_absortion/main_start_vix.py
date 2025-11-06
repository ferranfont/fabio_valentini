"""
MAIN SCRIPT - d-Shape & p-Shape Absorption Strategy WITH ATR + TRAILING STOP
==============================================================================

Ejecuta la estrategia completa con gestión de riesgo basada en volatilidad:
1. Backtest con strat_absortion_shape_vix.py (ATR + Trailing Stop)
2. Visualización de trades con plot_trades_chart.py
3. Gráficos de resultados con plot_backtest_results.py
4. Resumen estadístico con summary.py

DIFERENCIAS vs main_start.py estándar:
- SL/TP dinámicos basados en ATR (volatilidad)
- Trailing Stop que mueve el SL cuando el precio avanza a favor
- Parámetros ATR configurables (periodo, multiplicadores)
"""

from pathlib import Path
import re
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
TNS_FILE = DATA_DIR / "historic" / "time_and_sales_nq_20250919.csv"  # Archivo T&S

# PLASE HERE THE db_shapes FILE YOU WANT TO USE
tns_date_match = re.search(r"\d{8}", TNS_FILE.name)
if not tns_date_match:
    raise ValueError(f"No se pudo extraer una fecha (YYYYMMDD) del archivo T&S: {TNS_FILE.name}")
SIGNALS_DATE = tns_date_match.group(0)
_signals_filename = f"db_shapes_dom_{SIGNALS_DATE}.csv"
_signals_default = OUTPUTS_DIR / _signals_filename
_signals_absortion = OUTPUTS_DIR / "absortion_shape" / _signals_filename
if _signals_default.exists():
    SIGNALS_FILE = _signals_default
elif _signals_absortion.exists():
    SIGNALS_FILE = _signals_absortion
else:
    raise FileNotFoundError(
        f"No se encontro el archivo de senales {_signals_filename} ni en {OUTPUTS_DIR} ni en {OUTPUTS_DIR / 'absortion_shape'}"
    )

# Archivos de salida (con sufijo _vix para diferenciarlo)
_absortion_shape_dir = OUTPUTS_DIR / "absortion_shape"
_absortion_shape_dir.mkdir(parents=True, exist_ok=True)

TRACKING_RECORD_FILE = _absortion_shape_dir / f"dbshapes_TR_vix_{SIGNALS_DATE}.csv"
TRADES_CHART_FILE = CHARTS_DIR / f"trades_visualization_absortion_shape_vix_{SIGNALS_DATE}.html"
BACKTEST_CHART_FILE = CHARTS_DIR / f"backtest_results_absortion_shape_vix_{SIGNALS_DATE}.html"
SUMMARY_REPORT_FILE = CHARTS_DIR / f"summary_report_absortion_shape_vix_{SIGNALS_DATE}.html"

# ========= PARÁMETROS ATR Y TRAILING STOP =========
SYMBOL = "NQ"
ATR_PERIOD = 14                 # Periodo para calcular ATR (en minutos)
ATR_MULTIPLIER_SL = 1.0         # Multiplicador ATR para Stop Loss (1.5 x ATR)
ATR_MULTIPLIER_TP = 2.5         # Multiplicador ATR para Take Profit (2.5 x ATR)
TRAILING_STOP_ATR_MULT = 0.75   # Multiplicador ATR para trailing stop distance (0.75 x ATR)
USE_TRAILING_STOP = True        # Activar/desactivar trailing stop
POINT_VALUE = 20.0              # Valor del punto en dólares ($20 por punto para NQ)
THRESHOLD_EXTRA = 0.25          # Margen de seguridad adicional
CONTRACTS = 1                   # Número de contratos por trade
NUM_MAX_OPEN_CONTRACTS = 3      # Máximo de posiciones abiertas simultáneamente

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
    """Ejecuta el backtest de la estrategia con ATR y Trailing Stop."""
    print_step(1, "EJECUTANDO BACKTEST CON ATR + TRAILING STOP")

    # Importar función main de strat_absortion_shape_vix.py
    import strat_absortion_shape_vix

    # Configurar parámetros globales
    strat_absortion_shape_vix.TNS_FILE = TNS_FILE
    strat_absortion_shape_vix.SIGNALS_FILE = SIGNALS_FILE
    strat_absortion_shape_vix.OUTPUT_FILE = TRACKING_RECORD_FILE
    strat_absortion_shape_vix.SYMBOL = SYMBOL
    strat_absortion_shape_vix.ATR_PERIOD = ATR_PERIOD
    strat_absortion_shape_vix.ATR_MULTIPLIER_SL = ATR_MULTIPLIER_SL
    strat_absortion_shape_vix.ATR_MULTIPLIER_TP = ATR_MULTIPLIER_TP
    strat_absortion_shape_vix.TRAILING_STOP_ATR_MULT = TRAILING_STOP_ATR_MULT
    strat_absortion_shape_vix.USE_TRAILING_STOP = USE_TRAILING_STOP
    strat_absortion_shape_vix.POINT_VALUE = POINT_VALUE
    strat_absortion_shape_vix.THRESHOLD_EXTRA = THRESHOLD_EXTRA
    strat_absortion_shape_vix.CONTRACTS = CONTRACTS
    strat_absortion_shape_vix.NUM_MAX_OPEN_CONTRACTS = NUM_MAX_OPEN_CONTRACTS

    # Ejecutar backtest
    trades_df = strat_absortion_shape_vix.main()

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

    print_header("ESTRATEGIA d-SHAPE & p-SHAPE ABSORPTION - ATR + TRAILING STOP")

    print("CONFIGURACIÓN ATR Y TRAILING STOP:")
    print(f"  Símbolo: {SYMBOL}")
    print(f"  ATR Period: {ATR_PERIOD} periodos")
    print(f"  SL Multiplier: {ATR_MULTIPLIER_SL}x ATR")
    print(f"  TP Multiplier: {ATR_MULTIPLIER_TP}x ATR")
    print(f"  Trailing Stop: {'ENABLED' if USE_TRAILING_STOP else 'DISABLED'} ({TRAILING_STOP_ATR_MULT}x ATR)")
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
        print(f"  4. Graficos de equity/drawdown: {BACKTEST_CHART_FILE.parent}/backtest_results_absortion_shape_vix_{SIGNALS_DATE}_*.html")
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
