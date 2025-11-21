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
FILTER_BY_SMA = True  # Enable/disable SMA filter
# If True (checks orange dot position at big volume event):
#   - If orange dot < SMA: ONLY SELL (SHORT) orders allowed
#   - If orange dot > SMA: ONLY BUY (LONG) orders allowed

# ============================================================================
# TRADING PARAMETERS
# ============================================================================
TP_POINTS = 20.0   # Take profit in points
SL_POINTS = 9.0  # Stop loss in points

MEAN_REVERS_EXPAND = 10   # Points to expand mean reversion levels up/down
MEAN_REVERSE_TIMEOUT_ORDER = 3 #Timeout in minutes for mean reversion order lines (red/green)


