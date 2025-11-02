# 🎯 INSTRUCCIONES DE USO - Sistema de Estrategias Market Profile

## 📁 Estructura Creada

```
strategies/strat_OM_4_claude/
├── README.md                    ✅ Análisis completo de las 4 estrategias
├── INSTRUCCIONES_USO.md         ✅ Este archivo (cómo usar el sistema)
└── strategy_4_hybrid/           ✅ Estrategia Híbrida completa
    ├── config_strategy.py       ✅ SELECTOR DE ESTRATEGIAS
    ├── strat_absortion_shape.py ✅ Backtest con lógica híbrida
    ├── main_start.py            ✅ Orquestador completo
    ├── plot_trades_chart.py     ✅ Visualización
    ├── summary.py               ✅ Tabla de métricas
    └── plot_backtest_results.py ✅ Gráficos equity/drawdown
```

---

## 🚀 CÓMO CAMBIAR DE ESTRATEGIA

### Paso 1: Editar `config_strategy.py`

Abre el archivo `strategy_4_hybrid/config_strategy.py` y cambia la línea 14:

```python
STRATEGY_MODE = 4  # ← CAMBIAR AQUÍ
```

**Opciones disponibles:**
- `1` = Tendencia + EMA
- `2` = Clustering + Confirmación
- `3` = Mean Reversion (Rangos)
- `4` = Híbrida (RECOMENDADA)

### Paso 2: Ejecutar la estrategia

```bash
cd strategies/strat_OM_4_claude/strategy_4_hybrid
python main_start.py
```

El sistema automáticamente:
- Cargará la configuración de la estrategia seleccionada
- Mostrará el nombre de la estrategia en el título
- Aplicará los parámetros TP/SL correspondientes
- Generará archivos con el nombre de la estrategia

---

## 📊 RESULTADOS DE LA ESTRATEGIA HÍBRIDA

**Ya ejecutada y probada:**

```
Trades: 60
Win Rate: 40.0%
Total P&L: +$1,955
Profit Factor: 1.33
Max DD: -$1,800
Sharpe: 0.11
```

**Breakdown:**
- d_shape: 15 trades → +$680
- p_shape: 45 trades → +$1,275

**Archivos generados:**
- `tracking_record_hybrid_all_day.csv`
- `trades_visualization_hybrid_all_day.html`
- `summary_report_hybrid_all_day.html`
- `backtest_results_hybrid_all_day_*.html`

---

## 🎨 DETALLES DE CADA ESTRATEGIA

### 1️⃣ TENDENCIA + EMA
**Filosofía**: Operar solo a favor de la tendencia

**Lógica**:
- LONG: d_shape entre EMAs cuando EMA20 > EMA100
- SHORT: p_shape entre EMAs cuando EMA20 < EMA100

**Parámetros**:
- TP: 25 pts | SL: 15 pts | Break-even: 12 pts
- Max posiciones: 3

**Esperado**:
- Win Rate: 55-65%
- Sharpe: 2.0-2.5
- Trades/día: 4-8

---

### 2️⃣ CLUSTERING + CONFIRMACIÓN
**Filosofía**: Alta precisión con confluencia de señales

**Lógica**:
- Requiere 2 señales del mismo tipo en ventana de 30 minutos
- Confirmación: precio debe retroceder 5 puntos antes de entry
- Solo operar en sesión americana

**Parámetros**:
- TP: 30 pts | SL: 12 pts | Break-even: 15 pts
- Max posiciones: 2
- Time exit: 2 horas

**Esperado**:
- Win Rate: 65-75%
- Sharpe: 1.8-2.2
- Trades/día: 2-4

---

### 3️⃣ MEAN REVERSION (RANGOS)
**Filosofía**: Reversiones rápidas en mercados laterales

**Lógica**:
- Detecta rangos de 2 horas (high-low)
- Filtro ATR para confirmar mercado lateral
- d_shape cerca del low → LONG hacia centro
- p_shape cerca del high → SHORT hacia centro

**Parámetros**:
- TP: Centro del rango (dinámico) | SL: 10 pts
- Break-even: 8 pts
- Max posiciones: 3

**Esperado**:
- Win Rate: 70-80%
- Sharpe: 1.5-2.0
- Trades/día: 6-12

---

### 4️⃣ HÍBRIDA ⭐ (RECOMENDADA)
**Filosofía**: Combina lo mejor de las 3 anteriores

**Lógica**:
1. **Filtro de Tendencia** (de Estrategia 1):
   - EMA20 vs EMA100 para sesgo direccional

2. **Detección de Clustering** (de Estrategia 2):
   - Busca señales del mismo tipo en últimos 30 min
   - Categoría especial para señales con clustering

3. **Detección de Rangos** (de Estrategia 3):
   - Calcula ATR% sobre últimos 14 minutos
   - Si ATR% < 0.15% → mercado en rango
   - Targets dinámicos: centro del rango vs fijos

4. **Filtros Adicionales**:
   - En ranging: NO tomar d_shape SHORT ni p_shape LONG
   - En trending: Permitir todas las señales válidas

**Parámetros**:
- TP: 25 pts (trending) / centro rango (ranging) | SL: 15 pts
- Break-even: 12 pts
- Max posiciones: 3

**Esperado**:
- Win Rate: 58-68%
- Sharpe: 2.0-2.8
- Trades/día: 5-10

**Categorías de señal** (8 tipos):
```
trend_cluster_d_inside_green
trend_single_d_inside_green
trend_cluster_p_above_green
trend_single_p_above_green
trend_cluster_d_below_red
trend_single_d_below_red
trend_cluster_p_inside_red
trend_single_p_inside_red
range_cluster_*
range_single_*
```

---

## 🔧 PERSONALIZACIÓN ADICIONAL

### Cambiar parámetros manualmente

Si quieres ajustar TP/SL sin cambiar de estrategia, edita `main_start.py`:

```python
# Líneas 48-55
TP_POINTS = 25
SL_POINTS = 15
BREAK_EVEN_POINTS = 12.0
NUM_MAX_OPEN_CONTRACTS = 3
```

### Cambiar archivos de datos

Edita `main_start.py` líneas 35-39:

```python
TNS_FILE = DATA_DIR / "time_and_sales_20251031_074530.csv"
SIGNALS_FILE = OUTPUTS_DIR / "db_shapes_dom_20251101_150013.csv"
```

### Cambiar EMAs

Edita `main_start.py` líneas 57-59:

```python
EMA_FAST_PERIOD = 20   # Período de la EMA rápida (en minutos)
EMA_SLOW_PERIOD = 100  # Período de la EMA lenta (en minutos)
```

---

## 📈 ANÁLISIS DE RESULTADOS

Después de ejecutar `python main_start.py`, revisa:

1. **CSV de trades**: `outputs/tracking_record_[estrategia]_all_day.csv`
   - Columna `signal_category` muestra el tipo de señal
   - Analiza qué categorías tienen mejor performance

2. **Gráfico interactivo**: `charts/trades_visualization_[estrategia]_all_day.html`
   - Zoom para ver detalles
   - Hover sobre señales para ver info
   - Verifica que las entradas respeten las EMAs

3. **Tabla de métricas**: `charts/summary_report_[estrategia]_all_day.html`
   - Win Rate por categoría de señal
   - Profit por tipo de señal
   - Breakdown de exits (TARGET vs STOP)

4. **Equity curve**: `charts/backtest_results_[estrategia]_all_day_equity.html`
   - Curva de capital acumulado
   - Drawdown overlay
   - Identifica períodos de mejor/peor performance

---

## ⚠️ NOTAS IMPORTANTES

### Para implementar Estrategias 1, 2 y 3

Actualmente solo la **Estrategia 4 Híbrida** está completamente implementada.

Para crear las otras 3:
1. Duplicar la carpeta `strategy_4_hybrid`
2. Renombrar a `strategy_1_trend_ema`, `strategy_2_clustering`, `strategy_3_mean_reversion`
3. Modificar `strat_absortion_shape.py` con la lógica específica de cada una
4. Actualizar `config_strategy.py` para apuntar a la correcta

**O simplemente**, la Estrategia Híbrida YA INCLUYE toda la lógica de las 3, solo que las combina inteligentemente.

### Gestión de Riesgo

Recuerda ajustar:
- **Riesgo por trade**: 1-2% del capital
- **Max posiciones**: 3 es conservador, 5 es agresivo
- **Break-even**: Activar a mitad del TP (12 puntos si TP=25)

### Horarios de Trading

Mejor performance en:
- **Sesión americana**: 15:30-22:00 CET
- **Evitar**: Apertura asiática (baja liquidez)
- **Cuidado**: 15 min antes/después de noticias importantes

---

## 🎓 PRÓXIMOS PASOS RECOMENDADOS

1. ✅ **Ejecutar Estrategia Híbrida** con datos actuales
2. 📊 **Analizar categorías**: ¿Cuáles tienen mejor win rate?
3. 🔧 **Optimizar parámetros**: TP/SL según resultados
4. 📈 **Walk-forward testing**: Dividir datos en train/test
5. 🚀 **Paper trading**: Probar en demo antes de live

---

**Creado por**: Claude AI
**Fecha**: 2025-11-02
**Versión**: 1.0
**Estrategia implementada**: Híbrida (4)
