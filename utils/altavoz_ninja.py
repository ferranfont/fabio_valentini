import socket
import csv
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import threading
import time

# Importaciones para gráfico dinámico
try:
    import plotly.graph_objects as go
    import webbrowser
    import tempfile
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

HOST = '0.0.0.0'  # Escucha en todas las interfaces
PORT = 5559  # CAMBIO: Flask usa 5555, este usa 5556

# CSV de salida
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "monitor_ninja"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# CONFIGURACIÓN GRÁFICO DINÁMICO
# ============================================================
ENABLE_CHART = True                  # True para activar gráfico
MAX_CHART_POINTS = 5000              # Máximo de puntos en memoria
VISIBLE_TIME_WINDOW = 120            # Segundos visibles (ventana deslizante)
PADDING_RIGHT_SECONDS = 5            # Padding derecho en segundos
CHART_UPDATE_INTERVAL = 2.0          # Actualizar HTML cada N segundos

SECTION_LAYOUTS = {
    'TS': {
        'title': "[TIME & SALES]",
        'columns': f"{'date':<10} {'time':<12} {'bid':<10} {'ask':<10} {'last':<10} {'type':<6} {'volume':<8}"
    },
    'OB': {
        'title': "[ORDER BOOK]",
        'columns': f"{'time':<12} {'close':<10} {'price':<10} {'pos':<8} {'volume':<8}"
    }
}

TICK_HEADERS = ['date', 'time', 'bid', 'ask', 'last', 'volume']

# ============================================================
# CLASE GRÁFICO DINÁMICO
# ============================================================
class DynamicChart:
    """Gestor de gráfico dinámico con ventana temporal deslizante."""

    def __init__(self, max_points=5000):
        """Inicializa el gráfico dinámico."""
        if not PLOTLY_AVAILABLE:
            raise ImportError("Plotly no disponible. Instalar: pip install plotly")

        self.max_points = max_points
        self.data_buffer = {
            'timestamp': [],
            'close': [],
            'volume': [],
            'type': []  # 'Ask' o 'Bid'
        }
        self.fig = None
        self.html_file = None
        self.last_update = 0
        self._create_figure()

    def _create_figure(self):
        """Crea la figura de Plotly con precio + EMA."""
        self.fig = go.Figure()

        # Traza 1: Scatter con volumen y color
        self.fig.add_trace(go.Scatter(
            x=[],
            y=[],
            mode='markers',
            name='Close',
            marker=dict(
                size=[],
                color=[],
                opacity=[],
                line=dict(width=0)
            ),
            hovertemplate='<b>Time:</b> %{x}<br><b>Price:</b> %{y}<br><b>Vol:</b> %{text}<extra></extra>',
            text=[]
        ))

        # Traza 2: Media Exponencial (EMA)
        self.fig.add_trace(go.Scatter(
            x=[],
            y=[],
            mode='lines',
            name='EMA(20)',
            line=dict(color='blue', width=1.5)
        ))

        # Layout
        self.fig.update_layout(
            title='NinjaTrader Real-Time Monitor - Ventana Deslizante (120s)',
            xaxis_title='Time',
            yaxis_title='Price',
            hovermode='closest',
            height=700,
            template='plotly_white',
            showlegend=False,
            xaxis=dict(
                showgrid=False,
                tickformat='%H:%M',
                nticks=12
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='lightgray'
            )
        )

        # Archivo HTML temporal
        temp_dir = tempfile.gettempdir()
        self.html_file = Path(temp_dir) / "ninja_monitor_realtime.html"
        self._save_html()
        webbrowser.open(f'file:///{self.html_file}')
        print(f"[CHART] Gráfico abierto: {self.html_file}")

    def _save_html(self):
        """Guarda el HTML con auto-refresh."""
        html_string = self.fig.to_html(include_plotlyjs='cdn')
        html_with_refresh = html_string.replace(
            '<head>',
            '<head><meta http-equiv="refresh" content="2">'
        )
        with open(self.html_file, 'w', encoding='utf-8') as f:
            f.write(html_with_refresh)

    def add_point(self, timestamp_obj, last_price, volume, trade_type):
        """
        Añade un punto al buffer.

        Args:
            timestamp_obj: datetime object
            last_price: float
            volume: float
            trade_type: 'Ask' o 'Bid'
        """
        self.data_buffer['timestamp'].append(timestamp_obj)
        self.data_buffer['close'].append(last_price)
        self.data_buffer['volume'].append(volume)
        self.data_buffer['type'].append(trade_type)

        # Limitar buffer a MAX_CHART_POINTS
        if len(self.data_buffer['timestamp']) > self.max_points:
            for key in self.data_buffer:
                self.data_buffer[key] = self.data_buffer[key][-self.max_points:]

    def should_update(self):
        """Verifica si ha pasado suficiente tiempo para actualizar."""
        current_time = time.time()
        if current_time - self.last_update >= CHART_UPDATE_INTERVAL:
            self.last_update = current_time
            return True
        return False

    def update_chart(self):
        """Actualiza el gráfico completo."""
        if len(self.data_buffer['timestamp']) == 0:
            return

        # Calcular EMA (span=20)
        close_series = pd.Series(self.data_buffer['close'])
        ema_series = close_series.ewm(span=20, adjust=False).mean()
        ema_values = ema_series.tolist()

        # Normalizar volúmenes para tamaño (4-20 px)
        volumes = self.data_buffer['volume']
        min_vol = min(volumes)
        max_vol = max(volumes)

        if max_vol > min_vol:
            sizes = [4 + (v - min_vol) / (max_vol - min_vol) * 16 for v in volumes]
        else:
            sizes = [10] * len(volumes)

        # Opacidades inversas al volumen
        if max_vol > min_vol:
            opacities = [1.0 - (v - min_vol) / (max_vol - min_vol) * 0.7 for v in volumes]
        else:
            opacities = [0.7] * len(volumes)

        # Colores según tipo: Ask=green, Bid=red
        colors = ['green' if t == 'Ask' else 'red' for t in self.data_buffer['type']]

        # Actualizar traza 0 (scatter)
        self.fig.data[0].x = self.data_buffer['timestamp']
        self.fig.data[0].y = self.data_buffer['close']
        self.fig.data[0].marker.size = sizes
        self.fig.data[0].marker.color = colors
        self.fig.data[0].marker.opacity = opacities
        self.fig.data[0].text = [f"{v:.1f}" for v in volumes]

        # Actualizar traza 1 (EMA)
        self.fig.data[1].x = self.data_buffer['timestamp']
        self.fig.data[1].y = ema_values

        # Ajustar ventana temporal
        self._update_time_window()

        # Guardar HTML
        self._save_html()

    def _update_time_window(self):
        """Ajusta ventana temporal visible (deslizante)."""
        if len(self.data_buffer['timestamp']) == 0:
            return

        first_timestamp = self.data_buffer['timestamp'][0]
        last_timestamp = self.data_buffer['timestamp'][-1]
        time_span = (last_timestamp - first_timestamp).total_seconds()

        # Fase inicial: mostrar desde la izquierda
        if time_span < VISIBLE_TIME_WINDOW:
            time_window_start = first_timestamp
            time_window_end = last_timestamp + timedelta(seconds=PADDING_RIGHT_SECONDS)
        else:
            # Fase continua: ventana deslizante
            time_window_start = last_timestamp - timedelta(seconds=VISIBLE_TIME_WINDOW)
            time_window_end = last_timestamp + timedelta(seconds=PADDING_RIGHT_SECONDS)

        self.fig.update_xaxes(range=[time_window_start, time_window_end])


# ============================================================
# CLASE RECEPTOR NINJATRADER
# ============================================================
class NinjaTraderReceiver:
    def __init__(self, host=HOST, port=PORT):
        self.host = host
        self.port = port
        self.stats = {
            'ts_count': 0,
            'tick_count': 0,
            'ob_count': 0,
            'headers': []
        }
        self.current_section = None

        # Archivo CSV para T&S
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.csv_file = OUTPUT_DIR / f"monitor_TS_{timestamp}.csv"
        self.tick_csv_file = OUTPUT_DIR / f"monitor_TICK_{timestamp}.csv"
        self.csv_writer = None
        self.csv_handle = None
        self.tick_csv_writer = None
        self.tick_csv_handle = None

        # Gráfico dinámico
        self.chart = None
        if ENABLE_CHART and PLOTLY_AVAILABLE:
            try:
                self.chart = DynamicChart(max_points=MAX_CHART_POINTS)
                print(f"[CHART] Gráfico dinámico activado (ventana {VISIBLE_TIME_WINDOW}s)")
            except Exception as e:
                print(f"[WARN] No se pudo inicializar gráfico: {e}")
        elif ENABLE_CHART and not PLOTLY_AVAILABLE:
            print("[WARN] Plotly no disponible. Instalar: pip install plotly")
    
    def iniciar_csv(self):
        """Inicializa el archivo CSV con headers"""
        self.csv_handle = open(self.csv_file, 'w', newline='', encoding='utf-8')
        self.csv_writer = csv.writer(self.csv_handle, delimiter=';')
        # Header: date; time; bid; ask; last; type; volume (SIN color)
        self.csv_writer.writerow(['date', 'time', 'bid', 'ask', 'last', 'type', 'volume'])
        self.csv_handle.flush()
        print(f"[CSV] Creado: {self.csv_file.name}\n")

        # Archivo para Ticks
        self.tick_csv_handle = open(self.tick_csv_file, 'w', newline='', encoding='utf-8')
        self.tick_csv_writer = csv.writer(self.tick_csv_handle, delimiter=';')
        self.tick_csv_writer.writerow(TICK_HEADERS)
        self.tick_csv_handle.flush()
        print(f"[CSV] Creado: {self.tick_csv_file.name}\n")

    def cerrar_csv(self):
        """Cierra el archivo CSV"""
        if self.csv_handle:
            self.csv_handle.close()
            print(f"[CSV] Guardado: {self.csv_file}")
        if self.tick_csv_handle:
            self.tick_csv_handle.close()
            print(f"[CSV] Guardado: {self.tick_csv_file}")
        self.current_section = None

    def _ensure_section_header(self, section):
        """Muestra encabezados legibles cada vez que cambia la sección"""
        layout = SECTION_LAYOUTS.get(section)
        if not layout:
            return
        if self.current_section != section:
            print()
            print(layout['title'])
            print(layout['columns'])
            print("-" * len(layout['columns']))
            self.current_section = section

    def _split_timestamp(self, time_str):
        """Devuelve (date, time) a partir de una cadena yyyyMMddHHmmss.fff"""
        if not time_str:
            now = datetime.now()
            return now.strftime('%Y%m%d'), now.strftime('%H%M%S.%f')[:-3]

        cleaned = time_str.strip()
        if len(cleaned) >= 14:
            date_part = cleaned[:8]
            time_part = cleaned[8:14]
            if '.' in cleaned:
                millis = cleaned.split('.', 1)[1]
                time_part = f"{time_part}.{millis}"
            return date_part, time_part

        now = datetime.now()
        return now.strftime('%Y%m%d'), cleaned or now.strftime('%H%M%S')

    def parsear_linea(self, linea):
        """Parsea y clasifica las líneas según su tipo"""
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]

        if linea.startswith('HEADER_'):
            # Headers de inicio
            self.stats['headers'].append(linea)
            print(f"[{timestamp}] [HEADER] {linea}")
            return

        if linea.startswith('TS:'):
            # Time & Sales: TS:system_time;time;type;last;ask;bid;volume;color
            self.stats['ts_count'] += 1
            datos = linea[3:].split(';')
            if len(datos) >= 8:
                # Extraer: system_time, time, type, last, ask, bid, volume, color
                # time viene como: 20251107004134.672
                time_str = datos[1]  # yyyyMMddHHmmss.fff
                date_part, time_part = self._split_timestamp(time_str)

                # Filtrar valores invalidos (precios negativos o cero)
                try:
                    last_val = float(datos[3])
                    bid_val = float(datos[5])
                    ask_val = float(datos[4])

                    # Ignorar si los valores son invalidos (negativos o cero)
                    if last_val <= 0 or bid_val <= 0 or ask_val <= 0:
                        return  # No escribir al CSV ni imprimir
                except (ValueError, IndexError):
                    return  # Datos malformados, ignorar

                last_str = f"{last_val:.2f}"
                bid_str = f"{bid_val:.2f}"
                ask_str = f"{ask_val:.2f}"

                # Determinar type basado en color: green -> Ask, otro -> Bid
                color = datos[7].lower()
                type_value = 'Ask' if color == 'g' or color == 'green' else 'Bid'

                # Escribir al CSV: date; time; bid; ask; last; type; volume (SIN color)
                row = [
                    date_part,           # date
                    time_part,           # time
                    bid_str,             # bid
                    ask_str,             # ask
                    last_str,            # last
                    type_value,          # type (Ask/Bid basado en color)
                    datos[6]             # volume
                ]

                self.csv_writer.writerow(row)
                self.csv_handle.flush()  # Flush inmediato para lectura en tiempo real

                # Imprimir en formato DataFrame
                self._ensure_section_header('TS')
                print(f"{date_part:<10} {time_part:<12} {bid_str:<10} {ask_str:<10} {last_str:<10} {type_value:<6} {datos[6]:<8}")

                # Actualizar gráfico dinámico
                if self.chart is not None:
                    # Construir timestamp completo
                    try:
                        year = int(date_part[:4])
                        month = int(date_part[4:6])
                        day = int(date_part[6:8])

                        # Parsear time_part (puede ser HHMMSS.fff)
                        if '.' in time_part:
                            time_base, millis = time_part.split('.')
                        else:
                            time_base = time_part
                            millis = '0'

                        hour = int(time_base[:2]) if len(time_base) >= 2 else 0
                        minute = int(time_base[2:4]) if len(time_base) >= 4 else 0
                        second = int(time_base[4:6]) if len(time_base) >= 6 else 0

                        timestamp_obj = datetime(year, month, day, hour, minute, second)

                        # Añadir punto al gráfico
                        volume_val = float(datos[6]) if datos[6] else 1.0
                        self.chart.add_point(timestamp_obj, last_val, volume_val, type_value)

                        # Actualizar gráfico si ha pasado el intervalo
                        if self.chart.should_update():
                            self.chart.update_chart()
                    except Exception as e:
                        pass  # Silenciar errores de gráfico para no interrumpir recepción
            else:
                print(f"[{timestamp}] [WARN] T&S incompleto: {linea}")
            return
        
        if linea.startswith('TICK:'):
            # Ticks: TICK:system_time;time;last;ask;bid;volume
            self.stats['tick_count'] += 1
            datos = linea[5:].split(';')
            if len(datos) >= 6:
                date_part, time_part = self._split_timestamp(datos[1])
                try:
                    bid_str = f"{float(datos[4]):.2f}"
                    ask_str = f"{float(datos[3]):.2f}"
                    last_str = f"{float(datos[2]):.2f}"
                except ValueError:
                    return
                if self.tick_csv_writer:
                    self.tick_csv_writer.writerow([
                        date_part,
                        time_part,
                        bid_str,   # bid
                        ask_str,   # ask
                        last_str,  # last
                        datos[5]   # volume
                    ])
                    self.tick_csv_handle.flush()
            else:
                print(f"[{timestamp}] [WARN] TICK incompleto: {linea}")
            return

        if linea.startswith('OB:'):
            # Order Book: OB:time;close;priceBook;positionBook;volumeBook
            self.stats['ob_count'] += 1
            datos = linea[3:].split(';')
            if len(datos) >= 5:
                self._ensure_section_header('OB')
                time_val = datos[0] if datos[0] else timestamp
                print(f"{time_val:<12} {datos[1]:<10} {datos[2]:<10} {datos[3]:<8} {datos[4]:<8}")
            else:
                print(f"[{timestamp}] [WARN] OB incompleto: {linea}")
            return

        # Línea no reconocida
        print(f"[{timestamp}] [?] Desconocido: {linea}")
    
    def mostrar_estadisticas(self):
        """Muestra estadísticas de datos recibidos"""
        print("\n" + "="*60)
        print("[ESTADISTICAS]")
        print("="*60)
        print(f"Time & Sales (T&S): {self.stats['ts_count']:,}")
        print(f"Ticks:              {self.stats['tick_count']:,}")
        print(f"Order Book:         {self.stats['ob_count']:,}")
        print(f"Total:              {sum([self.stats['ts_count'], self.stats['tick_count'], self.stats['ob_count']]):,}")
        print("="*60 + "\n")
    
    def iniciar(self):
        """Inicia el servidor receptor"""
        print(f"[INIT] Iniciando receptor en {self.host}:{self.port}")

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as servidor:
            servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            servidor.bind((self.host, self.port))
            servidor.listen()
            print(f"[OK] Servidor escuchando... Esperando conexion de NinjaTrader")

            while True:
                try:
                    conexion, direccion = servidor.accept()
                    print(f"\n[CONNECTED] Conectado desde {direccion}")
                    print("Presiona Ctrl+C para ver estadisticas y detener\n")

                    # Iniciar CSV cuando se conecta
                    self.iniciar_csv()

                    with conexion:
                        buffer = ""
                        while True:
                            try:
                                data = conexion.recv(4096)
                                if not data:
                                    print("\n[DISCONNECT] Conexion cerrada por el cliente")
                                    self.cerrar_csv()
                                    self.mostrar_estadisticas()
                                    break
                                
                                buffer += data.decode('utf-8')
                                
                                # Procesar líneas completas
                                while '\n' in buffer:
                                    linea, buffer = buffer.split('\n', 1)
                                    if linea.strip():  # Ignorar líneas vacías
                                        self.parsear_linea(linea.strip())
                            
                            except UnicodeDecodeError as e:
                                print(f"[WARN] Error de decodificacion UTF-8: {e}")
                                buffer = ""  # Reset buffer en caso de error
                            except Exception as e:
                                print(f"[ERROR] Error procesando datos: {e}")
                                break

                    # Cerrar CSV al salir del with conexion
                    self.cerrar_csv()

                except KeyboardInterrupt:
                    print("\n\n[STOP] Servidor detenido por el usuario")
                    self.cerrar_csv()
                    self.mostrar_estadisticas()
                    break
                except Exception as e:
                    print(f"[ERROR] Error en servidor: {e}")
                    self.cerrar_csv()
                    self.mostrar_estadisticas()

if __name__ == "__main__":
    receptor = NinjaTraderReceiver()
    receptor.iniciar()
