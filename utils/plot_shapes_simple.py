"""
Script simple para visualizar precio vs tiempo con detecciones de Market Profile
- Línea azul: Precio de cierre
- Puntos rojos: d_shape (BID absorption)
- Puntos verdes: p_shape (ASK absorption)
"""

import os
import sys
import webbrowser
import pandas as pd
import plotly.graph_objs as go
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))
from config import DATA_DIR

# ====================================================
# CONFIGURACIÓN
# ====================================================
# Archivo de datos tick
DATA_FILE = "time_and_sales_nq_20250829.csv"

# Auto-extract date from DATA_FILE for SIGNALS_FILE
import re
date_match = re.search(r'(\d{8})', DATA_FILE)
data_date = date_match.group(1) if date_match else "00000000"

# Archivo de señales (detecciones) - Auto-generated from DATA_FILE date
# Format: db_shapes_dom_YYYYMMDD.csv (date from the data itself)
SIGNALS_FILE = f"db_shapes_dom_{data_date}.csv"
print("\nCSV de data: ", DATA_FILE)
print("CSV de señales: ", SIGNALS_FILE)

# Parámetros de indicadores
EMA_PERIOD = 30  # Período de la EMA rápida en minutos
EMA_SLOW_PERIOD = 200  # Período de la EMA lenta en minutos
VWAP_PERIOD = 100  # Período del VWAP rolling en minutos

# Rutas completas
DATA_PATH = Path(__file__).parent.parent / "data/historic" / DATA_FILE
SIGNALS_PATH = Path(__file__).parent.parent / "outputs/" / SIGNALS_FILE
OUTPUT_HTML = Path(__file__).parent.parent / "charts" / "shapes_visualization.html"

# ====================================================
# CARGA DE DATOS
# ====================================================
print("\n" + "=" * 80)
print("CARGANDO DATOS")
print("=" * 80)

# Leer datos de tick (precio vs tiempo)
print(f"\nCargando datos de tick: {DATA_FILE}")
df_ticks = pd.read_csv(DATA_PATH, sep=';', decimal=',')
print(f"[OK] {len(df_ticks):,} ticks cargados")

# Convertir timestamp a datetime
df_ticks['Timestamp'] = pd.to_datetime(df_ticks['Timestamp'])

# Para simplificar visualización, resamplear a 1 minuto
df_ticks = df_ticks.set_index('Timestamp')

# Resamplear precio, volumen para calcular VWAP
df_resampled = pd.DataFrame({
    'Precio': df_ticks['Precio'].resample('1min').last(),
    'Volumen': df_ticks['Volumen'].resample('1min').sum()
}).dropna()

df_price = df_resampled.reset_index()
df_price.columns = ['Timestamp', 'Precio', 'Volumen']

print(f"[OK] Resampled a 1 minuto: {len(df_price):,} puntos")

# Calcular VWAP Rolling (Volume Weighted Average Price)
print(f"[OK] Calculando VWAP rolling con periodo {VWAP_PERIOD}...")
df_price['PxV'] = df_price['Precio'] * df_price['Volumen']
df_price['VWAP'] = (
    df_price['PxV'].rolling(window=VWAP_PERIOD).sum() /
    df_price['Volumen'].rolling(window=VWAP_PERIOD).sum()
)

# Calcular EMA rápida
print(f"[OK] Calculando EMA rápida con periodo {EMA_PERIOD}...")
df_price['EMA'] = df_price['Precio'].ewm(span=EMA_PERIOD, adjust=False).mean()

# Calcular EMA lenta
print(f"[OK] Calculando EMA lenta con periodo {EMA_SLOW_PERIOD}...")
df_price['EMA_SLOW'] = df_price['Precio'].ewm(span=EMA_SLOW_PERIOD, adjust=False).mean()

# Leer señales de detección
print(f"\nCargando señales: {SIGNALS_FILE}")
df_signals = pd.read_csv(SIGNALS_PATH, sep=';', decimal=',')
print(f"[OK] {len(df_signals)} detecciones cargadas")

# Convertir timestamp a datetime
df_signals['timestamp'] = pd.to_datetime(df_signals['timestamp'])

# Separar por tipo de señal
df_d_shape = df_signals[df_signals['shape'] == 'd_shape'].copy()
df_p_shape = df_signals[df_signals['shape'] == 'p_shape'].copy()

print(f"  - d_shape (rojo): {len(df_d_shape)}")
print(f"  - p_shape (verde): {len(df_p_shape)}")

# ====================================================
# CREAR GRÁFICO
# ====================================================
print("\n" + "=" * 80)
print("GENERANDO GRÁFICO")
print("=" * 80)

fig = go.Figure()

# Añadir líneas verticales para cambios de día
# Obtener todos los días únicos en los datos
df_price['Date'] = df_price['Timestamp'].dt.date
unique_dates = df_price['Date'].unique()

# Añadir línea vertical al inicio de cada día (excepto el primero)
for i, date in enumerate(unique_dates[1:], 1):
    # Obtener el timestamp exacto del primer punto de ese día
    day_start = df_price[df_price['Date'] == date]['Timestamp'].min()

    fig.add_vline(
        x=day_start,
        line=dict(color='rgba(180,180,180,0.3)', width=1, dash='solid'),
        layer='below'
    )

# 1. Línea azul de precio
fig.add_trace(go.Scatter(
    x=df_price['Timestamp'],
    y=df_price['Precio'],
    mode='lines',
    line=dict(color='blue', width=1),
    name='Precio',
    showlegend=False,
    hovertemplate='%{x}<br>Precio: %{y:.2f}<extra></extra>'
))

# 1b. VWAP en magenta
fig.add_trace(go.Scatter(
    x=df_price['Timestamp'],
    y=df_price['VWAP'],
    mode='lines',
    line=dict(color='magenta', width=1.5, dash='dash'),
    name='VWAP',
    hovertemplate='%{x}<br>VWAP: %{y:.2f}<extra></extra>'
))

# 1c. EMA rápida en naranja
fig.add_trace(go.Scatter(
    x=df_price['Timestamp'],
    y=df_price['EMA'],
    mode='lines',
    line=dict(color='orange', width=1.5),
    name=f'EMA({EMA_PERIOD})',
    hovertemplate='%{x}<br>EMA: %{y:.2f}<extra></extra>'
))

# 1d. EMA lenta en verde
fig.add_trace(go.Scatter(
    x=df_price['Timestamp'],
    y=df_price['EMA_SLOW'],
    mode='lines',
    line=dict(color='green', width=1.5),
    name=f'EMA({EMA_SLOW_PERIOD})',
    hovertemplate='%{x}<br>EMA Lenta: %{y:.2f}<extra></extra>'
))

# 1e. Relleno entre EMAs (azul si EMA rápida > EMA lenta, rojo si no)
# Crear segmentos donde EMA > EMA_SLOW (azul) y EMA < EMA_SLOW (rojo)
df_price['ema_diff'] = df_price['EMA'] - df_price['EMA_SLOW']

# Segmentos alcistas (EMA > EMA_SLOW) - Relleno azul
df_bullish = df_price[df_price['ema_diff'] > 0].copy()
if len(df_bullish) > 0:
    fig.add_trace(go.Scatter(
        x=df_bullish['Timestamp'],
        y=df_bullish['EMA'],
        mode='lines',
        line=dict(width=0),
        showlegend=False,
        hoverinfo='skip'
    ))
    fig.add_trace(go.Scatter(
        x=df_bullish['Timestamp'],
        y=df_bullish['EMA_SLOW'],
        mode='lines',
        line=dict(width=0),
        fill='tonexty',
        fillcolor='rgba(144, 238, 144, 0.2)',  # Verde claro con alpha 0.2
        name='Zona Alcista (EMA30>EMA100)',
        hoverinfo='skip'
    ))

# Segmentos bajistas (EMA < EMA_SLOW) - Relleno rojo
df_bearish = df_price[df_price['ema_diff'] < 0].copy()
if len(df_bearish) > 0:
    fig.add_trace(go.Scatter(
        x=df_bearish['Timestamp'],
        y=df_bearish['EMA'],
        mode='lines',
        line=dict(width=0),
        showlegend=False,
        hoverinfo='skip'
    ))
    fig.add_trace(go.Scatter(
        x=df_bearish['Timestamp'],
        y=df_bearish['EMA_SLOW'],
        mode='lines',
        line=dict(width=0),
        fill='tonexty',
        fillcolor='rgba(255, 182, 193, 0.2)',  # Rojo pálido con alpha 0.2
        name='Zona Bajista (EMA30<EMA100)',
        hoverinfo='skip'
    ))

# 2. Puntos rojos para d_shape
if len(df_d_shape) > 0:
    fig.add_trace(go.Scatter(
        x=df_d_shape['timestamp'],
        y=df_d_shape['close_price'],
        mode='markers',
        marker=dict(
            color='red',
            size=9,
            symbol='circle',
            line=dict(color='white', width=1.5)
        ),
        name='d_shape',
        hovertemplate='<b>d_shape</b><br>%{x}<br>Precio: %{y:.2f}<extra></extra>'
    ))

# 3. Puntos verdes para p_shape
if len(df_p_shape) > 0:
    fig.add_trace(go.Scatter(
        x=df_p_shape['timestamp'],
        y=df_p_shape['close_price'],
        mode='markers',
        marker=dict(
            color='forestgreen',
            size=9,
            symbol='circle',
            line=dict(color='white', width=1.5)
        ),
        name='p_shape',
        hovertemplate='<b>p_shape</b><br>%{x}<br>Precio: %{y:.2f}<extra></extra>'
    ))

# Configuración del layout
fig.update_layout(
    title=f'Precio NQ con Detecciones de Market Profile<br><sub>{len(df_d_shape)} d_shapes (rojo) | {len(df_p_shape)} p_shapes (verde)</sub>',
    xaxis_title='',
    yaxis_title='',
    width=1600,
    height=800,
    hovermode='closest',
    plot_bgcolor='white',
    paper_bgcolor='white',
    font=dict(size=12, color='black'),
    xaxis=dict(
        showgrid=False,
        linecolor='black',
        linewidth=1
    ),
    yaxis=dict(
        showgrid=True,
        gridcolor='rgba(128,128,128,0.2)',
        linecolor='black',
        linewidth=1
    ),
    legend=dict(
        orientation='h',
        x=0.5,
        y=-0.1,
        xanchor='center',
        yanchor='top',
        bgcolor='rgba(255,255,255,0.9)',
        bordercolor='lightgrey',
        borderwidth=1,
        font=dict(color='grey')
    )
)

# Guardar HTML
OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
fig.write_html(
    str(OUTPUT_HTML),
    config={
        "scrollZoom": True,
        "displayModeBar": True,
        "modeBarButtonsToRemove": ['lasso2d', 'select2d'],
    }
)

print(f"\n[OK] Gráfico guardado: {OUTPUT_HTML}")
print(f"[OK] Abriendo en navegador...")

# Abrir en navegador
webbrowser.open('file://' + str(OUTPUT_HTML.resolve()))

print("\n" + "=" * 80)
print("COMPLETADO")
print("=" * 80)
print(f"\nResumen:")
print(f"  - Puntos de precio: {len(df_price):,}")
print(f"  - Detecciones d_shape: {len(df_d_shape)}")
print(f"  - Detecciones p_shape: {len(df_p_shape)}")
print(f"  - Total detecciones: {len(df_signals)}")
print()
