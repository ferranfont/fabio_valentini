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
from plotly.subplots import make_subplots
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))
from config import DATA_DIR

# ====================================================
# CONFIGURACIÓN
# ====================================================
# Archivo de datos tick
DATA_FILE = "time_and_sales_20251031_074530.csv"
# Archivo de señales (detecciones)
SIGNALS_FILE = "db_shapes_dom_20251101_150013.csv"

# Parámetros de indicadores
EMA_PERIOD = 20  # Período de la EMA rápida en minutos
EMA_SLOW_PERIOD = 200  # Período de la EMA lenta en minutos
VWAP_PERIOD = 100  # Período del VWAP rolling en minutos

# Parámetros de clustering
CLUSTER_TIME = 40  # Ventana de tiempo en minutos para medir densidad de señales
# Extensión de 8 horas para las líneas horizontales
LINE_EXTENSION_HOURS = 0.50
# Parámetros de eficiencia
EFFICIENCY_THRESHOLD = 30  # Puntos de precio mínimos esperados para considerar eficiencia
EFFICIENCY_TIME = 30  # Minutos para evaluar el movimiento del precio

# Rutas completas
DATA_PATH = Path(__file__).parent.parent / "data" / DATA_FILE
SIGNALS_PATH = Path(__file__).parent.parent / "outputs" / SIGNALS_FILE
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
# CALCULAR INDICADOR DE CLUSTERING
# ====================================================
print(f"\n[OK] Calculando densidad de clustering con ventana de {CLUSTER_TIME} minutos...")

# Crear series de tiempo de 1 minuto con conteo de señales p_shape y d_shape
cluster_p_density = []
cluster_d_density = []

for timestamp in df_price['Timestamp']:
    # Ventana de tiempo: desde (timestamp - CLUSTER_TIME) hasta timestamp
    window_start = timestamp - pd.Timedelta(minutes=CLUSTER_TIME)
    window_end = timestamp

    # Contar p_shapes en esta ventana
    p_count = len(df_p_shape[
        (df_p_shape['timestamp'] >= window_start) &
        (df_p_shape['timestamp'] <= window_end)
    ])

    # Contar d_shapes en esta ventana
    d_count = len(df_d_shape[
        (df_d_shape['timestamp'] >= window_start) &
        (df_d_shape['timestamp'] <= window_end)
    ])

    cluster_p_density.append(p_count)
    cluster_d_density.append(d_count)

df_price['cluster_p'] = cluster_p_density
df_price['cluster_d'] = cluster_d_density

print(f"[OK] Densidad cluster_p calculada (max: {df_price['cluster_p'].max()}, promedio: {df_price['cluster_p'].mean():.2f})")
print(f"[OK] Densidad cluster_d calculada (max: {df_price['cluster_d'].max()}, promedio: {df_price['cluster_d'].mean():.2f})")

# ====================================================
# CREAR GRÁFICO
# ====================================================
print("\n" + "=" * 80)
print("GENERANDO GRÁFICO")
print("=" * 80)

# Crear figura con 2 subplots: Precio arriba, Clustering abajo
fig = make_subplots(
    rows=2, cols=1,
    shared_xaxes=True,
    vertical_spacing=0.05,
    row_heights=[0.7, 0.3],
    subplot_titles=(None, None)  # Sin títulos en los subplots
)

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

# ====================================================
# SUBPLOT 1: PRECIO Y SEÑALES
# ====================================================

# 1. Línea azul de precio
fig.add_trace(go.Scatter(
    x=df_price['Timestamp'],
    y=df_price['Precio'],
    mode='lines',
    line=dict(color='blue', width=1),
    name='Precio',
    showlegend=False,
    hovertemplate='%{x}<br>Precio: %{y:.2f}<extra></extra>'
), row=1, col=1)

# 1b. VWAP en magenta
fig.add_trace(go.Scatter(
    x=df_price['Timestamp'],
    y=df_price['VWAP'],
    mode='lines',
    line=dict(color='magenta', width=1.5, dash='dash'),
    name='VWAP',
    hovertemplate='%{x}<br>VWAP: %{y:.2f}<extra></extra>'
), row=1, col=1)

# 1c. EMA rápida en naranja
fig.add_trace(go.Scatter(
    x=df_price['Timestamp'],
    y=df_price['EMA'],
    mode='lines',
    line=dict(color='orange', width=1.5),
    name=f'EMA({EMA_PERIOD})',
    hovertemplate='%{x}<br>EMA: %{y:.2f}<extra></extra>'
), row=1, col=1)

# 1d. EMA lenta en verde
fig.add_trace(go.Scatter(
    x=df_price['Timestamp'],
    y=df_price['EMA_SLOW'],
    mode='lines',
    line=dict(color='green', width=1.5),
    name=f'EMA({EMA_SLOW_PERIOD})',
    hovertemplate='%{x}<br>EMA Lenta: %{y:.2f}<extra></extra>'
), row=1, col=1)

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
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df_bullish['Timestamp'],
        y=df_bullish['EMA_SLOW'],
        mode='lines',
        line=dict(width=0),
        fill='tonexty',
        fillcolor='rgba(144, 238, 144, 0.2)',  # Verde claro con alpha 0.2
        name='Zona Alcista (EMA30>EMA100)',
        hoverinfo='skip'
    ), row=1, col=1)

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
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df_bearish['Timestamp'],
        y=df_bearish['EMA_SLOW'],
        mode='lines',
        line=dict(width=0),
        fill='tonexty',
        fillcolor='rgba(255, 182, 193, 0.2)',  # Rojo pálido con alpha 0.2
        name='Zona Bajista (EMA30<EMA100)',
        hoverinfo='skip'
    ), row=1, col=1)

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
    ), row=1, col=1)

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
    ), row=1, col=1)

# ====================================================
# SUBPLOT 2: INDICADOR DE CLUSTERING P-SHAPE
# ====================================================

# Línea verde de densidad de clustering p_shape
fig.add_trace(go.Scatter(
    x=df_price['Timestamp'],
    y=df_price['cluster_p'],
    mode='lines',
    line=dict(color='green', width=2),
    name=f'Cluster P ({CLUSTER_TIME}min)',
    fill='tozeroy',
    fillcolor='rgba(0, 255, 0, 0.1)',
    hovertemplate='%{x}<br>Señales P-Shape: %{y}<extra></extra>'
), row=2, col=1)

# Línea roja de densidad de clustering d_shape
fig.add_trace(go.Scatter(
    x=df_price['Timestamp'],
    y=df_price['cluster_d'],
    mode='lines',
    line=dict(color='red', width=2),
    name=f'Cluster D ({CLUSTER_TIME}min)',
    fill='tozeroy',
    fillcolor='rgba(255, 0, 0, 0.1)',
    hovertemplate='%{x}<br>Señales D-Shape: %{y}<extra></extra>'
), row=2, col=1)

# ====================================================
# DETECTAR Y DIBUJAR CLUSTERS
# ====================================================

def detect_clusters(df, column, threshold=2):
    """
    Detecta clusters consecutivos donde densidad > threshold
    Retorna lista de diccionarios con info de cada cluster
    """
    clusters = []
    in_cluster = False
    cluster_start_idx = None

    for idx, row in df.iterrows():
        if row[column] > threshold:
            if not in_cluster:
                # Inicio de nuevo cluster
                in_cluster = True
                cluster_start_idx = idx
        else:
            if in_cluster:
                # Fin de cluster
                cluster_data = df.loc[cluster_start_idx:idx-1]
                clusters.append({
                    'start_time': cluster_data['Timestamp'].iloc[0],
                    'end_time': cluster_data['Timestamp'].iloc[-1],
                    'weighted_price': (cluster_data['Precio'] * cluster_data[column]).sum() / cluster_data[column].sum(),
                    'max_density': cluster_data[column].max()
                })
                in_cluster = False

    # Si termina en cluster
    if in_cluster:
        cluster_data = df.loc[cluster_start_idx:]
        clusters.append({
            'start_time': cluster_data['Timestamp'].iloc[0],
            'end_time': cluster_data['Timestamp'].iloc[-1],
            'weighted_price': (cluster_data['Precio'] * cluster_data[column]).sum() / cluster_data[column].sum(),
            'max_density': cluster_data[column].max()
        })

    return clusters

# Detectar clusters de p_shape
print(f"\n[OK] Detectando clusters de p_shape (densidad > 2)...")
p_clusters = detect_clusters(df_price, 'cluster_p', threshold=2)
print(f"[OK] Encontrados {len(p_clusters)} clusters de p_shape")

# Detectar clusters de d_shape
print(f"[OK] Detectando clusters de d_shape (densidad > 2)...")
d_clusters = detect_clusters(df_price, 'cluster_d', threshold=2)
print(f"[OK] Encontrados {len(d_clusters)} clusters de d_shape")



# Dibujar líneas horizontales verdes para clusters de p_shape
for cluster in p_clusters:
    # Calcular tiempo final: inicio del cluster + 8 horas
    line_end_time = cluster['start_time'] + pd.Timedelta(hours=LINE_EXTENSION_HOURS)

    fig.add_trace(go.Scatter(
        x=[cluster['start_time'], line_end_time],
        y=[cluster['weighted_price'], cluster['weighted_price']],
        mode='lines',
        line=dict(color='green', width=1),
        name='Cluster P',
        showlegend=False,
        hoverinfo='skip'
    ), row=1, col=1)

# Dibujar líneas horizontales rojas para clusters de d_shape
for cluster in d_clusters:
    # Calcular tiempo final: inicio del cluster + 8 horas
    line_end_time = cluster['start_time'] + pd.Timedelta(hours=LINE_EXTENSION_HOURS)

    fig.add_trace(go.Scatter(
        x=[cluster['start_time'], line_end_time],
        y=[cluster['weighted_price'], cluster['weighted_price']],
        mode='lines',
        line=dict(color='red', width=1),
        name='Cluster D',
        showlegend=False,
        hoverinfo='skip'
    ), row=1, col=1)

# ====================================================
# DETECTAR EFICIENCIAS
# ====================================================

def detect_efficiency(cluster, cluster_type, df_price, threshold, time_minutes):
    """
    Detecta si el precio SÍ se movió suficiente en la dirección esperada (EFICIENCIA)

    cluster_type: 'p_shape' (esperamos bajada) o 'd_shape' (esperamos subida)
    threshold: puntos de movimiento mínimo esperado
    time_minutes: ventana de tiempo en minutos para evaluar el movimiento

    Returns: True si hay eficiencia (precio SÍ se movió lo esperado)
    """
    # Obtener datos de precio durante la ventana de tiempo
    end_time = cluster['start_time'] + pd.Timedelta(minutes=time_minutes)

    # Filtrar precios en el periodo
    window_data = df_price[
        (df_price['Timestamp'] >= cluster['start_time']) &
        (df_price['Timestamp'] <= end_time)
    ]

    if len(window_data) == 0:
        return False  # No hay datos suficientes

    cluster_price = cluster['weighted_price']

    if cluster_type == 'p_shape':
        # P-shape: esperamos que el precio BAJE al menos threshold puntos
        min_price = window_data['Precio'].min()
        price_move = cluster_price - min_price

        # EFICIENCIA = precio SÍ bajó lo suficiente
        return price_move >= threshold

    elif cluster_type == 'd_shape':
        # D-shape: esperamos que el precio SUBA al menos threshold puntos
        max_price = window_data['Precio'].max()
        price_move = max_price - cluster_price

        # EFICIENCIA = precio SÍ subió lo suficiente
        return price_move >= threshold

    return False

# Detectar eficiencias para clusters de p_shape
print(f"\n[OK] Detectando eficiencias en clusters de p_shape (ventana: {EFFICIENCY_TIME} min, umbral: {EFFICIENCY_THRESHOLD} puntos)...")
p_efficiencies = []
for cluster in p_clusters:
    if detect_efficiency(cluster, 'p_shape', df_price, EFFICIENCY_THRESHOLD, EFFICIENCY_TIME):
        p_efficiencies.append(cluster)

print(f"[OK] Encontradas {len(p_efficiencies)} eficiencias en p_shape (de {len(p_clusters)} clusters)")

# Detectar eficiencias para clusters de d_shape
print(f"[OK] Detectando eficiencias en clusters de d_shape (ventana: {EFFICIENCY_TIME} min, umbral: {EFFICIENCY_THRESHOLD} puntos)...")
d_efficiencies = []
for cluster in d_clusters:
    if detect_efficiency(cluster, 'd_shape', df_price, EFFICIENCY_THRESHOLD, EFFICIENCY_TIME):
        d_efficiencies.append(cluster)

print(f"[OK] Encontradas {len(d_efficiencies)} eficiencias en d_shape (de {len(d_clusters)} clusters)")

# Dibujar líneas verticales verdes SÓLIDAS para eficiencias de p_shape
for cluster in p_efficiencies:
    # Línea vertical al final del periodo de evaluación de eficiencia
    efficiency_time = cluster['start_time'] + pd.Timedelta(minutes=EFFICIENCY_TIME)

    # Obtener rango de precios para la línea vertical
    y_min = df_price['Precio'].min()
    y_max = df_price['Precio'].max()

    fig.add_trace(go.Scatter(
        x=[efficiency_time, efficiency_time],
        y=[y_min, y_max],
        mode='lines',
        line=dict(color='green', width=1),  # SÓLIDA width=1
        name='Eficiencia P',
        showlegend=False,
        hoverinfo='skip'
    ), row=1, col=1)

# Dibujar líneas verticales rojas SÓLIDAS para eficiencias de d_shape
for cluster in d_efficiencies:
    # Línea vertical al final del periodo de evaluación de eficiencia
    efficiency_time = cluster['start_time'] + pd.Timedelta(minutes=EFFICIENCY_TIME)

    # Obtener rango de precios para la línea vertical
    y_min = df_price['Precio'].min()
    y_max = df_price['Precio'].max()

    fig.add_trace(go.Scatter(
        x=[efficiency_time, efficiency_time],
        y=[y_min, y_max],
        mode='lines',
        line=dict(color='red', width=1),  # SÓLIDA width=1
        name='Eficiencia D',
        showlegend=False,
        hoverinfo='skip'
    ), row=1, col=1)

# Configuración del layout
fig.update_layout(
    title=None,  # Sin título principal
    width=1600,
    height=850,  # Reduced from 1000
    hovermode=False,  # Tooltips desactivados
    plot_bgcolor='white',
    paper_bgcolor='white',
    font=dict(size=12, color='black'),
    showlegend=True,
    legend=dict(
        orientation='h',
        x=0.5,
        y=-0.05,
        xanchor='center',
        yanchor='top',
        bgcolor='rgba(255,255,255,0.9)',
        bordercolor='lightgrey',
        borderwidth=1,
        font=dict(color='grey')
    )
)

# Update axes for subplot 1 (Price)
fig.update_xaxes(
    title_text=None,  # Sin título en eje X
    showgrid=False,
    linecolor='black',
    linewidth=1,
    row=1, col=1
)
fig.update_yaxes(
    title_text=None,  # Sin título en eje Y
    showgrid=True,
    gridcolor='rgba(128,128,128,0.2)',
    linecolor='black',
    linewidth=1,
    row=1, col=1
)

# Update axes for subplot 2 (Clustering)
fig.update_xaxes(
    title_text=None,  # Sin título en eje X
    showgrid=False,
    linecolor='black',
    linewidth=1,
    row=2, col=1
)
fig.update_yaxes(
    title_text=None,  # Sin título en eje Y
    showgrid=True,
    gridcolor='rgba(128,128,128,0.2)',
    linecolor='black',
    linewidth=1,
    row=2, col=1
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

# Calcular tasas de eficiencia
p_efficiency_rate = (len(p_efficiencies) / len(p_clusters) * 100) if len(p_clusters) > 0 else 0
d_efficiency_rate = (len(d_efficiencies) / len(d_clusters) * 100) if len(d_clusters) > 0 else 0
total_efficiencies = len(p_efficiencies) + len(d_efficiencies)
total_clusters = len(p_clusters) + len(d_clusters)
overall_efficiency_rate = (total_efficiencies / total_clusters * 100) if total_clusters > 0 else 0

print(f"\nResumen de Datos:")
print(f"  - Puntos de precio: {len(df_price):,}")
print(f"  - Detecciones d_shape: {len(df_d_shape)}")
print(f"  - Detecciones p_shape: {len(df_p_shape)}")
print(f"  - Total detecciones: {len(df_signals)}")

print(f"\nResumen de Clusters:")
print(f"  - Clusters P-Shape: {len(p_clusters)}")
print(f"  - Clusters D-Shape: {len(d_clusters)}")
print(f"  - Total Clusters: {total_clusters}")

print(f"\n{'=' * 80}")
print(f"RESUMEN DE EFICIENCIAS (Umbral: {EFFICIENCY_THRESHOLD} pts en {EFFICIENCY_TIME} min)")
print(f"{'=' * 80}")
print(f"\nP-Shape (Clusters Verdes - Esperamos BAJADA):")
print(f"  - Clusters totales: {len(p_clusters)}")
print(f"  - Eficiencias (precio bajo >={EFFICIENCY_THRESHOLD} pts): {len(p_efficiencies)}")
print(f"  - Tasa de eficiencia: {p_efficiency_rate:.1f}%")

print(f"\nD-Shape (Clusters Rojos - Esperamos SUBIDA):")
print(f"  - Clusters totales: {len(d_clusters)}")
print(f"  - Eficiencias (precio subio >={EFFICIENCY_THRESHOLD} pts): {len(d_efficiencies)}")
print(f"  - Tasa de eficiencia: {d_efficiency_rate:.1f}%")

print(f"\nEFICIENCIA GLOBAL:")
print(f"  - Total eventos eficientes: {total_efficiencies} de {total_clusters}")
print(f"  - Tasa global de eficiencia: {overall_efficiency_rate:.1f}%")
print(f"{'=' * 80}")
print()
