import pandas as pd
from pathlib import Path
import numpy as np

OUTPUT_DIR = Path(__file__).resolve().parent / "iter summary outputs"
date_folders = sorted([d for d in OUTPUT_DIR.iterdir() if d.is_dir() and d.name.isdigit()])

all_trades = []
for date_folder in date_folders:
    date = date_folder.name
    trades_file = date_folder / f'db_trinchera_TR_{date}.csv'
    if trades_file.exists():
        df = pd.read_csv(trades_file, sep=';', decimal=',', low_memory=False)
        df['date'] = date
        all_trades.append(df)

df_all_trades = pd.concat(all_trades, ignore_index=True)
df_all_trades = df_all_trades.sort_values(['date', 'entry_time'])
df_all_trades['cumulative_pnl'] = df_all_trades['pnl_usd'].cumsum()
df_all_trades['running_max'] = df_all_trades['cumulative_pnl'].cummax()
df_all_trades['drawdown'] = df_all_trades['cumulative_pnl'] - df_all_trades['running_max']

# Check Sortino components
mean_pnl = df_all_trades['pnl_usd'].mean()
downside_returns = df_all_trades[df_all_trades['pnl_usd'] < 0]['pnl_usd']
downside_std = downside_returns.std()

print(f'Mean P&L per trade: ${mean_pnl:.2f}')
print(f'Downside std: ${downside_std:.2f}')
print(f'Sortino (raw): {(mean_pnl / downside_std):.4f}')
print(f'Sortino (annualized): {(mean_pnl / downside_std) * (252 ** 0.5):.2f}')

# Check Ulcer components
print(f'\nDrawdown min: ${df_all_trades["drawdown"].min():,.2f}')
print(f'Drawdown max: ${df_all_trades["drawdown"].max():,.2f}')
print(f'Drawdown mean: ${df_all_trades["drawdown"].mean():,.2f}')
ulcer_squared = (df_all_trades['drawdown'] ** 2).mean()
print(f'Squared drawdown mean: {ulcer_squared:,.2f}')
print(f'Ulcer Index: ${np.sqrt(ulcer_squared):,.2f}')
