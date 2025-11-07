import base64
import io
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import matplotlib
matplotlib.use("Agg")  # Use non-interactive backend
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

from rolling_profile import RollingMarketProfile


class AbsorptionStrategy:
    """
    Market Profile Absorption Pattern Detection Strategy

    Detects d-shape and p-shape absorption patterns using rolling market profiles.
    Generates HTML reports with visualizations and CSV files with signal data.
    """

    def __init__(
        self,
        csv_path: Optional[Path] = None,
        profile_window: int = 20,
        extreme_volume_multiplier: float = 2.0,
        min_price_levels: int = 20,
        min_bid_ask_size: int = 30,
        price_position_threshold: float = 0.3,
        diff_distance: float = 0.0,
        min_volume: int = 10,
        filter_ny_hours: bool = False,
        filter_european_hours: bool = False,
        cooldown_period: int = 60,
        warmup_period: int = 60,
        output_dir: Optional[Path] = None,
        charts_dir: Optional[Path] = None,
    ):
        """
        Initialize the Absorption Strategy.

        Args:
            csv_path: Path to CSV file with tick data
            profile_window: Rolling window size in seconds
            extreme_volume_multiplier: Extreme bar must be N times the second-largest
            min_price_levels: Minimum number of active price levels
            min_bid_ask_size: Minimum absolute size of largest BID/ASK bar
            price_position_threshold: Price position threshold (0-1)
            diff_distance: Minimum absolute price difference
            min_volume: Minimum total volume (BID + ASK)
            filter_ny_hours: Filter for NY trading hours only
            filter_european_hours: Filter for European trading hours only
            cooldown_period: Cooldown period in seconds between detections
            warmup_period: Warmup period in seconds before starting detection
            output_dir: Directory for output CSV files
            charts_dir: Directory for HTML charts
        """
        # Configuration
        self.profile_window = profile_window
        self.extreme_volume_multiplier = extreme_volume_multiplier
        self.min_price_levels = min_price_levels
        self.min_bid_ask_size = min_bid_ask_size
        self.price_position_threshold = price_position_threshold
        self.diff_distance = diff_distance
        self.min_volume = min_volume
        self.filter_ny_hours = filter_ny_hours
        self.filter_european_hours = filter_european_hours
        self.cooldown_period = timedelta(seconds=cooldown_period)
        self.warmup_period = timedelta(seconds=warmup_period)

        # Setup paths
        base_dir = Path(__file__).resolve().parent
        data_dir = base_dir.parent / "data"

        if csv_path is None:
            env_csv = os.getenv("ABSORTION_SOURCE_CSV")
            fichero_origen = "time_and_sales_nq_20250915_redux"
            csv_path = (
                Path(env_csv).expanduser()
                if env_csv
                else (data_dir / f"historic/{fichero_origen}.csv")
            )

        self.csv_path = Path(csv_path).resolve()
        self.output_dir = output_dir or (base_dir.parent / "outputs/absortion_shape")
        self.charts_dir = charts_dir or (base_dir.parent / "charts/detections")

        # Create directories
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

        # State variables
        self.df: Optional[pd.DataFrame] = None
        self.output_html: Optional[Path] = None
        self.output_signals_csv: Optional[Path] = None
        self.signal_records: List[Dict[str, float]] = []
        self.detection_count = 0
        self.last_detection_time: Optional[datetime] = None

        # mpld3 disabled for compatibility
        self.mpld3 = None
        self.plugins = None

    def load_data(self) -> pd.DataFrame:
        """Load and preprocess tick data from CSV."""
        print("Loading data...")

        if not self.csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {self.csv_path}")

        # Detect CSV format
        with open(self.csv_path, "r") as f:
            first_line = f.readline().strip()

        is_dom_format = "DOM_BID" in first_line and "DOM_ASK" in first_line

        if is_dom_format:
            print("Detected DOM format (with JSON columns)")
            df = self._load_dom_format()
        else:
            print("Detected standard format (European CSV: semicolon separator, comma decimal)")
            df = pd.read_csv(self.csv_path, sep=";", decimal=",")
            df["Timestamp"] = pd.to_datetime(df["Timestamp"])

        print(f"Loaded {len(df)} rows")
        print(f"Time range: {df['Timestamp'].min()} to {df['Timestamp'].max()}")

        # Apply time filters
        df = self._apply_time_filters(df)

        print(f"Loaded {len(df)} ticks")
        print(f"Period: {df['Timestamp'].min()} to {df['Timestamp'].max()}")
        print("=" * 80)

        self.df = df
        return df

    def _load_dom_format(self) -> pd.DataFrame:
        """Load CSV with DOM format (malformed quoting)."""
        with open(self.csv_path, "r") as f:
            header = f.readline().strip().split(",")
            rows = []

            for line in f:
                line = line.strip()
                if line.startswith('"') and line.endswith('"'):
                    line = line[1:-1]

                parts = []
                current = ""
                in_dict = 0

                for char in line:
                    if char == "{":
                        in_dict += 1
                    elif char == "}":
                        in_dict -= 1

                    if char == "," and in_dict == 0:
                        parts.append(current)
                        current = ""
                    else:
                        current += char

                if current:
                    parts.append(current)

                if len(parts) >= 4:
                    rows.append(parts[:4])

        df = pd.DataFrame(rows, columns=header[:4])
        df["Timestamp"] = pd.to_datetime(df["Timestamp"])
        df = df.rename(columns={"Price": "Precio", "Size": "Volumen", "Side": "Lado"})
        df["Precio"] = df["Precio"].astype(float)
        df["Volumen"] = df["Volumen"].astype(int)

        return df

    def _apply_time_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply NY/European trading hours filters."""
        if not (self.filter_ny_hours or self.filter_european_hours):
            print("Processing ALL data (no hours filter)")
            return df

        df["hour"] = df["Timestamp"].dt.hour
        df["minute"] = df["Timestamp"].dt.minute
        df["time_minutes"] = df["hour"] * 60 + df["minute"]

        NY_OPEN_MADRID = 15 * 60 + 30
        NY_CLOSE_MADRID = 22 * 60
        EUROPEAN_OPEN_MADRID = 9 * 60
        EUROPEAN_CLOSE_MADRID = 22 * 60

        df_before = len(df)

        if self.filter_ny_hours and self.filter_european_hours:
            df = df[(df["time_minutes"] >= EUROPEAN_OPEN_MADRID) &
                    (df["time_minutes"] < EUROPEAN_CLOSE_MADRID)]
            print(f"Filtered {df_before - len(df)} ticks outside European+NY trading hours")
        elif self.filter_ny_hours:
            df = df[(df["time_minutes"] >= NY_OPEN_MADRID) &
                    (df["time_minutes"] < NY_CLOSE_MADRID)]
            print(f"Filtered {df_before - len(df)} ticks outside NY trading hours")
        else:
            df = df[(df["time_minutes"] >= EUROPEAN_OPEN_MADRID) &
                    (df["time_minutes"] < EUROPEAN_CLOSE_MADRID)]
            print(f"Filtered {df_before - len(df)} ticks outside European trading hours")

        return df

    def evaluate_profile_shape(
        self,
        profile: Dict,
        current_close: Optional[float] = None,
        previous_close: Optional[float] = None
    ) -> str:
        """
        Evaluate the distribution shape of a market profile with STRICT criteria.

        Returns:
            str: 'd_shape', 'p_shape', or 'balanced'
        """
        if not profile or current_close is None or previous_close is None:
            return "balanced"

        # Check minimum price difference
        price_diff = abs(current_close - previous_close)
        if price_diff < self.diff_distance:
            return "balanced"

        # Filter out price levels with no volume
        active_prices = []
        for price in sorted(profile.keys()):
            bid_vol = profile[price].get("BID", 0)
            ask_vol = profile[price].get("ASK", 0)
            if bid_vol > 0 or ask_vol > 0:
                active_prices.append(price)

        # Check minimum number of price levels
        if len(active_prices) < self.min_price_levels:
            return "balanced"

        # Calculate total volumes
        total_bid = sum(profile[p].get("BID", 0) for p in active_prices)
        total_ask = sum(profile[p].get("ASK", 0) for p in active_prices)
        total_volume = total_bid + total_ask

        if total_volume < self.min_volume:
            return "balanced"

        # Calculate price range
        min_price = min(active_prices)
        max_price = max(active_prices)
        price_range = max_price - min_price

        if price_range == 0:
            return "balanced"

        # Calculate price position (0 = bottom, 1 = top)
        price_position = (current_close - min_price) / price_range

        # Get extreme prices
        lowest_2_prices = active_prices[:2] if len(active_prices) >= 2 else active_prices
        highest_2_prices = active_prices[-2:] if len(active_prices) >= 2 else active_prices

        # Get max volumes
        max_bid_value = max((profile[p].get("BID", 0) for p in active_prices), default=0)
        max_ask_value = max((profile[p].get("ASK", 0) for p in active_prices), default=0)

        max_bid_price = max(active_prices, key=lambda p: profile[p].get("BID", 0)) if active_prices else None
        max_ask_price = max(active_prices, key=lambda p: profile[p].get("ASK", 0)) if active_prices else None

        # Combine all volumes to find second-largest
        all_volumes = []
        for p in active_prices:
            if profile[p].get("BID", 0) > 0:
                all_volumes.append(profile[p]["BID"])
            if profile[p].get("ASK", 0) > 0:
                all_volumes.append(profile[p]["ASK"])

        all_volumes_sorted = sorted(all_volumes, reverse=True)
        second_largest_overall = all_volumes_sorted[1] if len(all_volumes_sorted) > 1 else 0

        # Calculate ratios
        bid_ratio = max_bid_value / second_largest_overall if second_largest_overall > 0 else float("inf")
        ask_ratio = max_ask_value / second_largest_overall if second_largest_overall > 0 else float("inf")

        # Check for d_shape
        if (max_bid_value >= self.min_bid_ask_size and
            max_bid_price in lowest_2_prices and
            bid_ratio >= self.extreme_volume_multiplier and
            price_position <= self.price_position_threshold and
            current_close < previous_close):
            return "d_shape"

        # Check for p_shape
        if (max_ask_value >= self.min_bid_ask_size and
            max_ask_price in highest_2_prices and
            ask_ratio >= self.extreme_volume_multiplier and
            price_position >= (1 - self.price_position_threshold) and
            current_close > previous_close):
            return "p_shape"

        return "balanced"

    def plot_detection(
        self,
        detection_num: int,
        detection_time: datetime,
        pattern_type: str,
        profile_now: Dict,
        profile_after_1x: Dict,
        profile_after_2x: Dict,
        highest_price: float,
        lowest_price: float,
        max_ask_price: Optional[float],
        max_bid_price: Optional[float],
        current_price: float,
    ) -> str:
        """Create a 5-panel plot showing market profiles and price movement."""
        fig = plt.figure(figsize=(24, 12))
        gs = fig.add_gridspec(2, 4, hspace=0.3, wspace=0.3)

        ax1 = fig.add_subplot(gs[0, 0])
        ax2 = fig.add_subplot(gs[0, 1])
        ax3 = fig.add_subplot(gs[0, 2])
        ax4 = fig.add_subplot(gs[0, 3])
        ax5 = fig.add_subplot(gs[1, :])

        tooltip_specs = []

        # Helper function to plot market profile
        def plot_market_profile(ax, profile, title, closing_price=None):
            if not profile:
                ax.text(0.5, 0.5, "No data", ha="center", va="center")
                ax.set_title(title)
                return

            prices = sorted(profile.keys())
            bid_volumes = [profile[p]["BID"] for p in prices]
            ask_volumes = [profile[p]["ASK"] for p in prices]

            bar_height = (min(prices[i+1] - prices[i] for i in range(len(prices)-1)) * 0.8
                         if len(prices) > 1 else 0.25 * 0.8)

            bid_bars = ax.barh(prices, [-v for v in bid_volumes], height=bar_height,
                              color=(0.8, 0, 0, 0.8), label="BID",
                              edgecolor="darkred", linewidth=0.5)
            ask_bars = ax.barh(prices, ask_volumes, height=bar_height,
                              color=(0, 0.7, 0, 0.8), label="ASK",
                              edgecolor="darkgreen", linewidth=0.5)

            ax.axvline(x=0, color="black", linewidth=1.5, linestyle="-", alpha=0.7)

            if closing_price is not None and closing_price in prices:
                ax.plot(0, closing_price, "o", color="blue", markersize=10, zorder=5,
                       markeredgecolor="darkblue", markeredgewidth=2)

            max_x = max(max(bid_volumes) if bid_volumes else 1,
                       max(ask_volumes) if ask_volumes else 1) * 1.1
            ax.set_xlim(-max_x, max_x)
            ax.set_xlabel("Volume (BID ← | → ASK)", fontsize=12)
            ax.set_ylabel("Price Level", fontsize=12)
            ax.set_title(title, fontsize=14, fontweight="bold")
            ax.grid(True, alpha=0.3, axis="x")
            ax.legend(loc="upper right", fontsize=11)

        # Get closing prices
        closing_price_now = current_price

        time_after_1x = detection_time + timedelta(seconds=self.profile_window)
        price_data_after_1x = self.df[self.df["Timestamp"] <= time_after_1x]
        closing_price_after_1x = (float(str(price_data_after_1x.iloc[-1]["Precio"]).replace(",", "."))
                                  if len(price_data_after_1x) > 0 else None)

        time_after_2x = detection_time + timedelta(seconds=self.profile_window * 2)
        price_data_after_2x = self.df[self.df["Timestamp"] <= time_after_2x]
        closing_price_after_2x = (float(str(price_data_after_2x.iloc[-1]["Precio"]).replace(",", "."))
                                  if len(price_data_after_2x) > 0 else None)

        # Panel 1-3: Market profiles
        plot_market_profile(ax1, profile_now,
                           f"At Detection\n{detection_time.strftime('%H:%M:%S')}",
                           closing_price_now)
        plot_market_profile(ax2, profile_after_1x,
                           f"After {self.profile_window}s\n{time_after_1x.strftime('%H:%M:%S')}",
                           closing_price_after_1x)
        plot_market_profile(ax3, profile_after_2x,
                           f"After {self.profile_window*2}s\n{time_after_2x.strftime('%H:%M:%S')}",
                           closing_price_after_2x)

        # Panel 4: Price movement
        start_time = detection_time - timedelta(seconds=10)
        end_time = detection_time + timedelta(seconds=60)
        price_data = self.df[(self.df["Timestamp"] >= start_time) &
                             (self.df["Timestamp"] <= end_time)]

        if len(price_data) > 0:
            times_rel = [(t - detection_time).total_seconds() for t in price_data["Timestamp"]]
            prices_plot = price_data["Precio"].values

            bid_mask = price_data["Lado"].str.upper() == "BID"
            ask_mask = price_data["Lado"].str.upper() == "ASK"

            ax4.scatter([t for i, t in enumerate(times_rel) if bid_mask.iloc[i]],
                       [p for i, p in enumerate(prices_plot) if bid_mask.iloc[i]],
                       c="red", s=10, alpha=0.6, label="BID")
            ax4.scatter([t for i, t in enumerate(times_rel) if ask_mask.iloc[i]],
                       [p for i, p in enumerate(prices_plot) if ask_mask.iloc[i]],
                       c="green", s=10, alpha=0.6, label="ASK")

            ax4.set_xlabel("Time (seconds relative to detection)", fontsize=12)
            ax4.set_ylabel("Price", fontsize=12)
            ax4.set_title("Price Movement\n(-10s to +60s)", fontsize=14, fontweight="bold")
            ax4.grid(True, alpha=0.3)

            # Add vertical lines
            for x_pos, color, label in [(0, "blue", "Detection"),
                                        (self.profile_window, "orange", f"+{self.profile_window}s"),
                                        (self.profile_window*2, "purple", f"+{self.profile_window*2}s")]:
                ax4.axvline(x=x_pos, color=color, linewidth=2, linestyle="--",
                           alpha=0.8, label=label, zorder=5)

            ax4.legend(loc="best", fontsize=11)

        # Panel 5: Bid/Ask bubbles
        start_time_bidask = detection_time - timedelta(seconds=self.profile_window)
        end_time_bidask = detection_time + timedelta(seconds=4 * self.profile_window)
        bidask_data = self.df[(self.df["Timestamp"] >= start_time_bidask) &
                              (self.df["Timestamp"] <= end_time_bidask)].copy()

        if len(bidask_data) > 0:
            bidask_data = bidask_data.groupby(["Timestamp", "Lado"], as_index=False).agg({
                "Volumen": "sum",
                "Precio": "mean",
                "Bid": "first",
                "Ask": "first",
            })

            timestamps = bidask_data["Timestamp"].values
            times_rel_seconds = np.array([(t - detection_time).total_seconds() for t in timestamps])

            bid_mask = bidask_data["Lado"].str.upper() == "BID"
            ask_mask = bidask_data["Lado"].str.upper() == "ASK"

            bid_times = times_rel_seconds[bid_mask]
            bid_prices = bidask_data.loc[bid_mask, "Precio"].values
            bid_volumes = bidask_data.loc[bid_mask, "Volumen"].values

            ask_times = times_rel_seconds[ask_mask]
            ask_prices = bidask_data.loc[ask_mask, "Precio"].values
            ask_volumes = bidask_data.loc[ask_mask, "Volumen"].values

            bid_volume_sizes = np.clip(np.sqrt(bid_volumes) * 10, 10, 200)
            ask_volume_sizes = np.clip(np.sqrt(ask_volumes) * 10, 10, 200)

            ax5.scatter(bid_times, bid_prices, s=bid_volume_sizes, color="red", alpha=0.6,
                       edgecolors="darkred", linewidth=0.5, label="Bid")
            ax5.scatter(ask_times, ask_prices, s=ask_volume_sizes, color="green", alpha=0.6,
                       edgecolors="darkgreen", linewidth=0.5, label="Ask")

            ax5.set_xlabel("Seconds relative to detection (0 = detection)", fontsize=12)
            ax5.set_ylabel("Price", fontsize=12)
            ax5.set_title(f"Bid/Ask Bubbles (size=volume)\n(-{self.profile_window}s to +{4*self.profile_window}s)",
                         fontsize=14, fontweight="bold")
            ax5.grid(True, alpha=0.3)

            # Add vertical lines
            for i, (x_pos, color) in enumerate([(0, "blue"), (self.profile_window, "orange"),
                                                 (2*self.profile_window, "purple"),
                                                 (3*self.profile_window, "brown"),
                                                 (4*self.profile_window, "pink")]):
                label = "Detection (0s)" if i == 0 else f"+{x_pos}s"
                ax5.axvline(x=x_pos, color=color, linewidth=2, linestyle="--",
                           alpha=0.8, label=label)

            ax5.legend(loc="best", fontsize=11)

        # Synchronize y-axis scales
        all_prices = []
        if profile_now:
            all_prices.extend(list(profile_now.keys()))
        if profile_after_1x:
            all_prices.extend(list(profile_after_1x.keys()))
        if profile_after_2x:
            all_prices.extend(list(profile_after_2x.keys()))
        if len(price_data) > 0:
            all_prices.extend(price_data["Precio"].values)
        if len(bidask_data) > 0:
            all_prices.extend(bidask_data["Precio"].values)

        if all_prices:
            global_min = min(all_prices)
            global_max = max(all_prices)
            padding = (global_max - global_min) * 0.02
            y_min = global_min - padding
            y_max = global_max + padding

            for ax in [ax1, ax2, ax3, ax4, ax5]:
                ax.set_ylim(y_min, y_max)

        fig.suptitle(f"Detection #{detection_num} - Pattern: {pattern_type}",
                    fontsize=16, fontweight="bold", y=0.98)
        fig.tight_layout()

        # Convert to HTML
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", bbox_inches="tight")
        buffer.seek(0)
        img_b64 = base64.b64encode(buffer.read()).decode("ascii")
        html = (
            "<div class='static-fallback'>"
            "<p>Interactive export requires mpld3. Showing static image instead.</p>"
            f"<img src='data:image/png;base64,{img_b64}' "
            "alt='Market profile detection plot' style='max-width:100%;height:auto;'/>"
            "</div>"
        )

        plt.close(fig)
        return html

    def run(self) -> Dict[str, any]:
        """
        Execute the absorption strategy detection.

        Returns:
            Dict with results: detection_count, html_path, csv_path, signal_records
        """
        # Load data
        if self.df is None:
            self.load_data()

        # Prepare HTML report
        start_ts = self.df["Timestamp"].min()
        end_ts = self.df["Timestamp"].max()
        start_label = start_ts.strftime("%Y%m%d")
        end_label = end_ts.strftime("%Y%m%d")

        if start_label == end_label:
            date_slug = start_label
            title_suffix = start_ts.strftime("%Y-%m-%d")
        else:
            date_slug = f"{start_label}_{end_label}"
            title_suffix = f"{start_ts.strftime('%Y-%m-%d')} – {end_ts.strftime('%Y-%m-%d')}"

        self.output_html = self.charts_dir / f"absorption_report_{date_slug}.html"

        # Write HTML header
        with open(self.output_html, "w", encoding="utf-8") as report:
            report.write(
                "<!DOCTYPE html>\n"
                "<html lang='en'>\n"
                "<head>\n"
                "  <meta charset='utf-8'/>\n"
                f"  <title>Absorption Detections – {title_suffix}</title>\n"
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
                f"  <h1>Absorption Detections – {title_suffix}</h1>\n"
                "  <p>Generated by AbsorptionStrategy</p>\n"
            )

        # Create rolling market profile
        mp = RollingMarketProfile(window=timedelta(seconds=self.profile_window))

        # Reset state
        self.detection_count = 0
        self.last_detection_time = None
        self.signal_records = []

        start_time = self.df["Timestamp"].min()
        warmup_end = start_time + self.warmup_period

        print(f"\nWarmup period: {start_time} to {warmup_end}")
        print(f"Detection starts after: {warmup_end}")
        print(f"Detection criteria:")
        print(f"  - d_shape: BID absorption (price falling, BID concentration in 2 LOWEST prices)")
        print(f"  - p_shape: ASK absorption (price rising, ASK concentration in 2 HIGHEST prices)")
        print(f"  - MIN_PRICE_LEVELS: {self.min_price_levels}")
        print(f"  - MIN_BID_ASK_SIZE: {self.min_bid_ask_size}")
        print(f"  - PRICE_POSITION_THRESHOLD: {self.price_position_threshold*100:.0f}%")
        print(f"  - EXTREME_VOLUME_MULTIPLIER: {self.extreme_volume_multiplier}x")
        print("=" * 80)

        # Process each tick
        previous_close: Optional[float] = None
        total_ticks = len(self.df)
        progress_interval = max(total_ticks // 100, 1)

        for idx, row in enumerate(self.df.itertuples()):
            mp.update(row.Timestamp, row.Precio, row.Volumen, row.Lado)

            if idx % progress_interval == 0:
                percent = (idx / total_ticks) * 100
                print(f"Progress: {percent:5.1f}% ({idx:,}/{total_ticks:,})")

            current_time = row.Timestamp
            current_price = float(str(row.Precio).replace(",", "."))

            # Skip warmup period
            if (current_time - start_time) < self.warmup_period:
                previous_close = current_price
                continue

            # Check cooldown
            if self.last_detection_time is not None:
                if (current_time - self.last_detection_time) < self.cooldown_period:
                    previous_close = current_price
                    continue

            # Get profile
            profile = mp.profile(include_trades=True)
            if not profile:
                previous_close = current_price
                continue

            # Evaluate shape
            profile_shape = self.evaluate_profile_shape(profile, current_price, previous_close)
            previous_close = current_price

            if profile_shape not in ["d_shape", "p_shape"]:
                continue

            # Detection found!
            self._process_detection(current_time, current_price, profile, profile_shape, mp)

        # Finalize HTML
        with open(self.output_html, "a", encoding="utf-8") as report:
            if self.detection_count == 0:
                report.write("<p>No detections matched the criteria.</p>\n")
            report.write("</body></html>\n")

        # Save signals CSV
        if self.signal_records:
            signals_df = pd.DataFrame(self.signal_records)
            data_date = self.df['Timestamp'].min().strftime("%Y%m%d")
            self.output_signals_csv = self.output_dir / f"db_shapes_dom_{data_date}.csv"
            signals_df.to_csv(self.output_signals_csv, index=False, sep=";", decimal=",")
            print(f"Signals CSV: {self.output_signals_csv}")
        else:
            print("No signals recorded; signals CSV not created.")

        print(f"\n{'=' * 80}")
        print(f"Processing complete!")
        print(f"Total ticks processed: {len(self.df)}")
        print(f"Total detections: {self.detection_count}")
        print(f"HTML report: {self.output_html}")
        if self.output_signals_csv:
            print(f"Signals CSV: {self.output_signals_csv}")
        print(f"{'=' * 80}")

        return {
            "detection_count": self.detection_count,
            "html_path": self.output_html,
            "csv_path": self.output_signals_csv,
            "signal_records": self.signal_records,
        }

    def _process_detection(self, current_time, current_price, profile, profile_shape, mp):
        """Process a detected pattern (internal helper)."""
        self.detection_count += 1

        prices = sorted(profile.keys())
        highest_price = prices[-1] if prices else current_price
        lowest_price = prices[0] if prices else current_price

        ask_volumes = {p: profile[p]["ASK"] for p in prices if profile[p]["ASK"] > 0}
        bid_volumes = {p: profile[p]["BID"] for p in prices if profile[p]["BID"] > 0}

        max_ask_price = max(ask_volumes, key=ask_volumes.get) if ask_volumes else None
        max_bid_price = max(bid_volumes, key=bid_volumes.get) if bid_volumes else None

        total_bid = sum(profile[p].get("BID", 0) for p in prices)
        total_ask = sum(profile[p].get("ASK", 0) for p in prices)

        # Record signal
        active_prices = [p for p in prices if profile[p].get("BID", 0) > 0 or profile[p].get("ASK", 0) > 0]
        mid_point = len(active_prices) // 2
        lower_prices = active_prices[:mid_point + (1 if len(active_prices) % 2 == 1 else 0)]
        upper_prices = active_prices[mid_point:]

        lower_bid_volume = sum(profile[p].get("BID", 0) for p in lower_prices)
        upper_ask_volume = sum(profile[p].get("ASK", 0) for p in upper_prices)

        timestamp_str = current_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        self.signal_records.append({
            "timestamp": timestamp_str,
            "shape": profile_shape,
            "close_price": current_price,
            "total_bid": total_bid,
            "total_ask": total_ask,
            "bid_ask_ratio": total_bid / total_ask if total_ask > 0 else 0,
            "num_price_levels": len(active_prices),
        })

        # Compute future profiles
        time_after_1x = current_time + timedelta(seconds=self.profile_window)
        mp_after_1x = RollingMarketProfile(window=timedelta(seconds=self.profile_window))
        ticks_until_after_1x = self.df[(self.df["Timestamp"] > current_time) &
                                        (self.df["Timestamp"] <= time_after_1x)]
        for r in ticks_until_after_1x.itertuples():
            mp_after_1x.update(r.Timestamp, r.Precio, r.Volumen, r.Lado)
        profile_after_1x = mp_after_1x.profile(include_trades=True)

        time_after_2x = current_time + timedelta(seconds=self.profile_window * 2)
        mp_after_2x = RollingMarketProfile(window=timedelta(seconds=self.profile_window))
        ticks_until_after_2x = self.df[(self.df["Timestamp"] > current_time) &
                                        (self.df["Timestamp"] <= time_after_2x)]
        for r in ticks_until_after_2x.itertuples():
            mp_after_2x.update(r.Timestamp, r.Precio, r.Volumen, r.Lado)
        profile_after_2x = mp_after_2x.profile(include_trades=True)

        # Create plot
        print(f"\n{'=' * 80}")
        print(f"DETECTION #{self.detection_count} at {current_time}")
        print(f"Pattern: {profile_shape}")
        print(f"Current Price: {current_price:.2f} | Profile Range: {lowest_price:.2f} - {highest_price:.2f}")
        print(f"{'=' * 80}")

        fig_html = self.plot_detection(
            self.detection_count, current_time, profile_shape,
            profile, profile_after_1x, profile_after_2x,
            highest_price, lowest_price, max_ask_price, max_bid_price, current_price
        )

        # Write to HTML
        section_html = (
            "<section class='detection-block'>"
            f"<h2>Detection #{self.detection_count} — {profile_shape.upper()} ({current_time.strftime('%H:%M:%S')})</h2>"
            f"<div class='detection-meta'>Timestamp: {current_time}</div>"
            f"<div class='detection-figure'>{fig_html}</div>"
            "</section>\n"
        )

        with open(self.output_html, "a", encoding="utf-8") as report:
            report.write(section_html)

        self.last_detection_time = current_time
        print(f"Report updated: {self.output_html}")
