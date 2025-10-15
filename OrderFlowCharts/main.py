from OrderFlow import OrderFlowChart
import pandas as pd
import numpy as np

# Configuration
INPUT_FILE = '../data/time_and_sales_nq_30min.csv'
CANDLE_INTERVAL = '1min'
MAX_CANDLES = 500

print(f"Loading tick data from {INPUT_FILE}...")
# Read tick data with European format
df = pd.read_csv(
    INPUT_FILE,
    sep=';',
    decimal=',',
    parse_dates=['Timestamp'],
    dtype={'Volumen': int}
)

print(f"Loaded {len(df):,} ticks")

# Convert price columns to float
df['Precio'] = df['Precio'].astype(float)
df['Bid'] = df['Bid'].astype(float)
df['Ask'] = df['Ask'].astype(float)

# Set timestamp as index
df.set_index('Timestamp', inplace=True)

print(f"\nCreating {CANDLE_INTERVAL} candles...")

# Group by candle interval
df['candle_id'] = df.index.floor(CANDLE_INTERVAL)

# Limit to MAX_CANDLES most recent candles
unique_candles = df['candle_id'].unique()
if len(unique_candles) > MAX_CANDLES:
    print(f"Limiting to {MAX_CANDLES} most recent candles...")
    selected_candles = unique_candles[-MAX_CANDLES:]
    df = df[df['candle_id'].isin(selected_candles)]

print(f"Processing {df['candle_id'].nunique()} candles...")

# ============================================================================
# 1. Create OHLC data in memory
# ============================================================================
print("\nGenerating OHLC data...")

ohlc_list = []
for candle_time, group in df.groupby('candle_id'):
    ohlc_list.append({
        'timestamp': candle_time,
        'open': group['Precio'].iloc[0],
        'high': group['Precio'].max(),
        'low': group['Precio'].min(),
        'close': group['Precio'].iloc[-1],
        'identifier': candle_time.strftime('%Y-%m-%d %H:%M:%S')
    })

ohlc_data = pd.DataFrame(ohlc_list)
ohlc_data.set_index('timestamp', inplace=True)

print(f"Created {len(ohlc_data)} OHLC candles")

# ============================================================================
# 2. Create Orderflow data in memory
# ============================================================================
print("\nGenerating orderflow data...")

orderflow_list = []

for candle_time, group in df.groupby('candle_id'):
    identifier = candle_time.strftime('%Y-%m-%d %H:%M:%S')

    # Aggregate volume by price level and side
    volume_by_price = group.groupby(['Precio', 'Lado'])['Volumen'].sum().unstack(fill_value=0)

    # Ensure both BID and ASK columns exist
    if 'BID' not in volume_by_price.columns:
        volume_by_price['BID'] = 0
    if 'ASK' not in volume_by_price.columns:
        volume_by_price['ASK'] = 0

    # Get all price levels in this candle
    for price in volume_by_price.index:
        bid_vol = volume_by_price.loc[price, 'BID']
        ask_vol = volume_by_price.loc[price, 'ASK']

        orderflow_list.append({
            'timestamp': candle_time,
            'bid_size': int(bid_vol),
            'price': float(price),
            'ask_size': int(ask_vol),
            'identifier': identifier
        })

orderflow_data = pd.DataFrame(orderflow_list)
orderflow_data.set_index('timestamp', inplace=True)

print(f"Created {len(orderflow_data)} orderflow records across {orderflow_data['identifier'].nunique()} candles")
print(f"Price range: {orderflow_data['price'].min():.2f} - {orderflow_data['price'].max():.2f}")

# ============================================================================
# 3. Create OrderFlowChart and plot (no intermediate files)
# ============================================================================
print("\nCreating OrderFlowChart visualization...")

orderflowchart = OrderFlowChart(
    orderflow_data,
    ohlc_data,
    identifier_col='identifier'
)

# Plot the orderflow chart
orderflowchart.plot()