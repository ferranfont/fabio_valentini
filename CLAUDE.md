# CLAUDE.md - Fabio Valentini Project

## Project Overview
This is an advanced ES futures order flow analysis toolkit featuring:
- Footprint charts with volume intensity gradients
- Time & Sales tick-by-tick visualization
- Multi-timeframe analysis
- Interactive Plotly charts

## Data Sources

### Available Data Files
The project uses tick data and time series from the `data/` folder:
- `time_and_sales.csv` - Tick-by-tick data with BID/ASK/Volume
- `es_1D_data.csv` - Daily ES data (207 KB)
- `es_1min_data_2015_2025.csv` - 1-minute ES data (358 MB)

### Data Format
Time & sales CSV format:
```
Timestamp;Precio;Volumen;Lado;Bid;Ask
2025-10-09 06:00:20.592;6797,5;1;ASK;6797,25;6797,5
```

## Key Visualization Scripts

### 1. Footprint Chart (`plot_footprint_chart.py`)
- Aggregates volume by price level
- Shows BID (red) and ASK (green) with intensity gradients
- Alpha transparency based on volume (0.45 to 0.85)
- Configurable via `n_temp` variable (number of rows to analyze)

### 2. Time & Sales (`plot_time_and_sales.py`)
- Table-style visualization of tick data
- Color-coded: ASK (green), BID (red)
- Displays: Time, Price, Volume, Side, Bid, Ask
- Configurable via `limit_rows` variable

### 3. Tick Data Charts (`plot_tick_data.py`)
- Resamples tick data to candlestick charts
- Volume bars with color intensity
- Multiple timeframe support

## Configuration (`config.py`)
Central configuration for:
- Chart dimensions (CHART_WIDTH, CHART_HEIGHT)
- Data directories (DATA_DIR)
- Symbol settings (SYMBOL = 'ES')

## Important Notes
- All timestamps are in Madrid time (CET/CEST)
- CSV files use European format (semicolon separator, comma decimal)
- Charts are saved to `charts/` directory and auto-open in browser
- No emojis in console output (Windows compatibility)

## Development Guidelines
- Always use the local `data/` folder for data sources
- Maintain European CSV format (sep=';', decimal=',')
- Keep chart width minimal for footprint (400px)
- Use alpha gradients for volume intensity visualization
