"""
DOM Depth Inspector - Inspect Market Profile at specific fractal points

This script reads the MAJOR fractals CSV, displays available fractals,
and allows inspection of DOM depth around a specific fractal using preview_tick_index.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import json
from datetime import timedelta, datetime
import glob
import os

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import rolling profile from strat_absortion
sys.path.insert(0, str(PROJECT_ROOT / "strat_absortion"))
from rolling_profile import RollingMarketProfile

# Use TkAgg backend for better compatibility
import matplotlib
matplotlib.use('TkAgg')
import mplcursors
import matplotlib.pyplot as plt
from matplotlib.widgets import Button, Slider

# ============ CONFIGURATION ============
# Default fractal to inspect (can be changed via parameter)
DEFAULT_FRACTAL_NUMBER = 0  # First fractal by default

# Inspection window
INSPECTION_DURATION = 120  # seconds (2 minutes)

# Profile shape detection configuration
PROFILE_WINDOW = 5  # Market profile rolling window in seconds
DENSITY_SHAPE = 0.70  # 70% of volume must be concentrated
MIN_PRICE_LEVELS = 10
MIN_BID_ASK_SIZE = 20
PRICE_POSITION_THRESHOLD = 0.25
DIFF_DISTANCE = 0
MIN_VOLUME = 10

# Directories
DATA_DIR = PROJECT_ROOT / "data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
# =======================================


def load_major_fractals() -> pd.DataFrame:
    """
    Load the most recent MAJOR fractals CSV file
    """
    pattern = str(OUTPUTS_DIR / "zig_zag_fractals_major_*.csv")
    fractal_files = glob.glob(pattern)

    if not fractal_files:
        print(f"[ERROR] No MAJOR fractal files found in {OUTPUTS_DIR}")
        return None

    # Get most recent file
    latest_file = max(fractal_files, key=os.path.getctime)
    print(f"[INFO] Loading MAJOR fractals from: {Path(latest_file).name}")

    # Load with European format
    df = pd.read_csv(latest_file, sep=';', decimal=',')

    print(f"[OK] Loaded {len(df)} MAJOR fractals")

    return df


def display_fractal_list(df_fractals: pd.DataFrame):
    """
    Display a formatted list of all fractals with their details
    """
    print("\n" + "="*80)
    print("AVAILABLE FRACTALS FOR INSPECTION")
    print("="*80)
    print(f"{'#':<4} {'Type':<8} {'Timestamp':<20} {'Price':<12} {'Preview Tick':<15}")
    print("-"*80)

    for idx, row in df_fractals.iterrows():
        fractal_type = row['type']
        timestamp = row['timestamp']
        price = row['price']
        preview_tick = row['preview_tick_index']

        print(f"{idx:<4} {fractal_type:<8} {timestamp:<20} {price:<12.2f} {preview_tick:<15}")

    print("="*80)
    print(f"\nTotal fractals: {len(df_fractals)}")
    print(f"Use fractal number (0-{len(df_fractals)-1}) to inspect a specific fractal")
    print("="*80 + "\n")


def load_dom_data(csv_path: Path, start_tick_index: int, duration_seconds: int) -> pd.DataFrame:
    """
    Load DOM data starting from a specific tick index for a given duration

    Args:
        csv_path: Path to the DOM CSV file
        start_tick_index: Tick index to start from
        duration_seconds: How many seconds of data to load

    Returns:
        DataFrame with DOM data
    """
    print(f"[INFO] Loading DOM data from tick index {start_tick_index}...")
    print(f"[INFO] Duration: {duration_seconds} seconds")

    # Read file line by line since JSON contains commas
    data_rows = []
    current_tick = 0

    with open(csv_path, 'r') as f:
        header = f.readline().strip()  # Skip header

        for line in f:
            # Only process ticks starting from start_tick_index
            if current_tick < start_tick_index:
                current_tick += 1
                continue

            # Split only on first 4 commas to get: Timestamp, Price, Size, Side
            parts = line.strip().split(',', 4)
            if len(parts) >= 5:
                timestamp = parts[0]
                price = float(parts[1])
                size = int(parts[2])
                side = parts[3]

                # Rest of line contains the two JSON objects
                rest = parts[4]

                # Find where first JSON ends (count braces)
                brace_count = 0
                split_idx = 0
                for i, char in enumerate(rest):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            split_idx = i + 1
                            break

                dom_bid_str = rest[:split_idx]
                dom_ask_str = rest[split_idx+1:]  # Skip comma between JSONs

                try:
                    dom_bid = json.loads(dom_bid_str)
                    dom_ask = json.loads(dom_ask_str)

                    data_rows.append({
                        'Timestamp': timestamp,
                        'Price': price,
                        'Size': size,
                        'Side': side,
                        'DOM_BID_parsed': dom_bid,
                        'DOM_ASK_parsed': dom_ask
                    })
                except json.JSONDecodeError as e:
                    print(f"[WARNING] Failed to parse JSON on tick {current_tick}, skipping: {e}")
                    current_tick += 1
                    continue

            current_tick += 1

            # Check if we have enough data (based on time)
            if len(data_rows) > 0:
                first_ts = pd.to_datetime(data_rows[0]['Timestamp'])
                last_ts = pd.to_datetime(data_rows[-1]['Timestamp'])
                elapsed = (last_ts - first_ts).total_seconds()

                if elapsed >= duration_seconds:
                    break

    print(f"[OK] Loaded {len(data_rows)} ticks")

    if len(data_rows) == 0:
        print("[ERROR] No data loaded. Check start_tick_index.")
        return None

    df = pd.DataFrame(data_rows)
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])

    print(f"[INFO] Time range: {df['Timestamp'].min()} to {df['Timestamp'].max()}")
    print(f"[INFO] Duration: {(df['Timestamp'].max() - df['Timestamp'].min()).total_seconds():.1f} seconds")

    return df


def inspect_fractal(fractal_number: int, df_fractals: pd.DataFrame):
    """
    Inspect a specific fractal by plotting its DOM depth

    Args:
        fractal_number: Index of the fractal to inspect (0-based)
        df_fractals: DataFrame with all fractals
    """
    if fractal_number < 0 or fractal_number >= len(df_fractals):
        print(f"[ERROR] Invalid fractal number. Must be between 0 and {len(df_fractals)-1}")
        return

    # Get fractal details
    fractal = df_fractals.iloc[fractal_number]

    print("\n" + "="*80)
    print(f"INSPECTING FRACTAL #{fractal_number}")
    print("="*80)
    print(f"Type:          {fractal['type']}")
    print(f"Timestamp:     {fractal['timestamp']}")
    print(f"Price:         {fractal['price']:.2f}")
    print(f"Preview Tick:  {fractal['preview_tick_index']}")
    print(f"Fractal Tick:  {fractal['fractal_tick_index']}")
    print("="*80 + "\n")

    # Get the preview tick index
    preview_tick_idx = int(fractal['preview_tick_index'])

    # Load DOM data starting from preview tick
    dom_csv_path = DATA_DIR / "ts_and_dom_24_oct.csv"
    if not dom_csv_path.exists():
        print(f"[ERROR] DOM data file not found: {dom_csv_path}")
        return

    df_dom = load_dom_data(dom_csv_path, preview_tick_idx, INSPECTION_DURATION)

    if df_dom is None or len(df_dom) == 0:
        print("[ERROR] Failed to load DOM data")
        return

    # Generate timestamps every 1 second for visualization
    start_time = df_dom["Timestamp"].min()
    end_time = df_dom["Timestamp"].max()
    timestamps = pd.date_range(start=start_time, end=end_time, freq="1s")

    # Pre-compute market profiles and order book snapshots
    print("[INFO] Computing market profiles...")
    profiles_data = []

    for i, ts in enumerate(timestamps):
        # Get tick data in the rolling window
        window_start = ts - timedelta(seconds=PROFILE_WINDOW)
        window_data = df_dom[(df_dom["Timestamp"] >= window_start) & (df_dom["Timestamp"] <= ts)]

        if window_data.empty:
            continue

        # Get last DOM snapshot in the window
        last_row = window_data.iloc[-1]
        dom_bid = last_row['DOM_BID_parsed']
        dom_ask = last_row['DOM_ASK_parsed']
        current_price = last_row['Price']

        # Create rolling market profile for this window using the updated API
        profile = RollingMarketProfile(window=timedelta(seconds=PROFILE_WINDOW))

        for _, tick in window_data.iterrows():
            profile.update(
                timestamp=tick['Timestamp'],
                price=tick['Price'],
                volume=tick['Size'],
                side=tick['Side']
            )

        volume_profile = profile.profile()
        poc = None
        if volume_profile:
            poc = max(volume_profile.items(), key=lambda item: item[1]["Total"])[0]

        profiles_data.append({
            'timestamp': ts,
            'dom_bid': dom_bid,
            'dom_ask': dom_ask,
            'current_price': current_price,
            'volume_profile': volume_profile,
            'poc': poc
        })

    print(f"[OK] Computed {len(profiles_data)} market profiles")

    # Create visualization
    plot_dom_depth_inspector(profiles_data, fractal, fractal_number)


def plot_dom_depth_inspector(profiles_data: list, fractal: pd.Series, fractal_number: int):
    """
    Plot DOM depth visualization for fractal inspection
    """
    print("[INFO] Creating visualization...")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10))
    plt.subplots_adjust(bottom=0.15, hspace=0.3)

    # State
    current_frame = [0]

    def update_plot(frame_idx):
        """Update the visualization for the current frame"""
        if frame_idx < 0 or frame_idx >= len(profiles_data):
            return

        data = profiles_data[frame_idx]
        timestamp = data['timestamp']
        dom_bid = data['dom_bid']
        dom_ask = data['dom_ask']
        current_price = data['current_price']
        volume_profile = data['volume_profile']
        poc = data['poc']

        # Clear axes
        ax1.clear()
        ax2.clear()

        # === TOP PANEL: DOM DEPTH ===
        if dom_bid and dom_ask:
            bid_prices = sorted([float(p) for p in dom_bid.keys()], reverse=True)
            ask_prices = sorted([float(p) for p in dom_ask.keys()])

            bid_sizes = [dom_bid[str(p)] for p in bid_prices]
            ask_sizes = [dom_ask[str(p)] for p in ask_prices]

            # Plot bars
            ax1.barh(bid_prices, bid_sizes, color='green', alpha=0.6, label='BID')
            ax1.barh(ask_prices, [-s for s in ask_sizes], color='red', alpha=0.6, label='ASK')

            # Current price line
            ax1.axhline(y=current_price, color='blue', linestyle='--', linewidth=2, label='Price')

        ax1.set_xlabel('Size', fontsize=10)
        ax1.set_ylabel('Price Level', fontsize=10)
        ax1.set_title(f'DOM Depth - Fractal #{fractal_number} ({fractal["type"]}) - {timestamp}', fontsize=12, fontweight='bold')
        ax1.legend(loc='upper right')
        ax1.grid(True, alpha=0.3)

        # === BOTTOM PANEL: MARKET PROFILE ===
        if volume_profile:
            prices = sorted(volume_profile.keys())
            bid_volumes = [volume_profile[p]['BID'] for p in prices]
            ask_volumes = [volume_profile[p]['ASK'] for p in prices]

            ax2.barh(prices, bid_volumes, color='green', alpha=0.6, label='BID Volume')
            ax2.barh(prices, [-v for v in ask_volumes], color='red', alpha=0.6, label='ASK Volume')

            # POC line
            if poc:
                ax2.axhline(y=poc, color='orange', linestyle='--', linewidth=2, label='POC')

            # Current price line
            ax2.axhline(y=current_price, color='blue', linestyle='--', linewidth=2, label='Price')

        ax2.set_xlabel('Volume', fontsize=10)
        ax2.set_ylabel('Price Level', fontsize=10)
        ax2.set_title(f'Market Profile ({PROFILE_WINDOW}s rolling window)', fontsize=12)
        ax2.legend(loc='upper right')
        ax2.grid(True, alpha=0.3)

        fig.canvas.draw_idle()

    # Navigation buttons
    def next_frame(event):
        if current_frame[0] < len(profiles_data) - 1:
            current_frame[0] += 1
            update_plot(current_frame[0])
            slider.set_val(current_frame[0])

    def prev_frame(event):
        if current_frame[0] > 0:
            current_frame[0] -= 1
            update_plot(current_frame[0])
            slider.set_val(current_frame[0])

    def on_slider_change(val):
        frame_idx = int(val)
        current_frame[0] = frame_idx
        update_plot(frame_idx)

    # Add buttons and slider
    ax_prev = plt.axes([0.2, 0.02, 0.1, 0.04])
    ax_next = plt.axes([0.7, 0.02, 0.1, 0.04])
    ax_slider = plt.axes([0.2, 0.08, 0.6, 0.03])

    btn_prev = Button(ax_prev, 'Previous')
    btn_prev.on_clicked(prev_frame)

    btn_next = Button(ax_next, 'Next')
    btn_next.on_clicked(next_frame)

    slider = Slider(ax_slider, 'Frame', 0, len(profiles_data) - 1, valinit=0, valstep=1)
    slider.on_changed(on_slider_change)

    # Initial plot
    update_plot(0)

    plt.show()

    print("[OK] Visualization closed")


def main():
    """
    Main execution function
    """
    print("="*80)
    print("DOM DEPTH INSPECTOR - Fractal Analysis Tool")
    print("="*80)

    # Load MAJOR fractals
    df_fractals = load_major_fractals()

    if df_fractals is None or len(df_fractals) == 0:
        print("[ERROR] No fractals found. Run main_find_fractals.py first.")
        return

    # Display fractal list
    display_fractal_list(df_fractals)

    # Get fractal number from command line or use default
    fractal_number = DEFAULT_FRACTAL_NUMBER

    if len(sys.argv) > 1:
        try:
            fractal_number = int(sys.argv[1])
            print(f"[INFO] Using fractal number from command line: {fractal_number}")
        except ValueError:
            print(f"[WARNING] Invalid fractal number argument. Using default: {DEFAULT_FRACTAL_NUMBER}")

    print(f"\n[INFO] Inspecting fractal #{fractal_number}...")

    # Inspect the selected fractal
    inspect_fractal(fractal_number, df_fractals)


if __name__ == "__main__":
    main()
