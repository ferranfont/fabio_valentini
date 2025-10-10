# Fabio Valentini - ES Futures Analysis

Advanced trading analysis toolkit for ES (E-mini S&P 500) futures data with footprint charts and time & sales visualization.

## Installation

```bash
pip install -r requirements.txt
```

## Data Source

The script reads 1-minute ES futures data from the local `data/` folder:
- `es_1min_data_2015_2025.csv` - High frequency ES data (2015-2025)
- `es_1D_data.csv` - Daily ES data

## Features

- **Data Processing**: Loads and processes ES futures tick data and time & sales
- **Timeframe Conversion**: Resamples 1-minute data to daily candles
- **Footprint Charts**: Volume profile visualization with BID/ASK intensity gradients
- **Time & Sales**: Real-time tick data visualization with price levels
- **Visualization**: Creates price and volume charts with interactive Plotly charts
- **Technical Analysis**: Advanced order flow analysis for ES futures

## Usage

Run the main analysis:

```bash
python main.py
```

## Output

The script generates:
- Daily OHLCV data from 1-minute bars
- Price and volume charts
- Console output showing data characteristics

## Project Structure

```
fabio_valentini/
├── data/                           # Local data files
│   ├── time_and_sales.csv         # Tick data with BID/ASK
│   ├── es_1min_data_2015_2025.csv
│   └── es_1D_data.csv
├── utils/                          # Utility scripts
│   ├── read_tick_data.py          # Tick data reader
│   └── clean_data_*.py            # Data cleaning utilities
├── plot_footprint_chart.py        # Footprint chart visualization
├── plot_time_and_sales.py         # Time & sales display
├── plot_tick_data.py              # Tick data charting
├── main.py                        # Main analysis script
├── config.py                      # Configuration settings
└── README.md                      # This file
```
