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
# CONFIGURATION - ARCHIVOS DE INPUT
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
CHARTS_DIR = PROJECT_ROOT / "charts"

# Archivo específico de señales Market Profile (mes de septiembre)
# Format: db_shapes_dom_YYYYMMDD.csv (date from the data itself)
SIGNALS_FILE = "db_shapes_dom_20250915.csv"

# =============================================================================
# CONFIGURATION - PARÁMETROS DE VISUALIZACIÓN
# =============================================================================

CHART_WIDTH = 1400
CHART_HEIGHT = 800

def plot_fractals_chart(df_fractals_minor: pd.DataFrame, df_fractals_major: pd.DataFrame, df_signals: pd.DataFrame, output_path: Path):
    """
    Create interactive line chart with multi-level fractal points and Market Profile signals

    Args:
        df_fractals_minor: DataFrame with minor fractal data
        df_fractals_major: DataFrame with major fractal data
        df_signals: DataFrame with d-shape/p-shape signals
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

    # Parse signals if available
    df_d_shape = pd.DataFrame()
    df_p_shape = pd.DataFrame()
    if df_signals is not None and not df_signals.empty:
        df_signals['timestamp'] = pd.to_datetime(df_signals['timestamp'])
        df_d_shape = df_signals[df_signals['shape'] == 'd_shape'].copy()
        df_p_shape = df_signals[df_signals['shape'] == 'p_shape'].copy()
        print(f"[INFO] Loaded {len(df_d_shape)} d_shape signals and {len(df_p_shape)} p_shape signals")

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

    # Add Market Profile signals if available
    # D-Shape signals (red triangles pointing down) - TAMAÑO AUMENTADO
    if not df_d_shape.empty:
        fig.add_trace(go.Scatter(
            x=df_d_shape['timestamp'],
            y=df_d_shape['close_price'],
            mode='markers',
            name='d_shape (ASK absorption)',
            marker=dict(
                color='red',
                size=14,  # Aumentado de 10 a 14
                symbol='triangle-down',
                line=dict(color='white', width=2)  # Borde más grueso
            ),
            hovertemplate='<b>d_shape</b><br>Time: %{x}<br>Price: %{y:.2f}<extra></extra>'
        ))

    # P-Shape signals (green triangles pointing up) - TAMAÑO AUMENTADO
    if not df_p_shape.empty:
        fig.add_trace(go.Scatter(
            x=df_p_shape['timestamp'],
            y=df_p_shape['close_price'],
            mode='markers',
            name='p_shape (BID absorption)',
            marker=dict(
                color='forestgreen',
                size=14,  # Aumentado de 10 a 14
                symbol='triangle-up',
                line=dict(color='white', width=2)  # Borde más grueso
            ),
            hovertemplate='<b>p_shape</b><br>Time: %{x}<br>Price: %{y:.2f}<extra></extra>'
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
    print("FRACTAL VISUALIZATION - Multi-Level ZigZag + Market Profile Signals")
    print("="*70)

    # Find the most recent minor and major fractal CSV files
    pattern_minor = str(OUTPUTS_DIR / "zig_zag_fractals_minor_*.csv")
    pattern_major = str(OUTPUTS_DIR / "zig_zag_fractals_major_*.csv")
    pattern_signals = str(OUTPUTS_DIR / "db_shapes_*.csv")

    minor_files = glob.glob(pattern_minor)
    major_files = glob.glob(pattern_major)
    signals_files = glob.glob(pattern_signals)

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

    # Load Market Profile signals - USAR ARCHIVO ESPECÍFICO
    df_signals = None
    csv_file_signals = OUTPUTS_DIR / SIGNALS_FILE

    if csv_file_signals.exists():
        print(f"\n[INFO] Loading Market Profile signals from: {csv_file_signals.name}")

        # Try European format first, then standard format
        try:
            df_signals = pd.read_csv(str(csv_file_signals), sep=';', decimal=',')
        except:
            try:
                df_signals = pd.read_csv(str(csv_file_signals))
            except Exception as e:
                print(f"[WARNING] Could not load signals file: {e}")
                df_signals = None

        if df_signals is not None:
            print(f"[OK] Loaded {len(df_signals)} Market Profile signals")
            if 'shape' in df_signals.columns:
                d_count = len(df_signals[df_signals['shape'] == 'd_shape'])
                p_count = len(df_signals[df_signals['shape'] == 'p_shape'])
                print(f"    d_shape: {d_count}")
                print(f"    p_shape: {p_count}")
    else:
        print(f"\n[ERROR] Signals file not found: {SIGNALS_FILE}")
        print(f"[INFO] Expected path: {csv_file_signals}")

    # Create output filename using minor file timestamp
    timestamp = Path(csv_file_minor).stem.replace('zig_zag_fractals_minor_', '')
    output_file = CHARTS_DIR / f"fractal_zig_zag_levels_chart_{timestamp}.html"

    # Ensure charts directory exists
    CHARTS_DIR.mkdir(exist_ok=True)

    # Create multi-level chart
    plot_fractals_chart(df_fractals_minor, df_fractals_major, df_signals, output_file)

    # Display summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Input MINOR: {csv_file_minor.name}")
    print(f"Input MAJOR: {csv_file_major.name}")
    if df_signals is not None:
        print(f"Input SIGNALS: {csv_file_signals.name}")
    print(f"Total MINOR fractals: {len(df_fractals_minor)}")
    print(f"Total MAJOR fractals: {len(df_fractals_major)}")
    if df_signals is not None:
        print(f"Total Market Profile signals: {len(df_signals)}")
    print(f"Output chart: {output_file}")
    print("="*70)


if __name__ == "__main__":
    main()
