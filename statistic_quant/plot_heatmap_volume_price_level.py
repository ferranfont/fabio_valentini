"""
Visualización de mapa de calor de volumen acumulado por nivel de precio.

Muestra:
- Heatmap de vol_current_price por nivel de precio
- Línea de precios BID (rojo)
- Línea de precios ASK (verde)
- Marcadores en niveles con volumen extremo (z-score >= 2.0)
"""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import webbrowser
import os

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
INPUT_FILE = 'data/time_and_sales_absorption_NQ.csv'
OUTPUT_FILE = 'charts/heatmap_price_level.html'
ANOMALY_THRESHOLD = 2.0  # Z-score para marcar volumen extremo
TICK_SIZE = 0.25  # NQ tick size

# Rango de tiempo a visualizar (en minutos desde inicio)
START_MINUTE = 270
END_MINUTE = 300  # Primeros 30 minutos

# ==============================================================================
# CARGA DE DATOS
# ==============================================================================
print("="*80)
print("HEATMAP DE VOLUMEN POR NIVEL DE PRECIO - NQ")
print("="*80)
print(f"\nCargando {INPUT_FILE}...")

df = pd.read_csv(INPUT_FILE, sep=';', decimal=',')
df['TimeBin'] = pd.to_datetime(df['TimeBin'])

print(f"  Total registros: {len(df):,}")
print(f"  Rango temporal: {df['TimeBin'].min()} a {df['TimeBin'].max()}")

# Filtrar rango temporal
df['minutes_from_start'] = (df['TimeBin'] - df['TimeBin'].min()).dt.total_seconds() / 60
df = df[(df['minutes_from_start'] >= START_MINUTE) &
        (df['minutes_from_start'] <= END_MINUTE)].copy()

print(f"\nFiltrando minutos {START_MINUTE}-{END_MINUTE}...")
print(f"  Registros filtrados: {len(df):,}")

# ==============================================================================
# PREPARACIÓN DE DATOS PARA HEATMAP
# ==============================================================================
print("\nPreparando datos para heatmap...")

# Crear pivot para heatmap (separado por lado)
df_bid = df[df['Lado'] == 'BID'].copy()
df_ask = df[df['Lado'] == 'ASK'].copy()

# Redondear precios al tick más cercano para agrupar
df_bid['Precio_rounded'] = (df_bid['Precio'] / TICK_SIZE).round() * TICK_SIZE
df_ask['Precio_rounded'] = (df_ask['Precio'] / TICK_SIZE).round() * TICK_SIZE

# Crear bins de tiempo (cada 30 segundos para mejor visualización)
time_bins = pd.date_range(start=df['TimeBin'].min(),
                          end=df['TimeBin'].max(),
                          freq='30S')

df_bid['time_bin'] = pd.cut(df_bid['TimeBin'], bins=time_bins)
df_ask['time_bin'] = pd.cut(df_ask['TimeBin'], bins=time_bins)

# Agrupar por tiempo y precio, tomando el máximo vol_current_price del bin
heatmap_bid = df_bid.groupby(['time_bin', 'Precio_rounded'])['vol_current_price'].max().reset_index()
heatmap_ask = df_ask.groupby(['time_bin', 'Precio_rounded'])['vol_current_price'].max().reset_index()

# Convertir time_bin a timestamp para plotly
heatmap_bid['time_str'] = heatmap_bid['time_bin'].apply(lambda x: x.left if pd.notna(x) else None)
heatmap_ask['time_str'] = heatmap_ask['time_bin'].apply(lambda x: x.left if pd.notna(x) else None)

heatmap_bid = heatmap_bid.dropna(subset=['time_str'])
heatmap_ask = heatmap_ask.dropna(subset=['time_str'])

print(f"  Bins BID: {len(heatmap_bid):,}")
print(f"  Bins ASK: {len(heatmap_ask):,}")

# ==============================================================================
# CREAR LÍNEAS DE PRECIO (PROMEDIO BID/ASK POR TIMESTAMP)
# ==============================================================================
print("\nCreando líneas de precio...")

# Línea BID: último precio BID por cada timestamp
price_line_bid = df_bid.groupby('TimeBin').agg({
    'Precio': 'last'
}).reset_index()

# Línea ASK: último precio ASK por cada timestamp
price_line_ask = df_ask.groupby('TimeBin').agg({
    'Precio': 'last'
}).reset_index()

print(f"  Puntos línea BID: {len(price_line_bid):,}")
print(f"  Puntos línea ASK: {len(price_line_ask):,}")

# ==============================================================================
# DETECTAR VOLÚMENES EXTREMOS
# ==============================================================================
print("\nDetectando volúmenes extremos...")

extremos_bid = df_bid[df_bid['vol_zscore'] >= ANOMALY_THRESHOLD].copy()
extremos_ask = df_ask[df_ask['vol_zscore'] >= ANOMALY_THRESHOLD].copy()

print(f"  Volúmenes extremos BID: {len(extremos_bid):,}")
print(f"  Volúmenes extremos ASK: {len(extremos_ask):,}")

# ==============================================================================
# PREPARAR DATOS DE DENSIDAD
# ==============================================================================
print("\nPreparando datos de densidad...")

# Agrupar por tiempo para graficar densidad
density_bid = df_bid.groupby('TimeBin')['bid_density'].mean().reset_index()
density_ask = df_ask.groupby('TimeBin')['ask_density'].mean().reset_index()

# Net density (ASK - BID)
if 'net_density' in df.columns:
    density_net = df.groupby('TimeBin')['net_density'].mean().reset_index()
    print(f"  Puntos net_density: {len(density_net):,}")

print(f"  Puntos densidad BID: {len(density_bid):,}")
print(f"  Puntos densidad ASK: {len(density_ask):,}")

# ==============================================================================
# CREAR GRÁFICO CON SUBPLOTS
# ==============================================================================
print("\nCreando visualización...")

fig = make_subplots(
    rows=2, cols=1,
    row_heights=[0.75, 0.25],  # 75% para heatmap, 25% para densidad
    vertical_spacing=0.05,  # Reducido para juntar subplots
    subplot_titles=(None, None),  # Sin títulos en subplots
    specs=[[{"secondary_y": False}],
           [{"secondary_y": True}]]  # Eje Y secundario para net_density
)

# ==============================================================================
# SUBPLOT 1: HEATMAP + LÍNEAS + MARCADORES
# ==============================================================================

# Crear matriz para heatmap BID
pivot_bid = heatmap_bid.pivot(index='Precio_rounded',
                               columns='time_str',
                               values='vol_current_price')
pivot_bid = pivot_bid.fillna(0)

# Crear matriz para heatmap ASK
pivot_ask = heatmap_ask.pivot(index='Precio_rounded',
                               columns='time_str',
                               values='vol_current_price')
pivot_ask = pivot_ask.fillna(0)

# Combinar ambas matrices sumando BID + ASK para cada celda
# Alinear índices y columnas
all_prices = sorted(set(pivot_bid.index) | set(pivot_ask.index))
all_times = sorted(set(pivot_bid.columns) | set(pivot_ask.columns))

# Reindexar para tener mismas dimensiones
pivot_bid = pivot_bid.reindex(index=all_prices, columns=all_times, fill_value=0)
pivot_ask = pivot_ask.reindex(index=all_prices, columns=all_times, fill_value=0)

# Sumar ambas matrices (volumen total por nivel de precio)
pivot_combined = pivot_bid + pivot_ask

# Heatmap combinado
fig.add_trace(
    go.Heatmap(
        z=pivot_combined.values,
        x=pivot_combined.columns,
        y=pivot_combined.index,
        colorscale=[
            [0.0, '#f0f0f0'],    # Blanco (sin volumen)
            [0.3, '#fff4e6'],    # Naranja muy claro
            [0.5, '#ffe0b2'],    # Naranja claro
            [0.7, '#ffb74d'],    # Naranja
            [0.9, '#ff9800'],    # Naranja fuerte
            [1.0, '#e65100']     # Naranja oscuro
        ],
        colorbar=dict(
            title="Vol Acumulado<br>(contratos)",
            titleside="right",
            tickmode="linear",
            tick0=0,
            dtick=10
        ),
        hovertemplate='Tiempo: %{x}<br>Precio: %{y}<br>Vol acumulado: %{z}<extra></extra>',
        name='Volumen'
    ),
    row=1, col=1
)

# Puntos de cada tick BID (pequeños)
fig.add_trace(
    go.Scatter(
        x=df_bid['TimeBin'],
        y=df_bid['Precio'],
        mode='markers',
        marker=dict(color='red', size=3, opacity=0.6),
        name='Ticks BID',
        hovertemplate='Tiempo: %{x}<br>Precio BID: %{y}<br>Vol: %{customdata[0]}<extra></extra>',
        customdata=df_bid[['Volumen']].values,
        showlegend=True
    ),
    row=1, col=1
)

# Línea de precio BID
fig.add_trace(
    go.Scatter(
        x=price_line_bid['TimeBin'],
        y=price_line_bid['Precio'],
        mode='lines',
        line=dict(color='red', width=1),
        name='Línea BID',
        hovertemplate='Tiempo: %{x}<br>Precio BID: %{y}<extra></extra>'
    ),
    row=1, col=1
)

# Puntos de cada tick ASK (pequeños)
fig.add_trace(
    go.Scatter(
        x=df_ask['TimeBin'],
        y=df_ask['Precio'],
        mode='markers',
        marker=dict(color='green', size=3, opacity=0.6),
        name='Ticks ASK',
        hovertemplate='Tiempo: %{x}<br>Precio ASK: %{y}<br>Vol: %{customdata[0]}<extra></extra>',
        customdata=df_ask[['Volumen']].values,
        showlegend=True
    ),
    row=1, col=1
)

# Línea de precio ASK
fig.add_trace(
    go.Scatter(
        x=price_line_ask['TimeBin'],
        y=price_line_ask['Precio'],
        mode='lines',
        line=dict(color='green', width=1),
        name='Línea ASK',
        hovertemplate='Tiempo: %{x}<br>Precio ASK: %{y}<extra></extra>'
    ),
    row=1, col=1
)

# Marcadores de volumen extremo BID
if len(extremos_bid) > 0:
    fig.add_trace(
        go.Scatter(
            x=extremos_bid['TimeBin'],
            y=extremos_bid['Precio'],
            mode='markers',
            marker=dict(
                symbol='circle',
                size=12,
                color='rgb(255,0,0)',  # Rojo intenso
                line=dict(color='rgb(255,0,0)', width=2)  # Borde rojo
            ),
            name='Vol Extremo BID',
            hovertemplate=(
                'Tiempo: %{x}<br>'
                'Precio: %{y}<br>'
                'Vol acumulado: %{customdata[0]:.0f}<br>'
                'Z-score: %{customdata[1]:.2f}<br>'
                'Vol tick: %{customdata[2]:.0f}<extra></extra>'
            ),
            customdata=extremos_bid[['vol_current_price', 'vol_zscore', 'Volumen']].values
        ),
        row=1, col=1
    )

# Marcadores de volumen extremo ASK
if len(extremos_ask) > 0:
    fig.add_trace(
        go.Scatter(
            x=extremos_ask['TimeBin'],
            y=extremos_ask['Precio'],
            mode='markers',
            marker=dict(
                symbol='circle',
                size=12,
                color='rgb(0,255,0)',  # Verde intenso
                line=dict(color='rgb(0,255,0)', width=2)  # Borde verde
            ),
            name='Vol Extremo ASK',
            hovertemplate=(
                'Tiempo: %{x}<br>'
                'Precio: %{y}<br>'
                'Vol acumulado: %{customdata[0]:.0f}<br>'
                'Z-score: %{customdata[1]:.2f}<br>'
                'Vol tick: %{customdata[2]:.0f}<extra></extra>'
            ),
            customdata=extremos_ask[['vol_current_price', 'vol_zscore', 'Volumen']].values
        ),
        row=1, col=1
    )

# ==============================================================================
# SUBPLOT 2: DENSIDAD DE ABSORCIÓN
# ==============================================================================

# Curva de densidad BID (roja)
fig.add_trace(
    go.Scatter(
        x=density_bid['TimeBin'],
        y=density_bid['bid_density'],
        mode='lines',
        line=dict(color='rgb(255,0,0)', width=1),
        name='Densidad BID',
        hovertemplate='Tiempo: %{x}<br>Densidad BID: %{y:.2f}<extra></extra>'
    ),
    row=2, col=1
)

# Curva de densidad ASK (verde oscuro - forest green)
fig.add_trace(
    go.Scatter(
        x=density_ask['TimeBin'],
        y=density_ask['ask_density'],
        mode='lines',
        line=dict(color='rgb(34,139,34)', width=1),  # Forest green
        name='Densidad ASK',
        hovertemplate='Tiempo: %{x}<br>Densidad ASK: %{y:.2f}<extra></extra>'
    ),
    row=2, col=1
)

# Curva de net_density (negro) en eje Y derecho con áreas coloreadas
if 'net_density' in df.columns:
    # Área verde cuando net_density > 0 (más ASK que BID)
    density_positive = density_net.copy()
    density_positive['net_density_positive'] = density_net['net_density'].apply(lambda x: x if x > 0 else 0)

    fig.add_trace(
        go.Scatter(
            x=density_positive['TimeBin'],
            y=density_positive['net_density_positive'],
            fill='tozeroy',
            mode='none',
            fillcolor='rgba(0,255,0,0.1)',
            name='Net Density Positive',
            showlegend=False,
            yaxis='y3'
        ),
        row=2, col=1, secondary_y=True
    )

    # Área roja cuando net_density < 0 (más BID que ASK)
    density_negative = density_net.copy()
    density_negative['net_density_negative'] = density_net['net_density'].apply(lambda x: x if x < 0 else 0)

    fig.add_trace(
        go.Scatter(
            x=density_negative['TimeBin'],
            y=density_negative['net_density_negative'],
            fill='tozeroy',
            mode='none',
            fillcolor='rgba(255,0,0,0.1)',
            name='Net Density Negative',
            showlegend=False,
            yaxis='y3'
        ),
        row=2, col=1, secondary_y=True
    )

    # Línea horizontal en cero (referencia) - gris claro
    fig.add_hline(
        y=0,
        line=dict(color='rgba(128,128,128,0.3)', width=1),
        row=2, col=1,
        secondary_y=True
    )

# ==============================================================================
# LAYOUT
# ==============================================================================

fig.update_xaxes(title_text="", row=1, col=1, showgrid=False)  # Sin título
fig.update_yaxes(title_text="Precio", row=1, col=1, showgrid=False)
fig.update_xaxes(title_text="", row=2, col=1, showgrid=False)  # Sin título en eje X
fig.update_yaxes(title_text="Density 180s", row=2, col=1, showgrid=False, secondary_y=False)
fig.update_yaxes(title_text="Net Density", row=2, col=1, showgrid=False, secondary_y=True)

# Aplicar mismo background a ambos subplots
fig.update_xaxes(showline=True, linewidth=1, linecolor='lightgray', row=1, col=1)
fig.update_xaxes(showline=True, linewidth=1, linecolor='lightgray', row=2, col=1)
fig.update_yaxes(showline=True, linewidth=1, linecolor='lightgray', row=1, col=1)
fig.update_yaxes(showline=True, linewidth=1, linecolor='lightgray', row=2, col=1, secondary_y=False)
fig.update_yaxes(showline=True, linewidth=1, linecolor='lightgray', row=2, col=1, secondary_y=True)

fig.update_layout(
    title=dict(
        text=f'Mapa de Calor y Densidad - Volumen Acumulado por Nivel de Precio (NQ)<br>'
             f'<sub>Ventana: 10 minutos | Threshold: {ANOMALY_THRESHOLD} std | '
             f'Minutos {START_MINUTE}-{END_MINUTE}</sub>',
        x=0.5,
        xanchor='center',
        y=0.98,  # Bajar un poco el título
        yanchor='top'
    ),
    height=850,  # Reducido para gráfico más compacto
    showlegend=True,
    legend=dict(
        x=0.5,
        y=1.02,  # Arriba del gráfico
        xanchor='center',
        yanchor='bottom',
        orientation='h'
    ),
    hovermode='closest',
    plot_bgcolor='rgb(250,250,250)',  # Gris casi blanco
    paper_bgcolor='rgb(250,250,250)'   # Gris casi blanco para fondo
)

# ==============================================================================
# CREAR HISTOGRAMA SEPARADO (NUEVA PESTAÑA)
# ==============================================================================
print("\nCreando histograma de z-scores...")

z_scores_bid = df_bid[df_bid['vol_zscore'].notna()]['vol_zscore']
z_scores_ask = df_ask[df_ask['vol_zscore'].notna()]['vol_zscore']

fig_histogram = go.Figure()

# Histograma BID con más bins
fig_histogram.add_trace(
    go.Histogram(
        x=z_scores_bid,
        name='Z-scores BID',
        marker=dict(color='red', opacity=0.6),
        xbins=dict(start=-3, end=9, size=0.2),  # Bins más pequeños (0.2 vs 0.5)
        hovertemplate='Z-score: %{x}<br>Frecuencia: %{y}<extra></extra>'
    )
)

# Histograma ASK con más bins
fig_histogram.add_trace(
    go.Histogram(
        x=z_scores_ask,
        name='Z-scores ASK',
        marker=dict(color='green', opacity=0.6),
        xbins=dict(start=-3, end=9, size=0.2),  # Bins más pequeños
        hovertemplate='Z-score: %{x}<br>Frecuencia: %{y}<extra></extra>'
    )
)

# Línea vertical en threshold
fig_histogram.add_vline(
    x=ANOMALY_THRESHOLD,
    line=dict(color='orange', width=3, dash='dash'),
    annotation_text=f'Threshold = {ANOMALY_THRESHOLD}',
    annotation_position="top right"
)

# Layout del histograma
fig_histogram.update_layout(
    title=dict(
        text=f'Distribución de Z-Scores - Volumen por Nivel de Precio<br>'
             f'<sub>BID: {len(z_scores_bid):,} registros | ASK: {len(z_scores_ask):,} registros | '
             f'Minutos {START_MINUTE}-{END_MINUTE}</sub>',
        x=0.5,
        xanchor='center'
    ),
    xaxis_title="Z-score",
    yaxis_title="Frecuencia",
    height=600,
    barmode='overlay',
    showlegend=True,
    legend=dict(
        x=0.5,
        y=-0.15,
        xanchor='center',
        yanchor='top',
        orientation='h'
    ),
    hovermode='x'
)

# ==============================================================================
# GUARDAR Y ABRIR
# ==============================================================================
print(f"\nGuardando gráficos...")
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

# Guardar heatmap
fig.write_html(OUTPUT_FILE)
print(f"  1. Heatmap: {OUTPUT_FILE}")

# Guardar histograma
histogram_file = OUTPUT_FILE.replace('.html', '_histogram.html')
fig_histogram.write_html(histogram_file)
print(f"  2. Histograma: {histogram_file}")

print("\n" + "="*80)
print("ESTADISTICAS")
print("="*80)
print(f"\nVolumen extremo detectado:")
print(f"  BID: {len(extremos_bid):,} eventos")
print(f"  ASK: {len(extremos_ask):,} eventos")
print(f"\nZ-scores:")
print(f"  BID: max={z_scores_bid.max():.2f}, p95={z_scores_bid.quantile(0.95):.2f}")
print(f"  ASK: max={z_scores_ask.max():.2f}, p95={z_scores_ask.quantile(0.95):.2f}")
print(f"\nRango de precios:")
print(f"  Min: {df['Precio'].min()}")
print(f"  Max: {df['Precio'].max()}")
print(f"  Amplitud: {df['Precio'].max() - df['Precio'].min():.2f} puntos")

print("\n" + "="*80)
print(f"Graficos guardados:")
print(f"  1. {OUTPUT_FILE}")
print(f"  2. {histogram_file}")
print("="*80)

# Abrir ambos en navegador
webbrowser.open('file://' + os.path.abspath(OUTPUT_FILE))
webbrowser.open('file://' + os.path.abspath(histogram_file))
print("\nGraficos abiertos en navegador")
