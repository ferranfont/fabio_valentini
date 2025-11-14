import pandas as pd
from datetime import timedelta, datetime
from pathlib import Path
import sys

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
ROLLING_PROFILE_DIR = PROJECT_ROOT / "strat_absortion"
if str(ROLLING_PROFILE_DIR) not in sys.path:
    sys.path.append(str(ROLLING_PROFILE_DIR))

from rolling_profile import RollingMarketProfile

# Use TkAgg backend for better compatibility
import matplotlib
matplotlib.use('TkAgg')
import mplcursors
import matplotlib.pyplot as plt
from matplotlib.widgets import Button, Slider

# Force window to frontferr
import os
os.environ['QT_QPA_PLATFORM'] = 'windows'

# ============ CONFIGURATION ============
STARTING_INDEX = 0  # Change this to start at a different frame (0 = first frame)
# You can also set a specific time like: STARTING_TIME = "2025-10-09 18:15:00"
STARTING_TIME =  None   #"2025-10-09 18:02:25"    #None  # Set to None to use STARTING_INDEX instead
PROFILE_FREQUENCY = 1  # Frequency for Market Profile in seconds
FRAME_FREQUENCY = "1s" # Frequency for frame updates (500ms = 0.5 seconds)

# Mushroom profile detection configuration
TICK_SIZE = 0.25                # Price tick size for grouping levels
MIN_FLOOR_LEVELS = 9            # Minimum number of active price levels
CAP_FLOOR_LEVELS = 3            # Number of upper levels considered the cap block
UPPER_CLOSE_LEVELS = 3          # Closing price must fall inside these top levels (if enforced)
CAP_ASK_SHARE_MIN = 0.20        # Minimum ASK dominance inside the cap
STEM_ASK_FRAC_MAX = 0.05        # Maximum ASK participation across the stem
CHANGE_DIFF = 2.0               # Minimum positive price change vs previous frame (points)
INSIDE_PRICE = True             # Require closing price in the top price band (upper levels / upper half)
# =======================================
 
# Load data
csv_path = PROJECT_ROOT / "data" / "historic" / "time_and_sales_nq_20251022.csv"
#csv_path = "data/time_and_sales.csv"

print("Loading data...")
print(f"File path: {csv_path}")
print(f"File exists: {csv_path.exists()}")
df = pd.read_csv(csv_path, sep=";", decimal=",")
df["Timestamp"] = pd.to_datetime(df["Timestamp"])

# Pre-compute market profiles with 10-second aggregation
# FIXED: Create ONE RollingMarketProfile and process ticks sequentially
print("Pre-computing market profiles...")
profiles_data = []

# Generate timestamps every 0.5 seconds for aggregation
start_time = df["Timestamp"].min()
end_time = df["Timestamp"].max()
timestamps = pd.date_range(start=start_time, end=end_time, freq=FRAME_FREQUENCY)

# Create a SINGLE RollingMarketProfile instance
mp = RollingMarketProfile(
    window=timedelta(seconds=PROFILE_FREQUENCY),
    price_tick=TICK_SIZE,
)

total_ticks = len(df)
tick_idx = 0
last_known_price = None

for i, ts in enumerate(timestamps):
    if i % 50 == 0:
        print(f"  Processing {i}/{len(timestamps)}... (tick {tick_idx}/{total_ticks})")

    # Process all ticks up to this timestamp
    while tick_idx < total_ticks and df.iloc[tick_idx]["Timestamp"] <= ts:
        row = df.iloc[tick_idx]
        mp.update(row["Timestamp"], row["Precio"], row["Volumen"], row["Lado"])
        last_known_price = row["Precio"]  # Track last known price
        tick_idx += 1

    # Get closing price (last known price up to this timestamp)
    closing_price = last_known_price

    # Get the current profile (rolling window automatically maintained)
    profile = mp.profile()
    profiles_data.append((ts, profile, closing_price))

print(f"Pre-computed {len(profiles_data)} profiles (processed {tick_idx} ticks)")

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

# Store signal metadata for hover tooltips
signal_metadata = []  # List of dicts with signal info and positions
signal_scatter_mushroom = None  # Scatter plot for mushroom signals

def get_fixed_color(base_color):
    """Return fixed color."""
    if base_color == 'green':
        return (0, 0.7, 0, 0.8)  # Fixed green
    else:  # red
        return (0.8, 0, 0, 0.8)  # Fixed red

def evaluate_mushroom_profile(profile, closing_price, tick_size=TICK_SIZE):
    """
    Evaluate whether the rolling market profile forms a "mushroom" pattern.

    Criteria:
        1. At least MIN_FLOOR_LEVELS price levels with volume (stem + cap).
        2. Closing price located inside the upper band (top UPPER_CLOSE_LEVELS or upper 50% of range).
        3. ASK volume dominates inside the cap (>= CAP_ASK_SHARE_MIN).
        4. Stem ASK participation is almost null (<= STEM_ASK_FRAC_MAX of total volume).

    Returns:
        dict with metrics and a boolean 'mushroom' flag, or None if profile/price missing.
    """
    if not profile or closing_price is None or pd.isna(closing_price):
        return None

    active_prices = sorted(
        price for price, data in profile.items()
        if data.get('BID', 0) > 0 or data.get('ASK', 0) > 0
    )
    if not active_prices:
        return None

    floors_count = len(active_prices)
    total_bid = float(sum(profile[p].get('BID', 0.0) for p in active_prices))
    total_ask = float(sum(profile[p].get('ASK', 0.0) for p in active_prices))
    total_volume = total_bid + total_ask
    if total_volume <= 0:
        return None

    cap_span = CAP_FLOOR_LEVELS if CAP_FLOOR_LEVELS > 0 else len(active_prices)
    cap_levels = active_prices[-cap_span:] if floors_count >= cap_span else active_prices
    stem_levels = active_prices[:-len(cap_levels)] if len(cap_levels) < len(active_prices) else []

    cap_bid = float(sum(profile[p].get('BID', 0.0) for p in cap_levels))
    cap_ask = float(sum(profile[p].get('ASK', 0.0) for p in cap_levels))
    cap_total = cap_bid + cap_ask
    cap_ask_share = (cap_ask / cap_total) if cap_total > 0 else 0.0

    stem_bid = float(sum(profile[p].get('BID', 0.0) for p in stem_levels)) if stem_levels else 0.0
    stem_ask = float(sum(profile[p].get('ASK', 0.0) for p in stem_levels)) if stem_levels else 0.0
    stem_total = stem_bid + stem_ask
    stem_ask_frac_stem = (stem_ask / stem_total) if stem_total > 0 else 0.0

    tolerance = (tick_size or 0.0) / 2 if tick_size else 0.0
    upper_levels = active_prices[-UPPER_CLOSE_LEVELS:] if floors_count >= UPPER_CLOSE_LEVELS else active_prices
    upper_min = upper_levels[0] if upper_levels else None
    upper_max = upper_levels[-1] if upper_levels else None
    close_in_upper_band = False
    if upper_min is not None and upper_max is not None:
        close_in_upper_band = (closing_price >= upper_min - tolerance) and (closing_price <= upper_max + tolerance)

    min_price = min(active_prices)
    max_price = max(active_prices)
    price_range = max_price - min_price if max_price is not None else 0
    price_position = 0.0
    if price_range > 0:
        price_position = (closing_price - min_price) / price_range

    close_in_cap = close_in_upper_band or (price_position >= 0.5)

    cond_min_floors = floors_count >= MIN_FLOOR_LEVELS
    cond_cap_ask_dominant = cap_total > 0 and cap_ask_share >= CAP_ASK_SHARE_MIN
    cond_stem_ask_small = stem_ask_frac_stem <= STEM_ASK_FRAC_MAX
    cond_close_band = (close_in_cap if INSIDE_PRICE else True)

    mushroom = all([
        cond_min_floors,
        cond_close_band,
        cond_cap_ask_dominant,
        cond_stem_ask_small,
    ])

    return {
        'mushroom': bool(mushroom),
        'floors_count': floors_count,
        'cap_floor_levels': len(cap_levels),
        'stem_floor_levels': max(floors_count - len(cap_levels), 0),
        'close_in_cap': bool(close_in_cap),
        'cap_bid': cap_bid,
        'cap_ask': cap_ask,
        'cap_total': cap_total,
        'cap_ask_share': cap_ask_share,
        'stem_bid': stem_bid,
        'stem_ask': stem_ask,
        'stem_total': stem_total,
        'stem_ask_frac_stem': stem_ask_frac_stem,
        'total_bid': total_bid,
        'total_ask': total_ask,
        'total_volume': total_volume,
        'cond_min_floors': cond_min_floors,
        'cond_close_in_cap': bool(close_in_cap),
        'cond_cap_ask_dominant': cond_cap_ask_dominant,
        'cond_stem_ask_small': cond_stem_ask_small,
        'upper_band_min': upper_min,
        'upper_band_max': upper_max,
        'price_position': price_position,
    }

def extract_all_frames_data(profiles_data, df_ticks, window_seconds=PROFILE_FREQUENCY):
    """
    Extract aggregated OHLCV data for ALL frames (EVERY timestamp, not just Mushroom signals).

    This function creates a complete snapshot of EVERY 1-second frame with:
    - OHLCV (Open, High, Low, Close) aggregated from ticks
    - BID/ASK volume breakdown
    - Pattern tag (mushroom, neutral, etc.)
    - Complete Market Profile metrics

    Output: 100% coverage of all processed timestamps (~172k rows for a full day).

    Args:
        profiles_data: List of (timestamp, profile, closing_price) tuples
        df_ticks: Original tick data DataFrame
        window_seconds: Window size in seconds for aggregation

    Returns:
        DataFrame with ALL frames (mushroom + neutral + any other patterns)
    """
    all_frames = []

    for i, (timestamp, profile, closing_price) in enumerate(profiles_data):
        if i % 1000 == 0:
            print(f"  Extracting frame data {i}/{len(profiles_data)}...")

        # Get previous close for price change calculation
        previous_close = None
        if i > 0 and i - 1 < len(profiles_data):
            _, _, previous_close = profiles_data[i - 1]

        # Calculate price change
        price_change = closing_price - previous_close if previous_close is not None else 0
        price_change_pct = (price_change / previous_close * 100) if previous_close is not None and previous_close != 0 else 0

        # Extract ticks for this frame window
        window_start = timestamp - timedelta(seconds=window_seconds)
        window_end = timestamp
        frame_ticks = df_ticks[(df_ticks['Timestamp'] > window_start) & (df_ticks['Timestamp'] <= window_end)]

        # Calculate OHLC from frame ticks
        if len(frame_ticks) > 0:
            frame_open = frame_ticks.iloc[0]['Precio']
            frame_high = frame_ticks['Precio'].max()
            frame_low = frame_ticks['Precio'].min()
            frame_close = frame_ticks.iloc[-1]['Precio']
            tick_count = len(frame_ticks)

            # Calculate BID/ASK volumes from frame ticks
            bid_ticks = frame_ticks[frame_ticks['Lado'] == 'BID']
            ask_ticks = frame_ticks[frame_ticks['Lado'] == 'ASK']
            total_bid = bid_ticks['Volumen'].sum() if len(bid_ticks) > 0 else 0
            total_ask = ask_ticks['Volumen'].sum() if len(ask_ticks) > 0 else 0
            total_volume = total_bid + total_ask
            bid_ask_ratio = total_bid / total_ask if total_ask > 0 else 0
        else:
            frame_open = frame_high = frame_low = frame_close = closing_price
            tick_count = 0
            total_bid = total_ask = total_volume = bid_ask_ratio = 0

        # Count active price levels from profile
        num_price_levels = 0
        if profile:
            num_price_levels = len([p for p in profile.keys() if profile[p].get('BID', 0) > 0 or profile[p].get('ASK', 0) > 0])

        # Evaluate mushroom pattern
        mushroom_metrics = evaluate_mushroom_profile(profile, closing_price) if profile and closing_price is not None else None

        # Determine pattern tag
        pattern_tag = 'neutral'
        if mushroom_metrics and mushroom_metrics.get('mushroom'):
            # Check price change condition
            if price_change >= CHANGE_DIFF:
                pattern_tag = 'mushroom'

        # Build frame data dictionary
        frame_data = {
            'timestamp': timestamp,
            'pattern_tag': pattern_tag,
            'close_price': closing_price,
            'previous_close': previous_close,
            'price_change': price_change,
            'price_change_pct': price_change_pct,
            'frame_open': frame_open,
            'frame_high': frame_high,
            'frame_low': frame_low,
            'frame_close': frame_close,
            'total_bid': total_bid,
            'total_ask': total_ask,
            'bid_ask_ratio': bid_ask_ratio,
            'total_volume': total_volume,
            'tick_count': tick_count,
            'num_price_levels': num_price_levels,
        }

        # Add mushroom metrics if available
        if mushroom_metrics:
            frame_data.update({
                'floors_count': mushroom_metrics['floors_count'],
                'cap_floor_levels': mushroom_metrics['cap_floor_levels'],
                'stem_floor_levels': mushroom_metrics['stem_floor_levels'],
                'close_in_cap': mushroom_metrics['close_in_cap'],
                'cap_bid': mushroom_metrics['cap_bid'],
                'cap_ask': mushroom_metrics['cap_ask'],
                'cap_total': mushroom_metrics['cap_total'],
                'cap_ask_share': mushroom_metrics['cap_ask_share'],
                'stem_bid': mushroom_metrics['stem_bid'],
                'stem_ask': mushroom_metrics['stem_ask'],
                'stem_total': mushroom_metrics['stem_total'],
                'stem_ask_frac_stem': mushroom_metrics['stem_ask_frac_stem'],
                'cond_min_floors': mushroom_metrics['cond_min_floors'],
                'cond_close_in_cap': mushroom_metrics['cond_close_in_cap'],
                'cond_cap_ask_dominant': mushroom_metrics['cond_cap_ask_dominant'],
                'cond_stem_ask_small': mushroom_metrics['cond_stem_ask_small'],
                'price_position': mushroom_metrics['price_position'],
            })
        else:
            # Fill with None if no mushroom metrics
            frame_data.update({
                'floors_count': None,
                'cap_floor_levels': None,
                'stem_floor_levels': None,
                'close_in_cap': None,
                'cap_bid': None,
                'cap_ask': None,
                'cap_total': None,
                'cap_ask_share': None,
                'stem_bid': None,
                'stem_ask': None,
                'stem_total': None,
                'stem_ask_frac_stem': None,
                'cond_min_floors': None,
                'cond_close_in_cap': None,
                'cond_cap_ask_dominant': None,
                'cond_stem_ask_small': None,
                'price_position': None,
            })

        all_frames.append(frame_data)

    return pd.DataFrame(all_frames)

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
        # Add horizontal dashed blue line at closing price level
        ax.axhline(y=price_idx, color='blue', linewidth=1, linestyle='--', alpha=0.6, zorder=4)
        # Add blue dot on top of the line
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

    # Evaluate mushroom profile using current close price
    mushroom_metrics = evaluate_mushroom_profile(profile, closing_price)

    price_change = None
    if previous_close is not None and closing_price is not None:
        price_change = closing_price - previous_close
    change_condition_met = price_change is not None and price_change >= CHANGE_DIFF

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

    # Calculate real change and volume for this frame
    if price_change is not None:
        stats_text += f'Change: {price_change:.2f}\n'
    else:
        stats_text += f'Change: N/A\n'

    total_volume = total_bid + total_ask
    stats_text += f'Volume: {total_volume:.0f}\n'

    # Format profile tag: Mushroom or Neutral (requires price change condition)
    profile_is_mushroom = bool(mushroom_metrics and mushroom_metrics.get('mushroom') and change_condition_met)
    profile_display = "Mushroom" if profile_is_mushroom else "Neutral"
    stats_text += f'PROFILE: {profile_display}'

    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
            fontsize=9, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    return prices, (bid_volumes, ask_volumes)

def plot_price_line(index):
    """Plot price line chart showing historical close prices."""
    global signal_metadata, signal_scatter_mushroom
    ax_price.clear()
    signal_metadata = []  # Reset signal metadata for this frame
    signal_scatter_mushroom = None

    # Lists to collect signal coordinates for scatter plot
    mushroom_times, mushroom_prices = [], []

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
                    ax_price.plot(ts_marker, close_marker, 'o', color='grey',
                                  markersize=5, alpha=0.6, zorder=4)

        # Plot mushroom signals for ALL historical data in view
        for hist_idx in range(start_idx, index + 1):
            if hist_idx < len(profiles_data):
                ts_sig, profile_sig, close_sig = profiles_data[hist_idx]

                if close_sig is None or not profile_sig:
                    continue

                previous_close_sig = None
                if hist_idx > 0 and hist_idx - 1 < len(profiles_data):
                    _, _, previous_close_sig = profiles_data[hist_idx - 1]

                if previous_close_sig is None:
                    continue

                price_change_sig = close_sig - previous_close_sig
                if price_change_sig < CHANGE_DIFF:
                    continue

                metrics = evaluate_mushroom_profile(profile_sig, close_sig)
                if metrics and metrics.get('mushroom'):
                    metadata = {
                        'timestamp': ts_sig,
                        'price': close_sig,
                        'price_change': price_change_sig,
                        'floors_count': metrics['floors_count'],
                        'cap_floor_levels': metrics['cap_floor_levels'],
                        'stem_floor_levels': metrics['stem_floor_levels'],
                        'cap_ask_share': metrics['cap_ask_share'],
                        'stem_ask_frac': metrics['stem_ask_frac_stem'],
                        'cap_bid': metrics['cap_bid'],
                        'cap_ask': metrics['cap_ask'],
                        'cap_total': metrics['cap_total'],
                        'stem_bid': metrics['stem_bid'],
                        'stem_ask': metrics['stem_ask'],
                        'total_volume': metrics['total_volume'],
                        'close_in_cap': metrics['close_in_cap'],
                        'cond_min_floors': metrics['cond_min_floors'],
                        'cond_cap_ask_dominant': metrics['cond_cap_ask_dominant'],
                        'cond_stem_ask_small': metrics['cond_stem_ask_small'],
                    }
                    mushroom_times.append(ts_sig)
                    mushroom_prices.append(close_sig)
                    signal_metadata.append(metadata)

        if len(mushroom_times) > 0:
            signal_scatter_mushroom = ax_price.scatter(
                mushroom_times,
                mushroom_prices,
                s=80,
                c='magenta',
                alpha=0.95,
                zorder=6,
                edgecolors='black',
                linewidths=1.0,
                label='Mushroom'
            )

        # Mark current price with a blue dot (on top of everything)
        if len(times) > 0:
            ax_price.plot(times[-1], prices[-1], 'o', color='blue',
                          markersize=8, zorder=7)

        # Formatting
        ax_price.grid(True, alpha=0.3, axis='y')

        import matplotlib.dates as mdates
        from matplotlib.ticker import ScalarFormatter
        ax_price.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        ax_price.tick_params(axis='x', rotation=0, labelsize=6)
        ax_price.tick_params(axis='y', labelsize=7)
        ax_price.yaxis.set_major_formatter(ScalarFormatter(useOffset=False))
        ax_price.ticklabel_format(style='plain', axis='y')

        # Add current price info - calculate change from previous close
        current_price = prices[-1]

        previous_price = None
        if index > 0 and index - 1 < len(profiles_data):
            _, _, prev_close = profiles_data[index - 1]
            previous_price = prev_close

        if previous_price is not None:
            price_change = current_price - previous_price
            price_change_pct = (price_change / previous_price * 100) if previous_price != 0 else 0
            info_text = f'Close: {current_price:.2f}\n'
            info_text += f'Change: {price_change:+.2f} ({price_change_pct:+.2f}%)'
        else:
            info_text = f'Close: {current_price:.2f}\n'
            info_text += f'Change: N/A'

        ax_price.text(
            0.02,
            0.02,
            info_text,
            transform=ax_price.transAxes,
            fontsize=9,
            verticalalignment='bottom',
            horizontalalignment='left',
            bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.7),
        )

# Setup mplcursors for interactive tooltips on signal dots
cursors_mushroom = None

def setup_cursors():
    """Setup mplcursors after scatter plots are created."""
    global cursors_mushroom, signal_scatter_mushroom

    if cursors_mushroom is not None:
        try:
            cursors_mushroom.remove()
        except:
            pass

    if signal_scatter_mushroom is not None:
        cursors_mushroom = mplcursors.cursor(signal_scatter_mushroom, hover=True)

        @cursors_mushroom.connect("add")
        def on_add_mushroom(sel):
            idx = sel.index
            if idx < len(signal_metadata):
                meta = signal_metadata[idx]
                text = "PROFILE: Mushroom\n"
                text += f"Time: {meta['timestamp'].strftime('%H:%M:%S')}\n"
                text += f"Price: {meta['price']:.2f}\n"
                text += f"Change: {meta['price_change']:.2f}\n"
                text += f"Floors: {meta['floors_count']}\n"
                text += f"Cap Levels: {meta['cap_floor_levels']}\n"
                text += f"Stem Levels: {meta['stem_floor_levels']}\n"
                text += f"Cap ASK share: {meta['cap_ask_share']:.2%}\n"
                text += f"Stem ASK frac: {meta['stem_ask_frac']:.2%}\n"
                text += f"Cap ASK: {meta['cap_ask']:.0f}\n"
                text += f"Cap BID: {meta['cap_bid']:.0f}\n"
                text += f"Stem BID: {meta['stem_bid']:.0f}\n"
                text += f"Stem ASK: {meta['stem_ask']:.0f}\n"
                text += f"Cap Total: {meta['cap_total']:.0f}\n"
                text += f"Volume: {meta['total_volume']:.0f}\n"
                text += f"Close in cap: {meta['close_in_cap']}\n"
                text += f"Min floors: {meta['cond_min_floors']}\n"
                text += f"Cap ASK dom: {meta['cond_cap_ask_dominant']}\n"
                text += f"Stem ASK tiny: {meta['cond_stem_ask_small']}"
                sel.annotation.set_text(text)
                sel.annotation.get_bbox_patch().set(
                    fc='lightgrey', alpha=0.3, edgecolor='black', linewidth=2
                )
                sel.annotation.set_fontsize(9)
                sel.annotation.set_fontweight('bold')

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

    # Setup cursors for tooltips on signal dots
    setup_cursors()

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

# Extract ALL frames data (OHLCV + pattern tags for EVERY frame, not just signals)
print("\nExtracting ALL frames data with OHLCV aggregation...")
print(f"Processing {len(profiles_data)} frames (this takes ~1-2 minutes)...")
df_all_frames = extract_all_frames_data(profiles_data, df, window_seconds=PROFILE_FREQUENCY)

# Save ALL frames to CSV in strat_sweep folder
all_frames_output = CURRENT_DIR / "db_mushroom_all_data.csv"
df_all_frames.to_csv(all_frames_output, index=False, sep=';', decimal=',')
print(f"[OK] Saved {len(df_all_frames)} frames to {all_frames_output}")
print(f"  - Mushroom frames: {len(df_all_frames[df_all_frames['pattern_tag'] == 'mushroom'])}")
print(f"  - Neutral frames: {len(df_all_frames[df_all_frames['pattern_tag'] == 'neutral'])}")
print(f"  - Total coverage: 100% of all processed timestamps")

# Detect and save mushroom signals to CSV (only signals)
print("\nDetecting Mushroom patterns (signals only)...")
output_dir = Path("outputs")
output_dir.mkdir(exist_ok=True)

# Generate filename with data date (20251022)
#timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
csv_path_output = output_dir / "db_mushroom_dom_20251022.csv"

signals = []
for i, (timestamp, profile, closing_price) in enumerate(profiles_data):
    if not profile or closing_price is None:
        continue

    previous_close = None
    if i > 0 and i - 1 < len(profiles_data):
        _, _, previous_close = profiles_data[i - 1]

    if previous_close is None:
        continue

    price_change = closing_price - previous_close
    if price_change < CHANGE_DIFF:
        continue

    metrics = evaluate_mushroom_profile(profile, closing_price)

    if metrics and metrics.get('mushroom'):
        signals.append({
            'timestamp': timestamp,
            'mushroom': True,
            'close_price': closing_price,
            'previous_close': previous_close,
            'price_change': price_change,
            'total_bid': metrics['total_bid'],
            'total_ask': metrics['total_ask'],
            'total_volume': metrics['total_volume'],
            'floors_count': metrics['floors_count'],
            'cap_floor_levels': metrics['cap_floor_levels'],
            'stem_floor_levels': metrics['stem_floor_levels'],
            'close_in_cap': metrics['close_in_cap'],
            'cap_bid': metrics['cap_bid'],
            'cap_ask': metrics['cap_ask'],
            'cap_total': metrics['cap_total'],
            'cap_ask_share': metrics['cap_ask_share'],
            'stem_bid': metrics['stem_bid'],
            'stem_ask': metrics['stem_ask'],
            'stem_total': metrics['stem_total'],
            'stem_ask_frac_stem': metrics['stem_ask_frac_stem'],
            'cond_min_floors': metrics['cond_min_floors'],
            'cond_cap_ask_dominant': metrics['cond_cap_ask_dominant'],
            'cond_stem_ask_small': metrics['cond_stem_ask_small'],
        })

# Save to CSV
if signals:
    df_signals = pd.DataFrame(signals)
    df_signals.to_csv(csv_path_output, index=False, sep=';', decimal=',')
    print(f"Saved {len(signals)} Mushroom signals to {csv_path_output}")
else:
    print("No Mushroom signals detected")

# Force window to be visible and bring to front
try:
    fig.canvas.manager.window.wm_attributes('-topmost', 1)
    fig.canvas.manager.window.after_idle(fig.canvas.manager.window.attributes, '-topmost', False)
except:
    pass

plt.show(block=True)
