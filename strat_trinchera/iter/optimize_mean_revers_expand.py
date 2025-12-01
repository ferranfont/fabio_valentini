"""
Optimize MEAN_REVERS_EXPAND Parameter
Tests different values and generates comparison summary report
"""

import pandas as pd
import subprocess
import sys
from pathlib import Path
import shutil
from datetime import datetime
import webbrowser

# ============================================================================
# CONFIGURATION
# ============================================================================
CURRENT_DIR = Path(__file__).resolve().parent
STRAT_DIR = CURRENT_DIR.parent
CONFIG_FILE = STRAT_DIR / "config_trinchera.py"
OUTPUT_DIR = CURRENT_DIR / "optimization_results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Values to test
MEAN_REVERS_EXPAND_VALUES = [8, 10, 12, 14, 15, 16, 18, 20]

print("=" * 80)
print("MEAN_REVERS_EXPAND OPTIMIZATION")
print("=" * 80)
print(f"\nValues to test: {MEAN_REVERS_EXPAND_VALUES}")
print(f"Output directory: {OUTPUT_DIR}")

# ============================================================================
# BACKUP CURRENT CONFIG
# ============================================================================
print("\n" + "=" * 80)
print("BACKING UP CURRENT CONFIG")
print("=" * 80)

backup_file = OUTPUT_DIR / f"config_trinchera_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
shutil.copy2(CONFIG_FILE, backup_file)
print(f"[OK] Config backed up to: {backup_file.name}")

# Read original config
original_config = CONFIG_FILE.read_text(encoding='utf-8')

# ============================================================================
# RUN BATCH PROCESS FOR EACH VALUE
# ============================================================================
print("\n" + "=" * 80)
print("RUNNING BATCH PROCESS FOR EACH VALUE")
print("=" * 80)

results = []
batch_script = CURRENT_DIR / "main_batch_process_all_dates.py"

for value in MEAN_REVERS_EXPAND_VALUES:
    print("\n" + "=" * 80)
    print(f"TESTING MEAN_REVERS_EXPAND = {value}")
    print("=" * 80)

    # Update config with new value
    import re
    new_config = re.sub(
        r'MEAN_REVERS_EXPAND\s*=\s*\d+',
        f'MEAN_REVERS_EXPAND = {value}',
        original_config
    )
    CONFIG_FILE.write_text(new_config, encoding='utf-8')
    print(f"[OK] Config updated: MEAN_REVERS_EXPAND = {value}")

    # Run batch process
    print(f"\n[INFO] Running batch process...")
    try:
        result = subprocess.run(
            [sys.executable, str(batch_script)],
            cwd=str(CURRENT_DIR),
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )

        if result.returncode == 0:
            print(f"[OK] Batch process completed for value {value}")

            # Read the latest aggregate results
            aggregate_script = CURRENT_DIR / "aggregate_results.py"
            agg_result = subprocess.run(
                [sys.executable, str(aggregate_script)],
                cwd=str(CURRENT_DIR),
                capture_output=True,
                text=True
            )

            if agg_result.returncode == 0:
                # Find the latest stats file
                output_summary_dir = CURRENT_DIR / "iter summary outputs"
                stats_files = sorted(output_summary_dir.glob("stats_by_date_*.csv"))

                if stats_files:
                    latest_stats = stats_files[-1]
                    df_stats = pd.read_csv(latest_stats, sep=';', decimal=',')

                    # Calculate summary metrics
                    total_pnl = df_stats['total_pnl'].sum()
                    avg_daily_pnl = df_stats['total_pnl'].mean()
                    std_daily_pnl = df_stats['total_pnl'].std()
                    sharpe = (avg_daily_pnl / std_daily_pnl) if std_daily_pnl > 0 else 0

                    # Count profitable days
                    profitable_days = len(df_stats[df_stats['total_pnl'] > 0])
                    total_days = len(df_stats)
                    profit_days_pct = (profitable_days / total_days * 100) if total_days > 0 else 0

                    # Win rate
                    total_trades = df_stats['trades'].sum()
                    total_winners = df_stats['winners'].sum()
                    win_rate = (total_winners / total_trades * 100) if total_trades > 0 else 0

                    results.append({
                        'mean_revers_expand': value,
                        'total_pnl': total_pnl,
                        'avg_daily_pnl': avg_daily_pnl,
                        'sharpe_ratio': sharpe,
                        'total_trades': int(total_trades),
                        'win_rate': win_rate,
                        'profitable_days': profitable_days,
                        'total_days': total_days,
                        'profit_days_pct': profit_days_pct,
                        'status': 'SUCCESS'
                    })

                    print(f"[OK] Results collected: ${total_pnl:,.2f} | Sharpe: {sharpe:.2f} | WR: {win_rate:.1f}%")
                else:
                    print(f"[ERROR] No stats file found")
                    results.append({
                        'mean_revers_expand': value,
                        'status': 'NO_STATS'
                    })
            else:
                print(f"[ERROR] Aggregate failed")
                results.append({
                    'mean_revers_expand': value,
                    'status': 'AGG_FAILED'
                })
        else:
            print(f"[ERROR] Batch process failed")
            results.append({
                'mean_revers_expand': value,
                'status': 'BATCH_FAILED'
            })

    except subprocess.TimeoutExpired:
        print(f"[ERROR] Timeout")
        results.append({
            'mean_revers_expand': value,
            'status': 'TIMEOUT'
        })
    except Exception as e:
        print(f"[ERROR] {e}")
        results.append({
            'mean_revers_expand': value,
            'status': f'ERROR: {e}'
        })

# ============================================================================
# RESTORE ORIGINAL CONFIG
# ============================================================================
print("\n" + "=" * 80)
print("RESTORING ORIGINAL CONFIG")
print("=" * 80)

CONFIG_FILE.write_text(original_config, encoding='utf-8')
print(f"[OK] Original config restored")

# ============================================================================
# GENERATE COMPARISON REPORT
# ============================================================================
print("\n" + "=" * 80)
print("GENERATING COMPARISON REPORT")
print("=" * 80)

# Convert to DataFrame
df_results = pd.DataFrame(results)

# Filter only successful runs
df_success = df_results[df_results['status'] == 'SUCCESS'].copy()

if len(df_success) == 0:
    print("[ERROR] No successful runs to compare!")
    exit(1)

# Sort by total P&L descending
df_success = df_success.sort_values('total_pnl', ascending=False)

# Find best values
best_pnl = df_success.iloc[0]
best_sharpe = df_success.loc[df_success['sharpe_ratio'].idxmax()]
best_win_rate = df_success.loc[df_success['win_rate'].idxmax()]

# Save CSV
csv_file = OUTPUT_DIR / f"optimization_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
df_success.to_csv(csv_file, sep=';', decimal=',', index=False)
print(f"[OK] Results saved: {csv_file.name}")

# Generate HTML report
html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>MEAN_REVERS_EXPAND Optimization Results</title>
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
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
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
            font-size: 16px;
        }}
        .best-value {{
            font-size: 24px;
            font-weight: bold;
            color: #28a745;
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
    </style>
</head>
<body>
    <div class="header">
        <h1>MEAN_REVERS_EXPAND OPTIMIZATION RESULTS</h1>
        <p>Testing values: {', '.join(map(str, MEAN_REVERS_EXPAND_VALUES))}</p>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>

    <div class="best-results">
        <div class="best-card">
            <h3>BEST PROFIT</h3>
            <div class="best-value">{best_pnl['mean_revers_expand']:.0f} pts</div>
            <div>${best_pnl['total_pnl']:,.2f}</div>
        </div>
        <div class="best-card">
            <h3>BEST SHARPE RATIO</h3>
            <div class="best-value">{best_sharpe['mean_revers_expand']:.0f} pts</div>
            <div>{best_sharpe['sharpe_ratio']:.2f}</div>
        </div>
        <div class="best-card">
            <h3>BEST WIN RATE</h3>
            <div class="best-value">{best_win_rate['mean_revers_expand']:.0f} pts</div>
            <div>{best_win_rate['win_rate']:.1f}%</div>
        </div>
    </div>

    <h2>Comparison Table</h2>
    <table>
        <tr>
            <th>Entry (±pts)</th>
            <th>Total P&L</th>
            <th>Avg Daily P&L</th>
            <th>Sharpe Ratio</th>
            <th>Total Trades</th>
            <th>Win Rate</th>
            <th>Profit Days</th>
            <th>Profit Days %</th>
        </tr>
"""

for _, row in df_success.iterrows():
    is_best = row['mean_revers_expand'] == best_pnl['mean_revers_expand']
    row_class = 'highlight' if is_best else ''
    pnl_class = 'positive' if row['total_pnl'] >= 0 else 'negative'

    html_content += f"""
        <tr class="{row_class}">
            <td><strong>{row['mean_revers_expand']:.0f}</strong></td>
            <td class="{pnl_class}">${row['total_pnl']:,.2f}</td>
            <td class="{pnl_class}">${row['avg_daily_pnl']:,.2f}</td>
            <td>{row['sharpe_ratio']:.2f}</td>
            <td>{row['total_trades']:,}</td>
            <td>{row['win_rate']:.1f}%</td>
            <td>{row['profitable_days']}/{row['total_days']}</td>
            <td>{row['profit_days_pct']:.1f}%</td>
        </tr>
"""

html_content += """
    </table>
</body>
</html>
"""

html_file = OUTPUT_DIR / f"optimization_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
html_file.write_text(html_content, encoding='utf-8')
print(f"[OK] HTML report saved: {html_file.name}")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("OPTIMIZATION SUMMARY")
print("=" * 80)

print(f"\nBest by Total P&L:")
print(f"  MEAN_REVERS_EXPAND = {best_pnl['mean_revers_expand']:.0f} pts → ${best_pnl['total_pnl']:,.2f}")

print(f"\nBest by Sharpe Ratio:")
print(f"  MEAN_REVERS_EXPAND = {best_sharpe['mean_revers_expand']:.0f} pts → {best_sharpe['sharpe_ratio']:.2f}")

print(f"\nBest by Win Rate:")
print(f"  MEAN_REVERS_EXPAND = {best_win_rate['mean_revers_expand']:.0f} pts → {best_win_rate['win_rate']:.1f}%")

print("\n" + "=" * 80)
print("[SUCCESS] Optimization completed!")
print("=" * 80)

# Open HTML report
webbrowser.open('file://' + str(html_file.absolute()))
print(f"\n[OK] Opening report in browser...")
