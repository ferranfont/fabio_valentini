"""
Resample Sweep Data Plotter
Creates a line chart showing resampled close price over time from db_mushroom_all_data.csv
"""

import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from pathlib import Path
import webbrowser
import os

# ============================================================================
# CONFIGURATION VARIABLES
# ============================================================================
BIG_VOLUME = 90 #Volume threshold for red dots

# File paths
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
DATA_FILE = CURRENT_DIR / "db_mushroom_all_data.csv"
OUTPUT_FILE = PROJECT_ROOT / "charts" / "resample_sweep_chart.html"

print("="*80)
print("RESAMPLE SWEEP DATA PLOTTER")
print("="*80)

# Load data
print(f"\n[INFO] Loading data from: {DATA_FILE.name}")
df = pd.read_csv(DATA_FILE, sep=';', decimal=',')
# Strip whitespace from column names and string values
df.columns = df.columns.str.strip()
df['pattern_tag'] = df['pattern_tag'].str.strip()
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.sort_values('timestamp')

print(f"[OK] Loaded {len(df):,} frames")
print(f"[INFO] Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
print(f"[INFO] Price range: {df['close_price'].min():.2f} to {df['close_price'].max():.2f}")

# Pattern breakdown
pattern_counts = df['pattern_tag'].value_counts()
print(f"\n[INFO] Pattern breakdown:")
for pattern, count in pattern_counts.items():
    print(f"  - {pattern}: {count:,} frames ({count/len(df)*100:.2f}%)")

# Big volume breakdown
big_volume_count = len(df[df['total_volume'] > BIG_VOLUME])
print(f"\n[INFO] Big Volume (>{BIG_VOLUME}):")
print(f"  - Frames with big volume: {big_volume_count:,} ({big_volume_count/len(df)*100:.2f}%)")

# Create figure with subplots (2 rows)
fig = make_subplots(
    rows=2, cols=1,
    row_heights=[0.7, 0.3],
    vertical_spacing=0.05,
    subplot_titles=('Price Chart', 'BID/ASK Ratio'),
    specs=[[{"secondary_y": True}], [{"secondary_y": False}]]
)

# Add close price line (row 1, primary y-axis)
fig.add_trace(go.Scatter(
    x=df['timestamp'],
    y=df['close_price'],
    mode='lines',
    name='Close Price',
    line=dict(color='blue', width=1),
    hovertemplate='<b>%{x}</b><br>Close Price: %{y:.2f}<extra></extra>',
    showlegend=False
), row=1, col=1, secondary_y=False)

# Add big volume markers (VERTICAL LIGHT GREY LINES)
big_volume_df = df[df['total_volume'] > BIG_VOLUME].copy()
shapes = []
if len(big_volume_df) > 0:
    # Create shapes list for all vertical lines (much faster than individual vlines)
    for timestamp in big_volume_df['timestamp']:
        shapes.append(
            dict(
                type='line',
                x0=timestamp,
                x1=timestamp,
                y0=0,
                y1=1,
                yref='paper',  # Use paper coordinates for y (0 to 1 = full height)
                line=dict(color='lightgrey', width=1),
                layer='below'
            )
        )

# Add mushroom pattern markers (MAGENTA dots) (row 1, primary y-axis)
mushroom_df = df[df['pattern_tag'] == 'mushroom']
if len(mushroom_df) > 0:
    fig.add_trace(go.Scatter(
        x=mushroom_df['timestamp'],
        y=mushroom_df['close_price'],
        mode='markers',
        name='Mushroom Pattern',
        marker=dict(
            color='magenta',
            size=10,
            symbol='circle',
            line=dict(color='black', width=1)
        ),
        hovertemplate='<b>Mushroom</b><br>%{x}<br>Price: %{y:.2f}<extra></extra>',
        showlegend=False
    ), row=1, col=1, secondary_y=False)

# Add BID volume line (RED) (row 1, secondary y-axis)
fig.add_trace(go.Scatter(
    x=df['timestamp'],
    y=df['total_bid'],
    mode='lines',
    name='BID Volume',
    line=dict(color='red', width=1),
    showlegend=False
), row=1, col=1, secondary_y=True)

# Add ASK volume line (GREEN) (row 1, secondary y-axis)
fig.add_trace(go.Scatter(
    x=df['timestamp'],
    y=df['total_ask'],
    mode='lines',
    name='ASK Volume',
    line=dict(color='green', width=1),
    showlegend=False
), row=1, col=1, secondary_y=True)

# Add BID/ASK ratio (BLACK) (row 2)
fig.add_trace(go.Scatter(
    x=df['timestamp'],
    y=df['bid_ask_ratio'],
    mode='lines',
    name='BID/ASK Ratio',
    line=dict(color='black', width=1),
    showlegend=False
), row=2, col=1)

# Update layout
fig.update_layout(
    title=dict(
        text=f'NQ Resampled Price Chart - Mushroom Sweep Analysis<br><sub>{len(df):,} frames | {len(mushroom_df)} Mushroom patterns | {len(big_volume_df)} Big Volume (>{BIG_VOLUME})</sub>',
        x=0.5,
        xanchor='center',
        font=dict(size=18, color='black')
    ),
    width=1600,
    height=900,
    plot_bgcolor='white',
    paper_bgcolor='white',
    hovermode=False,
    dragmode='pan',
    showlegend=False,
    shapes=shapes  # Add all vertical lines at once
)

# Update xaxis and yaxis for subplot 1 (Price chart)
fig.update_xaxes(
    title='',
    showgrid=False,
    linecolor='black',
    linewidth=1,
    row=1, col=1
)

# Primary y-axis (left) - Price
fig.update_yaxes(
    title='Close Price (NQ)',
    showgrid=True,
    gridcolor='rgba(128,128,128,0.2)',
    linecolor='black',
    linewidth=1,
    row=1, col=1,
    secondary_y=False
)

# Secondary y-axis (right) - Volume
fig.update_yaxes(
    title='Volume',
    showgrid=False,
    linecolor='black',
    linewidth=1,
    row=1, col=1,
    secondary_y=True
)

# Update xaxis and yaxis for subplot 2 (BID/ASK Ratio)
fig.update_xaxes(
    title='Timestamp',
    showgrid=False,
    linecolor='black',
    linewidth=1,
    row=2, col=1
)
fig.update_yaxes(
    title='BID/ASK Ratio',
    showgrid=True,
    gridcolor='rgba(128,128,128,0.2)',
    linecolor='black',
    linewidth=1,
    row=2, col=1
)

# Save chart
OUTPUT_FILE.parent.mkdir(exist_ok=True)
fig.write_html(
    str(OUTPUT_FILE),
    config={
        "scrollZoom": True,
        "displayModeBar": True,
        "modeBarButtonsToRemove": ['lasso2d', 'select2d']
    }
)

print(f"\n[OK] Chart saved: {OUTPUT_FILE}")

# Open in browser
webbrowser.open('file://' + os.path.realpath(str(OUTPUT_FILE)))
print(f"[OK] Chart opened in browser")

print("\n" + "="*80)
print("COMPLETED")
print("="*80)
