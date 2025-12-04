"""
CLEAN VERSION - Receives ticks from NinjaTrader and sends "orange_dot" signal
Simple architecture:
  - Receives ticks on port 5555
  - Sends signals on port 5556
"""

import socket
import threading
import time
from datetime import datetime

# Configuration
TICK_RECEIVE_PORT = 5555  # Receive ticks from NinjaTrader
SIGNAL_SEND_PORT = 5556   # Send signals to NinjaTrader indicator
HOST = '127.0.0.1'

# Signal trigger (example: every 10 ticks)
SIGNAL_EVERY_N_TICKS = 10

# Global state
tick_count = 0
signal_socket = None
signal_connected = False


def connect_signal_sender(max_attempts=10, delay=2):
    """Connect to NinjaTrader indicator to send signals (with retry)"""
    global signal_socket, signal_connected

    print(f"[SIGNAL] Connecting to NinjaTrader indicator on port {SIGNAL_SEND_PORT}...")

    for attempt in range(max_attempts):
        try:
            signal_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            signal_socket.connect((HOST, SIGNAL_SEND_PORT))
            signal_connected = True
            print(f"[SIGNAL] ✓ CONNECTED to NinjaTrader indicator!")
            return True
        except Exception as e:
            print(f"[SIGNAL] Attempt {attempt+1}/{max_attempts} failed: {e}")
            if attempt < max_attempts - 1:
                print(f"[SIGNAL] Retrying in {delay} seconds...")
                time.sleep(delay)

    print(f"[SIGNAL] Failed to connect after {max_attempts} attempts")
    print(f"[SIGNAL] Make sure AAIndicatorTrinchera_Draw is added to the chart first")
    signal_connected = False
    return False


def send_signal(signal_text):
    """Send signal to NinjaTrader indicator"""
    global signal_socket, signal_connected

    if not signal_connected:
        return

    try:
        message = f"{signal_text}\n"
        signal_socket.sendall(message.encode('utf-8'))
        print(f"[SIGNAL] Sent: {signal_text}")
    except Exception as e:
        print(f"[SIGNAL] Send error: {e}")
        signal_connected = False


def tick_receiver_thread():
    """Connect to NinjaTrader indicator to receive ticks (CLIENT MODE)"""
    global tick_count

    print(f"[TICKS] Connecting to NinjaTrader indicator on port {TICK_RECEIVE_PORT}...")

    # CLIENTE: Conectarse a NinjaTrader (que es SERVIDOR en 5555)
    for attempt in range(10):
        try:
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.connect((HOST, TICK_RECEIVE_PORT))
            print(f"[TICKS] ✓ CONNECTED to NinjaTrader for receiving ticks!")
            break
        except Exception as e:
            print(f"[TICKS] Attempt {attempt+1}/10 failed: {e}")
            if attempt < 9:
                print(f"[TICKS] Retrying in 2 seconds...")
                time.sleep(2)
            else:
                print(f"[TICKS] Failed to connect to NinjaTrader tick sender")
                return
    print()
    print("-" * 60)
    print("TIMESTAMP              | PRICE")
    print("-" * 60)

    buffer = ""

    while True:
        try:
            data = conn.recv(4096).decode('utf-8')
            if not data:
                print("[TICKS] NinjaTrader disconnected.")
                break  # Exit and let the thread end

            buffer += data

            # Process complete messages (newline-separated)
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                process_tick(line.strip())

        except Exception as e:
            print(f"[TICKS] Error receiving: {e}")
            time.sleep(1)


def process_tick(tick_str):
    """Process incoming tick and trigger signals"""
    global tick_count

    try:
        if not tick_str:
            return

        # Expected format: "TIMESTAMP;PRICE"
        parts = tick_str.split(';')

        if len(parts) < 2:
            return

        timestamp_str = parts[0]
        price = float(parts[1])

        tick_count += 1

        # Print every 10 ticks
        if tick_count % 10 == 0:
            print(f"{timestamp_str} | {price:>10.2f}")

        # TRIGGER SIGNAL: Send "orange_dot" every N ticks
        if tick_count % SIGNAL_EVERY_N_TICKS == 0:
            print()
            print("=" * 60)
            print(f"SIGNAL TRIGGERED! (Tick #{tick_count})")
            print(f"Price: {price:.2f}")
            print("=" * 60)
            print()

            send_signal("orange_dot")

        # Print summary every 100 ticks
        if tick_count % 100 == 0:
            print(f"\n[TICKS] Total received: {tick_count}\n")
            print("-" * 60)
            print("TIMESTAMP              | PRICE")
            print("-" * 60)

    except Exception as e:
        print(f"[TICKS] Processing error: {e}")


def main():
    print("=" * 60)
    print("TICK RECEIVER V3 - CLEAN VERSION")
    print("=" * 60)
    print()
    print("Configuration:")
    print(f"  TICK_RECEIVE_PORT:  {TICK_RECEIVE_PORT}")
    print(f"  SIGNAL_SEND_PORT:   {SIGNAL_SEND_PORT}")
    print(f"  SIGNAL_TRIGGER:     Every {SIGNAL_EVERY_N_TICKS} ticks")
    print()
    print("Architecture:")
    print("  Port 5555: NinjaTrader (SERVER) -> Python (CLIENT) for ticks")
    print("  Port 5556: Python (CLIENT) -> NinjaTrader (SERVER) for signals")
    print()
    print("Start order:")
    print("  1. Add AAIndicatorTrinchera_Draw to chart in NinjaTrader")
    print("  2. Run this Python script (will connect to both ports)")
    print()
    print("NO NEED FOR STRATEGY - Indicator handles everything!")
    print()
    print("Press Ctrl+C to stop")
    print()
    print("-" * 60)

    # Connect to indicator (NinjaTrader must be listening)
    connect_signal_sender()

    # Start tick receiver thread
    receiver_thread = threading.Thread(target=tick_receiver_thread, daemon=True)
    receiver_thread.start()

    print("[SYSTEM] Receiver started")
    print("-" * 60)
    print()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[SYSTEM] Stopped by user")
        print(f"[SYSTEM] Total ticks received: {tick_count}")


if __name__ == "__main__":
    main()
