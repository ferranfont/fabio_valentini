"""
Inspector DOM Deep - Inspect individual MAJOR fractals with DOM depth visualization

Usage:
    python strat_fractal/inspector_dom_deep.py <fractal_index>

Example:
    python strat_fractal/inspector_dom_deep.py 0  # Inspect first MAJOR fractal
    python strat_fractal/inspector_dom_deep.py 5  # Inspect 6th MAJOR fractal
"""

import sys
import pandas as pd
import numpy as np
import json
from datetime import timedelta
from pathlib import Path
import glob
import os
# Rolling profile
sys.path.insert(0, str(Path(__file__).parent.parent / 'strat_absortion'))
from rolling_profile import RollingMarketProfile
# Matplotlib setup
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.widgets import Button, Slider

# ============================================================================
# CONFIGURATION
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
DATA_DIR = PROJECT_ROOT / "data"

DATA_FILE = "ts_and_dom_24_oct.csv"
PROFILE_WINDOW = 5  # seconds

# Profile shape detection (copied from plot_dom_deep.py)
DENSITY_SHAPE = 0.70
MIN_PRICE_LEVELS = 10
MIN_BID_ASK_SIZE = 20
PRICE_POSITION_THRESHOLD = 0.25
DIFF_DISTANCE = 0
MIN_VOLUME = 10

# ============================================================================
# HELPER FUNCTIONS (copied from plot_dom_deep.py)
# ============================================================================

def evaluate_profile_shape(profile, current_close=None, previous_close=None):
    """
    Evaluate the distribution shape of a market profile with STRICT criteria.
    Returns: 'd_shape', 'p_shape', or 'balanced'
    """
    if not profile or current_close is None or previous_close is None:
        return 'balanced'

    # Check minimum price difference
    price_diff = abs(current_close - previous_close)
    if price_diff < DIFF_DISTANCE:
        return 'balanced'

    # Filter active prices
    active_prices = []
    for price in sorted(profile.keys()):
        bid_vol = profile[price].get('BID', 0)
        ask_vol = profile[price].get('ASK', 0)
        if bid_vol > 0 or ask_vol > 0:
            active_prices.append(price)

    # Minimum price levels
    if len(active_prices) < MIN_PRICE_LEVELS:
        return 'balanced'

    # Total volumes
    total_bid = sum(profile[p].get('BID', 0) for p in active_prices)
    total_ask = sum(profile[p].get('ASK', 0) for p in active_prices)
    total_volume = total_bid + total_ask

    if total_volume < MIN_VOLUME:
        return 'balanced'

    # Price range
    min_price = min(active_prices)
    max_price = max(active_prices)
    price_range = max_price - min_price

    if price_range == 0:
        return 'balanced'

    # Price position (0 = bottom, 1 = top)
    price_position = (current_close - min_price) / price_range

    # Split into halves
    mid_point = len(active_prices) // 2
    lower_prices = active_prices[:mid_point + (1 if len(active_prices) % 2 == 1 else 0)]
    upper_prices = active_prices[mid_point:]

    # Calculate volumes
    lower_bid = sum(profile[p].get('BID', 0) for p in lower_prices)
    upper_ask = sum(profile[p].get('ASK', 0) for p in upper_prices)

    max_lower_bid = max([profile[p].get('BID', 0) for p in lower_prices]) if lower_prices else 0
    max_upper_ask = max([profile[p].get('ASK', 0) for p in upper_prices]) if upper_prices else 0

    # Check d_shape
    if total_bid > 0:
        is_d_shape = (
            max_lower_bid >= MIN_BID_ASK_SIZE and
            lower_bid / total_bid >= DENSITY_SHAPE and
            price_position <= PRICE_POSITION_THRESHOLD and
            current_close < previous_close
        )
        if is_d_shape:
            return 'd_shape'

    # Check p_shape
    if total_ask > 0:
        is_p_shape = (
            max_upper_ask >= MIN_BID_ASK_SIZE and
            upper_ask / total_ask >= DENSITY_SHAPE and
            price_position >= (1 - PRICE_POSITION_THRESHOLD) and
            current_close > previous_close
        )
        if is_p_shape:
            return 'p_shape'

    return 'balanced'


def plot_single_merged(ax, timestamp, profile, closing_price, dom_bid, dom_ask,
                       previous_close=None, title_prefix="", common_prices=None,
                       show_ylabel=True):
    """Plot a single merged DOM + Market Profile panel (copied from plot_dom_deep.py)"""
    ax.clear()

    # Get profile price range
    if profile:
        profile_prices = sorted(profile.keys())
        profile_high = profile_prices[-1] if profile_prices else None
        profile_low = profile_prices[0] if profile_prices else None
    else:
        profile_high = None
        profile_low = None
        profile_prices = []

    # Check data
    if not dom_bid and not dom_ask:
        ax.text(0.5, 0.5, "No order book data", ha='center', va='center', fontsize=14)
        ax.set_title(f"{title_prefix}{timestamp}")
        return

    # Calculate continuous price range
    tick_size = 0.25

    if common_prices is not None:
        all_prices = common_prices
    else:
        if profile_high is not None and profile_low is not None:
            lower_limit = profile_low - (3 * tick_size)
            upper_limit = profile_high + (3 * tick_size)
        else:
            all_dom_prices = [float(p) for p in set(list(dom_bid.keys()) + list(dom_ask.keys()))]
            if not all_dom_prices:
                ax.text(0.5, 0.5, "No order book data", ha='center', va='center', fontsize=14)
                return
            lower_limit = min(all_dom_prices)
            upper_limit = max(all_dom_prices)

        if closing_price is not None:
            lower_limit = min(lower_limit, closing_price)
            upper_limit = max(upper_limit, closing_price)

        # Generate continuous price levels
        all_prices = []
        current = lower_limit
        while current <= upper_limit:
            all_prices.append(round(current, 2))
            current += tick_size

    if not all_prices:
        ax.text(0.5, 0.5, "No price data in range", ha='center', va='center', fontsize=14)
        return

    y_positions = range(len(all_prices))

    # Prepare DOM sizes
    dom_bid_sizes = []
    dom_ask_sizes = []
    for price in all_prices:
        price_str = str(price)
        price_str_alt = f"{price:.2f}"

        bid_size = dom_bid.get(price_str, 0)
        if bid_size == 0:
            bid_size = dom_bid.get(price_str_alt, 0)

        ask_size = dom_ask.get(price_str, 0)
        if ask_size == 0:
            ask_size = dom_ask.get(price_str_alt, 0)

        dom_bid_sizes.append(bid_size)
        dom_ask_sizes.append(ask_size)

    # Max DOM size
    max_dom_size = max(
        max(dom_bid_sizes) if dom_bid_sizes else 1,
        max(dom_ask_sizes) if dom_ask_sizes else 1
    )

    # Plot ORDER BOOK bars (grey)
    bid_color_dom = '#999999'
    ask_color_dom = '#aaaaaa'

    max_bid_idx = dom_bid_sizes.index(max(dom_bid_sizes)) if dom_bid_sizes and max(dom_bid_sizes) > 0 else None
    max_ask_idx = dom_ask_sizes.index(max(dom_ask_sizes)) if dom_ask_sizes and max(dom_ask_sizes) > 0 else None

    # BID bars
    for i, size in enumerate(dom_bid_sizes):
        if size > 0:
            edgecolor = 'black' if i == max_bid_idx else 'none'
            linewidth = 2 if i == max_bid_idx else 0
            ax.barh(y_positions[i], -size, height=0.8,
                    color=bid_color_dom, edgecolor=edgecolor,
                    linewidth=linewidth, alpha=0.3, zorder=1)

    # ASK bars
    for i, size in enumerate(dom_ask_sizes):
        if size > 0:
            edgecolor = 'black' if i == max_ask_idx else 'none'
            linewidth = 2 if i == max_ask_idx else 0
            ax.barh(y_positions[i], size, height=0.8,
                    color=ask_color_dom, edgecolor=edgecolor,
                    linewidth=linewidth, alpha=0.3, zorder=1)

    # Overlay MARKET PROFILE bars (red/green)
    if profile:
        mp_bid_volumes = []
        mp_ask_volumes = []

        for price in all_prices:
            if price in profile:
                mp_bid_volumes.append(profile[price]["BID"])
                mp_ask_volumes.append(profile[price]["ASK"])
            else:
                mp_bid_volumes.append(0)
                mp_ask_volumes.append(0)

        # Scale to DOM
        max_mp_volume = max(
            max(mp_bid_volumes) if mp_bid_volumes else 1,
            max(mp_ask_volumes) if mp_ask_volumes else 1
        )

        scale_factor = (max_dom_size * 0.7) / max_mp_volume if max_mp_volume > 0 else 1
        mp_bid_scaled = [v * scale_factor for v in mp_bid_volumes]
        mp_ask_scaled = [v * scale_factor for v in mp_ask_volumes]

        bid_color_mp = (0.8, 0, 0, 0.8)  # Red
        ask_color_mp = (0, 0.7, 0, 0.8)  # Green

        ax.barh(y_positions, [-v for v in mp_bid_scaled], height=0.6,
                color=bid_color_mp, label='Profile BID', edgecolor='darkred',
                linewidth=0.5, zorder=10)
        ax.barh(y_positions, mp_ask_scaled, height=0.6,
                color=ask_color_mp, label='Profile ASK', edgecolor='darkgreen',
                linewidth=0.5, zorder=10)

    # Y-axis labels with thousand separator (dot)
    if show_ylabel:
        filtered_ticks = []
        filtered_labels = []
        for i, price in enumerate(all_prices):
            if price == int(price):
                filtered_ticks.append(i)
                # Format with dot as thousand separator: 25378 -> 25.378
                price_str = f"{int(price):,}".replace(',', '.')
                filtered_labels.append(price_str)

        ax.set_yticks(filtered_ticks)
        ax.set_yticklabels(filtered_labels, fontsize=6)
    else:
        ax.set_yticks([])
        ax.set_yticklabels([])

    # Vertical line at zero
    ax.axvline(x=0, color='black', linewidth=1.5, linestyle='-', alpha=0.7, zorder=2)

    # Evaluate shape
    profile_tag = evaluate_profile_shape(profile, closing_price, previous_close)

    # Dot color
    if profile_tag == 'd_shape':
        dot_color = 'red'
        dot_edge_color = 'darkred'
    elif profile_tag == 'p_shape':
        dot_color = 'green'
        dot_edge_color = 'darkgreen'
    else:
        dot_color = 'blue'
        dot_edge_color = 'darkblue'

    # Mark current price
    if closing_price and closing_price in all_prices:
        price_idx = all_prices.index(closing_price)
        ax.axhline(y=price_idx, color='blue', linewidth=1, linestyle='--', alpha=0.6, zorder=25)
        ax.plot(0, price_idx, 'o', color=dot_color, markersize=10, zorder=30,
                markeredgecolor=dot_edge_color, markeredgewidth=2)

    # X-axis limits
    ax.set_xlim(-max_dom_size * 1.1, max_dom_size * 1.1)

    # Title
    close_str = f' | Close: {closing_price:.2f}' if closing_price is not None else ''
    ax.set_title(f'{title_prefix}{timestamp.strftime("%H:%M:%S")}{close_str}',
                 fontsize=10, fontweight='bold', pad=10)

    # Grid
    ax.grid(True, alpha=0.3, axis='x')

    # Stats box
    total_dom_bid = sum(dom_bid_sizes)
    total_dom_ask = sum(dom_ask_sizes)

    stats_lines = []
    stats_lines.append(f'DOM BID: {total_dom_bid:.0f}')
    stats_lines.append(f'DOM ASK: {total_dom_ask:.0f}')

    if profile:
        total_mp_bid = sum(mp_bid_volumes)
        total_mp_ask = sum(mp_ask_volumes)
        stats_lines.append(f'Profile BID: {total_mp_bid:.0f}')
        stats_lines.append(f'Profile ASK: {total_mp_ask:.0f}')
        stats_lines.append(f'BID/ASK: {total_mp_bid/total_mp_ask if total_mp_ask > 0 else 0:.2f}')

    if previous_close is not None and closing_price is not None:
        price_change = closing_price - previous_close
        stats_lines.append(f'Change: {price_change:.2f}')
    else:
        stats_lines.append(f'Change: N/A')

    if profile:
        total_volume = total_mp_bid + total_mp_ask
        stats_lines.append(f'Volume: {total_volume:.0f}')

    stats_text = '\n'.join(stats_lines)

    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
            fontsize=9, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
            color='black')

    # Pattern label
    if profile_tag == 'd_shape':
        label_color = 'red'
        label_text = 'd-Shape'
    elif profile_tag == 'p_shape':
        label_color = 'green'
        label_text = 'p-Shape'
    else:
        label_color = '#C0C0C0'
        label_text = 'Balanced'

    ax.text(0.02, 0.02, label_text, transform=ax.transAxes,
            fontsize=10, verticalalignment='bottom', horizontalalignment='left',
            color=label_color, fontweight='bold')

    return all_prices


def plot_price_line(ax_price, profiles_data, current_index, fractal_timestamp=None):
    """Plot price line chart with signals"""
    ax_price.clear()

    # Show last 200 frames
    start_idx = max(0, current_index - 200)
    historical_data = profiles_data[start_idx:current_index + 1]

    # Extract timestamps and prices
    times = []
    prices = []
    for ts, _, close_price, _, _ in historical_data:
        if close_price is not None:
            times.append(ts)
            prices.append(close_price)

    if len(prices) > 0:
        # Price line (grey)
        ax_price.plot(times, prices, color='grey', linewidth=1, alpha=0.8)

        # Mark T-4, T-3, T-2, T-1
        frame_indices = [
            max(0, current_index - 4),
            max(0, current_index - 3),
            max(0, current_index - 2),
            max(0, current_index - 1),
        ]

        for frame_idx in frame_indices:
            if frame_idx < len(profiles_data):
                ts_marker, _, close_marker, _, _ = profiles_data[frame_idx]
                if close_marker is not None:
                    ax_price.plot(ts_marker, close_marker, 'o', color='grey',
                                 markersize=5, alpha=0.6, zorder=4)

        # Collect signals
        d_shape_times, d_shape_prices = [], []
        p_shape_times, p_shape_prices = [], []

        for hist_idx in range(start_idx, current_index + 1):
            if hist_idx < len(profiles_data):
                ts_sig, profile_sig, close_sig, _, _ = profiles_data[hist_idx]

                if close_sig is not None and profile_sig:
                    previous_close_sig = None
                    if hist_idx > 0 and hist_idx - 1 < len(profiles_data):
                        _, _, previous_close_sig, _, _ = profiles_data[hist_idx - 1]

                    shape = evaluate_profile_shape(profile_sig, close_sig, previous_close_sig)

                    if shape == 'd_shape':
                        d_shape_times.append(ts_sig)
                        d_shape_prices.append(close_sig)
                    elif shape == 'p_shape':
                        p_shape_times.append(ts_sig)
                        p_shape_prices.append(close_sig)

        # Plot signals
        if d_shape_times:
            ax_price.scatter(d_shape_times, d_shape_prices, color='red', s=30,
                           marker='o', alpha=0.7, zorder=5, label='d-Shape')

        if p_shape_times:
            ax_price.scatter(p_shape_times, p_shape_prices, color='lime', s=30,
                           marker='o', alpha=0.7, zorder=5, label='p-Shape')

        # Mark CURRENT frame with large blue circle (NO LABEL)
        if current_index < len(profiles_data):
            ts_current, _, close_current, _, _ = profiles_data[current_index]
            if close_current is not None:
                ax_price.plot(ts_current, close_current, 'o', color='blue',
                             markersize=12, markeredgecolor='darkblue',
                             markeredgewidth=2, zorder=10)

    # Add vertical dashed line at fractal timestamp (if provided)
    if fractal_timestamp is not None:
        ax_price.axvline(x=fractal_timestamp, color='blue', linestyle='--',
                        linewidth=1, alpha=0.5, zorder=3)

    # Labels
    # NO x-axis label, NO y-axis label
    ax_price.grid(True, alpha=0.3)
    ax_price.legend(loc='upper left', fontsize=8)

    # Format axes
    ax_price.tick_params(axis='x', labelsize=8, rotation=0)  # No rotation
    ax_price.tick_params(axis='y', labelsize=8)

    # Disable scientific notation on y-axis only (x-axis is datetime)
    ax_price.ticklabel_format(style='plain', axis='y', useOffset=False)

    return ax_price


# ============================================================================
# MAIN LOGIC
# ============================================================================

def load_fractal_list():
    """Load the most recent MAJOR fractals CSV"""
    pattern = str(OUTPUTS_DIR / "zig_zag_fractals_major_*.csv")
    files = glob.glob(pattern)

    if not files:
        print(f"[ERROR] No MAJOR fractal files found in {OUTPUTS_DIR}")
        sys.exit(1)

    latest_file = max(files, key=os.path.getctime)
    print(f"[INFO] Loading MAJOR fractals from: {Path(latest_file).name}")

    df = pd.read_csv(latest_file, sep=';', decimal=',')
    print(f"[OK] Loaded {len(df)} MAJOR fractals")

    return df


def load_tick_data_window(preview_tick_index, fractal_tick_index, num_minutes_after=1):
    """
    Load tick data window around fractal

    Args:
        preview_tick_index: Starting tick index (already 1 minute before fractal)
        fractal_tick_index: Exact fractal tick index
        num_minutes_after: Minutes to load after fractal (default 1)
    """
    csv_path = DATA_DIR / DATA_FILE
    print(f"[INFO] Loading tick data from: {csv_path.name}")

    # Calculate ticks to load after fractal (approx 60 ticks per second = 3600 per minute)
    ticks_after_fractal = int(60 * 60 * num_minutes_after)

    # Read file line by line (JSON parsing)
    data_rows = []
    with open(csv_path, 'r') as f:
        header = f.readline().strip()

        current_tick_idx = 0
        target_start = preview_tick_index
        target_end = fractal_tick_index + ticks_after_fractal  # 1 minute before + fractal + 1 minute after

        for line in f:
            if current_tick_idx < target_start:
                current_tick_idx += 1
                continue

            if current_tick_idx >= target_end:
                break

            parts = line.strip().split(',', 4)
            if len(parts) >= 5:
                timestamp = parts[0]
                price = float(parts[1])
                size = int(parts[2])
                side = parts[3]
                rest = parts[4]

                # Parse JSON
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
                dom_ask_str = rest[split_idx+1:]

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
                except json.JSONDecodeError:
                    pass

            current_tick_idx += 1

    print(f"[OK] Loaded {len(data_rows)} ticks")

    df = pd.DataFrame(data_rows)
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])

    return df


def precompute_profiles(df):
    """Pre-compute market profiles for every second"""
    start_time = df["Timestamp"].min()
    end_time = df["Timestamp"].max()
    timestamps = pd.date_range(start=start_time, end=end_time, freq="1s")

    print(f"[INFO] Pre-computing {len(timestamps)} profiles...")

    profiles_data = []

    for i, ts in enumerate(timestamps):
        if i % 20 == 0:
            print(f"  Processing {i}/{len(timestamps)}...")

        mp = RollingMarketProfile(window=timedelta(seconds=PROFILE_WINDOW))
        ticks_until = df[df["Timestamp"] <= ts]

        if len(ticks_until) > 0:
            last_row = ticks_until.iloc[-1]
            closing_price = float(last_row["Price"])
            dom_bid = last_row["DOM_BID_parsed"]
            dom_ask = last_row["DOM_ASK_parsed"]
        else:
            closing_price = None
            dom_bid = {}
            dom_ask = {}

        for _, row in ticks_until.iterrows():
            mp.update(row["Timestamp"], row["Price"], row["Size"], row["Side"])

        profile = mp.profile()
        profiles_data.append((ts, profile, closing_price, dom_bid, dom_ask))

    print(f"[OK] Pre-computed {len(profiles_data)} profiles")

    return profiles_data


def load_and_inspect_fractal(fractal_idx, df_fractals):
    """Load and display a specific fractal"""
    if fractal_idx < 0 or fractal_idx >= len(df_fractals):
        print(f"[ERROR] Fractal index {fractal_idx} out of range (0 to {len(df_fractals) - 1})")
        return None

    # Get fractal info
    fractal = df_fractals.iloc[fractal_idx]
    preview_tick_index = int(fractal['preview_tick_index'])
    fractal_tick_index = int(fractal['fractal_tick_index'])
    fractal_price = float(fractal['price'])
    fractal_type = fractal['type']
    fractal_timestamp_str = fractal['timestamp']

    # Convert timestamp to datetime object
    fractal_timestamp = pd.to_datetime(fractal_timestamp_str)

    print(f"\n[INFO] Inspecting MAJOR Fractal #{fractal_idx}")
    print(f"  Type: {fractal_type}")
    print(f"  Price: {fractal_price:.2f}")
    print(f"  Timestamp: {fractal_timestamp_str}")
    print(f"  Preview Tick Index: {preview_tick_index}")
    print(f"  Fractal Tick Index: {fractal_tick_index}")

    # Load data: 1 minute before fractal + 1 minute after fractal
    df_ticks = load_tick_data_window(preview_tick_index, fractal_tick_index, num_minutes_after=1)

    # Pre-compute profiles
    profiles_data = precompute_profiles(df_ticks)

    # Calculate the frame index where fractal occurs (for stopping animation)
    fractal_frame_index = None
    for i, (ts, _, _, _, _) in enumerate(profiles_data):
        if ts >= fractal_timestamp:
            fractal_frame_index = i
            break

    # Calculate max frame (1 minute = 60 seconds after fractal)
    if fractal_frame_index is not None:
        max_playback_frame = min(fractal_frame_index + 60, len(profiles_data) - 1)
    else:
        max_playback_frame = len(profiles_data) - 1

    print(f"\n[INFO] Fractal occurs at frame {fractal_frame_index}/{len(profiles_data)-1}")
    print(f"[INFO] Animation will stop at frame {max_playback_frame} (1 min after fractal)")

    # Create figure with 5 horizontal panels + price chart
    print("\n[INFO] Creating visualization...")

    fig = plt.figure(figsize=(45, 12))
    gs = fig.add_gridspec(2, 5, left=0.04, bottom=0.12, right=0.99, top=0.96,
                          wspace=0.04, hspace=0.10, height_ratios=[3, 1])

    # Top row: 5 DOM+Profile panels
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[0, 2])
    ax4 = fig.add_subplot(gs[0, 3])
    ax5 = fig.add_subplot(gs[0, 4])

    # Bottom row: Price chart
    ax_price = fig.add_subplot(gs[1, :])

    # Global state
    current_index = [0]
    is_playing = [False]
    timer = [None]

    def plot_all_panels(index):
        """Plot all 5 panels for T-4, T-3, T-2, T-1, CURRENT"""
        # Calculate indices
        idx_t4 = max(0, index - 4)
        idx_t3 = max(0, index - 3)
        idx_t2 = max(0, index - 2)
        idx_t1 = max(0, index - 1)
        idx_current = index

        # Get common price range
        common_prices = None

        # Plot panels
        if idx_t4 < len(profiles_data):
            ts, prof, close, bid, ask = profiles_data[idx_t4]
            prev_close = profiles_data[idx_t4 - 1][2] if idx_t4 > 0 else None
            common_prices = plot_single_merged(ax1, ts, prof, close, bid, ask,
                                              prev_close, "T-4: ", common_prices, True)

        if idx_t3 < len(profiles_data):
            ts, prof, close, bid, ask = profiles_data[idx_t3]
            prev_close = profiles_data[idx_t3 - 1][2] if idx_t3 > 0 else None
            common_prices = plot_single_merged(ax2, ts, prof, close, bid, ask,
                                              prev_close, "T-3: ", common_prices, False)

        if idx_t2 < len(profiles_data):
            ts, prof, close, bid, ask = profiles_data[idx_t2]
            prev_close = profiles_data[idx_t2 - 1][2] if idx_t2 > 0 else None
            common_prices = plot_single_merged(ax3, ts, prof, close, bid, ask,
                                              prev_close, "T-2: ", common_prices, False)

        if idx_t1 < len(profiles_data):
            ts, prof, close, bid, ask = profiles_data[idx_t1]
            prev_close = profiles_data[idx_t1 - 1][2] if idx_t1 > 0 else None
            common_prices = plot_single_merged(ax4, ts, prof, close, bid, ask,
                                              prev_close, "T-1: ", common_prices, False)

        if idx_current < len(profiles_data):
            ts, prof, close, bid, ask = profiles_data[idx_current]
            prev_close = profiles_data[idx_current - 1][2] if idx_current > 0 else None
            common_prices = plot_single_merged(ax5, ts, prof, close, bid, ask,
                                              prev_close, "CURRENT: ", common_prices, False)

        # Plot price line with fractal timestamp
        ax_price_ret = plot_price_line(ax_price, profiles_data, index, fractal_timestamp)

        # Add title as text in upper LEFT of price chart (using "Fractal" instead of "MAJOR")
        if ax_price_ret:
            ax_price_ret.text(0.02, 0.95,
                            f'Fractal #{fractal_idx} | {fractal_type} @ {fractal_price:.2f} | Frame {index}/{len(profiles_data)-1}',
                            transform=ax_price_ret.transAxes,
                            fontsize=9, verticalalignment='top', horizontalalignment='left',
                            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7),
                            color='black', fontweight='bold')

        fig.canvas.draw_idle()

    def update_display(val=None):
        """Update display from slider"""
        idx = int(slider.val)
        current_index[0] = idx
        plot_all_panels(idx)

    def on_previous(event):
        """Previous frame"""
        is_playing[0] = False
        if timer[0]:
            timer[0].stop()
        current_index[0] = max(0, current_index[0] - 1)
        slider.set_val(current_index[0])

    def on_next(event):
        """Next frame"""
        is_playing[0] = False
        if timer[0]:
            timer[0].stop()
        current_index[0] = min(len(profiles_data) - 1, current_index[0] + 1)
        slider.set_val(current_index[0])

    def on_play(event):
        """Play animation"""
        is_playing[0] = True
        animate()

    def on_pause(event):
        """Pause animation"""
        is_playing[0] = False
        if timer[0]:
            timer[0].stop()

    def animate():
        """Animate forward - stops at 1 minute after fractal"""
        if not is_playing[0]:
            return

        current_index[0] = min(max_playback_frame, current_index[0] + 1)
        slider.set_val(current_index[0])

        # Stop if we reached max playback frame (1 min after fractal)
        if current_index[0] >= max_playback_frame:
            is_playing[0] = False
            if timer[0]:
                timer[0].stop()
            print(f"\n[INFO] Animation stopped at 1 minute after fractal")
            print(f"[INFO] Click 'Next >' button to inspect next fractal")
            return

        if is_playing[0]:
            # Schedule next frame
            timer[0] = fig.canvas.new_timer(interval=300)  # 300ms for smoother playback
            timer[0].single_shot = True
            timer[0].add_callback(animate)
            timer[0].start()

    def on_prev_fractal(event):
        """Load previous fractal"""
        # Stop animation first
        is_playing[0] = False
        if timer[0]:
            timer[0].stop()
        plt.close(fig)
        new_idx = fractal_idx - 1
        if new_idx >= 0:
            load_and_inspect_fractal(new_idx, df_fractals)
        else:
            print(f"[INFO] Already at first fractal")

    def on_next_fractal(event):
        """Load next fractal"""
        # Stop animation first
        is_playing[0] = False
        if timer[0]:
            timer[0].stop()
        plt.close(fig)
        new_idx = fractal_idx + 1
        if new_idx < len(df_fractals):
            load_and_inspect_fractal(new_idx, df_fractals)
        else:
            print(f"[INFO] Already at last fractal")

    # Create frame navigation buttons (center, very small)
    ax_prev = plt.axes([0.30, 0.05, 0.03, 0.015])
    ax_play = plt.axes([0.34, 0.05, 0.03, 0.015])
    ax_pause = plt.axes([0.38, 0.05, 0.03, 0.015])
    ax_next = plt.axes([0.42, 0.05, 0.03, 0.015])

    btn_prev = Button(ax_prev, 'Previous', color='lightblue', hovercolor='skyblue')
    btn_play = Button(ax_play, 'Play', color='lightgreen', hovercolor='limegreen')
    btn_pause = Button(ax_pause, 'Pause', color='lightyellow', hovercolor='yellow')
    btn_next = Button(ax_next, 'Next', color='lightcoral', hovercolor='salmon')

    btn_prev.on_clicked(on_previous)
    btn_play.on_clicked(on_play)
    btn_pause.on_clicked(on_pause)
    btn_next.on_clicked(on_next)

    # Create slider (no label, wider)
    ax_slider = plt.axes([0.1, 0.01, 0.8, 0.02])
    slider = Slider(ax_slider, '', 0, max_playback_frame,  # Max at 1 min after fractal
                    valinit=0, valstep=1)
    slider.on_changed(update_display)

    # Create fractal navigation buttons (right side, above slider, smaller height)
    ax_prev_fractal = plt.axes([0.91, 0.04, 0.03, 0.018])  # Reduced height from 0.025 to 0.018
    ax_next_fractal = plt.axes([0.95, 0.04, 0.03, 0.018])  # Reduced height from 0.025 to 0.018

    btn_prev_fractal = Button(ax_prev_fractal, '< Prev', color='#FFE4B5', hovercolor='#FFD700')
    btn_next_fractal = Button(ax_next_fractal, 'Next >', color='#E0FFFF', hovercolor='#87CEEB')

    btn_prev_fractal.on_clicked(on_prev_fractal)
    btn_next_fractal.on_clicked(on_next_fractal)

    # Initial plot
    current_index[0] = 0  # Reset to frame 0
    is_playing[0] = False  # Ensure not playing
    plot_all_panels(0)

    print("[OK] Visualization ready")
    print("[INFO] Use slider or buttons to navigate")

    plt.show()


def main():
    """Main execution"""
    print("="*70)
    print("INSPECTOR DOM DEEP - Inspect MAJOR Fractals")
    print("="*70)

    # Load fractal list
    df_fractals = load_fractal_list()

    # Check argument
    if len(sys.argv) < 2:
        print("\n[INFO] Available MAJOR fractals:")
        print(f"  Index range: 0 to {len(df_fractals) - 1}")
        print(f"\n[INFO] No fractal index provided, opening fractal #0 by default...")
        print(f"[INFO] Usage: python {sys.argv[0]} <fractal_index>")
        print(f"[INFO] Example: python {sys.argv[0]} 5")
        fractal_idx = 0  # Default to first fractal
    else:
        # Parse fractal index
        try:
            fractal_idx = int(sys.argv[1])
        except ValueError:
            print(f"[ERROR] Invalid fractal index: {sys.argv[1]}")
            sys.exit(1)

    # Load and inspect the fractal
    load_and_inspect_fractal(fractal_idx, df_fractals)


if __name__ == "__main__":
    main()
