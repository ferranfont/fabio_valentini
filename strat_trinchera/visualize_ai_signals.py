import pandas as pd
import matplotlib.pyplot as plt
import sys
import os

# Import functions from the training script to reuse loading/feature engineering
# (Assuming they are in the same folder)
import joblib
sys.path.append(os.path.dirname(__file__))
from train_initiation_model import load_data, engineer_features, define_labels, train_model, load_model_from_file

def visualize_signals(csv_path=None, df=None, model_path=None):
    # 1. Pipeline Re-run
    if df is None:
        if csv_path:
            df = load_data(csv_path)
        else:
            print("Error: Must provide csv_path or df")
            return
    
    if df is None: return
    
    # Check required columns
    required_cols = ['factor_tps', 'price', 'timestamp']
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        print(f"Missing columns for visualization: {missing_cols}")
        return
    
    df = engineer_features(df)
    df = define_labels(df)

    print("Data loaded and features engineered.")
    
    # Check if we have signals
    num_signals = df['is_initiation'].sum()
    print(f"Number of signals found: {num_signals}")
    
    if num_signals == 0:
        print("No initiation signals found to verify. Force plotting anyway for debug.")
        # return # COMMENTED OUT TO FORCE PLOT
    
    # 2. Train Model (Real-world: Load saved model. Here: Retrain for demo)
    if model_path and os.path.exists(model_path):
        print(f"Loading pre-trained model from {model_path}...")
        model = load_model_from_file(model_path)
    else:
        print("Training model from scratch...")
        model = train_model(df)
    
    # 3. Predict (on same data for visualization purposes)
    print("Predicting...")
    features = [c for c in df.columns if 'lag' in c or 'mean' in c or 'std' in c or c == 'factor_tps']
    X = df[features]
    df['prob_initiation'] = model.predict_proba(X)[:, 1]
    df['pred_initiation'] = (df['prob_initiation'] > 0.5).astype(int)
    
    
    # 4. Plot (Interactive with Plotly)
    print("Plotting with Plotly...")
    
    # Create Figure
    import plotly.graph_objects as go
    fig = go.Figure()

    # Price Line
    fig.add_trace(go.Scatter(
        x=df['timestamp'], 
        y=df['price'], 
        mode='lines', 
        name='Price', 
        line=dict(color='gray', width=1),
        opacity=0.5
    ))

    # Signals
    signals = df[df['pred_initiation'] == 1].copy()
    print(f"Predicted signals count: {len(signals)}")
    
    # Split by direction
    if 'price_velocity_5' not in signals.columns:
        signals['price_velocity_5'] = signals['price'].diff(5).fillna(0)
    
    signals_up = signals[signals['price_velocity_5'] > 0]
    signals_down = signals[signals['price_velocity_5'] <= 0]
    
    # Plot UP signals (Green)
    fig.add_trace(go.Scatter(
        x=signals_up['timestamp'], 
        y=signals_up['price'], 
        mode='markers', 
        name='Initiation (Buy/Up)', 
        marker=dict(
            color='green', 
            size=8, 
            symbol='circle',
            line=dict(width=1, color='darkgreen')
        )
    ))
    
    # Plot DOWN signals (Red)
    fig.add_trace(go.Scatter(
        x=signals_down['timestamp'], 
        y=signals_down['price'], 
        mode='markers', 
        name='Initiation (Sell/Down)', 
        marker=dict(
            color='red', 
            size=8, 
            symbol='circle',
            line=dict(width=1, color='darkred')
        )
    ))

    fig.update_layout(
        title='AI Signal Detection: Initiation (Random Forest)',
        xaxis_title='Time',
        yaxis_title='Price',
        template='plotly_white',
        hovermode=False, # Disable hover info
        xaxis=dict(showgrid=False) # Remove vertical grid
    )

    # Output Directory Logic
    if csv_path:
        output_dir = os.path.dirname(csv_path)
    else:
        output_dir = os.path.join(os.path.dirname(__file__), 'outputs')
        os.makedirs(output_dir, exist_ok=True)
    
    # Determine Output Name based on context
    base_name = 'ai_signals_chart'
    if csv_path and 'virgin' in csv_path: 
         base_name += '_virgin'
    elif df is not None and len(df) < 100000: 
         base_name += '_virgin'
         
    output_html = os.path.join(output_dir, f'{base_name}.html')
    print(f"Saving interactive chart to {output_html}...")
    fig.write_html(output_html)
    print(f"Chart saved to: {output_html}")

    # Save Signals to CSV
    output_csv = os.path.join(output_dir, f'{base_name}.csv')
    print(f"Saving signals to {output_csv}...")
    signals[['timestamp', 'price', 'factor_tps', 'prob_initiation', 'price_velocity_5']].to_csv(output_csv, index=False, sep=';', decimal=',')
    print(f"Signals saved to: {output_csv}")

if __name__ == "__main__":
    CSV_PATH = r"d:\PYTHON\ALGOS\fabio_valentini\strat_trinchera\outputs\tick_record_20251212_132509.csv"
    visualize_signals(CSV_PATH)
