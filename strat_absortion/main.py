import pandas as pd
import matplotlib

matplotlib.use("Agg")  # Use non-interactive backend
import matplotlib.pyplot as plt
from datetime import timedelta
from rolling_profile import RollingMarketProfile
import os

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
):
    """Create a 3-panel plot for a detection."""

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(18, 8))

    # Helper function to plot market profile
    def plot_market_profile(ax, profile, title):
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

    # Panel 1: Market profile at detection
    plot_market_profile(
        ax1, profile_now, f"At Detection\n{detection_time.strftime('%H:%M:%S')}"
    )

    # Panel 2: Market profile after 1 minute
    plot_market_profile(
        ax2,
        profile_after,
        f"After 1 Minute\n{(detection_time + timedelta(seconds=60)).strftime('%H:%M:%S')}",
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
csv_path = "data/time_and_sales_nq.csv"
print("Loading data...")
df = pd.read_csv(csv_path, sep=";", decimal=",")
df["Timestamp"] = pd.to_datetime(df["Timestamp"])

# Filter for NY trading hours (9:30 AM - 4:00 PM ET)
# Timestamps are in Madrid time (CEST: UTC+2, October)
# NY is EDT (UTC-4) in October
# Madrid is 6 hours ahead of NY
# 9:30 AM ET = 3:30 PM (15:30) Madrid time
# 4:00 PM ET = 10:00 PM (22:00) Madrid time
df["hour"] = df["Timestamp"].dt.hour
df["minute"] = df["Timestamp"].dt.minute
df["time_minutes"] = df["hour"] * 60 + df["minute"]

# NY trading hours in Madrid time: 15:30 (930 minutes) to 22:00 (1320 minutes)
NY_OPEN_MADRID = 15 * 60 + 30  # 15:30 = 930 minutes
NY_CLOSE_MADRID = 22 * 60  # 22:00 = 1320 minutes

df = df[(df["time_minutes"] >= NY_OPEN_MADRID) & (df["time_minutes"] < NY_CLOSE_MADRID)]

print(f"Loaded {len(df)} ticks")
print(f"Period: {df['Timestamp'].min()} to {df['Timestamp'].max()}")
print(f"Filtered for NY trading hours (9:30 AM - 4:00 PM ET)")
print(f"  Madrid time equivalent: 15:30 - 22:00 (CEST, 6 hours ahead)")
print("=" * 80)

# Create rolling market profile with 60-second window
mp = RollingMarketProfile(window=timedelta(seconds=60))

# Track detected patterns
detection_count = 0
last_detection_time = None
COOLDOWN_PERIOD = timedelta(seconds=60)  # 1 minute cooldown
WARMUP_PERIOD = timedelta(seconds=120)  # Discard first 2 minutes
start_time = df["Timestamp"].min()
warmup_end = start_time + WARMUP_PERIOD

print(f"\nWarmup period: {start_time} to {warmup_end}")
print(f"Detection starts after: {warmup_end}")
print(f"Detection criteria:")
print(f"  - ASK_AT_HIGH: Heavy ASK volume at highest price + current price at high")
print(f"  - BID_AT_LOW: Heavy BID volume at lowest price + current price at low")
print(f"  - Price tolerance: 0.25 (1 tick)")
print("=" * 80)

# Process each tick
for idx, row in df.iterrows():
    mp.update(row["Timestamp"], row["Precio"], row["Volumen"], row["Lado"])

    current_time = row["Timestamp"]
    current_price = float(str(row["Precio"]).replace(",", "."))

    # Skip warmup period (first 2 minutes)
    if (current_time - start_time) < WARMUP_PERIOD:
        continue

    # Check if we're in cooldown period
    if last_detection_time is not None:
        time_since_last = current_time - last_detection_time
        if time_since_last < COOLDOWN_PERIOD:
            continue  # Skip detection, still in cooldown

    # Get current profile
    profile = mp.profile()

    if not profile:
        continue

    # Get all prices
    prices = sorted(profile.keys())
    if len(prices) < 2:
        continue

    highest_price = prices[-1]
    lowest_price = prices[0]

    # Get ASK volumes and find max
    ask_volumes = {p: profile[p]["ASK"] for p in prices if profile[p]["ASK"] > 0}
    if ask_volumes:
        max_ask_price = max(ask_volumes, key=ask_volumes.get)
        max_ask_volume = ask_volumes[max_ask_price]
    else:
        max_ask_price = None
        max_ask_volume = 0

    # Get BID volumes and find max
    bid_volumes = {p: profile[p]["BID"] for p in prices if profile[p]["BID"] > 0}
    if bid_volumes:
        max_bid_price = min(
            bid_volumes,
            key=lambda p: (
                p if bid_volumes[p] == max(bid_volumes.values()) else float("inf")
            ),
        )
        # Find the price with maximum BID volume
        max_bid_volume = max(bid_volumes.values())
        prices_with_max_bid = [p for p, v in bid_volumes.items() if v == max_bid_volume]
        max_bid_price = min(prices_with_max_bid) if prices_with_max_bid else None
    else:
        max_bid_price = None
        max_bid_volume = 0

    # Check conditions:
    # 1. Maximum ASK volume is at the highest price AND current price is at the high
    # 2. Maximum BID volume is at the lowest price AND current price is at the low
    condition_met = False
    condition_type = ""

    # Tolerance for price matching (1 tick = 0.25 points)
    PRICE_TOLERANCE = 0.25

    # ASK_AT_HIGH: Heavy buying at highest price AND current price is at/near the high
    if (
        max_ask_price is not None
        and max_ask_price == highest_price
        and max_ask_volume > 0
    ):
        if abs(current_price - highest_price) <= PRICE_TOLERANCE:
            condition_met = True
            condition_type = "ASK_AT_HIGH"

    # BID_AT_LOW: Heavy selling at lowest price AND current price is at/near the low
    if (
        max_bid_price is not None
        and max_bid_price == lowest_price
        and max_bid_volume > 0
    ):
        if abs(current_price - lowest_price) <= PRICE_TOLERANCE:
            condition_met = True
            if condition_type:
                condition_type += " + BID_AT_LOW"
            else:
                condition_type = "BID_AT_LOW"

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
        mp_after = RollingMarketProfile(window=timedelta(seconds=60))

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

            # Mark special prices
            marker = ""
            if price == highest_price and max_ask_price == highest_price:
                marker = " <- MAX ASK AT HIGH"
            if price == lowest_price and max_bid_price == lowest_price:
                marker = " <- MAX BID AT LOW"

            print(
                f"Price {price:>10.2f} | BID: {bid_vol:>6.0f} | "
                f"ASK: {ask_vol:>6.0f} | Total: {total_vol:>6.0f}{marker}"
            )

        print(f"{'-' * 80}")
        print(f"Total price levels: {len(prices)}")
        print(f"Price range: {lowest_price:.2f} - {highest_price:.2f}")

        # Show top volumes
        if bid_volumes:
            top_bid_price = max(bid_volumes, key=bid_volumes.get)
            print(
                f"Highest BID volume: {bid_volumes[top_bid_price]:.0f} at {top_bid_price:.2f}"
            )

        if ask_volumes:
            top_ask_price = max(ask_volumes, key=ask_volumes.get)
            print(
                f"Highest ASK volume: {ask_volumes[top_ask_price]:.0f} at {top_ask_price:.2f}"
            )

        print(f"{'=' * 80}\n")

print(f"\n{'=' * 80}")
print(f"Processing complete!")
print(f"Total ticks processed: {len(df)}")
print(f"Total detections: {detection_count}")
print(f"{'=' * 80}")
