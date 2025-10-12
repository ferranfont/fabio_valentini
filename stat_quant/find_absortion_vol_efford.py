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

WINDOW_MINUTES = 5
ANOMALY_THRESHOLD = 1.5  # Desviaciones estándar
PRICE_MOVE_TICKS = 2  # Ticks mínimos esperados de movimiento
TICK_SIZE = 0.25  # NQ: 0.25, ES: 0.25
FUTURE_WINDOW_SEC = 60


def load_and_prepare_data(filepath):
    """Carga datos y prepara para análisis."""
    print(f"Cargando {filepath}...")
    df = pd.read_csv(filepath, sep=';', decimal=',')
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    df = df.sort_values('Timestamp').reset_index(drop=True)

    print(f"  Registros: {len(df):,}")
    print(f"  Rango: {df['Timestamp'].min()} a {df['Timestamp'].max()}")
    print(f"  Precios únicos: {df['Precio'].nunique()}")

    # Resamplear a 5 segundos para acelerar
    print("\nResampleando a bins de 5s...")
    df['TimeBin'] = df['Timestamp'].dt.floor('5s')

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


def detect_absorption(df, price_move_ticks=2, tick_size=0.25, future_window_sec=60):
    """
    Detecta absorción: volumen anormal sin movimiento de precio proporcional.
    """
    print(f"\nDetectando absorción (movimiento esperado: {price_move_ticks} ticks)...")

    df = df.copy()
    df['bid_abs'] = False
    df['ask_abs'] = False
    df['price_move_ticks'] = 0.0

    # Solo analizar registros con anomalías
    anomaly_indices = df[df['is_anomaly']].index
    print(f"  Analizando {len(anomaly_indices):,} anomalías...")

    time_sec = df['time_sec'].values
    prices = df['Precio'].values
    sides = df['Lado'].values

    for idx_num, idx in enumerate(anomaly_indices):
        t = df.loc[idx, 'time_sec']
        precio = df.loc[idx, 'Precio']
        lado = df.loc[idx, 'Lado']

        # Ventana futura
        future_mask = (time_sec > t) & (time_sec <= t + future_window_sec)
        future_prices = prices[future_mask]

        if len(future_prices) == 0:
            continue

        if lado == 'BID':
            # BID: esperamos caída del precio tras venta fuerte
            min_price = future_prices.min()
            price_drop_ticks = (precio - min_price) / tick_size
            df.loc[idx, 'price_move_ticks'] = -price_drop_ticks

            # Absorción si NO cae lo suficiente
            if price_drop_ticks < price_move_ticks:
                df.loc[idx, 'bid_abs'] = True

        else:  # ASK
            # ASK: esperamos subida del precio tras compra fuerte
            max_price = future_prices.max()
            price_rise_ticks = (max_price - precio) / tick_size
            df.loc[idx, 'price_move_ticks'] = price_rise_ticks

            # Absorción si NO sube lo suficiente
            if price_rise_ticks < price_move_ticks:
                df.loc[idx, 'ask_abs'] = True

        if (idx_num + 1) % 200 == 0:
            print(f"    {idx_num + 1:,}/{len(anomaly_indices):,} ({(idx_num+1)/len(anomaly_indices)*100:.1f}%)")

    print(f"  BID absorción: {df['bid_abs'].sum():,}")
    print(f"  ASK absorción: {df['ask_abs'].sum():,}")

    return df


def print_summary(df):
    """Imprime resumen de resultados."""
    print("\n" + "="*80)
    print("RESUMEN")
    print("="*80)

    total = len(df)
    bid_vol = df['bid_vol'].sum()
    ask_vol = df['ask_vol'].sum()
    bid_abs = df['bid_abs'].sum()
    ask_abs = df['ask_abs'].sum()

    print(f"\nTotal registros: {total:,}")
    print(f"\nVolumen anormal:")
    print(f"  BID: {bid_vol:,} ({bid_vol/total*100:.2f}%)")
    print(f"  ASK: {ask_vol:,} ({ask_vol/total*100:.2f}%)")

    print(f"\nAbsorción:")
    print(f"  BID: {bid_abs:,} ({bid_abs/total*100:.3f}%)")
    if bid_vol > 0:
        print(f"       {bid_abs/bid_vol*100:.1f}% de anomalías BID")
    print(f"  ASK: {ask_abs:,} ({ask_abs/total*100:.3f}%)")
    if ask_vol > 0:
        print(f"       {ask_abs/ask_vol*100:.1f}% de anomalías ASK")

    # Ejemplos
    print("\n--- EJEMPLOS BID ABSORCIÓN ---")
    bid_ex = df[df['bid_abs']].nlargest(5, 'vol_zscore')
    if len(bid_ex) > 0:
        print(bid_ex[['TimeBin', 'Precio', 'Volumen', 'vol_zscore', 'price_move_ticks']].to_string(index=False))

    print("\n--- EJEMPLOS ASK ABSORCIÓN ---")
    ask_ex = df[df['ask_abs']].nlargest(5, 'vol_zscore')
    if len(ask_ex) > 0:
        print(ask_ex[['TimeBin', 'Precio', 'Volumen', 'vol_zscore', 'price_move_ticks']].to_string(index=False))

    print("\n" + "="*80)


def main():
    print("="*80)
    print("ANÁLISIS DE ABSORCIÓN - NQ TIME & SALES")
    print("="*80)
    print(f"Parámetros:")
    print(f"  Ventana: {WINDOW_MINUTES}min")
    print(f"  Threshold: {ANOMALY_THRESHOLD} std")
    print(f"  Movimiento esperado: {PRICE_MOVE_TICKS} ticks ({PRICE_MOVE_TICKS * TICK_SIZE} pts)")
    print(f"  Ventana futura: {FUTURE_WINDOW_SEC}s")
    print("="*80)

    df = load_and_prepare_data(DATA_FILE)
    df = compute_volume_stats_simple(df, window_minutes=WINDOW_MINUTES)
    df = detect_anomalies(df, threshold=ANOMALY_THRESHOLD)
    df = detect_absorption(df, price_move_ticks=PRICE_MOVE_TICKS,
                          tick_size=TICK_SIZE,
                          future_window_sec=FUTURE_WINDOW_SEC)

    print_summary(df)

    print(f"\nGuardando en {OUTPUT_FILE}...")
    df.to_csv(OUTPUT_FILE, sep=';', decimal=',', index=False)
    print("Completado!")

    return df


if __name__ == "__main__":
    df_result = main()
