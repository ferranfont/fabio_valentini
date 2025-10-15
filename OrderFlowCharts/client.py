"""
OrderFlow Client - Reads CSV and sends ticks to server
Supports velocity control to speed up/slow down playback
"""

import pandas as pd
import requests
import time
import argparse
from datetime import datetime

# Configuration
SERVER_URL = 'http://localhost:8765'
DEFAULT_VELOCITY = 10  # 10x faster than real-time

def send_tick(tick_data):
    """Send a single tick to the server"""
    try:
        response = requests.post(f'{SERVER_URL}/tick', json=tick_data, timeout=5)
        return response.status_code == 200
    except Exception as e:
        print(f"Error sending tick: {e}")
        return False

def reset_server():
    """Reset server data"""
    try:
        response = requests.post(f'{SERVER_URL}/reset', timeout=5)
        return response.status_code == 200
    except Exception as e:
        print(f"Error resetting server: {e}")
        return False

def stream_csv(csv_file, velocity=DEFAULT_VELOCITY, start_from=0, max_ticks=None):
    """
    Stream CSV data to server with velocity control

    Args:
        csv_file: Path to CSV file
        velocity: Speed multiplier (10 = 10x faster, 0.5 = half speed)
        start_from: Skip first N rows
        max_ticks: Maximum number of ticks to send (None = all)
    """
    print(f"Loading tick data from {csv_file}...")

    # Read CSV with European format
    df = pd.read_csv(
        csv_file,
        sep=';',
        decimal=',',
        parse_dates=['Timestamp']
    )

    print(f"Loaded {len(df):,} ticks")
    print(f"Date range: {df['Timestamp'].min()} to {df['Timestamp'].max()}")
    print(f"Velocity: {velocity}x")
    print(f"Starting from row: {start_from}")

    # Skip rows if requested
    if start_from > 0:
        df = df.iloc[start_from:]
        print(f"Skipped first {start_from} rows, {len(df):,} ticks remaining")

    # Limit ticks if requested
    if max_ticks is not None:
        df = df.head(max_ticks)
        print(f"Limited to {max_ticks} ticks")

    # Calculate time deltas between ticks
    df['TimeDelta'] = df['Timestamp'].diff().dt.total_seconds()

    # First tick has no delta, use 0
    df.loc[df.index[0], 'TimeDelta'] = 0

    print(f"\nConnecting to server at {SERVER_URL}...")

    # Test connection
    try:
        response = requests.get(f'{SERVER_URL}/stats', timeout=5)
        if response.status_code != 200:
            print("ERROR: Server not responding!")
            return
    except Exception as e:
        print(f"ERROR: Cannot connect to server: {e}")
        print(f"Make sure the server is running: python server.py")
        return

    print("Connected to server successfully!")
    print("\nStarting data stream...")
    print("Press Ctrl+C to stop\n")

    ticks_sent = 0
    errors = 0
    start_time = time.time()

    try:
        for idx, row in df.iterrows():
            # Calculate delay with velocity applied
            if ticks_sent > 0:
                real_delay = row['TimeDelta']
                adjusted_delay = real_delay / velocity

                # Sleep for the adjusted delay
                if adjusted_delay > 0:
                    time.sleep(adjusted_delay)

            # Prepare tick data
            tick_data = {
                'Timestamp': row['Timestamp'].isoformat(),
                'Precio': str(row['Precio']),  # Keep as string to preserve format
                'Volumen': int(row['Volumen']),
                'Lado': row['Lado'],
                'Bid': str(row['Bid']),
                'Ask': str(row['Ask'])
            }

            # Send to server
            success = send_tick(tick_data)

            if success:
                ticks_sent += 1

                # Print progress every 100 ticks
                if ticks_sent % 100 == 0:
                    elapsed = time.time() - start_time
                    rate = ticks_sent / elapsed
                    print(f"Sent {ticks_sent:,} ticks | Rate: {rate:.1f} ticks/sec | "
                          f"Time: {row['Timestamp']} | Price: {row['Precio']}")
            else:
                errors += 1
                if errors > 10:
                    print("Too many errors, stopping...")
                    break

    except KeyboardInterrupt:
        print("\n\nStopped by user")

    # Final statistics
    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"STREAMING COMPLETE")
    print(f"{'='*60}")
    print(f"Ticks sent: {ticks_sent:,}")
    print(f"Errors: {errors}")
    print(f"Elapsed time: {elapsed:.1f} seconds")
    print(f"Average rate: {ticks_sent/elapsed:.1f} ticks/sec")
    print(f"{'='*60}")

def main():
    global SERVER_URL

    parser = argparse.ArgumentParser(description='OrderFlow Client - Stream tick data to server')
    parser.add_argument('csv_file', help='Path to CSV file with tick data')
    parser.add_argument('--velocity', '-v', type=float, default=DEFAULT_VELOCITY,
                        help=f'Playback speed multiplier (default: {DEFAULT_VELOCITY}x)')
    parser.add_argument('--start-from', '-s', type=int, default=0,
                        help='Skip first N rows (default: 0)')
    parser.add_argument('--max-ticks', '-m', type=int, default=None,
                        help='Maximum number of ticks to send (default: all)')
    parser.add_argument('--reset', '-r', action='store_true',
                        help='Reset server data before starting')
    parser.add_argument('--server', type=str, default=SERVER_URL,
                        help=f'Server URL (default: {SERVER_URL})')

    args = parser.parse_args()

    # Update server URL if specified
    SERVER_URL = args.server

    print("="*60)
    print("OrderFlow Client")
    print("="*60)

    # Reset server if requested
    if args.reset:
        print("Resetting server data...")
        if reset_server():
            print("Server reset successfully!")
        else:
            print("WARNING: Failed to reset server")
        print()

    # Stream the data
    stream_csv(
        args.csv_file,
        velocity=args.velocity,
        start_from=args.start_from,
        max_ticks=args.max_ticks
    )

if __name__ == '__main__':
    main()
