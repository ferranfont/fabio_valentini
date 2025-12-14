"""
Analyze correlation between TPS (tick speed) and Window Volume
"""
import pandas as pd
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt

# Read CSV
input_file = r'd:\PYTHON\ALGOS\fabio_valentini\strat_trinchera\outputs\tick_record_20251212_132509.csv'

print("Reading CSV...")
df = pd.read_csv(input_file, sep=';', decimal=',')
df.columns = df.columns.str.strip()

print(f"Total records: {len(df):,}")
print(f"Columns: {list(df.columns)}")

# Convert timestamp
df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed', errors='coerce', utc=True)
df['timestamp'] = df['timestamp'].dt.tz_localize(None)
df = df.dropna(subset=['timestamp'])

# We need TPS window - calculate it if not in CSV
if 'tps_window' not in df.columns:
    print("\nCalculating TPS window...")
    df = df.sort_values('timestamp').reset_index(drop=True)

    start_time = df['timestamp'].min()
    df['seconds'] = (df['timestamp'] - start_time).dt.total_seconds()

    window_seconds = 10
    tps_window_values = []

    # Sample for speed
    sample_rate = 10
    sample_indices = list(range(0, len(df), sample_rate))

    print(f"  Processing {len(sample_indices):,} sample points...")

    for idx in sample_indices:
        current_sec = df.loc[idx, 'seconds']
        window_start = current_sec - window_seconds

        in_window = (df['seconds'] > window_start) & (df['seconds'] <= current_sec)
        count = in_window.sum()

        if count > 1:
            window_data = df.loc[in_window, 'seconds']
            duration = current_sec - window_data.min()
            tps = count / duration if duration > 0 else count
        else:
            tps = 1.0

        tps_window_values.append(tps)

    tps_sampled = pd.Series(tps_window_values, index=sample_indices)
    df['tps_window'] = tps_sampled.reindex(df.index).interpolate(method='linear').bfill().ffill()
    df = df.drop('seconds', axis=1)

# Now analyze correlation
print("\n" + "="*60)
print("CORRELATION ANALYSIS: TPS vs WINDOW VOLUME")
print("="*60)

# Basic statistics
print(f"\nTPS Window Statistics:")
print(f"  Mean: {df['tps_window'].mean():.2f}")
print(f"  Median: {df['tps_window'].median():.2f}")
print(f"  Min: {df['tps_window'].min():.2f}")
print(f"  Max: {df['tps_window'].max():.2f}")
print(f"  Std Dev: {df['tps_window'].std():.2f}")

print(f"\nWindow Volume Statistics:")
print(f"  Mean: {df['window_vol'].mean():.2f}")
print(f"  Median: {df['window_vol'].median():.2f}")
print(f"  Min: {df['window_vol'].min():.2f}")
print(f"  Max: {df['window_vol'].max():.2f}")
print(f"  Std Dev: {df['window_vol'].std():.2f}")

# Calculate Pearson correlation
pearson_corr, pearson_p = stats.pearsonr(df['tps_window'], df['window_vol'])

print(f"\n{'='*60}")
print(f"PEARSON CORRELATION COEFFICIENT: {pearson_corr:.4f}")
print(f"P-value: {pearson_p:.2e}")
print(f"{'='*60}")

# Interpretation
print("\nINTERPRETATION:")
if abs(pearson_corr) >= 0.7:
    strength = "FUERTE"
elif abs(pearson_corr) >= 0.4:
    strength = "MODERADA"
elif abs(pearson_corr) >= 0.2:
    strength = "DEBIL"
else:
    strength = "MUY DEBIL o NULA"

direction = "POSITIVA" if pearson_corr > 0 else "NEGATIVA"

print(f"  Correlacion {strength} {direction}")
print(f"  R-squared: {pearson_corr**2:.4f} ({pearson_corr**2*100:.2f}% varianza explicada)")

if pearson_corr > 0.7:
    print("\n  >>> ALTA CORRELACION POSITIVA:")
    print("      Cuando TPS aumenta, window_vol tambien aumenta")
    print("      Relacion muy fuerte entre velocidad de ticks y volumen")
elif pearson_corr > 0.4:
    print("\n  >>> CORRELACION MODERADA POSITIVA:")
    print("      Existe tendencia: mayor TPS -> mayor volumen")
    print("      Pero hay otros factores tambien importantes")
elif pearson_corr > 0:
    print("\n  >>> CORRELACION POSITIVA DEBIL:")
    print("      Poca relacion entre TPS y volumen")
else:
    print("\n  >>> CORRELACION NEGATIVA:")
    print("      Relacion inversa (raro en este contexto)")

# Spearman correlation (rank-based, more robust to outliers)
spearman_corr, spearman_p = stats.spearmanr(df['tps_window'], df['window_vol'])

print(f"\n{'='*60}")
print(f"SPEARMAN CORRELATION (rank-based): {spearman_corr:.4f}")
print(f"P-value: {spearman_p:.2e}")
print(f"{'='*60}")

# Conditional analysis
print(f"\n{'='*60}")
print("CONDITIONAL ANALYSIS")
print(f"{'='*60}")

# High TPS periods
high_tps_threshold = df['tps_window'].quantile(0.90)
high_tps = df[df['tps_window'] >= high_tps_threshold]

print(f"\nWhen TPS is HIGH (>= {high_tps_threshold:.2f}, top 10%):")
print(f"  Average window_vol: {high_tps['window_vol'].mean():.2f}")
print(f"  Median window_vol: {high_tps['window_vol'].median():.2f}")
print(f"  Max window_vol: {high_tps['window_vol'].max():.2f}")

# Low TPS periods
low_tps_threshold = df['tps_window'].quantile(0.10)
low_tps = df[df['tps_window'] <= low_tps_threshold]

print(f"\nWhen TPS is LOW (<= {low_tps_threshold:.2f}, bottom 10%):")
print(f"  Average window_vol: {low_tps['window_vol'].mean():.2f}")
print(f"  Median window_vol: {low_tps['window_vol'].median():.2f}")
print(f"  Max window_vol: {low_tps['window_vol'].max():.2f}")

# High volume periods
high_vol_threshold = 200  # BIG_VOLUME_TRIGGER
high_vol = df[df['window_vol'] >= high_vol_threshold]

print(f"\nWhen VOLUME is HIGH (>= {high_vol_threshold}):")
print(f"  Count: {len(high_vol):,} events ({len(high_vol)/len(df)*100:.2f}%)")
print(f"  Average TPS: {high_vol['tps_window'].mean():.2f}")
print(f"  Median TPS: {high_vol['tps_window'].median():.2f}")
print(f"  Max TPS: {high_vol['tps_window'].max():.2f}")

# Normal volume periods
normal_vol = df[df['window_vol'] < high_vol_threshold]

print(f"\nWhen VOLUME is NORMAL (< {high_vol_threshold}):")
print(f"  Count: {len(normal_vol):,} ({len(normal_vol)/len(df)*100:.2f}%)")
print(f"  Average TPS: {normal_vol['tps_window'].mean():.2f}")
print(f"  Median TPS: {normal_vol['tps_window'].median():.2f}")

# Ratio comparison
print(f"\n{'='*60}")
print("RATIO ANALYSIS")
print(f"{'='*60}")
ratio_high_low_vol = high_vol['tps_window'].mean() / normal_vol['tps_window'].mean()
ratio_high_low_tps = high_tps['window_vol'].mean() / low_tps['window_vol'].mean()

print(f"\nTPS ratio (high vol / normal vol): {ratio_high_low_vol:.2f}x")
print(f"Volume ratio (high TPS / low TPS): {ratio_high_low_tps:.2f}x")

if ratio_high_low_vol > 1.5:
    print("\n  >>> Alto volumen esta asociado con TPS significativamente mayor")
if ratio_high_low_tps > 1.5:
    print("  >>> Alto TPS esta asociado con volumen significativamente mayor")

print("\n" + "="*60)
print("CONCLUSION")
print("="*60)

if pearson_corr > 0.5:
    print("""
  La velocidad de llegada de ticks (TPS) y el volumen de ventana
  estan MODERADAMENTE/FUERTEMENTE correlacionados.

  Esto significa:
  - Cuando el mercado recibe muchos ticks por segundo, el volumen
    agregado en la ventana de 500ms tambien tiende a ser alto
  - La actividad del mercado se manifiesta simultaneamente en ambas
    metricas
  - Son indicadores complementarios de la intensidad del trading
    """)
elif pearson_corr > 0.2:
    print("""
  La correlacion es DEBIL pero POSITIVA.

  Esto significa:
  - Hay cierta tendencia: mas TPS -> mas volumen
  - Pero la relacion no es fuerte
  - Pueden ocurrir muchos ticks pequenos (alta TPS, bajo volumen)
  - O pocos ticks grandes (baja TPS, alto volumen)
  - Son metricas parcialmente independientes
    """)
else:
    print("""
  La correlacion es MUY DEBIL o NULA.

  Esto significa:
  - TPS y volumen son metricas bastante independientes
  - Alta velocidad de ticks NO implica necesariamente alto volumen
  - Se pueden usar como indicadores complementarios independientes
    """)

print("="*60)
