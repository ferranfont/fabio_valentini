# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OrderFlowCharts is a Python library for visualizing orderflow footprint charts using Plotly. It processes orderflow data (bid/ask sizes at different price levels) and OHLC (candlestick) data to create interactive heatmap-based footprint charts that show market microstructure.

## Running the Code

### Dependencies Installation
```bash
pip install -r requirements.txt
```

Required packages: numpy==1.24.1, pandas==1.5.2, plotly==5.9.0

### Running the Main Example
```bash
python main.py
```

This will generate an interactive orderflow chart from the sample data in the `data/` directory.

## Code Architecture

### Single-Class Design
The entire library is implemented in a single class `OrderFlowChart` located in `OrderFlow/__init__.py`. All visualization logic, data processing, and plotting functionality is contained within this ~469 line file.

### Two Data Input Methods

1. **Raw CSV Data** (via constructor):
   - Requires two CSV files: orderflow data and OHLC data
   - Orderflow data columns: `['bid_size', 'price', 'ask_size', 'identifier']`
   - OHLC data columns: `['open', 'high', 'low', 'close', 'identifier']`
   - Both should have datetime index
   - The `identifier` column links orderflow data to specific candles

2. **Preprocessed JSON Data** (via `from_preprocessed_data` classmethod):
   - Accepts a dictionary with 8 processed datasets: `orderflow`, `labels`, `green_hl`, `red_hl`, `green_oc`, `red_oc`, `orderflow2`, `ohlc`
   - Each dataset includes a `dtypes` dictionary for type preservation
   - See `data/preprocessed_data.json` for format example

### Key Processing Pipeline

The `process_data()` method (OrderFlow/__init__.py:160) orchestrates the entire data transformation:

1. **Identifier Creation**: If no identifier column provided, generates random strings to link orderflow data to candles
2. **Imbalance Calculation** (OrderFlow/__init__.py:60): Computes bid-ask imbalance using `(bid_size - ask_size.shift()) / (bid_size + ask_size.shift())`
3. **Candle Separation**: Splits OHLC data into green (bullish) and red (bearish) candles based on close vs open
4. **Range Processing** (OrderFlow/__init__.py:99): Transforms high-low and open-close ranges for plotting as line segments
5. **Parameter Calculation** (OrderFlow/__init__.py:126): Computes delta, cumulative delta, rate of change, and volume metrics

### Visualization Structure

The `plot()` method (OrderFlow/__init__.py:306) creates a 2-row subplot:
- **Row 1**: Main footprint chart with heatmap showing bid/ask imbalance, candlestick overlays, and volume profile
- **Row 2**: Heatmap showing delta, cumulative delta, ROC, and volume metrics

Uses Plotly's dark theme with custom pan mode, crosshair spikes, and drawing tools enabled.

### Data Granularity

The class automatically detects price granularity (tick size) from the first two rows of orderflow data: `abs(orderflow_data.iloc[0]['price'] - orderflow_data.iloc[1]['price'])` (OrderFlow/__init__.py:42)

## Sample Data

The `data/` directory contains example CSV files:
- `range_candles.csv` / `range_ohlc.csv`: Range-based bar data
- `time_candles.csv` / `time_ohlc.csv`: Time-based bar data
- `preprocessed_data.json`: Pre-processed data ready for `from_preprocessed_data()`

## Key Implementation Details

- **No test suite**: This project has no automated tests
- **No build process**: Direct Python execution, no compilation needed
- **Stateful processing**: The `is_processed` flag tracks whether data has been transformed
- **Type coercion**: Preprocessed data serialization converts all types to strings with dtype metadata for reconstruction
