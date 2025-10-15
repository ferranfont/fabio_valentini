"""
Test de sensibilidad: Detección de señales FAKE con diferentes ventanas look-ahead.

Compara 3 configuraciones:
- 30 segundos (restrictivo)
- 45 segundos (balance)
- 60 segundos (conservador)
"""

import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Importar funciones del script principal
sys.path.append(str(Path(__file__).parent))
from find_absortion_vol_efford import (
    load_and_prepare_data,
    compute_volume_stats_simple,
    detect_anomalies,
    detect_fake_signals,
    DATA_FILE,
    WINDOW_MINUTES,
    ANOMALY_THRESHOLD
)


def test_fake_detection(look_ahead_values=[30, 45, 60]):
    """
    Ejecuta test con diferentes valores de look-ahead.

    Args:
        look_ahead_values: Lista de segundos para ventana look-ahead
    """
    print("="*80)
    print("TEST DE SENSIBILIDAD - DETECCIÓN DE SEÑALES FAKE")
    print("="*80)
    print(f"\nValores a probar: {look_ahead_values} segundos")
    print(f"Dataset: {DATA_FILE}")
    print(f"Parámetros fijos:")
    print(f"  - Ventana volumen: {WINDOW_MINUTES} min")
    print(f"  - Threshold Z-score: {ANOMALY_THRESHOLD} std")
    print("="*80)

    # Cargar datos una sola vez
    print("\n[1/4] Cargando y preparando datos...")
    df = load_and_prepare_data(DATA_FILE)

    print("\n[2/4] Calculando estadísticas de volumen...")
    df = compute_volume_stats_simple(df, window_minutes=WINDOW_MINUTES)

    print("\n[3/4] Detectando anomalías...")
    df = detect_anomalies(df, threshold=ANOMALY_THRESHOLD)

    total_bid = df['bid_vol'].sum()
    total_ask = df['ask_vol'].sum()
    total_signals = total_bid + total_ask

    print(f"\nTotal señales detectadas:")
    print(f"  BID: {total_bid:,}")
    print(f"  ASK: {total_ask:,}")
    print(f"  TOTAL: {total_signals:,}")

    # Almacenar resultados
    results = []

    print("\n[4/4] Probando diferentes ventanas look-ahead...")
    print("="*80)

    for look_ahead_sec in look_ahead_values:
        print(f"\n{'='*80}")
        print(f"TEST: look_ahead = {look_ahead_sec}s")
        print(f"{'='*80}")

        # Detectar señales fake con este parámetro
        df_test = detect_fake_signals(df.copy(), look_ahead_sec=look_ahead_sec)

        # Calcular estadísticas
        fake_bid = df_test['fake_bid_vol'].sum()
        fake_ask = df_test['fake_ask_vol'].sum()
        total_fake = fake_bid + fake_ask

        real_bid = total_bid - fake_bid
        real_ask = total_ask - fake_ask
        total_real = total_signals - total_fake

        pct_fake_bid = (fake_bid / total_bid * 100) if total_bid > 0 else 0
        pct_fake_ask = (fake_ask / total_ask * 100) if total_ask > 0 else 0
        pct_fake_total = (total_fake / total_signals * 100) if total_signals > 0 else 0

        # Guardar resultados
        results.append({
            'look_ahead_sec': look_ahead_sec,
            'total_signals': total_signals,
            'fake_total': total_fake,
            'real_total': total_real,
            'pct_fake': pct_fake_total,
            'fake_bid': fake_bid,
            'real_bid': real_bid,
            'pct_fake_bid': pct_fake_bid,
            'fake_ask': fake_ask,
            'real_ask': real_ask,
            'pct_fake_ask': pct_fake_ask
        })

        print(f"\nRESULTADOS:")
        print(f"  BID: {fake_bid:,} fake ({pct_fake_bid:.1f}%) | {real_bid:,} real ({100-pct_fake_bid:.1f}%)")
        print(f"  ASK: {fake_ask:,} fake ({pct_fake_ask:.1f}%) | {real_ask:,} real ({100-pct_fake_ask:.1f}%)")
        print(f"  TOTAL: {total_fake:,} fake ({pct_fake_total:.1f}%) | {total_real:,} real ({100-pct_fake_total:.1f}%)")

    # Tabla comparativa final
    print("\n" + "="*80)
    print("TABLA COMPARATIVA")
    print("="*80)

    df_results = pd.DataFrame(results)

    print("\nSeñales FAKE por ventana look-ahead:")
    print("-" * 80)
    print(f"{'Look-ahead':<15} {'Total Fake':<12} {'% Fake':<10} {'BID Fake':<12} {'ASK Fake':<12}")
    print("-" * 80)

    for _, row in df_results.iterrows():
        print(f"{row['look_ahead_sec']:>3}s{'':<11} "
              f"{row['fake_total']:>6,}{'':<5} "
              f"{row['pct_fake']:>6.1f}%{'':<3} "
              f"{row['fake_bid']:>6,}{'':<5} "
              f"{row['fake_ask']:>6,}")

    print("-" * 80)

    print("\nSeñales REALES por ventana look-ahead:")
    print("-" * 80)
    print(f"{'Look-ahead':<15} {'Total Real':<12} {'% Real':<10} {'BID Real':<12} {'ASK Real':<12}")
    print("-" * 80)

    for _, row in df_results.iterrows():
        pct_real = 100 - row['pct_fake']
        print(f"{row['look_ahead_sec']:>3}s{'':<11} "
              f"{row['real_total']:>6,}{'':<5} "
              f"{pct_real:>6.1f}%{'':<3} "
              f"{row['real_bid']:>6,}{'':<5} "
              f"{row['real_ask']:>6,}")

    print("-" * 80)

    # Análisis de impacto
    print("\n" + "="*80)
    print("ANÁLISIS DE IMPACTO")
    print("="*80)

    if len(df_results) >= 2:
        diff_30_60 = df_results.iloc[-1]['fake_total'] - df_results.iloc[0]['fake_total']
        pct_change = (diff_30_60 / df_results.iloc[0]['fake_total'] * 100) if df_results.iloc[0]['fake_total'] > 0 else 0

        print(f"\nDiferencia entre 30s y {df_results.iloc[-1]['look_ahead_sec']}s:")
        print(f"  Señales fake adicionales: {diff_30_60:+,} ({pct_change:+.1f}%)")
        print(f"  Señales reales menos: {-diff_30_60:,}")

        print(f"\nInterpretación:")
        if pct_change > 50:
            print(f"  [!] GRAN DIFERENCIA: La ventana look-ahead tiene un impacto MUY significativo")
            print(f"      Recomendación: Usar ventana corta (30-45s) si TP se alcanza rápido")
        elif pct_change > 20:
            print(f"  [*] DIFERENCIA NOTABLE: La ventana afecta considerablemente los resultados")
            print(f"      Recomendación: Probar ambas en backtest y ver cuál da mejores resultados")
        else:
            print(f"  [OK] DIFERENCIA MENOR: La ventana tiene poco impacto")
            print(f"       Recomendación: Cualquier valor entre 30-60s es razonable")

    print("\n" + "="*80)
    print("TEST COMPLETADO")
    print("="*80)

    return df_results


if __name__ == "__main__":
    # Ejecutar test con 30s, 45s, 60s
    results = test_fake_detection(look_ahead_values=[30, 45, 60])

    # Guardar resultados
    output_file = "statistic_quant/fake_detection_test_results.csv"
    results.to_csv(output_file, index=False, sep=';', decimal=',')
    print(f"\nResultados guardados en: {output_file}")
