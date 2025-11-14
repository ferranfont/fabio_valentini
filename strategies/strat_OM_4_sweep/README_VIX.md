# Estrategia OM_4 - Versión con ATR y Trailing Stop

## Descripción

Esta es una versión avanzada de la estrategia de absorción (d-shape/p-shape) que utiliza **gestión de riesgo basada en volatilidad (ATR)** y **trailing stop dinámico**.

---

## Diferencias vs Versión Estándar

| Característica | Versión Estándar | Versión ATR/VIX |
|----------------|------------------|-----------------|
| **Stop Loss** | Fijo (ej: 1.5 pts) | Dinámico: `1.5 × ATR` |
| **Take Profit** | Fijo (ej: 3 pts) | Dinámico: `2.5 × ATR` |
| **Trailing Stop** | ❌ No | ✅ Sí (`0.75 × ATR`) |
| **Adaptación** | Mismo SL/TP siempre | Se ajusta a volatilidad |
| **Archivos** | `main_start.py` | `main_start_vix.py` |

---

## Archivos

### Motor de Backtest
- **strat_absortion_shape_vix.py**: Motor de backtest con ATR y trailing stop
- **main_start_vix.py**: Orchestrador principal (ejecutar este)

### Outputs
- **CSV**: `outputs/absortion_shape/dbshapes_TR_vix_{fecha}.csv`
- **Charts**: Sufijo `_vix` en todos los HTMLs

---

## Uso Rápido

```bash
cd strategies/strat_OM_4_absortion
python main_start_vix.py
```

Esto ejecuta:
1. ✅ Backtest con ATR + Trailing Stop
2. ✅ Visualización interactiva de trades
3. ✅ Estadísticas completas
4. ✅ Gráficos de equity y drawdown

---

## Configuración

### Archivo: `main_start_vix.py` (líneas 66-77)

```python
# Parámetros ATR
ATR_PERIOD = 14                 # Periodo para calcular ATR (en minutos)
ATR_MULTIPLIER_SL = 1.5         # Stop Loss = 1.5 × ATR
ATR_MULTIPLIER_TP = 2.5         # Take Profit = 2.5 × ATR
TRAILING_STOP_ATR_MULT = 0.75   # Trailing Stop distance = 0.75 × ATR
USE_TRAILING_STOP = True        # Activar/desactivar trailing stop
```

### ¿Qué hace el ATR?

**ATR (Average True Range)** mide la volatilidad del mercado:
- **Alta volatilidad** → ATR alto → SL/TP más amplios (evita stops prematuros)
- **Baja volatilidad** → ATR bajo → SL/TP más ajustados (captura movimientos pequeños)

### ¿Qué hace el Trailing Stop?

El **trailing stop** protege ganancias moviendo el SL a favor:

**LONG Trade**:
- Precio sube → SL sube (a distancia de `0.75 × ATR`)
- Precio baja → SL NO baja (lock profit)

**SHORT Trade**:
- Precio baja → SL baja (a distancia de `0.75 × ATR`)
- Precio sube → SL NO sube (lock profit)

---

## Ejemplo de Cálculo

### Scenario: Señal LONG

**Datos**:
- Precio entrada: **24,750**
- ATR actual: **10 puntos**

**SL/TP Estándar (fijo)**:
- SL: 24,750 - 1.5 = **24,748.5** ❌ Muy ajustado si hay volatilidad
- TP: 24,750 + 3.0 = **24,753.0**

**SL/TP con ATR (dinámico)**:
- SL: 24,750 - (1.5 × 10) = **24,735** ✅ Más holgado
- TP: 24,750 + (2.5 × 10) = **24,775** ✅ Target más ambicioso
- Trailing: **7.5 pts** debajo del máximo alcanzado

### Evolución del Trailing Stop

| Precio Actual | Máximo Alcanzado | SL (Trailing) | Estado |
|---------------|------------------|---------------|--------|
| 24,750 | 24,750 | 24,735 | Entrada |
| 24,765 | 24,765 | 24,757.5 | SL subió +22.5 pts |
| 24,772 | 24,772 | 24,764.5 | SL subió +29.5 pts |
| 24,768 | 24,772 | 24,764.5 | SL NO baja |
| 24,764 | 24,772 | 24,764.5 | **STOP activado** |

**Resultado**: Salida en 24,764.5 con +14.5 pts (vs -1.5 pts con SL fijo)

---

## Outputs Adicionales

### Columnas Nuevas en CSV

```csv
entry_time;entry_price;exit_price;side;exit_reason;trailing_stop_distance;highest_price_reached;...
```

**Nuevas columnas**:
- `trailing_stop_distance`: Distancia del trailing stop en puntos
- `highest_price_reached` (LONG): Precio máximo alcanzado antes de cerrar
- `lowest_price_reached` (SHORT): Precio mínimo alcanzado antes de cerrar

### Exit Reasons

- **`TARGET`**: Take profit alcanzado
- **`TRAILING_STOP`**: Trailing stop activado (si habilitado)
- **`STOP`**: Stop loss inicial (si trailing stop deshabilitado)
- **`END_OF_DATA`**: Fin de datos (posición abierta al terminar)

---

## Comparación de Resultados

### Ejemplo Real: 19 de Septiembre 2025

| Métrica | Versión Estándar | Versión ATR/VIX | Mejora |
|---------|------------------|-----------------|--------|
| **Total Trades** | 31 | ? | - |
| **Win Rate** | 35.5% | ? | - |
| **Total P&L** | -$260 | ? | - |
| **Max DD** | -$510 | ? | - |
| **Avg Win** | $40 | ? | - |
| **Avg Loss** | -$35 | ? | - |

*(Ejecutar para ver resultados comparativos)*

---

## Ventajas de ATR + Trailing Stop

### ✅ Pros

1. **Adaptación a mercado**: SL/TP se ajustan a volatilidad real
2. **Protección de ganancias**: Trailing stop lock profits automáticamente
3. **Menor ruido**: Stops más amplios en alta volatilidad evitan salidas prematuras
4. **Mayor reward**: Targets más ambiciosos cuando el mercado lo permite

### ⚠️ Cons

1. **Complejidad**: Más parámetros para optimizar
2. **Cálculo ATR**: Requiere más procesamiento (resampling a 1min)
3. **Stops amplios**: En alta volatilidad, puede dar más drawdown inicial

---

## Optimización de Parámetros

### ATR_MULTIPLIER_SL (Stop Loss)
- **Bajo (1.0-1.5)**: Stops ajustados, más salidas
- **Alto (2.0-3.0)**: Stops amplios, más aguante

### ATR_MULTIPLIER_TP (Take Profit)
- **Bajo (1.5-2.0)**: Targets cercanos, más wins
- **Alto (3.0-4.0)**: Targets lejanos, menos wins pero mayores

### TRAILING_STOP_ATR_MULT (Trailing Distance)
- **Bajo (0.5)**: Trailing muy ajustado, más lock profit
- **Alto (1.0)**: Trailing amplio, más aguante

### Recomendaciones Iniciales

**Mercado Volátil** (ATR alto):
```python
ATR_MULTIPLIER_SL = 2.0
ATR_MULTIPLIER_TP = 3.5
TRAILING_STOP_ATR_MULT = 1.0
```

**Mercado Tranquilo** (ATR bajo):
```python
ATR_MULTIPLIER_SL = 1.25
ATR_MULTIPLIER_TP = 2.0
TRAILING_STOP_ATR_MULT = 0.6
```

---

## Troubleshooting

### Error: "No module named 'strat_absortion_shape_vix'"

**Causa**: Script ejecutado desde directorio incorrecto

**Solución**:
```bash
cd strategies/strat_OM_4_absortion
python main_start_vix.py
```

### Warning: "ATR calculation slow"

**Causa**: Dataset muy grande (>500K ticks)

**Solución**: Normal, el resampling a 1min toma tiempo. Esperar.

### Todos los trades con exit_reason="STOP"

**Causa**: ATR_MULTIPLIER_TP muy alto, targets inalcanzables

**Solución**: Reducir `ATR_MULTIPLIER_TP` a 2.0-2.5

---

## Próximas Mejoras

- [ ] ATR adaptativo (recalcular cada X minutos)
- [ ] Trailing stop parcial (mover solo % del SL)
- [ ] Break-even basado en ATR
- [ ] Volatility regime detection (cambiar parámetros automáticamente)

---

**Última actualización**: 2025-11-04
**Versión**: 1.0 (ATR + Trailing Stop)
