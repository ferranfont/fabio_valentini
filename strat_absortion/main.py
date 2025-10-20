import random
from datetime import timedelta
import pandas as pd

from rolling_profile import RollingMarketProfile


# Load data
csv_path = "../data/time_and_sales_nq_30min.csv"
df = pd.read_csv(csv_path, sep=";", decimal=",")

# Get unique timestamps at second precision
df["ts_second"] = pd.to_datetime(df["Timestamp"]).dt.floor("s")
unique_seconds = df["ts_second"].unique()

# Pick a random second from the period
random_second = pd.Timestamp(random.choice(unique_seconds))
print(f"Random timestamp selected: {random_second}")
print(f"Period: {df['Timestamp'].min()} to {df['Timestamp'].max()}")
print(f"Total unique seconds in dataset: {len(unique_seconds)}")
print("-" * 80)

# Create rolling profile and process all ticks up to the random second
mp = RollingMarketProfile(window=timedelta(seconds=60))

ticks_until_random = df[pd.to_datetime(df["Timestamp"]) <= random_second]
print(f"Processing {len(ticks_until_random)} ticks up to {random_second}...")

for _, row in ticks_until_random.iterrows():
    mp.update(row["Timestamp"], row["Precio"], row["Volumen"], row["Lado"])

# Display market profile at the random second
print(f"\nMarket Profile at {random_second} (60-second rolling window):")
print("=" * 80)

profile = mp.profile()
if profile:
    sorted_prices = sorted(profile.keys(), reverse=True)
    for price in sorted_prices:
        data = profile[price]
        bid_vol = data["BID"]
        ask_vol = data["ASK"]
        total_vol = data["Total"]

        bid_count = mp.get_trade_count(price, "BID")
        ask_count = mp.get_trade_count(price, "ASK")

        print(f"Price {price:>10.2f} | BID: {bid_vol:>6.0f} ({bid_count:>3} trades) | "
              f"ASK: {ask_vol:>6.0f} ({ask_count:>3} trades) | Total: {total_vol:>6.0f}")

    print("-" * 80)
    print(f"Total price levels: {len(profile)}")
    print(f"Max Ask: {mp.get_max_ask()}")
    print(f"Min Bid: {mp.get_min_bid()}")

    # Top 5 BID prices
    bid_volumes = [(p, d["BID"]) for p, d in profile.items() if d["BID"] > 0]
    top_bids = sorted(bid_volumes, key=lambda x: x[1], reverse=True)[:5]
    print(f"\nTop 5 prices by BID volume:")
    for price, vol in top_bids:
        print(f"  {price:>10.2f}: {vol:>6.0f} contracts")

    # Top 5 ASK prices
    ask_volumes = [(p, d["ASK"]) for p, d in profile.items() if d["ASK"] > 0]
    top_asks = sorted(ask_volumes, key=lambda x: x[1], reverse=True)[:5]
    print(f"\nTop 5 prices by ASK volume:")
    for price, vol in top_asks:
        print(f"  {price:>10.2f}: {vol:>6.0f} contracts")
else:
    print("No data in the rolling window at this timestamp.")
