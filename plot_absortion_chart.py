"""
Gráfico de absorción: Precio en línea + marcadores de absorción BID/ASK.
"""

import pandas as pd
import plotly.graph_objects as go
from config import CHART_WIDTH, CHART_HEIGHT

# Configuración
SYMBOL = 'NQ'  # Cambiar a 'ES' si usas E-mini S&P 500
DATA_FILE = f'data/time_and_sales_absorption_{SYMBOL}.csv'
OUTPUT_FILE = f'charts/absorption_chart_{SYMBOL}.html'

# Parámetros visuales
MARKER_SIZE_NORMAL = 3
MARKER_SIZE_ABSORPTION = 15
ALPHA_ABSORPTION = 0.5


def load_data(filepath):
    """Carga datos de absorción."""
    print(f"Cargando {filepath}...")
    df = pd.read_csv(filepath, sep=';', decimal=',')

    # Detectar columna de timestamp
    timestamp_col = next((col for col in df.columns if 'time' in col.lower()), None)

    if timestamp_col:
        df[timestamp_col] = pd.to_datetime(df[timestamp_col])
        df = df.sort_values(timestamp_col).reset_index(drop=True)

    print(f"  Registros: {len(df):,}")

    # Verificar columnas requeridas
    required = ['Precio', 'Lado', 'bid_abs', 'ask_abs']
    missing = [col for col in required if col not in df.columns]

    if missing:
        raise ValueError(f"Columnas faltantes: {missing}")

    print(f"  BID absorción: {df['bid_abs'].sum():,}")
    print(f"  ASK absorción: {df['ask_abs'].sum():,}")

    return df, timestamp_col


def create_absorption_chart(df, timestamp_col):
    """Crea gráfico de absorción."""
    print("\nCreando gráfico...")

    fig = go.Figure()

    # Línea de precio
    fig.add_trace(go.Scatter(
        x=df[timestamp_col],
        y=df['Precio'],
        mode='lines',
        name='Precio',
        line=dict(color='lightgray', width=1),
        hovertemplate='%{x}<br>Precio: %{y:.2f}<extra></extra>'
    ))

    # Puntos normales BID (pequeños, sin absorción)
    df_bid_normal = df[(df['Lado'] == 'BID') & (df['bid_abs'] == False)]
    if len(df_bid_normal) > 0:
        fig.add_trace(go.Scatter(
            x=df_bid_normal[timestamp_col],
            y=df_bid_normal['Precio'],
            mode='markers',
            name='BID',
            marker=dict(
                color='red',
                size=MARKER_SIZE_NORMAL,
                opacity=0.3
            ),
            hovertemplate='BID<br>%{x}<br>Precio: %{y:.2f}<extra></extra>'
        ))

    # Puntos normales ASK (pequeños, sin absorción)
    df_ask_normal = df[(df['Lado'] == 'ASK') & (df['ask_abs'] == False)]
    if len(df_ask_normal) > 0:
        fig.add_trace(go.Scatter(
            x=df_ask_normal[timestamp_col],
            y=df_ask_normal['Precio'],
            mode='markers',
            name='ASK',
            marker=dict(
                color='green',
                size=MARKER_SIZE_NORMAL,
                opacity=0.3
            ),
            hovertemplate='ASK<br>%{x}<br>Precio: %{y:.2f}<extra></extra>'
        ))

    # Absorción BID (puntos grandes rojos con alpha)
    df_bid_abs = df[(df['Lado'] == 'BID') & (df['bid_abs'] == True)]
    if len(df_bid_abs) > 0:
        # Preparar hover text
        hover_text = []
        for _, row in df_bid_abs.iterrows():
            text = f"<b>BID ABSORPTION</b><br>"
            text += f"Tiempo: {row[timestamp_col]}<br>"
            text += f"Precio: {row['Precio']:.2f}<br>"
            text += f"Volumen: {row['Volumen']:,.0f}<br>"
            if 'vol_zscore' in df.columns:
                text += f"Z-score: {row['vol_zscore']:.2f}<br>"
            if 'price_move_ticks' in df.columns:
                text += f"Move: {row['price_move_ticks']:.1f} ticks"
            hover_text.append(text)

        fig.add_trace(go.Scatter(
            x=df_bid_abs[timestamp_col],
            y=df_bid_abs['Precio'],
            mode='markers',
            name='BID Absorption',
            marker=dict(
                color='red',
                size=MARKER_SIZE_ABSORPTION,
                opacity=ALPHA_ABSORPTION,
                line=dict(width=2, color='darkred')
            ),
            text=hover_text,
            hovertemplate='%{text}<extra></extra>'
        ))

        print(f"  BID absorption: {len(df_bid_abs)} puntos")

    # Absorción ASK (puntos grandes verdes con alpha)
    df_ask_abs = df[(df['Lado'] == 'ASK') & (df['ask_abs'] == True)]
    if len(df_ask_abs) > 0:
        # Preparar hover text
        hover_text = []
        for _, row in df_ask_abs.iterrows():
            text = f"<b>ASK ABSORPTION</b><br>"
            text += f"Tiempo: {row[timestamp_col]}<br>"
            text += f"Precio: {row['Precio']:.2f}<br>"
            text += f"Volumen: {row['Volumen']:,.0f}<br>"
            if 'vol_zscore' in df.columns:
                text += f"Z-score: {row['vol_zscore']:.2f}<br>"
            if 'price_move_ticks' in df.columns:
                text += f"Move: {row['price_move_ticks']:.1f} ticks"
            hover_text.append(text)

        fig.add_trace(go.Scatter(
            x=df_ask_abs[timestamp_col],
            y=df_ask_abs['Precio'],
            mode='markers',
            name='ASK Absorption',
            marker=dict(
                color='green',
                size=MARKER_SIZE_ABSORPTION,
                opacity=ALPHA_ABSORPTION,
                line=dict(width=2, color='darkgreen')
            ),
            text=hover_text,
            hovertemplate='%{text}<extra></extra>'
        ))

        print(f"  ASK absorption: {len(df_ask_abs)} puntos")

    # Layout
    fig.update_layout(
        title='Absorción en Time & Sales - NQ',
        xaxis_title='Tiempo',
        yaxis_title='Precio',
        width=CHART_WIDTH * 3,  # Más ancho para ver timeline
        height=CHART_HEIGHT,
        hovermode='closest',
        showlegend=True,
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01
        ),
        plot_bgcolor='white',
        xaxis=dict(
            showgrid=True,
            gridcolor='lightgray',
            gridwidth=0.5
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='lightgray',
            gridwidth=0.5
        )
    )

    return fig


def add_statistics_annotation(fig, df):
    """Añade estadísticas como anotación en el gráfico."""

    total = len(df)
    bid_abs = df['bid_abs'].sum()
    ask_abs = df['ask_abs'].sum()
    total_abs = bid_abs + ask_abs

    stats_text = (
        f"<b>Estadísticas</b><br>"
        f"Total registros: {total:,}<br>"
        f"BID absorption: {bid_abs} ({bid_abs/total*100:.2f}%)<br>"
        f"ASK absorption: {ask_abs} ({ask_abs/total*100:.2f}%)<br>"
        f"Total absorption: {total_abs} ({total_abs/total*100:.2f}%)"
    )

    fig.add_annotation(
        text=stats_text,
        xref="paper", yref="paper",
        x=0.02, y=0.98,
        xanchor='left', yanchor='top',
        showarrow=False,
        bgcolor="rgba(255, 255, 255, 0.8)",
        bordercolor="black",
        borderwidth=1,
        font=dict(size=10)
    )

    return fig


def main():
    """Función principal."""
    print("="*60)
    print("GRÁFICO DE ABSORCIÓN")
    print("="*60)

    # Cargar datos
    df, timestamp_col = load_data(DATA_FILE)

    # Crear gráfico
    fig = create_absorption_chart(df, timestamp_col)

    # Añadir estadísticas
    fig = add_statistics_annotation(fig, df)

    # Guardar
    print(f"\nGuardando en {OUTPUT_FILE}...")
    fig.write_html(OUTPUT_FILE)

    # Abrir en navegador
    print("Abriendo en navegador...")
    import webbrowser
    webbrowser.open(OUTPUT_FILE)

    print("\nCompletado!")
    print("="*60)


if __name__ == "__main__":
    main()
