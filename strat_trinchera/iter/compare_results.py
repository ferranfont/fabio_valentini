"""
Compare Results from Different MEAN_REVERS_EXPAND Values
Reads existing aggregate results and creates comparison summary
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
import webbrowser

# ============================================================================
# CONFIGURATION
# ============================================================================
CURRENT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = CURRENT_DIR / "iter summary outputs"

print("=" * 80)
print("COMPARE MEAN_REVERS_EXPAND RESULTS")
print("=" * 80)

# ============================================================================
# MANUAL INPUT: Define your test results
# ============================================================================
# Add your test results here manually
# Format: (mean_revers_expand, total_pnl, total_trades, win_rate, sharpe_ratio, max_drawdown)

RESULTS = [
    # From your first image (Entry: ±10 pts)
    {
        'mean_revers_expand': 10,
        'total_pnl': 42700.00,
        'points': 2135.00,
        'total_trades': 3017,
        'win_rate': 69.3,
        'sharpe_ratio': 0.61,  # Update if you have exact value
        'sortino_ratio': 0.71,  # Update if you have exact value
        'max_drawdown': -5880.00,
        'trading_days': 37,
        'profit_factor': 1.26,
        'recovery_factor': 7.26
    },
    # From your second image (Entry: ±14 pts)
    {
        'mean_revers_expand': 14,
        'total_pnl': 19140.00,
        'points': 957.00,
        'total_trades': 2311,
        'win_rate': 67.2,
        'sharpe_ratio': 0.31,
        'sortino_ratio': 0.38,
        'max_drawdown': -7320.00,
        'trading_days': 37,
        'profit_factor': 1.14,
        'recovery_factor': 2.61
    },
    # Add more results as you test them:
    # {
    #     'mean_revers_expand': 15,
    #     'total_pnl': 0.00,  # Fill in after testing
    #     'points': 0.00,
    #     'total_trades': 0,
    #     'win_rate': 0.0,
    #     'sharpe_ratio': 0.0,
    #     'sortino_ratio': 0.0,
    #     'max_drawdown': 0.0,
    #     'trading_days': 37,
    #     'profit_factor': 0.0,
    #     'recovery_factor': 0.0
    # },
]

# ============================================================================
# CREATE COMPARISON DATAFRAME
# ============================================================================
print("\n" + "=" * 80)
print("GENERATING COMPARISON REPORT")
print("=" * 80)

df_results = pd.DataFrame(RESULTS)

# Calculate additional metrics
df_results['avg_daily_pnl'] = df_results['total_pnl'] / df_results['trading_days']
df_results['avg_trade_pnl'] = df_results['total_pnl'] / df_results['total_trades']
df_results['trades_per_day'] = df_results['total_trades'] / df_results['trading_days']

# Sort by total P&L descending
df_results = df_results.sort_values('total_pnl', ascending=False)

# Find best values
best_pnl = df_results.iloc[0]
best_sharpe = df_results.loc[df_results['sharpe_ratio'].idxmax()]
best_profit_factor = df_results.loc[df_results['profit_factor'].idxmax()]

# Save CSV
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
csv_file = OUTPUT_DIR / f"comparison_mean_revers_expand_{timestamp}.csv"
df_results.to_csv(csv_file, sep=';', decimal=',', index=False)
print(f"[OK] Results saved: {csv_file.name}")

# ============================================================================
# GENERATE HTML REPORT
# ============================================================================
html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>MEAN_REVERS_EXPAND Comparison</title>
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
        .best-results {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .best-card {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-left: 4px solid #28a745;
        }}
        .best-card h3 {{
            margin: 0 0 10px 0;
            color: #333;
            font-size: 14px;
        }}
        .best-value {{
            font-size: 20px;
            font-weight: bold;
            color: #28a745;
        }}
        .best-detail {{
            font-size: 12px;
            color: #666;
        }}
        table {{
            width: 100%;
            background: white;
            border-collapse: collapse;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        th {{
            background: #667eea;
            color: white;
            padding: 10px;
            text-align: left;
            font-size: 12px;
        }}
        td {{
            padding: 8px 10px;
            border-bottom: 1px solid #eee;
            font-size: 11px;
        }}
        tr:hover {{
            background-color: #f8f9fa;
        }}
        .positive {{
            color: #28a745;
            font-weight: bold;
        }}
        .negative {{
            color: #dc3545;
            font-weight: bold;
        }}
        .highlight {{
            background-color: #d4edda !important;
        }}
        .conclusion {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-left: 4px solid #ffc107;
        }}
        .conclusion h3 {{
            margin-top: 0;
            color: #333;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>TRINCHERA - MEAN_REVERS_EXPAND COMPARISON</h1>
        <p>Comparing Entry Distance Performance</p>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>

    <div class="best-results">
        <div class="best-card">
            <h3>BEST TOTAL P&L</h3>
            <div class="best-value">±{best_pnl['mean_revers_expand']:.0f} pts</div>
            <div class="best-detail">${best_pnl['total_pnl']:,.2f}</div>
        </div>
        <div class="best-card">
            <h3>BEST SHARPE RATIO</h3>
            <div class="best-value">±{best_sharpe['mean_revers_expand']:.0f} pts</div>
            <div class="best-detail">{best_sharpe['sharpe_ratio']:.2f}</div>
        </div>
        <div class="best-card">
            <h3>BEST PROFIT FACTOR</h3>
            <div class="best-value">±{best_profit_factor['mean_revers_expand']:.0f} pts</div>
            <div class="best-detail">{best_profit_factor['profit_factor']:.2f}</div>
        </div>
    </div>

    <h2>Full Comparison</h2>
    <table>
        <tr>
            <th>Entry (±pts)</th>
            <th>Total P&L</th>
            <th>Points</th>
            <th>Avg/Day</th>
            <th>Avg/Trade</th>
            <th>Max DD</th>
            <th>Trades</th>
            <th>Trades/Day</th>
            <th>WR %</th>
            <th>PF</th>
            <th>Sharpe</th>
            <th>Sortino</th>
            <th>Recovery</th>
        </tr>
"""

for _, row in df_results.iterrows():
    is_best = row['mean_revers_expand'] == best_pnl['mean_revers_expand']
    row_class = 'highlight' if is_best else ''
    pnl_class = 'positive' if row['total_pnl'] >= 0 else 'negative'

    html_content += f"""
        <tr class="{row_class}">
            <td><strong>±{row['mean_revers_expand']:.0f}</strong></td>
            <td class="{pnl_class}">${row['total_pnl']:,.2f}</td>
            <td>{row['points']:.2f}</td>
            <td class="{pnl_class}">${row['avg_daily_pnl']:,.2f}</td>
            <td class="{pnl_class}">${row['avg_trade_pnl']:.2f}</td>
            <td class="negative">${row['max_drawdown']:,.2f}</td>
            <td>{row['total_trades']:,}</td>
            <td>{row['trades_per_day']:.1f}</td>
            <td>{row['win_rate']:.1f}%</td>
            <td>{row['profit_factor']:.2f}</td>
            <td>{row['sharpe_ratio']:.2f}</td>
            <td>{row['sortino_ratio']:.2f}</td>
            <td>{row['recovery_factor']:.2f}</td>
        </tr>
"""

# Calculate differences
diff_pnl = df_results.iloc[0]['total_pnl'] - df_results.iloc[1]['total_pnl']
diff_pct = (diff_pnl / abs(df_results.iloc[1]['total_pnl']) * 100) if df_results.iloc[1]['total_pnl'] != 0 else 0
diff_trades = df_results.iloc[0]['total_trades'] - df_results.iloc[1]['total_trades']

html_content += f"""
    </table>

    <div class="conclusion">
        <h3>ANALYSIS</h3>
        <p><strong>Winner: MEAN_REVERS_EXPAND = ±{best_pnl['mean_revers_expand']:.0f} pts</strong></p>

        <p><strong>Key Findings:</strong></p>
        <ul>
            <li>Best P&L: <span class="positive">${best_pnl['total_pnl']:,.2f}</span> with ±{best_pnl['mean_revers_expand']:.0f} pts entry</li>
            <li>Difference: <span class="positive">${diff_pnl:,.2f}</span> ({diff_pct:+.1f}%) vs second best</li>
            <li>Trade count difference: {int(diff_trades):+,d} trades ({diff_trades/df_results.iloc[1]['total_trades']*100:+.1f}%)</li>
            <li>Best consistency (Sharpe): ±{best_sharpe['mean_revers_expand']:.0f} pts → {best_sharpe['sharpe_ratio']:.2f}</li>
            <li>Best risk-adjusted (Recovery): ±{df_results.loc[df_results['recovery_factor'].idxmax(), 'mean_revers_expand']:.0f} pts → {df_results['recovery_factor'].max():.2f}</li>
        </ul>

        <p><strong>Recommendation:</strong></p>
        <p>Use <strong>MEAN_REVERS_EXPAND = {best_pnl['mean_revers_expand']:.0f}</strong> for maximum profitability.</p>
        <p>Entry distance of ±{best_pnl['mean_revers_expand']:.0f} points provides the best balance of:</p>
        <ul>
            <li>Total profit: ${best_pnl['total_pnl']:,.2f}</li>
            <li>Risk management: Recovery factor {best_pnl['recovery_factor']:.2f}</li>
            <li>Trade frequency: {best_pnl['trades_per_day']:.1f} trades/day</li>
        </ul>
    </div>
</body>
</html>
"""

html_file = OUTPUT_DIR / f"comparison_mean_revers_expand_{timestamp}.html"
html_file.write_text(html_content, encoding='utf-8')
print(f"[OK] HTML report saved: {html_file.name}")

# ============================================================================
# CONSOLE SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("COMPARISON SUMMARY")
print("=" * 80)

print(f"\nResults compared: {len(df_results)}")

print(f"\nBest by Total P&L:")
print(f"  +/-{best_pnl['mean_revers_expand']:.0f} pts -> ${best_pnl['total_pnl']:,.2f}")

print(f"\nBest by Sharpe Ratio:")
print(f"  +/-{best_sharpe['mean_revers_expand']:.0f} pts -> {best_sharpe['sharpe_ratio']:.2f}")

print(f"\nBest by Profit Factor:")
print(f"  +/-{best_profit_factor['mean_revers_expand']:.0f} pts -> {best_profit_factor['profit_factor']:.2f}")

print("\n" + "=" * 80)
print("[SUCCESS] Comparison completed!")
print("=" * 80)

# Open HTML report
webbrowser.open('file://' + str(html_file.absolute()))
print(f"\n[OK] Opening comparison report in browser...")
