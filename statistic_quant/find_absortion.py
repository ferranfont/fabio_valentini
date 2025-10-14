import os
import pandas as pd
import numpy as np
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config import DATA_DIR, SYMBOL


def detect_outliers(series, threshold=1.5):
    """
    Detecta outliers usando desviación estándar.

    Args:
        series: Serie de valores numéricos
        threshold: Umbral de desviación estándar (configurable, por defecto 1.5 sigma)

    Returns:
        Serie booleana con True para outliers
    """
    # Filtrar valores mayores que 0 para el cálculo estadístico
    non_zero = series[series > 0]

    if len(non_zero) == 0:
        return pd.Series([False] * len(series), index=series.index)

    mean = non_zero.mean()
    std = non_zero.std()

    if std == 0:
        return pd.Series([False] * len(series), index=series.index)

    # Calcular z-score y marcar outliers
    z_scores = np.abs((series - mean) / std)
    return z_scores > threshold


def find_absorption(df, outlier_threshold=1.5):
    """
    Agrupa el volumen por nivel de precio, separado por BID y ASK.
    Detecta outliers estadísticos en los volúmenes.

    Args:
        df: DataFrame con columnas: Timestamp (index), Precio, Volumen, Lado
        outlier_threshold: Umbral de desviación estándar para detectar outliers

    Returns:
        DataFrame con footprint clustering ordenado por precio (ascendente)
    """
    # Agrupar por Precio y Lado, sumando el Volumen
    footprint = df.groupby(['Precio', 'Lado'])['Volumen'].sum().unstack(fill_value=0)

    # Asegurar que tenemos columnas BID y ASK
    if 'BID' not in footprint.columns:
        footprint['BID'] = 0
    if 'ASK' not in footprint.columns:
        footprint['ASK'] = 0

    # Resetear índice para tener Precio como columna
    footprint = footprint.reset_index()

    # Detectar outliers para BID y ASK
    footprint['BID_outlier'] = detect_outliers(footprint['BID'], threshold=outlier_threshold)
    footprint['ASK_outlier'] = detect_outliers(footprint['ASK'], threshold=outlier_threshold)

    # Reordenar columnas: Precio, BID, BID_outlier, ASK, ASK_outlier
    footprint = footprint[['Precio', 'BID', 'BID_outlier', 'ASK', 'ASK_outlier']]

    # Ordenar por precio descendente (precios altos arriba, bajos abajo)
    footprint = footprint.sort_values('Precio', ascending=False).reset_index(drop=True)

    return footprint


if __name__ == "__main__":
    # Configuración
    n_temp = 1000  # Número de últimas filas a analizar
    outlier_threshold = 1.5  # Umbral de desviación estándar para outliers
    symbol = SYMBOL
    directorio = str(DATA_DIR)
    nombre_fichero = 'time_and_sales.csv'
    ruta_completa = os.path.join(directorio, nombre_fichero)

    print("\n======================== Find Absorption ===========================")

    # Leer CSV
    df = pd.read_csv(ruta_completa, sep=';', decimal=',')

    print(f'Fichero: {ruta_completa} importado')
    print(f"Registros totales: {df.shape[0]}")

    # Convertir Timestamp con formato específico
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], format='%Y-%m-%d %H:%M:%S.%f')

    # Tomar las últimas n_temp filas
    df_muestra = df.tail(n_temp)

    # Obtener timestamp de la última fila (sin milisegundos)
    last_timestamp = df_muestra['Timestamp'].iloc[-1]
    timestamp_str = last_timestamp.strftime('%H_%M_%S')

    print(f"\nAnalizando ultimas {n_temp} filas")
    print(f"Ultima fila timestamp: {last_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

    # Calcular footprint clustering
    footprint_cluster = find_absorption(df_muestra, outlier_threshold=outlier_threshold)

    # Mostrar resultado por terminal
    print(f"\nFootprint Clustering (ordenado por precio descendente):")
    print(footprint_cluster.to_string(index=False))

    # Guardar CSV
    output_filename = f'footprint_cluster_{timestamp_str}.csv'
    output_path = os.path.join(directorio, output_filename)
    footprint_cluster.to_csv(output_path, sep=';', decimal=',', index=False)

    print(f"\nCSV guardado: {output_path}")
    print(f"Niveles de precio analizados: {len(footprint_cluster)}")
