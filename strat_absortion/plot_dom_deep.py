import pandas as pd
import numpy as np
import json
from datetime import timedelta, datetime
from rolling_profile import RollingMarketProfile
from pathlib import Path

# Use TkAgg backend for better compatibility
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.widgets import Button, Slider

# Force window to front
import os
os.environ['QT_QPA_PLATFORM'] = 'windows'

# ============ CONFIGURATION ============
STARTING_INDEX = 0  # Change this to start at a different frame (0 = first frame)
STARTING_TIME = None  # Set to a specific time like "2025-10-20 18:09:00" or None
PROFILE_WINDOW = 5  # Market profile rolling window in seconds

# Profile shape detection configuration
DENSITY_SHAPE = 0.70  # 70% of volume must be concentrated in the zone (more strict)
MIN_PRICE_LEVELS = 10  # Minimum number of active price levels (increased from 8)
MIN_BID_ASK_SIZE = 20  # Minimum absolute size of largest BID/ASK bar (increased from 10)
PRICE_POSITION_THRESHOLD = 0.25  # Price must be in lower/upper 33% of the profile range
# =======================================

# Load data with custom parser (JSON not quoted in CSV)
csv_path = "data/ts_and_dom.csv"
print("Loading data with order book...")

# Read file line by line since JSON contains commas
data_rows = []
with open(csv_path, 'r') as f:
    header = f.readline().strip()  # Skip header
    for line in f:
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
                print(f"Warning: Failed to parse JSON on line, skipping: {e}")
                continue

print(f"Loaded {len(data_rows)} rows")
df = pd.DataFrame(data_rows)
df["Timestamp"] = pd.to_datetime(df["Timestamp"])

# Generate timestamps every 1 second
start_time = df["Timestamp"].min()
end_time = df["Timestamp"].max()
timestamps = pd.date_range(start=start_time, end=end_time, freq="1s")

# Pre-compute market profiles and order book snapshots for all timestamps
print("Pre-computing market profiles and order book snapshots...")
profiles_data = []

for i, ts in enumerate(timestamps):
    if i % 50 == 0:
        print(f"  Processing {i}/{len(timestamps)}...")

    # Market Profile
    mp = RollingMarketProfile(window=timedelta(seconds=PROFILE_WINDOW))
    ticks_until = df[df["Timestamp"] <= ts]

    # Get closing price and latest order book
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

print(f"Pre-computed {len(profiles_data)} profiles with order book data")

# Determine starting index
if STARTING_TIME is not None:
    starting_ts = pd.to_datetime(STARTING_TIME)
    start_idx = 0
    for i, (ts, _, _, _, _) in enumerate(profiles_data):
        if ts >= starting_ts:
            start_idx = i
            break
    print(f"Starting at timestamp: {profiles_data[start_idx][0]} (index {start_idx})")
else:
    start_idx = max(0, min(STARTING_INDEX, len(profiles_data) - 1))
    print(f"Starting at index: {start_idx} (timestamp: {profiles_data[start_idx][0]})")

# Create figure with 2 rows and 5 columns
# Top row: 5 DOM+Profile panels
# Bottom row: Price line chart (spanning all 5 columns)
fig = plt.figure(figsize=(45, 12))
gs = fig.add_gridspec(2, 5, left=0.04, bottom=0.12, right=0.99, top=0.96,
                      wspace=0.04, hspace=0.10, height_ratios=[3, 1])

# Top row: DOM+Profile subplots
ax1 = fig.add_subplot(gs[0, 0])
ax2 = fig.add_subplot(gs[0, 1])
ax3 = fig.add_subplot(gs[0, 2])
ax4 = fig.add_subplot(gs[0, 3])
ax5 = fig.add_subplot(gs[0, 4])

# Bottom row: Price line chart spanning all columns
ax_price = fig.add_subplot(gs[1, :])

# Global state
current_index = [start_idx]
is_playing = [False]
timer = [None]

def evaluate_profile_shape(profile, current_close=None, previous_close=None):
    """
    Evaluate the distribution shape of a market profile with STRICT criteria.

    Returns:
        str: 'd_shape', 'p_shape', or 'balanced'

    STRICT Criteria for d_shape (ALL must be met):
    1. Minimum MIN_PRICE_LEVELS active price levels
    2. At least one BID bar >= MIN_BID_ASK_SIZE in lower half
    3. >= DENSITY_SHAPE (70%) of total BID volume in lower half
    4. Current price must be in LOWER 33% of the profile range
    5. Price FALLING: current_close < previous_close (absorbing selling pressure)

    STRICT Criteria for p_shape (ALL must be met):
    1. Minimum MIN_PRICE_LEVELS active price levels
    2. At least one ASK bar >= MIN_BID_ASK_SIZE in upper half
    3. >= DENSITY_SHAPE (70%) of total ASK volume in upper half
    4. Current price must be in UPPER 33% of the profile range
    5. Price RISING: current_close > previous_close (absorbing buying pressure)
    """
    if not profile or current_close is None or previous_close is None:
        return 'balanced'

    # Filter out price levels with no volume (empty levels)
    active_prices = []
    for price in sorted(profile.keys()):
        bid_vol = profile[price].get('BID', 0)
        ask_vol = profile[price].get('ASK', 0)
        if bid_vol > 0 or ask_vol > 0:  # Only consider levels with volume
            active_prices.append(price)

    # Criterion 1: Minimum number of price levels
    if len(active_prices) < MIN_PRICE_LEVELS:
        return 'balanced'

    # Calculate total volumes
    total_bid = sum(profile[p].get('BID', 0) for p in active_prices)
    total_ask = sum(profile[p].get('ASK', 0) for p in active_prices)
    total_volume = total_bid + total_ask

    if total_volume == 0:
        return 'balanced'

    # Calculate price range
    min_price = min(active_prices)
    max_price = max(active_prices)
    price_range = max_price - min_price

    if price_range == 0:
        return 'balanced'

    # Calculate where current price is in the range (0 = bottom, 1 = top)
    price_position = (current_close - min_price) / price_range

    # Split active prices into lower half and upper half
    mid_point = len(active_prices) // 2
    lower_prices = active_prices[:mid_point + (1 if len(active_prices) % 2 == 1 else 0)]
    upper_prices = active_prices[mid_point:]

    # Calculate BID and ASK volume in each half
    lower_bid = sum(profile[p].get('BID', 0) for p in lower_prices)
    upper_ask = sum(profile[p].get('ASK', 0) for p in upper_prices)

    # Find max BID and ASK volumes in each half
    max_lower_bid = max([profile[p].get('BID', 0) for p in lower_prices]) if lower_prices else 0
    max_upper_ask = max([profile[p].get('ASK', 0) for p in upper_prices]) if upper_prices else 0

    # Check for d_shape - ALL criteria must be met
    if total_bid > 0:
        is_d_shape = (
            max_lower_bid >= MIN_BID_ASK_SIZE and  # Large BID bar in lower half
            lower_bid / total_bid >= DENSITY_SHAPE and  # 70% BID concentration in lower half
            price_position <= PRICE_POSITION_THRESHOLD and  # Price in lower 33% of range
            current_close < previous_close  # Price FALLING (absorbing selling pressure)
        )
        if is_d_shape:
            return 'd_shape'

    # Check for p_shape - ALL criteria must be met
    if total_ask > 0:
        is_p_shape = (
            max_upper_ask >= MIN_BID_ASK_SIZE and  # Large ASK bar in upper half
            upper_ask / total_ask >= DENSITY_SHAPE and  # 70% ASK concentration in upper half
            price_position >= (1 - PRICE_POSITION_THRESHOLD) and  # Price in upper 33% of range
            current_close > previous_close  # Price RISING (absorbing buying pressure)
        )
        if is_p_shape:
            return 'p_shape'

    return 'balanced'

def plot_single_merged(ax, index, title_prefix="", common_prices=None, show_ylabel=True):
    """Plot a single merged DOM + Market Profile panel."""
    ax.clear()

    if index >= len(profiles_data):
        index = len(profiles_data) - 1

    timestamp, profile, closing_price, dom_bid, dom_ask = profiles_data[index]

    # Get profile price range
    if profile:
        profile_prices = sorted(profile.keys())
        profile_high = profile_prices[-1] if profile_prices else None
        profile_low = profile_prices[0] if profile_prices else None
    else:
        profile_high = None
        profile_low = None
        profile_prices = []

    # Check if we have data
    if not dom_bid and not dom_ask:
        ax.text(0.5, 0.5, "No order book data", ha='center', va='center', fontsize=14)
        ax.set_title(f"{title_prefix}{timestamp}")
        return

    # Calculate continuous price range with no gaps
    tick_size = 0.25

    if common_prices is not None:
        all_prices = common_prices
    else:
        if profile_high is not None and profile_low is not None:
            # Use market profile range + 3 ticks above and below
            lower_limit = profile_low - (3 * tick_size)
            upper_limit = profile_high + (3 * tick_size)
        else:
            # Fallback to DOM data range
            all_dom_prices = [float(p) for p in set(list(dom_bid.keys()) + list(dom_ask.keys()))]
            if not all_dom_prices:
                ax.text(0.5, 0.5, "No order book data", ha='center', va='center', fontsize=14)
                return
            lower_limit = min(all_dom_prices)
            upper_limit = max(all_dom_prices)

        # Ensure current price is included in range
        if closing_price is not None:
            lower_limit = min(lower_limit, closing_price)
            upper_limit = max(upper_limit, closing_price)

        # Generate continuous price levels (no gaps)
        all_prices = []
        current = lower_limit
        while current <= upper_limit:
            all_prices.append(round(current, 2))
            current += tick_size

    if not all_prices:
        ax.text(0.5, 0.5, "No price data in range", ha='center', va='center', fontsize=14)
        return

    y_positions = range(len(all_prices))

    # Prepare DOM bid and ask sizes (fill with 0 if price not in DOM)
    dom_bid_sizes = []
    dom_ask_sizes = []
    for price in all_prices:
        # Try different string formats to match DOM keys
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

    # Calculate max DOM size for scaling
    max_dom_size = max(
        max(dom_bid_sizes) if dom_bid_sizes else 1,
        max(dom_ask_sizes) if dom_ask_sizes else 1
    )

    # Plot ORDER BOOK bars (grey colors with transparency)
    bid_color_dom = '#999999'  # Grey
    ask_color_dom = '#aaaaaa'  # Light grey

    # Find the index of the maximum BID and ASK bars
    max_bid_idx = dom_bid_sizes.index(max(dom_bid_sizes)) if dom_bid_sizes and max(dom_bid_sizes) > 0 else None
    max_ask_idx = dom_ask_sizes.index(max(dom_ask_sizes)) if dom_ask_sizes and max(dom_ask_sizes) > 0 else None

    # Plot all BID bars without edge first
    for i, size in enumerate(dom_bid_sizes):
        if size > 0:
            edgecolor = 'black' if i == max_bid_idx else 'none'
            linewidth = 2 if i == max_bid_idx else 0
            ax.barh(y_positions[i], -size, height=0.8,
                    color=bid_color_dom, edgecolor=edgecolor,
                    linewidth=linewidth, alpha=0.3, zorder=1)

    # Plot all ASK bars without edge first
    for i, size in enumerate(dom_ask_sizes):
        if size > 0:
            edgecolor = 'black' if i == max_ask_idx else 'none'
            linewidth = 2 if i == max_ask_idx else 0
            ax.barh(y_positions[i], size, height=0.8,
                    color=ask_color_dom, edgecolor=edgecolor,
                    linewidth=linewidth, alpha=0.3, zorder=1)

    # Add labels (only once, not per bar)
    if max_bid_idx is not None:
        ax.barh([], [], height=0.8, color=bid_color_dom, label='DOM BID', alpha=0.3)
    if max_ask_idx is not None:
        ax.barh([], [], height=0.8, color=ask_color_dom, label='DOM ASK', alpha=0.3)

    # Overlay MARKET PROFILE bars (solid red/green)
    if profile:
        # Prepare market profile volumes aligned with the same price levels
        mp_bid_volumes = []
        mp_ask_volumes = []

        for price in all_prices:
            if price in profile:
                mp_bid_volumes.append(profile[price]["BID"])
                mp_ask_volumes.append(profile[price]["ASK"])
            else:
                mp_bid_volumes.append(0)
                mp_ask_volumes.append(0)

        # Scale market profile to match DOM scale (normalize to max DOM size)
        max_mp_volume = max(
            max(mp_bid_volumes) if mp_bid_volumes else 1,
            max(mp_ask_volumes) if mp_ask_volumes else 1
        )

        # Scale factor: make MP bars ~70% of DOM scale
        scale_factor = (max_dom_size * 0.7) / max_mp_volume if max_mp_volume > 0 else 1
        mp_bid_scaled = [v * scale_factor for v in mp_bid_volumes]
        mp_ask_scaled = [v * scale_factor for v in mp_ask_volumes]

        bid_color_mp = (0.8, 0, 0, 0.8)  # Red
        ask_color_mp = (0, 0.7, 0, 0.8)  # Green

        # Plot solid bars (on top of order book bars)
        ax.barh(y_positions, [-v for v in mp_bid_scaled], height=0.6,
                color=bid_color_mp, label='Profile BID', edgecolor='darkred',
                linewidth=0.5, zorder=10)
        ax.barh(y_positions, mp_ask_scaled, height=0.6,
                color=ask_color_mp, label='Profile ASK', edgecolor='darkgreen',
                linewidth=0.5, zorder=10)

    # Set y-axis to prices
    if show_ylabel:
        # Filter to show only round integer values (no decimals)
        filtered_ticks = []
        filtered_labels = []
        for i, price in enumerate(all_prices):
            # Only show prices that are whole integers (no decimal part)
            if price == int(price):
                filtered_ticks.append(i)
                filtered_labels.append(f"{int(price)}")

        ax.set_yticks(filtered_ticks)
        ax.set_yticklabels(filtered_labels, fontsize=6)
    else:
        ax.set_yticks([])
        ax.set_yticklabels([])

    # Add vertical line at zero
    ax.axvline(x=0, color='black', linewidth=1.5, linestyle='-', alpha=0.7, zorder=2)

    # Get previous close for shape evaluation
    previous_close = None
    if index > 0 and index - 1 < len(profiles_data):
        _, _, previous_close, _, _ = profiles_data[index - 1]

    # Evaluate profile shape with current and previous close prices
    profile_tag = evaluate_profile_shape(profile, closing_price, previous_close)

    # Determine dot color based on profile shape
    if profile_tag == 'd_shape':
        dot_color = 'green'
        dot_edge_color = 'darkgreen'
    elif profile_tag == 'p_shape':
        dot_color = 'red'
        dot_edge_color = 'darkred'
    else:
        dot_color = 'blue'
        dot_edge_color = 'darkblue'

    # Mark current price with horizontal line and colored dot
    if closing_price and closing_price in all_prices:
        price_idx = all_prices.index(closing_price)
        ax.axhline(y=price_idx, color='blue', linewidth=1, linestyle='--', alpha=0.6, zorder=25)
        ax.plot(0, price_idx, 'o', color=dot_color, markersize=10, zorder=30,
                markeredgecolor=dot_edge_color, markeredgewidth=2)

    # Set x-axis limits
    ax.set_xlim(-max_dom_size * 1.1, max_dom_size * 1.1)

    # Title with closing price and profile tag (only time, no date)
    close_str = f' | Close: {closing_price:.2f}' if closing_price is not None else ''
    profile_display = profile_tag.replace('_', '-').title() if '_' in profile_tag else profile_tag.capitalize()
    ax.set_title(f'{title_prefix}{timestamp.strftime("%H:%M:%S")}{close_str}',
                 fontsize=10, fontweight='bold', pad=10)

    # Add grid
    ax.grid(True, alpha=0.3, axis='x')

    # Add legend (only on first panel)
    if show_ylabel:
        ax.legend(loc='upper right', fontsize=8, ncol=2)

    # Add statistics text box with profile tag and colored text
    total_dom_bid = sum(dom_bid_sizes)
    total_dom_ask = sum(dom_ask_sizes)

    # Build stats text (all lines in black except last line)
    stats_lines = []
    stats_lines.append(f'DOM BID: {total_dom_bid:.0f}')
    stats_lines.append(f'DOM ASK: {total_dom_ask:.0f}')

    if profile:
        total_mp_bid = sum(mp_bid_volumes)
        total_mp_ask = sum(mp_ask_volumes)
        stats_lines.append(f'Profile BID: {total_mp_bid:.0f}')
        stats_lines.append(f'Profile ASK: {total_mp_ask:.0f}')
        stats_lines.append(f'BID/ASK: {total_mp_bid/total_mp_ask if total_mp_ask > 0 else 0:.2f}')

    # Join all lines except last
    stats_text = '\n'.join(stats_lines)

    # Add text box with black text
    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
            fontsize=9, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
            color='black')

    # Add PROFILE line separately with red color if d_shape or p_shape
    profile_color = 'red' if profile_tag in ['d_shape', 'p_shape'] else 'black'
    profile_line = f'PROFILE: {profile_display}'

    # Calculate vertical position for PROFILE line (below other lines)
    num_lines = len(stats_lines)
    line_height = 0.04  # Approximate height per line in axes coordinates
    profile_y = 0.98 - (num_lines * line_height)

    ax.text(0.02, profile_y, profile_line, transform=ax.transAxes,
            fontsize=9, verticalalignment='top',
            color=profile_color, fontweight='bold')

    return all_prices

def plot_price_line(index):
    """Plot price line chart showing historical close prices with d-shape and p-shape signals."""
    ax_price.clear()

    # Get historical data up to current index
    # Show last 200 frames or all available data
    start_idx = max(0, index - 200)
    historical_data = profiles_data[start_idx:index + 1]

    # Extract timestamps and closing prices
    times = []
    prices = []
    for ts, _, close_price, _, _ in historical_data:
        if close_price is not None:
            times.append(ts)
            prices.append(close_price)

    if len(prices) > 0:
        # Plot price line in grey with transparency 0.8 and width 1
        ax_price.plot(times, prices, color='grey', linewidth=1, alpha=0.8)

        # Mark T-4, T-3, T-2, T-1 positions with small grey circles
        frame_indices = [
            max(0, index - 4),  # T-4
            max(0, index - 3),  # T-3
            max(0, index - 2),  # T-2
            max(0, index - 1),  # T-1
        ]

        for frame_idx in frame_indices:
            if frame_idx < len(profiles_data):
                ts_marker, _, close_marker, _, _ = profiles_data[frame_idx]
                if close_marker is not None:
                    # Plot small grey circle
                    ax_price.plot(ts_marker, close_marker, 'o', color='grey',
                                 markersize=5, alpha=0.6, zorder=4)

        # Collect d-shape and p-shape signals
        d_shape_times, d_shape_prices = [], []
        p_shape_times, p_shape_prices = [], []

        # Plot d-shape and p-shape signals for ALL historical data in view
        for hist_idx in range(start_idx, index + 1):
            if hist_idx < len(profiles_data):
                ts_sig, profile_sig, close_sig, _, _ = profiles_data[hist_idx]

                if close_sig is not None and profile_sig:
                    # Get previous close for shape evaluation
                    previous_close_sig = None
                    if hist_idx > 0 and hist_idx - 1 < len(profiles_data):
                        _, _, previous_close_sig, _, _ = profiles_data[hist_idx - 1]

                    # Evaluate shape
                    shape = evaluate_profile_shape(profile_sig, close_sig, previous_close_sig)

                    # Collect RED dots for d-shape
                    if shape == 'd_shape':
                        d_shape_times.append(ts_sig)
                        d_shape_prices.append(close_sig)

                    # Collect LIME GREEN dots for p-shape
                    elif shape == 'p_shape':
                        p_shape_times.append(ts_sig)
                        p_shape_prices.append(close_sig)

        # Draw all d-shape and p-shape signals as scatter plots
        if len(d_shape_times) > 0:
            ax_price.scatter(d_shape_times, d_shape_prices,
                            s=80, c='red', alpha=0.9, zorder=6,
                            edgecolors='darkred', linewidths=1.5)

        if len(p_shape_times) > 0:
            ax_price.scatter(p_shape_times, p_shape_prices,
                            s=80, c='lime', alpha=0.9, zorder=6,
                            edgecolors='darkgreen', linewidths=1.5)

        # Mark current price with a blue dot (on top of everything)
        if len(times) > 0:
            ax_price.plot(times[-1], prices[-1], 'o', color='blue',
                         markersize=8, zorder=7)

        # Formatting (no title, no legend, no axis labels)
        # Only horizontal grid
        ax_price.grid(True, alpha=0.3, axis='y')

        # Format x-axis to show only time (no rotation)
        import matplotlib.dates as mdates
        from matplotlib.ticker import ScalarFormatter
        ax_price.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        ax_price.tick_params(axis='x', rotation=0, labelsize=6)
        ax_price.tick_params(axis='y', labelsize=7)

        # Disable scientific notation on Y axis
        ax_price.yaxis.set_major_formatter(ScalarFormatter(useOffset=False))
        ax_price.ticklabel_format(style='plain', axis='y')

        # Add current price info (bottom left)
        if len(prices) > 0:
            current_price = prices[-1]

            # Get previous close price (from index - 1)
            previous_price = None
            if index > 0 and index - 1 < len(profiles_data):
                _, _, prev_close, _, _ = profiles_data[index - 1]
                previous_price = prev_close

            # Calculate change from previous close
            if previous_price is not None:
                price_change = current_price - previous_price
                price_change_pct = (price_change / previous_price * 100) if previous_price != 0 else 0
                info_text = f'Close: {current_price:.2f}\n'
                info_text += f'Change: {price_change:+.2f} ({price_change_pct:+.2f}%)'
            else:
                info_text = f'Close: {current_price:.2f}\n'
                info_text += f'Change: N/A'

            ax_price.text(0.02, 0.02, info_text, transform=ax_price.transAxes,
                         fontsize=9, verticalalignment='bottom', horizontalalignment='left',
                         bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.7))

def plot_all_panels(index):
    """Plot five frames: T-4, T-3, T-2, T-1, and CURRENT with common Y axis."""
    # Calculate frame indices
    frame1_index = max(0, index - 4)  # 4 frames ago
    frame2_index = max(0, index - 3)  # 3 frames ago
    frame3_index = max(0, index - 2)  # 2 frames ago
    frame4_index = max(0, index - 1)  # 1 frame ago
    frame5_index = index              # current frame

    # Collect all unique prices from all five profiles to create common Y axis
    all_prices_set = set()

    for idx in [frame1_index, frame2_index, frame3_index, frame4_index, frame5_index]:
        if idx < len(profiles_data):
            _, profile, closing_price, dom_bid, dom_ask = profiles_data[idx]

            # Add profile prices
            if profile:
                all_prices_set.update(profile.keys())

            # Add DOM prices
            if dom_bid:
                all_prices_set.update([float(p) for p in dom_bid.keys()])
            if dom_ask:
                all_prices_set.update([float(p) for p in dom_ask.keys()])

            # Add closing price
            if closing_price is not None:
                all_prices_set.add(closing_price)

    # Create common sorted price list with continuous range
    if all_prices_set:
        min_price = min(all_prices_set)
        max_price = max(all_prices_set)
        tick_size = 0.25

        common_prices = []
        current = min_price
        while current <= max_price:
            common_prices.append(round(current, 2))
            current += tick_size
    else:
        common_prices = None

    # Plot five panels with common Y axis
    # Panel 1 (leftmost): T-4 (ONLY THIS ONE shows Y-axis labels)
    plot_single_merged(ax1, frame1_index,
                       title_prefix="T-4 | ",
                       common_prices=common_prices, show_ylabel=True)

    # Panel 2: T-3
    plot_single_merged(ax2, frame2_index,
                       title_prefix="T-3 | ",
                       common_prices=common_prices, show_ylabel=False)

    # Panel 3: T-2
    plot_single_merged(ax3, frame3_index,
                       title_prefix="T-2 | ",
                       common_prices=common_prices, show_ylabel=False)

    # Panel 4: T-1
    plot_single_merged(ax4, frame4_index,
                       title_prefix="T-1 | ",
                       common_prices=common_prices, show_ylabel=False)

    # Panel 5 (rightmost): CURRENT
    plot_single_merged(ax5, frame5_index,
                       title_prefix="CURRENT | ",
                       common_prices=common_prices, show_ylabel=False)

    # Plot price line chart in bottom panel
    plot_price_line(index)

    fig.canvas.draw_idle()

def update_slider(val):
    """Update plot when slider changes."""
    if not is_playing[0]:
        index = int(slider.val)
        current_index[0] = index
        plot_all_panels(index)

def play(event):
    """Start animation."""
    is_playing[0] = True
    btn_play.label.set_text("Playing...")
    animate()

def pause(event):
    """Pause animation."""
    is_playing[0] = False
    btn_play.label.set_text("Play")
    if timer[0] is not None:
        timer[0].stop()
        timer[0] = None

def next_frame(event):
    """Go to next frame."""
    if is_playing[0]:
        pause(None)

    current_index[0] = min(current_index[0] + 1, len(profiles_data) - 1)
    slider.eventson = False
    slider.set_val(current_index[0])
    slider.eventson = True
    plot_all_panels(current_index[0])

def prev_frame(event):
    """Go to previous frame."""
    if is_playing[0]:
        pause(None)

    current_index[0] = max(current_index[0] - 1, 0)
    slider.eventson = False
    slider.set_val(current_index[0])
    slider.eventson = True
    plot_all_panels(current_index[0])

def animate():
    """Animation function."""
    if not is_playing[0]:
        return

    current_index[0] += 1
    if current_index[0] >= len(profiles_data):
        current_index[0] = 0

    slider.set_val(current_index[0])
    plot_all_panels(current_index[0])

    # Schedule next frame (500ms delay)
    timer[0] = fig.canvas.new_timer(interval=500)
    timer[0].single_shot = True
    timer[0].add_callback(animate)
    timer[0].start()

# Create buttons
ax_prev = plt.axes([0.1, 0.07, 0.05, 0.018])
ax_play = plt.axes([0.18, 0.07, 0.05, 0.018])
ax_pause = plt.axes([0.26, 0.07, 0.05, 0.018])
ax_next = plt.axes([0.34, 0.07, 0.05, 0.018])

# Create slider below buttons
ax_slider = plt.axes([0.1, 0.03, 0.85, 0.012])
slider = Slider(ax_slider, 'Time', 0, len(profiles_data) - 1,
                valinit=start_idx, valstep=1, color='skyblue')
slider.on_changed(update_slider)

btn_prev = Button(ax_prev, 'Previous', color='lightgray', hovercolor='gray')
btn_play = Button(ax_play, 'Play', color='lightgreen', hovercolor='green')
btn_pause = Button(ax_pause, 'Pause', color='lightcoral', hovercolor='red')
btn_next = Button(ax_next, 'Next', color='lightgray', hovercolor='gray')

btn_prev.on_clicked(prev_frame)
btn_play.on_clicked(play)
btn_pause.on_clicked(pause)
btn_next.on_clicked(next_frame)

# Initial plot
plot_all_panels(start_idx)

print("\nControls:")
print("  - Slider: Navigate to any time point")
print("  - Previous/Next: Step through frames")
print("  - Play: Start animation (500ms per frame)")
print("  - Pause: Stop animation")
print("\nClose the window to exit.")

# Detect and save d-Shape and p-Shape signals to CSV
print("\nDetecting d-Shape and p-Shape patterns...")
output_dir = Path("outputs")
output_dir.mkdir(exist_ok=True)

# Generate filename with timestamp
timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
csv_path_output = output_dir / f"db_shapes_dom_{timestamp_str}.csv"

signals = []
for i, (timestamp, profile, closing_price, dom_bid, dom_ask) in enumerate(profiles_data):
    if not profile or closing_price is None:
        continue

    # Get previous close for pattern detection
    previous_close = None
    if i > 0:
        _, _, previous_close, _, _ = profiles_data[i - 1]

    # Evaluate profile shape
    shape = evaluate_profile_shape(profile, closing_price, previous_close)

    # Only save d-Shape and p-Shape signals (not balanced)
    if shape in ['d_shape', 'p_shape']:
        # Calculate profile statistics
        active_prices = []
        for price in sorted(profile.keys()):
            bid_vol = profile[price].get('BID', 0)
            ask_vol = profile[price].get('ASK', 0)
            if bid_vol > 0 or ask_vol > 0:
                active_prices.append(price)

        total_bid = sum(profile[p].get('BID', 0) for p in active_prices)
        total_ask = sum(profile[p].get('ASK', 0) for p in active_prices)

        # Split into halves
        mid_point = len(active_prices) // 2
        lower_prices = active_prices[:mid_point + (1 if len(active_prices) % 2 == 1 else 0)]
        upper_prices = active_prices[mid_point:]

        lower_bid = sum(profile[p].get('BID', 0) for p in lower_prices)
        upper_ask = sum(profile[p].get('ASK', 0) for p in upper_prices)

        max_lower_bid = max([profile[p].get('BID', 0) for p in lower_prices]) if lower_prices else 0
        max_upper_ask = max([profile[p].get('ASK', 0) for p in upper_prices]) if upper_prices else 0

        # Price change
        price_change = closing_price - previous_close if previous_close is not None else 0
        price_change_pct = (price_change / previous_close * 100) if previous_close is not None and previous_close != 0 else 0

        signals.append({
            'timestamp': timestamp,
            'shape': shape,
            'close_price': closing_price,
            'previous_close': previous_close,
            'price_change': price_change,
            'price_change_pct': price_change_pct,
            'total_bid': total_bid,
            'total_ask': total_ask,
            'bid_ask_ratio': total_bid / total_ask if total_ask > 0 else 0,
            'num_price_levels': len(active_prices),
            'lower_bid_volume': lower_bid,
            'upper_ask_volume': upper_ask,
            'max_lower_bid': max_lower_bid,
            'max_upper_ask': max_upper_ask,
            'bid_concentration': lower_bid / total_bid if total_bid > 0 else 0,
            'ask_concentration': upper_ask / total_ask if total_ask > 0 else 0,
        })

# Save to CSV
if signals:
    df_signals = pd.DataFrame(signals)
    df_signals.to_csv(csv_path_output, index=False, sep=';', decimal=',')
    print(f"Saved {len(signals)} signals to {csv_path_output}")
    print(f"  - d-Shape signals: {len([s for s in signals if s['shape'] == 'd_shape'])}")
    print(f"  - p-Shape signals: {len([s for s in signals if s['shape'] == 'p_shape'])}")
else:
    print("No d-Shape or p-Shape signals detected")

# Force window to be visible and bring to front
try:
    fig.canvas.manager.window.wm_attributes('-topmost', 1)
    fig.canvas.manager.window.after_idle(fig.canvas.manager.window.attributes, '-topmost', False)
except:
    pass

plt.show(block=True)
