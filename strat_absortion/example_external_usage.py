"""
Example: Using AbsorptionStrategy from external code

This demonstrates how to use the AbsorptionStrategy class from
another module or application.
"""

from pathlib import Path
from absorption_strategy import AbsorptionStrategy


def run_custom_strategy():
    """Example of running the strategy with custom parameters."""

    # Option 1: Use with default CSV path (from environment or default file)
    strategy = AbsorptionStrategy(
        profile_window=30,  # Custom window size
        min_price_levels=15,  # Lower threshold for more detections
        filter_ny_hours=True,  # Only NY trading hours
    )

    results = strategy.run()

    print(f"\nStrategy completed!")
    print(f"Detections found: {results['detection_count']}")
    print(f"HTML report: {results['html_path']}")
    print(f"CSV signals: {results['csv_path']}")

    return results


def run_with_custom_csv():
    """Example of running with a specific CSV file."""

    # Option 2: Provide specific CSV path
    csv_path = Path("C:/trade/ferran/fabio_valentini/data/historic/my_custom_data.csv")

    strategy = AbsorptionStrategy(
        csv_path=csv_path,
        profile_window=20,
        extreme_volume_multiplier=2.5,  # Stricter criteria
        min_bid_ask_size=50,  # Higher minimum size
        cooldown_period=120,  # 2-minute cooldown
    )

    results = strategy.run()
    return results


def access_signal_data():
    """Example of accessing and processing signal data."""

    strategy = AbsorptionStrategy(
        profile_window=20,
        min_price_levels=20,
    )

    results = strategy.run()

    # Access the signal records
    for i, signal in enumerate(results['signal_records'][:5]):  # First 5 signals
        print(f"\nSignal {i+1}:")
        print(f"  Timestamp: {signal['timestamp']}")
        print(f"  Shape: {signal['shape']}")
        print(f"  Close Price: {signal['close_price']:.2f}")
        print(f"  Bid/Ask Ratio: {signal['bid_ask_ratio']:.2f}")
        print(f"  Price Levels: {signal['num_price_levels']}")

    return results


def integrate_with_trading_system():
    """
    Example: Integration with a trading system.

    This shows how you might use the strategy in a larger
    trading application.
    """

    # Initialize strategy with production parameters
    strategy = AbsorptionStrategy(
        profile_window=20,
        min_price_levels=20,
        min_bid_ask_size=30,
        filter_ny_hours=True,  # Production: only trade during NY hours
        cooldown_period=60,
    )

    # Run detection
    results = strategy.run()

    # Process signals for trading
    for signal in results['signal_records']:
        shape = signal['shape']
        price = signal['close_price']
        timestamp = signal['timestamp']

        # Your trading logic here
        if shape == 'd_shape':
            print(f"[{timestamp}] LONG signal at {price:.2f}")
            # send_long_order(price, timestamp)
        elif shape == 'p_shape':
            print(f"[{timestamp}] SHORT signal at {price:.2f}")
            # send_short_order(price, timestamp)

    return results


if __name__ == "__main__":
    print("=" * 80)
    print("Example 1: Running with custom parameters")
    print("=" * 80)

    # Uncomment to run examples:
    # run_custom_strategy()

    # run_with_custom_csv()

    # access_signal_data()

    # integrate_with_trading_system()

    print("\nExamples ready. Uncomment the function calls to execute.")
