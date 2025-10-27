"""
Plot Fractals - Visualize ZigZag fractal points
Creates an interactive line chart showing price movements and fractal pivot points
"""

import os
import webbrowser
import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from pathlib import Path
import glob

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
CHARTS_DIR = PROJECT_ROOT / "charts"
# Input CSV file (set to None to use the most recent file automatically)
INPUT_CSV_FILE = None  # Example: "zig_zag_fractals_20251027_220857.csv"

CHART_WIDTH = 1400
CHART_HEIGHT = 800

def plot_fractals_chart(df_fractals_minor: pd.DataFrame, df_fractals_major: pd.DataFrame, output_path: Path):
    """
    Create interactive line chart with multi-level fractal points

    Args:
        df_fractals_minor: DataFrame with minor fractal data
        df_fractals_major: DataFrame with major fractal data
        output_path: Path to save HTML chart
    """
    print(f"\n[INFO] Creating multi-level fractal visualization chart...")

    # Parse timestamps for both levels
    df_fractals_minor['timestamp'] = pd.to_datetime(df_fractals_minor['timestamp'])
    df_fractals_minor = df_fractals_minor.sort_values('timestamp')

    df_fractals_major['timestamp'] = pd.to_datetime(df_fractals_major['timestamp'])
    df_fractals_major = df_fractals_major.sort_values('timestamp')

    # Separate picos and valles for MAJOR only (MINOR has no markers)
    df_picos_major = df_fractals_major[df_fractals_major['type'] == 'PICO'].copy()
    df_valles_major = df_fractals_major[df_fractals_major['type'] == 'VALLE'].copy()

    # Create figure
    fig = go.Figure()

    # MAJOR structure - black line (width=2)
    fig.add_trace(go.Scatter(
        x=df_fractals_major['timestamp'],
        y=df_fractals_major['price'],
        mode='lines',
        name='ZigZag Major',
        line=dict(color='black', width=2),
        hovertemplate='<b>%{x}</b><br>Price: %{y:.2f}<extra></extra>'
    ))

    # MINOR structure - dark grey line (width=1) - ONLY LINES, NO MARKERS
    fig.add_trace(go.Scatter(
        x=df_fractals_minor['timestamp'],
        y=df_fractals_minor['price'],
        mode='lines',
        name='ZigZag Minor',
        line=dict(color='darkgrey', width=1),
        hovertemplate='<b>%{x}</b><br>Price: %{y:.2f}<extra></extra>'
    ))

    # MAJOR Picos (peaks) - EMPTY circles with green outline (no fill)
    fig.add_trace(go.Scatter(
        x=df_picos_major['timestamp'],
        y=df_picos_major['price'],
        mode='markers',
        name='PICO Major (High)',
        marker=dict(
            color='rgba(0,0,0,0)',  # Transparent (no fill)
            size=8,
            symbol='circle',
            line=dict(color='green', width=3)
        ),
        hovertemplate='<b>PICO Major</b><br>Time: %{x}<br>Price: %{y:.2f}<br>' +
                     'Tick Index: %{customdata[0]}<br>' +
                     'Preview Tick: %{customdata[1]}<extra></extra>',
        customdata=df_picos_major[['fractal_tick_index', 'preview_tick_index']].values
    ))

    # MAJOR Valles (valleys) - EMPTY circles with red outline (no fill)
    fig.add_trace(go.Scatter(
        x=df_valles_major['timestamp'],
        y=df_valles_major['price'],
        mode='markers',
        name='VALLE Major (Low)',
        marker=dict(
            color='rgba(0,0,0,0)',  # Transparent (no fill)
            size=8,
            symbol='circle',
            line=dict(color='red', width=3)
        ),
        hovertemplate='<b>VALLE Major</b><br>Time: %{x}<br>Price: %{y:.2f}<br>' +
                     'Tick Index: %{customdata[0]}<br>' +
                     'Preview Tick: %{customdata[1]}<extra></extra>',
        customdata=df_valles_major[['fractal_tick_index', 'preview_tick_index']].values
    ))

    # Update layout
    fig.update_layout(
        dragmode='pan',
        title=dict(
            text='ZigZag Fractal Analysis - Price Pivot Points',
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
            "filename": "fractal_chart",
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
    print("FRACTAL VISUALIZATION - Multi-Level ZigZag Price Pivot Points")
    print("="*70)

    # Find the most recent minor and major fractal CSV files
    pattern_minor = str(OUTPUTS_DIR / "zig_zag_fractals_minor_*.csv")
    pattern_major = str(OUTPUTS_DIR / "zig_zag_fractals_major_*.csv")

    minor_files = glob.glob(pattern_minor)
    major_files = glob.glob(pattern_major)

    if not minor_files or not major_files:
        print(f"\n[ERROR] Missing fractal files in {OUTPUTS_DIR}")
        print(f"[INFO] Minor files found: {len(minor_files)}")
        print(f"[INFO] Major files found: {len(major_files)}")
        print(f"[INFO] Run 'python strat_fractal/find_fractals.py' first to generate fractal data")
        return

    # Get most recent files
    csv_file_minor = Path(max(minor_files, key=os.path.getctime))
    csv_file_major = Path(max(major_files, key=os.path.getctime))

    print(f"\n[INFO] Loading MINOR fractals from: {csv_file_minor.name}")
    print(f"[INFO] Loading MAJOR fractals from: {csv_file_major.name}")

    # Load fractal data (European format with semicolon)
    df_fractals_minor = pd.read_csv(str(csv_file_minor), sep=';', decimal=',')
    df_fractals_major = pd.read_csv(str(csv_file_major), sep=';', decimal=',')

    print(f"[OK] Loaded {len(df_fractals_minor)} MINOR fractal points")
    print(f"    Picos: {len(df_fractals_minor[df_fractals_minor['type'] == 'PICO'])}")
    print(f"    Valles: {len(df_fractals_minor[df_fractals_minor['type'] == 'VALLE'])}")

    print(f"[OK] Loaded {len(df_fractals_major)} MAJOR fractal points")
    print(f"    Picos: {len(df_fractals_major[df_fractals_major['type'] == 'PICO'])}")
    print(f"    Valles: {len(df_fractals_major[df_fractals_major['type'] == 'VALLE'])}")

    # Create output filename using minor file timestamp
    timestamp = Path(csv_file_minor).stem.replace('zig_zag_fractals_minor_', '')
    output_file = CHARTS_DIR / f"fractal_zig_zag_levels_chart_{timestamp}.html"

    # Ensure charts directory exists
    CHARTS_DIR.mkdir(exist_ok=True)

    # Create multi-level chart
    plot_fractals_chart(df_fractals_minor, df_fractals_major, output_file)

    # Display summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Input MINOR: {csv_file_minor.name}")
    print(f"Input MAJOR: {csv_file_major.name}")
    print(f"Total MINOR fractals: {len(df_fractals_minor)}")
    print(f"Total MAJOR fractals: {len(df_fractals_major)}")
    print(f"Output chart: {output_file}")
    print("="*70)


if __name__ == "__main__":
    main()
