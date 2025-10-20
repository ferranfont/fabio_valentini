import sys
sys.path.insert(0, '/home/idroji/trading/workspace/fabio_valentini/strat_absortion')

import pandas as pd
import numpy as np
from datetime import timedelta
from rolling_profile import RollingMarketProfile

# Use TkAgg backend for better compatibility
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.widgets import Button, Slider

# Load data
csv_path = "../data/time_and_sales_nq_30min.csv"
print("Loading data...")
df = pd.read_csv(csv_path, sep=";", decimal=",")
df["Timestamp"] = pd.to_datetime(df["Timestamp"])

# Generate timestamps every 10 seconds
start_time = df["Timestamp"].min()
end_time = df["Timestamp"].max()
timestamps = pd.date_range(start=start_time, end=end_time, freq="10s")
print(f"Generated {len(timestamps)} timestamps (every 10 seconds)")

# Pre-compute market profiles for all timestamps
print("Pre-computing market profiles...")
profiles_data = []

for i, ts in enumerate(timestamps):
    if i % 50 == 0:
        print(f"  Processing {i}/{len(timestamps)}...")

    mp = RollingMarketProfile(window=timedelta(seconds=60))
    ticks_until = df[df["Timestamp"] <= ts]

    for _, row in ticks_until.iterrows():
        mp.update(row["Timestamp"], row["Precio"], row["Volumen"], row["Lado"])

    profile = mp.profile()
    profiles_data.append((ts, profile))

print(f"Pre-computed {len(profiles_data)} profiles")

# Create the figure and axis
fig, ax = plt.subplots(figsize=(14, 10))
plt.subplots_adjust(left=0.1, bottom=0.25, right=0.95, top=0.95)

# Global state
current_index = [0]
is_playing = [False]
timer = [None]

def get_color_with_intensity(base_color, volume, max_volume):
    """Generate color with intensity based on volume."""
    if max_volume == 0:
        intensity = 0.3
    else:
        # Scale from 0.3 (low) to 1.0 (high)
        intensity = 0.3 + 0.7 * (volume / max_volume)

    if base_color == 'green':
        return (0, intensity, 0, 0.8)  # Green with varying intensity
    else:  # red
        return (intensity, 0, 0, 0.8)  # Red with varying intensity

def plot_profile(index):
    """Plot the market profile for a given index."""
    ax.clear()

    if index >= len(profiles_data):
        index = len(profiles_data) - 1

    timestamp, profile = profiles_data[index]

    if not profile:
        ax.text(0.5, 0.5, "No data in rolling window",
                ha='center', va='center', fontsize=14)
        ax.set_title(f"Market Profile at {timestamp}")
        return

    # Extract prices and volumes
    prices = sorted(profile.keys())
    bid_volumes = [profile[p]["BID"] for p in prices]
    ask_volumes = [profile[p]["ASK"] for p in prices]

    # Get max volume for color scaling
    max_bid = max(bid_volumes) if bid_volumes else 1
    max_ask = max(ask_volumes) if ask_volumes else 1

    # Create horizontal bars
    y_positions = range(len(prices))

    # Plot BID volumes (left side, negative values, red)
    bid_colors = [get_color_with_intensity('red', v, max_bid) for v in bid_volumes]
    ax.barh(y_positions, [-v for v in bid_volumes], height=0.8,
            color=bid_colors, label='BID', edgecolor='darkred', linewidth=0.5)

    # Plot ASK volumes (right side, positive values, green)
    ask_colors = [get_color_with_intensity('green', v, max_ask) for v in ask_volumes]
    ax.barh(y_positions, ask_volumes, height=0.8,
            color=ask_colors, label='ASK', edgecolor='darkgreen', linewidth=0.5)

    # Set y-axis labels to prices
    ax.set_yticks(y_positions)
    ax.set_yticklabels([f"{p:.2f}" for p in prices], fontsize=8)

    # Add vertical line at zero
    ax.axvline(x=0, color='black', linewidth=1.5, linestyle='-', alpha=0.7)

    # Calculate max x-axis limit
    max_x = max(max(bid_volumes), max(ask_volumes)) * 1.1
    ax.set_xlim(-max_x, max_x)

    # Labels and title
    ax.set_xlabel('Volume (BID ← | → ASK)', fontsize=11, fontweight='bold')
    ax.set_ylabel('Price Level', fontsize=11, fontweight='bold')
    ax.set_title(f'Market Profile at {timestamp.strftime("%Y-%m-%d %H:%M:%S")}\n'
                 f'(60-second rolling window | Step {index+1}/{len(profiles_data)})',
                 fontsize=13, fontweight='bold', pad=15)

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
        timer[0].remove()
        timer[0] = None

def next_frame(event):
    """Go to next frame."""
    pause(None)
    current_index[0] = min(current_index[0] + 1, len(profiles_data) - 1)
    slider.set_val(current_index[0])
    plot_profile(current_index[0])

def prev_frame(event):
    """Go to previous frame."""
    pause(None)
    current_index[0] = max(current_index[0] - 1, 0)
    slider.set_val(current_index[0])
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
                valinit=0, valstep=1, color='skyblue')
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
plot_profile(0)

print("\nControls:")
print("  - Slider: Navigate to any time point")
print("  - Previous/Next: Step through frames")
print("  - Play: Start animation (500ms per frame)")
print("  - Pause: Stop animation")
print("\nClose the window to exit.")

plt.show()
