import socket
import csv
from datetime import datetime
from pathlib import Path

HOST = '0.0.0.0'  # Escucha en todas las interfaces
PORT = 5559  # CAMBIO: Flask usa 5555, este usa 5556

# CSV de salida
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "monitor_ninja"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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
