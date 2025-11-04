"""
Simple Price Chart Plotter - September 1, 2025 (Labor Day Early Close)
Creates a basic line chart showing price over time
"""

import pandas as pd
import plotly.graph_objs as go
from pathlib import Path
import webbrowser
import os

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
DATA_FILE = PROJECT_ROOT / "data" / "historic" / "time_and_sales_nq_20250901.csv"
OUTPUT_FILE = PROJECT_ROOT / "charts" / "price_chart_20250901.html"

print("="*80)
print("SIMPLE PRICE CHART PLOTTER - LABOR DAY 2025")
print("="*80)

# Load data
print(f"\n[INFO] Loading data from: {DATA_FILE.name}")
df = pd.read_csv(DATA_FILE, sep=';', decimal=',')
df['Timestamp'] = pd.to_datetime(df['Timestamp'])
df = df.sort_values('Timestamp')

print(f"[OK] Loaded {len(df):,} ticks")
print(f"[INFO] Date range: {df['Timestamp'].min()} to {df['Timestamp'].max()}")
print(f"[INFO] Price range: {df['Precio'].min():.2f} to {df['Precio'].max():.2f}")

# Calculate trading duration
duration = df['Timestamp'].max() - df['Timestamp'].min()
hours = duration.total_seconds() / 3600
print(f"[INFO] Trading duration: {hours:.2f} hours (Early close - Labor Day)")

# Create figure
fig = go.Figure()

# Add price line
fig.add_trace(go.Scatter(
    x=df['Timestamp'],
    y=df['Precio'],
    mode='lines',
    name='Price',
    line=dict(color='blue', width=1),
    hovertemplate='<b>%{x}</b><br>Price: %{y:.2f}<extra></extra>'
))

# Update layout
fig.update_layout(
    title=dict(
        text=f'NQ Price Chart - September 1, 2025 (Labor Day - Early Close)<br><sub>{len(df):,} ticks | Duration: {hours:.1f} hours</sub>',
        x=0.5,
        xanchor='center',
        font=dict(size=18, color='black')
    ),
    width=1600,
    height=800,
    xaxis=dict(
        title='Time',
        showgrid=True,
        gridcolor='rgba(128,128,128,0.2)',
        linecolor='black',
        linewidth=1
    ),
    yaxis=dict(
        title='Price (NQ)',
        showgrid=True,
        gridcolor='rgba(128,128,128,0.2)',
        linecolor='black',
        linewidth=1
    ),
    plot_bgcolor='white',
    paper_bgcolor='white',
    hovermode='x unified',
    dragmode='pan',
    annotations=[
        dict(
            x=0.5,
            y=0.98,
            xref='paper',
            yref='paper',
            text='<b>⚠️ LABOR DAY - EARLY MARKET CLOSE</b>',
            showarrow=False,
            font=dict(size=12, color='red'),
            xanchor='center'
        )
    ]
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
