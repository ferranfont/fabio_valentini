import pandas as pd
import numpy as np
from datetime import timedelta
from rolling_profile import RollingMarketProfile
import csv
from pathlib import Path

# Use TkAgg backend for better compatibility
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.widgets import Button, Slider

# Force window to frontferr
import os
os.environ['QT_QPA_PLATFORM'] = 'windows'

# ============ CONFIGURATION ============
STARTING_INDEX = 0  # Change this to start at a different frame (0 = first frame)
# You can also set a specific time like: STARTING_TIME = "2025-10-09 18:15:00"
STARTING_TIME =  "2025-10-09 18:02:25"    #None  # Set to None to use STARTING_INDEX instead
PROFILE_FREQUENCY = 5  # Frequency for Market Profile in seconds

# Profile shape detection configuration
DENSITY_SHAPE = 0.70  # 70% of volume must be concentrated in the zone (more strict)
MIN_PRICE_LEVELS = 10  # Minimum number of active price levels (increased from 8)
MIN_BID_ASK_SIZE = 20  # Minimum absolute size of largest BID/ASK bar (increased from 10)
PRICE_POSITION_THRESHOLD = 0.25  # Price must be in lower/upper 33% of the profile range
# =======================================

# Load data
csv_path = "data/time_and_sales_nq_30min.csv"
print("Loading data...")
df = pd.read_csv(csv_path, sep=";", decimal=",")
df["Timestamp"] = pd.to_datetime(df["Timestamp"])

# Generate timestamps every 10 seconds
start_time = df["Timestamp"].min()
end_time = df["Timestamp"].max()
timestamps = pd.date_range(start=start_time, end=end_time, freq="1s")  # Antes era 10s

# Pre-compute market profiles for all timestamps
print("Pre-computing market profiles...")
profiles_data = []

for i, ts in enumerate(timestamps):
    if i % 50 == 0:
        print(f"  Processing {i}/{len(timestamps)}...")

    mp = RollingMarketProfile(window=timedelta(seconds=PROFILE_FREQUENCY))  # Keep 60-second rolling window
    ticks_until = df[df["Timestamp"] <= ts]

    # Get closing price at this timestamp (last tick before or at ts)
    if len(ticks_until) > 0:
        closing_price = ticks_until.iloc[-1]["Precio"]
    else:
        closing_price = None

    for _, row in ticks_until.iterrows():
        mp.update(row["Timestamp"], row["Precio"], row["Volumen"], row["Lado"])

    profile = mp.profile()
    profiles_data.append((ts, profile, closing_price))

print(f"Pre-computed {len(profiles_data)} profiles")

# Determine starting index
if STARTING_TIME is not None:
    starting_ts = pd.to_datetime(STARTING_TIME)
    # Find closest timestamp
    start_idx = 0
    for i, (ts, _, _) in enumerate(profiles_data):
        if ts >= starting_ts:
            start_idx = i
            break
    print(f"Starting at timestamp: {profiles_data[start_idx][0]} (index {start_idx})")
else:
    start_idx = max(0, min(STARTING_INDEX, len(profiles_data) - 1))
    print(f"Starting at index: {start_idx} (timestamp: {profiles_data[start_idx][0]})")

# Create the figure with 2 rows and 5 columns
# Top row: 5 market profiles
# Bottom row: Price line chart (spanning all 5 columns)
fig = plt.figure(figsize=(45, 12))
gs = fig.add_gridspec(2, 5, left=0.04, bottom=0.12, right=0.99, top=0.96,
                      wspace=0.04, hspace=0.10, height_ratios=[3, 1])

# Top row: Market profile subplots
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

def get_fixed_color(base_color):
    """Return fixed color."""
    if base_color == 'green':
        return (0, 0.7, 0, 0.8)  # Fixed green
    else:  # red
        return (0.8, 0, 0, 0.8)  # Fixed red

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

def plot_single_profile(ax, index, title_prefix="", y_limits=None, common_prices=None, show_ylabel=True):
    """Plot a single market profile on the given axis.

    Args:
        ax: matplotlib axis
        index: frame index
        title_prefix: prefix for title
        y_limits: tuple (min_price, max_price) to set common Y axis
        common_prices: list of prices to use for Y axis (for alignment)
        show_ylabel: whether to show Y-axis labels
    """
    ax.clear()

    if index >= len(profiles_data):
        index = len(profiles_data) - 1

    timestamp, profile, closing_price = profiles_data[index]

    if not profile:
        ax.text(0.5, 0.5, "No data in rolling window",
                ha='center', va='center', fontsize=14)
        ax.set_title(f"Market Profile at {timestamp}")
        return None, None

    # Use common prices if provided, otherwise use profile prices
    if common_prices is not None:
        prices = common_prices
        bid_volumes = [profile.get(p, {}).get("BID", 0) for p in prices]
        ask_volumes = [profile.get(p, {}).get("ASK", 0) for p in prices]
    else:
        prices = sorted(profile.keys())
        bid_volumes = [profile[p]["BID"] for p in prices]
        ask_volumes = [profile[p]["ASK"] for p in prices]

    # Create horizontal bars
    y_positions = range(len(prices))

    # Plot BID volumes (left side, negative values, red)
    bid_color = get_fixed_color('red')
    ax.barh(y_positions, [-v for v in bid_volumes], height=0.8,
            color=bid_color, label='BID', edgecolor='darkred', linewidth=0.5)

    # Plot ASK volumes (right side, positive values, green)
    ask_color = get_fixed_color('green')
    ax.barh(y_positions, ask_volumes, height=0.8,
            color=ask_color, label='ASK', edgecolor='darkgreen', linewidth=0.5)

    # Get max volume for x-axis scaling
    max_bid = max(bid_volumes) if bid_volumes else 1
    max_ask = max(ask_volumes) if ask_volumes else 1

    # Set y-axis labels to prices (only show if requested)
    ax.set_yticks(y_positions)
    if show_ylabel:
        ax.set_yticklabels([f"{p:.2f}" for p in prices], fontsize=6)  # Increased to 6
    else:
        ax.set_yticklabels([])

    # Add vertical line at zero
    ax.axvline(x=0, color='black', linewidth=1.5, linestyle='-', alpha=0.7)

    # Add blue dot at closing price on y-axis
    if closing_price is not None and closing_price in prices:
        price_idx = prices.index(closing_price)
        ax.plot(0, price_idx, 'o', color='blue', markersize=10, zorder=5,
                markeredgecolor='darkblue', markeredgewidth=2)

    # Calculate max x-axis limit
    max_x = max(max(bid_volumes), max(ask_volumes)) * 1.1
    ax.set_xlim(-max_x, max_x)

    # Labels and title
    #ax.set_xlabel('Volume (BID ← | → ASK)', fontsize=11, fontweight='bold')
    # No Y-axis label (removed "Price Level")

    # Get previous close price for shape evaluation
    previous_close = None
    if index > 0 and index - 1 < len(profiles_data):
        _, _, previous_close = profiles_data[index - 1]

    # Evaluate profile shape with current and previous close prices
    profile_tag = evaluate_profile_shape(profile, closing_price, previous_close)

    # Title with closing price (only time, no date) - simplified, single line
    close_str = f' | Close: {closing_price:.2f}' if closing_price is not None else ''
    ax.set_title(f'{title_prefix}{timestamp.strftime("%H:%M:%S")}{close_str}',
                 fontsize=10, fontweight='bold', pad=10)

    # Add grid
    ax.grid(True, alpha=0.3, axis='x')

    # Add legend
    ax.legend(loc='upper right', fontsize=10)

    # Add statistics text box with profile tag
    total_bid = sum(bid_volumes)
    total_ask = sum(ask_volumes)
    stats_text = f'Total BID: {total_bid:.0f}\nTotal ASK: {total_ask:.0f}\n'
    stats_text += f'BID/ASK ratio: {total_bid/total_ask if total_ask > 0 else 0:.2f}\n'
    # Format profile tag: d-Shape, p-Shape, or Balanced
    profile_display = profile_tag.replace('_', '-').title() if '_' in profile_tag else profile_tag.capitalize()
    stats_text += f'PROFILE: {profile_display}'

    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
            fontsize=9, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    return prices, (bid_volumes, ask_volumes)

def plot_price_line(index):
    """Plot price line chart showing historical close prices."""
    ax_price.clear()

    # Get historical data up to current index
    # Show last 200 frames or all available data
    start_idx = max(0, index - 200)
    historical_data = profiles_data[start_idx:index + 1]

    # Extract timestamps and closing prices
    times = []
    prices = []
    for ts, _, close_price in historical_data:
        if close_price is not None:
            times.append(ts)
            prices.append(close_price)

    if len(prices) > 0:
        # Plot price line in grey with transparency 0.8 and width 1
        ax_price.plot(times, prices, color='grey', linewidth=1, alpha=0.8)

        # Mark T-4, T-3, T-2, T-1 positions with small grey circles
        # Get the timestamps for these frames
        frame_indices = [
            max(0, index - 4),  # T-4
            max(0, index - 3),  # T-3
            max(0, index - 2),  # T-2
            max(0, index - 1),  # T-1
        ]

        for frame_idx in frame_indices:
            if frame_idx < len(profiles_data):
                ts_marker, _, close_marker = profiles_data[frame_idx]
                if close_marker is not None:
                    # Plot small grey circle
                    ax_price.plot(ts_marker, close_marker, 'o', color='grey',
                                 markersize=5, alpha=0.6, zorder=4)

        # Mark current price with a blue dot (on top)
        if len(times) > 0:
            ax_price.plot(times[-1], prices[-1], 'o', color='blue',
                         markersize=8, zorder=5)

        # Formatting (no title, no legend, no axis labels)
        # Only horizontal grid
        ax_price.grid(True, alpha=0.3, axis='y')

        # Format x-axis to show only time (no rotation)
        import matplotlib.dates as mdates
        ax_price.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        ax_price.tick_params(axis='x', rotation=0, labelsize=6)  # Increased for time labels
        ax_price.tick_params(axis='y', labelsize=6)  # Same as upper subplot Y labels

        # Add current price info - calculate change from previous close
        if len(prices) > 0:
            current_price = prices[-1]

            # Get previous close price (from index - 1)
            previous_price = None
            if index > 0 and index - 1 < len(profiles_data):
                _, _, prev_close = profiles_data[index - 1]
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

            ax_price.text(0.98, 0.98, info_text, transform=ax_price.transAxes,
                         fontsize=9, verticalalignment='top', horizontalalignment='right',
                         bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.7))

def plot_profile(index):
    """Plot five frames: -4, -3, -2, -1, and current with common Y axis."""
    # Calculate frame indices
    frame1_index = max(0, index - 4)  # 4 frames ago
    frame2_index = max(0, index - 3)  # 3 frames ago
    frame3_index = max(0, index - 2)  # 2 frames ago
    frame4_index = max(0, index - 1)  # 1 frame ago
    frame5_index = index              # current frame

    # Collect all unique prices from all five profiles to create common Y axis
    all_prices = set()

    for idx in [frame1_index, frame2_index, frame3_index, frame4_index, frame5_index]:
        if idx < len(profiles_data):
            _, profile, _ = profiles_data[idx]
            if profile:
                all_prices.update(profile.keys())

    # Create common sorted price list
    common_prices = sorted(list(all_prices)) if all_prices else None

    # Plot five panels with common Y axis (simplified titles)
    # Panel 1 (leftmost): 4 frames ago (ONLY THIS ONE shows Y-axis labels)
    plot_single_profile(ax1, frame1_index,
                       title_prefix="T-4 | ",
                       common_prices=common_prices, show_ylabel=True)

    # Panel 2: 3 frames ago
    plot_single_profile(ax2, frame2_index,
                       title_prefix="T-3 | ",
                       common_prices=common_prices, show_ylabel=False)

    # Panel 3: 2 frames ago
    plot_single_profile(ax3, frame3_index,
                       title_prefix="T-2 | ",
                       common_prices=common_prices, show_ylabel=False)

    # Panel 4: 1 frame ago
    plot_single_profile(ax4, frame4_index,
                       title_prefix="T-1 | ",
                       common_prices=common_prices, show_ylabel=False)

    # Panel 5 (rightmost): Current frame
    plot_single_profile(ax5, frame5_index,
                       title_prefix="CURRENT | ",
                       common_prices=common_prices, show_ylabel=False)

    # Plot price line chart in bottom row
    plot_price_line(index)

    fig.canvas.draw_idle()

def update_slider(val):
    """Update plot when slider changes."""
    if not is_playing[0]:
        index = int(slider.val)
        current_index[0] = index
        plot_profile(index)

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
    slider.eventson = False  # Disable slider events temporarily
    slider.set_val(current_index[0])
    slider.eventson = True  # Re-enable slider events
    plot_profile(current_index[0])

def prev_frame(event):
    """Go to previous frame."""
    if is_playing[0]:
        pause(None)

    current_index[0] = max(current_index[0] - 1, 0)
    slider.eventson = False  # Disable slider events temporarily
    slider.set_val(current_index[0])
    slider.eventson = True  # Re-enable slider events
    plot_profile(current_index[0])

def animate():
    """Animation function."""
    if not is_playing[0]:
        return

    current_index[0] += 1
    if current_index[0] >= len(profiles_data):
        current_index[0] = 0

    slider.set_val(current_index[0])
    plot_profile(current_index[0])

    # Schedule next frame (500ms delay)
    timer[0] = fig.canvas.new_timer(interval=500)
    timer[0].single_shot = True
    timer[0].add_callback(animate)
    timer[0].start()

# Create buttons first (on top, smaller size)
ax_prev = plt.axes([0.1, 0.07, 0.05, 0.018])
ax_play = plt.axes([0.18, 0.07, 0.05, 0.018])
ax_pause = plt.axes([0.26, 0.07, 0.05, 0.018])
ax_next = plt.axes([0.34, 0.07, 0.05, 0.018])

# Create slider below buttons (smaller height)
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
plot_profile(start_idx)

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
csv_path_output = output_dir / "dP_Shapes.csv"

signals = []
for i, (timestamp, profile, closing_price) in enumerate(profiles_data):
    if not profile or closing_price is None:
        continue

    # Get previous close for pattern detection
    previous_close = None
    if i > 0:
        _, _, previous_close = profiles_data[i - 1]

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
