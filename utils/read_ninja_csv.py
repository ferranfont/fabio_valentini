import os
import glob
import pandas as pd
import matplotlib.pyplot as plt

# ============================================================
# CONFIGURACIÓN
# ============================================================
BASE_DIR = r"C:\Users\ferra\Documents\NinjaTrader 8\ticks"
SHOW_ROWS = 15     # cuántas últimas filas mostrar

# ============================================================
# FUNCIONES AUXILIARES
# ============================================================
def parse_times(df):
    """Convierte columnas con 'time' en datetime."""
    for col in df.columns:
        if 'time' in col.lower():
            df[col] = pd.to_datetime(df[col], errors='coerce')
    return df


def load_latest_files(base_dir):
    """Encuentra y carga los archivos más recientes de TS y Ticks."""
    files_ts = glob.glob(os.path.join(base_dir, "*_TS.csv"))
    files_ticks = glob.glob(os.path.join(base_dir, "*_Ticks.csv"))

    if not files_ts or not files_ticks:
        raise FileNotFoundError("No se encontraron archivos TS o Ticks en la carpeta.")

    latest_ts = max(files_ts, key=os.path.getctime)
    latest_ticks = max(files_ticks, key=os.path.getctime)

    print(f"Leyendo TS   : {latest_ts}")
    print(f"Leyendo Ticks: {latest_ticks}")

    df_ts = pd.read_csv(latest_ts, sep=';', engine='python')
    df_ticks = pd.read_csv(latest_ticks, sep=';', engine='python')

    df_ts = parse_times(df_ts)
    df_ticks = parse_times(df_ticks)

    return df_ts, df_ticks


def merge_by_time(df_ticks, df_ts, tolerance_ms=300):
    """Combina ambos DataFrames por columna de tiempo."""
    # Detectar nombres de columna con 'time'
    tick_time = next((c for c in df_ticks.columns if 'time' in c.lower()), None)
    ts_time   = next((c for c in df_ts.columns if 'time' in c.lower()), None)

    if not tick_time or not ts_time:
        print("⚠️  No se encontraron columnas de tiempo para hacer merge.")
        return None

    df_ticks = df_ticks.sort_values(tick_time)
    df_ts    = df_ts.sort_values(ts_time)

    merged = pd.merge_asof(
        df_ticks, df_ts,
        left_on=tick_time, right_on=ts_time,
        direction="backward",
        tolerance=pd.Timedelta(f"{tolerance_ms}ms")
    )
    return merged


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    if not os.path.isdir(BASE_DIR):
        raise FileNotFoundError(f"No existe la carpeta: {BASE_DIR}")

    df_ts, df_ticks = load_latest_files(BASE_DIR)

    # Mostrar últimas filas
    print("\n=== ÚLTIMAS FILAS T&S ===")
    print(df_ts.tail(SHOW_ROWS).to_string(index=False))

    print("\n=== ÚLTIMAS FILAS TICKS ===")
    print(df_ticks.tail(SHOW_ROWS).to_string(index=False))

    # Detectar nombres de columnas de tiempo (antes del merge para usarlos en el plot)
    tick_time = next((c for c in df_ticks.columns if 'time' in c.lower()), None)
    ts_time = next((c for c in df_ts.columns if 'time' in c.lower()), None)

    # Merge opcional
    merged = merge_by_time(df_ticks, df_ts)
    if merged is not None:
        print("\n=== ÚLTIMAS FILAS MERGE ===")
        print(merged.tail(SHOW_ROWS).to_string(index=False))

        # Plot rápido
        plt.figure(figsize=(10,4))
        if 'last_ts' in merged.columns:
            plt.plot(merged[ts_time], merged['last_ts'], label="TS last")
        elif 'last' in df_ts.columns:
            plt.plot(df_ts[ts_time], df_ts['last'], label="TS last")
        else:
            plt.plot(df_ticks[tick_time], df_ticks.iloc[:, 2], label="Ticks precio")

        plt.title("Últimos precios registrados")
        plt.xlabel("Tiempo")
        plt.ylabel("Precio")
        plt.legend()
        plt.tight_layout()
        plt.show()
