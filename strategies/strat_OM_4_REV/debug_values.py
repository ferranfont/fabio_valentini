from pathlib import Path

import pandas as pd

from analyze_shapes import _to_float, _read_semicolon_csv


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    tns_path = project_root / "data" / "time_and_sales_20251031_074530.csv"
    signals_path = project_root / "outputs" / "db_shapes_dom_20251101_150013.csv"

    df_ticks = _read_semicolon_csv(tns_path, usecols=["Timestamp", "Precio"]).head(5)
    df_ticks["Precio_float"] = _to_float(df_ticks["Precio"])
    print("Ticks sample:\n", df_ticks)

    df_signals = _read_semicolon_csv(signals_path, usecols=["timestamp", "shape", "close_price"]).head(5)
    df_signals["close_price_float"] = _to_float(df_signals["close_price"])
    print("\nSignals sample:\n", df_signals)


if __name__ == "__main__":
    main()
