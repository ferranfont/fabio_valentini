import pandas as pd
import numpy as np
import os

def process_historical_file(input_file, output_file, window_ms=500, tps_window_sec=10):
    print(f"I: Loading data from {input_file}...")
    
    # Load Data (European format: ; sep, comma dec)
    # Using low_memory=False to avoid mixed type warnings on large files
    df = pd.read_csv(input_file, sep=';', decimal=',', low_memory=False)
    
    # Clean and Parse Timestamp
    # Assuming Format: 2025-11-04 00:00:00.021
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
    df = df.dropna(subset=['Timestamp']).sort_values('Timestamp')
    
    # Ensure numeric columns
    numeric_cols = ['Precio', 'Volumen', 'Bid', 'Ask']
    for col in numeric_cols:
        if col in df.columns:
            # Handle string conversions if necessary (replace , with .)
            if df[col].dtype == 'object':
                 df[col] = df[col].str.replace(',', '.', regex=False)
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    print("I: Data loaded. Calculating features...")
    
    # --- Feature 1: Window Volume (Rolling 500ms) ---
    # We use a time-based rolling window on the timestamp index
    
    # Set timestamp as index for rolling operations
    df_indexed = df.set_index('Timestamp').sort_index()
    
    # 1. Window Volume (Sum of 'Volumen' in last 500ms)
    # Note: '500ms' usually means "Volume observed in the LAST 500ms window ending at current tick"
    df_indexed['window_vol'] = df_indexed['Volumen'].rolling(window=f'{window_ms}ms', closed='right').sum()
    
    # --- Feature 2: TPS Window (Ticks per Second in last 10s) ---
    # REVISED LOGIC to match Live Client "Instantaneous Rate"
    # Live Logic: TPS = Count / (Time_Last_Tick - Time_Oldest_Tick_In_Window)
    # This captures "burst" speed (e.g. 100 ticks in 0.1s = 1000 TPS)
    
    # 1. Count of ticks in last 10s
    # (Assuming 1 row = 1 tick, or use Volumen count if rows are aggregated? Live uses tick_timestamps list len)
    # If historical data is 1 row per tick, .count() is correct.
    window_count = df_indexed['Volumen'].rolling(window=f'{tps_window_sec}s', closed='right').count()
    
    # 2. Duration of the window (Time Span of the ticks actually present)
    # We need: Current_Time - Oldest_Time_In_Window
    # We can get Oldest_Time by rolling min on the index (Timestamp)
    # Note: rolling on index is slightly tricky, we can use the column 'Timestamp' if we didn't drop it.
    # We kept 'Timestamp' in df_result later, but df_indexed has it as index.
    
    # Create a Series for timestamp calculation
    # Rolling min on timestamps might convert to float, need to handle carefully.
    # Alternatively: df.index is datetime.
    # rolling().min() works on numeric.
    
    # Workaround: Convert to int64 (nanoseconds), roll, convert back
    ts_numerics = df_indexed.index.astype(np.int64)
    ts_series = pd.Series(ts_numerics, index=df_indexed.index)
    
    min_ts_in_window = ts_series.rolling(window=f'{tps_window_sec}s', closed='right').min()
    
    # Current timestamp (as int64)
    current_ts = ts_series
    
    # Duration in Seconds
    # (Current - Min) / 1e9
    duration_sec = (current_ts - min_ts_in_window) / 1e9
    
    # Avoid division by zero (if only 1 tick or duration is 0)
    # Live client: "if len > 1 else 1" for duration denominator roughly. 
    # Actually live code: if window_duration > 0. If 0, then 0.
    
    # Vectorized safety:
    # If duration < 0.001 (very small), clamp it? Or set TPS high? 
    # Live client: `if window_duration > 0 else 0`. 
    # But if 100 ticks arrive in 0.0s (same timestamp)? duration=0. 
    # Live code: timestamps are appended. current_time is datetime.now().
    # In processed data, unique timestamps might be same.
    # Let's set a minimum duration floor (e.g. 1ms or 0.001s) to avoid Inf, 
    # but close to reality (burst).
    
    # If duration is 0 (single tick), count is 1. TPS = 1/duration?
    # Let's use max(duration, 0.001) if count > 1.
    
    df_indexed['window_duration'] = duration_sec
    df_indexed['window_count'] = window_count
    
    def calc_tps(row):
        cnt = row['window_count']
        dur = row['window_duration']
        if cnt <= 1:
            return 0 # Or 1? Live client: len > 1 else 1 (denominator). so 1/1=1. 
            # If current_time - oldest is 0. 
        if dur <= 0.001:
             return cnt # Burst! effectively / 1 sec? No.
             # If 2 ticks in 0 sec. Live client would likely see 0 duration -> TPS=0.
             # Let's verify live code: `ticks_per_sec_window = len / window_duration if window_duration > 0 else 0`
             # So if burst in 0ms, TPS is 0 in live client? That seems like a bug in live client if so, 
             # but we strictly match it.
             return 0 
        return cnt / dur

    df_indexed['tps_window'] = df_indexed.apply(calc_tps, axis=1)
    
    # --- Feature 3: Factor TPS (Acceleration) ---
    # Formula: factor_tps = window_vol * tps_window
    df_indexed['factor_tps'] = df_indexed['window_vol'] * df_indexed['tps_window']
    
    # --- Reset Index to preserve Timestamp column ---
    df_result = df_indexed.reset_index()
    
    # Select columns as requested: Timestamp, Precio, Volumen, Lado, Bid, Ask, Window_vol, tps_window, factor_tps
    cols_to_keep = ['Timestamp', 'Precio', 'Volumen', 'Lado', 'Bid', 'Ask', 'window_vol', 'tps_window', 'factor_tps']
    # Filter for columns that actually exist
    cols_to_keep = [c for c in cols_to_keep if c in df_result.columns]
    
    df_final = df_result[cols_to_keep]
    
    print(f"I: Saving {len(df_final)} rows to {output_file}...")
    df_final.to_csv(output_file, index=False, sep=';', decimal=',')
    print(f"I: Done. Saved to {output_file}")

if __name__ == "__main__":
    # Input: Historical Data
    INPUT_CSV = r"d:\PYTHON\ALGOS\fabio_valentini\data\historic\time_and_sales_nq_20251211.csv"
    # Check if 20251103 exists, if not try 20251104 which was used before
    if not os.path.exists(INPUT_CSV):
        print(f"W: Input {INPUT_CSV} not found. Trying 20251211...")
        INPUT_CSV = r"d:\PYTHON\ALGOS\fabio_valentini\data\historic\time_and_sales_nq_20251211.csv"
        
    OUTPUT_CSV = os.path.join(os.path.dirname(__file__), 'outputs', 'processed_ticks_historical.csv')
    
    # Create outputs dir if needed
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    
    process_historical_file(INPUT_CSV, OUTPUT_CSV)
