"""
Estrategia de Trading basada en Volumen Extremo - SOLO SEÑALES REALES (NO FAKE).

Lógica Base:
- LONG: Cuando bid_vol = True AND fake_bid_vol = False (círculo rojo REAL)
- SHORT: Cuando ask_vol = True AND fake_ask_vol = False (círculo verde REAL)
- TP/SL: Fijos en 2 puntos ($40)

FILTRO CLAVE: Elimina señales "fake" (invalidadas por señal más fuerte en 30s)

Modos de Filtrado (mutuamente excluyentes):

MODO_1: VOLUME_ONLY (solo filtro fake)
  - LONG: bid_vol = True AND NOT fake_bid_vol
  - SHORT: ask_vol = True AND NOT fake_ask_vol

MODO_2: DENSITY (filtro fake + densidad individual)
  - LONG: bid_vol = True AND NOT fake_bid_vol AND bid_density > DENSITY_THRESHOLD
  - SHORT: ask_vol = True AND NOT fake_ask_vol AND ask_density > DENSITY_THRESHOLD

MODO_3: NET_DENSITY (filtro fake + net_density)
  - LONG: bid_vol = True AND NOT fake_bid_vol AND net_density < -NET_DENSITY_THRESHOLD
  - SHORT: ask_vol = True AND NOT fake_ask_vol AND net_density > NET_DENSITY_THRESHOLD

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
STRAT_NAME = 'strat_fabio_vol_not_fake'
SYMBOL = 'NQ'
DATA_FILE = f'data/time_and_sales_absorption_{SYMBOL}.csv'
OUTPUT_FILE = f'outputs/trading_record_{STRAT_NAME}.csv'

# Parámetros de la estrategia
TP_POINTS = 2.0  # Take Profit: 2 puntos = $40
SL_POINTS = 2.0  # Stop Loss: 2 puntos = -$40

# ==============================================================================
# SISTEMA DE FILTROS - Selecciona UNO de los tres modos
# ==============================================================================
# MODO_1: Entra en CADA círculo rojo (LONG) o verde (SHORT) sin filtros
#         Máximo número de trades, sin restricciones de densidad
#
# MODO_2: Solo entra si hay CLUSTERING (densidad > 10)
#         LONG: círculo rojo + bid_density > 10 (muchos vendedores juntos)
#         SHORT: círculo verde + ask_density > 10 (muchos compradores juntos)
#         Usa las líneas roja/verde del subplot de densidad (eje Y izquierdo)
#
# MODO_3: Solo entra en ÁREAS coloreadas (net_density fuerte)
#         LONG: círculo rojo + net_density < -10 (área ROJA, predominio vendedores)
#         SHORT: círculo verde + net_density > 10 (área VERDE, predominio compradores)
#         Usa la línea negra y áreas de color (eje Y derecho)
# ==============================================================================
FILTER_MODE = "MODO_1"  # Opciones: "MODO_1", "MODO_2", "MODO_3"

# Umbrales para filtros
DENSITY_THRESHOLD = 10      # Para MODO_2 (densidad individual)
NET_DENSITY_THRESHOLD = 10  # Para MODO_3 (net_density = ASK - BID)
# ==============================================================================

# Configuración del instrumento
TICK_SIZE = 0.25  # NQ tick size
POINT_VALUE = 20  # 1 punto NQ = $20
CONTRACTS = 1  # Contratos por operación

# Horario de trading
EOD_TIME = time(22, 0)  # 22:00 PM


def load_data(filepath):
    """Carga datos de time & sales con volumen extremo."""
    print(f"Cargando datos desde {filepath}...")

    df = pd.read_csv(filepath, sep=';', decimal=',', low_memory=False)

    # Limpiar nombres de columnas (quitar espacios)
    df.columns = df.columns.str.strip()

    # Convertir columnas booleanas que están como strings
    bool_cols = ['bid_vol', 'ask_vol', 'fake_bid_vol', 'fake_ask_vol', 'is_anomaly']
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.lower() == 'true'

    df['TimeBin'] = pd.to_datetime(df['TimeBin'])
    df = df.sort_values('TimeBin').reset_index(drop=True)

    print(f"  Total registros: {len(df):,}")
    print(f"  Rango temporal: {df['TimeBin'].min()} a {df['TimeBin'].max()}")

    # Verificar columnas necesarias
    required_cols = ['TimeBin', 'Precio', 'Volumen', 'bid_vol', 'ask_vol', 'fake_bid_vol', 'fake_ask_vol']
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {missing}")

    # Verificar columnas según el modo de filtro
    if FILTER_MODE == "MODO_1":
        print(f"  Modo: VOLUME_ONLY (solo filtro fake, sin densidad)")

    elif FILTER_MODE == "MODO_2":
        if 'bid_density' not in df.columns or 'ask_density' not in df.columns:
            raise ValueError("MODO_2 requiere columnas bid_density/ask_density")
        print(f"  Modo: DENSITY (threshold: {DENSITY_THRESHOLD})")

    elif FILTER_MODE == "MODO_3":
        if 'net_density' not in df.columns:
            raise ValueError("MODO_3 requiere columna net_density")
        print(f"  Modo: NET_DENSITY (threshold: {NET_DENSITY_THRESHOLD})")

    else:
        raise ValueError(f"FILTER_MODE inválido: {FILTER_MODE}. Usa 'MODO_1', 'MODO_2' o 'MODO_3'")

    return df


def run_backtest(df):
    """Ejecuta backtest de la estrategia de volumen extremo."""
    print("\n" + "="*70)
    print(f"BACKTESTING: {STRAT_NAME.upper()}")
    print("="*70)
    print(f"  TP: {TP_POINTS} pts (${TP_POINTS * POINT_VALUE})")
    print(f"  SL: {SL_POINTS} pts (${SL_POINTS * POINT_VALUE})")
    print(f"  Modo de filtro: {FILTER_MODE}")
    if FILTER_MODE == "MODO_2":
        print(f"  Threshold densidad: {DENSITY_THRESHOLD}")
    elif FILTER_MODE == "MODO_3":
        print(f"  Threshold net_density: {NET_DENSITY_THRESHOLD}")
    print("="*70)

    trades = []
    position = None  # None, 'LONG', 'SHORT'
    entry_price = None
    entry_time = None
    tp_price = None
    sl_price = None
    entry_density_bid = None
    entry_density_ask = None
    entry_net_density = None

    for idx, row in df.iterrows():
        current_time = row['TimeBin']
        current_price = row['Precio']
        bid_vol = row.get('bid_vol', False)
        ask_vol = row.get('ask_vol', False)
        fake_bid_vol = row.get('fake_bid_vol', False)
        fake_ask_vol = row.get('fake_ask_vol', False)

        # Obtener métricas según el modo
        bid_density = row.get('bid_density', 0)
        ask_density = row.get('ask_density', 0)
        net_density = row.get('net_density', 0)

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
                    'entry_bid_density': entry_density_bid,
                    'entry_ask_density': entry_density_ask,
                    'entry_net_density': entry_net_density,
                    'filter_mode': FILTER_MODE,
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
                    'entry_bid_density': entry_density_bid,
                    'entry_ask_density': entry_density_ask,
                    'entry_net_density': entry_net_density,
                    'filter_mode': FILTER_MODE,
                    'resultado': 'TP',
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
                    'entry_bid_density': entry_density_bid,
                    'entry_ask_density': entry_density_ask,
                    'entry_net_density': entry_net_density,
                    'filter_mode': FILTER_MODE,
                    'resultado': 'TP',
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
                    'entry_bid_density': entry_density_bid,
                    'entry_ask_density': entry_density_ask,
                    'entry_net_density': entry_net_density,
                    'filter_mode': FILTER_MODE,
                    'resultado': 'SL',
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
                    'entry_bid_density': entry_density_bid,
                    'entry_ask_density': entry_density_ask,
                    'entry_net_density': entry_net_density,
                    'filter_mode': FILTER_MODE,
                    'resultado': 'SL',
                    'profit_points': round(profit_points, 2),
                    'profit_dollars': round(profit_dollars, 2),
                    'contracts': CONTRACTS
                })

                position = None
                continue

        # === SEÑALES DE ENTRADA ===
        if position is None:

            # === SEÑALES DE ENTRADA SEGÚN MODO ===

            # LONG: Círculo rojo REAL (bid_vol = True AND NOT fake_bid_vol)
            if bid_vol and not fake_bid_vol:
                long_signal = False

                if FILTER_MODE == "MODO_1":
                    # Solo filtro fake (sin densidad)
                    long_signal = True

                elif FILTER_MODE == "MODO_2":
                    # Filtro fake + densidad individual
                    if bid_density > DENSITY_THRESHOLD:
                        long_signal = True

                elif FILTER_MODE == "MODO_3":
                    # Filtro fake + net_density (área roja, más BID que ASK)
                    if net_density < -NET_DENSITY_THRESHOLD:
                        long_signal = True

                if long_signal:
                    position = 'LONG'
                    entry_price = current_price
                    entry_time = current_time
                    tp_price = entry_price + TP_POINTS
                    sl_price = entry_price - SL_POINTS
                    entry_density_bid = bid_density
                    entry_density_ask = ask_density
                    entry_net_density = net_density

            # SHORT: Círculo verde REAL (ask_vol = True AND NOT fake_ask_vol)
            elif ask_vol and not fake_ask_vol:
                short_signal = False

                if FILTER_MODE == "MODO_1":
                    # Solo filtro fake (sin densidad)
                    short_signal = True

                elif FILTER_MODE == "MODO_2":
                    # Filtro fake + densidad individual
                    if ask_density > DENSITY_THRESHOLD:
                        short_signal = True

                elif FILTER_MODE == "MODO_3":
                    # Filtro fake + net_density (área verde, más ASK que BID)
                    if net_density > NET_DENSITY_THRESHOLD:
                        short_signal = True

                if short_signal:
                    position = 'SHORT'
                    entry_price = current_price
                    entry_time = current_time
                    tp_price = entry_price - TP_POINTS
                    sl_price = entry_price + SL_POINTS
                    entry_density_bid = bid_density
                    entry_density_ask = ask_density
                    entry_net_density = net_density

    # Convertir a DataFrame
    df_trades = pd.DataFrame(trades)

    # Agregar columna de profit acumulado
    if len(df_trades) > 0:
        df_trades['cumulative_profit'] = df_trades['profit_dollars'].cumsum()

    return df_trades


def print_results(df_trades):
    """Imprime estadísticas del backtest."""
    print("\n" + "="*70)
    print("RESULTADOS DEL BACKTEST")
    print("="*70)

    if len(df_trades) == 0:
        print("No se generaron trades.")
        return

    total_trades = len(df_trades)
    winning_trades = len(df_trades[df_trades['profit_dollars'] > 0])
    losing_trades = len(df_trades[df_trades['profit_dollars'] < 0])
    breakeven_trades = len(df_trades[df_trades['profit_dollars'] == 0])

    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

    total_profit = df_trades['profit_dollars'].sum()
    avg_profit = df_trades['profit_dollars'].mean()

    avg_win = df_trades[df_trades['profit_dollars'] > 0]['profit_dollars'].mean() if winning_trades > 0 else 0
    avg_loss = df_trades[df_trades['profit_dollars'] < 0]['profit_dollars'].mean() if losing_trades > 0 else 0

    # Profit factor
    gross_profit = df_trades[df_trades['profit_dollars'] > 0]['profit_dollars'].sum()
    gross_loss = abs(df_trades[df_trades['profit_dollars'] < 0]['profit_dollars'].sum())
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')

    # Resultados por tipo
    tp_count = len(df_trades[df_trades['resultado'] == 'TP'])
    sl_count = len(df_trades[df_trades['resultado'] == 'SL'])
    eod_count = len(df_trades[df_trades['resultado'] == 'EOD'])

    print(f"\nTotal Trades: {total_trades}")
    print(f"  Ganadores: {winning_trades} ({win_rate:.1f}%)")
    print(f"  Perdedores: {losing_trades} ({(losing_trades/total_trades*100):.1f}%)")
    print(f"  Breakeven: {breakeven_trades}")

    print(f"\nResultados por Salida:")
    print(f"  TP: {tp_count} ({(tp_count/total_trades*100):.1f}%)")
    print(f"  SL: {sl_count} ({(sl_count/total_trades*100):.1f}%)")
    print(f"  EOD: {eod_count} ({(eod_count/total_trades*100):.1f}%)")

    print(f"\nRentabilidad:")
    print(f"  Beneficio total: ${total_profit:,.2f}")
    print(f"  Beneficio promedio: ${avg_profit:,.2f}")
    print(f"  Ganancia promedio: ${avg_win:,.2f}")
    print(f"  Pérdida promedio: ${avg_loss:,.2f}")
    print(f"  Profit Factor: {profit_factor:.2f}")

    # Distribución por lado
    long_trades = df_trades[df_trades['side'] == 'LONG']
    short_trades = df_trades[df_trades['side'] == 'SHORT']

    print(f"\nDistribución por Lado:")
    print(f"  LONG: {len(long_trades)} trades, Profit: ${long_trades['profit_dollars'].sum():,.2f}")
    print(f"  SHORT: {len(short_trades)} trades, Profit: ${short_trades['profit_dollars'].sum():,.2f}")

    print("\n" + "="*70)


def main():
    """Función principal."""
    print("\n" + "="*70)
    print(f"ESTRATEGIA: {STRAT_NAME.upper()}")
    print("="*70)

    # Cargar datos
    df = load_data(DATA_FILE)

    # Ejecutar backtest
    df_trades = run_backtest(df)

    # Imprimir resultados
    print_results(df_trades)

    # Guardar resultados
    if len(df_trades) > 0:
        os.makedirs('outputs', exist_ok=True)
        df_trades.to_csv(OUTPUT_FILE, index=False, sep=';', decimal=',')
        print(f"\nTrades guardados en: {OUTPUT_FILE}")

        # Auto-ejecutar scripts de visualización
        print("\n" + "="*70)
        print("GENERANDO REPORTES Y GRÁFICOS")
        print("="*70)

        try:
            # Ejecutar summary.py (genera tabla + equity curve + distributions)
            import sys
            from pathlib import Path
            sys.path.append(str(Path(__file__).parent))

            print("\nEjecutando summary.py...")
            import summary

            # Ejecutar plot_trades_chart.py
            print("\n" + "="*70)
            print("GENERANDO GRÁFICO DE TRADES EN PRECIO")
            print("="*70)

            from plot_trades_chart import plot_trades_on_chart
            plot_trades_on_chart(start_idx=0, end_idx=500)

            print("\n" + "="*70)
            print("TODOS LOS REPORTES GENERADOS CON ÉXITO")
            print("="*70)

        except Exception as e:
            print(f"\nError generando reportes: {e}")
            print("Puedes ejecutar manualmente:")
            print("  python strat_OM_2/summary.py")
            print("  python strat_OM_2/plot_trades_chart.py")

    return df_trades


if __name__ == "__main__":
    df_trades = main()
