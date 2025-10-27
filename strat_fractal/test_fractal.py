"""
Test Fractal - Plot raw tick data from ts_and_dom_24_oct.csv

Visualizes tick-by-tick price data without aggregation using a simple line chart.
"""

import sys
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import webbrowser
import os

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# =============================================================================
# CONFIGURATION
# =============================================================================

INPUT_FILE = "ts_and_dom_24_oct.csv"

# Chart dimensions
CHART_WIDTH = 1400
CHART_HEIGHT = 800

# Directories
DATA_DIR = PROJECT_ROOT / "data"
CHARTS_DIR = PROJECT_ROOT / "charts"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

# =============================================================================
# MAIN FUNCTIONS
# =============================================================================

def load_tick_data(csv_path: Path) -> pd.DataFrame:
    """
    Load tick data from CSV file
    """
    print(f"[INFO] Loading tick data from: {csv_path.name}")

    # Read only first 2 columns to avoid issues with JSON columns
    # The file has: Timestamp,Price,Size,Side,DOM_BID,DOM_ASK
    # DOM columns contain JSON which breaks CSV parsing
    df = pd.read_csv(
        csv_path,
        sep=',',
        usecols=[0, 1],  # Only Timestamp and Price
        names=['Timestamp', 'Precio'],
        header=0
    )

    print(f"[INFO] Columns loaded: {list(df.columns)}")

    # Convert timestamp to datetime
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])

    # Sort by timestamp
    df = df.sort_values('Timestamp').reset_index(drop=True)

    print(f"[OK] Loaded {len(df):,} ticks")
    print(f"[INFO] Date range: {df['Timestamp'].min()} to {df['Timestamp'].max()}")
    print(f"[INFO] Price range: {df['Precio'].min():.2f} to {df['Precio'].max():.2f}")

    return df


def load_major_fractals() -> pd.DataFrame:
    """
    Load the most recent MAJOR fractals CSV file
    """
    import glob

    pattern = str(OUTPUTS_DIR / "zig_zag_fractals_major_*.csv")
    fractal_files = glob.glob(pattern)

    if not fractal_files:
        print(f"[WARNING] No MAJOR fractal files found in {OUTPUTS_DIR}")
        return None

    # Get most recent file
    latest_file = max(fractal_files, key=os.path.getctime)
    print(f"[INFO] Loading MAJOR fractals from: {Path(latest_file).name}")

    # Load with European format
    df = pd.read_csv(latest_file, sep=';', decimal=',')

    print(f"[OK] Loaded {len(df)} MAJOR fractals")

    return df


def plot_tick_data(df: pd.DataFrame, df_fractals_major: pd.DataFrame, output_path: Path):
    """
    Create line chart with tick-by-tick price data and fractal vertical lines
    """
    print(f"\n[INFO] Creating tick data visualization...")

    # Create figure
    fig = go.Figure()

    # Add price line (dark grey, thin)
    fig.add_trace(go.Scatter(
        x=df['Timestamp'],
        y=df['Precio'],
        mode='lines',
        name='Price',
        line=dict(color='darkgrey', width=1),
        hovertemplate='<b>%{x}</b><br>Price: %{y:.2f}<extra></extra>'
    ))

    # Add vertical lines at each MAJOR fractal tick index
    if df_fractals_major is not None and not df_fractals_major.empty:
        print(f"[INFO] Adding {len(df_fractals_major)} vertical lines for MAJOR fractals...")

        for idx, row in df_fractals_major.iterrows():
            fractal_tick_idx = row['fractal_tick_index']

            # Skip if fractal_tick_index is N/A or invalid
            if pd.isna(fractal_tick_idx) or fractal_tick_idx == 'N/A':
                continue

            fractal_tick_idx = int(fractal_tick_idx)

            # Get the timestamp at this tick index
            if fractal_tick_idx < len(df):
                timestamp = df.iloc[fractal_tick_idx]['Timestamp']

                # Add vertical line
                fig.add_vline(
                    x=timestamp,
                    line=dict(color='blue', width=1, dash='solid'),
                    opacity=0.5
                )

    # Update layout
    fig.update_layout(
        dragmode='pan',
        title=dict(
            text='Tick-by-Tick Price Data - ts_and_dom_24_oct.csv',
            x=0.5,
            xanchor='center',
            font=dict(size=20, color='black')
        ),
        width=CHART_WIDTH,
        height=CHART_HEIGHT,
        margin=dict(l=60, r=40, t=80, b=60),
        font=dict(size=12, color="black"),
        plot_bgcolor='white',
        paper_bgcolor='white',
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        template='plotly_white',
        xaxis=dict(
            title='Time',
            type='date',
            tickformat="%Y-%m-%d %H:%M",
            tickangle=45,
            showgrid=False,
            linecolor='black',
            linewidth=1,
            rangeslider=dict(visible=False)
        ),
        yaxis=dict(
            title='Price (NQ)',
            showgrid=True,
            gridcolor='rgba(128,128,128,0.2)',
            gridwidth=1,
            linecolor='black',
            linewidth=1
        ),
        hovermode='closest'
    )

    # Save HTML
    fig.write_html(output_path, config={
        "scrollZoom": True,
        "displayModeBar": True,
        "staticPlot": False,
        "toImageButtonOptions": {
            "format": "png",
            "filename": "tick_data_chart",
            "height": CHART_HEIGHT,
            "width": CHART_WIDTH,
            "scale": 2
        }
    })

    print(f"[OK] Chart saved to: {output_path}")

    # Open in browser
    webbrowser.open('file://' + os.path.realpath(str(output_path)))
    print(f"[OK] Chart opened in browser")


def main():
    """
    Main execution function
    """
    print("="*70)
    print("TICK DATA VISUALIZATION - Raw Price Data with MAJOR Fractals")
    print("="*70)

    # Load tick data
    csv_path = DATA_DIR / INPUT_FILE
    if not csv_path.exists():
        print(f"\n[ERROR] File not found: {csv_path}")
        return

    df = load_tick_data(csv_path)

    # Load MAJOR fractals
    df_fractals_major = load_major_fractals()

    # Create output filename
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = CHARTS_DIR / f"tick_data_chart_{timestamp}.html"

    # Ensure charts directory exists
    CHARTS_DIR.mkdir(exist_ok=True)

    # Create chart
    plot_tick_data(df, df_fractals_major, output_file)

    # Display summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Input file: {INPUT_FILE}")
    print(f"Total ticks: {len(df):,}")
    if df_fractals_major is not None:
        print(f"MAJOR fractals: {len(df_fractals_major)}")
    print(f"Output chart: {output_file}")
    print("="*70)


if __name__ == "__main__":
    main()
