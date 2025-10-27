"""
Fractal Detection for NQ Futures - Find Price Pivot Points
Detects peaks and valleys using Zigzag algorithm on time_and_sales data
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from enum import Enum


# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

# Input file
INPUT_FILE = "ts_and_dom_24_oct.csv"  # Use time_and_sales_nq.csv or ts_and_dom_24_oct.csv

# Zigzag parameters for MINOR structure (smaller fractals)
MIN_CHANGE_PCT_MINOR = 0.02 # 0.008% minimum change for minor pivot detection
# Zigzag parameters for MAJOR structure (larger fractals)
MIN_CHANGE_PCT_MAJOR = 0.10  # 0.10% minimum change for major pivot detection (5x larger)

# Aggregation window (in seconds) - create OHLC candles from ticks
AGGREGATION_WINDOW = 60  # 60 seconds = 1 minute candles

# Preview window (in minutes) - time before fractal for sequence replay
PREVIEW = 1  # 1 minute before fractal


# =============================================================================
# CLASSES
# =============================================================================

class ZigzagDirection(Enum):
    UP = "up"      # Pico (máximo)
    DOWN = "down"  # Valle (mínimo)


class ZigzagPoint:
    def __init__(self, index: int, price: float, direction: ZigzagDirection, timestamp: Optional[str] = None):
        self.index = index
        self.price = price
        self.direction = direction
        self.timestamp = timestamp
        self.confirmed = False

    def __repr__(self):
        tipo = "PICO" if self.direction == ZigzagDirection.UP else "VALLE"
        return f"{tipo} @ idx={self.index}, price={self.price:.2f}, ts={self.timestamp}"


class UnifiedZigzagDetector:
    def __init__(self, min_change_pct: float = 0.15):
        """
        Detector Zigzag unificado que procesa High/Low y garantiza alternancia

        Args:
            min_change_pct: Cambio mínimo en porcentaje (ej: 0.15 = 0.15%)
        """
        self.min_change_pct = min_change_pct / 100.0  # Convertir a decimal

        # Estado del detector
        self.candles = []  # Lista de velas (dict con High, Low, index)
        self.current_trend = None  # None, UP (buscando pico), DOWN (buscando valle)
        self.last_pivot = None  # Último punto de giro confirmado

        # Buffer para tracking
        self.current_high = None  # Máximo actual desde último valle
        self.current_high_index = None
        self.current_high_timestamp = None  # Timestamp donde ocurrió el high
        self.current_low = None   # Mínimo actual desde último pico
        self.current_low_index = None
        self.current_low_timestamp = None  # Timestamp donde ocurrió el low

        # Puntos de giro detectados
        self.zigzag_points = []

    def add_candle(self, high: float, low: float, index: int, timestamp: str = None) -> Optional[ZigzagPoint]:
        """
        Añade una nueva vela y retorna un punto zigzag si se detecta

        Args:
            high: Precio máximo de la vela
            low: Precio mínimo de la vela
            index: Índice de la vela
            timestamp: Timestamp de la vela (opcional)

        Returns:
            ZigzagPoint si se confirma un punto de giro, None en caso contrario
        """
        candle = {'high': high, 'low': low, 'index': index, 'timestamp': timestamp}
        self.candles.append(candle)

        # Primera vela - inicializar
        if len(self.candles) == 1:
            self.current_high = high
            self.current_high_index = index
            self.current_high_timestamp = timestamp
            self.current_low = low
            self.current_low_index = index
            self.current_low_timestamp = timestamp
            return None

        # Segunda vela - determinar tendencia inicial
        if len(self.candles) == 2:
            if high > self.current_high:
                self.current_high = high
                self.current_high_index = index
                self.current_high_timestamp = timestamp
            if low < self.current_low:
                self.current_low = low
                self.current_low_index = index
                self.current_low_timestamp = timestamp

            # Establecer tendencia inicial basada en qué se movió más
            high_change = (self.current_high - self.candles[0]['high']) / self.candles[0]['high']
            low_change = (self.candles[0]['low'] - self.current_low) / self.candles[0]['low']

            if high_change > low_change:
                self.current_trend = ZigzagDirection.UP  # Buscando pico
                # Primer punto es un valle
                self.last_pivot = ZigzagPoint(
                    self.current_low_index,
                    self.current_low,
                    ZigzagDirection.DOWN,
                    self.current_low_timestamp  # Usar timestamp del low
                )
            else:
                self.current_trend = ZigzagDirection.DOWN  # Buscando valle
                # Primer punto es un pico
                self.last_pivot = ZigzagPoint(
                    self.current_high_index,
                    self.current_high,
                    ZigzagDirection.UP,
                    self.current_high_timestamp  # Usar timestamp del high
                )
            return None

        return self._check_for_pivot(candle)

    def _check_for_pivot(self, candle: dict) -> Optional[ZigzagPoint]:
        """
        Verifica si la vela actual constituye un punto de giro
        """
        high = candle['high']
        low = candle['low']
        index = candle['index']
        timestamp = candle.get('timestamp')

        # Actualizar extremos actuales
        if high > self.current_high:
            self.current_high = high
            self.current_high_index = index
            self.current_high_timestamp = timestamp  # Guardar timestamp donde ocurrió el high
        if low < self.current_low:
            self.current_low = low
            self.current_low_index = index
            self.current_low_timestamp = timestamp  # Guardar timestamp donde ocurrió el low

        if not self.last_pivot:
            return None

        # Si estamos buscando un pico (tendencia alcista)
        if self.current_trend == ZigzagDirection.UP:
            # Verificar si hay una caída significativa desde el máximo actual
            if self.current_high > self.last_pivot.price:  # Nuevo máximo
                change_from_high = (self.current_high - low) / self.current_high
                if change_from_high >= self.min_change_pct:
                    # Confirmar el pico
                    pivot = ZigzagPoint(
                        self.current_high_index,
                        self.current_high,
                        ZigzagDirection.UP,
                        self.current_high_timestamp  # ✓ Usar timestamp donde ocurrió el high
                    )
                    pivot.confirmed = True
                    self.zigzag_points.append(pivot)
                    self.last_pivot = pivot
                    self.current_trend = ZigzagDirection.DOWN  # Ahora buscar valle

                    # Reiniciar tracking para el próximo valle
                    self.current_low = low
                    self.current_low_index = index
                    self.current_low_timestamp = timestamp

                    return pivot

        # Si estamos buscando un valle (tendencia bajista)
        elif self.current_trend == ZigzagDirection.DOWN:
            # Verificar si hay una subida significativa desde el mínimo actual
            if self.current_low < self.last_pivot.price:  # Nuevo mínimo
                change_from_low = (high - self.current_low) / self.current_low
                if change_from_low >= self.min_change_pct:
                    # Confirmar el valle
                    pivot = ZigzagPoint(
                        self.current_low_index,
                        self.current_low,
                        ZigzagDirection.DOWN,
                        self.current_low_timestamp  # ✓ Usar timestamp donde ocurrió el low
                    )
                    pivot.confirmed = True
                    self.zigzag_points.append(pivot)
                    self.last_pivot = pivot
                    self.current_trend = ZigzagDirection.UP  # Ahora buscar pico

                    # Reiniciar tracking para el próximo pico
                    self.current_high = high
                    self.current_high_index = index
                    self.current_high_timestamp = timestamp

                    return pivot

        return None

    def get_zigzag_points(self) -> List[ZigzagPoint]:
        """
        Retorna todos los puntos zigzag detectados
        """
        return self.zigzag_points.copy()

    def get_last_pivot(self) -> Optional[ZigzagPoint]:
        """
        Retorna el último punto de giro confirmado
        """
        return self.last_pivot

    def reset(self):
        """
        Reinicia el detector
        """
        self.candles.clear()
        self.current_trend = None
        self.last_pivot = None
        self.current_high = None
        self.current_high_index = None
        self.current_high_timestamp = None
        self.current_low = None
        self.current_low_index = None
        self.current_low_timestamp = None
        self.zigzag_points.clear()


# =============================================================================
# MAIN PROCESSING
# =============================================================================

def load_tick_data(csv_path: Path) -> pd.DataFrame:
    """
    Load tick data from CSV file
    """
    print(f"[INFO] Loading tick data from: {csv_path.name}")

    # Try to detect the separator
    with open(csv_path, 'r') as f:
        first_line = f.readline()

    # Determine separator
    if ';' in first_line and first_line.count(';') > first_line.count(','):
        # European format
        df = pd.read_csv(csv_path, sep=';', decimal=',')
    else:
        # Standard format - only load necessary columns to avoid JSON parsing issues
        # Read only the first 2 columns (Timestamp and Price)
        df = pd.read_csv(csv_path, usecols=[0, 1], names=['Timestamp', 'Price'], header=0)

    # Rename Price column to Precio if it exists
    if 'Price' in df.columns:
        df = df.rename(columns={'Price': 'Precio'})

    print(f"[OK] Loaded {len(df):,} ticks")
    print(f"[INFO] Columns: {list(df.columns)}")

    # Parse timestamp
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    df = df.sort_values('Timestamp').reset_index(drop=True)

    # Add tick index for reference
    df['tick_index'] = df.index

    return df


def create_ohlc_candles(df_ticks: pd.DataFrame, window_seconds: int) -> pd.DataFrame:
    """
    Aggregate tick data into OHLC candles

    Args:
        df_ticks: DataFrame with tick data
        window_seconds: Aggregation window in seconds

    Returns:
        DataFrame with OHLC candles
    """
    print(f"\n[INFO] Creating OHLC candles ({window_seconds}s window)...")

    # Set timestamp as index
    df_ticks = df_ticks.set_index('Timestamp')

    # Resample to create OHLC (use lowercase 's' for seconds)
    resampler = df_ticks['Precio'].resample(f'{window_seconds}s')

    ohlc = pd.DataFrame({
        'open': resampler.first(),
        'high': resampler.max(),
        'low': resampler.min(),
        'close': resampler.last()
    })

    # Remove candles with NaN (no ticks in that window)
    ohlc = ohlc.dropna()

    print(f"[OK] Created {len(ohlc):,} candles")

    return ohlc


def detect_fractals_from_ticks(df_ticks: pd.DataFrame, min_change_pct: float) -> List[ZigzagPoint]:
    """
    Detect fractal pivot points directly from tick data (NO AGGREGATION)

    Args:
        df_ticks: DataFrame with tick data (Timestamp, Precio, tick_index)
        min_change_pct: Minimum percentage change for pivot detection

    Returns:
        List of ZigzagPoint objects with exact tick-level precision
    """
    print(f"\n[INFO] Detecting fractals from TICKS (min_change={min_change_pct:.3f}%)...")
    print(f"[INFO] Processing {len(df_ticks):,} ticks...")

    fractals = []

    # Initialize zigzag tracking
    current_direction = None  # UP (searching for peak) or DOWN (searching for valley)
    last_pivot_price = None
    last_pivot_idx = None
    last_pivot_ts = None

    current_high = None
    current_high_idx = None
    current_high_ts = None

    current_low = None
    current_low_idx = None
    current_low_ts = None

    # Process each tick
    for idx, row in df_ticks.iterrows():
        price = row['Precio']
        tick_idx = row['tick_index']
        timestamp = row['Timestamp'].strftime('%Y-%m-%d %H:%M:%S')

        # First tick - initialize
        if current_direction is None:
            current_high = price
            current_high_idx = tick_idx
            current_high_ts = timestamp
            current_low = price
            current_low_idx = tick_idx
            current_low_ts = timestamp
            last_pivot_price = price
            last_pivot_idx = tick_idx
            last_pivot_ts = timestamp
            current_direction = ZigzagDirection.UP  # Start searching for first peak
            continue

        # Update current extremes
        if price > current_high:
            current_high = price
            current_high_idx = tick_idx
            current_high_ts = timestamp
        if price < current_low:
            current_low = price
            current_low_idx = tick_idx
            current_low_ts = timestamp

        # If searching for PEAK (UP trend)
        if current_direction == ZigzagDirection.UP:
            if current_high > last_pivot_price:
                # Check if price dropped enough from high to confirm peak
                change_from_high = (current_high - price) / current_high
                if change_from_high >= min_change_pct / 100.0:
                    # Confirm PEAK
                    fractal = ZigzagPoint(
                        index=current_high_idx,
                        price=current_high,
                        direction=ZigzagDirection.UP,
                        timestamp=current_high_ts
                    )
                    fractal.confirmed = True
                    fractals.append(fractal)

                    # Switch to searching for valley
                    current_direction = ZigzagDirection.DOWN
                    last_pivot_price = current_high
                    last_pivot_idx = current_high_idx
                    last_pivot_ts = current_high_ts

                    # Reset low tracking
                    current_low = price
                    current_low_idx = tick_idx
                    current_low_ts = timestamp

        # If searching for VALLEY (DOWN trend)
        elif current_direction == ZigzagDirection.DOWN:
            if current_low < last_pivot_price:
                # Check if price rose enough from low to confirm valley
                change_from_low = (price - current_low) / current_low
                if change_from_low >= min_change_pct / 100.0:
                    # Confirm VALLEY
                    fractal = ZigzagPoint(
                        index=current_low_idx,
                        price=current_low,
                        direction=ZigzagDirection.DOWN,
                        timestamp=current_low_ts
                    )
                    fractal.confirmed = True
                    fractals.append(fractal)

                    # Switch to searching for peak
                    current_direction = ZigzagDirection.UP
                    last_pivot_price = current_low
                    last_pivot_idx = current_low_idx
                    last_pivot_ts = current_low_ts

                    # Reset high tracking
                    current_high = price
                    current_high_idx = tick_idx
                    current_high_ts = timestamp

    print(f"[OK] Detected {len(fractals)} fractals")

    # Count picos and valles
    picos = [f for f in fractals if f.direction == ZigzagDirection.UP]
    valles = [f for f in fractals if f.direction == ZigzagDirection.DOWN]

    print(f"[INFO] Picos: {len(picos)}")
    print(f"[INFO] Valles: {len(valles)}")

    # Verify alternation
    alternancia_correcta = True
    for i in range(1, len(fractals)):
        if fractals[i].direction == fractals[i-1].direction:
            alternancia_correcta = False
            print(f"[WARNING] Alternancia incorrecta en índices {fractals[i-1].index} y {fractals[i].index}")

    if alternancia_correcta:
        print(f"[OK] Alternancia correcta verificada")

    return fractals


def save_fractals_to_csv(fractals: List[ZigzagPoint], df_ticks: pd.DataFrame,
                         output_path: Path, preview_minutes: int = 1):
    """
    Save detected fractals to CSV file with preview index

    Args:
        fractals: List of detected fractals
        df_ticks: DataFrame with original tick data
        output_path: Output CSV file path
        preview_minutes: Minutes before fractal for preview (default: 1)
    """
    print(f"\n[INFO] Saving fractals to CSV...")
    print(f"[INFO] Preview window: {preview_minutes} minute(s) before fractal")

    # Convert to DataFrame
    data = []
    for f in fractals:
        tipo = "PICO" if f.direction == ZigzagDirection.UP else "VALLE"

        # Get the timestamp of the fractal (already exact tick timestamp)
        fractal_ts = pd.to_datetime(f.timestamp)

        # Calculate timestamp N minutes before
        preview_ts = fractal_ts - pd.Timedelta(minutes=preview_minutes)

        # Find the closest tick index to the preview timestamp
        preview_idx = None
        if not df_ticks.empty:
            # Find the tick closest to preview_ts but not after fractal_ts
            mask = (df_ticks['Timestamp'] >= preview_ts) & (df_ticks['Timestamp'] <= fractal_ts)
            preview_ticks = df_ticks[mask]

            if not preview_ticks.empty:
                # Get the first tick in the preview window
                preview_idx = preview_ticks.iloc[0]['tick_index']
            else:
                # If no ticks in window, get the closest one before
                earlier_ticks = df_ticks[df_ticks['Timestamp'] <= preview_ts]
                if not earlier_ticks.empty:
                    preview_idx = earlier_ticks.iloc[-1]['tick_index']

        # The fractal_tick_index is already stored in f.index (exact tick index)
        fractal_tick_idx = f.index

        data.append({
            'tick_index': f.index,  # Exact tick index where fractal occurred
            'timestamp': f.timestamp,
            'price': f.price,
            'type': tipo,
            'direction': f.direction.value,
            'confirmed': f.confirmed,
            'preview_tick_index': preview_idx if preview_idx is not None else 'N/A',
            'fractal_tick_index': fractal_tick_idx,
            'preview_minutes': preview_minutes
        })

    df = pd.DataFrame(data)

    # Save with European format
    df.to_csv(output_path, sep=';', decimal=',', index=False)

    print(f"[OK] Fractals saved to: {output_path}")
    print(f"[INFO] Total records: {len(df)}")
    print(f"[INFO] Preview tick indices calculated for {preview_minutes} minute(s) before each fractal")


def main():
    """
    Main execution function
    """
    print("="*70)
    print("FRACTAL DETECTION - Tick-Level ZigZag Analysis (NO AGGREGATION)")
    print("="*70)
    print(f"\nInput file: {INPUT_FILE}")
    print(f"Detection method: TICK-LEVEL (exact precision)")
    print(f"Minor structure change: {MIN_CHANGE_PCT_MINOR}%")
    print(f"Major structure change: {MIN_CHANGE_PCT_MAJOR}%")
    print(f"Preview window: {PREVIEW} minute(s)")
    print("-"*70)

    # 1. Load tick data
    csv_path = DATA_DIR / INPUT_FILE
    if not csv_path.exists():
        print(f"\n[ERROR] File not found: {csv_path}")
        return

    df_ticks = load_tick_data(csv_path)

    # 2. Detect MINOR fractals directly from ticks (NO AGGREGATION)
    print(f"\n[INFO] Detecting MINOR fractals ({MIN_CHANGE_PCT_MINOR}%)...")
    fractals_minor = detect_fractals_from_ticks(df_ticks, MIN_CHANGE_PCT_MINOR)

    # 3. Detect MAJOR fractals directly from ticks (NO AGGREGATION)
    print(f"[INFO] Detecting MAJOR fractals ({MIN_CHANGE_PCT_MAJOR}%)...")
    fractals_major = detect_fractals_from_ticks(df_ticks, MIN_CHANGE_PCT_MAJOR)

    # 4. Save both results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Save minor fractals
    output_file_minor = OUTPUTS_DIR / f"zig_zag_fractals_minor_{timestamp}.csv"
    OUTPUTS_DIR.mkdir(exist_ok=True)
    save_fractals_to_csv(fractals_minor, df_ticks, output_file_minor, PREVIEW)

    # Save major fractals
    output_file_major = OUTPUTS_DIR / f"zig_zag_fractals_major_{timestamp}.csv"
    save_fractals_to_csv(fractals_major, df_ticks, output_file_major, PREVIEW)

    # 5. Display summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Input ticks: {len(df_ticks):,}")
    print(f"Detection method: TICK-LEVEL (no aggregation)")
    print(f"\nMINOR Fractals detected: {len(fractals_minor)}")
    print(f"  - Picos: {len([f for f in fractals_minor if f.direction == ZigzagDirection.UP])}")
    print(f"  - Valles: {len([f for f in fractals_minor if f.direction == ZigzagDirection.DOWN])}")
    print(f"  - Output: {output_file_minor.name}")
    print(f"\nMAJOR Fractals detected: {len(fractals_major)}")
    print(f"  - Picos: {len([f for f in fractals_major if f.direction == ZigzagDirection.UP])}")
    print(f"  - Valles: {len([f for f in fractals_major if f.direction == ZigzagDirection.DOWN])}")
    print(f"  - Output: {output_file_major.name}")
    print(f"\nPreview window: {PREVIEW} minute(s) before fractal")
    print("="*70)

    # 6. Automatically execute plot_fractals.py to visualize results
    print("\n" + "="*70)
    print("AUTO-EXECUTING VISUALIZATIONS")
    print("="*70)

    import subprocess

    # Execute plot_fractals.py (ZigZag chart)
    print("[INFO] Launching plot_fractals.py (ZigZag chart)...")
    plot_script = PROJECT_ROOT / "strat_fractal" / "plot_fractals.py"

    try:
        result = subprocess.run(
            ["python", str(plot_script)],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0:
            print("[OK] ZigZag visualization completed successfully")
        else:
            print(f"[WARNING] ZigZag visualization returned error code: {result.returncode}")
            if result.stderr:
                print(f"[ERROR] {result.stderr}")
    except subprocess.TimeoutExpired:
        print("[WARNING] ZigZag visualization timed out")
    except Exception as e:
        print(f"[WARNING] Could not execute ZigZag visualization: {e}")
        print(f"[INFO] You can manually run: python strat_fractal/plot_fractals.py")

    # Execute test_fractal.py (Tick data with vertical lines)
    print("\n[INFO] Launching test_fractal.py (Tick data chart with fractal markers)...")
    test_script = PROJECT_ROOT / "strat_fractal" / "test_fractal.py"

    try:
        result = subprocess.run(
            ["python", str(test_script)],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0:
            print("[OK] Tick data visualization completed successfully")
        else:
            print(f"[WARNING] Tick data visualization returned error code: {result.returncode}")
            if result.stderr:
                print(f"[ERROR] {result.stderr}")
    except subprocess.TimeoutExpired:
        print("[WARNING] Tick data visualization timed out")
    except Exception as e:
        print(f"[WARNING] Could not execute tick data visualization: {e}")
        print(f"[INFO] You can manually run: python strat_fractal/test_fractal.py")


if __name__ == "__main__":
    main()
