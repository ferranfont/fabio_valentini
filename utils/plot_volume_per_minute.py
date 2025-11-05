#!/usr/bin/env python3
"""
Volume per Minute Chart - Historic Data Analysis

Reads all CSV files from data/historic/ and plots volume per minute over time.
Each file is represented as a separate line with different color.
"""

import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

# Directories
DATA_HISTORIC_DIR = PROJECT_ROOT / "data" / "historic"
CHARTS_DIR = PROJECT_ROOT / "charts"
CHARTS_DIR.mkdir(exist_ok=True)

def read_historic_csv(file_path):
    """
    Read historic CSV file with European format.

    Args:
        file_path: Path to CSV file

    Returns:
        DataFrame with parsed data
    """
    try:
        df = pd.read_csv(
            file_path,
            sep=';',
            decimal=','
        )
        # Parse timestamp manually to avoid warnings
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
        return df
    except Exception as e:
        print(f"[ERROR] Failed to read {file_path.name}: {e}")
        return None

def calculate_volume_per_minute(df):
    """
    Calculate volume per minute from tick data.

    Args:
        df: DataFrame with Timestamp and Volumen columns

    Returns:
        DataFrame with time of day and total volume
    """
    # Create minute-level timestamp
    df['Minute'] = df['Timestamp'].dt.floor('min')  # Floor to minute

    # Extract time of day (hour:minute)
    df['TimeOfDay'] = df['Minute'].dt.time

    # Group by time of day and sum volume
    volume_per_minute = df.groupby('TimeOfDay')['Volumen'].sum().reset_index()
    volume_per_minute.columns = ['TimeOfDay', 'Volume']

    return volume_per_minute

def plot_volume_per_minute(data_dict):
    """
    Create interactive Plotly chart with volume per minute for all files.

    Args:
        data_dict: Dictionary {filename: volume_df}
    """
    fig = go.Figure()

    # Color palette
    colors = [
        '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
        '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
        '#aec7e8', '#ffbb78'
    ]

    # Add trace for each file
    for idx, (filename, df) in enumerate(data_dict.items()):
        color = colors[idx % len(colors)]

        # Extract date from filename (e.g., time_and_sales_nq_20250915.csv -> 2025-09-15)
        date_str = filename.split('_')[-1].replace('.csv', '')
        label = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

        # Convert time to datetime for proper plotting
        df['PlotTime'] = pd.to_datetime(df['TimeOfDay'].astype(str), format='%H:%M:%S')

        fig.add_trace(go.Scatter(
            x=df['PlotTime'],
            y=df['Volume'],
            mode='lines',
            name=label,
            line=dict(color=color, width=2),
            hovertemplate='<b>%{fullData.name}</b><br>' +
                          'Time: %{x|%H:%M}<br>' +
                          'Volume: %{y:,.0f}<br>' +
                          '<extra></extra>'
        ))

    # Update layout
    fig.update_layout(
        title={
            'text': 'Volume per Minute - Intraday Pattern Comparison',
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 20, 'color': '#2c3e50'}
        },
        xaxis={
            'title': 'Time of Day',
            'gridcolor': '#e0e0e0',
            'showgrid': True,
            'tickformat': '%H:%M',
            'type': 'date'
        },
        yaxis={
            'title': 'Volume (Contracts)',
            'gridcolor': '#e0e0e0',
            'showgrid': True
        },
        hovermode='x unified',
        plot_bgcolor='white',
        paper_bgcolor='white',
        width=1600,
        height=800,
        legend={
            'title': 'Date',
            'orientation': 'v',
            'yanchor': 'top',
            'y': 1,
            'xanchor': 'left',
            'x': 1.01
        },
        margin=dict(l=80, r=200, t=80, b=80)
    )

    # Save chart
    output_path = CHARTS_DIR / "volume_per_minute_historic.html"
    fig.write_html(str(output_path))
    print(f"[OK] Chart saved to: {output_path}")

    # Open in browser
    import webbrowser
    webbrowser.open(f"file://{output_path}")
    print("[OK] Chart opened in browser")

def main():
    """Main execution function"""
    print("=" * 60)
    print("VOLUME PER MINUTE - HISTORIC DATA ANALYSIS")
    print("=" * 60)

    # Check if historic directory exists
    if not DATA_HISTORIC_DIR.exists():
        print(f"[ERROR] Directory not found: {DATA_HISTORIC_DIR}")
        return

    # Get all CSV files
    csv_files = sorted(DATA_HISTORIC_DIR.glob("*.csv"))

    if not csv_files:
        print(f"[ERROR] No CSV files found in {DATA_HISTORIC_DIR}")
        return

    print(f"\n[INFO] Found {len(csv_files)} CSV files")

    # Process each file
    data_dict = {}

    for csv_file in csv_files:
        print(f"\n[PROCESSING] {csv_file.name}")

        # Read CSV
        df = read_historic_csv(csv_file)
        if df is None:
            continue

        print(f"  - Records: {len(df):,}")
        print(f"  - Date: {df['Timestamp'].dt.date.iloc[0]}")

        # Calculate volume per minute
        volume_df = calculate_volume_per_minute(df)
        print(f"  - Time periods: {len(volume_df)}")
        print(f"  - Total volume: {volume_df['Volume'].sum():,.0f}")
        print(f"  - Avg volume/min: {volume_df['Volume'].mean():.0f}")

        data_dict[csv_file.name] = volume_df

    # Create chart
    if data_dict:
        print(f"\n[INFO] Creating chart with {len(data_dict)} files...")
        plot_volume_per_minute(data_dict)
    else:
        print("[ERROR] No data to plot")

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)

if __name__ == "__main__":
    main()
