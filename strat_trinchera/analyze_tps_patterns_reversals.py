"""
Analyze if TPS PATTERNS (segments/trends) can predict market reversals
"""
import pandas as pd
import numpy as np
from scipy import stats

# Read CSV
input_file = r'd:\PYTHON\ALGOS\fabio_valentini\strat_trinchera\outputs\tick_record_20251212_132509.csv'

print("Reading CSV...")
df = pd.read_csv(input_file, sep=';', decimal=',')
df.columns = df.columns.str.strip()

print(f"Total records: {len(df):,}")

# Convert timestamp and price
df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed', errors='coerce', utc=True)
df['timestamp'] = df['timestamp'].dt.tz_localize(None)
df = df.dropna(subset=['timestamp'])
df['price'] = df['price'].astype(float)
df = df.sort_values('timestamp').reset_index(drop=True)

# Calculate TPS window if not present
if 'tps_window' not in df.columns:
    print("\nCalculating TPS window...")
    start_time = df['timestamp'].min()
    df['seconds'] = (df['timestamp'] - start_time).dt.total_seconds()

    window_seconds = 10
    tps_window_values = []
    sample_rate = 10
    sample_indices = list(range(0, len(df), sample_rate))

    for idx in sample_indices:
        current_sec = df.loc[idx, 'seconds']
        window_start = current_sec - window_seconds
        in_window = (df['seconds'] > window_start) & (df['seconds'] <= current_sec)
        count = in_window.sum()

        if count > 1:
            window_data = df.loc[in_window, 'seconds']
            duration = current_sec - window_data.min()
            tps = count / duration if duration > 0 else count
        else:
            tps = 1.0

        tps_window_values.append(tps)

    tps_sampled = pd.Series(tps_window_values, index=sample_indices)
    df['tps_window'] = tps_sampled.reindex(df.index).interpolate(method='linear').bfill().ffill()
    df = df.drop('seconds', axis=1)

print("\n" + "="*70)
print("ANALYZING TPS PATTERNS FOR MARKET REVERSAL PREDICTION")
print("="*70)

# Sample every 100 ticks for performance (still 4,316 points)
df_sample = df.iloc[::100].copy()
print(f"\nWorking with {len(df_sample):,} sampled points (every 100 ticks)")

# Calculate price changes and trends
df_sample['price_change_1min'] = df_sample['price'].diff(6)  # ~1 minute ahead
df_sample['price_change_5min'] = df_sample['price'].diff(30)  # ~5 minutes ahead

# Calculate TPS trends (change in TPS)
df_sample['tps_change'] = df_sample['tps_window'].diff()
df_sample['tps_pct_change'] = df_sample['tps_window'].pct_change() * 100

# Rolling statistics for TPS (pattern detection)
df_sample['tps_ma_short'] = df_sample['tps_window'].rolling(5).mean()
df_sample['tps_ma_long'] = df_sample['tps_window'].rolling(20).mean()
df_sample['tps_trend'] = df_sample['tps_ma_short'] - df_sample['tps_ma_long']

# Detect TPS spikes and drops
df_sample['tps_spike'] = (df_sample['tps_window'] > df_sample['tps_window'].rolling(10).mean() * 1.5)
df_sample['tps_drop'] = (df_sample['tps_window'] < df_sample['tps_window'].rolling(10).mean() * 0.5)

# Detect price reversals (local highs and lows)
df_sample['price_local_high'] = (
    (df_sample['price'] > df_sample['price'].shift(1)) &
    (df_sample['price'] > df_sample['price'].shift(-1)) &
    (df_sample['price'] > df_sample['price'].shift(2)) &
    (df_sample['price'] > df_sample['price'].shift(-2))
)

df_sample['price_local_low'] = (
    (df_sample['price'] < df_sample['price'].shift(1)) &
    (df_sample['price'] < df_sample['price'].shift(-1)) &
    (df_sample['price'] < df_sample['price'].shift(2)) &
    (df_sample['price'] < df_sample['price'].shift(-2))
)

# Drop NaN rows
df_sample = df_sample.dropna()

print("\n" + "="*70)
print("PATTERN 1: TPS SPIKES BEFORE REVERSALS")
print("="*70)

# Analyze TPS behavior before reversals
reversal_highs = df_sample[df_sample['price_local_high']]
reversal_lows = df_sample[df_sample['price_local_low']]

print(f"\nPrice local highs detected: {len(reversal_highs)}")
print(f"Price local lows detected: {len(reversal_lows)}")

# TPS statistics at reversal points
print("\nTPS at LOCAL HIGHS (potential reversal down):")
print(f"  Average TPS: {reversal_highs['tps_window'].mean():.2f}")
print(f"  Median TPS: {reversal_highs['tps_window'].median():.2f}")
print(f"  Avg TPS trend: {reversal_highs['tps_trend'].mean():.2f}")

# Check if TPS was spiking before high
spikes_before_high = reversal_highs['tps_spike'].sum()
pct_spikes_before_high = spikes_before_high / len(reversal_highs) * 100

print(f"\nTPS spikes at local highs: {spikes_before_high} ({pct_spikes_before_high:.1f}%)")

print("\nTPS at LOCAL LOWS (potential reversal up):")
print(f"  Average TPS: {reversal_lows['tps_window'].mean():.2f}")
print(f"  Median TPS: {reversal_lows['tps_window'].median():.2f}")
print(f"  Avg TPS trend: {reversal_lows['tps_trend'].mean():.2f}")

spikes_before_low = reversal_lows['tps_spike'].sum()
pct_spikes_before_low = spikes_before_low / len(reversal_lows) * 100

print(f"\nTPS spikes at local lows: {spikes_before_low} ({pct_spikes_before_low:.1f}%)")

# Overall TPS spike rate (baseline)
overall_spike_rate = df_sample['tps_spike'].sum() / len(df_sample) * 100
print(f"\nBaseline TPS spike rate: {overall_spike_rate:.1f}%")

print("\n" + "="*70)
print("PATTERN 2: TPS TREND CHANGES")
print("="*70)

# Detect TPS trend changes (from rising to falling, or vice versa)
df_sample['tps_trend_up'] = df_sample['tps_trend'] > 0
df_sample['tps_trend_change'] = df_sample['tps_trend_up'] != df_sample['tps_trend_up'].shift(1)

# Find points where TPS trend changes
tps_trend_changes = df_sample[df_sample['tps_trend_change']]

print(f"\nTPS trend changes detected: {len(tps_trend_changes)}")

# After TPS trend change, does price reverse?
# Check price direction 5-10 points ahead
trend_change_analysis = []

for idx in tps_trend_changes.index:
    try:
        # Get position in dataframe
        pos = df_sample.index.get_loc(idx)

        # Skip if near end
        if pos + 10 >= len(df_sample):
            continue

        current_price = df_sample.iloc[pos]['price']
        future_price_short = df_sample.iloc[pos + 5]['price']  # ~5 minutes
        future_price_long = df_sample.iloc[pos + 10]['price']  # ~10 minutes

        current_tps_trend = df_sample.iloc[pos]['tps_trend']

        price_change_short = future_price_short - current_price
        price_change_long = future_price_long - current_price

        trend_change_analysis.append({
            'tps_trend': current_tps_trend,
            'price_change_short': price_change_short,
            'price_change_long': price_change_long
        })
    except:
        continue

df_trend_analysis = pd.DataFrame(trend_change_analysis)

if len(df_trend_analysis) > 0:
    print("\nAfter TPS trend changes to POSITIVE (TPS accelerating):")
    tps_up = df_trend_analysis[df_trend_analysis['tps_trend'] > 0]
    print(f"  Count: {len(tps_up)}")
    print(f"  Avg price change (5min): {tps_up['price_change_short'].mean():.2f}")
    print(f"  Avg price change (10min): {tps_up['price_change_long'].mean():.2f}")

    print("\nAfter TPS trend changes to NEGATIVE (TPS decelerating):")
    tps_down = df_trend_analysis[df_trend_analysis['tps_trend'] < 0]
    print(f"  Count: {len(tps_down)}")
    print(f"  Avg price change (5min): {tps_down['price_change_short'].mean():.2f}")
    print(f"  Avg price change (10min): {tps_down['price_change_long'].mean():.2f}")

print("\n" + "="*70)
print("PATTERN 3: TPS SURGE -> EXHAUSTION -> REVERSAL")
print("="*70)

# Detect pattern: TPS surge followed by drop
df_sample['tps_surge'] = (
    (df_sample['tps_window'] > 80) &  # High TPS
    (df_sample['tps_pct_change'] > 20)  # Rapid increase
)

df_sample['tps_exhaustion'] = (
    (df_sample['tps_window'].shift(1) > 80) &  # Was high
    (df_sample['tps_window'] < df_sample['tps_window'].shift(1) * 0.7)  # Dropped significantly
)

surge_points = df_sample[df_sample['tps_surge']]
exhaustion_points = df_sample[df_sample['tps_exhaustion']]

print(f"\nTPS surge events: {len(surge_points)}")
print(f"TPS exhaustion events (drop after surge): {len(exhaustion_points)}")

# Analyze price behavior after exhaustion
exhaustion_analysis = []

for idx in exhaustion_points.index:
    try:
        pos = df_sample.index.get_loc(idx)
        if pos + 10 >= len(df_sample):
            continue

        current_price = df_sample.iloc[pos]['price']
        price_before = df_sample.iloc[pos - 3]['price']  # 3 points before
        future_price = df_sample.iloc[pos + 5]['price']  # 5 points after

        trend_before = 'up' if current_price > price_before else 'down'
        price_reversed = (
            (trend_before == 'up' and future_price < current_price) or
            (trend_before == 'down' and future_price > current_price)
        )

        exhaustion_analysis.append({
            'trend_before': trend_before,
            'reversed': price_reversed,
            'price_change': future_price - current_price
        })
    except:
        continue

df_exhaustion = pd.DataFrame(exhaustion_analysis)

if len(df_exhaustion) > 0:
    reversal_rate = df_exhaustion['reversed'].sum() / len(df_exhaustion) * 100

    print(f"\nAfter TPS exhaustion:")
    print(f"  Price reversed: {df_exhaustion['reversed'].sum()} / {len(df_exhaustion)} ({reversal_rate:.1f}%)")
    print(f"  Avg price change: {df_exhaustion['price_change'].mean():.2f}")

    print("\n  By prior trend:")
    for trend in ['up', 'down']:
        subset = df_exhaustion[df_exhaustion['trend_before'] == trend]
        if len(subset) > 0:
            rev_rate = subset['reversed'].sum() / len(subset) * 100
            print(f"    After {trend} trend: {rev_rate:.1f}% reversed")

print("\n" + "="*70)
print("PATTERN 4: TPS DIVERGENCE FROM PRICE")
print("="*70)

# Calculate price and TPS directions
df_sample['price_direction'] = np.sign(df_sample['price'].diff(3))
df_sample['tps_direction'] = np.sign(df_sample['tps_window'].diff(3))

# Divergence: price going up but TPS going down (or vice versa)
df_sample['divergence'] = (
    (df_sample['price_direction'] != df_sample['tps_direction']) &
    (df_sample['price_direction'] != 0) &
    (df_sample['tps_direction'] != 0)
)

divergence_points = df_sample[df_sample['divergence']]

print(f"\nDivergence points detected: {len(divergence_points)}")

# Analyze if divergence predicts reversal
divergence_analysis = []

for idx in divergence_points.index:
    try:
        pos = df_sample.index.get_loc(idx)
        if pos + 8 >= len(df_sample):
            continue

        current_price = df_sample.iloc[pos]['price']
        price_trend = df_sample.iloc[pos]['price_direction']
        tps_trend = df_sample.iloc[pos]['tps_direction']

        future_price = df_sample.iloc[pos + 8]['price']

        # Did price reverse after divergence?
        price_reversed = (
            (price_trend > 0 and future_price < current_price) or
            (price_trend < 0 and future_price > current_price)
        )

        divergence_analysis.append({
            'price_trend': 'up' if price_trend > 0 else 'down',
            'tps_trend': 'up' if tps_trend > 0 else 'down',
            'reversed': price_reversed
        })
    except:
        continue

df_divergence = pd.DataFrame(divergence_analysis)

if len(df_divergence) > 0:
    reversal_rate = df_divergence['reversed'].sum() / len(df_divergence) * 100

    print(f"\nAfter TPS-Price divergence:")
    print(f"  Price reversed: {df_divergence['reversed'].sum()} / {len(df_divergence)} ({reversal_rate:.1f}%)")

    print("\n  By divergence type:")
    # Price up, TPS down
    price_up_tps_down = df_divergence[
        (df_divergence['price_trend'] == 'up') &
        (df_divergence['tps_trend'] == 'down')
    ]
    if len(price_up_tps_down) > 0:
        rev_rate = price_up_tps_down['reversed'].sum() / len(price_up_tps_down) * 100
        print(f"    Price UP + TPS DOWN: {rev_rate:.1f}% reversed (n={len(price_up_tps_down)})")

    # Price down, TPS up
    price_down_tps_up = df_divergence[
        (df_divergence['price_trend'] == 'down') &
        (df_divergence['tps_trend'] == 'up')
    ]
    if len(price_down_tps_up) > 0:
        rev_rate = price_down_tps_up['reversed'].sum() / len(price_down_tps_up) * 100
        print(f"    Price DOWN + TPS UP: {rev_rate:.1f}% reversed (n={len(price_down_tps_up)})")

print("\n" + "="*70)
print("SUMMARY & CONCLUSIONS")
print("="*70)

print("""
FINDINGS:

1. TPS SPIKES AT REVERSALS:
   - Analyzed if high TPS occurs at price reversal points
   - Result: [See percentages above]

2. TPS TREND CHANGES:
   - When TPS accelerates/decelerates, does price follow?
   - Result: [See price changes above]

3. TPS EXHAUSTION PATTERN:
   - TPS surge -> drop = potential reversal signal?
   - Result: [See reversal rate above]

4. TPS-PRICE DIVERGENCE:
   - When price and TPS move in opposite directions
   - Classic reversal indicator from traditional TA
   - Result: [See reversal rate above]

BASELINE COMPARISON:
- Random chance of reversal: ~50%
- If pattern shows >60% reversal rate -> PREDICTIVE VALUE
- If pattern shows ~50% reversal rate -> NO PREDICTIVE VALUE
- If pattern shows <40% reversal rate -> CONTRARIAN INDICATOR

PRACTICAL USAGE:
- Patterns with >55% success can be used as CONFLUENCE factors
- Should NOT be used as standalone signals
- Best combined with price action, volume, and other indicators
""")

print("="*70)
