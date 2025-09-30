# Este código toma el fichero completo de datos desde el 2015  al 2025 en 1 minuto
# y lo resamplea a velas diarias, luego usa plot_chart_volume para graficar cierre y volumen

import pandas as pd
import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from plot_chart_volume import plot_close_and_volume
from config import DATA_DIR, SYMBOL, OHLCV_AGGREGATION


symbol = SYMBOL

# ====================================================
# 📥 CARGA DE DATOS
# ====================================================
directorio = str(DATA_DIR)
nombre_fichero = 'es_1min_data_2015_2025.csv'
ruta_completa = os.path.join(directorio, nombre_fichero)

print("\n======================== 🔍 df  ===========================")
df = pd.read_csv(ruta_completa)
print('Fichero:', ruta_completa, 'importado')
print(f"Características del Fichero Base: {df.shape}")

# Normalizar columnas a minúsculas y renombrar 'volumen' a 'volume'
df.columns = [col.strip().lower() for col in df.columns]
df = df.rename(columns={'volumen': 'volume'})

# Asegurar formato datetime con zona UTC
df['date'] = pd.to_datetime(df['date'], utc=True)
df = df.set_index('date')

# 🔁 Resample a velas diarias usando configuración
df_daily = df.resample('1D').agg(OHLCV_AGGREGATION).dropna()

# Reset index para usar 'date' como columna
df_daily = df_daily.reset_index()

print(df_daily.head())

# Ejecutar gráfico
timeframe = '1D'
plot_close_and_volume(symbol, timeframe, df_daily)