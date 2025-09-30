import os
import webbrowser
import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from config import CHART_WIDTH, CHART_HEIGHT, CHART_TEMPLATE, get_chart_path

def plot_close_and_volume(symbol, timeframe, df):
    html_path = get_chart_path(symbol, timeframe)

    df = df.rename(columns=str.lower)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.80, 0.20],
        vertical_spacing=0.03,
    )

    # Traza de precio (línea de cierre)
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['close'],
        mode='lines',
        line=dict(color='blue', width=1.5),
        name='Close'
    ), row=1, col=1)

    # Barras de volumen
    fig.add_trace(go.Bar(
        x=df['date'],
        y=df['volume'],
        marker_color='royalblue',
        marker_line_color='blue',
        marker_line_width=0.4,
        opacity=0.95,
        name='Volumen'
    ), row=2, col=1)

    fig.update_layout(
        dragmode='pan',
        title=f'{symbol}_{timeframe}',
        width=CHART_WIDTH,
        height=CHART_HEIGHT,
        margin=dict(l=20, r=20, t=40, b=20),
        font=dict(size=12, color="black"),
        plot_bgcolor='rgba(255,255,255,0.05)',
        paper_bgcolor='rgba(240,240,240,0.1)',
        showlegend=False,
        template=CHART_TEMPLATE,
        xaxis=dict(
            type='date',
            tickformat="%b %d<br>%Y",
            tickangle=0,
            showgrid=False,
            linecolor='gray',
            linewidth=1,
            range=[df['date'].min(), df['date'].max()]
        ),
        yaxis=dict(showgrid=True, linecolor='gray', linewidth=1),
        xaxis2=dict(
            type='date',
            tickformat="%b %d<br>%Y",
            tickangle=45,
            showgrid=False,
            linecolor='gray',
            linewidth=1,
            range=[df['date'].min(), df['date'].max()]
        ),
        yaxis2=dict(showgrid=True, linecolor='grey', linewidth=1),
        # shapes=shapes
    )

    fig.write_html(html_path, config={"scrollZoom": True})
    print(f"✅ Gráfico Plotly guardado como HTML: '{html_path}'")

    webbrowser.open('file://' + os.path.realpath(html_path))


if __name__ == "__main__":
    from config import DATA_DIR, SYMBOL, OHLCV_AGGREGATION

    symbol = SYMBOL
    directorio = str(DATA_DIR)
    nombre_fichero = 'es_1min_data_2015_2025.csv'
    ruta_completa = os.path.join(directorio, nombre_fichero)

    print("\n======================== 🔍 Cargando datos ===========================")
    df = pd.read_csv(ruta_completa)
    print(f'Fichero: {ruta_completa} importado')
    print(f"Características del Fichero: {df.shape}")

    # Normalizar columnas
    df.columns = [col.strip().lower() for col in df.columns]
    df = df.rename(columns={'volumen': 'volume'})

    # Formato datetime
    df['date'] = pd.to_datetime(df['date'], utc=True)
    df = df.set_index('date')

    # Resamplear a diario
    df_daily = df.resample('1D').agg(OHLCV_AGGREGATION).dropna()
    df_daily = df_daily.reset_index()

    print(f"\nDatos procesados: {df_daily.shape}")
    print(df_daily.head())

    # Graficar
    timeframe = '1D'
    plot_close_and_volume(symbol, timeframe, df_daily)
