"""
NinjaTrader Tick Receiver - LIVE VERSION WITH BIG VOLUME DETECTION
Connects to NinjaTrader:
  - Port 5555: Receives Ticks (Data Feed)
  - Port 5556: Sends Visual Signals (Indicator)
  - Port 5557: Sends Execution Commands (Strategy)
"""
import socket
import threading
import time
from datetime import datetime, timedelta
from collections import defaultdict
import sys
import os

# Añadir el directorio actual al path para asegurar que encuentra el config
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# Import configuration from config_trinchera_live
try:
    from config_trinchera_live import (
        BIG_VOLUME_TRIGGER,
        BIG_VOLUME_TIMEOUT,
        MEAN_REVERS_EXPAND,
        MEAN_REVERSE_TIMEOUT_ORDER,
        FILTER_USE_GRID,
        GRID_MEAN_REVERS_EXPAND,
        TP_POINTS,
        SL_POINTS,
        BOTH_SIDES_MEAN_REVERSE,
        HOST,
        PORT_TICK_RECEIVER,
        PORT_SIGNAL_SENDER,
        PORT_ORDER_EXECUTION
    )
    print(f"[CONFIG] Loaded configuration from config_trinchera_live.py")
except ImportError:
    print("[WARNING] Could not import config_trinchera_live.py, using defaults")
    BIG_VOLUME_TRIGGER = 200
    BIG_VOLUME_TIMEOUT = 10
    MEAN_REVERS_EXPAND = 14
    MEAN_REVERSE_TIMEOUT_ORDER = 3
    FILTER_USE_GRID = False
    GRID_MEAN_REVERS_EXPAND = 5.0
    TP_POINTS = 5.0
    SL_POINTS = 9.0
    BOTH_SIDES_MEAN_REVERSE = False
    HOST = '127.0.0.1'
    PORT_TICK_RECEIVER = 5555
    PORT_SIGNAL_SENDER = 5556
    PORT_ORDER_EXECUTION = 5557
class OrderExecutionClient:
    """Handles sending order commands to the NinjaTrader Strategy"""
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.socket = None
        self.connected = False
        self.lock = threading.Lock()
    def connect(self, max_attempts=5):
        print(f"\n{'='*70}")
        print(f"CONNECTING TO ORDER EXECUTION SERVER (STRATEGY)")
        print(f"{'='*70}")
        print(f"Host: {self.host}")
        print(f"Port: {self.port}")
        
        for attempt in range(1, max_attempts + 1):
            try:
                print(f"[EXEC] Attempt {attempt}/{max_attempts}...", end=" ")
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(5)
                self.socket.connect((self.host, self.port))
                self.connected = True
                print("[OK]")
                print(f"[EXEC] Connected to NinjaTrader Strategy at {self.host}:{self.port}\n")
                return True
            except Exception as e:
                print(f"[ERROR]: {e}")
                if attempt < max_attempts:
                    time.sleep(2)
        
        print(f"[EXEC] Failed to connect to Strategy on port {self.port}")
        return False
    def send_execution_command(self, sell_price, buy_price, timeout_mins, tp_points, sl_points, both_sides):
        """
        Sends a composite execution command.
        Format: EXECUTE;SELL_PRICE;BUY_PRICE;TIMEOUT;TP;SL;BOTH_SIDES
        """
        if not self.connected or not self.socket:
            print("[EXEC] Cannot send order: Not connected")
            return False
        try:
            # Format using invariant culture (dot decimal)
            # both_sides is sent as "1" (True) or "0" (False)
            both_sides_flag = "1" if both_sides else "0"
            
            cmd = f"EXECUTE;{sell_price:.2f};{buy_price:.2f};{timeout_mins};{tp_points:.2f};{sl_points:.2f};{both_sides_flag}\n"
            
            with self.lock:
                self.socket.sendall(cmd.encode('utf-8'))
                print(f"[EXEC] >> SENT: {cmd.strip()}")
            return True
        except Exception as e:
            print(f"[EXEC] Error sending order: {e}")
            self.connected = False
            return False
    def disconnect(self):
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
            self.connected = False
class TickReceiverClientLive:
    def __init__(self, host='127.0.0.1', tick_port=5555, signal_port=5556, exec_port=5557,
                 aggregation_window_ms=500):
        """
        Initialize the live tick receiver with big volume detection and order execution
        Args:
            host: NinjaTrader server host (default: localhost)
            tick_port: Port to receive ticks from NinjaTrader (default: 5555)
            signal_port: Port to send signals to NinjaTrader (default: 5556)
            exec_port: Port to send orders to NinjaTrader Strategy (default: 5557)
            aggregation_window_ms: Time window in milliseconds to aggregate volume (default: 500ms)
        """
        self.host = host
        self.tick_port = tick_port
        self.signal_port = signal_port
        self.exec_port = exec_port
        self.aggregation_window_ms = aggregation_window_ms
        # Volume detection parameters from config
        self.big_volume_trigger = BIG_VOLUME_TRIGGER
        self.big_volume_timeout = BIG_VOLUME_TIMEOUT
        self.mean_revers_expand = MEAN_REVERS_EXPAND
        self.mean_reverse_timeout_order = MEAN_REVERSE_TIMEOUT_ORDER
        self.filter_use_grid = FILTER_USE_GRID
        self.grid_mean_revers_expand = GRID_MEAN_REVERS_EXPAND
        self.tp_points = TP_POINTS
        self.sl_points = SL_POINTS
        self.both_sides_mean_reverse = BOTH_SIDES_MEAN_REVERSE
        self.tick_count = 0
        self.running = False
        # Separate sockets for receiving and sending
        self.tick_socket = None
        self.signal_socket = None
        self.tick_connected = False
        self.signal_connected = False
        
        # Execution Client
        self.exec_client = OrderExecutionClient(self.host, self.exec_port)
        # Volume aggregation data
        self.current_window_start = None
        self.current_window_volume = 0
        self.current_window_bid = 0
        self.current_window_ask = 0
        self.current_window_close = 0.0
        self.current_window_ticks = 0
        # Statistics
        self.start_time = None
        self.last_tick_time = None
        self.signals_sent = 0
        self.big_volume_events = 0
        self.last_signal_time = None
    def connect_tick_receiver(self, max_attempts=10, retry_delay=2):
        """Connect to NinjaTrader tick server"""
        print(f"\n{'='*70}")
        print(f"CONNECTING TO TICK SERVER")
        print(f"{'='*70}")
        print(f"Host: {self.host}")
        print(f"Port: {self.tick_port}")
        print(f"{'='*70}\n")
        for attempt in range(1, max_attempts + 1):
            try:
                print(f"[TICK] Attempt {attempt}/{max_attempts}...", end=" ")
                self.tick_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.tick_socket.settimeout(5)
                self.tick_socket.connect((self.host, self.tick_port))
                self.tick_connected = True
                print("[OK]")
                print(f"[TICK] Connected to NinjaTrader tick server at {self.host}:{self.tick_port}\n")
                return True
            except Exception as e:
                print(f"[ERROR]: {e}")
                if self.tick_socket:
                    try:
                        self.tick_socket.close()
                    except:
                        pass
                    self.tick_socket = None
                if attempt < max_attempts:
                    print(f"[TICK] Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
        print(f"\n[ERROR] Failed to connect to tick server after {max_attempts} attempts")
        print("[ERROR] Make sure AAIndicatorTrinchera_Draw is running in NinjaTrader")
        return False
    def connect_signal_sender(self, max_attempts=10, retry_delay=2):
        """Connect to NinjaTrader signal server"""
        print(f"\n{'='*70}")
        print(f"CONNECTING TO SIGNAL SERVER")
        print(f"{'='*70}")
        print(f"Host: {self.host}")
        print(f"Port: {self.signal_port}")
        print(f"{'='*70}\n")
        for attempt in range(1, max_attempts + 1):
            try:
                print(f"[SIGNAL] Attempt {attempt}/{max_attempts}...", end=" ")
                self.signal_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.signal_socket.settimeout(5)
                self.signal_socket.connect((self.host, self.signal_port))
                self.signal_connected = True
                print("[OK]")
                print(f"[SIGNAL] Connected to NinjaTrader signal server at {self.host}:{self.signal_port}\n")
                return True
            except Exception as e:
                print(f"[ERROR]: {e}")
                if self.signal_socket:
                    try:
                        self.signal_socket.close()
                    except:
                        pass
                    self.signal_socket = None
                if attempt < max_attempts:
                    print(f"[SIGNAL] Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
        print(f"\n[ERROR] Failed to connect to signal server after {max_attempts} attempts")
        return False
    def disconnect(self):
        """Disconnect from servers"""
        self.running = False
        self.tick_connected = False
        self.signal_connected = False
        
        # Disconnect Execution Client
        self.exec_client.disconnect()
        if self.tick_socket:
            try:
                self.tick_socket.close()
            except:
                pass
            self.tick_socket = None
        if self.signal_socket:
            try:
                self.signal_socket.close()
            except:
                pass
            self.signal_socket = None
        print(f"\n[CONNECTION] Disconnected from all servers")
    def send_signal(self, signal_name="orange_dot"):
        """Send signal to NinjaTrader (info already printed in check_big_volume)"""
        try:
            # Format: just the signal name with newline (as expected by C# ReadLine())
            message = f"{signal_name}\n"
            if self.signal_connected and self.signal_socket:
                self.signal_socket.sendall(message.encode('utf-8'))
                self.signals_sent += 1
                self.last_signal_time = datetime.now()
                return True
            else:
                print(f"[WARNING] Cannot send signal - not connected to signal server")
                return False
        except Exception as e:
            print(f"[ERROR] Failed to send signal: {e}")
            self.signal_connected = False
            return False
    def send_signal_with_levels(self, signal_name, sell_level, buy_level, timeout_minutes, timestamp):
        """Send signal with price levels and timeout to NinjaTrader"""
        try:
            # Format: orange_dot;SELL_LEVEL;BUY_LEVEL;TIMEOUT_MINUTES;TIMESTAMP
            # Use InvariantCulture format (dot as decimal separator)
            timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            message = f"{signal_name};{sell_level:.2f};{buy_level:.2f};{timeout_minutes};{timestamp_str}\n"
            if self.signal_connected and self.signal_socket:
                self.signal_socket.sendall(message.encode('utf-8'))
                self.signals_sent += 1
                self.last_signal_time = datetime.now()
                return True
            else:
                print(f"[WARNING] Cannot send signal - not connected to signal server")
                return False
        except Exception as e:
            print(f"[ERROR] Failed to send signal: {e}")
            self.signal_connected = False
            return False
    def check_big_volume(self, timestamp, volume, bid_volume, ask_volume, close_price):
        """
        Check if current window has big volume and send signal if detected
        Args:
            timestamp: Current tick timestamp
            volume: Total volume in current window
            bid_volume: Bid volume in current window
            ask_volume: Ask volume in current window
            close_price: Close price of current window
        """
        if volume > self.big_volume_trigger:
            self.big_volume_events += 1
            # Calculate mean reversion levels
            if self.filter_use_grid:
                sell_limit_level = close_price + self.mean_revers_expand + self.grid_mean_revers_expand
                buy_limit_level = close_price - self.mean_revers_expand - self.grid_mean_revers_expand
                expand_total = self.mean_revers_expand + self.grid_mean_revers_expand
            else:
                sell_limit_level = close_price + self.mean_revers_expand
                buy_limit_level = close_price - self.mean_revers_expand
                expand_total = self.mean_revers_expand
            # Print compact horizontal alert with emoji icons
            grid_text = " | GRID" if self.filter_use_grid else ""
            print(f"\n{'='*100}")
            print(f"\U0001F6A8 ALERT #{self.big_volume_events} | "
                  f"\U0001F55B {timestamp.strftime('%H:%M:%S.%f')[:-3]} | "
                  f"\U0001F4CA {close_price:.2f} | "
                  f"\U0001F4C8 VOL {volume}/{self.big_volume_trigger} (Bid:{bid_volume} Ask:{ask_volume})")
            print(f"\U0001F4CB ORDERS: \U0001F534 SELL:{sell_limit_level:.2f} (+{expand_total:.1f}) | "
                  f"\U0001F7E2 BUY:{buy_limit_level:.2f} (-{expand_total:.1f}) | "
                  f"\u23F3 {self.mean_reverse_timeout_order}m{grid_text} | "
                  f"\U0001F7E0 Sending orange_dot...")
            print(f"🎯 TP: {self.tp_points} | 🛑 SL: {self.sl_points} | 🔄 BOTH SIDES: {self.both_sides_mean_reverse}")
            print(f"{'='*100}\n")
            # 1. Send "orange_dot" signal with price levels and timeout to NinjaTrader (Visuals)
            self.send_signal_with_levels("orange_dot", sell_limit_level, buy_limit_level,
                                        self.mean_reverse_timeout_order, timestamp)
            
            # 2. Send Execution Command to Strategy (Port 5557)
            self.exec_client.send_execution_command(
                sell_price=sell_limit_level,
                buy_price=buy_limit_level,
                timeout_mins=self.mean_reverse_timeout_order,
                tp_points=self.tp_points,
                sl_points=self.sl_points,
                both_sides=self.both_sides_mean_reverse
            )
    def process_tick(self, tick_data):
        """Process incoming tick data and aggregate by time window"""
        try:
            if not tick_data or tick_data.strip() == "":
                return
            # Parse tick data
            # Format from C#: "timestamp;price;volume;type;bid;ask"
            parts = tick_data.strip().split(';')
            if len(parts) < 2:
                return
            timestamp_str = parts[0].strip()
            # Remove BOM (Byte Order Mark) if present
            if timestamp_str.startswith('\ufeff'):
                timestamp_str = timestamp_str[1:]
            price = float(parts[1])
            # Parse timestamp (handle both with and without microseconds)
            try:
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S.%f')
            except ValueError:
                # Try without microseconds
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            # Determine volume and side
            # Since we don't have individual tick volume, assume 1 contract per tick
            # In real scenario, you'd parse volume from parts[2] if available
            volume = 1
            # Simplified side detection (you may have better logic)
            # If parts has bid/ask info: parts[4] and parts[5]
            is_bid = False
            is_ask = False
            if len(parts) >= 6:
                try:
                    bid_price = float(parts[4])
                    ask_price = float(parts[5])
                    # If price closer to bid, it's a sell
                    # If price closer to ask, it's a buy
                    if abs(price - bid_price) < abs(price - ask_price):
                        is_bid = True
                    else:
                        is_ask = True
                except:
                    # Default to ask if parsing fails
                    is_ask = True
            else:
                # Default to ask if no bid/ask data
                is_ask = True
            self.tick_count += 1
            self.last_tick_time = datetime.now()
            # Initialize window if first tick
            if self.current_window_start is None:
                self.current_window_start = timestamp
                self.current_window_volume = 0
                self.current_window_bid = 0
                self.current_window_ask = 0
                self.current_window_close = price
                self.current_window_ticks = 0
            # Check if we need to start a new window
            time_diff_ms = (timestamp - self.current_window_start).total_seconds() * 1000
            if time_diff_ms >= self.aggregation_window_ms:
                # Check if previous window had big volume
                if self.current_window_ticks > 0:
                    self.check_big_volume(
                        self.current_window_start,
                        self.current_window_volume,
                        self.current_window_bid,
                        self.current_window_ask,
                        self.current_window_close
                    )
                # Start new window
                self.current_window_start = timestamp
                self.current_window_volume = 0
                self.current_window_bid = 0
                self.current_window_ask = 0
                self.current_window_close = price
                self.current_window_ticks = 0
            # Add current tick to window
            self.current_window_volume += volume
            if is_bid:
                self.current_window_bid += volume
            if is_ask:
                self.current_window_ask += volume
            self.current_window_close = price
            self.current_window_ticks += 1
            # Print tick info every 100 ticks for monitoring
            if self.tick_count % 100 == 0:
                elapsed = (datetime.now() - self.start_time).total_seconds()
                ticks_per_sec = self.tick_count / elapsed if elapsed > 0 else 0
                print(f"[TICK #{self.tick_count:>6}] {timestamp_str} | Price: {price:>10.2f} | "
                      f"Window Vol: {self.current_window_volume:>3} | Rate: {ticks_per_sec:.2f} tps")
            # Print summary every 1000 ticks
            if self.tick_count % 1000 == 0:
                self.print_summary()
        except Exception as e:
            print(f"[ERROR] Processing tick: {e}")
            print(f"[DEBUG] Raw data: {tick_data}")
    def print_summary(self):
        """Print statistics summary"""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        ticks_per_sec = self.tick_count / elapsed if elapsed > 0 else 0
        print(f"\n{'='*70}")
        print(f"SUMMARY - {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*70}")
        print(f"Total ticks received: {self.tick_count}")
        print(f"Big volume events detected: {self.big_volume_events}")
        print(f"Total signals sent: {self.signals_sent}")
        print(f"Average rate: {ticks_per_sec:.2f} ticks/second")
        print(f"Running time: {elapsed:.1f} seconds")
        if self.last_signal_time:
            since_last = (datetime.now() - self.last_signal_time).total_seconds()
            print(f"Time since last signal: {since_last:.1f} seconds")
        print(f"{'='*70}\n")
    def receive_loop(self):
        """Main receive loop"""
        buffer = ""
        print(f"\n{'='*70}")
        print(f"RECEIVING TICKS FROM NINJATRADER (LIVE MODE)")
        print(f"{'='*70}\n")
        self.start_time = datetime.now()
        try:
            while self.running and self.tick_connected:
                try:
                    # Receive data from NinjaTrader
                    data = self.tick_socket.recv(4096)
                    if not data:
                        print("[WARNING] No data received - connection may be closed")
                        break
                    # Decode and add to buffer
                    buffer += data.decode('utf-8')
                    # Process complete messages (newline-separated)
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        self.process_tick(line.strip())
                except socket.timeout:
                    # Timeout is normal, just continue
                    continue
                except Exception as e:
                    print(f"[ERROR] Receive error: {e}")
                    break
        except KeyboardInterrupt:
            print("\n[INFO] Interrupted by user")
        finally:
            self.tick_connected = False
    def start(self):
        """Start the live tick receiver"""
        print(f"\n{'#'*70}")
        print(f"# NINJATRADER TICK RECEIVER CLIENT - LIVE MODE")
        print(f"# Detects BIG VOLUME events and sends 'orange_dot' signal")
        print(f"{'#'*70}\n")
        print("Configuration from config_trinchera_live.py:")
        print(f"  - BIG_VOLUME_TRIGGER: {self.big_volume_trigger}")
        print(f"  - BIG_VOLUME_TIMEOUT: {self.big_volume_timeout} minutes")
        print(f"  - MEAN_REVERS_EXPAND: {self.mean_revers_expand} points")
        print(f"  - MEAN_REVERSE_TIMEOUT_ORDER: {self.mean_reverse_timeout_order} minutes")
        print(f"  - FILTER_USE_GRID: {self.filter_use_grid}")
        if self.filter_use_grid:
            print(f"  - GRID_MEAN_REVERS_EXPAND: {self.grid_mean_revers_expand} points")
        print(f"\nConnection settings:")
        print(f"  - Host: {self.host}")
        print(f"  - Tick receive port: {self.tick_port}")
        print(f"  - Signal send port: {self.signal_port}")
        print(f"  - Order execution port: {self.exec_port}")
        print(f"  - Aggregation window: {self.aggregation_window_ms}ms")
        print("\nSetup instructions:")
        print("  1. Open NinjaTrader")
        print("  2. Compile AAIndicatorTrinchera_Draw (F5 in NinjaScript Editor)")
        print("  3. Compile Main_Strategy_Trading_Client_Live (F5 in NinjaScript Editor)")
        print("  4. Add AAIndicatorTrinchera_Draw to your chart")
        print("  5. Add Main_Strategy_Trading_Client_Live to your chart (Enable it!)")
        print("  6. Verify indicator settings: TickSendPort=5555, SignalReceivePort=5556")
        print("  7. Verify strategy settings: ExecutionPort=5557")
        print("\nPress Ctrl+C to stop\n")
        # Connect to tick server
        if not self.connect_tick_receiver():
            print("[ERROR] Failed to connect to tick server.")
            print("\nTroubleshooting:")
            print("  - Is NinjaTrader running?")
            print("  - Is AAIndicatorTrinchera_Draw added to a chart?")
            print("  - Check NinjaTrader Output window for errors")
            return False
        # Connect to signal server
        if not self.connect_signal_sender():
            print("[ERROR] Failed to connect to signal server.")
            self.disconnect()
            return False
            
        # Connect to execution server
        if not self.exec_client.connect():
            print("[ERROR] Failed to connect to execution server (Strategy).")
            print("  - Is Main_Strategy_Trading_Client_Live added to a chart and ENABLED?")
            # We can continue without execution if user wants, but for now let's warn heavily
            print("[WARNING] Continuing without execution capability...")
        print(f"\n{'='*70}")
        print("[OK] CONNECTIONS ESTABLISHED")
        print(f"{'='*70}\n")
        self.running = True
        # Start receive loop in main thread
        try:
            self.receive_loop()
        except KeyboardInterrupt:
            print("\n[INFO] Stopping...")
        finally:
            self.print_summary()
            self.disconnect()
        return True
def main():
    """Main entry point"""
    # Create and start receiver using CONFIG variables
    receiver = TickReceiverClientLive(
        host=HOST,
        tick_port=PORT_TICK_RECEIVER,
        signal_port=PORT_SIGNAL_SENDER,
        exec_port=PORT_ORDER_EXECUTION,
        aggregation_window_ms=500
    )
    receiver.start()
    print("\n[INFO] Receiver stopped")
    print(f"[INFO] Total ticks processed: {receiver.tick_count}")
    print(f"[INFO] Big volume events detected: {receiver.big_volume_events}")
    print(f"[INFO] Total signals sent: {receiver.signals_sent}")
if __name__ == "__main__":
    main()