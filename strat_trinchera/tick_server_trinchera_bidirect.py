"""
Trinchera Live Trading - Bidirectional NinjaTrader Integration
Receives tick data from NinjaTrader and sends orders back in real-time
"""

import socket
import threading
import time
import numpy as np
from datetime import datetime, timedelta
from collections import deque
import json
import logging
from pathlib import Path

# Import configuration
from config_trinchera_live import *

# ============================================================================
# LOGGING SETUP
# ============================================================================
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ============================================================================
# GLOBAL STATE
# ============================================================================
class TrìncheraState:
    """Maintains real-time strategy state"""

    def __init__(self):
        # Price buffers
        self.price_buffer = deque(maxlen=SMA_PERIOD)  # For SMA calculation
        self.recent_volumes = deque(maxlen=100)       # For big volume detection

        # Current market state
        self.current_price = 0.0
        self.current_bid = 0.0
        self.current_ask = 0.0
        self.current_sma = 0.0
        self.last_big_volume_time = None
        self.last_orange_dot_price = 0.0

        # Mean reversion levels
        self.buy_level = 0.0
        self.sell_level = 0.0
        self.levels_timestamp = None

        # Active positions
        self.position = None  # {'side': 'LONG/SHORT', 'entry_price': X, 'contracts': N, 'entry_time': DT}
        self.daily_pnl = 0.0
        self.daily_trades = 0

        # Trade log
        self.trades = []

        # Safety flags
        self.trading_enabled = True
        self.circuit_breaker_triggered = False

    def add_price(self, price):
        """Add price to buffer and update SMA"""
        self.price_buffer.append(price)
        if len(self.price_buffer) == SMA_PERIOD:
            self.current_sma = np.mean(self.price_buffer)

    def detect_big_volume(self, volume):
        """Detect if current volume exceeds threshold"""
        self.recent_volumes.append(volume)

        if volume >= BIG_VOLUME_TRIGGER:
            # Check timeout (don't trigger if recent big volume already active)
            now = datetime.now()
            if self.last_big_volume_time is None or \
               (now - self.last_big_volume_time).seconds / 60 >= BIG_VOLUME_TIMEOUT:
                self.last_big_volume_time = now
                return True
        return False

    def calculate_mean_reversion_levels(self, orange_dot_price):
        """Calculate entry levels based on orange dot"""
        self.last_orange_dot_price = orange_dot_price
        self.buy_level = orange_dot_price - MEAN_REVERS_EXPAND
        self.sell_level = orange_dot_price + MEAN_REVERS_EXPAND
        self.levels_timestamp = datetime.now()

        logger.info(f"🟠 ORANGE DOT at {orange_dot_price:.2f} | BUY: {self.buy_level:.2f} | SELL: {self.sell_level:.2f}")

    def levels_expired(self):
        """Check if mean reversion levels have expired"""
        if self.levels_timestamp is None:
            return True
        elapsed_minutes = (datetime.now() - self.levels_timestamp).seconds / 60
        return elapsed_minutes >= MEAN_REVERSE_TIMEOUT_ORDER

    def check_circuit_breakers(self):
        """Check if circuit breakers triggered"""
        if abs(self.daily_pnl) >= MAX_DAILY_LOSS:
            logger.error(f"🚨 CIRCUIT BREAKER: Daily loss limit ${abs(self.daily_pnl):.2f} >= ${MAX_DAILY_LOSS}")
            self.circuit_breaker_triggered = True
            self.trading_enabled = False
            return False

        if self.daily_trades >= MAX_DAILY_TRADES:
            logger.error(f"🚨 CIRCUIT BREAKER: Daily trade limit {self.daily_trades} >= {MAX_DAILY_TRADES}")
            self.circuit_breaker_triggered = True
            self.trading_enabled = False
            return False

        return True

    def can_trade(self):
        """Check if trading is allowed"""
        # Check circuit breakers
        if not self.check_circuit_breakers():
            return False

        # Check time filter
        if FILTER_TIME_OF_DAY:
            now_time = datetime.now().time()
            start_time = datetime.strptime(START_TRADING_TIME, "%H:%M:%S").time()
            end_time = datetime.strptime(END_TRADING_TIME, "%H:%M:%S").time()

            if not (start_time <= now_time <= end_time):
                return False

        # Check if position already open
        if self.position is not None:
            return False

        return self.trading_enabled

# Initialize global state
state = TrìncheraState()

# ============================================================================
# TICK DATA RECEIVER (FROM NINJATRADER)
# ============================================================================
def tick_receiver_thread():
    """Receives tick data from NinjaTrader"""
    logger.info(f"🎧 Starting tick receiver on {TICK_SERVER_HOST}:{TICK_SERVER_PORT}")

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((TICK_SERVER_HOST, TICK_SERVER_PORT))
    server_socket.listen(1)

    logger.info(f"✅ Waiting for NinjaTrader connection...")

    conn, addr = server_socket.accept()
    logger.info(f"✅ NinjaTrader connected from {addr}")

    buffer = ""

    while True:
        try:
            data = conn.recv(4096).decode('utf-8')
            if not data:
                logger.warning("⚠️ NinjaTrader disconnected. Reconnecting...")
                conn.close()
                conn, addr = server_socket.accept()
                logger.info(f"✅ NinjaTrader reconnected from {addr}")
                continue

            buffer += data

            # Process complete messages (newline-separated)
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                process_tick_data(line.strip())

        except Exception as e:
            logger.error(f"❌ Error receiving tick data: {e}")
            time.sleep(1)

def process_tick_data(tick_str):
    """Process incoming tick data and generate signals"""
    try:
        # Expected format: "TIMESTAMP;PRICE;VOLUME;SIDE;BID;ASK"
        # Example: "2025-12-01 14:30:25.123;20500.25;50;BUY;20500.00;20500.50"

        parts = tick_str.split(';')
        if len(parts) != 6:
            return

        timestamp_str, price_str, volume_str, side, bid_str, ask_str = parts

        # Parse values
        price = float(price_str.replace(',', '.'))
        volume = int(volume_str)
        bid = float(bid_str.replace(',', '.'))
        ask = float(ask_str.replace(',', '.'))

        # Update state
        state.current_price = price
        state.current_bid = bid
        state.current_ask = ask
        state.add_price(price)

        # Check if SMA is ready
        if len(state.price_buffer) < SMA_PERIOD:
            if len(state.price_buffer) % 20 == 0:  # Log every 20 ticks
                logger.info(f"📊 Initializing SMA: {len(state.price_buffer)}/{SMA_PERIOD} ticks")
            return

        # ====================================================================
        # ORANGE DOT DETECTION (Big Volume Event)
        # ====================================================================
        if state.detect_big_volume(volume):
            orange_dot_price = price
            logger.warning(f"🟠 BIG VOLUME DETECTED: {volume} contracts at {orange_dot_price:.2f} (Threshold: {BIG_VOLUME_TRIGGER})")
            logger.info(f"📈 Current SMA: {state.current_sma:.2f}")

            # Calculate mean reversion levels
            state.calculate_mean_reversion_levels(orange_dot_price)

            # Check SMA filter
            if FILTER_BY_SMA:
                if orange_dot_price > state.current_sma:
                    logger.info(f"✅ SMA Filter: Orange dot ABOVE SMA → LONG only")
                else:
                    logger.info(f"✅ SMA Filter: Orange dot BELOW SMA → SHORT only")

        # ====================================================================
        # ENTRY SIGNAL DETECTION
        # ====================================================================
        if not state.can_trade():
            return

        if state.levels_expired():
            return

        # Check BUY level
        if price <= state.buy_level:
            # Check SMA filter
            if FILTER_BY_SMA and state.last_orange_dot_price <= state.current_sma:
                return  # Filter blocks LONG when orange dot below SMA

            logger.info(f"🟢 BUY SIGNAL at {price:.2f} (Level: {state.buy_level:.2f})")
            send_entry_order('LONG', price)

        # Check SELL level
        elif price >= state.sell_level:
            # Check SMA filter
            if FILTER_BY_SMA and state.last_orange_dot_price >= state.current_sma:
                return  # Filter blocks SHORT when orange dot above SMA

            logger.info(f"🔴 SELL SIGNAL at {price:.2f} (Level: {state.sell_level:.2f})")
            send_entry_order('SHORT', price)

        # ====================================================================
        # EXIT MANAGEMENT (If position open)
        # ====================================================================
        if state.position is not None:
            check_exit_conditions(price)

    except Exception as e:
        logger.error(f"❌ Error processing tick: {tick_str} | {e}")

# ============================================================================
# ORDER SENDER (TO NINJATRADER)
# ============================================================================
order_socket = None
order_server = None

def start_order_server():
    """Start server to accept NinjaTrader connection for sending orders"""
    global order_socket, order_server

    logger.info(f"🔌 Starting order server on localhost:{ORDER_SERVER_PORT}")

    order_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    order_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    order_server.bind(('127.0.0.1', ORDER_SERVER_PORT))
    order_server.listen(1)

    logger.info(f"✅ Order server listening on port {ORDER_SERVER_PORT}")
    logger.info(f"⏳ Waiting for NinjaTrader to connect...")

    # Accept connection from NinjaTrader
    order_socket, addr = order_server.accept()
    logger.info(f"✅ NinjaTrader connected from {addr}")

def send_order(order_dict):
    """Send order to NinjaTrader"""
    global order_socket

    if PAPER_TRADING_MODE:
        logger.warning(f"📄 PAPER TRADING: {order_dict}")
        return

    if REQUIRE_CONFIRMATION:
        confirm = input(f"\n⚠️  CONFIRM ORDER: {order_dict} (yes/no): ")
        if confirm.lower() != 'yes':
            logger.warning("❌ Order cancelled by user")
            return

    try:
        message = json.dumps(order_dict) + '\n'
        order_socket.sendall(message.encode('utf-8'))
        logger.info(f"📤 Order sent: {order_dict}")
    except Exception as e:
        logger.error(f"❌ Error sending order: {e}")
        # Try to send again (connection should be persistent)
        try:
            order_socket.sendall(message.encode('utf-8'))
            logger.info(f"📤 Order sent on retry")
        except:
            logger.error(f"❌ Failed to send order on retry")

def send_entry_order(side, entry_price):
    """Send entry order (LONG or SHORT)"""
    tp_price = entry_price + TP_POINTS if side == 'LONG' else entry_price - TP_POINTS
    sl_price = entry_price - SL_POINTS if side == 'LONG' else entry_price + SL_POINTS

    order = {
        'action': 'ENTRY',
        'side': side,
        'contracts': MAX_CONTRACTS,
        'entry_price': entry_price,
        'tp_price': tp_price,
        'sl_price': sl_price,
        'timestamp': datetime.now().isoformat()
    }

    send_order(order)

    # Update position state
    state.position = {
        'side': side,
        'entry_price': entry_price,
        'contracts': MAX_CONTRACTS,
        'entry_time': datetime.now(),
        'tp_price': tp_price,
        'sl_price': sl_price
    }

    logger.info(f"💼 Position opened: {side} @ {entry_price:.2f} | TP: {tp_price:.2f} | SL: {sl_price:.2f}")

def send_exit_order(exit_price, exit_reason):
    """Send exit order"""
    if state.position is None:
        return

    order = {
        'action': 'EXIT',
        'side': 'SELL' if state.position['side'] == 'LONG' else 'BUY',
        'contracts': state.position['contracts'],
        'exit_price': exit_price,
        'exit_reason': exit_reason,
        'timestamp': datetime.now().isoformat()
    }

    send_order(order)

    # Calculate P&L
    if state.position['side'] == 'LONG':
        pnl_points = exit_price - state.position['entry_price']
    else:
        pnl_points = state.position['entry_price'] - exit_price

    pnl_dollars = pnl_points * 20.0 * state.position['contracts']  # NQ point value = $20

    # Update state
    state.daily_pnl += pnl_dollars
    state.daily_trades += 1

    # Log trade
    trade = {
        'entry_time': state.position['entry_time'].isoformat(),
        'exit_time': datetime.now().isoformat(),
        'side': state.position['side'],
        'entry_price': state.position['entry_price'],
        'exit_price': exit_price,
        'exit_reason': exit_reason,
        'pnl_points': pnl_points,
        'pnl_dollars': pnl_dollars,
        'contracts': state.position['contracts']
    }
    state.trades.append(trade)

    logger.info(f"💰 Position closed: {exit_reason} @ {exit_price:.2f} | P&L: ${pnl_dollars:.2f} ({pnl_points:+.2f} pts)")
    logger.info(f"📊 Daily P&L: ${state.daily_pnl:.2f} | Trades: {state.daily_trades}")

    # Save trade to CSV
    if SAVE_TRADES_TO_CSV:
        save_trade_to_csv(trade)

    # Clear position
    state.position = None

def check_exit_conditions(current_price):
    """Check if position should be exited"""
    if state.position is None:
        return

    side = state.position['side']
    tp_price = state.position['tp_price']
    sl_price = state.position['sl_price']

    if side == 'LONG':
        if current_price >= tp_price:
            send_exit_order(current_price, 'TARGET')
        elif current_price <= sl_price:
            send_exit_order(current_price, 'STOP')
    else:  # SHORT
        if current_price <= tp_price:
            send_exit_order(current_price, 'TARGET')
        elif current_price >= sl_price:
            send_exit_order(current_price, 'STOP')

# ============================================================================
# CSV TRADE LOGGING
# ============================================================================
def save_trade_to_csv(trade):
    """Save trade to CSV file"""
    try:
        csv_dir = Path(CSV_OUTPUT_DIR)
        csv_dir.mkdir(exist_ok=True)

        today = datetime.now().strftime('%Y%m%d')
        csv_file = csv_dir / f"trinchera_trades_{today}.csv"

        # Check if file exists
        file_exists = csv_file.exists()

        with open(csv_file, 'a') as f:
            if not file_exists:
                # Write header
                f.write("entry_time;exit_time;side;entry_price;exit_price;exit_reason;pnl_points;pnl_dollars;contracts\n")

            # Write trade
            f.write(f"{trade['entry_time']};{trade['exit_time']};{trade['side']};")
            f.write(f"{trade['entry_price']:.2f};{trade['exit_price']:.2f};{trade['exit_reason']};")
            f.write(f"{trade['pnl_points']:.2f};{trade['pnl_dollars']:.2f};{trade['contracts']}\n")

    except Exception as e:
        logger.error(f"❌ Error saving trade to CSV: {e}")

# ============================================================================
# MAIN STARTUP
# ============================================================================
def main():
    logger.info("=" * 80)
    logger.info("TRINCHERA LIVE TRADING - BIDIRECTIONAL NINJATRADER INTEGRATION")
    logger.info("=" * 80)

    logger.info(f"\n📋 Configuration:")
    logger.info(f"   TP: {TP_POINTS} pts | SL: {SL_POINTS} pts")
    logger.info(f"   Big Volume Trigger: {BIG_VOLUME_TRIGGER}")
    logger.info(f"   Entry Distance: ±{MEAN_REVERS_EXPAND} pts")
    logger.info(f"   SMA Period: {SMA_PERIOD}")
    logger.info(f"   SMA Filter: {'ON' if FILTER_BY_SMA else 'OFF'}")
    logger.info(f"   Time Filter: {'ON' if FILTER_TIME_OF_DAY else 'OFF'}")
    logger.info(f"   Trailing Stop: {'ON' if SMA_TRAILING_STOP else ('Cash+Trail' if SMA_CASH_TRAILING_ENABLED else 'OFF')}")

    logger.info(f"\n🔌 Network:")
    logger.info(f"   Receiving ticks on: {TICK_SERVER_HOST}:{TICK_SERVER_PORT}")
    logger.info(f"   Sending orders to: localhost:{ORDER_SERVER_PORT}")

    logger.info(f"\n⚠️  Safety:")
    logger.info(f"   Paper Trading: {PAPER_TRADING_MODE}")
    logger.info(f"   Require Confirmation: {REQUIRE_CONFIRMATION}")
    logger.info(f"   Max Daily Loss: ${MAX_DAILY_LOSS}")
    logger.info(f"   Max Daily Trades: {MAX_DAILY_TRADES}")

    # Start order server (NinjaTrader will connect to us)
    try:
        start_order_server()
    except Exception as e:
        logger.error(f"❌ Failed to start order server: {e}")
        logger.info("ℹ️  Make sure port 5556 is not in use")
        return

    # Start tick receiver thread
    receiver_thread = threading.Thread(target=tick_receiver_thread, daemon=True)
    receiver_thread.start()

    logger.info("\n✅ LIVE TRADING STARTED - Press Ctrl+C to stop\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("\n🛑 Shutting down...")

        # Print final statistics
        logger.info("=" * 80)
        logger.info("SESSION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total Trades: {state.daily_trades}")
        logger.info(f"Daily P&L: ${state.daily_pnl:.2f}")

        if state.position is not None:
            logger.warning(f"⚠️  Open position still active: {state.position}")

if __name__ == "__main__":
    main()
