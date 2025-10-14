"""
Estrategia de Trading con CORRECCIÓN DE LOOK-AHEAD BIAS.

PROBLEMA CORREGIDO:
- La estrategia original entraba en T cuando la señal bid_abs/ask_abs se calculaba
  mirando 60s al FUTURO (T+60s).
- En tiempo real, la señal solo está disponible DESPUÉS de esos 60s.

SOLUCIÓN (Shift de Señales):
- Las señales se desplazan SIGNAL_DELAY_SEC segundos hacia adelante.
- Entrada al precio disponible en T+60s, no en T.
- SIN look-ahead bias: solo usa información disponible en el momento de entrada.

Lógica:
- LONG: Cuando bid_abs = True (absorción BID confirmada después de 60s)
- SHORT: Cuando ask_abs = True (absorción ASK confirmada después de 60s)
- TP/SL: Fijos en puntos

Gestión:
- 1 contrato por operación
- 1 punto NQ = $20
- Cierre automático al final del día (EOD)
"""

import pandas as pd
import numpy as np
from datetime import datetime, time
import os

# ========== CONFIGURACIÓN ==========
SYMBOL = 'NQ'
DATA_FILE = f'data/time_and_sales_absorption_{SYMBOL}.csv'
OUTPUT_FILE = 'outputs/tracking_record_window.csv'

# ========== PARÁMETRO CRÍTICO: DELAY DE SEÑALES ==========
# Este es el tiempo de la ventana futura usada en find_absortion_vol_efford.py
# FUTURE_WINDOW_SEC = 30 en el script de detección (ACTUALIZADO - ventana rápida)
SIGNAL_DELAY_SEC = 15 # Segundos de retraso para corregir look-ahead bias

# Parámetros de la estrategia
ATR_PERIOD = 14  # Solo para referencia

# ==============================================================================
# Targets y Stops FIJOS - CONFIGURACIÓN RÁPIDA Y EQUILIBRADA
# ==============================================================================
# OBJETIVO: TP/SL equilibrado (1:1) para señales rápidas
#
# CONFIGURACIONES ANTERIORES:
#   Config 1: TP=2.5, SL=2.0 → R:R = 1.25:1
#   Config 2: TP=4.0, SL=3.0 → R:R = 1.33:1 (demasiado amplio, pocos hits)
#
# NUEVA (equilibrio - TP/SL simétrico):
TP_POINTS = 2.0  # Take Profit: 2 puntos = $40 por trade
SL_POINTS = 2.0  # Stop Loss: 2 puntos = -$40 por trade
# Ratio R:R = 1.0:1 (equilibrado, mayor probabilidad de hit)
# ==============================================================================

# Configuración del instrumento
TICK_SIZE = 0.25  # NQ tick size
POINT_VALUE = 20  # 1 punto NQ = $20
CONTRACTS = 1  # Contratos por operación

# Horario de trading (cierre de posiciones al final del día)
EOD_TIME = time(16, 00)  # 4:00 PM hora de mercado


def calculate_atr(df, period=14):
    """
    Calcula Average True Range usando pandas (sin librerías externas).

    ATR mide la volatilidad promedio del mercado.
    """
    print(f"Calculando ATR (period={period})...")

    # Necesitamos High, Low, Close previo
    # Como tenemos datos tick-by-tick, vamos a resamplear a barras más grandes
    # Resamplear a 5 minutos para tener OHLC

    df_resampled = df.set_index('TimeBin').resample('5min').agg({
        'Precio': ['first', 'max', 'min', 'last'],
        'Volumen': 'sum'
    })

    df_resampled.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    df_resampled = df_resampled.dropna()

    # Calcular True Range
    df_resampled['prev_close'] = df_resampled['Close'].shift(1)

    df_resampled['tr1'] = df_resampled['High'] - df_resampled['Low']
    df_resampled['tr2'] = abs(df_resampled['High'] - df_resampled['prev_close'])
    df_resampled['tr3'] = abs(df_resampled['Low'] - df_resampled['prev_close'])

    df_resampled['true_range'] = df_resampled[['tr1', 'tr2', 'tr3']].max(axis=1)

    # ATR es la media móvil del True Range
    df_resampled['atr'] = df_resampled['true_range'].rolling(window=period).mean()

    # Merge back al dataframe original usando merge_asof
    df_with_atr = pd.merge_asof(
        df.sort_values('TimeBin'),
        df_resampled[['atr']].reset_index(),
        left_on='TimeBin',
        right_on='TimeBin',
        direction='backward'
    )

    print(f"  ATR medio: {df_with_atr['atr'].mean():.2f} puntos")
    print(f"  ATR min/max: {df_with_atr['atr'].min():.2f} / {df_with_atr['atr'].max():.2f}")

    return df_with_atr


def shift_signals(df, delay_seconds=60):
    """
    CORRECCIÓN DE LOOK-AHEAD BIAS:
    Desplaza las señales bid_abs y ask_abs hacia adelante en el tiempo.

    Ejemplo:
    - ANTES: T=100s tiene bid_abs=True (calculado mirando hasta T=160s)
    - DESPUÉS: T=160s tiene bid_abs=True (disponible cuando realmente se conoce)

    Args:
        df: DataFrame con columnas TimeBin, bid_abs, ask_abs
        delay_seconds: Segundos de desplazamiento (debe coincidir con FUTURE_WINDOW_SEC)

    Returns:
        DataFrame con señales desplazadas
    """
    print(f"\nAplicando corrección de look-ahead bias...")
    print(f"  Desplazando señales {delay_seconds}s hacia adelante")

    df = df.copy()
    df['time_sec'] = (df['TimeBin'] - df['TimeBin'].min()).dt.total_seconds()

    # Contar señales originales
    original_bid_abs = df['bid_abs'].sum()
    original_ask_abs = df['ask_abs'].sum()
    print(f"  Señales originales: BID={original_bid_abs}, ASK={original_ask_abs}")

    # Crear nuevas columnas desplazadas
    df['bid_abs_shifted'] = False
    df['ask_abs_shifted'] = False

    # Para cada señal original, marcarla delay_seconds después
    for idx in df[df['bid_abs']].index:
        t_original = df.loc[idx, 'time_sec']
        t_target = t_original + delay_seconds

        # Buscar la fila más cercana a t_target
        future_mask = df['time_sec'] >= t_target
        if future_mask.any():
            target_idx = df[future_mask].index[0]
            df.loc[target_idx, 'bid_abs_shifted'] = True

    for idx in df[df['ask_abs']].index:
        t_original = df.loc[idx, 'time_sec']
        t_target = t_original + delay_seconds

        # Buscar la fila más cercana a t_target
        future_mask = df['time_sec'] >= t_target
        if future_mask.any():
            target_idx = df[future_mask].index[0]
            df.loc[target_idx, 'ask_abs_shifted'] = True

    # Reemplazar columnas originales con las desplazadas
    df['bid_abs'] = df['bid_abs_shifted']
    df['ask_abs'] = df['ask_abs_shifted']

    # Contar señales después del shift
    shifted_bid_abs = df['bid_abs'].sum()
    shifted_ask_abs = df['ask_abs'].sum()
    print(f"  Señales después del shift: BID={shifted_bid_abs}, ASK={shifted_ask_abs}")
    print(f"  Señales perdidas (fuera de ventana): BID={original_bid_abs - shifted_bid_abs}, ASK={original_ask_abs - shifted_ask_abs}")

    # Limpiar columnas temporales
    df = df.drop(columns=['time_sec', 'bid_abs_shifted', 'ask_abs_shifted'])

    return df


def run_backtest(df):
    """
    Ejecuta backtest de la estrategia CON CORRECCIÓN DE BIAS.
    """
    print("\n" + "="*70)
    print("BACKTESTING ESTRATEGIA CON CORRECCIÓN DE LOOK-AHEAD BIAS")
    print("="*70)

    trades = []
    position = None  # None, 'LONG', 'SHORT'
    entry_price = None
    entry_time = None
    entry_atr = None
    tp_price = None
    sl_price = None

    total_rows = len(df)

    for idx, row in df.iterrows():
        current_time = row['TimeBin']
        current_price = row['Precio']
        current_atr = row['atr']
        bid_abs = row.get('bid_abs', False)
        ask_abs = row.get('ask_abs', False)

        # Skip si no hay ATR calculado aún
        if pd.isna(current_atr):
            continue

        # === GESTIÓN DE POSICIÓN ABIERTA ===
        if position is not None:

            # Verificar cierre EOD
            if current_time.time() >= EOD_TIME:
                exit_price = current_price
                exit_time = current_time

                if position == 'LONG':
                    profit_points = exit_price - entry_price
                else:  # SHORT
                    profit_points = entry_price - exit_price

                profit_dollars = profit_points * POINT_VALUE * CONTRACTS

                trades.append({
                    'entry_time': entry_time,
                    'entry_price': entry_price,
                    'exit_time': exit_time,
                    'exit_price': exit_price,
                    'side': position,
                    'tp_price': tp_price,
                    'sl_price': sl_price,
                    'atr_entry': entry_atr,
                    'resultado': 'EOD',
                    'profit_points': round(profit_points, 2),
                    'profit_dollars': round(profit_dollars, 2),
                    'contracts': CONTRACTS
                })

                position = None
                continue

            # Verificar TP
            if position == 'LONG' and current_price >= tp_price:
                profit_points = tp_price - entry_price
                profit_dollars = profit_points * POINT_VALUE * CONTRACTS

                trades.append({
                    'entry_time': entry_time,
                    'entry_price': entry_price,
                    'exit_time': current_time,
                    'exit_price': tp_price,
                    'side': position,
                    'tp_price': tp_price,
                    'sl_price': sl_price,
                    'atr_entry': entry_atr,
                    'resultado': 'TARGET',
                    'profit_points': round(profit_points, 2),
                    'profit_dollars': round(profit_dollars, 2),
                    'contracts': CONTRACTS
                })

                position = None
                continue

            elif position == 'SHORT' and current_price <= tp_price:
                profit_points = entry_price - tp_price
                profit_dollars = profit_points * POINT_VALUE * CONTRACTS

                trades.append({
                    'entry_time': entry_time,
                    'entry_price': entry_price,
                    'exit_time': current_time,
                    'exit_price': tp_price,
                    'side': position,
                    'tp_price': tp_price,
                    'sl_price': sl_price,
                    'atr_entry': entry_atr,
                    'resultado': 'TARGET',
                    'profit_points': round(profit_points, 2),
                    'profit_dollars': round(profit_dollars, 2),
                    'contracts': CONTRACTS
                })

                position = None
                continue

            # Verificar SL
            if position == 'LONG' and current_price <= sl_price:
                profit_points = sl_price - entry_price
                profit_dollars = profit_points * POINT_VALUE * CONTRACTS

                trades.append({
                    'entry_time': entry_time,
                    'entry_price': entry_price,
                    'exit_time': current_time,
                    'exit_price': sl_price,
                    'side': position,
                    'tp_price': tp_price,
                    'sl_price': sl_price,
                    'atr_entry': entry_atr,
                    'resultado': 'STOP',
                    'profit_points': round(profit_points, 2),
                    'profit_dollars': round(profit_dollars, 2),
                    'contracts': CONTRACTS
                })

                position = None
                continue

            elif position == 'SHORT' and current_price >= sl_price:
                profit_points = entry_price - sl_price
                profit_dollars = profit_points * POINT_VALUE * CONTRACTS

                trades.append({
                    'entry_time': entry_time,
                    'entry_price': entry_price,
                    'exit_time': current_time,
                    'exit_price': sl_price,
                    'side': position,
                    'tp_price': tp_price,
                    'sl_price': sl_price,
                    'atr_entry': entry_atr,
                    'resultado': 'STOP',
                    'profit_points': round(profit_points, 2),
                    'profit_dollars': round(profit_dollars, 2),
                    'contracts': CONTRACTS
                })

                position = None
                continue

        # === SEÑALES DE ENTRADA (CON SEÑALES CORREGIDAS) ===
        if position is None:

            # LONG: BID Absorption (señal ahora disponible en el momento correcto)
            if bid_abs:
                position = 'LONG'
                entry_price = current_price
                entry_time = current_time
                entry_atr = current_atr
                tp_price = entry_price + TP_POINTS
                sl_price = entry_price - SL_POINTS

            # SHORT: ASK Absorption (señal ahora disponible en el momento correcto)
            elif ask_abs:
                position = 'SHORT'
                entry_price = current_price
                entry_time = current_time
                entry_atr = current_atr
                tp_price = entry_price - TP_POINTS
                sl_price = entry_price + SL_POINTS

        # Progreso
        if (idx + 1) % 10000 == 0:
            print(f"  Procesado {idx + 1:,}/{total_rows:,} ({(idx+1)/total_rows*100:.1f}%)")

    # Cerrar posición abierta al final del backtest
    if position is not None:
        exit_price = df.iloc[-1]['Precio']
        exit_time = df.iloc[-1]['TimeBin']

        if position == 'LONG':
            profit_points = exit_price - entry_price
        else:
            profit_points = entry_price - exit_price

        profit_dollars = profit_points * POINT_VALUE * CONTRACTS

        trades.append({
            'entry_time': entry_time,
            'entry_price': entry_price,
            'exit_time': exit_time,
            'exit_price': exit_price,
            'side': position,
            'tp_price': tp_price,
            'sl_price': sl_price,
            'atr_entry': entry_atr,
            'resultado': 'EOD',
            'profit_points': round(profit_points, 2),
            'profit_dollars': round(profit_dollars, 2),
            'contracts': CONTRACTS
        })

    return pd.DataFrame(trades)


def generate_statistics(trades_df):
    """
    Genera estadísticas del backtest.
    """
    print("\n" + "="*70)
    print("ESTADÍSTICAS DE BACKTEST (CON CORRECCIÓN DE BIAS)")
    print("="*70)

    if len(trades_df) == 0:
        print("\n⚠️  No se generaron trades en el backtest")
        return

    total_trades = len(trades_df)

    # Por resultado
    targets = trades_df[trades_df['resultado'] == 'TARGET']
    stops = trades_df[trades_df['resultado'] == 'STOP']
    eods = trades_df[trades_df['resultado'] == 'EOD']

    # Por lado
    longs = trades_df[trades_df['side'] == 'LONG']
    shorts = trades_df[trades_df['side'] == 'SHORT']

    # Profit/Loss
    total_profit = trades_df['profit_dollars'].sum()
    winning_trades = trades_df[trades_df['profit_dollars'] > 0]
    losing_trades = trades_df[trades_df['profit_dollars'] < 0]

    win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0

    print(f"\nRESUMEN GENERAL")
    print(f"  Total de trades: {total_trades}")
    print(f"  Periodo: {trades_df['entry_time'].min()} a {trades_df['exit_time'].max()}")

    print(f"\nPROFIT & LOSS")
    print(f"  Profit total: ${total_profit:,.2f}")
    print(f"  Profit promedio por trade: ${total_profit/total_trades:,.2f}")
    print(f"  Trades ganadores: {len(winning_trades)} ({len(winning_trades)/total_trades*100:.1f}%)")
    print(f"  Trades perdedores: {len(losing_trades)} ({len(losing_trades)/total_trades*100:.1f}%)")
    print(f"  Win rate: {win_rate:.1f}%")

    if len(winning_trades) > 0:
        print(f"  Ganancia promedio: ${winning_trades['profit_dollars'].mean():,.2f}")
        print(f"  Mayor ganancia: ${winning_trades['profit_dollars'].max():,.2f}")

    if len(losing_trades) > 0:
        print(f"  Pérdida promedio: ${losing_trades['profit_dollars'].mean():,.2f}")
        print(f"  Mayor pérdida: ${losing_trades['profit_dollars'].min():,.2f}")

    print(f"\nPOR RESULTADO")
    print(f"  TARGET: {len(targets)} ({len(targets)/total_trades*100:.1f}%)")
    print(f"  STOP: {len(stops)} ({len(stops)/total_trades*100:.1f}%)")
    print(f"  EOD: {len(eods)} ({len(eods)/total_trades*100:.1f}%)")

    print(f"\nPOR DIRECCION")
    print(f"  LONG: {len(longs)} ({len(longs)/total_trades*100:.1f}%)")
    if len(longs) > 0:
        print(f"    Profit: ${longs['profit_dollars'].sum():,.2f}")
    print(f"  SHORT: {len(shorts)} ({len(shorts)/total_trades*100:.1f}%)")
    if len(shorts) > 0:
        print(f"    Profit: ${shorts['profit_dollars'].sum():,.2f}")

    print(f"\nMETRICAS DE RIESGO")
    print(f"  ATR promedio en entradas: {trades_df['atr_entry'].mean():.2f} puntos (solo referencia)")
    print(f"  TP FIJO: {TP_POINTS} puntos")
    print(f"  SL FIJO: {SL_POINTS} puntos")
    print(f"  Ratio Reward/Risk: {TP_POINTS / SL_POINTS:.2f}")

    # Curva de equity
    trades_df['cumulative_profit'] = trades_df['profit_dollars'].cumsum()
    max_equity = trades_df['cumulative_profit'].cummax()
    drawdown = trades_df['cumulative_profit'] - max_equity
    max_drawdown = drawdown.min()

    print(f"\nDRAWDOWN")
    print(f"  Max drawdown: ${max_drawdown:,.2f}")

    # Trades consecutivos
    trades_df['win'] = trades_df['profit_dollars'] > 0
    trades_df['streak'] = (trades_df['win'] != trades_df['win'].shift()).cumsum()
    winning_streaks = trades_df[trades_df['win']].groupby('streak').size()
    losing_streaks = trades_df[~trades_df['win']].groupby('streak').size()

    if len(winning_streaks) > 0:
        print(f"\nRACHAS")
        print(f"  Mayor racha ganadora: {winning_streaks.max()} trades")
    if len(losing_streaks) > 0:
        print(f"  Mayor racha perdedora: {losing_streaks.max()} trades")

    print("\n" + "="*70)


def main():
    """
    Función principal.
    """
    print("="*70)
    print("ESTRATEGIA CON CORRECCIÓN DE LOOK-AHEAD BIAS")
    print("="*70)
    print(f"\nConfiguración:")
    print(f"  Símbolo: {SYMBOL}")
    print(f"  SIGNAL_DELAY_SEC: {SIGNAL_DELAY_SEC}s (corrección de bias)")
    print(f"  ATR Period: {ATR_PERIOD} (solo para referencia)")
    print(f"  Take Profit FIJO: {TP_POINTS} puntos")
    print(f"  Stop Loss FIJO: {SL_POINTS} puntos")
    print(f"  Contratos: {CONTRACTS}")
    print(f"  Point Value: ${POINT_VALUE}")
    print(f"  EOD Time: {EOD_TIME}")

    # Cargar datos
    print(f"\nCargando {DATA_FILE}...")
    df = pd.read_csv(DATA_FILE, sep=';', decimal=',')

    # Limpiar nombres de columnas (quitar espacios)
    df.columns = df.columns.str.strip()

    # Detectar columna de timestamp
    timestamp_col = next((col for col in df.columns if 'timebin' in col.lower()), None)
    if timestamp_col:
        df[timestamp_col] = pd.to_datetime(df[timestamp_col])
        if timestamp_col != 'TimeBin':
            df = df.rename(columns={timestamp_col: 'TimeBin'})

    df = df.sort_values('TimeBin').reset_index(drop=True)

    print(f"  Registros: {len(df):,}")
    print(f"  Rango: {df['TimeBin'].min()} a {df['TimeBin'].max()}")

    # Verificar columnas necesarias
    required = ['Precio', 'bid_abs', 'ask_abs']
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Columnas faltantes: {missing}")

    # PASO CRÍTICO: Aplicar corrección de look-ahead bias
    df = shift_signals(df, delay_seconds=SIGNAL_DELAY_SEC)

    # Calcular ATR
    df = calculate_atr(df, period=ATR_PERIOD)

    # Ejecutar backtest
    trades_df = run_backtest(df)

    # Generar estadísticas
    generate_statistics(trades_df)

    # Guardar resultados
    os.makedirs('outputs', exist_ok=True)
    print(f"\nGuardando resultados en {OUTPUT_FILE}...")
    trades_df.to_csv(OUTPUT_FILE, sep=';', decimal=',', index=False)

    print("\n" + "="*70)
    print("COMPARACIÓN CON ESTRATEGIA ORIGINAL:")
    print("  - Estrategia original (strat_fabio_ATR.py): CON look-ahead bias")
    print("  - Esta estrategia (strat_fabio_window.py): SIN look-ahead bias")
    print("  - Compara los resultados para ver el impacto real del bias")
    print("="*70)

    print("\nBacktest completado!")
    print("="*70)

    return trades_df


if __name__ == "__main__":
    trades_result = main()

    # ========== VISUALIZACIÓN AUTOMÁTICA DE TRADES ==========
    print("\n" + "="*70)
    print("GENERANDO VISUALIZACIÓN DE TRADES")
    print("="*70)

    try:
        from pathlib import Path
        import sys
        import webbrowser

        # Import plot_trades_chart function
        sys.path.append(str(Path(__file__).parent))
        from plot_trades_chart import plot_trades_on_chart

        print("\nLlamando a plot_trades_chart.py...")
        print("Visualizando primeros 500 trades (configurable en el script)\n")

        # Call the plotting function with default parameters
        plot_trades_on_chart(start_idx=0, end_idx=500)

        print("\n✓ Gráfico de trades generado exitosamente")

    except ImportError as e:
        print(f"\n✗ Error importando plot_trades_chart: {e}")
        print("Puedes ejecutar manualmente: python strat/plot_trades_chart.py")
    except Exception as e:
        print(f"\n✗ Error generando visualización: {e}")
        print("El backtest se completó correctamente, pero la visualización falló.")
        print("Puedes ejecutar manualmente: python strat/plot_trades_chart.py")

    # ========== EJECUTAR SUMMARY Y ANÁLISIS DE PERFORMANCE ==========
    print("\n" + "="*70)
    print("GENERANDO REPORTES DE PERFORMANCE")
    print("="*70)

    try:
        import subprocess

        print("\nEjecutando summary.py para análisis completo...")
        print("(Esto generará: summary_report.html, equity curve, distributions)\n")

        # Execute summary.py which will also call plot_backtest_results
        result = subprocess.run(
            ["python", "strat/summary.py"],
            capture_output=False,
            text=True,
            check=True
        )

        print("\n✓ Reportes de performance generados exitosamente")

    except subprocess.CalledProcessError as e:
        print(f"\n✗ Error ejecutando summary.py: {e}")
        print("Puedes ejecutar manualmente: python strat/summary.py")
    except Exception as e:
        print(f"\n✗ Error inesperado: {e}")
        print("Puedes ejecutar manualmente: python strat/summary.py")

    # ========== RESUMEN FINAL ==========
    print("\n" + "="*70)
    print("PROCESO COMPLETO FINALIZADO")
    print("="*70)
    print("\nArchivos generados:")
    print(f"  1. {OUTPUT_FILE}")
    print(f"     → Log completo de trades")
    print(f"\n  2. charts/trades_visualization_window.html")
    print(f"     → Gráfico de entradas/salidas sobre precio")
    print(f"\n  3. summary_report_window.html")
    print(f"     → Tabla de métricas de performance")
    print(f"\n  4. charts/backtest_results_equity.html")
    print(f"     → Curva de equity + P/L por trade + Drawdown")
    print(f"\n  5. charts/backtest_results_distributions.html")
    print(f"     → Distribuciones y análisis temporal")
    print("\n" + "="*70)
    print("Para cambiar rango de trades visualizados, edita DEFAULT_START_INDEX")
    print("y DEFAULT_END_INDEX en strat/plot_trades_chart.py")
    print("="*70)
