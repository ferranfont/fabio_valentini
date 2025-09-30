# config.py
"""Configuration settings for Perdices ES Futures Analysis"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Project paths
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / 'data'
CHARTS_DIR = PROJECT_ROOT / 'charts'
OUTPUT_DIR = PROJECT_ROOT / 'outputs'

# Data settings
ES_1D_FILE = 'es_1D_data.csv'
ES_1MIN_FILE = 'es_1min_data_2015_2025.csv'
DEFAULT_ES_FILE = 'export_es_2015_formatted.csv'
DEFAULT_DATA_FILE = ES_1MIN_FILE  # Current default

# Trading symbol
SYMBOL = 'ES'

# Chart settings
CHART_WIDTH = 1500
CHART_HEIGHT = 900
CHART_TEMPLATE = 'plotly_white'
DEFAULT_TIMEFRAME = '1D'

# Timeframe settings
RESAMPLE_TIMEFRAME = '1D'  # Daily resampling
VALID_TIMEFRAMES = ['1min', '5min', '15min', '30min', '1H', '4H', '1D', '1W']

# Data processing settings
OHLCV_AGGREGATION = {
    'open': 'first',
    'high': 'max',
    'low': 'min',
    'close': 'last',
    'volume': 'sum'
}

# Date and timezone settings
USE_LOCAL_DATA = True
DATE_FORMAT = '%Y-%m-%d'
DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
TIMEZONE = 'UTC'

# File paths
def get_data_path(filename=None):
    """Get full path to data file"""
    if filename is None:
        filename = DEFAULT_DATA_FILE
    return DATA_DIR / filename

def get_chart_path(symbol, timeframe):
    """Get full path for chart output"""
    CHARTS_DIR.mkdir(exist_ok=True)
    return CHARTS_DIR / f'close_vol_chart_{symbol}_{timeframe}.html'

def get_output_path(filename):
    """Get full path for output files"""
    OUTPUT_DIR.mkdir(exist_ok=True)
    return OUTPUT_DIR / filename

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
CHARTS_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)