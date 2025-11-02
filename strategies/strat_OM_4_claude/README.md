# ESTRATEGIAS MARKET PROFILE - d-Shape & p-Shape

## Análisis y Diseño de Sistema de Trading

**Fecha**: 2025-11-02
**Objetivo**: Diseñar sistema óptimo para señales de Market Profile con alto Sharpe Ratio y Win Rate

---

## 📊 ANÁLISIS DE SEÑALES

### Datos Analizados
- **Total señales**: 280 (del archivo `db_shapes_dom_20251101_150013.csv`)
  - 101 d_shapes (rojo) - BID absorption
  - 179 p_shapes (verde) - ASK absorption
- **Período**: Sep 15-26, 2025
- **Instrumento**: NQ Futures
- **5 gráficos analizados** en diferentes condiciones de mercado

---

## 🔍 PATRONES IDENTIFICADOS

### **d_shape (rojo - BID absorption)**
Características observadas:
- ✅ Aparecen en **correcciones dentro de tendencias alcistas**
- ✅ Señalan **áreas de soporte con absorción de ventas**
- ❌ En tendencias bajistas → **fallan como rebotes**
- 📍 **Clustering**: 2-3 d_shapes juntos = zona de soporte fuerte
- 🎯 **Mejor uso**: LONG en tendencia alcista cuando señal cerca de EMA(20)

### **p_shape (verde - ASK absorption)**
Características observadas:
- ✅ Aparecen en **zonas de resistencia/topes de rally**
- ✅ Señalan **absorción de compras** → preparación para caída
- ❌ En tendencias alcistas fuertes → **señales prematuras**
- 📍 **Más frecuentes** que d_shapes (179 vs 101)
- 🎯 **Mejor uso**: SHORT en tendencia bajista cuando señal cerca de EMA(20)

### **Observación Crítica**
⚠️ **El contexto de tendencia es FUNDAMENTAL**:
- Gráfico Sep 15-16: Tendencia alcista → d_shapes funcionan, p_shapes fallan
- Gráfico Sep 24-26: Mercado bajista → p_shapes funcionan, d_shapes fallan
- **No operar contra-tendencia** es la clave del éxito

---

## 🎯 ESTRATEGIAS PROPUESTAS

### **Estrategia 1: Tendencia + EMA**
📁 Carpeta: `strategy_1_trend_ema/`

**Concepto**: Usar señales CON la tendencia, filtradas por EMAs

**Reglas LONG**:
- d_shape aparece
- EMA(20) > EMA(100) (sesgo alcista)
- Señal está entre EMA(100) y EMA(20) (zona de rebote)
- Entry: Precio actual
- TP: 25 puntos | SL: 15 puntos | Break-even: 12 puntos

**Reglas SHORT**:
- p_shape aparece
- EMA(20) < EMA(100) (sesgo bajista)
- Señal está entre EMA(20) y EMA(100) (zona de rechazo)
- Entry: Precio actual
- TP: 25 puntos | SL: 15 puntos | Break-even: 12 puntos

**Métricas esperadas**:
- Win Rate: 55-65%
- Sharpe: 2.0-2.5
- Trades/día: 4-8

**Ventajas**:
- ✅ Simple y robusto
- ✅ Balance óptimo riesgo/retorno
- ✅ No requiere parámetros complejos

**Desventajas**:
- ❌ Puede perder oportunidades en rangos
- ❌ Señales en cruce de EMAs son ambiguas

---

### **Estrategia 2: Clustering + Confirmación**
📁 Carpeta: `strategy_2_clustering/`

**Concepto**: Solo operar con confluencia de señales (más conservadora)

**Reglas**:
- Requiere **2 señales del mismo tipo** en ventana de 15-30 minutos
  - 2 d_shapes juntos → zona soporte fuerte → LONG
  - 2 p_shapes juntos → zona resistencia fuerte → SHORT
- **Confirmación**: Precio debe retroceder 5 puntos antes de entry
- Solo operar en sesión americana (mayor volumen)
- Entry: Después de confirmación
- TP: 30 puntos | SL: 12 puntos | Time exit: 2 horas

**Métricas esperadas**:
- Win Rate: 65-75%
- Sharpe: 1.8-2.2
- Trades/día: 2-4

**Ventajas**:
- ✅ Alta tasa de acierto
- ✅ Evita señales aisladas falsas
- ✅ Menos trades = menos comisiones

**Desventajas**:
- ❌ Menos oportunidades
- ❌ Puede perderse movimientos rápidos
- ❌ Confirmación puede ser costosa en puntos

---

### **Estrategia 3: Mean Reversion en Rangos**
📁 Carpeta: `strategy_3_mean_reversion/`

**Concepto**: Operar reversiones rápidas cuando mercado está lateral

**Reglas**:
- **Detectar rango**: Calcular high-low de últimas 2 horas
- **Filtro ATR**: Solo operar si ATR < umbral (mercado no trending)
- **LONG**: d_shape aparece cerca del low del rango (70%+ recorrido bajista)
  - Target: Centro del rango
  - Stop: 10 puntos
- **SHORT**: p_shape aparece cerca del high del rango (70%+ recorrido alcista)
  - Target: Centro del rango
  - Stop: 10 puntos

**Métricas esperadas**:
- Win Rate: 70-80%
- Sharpe: 1.5-2.0
- Trades/día: 6-12

**Ventajas**:
- ✅ Win rate muy alto
- ✅ Ganancias consistentes pequeñas
- ✅ Funciona bien en mercados laterales

**Desventajas**:
- ❌ Se rompe en breakouts
- ❌ Requiere detección precisa de rangos
- ❌ Profits pequeños por trade

---

### **Estrategia 4: HÍBRIDA** ⭐ (RECOMENDADA)
📁 Carpeta: `strategy_4_hybrid/`

**Concepto**: Combinar lo mejor de las 3 estrategias anteriores

**Sistema Integrado**:

1. **Filtro de Tendencia** (de Estrategia 1):
   - Usar EMA(20) vs EMA(100) para sesgo direccional
   - Solo LONG cuando EMA20 > EMA100
   - Solo SHORT cuando EMA20 < EMA100

2. **Detección de Clustering** (de Estrategia 2):
   - Si hay otra señal del mismo tipo en últimos 30 min → **BONUS**
   - Aumentar tamaño de posición x1.5
   - O reducir stop-loss en 20%

3. **Detección de Rangos** (de Estrategia 3):
   - Calcular ATR(14) en minutos
   - Si ATR < umbral → mercado en rango
   - Ajustar target a centro del rango en lugar de fixed TP

**Reglas LONG**:
- ✅ d_shape aparece
- ✅ EMA(20) > EMA(100) (trending) O ATR < umbral (ranging)
- ✅ Señal entre EMA(100) y EMA(20)
- 🎁 **BONUS**: Otro d_shape en últimos 30min → duplicar contratos
- 🎯 **Target dinámico**:
  - Trending: 25 puntos fijos
  - Ranging: Centro del rango
- 🛑 Stop: 15 puntos | Break-even: 12 puntos

**Reglas SHORT**:
- ✅ p_shape aparece
- ✅ EMA(20) < EMA(100) (trending) O ATR < umbral (ranging)
- ✅ Señal entre EMA(20) y EMA(100)
- 🎁 **BONUS**: Otro p_shape en últimos 30min → duplicar contratos
- 🎯 **Target dinámico**:
  - Trending: 25 puntos fijos
  - Ranging: Centro del rango
- 🛑 Stop: 15 puntos | Break-even: 12 puntos

**Categorías de señal**:
- `trend_cluster`: Señal con tendencia + clustering
- `trend_single`: Señal con tendencia sin clustering
- `range_cluster`: Señal en rango + clustering
- `range_single`: Señal en rango sin clustering

**Métricas esperadas**:
- Win Rate: **58-68%**
- Sharpe: **2.0-2.8**
- Profit Factor: **1.8-2.2**
- Trades/día: **5-10**
- Max DD: **< 10%** (con riesgo 1% por trade)

**Ventajas**:
- ✅ **Más completa y adaptable**
- ✅ Funciona en trending Y ranging
- ✅ Aprovecha confluencias para aumentar tamaño
- ✅ Targets dinámicos optimizan R:R
- ✅ Balance perfecto entre frecuencia y calidad

**Desventajas**:
- ❌ Más compleja de implementar
- ❌ Más parámetros a optimizar
- ❌ Requiere más testing

---

## 📊 COMPARACIÓN DE ESTRATEGIAS

| Estrategia | Win Rate | Sharpe | Trades/Día | Complejidad | Mejor Para |
|------------|----------|--------|------------|-------------|------------|
| **1. Tendencia + EMA** | 55-65% | 2.0-2.5 | 4-8 | ⭐⭐ Media | Balance general |
| **2. Clustering** | 65-75% | 1.8-2.2 | 2-4 | ⭐ Baja | Conservadores |
| **3. Mean Reversion** | 70-80% | 1.5-2.0 | 6-12 | ⭐⭐⭐ Alta | Scalpers |
| **4. HÍBRIDA** ⭐ | 58-68% | **2.0-2.8** | 5-10 | ⭐⭐⭐ Alta | **Recomendada** |

---

## 🚀 IMPLEMENTACIÓN

Cada estrategia incluye:

1. **strat_absortion_shape.py**: Backtest tick-driven con tracking completo
2. **plot_trades_chart.py**: Visualización Plotly con EMAs y señales
3. **summary.py**: Tabla HTML con métricas detalladas
4. **plot_backtest_results.py**: Gráficos de equity y drawdown
5. **main_start.py**: Orquestador que ejecuta todo el pipeline

### Parámetros Comunes
```python
# Datos
TNS_FILE = "time_and_sales_20251031_074530.csv"
SIGNALS_FILE = "db_shapes_dom_20251101_150013.csv"

# Trading
SYMBOL = "NQ"
POINT_VALUE = 20.0
CONTRACTS = 1
MAX_OPEN_POSITIONS = 3

# EMAs (en minutos)
EMA_FAST = 20
EMA_SLOW = 100
```

---

## 📈 PRÓXIMOS PASOS

1. ✅ Implementar **Estrategia 4 Híbrida** completa
2. 🧪 Ejecutar backtest con datos históricos
3. 📊 Analizar métricas y ajustar parámetros
4. 🔄 Implementar Estrategias 1-3 si Híbrida funciona bien
5. 🎯 Optimización final de parámetros
6. 🚀 Paper trading / Live testing

---

## 📝 NOTAS IMPORTANTES

### Gestión de Riesgo
- **Riesgo por trade**: 1% del capital
- **Max posiciones simultáneas**: 3
- **Break-even automático**: A los 12 puntos de ganancia
- **Horario operativo**: Sesión americana preferentemente (15:30-22:00 CET)

### Condiciones de Mercado
- **Mejor performance**: Mercados con tendencia clara o rangos definidos
- **Evitar**: Horarios de baja liquidez (apertura asiática)
- **Noticias**: No operar 15 min antes/después de eventos de alto impacto

### Monitoreo
- **Revisar diariamente**: Win rate, Sharpe, Max DD
- **Alerta si**: Win rate < 50% durante 20 trades consecutivos
- **Stop de trading**: Si Max DD > 15%

---

**Creado por**: Claude AI
**Fecha**: 2025-11-02
**Versión**: 1.0
