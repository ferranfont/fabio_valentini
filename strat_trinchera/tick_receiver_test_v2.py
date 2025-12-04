"""
TEST VERSION - Recibe ticks y detecta BIG VOLUME (Orange Dot)
Usa la misma arquitectura de tick_server_trinchera_bidirect.py
"""

import socket
import threading
import time
import numpy as np
from datetime import datetime, timedelta
from collections import deque

# Configuration
TICK_SERVER_HOST = '127.0.0.1'
TICK_SERVER_PORT = 5555
DRAW_SERVER_PORT = 5557  # NEW: Port to send drawing commands to NinjaTrader

# Strategy parameters (from config_trinchera_live.py)
BIG_VOLUME_TRIGGER = 1        # Minimum volume to detect as "big volume"
BIG_VOLUME_TIMEOUT = 1        # Timeout in minutes for big volume effect
SMA_PERIOD = 10               # Simple Moving Average period
MEAN_REVERS_EXPAND = 3        # Points to expand mean reversion levels up/down
MEAN_REVERSE_TIMEOUT_TIMER = 5  # Seconds - Auto-remove drawings in NinjaTrader (controlled by NinjaTrader indicator)

# Global state
tick_count = 0
last_tick_time = None
price_buffer = deque(maxlen=SMA_PERIOD)
recent_volumes = deque(maxlen=100)
last_big_volume_time = None
current_sma = 0.0

# Drawing connection
draw_socket = None
draw_connected = False

def connect_to_draw_server(max_attempts=10, delay=2):
    """Connect to NinjaTrader drawing server with retry logic"""
    global draw_socket, draw_connected

    # Close old socket if exists
    if draw_socket is not None:
        try:
            draw_socket.close()
        except:
            pass
        draw_socket = None

    print(f"[DRAW] Attempting to connect to NinjaTrader on port {DRAW_SERVER_PORT}...")

    for attempt in range(max_attempts):
        try:
            draw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            draw_socket.connect((TICK_SERVER_HOST, DRAW_SERVER_PORT))
            draw_connected = True
            print(f"[DRAW] Connected successfully to NinjaTrader drawing server!")
            return True
        except Exception as e:
            print(f"[DRAW] Attempt {attempt+1}/{max_attempts} failed: {e}")
            if attempt < max_attempts - 1:
                print(f"[DRAW] Retrying in {delay} seconds...")
                time.sleep(delay)

    print(f"[DRAW] Failed to connect after {max_attempts} attempts")
    print(f"[DRAW] Make sure AAIndicatorTrinchera is added to the chart in NinjaTrader")
    draw_connected = False
    return False

def send_draw_command(orange_dot_price, buy_level, sell_level, signal_time=None):
    """Send drawing command to NinjaTrader with auto-reconnect"""
    global draw_socket, draw_connected

    if not draw_connected:
        print("[DRAW] Not connected, attempting to reconnect...")
        if not connect_to_draw_server(max_attempts=3, delay=1):
            print("[DRAW] Failed to reconnect, skipping draw command")
            return

    try:
        # Format: TIMESTAMP;ORANGE_PRICE;BUY_LEVEL;SELL_LEVEL
        # If no timestamp provided, use current time
        if signal_time is None:
            signal_time = datetime.now()

        timestamp_str = signal_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]  # Milliseconds
        command = f"{timestamp_str};{orange_dot_price:.2f};{buy_level:.2f};{sell_level:.2f}\n"
        draw_socket.sendall(command.encode('utf-8'))
        print(f"[DRAW] 🎯 Sent drawing command: {command.strip()}")
    except Exception as e:
        print(f"[DRAW] Error sending command: {e}")
        draw_connected = False

        # Try to reconnect once
        print("[DRAW] Connection lost, attempting to reconnect...")
        if connect_to_draw_server(max_attempts=3, delay=1):
            # Retry sending the command
            try:
                draw_socket.sendall(command.encode('utf-8'))
                print(f"[DRAW] 🎯 Reconnected and sent command: {command.strip()}")
            except Exception as e2:
                print(f"[DRAW] Failed to send after reconnect: {e2}")
        else:
            print("[DRAW] Reconnection failed")

def tick_receiver_thread():
    """Receives tick data from NinjaTrader (same architecture as bidirect)"""
    global tick_count, last_tick_time

    print(f"[TEST] Starting tick receiver on {TICK_SERVER_HOST}:{TICK_SERVER_PORT}")

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((TICK_SERVER_HOST, TICK_SERVER_PORT))
    server_socket.listen(1)

    print(f"[TEST] Waiting for NinjaTrader connection...")

    conn, addr = server_socket.accept()
    print(f"[TEST] NinjaTrader connected from {addr}")
    print()
    print("-" * 70)
    print("TIMESTAMP              | PRICE      | VOL | SIDE | BID        | ASK")
    print("-" * 70)

    buffer = ""

    while True:
        try:
            data = conn.recv(4096).decode('utf-8')
            if not data:
                print("[TEST] NinjaTrader disconnected. Reconnecting...")
                conn.close()
                conn, addr = server_socket.accept()
                print(f"[TEST] NinjaTrader reconnected from {addr}")
                continue

            buffer += data

            # Process complete messages (newline-separated)
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                process_tick_data(line.strip())

        except Exception as e:
            print(f"[TEST] Error receiving tick data: {e}")
            time.sleep(1)

def process_tick_data(tick_str):
    """Process incoming tick data and detect big volume"""
    global tick_count, last_tick_time, price_buffer, recent_volumes, last_big_volume_time, current_sma

    try:
        if not tick_str:
            return

        # Expected format: "TIMESTAMP;PRICE;VOLUME;SIDE;BID;ASK"
        parts = tick_str.split(';')

        if len(parts) != 6:
            return

        timestamp_str, price_str, volume_str, side, bid, ask = parts

        # Parse numeric values
        price = float(price_str)
        volume = int(volume_str)

        # Parse MARKET TIME (critical for consistent behavior in replay/backtest/live)
        try:
            tick_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S.%f')
        except ValueError:
            # Try without microseconds
            try:
                tick_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                # Fallback: use system time if parsing fails
                tick_time = datetime.now()

        tick_count += 1
        last_tick_time = tick_time  # Use MARKET time instead of system time

        # Update price buffer and calculate SMA
        price_buffer.append(price)
        if len(price_buffer) == SMA_PERIOD:
            current_sma = sum(price_buffer) / len(price_buffer)

        # Add to recent volumes
        recent_volumes.append(volume)

        # ====================================================================
        # BIG VOLUME DETECTION (ORANGE DOT)
        # ====================================================================
        if volume >= BIG_VOLUME_TRIGGER:
            # Check timeout (don't trigger if recent big volume already active)
            # USE MARKET TIME (tick_time) instead of datetime.now()
            if last_big_volume_time is None or \
               (tick_time - last_big_volume_time).total_seconds() / 60 >= BIG_VOLUME_TIMEOUT:

                last_big_volume_time = tick_time  # Store MARKET time

                # Calculate mean reversion levels
                orange_dot_price = price
                buy_level = orange_dot_price - MEAN_REVERS_EXPAND
                sell_level = orange_dot_price + MEAN_REVERS_EXPAND

                print()
                print("=" * 70)
                print(f"🔴 SIGNAL! BIG VOLUME DETECTED 🔴")
                print("=" * 70)
                print(f"Time:         {timestamp_str}")
                print(f"Orange Dot:   {orange_dot_price:.2f}")
                print(f"Volume:       {volume} (trigger: {BIG_VOLUME_TRIGGER})")
                print(f"BUY Level:    {buy_level:.2f}  (Orange - {MEAN_REVERS_EXPAND})")
                print(f"SELL Level:   {sell_level:.2f}  (Orange + {MEAN_REVERS_EXPAND})")
                if len(price_buffer) == SMA_PERIOD:
                    print(f"SMA({SMA_PERIOD}):      {current_sma:.2f}")
                print("=" * 70)
                print()

                # Send drawing command to NinjaTrader with signal timestamp
                send_draw_command(orange_dot_price, buy_level, sell_level, tick_time)

        # Print every 10 ticks
        if tick_count % 10 == 0:
            print(f"{timestamp_str} | {price:>10.2f} | {volume:>3} | {side:>4} | {float(bid):>10.2f} | {float(ask):>10.2f}")

        # Print summary every 100 ticks
        if tick_count % 100 == 0:
            print(f"\n[TEST] Total ticks: {tick_count}", end="")
            if len(price_buffer) == SMA_PERIOD:
                print(f" | SMA: {current_sma:.2f}", end="")
            print(f" | Last Price: {price:.2f}\n")
            print("-" * 70)
            print("TIMESTAMP              | PRICE      | VOL | SIDE | BID        | ASK")
            print("-" * 70)

    except Exception as e:
        print(f"[TEST] Error processing tick: {e}")

def main():
    print("=" * 70)
    print("TEST - TICK RECEIVER WITH BIG VOLUME DETECTION")
    print("=" * 70)
    print()
    print("Configuration:")
    print(f"  BIG_VOLUME_TRIGGER:          {BIG_VOLUME_TRIGGER}")
    print(f"  BIG_VOLUME_TIMEOUT:          {BIG_VOLUME_TIMEOUT} minutes")
    print(f"  SMA_PERIOD:                  {SMA_PERIOD}")
    print(f"  MEAN_REVERS_EXPAND:          {MEAN_REVERS_EXPAND} points")
    print(f"  MEAN_REVERSE_TIMEOUT_TIMER:  {MEAN_REVERSE_TIMEOUT_TIMER} seconds (NinjaTrader auto-remove)")
    print()
    print("Architecture:")
    print("  Port 5555: NinjaTrader -> Python (tick streaming)")
    print("  Port 5557: Python -> NinjaTrader (drawing commands)")
    print()
    print("IMPORTANT - Start order:")
    print("  1. Add AAIndicatorTrinchera to chart in NinjaTrader")
    print("  2. Enable AAStrategyTrinchera_TEST strategy")
    print("  3. Run this Python script")
    print()
    print("Press Ctrl+C to stop")
    print()
    print("-" * 70)

    # Connect to drawing server (NinjaTrader must be listening)
    connect_to_draw_server()

    # Start tick receiver thread
    receiver_thread = threading.Thread(target=tick_receiver_thread, daemon=True)
    receiver_thread.start()

    print("[TEST] RECEIVER STARTED")
    print("-" * 70)
    print()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[TEST] Stopped by user")
        print(f"[TEST] Total ticks received: {tick_count}")

if __name__ == "__main__":
    main()
