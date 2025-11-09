# Sistema Bidireccional NinjaTrader ↔ Python

## Arquitectura

```
┌─────────────────┐         ┌──────────────────────┐         ┌─────────────────┐
│  NinjaTrader 8  │         │   Python Server      │         │  Visualización  │
│                 │         │  tick_server_bidirect│         │ plot_tick_server│
├─────────────────┤         ├──────────────────────┤         ├─────────────────┤
│  AASender.cs    │────────>│ Puerto 55555         │         │                 │
│  (Indicador)    │  Ticks  │ Recibe ticks         │────────>│ Gráfico HTML    │
│                 │         │ Detecta patrones     │   CSV   │ con órdenes     │
├─────────────────┤         ├──────────────────────┤         └─────────────────┘
│AAStrategyBidirect│<───────│ Puerto 55556         │
│  (Estrategia)   │ Señales │ Envía PATTERN        │
│                 │ EXIT    │ Recibe EXIT          │
└─────────────────┘         └──────────────────────┘
```

## Problema Resuelto

### ❌ Antes (INCORRECTO)
```
1. Python detecta patrón
2. Python envía orden MARKET de entrada
3. Python envía TP y SL inmediatamente  ← ERROR: Órdenes OCO antes del fill
4. Ninja rechaza: "Order status is CancelPending, affected Order: Buy 1 StopMarket @ 25322.5"
```

### ✅ Ahora (CORRECTO)
```
1. Python detecta patrón
2. Python envía señal PATTERN a NinjaTrader
3. NinjaTrader ejecuta orden MARKET de entrada
4. NinjaTrader espera el FILL (OnExecutionUpdate)
5. Solo después del fill, NinjaTrader coloca TP y SL
6. Cuando TP o SL se ejecuta, NinjaTrader envía EXIT a Python
7. Python registra la salida en CSV
```

## Componentes

### 1. AASender.cs (Indicador)
- **Puerto**: 55555
- **Función**: Envía ticks de mercado a Python
- **Datos**: timestamp, price, volume, side (BID/ASK/BETWEEN)

### 2. AAStrategyBidirect.cs (Estrategia) - NUEVO
- **Puerto**: 55556 (diferente del indicador)
- **Función**:
  - Escucha señales PATTERN desde Python
  - Ejecuta órdenes MARKET de entrada
  - **Espera el fill** antes de colocar TP/SL
  - Envía señales EXIT a Python cuando TP o SL se ejecuta

**Parámetros**:
- `TakeProfitTicks`: 16 (4 puntos × 4 ticks/punto)
- `StopLossTicks`: 12 (3 puntos × 4 ticks/punto)
- `Quantity`: 1
- `ServerHost`: 127.0.0.1
- `ServerPort`: 55556

### 3. tick_server_bidirect.py (Python)
- **Escucha en puerto 55555**: Recibe ticks de AASender
- **Escucha en puerto 55556**: Envía PATTERN y recibe EXIT
- **Funciones**:
  - Detecta patrones d_shape/p_shape
  - Envía señales PATTERN a NinjaTrader
  - Recibe señales EXIT de NinjaTrader
  - Registra todo en CSV con columnas de órdenes

## Instalación

### Paso 1: Compilar Indicador y Estrategia en NinjaTrader

1. Abrir NinjaTrader 8
2. Menú → Tools → NinjaScript Editor
3. Crear nuevo Indicator:
   - Copiar contenido de `AASender.cs`
   - Compilar (F5)
4. Crear nueva Strategy:
   - Copiar contenido de `AAStrategyBidirect.cs`
   - Compilar (F5)

### Paso 2: Configurar NinjaTrader

#### A) Agregar Indicador al Gráfico
1. Gráfico NQ → Indicators → AASender
2. Parámetros:
   - Server Host: 127.0.0.1
   - Server Port: 55555

#### B) Activar Estrategia
1. Control Center → Strategies → AAStrategyBidirect
2. Parámetros:
   - Server Host: 127.0.0.1
   - Server Port: 55556
   - Take Profit: 16 ticks
   - Stop Loss: 12 ticks
   - Quantity: 1
3. Enable strategy

### Paso 3: Ejecutar Python Server

```bash
cd strat_absortion
python tick_server_bidirect.py
```

**Salida esperada**:
```
================================================================================
ABSORPTION STRATEGY SERVER
================================================================================
Host: localhost
Port: 55555

Strategy Configuration:
  Profile Window: 20s
  Min Price Levels: 3
  Min Bid/Ask Size: 3
  Cooldown: 60s

[OK] Server listening on localhost:55555
[OK] Waiting for client connection...
```

## Flujo de Trabajo Completo

### 1. Iniciar Sistema
```bash
# Terminal 1: Python Server
python strat_absortion/tick_server_bidirect.py

# NinjaTrader:
# - Activar indicador AASender en gráfico NQ
# - Activar estrategia AAStrategyBidirect
```

### 2. Detección de Patrón
```
[Python] PATTERN DETECTED!
         Detection #1
         Shape: d_shape
         Price: 25320.50
         Time: 2025-11-09 14:23:45

[Python] -> Ninja: {"command":"PATTERN","shape":"d_shape",...}

[Ninja]  Received d_shape signal -> LONG entry
[Ninja]  Submitted order: Buy 1 Market
```

### 3. Fill de Entrada
```
[Ninja]  Entry filled at 25320.75, placing TP/SL
[Ninja]  Set Profit Target: 25324.75 (16 ticks = 4 points)
[Ninja]  Set Stop Loss: 25317.75 (12 ticks = 3 points)
```

### 4. Salida (TP o SL)
```
[Ninja]  Exit filled at 25324.75 (TARGET)
[Ninja]  -> Python: {"command":"EXIT","price":25324.75,"tag":"TARGET"}

[Python] [EXIT] Received from NinjaTrader: TARGET @ 25324.75
[Python] [ORDER] Exit logged: TARGET @ 25324.75
```

### 5. Registro en CSV
```csv
date;time;bid;ask;price;volume;side;shape;order_type;entry_price;exit_price;exit_tag
20251109;142345.123;;;;25320.50;1;ASK;d_shape;LONG;25320.75;;
20251109;142347.456;;;;25324.75;1;ASK;;;25324.75;TARGET
```

### 6. Visualización
```bash
python utils/plot_tick_server.py
```

**Elementos del gráfico**:
- 🔺 LONG Entry: triángulo verde hacia arriba
- 🔻 SHORT Entry: triángulo rojo hacia abajo
- ⬜ TARGET Exit: cuadrado verde vacío
- ⬜ STOP Exit: cuadrado rojo vacío
- 📈 Líneas punteadas conectando entrada → salida

## Formato CSV

### Columnas
```
date        : YYYYMMDD
time        : HHMMSS.fff
bid         : Precio BID (si disponible)
ask         : Precio ASK (si disponible)
price       : Precio del tick
volume      : Volumen del tick
side        : BID/ASK/BETWEEN/UNKNOWN
shape       : d_shape/p_shape (solo en detecciones)
order_type  : LONG/SHORT (solo en entradas)
entry_price : Precio de entrada (solo en entradas)
exit_price  : Precio de salida (solo en salidas)
exit_tag    : TARGET/STOP (solo en salidas)
```

### Ejemplo Real
```csv
date;time;bid;ask;price;volume;side;shape;order_type;entry_price;exit_price;exit_tag
20251109;142300.123;25320.25;;25320.25;2;BID;;;;;
20251109;142345.456;;;;25320.50;1;ASK;d_shape;LONG;25320.75;;
20251109;142347.789;25324.75;;25324.75;1;BID;;;25324.75;TARGET
```

## Ventajas del Sistema

### ✅ Flujo Correcto de Órdenes
- TP y SL solo se colocan **después** del fill de entrada
- No más errores "Order status is CancelPending"
- Órdenes OCO correctamente vinculadas

### ✅ Bidireccional
- Python → Ninja: Señales de detección
- Ninja → Python: Confirmación de ejecuciones
- CSV completo con todas las operaciones

### ✅ Separación de Responsabilidades
- **Python**: Análisis de patrones, registro histórico
- **NinjaTrader**: Ejecución de órdenes, gestión de posiciones

### ✅ Visualización Completa
- Gráfico interactivo con Plotly
- Tooltip fijo con información de detecciones
- Marcadores visuales para entradas/salidas
- Líneas conectoras codificadas por color

## Solución de Problemas

### Error: "Failed to connect after 10 attempts"
**Causa**: Python server no está corriendo
**Solución**:
```bash
python strat_absortion/tick_server_bidirect.py
```

### Error: "Order status is CancelPending"
**Causa**: Usando versión antigua sin AAStrategyBidirect
**Solución**: Usar la nueva estrategia AAStrategyBidirect.cs

### No se visualizan órdenes en gráfico
**Causa**: CSV no tiene columnas de órdenes o están vacías
**Solución**:
1. Verificar que tick_server_bidirect.py está corriendo
2. Verificar que AAStrategyBidirect está activa
3. Esperar a que se ejecute algún patrón

### Órdenes no se ejecutan
**Causa**: Puerto incorrecto o estrategia no conectada
**Solución**:
- Verificar puerto 55556 en Python y NinjaTrader
- Revisar logs en NinjaTrader Output Window
- Verificar que estrategia está "Enabled"

## Logs de Depuración

### Python
```python
[OK] Server listening on localhost:55555
[OK] Client connected from ('127.0.0.1', 52341)
[PATTERN DETECTED!] Detection #1, Shape: d_shape
[ORDER] Entry logged: LONG @ 25320.75
[EXIT] Received from NinjaTrader: TARGET @ 25324.75
[ORDER] Exit logged: TARGET @ 25324.75
```

### NinjaTrader (Output Window)
```
[AAStrategyBidirect] Connected to 127.0.0.1:55556
[AAStrategyBidirect] Received d_shape signal -> LONG entry
[AAStrategyBidirect] Entry filled at 25320.75, placing TP/SL
[AAStrategyBidirect] Exit filled at 25324.75 (TARGET)
[AAStrategyBidirect] Sent EXIT to server: TARGET @ 25324.75
```

## Archivos Generados

```
data/monitor_ninja/
  ├── tick_server_bidirect_20251109_142300.csv  ← Con órdenes
  └── tick_server_20251109_142300.csv           ← Sin órdenes (versión antigua)

charts/
  └── tick_server_chart_142300.html             ← Visualización interactiva
```

## Próximos Pasos

1. **Gestión de Múltiples Posiciones**: Modificar `NUM_MAX_OPEN_CONTRACTS` > 1
2. **TP/SL Dinámicos**: Basados en ATR o volatilidad
3. **Trailing Stop**: Implementar en AAStrategyBidirect.cs
4. **Filtros Adicionales**: Hora del día, dirección del mercado, etc.
5. **Dashboard en Tiempo Real**: Web app con gráficos live

---

**Versión**: 2.0 (Bidirectional)
**Fecha**: 2025-11-09
**Autor**: Fabio Valentini + Claude Code
