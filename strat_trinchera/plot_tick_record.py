"""
Plot Tick Record Chart - Simple Version
Shows Price (left axis) and factor_tps (right axis) over time
"""
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
from datetime import datetime
import webbrowser

vwap_window = 12000
FACTOR_TPS_THRESHOLD = 3000

# File paths
input_file = r'd:\PYTHON\ALGOS\fabio_valentini\strat_trinchera\outputs\tick_record_20251212_132509.csv'
output_dir = r'd:\PYTHON\ALGOS\fabio_valentini\strat_trinchera\charts'

# Create charts directory if it doesn't exist
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

print(f"Reading file: {input_file}")

# Read CSV with European format
df = pd.read_csv(input_file, sep=';', decimal=',')

# Clean column names
df.columns = df.columns.str.strip()

print(f"Total records: {len(df):,}")
print(f"Columns: {list(df.columns)}")

# Check if factor_tps exists
if 'factor_tps' not in df.columns:
    print("\n[ERROR] Column 'factor_tps' not found in CSV!")
    print("Please run add_factor_tps.py first to add the factor_tps column.")
    exit(1)

# Convert timestamp to datetime
df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed', errors='coerce', utc=True)
df['timestamp'] = df['timestamp'].dt.tz_localize(None)
df = df.dropna(subset=['timestamp'])

# Convert to numeric
df['price'] = pd.to_numeric(df['price'], errors='coerce')
df['factor_tps'] = pd.to_numeric(df['factor_tps'], errors='coerce')

# Drop NaN values
df = df.dropna(subset=['price', 'factor_tps'])

# Sort by timestamp
df = df.sort_values('timestamp').reset_index(drop=True)

print(f"\nValid records: {len(df):,}")
print(f"Price range: {df['price'].min():.2f} - {df['price'].max():.2f}")
print(f"Factor TPS range: {df['factor_tps'].min():.2f} - {df['factor_tps'].max():.2f}")

# Calculate VWAP (Volume Weighted Average Price) - Rolling 144 ticks
print("\nCalculating VWAP (ticks rolling window)...")


df['vol_price'] = df['price'] * df['window_vol']
df['rolling_vol'] = df['window_vol'].rolling(window=vwap_window, min_periods=1).sum()
df['rolling_vol_price'] = df['vol_price'].rolling(window=vwap_window, min_periods=1).sum()
df['vwap'] = df['rolling_vol_price'] / df['rolling_vol']

# Drop temporary columns
df = df.drop(['vol_price', 'rolling_vol', 'rolling_vol_price'], axis=1)

print(f"VWAP range: {df['vwap'].min():.2f} - {df['vwap'].max():.2f}")

# Create figure with secondary y-axis
fig = make_subplots(specs=[[{"secondary_y": True}]])

# Add Price trace (left y-axis, royal blue)
fig.add_trace(
    go.Scatter(
        x=df['timestamp'],
        y=df['price'],
        name='Price',
        mode='lines',
        line=dict(color='#4169E1', width=1.5),  # Royal blue
        hoverinfo='skip'
    ),
    secondary_y=False
)

# Add VWAP trace (left y-axis, dark green)
fig.add_trace(
    go.Scatter(
        x=df['timestamp'],
        y=df['vwap'],
        name='VWAP',
        mode='lines',
        line=dict(color='#228B22', width=2),  # Dark green (Forest Green)
        hoverinfo='skip'
    ),
    secondary_y=False
)

# Add factor_tps trace (right y-axis, bright red)
fig.add_trace(
    go.Scatter(
        x=df['timestamp'],
        y=df['factor_tps'],
        name='Factor TPS',
        mode='lines',
        line=dict(color='#FF0000', width=1.5),  # Bright red
        hoverinfo='skip'
    ),
    secondary_y=True
)

# Add RED DOTS on price line when factor_tps > 1500

high_factor_events = df[df['factor_tps'] > FACTOR_TPS_THRESHOLD].copy()

print(f"\nHigh factor_tps events (>{FACTOR_TPS_THRESHOLD}): {len(high_factor_events)}")

if len(high_factor_events) > 0:
    fig.add_trace(
        go.Scatter(
            x=high_factor_events['timestamp'],
            y=high_factor_events['price'],
            name=f'High Factor TPS (>{FACTOR_TPS_THRESHOLD})',
            mode='markers',
            marker=dict(
                color='#FF0000',  # Bright red
                size=6,
                symbol='circle',
                line=dict(color='#CC0000', width=1)
            ),
            hoverinfo='skip'
        ),
        secondary_y=False
    )

# Update layout
fig.update_layout(
    title=dict(
        text='Tick Record Analysis - Price, VWAP & Factor TPS',
        font=dict(size=20, color='#2c3e50')
    ),
    hovermode=False,  # Disable hover
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1
    ),
    plot_bgcolor='white',
    width=1800,
    height=900,
    margin=dict(l=80, r=80, t=120, b=80)
)

# Update x-axis
fig.update_xaxes(
    title_text="Time",
    showgrid=False
)

# Update y-axes titles
fig.update_yaxes(
    title_text="<b>Price (NQ)</b>",
    showgrid=False,
    tickformat='.2f',
    secondary_y=False
)

fig.update_yaxes(
    title_text="<b>Factor TPS (window_vol × tps_window)</b>",
    showgrid=False,
    tickformat=',.0f',
    secondary_y=True
)

# Save chart
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
output_file = os.path.join(output_dir, f'tick_record_chart_{timestamp}.html')

fig.write_html(output_file)

print(f"\nChart saved: {output_file}")

# Open in browser
webbrowser.open('file://' + output_file)
print("Chart opened in browser!")
