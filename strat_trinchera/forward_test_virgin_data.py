import pandas as pd
import sys
import os

# Add current dir to path to import analyze script
sys.path.append(os.path.dirname(__file__))
from visualize_ai_signals import visualize_signals

def process_and_run_forward_test(csv_path, model_path=None):
    print(f"Loading virgin data from {csv_path}...")
    try:
        # Load Raw Data
        df = pd.read_csv(csv_path, sep=';', decimal=',')
        print(f"Raw rows: {len(df)}")
        print(df.head())
        
        # Rename Cols
        # Timestamp;Precio;Volumen;Lado;Bid;Ask
        df = df.rename(columns={
            'Timestamp': 'timestamp',
            'Precio': 'price',
            'Volumen': 'window_vol' # Trade volume
        })
        
        # Parse Timestamp
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
        df = df.dropna(subset=['timestamp'])
        
        # Resample to 1 Second
        print("Resampling to 1-second intervals...")
        df = df.set_index('timestamp')
        
        resampled = df.resample('1S').agg({
            'price': 'last',
            'window_vol': 'sum'
        })
        
        # Calculate TPS (Ticks Per Second) = Count of ticks in that second
        resampled['tps'] = df['price'].resample('1S').count()
        
        # Reset index to get timestamp back as col
        resampled = resampled.reset_index()
        
        # Filter empty seconds
        resampled = resampled[resampled['tps'] > 0].copy()
        
        # Calculate Factor TPS
        # Logic: window_vol * tps
        resampled['factor_tps'] = resampled['window_vol'] * resampled['tps']
        
        print(f"Aggregated rows: {len(resampled)}")
        print("Sample processed features:")
        print(resampled[['timestamp', 'price', 'factor_tps', 'tps', 'window_vol']].head())
        
        # Run Visualization
        print("Running AI Model Visualization...")
        visualize_signals(csv_path=None, df=resampled, model_path=model_path)
        
    except Exception as e:
        print(f"Error processing virgin data: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    VIRGIN_CSV = r"d:\PYTHON\ALGOS\fabio_valentini\data\historic\time_and_sales_nq_20251104.csv"
    # Pre-trained model path (will be created by train_initiation_model.py)
    MODEL_PATH = r"d:\PYTHON\ALGOS\fabio_valentini\strat_trinchera\outputs\initiation_model.pkl"
    process_and_run_forward_test(VIRGIN_CSV, MODEL_PATH)
