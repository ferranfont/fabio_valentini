"""
CONFIGURACIÓN CENTRAL DE ESTRATEGIAS
Selecciona qué estrategia ejecutar cambiando STRATEGY_MODE
"""

# ============================================================================
# SELECTOR DE ESTRATEGIA
# ============================================================================
# Opciones: 1, 2, 3, 4
# 1 = Trend + EMA
# 2 = Clustering + Confirmation
# 3 = Mean Reversion (Rangos)
# 4 = Hybrid (RECOMENDADA)

STRATEGY_MODE = 2  # ← CAMBIAR AQUÍ PARA ELEGIR ESTRATEGIA

# ============================================================================
# NOMBRES Y DESCRIPCIONES POR ESTRATEGIA
# ============================================================================

STRATEGY_CONFIG = {
    1: {
        "name": "TENDENCIA + EMA",
        "description": "Filtro de tendencia con EMAs - Simple y robusto",
        "short_name": "trend_ema",
        "tp_points": 25,
        "sl_points": 15,
        "break_even": 12,
        "max_positions": 3,
        "expected_win_rate": "55-65%",
        "expected_sharpe": "2.0-2.5",
        "trades_per_day": "4-8"
    },
    2: {
        "name": "CLUSTERING + CONFIRMACIÓN",
        "description": "Requiere 2 señales del mismo tipo en 30min - Alta precisión",
        "short_name": "clustering",
        "tp_points": 30,
        "sl_points": 12,
        "break_even": 15,
        "max_positions": 2,
        "expected_win_rate": "65-75%",
        "expected_sharpe": "1.8-2.2",
        "trades_per_day": "2-4"
    },
    3: {
        "name": "MEAN REVERSION (RANGOS)",
        "description": "Opera reversiones en mercados laterales - Win rate alto",
        "short_name": "mean_reversion",
        "tp_points": 20,  # Target dinámico a centro del rango
        "sl_points": 10,
        "break_even": 8,
        "max_positions": 3,
        "expected_win_rate": "70-80%",
        "expected_sharpe": "1.5-2.0",
        "trades_per_day": "6-12"
    },
    4: {
        "name": "HÍBRIDA",
        "description": "Combina Tendencia + Clustering + Rangos - Balance óptimo",
        "short_name": "hybrid",
        "tp_points": 25,  # Dinámico en ranging
        "sl_points": 15,
        "break_even": 12,
        "max_positions": 3,
        "expected_win_rate": "58-68%",
        "expected_sharpe": "2.0-2.8",
        "trades_per_day": "5-10"
    }
}

# ============================================================================
# FUNCIONES HELPER
# ============================================================================

def get_strategy_config(mode=None):
    """
    Retorna la configuración de la estrategia seleccionada

    Args:
        mode: int (1-4) o None para usar STRATEGY_MODE global

    Returns:
        dict con configuración de la estrategia
    """
    if mode is None:
        mode = STRATEGY_MODE

    if mode not in STRATEGY_CONFIG:
        raise ValueError(f"STRATEGY_MODE debe ser 1, 2, 3 o 4. Valor actual: {mode}")

    return STRATEGY_CONFIG[mode]


def get_strategy_name(mode=None):
    """Retorna el nombre completo de la estrategia"""
    config = get_strategy_config(mode)
    return config["name"]


def get_strategy_title(mode=None):
    """Retorna título para headers y archivos"""
    config = get_strategy_config(mode)
    return f"ESTRATEGIA {mode}: {config['name']}"


def get_output_suffix(mode=None):
    """Retorna sufijo para archivos de salida"""
    config = get_strategy_config(mode)
    return config["short_name"]


def print_strategy_info(mode=None):
    """Imprime información de la estrategia seleccionada"""
    if mode is None:
        mode = STRATEGY_MODE

    config = get_strategy_config(mode)

    print(f"\n{'='*80}")
    print(f"ESTRATEGIA #{mode}: {config['name']}")
    print(f"{'='*80}")
    print(f"Descripción: {config['description']}")
    print(f"\nParámetros:")
    print(f"  - TP: {config['tp_points']} puntos")
    print(f"  - SL: {config['sl_points']} puntos")
    print(f"  - Break-even: {config['break_even']} puntos")
    print(f"  - Max posiciones: {config['max_positions']}")
    print(f"\nMétricas esperadas:")
    print(f"  - Win Rate: {config['expected_win_rate']}")
    print(f"  - Sharpe: {config['expected_sharpe']}")
    print(f"  - Trades/día: {config['trades_per_day']}")
    print(f"{'='*80}\n")


# ============================================================================
# VALIDACIÓN AL IMPORTAR
# ============================================================================

if __name__ == "__main__":
    # Si se ejecuta directamente, muestra info de todas las estrategias
    print("\n" + "="*80)
    print("ESTRATEGIAS DISPONIBLES")
    print("="*80)

    for mode in [1, 2, 3, 4]:
        config = get_strategy_config(mode)
        print(f"\n{mode}. {config['name']}")
        print(f"   {config['description']}")
        print(f"   Win Rate: {config['expected_win_rate']} | Sharpe: {config['expected_sharpe']} | Trades/día: {config['trades_per_day']}")

    print("\n" + "="*80)
    print(f"\nESTRATEGIA ACTUAL: {STRATEGY_MODE}")
    print_strategy_info(STRATEGY_MODE)
else:
    # Validar al importar
    if STRATEGY_MODE not in [1, 2, 3, 4]:
        raise ValueError(f"STRATEGY_MODE debe ser 1, 2, 3 o 4. Valor actual: {STRATEGY_MODE}")
