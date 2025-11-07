"""
Streaming version of AbsorptionStrategy for real-time tick processing.
Processes ticks one at a time as they arrive from a live feed or client.
"""

import base64
import io
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Callable
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

from rolling_profile import RollingMarketProfile


class AbsorptionStrategyStreaming:
    """
    Real-time streaming version of Absorption Strategy.

    Processes ticks one at a time and triggers callbacks on pattern detection.
    """

    def __init__(
        self,
        profile_window: int = 20,
        extreme_volume_multiplier: float = 2.0,
        min_price_levels: int = 20,
        min_bid_ask_size: int = 30,
        price_position_threshold: float = 0.3,
        diff_distance: float = 0.0,
        min_volume: int = 10,
        cooldown_period: int = 60,
        warmup_period: int = 60,
        output_dir: Optional[Path] = None,
        charts_dir: Optional[Path] = None,
        on_detection_callback: Optional[Callable] = None,
    ):
        """
        Initialize the Streaming Absorption Strategy.

        Args:
            profile_window: Rolling window size in seconds
            extreme_volume_multiplier: Extreme bar multiplier threshold
            min_price_levels: Minimum active price levels
            min_bid_ask_size: Minimum BID/ASK bar size
            price_position_threshold: Price position threshold (0-1)
            diff_distance: Minimum price difference
            min_volume: Minimum total volume
            cooldown_period: Cooldown seconds between detections
            warmup_period: Warmup seconds before detection
            output_dir: Output directory for CSV
            charts_dir: Charts directory for HTML
            on_detection_callback: Function to call on detection (receives detection_data dict)
        """
        # Configuration
        self.profile_window = profile_window
        self.extreme_volume_multiplier = extreme_volume_multiplier
        self.min_price_levels = min_price_levels
        self.min_bid_ask_size = min_bid_ask_size
        self.price_position_threshold = price_position_threshold
        self.diff_distance = diff_distance
        self.min_volume = min_volume
        self.cooldown_period = timedelta(seconds=cooldown_period)
        self.warmup_period = timedelta(seconds=warmup_period)
        self.on_detection_callback = on_detection_callback

        # Setup paths
        base_dir = Path(__file__).resolve().parent
        self.output_dir = output_dir or (base_dir.parent / "outputs/absortion_shape")
        self.charts_dir = charts_dir or (base_dir.parent / "charts/detections")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.charts_dir.mkdir(parents=True, exist_ok=True)

        # Configure matplotlib
        plt.rcParams.update({
            "font.size": 12,
            "axes.titlesize": 14,
            "axes.labelsize": 12,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
            "legend.fontsize": 11,
        })

        # Streaming state
        self.mp = RollingMarketProfile(window=timedelta(seconds=self.profile_window))
        self.detection_count = 0
        self.last_detection_time: Optional[datetime] = None
        self.previous_close: Optional[float] = None
        self.start_time: Optional[datetime] = None
        self.tick_buffer: List[Dict] = []  # Buffer recent ticks for future profiles
        self.signal_records: List[Dict] = []

        # HTML report (created on first detection)
        self.output_html: Optional[Path] = None
        self.html_initialized = False

    def initialize_html_report(self, first_timestamp: datetime):
        """Initialize HTML report on first detection."""
        if self.html_initialized:
            return

        date_slug = first_timestamp.strftime("%Y%m%d")
        title_suffix = first_timestamp.strftime("%Y-%m-%d")

        self.output_html = self.charts_dir / f"absorption_report_streaming_{date_slug}.html"

        with open(self.output_html, "w", encoding="utf-8") as report:
            report.write(
                "<!DOCTYPE html>\n"
                "<html lang='en'>\n"
                "<head>\n"
                "  <meta charset='utf-8'/>\n"
                f"  <title>Absorption Detections (Streaming) – {title_suffix}</title>\n"
                "  <style>\n"
                "    body {font-family: Arial, sans-serif; margin: 24px; background-color: #0b0b10; color: #f0f0f5;}\n"
                "    h1 {margin-bottom: 16px;}\n"
                "    h2 {margin-top: 32px; color: #ffda7b;}\n"
                "    .detection-block {margin-bottom: 48px; padding-bottom: 32px; border-bottom: 1px solid #303046;}\n"
                "    .detection-meta {margin-bottom: 12px; font-size: 14px; color: #bbbbcf;}\n"
                "    .detection-text {background:#161622; padding:16px; border-radius:8px; border:1px solid #303046; color:#e8e8ff;}\n"
                "    pre.detection-text {white-space: pre-wrap; font-size: 14px; line-height: 1.5;}\n"
                "    .detection-figure {margin-top: 16px; background:#ffffff; border-radius:8px; padding:12px; color:#000; box-shadow:0 2px 8px rgba(0,0,0,0.35);}\n"
                "    a {color: #7cc6ff;}\n"
                "  </style>\n"
                "</head>\n"
                "<body>\n"
                f"  <h1>Absorption Detections (Streaming) – {title_suffix}</h1>\n"
                "  <p>Generated by AbsorptionStrategyStreaming (Real-time)</p>\n"
            )

        self.html_initialized = True
        print(f"HTML report initialized: {self.output_html}")

    def process_tick(self, timestamp: datetime, price: float, volume: int, side: str) -> Optional[Dict]:
        """
        Process a single tick in real-time.

        Args:
            timestamp: Tick timestamp
            price: Trade price
            volume: Trade volume
            side: Trade side ('BID' or 'ASK')

        Returns:
            Detection data dict if pattern detected, None otherwise
        """
        # Initialize start time on first tick
        if self.start_time is None:
            self.start_time = timestamp
            print(f"Strategy started at: {self.start_time}")
            print(f"Warmup period: {self.warmup_period.total_seconds():.0f}s")
            print(f"Detection starts after: {self.start_time + self.warmup_period}")

        # Update market profile
        self.mp.update(timestamp, price, volume, side)

        # Store tick in buffer (for future profile generation)
        self.tick_buffer.append({
            'timestamp': timestamp,
            'price': price,
            'volume': volume,
            'side': side,
        })

        # Keep only last 2 hours of ticks in buffer
        cutoff_time = timestamp - timedelta(hours=2)
        self.tick_buffer = [t for t in self.tick_buffer if t['timestamp'] > cutoff_time]

        # Skip warmup period
        if (timestamp - self.start_time) < self.warmup_period:
            self.previous_close = price
            return None

        # Check cooldown
        if self.last_detection_time is not None:
            if (timestamp - self.last_detection_time) < self.cooldown_period:
                self.previous_close = price
                return None

        # Get current profile
        profile = self.mp.profile(include_trades=True)
        if not profile:
            self.previous_close = price
            return None

        # Evaluate shape
        profile_shape = self.evaluate_profile_shape(profile, price, self.previous_close)
        self.previous_close = price

        if profile_shape not in ["d_shape", "p_shape"]:
            return None

        # Pattern detected!
        detection_data = self._create_detection(timestamp, price, profile, profile_shape)

        # Trigger callback if provided
        if self.on_detection_callback:
            try:
                self.on_detection_callback(detection_data)
            except Exception as e:
                print(f"Error in detection callback: {e}")

        return detection_data

    def evaluate_profile_shape(
        self,
        profile: Dict,
        current_close: Optional[float] = None,
        previous_close: Optional[float] = None
    ) -> str:
        """Evaluate the distribution shape of a market profile."""
        if not profile or current_close is None or previous_close is None:
            return "balanced"

        price_diff = abs(current_close - previous_close)
        if price_diff < self.diff_distance:
            return "balanced"

        active_prices = []
        for price in sorted(profile.keys()):
            bid_vol = profile[price].get("BID", 0)
            ask_vol = profile[price].get("ASK", 0)
            if bid_vol > 0 or ask_vol > 0:
                active_prices.append(price)

        if len(active_prices) < self.min_price_levels:
            return "balanced"

        total_bid = sum(profile[p].get("BID", 0) for p in active_prices)
        total_ask = sum(profile[p].get("ASK", 0) for p in active_prices)
        total_volume = total_bid + total_ask

        if total_volume < self.min_volume:
            return "balanced"

        min_price = min(active_prices)
        max_price = max(active_prices)
        price_range = max_price - min_price

        if price_range == 0:
            return "balanced"

        price_position = (current_close - min_price) / price_range

        lowest_2_prices = active_prices[:2] if len(active_prices) >= 2 else active_prices
        highest_2_prices = active_prices[-2:] if len(active_prices) >= 2 else active_prices

        max_bid_value = max((profile[p].get("BID", 0) for p in active_prices), default=0)
        max_ask_value = max((profile[p].get("ASK", 0) for p in active_prices), default=0)

        max_bid_price = max(active_prices, key=lambda p: profile[p].get("BID", 0)) if active_prices else None
        max_ask_price = max(active_prices, key=lambda p: profile[p].get("ASK", 0)) if active_prices else None

        all_volumes = []
        for p in active_prices:
            if profile[p].get("BID", 0) > 0:
                all_volumes.append(profile[p]["BID"])
            if profile[p].get("ASK", 0) > 0:
                all_volumes.append(profile[p]["ASK"])

        all_volumes_sorted = sorted(all_volumes, reverse=True)
        second_largest_overall = all_volumes_sorted[1] if len(all_volumes_sorted) > 1 else 0

        bid_ratio = max_bid_value / second_largest_overall if second_largest_overall > 0 else float("inf")
        ask_ratio = max_ask_value / second_largest_overall if second_largest_overall > 0 else float("inf")

        if (max_bid_value >= self.min_bid_ask_size and
            max_bid_price in lowest_2_prices and
            bid_ratio >= self.extreme_volume_multiplier and
            price_position <= self.price_position_threshold and
            current_close < previous_close):
            return "d_shape"

        if (max_ask_value >= self.min_bid_ask_size and
            max_ask_price in highest_2_prices and
            ask_ratio >= self.extreme_volume_multiplier and
            price_position >= (1 - self.price_position_threshold) and
            current_close > previous_close):
            return "p_shape"

        return "balanced"

    def _create_detection(self, timestamp: datetime, price: float, profile: Dict, shape: str) -> Dict:
        """Create detection data and generate report."""
        self.detection_count += 1

        # Initialize HTML on first detection
        if not self.html_initialized:
            self.initialize_html_report(timestamp)

        prices = sorted(profile.keys())
        highest_price = prices[-1] if prices else price
        lowest_price = prices[0] if prices else price

        total_bid = sum(profile[p].get("BID", 0) for p in prices)
        total_ask = sum(profile[p].get("ASK", 0) for p in prices)

        active_prices = [p for p in prices if profile[p].get("BID", 0) > 0 or profile[p].get("ASK", 0) > 0]

        # Record signal
        timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        signal_record = {
            "timestamp": timestamp_str,
            "shape": shape,
            "close_price": price,
            "total_bid": total_bid,
            "total_ask": total_ask,
            "bid_ask_ratio": total_bid / total_ask if total_ask > 0 else 0,
            "num_price_levels": len(active_prices),
        }
        self.signal_records.append(signal_record)

        # Generate simple chart (no future profiles in streaming mode)
        print(f"\n{'=' * 80}")
        print(f"DETECTION #{self.detection_count} at {timestamp}")
        print(f"Pattern: {shape}")
        print(f"Price: {price:.2f} | Range: {lowest_price:.2f} - {highest_price:.2f}")
        print(f"{'=' * 80}")

        # Create simplified detection data
        detection_data = {
            'detection_num': self.detection_count,
            'timestamp': timestamp,
            'shape': shape,
            'price': price,
            'profile': profile,
            'signal_record': signal_record,
            'html_path': self.output_html,
        }

        # Update HTML report
        if self.output_html:
            section_html = (
                "<section class='detection-block'>"
                f"<h2>Detection #{self.detection_count} — {shape.upper()} ({timestamp.strftime('%H:%M:%S')})</h2>"
                f"<div class='detection-meta'>Timestamp: {timestamp} | Price: {price:.2f}</div>"
                f"<pre class='detection-text'>Shape: {shape}\nPrice: {price:.2f}\n"
                f"Bid: {total_bid:.0f} | Ask: {total_ask:.0f}\nLevels: {len(active_prices)}</pre>"
                "</section>\n"
            )

            with open(self.output_html, "a", encoding="utf-8") as report:
                report.write(section_html)

        self.last_detection_time = timestamp
        return detection_data

    def finalize(self):
        """Finalize HTML report and save signals CSV."""
        if self.output_html and self.html_initialized:
            with open(self.output_html, "a", encoding="utf-8") as report:
                if self.detection_count == 0:
                    report.write("<p>No detections matched the criteria.</p>\n")
                report.write("</body></html>\n")

        if self.signal_records:
            data_date = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_signals_csv = self.output_dir / f"db_shapes_streaming_{data_date}.csv"
            signals_df = pd.DataFrame(self.signal_records)
            signals_df.to_csv(output_signals_csv, index=False, sep=";", decimal=",")
            print(f"Signals CSV saved: {output_signals_csv}")
            return output_signals_csv

        return None

    def get_stats(self) -> Dict:
        """Get current strategy statistics."""
        return {
            'detection_count': self.detection_count,
            'total_ticks': len(self.tick_buffer),
            'last_detection': self.last_detection_time,
            'html_path': self.output_html,
        }
