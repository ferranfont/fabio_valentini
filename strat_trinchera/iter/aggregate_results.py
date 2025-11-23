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
ITER_SUMMARY_DIR = CURRENT_DIR / "iter_summary"

print("=" * 80)
print("TRINCHERA RESULTS AGGREGATOR")
print("=" * 80)
print(f"\nInput directory: {ITER_SUMMARY_DIR}")

if not ITER_SUMMARY_DIR.exists():
    print(f"\n[ERROR] Directory not found: {ITER_SUMMARY_DIR}")
    print("[ERROR] Run batch_process_all_dates.py first")
    exit(1)

# ============================================================================
# STEP 1: COLLECT ALL TRADES
# ============================================================================
print("\n" + "=" * 80)
print("STEP 1: COLLECTING TRADES FROM ALL DATES")
print("=" * 80)

all_trades = []
date_folders = sorted([d for d in ITER_SUMMARY_DIR.iterdir() if d.is_dir() and d.name.isdigit()])

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
total_pnl_dollars = df_all_trades['pnl_dollars'].sum()

winning_trades = df_all_trades[df_all_trades['pnl'] > 0]
losing_trades = df_all_trades[df_all_trades['pnl'] < 0]

num_winners = len(winning_trades)
num_losers = len(losing_trades)
win_rate = (num_winners / total_trades * 100) if total_trades > 0 else 0

avg_win = winning_trades['pnl_dollars'].mean() if num_winners > 0 else 0
avg_loss = losing_trades['pnl_dollars'].mean() if num_losers > 0 else 0

total_wins = winning_trades['pnl_dollars'].sum() if num_winners > 0 else 0
total_losses = abs(losing_trades['pnl_dollars'].sum()) if num_losers > 0 else 0

profit_factor = (total_wins / total_losses) if total_losses > 0 else 0

# Calculate drawdown
df_all_trades = df_all_trades.sort_values(['date', 'entry_time'])
df_all_trades['cumulative_pnl'] = df_all_trades['pnl_dollars'].cumsum()
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
        'total_pnl': date_trades['pnl_dollars'].sum(),
        'avg_pnl': date_trades['pnl_dollars'].mean(),
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
all_trades_file = ITER_SUMMARY_DIR / f"all_trades_combined_{timestamp}.csv"
df_all_trades.to_csv(all_trades_file, sep=';', decimal=',', index=False)
print(f"\n[OK] All trades saved: {all_trades_file.name}")

# Save statistics by date CSV
stats_file = ITER_SUMMARY_DIR / f"stats_by_date_{timestamp}.csv"
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
html_file = ITER_SUMMARY_DIR / f"consolidated_report_{timestamp}.html"
html_file.write_text(html_content, encoding='utf-8')
print(f"[OK] HTML report saved: {html_file.name}")

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

print("\n" + "=" * 80)
print("[SUCCESS] Results aggregation completed!")
print("=" * 80)

# Open HTML report in browser
import webbrowser
webbrowser.open('file://' + str(html_file.absolute()))
print(f"\n[OK] Opening consolidated report in browser...")
