import pandas as pd
import numpy as np
import webbrowser
import plotly.graph_objects as go
from pathlib import Path

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
TRADES_FILE = 'outputs/trading_record_strat_fabio_vol_not_fake.csv'
OUTPUT_HTML = 'charts/summary_report_vol_not_fake.html'

# ==============================================================================

# Function to calculate Maximum Drawdown (MDD)
def calculate_mdd(equity_curve):
    """Calculates the Maximum Drawdown from an equity curve (cumulative profits)."""
    if equity_curve.empty:
        return 0.0

    # Calculate the running maximum (peak)
    peak = equity_curve.cummax()
    # Calculate the drawdown from the peak
    drawdown = (peak - equity_curve)
    # The Maximum Drawdown is the largest value in the drawdown series
    mdd = drawdown.max()
    return mdd

# === 1. Load data ===

# Load the trades CSV
df = pd.read_csv(TRADES_FILE, sep=';', decimal=',')

# Specify the profit column
profit_col = 'profit_dollars'

if profit_col not in df.columns:
    raise ValueError(f"Required profit column '{profit_col}' not found. Available columns: {list(df.columns)}")

profits = df[profit_col].astype(float)


# === 2. Compute statistics ===
wins = profits[profits > 0]
losses = profits[profits < 0]
n_trades = len(profits)
n_wins = len(wins)
n_losses = len(losses)
win_rate = (n_wins / n_trades) * 100 if n_trades > 0 else 0
avg_profit = profits.mean()
avg_win = wins.mean() if len(wins) > 0 else 0
avg_loss = losses.mean() if len(losses) > 0 else 0

# Profit Factor
if losses.sum() == 0:
    profit_factor = np.inf
else:
    profit_factor = abs(wins.sum() / losses.sum())

expectancy = (win_rate/100 * avg_win) + ((1 - win_rate/100) * avg_loss)
equity_curve = profits.cumsum()
total_profit = equity_curve.iloc[-1] if not equity_curve.empty else 0

# Risk Ratios
risk_free_rate = 0.0

# Sharpe Ratio (uses total profit STD for normalization)
std_dev = profits.std()
sharpe_ratio = (
    (profits.mean() - risk_free_rate) / std_dev * np.sqrt(len(profits))
    if std_dev != 0 else 0
)

# Sortino Ratio (uses negative profit STD for normalization)
neg_profits = profits[profits < 0]
neg_std = neg_profits.std()
sortino_ratio = (
    (profits.mean() - risk_free_rate) / neg_std * np.sqrt(len(profits))
    if neg_std and neg_std != 0 else 0
)

# Maximum Drawdown (MDD)
mdd = calculate_mdd(equity_curve)

# Calmar Ratio (Annualized Return / Max Drawdown)
annualized_return_proxy = total_profit / n_trades * 252 # Use 252 for trading days
calmar_ratio = (
    annualized_return_proxy / mdd
    if mdd > 0 else np.inf
)

# === 3. Build summary table (Transposed) ===
summary_data = {
    "Metric": [
        "💰 Total Profit", "📈 Total Trades", "✅ Wins", "❌ Losses",
        "🏆 Win %", "💵 Avg Profit", "⬆️ Avg Win", "⬇️ Avg Loss",
        "⚖️ Profit Factor", "🔮 Expectancy",
        "⛰️ Max Drawdown", "🎯 Sharpe Ratio", "🛡️ Sortino Ratio", "🔥 Calmar Ratio"
    ],
    "Value": [
        f"${total_profit:.2f}",
        f"{n_trades}",
        f"{n_wins}",
        f"{n_losses}",
        f"{win_rate:.2f}%",
        f"${avg_profit:.2f}",
        f"${avg_win:.2f}",
        f"${avg_loss:.2f}",
        f"{profit_factor:.2f}" if profit_factor != np.inf else "Inf",
        f"${expectancy:.2f}",
        f"${mdd:.2f}",
        f"{sharpe_ratio:.2f}",
        f"{sortino_ratio:.2f}",
        f"{calmar_ratio:.2f}" if calmar_ratio != np.inf else "Inf"
    ]
}

summary_df = pd.DataFrame(summary_data)

# === 4. Create HTML table and Title ===
# Detectar el modo usado (MODO_1, MODO_2, MODO_3)
filter_mode = df['filter_mode'].iloc[0] if 'filter_mode' in df.columns else 'MODO_1'
table_title = f"Summary - {filter_mode} (NO FAKE)"

fig = go.Figure(
    data=[
        go.Table(
            columnorder=[1, 2],
            columnwidth=[60, 40],

            header=dict(
                values=list(summary_df.columns),
                fill_color='#2c3e50', # Dark blue/gray header
                font=dict(color='white', size=14),
                align='left'
            ),
            cells=dict(
                values=[summary_df[col] for col in summary_df.columns],
                # Alternating row colors for better readability
                fill_color=[['#ecf0f1', '#bdc3c7'] * (len(summary_df) // 2 + 1)], # Light gray / lighter gray
                font=dict(color='#34495e', size=12), # Dark text
                align='left'
            )
        )
    ]
)

new_width = 380

fig.update_layout(
    title={
        'text': table_title,
        'y':0.95,
        'x':0.5,
        'xanchor': 'center',
        'yanchor': 'top',
        'font': dict(size=14, color='#2980b9') # Blue title
    },
    width=new_width,
    margin=dict(l=20, r=20, t=60, b=50),
    paper_bgcolor='white'
)


fig.write_html(str(OUTPUT_HTML), auto_open=False)

# === 5. Open summary in Chrome ===
try:
    # Attempt to open with the system's preferred browser
    webbrowser.open_new_tab(str(Path(OUTPUT_HTML).resolve()))
except webbrowser.Error:
    print("Could not open the report automatically. Please check summary report file.")

# === 6. Call the equity curve plot script ===
print(f"\nSummary report generated and opened.")
print(f"\n{'='*70}")
print("GENERATING EQUITY CURVE AND DISTRIBUTION CHARTS")
print('='*70)

# Import plot_backtest_results functions
import sys
sys.path.append(str(Path(__file__).parent))
from plot_backtest_results import load_trades, create_equity_curve, create_distribution_charts, print_summary as print_detailed_summary

try:
    # Load trades data
    df_trades = load_trades(TRADES_FILE)

    # Print detailed summary
    print_detailed_summary(df_trades)

    # Create equity curve chart
    print(f"\nCreating equity curve chart...")
    fig_equity = create_equity_curve(df_trades)
    equity_path = Path("charts/backtest_results_volume_equity.html")
    fig_equity.write_html(str(equity_path))
    print(f"  Saved: {equity_path}")

    # Create distribution charts
    print(f"Creating distribution charts...")
    fig_dist = create_distribution_charts(df_trades)
    dist_path = Path("charts/backtest_results_volume_distributions.html")
    fig_dist.write_html(str(dist_path))
    print(f"  Saved: {dist_path}")

    # Open equity chart in browser
    print("\nOpening equity curve in browser...")
    webbrowser.open(str(equity_path.resolve()))

    print("\nAll reports generated successfully!")
    print(f"  - Summary: {OUTPUT_HTML}")
    print(f"  - Equity Curve: {equity_path}")
    print(f"  - Distributions: {dist_path}")

except Exception as e:
    print(f"\nError generating backtest charts: {e}")
    print("Summary report was generated successfully, but backtest charts failed.")
    print("You can run 'python strat_OM_2/plot_backtest_results.py' manually.")
