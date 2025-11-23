"""
Aggregate Results from Batch Processing
Combines all individual date results into consolidated reports
"""

import pandas as pd
from pathlib import Path
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================
CURRENT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = CURRENT_DIR / "iter summary outputs"

print("=" * 80)
print("TRINCHERA RESULTS AGGREGATOR")
print("=" * 80)
print(f"\nInput directory: {OUTPUT_DIR}")

# ============================================================================
# STEP 1: COLLECT ALL TRADES
# ============================================================================
print("\n" + "=" * 80)
print("STEP 1: COLLECTING TRADES FROM ALL DATES")
print("=" * 80)

all_trades = []
date_folders = sorted([d for d in OUTPUT_DIR.iterdir() if d.is_dir() and d.name.isdigit()])

if not date_folders:
    print(f"\n[ERROR] No date folders found in: {OUTPUT_DIR}")
    print("[ERROR] Run batch_process_all_dates.py first")
    exit(1)

print(f"\n[INFO] Found {len(date_folders)} date folders")

for date_folder in date_folders:
    date = date_folder.name
    trades_file = date_folder / f"db_trinchera_TR_{date}.csv"

    if trades_file.exists():
        try:
            df = pd.read_csv(trades_file, sep=';', decimal=',', low_memory=False)
            df['date'] = date
            all_trades.append(df)
            print(f"  [OK] {date}: {len(df)} trades")
        except Exception as e:
            print(f"  [ERROR] {date}: Failed to load - {e}")
    else:
        print(f"  [WARN] {date}: No trades file found")

if not all_trades:
    print("\n[ERROR] No trade files found!")
    exit(1)

# Combine all trades
df_all_trades = pd.concat(all_trades, ignore_index=True)
print(f"\n[OK] Total trades collected: {len(df_all_trades)}")

# ============================================================================
# STEP 2: AGGREGATE STATISTICS
# ============================================================================
print("\n" + "=" * 80)
print("STEP 2: CALCULATING AGGREGATE STATISTICS")
print("=" * 80)

# Overall statistics
total_trades = len(df_all_trades)
total_pnl_points = df_all_trades['pnl'].sum()
total_pnl_dollars = df_all_trades['pnl_usd'].sum()

winning_trades = df_all_trades[df_all_trades['pnl'] > 0]
losing_trades = df_all_trades[df_all_trades['pnl'] < 0]

num_winners = len(winning_trades)
num_losers = len(losing_trades)
win_rate = (num_winners / total_trades * 100) if total_trades > 0 else 0

avg_win = winning_trades['pnl_usd'].mean() if num_winners > 0 else 0
avg_loss = losing_trades['pnl_usd'].mean() if num_losers > 0 else 0

total_wins = winning_trades['pnl_usd'].sum() if num_winners > 0 else 0
total_losses = abs(losing_trades['pnl_usd'].sum()) if num_losers > 0 else 0

profit_factor = (total_wins / total_losses) if total_losses > 0 else 0

# Calculate drawdown
df_all_trades = df_all_trades.sort_values(['date', 'entry_time'])
df_all_trades['cumulative_pnl'] = df_all_trades['pnl_usd'].cumsum()
df_all_trades['running_max'] = df_all_trades['cumulative_pnl'].cummax()
df_all_trades['drawdown'] = df_all_trades['cumulative_pnl'] - df_all_trades['running_max']
max_drawdown = df_all_trades['drawdown'].min()

# Statistics by date
stats_by_date = []
for date in sorted(df_all_trades['date'].unique()):
    date_trades = df_all_trades[df_all_trades['date'] == date]

    stats_by_date.append({
        'date': date,
        'trades': len(date_trades),
        'winners': len(date_trades[date_trades['pnl'] > 0]),
        'losers': len(date_trades[date_trades['pnl'] < 0]),
        'win_rate': (len(date_trades[date_trades['pnl'] > 0]) / len(date_trades) * 100) if len(date_trades) > 0 else 0,
        'total_pnl': date_trades['pnl_usd'].sum(),
        'avg_pnl': date_trades['pnl_usd'].mean(),
    })

df_stats_by_date = pd.DataFrame(stats_by_date)

print(f"\nOverall Statistics:")
print(f"  Total Trades: {total_trades:,}")
print(f"  Total P&L: ${total_pnl_dollars:,.2f} ({total_pnl_points:.2f} points)")
print(f"  Win Rate: {win_rate:.1f}%")
print(f"  Winners: {num_winners} (avg: ${avg_win:.2f})")
print(f"  Losers: {num_losers} (avg: ${avg_loss:.2f})")
print(f"  Profit Factor: {profit_factor:.2f}")
print(f"  Max Drawdown: ${max_drawdown:,.2f}")

# ============================================================================
# STEP 3: SAVE AGGREGATED DATA
# ============================================================================
print("\n" + "=" * 80)
print("STEP 3: SAVING AGGREGATED REPORTS")
print("=" * 80)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

# Save combined trades CSV
all_trades_file = OUTPUT_DIR / f"all_trades_combined_{timestamp}.csv"
df_all_trades.to_csv(all_trades_file, sep=';', decimal=',', index=False)
print(f"\n[OK] All trades saved: {all_trades_file.name}")

# Save statistics by date CSV
stats_file = OUTPUT_DIR / f"stats_by_date_{timestamp}.csv"
df_stats_by_date.to_csv(stats_file, sep=';', decimal=',', index=False)
print(f"[OK] Date statistics saved: {stats_file.name}")

# ============================================================================
# STEP 4: GENERATE HTML SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("STEP 4: GENERATING CONSOLIDATED HTML REPORT")
print("=" * 80)

# Best and worst days
best_day = df_stats_by_date.loc[df_stats_by_date['total_pnl'].idxmax()]
worst_day = df_stats_by_date.loc[df_stats_by_date['total_pnl'].idxmin()]

html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Trinchera Strategy - Consolidated Results</title>
    <style>
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: center;
        }}
        h1 {{
            margin: 0;
            font-size: 28px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .stat-label {{
            color: #666;
            font-size: 12px;
            text-transform: uppercase;
            margin-bottom: 5px;
        }}
        .stat-value {{
            font-size: 24px;
            font-weight: bold;
            color: #333;
        }}
        .positive {{
            color: #28a745;
        }}
        .negative {{
            color: #dc3545;
        }}
        table {{
            width: 100%;
            background: white;
            border-collapse: collapse;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        th {{
            background: #667eea;
            color: white;
            padding: 12px;
            text-align: left;
            font-size: 13px;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #eee;
            font-size: 12px;
        }}
        tr:hover {{
            background-color: #f8f9fa;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>TRINCHERA STRATEGY - CONSOLIDATED RESULTS</h1>
        <p>Period: {df_stats_by_date['date'].min()} to {df_stats_by_date['date'].max()} ({len(date_folders)} trading days)</p>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-label">Total Trades</div>
            <div class="stat-value">{total_trades:,}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Total P&L</div>
            <div class="stat-value {'positive' if total_pnl_dollars >= 0 else 'negative'}">${total_pnl_dollars:,.2f}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Win Rate</div>
            <div class="stat-value">{win_rate:.1f}%</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Profit Factor</div>
            <div class="stat-value {'positive' if profit_factor >= 1 else 'negative'}">{profit_factor:.2f}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Avg Win</div>
            <div class="stat-value positive">${avg_win:.2f}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Avg Loss</div>
            <div class="stat-value negative">${avg_loss:.2f}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Max Drawdown</div>
            <div class="stat-value negative">${max_drawdown:,.2f}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Best Day</div>
            <div class="stat-value positive">${best_day['total_pnl']:.2f}</div>
            <div class="stat-label">{best_day['date']}</div>
        </div>
    </div>

    <h2>Performance by Date</h2>
    <table>
        <tr>
            <th>Date</th>
            <th>Trades</th>
            <th>Winners</th>
            <th>Losers</th>
            <th>Win Rate</th>
            <th>Total P&L</th>
            <th>Avg P&L</th>
        </tr>
"""

for _, row in df_stats_by_date.iterrows():
    pnl_class = 'positive' if row['total_pnl'] >= 0 else 'negative'
    html_content += f"""
        <tr>
            <td>{row['date']}</td>
            <td>{row['trades']}</td>
            <td>{row['winners']}</td>
            <td>{row['losers']}</td>
            <td>{row['win_rate']:.1f}%</td>
            <td class="{pnl_class}">${row['total_pnl']:,.2f}</td>
            <td class="{pnl_class}">${row['avg_pnl']:.2f}</td>
        </tr>
"""

html_content += """
    </table>
</body>
</html>
"""

# Save HTML report
html_file = OUTPUT_DIR / f"consolidated_report_{timestamp}.html"
html_file.write_text(html_content, encoding='utf-8')
print(f"[OK] HTML report saved: {html_file.name}")

# ============================================================================
# STEP 5: GENERATE RATIOS REPORT
# ============================================================================
print("\n" + "=" * 80)
print("STEP 5: GENERATING RATIOS REPORT")
print("=" * 80)

# Calculate additional ratios
avg_trade = total_pnl_dollars / total_trades if total_trades > 0 else 0
expectancy = (win_rate / 100 * avg_win) + ((100 - win_rate) / 100 * avg_loss)
recovery_factor = abs(total_pnl_dollars / max_drawdown) if max_drawdown != 0 else 0
sharpe_ratio = (df_all_trades['pnl_usd'].mean() / df_all_trades['pnl_usd'].std()) * (252 ** 0.5) if len(df_all_trades) > 1 else 0

ratios_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Trinchera Strategy - Performance Ratios</title>
    <style>
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: center;
        }}
        h1 {{
            margin: 0;
            font-size: 28px;
        }}
        .ratios-container {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            max-width: 1000px;
            margin: 0 auto;
        }}
        .two-column-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th {{
            background: #667eea;
            color: white;
            padding: 8px 10px;
            text-align: left;
            font-size: 12px;
        }}
        td {{
            padding: 6px 10px;
            border-bottom: 1px solid #eee;
            font-size: 11px;
        }}
        td:first-child {{
            font-weight: bold;
            color: #555;
            width: 60%;
        }}
        td:last-child {{
            text-align: right;
            font-size: 12px;
            font-weight: bold;
            width: 40%;
        }}
        .positive {{
            color: #28a745;
        }}
        .negative {{
            color: #dc3545;
        }}
        .neutral {{
            color: #6c757d;
        }}
        tr:hover {{
            background-color: #f8f9fa;
        }}
        .section-header {{
            background: #f8f9fa !important;
            font-weight: bold;
            color: #333 !important;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>TRINCHERA STRATEGY - PERFORMANCE RATIOS</h1>
        <p>Period: {df_stats_by_date['date'].min()} to {df_stats_by_date['date'].max()} ({len(date_folders)} trading days)</p>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>

    <div class="ratios-container">
        <div class="two-column-grid">
            <!-- Column 1 -->
            <div>
                <table>
                    <tr><th colspan="2">GENERAL</th></tr>
                    <tr><td>Total Trades</td><td class="neutral">{total_trades:,}</td></tr>
                    <tr><td>Trading Days</td><td class="neutral">{len(date_folders)}</td></tr>
                    <tr><td>Avg Trades/Day</td><td class="neutral">{total_trades / len(date_folders):.1f}</td></tr>
                </table>

                <table style="margin-top:15px;">
                    <tr><th colspan="2">PROFITABILITY</th></tr>
                    <tr><td>Total P&L</td><td class="{'positive' if total_pnl_dollars >= 0 else 'negative'}">${total_pnl_dollars:,.2f}</td></tr>
                    <tr><td>Points</td><td class="{'positive' if total_pnl_points >= 0 else 'negative'}">{total_pnl_points:.2f}</td></tr>
                    <tr><td>Avg Trade</td><td class="{'positive' if avg_trade >= 0 else 'negative'}">${avg_trade:.2f}</td></tr>
                    <tr><td>Expectancy</td><td class="{'positive' if expectancy >= 0 else 'negative'}">${expectancy:.2f}</td></tr>
                </table>

                <table style="margin-top:15px;">
                    <tr><th colspan="2">WIN/LOSS</th></tr>
                    <tr><td>Win Rate</td><td class="{'positive' if win_rate >= 50 else 'negative'}">{win_rate:.1f}%</td></tr>
                    <tr><td>Winners</td><td class="positive">{num_winners:,}</td></tr>
                    <tr><td>Losers</td><td class="negative">{num_losers:,}</td></tr>
                    <tr><td>Avg Win</td><td class="positive">${avg_win:.2f}</td></tr>
                    <tr><td>Avg Loss</td><td class="negative">${avg_loss:.2f}</td></tr>
                    <tr><td>Win/Loss Ratio</td><td class="{'positive' if abs(avg_win/avg_loss) >= 1 else 'negative'}">{abs(avg_win/avg_loss):.2f}</td></tr>
                </table>
            </div>

            <!-- Column 2 -->
            <div>
                <table>
                    <tr><th colspan="2">RISK METRICS</th></tr>
                    <tr><td>Profit Factor</td><td class="{'positive' if profit_factor >= 1 else 'negative'}">{profit_factor:.2f}</td></tr>
                    <tr><td>Sharpe Ratio</td><td class="{'positive' if sharpe_ratio >= 1 else 'negative'}">{sharpe_ratio:.2f}</td></tr>
                    <tr><td>Max Drawdown</td><td class="negative">${max_drawdown:,.2f}</td></tr>
                    <tr><td>Recovery Factor</td><td class="{'positive' if recovery_factor >= 2 else 'negative'}">{recovery_factor:.2f}</td></tr>
                </table>

                <table style="margin-top:15px;">
                    <tr><th colspan="2">DAILY PERFORMANCE</th></tr>
                    <tr><td>Best Day</td><td class="positive">${best_day['total_pnl']:.2f}</td></tr>
                    <tr><td>Best Date</td><td class="neutral">{best_day['date']}</td></tr>
                    <tr><td>Worst Day</td><td class="negative">${worst_day['total_pnl']:.2f}</td></tr>
                    <tr><td>Worst Date</td><td class="neutral">{worst_day['date']}</td></tr>
                    <tr><td>Avg Daily P&L</td><td class="{'positive' if df_stats_by_date['total_pnl'].mean() >= 0 else 'negative'}">${df_stats_by_date['total_pnl'].mean():.2f}</td></tr>
                    <tr><td>Profitable Days</td><td class="positive">{len(df_stats_by_date[df_stats_by_date['total_pnl'] > 0])}/{len(df_stats_by_date)}</td></tr>
                    <tr><td>Profit Days %</td><td class="positive">{len(df_stats_by_date[df_stats_by_date['total_pnl'] > 0])/len(df_stats_by_date)*100:.1f}%</td></tr>
                </table>
            </div>
        </div>
    </div>
</body>
</html>
"""

ratios_file = OUTPUT_DIR / f"consolidated_report_ratios_{timestamp}.html"
ratios_file.write_text(ratios_html, encoding='utf-8')
print(f"[OK] Ratios report saved: {ratios_file.name}")

# ============================================================================
# STEP 6: GENERATE EQUITY CURVE CHART
# ============================================================================
print("\n" + "=" * 80)
print("STEP 6: GENERATING EQUITY CURVE CHART")
print("=" * 80)

import plotly.graph_objs as go
from plotly.subplots import make_subplots

# Prepare data for equity curve
df_equity = df_all_trades.sort_values(['date', 'entry_time']).copy()
df_equity['cumulative_pnl'] = df_equity['pnl_usd'].cumsum()
df_equity['running_max'] = df_equity['cumulative_pnl'].cummax()
df_equity['drawdown'] = df_equity['cumulative_pnl'] - df_equity['running_max']
df_equity['trade_number'] = range(1, len(df_equity) + 1)

# Create subplot figure
fig = make_subplots(
    rows=2, cols=1,
    row_heights=[0.7, 0.3],
    subplot_titles=('Equity Curve', 'Drawdown'),
    vertical_spacing=0.1
)

# Equity curve - Green with fill
fig.add_trace(
    go.Scatter(
        x=df_equity['trade_number'],
        y=df_equity['cumulative_pnl'],
        mode='lines',
        name='Equity',
        fill='tozeroy',
        line=dict(color='rgba(40, 167, 69, 0.8)', width=2),
        fillcolor='rgba(40, 167, 69, 0.2)',
        hovertemplate='<b>Trade #%{x}</b><br>Equity: $%{y:,.2f}<extra></extra>'
    ),
    row=1, col=1
)

# Zero line
fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5, row=1, col=1)

# Drawdown
fig.add_trace(
    go.Scatter(
        x=df_equity['trade_number'],
        y=df_equity['drawdown'],
        mode='lines',
        name='Drawdown',
        fill='tozeroy',
        line=dict(color='#dc3545', width=1),
        fillcolor='rgba(220, 53, 69, 0.3)',
        hovertemplate='<b>Trade #%{x}</b><br>Drawdown: $%{y:,.2f}<extra></extra>'
    ),
    row=2, col=1
)

# Update layout
fig.update_layout(
    title=dict(
        text=f'Trinchera Strategy - Equity Curve<br><sub>Period: {df_stats_by_date["date"].min()} to {df_stats_by_date["date"].max()} | {total_trades:,} trades | Total P&L: ${total_pnl_dollars:,.2f}</sub>',
        x=0.5,
        xanchor='center'
    ),
    height=800,
    showlegend=True,
    hovermode='x unified',
    template='plotly_white'
)

fig.update_xaxes(title_text="Trade Number", row=2, col=1)
fig.update_yaxes(title_text="Cumulative P&L ($)", row=1, col=1)
fig.update_yaxes(title_text="Drawdown ($)", row=2, col=1)

equity_file = OUTPUT_DIR / f"consolidated_equity_{timestamp}.html"
fig.write_html(str(equity_file))
print(f"[OK] Equity curve saved: {equity_file.name}")

# ============================================================================
# FINAL SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("AGGREGATION COMPLETED")
print("=" * 80)

print(f"\nFiles generated:")
print(f"  - {all_trades_file.name} ({len(df_all_trades):,} trades)")
print(f"  - {stats_file.name} ({len(df_stats_by_date)} dates)")
print(f"  - {html_file.name}")
print(f"  - {ratios_file.name}")
print(f"  - {equity_file.name}")

print("\n" + "=" * 80)
print("[SUCCESS] Results aggregation completed!")
print("=" * 80)

# Open HTML reports in browser
import webbrowser
webbrowser.open('file://' + str(ratios_file.absolute()))
print(f"\n[OK] Opening ratios report in browser...")
webbrowser.open('file://' + str(equity_file.absolute()))
print(f"[OK] Opening equity curve in browser...")
