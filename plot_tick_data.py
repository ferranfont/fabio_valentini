import os
import webbrowser
import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))
from config import CHART_WIDTH, CHART_HEIGHT, get_chart_path, DATA_DIR, SYMBOL

def plot_tick_data(symbol, timeframe, df, resample_seconds=60):
    """
    Función especializada para graficar datos tick con resample a segundos/minutos
    y mostrar como candlestick chart

    Args:
        symbol: Símbolo del instrumento (e.g., 'ES')
        timeframe: Timeframe string para el nombre del archivo
        df: DataFrame con tick data (debe tener índice datetime)
        resample_seconds: Segundos para resamplear (default 60 = 1 minuto)
    """
    html_path = get_chart_path(symbol, timeframe)

    # Asegurar que el DataFrame tenga índice datetime
    if not isinstance(df.index, pd.DatetimeIndex):
        if 'datetime' in df.columns:
            df = df.set_index('datetime')
        elif 'date' in df.columns:
            df = df.set_index('date')

    # Resamplear tick data a barras de tiempo
    resample_str = f'{resample_seconds}S' if resample_seconds < 60 else f'{resample_seconds//60}min'

    df_resampled = df.resample(resample_str).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()

    # Reset index para usar datetime como columna
    df_resampled = df_resampled.reset_index()
    df_resampled.columns = [col.lower() for col in df_resampled.columns]

    # Renombrar columna según sea necesario
    date_col = 'datetime' if 'datetime' in df_resampled.columns else 'date'

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.80, 0.20],
        vertical_spacing=0.03,
    )

    # Gráfico de velas (candlestick)
    fig.add_trace(go.Candlestick(
        x=df_resampled[date_col],
        open=df_resampled['open'],
        high=df_resampled['high'],
        low=df_resampled['low'],
        close=df_resampled['close'],
        increasing_line_color='rgba(0,0,0,0.95)',
        decreasing_line_color='rgba(0,0,0,0.95)',
        increasing_fillcolor='lime',
        decreasing_fillcolor='red',
        line=dict(width=1),
        name='OHLC'
    ), row=1, col=1)

    # Barras de volumen
    fig.add_trace(go.Bar(
        x=df_resampled[date_col],
        y=df_resampled['volume'],
        marker_color='royalblue',
        marker_line_color='blue',
        marker_line_width=0.4,
        opacity=0.95,
        name='Volume'
    ), row=2, col=1)

    # Determinar formato de tiempo según el resample
    if resample_seconds < 60:
        tick_format = "%H:%M:%S"
        dtick_ms = resample_seconds * 1000 * 10  # 10x resample interval
    else:
        tick_format = "%H:%M"
        dtick_ms = 3600000  # 1 hora

    fig.update_layout(
        dragmode='pan',
        title=f'{symbol}_{timeframe} - Tick Data Resampled to {resample_str}',
        width=CHART_WIDTH,
        height=CHART_HEIGHT,
        margin=dict(l=20, r=20, t=40, b=20),
        font=dict(size=12, color="black"),
        plot_bgcolor='white',
        paper_bgcolor='white',
        showlegend=False,
        template='plotly_white',
        xaxis=dict(
            type='date',
            tickformat=tick_format,
            tickangle=0,
            showgrid=False,
            linecolor='black',
            linewidth=1,
            range=[df_resampled[date_col].min(), df_resampled[date_col].max()],
            rangeslider=dict(visible=False)
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(128,128,128,0.2)',
            gridwidth=1,
            linecolor='black',
            linewidth=1
        ),
        xaxis2=dict(
            type='date',
            tickformat=tick_format,
            tickangle=45,
            showgrid=False,
            linecolor='black',
            linewidth=1,
            range=[df_resampled[date_col].min(), df_resampled[date_col].max()]
        ),
        yaxis2=dict(
            showgrid=True,
            gridcolor='rgba(128,128,128,0.1)',
            gridwidth=1,
            linecolor='black',
            linewidth=1
        ),
    )

    fig.write_html(html_path, config={
        "scrollZoom": True,
        "displayModeBar": True,
        "staticPlot": False,
        "toImageButtonOptions": {
            "format": "png",
            "filename": "tick_chart",
            "height": 500,
            "width": 700,
            "scale": 1
        }
    })

    print(f"✅ Gráfico de tick data guardado como HTML: '{html_path}'")
    print(f"📊 Tick data resampled a {resample_str} ({len(df_resampled)} barras)")

    webbrowser.open('file://' + os.path.realpath(html_path))


if __name__ == "__main__":
    # Configuración
    symbol = SYMBOL
    directorio = str(DATA_DIR)
    nombre_fichero = 'time_and_sales_nq_20250829.csv'
    ruta_completa = os.path.join(directorio, nombre_fichero)

    print("\n======================== 🔍 Cargando tick data ===========================")

    # Leer CSV con formato europeo
    df = pd.read_csv(
        ruta_completa,
        sep=';',
        decimal=',',
        names=['datetime', 'open', 'high', 'low', 'close', 'volume']
    )

    print(f'Fichero: {ruta_completa} importado')
    print(f"Características del Fichero: {df.shape}")

    # Convertir datetime
    df['datetime'] = pd.to_datetime(df['datetime'], format='%d/%m/%Y %H:%M', utc=True)
    df = df.set_index('datetime')

    print(f"Primeras filas:")
    print(df.head())
    print(f"\nÚltimas filas:")
    print(df.tail())

    # Graficar con diferentes resamples
    # Opción 1: 1 minuto (60 segundos)
    timeframe = 'tick_1min'
    plot_tick_data(symbol, timeframe, df, resample_seconds=60)