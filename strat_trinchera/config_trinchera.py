"""
Trinchera Configuration
Shared configuration for all trinchera scripts
"""

# ============================================================================
# BIG VOLUME DETECTION
# ============================================================================
BIG_VOLUME_TRIGGER = 200  # Minimum volume to detect as "big volume"
BIG_VOLUME_TIMEOUT = 10   # Timeout in minutes for big volume effect

MEAN_REVERS_EXPAND = 10   # Points to expand mean reversion levels up/down
MEAN_REVERSE_TIMEOUT_ORDER = 1  # Timeout in minutes for mean reversion order lines (red/green)
