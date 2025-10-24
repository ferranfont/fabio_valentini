import pandas as pd
from pathlib import Path

# Load CSV file - tracking_record contains exit_reason, profit_dollars, side, entry_signal
csv_path = Path("outputs/tracking_record_absortion_shape_all_day.csv")

# Read with European format (semicolon separator, comma decimal)
df = pd.read_csv(csv_path, sep=";", decimal=",")

# Count exit reasons
target_df = df[df["exit_reason"] == "TARGET"]
stop_df = df[df["exit_reason"] == "STOP"]

target_count = len(target_df)
stop_count = len(stop_df)
total_trades = len(df)

# Sum profit_dollars
target_profit = target_df["profit_dollars"].sum()
stop_profit = stop_df["profit_dollars"].sum()
total_profit = df["profit_dollars"].sum()

# Calculate percentages
target_pct = (target_count / total_trades * 100) if total_trades > 0 else 0
stop_pct = (stop_count / total_trades * 100) if total_trades > 0 else 0

# Print results
print("=" * 50)
print("EXIT REASON ANALYSIS")
print("=" * 50)
print(f"Total Trades:  {total_trades}")
print(f"Total Profit:  ${total_profit:,.2f}")
print("-" * 50)
print(f"TARGET exits: {target_count:4d} ({target_pct:5.2f}%) | Profit: ${target_profit:,.2f}")
print(f"STOP exits:   {stop_count:4d} ({stop_pct:5.2f}%) | Profit: ${stop_profit:,.2f}")
print("=" * 50)

# Additional breakdown by side
print("\nBREAKDOWN BY SIDE:")
print("-" * 50)
for side in df["side"].unique():
    side_df = df[df["side"] == side]
    side_target_df = side_df[side_df["exit_reason"] == "TARGET"]
    side_stop_df = side_df[side_df["exit_reason"] == "STOP"]

    side_target = len(side_target_df)
    side_stop = len(side_stop_df)
    side_total = len(side_df)

    side_target_profit = side_target_df["profit_dollars"].sum()
    side_stop_profit = side_stop_df["profit_dollars"].sum()
    side_total_profit = side_df["profit_dollars"].sum()

    print(f"\n{side}:")
    print(f"  Total:  {side_total} | Profit: ${side_total_profit:,.2f}")
    print(f"  TARGET: {side_target} ({side_target/side_total*100:.2f}%) | ${side_target_profit:,.2f}")
    print(f"  STOP:   {side_stop} ({side_stop/side_total*100:.2f}%) | ${side_stop_profit:,.2f}")

# Breakdown by entry signal
print("\n" + "=" * 50)
print("BREAKDOWN BY ENTRY SIGNAL:")
print("-" * 50)
for signal in df["entry_signal"].unique():
    signal_df = df[df["entry_signal"] == signal]
    signal_target_df = signal_df[signal_df["exit_reason"] == "TARGET"]
    signal_stop_df = signal_df[signal_df["exit_reason"] == "STOP"]

    signal_target = len(signal_target_df)
    signal_stop = len(signal_stop_df)
    signal_total = len(signal_df)

    signal_target_profit = signal_target_df["profit_dollars"].sum()
    signal_stop_profit = signal_stop_df["profit_dollars"].sum()
    signal_total_profit = signal_df["profit_dollars"].sum()

    print(f"\n{signal}:")
    print(f"  Total:  {signal_total} | Profit: ${signal_total_profit:,.2f}")
    print(f"  TARGET: {signal_target} ({signal_target/signal_total*100:.2f}%) | ${signal_target_profit:,.2f}")
    print(f"  STOP:   {signal_stop} ({signal_stop/signal_total*100:.2f}%) | ${signal_stop_profit:,.2f}")

print("\n" + "=" * 50)
