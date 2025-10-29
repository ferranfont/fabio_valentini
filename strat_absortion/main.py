import base64
import io
import os
import sys
from datetime import timedelta
from typing import Optional
import matplotlib

matplotlib.use("Agg")  # Use non-interactive backend
import matplotlib.pyplot as plt

csv_path = (
    "../data/time_and_sales_nq.csv"  # Can use time_and_sales_nq.csv or ts_and_dom_*.csv
)

# Profile shape detection configuration (modified from plot_deep.py)
EXTREME_VOLUME_MULTIPLIER = 3  # Extreme bar must be N times the second-largest overall
MIN_PRICE_LEVELS = 10  # Minimum number of active price levels
MIN_BID_ASK_SIZE = 30  # Minimum absolute size of largest BID/ASK bar
PRICE_POSITION_THRESHOLD = 0.3  # Price must be in lower/upper 25% of the profile range
DIFF_DISTANCE = 0  # Minimum absolute price difference between current and previous close (0 = no filter)
MIN_VOLUME = 10  # Minimum total volume (BID + ASK) in the profile


# Configuration: Set to True to filter for NY hours only
FILTER_NY_HOURS = True  # Set to False to process all data

# Configuration: Set to True to filter for European hours only
FILTER_EUROPEAN_HOURS = True  # Set to False to process all data


plt.rcParams.update(
    {
        "font.size": 12,
        "axes.titlesize": 14,
        "axes.labelsize": 12,
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
        "legend.fontsize": 11,
    }
)
import pandas as pd

from rolling_profile import RollingMarketProfile

try:
    import mpld3
    from mpld3 import plugins
except ImportError:  # pragma: no cover - optional dependency for interactive HTML
    mpld3 = None
    plugins = None

if mpld3 is None or plugins is None:
    print(
        "mpld3 not available; falling back to static HTML export without interactivity."
    )


# Create output directory for plots
os.makedirs("charts/detections", exist_ok=True)

OUTPUT_HTML = None


def plot_detection(
    detection_num,
    detection_time,
    pattern_type,
    df_all,
    profile_now,
    profile_after_1x,
    profile_after_2x,
    highest_price,
    lowest_price,
    max_ask_price,
    max_bid_price,
    current_price,
    profile_window,
):
    """Create a 4-panel plot showing market profiles at detection, +1x window, +2x window, and price movement."""

    fig, (ax1, ax2, ax3, ax4) = plt.subplots(1, 4, figsize=(24, 6))
    tooltip_specs = []

    # Helper function to plot market profile
    def plot_market_profile(ax, profile, title, closing_price=None):
        if not profile:
            ax.text(0.5, 0.5, "No data", ha="center", va="center")
            ax.set_title(title)
            return

        prices = sorted(profile.keys())
        bid_volumes = [profile[p]["BID"] for p in prices]
        ask_volumes = [profile[p]["ASK"] for p in prices]

        # Use actual prices on y-axis instead of index positions
        if len(prices) > 1:
            bar_height = (
                min(prices[i + 1] - prices[i] for i in range(len(prices) - 1)) * 0.8
            )
        else:
            bar_height = 0.25 * 0.8

        # Plot bars using actual price values
        bid_bars = ax.barh(
            prices,
            [-v for v in bid_volumes],
            height=bar_height,
            color=(0.8, 0, 0, 0.8),
            label="BID",
            edgecolor="darkred",
            linewidth=0.5,
        )
        ask_bars = ax.barh(
            prices,
            ask_volumes,
            height=bar_height,
            color=(0, 0.7, 0, 0.8),
            label="ASK",
            edgecolor="darkgreen",
            linewidth=0.5,
        )

        ax.axvline(x=0, color="black", linewidth=1.5, linestyle="-", alpha=0.7)

        # Add blue dot at closing price (like in plot_dom.py)
        if closing_price is not None and closing_price in prices:
            ax.plot(
                0,
                closing_price,
                "o",
                color="blue",
                markersize=10,
                zorder=5,
                markeredgecolor="darkblue",
                markeredgewidth=2,
            )

        max_x = (
            max(
                max(bid_volumes) if bid_volumes else 1,
                max(ask_volumes) if ask_volumes else 1,
            )
            * 1.1
        )
        ax.set_xlim(-max_x, max_x)
        ax.set_xlabel("Volume (BID ← | → ASK)", fontsize=12)
        ax.set_ylabel("Price Level", fontsize=12)
        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.grid(True, alpha=0.3, axis="x")
        ax.legend(loc="upper right", fontsize=11)

        tooltip_css = (
            ".mpld3-tooltip {background: rgba(255,255,255,0.95);"
            "border: 1px solid #555;border-radius: 4px;padding: 8px 10px;"
            "font-size: 14px;color: #222;box-shadow: 0 2px 6px rgba(0,0,0,0.3);}"
            ".mpld3-tooltip table {border-collapse: collapse;margin-top:4px;}"
            ".mpld3-tooltip th {text-align:left;padding:2px 4px;border-bottom:1px solid #ccc;}"
            ".mpld3-tooltip td {padding:2px 4px;}"
            ".mpld3-tooltip td:last-child {text-align:right;}"
        )

        for side, volumes, bars in (
            ("BID", bid_volumes, bid_bars.patches),
            ("ASK", ask_volumes, ask_bars.patches),
        ):
            x_vals = []
            y_vals = []
            labels = []
            sizes = []
            for price, volume, rect in zip(prices, volumes, bars):
                if volume <= 0:
                    continue
                trades = profile.get(price, {}).get("Trades", {}).get(side, [])
                mid_x = rect.get_x() + rect.get_width() / 2
                x_vals.append(mid_x)
                y_vals.append(price)
                sizes.append(max(abs(volume), 1) * 120)

                if not trades:
                    labels.append(
                        f"<strong>{side} @ {price:.2f}</strong><br/>No trades captured"
                    )
                    continue

                rows = "".join(
                    "<tr><td style='padding:2px 4px;'>"
                    + trade.get("timestamp_str", "")
                    + "</td><td style='padding:2px 4px;text-align:right;'>"
                    + f"{trade.get('volume', 0):g}"
                    + "</td></tr>"
                    for trade in trades[:15]
                )
                extra = ""
                if len(trades) > 15:
                    extra = (
                        "<tr><td colspan='2' style='padding:2px 4px;'>"
                        + f"... (+{len(trades) - 15} more)"
                        + "</td></tr>"
                    )

                table = (
                    f"<strong>{side} @ {price:.2f}</strong>"
                    "<table style='border-collapse:collapse;margin-top:4px;'>"
                    '<thead><tr><th style="padding:2px 4px;border-bottom:1px solid #ccc;">Time</th><th style="padding:2px 4px;border-bottom:1px solid #ccc;text-align:right;">Vol</th></tr></thead>'
                    f"<tbody>{rows}{extra}</tbody></table>"
                )
                labels.append(table)

            if x_vals and labels:
                invisible_scatter = ax.scatter(
                    x_vals,
                    y_vals,
                    s=sizes,
                    marker="s",
                    alpha=0.01,
                )
                tooltip_specs.append((invisible_scatter, labels, tooltip_css))

    # Get closing prices at different time points
    closing_price_now = current_price

    time_after_1x = detection_time + timedelta(seconds=profile_window)
    price_data_after_1x = df_all[df_all["Timestamp"] <= time_after_1x]
    if len(price_data_after_1x) > 0:
        closing_price_after_1x = float(
            str(price_data_after_1x.iloc[-1]["Precio"]).replace(",", ".")
        )
    else:
        closing_price_after_1x = None

    time_after_2x = detection_time + timedelta(seconds=profile_window * 2)
    price_data_after_2x = df_all[df_all["Timestamp"] <= time_after_2x]
    if len(price_data_after_2x) > 0:
        closing_price_after_2x = float(
            str(price_data_after_2x.iloc[-1]["Precio"]).replace(",", ".")
        )
    else:
        closing_price_after_2x = None

    # Panel 1: Market profile at detection
    plot_market_profile(
        ax1,
        profile_now,
        f"At Detection\n{detection_time.strftime('%H:%M:%S')}",
        closing_price_now,
    )

    # Panel 2: Market profile after profile_window seconds
    plot_market_profile(
        ax2,
        profile_after_1x,
        f"After {profile_window}s\n{time_after_1x.strftime('%H:%M:%S')}",
        closing_price_after_1x,
    )

    # Panel 3: Market profile after 2x profile_window seconds
    plot_market_profile(
        ax3,
        profile_after_2x,
        f"After {profile_window*2}s\n{time_after_2x.strftime('%H:%M:%S')}",
        closing_price_after_2x,
    )

    # Panel 4: Price movement chart
    start_time = detection_time - timedelta(seconds=10)
    end_time = detection_time + timedelta(seconds=60)
    price_data = df_all[
        (df_all["Timestamp"] >= start_time) & (df_all["Timestamp"] <= end_time)
    ]

    if len(price_data) > 0:
        # Get price for each tick
        times_rel = [
            (t - detection_time).total_seconds() for t in price_data["Timestamp"]
        ]
        prices_plot = price_data["Precio"].values

        # Color by side
        bid_mask = price_data["Lado"].str.upper() == "BID"
        ask_mask = price_data["Lado"].str.upper() == "ASK"

        ax4.scatter(
            [t for i, t in enumerate(times_rel) if bid_mask.iloc[i]],
            [p for i, p in enumerate(prices_plot) if bid_mask.iloc[i]],
            c="red",
            s=10,
            alpha=0.6,
            label="BID",
        )
        ax4.scatter(
            [t for i, t in enumerate(times_rel) if ask_mask.iloc[i]],
            [p for i, p in enumerate(prices_plot) if ask_mask.iloc[i]],
            c="green",
            s=10,
            alpha=0.6,
            label="ASK",
        )

        ax4.set_xlabel("Time (seconds relative to detection)", fontsize=12)
        ax4.set_ylabel("Price", fontsize=12)
        ax4.set_title("Price Movement\n(-10s to +60s)", fontsize=14, fontweight="bold")
        ax4.grid(True, alpha=0.3)

        # Add price range info
        price_at_detect = (
            price_data[price_data["Timestamp"] <= detection_time]["Precio"].iloc[-1]
            if len(price_data[price_data["Timestamp"] <= detection_time]) > 0
            else None
        )
        price_after_1min = (
            price_data[price_data["Timestamp"] >= end_time]["Precio"].iloc[0]
            if len(price_data[price_data["Timestamp"] >= end_time]) > 0
            else price_data["Precio"].iloc[-1]
        )

        if price_at_detect is not None:
            price_change = price_after_1min - price_at_detect
            ax4.text(
                0.02,
                0.98,
                f"Start: {price_at_detect:.2f}\nEnd: {price_after_1min:.2f}\nChange: {price_change:+.2f}",
                transform=ax4.transAxes,
                fontsize=11,
                verticalalignment="top",
                bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
            )
    else:
        ax4.text(0.5, 0.5, "No price data available", ha="center", va="center")
        ax4.set_title("Price Movement", fontsize=14, fontweight="bold")

    # Reference lines at detection, +1x, +2x profile window
    marker_lines = [
        (
            0,
            {
                "color": "blue",
                "label": "Detection",
            },
        ),
        (
            profile_window,
            {
                "color": "orange",
                "label": f"+{profile_window}s",
            },
        ),
        (
            profile_window * 2,
            {
                "color": "purple",
                "label": f"+{profile_window*2}s",
            },
        ),
    ]

    for x_pos, style in marker_lines:
        ax4.axvline(
            x=x_pos,
            color=style["color"],
            linewidth=2,
            linestyle="--",
            alpha=0.8,
            label=style["label"],
            zorder=5,
        )

    handles, labels = ax4.get_legend_handles_labels()
    uniq_handles = []
    uniq_labels = []
    seen = set()
    for handle, label in zip(handles, labels):
        if label in seen:
            continue
        seen.add(label)
        uniq_handles.append(handle)
        uniq_labels.append(label)
    ax4.legend(uniq_handles, uniq_labels, loc="best", fontsize=11)

    # Synchronize y-axis scales across all 4 panels
    all_prices = []

    # Collect prices from all three market profiles
    if profile_now:
        all_prices.extend(list(profile_now.keys()))
    if profile_after_1x:
        all_prices.extend(list(profile_after_1x.keys()))
    if profile_after_2x:
        all_prices.extend(list(profile_after_2x.keys()))

    # Also include prices from price movement chart
    if len(price_data) > 0:
        all_prices.extend(price_data["Precio"].values)

    # Find global min and max
    if all_prices:
        global_min = min(all_prices)
        global_max = max(all_prices)

        # Add some padding (2% on each side)
        price_range = global_max - global_min
        padding = price_range * 0.02
        y_min = global_min - padding
        y_max = global_max + padding

        # Apply same limits to all axes
        ax1.set_ylim(y_min, y_max)
        ax2.set_ylim(y_min, y_max)
        ax3.set_ylim(y_min, y_max)
        ax4.set_ylim(y_min, y_max)

    # Main title
    fig.suptitle(
        f"Detection #{detection_num} - Pattern: {pattern_type}",
        fontsize=16,
        fontweight="bold",
        y=0.98,
    )

    if plugins is not None:
        for artist, labels, css in tooltip_specs:
            plugins.connect(
                fig,
                plugins.PointHTMLTooltip(
                    artist,
                    labels,
                    hoffset=15,
                    voffset=-10,
                    css=css,
                ),
            )

    fig.tight_layout()

    if mpld3 is not None:
        html = mpld3.fig_to_html(fig)
    else:
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", bbox_inches="tight")
        buffer.seek(0)
        img_b64 = base64.b64encode(buffer.read()).decode("ascii")
        html = (
            "<div class='static-fallback'>"
            "<p>Interactive export requires mpld3. Showing static image instead.</p>"
            f"<img src='data:image/png;base64,{img_b64}' "
            "alt='Market profile detection plot' style='max-width:100%;height:auto;'/>"
            "</div>"
        )

    plt.close(fig)

    return html


# Load data
print("Loading data...")

if not os.path.exists(csv_path):
    print(f"CSV file not found: {csv_path}")
    print("Aborting processing.")
    sys.exit(1)

# Detect CSV format by reading first line
with open(csv_path, "r") as f:
    first_line = f.readline().strip()

# Check if it's the DOM format (comma-separated with DOM_BID, DOM_ASK columns)
is_dom_format = "DOM_BID" in first_line and "DOM_ASK" in first_line

if is_dom_format:
    print("Detected DOM format (with JSON columns)")
    # The CSV has malformed quoting (entire row in quotes). Parse manually.
    with open(csv_path, "r") as f:
        # Read header
        header = f.readline().strip().split(",")

        # Parse each line manually
        rows = []
        for line in f:
            # Remove outer quotes if present
            line = line.strip()
            if line.startswith('"') and line.endswith('"'):
                line = line[1:-1]

            # Split by comma, but need to handle JSON dictionaries
            parts = []
            current = ""
            in_dict = 0

            for char in line:
                if char == "{":
                    in_dict += 1
                elif char == "}":
                    in_dict -= 1

                if char == "," and in_dict == 0:
                    parts.append(current)
                    current = ""
                else:
                    current += char

            # Add the last part
            if current:
                parts.append(current)

            # We only need first 4 columns: Timestamp, Price, Size, Side
            if len(parts) >= 4:
                rows.append(parts[:4])

    df = pd.DataFrame(rows, columns=header[:4])
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])

    # Rename columns to match expected format
    df = df.rename(columns={"Price": "Precio", "Size": "Volumen", "Side": "Lado"})

    # Convert numeric columns
    df["Precio"] = df["Precio"].astype(float)
    df["Volumen"] = df["Volumen"].astype(int)
else:
    print("Detected standard format (European CSV: semicolon separator, comma decimal)")
    # Standard European format: semicolon separator, comma decimal
    df = pd.read_csv(csv_path, sep=";", decimal=",")
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    # Columns already named: Timestamp, Precio, Volumen, Lado

print(f"Loaded {len(df)} rows")
print(f"Time range: {df['Timestamp'].min()} to {df['Timestamp'].max()}")

# Filter for NY trading hours (9:30 AM - 4:00 PM ET)
# Timestamps are in Madrid time (CEST: UTC+2, October)
# NY is EDT (UTC-4) in October
# Madrid is 6 hours ahead of NY
# 9:30 AM ET = 3:30 PM (15:30) Madrid time
# 4:00 PM ET = 10:00 PM (22:00) Madrid time


if FILTER_NY_HOURS or FILTER_EUROPEAN_HOURS:
    df["hour"] = df["Timestamp"].dt.hour
    df["minute"] = df["Timestamp"].dt.minute
    df["time_minutes"] = df["hour"] * 60 + df["minute"]

    # Define time ranges
    NY_OPEN_MADRID = 15 * 60 + 30  # 15:30 = 930 minutes
    NY_CLOSE_MADRID = 22 * 60  # 22:00 = 1320 minutes
    EUROPEAN_OPEN_MADRID = 9 * 60  # 09:00 = 480 minutes
    EUROPEAN_CLOSE_MADRID = 22 * 60  # 22:00 = 1320 minutes

    df_before = len(df)

    if FILTER_NY_HOURS and FILTER_EUROPEAN_HOURS:
        # Both enabled: Union of both time ranges (08:00-22:00, which covers both)
        df = df[
            (df["time_minutes"] >= EUROPEAN_OPEN_MADRID)
            & (df["time_minutes"] < EUROPEAN_CLOSE_MADRID)
        ]
        print(f"Filtered {df_before - len(df)} ticks outside European+NY trading hours")
        print(
            f"Combined trading hours (Madrid time): 08:00 - 22:00 (covers both EU and NY)"
        )
    elif FILTER_NY_HOURS:
        # NY only: 15:30-22:00
        df = df[
            (df["time_minutes"] >= NY_OPEN_MADRID)
            & (df["time_minutes"] < NY_CLOSE_MADRID)
        ]
        print(f"Filtered {df_before - len(df)} ticks outside NY trading hours")
        print(f"NY trading hours (Madrid time): 15:30 - 22:00 (CEST, 6 hours ahead)")
    else:
        # European only: 08:00-22:00
        df = df[
            (df["time_minutes"] >= EUROPEAN_OPEN_MADRID)
            & (df["time_minutes"] < EUROPEAN_CLOSE_MADRID)
        ]
        print(f"Filtered {df_before - len(df)} ticks outside European trading hours")
        print(f"European trading hours (Madrid time): 08:00 - 22:00 (CEST)")
else:
    print("Processing ALL data (no hours filter)")

print(f"Loaded {len(df)} ticks")
print(f"Period: {df['Timestamp'].min()} to {df['Timestamp'].max()}")
print("=" * 80)

# Prepare HTML report filename based on data date(s)
start_ts = df["Timestamp"].min()
end_ts = df["Timestamp"].max()

start_label = start_ts.strftime("%Y%m%d")
end_label = end_ts.strftime("%Y%m%d")

if start_label == end_label:
    date_slug = start_label
    title_suffix = start_ts.strftime("%Y-%m-%d")
else:
    date_slug = f"{start_label}_{end_label}"
    title_suffix = f"{start_ts.strftime('%Y-%m-%d')} – {end_ts.strftime('%Y-%m-%d')}"

OUTPUT_HTML = f"charts/detections/absorption_report_{date_slug}.html"

with open(OUTPUT_HTML, "w", encoding="utf-8") as report:
    report.write(
        "<!DOCTYPE html>\n"
        "<html lang='en'>\n"
        "<head>\n"
        "  <meta charset='utf-8'/>\n"
        f"  <title>Absorption Detections – {title_suffix}</title>\n"
        "  <style>\n"
        "    body {font-family: Arial, sans-serif; margin: 24px; background-color: #0b0b10; color: #f0f0f5;}\n"
        "    h1 {margin-bottom: 16px;}\n"
        "    h2 {margin-top: 32px; color: #ffda7b;}\n"
        "    .detection-block {margin-bottom: 48px; padding-bottom: 32px; border-bottom: 1px solid #303046;}\n"
        "    .detection-meta {margin-bottom: 12px; font-size: 14px; color: #bbbbcf;}\n"
        "    .detection-text {background:#161622; padding:16px; border-radius:8px; border:1px solid #303046; color:#e8e8ff;}\n"
        "    pre.detection-text {white-space: pre-wrap; font-size: 14px; line-height: 1.5;}\n"
        "    .detection-figure {margin-top: 16px; background:#ffffff; border-radius:8px; padding:12px; color:#000; box-shadow:0 2px 8px rgba(0,0,0,0.35);}\n"
        "    a {color: #7cc6ff;}\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        f"  <h1>Absorption Detections – {title_suffix}</h1>\n"
        "  <p>Generated by strat_absortion/main.py</p>\n"
    )

# Create rolling market profile with 20-second window
profile_window = 20
mp = RollingMarketProfile(window=timedelta(seconds=profile_window))

# Track detected patterns
detection_count = 0
last_detection_time = None
COOLDOWN_PERIOD = timedelta(seconds=60)  # 1 minute cooldown
WARMUP_PERIOD = timedelta(seconds=120)  # Discard first 2 minutes
start_time = df["Timestamp"].min()
warmup_end = start_time + WARMUP_PERIOD


def evaluate_profile_shape(profile, current_close=None, previous_close=None):
    """
    Evaluate the distribution shape of a market profile with STRICT criteria.

    Returns:
        str: 'd_shape', 'p_shape', or 'balanced'

    STRICT Criteria for d_shape (ALL must be met):
    1. Minimum MIN_PRICE_LEVELS active price levels
    2. Largest BID bar across all prices is located within the 2 LOWEST prices
    3. That BID bar is >= MIN_BID_ASK_SIZE and at least EXTREME_VOLUME_MULTIPLIER times the second-largest bar overall (BID or ASK)
    4. Current price must be in LOWER 25% of the profile range
    5. Price FALLING: current_close < previous_close (absorbing selling pressure)
    6. Absolute price difference >= DIFF_DISTANCE

    STRICT Criteria for p_shape (ALL must be met):
    1. Minimum MIN_PRICE_LEVELS active price levels
    2. Largest ASK bar across all prices is located within the 2 HIGHEST prices
    3. That ASK bar is >= MIN_BID_ASK_SIZE and at least EXTREME_VOLUME_MULTIPLIER times the second-largest bar overall (BID or ASK)
    4. Current price must be in UPPER 25% of the profile range
    5. Price RISING: current_close > previous_close (absorbing buying pressure)
    6. Absolute price difference >= DIFF_DISTANCE
    """
    if not profile or current_close is None or previous_close is None:
        return "balanced"

    # Check minimum price difference (absolute value)
    price_diff = abs(current_close - previous_close)
    if price_diff < DIFF_DISTANCE:
        return "balanced"

    # Filter out price levels with no volume (empty levels)
    active_prices = []
    for price in sorted(profile.keys()):
        bid_vol = profile[price].get("BID", 0)
        ask_vol = profile[price].get("ASK", 0)
        if bid_vol > 0 or ask_vol > 0:  # Only consider levels with volume
            active_prices.append(price)

    # Criterion 1: Minimum number of price levels
    if len(active_prices) < MIN_PRICE_LEVELS:
        return "balanced"

    # Calculate total volumes
    total_bid = sum(profile[p].get("BID", 0) for p in active_prices)
    total_ask = sum(profile[p].get("ASK", 0) for p in active_prices)
    total_volume = total_bid + total_ask

    # Check minimum volume requirement
    if total_volume < MIN_VOLUME:
        return "balanced"

    # Calculate price range
    min_price = min(active_prices)
    max_price = max(active_prices)
    price_range = max_price - min_price

    if price_range == 0:
        return "balanced"

    # Calculate where current price is in the range (0 = bottom, 1 = top)
    price_position = (current_close - min_price) / price_range

    # Get the 2 lowest and 2 highest prices for extreme level concentration check
    lowest_2_prices = active_prices[:2] if len(active_prices) >= 2 else active_prices
    highest_2_prices = active_prices[-2:] if len(active_prices) >= 2 else active_prices

    # Prepare global volume rankings for BID/ASK
    bid_volumes_sorted = sorted(
        (profile[p].get("BID", 0) for p in active_prices), reverse=True
    )
    ask_volumes_sorted = sorted(
        (profile[p].get("ASK", 0) for p in active_prices), reverse=True
    )

    max_bid_value = bid_volumes_sorted[0] if bid_volumes_sorted else 0
    max_ask_value = ask_volumes_sorted[0] if ask_volumes_sorted else 0

    max_bid_price = (
        max(active_prices, key=lambda p: profile[p].get("BID", 0))
        if active_prices
        else None
    )
    max_ask_price = (
        max(active_prices, key=lambda p: profile[p].get("ASK", 0))
        if active_prices
        else None
    )

    # Combine ALL volumes (both BID and ASK) to find second-largest overall
    all_volumes = []
    for p in active_prices:
        bid_vol = profile[p].get("BID", 0)
        ask_vol = profile[p].get("ASK", 0)
        if bid_vol > 0:
            all_volumes.append(bid_vol)
        if ask_vol > 0:
            all_volumes.append(ask_vol)

    all_volumes_sorted = sorted(all_volumes, reverse=True)
    second_largest_overall = all_volumes_sorted[1] if len(all_volumes_sorted) > 1 else 0

    # Compare extreme bar against second-largest across BOTH BID and ASK
    bid_ratio = (
        max_bid_value / second_largest_overall
        if second_largest_overall > 0
        else float("inf")
    )
    ask_ratio = (
        max_ask_value / second_largest_overall
        if second_largest_overall > 0
        else float("inf")
    )

    # Check for d_shape - ALL criteria must be met
    if (
        max_bid_value >= MIN_BID_ASK_SIZE
        and max_bid_price in lowest_2_prices
        and bid_ratio >= EXTREME_VOLUME_MULTIPLIER
        and price_position <= PRICE_POSITION_THRESHOLD
        and current_close < previous_close
    ):
        return "d_shape"

    # Check for p_shape - ALL criteria must be met
    if (
        max_ask_value >= MIN_BID_ASK_SIZE
        and max_ask_price in highest_2_prices
        and ask_ratio >= EXTREME_VOLUME_MULTIPLIER
        and price_position >= (1 - PRICE_POSITION_THRESHOLD)
        and current_close > previous_close
    ):
        return "p_shape"

    return "balanced"


print(f"\nWarmup period: {start_time} to {warmup_end}")
print(f"Detection starts after: {warmup_end}")
print(f"Detection criteria (modified from plot_deep.py):")
print(
    f"  - d_shape: BID absorption (price falling, BID concentration in 2 LOWEST prices)"
)
print(
    f"  - p_shape: ASK absorption (price rising, ASK concentration in 2 HIGHEST prices)"
)
print(f"  - MIN_PRICE_LEVELS: {MIN_PRICE_LEVELS}")
print(f"  - MIN_BID_ASK_SIZE: {MIN_BID_ASK_SIZE}")
print(f"  - PRICE_POSITION_THRESHOLD: {PRICE_POSITION_THRESHOLD*100:.0f}%")
print(
    f"  - EXTREME_VOLUME_MULTIPLIER: {EXTREME_VOLUME_MULTIPLIER}x (extreme bar vs second largest overall BID/ASK)"
)
print("=" * 80)

# Process each tick - track previous close for shape detection
previous_close: Optional[float] = None
total_ticks = len(df)
progress_interval = max(total_ticks // 100, 1)

for idx, row in df.iterrows():
    mp.update(row["Timestamp"], row["Precio"], row["Volumen"], row["Lado"])

    if idx % progress_interval == 0:
        percent = (idx / total_ticks) * 100
        print(f"Progress: {percent:5.1f}% ({idx:,}/{total_ticks:,})")

    current_time = row["Timestamp"]
    current_price = float(str(row["Precio"]).replace(",", "."))

    # Skip warmup period (first 2 minutes)
    if (current_time - start_time) < WARMUP_PERIOD:
        previous_close = current_price  # Track for next iteration
        continue

    # Check if we're in cooldown period
    if last_detection_time is not None:
        time_since_last = current_time - last_detection_time
        if time_since_last < COOLDOWN_PERIOD:
            previous_close = current_price  # Track for next iteration
            continue  # Skip detection, still in cooldown

    # Get current profile
    profile = mp.profile(include_trades=True)

    if not profile:
        previous_close = current_price  # Track for next iteration
        continue

    # Evaluate profile shape using the sophisticated algorithm
    profile_shape = evaluate_profile_shape(profile, current_price, previous_close)

    # Update previous close for next iteration
    previous_close = current_price

    # Only detect if shape is d_shape or p_shape (not balanced)
    if profile_shape not in ["d_shape", "p_shape"]:
        continue

    # Get all prices for display
    prices = sorted(profile.keys())
    highest_price = prices[-1] if prices else current_price
    lowest_price = prices[0] if prices else current_price

    # Calculate volume statistics for display
    ask_volumes = {p: profile[p]["ASK"] for p in prices if profile[p]["ASK"] > 0}
    bid_volumes = {p: profile[p]["BID"] for p in prices if profile[p]["BID"] > 0}

    max_ask_price = max(ask_volumes, key=ask_volumes.get) if ask_volumes else None
    max_bid_price = max(bid_volumes, key=bid_volumes.get) if bid_volumes else None

    # Calculate shape-specific statistics (2 lowest and 2 highest prices)
    lowest_2_prices = prices[:2] if len(prices) >= 2 else prices
    highest_2_prices = prices[-2:] if len(prices) >= 2 else prices

    lowest_2_bid_volume = sum(profile[p].get("BID", 0) for p in lowest_2_prices)
    highest_2_ask_volume = sum(profile[p].get("ASK", 0) for p in highest_2_prices)
    total_bid = sum(profile[p].get("BID", 0) for p in prices)
    total_ask = sum(profile[p].get("ASK", 0) for p in prices)

    max_lowest_2_bid = (
        max([profile[p].get("BID", 0) for p in lowest_2_prices])
        if lowest_2_prices
        else 0
    )
    max_highest_2_ask = (
        max([profile[p].get("ASK", 0) for p in highest_2_prices])
        if highest_2_prices
        else 0
    )

    # Pattern detected!
    condition_met = True
    condition_type = profile_shape

    # Log the market profile if condition is met
    if condition_met:
        detection_count += 1

        # Calculate time since last detection
        time_since_str = ""
        time_since_display = None
        if last_detection_time is not None:
            time_since = (current_time - last_detection_time).total_seconds()
            time_since_str = f" (Time since last: {time_since:.1f}s)"
            time_since_display = f"{time_since:.1f}s"

        # Update last detection time for cooldown
        last_detection_time = current_time

        print(f"\n{'=' * 80}")
        print(f"DETECTION #{detection_count} at {row['Timestamp']}{time_since_str}")
        print(f"Pattern: {condition_type}")
        print(
            f"Current Price: {current_price:.2f} | Profile Range: {lowest_price:.2f} - {highest_price:.2f}"
        )
        print(f"Cooldown active until: {current_time + COOLDOWN_PERIOD}")
        print(f"{'=' * 80}")

        # Compute market profile after profile_window (20s) and 2x profile_window (40s)
        time_after_1x = current_time + timedelta(seconds=profile_window)
        mp_after_1x = RollingMarketProfile(window=timedelta(seconds=profile_window))

        ticks_until_after_1x = df[df["Timestamp"] <= time_after_1x]
        for _, r in ticks_until_after_1x.iterrows():
            mp_after_1x.update(r["Timestamp"], r["Precio"], r["Volumen"], r["Lado"])

        profile_after_1x = mp_after_1x.profile(include_trades=True)

        time_after_2x = current_time + timedelta(seconds=profile_window * 2)
        mp_after_2x = RollingMarketProfile(window=timedelta(seconds=profile_window))

        ticks_until_after_2x = df[df["Timestamp"] <= time_after_2x]
        for _, r in ticks_until_after_2x.iterrows():
            mp_after_2x.update(r["Timestamp"], r["Precio"], r["Volumen"], r["Lado"])

        profile_after_2x = mp_after_2x.profile(include_trades=True)

        # Create plot
        print(f"Creating visualization...")
        fig_html = plot_detection(
            detection_count,
            current_time,
            condition_type,
            df,
            profile,
            profile_after_1x,
            profile_after_2x,
            highest_price,
            lowest_price,
            max_ask_price,
            max_bid_price,
            current_price,
            profile_window,
        )
        print(f"Report section prepared")

        # Display market profile (high to low)
        print(f"\nMarket Profile ({profile_window}-second rolling window):")
        print(f"{'-' * 80}")

        for price in reversed(prices):
            data = profile[price]
            bid_vol = data["BID"]
            ask_vol = data["ASK"]
            total_vol = data["Total"]

            # Mark special prices based on detected shape
            marker = ""
            if condition_type == "d_shape" and price in lowest_2_prices:
                if profile[price]["BID"] == max_lowest_2_bid:
                    marker = " <- MAX BID IN 2 LOWEST (d-shape)"
            elif condition_type == "p_shape" and price in highest_2_prices:
                if profile[price]["ASK"] == max_highest_2_ask:
                    marker = " <- MAX ASK IN 2 HIGHEST (p-shape)"

            print(
                f"Price {price:>10.2f} | BID: {bid_vol:>6.0f} | "
                f"ASK: {ask_vol:>6.0f} | Total: {total_vol:>6.0f}{marker}"
            )

        print(f"{'-' * 80}")
        summary_lines = [
            f"Total price levels: {len(prices)}",
            f"Price range: {lowest_price:.2f} - {highest_price:.2f}",
            f"Current price: {current_price:.2f} (prev: {previous_close:.2f})",
        ]

        for line in summary_lines:
            print(line)

        # Show shape-specific statistics
        shape_lines = []
        if condition_type == "d_shape":
            bid_concentration = (
                (lowest_2_bid_volume / total_bid * 100) if total_bid > 0 else 0
            )
            # Calculate diagonal opposition for display (BID@low vs ASK@low)
            lowest_2_ask_volume_display = sum(
                profile[p].get("ASK", 0) for p in lowest_2_prices
            )
            diagonal_ratio = (
                lowest_2_bid_volume / lowest_2_ask_volume_display
                if lowest_2_ask_volume_display > 0
                else float("inf")
            )

            shape_lines = [
                "",
                "d-Shape Statistics:",
                f"  2 LOWEST prices BID volume: {lowest_2_bid_volume:.0f} ({bid_concentration:.1f}% of total BID)",
                (
                    f"  Lowest 2 prices: {lowest_2_prices[0]:.2f}, {lowest_2_prices[1]:.2f}"
                    if len(lowest_2_prices) >= 2
                    else f"  Lowest price: {lowest_2_prices[0]:.2f}"
                ),
                f"  Max BID in lowest 2: {max_lowest_2_bid:.0f}",
                f"  Total BID: {total_bid:.0f}",
                f"  Diagonal opposition: BID@low({lowest_2_bid_volume:.0f}) / ASK@low({lowest_2_ask_volume_display:.0f}) = {diagonal_ratio:.2f}x",
                f"  Price position: LOWER {PRICE_POSITION_THRESHOLD*100:.0f}% (falling)",
            ]
        elif condition_type == "p_shape":
            ask_concentration = (
                (highest_2_ask_volume / total_ask * 100) if total_ask > 0 else 0
            )
            # Calculate diagonal opposition for display (ASK@high vs BID@high)
            highest_2_bid_volume_display = sum(
                profile[p].get("BID", 0) for p in highest_2_prices
            )
            diagonal_ratio = (
                highest_2_ask_volume / highest_2_bid_volume_display
                if highest_2_bid_volume_display > 0
                else float("inf")
            )

            shape_lines = [
                "",
                "p-Shape Statistics:",
                f"  2 HIGHEST prices ASK volume: {highest_2_ask_volume:.0f} ({ask_concentration:.1f}% of total ASK)",
                (
                    f"  Highest 2 prices: {highest_2_prices[0]:.2f}, {highest_2_prices[1]:.2f}"
                    if len(highest_2_prices) >= 2
                    else f"  Highest price: {highest_2_prices[0]:.2f}"
                ),
                f"  Max ASK in highest 2: {max_highest_2_ask:.0f}",
                f"  Total ASK: {total_ask:.0f}",
                f"  Diagonal opposition: ASK@high({highest_2_ask_volume:.0f}) / BID@high({highest_2_bid_volume_display:.0f}) = {diagonal_ratio:.2f}x",
                f"  Price position: UPPER {PRICE_POSITION_THRESHOLD*100:.0f}% (rising)",
            ]
        if shape_lines:
            for line in shape_lines:
                print(line)
            summary_lines.extend(shape_lines)

        print(f"{'=' * 80}\n")

        summary_lines.append("=" * 80)

        summary_text = "\n".join(summary_lines)
        summary_html = f"<pre class='detection-text'>{summary_text}</pre>"

        meta_parts = [f"Timestamp: {current_time}"]
        if time_since_display is not None:
            meta_parts.append(f"Time since last: {time_since_display}")
        section_html = (
            "<section class='detection-block'>"
            f"<h2>Detection #{detection_count} — {condition_type.upper()} ({current_time.strftime('%H:%M:%S')})</h2>"
            f"<div class='detection-meta'>{' | '.join(meta_parts)}</div>"
            f"{summary_html}"
            f"<div class='detection-figure'>{fig_html}</div>"
            "</section>\n"
        )

        with open(OUTPUT_HTML, "a", encoding="utf-8") as report:
            report.write(section_html)

        print(f"Report updated: {OUTPUT_HTML}")

with open(OUTPUT_HTML, "a", encoding="utf-8") as report:
    if detection_count == 0:
        report.write("<p>No detections matched the criteria.</p>\n")
    report.write("</body></html>\n")

print(f"\n{'=' * 80}")
print(f"Processing complete!")
print(f"Total ticks processed: {len(df)}")
print(f"Total detections: {detection_count}")
print(f"HTML report: {OUTPUT_HTML}")
print(f"{'=' * 80}")
