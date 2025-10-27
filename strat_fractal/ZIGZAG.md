# ZigZag Fractal Detection Method

## Overview
Sistema de detección de pivotes de precio (fractales) usando algoritmo ZigZag multi-nivel para análisis de estructuras de mercado anidadas en futuros NQ (Nasdaq-100 E-mini).

## Concepto del Algoritmo ZigZag

El algoritmo ZigZag filtra el ruido del precio conectando solo puntos de pivote significativos (picos y valles) que cumplen un umbral mínimo de movimiento porcentual. Esto permite identificar la estructura direccional del mercado eliminando fluctuaciones menores.

### Características Principales
- **Detección de pivotes alternados**: Alterna entre PICO (peak) y VALLE (valley)
- **Umbral porcentual**: Solo registra movimientos superiores a un % mínimo configurable
- **Multi-nivel**: Detecta estructuras anidadas (MINOR y MAJOR) simultáneamente
- **Preview tracking**: Incluye índice de tick 1 minuto antes del fractal para replay

---

## Arquitectura del Sistema

### 1. Detección de Fractales (`find_fractals.py`)

**Input**: Datos tick-by-tick del archivo `ts_and_dom_24_oct.csv`

**Proceso**:
```
Tick Data (367,630 registros)
    ↓
Agregación OHLC (ventanas de 60 segundos)
    ↓
ZigZag Detector MINOR (0.02% threshold)
    ↓
ZigZag Detector MAJOR (0.10% threshold)
    ↓
Output: 2 archivos CSV con fractales detectados
```

**Output**:
- `zig_zag_fractals_minor_{timestamp}.csv` - Estructura menor anidada
- `zig_zag_fractals_major_{timestamp}.csv` - Estructura mayor primaria

---

## Configuración

### Parámetros Principales (`find_fractals.py` líneas 22-35)

```python
# Archivo de entrada
INPUT_FILE = "ts_and_dom_24_oct.csv"

# Parámetros ZigZag para estructura MINOR (fractales pequeños)
MIN_CHANGE_PCT_MINOR = 0.02  # 0.02% cambio mínimo

# Parámetros ZigZag para estructura MAJOR (fractales grandes)
MIN_CHANGE_PCT_MAJOR = 0.10  # 0.10% cambio mínimo (5x mayor)

# Agregación de datos
AGGREGATION_WINDOW = 60  # 60 segundos = velas de 1 minuto

# Preview para replay
PREVIEW = 1  # 1 minuto antes del fractal
```

### Niveles de Detección

| Nivel | Umbral | Propósito | Color Visualización |
|-------|--------|-----------|---------------------|
| **MINOR** | 0.02% | Estructura anidada, movimientos menores | Gris oscuro (width=1) |
| **MAJOR** | 0.10% | Estructura primaria, movimientos significativos | Negro (width=2) |

---

## Algoritmo de Detección

### Clase `UnifiedZigzagDetector`

**Estado Interno**:
```python
current_direction: UP | DOWN  # Dirección actual de búsqueda
current_high: float           # Máximo actual (para buscar PICO)
current_low: float            # Mínimo actual (para buscar VALLE)
last_pivot_price: float       # Precio del último pivote confirmado
```

**Lógica de Detección**:

1. **Dirección UP** (buscando PICO):
   ```
   Si precio > current_high:
       → Actualizar current_high
       → Actualizar current_low = precio

   Si precio < current_high - (MIN_CHANGE_PCT * current_high):
       → Confirmar PICO en current_high
       → Cambiar dirección a DOWN
       → Buscar próximo VALLE
   ```

2. **Dirección DOWN** (buscando VALLE):
   ```
   Si precio < current_low:
       → Actualizar current_low
       → Actualizar current_high = precio

   Si precio > current_low + (MIN_CHANGE_PCT * current_low):
       → Confirmar VALLE en current_low
       → Cambiar dirección a UP
       → Buscar próximo PICO
   ```

### Alternancia Garantizada

El algoritmo **garantiza alternancia** entre PICO y VALLE:
- Después de detectar un PICO, solo busca VALLE
- Después de detectar un VALLE, solo busca PICO
- Nunca detecta dos PICOS o dos VALLES consecutivos

---

## Formato de Datos de Salida

### Estructura CSV de Fractales

Columnas en `zig_zag_fractals_minor_*.csv` y `zig_zag_fractals_major_*.csv`:

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `candle_index` | int | Índice de la vela OHLC donde ocurrió el fractal |
| `timestamp` | datetime | Timestamp del fractal (formato: YYYY-MM-DD HH:MM:SS) |
| `price` | float | Precio del pivote (PICO o VALLE) |
| `type` | str | Tipo de fractal: "PICO" o "VALLE" |
| `direction` | str | Dirección del movimiento: "UP" o "DOWN" |
| `confirmed` | bool | Siempre True (fractal confirmado) |
| `preview_tick_index` | int | Índice del tick 1 minuto ANTES del fractal |
| `fractal_tick_index` | int | Índice del tick exacto del fractal |
| `preview_minutes` | int | Minutos de preview (siempre 1) |

**Ejemplo**:
```csv
candle_index;timestamp;price;type;direction;confirmed;preview_tick_index;fractal_tick_index;preview_minutes
42;2025-10-24 06:42:35;20327,5;PICO;UP;True;2450;2510;1
87;2025-10-24 07:27:18;20321,25;VALLE;DOWN;True;5123;5201;1
```

---

## Visualización (`plot_fractals.py`)

### Características del Gráfico

**Elementos Visuales**:

1. **Líneas ZigZag**:
   - **MAJOR**: Negro, grosor 2
   - **MINOR**: Gris oscuro, grosor 1

2. **Círculos de Pivotes**:
   - **MAJOR**:
     - Tamaño 8
     - Relleno negro
     - Contorno: Verde (PICO) / Rojo (VALLE), grosor 3

   - **MINOR**:
     - Tamaño 5
     - Relleno negro
     - Contorno: Verde (PICO) / Rojo (VALLE), grosor 2

3. **Diseño**:
   - Fondo blanco
   - Sin grid vertical
   - Grid horizontal tenue
   - Dimensiones: 1400x800 px
   - Interactivo con zoom y tooltips

**Tooltips**:
```
Tipo: PICO / VALLE
Precio: {price}
Timestamp: {timestamp}
Candle Index: {candle_index}
```

---

## Flujo de Ejecución

### Ejecución Automática

```bash
python strat_fractal/find_fractals.py
```

**Pasos**:
1. Carga tick data desde `data/ts_and_dom_24_oct.csv`
2. Agrega en velas OHLC de 60 segundos
3. Ejecuta ZigZag MINOR (0.02%)
4. Ejecuta ZigZag MAJOR (0.10%)
5. Calcula `preview_tick_index` (1 minuto antes)
6. Calcula `fractal_tick_index` (timestamp exacto)
7. Guarda 2 archivos CSV en `outputs/`
8. **Auto-ejecuta** `plot_fractals.py` via subprocess
9. Abre visualización en navegador

### Ejecución Manual de Visualización

```bash
python strat_fractal/plot_fractals.py
```

Carga automáticamente los archivos más recientes de fractales MINOR y MAJOR.

---

## Casos de Uso

### 1. Análisis de Estructura de Mercado

Identificar niveles de soporte/resistencia basados en pivotes históricos confirmados.

**Aplicación**:
- MAJOR fractals → Niveles estructurales significativos
- MINOR fractals → Niveles intra-día y patrones anidados

### 2. Replay de Secuencias

Usar `preview_tick_index` para recrear condiciones del mercado 1 minuto antes del fractal.

**Workflow**:
```python
# Obtener tick 1 minuto antes del fractal
preview_idx = df_fractals['preview_tick_index'].iloc[0]
df_ticks_preview = df_ticks.iloc[preview_idx - 100 : preview_idx + 100]

# Analizar contexto pre-fractal
dom_snapshot = df_ticks_preview['DOM_BID'].iloc[-1]
```

### 3. Filtrado de Señales de Trading

Filtrar señales de otros sistemas basándose en estructura fractal.

**Ejemplo**:
```python
# Solo operar si hay fractal MAJOR cercano
signal_price = 20325.0
nearest_major = df_fractals_major[
    abs(df_fractals_major['price'] - signal_price) < 10
]

if not nearest_major.empty:
    # Señal válida - hay estructura MAJOR cercana
    execute_trade()
```

---

## Rendimiento

### Benchmarks (dataset 367,630 ticks)

| Proceso | Duración | Memoria |
|---------|----------|---------|
| Carga de datos | ~3-5 segundos | 50 MB |
| Agregación OHLC | ~2-3 segundos | 20 MB |
| ZigZag MINOR | ~1-2 segundos | 10 MB |
| ZigZag MAJOR | ~1-2 segundos | 10 MB |
| Cálculo preview | ~1 segundo | 5 MB |
| Guardado CSV | ~1 segundo | - |
| **Total** | **~10-15 segundos** | **~95 MB** |

### Resultados Típicos

**Dataset: ts_and_dom_24_oct.csv** (367,630 ticks, 2 días)

- **MINOR Fractals**: ~800-1200 fractales
  - Picos: ~400-600
  - Valles: ~400-600

- **MAJOR Fractals**: ~150-250 fractales
  - Picos: ~75-125
  - Valles: ~75-125

---

## Diferencias vs. Indicadores Tradicionales

### ZigZag vs. Moving Averages

| Aspecto | ZigZag | Moving Average |
|---------|--------|----------------|
| Lag | Mínimo (1 umbral) | Alto (ventana completa) |
| Pivotes | Explícitos (PICO/VALLE) | Implícitos (cruces) |
| Repaint | Sí (último pivote) | No |
| Alternancia | Garantizada | No garantizada |

### ZigZag vs. Swing High/Low

| Aspecto | ZigZag | Swing High/Low |
|---------|--------|----------------|
| Umbral | Porcentual | Barras fijas |
| Flexibilidad | Alta (ajustable) | Baja (solo #barras) |
| Ruido | Filtrado efectivo | Sensible a volatilidad |
| Multi-nivel | Soportado | No nativo |

---

## Consideraciones Importantes

### 1. Repainting

**El último pivote puede cambiar** hasta que se confirme el siguiente:

```
Precio: 100 → 105 (PICO detectado en 105)
Precio: 105 → 106 (PICO actualizado a 106)
Precio: 106 → 103 (PICO confirmado en 106 al caer 0.10%)
```

**Solución**: Solo usar fractales confirmados con `confirmed=True` (todos los guardados en CSV).

### 2. Umbral de Detección

**Umbral muy bajo** (ej. 0.01%):
- ❌ Demasiados fractales (ruido)
- ❌ Estructura poco clara
- ✅ Sensibilidad alta

**Umbral muy alto** (ej. 0.50%):
- ❌ Muy pocos fractales
- ❌ Pierde movimientos intermedios
- ✅ Solo movimientos mayores

**Recomendación**:
- MINOR: 0.02% - 0.05% (intra-día)
- MAJOR: 0.10% - 0.20% (swing)

### 3. Agregación Temporal

**60 segundos** (actual):
- ✅ Balance precisión/ruido
- ✅ Suficiente granularidad para NQ
- ✅ Rendimiento óptimo

**Alternativas**:
- 30 segundos: Mayor precisión, más fractales MINOR
- 120 segundos: Menos ruido, menos fractales MINOR

---

## Extensiones Futuras

### 1. Detección de Patrones

Identificar patrones específicos en la secuencia de fractales:

```python
# Ejemplo: Doble techo
def detect_double_top(fractals):
    for i in range(len(fractals) - 2):
        if (fractals[i]['type'] == 'PICO' and
            fractals[i+2]['type'] == 'PICO'):
            if abs(fractals[i]['price'] - fractals[i+2]['price']) < 5:
                return True
```

### 2. Niveles Dinámicos

Usar fractales como niveles dinámicos de soporte/resistencia:

```python
# Último fractal MAJOR como nivel clave
last_major_peak = df_major[df_major['type'] == 'PICO'].iloc[-1]['price']
resistance_level = last_major_peak
```

### 3. Integración con Estrategias

Filtrar entradas de estrategias existentes:

```python
# Solo operar cerca de fractales MAJOR
def validate_signal(price, df_major):
    nearest = df_major.iloc[(df_major['price'] - price).abs().argsort()[:1]]
    distance = abs(nearest['price'].values[0] - price)
    return distance < 10  # Dentro de 10 puntos
```

### 4. Análisis de Retrocesos

Medir retrocesos entre fractales para identificar zonas Fibonacci:

```python
# Calcular retroceso entre VALLE y PICO
valley_price = fractals[i]['price']  # VALLE
peak_price = fractals[i+1]['price']  # PICO
retracement_38 = peak_price - (peak_price - valley_price) * 0.382
```

---

## Comparación con Market Profile

### Complementariedad

**ZigZag Fractals**:
- Identifica CUÁNDO y DÓNDE cambia la dirección
- Estructura temporal secuencial
- Perspectiva direccional

**Market Profile** (d-Shape/p-Shape):
- Identifica CÓMO se distribuye el volumen
- Estructura de absorción en niveles
- Perspectiva de flujo de órdenes

**Uso Conjunto**:
```python
# Ejemplo: Fractal MAJOR + d-Shape = Setup fuerte
if (fractal['type'] == 'VALLE' and
    shape['type'] == 'd_shape' and
    abs(fractal['price'] - shape['close_price']) < 5):
    # LONG setup: VALLE + absorción BID
    execute_long()
```

---

## Troubleshooting

### Problema: Muy pocos fractales MAJOR

**Causa**: Umbral demasiado alto
**Solución**: Reducir `MIN_CHANGE_PCT_MAJOR` a 0.08% o 0.07%

### Problema: Demasiados fractales MINOR

**Causa**: Umbral muy bajo o agregación muy fina
**Solución**:
- Aumentar `MIN_CHANGE_PCT_MINOR` a 0.03%
- Aumentar `AGGREGATION_WINDOW` a 90 o 120 segundos

### Problema: Fractales no alternados

**Causa**: Error en lógica del detector
**Verificación**:
```python
# Verificar alternancia en output
df = pd.read_csv('outputs/zig_zag_fractals_minor_latest.csv', sep=';')
types = df['type'].values
for i in range(len(types) - 1):
    assert types[i] != types[i+1], f"Error: tipos consecutivos en índice {i}"
```

### Problema: Preview_tick_index fuera de rango

**Causa**: Fractal muy cerca del inicio del dataset
**Solución**: Ya manejado con `max(0, ...)` en el código

---

## Referencias

### Papers y Literatura

- **Swing Trading**: Uso de pivotes para identificar cambios de tendencia
- **Dow Theory**: Concepto de Higher Highs / Lower Lows
- **Elliott Wave**: Estructura fractal de mercados

### Indicadores Relacionados

- **ZigZag (TradingView)**: Similar pero sin multi-nivel
- **Swing High/Low**: Basado en barras en lugar de %
- **Pivot Points**: Basado en OHLC pero sin filtrado dinámico

---

## Archivos del Sistema

```
strat_fractal/
├── find_fractals.py          # Detección de fractales (ejecutar primero)
├── plot_fractals.py          # Visualización multi-nivel (auto-ejecutado)
├── ZIGZAG.md                 # Esta documentación
└── (backups antiguos)

outputs/
├── zig_zag_fractals_minor_YYYYMMDD_HHMMSS.csv
└── zig_zag_fractals_major_YYYYMMDD_HHMMSS.csv

charts/
└── fractals_multi_level_chart_YYYYMMDD_HHMMSS.html
```

---

## Contacto y Mantenimiento

**Versión**: 1.0 (Multi-Level ZigZag)
**Última actualización**: 2025-10-27
**Proyecto**: Fabio Valentini NQ Trading Toolkit

---

*Este método es parte del sistema de análisis de orden flow para futuros NQ, complementando las herramientas de Market Profile (d-Shape/p-Shape) y backtesting tick-driven.*
