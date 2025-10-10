import os
import webbrowser
import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))
from config import CHART_WIDTH, CHART_HEIGHT, get_chart_path, DATA_DIR, SYMBOL


def plot_time_and_sales(symbol, df):
    """
    Visualiza datos de time and sales con formato tipo tabla
    Muestra: Hora, Precio (verde ASK/rojo BID), Volumen, Lado, Bid, Ask

    Args:
        symbol: Símbolo del instrumento
        df: DataFrame con columnas: Timestamp (index), Precio, Volumen, Lado, Bid, Ask
    """
    html_path = get_chart_path(symbol, 'time_and_sales')

    # Preparar datos para la visualización
    df_display = df.copy()

    # Extraer hora con milisegundos del timestamp
    df_display['Time'] = df_display.index.strftime('%H:%M:%S.%f').str[:-3]  # Elimina los últimos 3 dígitos para mostrar milisegundos

    # Debug: mostrar primeras horas
    print(f"\nPrimeras horas a mostrar:")
    print(df_display['Time'].head(10))

    # Crear figura con tabla estilo scatter
    fig = go.Figure()

    # Columnas a mostrar: time, price, volume, side, bid, ask
    # Espaciado mínimo entre columnas
    columns_config = [
        {'col': 'Time', 'x': 0.08, 'color': 'black'},
        {'col': 'Precio', 'x': 0.20, 'color_map': {'ASK': 'green', 'BID': 'red'}},
        {'col': 'Volumen', 'x': 0.30, 'color': 'black'},
        {'col': 'Lado', 'x': 0.38, 'color_map': {'ASK': 'green', 'BID': 'red'}},
        {'col': 'Bid', 'x': 0.46, 'color': 'black'},
        {'col': 'Ask', 'x': 0.54, 'color': 'black'}
    ]

    # Añadir puntos para cada columna
    for config in columns_config:
        col_name = config['col']
        x_pos = config['x']

        if 'color_map' in config:
            # Precio: color según BID/ASK
            for lado, color in [('BID', 'red'), ('ASK', 'green')]:
                df_lado = df_display[df_display['Lado'] == lado]
                y_positions = [i for i, idx in enumerate(df_display.index) if idx in df_lado.index]

                fig.add_trace(go.Scatter(
                    x=[x_pos] * len(df_lado),
                    y=y_positions,
                    mode='text',
                    text=df_lado[col_name].values,
                    textposition='middle center',
                    textfont=dict(size=10, color=color),
                    showlegend=False,
                    hoverinfo='skip'
                ))
        else:
            # Otras columnas con color fijo
            fig.add_trace(go.Scatter(
                x=[x_pos] * len(df_display),
                y=list(range(len(df_display))),
                mode='text',
                text=df_display[col_name].values,
                textposition='middle center',
                textfont=dict(size=10, color=config['color']),
                showlegend=False,
                hoverinfo='skip'
            ))

    # Actualizar layout para que parezca una tabla
    fig.update_layout(
        title=f'{symbol} - Time and Sales',
        width=400,  # Width reducido
        height=CHART_HEIGHT,
        margin=dict(l=60, r=20, t=100, b=20),  # Margen superior mayor para separar título de cabecera
        plot_bgcolor='white',
        paper_bgcolor='white',
        xaxis=dict(
            showgrid=False,
            showticklabels=True,
            tickmode='array',
            tickvals=[0.08, 0.20, 0.30, 0.38, 0.46, 0.54],
            ticktext=['time', 'price', 'volume', 'side', 'bid', 'ask'],  # Minúsculas
            range=[0, 0.62],  # Rango ajustado con margen
            fixedrange=True,
            side='top'  # Mover etiquetas arriba
        ),
        yaxis=dict(
            showgrid=False,  # Sin grid horizontal
            showticklabels=False,
            range=[-1, len(df)],
            fixedrange=False,
            autorange='reversed'
        ),
        showlegend=False,
        hovermode=False
    )

    fig.write_html(html_path, config={
        "scrollZoom": True,
        "displayModeBar": True,
        "staticPlot": False
    })

    print(f"Grafico de Time and Sales guardado: '{html_path}'")
    print(f"Registros mostrados: {len(df)}")

    webbrowser.open('file://' + os.path.realpath(html_path))


if __name__ == "__main__":
    # Configuración
    limit_rows = 50  # None para mostrar todas las filas, o un número (ej: 100)
    symbol = SYMBOL
    directorio = str(DATA_DIR)
    nombre_fichero = 'time_and_sales.csv'
    ruta_completa = os.path.join(directorio, nombre_fichero)

    print("\n======================== Time and Sales ===========================")

    # Leer CSV
    df = pd.read_csv(ruta_completa, sep=';', decimal=',')

    print(f'Fichero: {ruta_completa} importado')
    print(f"Registros: {df.shape[0]}")
    print(f"Columnas: {df.columns.tolist()}")

    # Convertir Timestamp con formato específico
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], format='%Y-%m-%d %H:%M:%S.%f')
    df = df.set_index('Timestamp')

    print(f"Primeras filas:")
    print(df.head(20))

    # Aplicar límite de filas si está definido
    if limit_rows is not None:
        df = df.head(limit_rows)  # Cambiado de tail a head para mostrar las primeras filas
        print(f"\nMostrando primeras {limit_rows} filas")
    else:
        print(f"\nMostrando todas las filas ({len(df)} registros)")

    # Graficar
    plot_time_and_sales(symbol, df)
