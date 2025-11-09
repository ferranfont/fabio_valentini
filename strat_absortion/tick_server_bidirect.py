"""
Simple Bidirectional Tick Server - Single Port

Receives tick data from AASender, detects patterns,
and sends pattern signals back through the same socket.
"""

import socket
import json
import threading
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
EXTREME_VOLUME_MULTIPLIER = 0.1
MIN_PRICE_LEVELS = 3
MIN_BID_ASK_SIZE = 3
PRICE_POSITION_THRESHOLD = 0.3
DIFF_DISTANCE = 0
MIN_VOLUME = 1

# Detection timing
COOLDOWN_PERIOD = 60
WARMUP_PERIOD = 60

# Logging configuration
VERBOSE = True
LOG_INTERVAL = 1000

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

    def stop(self):
        """Stop the server."""
        self.running = False

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
