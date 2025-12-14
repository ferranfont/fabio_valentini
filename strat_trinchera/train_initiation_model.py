import pandas as pd
import numpy as np
import os
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
import sys

# clean output encoding
sys.stdout.reconfigure(encoding='utf-8')

def load_data(filepath):
    """
    Load data from CSV, handling European format (semi-colon sep, comma decimal).
    """
    print(f"Loading data from {filepath}...")
    try:
        df = pd.read_csv(filepath, sep=';', decimal=',', low_memory=False)
        # Parse timestamp
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
        # Drop invalid timestamps
        df = df.dropna(subset=['timestamp'])
        df = df.sort_values('timestamp').reset_index(drop=True)
        print("Data loaded successfully.")
        print(df.head())
        print(df.dtypes)
        return df
    except Exception as e:
        print(f"Error loading data: {e}")
        return None

def engineer_features(df):
    """
    Create features for the ML model.
    """
    print("Engineering features...")
    
    # Ensure factor_tps is numeric. If read_csv worked with decimal=',', they should be floats.
    # But mixed types warning suggests otherwise.
    # Force conversion.
    if df['factor_tps'].dtype == 'object':
         df['factor_tps'] = df['factor_tps'].str.replace(',', '.', regex=False)
    
    df['factor_tps'] = pd.to_numeric(df['factor_tps'], errors='coerce').fillna(0)
    df['price'] = pd.to_numeric(df['price'], errors='coerce')
    
    # 1. Lagged Features (History of TPS)
    for i in range(1, 6):
        df[f'factor_tps_lag_{i}'] = df['factor_tps'].shift(i)
        
    # 2. Rolling Stats
    df['factor_tps_mean_5'] = df['factor_tps'].rolling(window=5).mean()
    df['factor_tps_std_5'] = df['factor_tps'].rolling(window=5).std().fillna(0)
    
    # 3. Price Velocity (Price change over last N ticks)
    # Note: timestamp is 1 sec resolution, so this is approx price speed
    df['price_velocity_5'] = df['price'].diff(5)
    
    # Drop NaNs created by shifting
    df = df.dropna()
    return df

def define_labels(df, tps_threshold=4000, price_move_threshold=3.5, future_window=10):
    """
    Heuristic Labeling for 'Initiation':
    - High Factor TPS (Acceleration)
    - Followed by significant price movement in the direction of the break.
    """
    print("Defining heuristic labels...")
    
    # Future price change (looking forward)
    # We want to see if price MOVED significantly in the next 'future_window' steps
    indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=future_window)
    df['future_price_max'] = df['price'].rolling(window=indexer).max()
    df['future_price_min'] = df['price'].rolling(window=indexer).min()
    
    # Directional move magnitude
    df['price_move_up'] = df['future_price_max'] - df['price']
    df['price_move_down'] = df['price'] - df['future_price_min']
    df['max_future_move'] = df[['price_move_up', 'price_move_down']].max(axis=1)
    
    # LABEL LOGIC:
    # 1. High TPS
    # 2. Significant follow-through (price move)
    # This filters out "noise" or "exhaustion" where TPS is high but price reverses or stops.
    df['is_initiation'] = (
        (df['factor_tps'] > tps_threshold) & 
        (df['max_future_move'] >= price_move_threshold)
    ).astype(int)
    
    print(f"Total samples: {len(df)}")
    print(f"Initiation signals found (heuristic): {df['is_initiation'].sum()}")
    
    return df

def train_model(df):
    """
    Train Random Forest Classifier.
    """
    print("Training Random Forest model...")
    
    # Features to use
    features = [c for c in df.columns if 'lag' in c or 'mean' in c or 'std' in c or c == 'factor_tps']
    X = df[features]
    y = df['is_initiation']
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42, stratify=y)
    
    # Train
    # Class weight balanced because Initiation is likely rare
    clf = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced')
    clf.fit(X_train, y_train)
    
    # Evaluate
    print("\n--- Model Evaluation ---")
    y_pred = clf.predict(X_test)
    print(classification_report(y_test, y_pred))
    
    # Feature Importance
    print("\n--- Feature Importance ---")
    importances = pd.DataFrame({
        'feature': features,
        'importance': clf.feature_importances_
    }).sort_values('importance', ascending=False)
    print(importances.head(10))
    
    return clf

import joblib

def save_model(model, filepath):
    print(f"Saving model to {filepath}...")
    joblib.dump(model, filepath)

def load_model_from_file(filepath):
    print(f"Loading model from {filepath}...")
    return joblib.load(filepath)

if __name__ == "__main__":
    # FILE IS HARDCODED for this task as requested
    CSV_PATH = r"d:\PYTHON\ALGOS\fabio_valentini\strat_trinchera\outputs\tick_record_20251212_132509.csv"
    
    df = load_data(CSV_PATH)
    if df is not None:
        df = engineer_features(df)
        df = define_labels(df)
        if df['is_initiation'].sum() > 0:
            model = train_model(df)
            print("\nModel training complete.")
            # Save for demo
            save_model(model, os.path.join(os.path.dirname(CSV_PATH), 'initiation_model.pkl'))
        else:
            print(f"No 'Initiation' events found. Max TPS: {df['factor_tps'].max()}, Max Move: {df['max_future_move'].max()}")
