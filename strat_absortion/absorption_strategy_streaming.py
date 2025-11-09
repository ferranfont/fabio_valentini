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
        # Validate price (reject 0 or negative prices)
        if price <= 0:
            return None

        # Validate volume
        if volume <= 0:
            return None

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

    def _generate_comprehensive_chart(self, profile: Dict, timestamp: datetime, price: float, shape: str) -> str:
        """
        Generate comprehensive 5-panel chart matching non-streaming version layout.

        Args:
            profile: Market profile data at detection
            timestamp: Detection timestamp
            price: Current price
            shape: Pattern shape

        Returns:
            Base64 encoded image string
        """
        try:
            # Create figure with 5 panels (2 rows, 4 columns) - same as non-streaming version
            fig = plt.figure(figsize=(24, 12))
            gs = fig.add_gridspec(2, 4, hspace=0.3, wspace=0.3)

            ax1 = fig.add_subplot(gs[0, 0])  # Profile at detection
            ax2 = fig.add_subplot(gs[0, 1])  # Profile -20s (historical)
            ax3 = fig.add_subplot(gs[0, 2])  # Profile -40s (historical)
            ax4 = fig.add_subplot(gs[0, 3])  # Price movement
            ax5 = fig.add_subplot(gs[1, :])  # Bid/Ask bubbles (bottom row)

            # Helper function to plot market profile
            def plot_market_profile(ax, prof, title, closing_price=None):
                if not prof:
                    ax.text(0.5, 0.5, "No data", ha="center", va="center")
                    ax.set_title(title, fontsize=14, fontweight="bold")
                    return

                prof_prices = sorted(prof.keys())
                prof_bid_volumes = [prof[p].get("BID", 0) for p in prof_prices]
                prof_ask_volumes = [prof[p].get("ASK", 0) for p in prof_prices]

                bar_height = (min(prof_prices[i+1] - prof_prices[i] for i in range(len(prof_prices)-1)) * 0.8
                             if len(prof_prices) > 1 else 0.25 * 0.8)

                ax.barh(prof_prices, [-v for v in prof_bid_volumes], height=bar_height,
                        color=(0.8, 0, 0, 0.8), label="BID",
                        edgecolor="darkred", linewidth=0.5)
                ax.barh(prof_prices, prof_ask_volumes, height=bar_height,
                        color=(0, 0.7, 0, 0.8), label="ASK",
                        edgecolor="darkgreen", linewidth=0.5)

                ax.axvline(x=0, color="black", linewidth=1.5, linestyle="-", alpha=0.7)

                if closing_price is not None and closing_price in prof_prices:
                    ax.plot(0, closing_price, "o", color="blue", markersize=10, zorder=5,
                           markeredgecolor="darkblue", markeredgewidth=2)

                max_x = max(max(prof_bid_volumes) if prof_bid_volumes else 1,
                           max(prof_ask_volumes) if prof_ask_volumes else 1) * 1.1
                ax.set_xlim(-max_x, max_x)
                ax.set_xlabel("Volume (BID ← | → ASK)", fontsize=12)
                ax.set_ylabel("Price Level", fontsize=12)
                ax.set_title(title, fontsize=14, fontweight="bold")
                ax.grid(True, alpha=0.3, axis="x")
                ax.legend(loc="upper right", fontsize=11)

            # Calculate closing prices for each panel
            closing_price_now = price

            # Historical profiles (since we can't show future in streaming)
            time_before_1x = timestamp - timedelta(seconds=self.profile_window)
            time_before_2x = timestamp - timedelta(seconds=self.profile_window * 2)

            # Build historical profiles from tick buffer
            profile_before_1x = {}
            profile_before_2x = {}
            closing_price_before_1x = None
            closing_price_before_2x = None

            for tick in self.tick_buffer:
                t_time = tick['timestamp']
                t_price = tick['price']
                t_volume = tick['volume']
                t_side = tick['side'].upper()

                # Profile at -20s
                if time_before_1x <= t_time <= timestamp - timedelta(seconds=self.profile_window // 2):
                    # Skip BETWEEN and UNKNOWN sides
                    if t_side not in ['BID', 'ASK']:
                        continue
                    if t_price not in profile_before_1x:
                        profile_before_1x[t_price] = {"BID": 0, "ASK": 0}
                    profile_before_1x[t_price][t_side] += t_volume
                    closing_price_before_1x = t_price

                # Profile at -40s
                if time_before_2x <= t_time <= time_before_1x:
                    # Skip BETWEEN and UNKNOWN sides
                    if t_side not in ['BID', 'ASK']:
                        continue
                    if t_price not in profile_before_2x:
                        profile_before_2x[t_price] = {"BID": 0, "ASK": 0}
                    profile_before_2x[t_price][t_side] += t_volume
                    closing_price_before_2x = t_price

            # Panel 1-3: Market profiles
            plot_market_profile(ax1, profile,
                               f"At Detection\n{timestamp.strftime('%H:%M:%S')}",
                               closing_price_now)
            plot_market_profile(ax2, profile_before_1x,
                               f"Before {self.profile_window}s\n{time_before_1x.strftime('%H:%M:%S')}",
                               closing_price_before_1x)
            plot_market_profile(ax3, profile_before_2x,
                               f"Before {self.profile_window*2}s\n{time_before_2x.strftime('%H:%M:%S')}",
                               closing_price_before_2x)

            # Panel 4: Price Movement
            lookback_seconds = 10
            lookforward_seconds = 60
            start_time = timestamp - timedelta(seconds=lookback_seconds)
            end_time = timestamp + timedelta(seconds=lookforward_seconds)

            # Filter tick buffer for this time range
            price_ticks = [t for t in self.tick_buffer
                          if start_time <= t['timestamp'] <= end_time]

            if price_ticks:
                times_rel = [(t['timestamp'] - timestamp).total_seconds() for t in price_ticks]
                prices_plot = [t['price'] for t in price_ticks]

                bid_mask = [t['side'].upper() == 'BID' for t in price_ticks]
                ask_mask = [t['side'].upper() == 'ASK' for t in price_ticks]

                bid_times = [t for i, t in enumerate(times_rel) if bid_mask[i]]
                bid_prices = [p for i, p in enumerate(prices_plot) if bid_mask[i]]
                ask_times = [t for i, t in enumerate(times_rel) if ask_mask[i]]
                ask_prices = [p for i, p in enumerate(prices_plot) if ask_mask[i]]

                ax4.scatter(bid_times, bid_prices, c="red", s=10, alpha=0.6, label="BID")
                ax4.scatter(ask_times, ask_prices, c="green", s=10, alpha=0.6, label="ASK")

                # Add vertical lines
                for x_pos, color, label in [(0, "blue", "Detection"),
                                            (self.profile_window, "orange", f"+{self.profile_window}s"),
                                            (self.profile_window*2, "purple", f"+{self.profile_window*2}s")]:
                    if -lookback_seconds <= x_pos <= lookforward_seconds:
                        ax4.axvline(x=x_pos, color=color, linewidth=2, linestyle="--",
                                  alpha=0.8, label=label, zorder=5)

                ax4.set_xlabel("Time (seconds relative to detection)", fontsize=12)
                ax4.set_ylabel("Price", fontsize=12)
                ax4.set_title(f"Price Movement\n(-{lookback_seconds}s to +{lookforward_seconds}s)",
                            fontsize=14, fontweight="bold")
                ax4.grid(True, alpha=0.3)
                ax4.legend(loc="best", fontsize=11)

            # Panel 5: Bid/Ask Bubble Chart (bottom row spanning all columns)
            bubble_lookback = self.profile_window
            bubble_lookforward = self.profile_window * 4
            bubble_start = timestamp - timedelta(seconds=bubble_lookback)
            bubble_end = timestamp + timedelta(seconds=bubble_lookforward)

            bubble_ticks = [t for t in self.tick_buffer
                           if bubble_start <= t['timestamp'] <= bubble_end]

            if bubble_ticks:
                # Aggregate by timestamp and side
                df_bubble = pd.DataFrame(bubble_ticks)
                df_bubble['time_rel'] = df_bubble['timestamp'].apply(lambda t: (t - timestamp).total_seconds())

                agg_data = df_bubble.groupby(['timestamp', 'side'], as_index=False).agg({
                    'volume': 'sum',
                    'price': 'mean',
                    'time_rel': 'first'
                })

                bid_data = agg_data[agg_data['side'].str.upper() == 'BID']
                ask_data = agg_data[agg_data['side'].str.upper() == 'ASK']

                if len(bid_data) > 0:
                    bid_sizes = np.clip(np.sqrt(bid_data['volume'].values) * 10, 10, 200)
                    ax5.scatter(bid_data['time_rel'].values, bid_data['price'].values,
                              s=bid_sizes, color="red", alpha=0.6,
                              edgecolors="darkred", linewidth=0.5, label="Bid")

                if len(ask_data) > 0:
                    ask_sizes = np.clip(np.sqrt(ask_data['volume'].values) * 10, 10, 200)
                    ax5.scatter(ask_data['time_rel'].values, ask_data['price'].values,
                              s=ask_sizes, color="green", alpha=0.6,
                              edgecolors="darkgreen", linewidth=0.5, label="Ask")

                # Add vertical lines
                for i, (x_pos, color) in enumerate([(0, "blue"),
                                                     (self.profile_window, "orange"),
                                                     (2*self.profile_window, "purple"),
                                                     (3*self.profile_window, "brown"),
                                                     (4*self.profile_window, "pink")]):
                    label = "Detection (0s)" if i == 0 else f"+{x_pos}s"
                    if -bubble_lookback <= x_pos <= bubble_lookforward:
                        ax5.axvline(x=x_pos, color=color, linewidth=2, linestyle="--",
                                  alpha=0.8, label=label)

                ax5.set_xlabel("Seconds relative to detection (0 = detection)", fontsize=12)
                ax5.set_ylabel("Price", fontsize=12)
                ax5.set_title(f"Bid/Ask Bubbles (size=volume)\n(-{bubble_lookback}s to +{bubble_lookforward}s)",
                            fontsize=14, fontweight="bold")
                ax5.grid(True, alpha=0.3)
                ax5.legend(loc="best", fontsize=11)

            # Synchronize y-axis scales across all panels
            all_prices = []
            if profile:
                all_prices.extend(list(profile.keys()))
            if profile_before_1x:
                all_prices.extend(list(profile_before_1x.keys()))
            if profile_before_2x:
                all_prices.extend(list(profile_before_2x.keys()))
            if price_ticks:
                all_prices.extend([t['price'] for t in price_ticks])
            if bubble_ticks:
                all_prices.extend([t['price'] for t in bubble_ticks])

            if all_prices:
                global_min = min(all_prices)
                global_max = max(all_prices)
                padding = (global_max - global_min) * 0.02
                y_min = global_min - padding
                y_max = global_max + padding

                for ax in [ax1, ax2, ax3, ax4, ax5]:
                    ax.set_ylim(y_min, y_max)

            # Title
            fig.suptitle(f"Detection #{self.detection_count} - Pattern: {shape.upper()}",
                        fontsize=16, fontweight="bold", y=0.98)
            fig.tight_layout()

            # Convert to base64
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=100, bbox_inches='tight',
                       facecolor='white', edgecolor='none')
            buf.seek(0)
            img_base64 = base64.b64encode(buf.read()).decode('utf-8')
            plt.close(fig)

            return img_base64

        except Exception as e:
            print(f"[WARNING] Failed to generate comprehensive chart: {e}")
            import traceback
            traceback.print_exc()
            return ""

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

        # Generate comprehensive chart
        print(f"\n{'=' * 80}")
        print(f"DETECTION #{self.detection_count} at {timestamp}")
        print(f"Pattern: {shape}")
        print(f"Price: {price:.2f} | Range: {lowest_price:.2f} - {highest_price:.2f}")
        print(f"Generating comprehensive chart (3 panels)...")
        print(f"{'=' * 80}")

        # Generate comprehensive chart
        chart_base64 = self._generate_comprehensive_chart(profile, timestamp, price, shape)

        # Create detection data
        detection_data = {
            'detection_num': self.detection_count,
            'timestamp': timestamp,
            'shape': shape,
            'price': price,
            'profile': profile,
            'signal_record': signal_record,
            'html_path': self.output_html,
        }

        # Update HTML report with chart
        if self.output_html:
            chart_img = ""
            if chart_base64:
                chart_img = f"<div class='detection-figure'><img src='data:image/png;base64,{chart_base64}' style='max-width: 100%; height: auto;'/></div>"

            section_html = (
                "<section class='detection-block'>"
                f"<h2>Detection #{self.detection_count} — {shape.upper()} ({timestamp.strftime('%H:%M:%S')})</h2>"
                f"<div class='detection-meta'>Timestamp: {timestamp} | Price: {price:.2f}</div>"
                f"<pre class='detection-text'>Shape: {shape}\nPrice: {price:.2f}\n"
                f"Bid: {total_bid:.0f} | Ask: {total_ask:.0f}\nLevels: {len(active_prices)}</pre>"
                f"{chart_img}"
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
