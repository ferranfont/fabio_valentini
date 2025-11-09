from __future__ import annotations

"""
Herramienta de diagnóstico para las señales d_shape / p_shape.

Objetivos:
1. Resamplear el tape tick a barras de 1 minuto con métricas de tendencia y volatilidad.
2. Medir forward-returns (en puntos y en %) a distintos horizontes para cada señal.
3. Evaluar las señales en el contexto de EMA30 vs EMA100 y distancia a VWAP.

Uso:
    python analyze_shapes.py

Personalización a través de variables de entorno:
    REV_SIGNALS_CSV -> Ruta del CSV de señales (por defecto último db_shapes_dom_*.csv)
    REV_TNS_CSV     -> Ruta del CSV principal de Time & Sales
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


# =============================================================================
# Rutas raíz
# =============================================================================
THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
REPORTS_DIR = PROJECT_ROOT / "outputs" / "rev_diagnostics"

# Archivos por defecto
DEFAULT_TNS = DATA_DIR / "time_and_sales_20251031_074530.csv"
DEFAULT_SIGNALS = None  # Determinado dinámicamente

# Horizontes de evaluación (en minutos)
FWD_HORIZONS = (5, 10, 20, 40, 80)

# Umbral de rango neutral para EMA30-EMA100 (en puntos)
EMA_NEUTRAL_THRESHOLD = 5.0


# =============================================================================
# Utilidades generales
# =============================================================================
def _resolve_latest_signals() -> Path | None:
    """Devuelve el archivo de señales más reciente si existe."""
    candidates: list[tuple[float, Path]] = []
    for pattern in ("db_shapes_dom_*.csv", "db_shapes_*.csv"):
        for path in OUTPUTS_DIR.glob(pattern):
            try:
                candidates.append((path.stat().st_mtime, path))
            except FileNotFoundError:
                continue

    if not candidates:
        return None

    _, latest = max(candidates, key=lambda item: item[0])
    return latest


def _choose_signals_file() -> Path:
    """Obtiene la ruta al CSV de señales."""
    override = os.getenv("REV_SIGNALS_CSV")
    if override:
        return Path(override).expanduser()

    resolved = _resolve_latest_signals()
    if resolved is not None:
        return resolved

    raise FileNotFoundError("No se encontró ningún archivo db_shapes*.csv en outputs/")


def _choose_tns_file() -> Path:
    override = os.getenv("REV_TNS_CSV")
    if override:
        return Path(override).expanduser()
    return DEFAULT_TNS


def _read_semicolon_csv(path: Path, usecols: Iterable[str] | None = None) -> pd.DataFrame:
    """Lee CSV con separador ';' y decimales ','."""
    df = pd.read_csv(
        path,
        sep=";",
        decimal=",",
        usecols=usecols,
        engine="python",
    )
    return df


def _to_float(series: pd.Series) -> pd.Series:
    """Convierte serie con formato europeo (coma decimal) a float."""
    if pd.api.types.is_numeric_dtype(series):
        return series.astype(float)

    cleaned = series.astype(str).str.replace("\xa0", "", regex=False).str.strip()
    cleaned = cleaned.replace({"": np.nan, "nan": np.nan, "None": np.nan})

    mask_comma = cleaned.str.contains(",", regex=False, na=False)
    cleaned.loc[mask_comma] = cleaned.loc[mask_comma].str.replace(".", "", regex=False)
    cleaned = cleaned.str.replace(",", ".", regex=False)

    return pd.to_numeric(cleaned, errors="coerce")


# =============================================================================
# Lectura de datos
# =============================================================================
def load_signals(path: Path) -> pd.DataFrame:
    df = _read_semicolon_csv(path)
    df.columns = df.columns.str.strip().str.lower()

    required = {"timestamp", "shape", "close_price"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas en señales: {missing}")

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["shape"] = df["shape"].str.strip().str.lower()
    df["close_price"] = _to_float(df["close_price"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    return df


def load_ticks(path: Path) -> pd.DataFrame:
    usecols = ["Timestamp", "Precio", "Volumen"]
    df = _read_semicolon_csv(path, usecols=usecols)
    df.columns = ["timestamp", "price", "volume"]
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["price"] = _to_float(df["price"])
    df["volume"] = _to_float(df["volume"])

    df = df.dropna(subset=["timestamp"]).sort_values("timestamp").set_index("timestamp")
    return df


# =============================================================================
# Transformaciones de series
# =============================================================================
def build_minute_bars(df_ticks: pd.DataFrame) -> pd.DataFrame:
    """
    Agrega ticks a una serie de 1 minuto con:
        close, volume, ema30, ema100, ema200, vwap60, volatilidad (atr proxy),
        forward returns en puntos y porcentaje.
    """
    df_min = pd.DataFrame()
    df_min["close"] = df_ticks["price"].resample("1min").last().ffill().dropna()
    df_min["volume"] = df_ticks["volume"].resample("1min").sum().fillna(0.0)

    # Indicadores de tendencia
    df_min["ema30"] = df_min["close"].ewm(span=30, adjust=False).mean()
    df_min["ema100"] = df_min["close"].ewm(span=100, adjust=False).mean()
    df_min["ema200"] = df_min["close"].ewm(span=200, adjust=False).mean()
    df_min["ema_diff"] = df_min["ema30"] - df_min["ema100"]
    df_min["ema30_slope"] = df_min["ema30"].diff()

    # VWAP rolling 60 minutos
    tpv = (df_min["close"] * df_min["volume"]).rolling(window=60, min_periods=1).sum()
    vol_rolling = df_min["volume"].rolling(window=60, min_periods=1).sum()
    df_min["vwap60"] = tpv / vol_rolling.replace({0.0: np.nan})
    df_min["dist_vwap"] = df_min["close"] - df_min["vwap60"]

    # Proxy de volatilidad: media móvil de rango absoluto
    df_min["abs_return_pts"] = df_min["close"].diff().abs()
    df_min["atr30_pts"] = df_min["abs_return_pts"].rolling(window=30, min_periods=1).mean()

    # Forward returns
    for horizon in FWD_HORIZONS:
        future_price = df_min["close"].shift(-horizon)
        df_min[f"fwd_pts_{horizon}"] = future_price - df_min["close"]
        df_min[f"fwd_ret_{horizon}"] = (future_price / df_min["close"]) - 1.0

    return df_min


def classify_trend(ema_diff: float) -> str:
    if np.isnan(ema_diff):
        return "unknown"
    if ema_diff > EMA_NEUTRAL_THRESHOLD:
        return "bull"
    if ema_diff < -EMA_NEUTRAL_THRESHOLD:
        return "bear"
    return "neutral"


@dataclass
class SummaryResult:
    shape: str
    trend: str
    horizon: int
    count: int
    win_rate: float
    avg_pts: float
    median_pts: float
    p95_pts: float
    p05_pts: float
    avg_ret: float
    sharpe_like: float


def summarize_signals(df_events: pd.DataFrame) -> pd.DataFrame:
    results: list[SummaryResult] = []

    for shape in ("d_shape", "p_shape"):
        df_shape = df_events[df_events["shape"] == shape]
        if df_shape.empty:
            continue

        for trend in ("bull", "neutral", "bear"):
            subset = df_shape[df_shape["trend_regime"] == trend]
            if subset.empty:
                continue

            for horizon in FWD_HORIZONS:
                pts_col = f"fwd_pts_{horizon}"
                ret_col = f"fwd_ret_{horizon}"

                valid = subset[pts_col].notna()
                if valid.sum() < 10:
                    continue

                sub_valid = subset.loc[valid]
                direction = np.where(sub_valid["shape"] == "d_shape", 1.0, -1.0)

                pts = sub_valid[pts_col].to_numpy() * direction
                rets = sub_valid[ret_col].to_numpy() * direction

                avg_pts = float(np.mean(pts))
                median_pts = float(np.median(pts))
                p95 = float(np.quantile(pts, 0.95))
                p05 = float(np.quantile(pts, 0.05))
                win_rate = float(np.mean(pts > 0.0))
                avg_ret = float(np.mean(rets))
                std_ret = float(np.std(rets, ddof=1))
                sharpe_like = avg_ret / std_ret if std_ret > 1e-9 else np.nan

                results.append(
                    SummaryResult(
                        shape=shape,
                        trend=trend,
                        horizon=horizon,
                        count=int(valid.sum()),
                        win_rate=win_rate,
                        avg_pts=avg_pts,
                        median_pts=median_pts,
                        p95_pts=p95,
                        p05_pts=p05,
                        avg_ret=avg_ret,
                        sharpe_like=sharpe_like,
                    )
                )

    return pd.DataFrame([r.__dict__ for r in results])


def attach_context(df_signals: pd.DataFrame, df_minute: pd.DataFrame) -> pd.DataFrame:
    df_signals = df_signals.copy()
    df_signals["minute"] = df_signals["timestamp"].dt.floor("min")

    merged = pd.merge(
        df_signals,
        df_minute,
        how="left",
        left_on="minute",
        right_index=True,
        suffixes=("", "_minute"),
    )

    merged["trend_regime"] = merged["ema_diff"].apply(classify_trend)
    merged["direction"] = np.where(merged["shape"] == "d_shape", 1.0, -1.0)

    # Distancia normalizada a VWAP para filtros potenciales
    merged["vwap_z"] = merged["dist_vwap"] / merged["atr30_pts"].replace({0.0: np.nan})

    return merged


def export_summary(summary: pd.DataFrame, df_events: pd.DataFrame, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    summary_path = dest_dir / "rev_forward_stats.csv"
    events_path = dest_dir / "rev_signal_events.csv"

    summary.to_csv(summary_path, index=False)
    df_events.to_csv(events_path, index=False)

    print(f"\n[OK] Resumen guardado en {summary_path}")
    print(f"[OK] Eventos con contexto guardados en {events_path}")


def main() -> None:
    signals_path = _choose_signals_file()
    tns_path = _choose_tns_file()

    print("=" * 80)
    print("ANÁLISIS REVERSIÓN d_shape / p_shape")
    print("=" * 80)
    print(f"Señales: {signals_path}")
    print(f"Tape   : {tns_path}")

    if not signals_path.exists():
        raise FileNotFoundError(signals_path)
    if not tns_path.exists():
        raise FileNotFoundError(tns_path)

    print("\n> Cargando señales...")
    df_signals = load_signals(signals_path)
    print(f"  {len(df_signals):,} filas | {df_signals['shape'].value_counts().to_dict()}")

    print("\n> Cargando tape tick...")
    df_ticks = load_ticks(tns_path)
    print(f"  {len(df_ticks):,} ticks desde {df_ticks.index.min()} hasta {df_ticks.index.max()}")

    print("\n> Resampleando a 1 minuto...")
    df_minute = build_minute_bars(df_ticks)
    print(f"  {len(df_minute):,} barras de minuto")

    print("\n> Uniendo señales con contexto de barra...")
    df_events = attach_context(df_signals, df_minute)
    matched = df_events["close"].notna().sum()
    print(f"  Señales con datos minuto disponibles: {matched} ({matched / len(df_events):.1%})")

    print("\n> Calculando métricas forward...")
    summary_df = summarize_signals(df_events)
    if summary_df.empty:
        print("No se pudieron calcular métricas (insuficientes datos tras merge).")
        return

    summary_df = summary_df.sort_values(["shape", "trend", "horizon"]).reset_index(drop=True)
    pd.set_option("display.float_format", lambda x: f"{x:0.4f}")

    print("\n--- Métricas por tipo de señal / tendencia ---")
    display_cols = [
        "shape",
        "trend",
        "horizon",
        "count",
        "win_rate",
        "avg_pts",
        "median_pts",
        "p95_pts",
        "p05_pts",
        "avg_ret",
        "sharpe_like",
    ]
    print(summary_df[display_cols].to_string(index=False))

    print("\n> Guardando reportes detallados...")
    export_summary(summary_df, df_events, REPORTS_DIR)


if __name__ == "__main__":
    main()
