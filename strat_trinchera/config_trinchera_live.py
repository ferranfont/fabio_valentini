"""
Trinchera Live Trading Configuration
Settings for real-time NinjaTrader integration
"""

# ============================================================================
# NETWORKING - BIDIRECTIONAL COMMUNICATION
# ============================================================================
TICK_SERVER_HOST = "127.0.0.1"  # Localhost
TICK_SERVER_PORT = 5555          # Port to RECEIVE tick data from NinjaTrader
ORDER_SERVER_PORT = 5556         # Port to SEND orders to NinjaTrader

# ============================================================================
# BIG VOLUME DETECTION
# ============================================================================
BIG_VOLUME_TRIGGER = 200  # Minimum volume to detect as "big volume"
BIG_VOLUME_TIMEOUT = 10   # Timeout in minutes for big volume effect

# ============================================================================
# INDICATORS
# ============================================================================
SMA_PERIOD = 200  # Simple Moving Average period (needs 200 ticks to initialize)

# ============================================================================
# TRADING PARAMETERS
# ============================================================================
TP_POINTS = 5.0   # Take profit in points
SL_POINTS = 9.0   # Stop loss in points

MEAN_REVERS_EXPAND = 10        # Points to expand mean reversion levels up/down
MEAN_REVERSE_TIMEOUT_ORDER = 3 # Timeout in minutes for mean reversion order lines

# ============================================================================
# FILTERS TRADING SYSTEM
# ============================================================================
FILTER_BY_SMA = False  # Enable/disable SMA filter
# If True (checks orange dot position at big volume event):
#   - If orange dot < SMA: ONLY SELL (SHORT) orders allowed
#   - If orange dot > SMA: ONLY BUY (LONG) orders allowed

SMA_CASH_TRAILING_ENABLED = True  # Enable hybrid cash & trail strategy
SMA_CASH_TRAILING = 25.0          # Points in favor to activate trailing stop
SMA_CASH_TRAILING_DISTANCE = 10.0 # Trailing stop distance after activation

SMA_TRAILING_STOP = True          # Enable/disable full trailing stop from entry
TRAILING_STOP_ATR_MULT = 20.75    # Distance in points from price for trailing stop

# ============================================================================
# TOF FILTER - TIME OF DAY FILTER
# ============================================================================
FILTER_TIME_OF_DAY = False        # Enable/disable time-of-day filter
START_TRADING_TIME = "18:50:00"   # Start trading from this time (HH:MM:SS)
END_TRADING_TIME = "22:50:00"     # Stop trading after this time (HH:MM:SS)

# ============================================================================
# GRID SYSTEM
# ============================================================================
FILTER_USE_GRID = False           # Enable/disable GRID system (second entry)
GRID_MEAN_REVERS_EXPAND = 5.0     # Distance for second entry from first entry
GRID_TP_POINTS = 4.0              # Take profit distance from average entry price
GRID_SL_POINTS = 3.0              # Stop loss distance BEYOND second entry level

# ============================================================================
# RISK MANAGEMENT
# ============================================================================
MAX_CONTRACTS = 1                 # Maximum contracts per trade
MAX_DAILY_LOSS = 1000.0          # Maximum daily loss in dollars (circuit breaker)
MAX_DAILY_TRADES = 50            # Maximum trades per day (circuit breaker)

# ============================================================================
# LOGGING & MONITORING
# ============================================================================
LOG_LEVEL = "INFO"               # DEBUG, INFO, WARNING, ERROR
SAVE_TRADES_TO_CSV = True        # Save executed trades to CSV
CSV_OUTPUT_DIR = "live_trades"   # Directory for trade logs

# ============================================================================
# LIVE TRADING SAFETY
# ============================================================================
PAPER_TRADING_MODE = False        # Set to False for REAL trading
REQUIRE_CONFIRMATION = False      # Require manual confirmation before sending orders
