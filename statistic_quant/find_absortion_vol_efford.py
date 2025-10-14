"""
Detecta absorción en datos de Time & Sales del NQ.
Versión SIMPLIFICADA y CORRECTA.

Absorción = Volumen anormalmente alto que NO produce el movimiento de precio esperado:
- BID absorption: Fuerte venta que NO hace bajar el precio
- ASK absorption: Fuerte compra que NO hace subir el precio
"""

import pandas as pd
import numpy as np

# Configuración
SYMBOL = 'NQ'  # Cambiar a 'ES' para E-mini S&P 500
DATA_FILE = f'data/time_and_sales_{SYMBOL.lower()}.csv'
OUTPUT_FILE = f'data/time_and_sales_absorption_{SYMBOL}.csv'

# ==============================================================================
# PARÁMETROS DE DETECCIÓN - CONFIGURACIÓN RÁPIDA Y AJUSTADA
# ==============================================================================
# OBJETIVO: Señales más rápidas con TP/SL equilibrado (2.0/2.0)
#
# CONFIGURACIONES ANTERIORES:
#   Config 1: WINDOW=5, THRESHOLD=1.5, TICKS=2, FUTURE=60  → Muchas señales
#   Config 2: WINDOW=10, THRESHOLD=2.0, TICKS=3, FUTURE=90 → Pocas señales
#
# NUEVA (equilibrio - señales rápidas y selectivas):
WINDOW_MINUTES = 10          # Ventana amplia para estadísticas robustas
ANOMALY_THRESHOLD = 2.0      # Solo top 5% volúmenes

# Parámetros de densidad
DENSITY_WINDOW_SEC = 180     # Ventana para calcular densidad (3 minutos)
# ==============================================================================


def load_and_prepare_data(filepath):
    """Carga datos y prepara para análisis."""
    print(f"Cargando {filepath}...")
    df = pd.read_csv(filepath, sep=';', decimal=',')
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    df = df.sort_values('Timestamp').reset_index(drop=True)

    print(f"  Registros: {len(df):,}")
    print(f"  Rango: {df['Timestamp'].min()} a {df['Timestamp'].max()}")
    print(f"  Precios únicos: {df['Precio'].nunique()}")

    # Resamplear a medio segundo para mayor granularidad
    print("\nResampleando a bins de 500ms...")
    df['TimeBin'] = df['Timestamp'].dt.floor('500ms')

    resampled = df.groupby(['TimeBin', 'Precio', 'Lado'], as_index=False).agg({
        'Volumen': 'sum',
        'Timestamp': 'first'
    })

    resampled = resampled.sort_values('TimeBin').reset_index(drop=True)
    print(f"  Reducido a {len(resampled):,} registros ({len(resampled)/len(df)*100:.1f}%)")

    return resampled


def compute_volume_stats_simple(df, window_minutes=5):
    """
    Calcula estadísticas de volumen usando enfoque simple:
    Para cada fila, calcula stats del volumen en su ventana temporal.
    """
    print(f"\nCalculando estadísticas de volumen (ventana {window_minutes}min)...")

    df = df.copy()
    window_sec = window_minutes * 60

    # Convertir a timestamp numérico
    df['time_sec'] = (df['TimeBin'] - df['TimeBin'].min()).dt.total_seconds()

    # Inicializar columnas de estadísticas
    df['vol_current_price'] = 0.0  # Volumen acumulado del nivel de precio específico
    df['vol_mean'] = np.nan
    df['vol_std'] = np.nan
    df['vol_zscore'] = 0.0

    # Separar por lado para procesar
    for lado in ['BID', 'ASK']:
        lado_mask = df['Lado'] == lado
        indices = df[lado_mask].index

        print(f"  Procesando {lado} ({len(indices):,} registros)...")

        for idx_num, idx in enumerate(indices):
            t = df.loc[idx, 'time_sec']
            precio = df.loc[idx, 'Precio']

            # Ventana temporal
            window_mask = lado_mask & \
                         (df['time_sec'] >= t - window_sec) & \
                         (df['time_sec'] <= t)

            window_data = df[window_mask]

            if len(window_data) < 5:
                continue

            # Agregar por precio en ventana
            vol_by_price = window_data.groupby('Precio')['Volumen'].sum()

            if len(vol_by_price) < 3:
                continue

            # Estadísticas
            vol_mean = vol_by_price.mean()
            vol_std = vol_by_price.std()
            vol_current = vol_by_price.get(precio, 0)

            df.loc[idx, 'vol_current_price'] = vol_current  # Volumen acumulado del nivel de precio
            df.loc[idx, 'vol_mean'] = vol_mean
            df.loc[idx, 'vol_std'] = vol_std

            # Z-score
            if vol_std > 0:
                df.loc[idx, 'vol_zscore'] = (vol_current - vol_mean) / vol_std

            if (idx_num + 1) % 5000 == 0:
                print(f"    {idx_num + 1:,}/{len(indices):,} ({(idx_num+1)/len(indices)*100:.1f}%)")

    return df


def detect_anomalies(df, threshold=1.5):
    """Marca volúmenes anormales basado en Z-score."""
    print(f"\nDetectando anomalías (threshold={threshold} std)...")

    df = df.copy()
    df['is_anomaly'] = df['vol_zscore'].abs() >= threshold

    # Diagnóstico
    bid_zscores = df[df['Lado'] == 'BID']['vol_zscore']
    ask_zscores = df[df['Lado'] == 'ASK']['vol_zscore']

    print(f"  Z-scores BID: max={bid_zscores.max():.2f}, p95={bid_zscores.quantile(0.95):.2f}")
    print(f"  Z-scores ASK: max={ask_zscores.max():.2f}, p95={ask_zscores.quantile(0.95):.2f}")

    bid_anom = df[(df['Lado'] == 'BID') & df['is_anomaly']]
    ask_anom = df[(df['Lado'] == 'ASK') & df['is_anomaly']]

    print(f"  Anomalías BID: {len(bid_anom):,}")
    print(f"  Anomalías ASK: {len(ask_anom):,}")

    # Columnas separadas por lado
    df['bid_vol'] = (df['Lado'] == 'BID') & df['is_anomaly']
    df['ask_vol'] = (df['Lado'] == 'ASK') & df['is_anomaly']

    return df


# Función detect_absorption eliminada - se reevaluará el método


def compute_density(df, density_window_sec=120):
    """
    Calcula densidad de volumen extremo en ventana temporal.
    Cuenta cuántos eventos de volumen extremo (círculos rojos/verdes) hay cerca en el tiempo.

    Para cada registro, cuenta:
    - bid_density: cantidad de bid_vol=True en ventana de ±60s (total 120s)
    - ask_density: cantidad de ask_vol=True en ventana de ±60s (total 120s)

    La densidad refleja clustering temporal de volúmenes extremos.
    """
    print(f"\nCalculando densidad de volumen extremo (ventana {density_window_sec}s)...")

    df = df.copy()
    df['bid_density'] = 0
    df['ask_density'] = 0

    time_sec = df['time_sec'].values
    bid_vol = df['bid_vol'].values  # Volumen extremo BID
    ask_vol = df['ask_vol'].values  # Volumen extremo ASK

    half_window = density_window_sec / 2

    print(f"  Procesando {len(df):,} registros...")

    for idx in range(len(df)):
        t = time_sec[idx]

        # Ventana temporal: [t - 60s, t + 60s]
        window_mask = (time_sec >= t - half_window) & (time_sec <= t + half_window)

        # Contar volúmenes extremos en ventana (círculos rojos/verdes)
        bid_count = bid_vol[window_mask].sum()
        ask_count = ask_vol[window_mask].sum()

        df.loc[idx, 'bid_density'] = bid_count
        df.loc[idx, 'ask_density'] = ask_count

        if (idx + 1) % 10000 == 0:
            print(f"    {idx + 1:,}/{len(df):,} ({(idx+1)/len(df)*100:.1f}%)")

    # Estadísticas
    bid_density_nonzero = df[df['bid_density'] > 0]['bid_density']
    ask_density_nonzero = df[df['ask_density'] > 0]['ask_density']

    print(f"\n  BID density stats:")
    if len(bid_density_nonzero) > 0:
        print(f"    Registros con densidad > 0: {len(bid_density_nonzero):,}")
        print(f"    Media: {bid_density_nonzero.mean():.2f}")
        print(f"    Max: {bid_density_nonzero.max():.0f}")

    print(f"\n  ASK density stats:")
    if len(ask_density_nonzero) > 0:
        print(f"    Registros con densidad > 0: {len(ask_density_nonzero):,}")
        print(f"    Media: {ask_density_nonzero.mean():.2f}")
        print(f"    Max: {ask_density_nonzero.max():.0f}")

    # Calcular net_density (ASK - BID)
    df['net_density'] = df['ask_density'] - df['bid_density']

    print(f"\n  NET density stats (ASK - BID):")
    print(f"    Media: {df['net_density'].mean():.2f}")
    print(f"    Min: {df['net_density'].min():.2f}")
    print(f"    Max: {df['net_density'].max():.2f}")

    return df


def print_summary(df):
    """Imprime resumen de resultados."""
    print("\n" + "="*80)
    print("RESUMEN")
    print("="*80)

    total = len(df)
    bid_vol = df['bid_vol'].sum()
    ask_vol = df['ask_vol'].sum()

    print(f"\nTotal registros: {total:,}")
    print(f"\nVolumen extremo (Z-score >= {ANOMALY_THRESHOLD}):")
    print(f"  BID: {bid_vol:,} ({bid_vol/total*100:.2f}%)")
    print(f"  ASK: {ask_vol:,} ({ask_vol/total*100:.2f}%)")

    # Ejemplos de volumen extremo
    print("\n--- EJEMPLOS BID VOLUMEN EXTREMO ---")
    bid_ex = df[df['bid_vol']].nlargest(5, 'vol_zscore')
    if len(bid_ex) > 0:
        print(bid_ex[['TimeBin', 'Precio', 'Volumen', 'vol_zscore', 'vol_current_price']].to_string(index=False))

    print("\n--- EJEMPLOS ASK VOLUMEN EXTREMO ---")
    ask_ex = df[df['ask_vol']].nlargest(5, 'vol_zscore')
    if len(ask_ex) > 0:
        print(ask_ex[['TimeBin', 'Precio', 'Volumen', 'vol_zscore', 'vol_current_price']].to_string(index=False))

    print("\n" + "="*80)


def main():
    print("="*80)
    print("ANÁLISIS DE VOLUMEN EXTREMO - NQ TIME & SALES")
    print("="*80)
    print(f"Parámetros:")
    print(f"  Ventana: {WINDOW_MINUTES}min")
    print(f"  Threshold: {ANOMALY_THRESHOLD} std")
    print(f"  Ventana densidad: {DENSITY_WINDOW_SEC}s")
    print("="*80)

    df = load_and_prepare_data(DATA_FILE)
    df = compute_volume_stats_simple(df, window_minutes=WINDOW_MINUTES)
    df = detect_anomalies(df, threshold=ANOMALY_THRESHOLD)
    df = compute_density(df, density_window_sec=DENSITY_WINDOW_SEC)

    print_summary(df)

    print(f"\nGuardando en {OUTPUT_FILE}...")
    df.to_csv(OUTPUT_FILE, sep=';', decimal=',', index=False)
    print("Completado!")

    return df


if __name__ == "__main__":
    df_result = main()
