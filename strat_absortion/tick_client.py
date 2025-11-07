"""
Client - CSV Data Streamer

Reads tick data from CSV file and streams it to the server via TCP socket.
Simulates real-time data feed by sending one tick at a time.
"""

import socket
import json
import time
import sys
from pathlib import Path
import pandas as pd


# ============================================================================
# CONFIGURATION - Edit these settings as needed
# ============================================================================

# Network configuration
PORT = 55555  # Server port (localhost is always used)

# Data source
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"
FICHERO_ORIGEN = "time_and_sales_nq_20250915_redux"
CSV_PATH = DATA_DIR / f"historic/{FICHERO_ORIGEN}.csv"

# Streaming speed
TICK_DELAY_MS = 10  # Milliseconds between ticks
# 0 = Maximum speed (backtesting)
# 10 = ~100 ticks/sec (realistic for live data)
# 100-1000 = Slower, more observable streaming

# Logging
LOG_INTERVAL = 1000  # Log progress every N ticks

# ============================================================================


class TickClient:
    """Client that streams tick data to the server."""

    def __init__(self, csv_path: Path, port: int = PORT):
        """
        Initialize the tick data client.

        Args:
            csv_path: Path to CSV file with tick data
            port: Server port (connects to localhost)
        """
        self.csv_path = csv_path
        self.host = '127.0.0.1'  # Always localhost
        self.port = port
        self.socket = None
        self.connected = False

    def connect(self) -> bool:
        """Connect to the server."""
        try:
            print(f"Connecting to server at localhost:{self.port}...")
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.connected = True
            print(f"[OK] Connected to server")
            return True
        except Exception as e:
            print(f"[ERROR] Connection failed: {e}")
            return False

    def send_tick(self, tick_data: dict) -> bool:
        """
        Send a single tick to the server.

        Args:
            tick_data: Dictionary with tick data (timestamp, price, volume, side)

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.connected:
            return False

        try:
            # Convert to JSON and send
            message = json.dumps(tick_data) + "\n"
            self.socket.sendall(message.encode('utf-8'))
            return True
        except Exception as e:
            print(f"[ERROR] Failed to send tick: {e}")
            self.connected = False
            return False

    def stream_csv(self, delay_ms: int = TICK_DELAY_MS):
        """
        Stream all ticks from CSV file to server.

        Args:
            delay_ms: Delay in milliseconds between ticks
        """
        if not self.csv_path.exists():
            print(f"[ERROR] CSV file not found: {self.csv_path}")
            return

        print(f"Loading CSV: {self.csv_path}")

        # Detect CSV format
        with open(self.csv_path, "r") as f:
            first_line = f.readline().strip()

        is_dom_format = "DOM_BID" in first_line and "DOM_ASK" in first_line

        if is_dom_format:
            print("Detected DOM format")
            df = self._load_dom_format()
        else:
            print("Detected standard format (European CSV)")
            df = pd.read_csv(self.csv_path, sep=";", decimal=",")
            df["Timestamp"] = pd.to_datetime(df["Timestamp"])

        print(f"Loaded {len(df)} ticks")
        print(f"Time range: {df['Timestamp'].min()} to {df['Timestamp'].max()}")

        if not self.connect():
            return

        print(f"\nStarting to stream ticks (delay: {delay_ms}ms between ticks)...")
        print("Press Ctrl+C to stop\n")

        delay_sec = delay_ms / 1000.0
        total_ticks = len(df)
        sent_count = 0
        start_time = time.time()

        try:
            for idx, row in enumerate(df.itertuples()):
                # Prepare tick data
                tick_data = {
                    'timestamp': row.Timestamp.isoformat(),
                    'price': float(str(row.Precio).replace(",", ".")),
                    'volume': int(row.Volumen),
                    'side': str(row.Lado).upper(),
                }

                # Send tick
                if self.send_tick(tick_data):
                    sent_count += 1

                    # Progress reporting
                    if sent_count % LOG_INTERVAL == 0:
                        percent = (sent_count / total_ticks) * 100
                        elapsed = time.time() - start_time
                        rate = sent_count / elapsed if elapsed > 0 else 0
                        print(f"Progress: {percent:5.1f}% ({sent_count:,}/{total_ticks:,}) | "
                              f"Rate: {rate:.0f} ticks/sec")

                    # Delay before next tick
                    if delay_sec > 0:
                        time.sleep(delay_sec)
                else:
                    print(f"[ERROR] Failed to send tick {sent_count}, stopping...")
                    break

        except KeyboardInterrupt:
            print(f"\n[STOP] Interrupted by user")
        except Exception as e:
            print(f"\n[ERROR] Streaming error: {e}")

        # Send completion signal
        self.send_tick({'command': 'COMPLETE'})

        elapsed = time.time() - start_time
        print(f"\n{'=' * 80}")
        print(f"Streaming complete!")
        print(f"Ticks sent: {sent_count:,} / {total_ticks:,}")
        print(f"Duration: {elapsed:.1f}s")
        print(f"Average rate: {sent_count/elapsed:.0f} ticks/sec")
        print(f"{'=' * 80}")

        self.disconnect()

    def _load_dom_format(self) -> pd.DataFrame:
        """Load CSV with DOM format (malformed quoting)."""
        with open(self.csv_path, "r") as f:
            header = f.readline().strip().split(",")
            rows = []

            for line in f:
                line = line.strip()
                if line.startswith('"') and line.endswith('"'):
                    line = line[1:-1]

                parts = []
                current = ""
                in_dict = 0

                for char in line:
                    if char == "{":
                        in_dict += 1
                    elif char == "}":
                        in_dict -= 1

                    if char == "," and in_dict == 0:
                        parts.append(current)
                        current = ""
                    else:
                        current += char

                if current:
                    parts.append(current)

                if len(parts) >= 4:
                    rows.append(parts[:4])

        df = pd.DataFrame(rows, columns=header[:4])
        df["Timestamp"] = pd.to_datetime(df["Timestamp"])
        df = df.rename(columns={"Price": "Precio", "Size": "Volumen", "Side": "Lado"})
        df["Precio"] = df["Precio"].astype(float)
        df["Volumen"] = df["Volumen"].astype(int)

        return df

    def disconnect(self):
        """Disconnect from server."""
        if self.socket:
            try:
                self.socket.close()
                print("[OK] Disconnected from server")
            except:
                pass
        self.connected = False


def main():
    """Main client entry point."""
    print("=" * 80)
    print("TICK DATA CLIENT")
    print("=" * 80)
    print(f"CSV File: {CSV_PATH}")
    print(f"Server: localhost:{PORT}")
    print(f"Tick Delay: {TICK_DELAY_MS}ms")
    print("=" * 80 + "\n")

    client = TickClient(CSV_PATH, PORT)
    client.stream_csv(delay_ms=TICK_DELAY_MS)


if __name__ == "__main__":
    main()
