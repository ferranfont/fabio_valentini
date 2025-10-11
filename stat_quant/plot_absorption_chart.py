import os
import webbrowser
import pandas as pd
import plotly.graph_objs as go
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config import CHART_WIDTH, CHART_HEIGHT, get_chart_path, DATA_DIR, SYMBOL
from find_absortion import find_absorption


def plot_absorption_chart(symbol, df, outlier_threshold=1.5):
    """
    Visualiza el gráfico de precios con círculos que marcan outliers de BID/ASK

    Args:
        symbol: Símbolo del instrumento
        df: DataFrame con columnas: Timestamp (index), Precio, Volumen, Lado
        outlier_threshold: Umbral para detección de outliers
    """
    html_path = get_chart_path(symbol, 'absorption')

    # Obtener footprint con outliers
    footprint = find_absorption(df, outlier_threshold=outlier_threshold)

    # Crear figura
    fig = go.Figure()

    # Línea de precios (usando todos los ticks del time and sales)
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df['Precio'],
        mode='lines',
        name='Precio',
        line=dict(color='blue', width=1),
        hovertemplate='Time: %{x}<br>Price: %{y}<extra></extra>'
    ))

    # Preparar datos para círculos de outliers
    # Necesitamos encontrar un timestamp representativo para cada nivel de precio
    price_timestamps = df.groupby('Precio')['Precio'].first()

    # Filtrar outliers de BID
    bid_outliers = footprint[footprint['BID_outlier'] == True]
    ask_outliers = footprint[footprint['ASK_outlier'] == True]

    # Círculos rojos para BID outliers
    for _, row in bid_outliers.iterrows():
        precio = row['Precio']
        volumen = row['BID']

        # Encontrar timestamp para este precio
        timestamps_precio = df[df['Precio'] == precio].index
        if len(timestamps_precio) > 0:
            timestamp = timestamps_precio[len(timestamps_precio) // 2]  # Usar timestamp medio

            fig.add_trace(go.Scatter(
                x=[timestamp],
                y=[precio],
                mode='markers',
                marker=dict(
                    size=30,
                    color='rgba(255, 0, 0, 0.5)',
                    line=dict(color='red', width=2)
                ),
                name=f'BID Outlier ({int(volumen)})',
                showlegend=False,
                hovertemplate=f'Price: {precio}<br>BID Volume: {int(volumen)}<br>OUTLIER<extra></extra>'
            ))

    # Círculos verdes para ASK outliers
    for _, row in ask_outliers.iterrows():
        precio = row['Precio']
        volumen = row['ASK']

        # Encontrar timestamp para este precio
        timestamps_precio = df[df['Precio'] == precio].index
        if len(timestamps_precio) > 0:
            timestamp = timestamps_precio[len(timestamps_precio) // 2]  # Usar timestamp medio

            fig.add_trace(go.Scatter(
                x=[timestamp],
                y=[precio],
                mode='markers',
                marker=dict(
                    size=30,
                    color='rgba(0, 255, 0, 0.5)',
                    line=dict(color='green', width=2)
                ),
                name=f'ASK Outlier ({int(volumen)})',
                showlegend=False,
                hovertemplate=f'Price: {precio}<br>ASK Volume: {int(volumen)}<br>OUTLIER<extra></extra>'
            ))

    # Layout
    fig.update_layout(
        title=f'{symbol} - Absorption Analysis (Outliers)',
        xaxis=dict(
            title='Time',
            showgrid=True,
            gridcolor='lightgray'
        ),
        yaxis=dict(
            title='Price',
            showgrid=True,
            gridcolor='lightgray'
        ),
        width=CHART_WIDTH,
        height=CHART_HEIGHT,
        plot_bgcolor='white',
        paper_bgcolor='white',
        hovermode='closest'
    )

    fig.write_html(html_path, config={
        "scrollZoom": True,
        "displayModeBar": True,
        "staticPlot": False
    })

    print(f"\nGrafico de Absorption guardado: '{html_path}'")
    print(f"BID Outliers detectados: {len(bid_outliers)}")
    print(f"ASK Outliers detectados: {len(ask_outliers)}")

    webbrowser.open('file://' + os.path.realpath(html_path))


if __name__ == "__main__":
    # Configuración
    n_temp = 1000  # Número de últimas filas a analizar
    outlier_threshold = 1.5  # Umbral de desviación estándar para outliers
    symbol = SYMBOL
    directorio = str(DATA_DIR)
    nombre_fichero = 'time_and_sales.csv'
    ruta_completa = os.path.join(directorio, nombre_fichero)

    print("\n======================== Absorption Chart ===========================")

    # Leer CSV
    df = pd.read_csv(ruta_completa, sep=';', decimal=',')

    print(f'Fichero: {ruta_completa} importado')
    print(f"Registros totales: {df.shape[0]}")

    # Convertir Timestamp con formato específico
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], format='%Y-%m-%d %H:%M:%S.%f')
    df = df.set_index('Timestamp')

    # Tomar las últimas n_temp filas
    df_muestra = df.tail(n_temp)

    print(f"\nAnalizando ultimas {n_temp} filas")
    print(f"Periodo: {df_muestra.index[0]} - {df_muestra.index[-1]}")

    # Graficar absorption con outliers
    plot_absorption_chart(symbol, df_muestra, outlier_threshold=outlier_threshold)
