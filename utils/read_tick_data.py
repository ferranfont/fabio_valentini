# Este código lee los datos de time and sales (tick data)

import pandas as pd
import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config import DATA_DIR


# ====================================================
# 📥 CARGA DE DATOS
# ====================================================
directorio = str(DATA_DIR)
nombre_fichero = 'time_and_sales.csv'

ruta_completa = os.path.join(directorio, nombre_fichero)

print("\n======================== 🔍 Time and Sales Data  ===========================")
# Leer CSV con formato europeo (separador ; y decimal ,)
df = pd.read_csv(ruta_completa, sep=';', decimal=',')
print('Fichero:', ruta_completa, 'importado')
print(f"Características del Fichero: {df.shape}")
print("Columnas disponibles:", df.columns.tolist())

# Convertir Timestamp a formato pandas datetime
df['Timestamp'] = pd.to_datetime(df['Timestamp'])

# Establecer Timestamp como índice
df = df.set_index('Timestamp')

print("\nPrimeras filas del DataFrame:")
print(df.head(10))
print("\nÚltimas filas del DataFrame:")
print(df.tail(10))

print("\nInformación del DataFrame:")
print(df.info())
print("\nEstadísticas descriptivas:")
print(df.describe())
