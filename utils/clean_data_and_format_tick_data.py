# Este código toma un fichero de near-tick data y lo convierte a casi-minutos
# Usa plot_tick_data para graficar los datos resampleados a 1 minuto

import pandas as pd
import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from plot_tick_data import plot_tick_data
from config import DATA_DIR, SYMBOL


symbol = SYMBOL

# ====================================================
# 📥 CARGA DE DATOS
# ====================================================
directorio = str(DATA_DIR)
nombre_fichero = 'ES_near_tick_data_27_jul_2025.csv'

ruta_completa = os.path.join(directorio, nombre_fichero)

print("\n======================== 🔍 df  ===========================")
# Leer CSV con formato europeo (separador ; y decimal ,)
df = pd.read_csv(ruta_completa, sep=';', decimal=',',
                 names=['datetime', 'open', 'high', 'low', 'close', 'volume'])
print('Fichero:', ruta_completa, 'importado')
print(f"Características del Fichero Base: {df.shape}")
print("Columnas disponibles:", df.columns.tolist())

# Convertir datetime a formato pandas y separar fecha y hora
df['datetime'] = pd.to_datetime(df['datetime'], format='%d/%m/%Y %H:%M', utc=True)

# Establecer datetime como índice
df = df.set_index('datetime')

print("Primeras filas del DataFrame:")
print(df.head(10))
print("\nÚltimas filas del DataFrame:")
print(df.tail(10))

# Ejecutar gráfico con tick data resampled a 1 minuto
timeframe = 'tick_1min'
plot_tick_data(symbol, timeframe, df, resample_seconds=60)
