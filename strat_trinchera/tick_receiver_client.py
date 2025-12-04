"""
NinjaTrader Tick Receiver - CLIENT VERSION
Connects to NinjaTrader indicator servers:
  - Receives ticks from NinjaTrader SERVER on port 5555
  - Sends "orange_dot" signals to NinjaTrader SERVER on port 5556
"""

import socket
import threading
import time
from datetime import datetime


class TickReceiverClient:
    def __init__(self, host='127.0.0.1', tick_port=5555, signal_port=5556, signal_interval=1000):
        """
        Initialize the tick receiver client
        
        
        Args:
            host: NinjaTrader server host (default: localhost)
            tick_port: Port to receive ticks from NinjaTrader (default: 5555)
            signal_port: Port to send signals to NinjaTrader (default: 5556)
            signal_interval: Send signal every N ticks (default: 100)
        """
        self.host = host
        self.tick_port = tick_port
        self.signal_port = signal_port
        self.signal_interval = signal_interval
        
        self.tick_count = 0
        self.running = False
        
        # Separate sockets for receiving and sending
        self.tick_socket = None
        self.signal_socket = None
        self.tick_connected = False
        self.signal_connected = False
        
        # Statistics
        self.start_time = None
        self.last_tick_time = None
        self.signals_sent = 0
        
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
                print("✓ SUCCESS")
                print(f"[TICK] Connected to NinjaTrader tick server at {self.host}:{self.tick_port}\n")
                return True
                
            except Exception as e:
                print(f"✗ FAILED: {e}")
                
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
                print("✓ SUCCESS")
                print(f"[SIGNAL] Connected to NinjaTrader signal server at {self.host}:{self.signal_port}\n")
                return True
                
            except Exception as e:
                print(f"✗ FAILED: {e}")
                
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
        """Send signal to NinjaTrader"""
        try:
            # Format: just the signal name with newline (as expected by C# ReadLine())
            message = f"{signal_name}\n"
            
            if self.signal_connected and self.signal_socket:
                self.signal_socket.sendall(message.encode('utf-8'))
                self.signals_sent += 1
                
                print(f"\n{'*'*70}")
                print(f"🟠 SIGNAL SENT: {signal_name}")
                print(f"{'*'*70}")
                print(f"Tick count: {self.tick_count}")
                print(f"Total signals sent: {self.signals_sent}")
                print(f"Time: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
                print(f"{'*'*70}\n")
                
                return True
            else:
                print(f"[WARNING] Cannot send signal - not connected to signal server")
                return False
                
        except Exception as e:
            print(f"[ERROR] Failed to send signal: {e}")
            self.signal_connected = False
            return False
    
    def process_tick(self, tick_data):
        """Process incoming tick data"""
        try:
            if not tick_data or tick_data.strip() == "":
                return
            
            # Parse tick data
            # Format from C#: "timestamp;price;volume;type;bid;ask"
            parts = tick_data.strip().split(';')
            
            if len(parts) < 2:
                return
            
            timestamp_str = parts[0]
            price = float(parts[1])
            
            self.tick_count += 1
            self.last_tick_time = datetime.now()
            
            # Print tick info every 10 ticks for monitoring
            if self.tick_count % 10 == 0:
                elapsed = (datetime.now() - self.start_time).total_seconds()
                ticks_per_sec = self.tick_count / elapsed if elapsed > 0 else 0
                
                print(f"[TICK #{self.tick_count:>6}] {timestamp_str} | Price: {price:>10.2f} | Rate: {ticks_per_sec:.2f} ticks/sec")
            
            # Send signal every N ticks
            if self.tick_count % self.signal_interval == 0:
                self.send_signal("orange_dot")
            
            # Print summary every 500 ticks
            if self.tick_count % 500 == 0:
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
        print(f"Total signals sent: {self.signals_sent}")
        print(f"Average rate: {ticks_per_sec:.2f} ticks/second")
        print(f"Running time: {elapsed:.1f} seconds")
        print(f"{'='*70}\n")
    
    def receive_loop(self):
        """Main receive loop"""
        buffer = ""
        
        print(f"\n{'='*70}")
        print(f"RECEIVING TICKS FROM NINJATRADER")
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
        """Start the tick receiver"""
        print(f"\n{'#'*70}")
        print(f"# NINJATRADER TICK RECEIVER CLIENT")
        print(f"# Receives ticks and sends 'orange_dot' signal every {self.signal_interval} ticks")
        print(f"{'#'*70}\n")
        
        print("Configuration:")
        print(f"  - Host: {self.host}")
        print(f"  - Tick receive port: {self.tick_port}")
        print(f"  - Signal send port: {self.signal_port}")
        print(f"  - Signal interval: {self.signal_interval} ticks")
        print("\nSetup instructions:")
        print("  1. Open NinjaTrader")
        print("  2. Compile AAIndicatorTrinchera_Draw (F5 in NinjaScript Editor)")
        print("  3. Add AAIndicatorTrinchera_Draw to your chart")
        print("  4. Verify indicator settings: TickSendPort=5555, SignalReceivePort=5556")
        print("  5. Make sure the indicator is running (check NinjaTrader Output window)")
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
        
        print(f"\n{'='*70}")
        print("✓✓✓ BOTH CONNECTIONS ESTABLISHED ✓✓✓")
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
    # Create and start receiver
    receiver = TickReceiverClient(
        host='127.0.0.1',
        tick_port=5555,      # NinjaTrader sends ticks on this port
        signal_port=5556,    # NinjaTrader receives signals on this port
        signal_interval=1000  # Send "orange_dot" every 100 ticks
    )
    
    receiver.start()
    
    print("\n[INFO] Receiver stopped")
    print(f"[INFO] Total ticks processed: {receiver.tick_count}")
    print(f"[INFO] Total signals sent: {receiver.signals_sent}")


if __name__ == "__main__":
    main()
