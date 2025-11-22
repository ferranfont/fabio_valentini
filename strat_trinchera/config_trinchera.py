"""
Trinchera Configuration
Shared configuration for all trinchera scripts
"""

# ============================================================================
# BIG VOLUME DETECTION
# ============================================================================
BIG_VOLUME_TRIGGER = 200  # Minimum volume to detect as "big volume"
BIG_VOLUME_TIMEOUT = 10   # Timeout in minutes for big volume effect

# ============================================================================
# INDICATORS
# ============================================================================
SMA_PERIOD = 200  # Simple Moving Average period

# ============================================================================
# FILTERS TRADING SYSTEM
# ============================================================================
FILTER_BY_SMA = False  # Enable/disable SMA filter
# If True (checks orange dot position at big volume event):
#   - If orange dot < SMA: ONLY SELL (SHORT) orders allowed
#   - If orange dot > SMA: ONLY BUY (LONG) orders allowed

SMA_TRAILING_STOP = False  # Enable/disable SMA-based trailing stop (only works if FILTER_BY_SMA = True)
TRAILING_STOP_ATR_MULT = 0.75  # Distance from SMA for trailing stop (in points, or ATR multiplier if using ATR)
# If SMA_TRAILING_STOP = True (only when FILTER_BY_SMA is also True):
#   - DISABLES fixed TP - lets profits run until price crosses back through SMA
#   - For LONG trades: Move stop loss up following the SMA as it rises (never moves down)
#   - For SHORT trades: Move stop loss down following the SMA as it falls (never moves up)
#   - Locks in profits as price moves favorably and SMA follows
#   - Trade exits when price crosses back through the trailing SMA level
#   - Exit reason will be 'trailing_stop' instead of 'stop'
#   - NO fixed TP is used when trailing stop is active (let profits run)

FILTER_TIME_OF_DAY = False  # Enable/disable time-of-day filter
START_TRADING_TIME = "18:50:00"  # Start trading from this time (HH:MM:SS)
END_TRADING_TIME = "22:50:00"    # Stop trading after this time (HH:MM:SS)
# If True: Only trades with entry_time between START and END are allowed

# ============================================================================
# TRADING PARAMETERS
# ============================================================================
TP_POINTS = 5.0   # Take profit in points, usar 4 oara scalping and 20 for swing
SL_POINTS = 10.0  # Stop loss in points, usar 9 para scalping

MEAN_REVERS_EXPAND = 10          # Points to expand mean reversion levels up/down
MEAN_REVERSE_TIMEOUT_ORDER = 3   # Timeout in minutes for mean reversion order lines (red/green)

# ============================================================================
# GRID SYSTEM
# ============================================================================
FILTER_USE_GRID = False  # Enable/disable GRID system (second entry)
GRID_MEAN_REVERS_EXPAND = 5.0  # Distance in points for second entry from first entry
GRID_TP_POINTS = 4.0  # Take profit distance from average entry price when GRID is active
GRID_SL_POINTS = 3.0   # Stop loss distance BEYOND second entry level when GRID is active
# If True:
#   - SELL: First entry at MEAN_REVERS_EXPAND, second entry at MEAN_REVERS_EXPAND + GRID_MEAN_REVERS_EXPAND
#   - BUY: First entry at MEAN_REVERS_EXPAND, second entry at MEAN_REVERS_EXPAND + GRID_MEAN_REVERS_EXPAND
#   - If first entry reaches TP_POINTS before second entry triggers → close immediately at profit
#   - If price squeezes and second entry triggers → use GRID_TP_POINTS from average price, GRID_SL_POINTS beyond second entry
#   - Filled zones drawn at MEAN_REVERS_EXPAND + GRID_MEAN_REVERS_EXPAND (where second entry would be)


