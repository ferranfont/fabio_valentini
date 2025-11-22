"""
Plot Trinchera Data with Trade Markers
Shows close price with trade entry/exit markers:
- Triangle down (red) = SHORT entry
- Triangle up (green) = LONG entry
- Square open (red) = STOP exit
- Square open (green) = PROFIT exit
- Light grey alpha lines connecting entry to exit
"""

import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from pathlib import Path
import webbrowser
from datetime import datetime
from config_trinchera import (
    BIG_VOLUME_TRIGGER, FILTER_BY_SMA, MEAN_REVERS_EXPAND, FILTER_USE_GRID,
    GRID_MEAN_REVERS_EXPAND, TP_POINTS, SL_POINTS, SMA_TRAILING_STOP,
    TRAILING_STOP_ATR_MULT, FILTER_TIME_OF_DAY, GRID_TP_POINTS, GRID_SL_POINTS,
    SMA_CASH_TRAILING_ENABLED, SMA_CASH_TRAILING, SMA_CASH_TRAILING_DISTANCE, DATE
)

# ============================================================================
# FILTER CONFIGURATION
# ============================================================================
FILTER_FROM_14H = True  # Set to True to show only data from 14:00:00 onwards
START_TIME = "14:50:00"  # Start time for filtering

# ============================================================================
# CONFIGURATION
# ============================================================================
CURRENT_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = CURRENT_DIR / "outputs"
CHARTS_DIR = CURRENT_DIR / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

# Use DATE from config
DATA_FILE = OUTPUTS_DIR / f"db_trinchera_all_data_{DATE}.csv"
TRADES_FILE = OUTPUTS_DIR / f"db_trinchera_TR_{DATE}.csv"
OUTPUT_FILE = CHARTS_DIR / f"chart_trinchera_trades_{DATE}.html"

print("="*80)
print("TRINCHERA TRADES PLOTTER")
print("="*80)

# Load data
print(f"\n[INFO] Loading data from: {DATA_FILE.name}")
df = pd.read_csv(DATA_FILE, sep=';', decimal=',', low_memory=False)
df.columns = df.columns.str.strip()
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.sort_values('timestamp')

print(f"[OK] Loaded {len(df):,} frames (total)")

# Apply time filter if enabled
if FILTER_FROM_14H:
    df = df[df['timestamp'].dt.time >= pd.to_datetime(START_TIME).time()].copy()
    print(f"[INFO] Filter applied: showing only from {START_TIME} onwards")
    print(f"[OK] Filtered to {len(df):,} frames")

print(f"[INFO] Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
print(f"[INFO] Price range: {df['close'].min():.2f} to {df['close'].max():.2f}")

# Load trades
df_trades = None
if TRADES_FILE.exists():
    print(f"\n[INFO] Loading trades from: {TRADES_FILE.name}")
    df_trades = pd.read_csv(TRADES_FILE, sep=';', decimal=',', low_memory=False)
    df_trades.columns = df_trades.columns.str.strip()
    df_trades['entry_time'] = pd.to_datetime(df_trades['entry_time'])
    df_trades['exit_time'] = pd.to_datetime(df_trades['exit_time'])

    print(f"[OK] Loaded {len(df_trades)} trades (total)")

    # Apply time filter to trades if enabled
    if FILTER_FROM_14H:
        df_trades = df_trades[df_trades['entry_time'].dt.time >= pd.to_datetime(START_TIME).time()].copy()
        print(f"[INFO] Filtered trades from {START_TIME} onwards: {len(df_trades)} trades")
else:
    print(f"\n[WARN] Trades file not found: {TRADES_FILE.name}")

# Load big volume events
bins_files = sorted(OUTPUTS_DIR.glob("db_trinchera_bins_*.csv"))
BINS_FILE = bins_files[-1] if bins_files else None
big_volume_events = []
df_bins = None
if BINS_FILE and BINS_FILE.exists():
    print(f"\n[INFO] Loading big volume events from: {BINS_FILE.name}")
    df_bins = pd.read_csv(BINS_FILE, sep=';', decimal=',', low_memory=False)
    df_bins.columns = df_bins.columns.str.strip()
    df_bins['timestamp'] = pd.to_datetime(df_bins['timestamp'])
    df_bins['start_timestamp'] = pd.to_datetime(df_bins['start_timestamp'])
    df_bins['end_timeout_bigvolume'] = pd.to_datetime(df_bins['end_timeout_bigvolume'])
    df_bins['end_timeout_mean_reversion'] = pd.to_datetime(df_bins['end_timeout_mean_reversion'])

    print(f"[OK] Loaded {len(df_bins)} big volume events (total)")

    # Apply time filter to big volume events if enabled
    if FILTER_FROM_14H:
        df_bins = df_bins[df_bins['timestamp'].dt.time >= pd.to_datetime(START_TIME).time()].copy()
        print(f"[INFO] Filtered big volume events from {START_TIME} onwards: {len(df_bins)} events")

    big_volume_events = df_bins['timestamp'].tolist()

# Create figure with secondary y-axis
fig = make_subplots(specs=[[{"secondary_y": True}]])

# Add close price line (blue) on primary y-axis (left)
fig.add_trace(go.Scatter(
    x=df['timestamp'],
    y=df['close'],
    mode='lines',
    name='Close Price',
    line=dict(color='blue', width=1),
    hovertemplate='<b>%{x}</b><br>Close: %{y:.2f}<extra></extra>',
    showlegend=False
), secondary_y=False)

# Add SMA line (green with alpha) on primary y-axis (left)
fig.add_trace(go.Scatter(
    x=df['timestamp'],
    y=df['sma'],
    mode='lines',
    name='SMA-200',
    line=dict(color='rgba(0,128,0,0.5)', width=1),
    hovertemplate='<b>%{x}</b><br>SMA: %{y:.2f}<extra></extra>',
    showlegend=True
), secondary_y=False)

# Add total volume line (orange) on secondary y-axis (right)
fig.add_trace(go.Scatter(
    x=df['timestamp'],
    y=df['total_volume'],
    mode='lines',
    name='Total Volume',
    line=dict(color='orange', width=1),
    hovertemplate='<b>%{x}</b><br>Volume: %{y:.0f}<extra></extra>',
    showlegend=False
), secondary_y=True)

# Add horizontal line for BIG_VOLUME_TRIGGER on secondary y-axis (right)
fig.add_trace(go.Scatter(
    x=[df['timestamp'].min(), df['timestamp'].max()],
    y=[BIG_VOLUME_TRIGGER, BIG_VOLUME_TRIGGER],
    mode='lines',
    name=f'Trigger ({BIG_VOLUME_TRIGGER})',
    line=dict(color='orange', width=1, dash='dot'),
    showlegend=False
), secondary_y=True)

# Add orange dots at big volume events on the close price line
if len(big_volume_events) > 0:
    df_big_volume = df[df['timestamp'].isin(big_volume_events)]

    fig.add_trace(go.Scatter(
        x=df_big_volume['timestamp'],
        y=df_big_volume['close'],
        mode='markers',
        name='Big Volume',
        marker=dict(
            color='orange',
            size=10,
            symbol='circle'
        ),
        showlegend=True
    ), secondary_y=False)

    print(f"[INFO] Added {len(df_big_volume)} orange dots for big volume events")

# Add shapes for big volume events
shapes = []
if len(big_volume_events) > 0 and df_bins is not None:
    # Add vertical lines at big volume events
    for timestamp in big_volume_events:
        shapes.append(
            dict(
                type='line',
                x0=timestamp,
                x1=timestamp,
                y0=0,
                y1=1,
                yref='paper',
                line=dict(color='rgba(211,211,211,0.6)', width=1),
                layer='below'
            )
        )

    # Add horizontal timeout lines as scatter traces (for legend control)
    for idx, row in df_bins.iterrows():
        start_ts = row['start_timestamp']
        end_ts_bigvolume = row['end_timeout_bigvolume']
        end_ts_mean_reversion = row['end_timeout_mean_reversion']
        close_price = row['close']
        mean_level_up = row['mean_level_up']
        mean_level_down = row['mean_level_down']
        event_sma = row['sma']
        event_timestamp = row['timestamp']

        # Orange line at close price (as scatter trace)
        # Use mean_reversion timeout to match red/green lines duration
        fig.add_trace(go.Scatter(
            x=[start_ts, end_ts_mean_reversion],
            y=[close_price, close_price],
            mode='lines',
            name='Big Volume Timeout',
            line=dict(color='rgba(255,165,0,0.3)', width=10),
            showlegend=(idx == 0),  # Only show in legend once
            legendgroup='big_volume_timeout',  # Group all timeout lines together
            hoverinfo='skip'
        ), secondary_y=False)

        # Determine which lines to show based on filter
        show_red = True
        show_green = True

        if FILTER_BY_SMA:
            # Check if orange dot is above or below SMA
            if close_price < event_sma:
                # Orange dot below SMA → Only SELL allowed → Show only RED line
                show_red = True
                show_green = False
            else:
                # Orange dot above SMA → Only BUY allowed → Show only GREEN line
                show_red = False
                show_green = True

        # Red line at mean_level_up (only if allowed and GRID is disabled)
        if show_red:
            # Only draw horizontal line if GRID is disabled
            if not FILTER_USE_GRID:
                shapes.append(
                    dict(
                        type='line',
                        x0=start_ts,
                        x1=end_ts_mean_reversion,
                        y0=mean_level_up,
                        y1=mean_level_up,
                        yref='y',
                        line=dict(color='rgba(255,0,0,0.7)', width=1),
                        layer='below'
                    )
                )

            # Add red filled rectangle for GRID zone (SELL zone)
            # From mean_level_up down to (close + MEAN_REVERS_EXPAND)
            if FILTER_USE_GRID:
                first_entry_level = close_price + MEAN_REVERS_EXPAND
                shapes.append(
                    dict(
                        type='rect',
                        x0=start_ts,
                        x1=end_ts_mean_reversion,
                        y0=mean_level_up,  # Current red line (MEAN_REVERS_EXPAND + GRID_MEAN_REVERS_EXPAND)
                        y1=first_entry_level,  # Down to MEAN_REVERS_EXPAND level
                        yref='y',
                        fillcolor='rgba(255,0,0,0.05)',
                        line=dict(width=0),
                        layer='below'
                    )
                )

        # Green line at mean_level_down (only if allowed and GRID is disabled)
        if show_green:
            # Only draw horizontal line if GRID is disabled
            if not FILTER_USE_GRID:
                shapes.append(
                    dict(
                        type='line',
                        x0=start_ts,
                        x1=end_ts_mean_reversion,
                        y0=mean_level_down,
                        y1=mean_level_down,
                        yref='y',
                        line=dict(color='rgba(34,139,34,0.7)', width=1),
                        layer='below'
                    )
                )

            # Add green filled rectangle for GRID zone (BUY zone)
            # From mean_level_down up to (close - MEAN_REVERS_EXPAND)
            if FILTER_USE_GRID:
                first_entry_level = close_price - MEAN_REVERS_EXPAND
                shapes.append(
                    dict(
                        type='rect',
                        x0=start_ts,
                        x1=end_ts_mean_reversion,
                        y0=mean_level_down,  # Current green line (MEAN_REVERS_EXPAND + GRID_MEAN_REVERS_EXPAND)
                        y1=first_entry_level,  # Up to MEAN_REVERS_EXPAND level
                        yref='y',
                        fillcolor='rgba(0,128,0,0.05)',
                        line=dict(width=0),
                        layer='below'
                    )
                )

# Add trade markers and connection lines
if df_trades is not None and len(df_trades) > 0:
    # Separate trades by direction and exit reason
    buy_trades = df_trades[df_trades['direction'] == 'BUY']
    sell_trades = df_trades[df_trades['direction'] == 'SELL']

    # BUY entries (triangle up, green) - First entry
    if len(buy_trades) > 0:
        fig.add_trace(go.Scatter(
            x=buy_trades['entry_time'],
            y=buy_trades['entry_price'],
            mode='markers',
            name='BUY Entry',
            marker=dict(
                color='green',
                size=12,
                symbol='triangle-up',
                line=dict(color='green', width=1)
            ),
            showlegend=False
        ), secondary_y=False)

        # BUY second entries (GRID)
        buy_grid = buy_trades[buy_trades['entry_time_2'].notna()]
        if len(buy_grid) > 0:
            fig.add_trace(go.Scatter(
                x=buy_grid['entry_time_2'],
                y=buy_grid['entry_price_2'],
                mode='markers',
                name='BUY Entry 2 (GRID)',
                marker=dict(
                    color='green',
                    size=12,
                    symbol='triangle-up',
                    line=dict(color='green', width=1)
                ),
                showlegend=False
            ), secondary_y=False)

    # SELL entries (triangle down, red) - First entry
    if len(sell_trades) > 0:
        fig.add_trace(go.Scatter(
            x=sell_trades['entry_time'],
            y=sell_trades['entry_price'],
            mode='markers',
            name='SELL Entry',
            marker=dict(
                color='red',
                size=12,
                symbol='triangle-down',
                line=dict(color='red', width=1)
            ),
            showlegend=False
        ), secondary_y=False)

        # SELL second entries (GRID)
        sell_grid = sell_trades[sell_trades['entry_time_2'].notna()]
        if len(sell_grid) > 0:
            fig.add_trace(go.Scatter(
                x=sell_grid['entry_time_2'],
                y=sell_grid['entry_price_2'],
                mode='markers',
                name='SELL Entry 2 (GRID)',
                marker=dict(
                    color='red',
                    size=12,
                    symbol='triangle-down',
                    line=dict(color='red', width=1)
                ),
                showlegend=False
            ), secondary_y=False)

    # Exit markers - color based on P&L, not exit reason
    # Green squares for profitable exits (pnl > 0), red squares for losing exits (pnl <= 0)
    winning_exits = df_trades[df_trades['pnl'] > 0]
    if len(winning_exits) > 0:
        fig.add_trace(go.Scatter(
            x=winning_exits['exit_time'],
            y=winning_exits['exit_price'],
            mode='markers',
            name='Winning Exit (Profit)',
            marker=dict(
                color='rgba(0,0,0,0)',  # Transparent fill
                size=10,
                symbol='square',
                line=dict(color='green', width=2)
            ),
            showlegend=False
        ), secondary_y=False)

    losing_exits = df_trades[df_trades['pnl'] <= 0]
    if len(losing_exits) > 0:
        fig.add_trace(go.Scatter(
            x=losing_exits['exit_time'],
            y=losing_exits['exit_price'],
            mode='markers',
            name='Losing Exit (Loss)',
            marker=dict(
                color='rgba(0,0,0,0)',  # Transparent fill
                size=10,
                symbol='square',
                line=dict(color='red', width=2)
            ),
            showlegend=False
        ), secondary_y=False)

    # Add connection lines from entries to exit
    for _, trade in df_trades.iterrows():
        # Always draw line from first entry to exit
        shapes.append(
            dict(
                type='line',
                x0=trade['entry_time'],
                x1=trade['exit_time'],
                y0=trade['entry_price'],
                y1=trade['exit_price'],
                yref='y',
                line=dict(color='rgba(211,211,211,0.8)', width=1, dash='dot'),
                layer='below'
            )
        )

        # If has second entry (GRID), draw second line
        if pd.notna(trade.get('entry_time_2')):
            shapes.append(
                dict(
                    type='line',
                    x0=trade['entry_time_2'],
                    x1=trade['exit_time'],
                    y0=trade['entry_price_2'],
                    y1=trade['exit_price'],
                    yref='y',
                    line=dict(color='rgba(211,211,211,0.8)', width=1, dash='dot'),
                    layer='below'
                )
            )

    # Add GRID zone traces (only if GRID is enabled)
    # These will be linked to legend so they can be toggled
    if FILTER_USE_GRID:
        # First, add the actual filled zones as scatter traces (they will be hidden in legend)
        # Then add invisible legend items that control them via legendgroup

        # Collect all SELL zone rectangles from shapes list
        sell_zones = []
        buy_zones = []

        for shape in shapes[:]:  # Iterate over copy
            if shape.get('type') == 'rect' and shape.get('fillcolor'):
                if 'rgba(255,0,0' in shape['fillcolor']:  # Red SELL zone
                    # Convert rectangle to scatter trace with fill
                    x_coords = [shape['x0'], shape['x1'], shape['x1'], shape['x0'], shape['x0']]
                    y_coords = [shape['y0'], shape['y0'], shape['y1'], shape['y1'], shape['y0']]
                    sell_zones.append((x_coords, y_coords))
                    shapes.remove(shape)  # Remove from shapes list
                elif 'rgba(0,128,0' in shape['fillcolor']:  # Green BUY zone
                    # Convert rectangle to scatter trace with fill
                    x_coords = [shape['x0'], shape['x1'], shape['x1'], shape['x0'], shape['x0']]
                    y_coords = [shape['y0'], shape['y0'], shape['y1'], shape['y1'], shape['y0']]
                    buy_zones.append((x_coords, y_coords))
                    shapes.remove(shape)  # Remove from shapes list

        # Add SELL Zone legend entry
        fig.add_trace(go.Scatter(
            x=[None],
            y=[None],
            mode='markers',
            name='SELL Zone (GRID)',
            marker=dict(
                color='rgba(255,0,0,0.05)',
                size=15,
                symbol='square',
                line=dict(color='red', width=1)
            ),
            legendgroup='sell_zone',
            showlegend=True
        ), secondary_y=False)

        # Add all SELL zone fills (linked to legend entry)
        for x_coords, y_coords in sell_zones:
            fig.add_trace(go.Scatter(
                x=x_coords,
                y=y_coords,
                fill='toself',
                fillcolor='rgba(255,0,0,0.05)',
                line=dict(width=0),
                mode='lines',
                legendgroup='sell_zone',
                showlegend=False,
                hoverinfo='skip'
            ), secondary_y=False)

        # Add BUY Zone legend entry
        fig.add_trace(go.Scatter(
            x=[None],
            y=[None],
            mode='markers',
            name='BUY Zone (GRID)',
            marker=dict(
                color='rgba(0,128,0,0.05)',
                size=15,
                symbol='square',
                line=dict(color='green', width=1)
            ),
            legendgroup='buy_zone',
            showlegend=True
        ), secondary_y=False)

        # Add all BUY zone fills (linked to legend entry)
        for x_coords, y_coords in buy_zones:
            fig.add_trace(go.Scatter(
                x=x_coords,
                y=y_coords,
                fill='toself',
                fillcolor='rgba(0,128,0,0.05)',
                line=dict(width=0),
                mode='lines',
                legendgroup='buy_zone',
                showlegend=False,
                hoverinfo='skip'
            ), secondary_y=False)

    # Count GRID entries
    buy_grid_count = len(buy_trades[buy_trades['entry_time_2'].notna()]) if 'entry_time_2' in buy_trades.columns else 0
    sell_grid_count = len(sell_trades[sell_trades['entry_time_2'].notna()]) if 'entry_time_2' in sell_trades.columns else 0

    print(f"[INFO] Added {len(buy_trades)} BUY entry markers ({buy_grid_count} with GRID)")
    print(f"[INFO] Added {len(sell_trades)} SELL entry markers ({sell_grid_count} with GRID)")
    print(f"[INFO] Added {len(winning_exits)} WINNING exit markers (green squares)")
    print(f"[INFO] Added {len(losing_exits)} LOSING exit markers (red squares)")
    print(f"[INFO] Added {len(df_trades)} connection lines")

# Build dynamic title with filter status and TP/SL info
filters_status = []
if FILTER_BY_SMA:
    filters_status.append("SMA Filter: ON")
else:
    filters_status.append("SMA Filter: OFF")

# GRID info - if trailing stop is ON, GRID_TP_POINTS is ignored (trailing stop overrides)
if FILTER_USE_GRID:
    if SMA_TRAILING_STOP:
        # Trailing stop overrides GRID_TP_POINTS - only show SL
        filters_status.append(f"GRID: ON (SL:{GRID_SL_POINTS}p)")
    else:
        # Normal GRID behavior with fixed TP/SL
        filters_status.append(f"GRID: ON (TP:{GRID_TP_POINTS}p SL:{GRID_SL_POINTS}p)")
else:
    filters_status.append("GRID: OFF")

# Trailing stop info and main TP/SL
if SMA_TRAILING_STOP:
    filters_status.append(f"Trailing Stop: ON ({TRAILING_STOP_ATR_MULT}p)")
    # When trailing stop is active, no fixed TP is used (for both GRID and non-GRID)
    if FILTER_USE_GRID:
        tp_sl_info = f"SL:{GRID_SL_POINTS}p"  # Use GRID SL when GRID is enabled
    else:
        tp_sl_info = f"SL:{SL_POINTS}p"  # Use normal SL when GRID is disabled
else:
    # Normal fixed TP/SL behavior
    if FILTER_USE_GRID:
        tp_sl_info = f"TP:{GRID_TP_POINTS}p SL:{GRID_SL_POINTS}p"
    else:
        tp_sl_info = f"TP:{TP_POINTS}p SL:{SL_POINTS}p"

    # Add Cash & Trail status (only shown when full trailing stop is OFF)
    if SMA_CASH_TRAILING_ENABLED:
        filters_status.append(f"Cash&Trail: ON ({SMA_CASH_TRAILING}p→{SMA_CASH_TRAILING_DISTANCE}p)")
    else:
        filters_status.append("Cash&Trail: OFF")

if FILTER_TIME_OF_DAY:
    filters_status.append("Time Filter: ON")

title_text = f"Trinchera - Trades Visualization | {tp_sl_info} | {' | '.join(filters_status)}"

# Update layout with shapes
fig.update_layout(
    title=title_text,
    xaxis_title='',
    yaxis_title='',
    hovermode=False,
    width=1800,
    height=900,
    template='plotly_white',
    showlegend=True,
    legend=dict(
        yanchor="top",
        y=0.99,
        xanchor="left",
        x=0.01
    ),
    shapes=shapes
)

# Update x-axis format
fig.update_xaxes(
    tickformat='%H:%M:%S',
    showgrid=False,
    showline=True,
    linewidth=1,
    linecolor='rgba(211,211,211,0.6)',
    mirror=True
)

# Update primary y-axis (left - price)
fig.update_yaxes(
    showgrid=True,
    gridcolor='rgba(211,211,211,0.1)',
    tickformat='.2f',
    showline=True,
    linewidth=1,
    linecolor='rgba(211,211,211,0.6)',
    mirror=True,
    secondary_y=False
)

# Update secondary y-axis (right - volume)
fig.update_yaxes(
    showgrid=False,
    tickformat='.0f',
    showline=True,
    linewidth=1,
    linecolor='rgba(211,211,211,0.6)',
    mirror=True,
    secondary_y=True
)

# Save to HTML
fig.write_html(str(OUTPUT_FILE))
print(f"\n[OK] Chart saved to: {OUTPUT_FILE.name}")

# Open in browser
webbrowser.open('file://' + str(OUTPUT_FILE.absolute()))
print(f"[OK] Opening chart in browser...")

print("\n" + "="*80)
print("[SUCCESS] Trades visualization completed!")
print("="*80)
