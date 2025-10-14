"""
Visualización en tiempo real de Time & Sales con detección de absorción.
Streamlit app que simula streaming de datos tick por tick.
"""

import streamlit as st
import pandas as pd
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import os

st.set_page_config(page_title="Time & Sales Real-Time", layout="wide")

# === INICIALIZAR SESSION STATE ===
if 'streaming' not in st.session_state:
    st.session_state.streaming = False
if 'current_index' not in st.session_state:
    st.session_state.current_index = 0
if 'df_loaded' not in st.session_state:
    st.session_state.df_loaded = None
if 'buffer_data' not in st.session_state:
    st.session_state.buffer_data = []

# === TÍTULO ===
st.title("📊 Time & Sales - Real Time con Detección de Absorción")

# === SIDEBAR: CONFIGURACIÓN ===
st.sidebar.header("⚙️ Configuración")

# Detectar ruta absoluta - usar getcwd() para Streamlit
work_dir = os.getcwd()
SYMBOL = 'NQ'  # Cambiar a 'ES' si usas E-mini S&P 500
default_csv_path = os.path.join(work_dir, "data", f"time_and_sales_absorption_{SYMBOL}.csv")

# Mostrar directorio actual para debug
st.sidebar.caption(f"📂 Directorio: {work_dir}")
st.sidebar.caption(f"📊 Símbolo: {SYMBOL}")

# Opción de carga: archivo local o upload
modo_carga = st.sidebar.radio(
    "Modo de carga:",
    ["📁 Archivo local", "⬆️ Subir CSV"]
)

if modo_carga == "📁 Archivo local":
    csv_file = st.sidebar.text_input(
        "📁 Ruta del CSV:",
        default_csv_path
    )
    uploaded_file = None
else:
    uploaded_file = st.sidebar.file_uploader(
        "⬆️ Subir CSV",
        type=['csv'],
        help="Sube el archivo time_and_sales_absorption.csv"
    )
    csv_file = None

# Cargar CSV desde archivo local
@st.cache_data
def cargar_csv(file_path):
    try:
        df = pd.read_csv(file_path, sep=';', decimal=',')

        # Detectar columnas de timestamp
        timestamp_cols = [col for col in df.columns if 'time' in col.lower() or 'timestamp' in col.lower()]
        if timestamp_cols:
            df[timestamp_cols[0]] = pd.to_datetime(df[timestamp_cols[0]])

        return df
    except Exception as e:
        st.error(f"Error al cargar CSV: {e}")
        return None

# Cargar CSV desde uploaded file
@st.cache_data
def cargar_csv_uploaded(uploaded_file):
    try:
        df = pd.read_csv(uploaded_file, sep=';', decimal=',')

        # Detectar columnas de timestamp
        timestamp_cols = [col for col in df.columns if 'time' in col.lower() or 'timestamp' in col.lower()]
        if timestamp_cols:
            df[timestamp_cols[0]] = pd.to_datetime(df[timestamp_cols[0]])

        return df
    except Exception as e:
        st.error(f"Error al cargar CSV: {e}")
        return None

# Cargar automáticamente al inicio si no hay datos cargados
if st.session_state.df_loaded is None:
    if csv_file and os.path.exists(csv_file):
        st.session_state.df_loaded = cargar_csv(csv_file)
    elif uploaded_file is not None:
        st.session_state.df_loaded = cargar_csv_uploaded(uploaded_file)

# Botón de carga/recarga
if st.sidebar.button("🔄 Cargar/Recargar CSV"):
    if csv_file:
        st.session_state.df_loaded = cargar_csv(csv_file)
    elif uploaded_file is not None:
        st.session_state.df_loaded = cargar_csv_uploaded(uploaded_file)
    else:
        st.error("Por favor, proporciona un archivo CSV")

    st.session_state.current_index = 0
    st.session_state.buffer_data = []
    st.session_state.streaming = False

df = st.session_state.df_loaded

if df is not None and len(df) > 0:
    st.sidebar.success(f"✅ CSV cargado: {len(df):,} registros")

    # === CONFIGURACIÓN DE COLUMNAS ===
    st.sidebar.subheader("📋 Mapeo de Columnas")

    columnas = df.columns.tolist()

    # Autodetección inteligente
    col_timestamp_default = next((i for i, c in enumerate(columnas) if 'time' in c.lower()), 0)
    col_precio_default = next((i for i, c in enumerate(columnas) if 'precio' in c.lower() or 'price' in c.lower()), 1)
    col_volumen_default = next((i for i, c in enumerate(columnas) if 'volumen' in c.lower() or 'volume' in c.lower()), 2)
    col_lado_default = next((i for i, c in enumerate(columnas) if 'lado' in c.lower() or 'side' in c.lower()), 3)

    col_timestamp = st.sidebar.selectbox("⏰ Timestamp:", columnas, index=col_timestamp_default)
    col_precio = st.sidebar.selectbox("💰 Precio:", columnas, index=col_precio_default)
    col_volumen = st.sidebar.selectbox("📦 Volumen:", columnas, index=col_volumen_default)
    col_lado = st.sidebar.selectbox("↔️ Lado (BID/ASK):", columnas, index=col_lado_default)

    # Ya no usamos absorción, solo volumen extremo
    mostrar_absortion = False

    # === CONTROL DE VELOCIDAD ===
    st.sidebar.subheader("⚡ Velocidad")

    modo_velocidad = st.sidebar.radio(
        "Modo:",
        ["Lento (1/s)", "Normal (10/s)", "Rápido (50/s)", "Ultra (100/s)", "Personalizado"]
    )

    if modo_velocidad == "Personalizado":
        velocidad = st.sidebar.slider("Registros/segundo:", 1, 500, 20)
    else:
        velocidades = {
            "Lento (1/s)": 1,
            "Normal (10/s)": 10,
            "Rápido (50/s)": 50,
            "Ultra (100/s)": 100
        }
        velocidad = velocidades[modo_velocidad]

    delay = 1.0 / velocidad
    tiempo_total = len(df) * delay

    st.sidebar.info(f"⏱️ Delay: {delay*1000:.1f}ms")
    st.sidebar.info(f"⏳ Tiempo total: {tiempo_total/60:.1f} min")

    # === FILTROS ===
    st.sidebar.subheader("🔍 Filtros")

    filtrar_por_rango = st.sidebar.checkbox("Filtrar por rango de índices")
    if filtrar_por_rango:
        idx_start = st.sidebar.number_input("Desde índice:", 0, len(df)-1, 0)
        idx_end = st.sidebar.number_input("Hasta índice:", 0, len(df)-1, min(1000, len(df)-1))
        df = df.iloc[idx_start:idx_end+1].reset_index(drop=True)
        st.sidebar.info(f"📊 Mostrando {len(df):,} registros")

    # === CONTROLES PRINCIPALES ===
    st.sidebar.subheader("🎮 Controles")

    col_play, col_pause = st.sidebar.columns(2)

    with col_play:
        if st.button("▶️ Play", use_container_width=True):
            st.session_state.streaming = True

    with col_pause:
        if st.button("⏸️ Pause", use_container_width=True):
            st.session_state.streaming = False

    col_reset, col_skip = st.sidebar.columns(2)

    with col_reset:
        if st.button("🔄 Reiniciar", use_container_width=True):
            st.session_state.current_index = 0
            st.session_state.buffer_data = []
            st.session_state.streaming = False
            st.rerun()

    with col_skip:
        if st.button("⏭️ Final", use_container_width=True):
            st.session_state.current_index = len(df)
            st.session_state.buffer_data = df.to_dict('records')
            st.session_state.streaming = False

    # === VISTA: BUFFER DE DATOS ===
    st.sidebar.subheader("📊 Buffer")
    buffer_size = st.sidebar.slider("Tamaño ventana visual:", 50, 5000, 500)

    # === ÁREA PRINCIPAL ===

    # Métricas superiores
    col1, col2, col3, col4, col5 = st.columns(5)

    metric_precio = col1.empty()
    metric_volumen = col2.empty()
    metric_lado = col3.empty()
    metric_absortion = col4.empty()
    metric_progreso = col5.empty()

    # Barra de progreso
    progress_bar = st.progress(0)
    status_text = st.empty()

    # Gráfico principal
    chart_container = st.empty()

    # Tabs para diferentes vistas
    tab1, tab2, tab3 = st.tabs(["📋 Tabla Reciente", "📊 Estadísticas", "⚡ Detalles Volumen Extremo"])

    with tab1:
        table_container = st.empty()

    with tab2:
        stats_container = st.empty()

    with tab3:
        absortion_container = st.empty()

    # === LÓGICA DE STREAMING ===

    if st.session_state.streaming and st.session_state.current_index < len(df):

        idx = st.session_state.current_index
        row = df.iloc[idx]

        # Agregar al buffer
        st.session_state.buffer_data.append(row.to_dict())

        # Limitar tamaño del buffer para performance
        if len(st.session_state.buffer_data) > buffer_size:
            st.session_state.buffer_data = st.session_state.buffer_data[-buffer_size:]

        # Convertir buffer a DataFrame
        df_buffer = pd.DataFrame(st.session_state.buffer_data)

        # === MÉTRICAS ===
        precio_actual = row[col_precio]
        volumen_actual = row[col_volumen]
        lado_actual = row[col_lado]

        # Delta de precio
        delta_precio = None
        if len(df_buffer) > 1:
            delta_precio = precio_actual - df_buffer[col_precio].iloc[-2]

        metric_precio.metric(
            "💰 Precio",
            f"{precio_actual:.2f}",
            delta=f"{delta_precio:.2f}" if delta_precio else None
        )
        metric_volumen.metric("📦 Volumen", f"{volumen_actual:,.0f}")

        # Color para lado
        lado_color = "🟢" if lado_actual == "ASK" else "🔴"
        metric_lado.metric("↔️ Lado", f"{lado_color} {lado_actual}")

        # Volumen extremo
        es_bid_vol = row.get('bid_vol', False)
        es_ask_vol = row.get('ask_vol', False)
        if es_bid_vol or es_ask_vol:
            tipo_vol = "BID" if es_bid_vol else "ASK"
            metric_absortion.metric("⚡ Vol Extremo", f"⚠️ {tipo_vol}", delta="Z-score >= 2.0")
        else:
            metric_absortion.metric("⚡ Vol Extremo", "---")

        # Progreso
        progreso = (idx + 1) / len(df)
        metric_progreso.metric("📈 Progreso", f"{progreso*100:.1f}%")

        # === GRÁFICO ===
        fig = make_subplots(
            rows=3, cols=1,
            row_heights=[0.5, 0.25, 0.25],
            shared_xaxes=True,
            vertical_spacing=0.04,
            subplot_titles=("Heatmap - Volumen por Nivel de Precio", "Volumen", "Densidad")
        )

        # === SUBPLOT 1: HEATMAP + BOLITAS ===
        df_bid = df_buffer[df_buffer[col_lado] == 'BID']
        df_ask = df_buffer[df_buffer[col_lado] == 'ASK']

        # Preparar heatmap si existe vol_current_price
        if 'vol_current_price' in df_buffer.columns:
            # Redondear precios para agrupar
            TICK_SIZE = 0.25
            df_buffer_copy = df_buffer.copy()
            df_buffer_copy['Precio_rounded'] = (df_buffer_copy[col_precio] / TICK_SIZE).round() * TICK_SIZE

            # Crear bins de tiempo (cada 5 registros para performance)
            bin_size = max(5, len(df_buffer) // 50)  # Máximo 50 bins
            df_buffer_copy['time_bin'] = df_buffer_copy.index // bin_size

            # Pivot para heatmap
            try:
                pivot = df_buffer_copy.pivot_table(
                    values='vol_current_price',
                    index='Precio_rounded',
                    columns='time_bin',
                    aggfunc='max',
                    fill_value=0
                )

                # Agregar heatmap
                fig.add_trace(
                    go.Heatmap(
                        z=pivot.values,
                        x=pivot.columns,
                        y=pivot.index,
                        colorscale=[
                            [0.0, '#f0f0f0'],
                            [0.3, '#fff4e6'],
                            [0.5, '#ffe0b2'],
                            [0.7, '#ffb74d'],
                            [0.9, '#ff9800'],
                            [1.0, '#e65100']
                        ],
                        showscale=False,
                        hovertemplate='Precio: %{y}<br>Vol: %{z}<extra></extra>',
                        name='Volumen'
                    ),
                    row=1, col=1
                )
            except:
                pass  # Si falla pivot, continuar sin heatmap

        # Crear índices para scatter plots
        indices = list(range(len(df_buffer)))
        bid_mask = df_buffer[col_lado] == 'BID'
        ask_mask = df_buffer[col_lado] == 'ASK'

        bid_indices = [i for i, m in enumerate(bid_mask) if m]
        ask_indices = [i for i, m in enumerate(ask_mask) if m]

        # Líneas de precio BID/ASK
        if len(df_bid) > 0:
            fig.add_trace(
                go.Scatter(
                    x=bid_indices,
                    y=df_bid[col_precio],
                    mode='lines',
                    name='BID Line',
                    line=dict(color='red', width=1),
                    opacity=0.7
                ),
                row=1, col=1
            )

        if len(df_ask) > 0:
            fig.add_trace(
                go.Scatter(
                    x=ask_indices,
                    y=df_ask[col_precio],
                    mode='lines',
                    name='ASK Line',
                    line=dict(color='green', width=1),
                    opacity=0.7
                ),
                row=1, col=1
            )

        # Bolitas de volumen extremo (círculos rojos/verdes)
        if 'bid_vol' in df_buffer.columns and 'ask_vol' in df_buffer.columns:
            df_bid_vol = df_buffer[df_buffer['bid_vol'] == True]
            df_ask_vol = df_buffer[df_buffer['ask_vol'] == True]

            if len(df_bid_vol) > 0:
                indices_bid_vol = [i for i, val in enumerate(df_buffer['bid_vol']) if val]
                fig.add_trace(
                    go.Scatter(
                        x=indices_bid_vol,
                        y=df_bid_vol[col_precio],
                        mode='markers',
                        name='Vol Extremo BID',
                        marker=dict(
                            color='rgb(255,0,0)',
                            size=12,
                            symbol='circle',
                            line=dict(color='rgb(255,0,0)', width=2)
                        )
                    ),
                    row=1, col=1
                )

            if len(df_ask_vol) > 0:
                indices_ask_vol = [i for i, val in enumerate(df_buffer['ask_vol']) if val]
                fig.add_trace(
                    go.Scatter(
                        x=indices_ask_vol,
                        y=df_ask_vol[col_precio],
                        mode='markers',
                        name='Vol Extremo ASK',
                        marker=dict(
                            color='rgb(0,255,0)',
                            size=12,
                            symbol='circle',
                            line=dict(color='rgb(0,255,0)', width=2)
                        )
                    ),
                    row=1, col=1
                )


        # Absorción eliminada - se reevaluará el método

        # === SUBPLOT 2: VOLUMEN ===
        colors_vol = ['red' if s == 'BID' else 'green' for s in df_buffer[col_lado]]
        fig.add_trace(
            go.Bar(
                x=list(range(len(df_buffer))),
                y=df_buffer[col_volumen],
                name='Volumen',
                marker_color=colors_vol,
                opacity=0.5
            ),
            row=2, col=1
        )

        # === SUBPLOT 3: DENSIDAD ===
        if 'bid_density' in df_buffer.columns and 'ask_density' in df_buffer.columns:
            fig.add_trace(
                go.Scatter(
                    x=list(range(len(df_buffer))),
                    y=df_buffer['bid_density'],
                    mode='lines',
                    name='Densidad BID',
                    line=dict(color='rgb(255,0,0)', width=1)
                ),
                row=3, col=1
            )

            fig.add_trace(
                go.Scatter(
                    x=list(range(len(df_buffer))),
                    y=df_buffer['ask_density'],
                    mode='lines',
                    name='Densidad ASK',
                    line=dict(color='rgb(0,255,0)', width=1)
                ),
                row=3, col=1
            )

        # Layout
        fig.update_layout(
            title=f"📊 Registro {idx+1}/{len(df)} | {velocidad} reg/s | Buffer: {len(df_buffer)}",
            height=900,
            hovermode='x unified',
            showlegend=True,
            plot_bgcolor='rgb(250,250,250)',
            paper_bgcolor='rgb(250,250,250)'
        )

        fig.update_xaxes(title_text="", row=1, col=1, showgrid=False)
        fig.update_xaxes(title_text="", row=2, col=1, showgrid=False)
        fig.update_xaxes(title_text="Índice", row=3, col=1, showgrid=False)
        fig.update_yaxes(title_text="Precio", row=1, col=1, showgrid=False)
        fig.update_yaxes(title_text="Volumen", row=2, col=1, showgrid=False)
        fig.update_yaxes(title_text="Densidad", row=3, col=1, showgrid=False)

        chart_container.plotly_chart(fig, use_container_width=True, key=f"chart_{idx}")

        # === TABLA ===
        n_recientes = min(20, len(df_buffer))
        df_tabla = df_buffer.tail(n_recientes).copy()

        # Formatear columnas para display
        cols_display = [col_timestamp, col_precio, col_volumen, col_lado]
        # Agregar columnas de volumen extremo si existen
        if 'bid_vol' in df_buffer.columns:
            cols_display.extend(['bid_vol', 'ask_vol'])
        if 'bid_density' in df_buffer.columns:
            cols_display.extend(['bid_density', 'ask_density'])

        df_tabla_display = df_tabla[cols_display].copy()
        df_tabla_display[col_precio] = df_tabla_display[col_precio].apply(lambda x: f"{x:.2f}")
        df_tabla_display[col_volumen] = df_tabla_display[col_volumen].apply(lambda x: f"{x:,.0f}")

        table_container.dataframe(df_tabla_display, use_container_width=True, hide_index=True)

        # === ESTADÍSTICAS ===
        total_registros = len(df_buffer)
        vol_total = df_buffer[col_volumen].sum()
        precio_min = df_buffer[col_precio].min()
        precio_max = df_buffer[col_precio].max()
        precio_mean = df_buffer[col_precio].mean()

        bid_count = (df_buffer[col_lado] == 'BID').sum()
        ask_count = (df_buffer[col_lado] == 'ASK').sum()

        stats_html = f"""
        <h3>Estadísticas del Buffer</h3>
        <ul>
            <li><b>Total registros:</b> {total_registros:,}</li>
            <li><b>Volumen total:</b> {vol_total:,.0f}</li>
            <li><b>Precio min/max/mean:</b> {precio_min:.2f} / {precio_max:.2f} / {precio_mean:.2f}</li>
            <li><b>BID count:</b> {bid_count:,} ({bid_count/total_registros*100:.1f}%)</li>
            <li><b>ASK count:</b> {ask_count:,} ({ask_count/total_registros*100:.1f}%)</li>
        </ul>
        """

        # Volumen extremo si existe
        if 'bid_vol' in df_buffer.columns and 'ask_vol' in df_buffer.columns:
            bid_vol_count = df_buffer['bid_vol'].sum()
            ask_vol_count = df_buffer['ask_vol'].sum()
            stats_html += f"""
            <h3>Volumen Extremo (Z-score >= 2.0)</h3>
            <ul>
                <li><b>BID volumen extremo:</b> {bid_vol_count} eventos</li>
                <li><b>ASK volumen extremo:</b> {ask_vol_count} eventos</li>
            </ul>
            """

        stats_container.markdown(stats_html, unsafe_allow_html=True)

        # === DETALLES VOLUMEN EXTREMO ===
        if 'bid_vol' in df_buffer.columns and 'ask_vol' in df_buffer.columns:
            df_vol_ext = df_buffer[(df_buffer['bid_vol'] == True) | (df_buffer['ask_vol'] == True)]

            if len(df_vol_ext) > 0:
                absortion_container.dataframe(
                    df_vol_ext[[col_timestamp, col_precio, col_volumen, col_lado, 'bid_vol', 'ask_vol']].tail(10),
                    use_container_width=True
                )
            else:
                absortion_container.info("No hay eventos de volumen extremo en el buffer actual")

        # Actualizar progreso
        progress_bar.progress(progreso)
        status_text.text(f"⏳ Streaming: {idx+1}/{len(df)} ({progreso*100:.1f}%) | ⚡ {velocidad} reg/s")

        # Incrementar y rerun
        st.session_state.current_index += 1
        time.sleep(delay)
        st.rerun()

    elif st.session_state.current_index >= len(df):
        st.success("✅ Stream completado!")
        st.balloons()
        st.session_state.streaming = False

    else:
        st.info("⏸️ Presiona PLAY para iniciar el streaming")

else:
    st.warning("⚠️ Proporciona una ruta válida y presiona 'Cargar/Recargar CSV'")
