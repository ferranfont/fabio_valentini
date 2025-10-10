import os
import webbrowser
import pandas as pd
import plotly.graph_objs as go
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))
from config import CHART_WIDTH, CHART_HEIGHT, get_chart_path, DATA_DIR, SYMBOL


def plot_footprint_chart(symbol, df):
    """
    Visualiza footprint chart agregando volumen por nivel de precio
    Muestra BID y ASK por cada nivel de precio

    Args:
        symbol: Símbolo del instrumento
        df: DataFrame con columnas: Timestamp (index), Precio, Volumen, Lado
    """
    html_path = get_chart_path(symbol, 'footprint')

    # Agrupar por Precio y Lado, sumando el Volumen
    footprint = df.groupby(['Precio', 'Lado'])['Volumen'].sum().unstack(fill_value=0)

    # Asegurar que tenemos columnas BID y ASK
    if 'BID' not in footprint.columns:
        footprint['BID'] = 0
    if 'ASK' not in footprint.columns:
        footprint['ASK'] = 0

    # Ordenar por precio
    footprint = footprint.sort_index()

    print("\nFootprint data:")
    print(footprint)

    # Calcular volumen máximo para normalizar colores
    max_volume = max(footprint['BID'].max(), footprint['ASK'].max())

    # Calcular intensidad de color basada en el volumen (0.45 a 0.85 alpha)
    def get_color_with_alpha(volume, max_vol, base_color):
        if max_vol == 0 or volume == 0:
            alpha = 0.45
        else:
            # Alpha entre 0.45 (bajo volumen) y 0.85 (alto volumen)
            alpha = 0.45 + (volume / max_vol) * 0.4

        if base_color == 'red':
            return f'rgba(255, 0, 0, {alpha})'
        else:  # green
            return f'rgba(0, 128, 0, {alpha})'

    # Crear colores con gradiente para BID y ASK
    bid_colors = [get_color_with_alpha(vol, max_volume, 'red') for vol in footprint['BID']]
    ask_colors = [get_color_with_alpha(vol, max_volume, 'green') for vol in footprint['ASK']]

    # Crear figura
    fig = go.Figure()

    # Longitud constante para las barras (más pequeña, casi cuadradas)
    bar_length = 0.15

    # Barra de BID (izquierda, en rojo) - longitud fija, texto alineado a la derecha (hacia el centro)
    fig.add_trace(go.Bar(
        y=footprint.index,
        x=[-bar_length] * len(footprint),  # Longitud constante
        orientation='h',
        name='BID',
        marker=dict(color=bid_colors),  # Colores con gradiente
        text=['     ' + str(int(val)) for val in footprint['BID']],  # Más espacio a la derecha
        textfont=dict(size=32, color='black'),  # Fuente negra siempre
        textposition='inside',
        insidetextanchor='start',  # Alineado a la derecha (cerca de la línea central)
        hovertemplate='Price: %{y}<br>BID Volume: %{text}<extra></extra>'
    ))

    # Barra de ASK (derecha, en verde) - longitud fija, texto alineado a la izquierda
    fig.add_trace(go.Bar(
        y=footprint.index,
        x=[bar_length] * len(footprint),  # Longitud constante
        orientation='h',
        name='ASK',
        marker=dict(color=ask_colors),  # Colores con gradiente
        text=[str(int(val)) + '     ' for val in footprint['ASK']],  # Más espacio a la izquierda
        textfont=dict(size=32, color='black'),  # Fuente negra siempre
        textposition='inside',
        insidetextanchor='start',  # Alineado a la izquierda
        hovertemplate='Price: %{y}<br>ASK Volume: %{text}<extra></extra>'
    ))

    # Línea vertical negra central
    fig.add_shape(
        type="line",
        x0=0, y0=-0.5,
        x1=0, y1=len(footprint) - 0.5,
        line=dict(color="black", width=2)
    )

    # Layout
    fig.update_layout(
        title=f'{symbol} - Footprint Chart',
        barmode='overlay',
        width=400,  # Width más pequeño
        height=600,  # Altura reducida
        plot_bgcolor='white',
        paper_bgcolor='white',
        xaxis=dict(
            title='',
            showgrid=False,
            zeroline=False,
            showticklabels=False
        ),
        yaxis=dict(
            title='',
            showgrid=False,
            type='category',
            side='left'  # Precios a la izquierda
        ),
        showlegend=False
    )

    fig.write_html(html_path, config={
        "scrollZoom": True,
        "displayModeBar": True,
        "staticPlot": False
    })

    print(f"\nGrafico de Footprint guardado: '{html_path}'")
    print(f"Niveles de precio: {len(footprint)}")

    webbrowser.open('file://' + os.path.realpath(html_path))


if __name__ == "__main__":
    # Configuración
    n_temp = 500  # Número de filas a mostrar (para debug)
    symbol = SYMBOL
    directorio = str(DATA_DIR)
    nombre_fichero = 'time_and_sales.csv'
    ruta_completa = os.path.join(directorio, nombre_fichero)

    print("\n======================== Footprint Chart ===========================")

    # Leer CSV
    df = pd.read_csv(ruta_completa, sep=';', decimal=',')

    print(f'Fichero: {ruta_completa} importado')
    print(f"Registros totales: {df.shape[0]}")

    # Convertir Timestamp con formato específico
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], format='%Y-%m-%d %H:%M:%S.%f')
    df = df.set_index('Timestamp')

    # Tomar solo las primeras n_temp filas
    df_muestra = df.head(n_temp)

    print(f"\nMostrando primeras {n_temp} filas")
    print(f"Registros: {len(df_muestra)}")
    print(f"\nDatos:")
    print(df_muestra)

    # Graficar footprint
    plot_footprint_chart(symbol, df_muestra)
