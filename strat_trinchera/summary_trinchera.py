"""
Trinchera Strategy Summary Report
Generates comprehensive HTML report with performance metrics, risk ratios, and distributions
"""

import pandas as pd
from pathlib import Path
import webbrowser
from datetime import datetime
from config_trinchera import MEAN_REVERS_EXPAND, BIG_VOLUME_TRIGGER, TP_POINTS, SL_POINTS, FILTER_BY_SMA, FILTER_TIME_OF_DAY, START_TRADING_TIME, END_TRADING_TIME, FILTER_USE_GRID, GRID_MEAN_REVERS_EXPAND, GRID_TP_POINTS, GRID_SL_POINTS, SMA_TRAILING_STOP, TRAILING_STOP_ATR_MULT

# ============================================================================
# CONFIGURATION
# ============================================================================
CURRENT_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = CURRENT_DIR / "outputs"
CHARTS_DIR = CURRENT_DIR / "charts"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
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
OUTPUT_FILE = CHARTS_DIR / f"summary_trinchera_{date_str}.html"

# Strategy parameters
POINT_VALUE = 20.0

print("="*80)
print("TRINCHERA SUMMARY REPORT GENERATOR")
print("="*80)

# Load trades
print(f"\n[INFO] Loading trades from: {TRADES_FILE.name}")
df_trades = pd.read_csv(TRADES_FILE, sep=';', decimal=',', low_memory=False)
df_trades.columns = df_trades.columns.str.strip()
df_trades['entry_time'] = pd.to_datetime(df_trades['entry_time'])
df_trades['exit_time'] = pd.to_datetime(df_trades['exit_time'])

print(f"[OK] Loaded {len(df_trades)} trades")

# Calculate trade duration in minutes
df_trades['duration_minutes'] = (df_trades['exit_time'] - df_trades['entry_time']).dt.total_seconds() / 60

# ============================================================================
# CALCULATE METRICS
# ============================================================================

# GENERAL
total_trades = len(df_trades)
period_start = df_trades['entry_time'].min()
period_end = df_trades['exit_time'].max()
exposure_days = (period_end - period_start).days
trades_per_day = total_trades / exposure_days if exposure_days > 0 else 0
avg_duration = df_trades['duration_minutes'].mean()
median_duration = df_trades['duration_minutes'].median()

# PERFORMANCE
total_pnl = df_trades['pnl'].sum()
total_pnl_usd = df_trades['pnl_usd'].sum()
avg_profit = df_trades['pnl'].mean()
avg_profit_usd = df_trades['pnl_usd'].mean()
median_profit = df_trades['pnl'].median()
median_profit_usd = df_trades['pnl_usd'].median()
std_profit = df_trades['pnl'].std()
std_profit_usd = df_trades['pnl_usd'].std()

# WIN/LOSS
winners = df_trades[df_trades['exit_reason'] == 'profit']
losers = df_trades[(df_trades['exit_reason'] == 'stop') | (df_trades['exit_reason'] == 'trailing_stop')]
trailing_stops = df_trades[df_trades['exit_reason'] == 'trailing_stop']
win_rate = len(winners) / total_trades * 100 if total_trades > 0 else 0
num_winners = len(winners)
num_losers = len(losers)
num_trailing_stops = len(trailing_stops)

gross_profit = winners['pnl'].sum() if len(winners) > 0 else 0
gross_profit_usd = winners['pnl_usd'].sum() if len(winners) > 0 else 0
gross_loss = abs(losers['pnl'].sum()) if len(losers) > 0 else 0
gross_loss_usd = abs(losers['pnl_usd'].sum()) if len(losers) > 0 else 0

avg_winner = winners['pnl'].mean() if len(winners) > 0 else 0
avg_winner_usd = winners['pnl_usd'].mean() if len(winners) > 0 else 0
avg_loser = losers['pnl'].mean() if len(losers) > 0 else 0
avg_loser_usd = losers['pnl_usd'].mean() if len(losers) > 0 else 0

largest_winner = winners['pnl'].max() if len(winners) > 0 else 0
largest_winner_usd = winners['pnl_usd'].max() if len(winners) > 0 else 0
largest_loser = losers['pnl'].min() if len(losers) > 0 else 0
largest_loser_usd = losers['pnl_usd'].min() if len(losers) > 0 else 0

profit_factor = gross_profit / gross_loss if gross_loss != 0 else 0
expectancy = avg_profit
expectancy_usd = avg_profit_usd

# RISK METRICS
df_trades['cumulative_pnl'] = df_trades['pnl'].cumsum()
df_trades['cumulative_pnl_usd'] = df_trades['pnl_usd'].cumsum()
df_trades['running_max'] = df_trades['cumulative_pnl'].cummax()
df_trades['running_max_usd'] = df_trades['cumulative_pnl_usd'].cummax()
df_trades['drawdown'] = df_trades['cumulative_pnl'] - df_trades['running_max']
df_trades['drawdown_usd'] = df_trades['cumulative_pnl_usd'] - df_trades['running_max_usd']

max_drawdown = df_trades['drawdown'].min()
max_drawdown_usd = df_trades['drawdown_usd'].min()

# Ulcer Index (RMS of drawdowns)
ulcer_index = (df_trades['drawdown'] ** 2).mean() ** 0.5
ulcer_index_usd = (df_trades['drawdown_usd'] ** 2).mean() ** 0.5

# Recovery Factor
recovery_factor = abs(total_pnl / max_drawdown) if max_drawdown != 0 else 0

# Sharpe Ratio (assuming 0 risk-free rate)
sharpe_ratio = avg_profit / std_profit if std_profit != 0 else 0

# Sortino Ratio (downside deviation from zero)
# Calculate downside deviation: square root of mean of squared negative returns
downside_returns = df_trades['pnl'].copy()
downside_returns[downside_returns > 0] = 0  # Zero out positive returns
downside_deviation = ((downside_returns ** 2).mean()) ** 0.5
sortino_ratio = avg_profit / downside_deviation if downside_deviation != 0 else 0

# Winning/Losing Streaks
df_trades['win'] = (df_trades['exit_reason'] == 'profit').astype(int)
df_trades['streak_id'] = (df_trades['win'] != df_trades['win'].shift()).cumsum()
streaks = df_trades.groupby('streak_id')['win'].agg(['first', 'count'])
max_win_streak = streaks[streaks['first'] == 1]['count'].max() if len(streaks[streaks['first'] == 1]) > 0 else 0
max_loss_streak = streaks[streaks['first'] == 0]['count'].max() if len(streaks[streaks['first'] == 0]) > 0 else 0

# DISTRIBUTION
skewness = df_trades['pnl'].skew()
kurtosis = df_trades['pnl'].kurtosis()

# EXIT REASONS
target_exits = len(df_trades[df_trades['exit_reason'] == 'profit'])
stop_exits = len(df_trades[df_trades['exit_reason'] == 'stop'])
eod_exits = 0  # Not applicable in this strategy

# SIGNAL BREAKDOWN
long_trades = df_trades[df_trades['direction'] == 'BUY']
short_trades = df_trades[df_trades['direction'] == 'SELL']

num_long = len(long_trades)
num_short = len(short_trades)
long_pnl = long_trades['pnl_usd'].sum() if len(long_trades) > 0 else 0
short_pnl = short_trades['pnl_usd'].sum() if len(short_trades) > 0 else 0

# ============================================================================
# GENERATE HTML REPORT
# ============================================================================

html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Trinchera Strategy Summary</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background-color: white;
            color: black;
            padding: 20px;
            text-align: center;
            margin-bottom: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
        }}
        .header p {{
            margin: 5px 0;
            font-size: 14px;
            color: #666;
        }}
        .container {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            max-width: 1000px;
            margin: 0 auto;
        }}
        .section {{
            background-color: white;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .section-header {{
            background-color: #2196F3;
            color: white;
            padding: 8px 12px;
            font-weight: bold;
            font-size: 13px;
        }}
        .section-content {{
            padding: 12px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        tr {{
            border-bottom: 1px solid #f0f0f0;
        }}
        tr:last-child {{
            border-bottom: none;
        }}
        td {{
            padding: 6px 8px;
            font-size: 12px;
        }}
        td:first-child {{
            color: #666;
            width: 60%;
        }}
        td:last-child {{
            text-align: right;
            font-weight: bold;
            width: 40%;
        }}
        .positive {{
            color: #4CAF50;
        }}
        .negative {{
            color: #f44336;
        }}
        .footer {{
            text-align: center;
            margin-top: 20px;
            padding: 10px;
            color: #666;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>TRINCHERA MEAN REVERSION STRATEGY</h1>
        <p>TP: {TP_POINTS} pts (${TP_POINTS * POINT_VALUE:.0f}) | SL: {SL_POINTS} pts (${SL_POINTS * POINT_VALUE:.0f}) | Mean Reversion: ±{MEAN_REVERS_EXPAND} pts | Volume Trigger: {BIG_VOLUME_TRIGGER}</p>
        <p>GRID: {'ENABLED' if FILTER_USE_GRID else 'DISABLED'}{' | Distance: ' + str(GRID_MEAN_REVERS_EXPAND) + ' pts | TP: ' + str(GRID_TP_POINTS) + ' pts ($' + str(int(GRID_TP_POINTS * POINT_VALUE)) + ') | SL: ' + str(GRID_SL_POINTS) + ' pts ($' + str(int(GRID_SL_POINTS * POINT_VALUE)) + ')' if FILTER_USE_GRID else ''}</p>
        <p>Period: {period_start.strftime('%Y-%m-%d %H:%M')} to {period_end.strftime('%Y-%m-%d %H:%M')}</p>
        <p>Filters: SMA Filter {'ENABLED' if FILTER_BY_SMA else 'DISABLED'}{' (Trailing Stop: ' + ('ENABLED' if SMA_TRAILING_STOP else 'DISABLED') + ')' if FILTER_BY_SMA else ''} | Time Filter {'ENABLED' if FILTER_TIME_OF_DAY else 'DISABLED'}{' (' + START_TRADING_TIME + ' to ' + END_TRADING_TIME + ')' if FILTER_TIME_OF_DAY else ''}</p>
    </div>

    <div class="container">
        <!-- GENERAL -->
        <div class="section">
            <div class="section-header">GENERAL</div>
            <div class="section-content">
                <table>
                    <tr><td>Total Trades</td><td>{total_trades}</td></tr>
                    <tr><td>Periodo</td><td>{'Time: ' + START_TRADING_TIME + ' to ' + END_TRADING_TIME if FILTER_TIME_OF_DAY else period_start.strftime('%Y-%m-%d %H:%M:%S') + '<br>' + period_end.strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
                    <tr><td>Exposure Days</td><td>{exposure_days}</td></tr>
                    <tr><td>Trades per Day</td><td>{trades_per_day:.1f}</td></tr>
                    <tr><td>Avg Duration</td><td>{avg_duration:.1f} min</td></tr>
                    <tr><td>Median Duration</td><td>{median_duration:.1f} min</td></tr>
                </table>
            </div>
        </div>

        <!-- PERFORMANCE -->
        <div class="section">
            <div class="section-header">PERFORMANCE</div>
            <div class="section-content">
                <table>
                    <tr><td>Total Profit</td><td class="{'positive' if total_pnl_usd >= 0 else 'negative'}">${total_pnl_usd:,.2f}</td></tr>
                    <tr><td>Avg Profit</td><td class="{'positive' if avg_profit_usd >= 0 else 'negative'}">${avg_profit_usd:.2f}</td></tr>
                    <tr><td>Median Profit</td><td class="{'positive' if median_profit_usd >= 0 else 'negative'}">${median_profit_usd:.2f}</td></tr>
                    <tr><td>Std Profit</td><td>${std_profit_usd:.2f}</td></tr>
                    <tr><td>Profit Factor</td><td>{profit_factor:.2f}</td></tr>
                    <tr><td>Expectancy</td><td class="{'positive' if expectancy_usd >= 0 else 'negative'}">${expectancy_usd:.2f}</td></tr>
                </table>
            </div>
        </div>

        <!-- WIN/LOSS -->
        <div class="section">
            <div class="section-header">WIN/LOSS</div>
            <div class="section-content">
                <table>
                    <tr><td>Win Rate</td><td>{win_rate:.1f}%</td></tr>
                    <tr><td>Winners / Losers</td><td>{num_winners} / {num_losers}</td></tr>
                    <tr><td>Gross Profit</td><td class="positive">${gross_profit_usd:,.2f}</td></tr>
                    <tr><td>Gross Loss</td><td class="negative">${gross_loss_usd:,.2f}</td></tr>
                    <tr><td>Avg Winner</td><td class="positive">${avg_winner_usd:.2f}</td></tr>
                    <tr><td>Avg Loser</td><td class="negative">${avg_loser_usd:.2f}</td></tr>
                    <tr><td>Largest Winner</td><td class="positive">${largest_winner_usd:.2f}</td></tr>
                    <tr><td>Largest Loser</td><td class="negative">${largest_loser_usd:.2f}</td></tr>
                </table>
            </div>
        </div>

        <!-- RISK METRICS -->
        <div class="section">
            <div class="section-header">RISK METRICS</div>
            <div class="section-content">
                <table>
                    <tr><td>Max Drawdown</td><td class="negative">${max_drawdown_usd:,.2f}</td></tr>
                    <tr><td>Ulcer Index</td><td>{ulcer_index_usd:.2f}</td></tr>
                    <tr><td>Recovery Factor</td><td>{recovery_factor:.2f}</td></tr>
                    <tr><td>Sharpe Ratio</td><td>{sharpe_ratio:.2f}</td></tr>
                    <tr><td>Sortino Ratio</td><td>{sortino_ratio:.2f}</td></tr>
                    <tr><td>Skewness</td><td>{skewness:.3f}</td></tr>
                    <tr><td>Kurtosis</td><td>{kurtosis:.3f}</td></tr>
                    <tr><td>Max Winning Streak</td><td>{max_win_streak:.0f}</td></tr>
                    <tr><td>Max Losing Streak</td><td>{max_loss_streak:.0f}</td></tr>
                </table>
            </div>
        </div>

        <!-- EXIT REASONS -->
        <div class="section">
            <div class="section-header">EXIT REASONS</div>
            <div class="section-content">
                <table>
                    <tr><td>TARGET exits</td><td>{target_exits} ({target_exits/total_trades*100:.1f}%)</td></tr>
                    <tr><td>STOP exits</td><td>{stop_exits} ({stop_exits/total_trades*100:.1f}%)</td></tr>
                    {'<tr><td>TRAILING STOP exits</td><td>' + str(num_trailing_stops) + ' (' + f'{num_trailing_stops/total_trades*100:.1f}' + '%)</td></tr>' if num_trailing_stops > 0 else ''}
                    <tr><td>EOD exits</td><td>{eod_exits} ({eod_exits/total_trades*100 if total_trades > 0 else 0:.1f}%)</td></tr>
                </table>
            </div>
        </div>

        <!-- SIGNAL BREAKDOWN -->
        <div class="section">
            <div class="section-header">SIGNAL BREAKDOWN</div>
            <div class="section-content">
                <table>
                    <tr><td>BUY (LONG)</td><td>{num_long} ({num_long/total_trades*100:.1f}%)</td></tr>
                    <tr><td>BUY Profit</td><td class="{'positive' if long_pnl >= 0 else 'negative'}">${long_pnl:,.2f}</td></tr>
                    <tr><td>SELL (SHORT)</td><td>{num_short} ({num_short/total_trades*100:.1f}%)</td></tr>
                    <tr><td>SELL Profit</td><td class="{'positive' if short_pnl >= 0 else 'negative'}">${short_pnl:,.2f}</td></tr>
                </table>
            </div>
        </div>
    </div>

    <div class="footer">
        Generated by Trinchera Strategy Backtest | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    </div>
</body>
</html>
"""

# Save HTML file
with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    f.write(html_content)

print(f"\n[OK] Summary report saved to: {OUTPUT_FILE.name}")

# Open in browser
webbrowser.open('file://' + str(OUTPUT_FILE.absolute()))
print(f"[OK] Opening summary report in browser...")

print("\n" + "="*80)
print("[SUCCESS] Summary report generated!")
print("="*80)
