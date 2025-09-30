# Data Cleaning Scripts Documentation

## Overview
This folder contains Python scripts to process, clean, and visualize E-mini S&P 500 (ES) futures data at different timeframes.

---

## 📊 Data Granularity Overview

### Most Detailed Data File

**`ES_near_tick_data_27_jul_2025.csv`**

- **Granularity:** Tick-by-tick (every single trade)
- **Records:** ~547,019 ticks
- **Time Coverage:** Single day (July 25, 2025)
- **Resolution:** Highest - each row represents an individual trade or price update

### Most Extensive Time Coverage with High Granularity

**`es_1min_data_2015_2025.csv`**

- **Granularity:** 1-minute candles
- **Records:** ~3,560,671 bars
- **Time Coverage:** 10+ years (2015-2025)
- **Resolution:** Minute-level detail across a decade

### Summary

| Criterion | File | Details |
|-----------|------|---------|
| **Most granular** | `ES_near_tick_data_27_jul_2025.csv` | Tick data (but only 1 day) |
| **Most extensive + granular** | `es_1min_data_2015_2025.csv` | 1-minute data (10 years) |
| **Primary dataset** | `es_1min_data_2015_2025.csv` | Best for both detailed intraday analysis and long-term historical studies |

---

## 📋 Processing Scripts

### 1. **clean_data_and_format_tick_data.py**

**Purpose:** Process tick data and resample to daily candles

**Input File:** `data/ES_near_tick_data_27_jul_2025.csv` (~547K ticks)

**What it does:**

1. **Loads tick data** (lines 22-23):
   - Reads European CSV format (`;` separator, `,` decimal)
   - Assigns column names: `datetime`, `open`, `high`, `low`, `close`, `volume`

2. **Converts datetime format** (lines 29-31):
   - Parses `DD/MM/YYYY HH:MM` format → pandas datetime (UTC)
   - Extracts `date` and `time` components

3. **Sets datetime index** (line 34):
   - Uses `datetime` as DataFrame index for time-series operations

4. **Resamples to daily candles** (lines 42-48):
   - Aggregates tick data → 1D (daily) timeframe
   - `open`: first value of the day
   - `high`: maximum value
   - `low`: minimum value
   - `close`: last value of the day
   - `volume`: sum of all volume

5. **Plots chart** (line 58):
   - Generates line chart (close prices) + volume bars
   - Uses `plot_close_and_volume()` function

**Run command:**
```bash
python utils/clean_data_and_format_tick_data.py
```

**Output:**
- Daily chart HTML file in `charts/` folder
- Browser opens automatically with the chart

---

### 2. **clean_data_minut_format_all_dataframe.py**

**Purpose:** Resample 10 years of minute data to daily candles

**Input File:** `data/es_1min_data_2015_2025.csv` (~3.5M minute bars, 2015-2025)

**What it does:**

1. **Loads minute data** (line 20):
   - Reads full 10-year dataset of 1-minute candles

2. **Normalizes columns** (lines 25-26):
   - Converts column names to lowercase
   - Renames `'volumen'` → `'volume'` for consistency

3. **Formats datetime** (lines 29-30):
   - Converts `date` column to UTC datetime
   - Sets as DataFrame index for resampling

4. **Resamples to daily** (line 33):
   - Aggregates minutes → 1D (daily) timeframe
   - Uses `OHLCV_AGGREGATION` config from `config.py`:
     ```python
     {
         'open': 'first',
         'high': 'max',
         'low': 'min',
         'close': 'last',
         'volume': 'sum'
     }
     ```

5. **Plots long-term chart** (line 42):
   - Generates daily line chart spanning 2015-2025
   - Uses `plot_close_and_volume()` function

**Run command:**
```bash
python utils/clean_data_minut_format_all_dataframe.py
```

**Output:**
- Daily chart HTML file showing 10 years of data
- Browser opens automatically

---

### 3. **clean_data_one_day_data.py**

**Purpose:** Extract and visualize a specific single day from minute data

**Input File:** `data/es_1min_data_2015_2025.csv`

**Configuration:**
- `TARGET_DATE = '2023-03-01'` (line 15) - **Change this to extract different dates**

**What it does:**

1. **Loads full dataset** (line 25):
   - Reads entire 10-year minute data file

2. **Normalizes columns** (lines 30-31):
   - Lowercase column names
   - Renames `'volumen'` → `'volume'`

3. **Filters single day** (lines 37-40):
   - Converts `TARGET_DATE` to datetime range
   - Extracts only records within that 24-hour period
   - Creates filtered DataFrame with ~1,380 minute bars

4. **Saves extracted data** (lines 46-50):
   - Creates new CSV file: `es_1min_data_YYYY_MM_DD.csv`
   - Saves to `data/` folder

5. **Displays statistics** (lines 57-62):
   - Prints daily OHLC values
   - Shows total volume for the day

6. **Plots minute-level chart** (line 67):
   - Generates **candlestick chart** with minute bars
   - X-axis shows time (HH:MM format)
   - Uses `plot_minute_data()` function (specialized for intraday)

**Run command:**
```bash
python utils/clean_data_one_day_data.py
```

**Output:**
- New CSV file: `data/es_1min_data_2023_03_01.csv`
- Candlestick chart HTML in `charts/` folder
- Console statistics for the day
- Browser opens automatically with intraday chart

**To extract a different day:**
Edit line 15 in the script:
```python
TARGET_DATE = '2024-05-15'  # Change to desired date
```

---

## 🔄 Data Flow Summary

| Script | Input | Processing | Output Chart Type | Output File |
|--------|-------|------------|-------------------|-------------|
| `clean_data_and_format_tick_data.py` | Tick data (547K records) | Tick → Daily | Line + Volume | HTML chart |
| `clean_data_minut_format_all_dataframe.py` | 10 years minute data (3.5M records) | Minutes → Daily | Line + Volume | HTML chart |
| `clean_data_one_day_data.py` | 10 years minute data | Filter 1 day → Extract | Candlestick + Volume | CSV + HTML chart |

---

## 📈 Data Hierarchy

```
Tick Data (highest resolution)
    ↓ resample
1-Minute Data
    ↓ resample / extract
Daily Data / Single Day Data
```

---

## 🎨 Visualization Differences

- **Scripts 1 & 2** use `plot_close_and_volume()`:
  - Line chart (close prices only)
  - X-axis: Date format (e.g., "Jan 15 2023")
  - Best for long-term daily trends

- **Script 3** uses `plot_minute_data()`:
  - Candlestick chart (full OHLC bars)
  - X-axis: Time format (e.g., "14:30")
  - Best for intraday minute-by-minute analysis

---

## 💡 Common Use Cases

1. **Analyze tick-level data from a specific day:**
   ```bash
   python utils/clean_data_and_format_tick_data.py
   ```

2. **View 10-year historical daily trends:**
   ```bash
   python utils/clean_data_minut_format_all_dataframe.py
   ```

3. **Study intraday price action for March 1, 2023:**
   ```bash
   python utils/clean_data_one_day_data.py
   ```

4. **Extract data for a new date (e.g., Jan 5, 2024):**
   - Edit `clean_data_one_day_data.py` line 15:
     ```python
     TARGET_DATE = '2024-01-05'
     ```
   - Run: `python utils/clean_data_one_day_data.py`
   - Output: `data/es_1min_data_2024_01_05.csv` + chart