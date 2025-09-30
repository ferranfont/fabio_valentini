# Este toma todo el universo de datos desde el 2015 al 2025 y extrae un día específico
# Luego crea un CSV con los datos de ese día y usa plot_minute_data para graficar   
# Cambiar la variable TARGET_DATE para extraer otro día

import pandas as pd
import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config import DATA_DIR, SYMBOL
from plot_minute_data import plot_minute_data

# ====================================================
# 📥 CONFIGURACIÓN
# ====================================================
symbol = SYMBOL

# Variable de fecha - cambiar esta fecha para extraer datos de otro día
TARGET_DATE = '2023-03-01'  # Formato: YYYY-MM-DD

# ====================================================
# 📥 CARGA DE DATOS
# ====================================================
directorio = str(DATA_DIR)
nombre_fichero = 'es_1min_data_2015_2025.csv'
ruta_completa = os.path.join(directorio, nombre_fichero)

print(f"\n======================== 🔍 Extrayendo datos del {TARGET_DATE} ===========================")
df = pd.read_csv(ruta_completa)
print('Fichero:', ruta_completa, 'importado')
print(f"Características del Fichero Base: {df.shape}")

# Normalizar columnas a minúsculas y renombrar 'volumen' a 'volume'
df.columns = [col.strip().lower() for col in df.columns]
df = df.rename(columns={'volumen': 'volume'})

# Asegurar formato datetime con zona UTC
df['date'] = pd.to_datetime(df['date'], utc=True)

# Filtrar datos solo para la fecha objetivo
target_date_start = pd.to_datetime(TARGET_DATE, utc=True)
target_date_end = target_date_start + pd.Timedelta(days=1)

df_filtered = df[(df['date'] >= target_date_start) & (df['date'] < target_date_end)].copy()

print(f"Datos encontrados para {TARGET_DATE}: {len(df_filtered)} registros")

if len(df_filtered) > 0:
    # Crear nombre de archivo para el día específico
    output_filename = f'es_1min_data_{TARGET_DATE.replace("-", "_")}.csv'
    output_path = os.path.join(directorio, output_filename)

    # Guardar CSV con datos del día específico
    df_filtered.to_csv(output_path, index=False)

    print(f"✅ Archivo creado: {output_path}")
    print(f"📊 Registros guardados: {len(df_filtered)}")
    print(f"⏰ Rango de tiempo: {df_filtered['date'].min()} a {df_filtered['date'].max()}")

    # Mostrar estadísticas básicas
    print("\n📈 Estadísticas del día:")
    print(f"Open: {df_filtered['open'].iloc[0]:.2f}")
    print(f"High: {df_filtered['high'].max():.2f}")
    print(f"Low: {df_filtered['low'].min():.2f}")
    print(f"Close: {df_filtered['close'].iloc[-1]:.2f}")
    print(f"Volume total: {df_filtered['volume'].sum():,.0f}")

    # Crear gráfico con los datos del día específico
    print(f"\n📊 Generando gráfico para {TARGET_DATE}...")
    timeframe = f'1min_{TARGET_DATE}'
    plot_minute_data(symbol, timeframe, df_filtered)

else:
    print(f"❌ No se encontraron datos para la fecha {TARGET_DATE}")
    print("Verifique que la fecha esté disponible en el archivo de datos.")