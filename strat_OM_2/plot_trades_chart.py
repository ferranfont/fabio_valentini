import os
import webbrowser
import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config import CHART_WIDTH, CHART_HEIGHT, DATA_DIR, SYMBOL

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
TRADES_FILE = 'outputs/trading_record_strat_fabio_only_volume.csv'
DATA_FILE = f'data/time_and_sales_absorption_{SYMBOL}.csv'
OUTPUT_HTML = 'charts/trades_visualization_volume.html'

# Rango de trades a visualizar (por defecto)
DEFAULT_START_INDEX = 0
DEFAULT_END_INDEX = 500

# ==============================================================================
# FUNCIÓN PRINCIPAL
# ==============================================================================
def plot_trades_on_chart(start_idx=DEFAULT_START_INDEX, end_idx=DEFAULT_END_INDEX):
    """
    Visualiza las entradas y salidas de trades sobre el gráfico de precios

    Args:
        start_idx: Índice inicial del trade (filtro)
        end_idx: Índice final del trade (filtro)
    """

    print(f"\n{'='*70}")
    print(f"VISUALIZACIÓN DE TRADES - Índices {start_idx} a {end_idx}")
    print(f"{'='*70}\n")

    # Cargar datos de trades
    print(f"Cargando {TRADES_FILE}...")
    df_trades = pd.read_csv(TRADES_FILE, sep=';', decimal=',')
    df_trades.columns = df_trades.columns.str.strip()
    print(f"  Total trades: {len(df_trades):,}")

    # Filtrar por rango de índice
    df_trades = df_trades[(df_trades.index >= start_idx) & (df_trades.index < end_idx)].copy()
    print(f"  Trades filtrados: {len(df_trades):,}")

    if len(df_trades) == 0:
        print("No hay trades en el rango especificado.")
        return

    # Convertir fechas
    df_trades['entry_time'] = pd.to_datetime(df_trades['entry_time'])
    df_trades['exit_time'] = pd.to_datetime(df_trades['exit_time'])

    # Cargar datos de precio (time & sales)
    print(f"\nCargando {DATA_FILE}...")
    df_price = pd.read_csv(DATA_FILE, sep=';', decimal=',')
    df_price.columns = df_price.columns.str.strip()
    df_price['Timestamp'] = pd.to_datetime(df_price['Timestamp'])

    # Filtrar datos de precio según el rango temporal de los trades
    time_start = df_trades['entry_time'].min()
    time_end = df_trades['exit_time'].max()

    # Añadir margen de 5 minutos antes/después
    time_start = time_start - pd.Timedelta(minutes=5)
    time_end = time_end + pd.Timedelta(minutes=5)

    df_price = df_price[(df_price['Timestamp'] >= time_start) &
                        (df_price['Timestamp'] <= time_end)].copy()
    print(f"  Registros de precio: {len(df_price):,}")
    print(f"  Rango temporal: {time_start} a {time_end}")

    # ==============================================================================
    # CREAR GRÁFICO
    # ==============================================================================
    fig = go.Figure()

    # Línea de precio (tick data)
    fig.add_trace(go.Scatter(
        x=df_price['Timestamp'],
        y=df_price['Precio'],
        mode='lines',
        line=dict(color='blue', width=1),
        opacity=0.6,
        name='Precio',
        hovertemplate='<b>%{x}</b><br>Precio: %{y:.2f}<extra></extra>'
    ))

    # Agregar círculos de volumen extremo (bid_vol=rojo, ask_vol=verde)
    df_bid_vol = df_price[(df_price['bid_vol'] == True)]
    df_ask_vol = df_price[(df_price['ask_vol'] == True)]

    # BID volume extreme (círculos rojos alpha 0.4)
    if len(df_bid_vol) > 0:
        fig.add_trace(go.Scatter(
            x=df_bid_vol['Timestamp'],
            y=df_bid_vol['Precio']-0.25,
            mode='markers',
            marker=dict(
                symbol='circle',
                size=14,
                color='red',
                line=dict(width=1, color='darkred')
            ),
            opacity=0.4,
            name='BID Vol Extreme',
            showlegend=False,
            hovertemplate='<b>BID VOL</b><br>%{x}<br>Precio: %{y:.2f}<extra></extra>'
        ))

    # ASK volume extreme (círculos verdes alpha 0.4)
    if len(df_ask_vol) > 0:
        fig.add_trace(go.Scatter(
            x=df_ask_vol['Timestamp'],
            y=df_ask_vol['Precio']+0.25,
            mode='markers',
            marker=dict(
                symbol='circle',
                size=14,
                color='green',
                line=dict(width=1, color='darkgreen')
            ),
            opacity=0.4,
            name='ASK Vol Extreme',
            showlegend=False,
            hovertemplate='<b>ASK VOL</b><br>%{x}<br>Precio: %{y:.2f}<extra></extra>'
        ))

    # Agregar entradas y salidas de cada trade
    for idx, trade in df_trades.iterrows():
        side = trade['side']
        entry_time = trade['entry_time']
        exit_time = trade['exit_time']
        entry_price = trade['entry_price']
        exit_price = trade['exit_price']
        profit = trade['profit_dollars']
        resultado = trade['resultado']

        # Color según resultado
        if profit > 0:
            line_color = 'green'
        elif profit < 0:
            line_color = 'red'
        else:
            line_color = 'grey'

        # Entrada: triángulo up (LONG) o down (SHORT)
        if side == 'LONG':
            entry_symbol = 'triangle-up'
            entry_color = 'green'
        else:  # SHORT
            entry_symbol = 'triangle-down'
            entry_color = 'red'

        fig.add_trace(go.Scatter(
            x=[entry_time],
            y=[entry_price],
            mode='markers',
            marker=dict(
                symbol=entry_symbol,
                size=12,
                color=entry_color,
                line=dict(width=1, color='black')
            ),
            name=f'Entry {side}',
            showlegend=False,
            hovertemplate=(f'<b>ENTRY {side}</b><br>'
                          f'Index: {idx}<br>'
                          f'Time: {entry_time}<br>'
                          f'Price: {entry_price:.2f}<br>'
                          f'<extra></extra>')
        ))

        # Salida: cuadrado hueco (color según resultado)
        if profit > 0:
            exit_marker = 'green'
        elif profit < 0:
            exit_marker = 'red'
        else:
            exit_marker = 'grey'

        fig.add_trace(go.Scatter(
            x=[exit_time],
            y=[exit_price],
            mode='markers',
            marker=dict(
                symbol='square-open',
                size=8,
                color=exit_marker,
                line=dict(width=1, color=exit_marker)
            ),
            name='Exit',
            showlegend=False,
            hovertemplate=(f'<b>EXIT</b><br>'
                          f'Index: {idx}<br>'
                          f'Time: {exit_time}<br>'
                          f'Price: {exit_price:.2f}<br>'
                          f'Resultado: {resultado}<br>'
                          f'Profit: ${profit:.2f}<br>'
                          f'<extra></extra>')
        ))

        # Línea conectando entrada y salida (color según resultado, alpha 0.4)
        fig.add_trace(go.Scatter(
            x=[entry_time, exit_time],
            y=[entry_price, exit_price],
            mode='lines',
            line=dict(color=line_color, width=1),
            opacity=0.4,
            showlegend=False,
            hoverinfo='skip'
        ))

    # Layout
    fig.update_layout(
        title=f'{SYMBOL} - Trades Visualization - Fabio Only Volume (Índices {start_idx} a {end_idx})',
        width=CHART_WIDTH,
        height=CHART_HEIGHT,
        margin=dict(l=20, r=20, t=60, b=20),
        font=dict(size=12, color="black"),
        plot_bgcolor='white',
        paper_bgcolor='white',
        xaxis=dict(
            title='Tiempo',
            type='date',
            tickformat="%H:%M:%S",
            showgrid=False,  # Sin grid vertical
            linecolor='black',
            linewidth=1
        ),
        yaxis=dict(
            title='Precio',
            showgrid=True,  # Sólo grid horizontal
            gridcolor='rgba(128,128,128,0.2)',
            linecolor='black',
            linewidth=1
        ),
        hovermode='closest',
        dragmode='pan'
    )

    # Guardar HTML
    output_path = os.path.join(os.getcwd(), OUTPUT_HTML)
    fig.write_html(output_path, config={
        "scrollZoom": True,
        "displayModeBar": True,
        "staticPlot": False
    })

    print(f"\nGráfico guardado: {output_path}")
    print(f"\nEstadísticas del rango visualizado:")
    print(f"  Trades: {len(df_trades)}")
    print(f"  LONG: {len(df_trades[df_trades['side']=='LONG'])}")
    print(f"  SHORT: {len(df_trades[df_trades['side']=='SHORT'])}")
    print(f"  Profit total: ${df_trades['profit_dollars'].sum():.2f}")
    print(f"  Win rate: {(df_trades['profit_dollars'] > 0).sum() / len(df_trades) * 100:.1f}%")
    print(f"\n{'='*70}\n")

    # Abrir en navegador
    webbrowser.open('file://' + os.path.realpath(output_path))


if __name__ == "__main__":
    # Ejecutar con rango por defecto
    plot_trades_on_chart(start_idx=DEFAULT_START_INDEX, end_idx=DEFAULT_END_INDEX)

    # Para ejecutar con rangos personalizados:
    # plot_trades_on_chart(start_idx=5000, end_idx=10000)
