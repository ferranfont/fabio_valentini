import pandas as pd
import numpy as np
from datetime import timedelta
from rolling_profile import RollingMarketProfile

# Use TkAgg backend for better compatibility
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.widgets import Button, Slider

# ============ CONFIGURATION ============
STARTING_INDEX = 0  # Change this to start at a different frame (0 = first frame)
# You can also set a specific time like: STARTING_TIME = "2025-10-09 18:15:00"
STARTING_TIME =  "2025-10-09 18:02:25"    #None  # Set to None to use STARTING_INDEX instead
PROFILE_FREQUENCY = 5  # Frequency for Market Profile
# =======================================

# Load data
csv_path = "data/time_and_sales_nq_30min.csv"
print("Loading data...")
df = pd.read_csv(csv_path, sep=";", decimal=",")
df["Timestamp"] = pd.to_datetime(df["Timestamp"])

# Generate timestamps every 10 seconds
start_time = df["Timestamp"].min()
end_time = df["Timestamp"].max()
timestamps = pd.date_range(start=start_time, end=end_time, freq="2s")  # Antes era 10s

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

# Create the figure with four subplots (left to right: oldest to newest)
fig, (ax1, ax2, ax3, ax4) = plt.subplots(1, 4, figsize=(36, 10))
plt.subplots_adjust(left=0.03, bottom=0.25, right=0.99, top=0.95, wspace=0.04)

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
        ax.set_yticklabels([f"{p:.2f}" for p in prices], fontsize=6)  # Reduced from 8 to 6
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
    # Only show Y-axis label if show_ylabel is True
    if show_ylabel:
        ax.set_ylabel('Price Level', fontsize=11, fontweight='bold')

    # Title with closing price
    close_str = f' | Close: {closing_price:.2f}' if closing_price is not None else ''
    ax.set_title(f'{title_prefix}-{timestamp.strftime("%Y-%m-%d %H:%M:%S")}{close_str}\n'
                 f'({PROFILE_FREQUENCY}-second rolling window | Step {index+1}/{len(profiles_data)})',
                 fontsize=10, fontweight='bold', pad=10)

    # Add price line showing historical movement
    # Get price history up to current timestamp
    historical_prices = []
    historical_times = []
    for i in range(max(0, index - 60), index + 1):  # Last 60 frames (~10 min)
        if i < len(profiles_data):
            ts_hist, _, close_hist = profiles_data[i]
            if close_hist is not None:
                historical_prices.append(close_hist)
                historical_times.append(i - max(0, index - 60))

    # Plot price line on the right side of the chart
    if len(historical_prices) > 1:
        # Normalize historical times to x-axis position (right side)
        x_offset = max_x * 0.7  # Start at 70% of max_x
        x_range = max_x * 0.25   # Use 25% of max_x for price line width
        x_positions = [x_offset + (t / max(historical_times)) * x_range for t in historical_times]

        # Map prices to y-axis positions
        y_line_positions = []
        for price in historical_prices:
            # Find closest price level in y_positions
            if price in prices:
                y_line_positions.append(prices.index(price))
            else:
                # Interpolate position
                sorted_prices = sorted(prices)
                for i, p in enumerate(sorted_prices):
                    if price <= p:
                        y_line_positions.append(i)
                        break
                else:
                    y_line_positions.append(len(prices) - 1)

        # Draw price line in grey with width 1
        ax.plot(x_positions, y_line_positions, color='grey', linewidth=1, alpha=0.8, zorder=4)

        # Add blue dot at the end of the price line (current closing price)
        if len(y_line_positions) > 0:
            ax.plot(x_positions[-1], y_line_positions[-1], 'o', color='blue', markersize=8, zorder=5,
                    markeredgecolor='darkblue', markeredgewidth=1.5)

    # Add grid
    ax.grid(True, alpha=0.3, axis='x')

    # Add legend
    ax.legend(loc='upper right', fontsize=10)

    # Add statistics text box
    total_bid = sum(bid_volumes)
    total_ask = sum(ask_volumes)
    stats_text = f'Total BID: {total_bid:.0f}\nTotal ASK: {total_ask:.0f}\n'
    stats_text += f'Price levels: {len(prices)}\n'
    stats_text += f'BID/ASK ratio: {total_bid/total_ask if total_ask > 0 else 0:.2f}'

    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
            fontsize=9, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    return prices, (bid_volumes, ask_volumes)

def plot_profile(index):
    """Plot four frames: -3, -2, -1, and current with common Y axis."""
    # Calculate frame indices
    frame1_index = max(0, index - 3)  # 3 frames ago
    frame2_index = max(0, index - 2)  # 2 frames ago
    frame3_index = max(0, index - 1)  # 1 frame ago
    frame4_index = index              # current frame

    # Collect all unique prices from all four profiles to create common Y axis
    all_prices = set()

    for idx in [frame1_index, frame2_index, frame3_index, frame4_index]:
        if idx < len(profiles_data):
            _, profile, _ = profiles_data[idx]
            if profile:
                all_prices.update(profile.keys())

    # Create common sorted price list
    common_prices = sorted(list(all_prices)) if all_prices else None

    # Calculate time differences in seconds (each frame is 5 seconds based on freq='5s')
    time_3frames = 3 * 5  # 3 frames = 15 seconds
    time_2frames = 2 * 5  # 2 frames = 10 seconds
    time_1frame = 1 * 5   # 1 frame = 5 seconds

    # Plot four panels with common Y axis
    # Panel 1 (leftmost): 3 frames ago (ONLY THIS ONE shows Y-axis labels)
    plot_single_profile(ax1, frame1_index,
                       title_prefix=f"T-3 (-{time_3frames}s) - ",
                       common_prices=common_prices, show_ylabel=True)

    # Panel 2: 2 frames ago
    plot_single_profile(ax2, frame2_index,
                       title_prefix=f"T-2 (-{time_2frames}s) - ",
                       common_prices=common_prices, show_ylabel=False)

    # Panel 3: 1 frame ago
    plot_single_profile(ax3, frame3_index,
                       title_prefix=f"T-1 (-{time_1frame}s) - ",
                       common_prices=common_prices, show_ylabel=False)

    # Panel 4 (rightmost): Current frame
    plot_single_profile(ax4, frame4_index,
                       title_prefix=f"CURRENT (T-0) - ",
                       common_prices=common_prices, show_ylabel=False)

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

# Create slider for navigation
ax_slider = plt.axes([0.1, 0.12, 0.85, 0.03])
slider = Slider(ax_slider, 'Time', 0, len(profiles_data) - 1,
                valinit=start_idx, valstep=1, color='skyblue')
slider.on_changed(update_slider)

# Create buttons
ax_prev = plt.axes([0.1, 0.05, 0.1, 0.04])
ax_play = plt.axes([0.25, 0.05, 0.1, 0.04])
ax_pause = plt.axes([0.4, 0.05, 0.1, 0.04])
ax_next = plt.axes([0.55, 0.05, 0.1, 0.04])

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

plt.show()
