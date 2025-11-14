# Workflow Completo - Estrategia d-Shape & p-Shape

## Arquitectura de la Estrategia

La estrategia tiene **DOS VARIANTES** de backtest:

### 1. **FIXED** - TP/SL Fijos
- Script: `strat_absortion_shape.py`
- Stop Loss: 3.0 puntos (fijo)
- Take Profit: 4.0 puntos (fijo)
- Tracking: `outputs/absortion_shape/tracking_record/`

### 2. **VIX** - ATR + Trailing Stop
- Script: `strat_absortion_shape_vix.py`
- Stop Loss: Dinámico (ATR_MULTIPLIER_SL × ATR)
- Take Profit: Dinámico (ATR_MULTIPLIER_TP × ATR)
- Trailing Stop: Activado (TRAILING_STOP_ATR_MULT × ATR)
- Tracking: `outputs/absortion_shape/tracking_record_vix/`

---

## Workflow Paso a Paso

### **FASE 1: Preparación de Datos**

#### 1.1. Obtener datos de Time & Sales
Descarga archivos de Rithmic y colócalos en:
```
data/time_and_sales_YYYYMMDD_HHMMSS.csv
```

#### 1.2. Dividir por fecha (si es necesario)
Si tienes un archivo con múltiples días:

```bash
# Editar split_by_date.py línea 16 con el archivo correcto
python strat_absortion/split_by_date.py
```

**Salida**: `data/historic/time_and_sales_nq_YYYYMMDD.csv` (un archivo por día)

---

### **FASE 2: Detección de Patrones**

#### 2.1. Generar señales (db_shapes) para todos los días

```bash
python strat_absortion/iterate_on_main_to_sb_shapes.py
```

**Proceso**:
- Busca todos los archivos `time_and_sales_nq_*.csv` en `data/historic/`
- Ejecuta `strat_absortion/main.py` para cada día
- Genera:
  - CSV: `outputs/absortion_shape/db_shapes_dom_YYYYMMDD.csv`
  - HTML: `charts/detections/absorption_report_YYYYMMDD.html`
- Skip automático de archivos ya procesados
- Timeout: 45 minutos por archivo (configurable)

**Parámetros clave** (en `main.py`):
```python
PROFILE_WINDOW = 20                  # Rolling window de 20 segundos
EXTREME_VOLUME_MULTIPLIER = 2        # Volumen extremo = 2x segundo mayor
MIN_PRICE_LEVELS = 20                # Mínimo 20 niveles de precio
MIN_BID_ASK_SIZE = 30                # Tamaño mínimo de barra BID/ASK
PRICE_POSITION_THRESHOLD = 0.3       # Precio en 30% inferior/superior
```

**Salida**:
- Solo genera CSV si detecta patrones (d-shape o p-shape)
- Siempre genera HTML (incluso sin detecciones para análisis visual)

---

### **FASE 3: Backtest Multi-Día + Reporte Automático**

#### 3.1. Ejecutar backtest para todos los días con señales

```bash
cd strategies/strat_OM_4_absortion
python iterate_backtest_all_days.py
```

**Interactivo - Te pregunta**:
```
SELECT BACKTEST STRATEGY:
  1. FIXED   - Fixed TP/SL (strat_absortion_shape.py)
  2. VIX     - ATR + Trailing Stop (strat_absortion_shape_vix.py)

Enter choice (1 or 2): _
```

**Proceso COMPLETO**:
1. Busca todos los `db_shapes_dom_YYYYMMDD.csv` en `outputs/absortion_shape/`
2. Busca archivos T&S correspondientes en `data/historic/`
3. Ejecuta backtest elegido (FIXED o VIX) para cada día
4. Guarda tracking_records en carpetas separadas:
   - **FIXED**: `outputs/absortion_shape/tracking_record/dbshapes_TR_YYYYMMDD.csv`
   - **VIX**: `outputs/absortion_shape/tracking_record_vix/dbshapes_TR_vix_YYYYMMDD.csv`
5. Skip automático de archivos ya procesados
6. **AUTOMÁTICAMENTE ejecuta `main_stat_all_days.py`** al finalizar
7. **Abre el navegador con el reporte HTML completo**:
   - Tabla de métricas en 2 columnas
   - Equity curve (área verde pastel)
   - Histograma de profit
   - Profit por hora del día
   - Profit por día de la semana

**Parámetros FIXED** (en `strat_absortion_shape.py`):
```python
TP_POINTS = 4.0                      # Take Profit fijo
SL_POINTS = 3.0                      # Stop Loss fijo
POINT_VALUE = 20.0                   # $20 por punto (NQ)
CONTRACTS = 1                        # 1 contrato por trade
NUM_MAX_OPEN_CONTRACTS = 1           # Máximo 1 posición abierta
```

**Parámetros VIX** (en `strat_absortion_shape_vix.py`):
```python
ATR_PERIOD = 14                      # Periodo ATR (14 minutos)
ATR_MULTIPLIER_SL = 1.0              # SL = 1.0 × ATR
ATR_MULTIPLIER_TP = 2.5              # TP = 2.5 × ATR
TRAILING_STOP_ATR_MULT = 0.75        # Trailing = 0.75 × ATR
USE_TRAILING_STOP = True             # Activar trailing stop
CONTRACTS = 1                        # 1 contrato por trade
NUM_MAX_OPEN_CONTRACTS = 3           # Máximo 3 posiciones abiertas
```

---

### **FASE 4: Análisis de Resultados (OPCIONAL - Ya ejecutado automáticamente)**

> **NOTA**: Esta fase **se ejecuta automáticamente** al final de la Fase 3. Solo necesitas ejecutarla manualmente si:
> - Quieres regenerar el reporte con datos existentes
> - Quieres cambiar parámetros de visualización
> - El reporte automático falló

#### 4.1. Generar reporte consolidado multi-día (manual)

```bash
cd strategies/strat_OM_4_absortion
python main_stat_all_days.py
```

**Interactivo - Te pregunta**:
```
SELECT STRATEGY TYPE TO ANALYZE:
  1. FIXED   - Fixed TP/SL (tracking_record/)
  2. VIX     - ATR + Trailing Stop (tracking_record_vix/)

Enter choice (1 or 2): _
```

**También puedes usar línea de comandos**:
```bash
# Analizar FIXED directamente
python main_stat_all_days.py --strategy FIXED

# Analizar VIX directamente
python main_stat_all_days.py --strategy VIX

# No abrir navegador automáticamente
python main_stat_all_days.py --strategy VIX --no-open
```

**Salida**:
- **FIXED**: `charts/absortion_shape_stats_all_days_FIXED.html`
- **VIX**: `charts/absortion_shape_stats_all_days_VIX.html`

**Contenido del reporte**:
1. **Tabla de métricas en 2 columnas**:
   - General: Total trades, periodo, exposure days, avg duration
   - Performance: Total profit, avg profit, profit factor, expectancy
   - Win/Loss: Win rate, avg winner/loser, largest trades
   - Risk: Max drawdown, Sharpe ratio, Sortino ratio, streaks
   - Distribution: Skewness, kurtosis
   - Exit reasons: TARGET, STOP, EOD
   - Signal breakdown: d-shape vs p-shape profit

2. **Gráficos interactivos (Plotly)**:
   - Equity curve (área verde pastel con alpha)
   - Histograma de profit distribution
   - Profit por hora del día
   - Profit por día de la semana

---

### **FASE 5: Análisis Individual (Opcional)**

Si quieres analizar un día específico en detalle:

#### Para FIXED:
```bash
cd strategies/strat_OM_4_absortion

# Editar main_start.py líneas 39-41:
TNS_FILE = DATA_DIR / "historic" / "time_and_sales_nq_20250918.csv"
# (el SIGNALS_DATE se extrae automáticamente)

python main_start.py
```

#### Para VIX:
```bash
cd strategies/strat_OM_4_absortion

# Editar main_start_vix.py líneas 39-41:
TNS_FILE = DATA_DIR / "historic" / "time_and_sales_nq_20250918.csv"

python main_start_vix.py
```

**Ambos generan**:
1. Trades CSV en `outputs/absortion_shape/`
2. Visualización de trades: `charts/trades_visualization_*.html`
3. Resumen estadístico: `charts/summary_report_*.html`
4. Gráficos de equity/drawdown: `charts/backtest_results_*.html`

---

## Resumen de Scripts

| Script | Propósito | Genera CSV | Genera HTML | Cuándo usar |
|--------|-----------|------------|-------------|-------------|
| `split_by_date.py` | Dividir T&S por fecha | ✅ | ❌ | Archivos multi-día |
| `iterate_on_main_to_sb_shapes.py` | Generar señales (db_shapes) | ✅ | ✅ | Procesar todos los días |
| `iterate_backtest_all_days.py` | Backtest + Reporte automático | ✅ | ✅ | **PRINCIPAL - Después de tener señales** |
| `main_stat_all_days.py` | Análisis consolidado | ❌ | ✅ | Solo si falla reporte automático |
| `main_start.py` | Análisis un día (FIXED) | ✅ | ✅ | Análisis detallado individual |
| `main_start_vix.py` | Análisis un día (VIX) | ✅ | ✅ | Análisis detallado individual |

---

## Estructura de Archivos

```
fabio_valentini/
├── data/
│   ├── time_and_sales_YYYYMMDD_HHMMSS.csv  (raw downloads)
│   └── historic/
│       └── time_and_sales_nq_YYYYMMDD.csv  (split by date)
│
├── outputs/absortion_shape/
│   ├── db_shapes_dom_YYYYMMDD.csv          (señales detectadas)
│   ├── tracking_record/                     (resultados FIXED)
│   │   └── dbshapes_TR_YYYYMMDD.csv
│   └── tracking_record_vix/                 (resultados VIX)
│       └── dbshapes_TR_vix_YYYYMMDD.csv
│
├── charts/
│   ├── detections/
│   │   └── absorption_report_YYYYMMDD.html
│   ├── absortion_shape_stats_all_days_FIXED.html
│   ├── absortion_shape_stats_all_days_VIX.html
│   ├── trades_visualization_*.html
│   ├── summary_report_*.html
│   └── backtest_results_*.html
│
├── strat_absortion/
│   ├── main.py                              (detectar patrones)
│   ├── iterate_on_main_to_sb_shapes.py     (batch detección)
│   └── split_by_date.py                     (dividir T&S)
│
└── strategies/strat_OM_4_absortion/
    ├── iterate_backtest_all_days.py         (batch backtest)
    ├── main_stat_all_days.py                (análisis multi-día)
    ├── main_start.py                        (un día FIXED)
    ├── main_start_vix.py                    (un día VIX)
    ├── strat_absortion_shape.py             (engine FIXED)
    └── strat_absortion_shape_vix.py         (engine VIX)
```

---

## Workflow Rápido (Ejemplo Completo)

```bash
# 1. Dividir archivos por fecha (si es necesario)
python strat_absortion/split_by_date.py

# 2. Generar señales para todos los días
python strat_absortion/iterate_on_main_to_sb_shapes.py
# → Confirmar: y

# 3. Ejecutar backtest VIX para todos los días + Reporte automático
cd strategies/strat_OM_4_absortion
python iterate_backtest_all_days.py
# → Elegir: 2 (VIX)
# → Confirmar: y
# (El script ejecuta backtest Y genera el reporte HTML automáticamente)

# Resultado:
# - 35 archivos CSV generados en tracking_record_vix/
# - Navegador abre automáticamente con reporte completo (tabla + 4 gráficos)
```

**¡SOLO 3 PASOS!** Ya no necesitas ejecutar `main_stat_all_days.py` manualmente.

---

## Comparación FIXED vs VIX

Para comparar ambas estrategias:

```bash
# 1. Ejecutar backtest FIXED (genera reporte automáticamente)
python iterate_backtest_all_days.py  # Elegir 1 (FIXED)
# → Genera: charts/absortion_shape_stats_all_days_FIXED.html

# 2. Ejecutar backtest VIX (genera reporte automáticamente)
python iterate_backtest_all_days.py  # Elegir 2 (VIX)
# → Genera: charts/absortion_shape_stats_all_days_VIX.html

# 3. Comparar ambos reportes abriendo los 2 HTML en el navegador
```

**Simplificado**: Cada ejecución de `iterate_backtest_all_days.py` genera automáticamente su reporte, eliminando pasos manuales.

---

## Troubleshooting

### Problema: No se generan CSV de señales
**Causa**: Parámetros muy estrictos o datos insuficientes

**Solución**: Editar `strat_absortion/main.py` líneas 27-34:
```python
PROFILE_WINDOW = 20                  # Reducir a 15 si muy pocos datos
EXTREME_VOLUME_MULTIPLIER = 2        # Reducir a 1.5 para más detecciones
MIN_PRICE_LEVELS = 20                # Reducir a 15
MIN_BID_ASK_SIZE = 30                # Reducir a 20
```

### Problema: Backtest timeout en archivos grandes
**Causa**: Archivo T&S muy grande (>40MB)

**Solución**: Aumentar timeout en `iterate_on_main_to_sb_shapes.py` línea 105:
```python
timeout=3600  # 60 minutos para archivos muy grandes
```

### Problema: No hay tracking_records para analizar
**Causa**: No se ejecutó el backtest (Fase 3)

**Solución**: Primero ejecutar `iterate_backtest_all_days.py` antes de `main_stat_all_days.py`

---

*Última actualización: 2025-11-05*
