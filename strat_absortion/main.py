import pandas as pd
import matplotlib

matplotlib.use("Agg")  # Use non-interactive backend
import matplotlib.pyplot as plt
from datetime import timedelta
from rolling_profile import RollingMarketProfile
import os

csv_path = (
    "../data/time_and_sales_nq.csv"  # Can use time_and_sales_nq.csv or ts_and_dom_*.csv
)

# Profile shape detection configuration (modified from plot_deep.py)
DENSITY_SHAPE = 0.3  # 50% of volume must be concentrated in 2 extreme prices
DIAGONAL_OPPOSITION_RATIO = (
    3.0  # Strong side must be 3x opposite at SAME levels (e.g., ASK@high vs BID@high)
)

MIN_PRICE_LEVELS = 6  # Minimum number of active price levels
MIN_BID_ASK_SIZE = 15  # Minimum absolute size of largest BID/ASK bar
PRICE_POSITION_THRESHOLD = 0.3  # Price must be in lower/upper 25% of the profile range
DIFF_DISTANCE = 0  # Minimum absolute price difference between current and previous close (0 = no filter)
MIN_VOLUME = 10  # Minimum total volume (BID + ASK) in the profile

# Configuration: Set to True to filter for NY hours only
FILTER_NY_HOURS = True  # Set to False to process all data

# Configuration: Set to True to filter for European hours only
FILTER_EUROPEAN_HOURS = True  # Set to False to process all data


# Create output directory for plots
os.makedirs("charts/detections", exist_ok=True)


def plot_detection(
    detection_num,
    detection_time,
    pattern_type,
    df_all,
    profile_now,
    profile_after,
    highest_price,
    lowest_price,
    max_ask_price,
    max_bid_price,
    current_price,
):
    """Create a 3-panel plot for a detection."""

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(18, 8))

    # Helper function to plot market profile
    def plot_market_profile(ax, profile, title, closing_price=None):
        if not profile:
            ax.text(0.5, 0.5, "No data", ha="center", va="center")
            ax.set_title(title)
            return

        prices = sorted(profile.keys())
        bid_volumes = [profile[p]["BID"] for p in prices]
        ask_volumes = [profile[p]["ASK"] for p in prices]
        y_positions = range(len(prices))

        # Plot bars
        ax.barh(
            y_positions,
            [-v for v in bid_volumes],
            height=0.8,
            color=(0.8, 0, 0, 0.8),
            label="BID",
            edgecolor="darkred",
            linewidth=0.5,
        )
        ax.barh(
            y_positions,
            ask_volumes,
            height=0.8,
            color=(0, 0.7, 0, 0.8),
            label="ASK",
            edgecolor="darkgreen",
            linewidth=0.5,
        )

        ax.set_yticks(y_positions)
        ax.set_yticklabels([f"{p:.2f}" for p in prices], fontsize=7)
        ax.axvline(x=0, color="black", linewidth=1.5, linestyle="-", alpha=0.7)

        # Add blue dot at closing price (like in plot_dom.py)
        if closing_price is not None and closing_price in prices:
            price_idx = prices.index(closing_price)
            ax.plot(
                0,
                price_idx,
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
        ax.set_xlabel("Volume (BID ← | → ASK)", fontsize=9)
        ax.set_ylabel("Price Level", fontsize=9)
        ax.set_title(title, fontsize=10, fontweight="bold")
        ax.grid(True, alpha=0.3, axis="x")
        ax.legend(loc="upper right", fontsize=8)

    # Get closing price at detection time
    closing_price_now = current_price

    # Get closing price after 1 minute
    time_after = detection_time + timedelta(seconds=60)
    price_data_after = df_all[df_all["Timestamp"] <= time_after]
    if len(price_data_after) > 0:
        closing_price_after = float(
            str(price_data_after.iloc[-1]["Precio"]).replace(",", ".")
        )
    else:
        closing_price_after = None

    # Panel 1: Market profile at detection
    plot_market_profile(
        ax1,
        profile_now,
        f"At Detection\n{detection_time.strftime('%H:%M:%S')}",
        closing_price_now,
    )

    # Panel 2: Market profile after 1 minute
    plot_market_profile(
        ax2,
        profile_after,
        f"After 1 Minute\n{(detection_time + timedelta(seconds=60)).strftime('%H:%M:%S')}",
        closing_price_after,
    )

    # Panel 3: Price movement
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

        ax3.scatter(
            [t for i, t in enumerate(times_rel) if bid_mask.iloc[i]],
            [p for i, p in enumerate(prices_plot) if bid_mask.iloc[i]],
            c="red",
            s=10,
            alpha=0.6,
            label="BID",
        )
        ax3.scatter(
            [t for i, t in enumerate(times_rel) if ask_mask.iloc[i]],
            [p for i, p in enumerate(prices_plot) if ask_mask.iloc[i]],
            c="green",
            s=10,
            alpha=0.6,
            label="ASK",
        )

        # Mark detection time
        ax3.axvline(
            x=0, color="blue", linewidth=2, linestyle="--", alpha=0.7, label="Detection"
        )

        # Mark 1 minute after
        ax3.axvline(
            x=60, color="orange", linewidth=2, linestyle="--", alpha=0.7, label="+1 min"
        )

        ax3.set_xlabel("Time (seconds relative to detection)", fontsize=9)
        ax3.set_ylabel("Price", fontsize=9)
        ax3.set_title("Price Movement\n(-10s to +60s)", fontsize=10, fontweight="bold")
        ax3.grid(True, alpha=0.3)
        ax3.legend(loc="best", fontsize=8)

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
            ax3.text(
                0.02,
                0.98,
                f"Start: {price_at_detect:.2f}\nEnd: {price_after_1min:.2f}\nChange: {price_change:+.2f}",
                transform=ax3.transAxes,
                fontsize=8,
                verticalalignment="top",
                bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
            )
    else:
        ax3.text(0.5, 0.5, "No price data available", ha="center", va="center")
        ax3.set_title("Price Movement", fontsize=10, fontweight="bold")

    # Main title
    fig.suptitle(
        f"Detection #{detection_num} - Pattern: {pattern_type}",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )

    plt.tight_layout()

    # Save plot
    filename = f"charts/detections/detection_{detection_num:03d}_{detection_time.strftime('%H%M%S')}.png"
    plt.savefig(filename, dpi=100, bbox_inches="tight")
    plt.close()

    return filename


# Load data
print("Loading data...")

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
    EUROPEAN_OPEN_MADRID = 8 * 60  # 08:00 = 480 minutes
    EUROPEAN_CLOSE_MADRID = 22 * 60  # 22:00 = 1320 minutes

    df_before = len(df)

    if FILTER_NY_HOURS and FILTER_EUROPEAN_HOURS:
        # Both enabled: Union of both time ranges (08:00-22:00, which covers both)
        df = df[
            (df["time_minutes"] >= EUROPEAN_OPEN_MADRID) & (df["time_minutes"] < EUROPEAN_CLOSE_MADRID)
        ]
        print(f"Filtered {df_before - len(df)} ticks outside European+NY trading hours")
        print(f"Combined trading hours (Madrid time): 08:00 - 22:00 (covers both EU and NY)")
    elif FILTER_NY_HOURS:
        # NY only: 15:30-22:00
        df = df[
            (df["time_minutes"] >= NY_OPEN_MADRID) & (df["time_minutes"] < NY_CLOSE_MADRID)
        ]
        print(f"Filtered {df_before - len(df)} ticks outside NY trading hours")
        print(f"NY trading hours (Madrid time): 15:30 - 22:00 (CEST, 6 hours ahead)")
    else:
        # European only: 08:00-22:00
        df = df[
            (df["time_minutes"] >= EUROPEAN_OPEN_MADRID) & (df["time_minutes"] < EUROPEAN_CLOSE_MADRID)
        ]
        print(f"Filtered {df_before - len(df)} ticks outside European trading hours")
        print(f"European trading hours (Madrid time): 08:00 - 22:00 (CEST)")
else:
    print("Processing ALL data (no hours filter)")

print(f"Loaded {len(df)} ticks")
print(f"Period: {df['Timestamp'].min()} to {df['Timestamp'].max()}")
print("=" * 80)

# Create rolling market profile with 20-second window
mp = RollingMarketProfile(window=timedelta(seconds=20))

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
    2. At least one BID bar >= MIN_BID_ASK_SIZE in 2 LOWEST prices
    3. >= DENSITY_SHAPE (50%) of total BID volume concentrated in 2 LOWEST prices
    4. BID volume in 2 LOWEST must be >= 3x ASK volume in SAME 2 LOWEST (diagonal opposition)
    5. Current price must be in LOWER 25% of the profile range
    6. Price FALLING: current_close < previous_close (absorbing selling pressure)
    7. Absolute price difference >= DIFF_DISTANCE

    STRICT Criteria for p_shape (ALL must be met):
    1. Minimum MIN_PRICE_LEVELS active price levels
    2. At least one ASK bar >= MIN_BID_ASK_SIZE in 2 HIGHEST prices
    3. >= DENSITY_SHAPE (50%) of total ASK volume concentrated in 2 HIGHEST prices
    4. ASK volume in 2 HIGHEST must be >= 3x BID volume in SAME 2 HIGHEST (diagonal opposition)
    5. Current price must be in UPPER 25% of the profile range
    6. Price RISING: current_close > previous_close (absorbing buying pressure)
    7. Absolute price difference >= DIFF_DISTANCE
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

    # Calculate BID and ASK volumes in 2 lowest prices
    lowest_2_bid = sum(profile[p].get("BID", 0) for p in lowest_2_prices)
    lowest_2_ask = sum(profile[p].get("ASK", 0) for p in lowest_2_prices)

    # Calculate ASK and BID volumes in 2 highest prices
    highest_2_ask = sum(profile[p].get("ASK", 0) for p in highest_2_prices)
    highest_2_bid = sum(profile[p].get("BID", 0) for p in highest_2_prices)

    # Find max BID in lowest 2 prices and max ASK in highest 2 prices
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

    # Check for d_shape - ALL criteria must be met
    if total_bid > 0:
        bid_concentration = lowest_2_bid / total_bid
        # Diagonal opposition: BID@low must be >= 3x ASK@low (same price levels)
        diagonal_opposition_ratio = (
            lowest_2_bid / lowest_2_ask if lowest_2_ask > 0 else float("inf")
        )

        is_d_shape = (
            max_lowest_2_bid >= MIN_BID_ASK_SIZE  # Large BID bar in 2 lowest prices
            and bid_concentration
            >= DENSITY_SHAPE  # 50% BID concentration in 2 lowest prices
            and diagonal_opposition_ratio
            >= DIAGONAL_OPPOSITION_RATIO  # BID@low >= 3x ASK@low (same levels)
            and price_position
            <= PRICE_POSITION_THRESHOLD  # Price in lower 25% of range
            and current_close
            < previous_close  # Price FALLING (absorbing selling pressure)
        )

        if is_d_shape:
            return "d_shape"

    # Check for p_shape - ALL criteria must be met
    if total_ask > 0:
        ask_concentration = highest_2_ask / total_ask
        # Diagonal opposition: ASK@high must be >= 3x BID@high (same price levels)
        diagonal_opposition_ratio = (
            highest_2_ask / highest_2_bid if highest_2_bid > 0 else float("inf")
        )

        is_p_shape = (
            max_highest_2_ask >= MIN_BID_ASK_SIZE  # Large ASK bar in 2 highest prices
            and ask_concentration
            >= DENSITY_SHAPE  # 50% ASK concentration in 2 highest prices
            and diagonal_opposition_ratio
            >= DIAGONAL_OPPOSITION_RATIO  # ASK@high >= 3x BID@high (same levels)
            and price_position
            >= (1 - PRICE_POSITION_THRESHOLD)  # Price in upper 25% of range
            and current_close
            > previous_close  # Price RISING (absorbing buying pressure)
        )

        if is_p_shape:
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
print(
    f"  - DENSITY_SHAPE: {DENSITY_SHAPE*100:.0f}% volume concentration required in 2 extreme prices"
)
print(f"  - MIN_PRICE_LEVELS: {MIN_PRICE_LEVELS}")
print(f"  - MIN_BID_ASK_SIZE: {MIN_BID_ASK_SIZE}")
print(f"  - PRICE_POSITION_THRESHOLD: {PRICE_POSITION_THRESHOLD*100:.0f}%")
print(
    f"  - DIAGONAL_OPPOSITION_RATIO: {DIAGONAL_OPPOSITION_RATIO:.1f}x (strong side must be 3x opposite)"
)
print("=" * 80)

# Process each tick - track previous close for shape detection
previous_close = None

for idx, row in df.iterrows():
    mp.update(row["Timestamp"], row["Precio"], row["Volumen"], row["Lado"])

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
    profile = mp.profile()

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
        if last_detection_time is not None:
            time_since = (current_time - last_detection_time).total_seconds()
            time_since_str = f" (Time since last: {time_since:.1f}s)"

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

        # Compute market profile 1 minute after detection
        time_after = current_time + timedelta(seconds=60)
        mp_after = RollingMarketProfile(window=timedelta(seconds=20))

        ticks_until_after = df[df["Timestamp"] <= time_after]
        for _, r in ticks_until_after.iterrows():
            mp_after.update(r["Timestamp"], r["Precio"], r["Volumen"], r["Lado"])

        profile_after = mp_after.profile()

        # Create plot
        print(f"Creating visualization...")
        filename = plot_detection(
            detection_count,
            current_time,
            condition_type,
            df,
            profile,
            profile_after,
            highest_price,
            lowest_price,
            max_ask_price,
            max_bid_price,
            current_price,
        )
        print(f"Plot saved: {filename}")

        # Display market profile (high to low)
        print(f"\nMarket Profile (60-second rolling window):")
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
        print(f"Total price levels: {len(prices)}")
        print(f"Price range: {lowest_price:.2f} - {highest_price:.2f}")
        print(f"Current price: {current_price:.2f} (prev: {previous_close:.2f})")

        # Show shape-specific statistics
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

            print(f"\nd-Shape Statistics:")
            print(
                f"  2 LOWEST prices BID volume: {lowest_2_bid_volume:.0f} ({bid_concentration:.1f}% of total BID)"
            )
            print(
                f"  Lowest 2 prices: {lowest_2_prices[0]:.2f}, {lowest_2_prices[1]:.2f}"
                if len(lowest_2_prices) >= 2
                else f"  Lowest price: {lowest_2_prices[0]:.2f}"
            )
            print(f"  Max BID in lowest 2: {max_lowest_2_bid:.0f}")
            print(f"  Total BID: {total_bid:.0f}")
            print(
                f"  Diagonal opposition: BID@low({lowest_2_bid_volume:.0f}) / ASK@low({lowest_2_ask_volume_display:.0f}) = {diagonal_ratio:.2f}x"
            )
            print(
                f"  Price position: LOWER {PRICE_POSITION_THRESHOLD*100:.0f}% (falling)"
            )
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

            print(f"\np-Shape Statistics:")
            print(
                f"  2 HIGHEST prices ASK volume: {highest_2_ask_volume:.0f} ({ask_concentration:.1f}% of total ASK)"
            )
            print(
                f"  Highest 2 prices: {highest_2_prices[0]:.2f}, {highest_2_prices[1]:.2f}"
                if len(highest_2_prices) >= 2
                else f"  Highest price: {highest_2_prices[0]:.2f}"
            )
            print(f"  Max ASK in highest 2: {max_highest_2_ask:.0f}")
            print(f"  Total ASK: {total_ask:.0f}")
            print(
                f"  Diagonal opposition: ASK@high({highest_2_ask_volume:.0f}) / BID@high({highest_2_bid_volume_display:.0f}) = {diagonal_ratio:.2f}x"
            )
            print(
                f"  Price position: UPPER {PRICE_POSITION_THRESHOLD*100:.0f}% (rising)"
            )

        print(f"{'=' * 80}\n")

print(f"\n{'=' * 80}")
print(f"Processing complete!")
print(f"Total ticks processed: {len(df)}")
print(f"Total detections: {detection_count}")
print(f"{'=' * 80}")
