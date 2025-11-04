# Estrategia OM_4 - Absorption Shape (d-Shape & p-Shape)

## Descripción

Estrategia de trading basada en la detección de patrones de absorción en Market Profile:
- **d-shape**: Absorción en el ASK → Señal de venta (esperamos caída)
- **p-shape**: Absorción en el BID → Señal de compra (esperamos subida)

La estrategia ejecuta backtests tick-by-tick con gestión de riesgo (TP/SL) y control de posiciones simultáneas.

---

## Estructura de Archivos

```
strat_OM_4_absortion/
├── README.md                          # Este archivo
├── main_start.py                      # Orchestrador principal (EJECUTAR ESTE)
├── strat_absortion_shape.py          # Motor de backtest
├── plot_trades_chart.py               # Visualización de trades
├── plot_backtest_results.py           # Gráficos de equity/drawdown
└── summary.py                         # Resumen estadístico
```

---

## Requisitos Previos

### 1. Datos de Input

**Archivo de Time & Sales (T&S):**
- Ubicación: `data/historic/time_and_sales_nq_YYYYMMDD.csv`
- Formato: CSV europeo (`;` separador, `,` decimal)
- Columnas: `Timestamp;Precio;Volumen;Lado;Bid;Ask`

**Archivo de Señales:**
- Ubicación: `outputs/absortion_shape/db_shapes_dom_YYYYMMDD.csv`
- Generado por: `python strat_absortion/main.py`
- Formato: CSV europeo
- Columnas: `timestamp;shape;close_price;bid_ask_ratio;num_price_levels;...`

### 2. Generar Señales (si no existen)

```bash
# Configurar fecha en strat_absortion/main.py (línea 13)
FICHERO_ORIGEN = "time_and_sales_nq_20250918"

# Ejecutar detección de patrones
python strat_absortion/main.py
```

Esto generará:
- `outputs/absortion_shape/db_shapes_dom_20250918.csv`
- `charts/detections/market_profile_detections_YYYYMMDD_HHMMSS.html`

---

## Uso Rápido (Recomendado)

### Ejecutar Pipeline Completo

```bash
cd strategies/strat_OM_4_absortion
python main_start.py
```

**Este comando ejecuta automáticamente:**
1. ✅ **Backtest** → Genera CSV de trades
2. ✅ **Visualización** → Gráfico interactivo con entradas/salidas
3. ✅ **Estadísticas** → Reporte HTML con métricas
4. ✅ **Gráficos** → Equity curve y drawdown

---

## Configuración

### Archivo: `main_start.py` (líneas 36-75)

#### **Archivos de Entrada**
```python
# Time & Sales (cambiar fecha según necesidad)
TNS_FILE = DATA_DIR / "historic" / "time_and_sales_nq_20250918.csv"

# El archivo de señales se busca AUTOMÁTICAMENTE:
# - Extrae la fecha del TNS_FILE (ejemplo: 20250918)
# - Busca db_shapes_dom_20250918.csv en:
#   1. outputs/absortion_shape/
#   2. outputs/
```

#### **Parámetros de Trading**
```python
SYMBOL = "NQ"                    # Nasdaq-100 E-mini
TP_POINTS = 3.0                  # Take Profit en puntos
SL_POINTS = 1.5                  # Stop Loss en puntos
POINT_VALUE = 20.0               # Valor del punto ($20 por punto NQ)
THRESHOLD_EXTRA = 0.25           # Margen de seguridad adicional
CONTRACTS = 1                    # Contratos por trade
BREAK_EVEN_POINTS = 50.0         # Mover stop a breakeven después de X puntos
NUM_MAX_OPEN_CONTRACTS = 3       # Máximo de posiciones simultáneas
```

#### **Visualización**
```python
USE_INDEX_RANGE = False          # True: filtrar trades, False: mostrar todo
START_INDEX = 0                  # Índice inicial (si USE_INDEX_RANGE = True)
END_INDEX = 50                   # Índice final (si USE_INDEX_RANGE = True)
```

---

## Archivos de Salida

### Ubicaciones y Nombres

#### **CSV de Trades**
```
outputs/absortion_shape/dbshapes_TR_20250918.csv
```
**Formato:** `dbshapes_TR_{fecha}.csv` (fecha extraída del archivo de señales)

**Columnas:**
- `timestamp`: Timestamp de la señal
- `shape`: d_shape o p_shape
- `entry_price`: Precio de entrada
- `exit_price`: Precio de salida
- `exit_reason`: TARGET o STOP
- `pnl_points`: Profit/Loss en puntos
- `pnl_dollars`: Profit/Loss en dólares
- `signal_type`: LONG o SHORT

#### **Gráficos HTML (carpeta `charts/`)**

1. **Visualización de Trades**
   ```
   charts/trades_visualization_absortion_shape_20250918.html
   ```
   - Gráfico interactivo Plotly
   - Marcadores de entrada (triángulos)
   - Marcadores de salida (cuadrados)
   - Líneas punteadas conectando entrada-salida
   - Panel inferior con P&L acumulado

2. **Resumen Estadístico**
   ```
   charts/summary_report_absortion_shape_20250918.html
   ```
   - Tabla HTML con métricas clave
   - Win Rate, Profit Factor, Sharpe Ratio
   - Max Drawdown, Recovery Factor
   - Breakdown por tipo de señal

3. **Gráficos de Equity**
   ```
   charts/backtest_results_absortion_shape_20250918_*.html
   ```
   - Curva de equity
   - Drawdown overlay
   - Distribución de ganancias/pérdidas

---

## Workflow Manual (Paso a Paso)

Si prefieres ejecutar cada componente por separado:

### 1. Backtest
```bash
python strat_absortion_shape.py
```
**Output:** `outputs/absortion_shape/dbshapes_TR_20250918.csv`

### 2. Visualización de Trades
```bash
python plot_trades_chart.py
```
**Output:** `charts/trades_visualization_absortion_shape_20250918.html`

### 3. Resumen Estadístico
```bash
python summary.py
```
**Output:** `charts/summary_report_absortion_shape_20250918.html`

### 4. Gráficos de Resultados
```bash
python plot_backtest_results.py
```
**Output:** `charts/backtest_results_absortion_shape_20250918_*.html`

---

## Interpretación de Resultados

### Leyenda de Gráficos

#### **Entradas**
- 🔺 **Triángulo Verde hacia arriba** = Entrada LONG (p_shape)
- 🔻 **Triángulo Rojo hacia abajo** = Entrada SHORT (d_shape)

#### **Salidas**
- 🟩 **Cuadrado Verde abierto** = Salida por TARGET (ganancia)
- 🟥 **Cuadrado Rojo abierto** = Salida por STOP (pérdida)

#### **Conexiones**
- **Línea punteada verde** = Trade cerrado en TARGET
- **Línea punteada roja** = Trade cerrado en STOP

### Métricas Clave

| Métrica | Descripción | Objetivo |
|---------|-------------|----------|
| **Win Rate** | % de trades ganadores | > 50% |
| **Profit Factor** | Ganancias / Pérdidas | > 1.5 |
| **Sharpe Ratio** | Retorno ajustado por riesgo | > 1.0 |
| **Max Drawdown** | Mayor caída desde peak | Minimizar |
| **Recovery Factor** | Total P&L / Max DD | > 2.0 |

---

## Ejemplos de Uso

### Ejemplo 1: Backtest de Septiembre 2025

```bash
# 1. Editar main_start.py (línea 36)
TNS_FILE = DATA_DIR / "historic" / "time_and_sales_nq_20250915.csv"

# 2. Ejecutar pipeline completo
cd strategies/strat_OM_4_absortion
python main_start.py
```

**Archivos generados:**
- `outputs/absortion_shape/dbshapes_TR_20250915.csv`
- `charts/trades_visualization_absortion_shape_20250915.html`
- `charts/summary_report_absortion_shape_20250915.html`

### Ejemplo 2: Optimización de Parámetros

```python
# Probar diferentes configuraciones TP/SL
# Editar main_start.py:

# Configuración Conservadora
TP_POINTS = 2.0
SL_POINTS = 1.0
NUM_MAX_OPEN_CONTRACTS = 1

# Configuración Agresiva
TP_POINTS = 5.0
SL_POINTS = 2.5
NUM_MAX_OPEN_CONTRACTS = 5
```

### Ejemplo 3: Filtrar Visualización por Rango

```python
# Editar main_start.py (líneas 75-77)
USE_INDEX_RANGE = True
START_INDEX = 0
END_INDEX = 50

# Esto mostrará solo los primeros 50 trades en el gráfico
```

---

## Troubleshooting

### Error: "No se encontró el archivo de señales"

**Causa:** No existe `db_shapes_dom_{fecha}.csv`

**Solución:**
```bash
# 1. Verificar fecha del TNS_FILE
# 2. Generar señales
python strat_absortion/main.py
```

### Error: "File has been modified since read"

**Causa:** Proceso en segundo plano modificando el archivo

**Solución:**
```bash
# Esperar a que termine el proceso o matar procesos Python:
taskkill /F /IM python.exe  # Windows
pkill python  # Linux/Mac
```

### Gráfico no se abre automáticamente

**Causa:** Navegador no encontrado

**Solución:**
- Abrir manualmente desde `charts/`
- Verificar que existe un navegador por defecto configurado

---

## Notas Técnicas

### Formato de CSV
- **Separador:** `;` (punto y coma)
- **Decimal:** `,` (coma)
- **Encoding:** UTF-8

### Control de Posiciones
- El parámetro `NUM_MAX_OPEN_CONTRACTS` evita overlapping de trades
- Si hay 3 posiciones abiertas y `NUM_MAX_OPEN_CONTRACTS=3`, nuevas señales se ignoran
- Esto previene over-trading y mejora el realismo del backtest

### Arquitectura Tick-Driven
- Procesamiento secuencial tick-by-tick
- Merge de señales + ticks para orden cronológico exacto
- Real-time position tracking (no batch processing)

---

## Próximas Mejoras

- [ ] TP/SL dinámico basado en ATR
- [ ] Simulación de slippage
- [ ] Comisiones integradas
- [ ] Walk-forward analysis
- [ ] Optimización con grid search
- [ ] Real-time signal streaming

---

## Referencias

- **CLAUDE.md**: Documentación completa del proyecto
- **strat_absortion/main.py**: Detección de patrones Market Profile
- **config.py**: Configuración global del proyecto

---

## Contacto

Para reportar bugs o sugerencias:
- GitHub Issues: [fabio_valentini/issues](https://github.com/ferranfont/fabio_valentini/issues)

---

**Última actualización:** 2025-11-04
**Versión:** 2.1 (Auto-naming con fecha extraída)
