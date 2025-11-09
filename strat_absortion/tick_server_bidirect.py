"""
Server - Absorption Strategy Processor with Screen Recording

Receives tick data from client, processes with streaming absorption strategy,
and records screen for 10 seconds on pattern detection.
"""

import socket
import json
import threading
import csv
from datetime import datetime
from pathlib import Path
import sys
import winsound

from absorption_strategy_streaming import AbsorptionStrategyStreaming


# ============================================================================
# CONFIGURATION - Edit these settings as needed
# ============================================================================

# Network configuration
PORT = 55555  # Server port (localhost is always used)
BUFFER_SIZE = 4096  # TCP receive buffer size in bytes

# Strategy parameters (from main.py)
PROFILE_WINDOW = 20  # Rolling window size in seconds
EXTREME_VOLUME_MULTIPLIER = 0.1  # Antes 2 Extreme bar must be N times the second-largest
MIN_PRICE_LEVELS = 3  # Antes 20 Minimum number of active price levels
MIN_BID_ASK_SIZE = 3  # Antes 30 Minimum absolute size of largest BID/ASK bar
PRICE_POSITION_THRESHOLD = 0.3  # Price must be in lower/upper 30% of profile range
DIFF_DISTANCE = 0  # Minimum absolute price difference
MIN_VOLUME = 1 # Antes 10 inimum total volume (BID + ASK)

# Detection timing
COOLDOWN_PERIOD = 60  # Cooldown period in seconds between detections
WARMUP_PERIOD = 60  # Warmup period in seconds before starting detection

# Screen recording configuration
BASE_DIR = Path(__file__).resolve().parent
SCREEN_RECORD_DIR = BASE_DIR.parent / "recordings"
SCREEN_RECORD_DIR.mkdir(parents=True, exist_ok=True)

# CSV logging configuration
CSV_OUTPUT_DIR = BASE_DIR.parent / "data" / "monitor_ninja"
CSV_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SCREEN_RECORD_DURATION = 120  # Seconds to record after detection
SCREEN_RECORD_FPS = 10  # Frames per second for recording
VIDEO_CODEC = 'mp4v'  # Video codec (options: 'mp4v', 'XVID', 'MJPG')

# Logging configuration
VERBOSE = True  # Enable verbose logging
LOG_INTERVAL = 1000  # Log every N ticks processed

# ============================================================================


def play_beep(count: int = 1, frequency: int = 1000, duration_ms: int = 200, pause_ms: int = 100):
    """
    Play system beep(s).

    Args:
        count: Number of beeps to play
        frequency: Beep frequency in Hz
        duration_ms: Duration of each beep in milliseconds
        pause_ms: Pause between beeps in milliseconds
    """
    try:
        import time
        for i in range(count):
            winsound.Beep(frequency, duration_ms)
            if i < count - 1:  # Don't pause after last beep
                time.sleep(pause_ms / 1000.0)
    except Exception as e:
        # Silently fail if beep not available
        pass


class ScreenRecorder:
    """Screen recorder using mss and opencv."""

    def __init__(self, output_dir: Path):
        """
        Initialize screen recorder.

        Args:
            output_dir: Directory to save recordings
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Try to import screen capture libraries
        try:
            import cv2
            import mss
            import numpy as np
            self.cv2 = cv2
            self.mss = mss
            self.np = np
            self.available = True
            print("[OK] Screen recording libraries loaded (mss, opencv)")
        except ImportError as e:
            print(f"[WARNING] Screen recording not available: {e}")
            print("Install with: pip install mss opencv-python numpy")
            self.available = False

    def record(self, duration: int, filename: str, fps: int = SCREEN_RECORD_FPS):
        """
        Record screen for specified duration.

        Args:
            duration: Recording duration in seconds
            filename: Output filename (without extension)
            fps: Frames per second
        """
        if not self.available:
            print(f"[WARNING] Screen recording skipped (libraries not available)")
            return

        output_path = self.output_dir / f"{filename}.mp4"

        def record_thread():
            try:
                print(f"[RECORDING] Starting screen capture for {duration}s...")

                with self.mss.mss() as sct:
                    # Get primary monitor
                    monitor = sct.monitors[1]

                    # Setup video writer
                    fourcc = self.cv2.VideoWriter_fourcc(*VIDEO_CODEC)
                    width = monitor['width']
                    height = monitor['height']
                    out = self.cv2.VideoWriter(
                        str(output_path),
                        fourcc,
                        fps,
                        (width, height)
                    )

                    if not out.isOpened():
                        print(f"[ERROR] Failed to open video writer")
                        return

                    # Calculate total frames
                    total_frames = duration * fps
                    frame_delay = 1.0 / fps

                    import time
                    start_time = time.time()

                    for i in range(total_frames):
                        # Capture screen
                        img = sct.grab(monitor)

                        # Convert to numpy array
                        frame = self.np.array(img)

                        # Convert BGRA to BGR
                        frame = self.cv2.cvtColor(frame, self.cv2.COLOR_BGRA2BGR)

                        # Write frame
                        out.write(frame)

                        # Wait for next frame
                        next_frame_time = start_time + (i + 1) * frame_delay
                        sleep_time = next_frame_time - time.time()
                        if sleep_time > 0:
                            time.sleep(sleep_time)

                    out.release()
                    elapsed = time.time() - start_time

                    print(f"[RECORDING] Completed! Saved to: {output_path}")
                    print(f"[RECORDING] Duration: {elapsed:.1f}s | Frames: {total_frames}")

                    # Play single beep for completion
                    play_beep(count=1, frequency=800, duration_ms=300)

            except Exception as e:
                print(f"[ERROR] Screen recording failed: {e}")
                import traceback
                traceback.print_exc()

        # Start recording in separate thread
        thread = threading.Thread(target=record_thread, daemon=True)
        thread.start()


class TickServer:
    """Server that receives ticks and processes with absorption strategy."""

    def __init__(self, port: int = PORT):
        """
        Initialize the server.

        Args:
            port: Server port (listens on localhost)
        """
        self.host = '127.0.0.1'  # Always localhost
        self.port = port
        self.socket = None
        self.running = False
        self.active_client_socket = None

        # Initialize screen recorder
        self.recorder = ScreenRecorder(SCREEN_RECORD_DIR)

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
        self.last_tick_data = None  # Almacenar último tick recibido
        self.last_print_time = datetime.now()  # Control de impresión cada 10s

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

    def send_message_to_client(self, message: str):
        """Send simple text message to connected client (Ninja)."""
        if not message:
            return

        client_socket = self.active_client_socket
        if not client_socket:
            return

        try:
            payload = message.strip() + "\n"
            client_socket.sendall(payload.encode('utf-8'))
            preview = message if len(message) < 160 else message[:157] + "..."
            print(f"[BIDIRECT] -> {preview}")
        except Exception as e:
            print(f"[WARN] Failed to send message to client: {e}")

    def notify_client_pattern(self, detection_data: dict):
        """Send pattern notification to Ninja output."""
        shape = detection_data.get('shape', '')
        price = detection_data.get('price')
        timestamp = detection_data.get('timestamp')
        detection_num = detection_data.get('detection_num')

        if not shape or price is None or timestamp is None:
            return

        payload = {
            "command": "PATTERN",
            "shape": shape,
            "price": float(price),
            "timestamp": timestamp.isoformat() if isinstance(timestamp, datetime) else str(timestamp),
            "detection_num": detection_num,
            "message": self._format_shape_message(shape)
        }

        try:
            serialized = json.dumps(payload)
        except Exception as exc:
            print(f"[WARN] Failed to serialize pattern payload: {exc}")
            serialized = payload.get("message", "")

        if serialized:
            self.send_message_to_client(serialized)

    @staticmethod
    def _format_shape_message(shape: str) -> str:
        """Return formatted message for supported shapes."""
        if not shape:
            return ""

        normalized = str(shape).lower()
        if normalized.startswith('d'):
            return "Patrón d-SHAPE detectado"
        if normalized.startswith('p'):
            return "Patrón p-SHAPE detectado"
        return ""

    def on_pattern_detected(self, detection_data: dict):
        """
        Callback triggered when a pattern is detected.

        Args:
            detection_data: Detection information from strategy
        """
        timestamp = detection_data['timestamp']
        shape = detection_data['shape']
        price = detection_data['price']
        detection_num = detection_data['detection_num']

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

        # Play double beep for detection
        play_beep(count=2, frequency=1200, duration_ms=150, pause_ms=100)

        # Start screen recording
        filename = f"detection_{detection_num}_{shape}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        self.recorder.record(
            duration=SCREEN_RECORD_DURATION,
            filename=filename,
            fps=SCREEN_RECORD_FPS
        )
        self.notify_client_pattern(detection_data)

    def start(self):
        """Start the server and listen for connections."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(1)
            # Set timeout to make Ctrl+C more responsive
            self.socket.settimeout(1.0)

            print(f"[OK] Server listening on localhost:{self.port}")
            print(f"[OK] Waiting for client connection...")
            print(f"[OK] Press Ctrl+C to stop server\n")

            self.running = True

            while self.running:
                try:
                    # Accept client connection
                    client_socket, client_address = self.socket.accept()
                    print(f"[OK] Client connected from {client_address}")

                    # Limpiar buffer de estrategia al conectar cliente nuevo
                    print(f"[RESET] Limpiando buffer de estrategia...")

                    # Close previous CSV if exists
                    self.close_csv()

                    # Initialize new CSV for this session
                    self.initialize_csv()

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
                    self.last_tick_data = None
                    self.last_print_time = datetime.now()
                    self.last_detection_timestamp = None
                    self.last_detection_shape = None
                    print(f"[OK] Buffer limpiado, estrategia reiniciada\n")

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

    def handle_client(self, client_socket):
        """
        Handle incoming client connection and process tick data.

        Args:
            client_socket: Connected client socket
        """
        buffer = ""
        self.active_client_socket = client_socket

        try:
            while self.running:
                # Receive data
                data = client_socket.recv(BUFFER_SIZE)
                if not data:
                    print("[INFO] Client disconnected")
                    break

                # Decode and add to buffer
                buffer += data.decode('utf-8')

                # Process complete messages (newline-separated JSON)
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)

                    if not line.strip():
                        continue

                    try:
                        tick_data = json.loads(line)

                        # Check for completion signal
                        if tick_data.get('command') == 'COMPLETE':
                            print("\n[INFO] Received completion signal from client")
                            self.finalize()
                            break

                        # Process tick
                        self.process_tick(tick_data)

                    except json.JSONDecodeError as e:
                        print(f"[ERROR] Invalid JSON: {e}")
                    except Exception as e:
                        print(f"[ERROR] Processing error: {e}")

        except KeyboardInterrupt:
            print(f"\n[STOP] Server interrupted by user (Ctrl+C)")
            self.running = False
            raise  # Re-raise to be caught by start()
        except Exception as e:
            print(f"[ERROR] Client handler error: {e}")
        finally:
            if self.active_client_socket is client_socket:
                self.active_client_socket = None
            client_socket.close()

    def process_tick(self, tick_data: dict):
        """
        Process a single tick through the strategy.

        Args:
            tick_data: Tick data dictionary (timestamp, price, volume, side)
        """
        try:
            # Parse tick data
            timestamp = datetime.fromisoformat(tick_data['timestamp'])
            price = float(tick_data['price'])
            volume = int(tick_data['volume'])
            side = str(tick_data['side']).upper()

            # Guardar último tick recibido
            self.last_tick_data = {
                'timestamp': timestamp,
                'price': price,
                'volume': volume,
                'side': side
            }

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

            # Mostrar último tick cada 10 segundos
            now = datetime.now()
            if (now - self.last_print_time).total_seconds() >= 10:
                print(f"[TICK] Time: {timestamp.strftime('%H:%M:%S')} | "
                      f"Price: {price:.2f} | "
                      f"Volume: {volume} | "
                      f"Side: {side} | "
                      f"Total ticks: {self.tick_count + 1:,}")
                self.last_print_time = now

            # Process through strategy
            detection = self.strategy.process_tick(timestamp, price, volume, side)

            self.tick_count += 1

        except Exception as e:
            print(f"[ERROR] Tick processing error: {e}")

    def finalize(self):
        """Finalize strategy and save results."""
        print(f"\n{'=' * 80}")
        print(f"Finalizing strategy...")

        # Close CSV logging
        self.close_csv()

        csv_path = self.strategy.finalize()

        stats = self.strategy.get_stats()
        print(f"\n{'=' * 80}")
        print(f"PROCESSING COMPLETE!")
        print(f"Total ticks processed: {self.tick_count:,}")
        print(f"Total detections: {stats['detection_count']}")
        if stats['html_path']:
            print(f"HTML report: {stats['html_path']}")
        if csv_path:
            print(f"Signals CSV: {csv_path}")
        if self.csv_file:
            print(f"Tick log CSV: {self.csv_file}")
        print(f"Recordings directory: {SCREEN_RECORD_DIR}")
        print(f"{'=' * 80}")

    def stop(self):
        """Stop the server."""
        self.running = False

        # Close CSV if still open
        self.close_csv()

        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        self.active_client_socket = None
        print("[OK] Server stopped")


def main():
    """Main server entry point."""
    print("=" * 80)
    print("ABSORPTION STRATEGY SERVER")
    print("=" * 80)
    print(f"Host: localhost")
    print(f"Port: {PORT}")
    print(f"\nStrategy Configuration:")
    print(f"  Profile Window: {PROFILE_WINDOW}s")
    print(f"  Min Price Levels: {MIN_PRICE_LEVELS}")
    print(f"  Min Bid/Ask Size: {MIN_BID_ASK_SIZE}")
    print(f"  Cooldown: {COOLDOWN_PERIOD}s")
    print(f"\nScreen Recording:")
    print(f"  Duration: {SCREEN_RECORD_DURATION}s")
    print(f"  FPS: {SCREEN_RECORD_FPS}")
    print(f"  Output: {SCREEN_RECORD_DIR}")
    print(f"\nTick Logging:")
    print(f"  CSV Output: {CSV_OUTPUT_DIR}")
    print("=" * 80 + "\n")

    server = TickServer(PORT)
    server.start()


if __name__ == "__main__":
    main()
