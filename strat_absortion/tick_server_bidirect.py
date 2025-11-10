"""
Simple Bidirectional Tick Server - Single Port

Receives tick data from AASender, detects patterns,
and sends pattern signals back through the same socket.
"""

import socket
import json
import threading
import csv
from datetime import datetime
from pathlib import Path
import sys

from absorption_strategy_streaming import AbsorptionStrategyStreaming


# ============================================================================
# CONFIGURATION
# ============================================================================

# Network configuration
PORT = 55555  # Single port for bidirectional communication
BUFFER_SIZE = 4096

# Strategy parameters
PROFILE_WINDOW = 20
EXTREME_VOLUME_MULTIPLIER = 2
MIN_PRICE_LEVELS = 20
MIN_BID_ASK_SIZE = 30
PRICE_POSITION_THRESHOLD = 0.3
DIFF_DISTANCE = 0
MIN_VOLUME = 1

# Detection timing
COOLDOWN_PERIOD = 60
WARMUP_PERIOD = 60

# Logging configuration
VERBOSE = True
LOG_INTERVAL = 1000

# CSV logging configuration
BASE_DIR = Path(__file__).resolve().parent
CSV_OUTPUT_DIR = BASE_DIR.parent / "data" / "monitor_ninja"
CSV_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================


class SimpleBidirectServer:
    """Simple bidirectional tick server with pattern detection."""

    def __init__(self, port: int):
        """
        Initialize server.

        Args:
            port: TCP port to listen on
        """
        self.port = port
        self.socket = None
        self.running = False
        self.client_socket = None  # Current connected client

        # Initialize streaming strategy
        self.strategy = AbsorptionStrategyStreaming(
            profile_window=PROFILE_WINDOW,
            extreme_volume_multiplier=EXTREME_VOLUME_MULTIPLIER,
            min_price_levels=MIN_PRICE_LEVELS,
            min_bid_ask_size=MIN_BID_ASK_SIZE,
            price_position_threshold=PRICE_POSITION_THRESHOLD,
            diff_distance=DIFF_DISTANCE,
            min_volume=MIN_VOLUME,
            cooldown_period=COOLDOWN_PERIOD,
            warmup_period=WARMUP_PERIOD,
            on_detection_callback=self.on_pattern_detected,
        )

        self.tick_count = 0
        self.detection_count = 0

        # CSV logging
        self.csv_file = None
        self.csv_writer = None
        self.csv_handle = None

        # Detection tracking for CSV shape column
        self.last_detection_timestamp = None
        self.last_detection_shape = None

    def initialize_csv(self):
        """Initialize CSV file for tick logging."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.csv_file = CSV_OUTPUT_DIR / f"tick_server_bidirect_{timestamp}.csv"
        self.csv_handle = open(self.csv_file, 'w', newline='', encoding='utf-8')
        self.csv_writer = csv.writer(self.csv_handle, delimiter=';')
        # Headers: date;time;bid;ask;price;volume;side;shape
        self.csv_writer.writerow(['date', 'time', 'bid', 'ask', 'price', 'volume', 'side', 'shape'])
        self.csv_handle.flush()
        print(f"[CSV] Logging ticks to: {self.csv_file}")

    def close_csv(self):
        """Close CSV file."""
        if self.csv_handle:
            self.csv_handle.close()
            self.csv_handle = None
            self.csv_writer = None
            print(f"[CSV] Closed: {self.csv_file}")

    def log_tick_to_csv(self, timestamp: datetime, price: float, volume: int, side: str, bid: float = None, ask: float = None, shape: str = None):
        """
        Log tick to CSV file.

        Args:
            timestamp: Tick timestamp
            price: Trade price
            volume: Trade volume
            side: Trade side (BID/ASK/BETWEEN/UNKNOWN)
            bid: Bid price (if available)
            ask: Ask price (if available)
            shape: Detection shape (d_shape/p_shape/None)
        """
        if not self.csv_writer:
            return

        date_str = timestamp.strftime('%Y%m%d')
        time_str = timestamp.strftime('%H%M%S.%f')[:-3]  # Include milliseconds

        # Check if this tick matches a detection timestamp
        shape_value = ""
        if self.last_detection_timestamp and self.last_detection_shape:
            # Match detection to tick (within 1 second tolerance)
            time_diff = abs((timestamp - self.last_detection_timestamp).total_seconds())
            if time_diff < 1.0:
                shape_value = self.last_detection_shape
                # Clear detection after marking it
                self.last_detection_timestamp = None
                self.last_detection_shape = None

        row = [
            date_str,
            time_str,
            f"{bid:.2f}" if bid is not None else "",
            f"{ask:.2f}" if ask is not None else "",
            f"{price:.2f}",
            volume,
            side,
            shape_value  # Will be empty string for most ticks, d_shape/p_shape for detections
        ]

        self.csv_writer.writerow(row)
        self.csv_handle.flush()

    def on_pattern_detected(self, detection_data: dict):
        """
        Callback triggered when a pattern is detected.
        Sends signal back to client.

        Args:
            detection_data: Detection information from strategy
        """
        timestamp = detection_data['timestamp']
        shape = detection_data['shape']
        price = detection_data['price']
        detection_num = detection_data['detection_num']

        self.detection_count = detection_num

        # Store detection info for CSV tagging
        self.last_detection_timestamp = timestamp
        self.last_detection_shape = shape

        print(f"\n{'*' * 80}")
        print(f"PATTERN DETECTED!")
        print(f"Detection #{detection_num}")
        print(f"Shape: {shape}")
        print(f"Price: {price:.2f}")
        print(f"Time: {timestamp}")
        print(f"{'*' * 80}\n")

        # Send signal back to client
        self.send_pattern_signal(shape, price, timestamp)

    def send_pattern_signal(self, shape: str, price: float, timestamp: datetime):
        """
        Send pattern detection signal to client.

        Args:
            shape: Pattern shape (d_shape or p_shape)
            price: Detection price
            timestamp: Detection timestamp
        """
        if self.client_socket is None:
            print("[WARN] No client connected, pattern signal not sent")
            return

        try:
            signal = {
                "command": "PATTERN",
                "shape": shape,
                "price": price,
                "timestamp": timestamp.isoformat()
            }

            message = json.dumps(signal) + "\n"
            self.client_socket.sendall(message.encode('utf-8'))

            print(f"[OK] Sent {shape} signal to client @ {price:.2f}")

        except Exception as e:
            print(f"[ERROR] Failed to send pattern signal: {e}")
            self.client_socket = None

    def process_tick(self, tick_data: dict):
        """
        Process incoming tick data.

        Args:
            tick_data: Tick information from client
        """
        try:
            # Parse tick data
            timestamp = datetime.fromisoformat(tick_data['timestamp'])
            price = float(tick_data['price'])
            volume = int(tick_data['volume'])
            side = str(tick_data['side']).upper()

            # Log tick to CSV
            # Note: NinjaTrader AASender doesn't send bid/ask separately,
            # so we infer from side and price
            bid_price = None
            ask_price = None
            if side == 'BID':
                bid_price = price
            elif side == 'ASK':
                ask_price = price

            self.log_tick_to_csv(timestamp, price, volume, side, bid_price, ask_price)

            # Process through strategy
            detection = self.strategy.process_tick(timestamp, price, volume, side)

            self.tick_count += 1

            # Log progress
            if VERBOSE and self.tick_count % LOG_INTERVAL == 0:
                stats = self.strategy.get_stats()
                print(f"[STATS] Ticks: {self.tick_count:,} | "
                      f"Detections: {stats['detection_count']} | "
                      f"Last: {stats['last_detection']}")

        except Exception as e:
            print(f"[ERROR] Tick processing error: {e}")

    def handle_client(self, client_socket: socket.socket):
        """
        Handle connected client.

        Args:
            client_socket: Connected client socket
        """
        self.client_socket = client_socket
        buffer = ""

        try:
            while self.running:
                # Receive data
                data = client_socket.recv(BUFFER_SIZE)
                if not data:
                    print("[OK] Client disconnected")
                    break

                # Decode and add to buffer
                buffer += data.decode('utf-8')

                # Process complete messages (newline-delimited JSON)
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.strip()

                    if not line:
                        continue

                    try:
                        message = json.loads(line)

                        # Handle different message types
                        if "command" in message:
                            if message["command"] == "COMPLETE":
                                print("[OK] Received completion signal from client")
                                self.finalize()
                                return
                        else:
                            # Regular tick data
                            self.process_tick(message)

                    except json.JSONDecodeError as e:
                        print(f"[ERROR] Invalid JSON: {e}")
                        continue

        except Exception as e:
            print(f"[ERROR] Client handler error: {e}")
        finally:
            self.client_socket = None
            try:
                client_socket.close()
            except:
                pass

    def start(self):
        """Start the server."""
        try:
            # Create TCP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(('localhost', self.port))
            self.socket.listen(1)
            self.socket.settimeout(1.0)  # 1 second timeout for accept()

            print(f"[OK] Server listening on localhost:{self.port}")
            print(f"[OK] Waiting for client connection...")
            print(f"[OK] Press Ctrl+C to stop server\n")

            self.running = True

            while self.running:
                try:
                    # Accept client connection
                    client_socket, client_address = self.socket.accept()
                    print(f"[OK] Client connected from {client_address}")

                    # Close previous CSV if exists
                    self.close_csv()

                    # Initialize new CSV for this session
                    self.initialize_csv()

                    # Reset strategy for new session
                    print(f"[RESET] Resetting strategy...")
                    self.strategy = AbsorptionStrategyStreaming(
                        profile_window=PROFILE_WINDOW,
                        extreme_volume_multiplier=EXTREME_VOLUME_MULTIPLIER,
                        min_price_levels=MIN_PRICE_LEVELS,
                        min_bid_ask_size=MIN_BID_ASK_SIZE,
                        price_position_threshold=PRICE_POSITION_THRESHOLD,
                        diff_distance=DIFF_DISTANCE,
                        min_volume=MIN_VOLUME,
                        cooldown_period=COOLDOWN_PERIOD,
                        warmup_period=WARMUP_PERIOD,
                        on_detection_callback=self.on_pattern_detected,
                    )
                    self.tick_count = 0
                    self.detection_count = 0
                    self.last_detection_timestamp = None
                    self.last_detection_shape = None
                    print(f"[OK] Strategy reset complete\n")

                    # Handle client
                    self.handle_client(client_socket)
                except socket.timeout:
                    # Timeout allows checking self.running flag
                    continue

        except KeyboardInterrupt:
            print(f"\n[STOP] Server interrupted by user")
        except Exception as e:
            print(f"[ERROR] Server error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.stop()

    def finalize(self):
        """Finalize strategy and save results."""
        print(f"\n{'=' * 80}")
        print(f"Finalizing strategy...")

        # Close CSV logging
        self.close_csv()

        # Finalize strategy (generates HTML and signals CSV)
        csv_path = self.strategy.finalize()

        stats = self.strategy.get_stats()
        print(f"\n{'=' * 80}")
        print(f"PROCESSING COMPLETE!")
        print(f"Total ticks processed: {self.tick_count:,}")
        print(f"Total detections: {stats['detection_count']}")
        if stats.get('html_path'):
            print(f"HTML report: {stats['html_path']}")
        if csv_path:
            print(f"Signals CSV: {csv_path}")
        if self.csv_file:
            print(f"Tick log CSV: {self.csv_file}")
        print(f"{'=' * 80}")

    def stop(self):
        """Stop the server."""
        self.running = False

        # Close CSV if still open
        self.close_csv()

        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass

        if self.socket:
            try:
                self.socket.close()
            except:
                pass

        print("[OK] Server stopped")


def main():
    """Main entry point."""
    print("=" * 80)
    print("SIMPLE BIDIRECTIONAL TICK SERVER")
    print("=" * 80)
    print(f"Host: localhost")
    print(f"Port: {PORT}")
    print(f"\nStrategy Configuration:")
    print(f"  Profile Window: {PROFILE_WINDOW}s")
    print(f"  Min Price Levels: {MIN_PRICE_LEVELS}")
    print(f"  Min Bid/Ask Size: {MIN_BID_ASK_SIZE}")
    print(f"  Cooldown: {COOLDOWN_PERIOD}s")
    print("=" * 80 + "\n")

    server = SimpleBidirectServer(PORT)
    server.start()


if __name__ == "__main__":
    main()
