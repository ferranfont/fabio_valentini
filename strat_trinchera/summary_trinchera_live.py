import os

# ======================================================================================
# FIX: Change to script directory to avoid numpy import issues
# ======================================================================================
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# Now safe to import pandas/numpy
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import glob
from datetime import datetime
import numpy as np
import webbrowser

# ======================================================================================
# CONFIGURATION
# ======================================================================================
BASE_DIR = script_dir
OUTPUTS_DIR = os.path.join(BASE_DIR, 'outputs')
# ======================================================================================
# HELPER FUNCTIONS
# ======================================================================================
def get_latest_csv(directory):
    """Finds the most recent tracking_record_live CSV file."""
    search_pattern = os.path.join(directory, "tracking_record_live_*.csv")
    files = glob.glob(search_pattern)
    if not files:
        return None
    latest_file = max(files, key=os.path.getmtime)
    return latest_file
def clean_and_read_csv(filepath):
    """
    Lee el CSV intentando reparar el problema de comas decimales (Ej: '25600, 75' -> '25600.75').
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        if not lines:
            return pd.DataFrame()
        # Limpiamos header
        header = lines[0].strip().split(',')
        header = [h.strip() for h in header] 
        expected_cols = len(header)
        
        data = []
        for line in lines[1:]:
            parts = line.strip().split(',')
            
            # Fusión heurística si hay comas extra (decimales europeos)
            if len(parts) > expected_cols:
                new_parts = []
                skip_next = False
                for j in range(len(parts)):
                    if skip_next:
                        skip_next = False
                        continue
                    val = parts[j].strip()
                    if j < len(parts) - 1:
                        next_val = parts[j+1].strip()
                        # Si parecen ser parte de un decimal partido
                        if val.replace('-','').isdigit() and next_val.isdigit():
                            val = f"{val}.{next_val}"
                            skip_next = True
                    new_parts.append(val)
                parts = new_parts
            parts = [p.strip() for p in parts]
            
            # Ajuste final de longitud
            if len(parts) > expected_cols: parts = parts[:expected_cols]
            elif len(parts) < expected_cols: parts += [''] * (expected_cols - len(parts))
                
            data.append(parts)
        df = pd.DataFrame(data, columns=header)
        
        # Conversión Numérica
        # Intentamos convertir todo lo que parezca número
        cols_to_check = ['price', 'quantity', 'pnl', 'duration_sec', 'market_price']
        for col in cols_to_check:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                
        return df
    except Exception as e:
        print(f"[ERROR] Reading CSV failed: {e}")
        return pd.DataFrame()
def calculate_metrics(df_trades):
    if df_trades.empty: return None
    def safe_div(n, d): return n / d if d != 0 else 0
    total_trades = len(df_trades)
    
    # PnL Stats
    df_trades['cumulative_pnl'] = df_trades['pnl'].cumsum()
    net_profit = df_trades['pnl'].sum()
    
    winners = df_trades[df_trades['pnl'] > 0]
    losers = df_trades[df_trades['pnl'] <= 0]
    
    num_winners = len(winners)
    num_losers = len(losers)
    win_rate = safe_div(num_winners, total_trades) * 100
    
    gross_profit = winners['pnl'].sum()
    gross_loss = losers['pnl'].sum()
    
    avg_profit = df_trades['pnl'].mean()
    median_profit = df_trades['pnl'].median()
    if len(df_trades) > 1:
        std_profit = df_trades['pnl'].std()
    else:
        std_profit = 0
    
    avg_winner = winners['pnl'].mean() if not winners.empty else 0
    avg_loser = losers['pnl'].mean() if not losers.empty else 0
    
    largest_winner = winners['pnl'].max() if not winners.empty else 0
    largest_loser = losers['pnl'].min() if not losers.empty else 0
    
    profit_factor = safe_div(gross_profit, abs(gross_loss))
    expectancy = avg_profit
    
    # Drawdown
    cum_max = df_trades['cumulative_pnl'].cummax()
    drawdown = df_trades['cumulative_pnl'] - cum_max
    max_drawdown = drawdown.min()
    
    recovery_factor = safe_div(net_profit, abs(max_drawdown))
    
    # Streaks
    results = np.where(df_trades['pnl'] > 0, 1, -1)
    if len(results) > 0:
        change_points = np.diff(np.concatenate(([0], results))) != 0
        indices = np.where(change_points)[0]
        run_lengths = np.diff(np.concatenate((indices, [len(results)])))
        run_values = results[indices]
        max_win_streak = run_lengths[run_values == 1].max() if np.any(run_values == 1) else 0
        max_lose_streak = run_lengths[run_values == -1].max() if np.any(run_values == -1) else 0
    else:
        max_win_streak = 0
        max_lose_streak = 0
    # Duration
    avg_duration_min = (df_trades['duration_sec'].mean() / 60) if 'duration_sec' in df_trades else 0
    median_duration_min = (df_trades['duration_sec'].median() / 60) if 'duration_sec' in df_trades else 0
    # Breakdown
    long_trades = df_trades[df_trades['action'].str.contains('SELL', case=False, na=False)]
    short_trades = df_trades[df_trades['action'].str.contains('BUY', case=False, na=False)]
    
    num_longs = len(long_trades)
    num_shorts = len(short_trades)
    long_profit = long_trades['pnl'].sum()
    short_profit = short_trades['pnl'].sum()
    target_exits = len(df_trades[df_trades['exit_reason'] == 'TARGET']) if 'exit_reason' in df_trades else 0
    stop_exits = len(df_trades[df_trades['exit_reason'] == 'STOP']) if 'exit_reason' in df_trades else 0
    return {
        'total_trades': total_trades,
        'start_date': df_trades['timestamp'].min(),
        'end_date': df_trades['timestamp'].max(),
        'avg_duration': avg_duration_min,
        'median_duration': median_duration_min,
        'net_profit': net_profit,
        'avg_profit': avg_profit,
        'median_profit': median_profit,
        'std_profit': std_profit,
        'profit_factor': profit_factor,
        'expectancy': expectancy,
        'win_rate': win_rate,
        'num_winners': num_winners,
        'num_losers': num_losers,
        'gross_profit': gross_profit,
        'gross_loss': gross_loss,
        'avg_winner': avg_winner,
        'avg_loser': avg_loser,
        'largest_winner': largest_winner,
        'largest_loser': largest_loser,
        'max_drawdown': max_drawdown,
        'recovery_factor': recovery_factor,
        'max_win_streak': max_win_streak,
        'max_lose_streak': max_lose_streak,
        'target_exits': target_exits,
        'stop_exits': stop_exits,
        'num_longs': num_longs,
        'long_profit': long_profit,
        'num_shorts': num_shorts,
        'short_profit': short_profit
    }, df_trades
def generate_html_report(metrics, df_trades, filename):
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.1, 
                        row_heights=[0.5, 0.25, 0.25],
                        subplot_titles=("Equity Curve", "Profit per Trade", "Drawdown"))
    # Equity
    fig.add_trace(go.Scatter(x=df_trades['timestamp'], y=df_trades['cumulative_pnl'],
                             mode='lines', name='Equity', fill='tozeroy', 
                             line=dict(color='#2ecc71', width=2),
                             fillcolor='rgba(46, 204, 113, 0.2)'), row=1, col=1)
    # P/L
    colors = ['#2ecc71' if v > 0 else '#e74c3c' for v in df_trades['pnl']]
    fig.add_trace(go.Bar(x=df_trades['timestamp'], y=df_trades['pnl'],
                         name='P/L', marker_color=colors), row=2, col=1)
    # Drawdown
    cum_max = df_trades['cumulative_pnl'].cummax()
    drawdown = df_trades['cumulative_pnl'] - cum_max
    fig.add_trace(go.Scatter(x=df_trades['timestamp'], y=drawdown,
                             mode='lines', name='Drawdown', fill='tozeroy',
                             line=dict(color='#e74c3c', width=1),
                             fillcolor='rgba(231, 76, 60, 0.2)'), row=3, col=1)
    fig.update_layout(height=800, template='plotly_white', showlegend=False,
                      title_text=f"Performance for {os.path.basename(filename)}")
    
    plot_html = fig.to_html(full_html=False, include_plotlyjs='cdn')
    # Formatting helpers
    def currency(val): return f"${val:,.2f}"
    def num(val, dec=2): return f"{val:,.{dec}f}"
    def percent(val): return f"{val:.1f}%"
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Trinchera Live Report</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f6f9; margin: 0; padding: 20px; }}
            .container {{ max_width: 1200px; margin: 0 auto; background: white; box-shadow: 0 0 15px rgba(0,0,0,0.1); padding: 25px; border-radius: 8px; }}
            h1, h2 {{ text-align: center; color: #2c3e50; }}
            .header-info {{ text-align: center; margin-bottom: 30px; color: #7f8c8d; }}
            
            .grid-container {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 30px; }}
            .card {{ border: 1px solid #e0e0e0; border-radius: 5px; overflow: hidden; }}
            .card-header {{ background-color: #3498db; color: white; padding: 10px 15px; font-weight: bold; text-transform: uppercase; font-size: 0.9em; }}
            .card-body {{ padding: 15px; }}
            
            .metric-row {{ display: flex; justifies-content: space-between; margin-bottom: 8px; border-bottom: 1px solid #f0f0f0; padding-bottom: 5px; }}
            .metric-row:last-child {{ border-bottom: none; }}
            .metric-label {{ color: #7f8c8d; font-size: 0.9em; }}
            .metric-value {{ font-weight: bold; color: #2c3e50; text-align: right; margin-left: auto; }}
            
            .pos {{ color: #27ae60; }}
            .neg {{ color: #c0392b; }}
            
            .plot-container {{ margin-top: 30px; border: 1px solid #ddd; padding: 10px; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>TRINCHERA LIVE STRATEGY REPORT</h1>
            <div class="header-info">File: {os.path.basename(filename)}</div>
            <div class="grid-container">
                <!-- GENERAL -->
                <div class="card">
                    <div class="card-header">General</div>
                    <div class="card-body">
                        <div class="metric-row"><span class="metric-label">Total Trades</span><span class="metric-value">{metrics['total_trades']}</span></div>
                        <div class="metric-row"><span class="metric-label">Avg Duration</span><span class="metric-value">{num(metrics['avg_duration'])} min</span></div>
                        <div class="metric-row"><span class="metric-label">Median Duration</span><span class="metric-value">{num(metrics['median_duration'])} min</span></div>
                    </div>
                </div>
                <!-- PERFORMANCE -->
                <div class="card">
                    <div class="card-header">Performance</div>
                    <div class="card-body">
                        <div class="metric-row"><span class="metric-label">Total Profit</span><span class="metric-value { 'pos' if metrics['net_profit'] >=0 else 'neg' }">{currency(metrics['net_profit'])}</span></div>
                        <div class="metric-row"><span class="metric-label">Avg Profit</span><span class="metric-value { 'pos' if metrics['avg_profit'] >=0 else 'neg' }">{currency(metrics['avg_profit'])}</span></div>
                        <div class="metric-row"><span class="metric-label">Profit Factor</span><span class="metric-value">{num(metrics['profit_factor'])}</span></div>
                    </div>
                </div>
                <!-- WIN/LOSS -->
                <div class="card">
                    <div class="card-header">Win / Loss</div>
                    <div class="card-body">
                        <div class="metric-row"><span class="metric-label">Win Rate</span><span class="metric-value">{percent(metrics['win_rate'])}</span></div>
                        <div class="metric-row"><span class="metric-label">Max Drawdown</span><span class="metric-value neg">{currency(metrics['max_drawdown'])}</span></div>
                    </div>
                </div>
                 <!-- BREAKDOWN -->
                 <div class="card">
                    <div class="card-header">Breakdown</div>
                    <div class="card-body">
                        <div class="metric-row"><span class="metric-label">Long Profit</span><span class="metric-value">{currency(metrics['long_profit'])}</span></div>
                        <div class="metric-row"><span class="metric-label">Short Profit</span><span class="metric-value">{currency(metrics['short_profit'])}</span></div>
                    </div>
                </div>
            </div>
            <div class="plot-container">
                {plot_html}
            </div>
        </div>
    </body>
    </html>
    """
    
    output_path = filename.replace('.csv', '_report.html')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"\n[SUCCESS] Report generated: {output_path}")
    return output_path
# ======================================================================================
# MAIN
# ======================================================================================
def main():
    print("--- TRINCHERA LIVE STRATEGY SUMMARY ---")
    
    if not os.path.exists(OUTPUTS_DIR):
        print(f"[ERROR] Outputs directory not found: {OUTPUTS_DIR}")
        return
    latest_csv = get_latest_csv(OUTPUTS_DIR)
    if not latest_csv:
        print(f"[ERROR] No csv files found.")
        return
    print(f"[INFO] Analyizing file: {latest_csv}")
    
    # NEW ROBUST READ METHOD
    df = clean_and_read_csv(latest_csv)
    
    if df.empty or 'event_type' not in df.columns:
        print("[ERROR] CSV invalid or empty.")
        return
    df_closed = df[df['event_type'] == 'TRADE_CLOSED'].copy()
    
    # Timestamp parsing
    df_closed['timestamp'] = pd.to_datetime(df_closed['timestamp'], errors='coerce')
    df_closed = df_closed.dropna(subset=['timestamp']).sort_values('timestamp')
    
    print(f"[INFO] Found {len(df_closed)} closed trades.")
    
    result = calculate_metrics(df_closed)
    if result is None:
        print("[WARNING] No closed trades found yet.")
        return
        
    metrics, df_processed = result
    print(f"\n[SUMMARY]")
    print(f"Total Trades: {metrics['total_trades']}")
    print(f"Net Profit:   ${metrics['net_profit']:.2f}")
    report_file = generate_html_report(metrics, df_processed, latest_csv)
    try:
        webbrowser.open('file://' + report_file)
    except:
        pass
if __name__ == "__main__":
    main()