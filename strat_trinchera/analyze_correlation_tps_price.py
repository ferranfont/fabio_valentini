"""
Analyze correlation between TPS (tick speed) and Price
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

# Convert price to float
df['price'] = df['price'].astype(float)

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

# Calculate price changes
df['price_change'] = df['price'].diff()
df['price_change_pct'] = df['price'].pct_change() * 100

# Calculate absolute price change (volatility)
df['abs_price_change'] = df['price_change'].abs()

# Now analyze correlation
print("\n" + "="*60)
print("CORRELATION ANALYSIS: TPS vs PRICE")
print("="*60)

# Basic statistics
print(f"\nPrice Statistics:")
print(f"  Mean: {df['price'].mean():.2f}")
print(f"  Median: {df['price'].median():.2f}")
print(f"  Min: {df['price'].min():.2f}")
print(f"  Max: {df['price'].max():.2f}")
print(f"  Range: {df['price'].max() - df['price'].min():.2f} points")
print(f"  Std Dev: {df['price'].std():.2f}")

print(f"\nTPS Window Statistics:")
print(f"  Mean: {df['tps_window'].mean():.2f}")
print(f"  Median: {df['tps_window'].median():.2f}")
print(f"  Min: {df['tps_window'].min():.2f}")
print(f"  Max: {df['tps_window'].max():.2f}")
print(f"  Std Dev: {df['tps_window'].std():.2f}")

# Calculate Pearson correlation (TPS vs absolute price level)
pearson_corr_level, pearson_p_level = stats.pearsonr(df['tps_window'], df['price'])

print(f"\n{'='*60}")
print(f"TPS vs PRICE LEVEL (absolute value)")
print(f"{'='*60}")
print(f"PEARSON CORRELATION: {pearson_corr_level:.4f}")
print(f"P-value: {pearson_p_level:.2e}")

# Interpretation
if abs(pearson_corr_level) >= 0.7:
    strength = "FUERTE"
elif abs(pearson_corr_level) >= 0.4:
    strength = "MODERADA"
elif abs(pearson_corr_level) >= 0.2:
    strength = "DEBIL"
else:
    strength = "MUY DEBIL o NULA"

direction = "POSITIVA" if pearson_corr_level > 0 else "NEGATIVA"

print(f"\nCorrelacion {strength} {direction}")
print(f"R-squared: {pearson_corr_level**2:.4f} ({pearson_corr_level**2*100:.2f}% varianza explicada)")

# Calculate correlation with price CHANGES (more relevant)
df_changes = df.dropna(subset=['price_change'])

pearson_corr_change, pearson_p_change = stats.pearsonr(
    df_changes['tps_window'],
    df_changes['abs_price_change']
)

print(f"\n{'='*60}")
print(f"TPS vs PRICE VOLATILITY (absolute price change)")
print(f"{'='*60}")
print(f"PEARSON CORRELATION: {pearson_corr_change:.4f}")
print(f"P-value: {pearson_p_change:.2e}")

if abs(pearson_corr_change) >= 0.7:
    strength = "FUERTE"
elif abs(pearson_corr_change) >= 0.4:
    strength = "MODERADA"
elif abs(pearson_corr_change) >= 0.2:
    strength = "DEBIL"
else:
    strength = "MUY DEBIL o NULA"

direction = "POSITIVA" if pearson_corr_change > 0 else "NEGATIVA"

print(f"\nCorrelacion {strength} {direction}")
print(f"R-squared: {pearson_corr_change**2:.4f} ({pearson_corr_change**2*100:.2f}% varianza explicada)")

if pearson_corr_change > 0.3:
    print("\n  >>> IMPORTANTE:")
    print("      Mayor TPS esta asociado con MAYOR VOLATILIDAD de precio")
    print("      Cuando el mercado esta activo (alto TPS), el precio se mueve mas")
elif pearson_corr_change > 0.1:
    print("\n  >>> Hay cierta tendencia:")
    print("      Mayor TPS -> precio mas volatil, pero la relacion es debil")
else:
    print("\n  >>> TPS y volatilidad de precio son casi independientes")

# Spearman correlations
spearman_corr_level, spearman_p_level = stats.spearmanr(df['tps_window'], df['price'])
spearman_corr_change, spearman_p_change = stats.spearmanr(
    df_changes['tps_window'],
    df_changes['abs_price_change']
)

print(f"\n{'='*60}")
print(f"SPEARMAN CORRELATIONS (rank-based)")
print(f"{'='*60}")
print(f"TPS vs Price Level: {spearman_corr_level:.4f} (p={spearman_p_level:.2e})")
print(f"TPS vs Price Volatility: {spearman_corr_change:.4f} (p={spearman_p_change:.2e})")

# Conditional analysis - HIGH TPS periods
print(f"\n{'='*60}")
print("CONDITIONAL ANALYSIS: HIGH TPS PERIODS")
print(f"{'='*60}")

high_tps_threshold = df['tps_window'].quantile(0.90)
high_tps = df[df['tps_window'] >= high_tps_threshold].copy()
high_tps['abs_price_change'] = high_tps['price'].diff().abs()

low_tps_threshold = df['tps_window'].quantile(0.10)
low_tps = df[df['tps_window'] <= low_tps_threshold].copy()
low_tps['abs_price_change'] = low_tps['price'].diff().abs()

print(f"\nWhen TPS is HIGH (>= {high_tps_threshold:.2f}, top 10%):")
print(f"  Count: {len(high_tps):,} ticks")
print(f"  Average price: {high_tps['price'].mean():.2f}")
print(f"  Price std dev: {high_tps['price'].std():.2f}")
print(f"  Avg abs price change: {high_tps['abs_price_change'].mean():.4f} points")
print(f"  Max abs price change: {high_tps['abs_price_change'].max():.2f} points")

print(f"\nWhen TPS is LOW (<= {low_tps_threshold:.2f}, bottom 10%):")
print(f"  Count: {len(low_tps):,} ticks")
print(f"  Average price: {low_tps['price'].mean():.2f}")
print(f"  Price std dev: {low_tps['price'].std():.2f}")
print(f"  Avg abs price change: {low_tps['abs_price_change'].mean():.4f} points")
print(f"  Max abs price change: {low_tps['abs_price_change'].max():.2f} points")

# Calculate volatility ratio
volatility_ratio = high_tps['abs_price_change'].mean() / low_tps['abs_price_change'].mean()

print(f"\n{'='*60}")
print(f"VOLATILITY RATIO (High TPS / Low TPS): {volatility_ratio:.2f}x")
print(f"{'='*60}")

if volatility_ratio > 1.5:
    print(f"\n  >>> El precio es {volatility_ratio:.2f}x MAS VOLATIL cuando TPS es alto")
    print("      Alto TPS coincide con movimientos de precio mas grandes")
elif volatility_ratio > 1.0:
    print(f"\n  >>> El precio es ligeramente mas volatil cuando TPS es alto ({volatility_ratio:.2f}x)")
else:
    print("\n  >>> No hay diferencia significativa en volatilidad")

# Price direction analysis
print(f"\n{'='*60}")
print("PRICE DIRECTION ANALYSIS")
print(f"{'='*60}")

# Categorize price movements
df_changes['price_direction'] = 'flat'
df_changes.loc[df_changes['price_change'] > 0.25, 'price_direction'] = 'up'
df_changes.loc[df_changes['price_change'] < -0.25, 'price_direction'] = 'down'

print("\nAverage TPS by price direction:")
for direction in ['up', 'flat', 'down']:
    subset = df_changes[df_changes['price_direction'] == direction]
    if len(subset) > 0:
        avg_tps = subset['tps_window'].mean()
        count = len(subset)
        pct = count / len(df_changes) * 100
        print(f"  {direction.upper():5s}: TPS={avg_tps:6.2f} | Count={count:7,} ({pct:5.2f}%)")

# Large price movements
large_moves = df_changes[df_changes['abs_price_change'] > 0.5]
print(f"\nLarge price movements (>0.5 points):")
print(f"  Count: {len(large_moves):,} ({len(large_moves)/len(df_changes)*100:.2f}%)")
print(f"  Average TPS: {large_moves['tps_window'].mean():.2f}")
print(f"  Median TPS: {large_moves['tps_window'].median():.2f}")

small_moves = df_changes[df_changes['abs_price_change'] <= 0.25]
print(f"\nSmall price movements (<=0.25 points):")
print(f"  Count: {len(small_moves):,} ({len(small_moves)/len(df_changes)*100:.2f}%)")
print(f"  Average TPS: {small_moves['tps_window'].mean():.2f}")
print(f"  Median TPS: {small_moves['tps_window'].median():.2f}")

# Binned analysis - TPS ranges
print(f"\n{'='*60}")
print("BINNED ANALYSIS: Price behavior by TPS ranges")
print(f"{'='*60}")

# Create TPS bins
df_changes['tps_bin'] = pd.cut(df_changes['tps_window'],
                                bins=[0, 20, 50, 100, 200, 400],
                                labels=['0-20', '20-50', '50-100', '100-200', '200+'])

print("\nPrice volatility by TPS bin:")
for bin_name in ['0-20', '20-50', '50-100', '100-200', '200+']:
    subset = df_changes[df_changes['tps_bin'] == bin_name]
    if len(subset) > 0:
        avg_vol = subset['abs_price_change'].mean()
        count = len(subset)
        pct = count / len(df_changes) * 100
        print(f"  TPS {bin_name:8s}: Volatility={avg_vol:.4f} | Count={count:7,} ({pct:5.2f}%)")

print("\n" + "="*60)
print("CONCLUSION")
print("="*60)

if abs(pearson_corr_level) < 0.1:
    print("""
  NO HAY CORRELACION entre TPS y el NIVEL ABSOLUTO del precio.

  Esto es ESPERADO y CORRECTO:
  - El precio es una variable de mercado (oferta/demanda)
  - El TPS es una metrica de actividad (velocidad de actualizacion)
  - No tiene sentido que un precio de 25,300 vs 25,400 afecte al TPS
    """)
else:
    print(f"""
  Existe correlacion {strength} ({pearson_corr_level:.4f}) entre TPS y precio.
  Esto es INUSUAL y puede indicar:
  - Tendencia temporal (precio subio durante el dia, TPS tambien)
  - O coincidencia estadistica
    """)

if pearson_corr_change > 0.2:
    print(f"""
  SI HAY CORRELACION entre TPS y VOLATILIDAD de precio ({pearson_corr_change:.4f}).

  Conclusion:
  - Mayor TPS = Mayor actividad = Mayor movimiento de precio
  - Cuando el mercado esta activo (alto TPS), el precio se mueve mas
  - TPS es un indicador util de volatilidad intrabar
  - Volatilidad es {volatility_ratio:.2f}x mayor en periodos de alto TPS
    """)
else:
    print(f"""
  Correlacion DEBIL entre TPS y volatilidad ({pearson_corr_change:.4f}).

  Conclusion:
  - TPS y movimiento de precio son relativamente independientes
  - Alto TPS NO garantiza grandes movimientos de precio
  - El precio puede moverse mucho con bajo TPS (ordenes grandes)
  - O moverse poco con alto TPS (muchas ordenes pequeñas)
    """)

print("="*60)
print("\nINTERPRETACION PARA TRADING:")
print("="*60)

if volatility_ratio > 1.5:
    print("""
  1. Usar TPS como FILTRO de actividad:
     - Evitar operar cuando TPS < 20 (mercado lento)
     - Aumentar atencion cuando TPS > 100 (mercado activo)

  2. Ajustar stops y targets:
     - Stops mas amplios cuando TPS alto (mayor volatilidad)
     - Targets mas ambiciosos cuando TPS alto (precio se mueve mas)

  3. Timing de entradas:
     - Esperar picos de TPS para entrar (confirmacion de movimiento)
     - O evitar picos de TPS (demasiado ruido)
    """)
else:
    print("""
  1. TPS y precio son relativamente independientes
  2. TPS es util para medir ACTIVIDAD, no DIRECCION
  3. Combinar TPS con otros indicadores para decisiones de trading
    """)

print("="*60)
