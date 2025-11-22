"""
Plot Equity Curve for Trinchera Strategy
Generates equity curve, drawdown, and profit distribution charts
"""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import webbrowser
from pathlib import Path
from datetime import datetime
from config_trinchera import FILTER_BY_SMA, FILTER_TIME_OF_DAY, START_TRADING_TIME, END_TRADING_TIME, SMA_TRAILING_STOP

# ============================================================================
# CONFIGURATION
# ============================================================================
CURRENT_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = CURRENT_DIR / "outputs"
CHARTS_DIR = CURRENT_DIR / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

# Find most recent trades file
trades_files = sorted(OUTPUTS_DIR.glob("db_trinchera_TR_*.csv"))
if not trades_files:
    raise FileNotFoundError(f"No trades file found in {OUTPUTS_DIR}")
TRADES_FILE = trades_files[-1]  # Get most recent

# Extract date from trades filename (e.g., db_trinchera_TR_20251022.csv -> 20251022)
import re
date_match = re.search(r'_(\d{8})\.csv', TRADES_FILE.name)
date_str = date_match.group(1) if date_match else datetime.now().strftime("%Y%m%d")
OUTPUT_FILE = CHARTS_DIR / f"equity_trinchera_{date_str}.html"

print("="*80)
print("TRINCHERA EQUITY CURVE PLOTTER")
print("="*80)

# Load trades
print(f"\n[INFO] Loading trades from: {TRADES_FILE.name}")
df = pd.read_csv(TRADES_FILE, sep=';', decimal=',', low_memory=False)
df.columns = df.columns.str.strip()
df['entry_time'] = pd.to_datetime(df['entry_time'])
df['exit_time'] = pd.to_datetime(df['exit_time'])

print(f"[OK] Loaded {len(df)} trades")

# Calculate cumulative profit
df['cumulative_pnl_usd'] = df['pnl_usd'].cumsum()

# Calculate duration in minutes
df['duration_minutes'] = (df['exit_time'] - df['entry_time']).dt.total_seconds() / 60

# Extract time of day for hover info
df['entry_time_only'] = df['entry_time'].dt.strftime('%H:%M:%S')

# Create figure with 3 subplots
fig = make_subplots(
    rows=3, cols=1,
    row_heights=[0.5, 0.25, 0.25],
    shared_xaxes=True,
    subplot_titles=("Equity Curve", "Profit per Trade", "Drawdown"),
    vertical_spacing=0.08
)

# 1. Equity curve with color based on final result
equity_color = 'green' if df['cumulative_pnl_usd'].iloc[-1] > 0 else 'red'
fill_color = 'rgba(0,200,0,0.2)' if df['cumulative_pnl_usd'].iloc[-1] > 0 else 'rgba(200,0,0,0.2)'

fig.add_trace(
    go.Scatter(
        x=list(range(len(df))),
        y=df['cumulative_pnl_usd'],
        mode='lines',
        name='Equity',
        line=dict(color=equity_color, width=2),
        fill='tozeroy',
        fillcolor=fill_color,
        customdata=df[['trade_id', 'entry_time_only']],
        hovertemplate='Trade ID: %{customdata[0]}<br>Entry Time: %{customdata[1]}<br>Equity: $%{y:,.2f}<extra></extra>'
    ),
    row=1, col=1
)

# 2. Profit per trade with colors
colors = ['green' if p > 0 else 'red' for p in df['pnl_usd']]
fig.add_trace(
    go.Bar(
        x=list(range(len(df))),
        y=df['pnl_usd'],
        name='Profit/Loss',
        marker_color=colors,
        opacity=0.6,
        customdata=df[['trade_id', 'entry_time_only']],
        hovertemplate='Trade ID: %{customdata[0]}<br>Entry Time: %{customdata[1]}<br>P/L: $%{y:,.2f}<extra></extra>'
    ),
    row=2, col=1
)

# 3. Drawdown
max_equity = df['cumulative_pnl_usd'].cummax()
drawdown = df['cumulative_pnl_usd'] - max_equity

fig.add_trace(
    go.Scatter(
        x=list(range(len(df))),
        y=drawdown,
        mode='lines',
        name='Drawdown',
        line=dict(color='red', width=2),
        fill='tozeroy',
        fillcolor='rgba(200,0,0,0.2)',
        customdata=df[['trade_id', 'entry_time_only']],
        hovertemplate='Trade ID: %{customdata[0]}<br>Entry Time: %{customdata[1]}<br>DD: $%{y:,.2f}<extra></extra>'
    ),
    row=3, col=1
)

# Update axes labels
fig.update_xaxes(title_text="Trade #", row=3, col=1)
fig.update_yaxes(title_text="Equity ($)", row=1, col=1)
fig.update_yaxes(title_text="P/L ($)", row=2, col=1)
fig.update_yaxes(title_text="DD ($)", row=3, col=1)

# Build filter info for title
filter_info = f"SMA Filter: {'ENABLED' if FILTER_BY_SMA else 'DISABLED'}"
if FILTER_BY_SMA and SMA_TRAILING_STOP:
    filter_info += " (Trailing Stop: ENABLED)"
filter_info += f" | Time Filter: {'ENABLED' if FILTER_TIME_OF_DAY else 'DISABLED'}"
if FILTER_TIME_OF_DAY:
    filter_info += f" ({START_TRADING_TIME} to {END_TRADING_TIME})"

# Update layout
fig.update_layout(
    height=900,
    width=1400,
    showlegend=True,
    hovermode='x unified',
    title_text=f"Trinchera Strategy - Backtest Results ({len(df):,} trades)<br><sub>{filter_info}</sub>",
    template='plotly_white'
)

# Save to HTML
fig.write_html(str(OUTPUT_FILE))
print(f"\n[OK] Equity chart saved to: {OUTPUT_FILE.name}")

# Print summary statistics
print("\n" + "="*80)
print("EQUITY CURVE STATISTICS")
print("="*80)

total_trades = len(df)
winners = df[df['pnl_usd'] > 0]
losers = df[df['pnl_usd'] <= 0]

print(f"\nTrades: {total_trades:,}")
print(f"  Winners: {len(winners):,} ({len(winners)/total_trades*100:.1f}%)")
print(f"  Losers: {len(losers):,} ({len(losers)/total_trades*100:.1f}%)")

print(f"\nProfit:")
print(f"  Total: ${df['pnl_usd'].sum():,.2f}")
print(f"  Average: ${df['pnl_usd'].mean():,.2f}")
print(f"  Median: ${df['pnl_usd'].median():,.2f}")

if len(winners) > 0:
    print(f"\nWinners:")
    print(f"  Average: ${winners['pnl_usd'].mean():,.2f}")
    print(f"  Max: ${winners['pnl_usd'].max():,.2f}")

if len(losers) > 0:
    print(f"\nLosers:")
    print(f"  Average: ${losers['pnl_usd'].mean():,.2f}")
    print(f"  Max: ${losers['pnl_usd'].min():,.2f}")

max_dd = drawdown.min()
print(f"\nDrawdown:")
print(f"  Max: ${max_dd:,.2f}")

print(f"\nDuration:")
print(f"  Average: {df['duration_minutes'].mean():.1f} minutes")
print(f"  Median: {df['duration_minutes'].median():.1f} minutes")

print(f"\nExit Reasons:")
for reason, count in df['exit_reason'].value_counts().items():
    print(f"  {reason}: {count} ({count/total_trades*100:.1f}%)")

print(f"\nDirection:")
for direction, count in df['direction'].value_counts().items():
    print(f"  {direction}: {count} ({count/total_trades*100:.1f}%)")

# Open in browser
webbrowser.open('file://' + str(OUTPUT_FILE.absolute()))
print(f"\n[OK] Opening equity chart in browser...")

print("\n" + "="*80)
print("[SUCCESS] Equity curve generation completed!")
print("="*80)
