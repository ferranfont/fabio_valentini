import pandas as pd
import numpy as np
import json
from datetime import timedelta
from rolling_profile import RollingMarketProfile

# Use TkAgg backend for better compatibility
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.widgets import Button, Slider

# ============ CONFIGURATION ============
STARTING_INDEX = 0  # Change this to start at a different frame (0 = first frame)
STARTING_TIME = None  # Set to a specific time like "2025-10-20 18:09:00" or None
PROFILE_WINDOW = 5  # Market profile rolling window in seconds
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

# Create figure with single subplot (merged Order Book + Market Profile)
fig, ax = plt.subplots(1, 1, figsize=(16, 12))
plt.subplots_adjust(left=0.08, bottom=0.12, right=0.95, top=0.95)

# Global state
current_index = [start_idx]
is_playing = [False]
timer = [None]

def get_fixed_color(base_color):
    """Return fixed color."""
    if base_color == 'blue':
        return (0, 0.4, 0.8, 0.8)  # Blue for ASK
    else:  # orange
        return (1.0, 0.6, 0, 0.8)  # Orange for BID

def plot_order_book(ax, dom_bid, dom_ask, current_price, profile_high=None, profile_low=None):
    """Plot order book (DOM) visualization."""
    ax.clear()

    if not dom_bid and not dom_ask:
        ax.text(0.5, 0.5, "No order book data",
                ha='center', va='center', fontsize=14)
        ax.set_title("Order Book (DOM)")
        return

    # Calculate continuous price range with no gaps
    tick_size = 0.25

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
    if current_price is not None:
        lower_limit = min(lower_limit, current_price)
        upper_limit = max(upper_limit, current_price)

    # Generate continuous price levels (no gaps)
    all_prices = []
    current = lower_limit
    while current <= upper_limit:
        all_prices.append(round(current, 2))
        current += tick_size

    y_positions = range(len(all_prices))

    # Prepare bid and ask sizes (fill with 0 if price not in DOM)
    bid_sizes = []
    ask_sizes = []
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

        bid_sizes.append(bid_size)
        ask_sizes.append(ask_size)

    # Plot BID side (left, grey #999999, diagonal dashes) - BOTTOM LAYER
    bid_color = '#999999'  # Grey
    ax.barh(y_positions, [-size for size in bid_sizes], height=0.8,
            color=bid_color, label='BID', edgecolor='#666666',
            linewidth=1.5, hatch='///', alpha=0.25, zorder=1)

    # Plot ASK side (right, light grey #aaaaaa, diagonal dashes) - BOTTOM LAYER
    ask_color = '#aaaaaa'  # Light grey
    ax.barh(y_positions, ask_sizes, height=0.8,
            color=ask_color, label='ASK', edgecolor='#888888',
            linewidth=1.5, hatch='///', alpha=0.25, zorder=1)

    # Calculate max size for x-axis scaling
    max_size = max(max(bid_sizes) if bid_sizes else 1, max(ask_sizes) if ask_sizes else 1)

    # Add dashed rectangle border around the order book
    from matplotlib.patches import Rectangle
    if len(y_positions) > 0:
        rect = Rectangle(
            (-max_size * 1.1, -0.5),  # (x, y) lower-left corner
            max_size * 2.2,  # width (covers both sides)
            len(y_positions),  # height
            linewidth=2,
            edgecolor='gray',
            facecolor='none',
            linestyle='--',
            alpha=0.7,
            zorder=10
        )
        ax.add_patch(rect)

    # Set y-axis to prices
    ax.set_yticks(y_positions)
    ax.set_yticklabels([f"{p:.2f}" for p in all_prices], fontsize=8)

    # Add vertical line at zero
    ax.axvline(x=0, color='black', linewidth=2, linestyle='-', alpha=0.7)

    # Mark current price with horizontal line and blue dot
    if current_price and current_price in all_prices:
        price_idx = all_prices.index(current_price)
        ax.axhline(y=price_idx, color='blue', linewidth=2, linestyle='--', alpha=0.6, zorder=5)
        ax.plot(0, price_idx, 'o', color='blue', markersize=12, zorder=6,
                markeredgecolor='darkblue', markeredgewidth=2)

    # Set x-axis limits (max_size already calculated above)
    ax.set_xlim(-max_size * 1.1, max_size * 1.1)

    # Labels and title
    ax.set_xlabel('Size (BID ← | → ASK)', fontsize=11, fontweight='bold')
    ax.set_ylabel('Price Level', fontsize=11, fontweight='bold')
    ax.set_title('Order Book (Depth of Market)', fontsize=12, fontweight='bold', pad=10)

    # Add grid
    ax.grid(True, alpha=0.3, axis='x')

    # Add legend
    ax.legend(loc='upper right', fontsize=10)

    # Add statistics
    total_bid_size = sum(bid_sizes)
    total_ask_size = sum(ask_sizes)

    # Calculate spread from DOM data (best bid and best ask)
    bid_prices_with_vol = [float(p) for p, v in dom_bid.items() if v > 0]
    ask_prices_with_vol = [float(p) for p, v in dom_ask.items() if v > 0]

    if bid_prices_with_vol and ask_prices_with_vol:
        best_bid = max(bid_prices_with_vol)
        best_ask = min(ask_prices_with_vol)
        spread = best_ask - best_bid
    else:
        spread = 0

    stats_text = f'Total BID: {total_bid_size:.0f}\n'
    stats_text += f'Total ASK: {total_ask_size:.0f}\n'
    stats_text += f'Spread: {spread:.2f}\n'
    stats_text += f'BID/ASK: {total_bid_size/total_ask_size if total_ask_size > 0 else 0:.2f}'

    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
            fontsize=9, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.6))

def plot_market_profile(ax, index):
    """Plot market profile."""
    ax.clear()

    if index >= len(profiles_data):
        index = len(profiles_data) - 1

    timestamp, profile, closing_price, _, _ = profiles_data[index]

    if not profile:
        ax.text(0.5, 0.5, "No data in rolling window",
                ha='center', va='center', fontsize=14)
        ax.set_title(f"Market Profile at {timestamp}")
        return

    # Extract prices and volumes
    prices = sorted(profile.keys())
    bid_volumes = [profile[p]["BID"] for p in prices]
    ask_volumes = [profile[p]["ASK"] for p in prices]

    # Create horizontal bars
    y_positions = range(len(prices))

    # Plot BID volumes (left side, negative values, red)
    bid_color = (0.8, 0, 0, 0.8)  # Red
    ax.barh(y_positions, [-v for v in bid_volumes], height=0.8,
            color=bid_color, label='BID', edgecolor='darkred', linewidth=0.5)

    # Plot ASK volumes (right side, positive values, green)
    ask_color = (0, 0.7, 0, 0.8)  # Green
    ax.barh(y_positions, ask_volumes, height=0.8,
            color=ask_color, label='ASK', edgecolor='darkgreen', linewidth=0.5)

    # Set y-axis labels to prices
    ax.set_yticks(y_positions)
    ax.set_yticklabels([f"{p:.2f}" for p in prices], fontsize=8)

    # Add vertical line at zero
    ax.axvline(x=0, color='black', linewidth=1.5, linestyle='-', alpha=0.7)

    # Add blue dot at closing price
    if closing_price is not None and closing_price in prices:
        price_idx = prices.index(closing_price)
        ax.plot(0, price_idx, 'o', color='blue', markersize=10, zorder=5,
                markeredgecolor='darkblue', markeredgewidth=2)

    # Calculate max x-axis limit
    max_bid = max(bid_volumes) if bid_volumes else 1
    max_ask = max(ask_volumes) if ask_volumes else 1
    max_x = max(max_bid, max_ask) * 1.1
    ax.set_xlim(-max_x, max_x)

    # Labels and title
    ax.set_xlabel('Volume (BID ← | → ASK)', fontsize=11, fontweight='bold')
    ax.set_ylabel('Price Level', fontsize=11, fontweight='bold')

    # Title with closing price
    close_str = f' | Close: {closing_price:.2f}' if closing_price is not None else ''
    ax.set_title(f'Market Profile at {timestamp.strftime("%Y-%m-%d %H:%M:%S")}{close_str}\n'
                 f'({PROFILE_WINDOW}s rolling window | Step {index+1}/{len(profiles_data)})',
                 fontsize=10, fontweight='bold', pad=10)

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

    fig.canvas.draw_idle()

def plot_merged(index):
    """Plot merged order book and market profile on same chart."""
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
        ax.set_title(f"Merged View at {timestamp}")
        return

    # Calculate continuous price range with no gaps
    tick_size = 0.25

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

    # Plot ORDER BOOK bars (diagonal dashes, grey colors with 0.25 opacity)
    bid_color_dom = '#999999'  # Grey
    ask_color_dom = '#aaaaaa'  # Light grey

    ax.barh(y_positions, [-size for size in dom_bid_sizes], height=0.8,
            color=bid_color_dom, label='DOM BID', edgecolor='#666666',
            linewidth=1.5, hatch='///', alpha=0.25, zorder=1)
    ax.barh(y_positions, dom_ask_sizes, height=0.8,
            color=ask_color_dom, label='DOM ASK', edgecolor='#888888',
            linewidth=1.5, hatch='///', alpha=0.25, zorder=1)

    # Overlay MARKET PROFILE bars (dashed transparent, red/green)
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

        bid_color_mp = (0.8, 0, 0, 0.7)  # Red, semi-transparent
        ask_color_mp = (0, 0.7, 0, 0.7)  # Green, semi-transparent

        # Plot solid bars (on top of order book bars)
        ax.barh(y_positions, [-v for v in mp_bid_scaled], height=0.6,
                color=bid_color_mp, label='Profile BID', alpha=0.7, zorder=10)
        ax.barh(y_positions, mp_ask_scaled, height=0.6,
                color=ask_color_mp, label='Profile ASK', alpha=0.7, zorder=10)

    # Set y-axis to prices
    ax.set_yticks(y_positions)
    ax.set_yticklabels([f"{p:.2f}" for p in all_prices], fontsize=8)

    # Add vertical line at zero (between order book and market profile)
    ax.axvline(x=0, color='black', linewidth=2, linestyle='-', alpha=0.7, zorder=2)

    # Mark current price (on top of everything)
    if closing_price and closing_price in all_prices:
        price_idx = all_prices.index(closing_price)
        ax.axhline(y=price_idx, color='blue', linewidth=2, linestyle='--', alpha=0.6, zorder=25)
        ax.plot(0, price_idx, 'o', color='blue', markersize=12, zorder=30,
                markeredgecolor='darkblue', markeredgewidth=2)

    # Set x-axis limits
    ax.set_xlim(-max_dom_size * 1.1, max_dom_size * 1.1)

    # Add dashed rectangle border
    from matplotlib.patches import Rectangle
    if len(y_positions) > 0:
        rect = Rectangle(
            (-max_dom_size * 1.1, -0.5),
            max_dom_size * 2.2,
            len(y_positions),
            linewidth=2,
            edgecolor='gray',
            facecolor='none',
            linestyle='--',
            alpha=0.7,
            zorder=20
        )
        ax.add_patch(rect)

    # Labels and title
    ax.set_xlabel('Size (BID ← | → ASK)', fontsize=11, fontweight='bold')
    ax.set_ylabel('Price Level', fontsize=11, fontweight='bold')

    close_str = f' | Close: {closing_price:.2f}' if closing_price is not None else ''
    ax.set_title(f'Merged Order Book + Market Profile at {timestamp.strftime("%Y-%m-%d %H:%M:%S")}{close_str}\n'
                 f'({PROFILE_WINDOW}s rolling window | Step {index+1}/{len(profiles_data)})',
                 fontsize=11, fontweight='bold', pad=10)

    # Grid
    ax.grid(True, alpha=0.3, axis='x')

    # Legend
    ax.legend(loc='upper right', fontsize=9, ncol=2)

    # Statistics
    total_dom_bid = sum(dom_bid_sizes)
    total_dom_ask = sum(dom_ask_sizes)

    stats_text = f'DOM BID: {total_dom_bid:.0f} | DOM ASK: {total_dom_ask:.0f}\n'

    if profile:
        total_mp_bid = sum(mp_bid_volumes)
        total_mp_ask = sum(mp_ask_volumes)
        stats_text += f'Profile BID: {total_mp_bid:.0f} | Profile ASK: {total_mp_ask:.0f}'

    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
            fontsize=9, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.7))

    fig.canvas.draw_idle()

def plot_all(index):
    """Wrapper for backward compatibility."""
    plot_merged(index)

def update_slider(val):
    """Update plot when slider changes."""
    if not is_playing[0]:
        index = int(slider.val)
        current_index[0] = index
        plot_all(index)

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
    plot_all(current_index[0])

def prev_frame(event):
    """Go to previous frame."""
    if is_playing[0]:
        pause(None)

    current_index[0] = max(current_index[0] - 1, 0)
    slider.eventson = False
    slider.set_val(current_index[0])
    slider.eventson = True
    plot_all(current_index[0])

def animate():
    """Animation function."""
    if not is_playing[0]:
        return

    current_index[0] += 1
    if current_index[0] >= len(profiles_data):
        current_index[0] = 0

    slider.set_val(current_index[0])
    plot_all(current_index[0])

    # Schedule next frame (500ms delay)
    timer[0] = fig.canvas.new_timer(interval=500)
    timer[0].single_shot = True
    timer[0].add_callback(animate)
    timer[0].start()

# Create slider for navigation
ax_slider = plt.axes([0.1, 0.06, 0.85, 0.02])
slider = Slider(ax_slider, 'Time', 0, len(profiles_data) - 1,
                valinit=start_idx, valstep=1, color='skyblue')
slider.on_changed(update_slider)

# Create buttons
ax_prev = plt.axes([0.1, 0.02, 0.08, 0.03])
ax_play = plt.axes([0.22, 0.02, 0.08, 0.03])
ax_pause = plt.axes([0.34, 0.02, 0.08, 0.03])
ax_next = plt.axes([0.46, 0.02, 0.08, 0.03])

btn_prev = Button(ax_prev, 'Previous', color='lightgray', hovercolor='gray')
btn_play = Button(ax_play, 'Play', color='lightgreen', hovercolor='green')
btn_pause = Button(ax_pause, 'Pause', color='lightcoral', hovercolor='red')
btn_next = Button(ax_next, 'Next', color='lightgray', hovercolor='gray')

btn_prev.on_clicked(prev_frame)
btn_play.on_clicked(play)
btn_pause.on_clicked(pause)
btn_next.on_clicked(next_frame)

# Initial plot
plot_all(start_idx)

print("\nControls:")
print("  - Slider: Navigate to any time point")
print("  - Previous/Next: Step through frames")
print("  - Play: Start animation (500ms per frame)")
print("  - Pause: Stop animation")
print("\nVisualization:")
print("  - Merged chart showing Order Book + Market Profile overlay")
print("  - Grey diagonal dashed bars: Order Book (pending orders)")
print("  - Solid red/green bars: Market Profile (executed volume)")
print("\nClose the window to exit.")

plt.show()
