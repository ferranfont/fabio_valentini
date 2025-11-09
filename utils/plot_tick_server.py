"""
Tick Server CSV Plotter
Visualizes tick data from tick_server.py with detection markers
"""

import pandas as pd
import plotly.graph_objs as go
from pathlib import Path
import webbrowser
import os
from datetime import datetime

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "monitor_ninja"

# Find most recent tick_server CSV
csv_files = list(DATA_DIR.glob("tick_server_*.csv"))
if not csv_files:
    print("[ERROR] No tick_server CSV files found in data/monitor_ninja/")
    exit(1)

DATA_FILE = max(csv_files, key=lambda p: p.stat().st_mtime)
OUTPUT_FILE = PROJECT_ROOT / "charts" / f"tick_server_chart_{DATA_FILE.stem.split('_')[-1]}.html"

print("="*80)
print("TICK SERVER CSV PLOTTER")
print("="*80)

# Load data
print(f"\n[INFO] Loading data from: {DATA_FILE.name}")
df = pd.read_csv(DATA_FILE, sep=';')

# Parse timestamp from date + time columns
# Format: date=20251107, time=211647.382 (HHMMSS.fff)
def parse_timestamp(row):
    try:
        date_str = str(row['date'])
        time_str = str(row['time'])

        # Parse date: YYYYMMDD
        year = int(date_str[:4])
        month = int(date_str[4:6])
        day = int(date_str[6:8])

        # Parse time: HHMMSS.fff (always 6 digits before decimal)
        time_parts = time_str.split('.')
        time_base = time_parts[0].zfill(6)  # Pad with zeros if needed
        milliseconds = int(time_parts[1]) if len(time_parts) > 1 else 0

        hour = int(time_base[0:2])
        minute = int(time_base[2:4])
        second = int(time_base[4:6])

        # Validate ranges
        if not (0 <= hour <= 23):
            print(f"[WARNING] Invalid hour {hour} in row, setting to 0. Date: {date_str}, Time: {time_str}")
            hour = 0
        if not (0 <= minute <= 59):
            print(f"[WARNING] Invalid minute {minute} in row, setting to 0")
            minute = 0
        if not (0 <= second <= 59):
            print(f"[WARNING] Invalid second {second} in row, setting to 0")
            second = 0

        return datetime(year, month, day, hour, minute, second, milliseconds * 1000)
    except Exception as e:
        print(f"[ERROR] Failed to parse timestamp: date={row.get('date', 'N/A')}, time={row.get('time', 'N/A')}, error={e}")
        # Return a default datetime
        return datetime(2025, 1, 1, 0, 0, 0)

df['timestamp'] = df.apply(parse_timestamp, axis=1)

# Clean and convert price to float
df['price'] = df['price'].astype(str).str.replace(',', '.').astype(float)
df = df.sort_values('timestamp')

print(f"[OK] Loaded {len(df):,} ticks")
print(f"[INFO] Time range: {df['timestamp'].min()} to {df['timestamp'].max()}")
print(f"[INFO] Price range: {df['price'].min():.2f} to {df['price'].max():.2f}")

# Check for detections
detections = df[df['shape'].notna() & (df['shape'] != '')]
if len(detections) > 0:
    print(f"[INFO] Found {len(detections)} pattern detections:")
    for shape in detections['shape'].unique():
        count = len(detections[detections['shape'] == shape])
        print(f"  - {shape}: {count}")

    # Print detection rows as DataFrame
    print(f"\n{'='*80}")
    print("DETECTION DETAILS:")
    print(f"{'='*80}")
    detection_display = detections[['timestamp', 'price', 'volume', 'side', 'shape']].copy()
    print(detection_display.to_string(index=False))
    print(f"{'='*80}\n")

# Create figure
fig = go.Figure()

# Add price line (no hover)
fig.add_trace(go.Scatter(
    x=df['timestamp'],
    y=df['price'],
    mode='lines',
    name='Price',
    line=dict(color='blue', width=1),
    hoverinfo='skip'
))

# Add vertical lines at detection points (before markers so they're behind)
# Red lines for d_shape, green lines for p_shape
if len(detections) > 0:
    for _, det in detections.iterrows():
        # Choose color based on shape
        line_color = 'rgba(255,0,0,0.3)' if det['shape'] == 'd_shape' else 'rgba(0,128,0,0.3)'
        fig.add_vline(
            x=det['timestamp'],
            line=dict(color=line_color, width=1, dash='solid'),
            layer='below'
        )

# Add detection markers
if len(detections) > 0:
    # d_shape markers (red dots)
    d_shapes = detections[detections['shape'] == 'd_shape']
    if len(d_shapes) > 0:
        fig.add_trace(go.Scatter(
            x=d_shapes['timestamp'],
            y=d_shapes['price'],
            mode='markers',
            name='d_shape',
            showlegend=False,
            marker=dict(
                symbol='circle',
                size=12,
                color='red',
                line=dict(color='darkred', width=2)
            ),
            customdata=list(zip(d_shapes['volume'], d_shapes['side'])),
            hoverinfo='none'
        ))

    # p_shape markers (green dots)
    p_shapes = detections[detections['shape'] == 'p_shape']
    if len(p_shapes) > 0:
        fig.add_trace(go.Scatter(
            x=p_shapes['timestamp'],
            y=p_shapes['price'],
            mode='markers',
            name='p_shape',
            showlegend=False,
            marker=dict(
                symbol='circle',
                size=12,
                color='green',
                line=dict(color='darkgreen', width=2)
            ),
            customdata=list(zip(p_shapes['volume'], p_shapes['side'])),
            hoverinfo='none'
        ))

# Extract date from filename for title
file_date = DATA_FILE.stem.split('_')[-1]  # e.g., "20251107_211647"
title_date = file_date[:8]  # YYYYMMDD
title_time = file_date[9:] if len(file_date) > 8 else ""

# Update layout
fig.update_layout(
    title=dict(
        text=f'NQ Tick Server Data - {title_date} {title_time}<br><sub>{len(df):,} ticks | {len(detections)} detections</sub>',
        x=0.5,
        xanchor='center',
        font=dict(size=18, color='black')
    ),
    width=1600,
    height=800,
    xaxis=dict(
        title='Time',
        showgrid=False,  # No vertical grid
        linecolor='black',
        linewidth=1,
        showspikes=True,
        spikemode='across',
        spikesnap='cursor',
        spikecolor='rgba(128,128,128,0.3)',
        spikethickness=1,
        spikedash='dot'
    ),
    yaxis=dict(
        title='Price (NQ)',
        showgrid=True,  # Keep horizontal grid
        gridcolor='rgba(128,128,128,0.2)',
        linecolor='black',
        linewidth=1
    ),
    plot_bgcolor='white',
    paper_bgcolor='white',
    hovermode='closest',
    dragmode='pan',
    showlegend=False
)

# Save chart with custom JavaScript for fixed tooltip
OUTPUT_FILE.parent.mkdir(exist_ok=True)

# Custom JavaScript to create fixed tooltip
custom_js = """
<style>
#fixed-tooltip {
    position: fixed;
    left: 120px;
    top: 150px;
    background: white;
    border: 2px solid black;
    padding: 10px;
    font-family: monospace;
    font-size: 12px;
    display: none;
    z-index: 9999;
    min-width: 180px;
    box-shadow: 2px 2px 5px rgba(0,0,0,0.3);
}
</style>
<div id="fixed-tooltip"></div>
<script>
(function() {
    // Wait for Plotly to be ready
    var checkPlotly = setInterval(function() {
        var plotDiv = document.querySelector('.js-plotly-plot');
        var tooltip = document.getElementById('fixed-tooltip');

        if (plotDiv && tooltip && typeof Plotly !== 'undefined') {
            clearInterval(checkPlotly);

            // Bind hover events
            plotDiv.on('plotly_hover', function(data) {
                if (data.points && data.points.length > 0) {
                    var point = data.points[0];

                    // Only show tooltip for detection markers
                    if (point.data.name === 'd_shape' || point.data.name === 'p_shape') {
                        var shape = point.data.name;
                        var time = point.x;
                        var price = point.y.toFixed(2);
                        var volume = point.customdata[0];
                        var side = point.customdata[1];

                        tooltip.innerHTML = '<b>' + shape + '</b><br>' + time + '<br>Price: ' + price + '<br>' + volume + ' ' + side;
                        tooltip.style.display = 'block';
                    }
                }
            });

            plotDiv.on('plotly_unhover', function(data) {
                tooltip.style.display = 'none';
            });
        }
    }, 100);
})();
</script>
"""

# Write HTML with custom tooltip
html_string = fig.to_html(
    include_plotlyjs='cdn',
    config={
        "scrollZoom": True,
        "displayModeBar": True,
        "modeBarButtonsToRemove": ['lasso2d', 'select2d']
    }
)

# Insert custom JavaScript and CSS after body tag opens
html_with_tooltip = html_string.replace('<body>', '<body>' + custom_js)

with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    f.write(html_with_tooltip)

print(f"\n[OK] Chart saved: {OUTPUT_FILE}")

# Open in browser
webbrowser.open('file://' + os.path.realpath(str(OUTPUT_FILE)))
print(f"[OK] Chart opened in browser")

print("\n" + "="*80)
print("COMPLETED")
print("="*80)
