"""
Monitor en tiempo real de archivos CSV de NinjaTrader 8.

Este script:
1. Observa un archivo CSV (TS o Ticks) en tiempo real
2. Detecta cuando NinjaTrader añade nuevas filas
3. Muestra las nuevas filas inmediatamente en el terminal

Uso:
    python utils/monitor_ninja_csv.py
"""

import os
import time
import pandas as pd
from pathlib import Path
from datetime import datetime

# ============================================================
# IMPORTACIONES OPCIONALES PARA GRÁFICO DINÁMICO
# ============================================================
# Solo se importan si ENABLE_DYNAMIC_CHART = True
PLOTLY_AVAILABLE = False
try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import webbrowser
    import tempfile
    PLOTLY_AVAILABLE = True
except ImportError:
    pass

# ============================================================
# CONFIGURACIÓN
# ============================================================
BASE_DIR = Path(r"C:\Users\ferra\Documents\NinjaTrader 8\ticks")

# Tipo de archivo a monitorear
FILE_TYPE = "TS"  # "TS" o "Ticks"

# Intervalo de chequeo en segundos
CHECK_INTERVAL = 1.0

# Directorio de salida para CSV limpio
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "monitor_ninja"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# CONFIGURACIÓN GRÁFICO DINÁMICO (OPCIONAL)
# ============================================================
# Cambiar a True para habilitar el gráfico dinámico con Plotly
ENABLE_DYNAMIC_CHART = True  # False = solo terminal, True = gráfico + terminal
MAX_CHART_POINTS = 5000      # Máximo de puntos en el gráfico (ventana deslizante)
VISIBLE_TIME_WINDOW = 120    # Segundos visibles en el eje X (ventana deslizante temporal)
PADDING_RIGHT_SECONDS = 5    # Padding en blanco a la derecha (segundos)

# ============================================================
# FUNCIONES
# ============================================================

# ============================================================
# BLOQUE OPCIONAL: GRÁFICO DINÁMICO CON PLOTLY
# ============================================================
# Este bloque completo puede eliminarse sin afectar la funcionalidad principal
# del monitor (terminal output + CSV save)

class DynamicChart:
    """Gestor de gráfico dinámico con Plotly (OPCIONAL)."""

    def __init__(self, max_points=100):
        """
        Inicializa el gráfico dinámico.

        Args:
            max_points: Máximo de puntos a mostrar (ventana deslizante)
        """
        if not PLOTLY_AVAILABLE:
            raise ImportError("Plotly no está instalado. Instalar con: pip install plotly")

        self.max_points = max_points
        self.data_buffer = {
            'timestamp': [],
            'close': [],
            'volume': [],
            'color': []
        }
        self.fig = None
        self.html_file = None
        self._create_figure()

    def _create_figure(self):
        """Crea la figura de Plotly con 2 trazas (Scatter + EMA)."""
        self.fig = go.Figure()

        # Traza 1: Scatter con volumen y color
        self.fig.add_trace(go.Scatter(
            x=[],
            y=[],
            mode='markers',
            name='Last',
            marker=dict(
                size=[],
                color=[],
                opacity=[],
                line=dict(width=0)
            ),
            hovertemplate='<b>Time:</b> %{x}<br><b>Price:</b> %{y}<br><b>Vol:</b> %{text}<extra></extra>',
            text=[]
        ))

        # Traza 2: Media Exponencial
        self.fig.add_trace(go.Scatter(
            x=[],
            y=[],
            mode='lines',
            name='EMA',
            line=dict(color='blue', width=1)
        ))

        # Layout
        self.fig.update_layout(
            title='NinjaTrader Real-Time Monitor (EMA + Volume-Weighted Points)',
            xaxis_title='Time',
            yaxis_title='Price',
            hovermode='closest',
            height=600,
            template='plotly_white',
            showlegend=False,  # Sin leyenda
            xaxis=dict(
                showgrid=False,  # Sin grid vertical
                tickformat='%H:%M',  # Solo hora:minutos
                nticks=10  # Máximo 10 ticks en el eje X
            ),
            yaxis=dict(
                showgrid=True,  # Grid horizontal activado
                gridcolor='lightgray'
            )
        )

        # Crear archivo HTML temporal con auto-refresh
        temp_dir = tempfile.gettempdir()
        self.html_file = Path(temp_dir) / "ninja_monitor_realtime.html"

        # Escribir HTML con meta refresh
        html_string = self.fig.to_html(include_plotlyjs='cdn')
        # Añadir meta refresh al HTML (recargar cada 2 segundos)
        html_with_refresh = html_string.replace(
            '<head>',
            '<head><meta http-equiv="refresh" content="2">'
        )

        with open(self.html_file, 'w', encoding='utf-8') as f:
            f.write(html_with_refresh)

        # Abrir en navegador
        webbrowser.open(f'file:///{self.html_file}')
        print(f"[CHART] Gráfico abierto en navegador: {self.html_file}")
        print(f"[CHART] Auto-refresh cada 2 segundos activado")

    def update(self, df_clean):
        """
        Actualiza el gráfico con nuevas filas.

        Args:
            df_clean: DataFrame con nuevas filas limpias
        """
        if df_clean.empty:
            return

        # Convertir valores a float (pueden venir como strings con formato europeo)
        def safe_float(val):
            if pd.isna(val) or val is None:
                return None
            try:
                # Si es string, reemplazar coma por punto
                if isinstance(val, str):
                    val = val.replace(',', '.')
                return float(val)
            except (ValueError, TypeError):
                return None

        # Extraer datos relevantes
        for _, row in df_clean.iterrows():
            # Combinar date y time para el timestamp
            if 'date' in row and 'time' in row:
                # Formato: date=YYYYMMDD, time=HHMMSS.f
                date_str = str(row['date'])
                time_str = str(row['time'])

                # Parsear y convertir a objeto datetime para Plotly
                try:
                    # Extraer componentes de fecha
                    year = int(date_str[:4])
                    month = int(date_str[4:6])
                    day = int(date_str[6:8])

                    # Time puede tener formato HHMMSS.f o HH:MM:SS
                    if ':' in time_str:
                        time_parts = time_str.split(':')
                        hour = int(time_parts[0])
                        minute = int(time_parts[1])
                        second = int(float(time_parts[2])) if len(time_parts) > 2 else 0
                    else:
                        hour = int(time_str[:2]) if len(time_str) >= 2 else 0
                        minute = int(time_str[2:4]) if len(time_str) >= 4 else 0
                        second = int(time_str[4:6]) if len(time_str) >= 6 else 0

                    # Crear objeto datetime
                    timestamp_obj = datetime(year, month, day, hour, minute, second)
                except:
                    timestamp_obj = datetime.now()

            elif 'time' in row:
                try:
                    timestamp_obj = datetime.strptime(str(row['time']), "%Y%m%d %H%M%S.%f")
                except:
                    timestamp_obj = datetime.now()
            else:
                timestamp_obj = datetime.now()

            self.data_buffer['timestamp'].append(timestamp_obj)
            self.data_buffer['close'].append(safe_float(row.get('last', None)))
            self.data_buffer['volume'].append(safe_float(row.get('volume', 1)))
            self.data_buffer['color'].append(row.get('color', None))

        # Aplicar ventana deslizante (solo últimos MAX_POINTS)
        if len(self.data_buffer['timestamp']) > self.max_points:
            for key in self.data_buffer:
                self.data_buffer[key] = self.data_buffer[key][-self.max_points:]

        # Calcular EMA (span=20 por defecto)
        close_series = pd.Series([c for c in self.data_buffer['close'] if c is not None])
        if len(close_series) > 0:
            ema_series = close_series.ewm(span=20, adjust=False).mean()
            ema_values = ema_series.tolist()
        else:
            ema_values = []

        # Normalizar volúmenes para tamaño de puntos (rango 4-20)
        volumes = [v if v is not None else 1 for v in self.data_buffer['volume']]
        if len(volumes) > 0 and max(volumes) > 0:
            min_vol = min(volumes)
            max_vol = max(volumes)
            if max_vol > min_vol:
                sizes = [4 + (v - min_vol) / (max_vol - min_vol) * 16 for v in volumes]
            else:
                sizes = [10] * len(volumes)
        else:
            sizes = [10] * len(volumes)

        # Calcular opacidades (inversamente proporcional al volumen: más volumen = más transparente)
        if len(volumes) > 0 and max(volumes) > 0:
            min_vol = min(volumes)
            max_vol = max(volumes)
            if max_vol > min_vol:
                # Rango de opacidad: 0.3 (max vol) a 1.0 (min vol)
                opacities = [1.0 - (v - min_vol) / (max_vol - min_vol) * 0.7 for v in volumes]
            else:
                opacities = [0.7] * len(volumes)
        else:
            opacities = [0.7] * len(volumes)

        # Convertir colores según columna 'color'
        colors = []
        for c in self.data_buffer['color']:
            if pd.isna(c) or c is None:
                colors.append('gray')
            elif str(c).lower() == 'g':
                colors.append('green')
            elif str(c).lower() == 'o':
                colors.append('red')
            else:
                colors.append('gray')

        # Actualizar traza 0 (scatter con puntos)
        self.fig.data[0].x = self.data_buffer['timestamp']
        self.fig.data[0].y = self.data_buffer['close']
        self.fig.data[0].marker.size = sizes
        self.fig.data[0].marker.color = colors
        self.fig.data[0].marker.opacity = opacities
        self.fig.data[0].text = [f"{v}" for v in volumes]

        # Actualizar traza 1 (EMA)
        # Ajustar x para que coincida con los valores no-None de close
        valid_indices = [i for i, c in enumerate(self.data_buffer['close']) if c is not None]
        ema_timestamps = [self.data_buffer['timestamp'][i] for i in valid_indices]
        self.fig.data[1].x = ema_timestamps
        self.fig.data[1].y = ema_values

        # Ajustar rango del eje X para ventana deslizante temporal
        if len(self.data_buffer['timestamp']) > 0:
            from datetime import timedelta

            # Obtener el último timestamp real de los datos
            last_timestamp = self.data_buffer['timestamp'][-1]
            first_timestamp = self.data_buffer['timestamp'][0]

            # Calcular cuánto tiempo de historia tenemos
            time_span = (last_timestamp - first_timestamp).total_seconds()

            # Si tenemos menos historia que VISIBLE_TIME_WINDOW, mostrar desde el inicio
            if time_span < VISIBLE_TIME_WINDOW:
                # Mostrar desde el primer dato con padding a la derecha
                time_window_start = first_timestamp
                time_window_end = last_timestamp + timedelta(seconds=PADDING_RIGHT_SECONDS)
            else:
                # Ventana deslizante: mostrar últimos VISIBLE_TIME_WINDOW segundos
                time_window_start = last_timestamp - timedelta(seconds=VISIBLE_TIME_WINDOW)
                time_window_end = last_timestamp + timedelta(seconds=PADDING_RIGHT_SECONDS)

            # Actualizar el rango del eje X
            self.fig.update_xaxes(range=[time_window_start, time_window_end])

        # Guardar HTML actualizado con auto-refresh
        html_string = self.fig.to_html(include_plotlyjs='cdn')
        html_with_refresh = html_string.replace(
            '<head>',
            '<head><meta http-equiv="refresh" content="2">'
        )

        with open(self.html_file, 'w', encoding='utf-8') as f:
            f.write(html_with_refresh)

# FIN BLOQUE OPCIONAL: GRÁFICO DINÁMICO
# ============================================================


def find_latest_file(base_dir, file_type):
    """
    Encuentra el archivo más reciente del tipo especificado.
    Busca cualquier archivo CSV que contenga el tipo especificado.

    Args:
        base_dir: Directorio base
        file_type: "TS" o "Ticks"

    Returns:
        Path del archivo más reciente o None
    """
    # Buscar todos los archivos CSV en el directorio
    all_csv_files = list(base_dir.glob("*.csv"))

    if not all_csv_files:
        return None

    # Filtrar por tipo (case-insensitive)
    type_pattern = f"_{file_type}".lower()
    matching_files = [f for f in all_csv_files if type_pattern in f.name.lower()]

    if not matching_files:
        # Si no hay matches con patrón específico, buscar cualquier CSV
        print(f"[WARN] No se encontraron archivos con patrón '*_{file_type}.csv'")
        print(f"[INFO] Buscando el CSV más reciente en la carpeta...")
        matching_files = all_csv_files

    # Ordenar por fecha de modificación (más reciente primero)
    latest = max(matching_files, key=lambda f: f.stat().st_mtime)

    return latest


def get_file_line_count(file_path):
    """
    Cuenta el número de líneas en el archivo de forma eficiente.

    Args:
        file_path: Path al archivo

    Returns:
        int: Número de líneas
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return sum(1 for _ in f)
    except Exception as e:
        print(f"[ERROR] No se pudo leer el archivo: {e}")
        return 0


def read_new_rows(file_path, last_line_count):
    """
    Lee solo las nuevas filas añadidas al archivo.

    Args:
        file_path: Path al archivo
        last_line_count: Número de líneas en la lectura anterior

    Returns:
        tuple: (DataFrame con nuevas filas, nuevo conteo de líneas)
    """
    try:
        # Leer archivo completo
        df = pd.read_csv(file_path, sep=';', engine='python')
        current_line_count = len(df) + 1  # +1 por el header

        # Si hay nuevas filas
        if current_line_count > last_line_count:
            # Calcular cuántas filas nuevas hay
            new_rows_count = current_line_count - last_line_count

            # Extraer solo las nuevas filas
            new_rows = df.tail(new_rows_count)

            return new_rows, current_line_count
        else:
            return None, current_line_count

    except Exception as e:
        print(f"[ERROR] Error al leer nuevas filas: {e}")
        return None, last_line_count


def clean_and_transform_data(df_raw):
    """
    Limpia y transforma los datos:
    1. Filtra rows con type = 'DailyVolume' (no interesan)
    2. Extrae date de time (YYYYMMDD)
    3. Deja solo hora en time (HHMMSS.f)
    4. Elimina system_time
    5. Reordena columnas

    Args:
        df_raw: DataFrame con datos raw

    Returns:
        DataFrame limpio
    """
    df_clean = df_raw.copy()

    # Filtrar filas con type = 'DailyVolume' (no interesan)
    if 'type' in df_clean.columns:
        df_clean = df_clean[df_clean['type'] != 'DailyVolume']

    # Si después del filtro no quedan filas, retornar DataFrame vacío
    if len(df_clean) == 0:
        return df_clean

    # Procesar columna 'time' si existe
    if 'time' in df_clean.columns:
        # Convertir a string para manipular
        df_clean['time'] = df_clean['time'].astype(str)

        # Extraer date (primeros 8 caracteres: YYYYMMDD)
        df_clean['date'] = df_clean['time'].str[:8]

        # Extraer time (después de YYYYMMDD: HHMMSS.f)
        df_clean['time'] = df_clean['time'].str[8:]

    # Eliminar system_time si existe
    if 'system_time' in df_clean.columns:
        df_clean = df_clean.drop(columns=['system_time'])

    # Reordenar columnas: date, time, bid, ask, last, type, volume, color
    # Ya tenemos date y time separados de la extracción anterior
    desired_order = ['date', 'time', 'bid', 'ask', 'last', 'type', 'volume', 'color']
    available_cols = [col for col in desired_order if col in df_clean.columns]

    # Si no hay columnas con esos nombres, usar todas las disponibles
    if not available_cols:
        available_cols = df_clean.columns.tolist()

    return df_clean[available_cols]


def format_row_output(df_clean):
    """
    Formatea nuevas filas en formato DataFrame para mostrar en el terminal.

    Args:
        df_clean: DataFrame con las nuevas filas limpias

    Returns:
        str: Filas formateadas como tabla
    """
    # Obtener timestamp actual
    now = datetime.now().strftime("%H:%M:%S.%f")[:-3]

    # Convertir a string con formato tabla
    table_str = df_clean.to_string(index=False)

    return f"[{now}] NEW ROWS:\n{table_str}\n"


def save_to_csv(df_clean, file_type):
    """
    Guarda o append datos limpios a CSV en data/monitor_ninja/

    Args:
        df_clean: DataFrame limpio
        file_type: "TS" o "Ticks"
    """
    # Nombre del archivo de salida
    today = datetime.now().strftime("%Y%m%d")
    output_file = OUTPUT_DIR / f"monitor_{file_type}_{today}.csv"

    # Si el archivo ya existe, hacer append; si no, crear con header
    if output_file.exists():
        df_clean.to_csv(output_file, mode='a', header=False, index=False, sep=';', decimal=',')
    else:
        df_clean.to_csv(output_file, mode='w', header=True, index=False, sep=';', decimal=',')

    return output_file


def monitor_file(file_path, file_type):
    """
    Monitorea un archivo CSV en tiempo real.

    Args:
        file_path: Path al archivo a monitorear
        file_type: "TS" o "Ticks"
    """
    print("="*80)
    print(f"MONITOR EN TIEMPO REAL - {file_type}")
    print("="*80)
    print(f"Archivo: {file_path.name}")
    print(f"Ubicación: {file_path.parent}")
    print(f"Output CSV: {OUTPUT_DIR}")
    print(f"Intervalo de chequeo: {CHECK_INTERVAL}s")

    # ============================================================
    # BLOQUE OPCIONAL: Inicializar gráfico dinámico si está habilitado
    # ============================================================
    chart = None
    if ENABLE_DYNAMIC_CHART:
        if PLOTLY_AVAILABLE:
            try:
                chart = DynamicChart(max_points=MAX_CHART_POINTS)
                print(f"[CHART] Gráfico dinámico ACTIVADO (ventana de {MAX_CHART_POINTS} puntos)")

                # Cargar datos iniciales (últimas 20 filas del CSV)
                try:
                    df_initial = pd.read_csv(file_path, sep=';', engine='python')
                    if len(df_initial) > 0:
                        # Tomar últimas 20 filas
                        df_initial_tail = df_initial.tail(20)
                        df_initial_clean = clean_and_transform_data(df_initial_tail)
                        if len(df_initial_clean) > 0:
                            chart.update(df_initial_clean)
                            print(f"[CHART] Cargadas {len(df_initial_clean)} filas iniciales al gráfico")
                except Exception as e:
                    print(f"[WARN] No se pudieron cargar datos iniciales al gráfico: {e}")

            except Exception as e:
                print(f"[WARN] No se pudo inicializar el gráfico: {e}")
                print("[INFO] Continuando solo con terminal output...")
        else:
            print("[WARN] Plotly no disponible. Instalar con: pip install plotly")
            print("[INFO] Continuando solo con terminal output...")
    # FIN BLOQUE OPCIONAL
    # ============================================================

    print()
    print("Esperando nuevas filas... (Ctrl+C para detener)")
    print("="*80)
    print()

    # Obtener conteo inicial de líneas
    last_line_count = get_file_line_count(file_path)
    print(f"[INFO] Líneas iniciales en el archivo: {last_line_count - 1}")  # -1 por el header
    print()

    try:
        while True:
            # Leer nuevas filas si las hay
            new_rows, last_line_count = read_new_rows(file_path, last_line_count)

            if new_rows is not None and len(new_rows) > 0:
                # Limpiar y transformar datos
                df_clean = clean_and_transform_data(new_rows)

                # Solo procesar si quedan filas después del filtro
                if len(df_clean) > 0:
                    # Mostrar todas las nuevas filas en formato tabla
                    print(format_row_output(df_clean))

                    # Guardar a CSV
                    output_file = save_to_csv(df_clean, file_type)
                    print(f"[SAVED] {len(df_clean)} rows -> {output_file.name}")
                    print()

                    # ============================================================
                    # BLOQUE OPCIONAL: Actualizar gráfico dinámico
                    # ============================================================
                    if chart is not None:
                        try:
                            chart.update(df_clean)
                        except Exception as e:
                            print(f"[WARN] Error actualizando gráfico: {e}")
                    # FIN BLOQUE OPCIONAL
                    # ============================================================

            # Esperar antes del siguiente chequeo
            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        print()
        print("="*80)
        print("[INFO] Monitor detenido por el usuario")
        print("="*80)


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    # Verificar que el directorio existe
    if not BASE_DIR.exists():
        print(f"[ERROR] No existe el directorio: {BASE_DIR}")
        exit(1)

    # Buscar archivo más reciente
    print(f"[INFO] Buscando archivo {FILE_TYPE} más reciente en: {BASE_DIR}")
    file_path = find_latest_file(BASE_DIR, FILE_TYPE)

    if not file_path:
        print(f"[ERROR] No se encontraron archivos *_{FILE_TYPE}.csv en {BASE_DIR}")
        exit(1)

    print(f"[OK] Archivo encontrado: {file_path.name}")
    print()

    # Iniciar monitoreo
    monitor_file(file_path, FILE_TYPE)
