# Path Fix - Strategies Folder

## Problem Solved
After moving strategy folders inside `strategies/`, scripts couldn't find `data/`, `outputs/`, and `charts/` folders because they used relative paths.

## Solution Implemented
Created a **path helper system** that dynamically finds the project root and constructs absolute paths.

---

## Files Modified

### Helper Module (NEW)
- **`strategies/path_helper.py`**: Central path management module

### Updated Scripts in strat_OM_1:
1. ✅ `strat_fabio_ATR.py` - Main strategy
2. ✅ `summary.py` - Performance analysis
3. ✅ `plot_trades_chart.py` - Trade visualization
4. ✅ `strat_fabio_window.py` - Window-based strategy (corrected look-ahead bias)
5. ✅ `plot_backtest_results.py` - Results visualization
6. ✅ `compare_strategies.py` - Strategy comparison tool

### Updated Scripts in strat_OM_2:
1. ✅ `strat_fabio_only_volume.py` - Volume-based strategy
2. ✅ `summary.py` - Performance analysis
3. ✅ `plot_trades_chart.py` - Trade visualization
4. ✅ `plot_backtest_results.py` - Results visualization

### Updated Scripts in strat_OM_3:
1. ✅ `strat_fabio_vol_not_fake.py` - Volume strategy (not fake)
2. ✅ `summary.py` - Performance analysis
3. ✅ `plot_trades_chart.py` - Trade visualization
4. ✅ `plot_backtest_results.py` - Results visualization

### Updated Scripts in strat_OM_4_absortion:
1. ✅ `main_start.py` - Orchestrator with centralized configuration
2. ✅ `strat_absortion_shape.py` - Tick-driven backtest engine
3. ✅ `plot_trades_chart.py` - Trade visualization
4. ✅ `summary.py` - Performance summary
5. ✅ `plot_backtest_results.py` - Equity charts

---

## How It Works

### Before (Broken):
```python
# This fails when running from strategies/strat_OM_1/
DATA_FILE = 'data/time_and_sales_absorption_NQ.csv'
OUTPUT_FILE = 'outputs/tracking_record.csv'
```

### After (Fixed):
```python
import sys
from pathlib import Path

# Add strategies folder to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from path_helper import get_data_path, get_output_path

# Now works from any location
DATA_FILE = get_data_path('time_and_sales_absorption_NQ.csv')
OUTPUT_FILE = get_output_path('tracking_record.csv')
```

---

## Available Functions

### `get_project_root()`
Returns the absolute path to `fabio_valentini/` folder.

```python
from path_helper import get_project_root
root = get_project_root()
# Returns: D:\PYTHON\ALGOS\fabio_valentini
```

### `get_data_path(filename='')`
Returns absolute path to `data/` folder or specific file.

```python
from path_helper import get_data_path

# Get data folder
data_dir = get_data_path()

# Get specific file
csv_file = get_data_path('time_and_sales_absorption_NQ.csv')
# Returns: D:\PYTHON\ALGOS\fabio_valentini\data\time_and_sales_absorption_NQ.csv
```

### `get_output_path(filename='')`
Returns absolute path to `outputs/` folder or specific file.
Creates folder if it doesn't exist.

```python
from path_helper import get_output_path

output_file = get_output_path('tracking_record.csv')
# Returns: D:\PYTHON\ALGOS\fabio_valentini\outputs\tracking_record.csv
```

### `get_charts_path(filename='')`
Returns absolute path to `charts/` folder or specific file.
Creates folder if it doesn't exist.

```python
from path_helper import get_charts_path

html_file = get_charts_path('trades_visualization.html')
# Returns: D:\PYTHON\ALGOS\fabio_valentini\charts\trades_visualization.html
```

### `get_config_path()`
Returns absolute path to `config.py`.

```python
from path_helper import get_config_path
config = get_config_path()
```

### `setup_project_imports()`
Adds project root to sys.path for imports.

```python
from path_helper import setup_project_imports
setup_project_imports()

# Now you can import from project root
from config import SYMBOL, CHART_WIDTH
```

---

## Usage Examples

### Strategy Script Template
```python
import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Add strategies folder to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from path_helper import get_data_path, get_output_path

# Configuration with dynamic paths
SYMBOL = 'NQ'
DATA_FILE = get_data_path(f'time_and_sales_absorption_{SYMBOL}.csv')
OUTPUT_FILE = get_output_path('tracking_record.csv')

# Rest of your code...
```

### Visualization Script Template
```python
import plotly.graph_objs as go
import sys
from pathlib import Path

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # For config.py
sys.path.insert(0, str(Path(__file__).parent.parent))         # For path_helper.py
from config import CHART_WIDTH, CHART_HEIGHT, SYMBOL
from path_helper import get_data_path, get_charts_path, get_output_path

# Configuration
DATA_FILE = get_data_path(f'time_and_sales_absorption_{SYMBOL}.csv')
TRADES_FILE = get_output_path('tracking_record.csv')
OUTPUT_HTML = get_charts_path('trades_visualization.html')

# Rest of your code...
```

---

## Running Scripts

### ✅ Now works from ANY location:

```bash
# From project root
cd d:/PYTHON/ALGOS/fabio_valentini
python strategies/strat_OM_1/strat_fabio_ATR.py

# From strategies folder
cd strategies
python strat_OM_1/strat_fabio_ATR.py

# From strategy folder
cd strat_OM_1
python strat_fabio_ATR.py

# From anywhere
python d:/PYTHON/ALGOS/fabio_valentini/strategies/strat_OM_1/strat_fabio_ATR.py
```

All will work correctly!

---

## Manual Update Guide

For scripts that still need updating, follow these steps:

### Step 1: Add imports at the top
```python
import sys
from pathlib import Path

# Add strategies folder to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from path_helper import get_data_path, get_output_path, get_charts_path
```

### Step 2: Replace path strings
```python
# BEFORE:
DATA_FILE = 'data/time_and_sales_absorption_NQ.csv'
OUTPUT_FILE = 'outputs/tracking_record.csv'
CHART_FILE = 'charts/trades_chart.html'

# AFTER:
DATA_FILE = get_data_path('time_and_sales_absorption_NQ.csv')
OUTPUT_FILE = get_output_path('tracking_record.csv')
CHART_FILE = get_charts_path('trades_chart.html')
```

### Step 3: For config.py imports
```python
# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import SYMBOL, CHART_WIDTH, CHART_HEIGHT
```

---

## Benefits

1. ✅ **Location independent**: Scripts work from any directory
2. ✅ **No hardcoded paths**: Everything is dynamic
3. ✅ **Auto folder creation**: Creates `outputs/` and `charts/` if missing
4. ✅ **Clean imports**: Easy to import from project root
5. ✅ **Maintainable**: Change project structure without breaking scripts

---

## Testing

To verify a script is updated correctly:

```bash
# Test from different locations
cd d:/PYTHON/ALGOS/fabio_valentini
python strategies/strat_OM_1/strat_fabio_ATR.py

cd strategies/strat_OM_1
python strat_fabio_ATR.py

# Both should work without errors
```

---

## Common Issues

### Issue: `ModuleNotFoundError: No module named 'path_helper'`
**Cause**: Missing sys.path.insert line
**Fix**: Add this at top of script:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from path_helper import get_data_path, get_output_path
```

### Issue: `RuntimeError: Could not find project root`
**Cause**: Script is outside the project folder
**Fix**: Ensure the script is inside `fabio_valentini/` folder structure

### Issue: `ModuleNotFoundError: No module named 'config'`
**Cause**: Project root not in sys.path
**Fix**: Add this line:
```python
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
```

---

## Next Steps

1. ✅ Update remaining scripts in `strat_OM_1/` - COMPLETED
2. ✅ Apply same fix to `strat_OM_2/` - COMPLETED
3. ✅ Apply same fix to `strat_OM_3/` - COMPLETED
4. ✅ Apply same fix to `strat_OM_4_absortion/` - COMPLETED (5 files updated)
5. ⚠️ Update any other scripts outside strategies/ folder if needed

---

## Version History

- **2025-10-24**: Complete path fix implementation
  - Created `path_helper.py` central module
  - Updated ALL scripts in `strat_OM_1/` (6 files)
  - Updated ALL scripts in `strat_OM_2/` (4 files)
  - Updated ALL scripts in `strat_OM_3/` (4 files)
  - Updated ALL scripts in `strat_OM_4_absortion/` (5 files)
  - **Total: 19 Python files updated successfully**
