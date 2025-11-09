# Testing Checklist - Sistema Bidireccional NinjaTrader ↔ Python

## Estado Actual

### ✅ Funcionando:
1. **CSV Bidireccional**: Genera `tick_server_bidirect_YYYYMMDD_HHMMSS.csv` con columnas de órdenes
2. **Detección de Patrones**: Python detecta d_shape y p_shape correctamente
3. **Visualización Mejorada**:
   - Puntitos rojos/verdes para detecciones (d_shape/p_shape)
   - Triángulos verde-up para LONG entries
   - Triángulos rojo-down para SHORT entries
4. **Conexión Realtime + Playback**: AAStrategyBidirect.cs se conecta en ambos modos

### ❌ Por Verificar el Lunes:
1. **Ejecución de Órdenes en NinjaTrader**: Verificar que las órdenes MARKET se ejecuten
2. **OCO Bracket Order**: Verificar que TP y SL se muestren en el gráfico de NinjaTrader
3. **Envío de EXIT a Python**: Verificar que cuando TP o SL se ejecuta, Python recibe la señal
4. **Logging de Salidas en CSV**: Verificar que las columnas `exit_price` y `exit_tag` se llenen
5. **Visualización de Salidas**: Cuadrados verdes (TARGET) y rojos (STOP) en el gráfico

---

## Pasos para Probar el Lunes

### 1. Compilar AAStrategyBidirect.cs

**En NinjaTrader:**
1. Tools → NinjaScript Editor (F11)
2. Strategies → AAStrategyBidirect
3. **F5** para compilar
4. Verificar que compile sin errores
5. Cerrar editor

**Cambios recientes**:
- Conecta en `State.DataLoaded` (funciona en Realtime + Playback)
- Logs detallados en `OnExecutionUpdate` para debugging

---

### 2. Iniciar Servidor Python

**Terminal 1:**
```bash
cd strat_absortion
python tick_server_bidirect.py
```

**Salida esperada:**
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
[OK] Strategy server listening on localhost:55556
[OK] Waiting for client connection...
```

---

### 3. Activar NinjaTrader

**Control Center → Strategies:**
1. Disable AAStrategyBidirect (si estaba activa)
2. Enable AAStrategyBidirect
3. Verificar parámetros:
   - Server Host: 127.0.0.1
   - Server Port: 55556
   - Take Profit: 16 ticks
   - Stop Loss: 12 ticks
   - Quantity: 1

**Control Center → Gráfico NQ:**
1. Indicators → AASender
2. Verificar parámetros:
   - Server Host: 127.0.0.1
   - Server Port: 55555

---

### 4. Verificar Conexiones

**En NinjaTrader Output Window (Tools → Output Window):**
```
[AASender] Connection attempt 1/10...
[AASender] Connection successful!
[AASender] Connected to 127.0.0.1:55555

[AAStrategyBidirect] Connection attempt 1/10...
[AAStrategyBidirect] Connection successful!
[AAStrategyBidirect] Connected to 127.0.0.1:55556
```

**En Python console:**
```
[OK] Client connected from ('127.0.0.1', XXXXX)
[OK] Strategy connected from ('127.0.0.1', XXXXX)
```

**Si no se conecta:**
- Verificar que puertos 55555 y 55556 no estén bloqueados
- Reiniciar servidor Python
- Reiniciar estrategia en NinjaTrader

---

### 5. Esperar Detección de Patrón

**En Python console:**
```
================================================================================
PATTERN DETECTED!
================================================================================
Detection #1
Shape: d_shape
Price: 25320.50
Time: 2025-11-11 14:23:45
...

[BIDIRECT] -> Strategy: d_shape @ 25320.50
```

**En NinjaTrader Output Window:**
```
[AAStrategyBidirect] Received d_shape signal -> LONG entry
[AAStrategyBidirect] Execution: LONG_ENTRY | Order: Buy 1 Market | State: Working | Price: 25320.50
[AAStrategyBidirect] *** ENTRY FILLED at 25320.50, placing TP/SL ***
[AAStrategyBidirect] Setting LONG TP/SL: TP=16 ticks, SL=12 ticks
```

**Verificar en gráfico NinjaTrader:**
- [ ] Aparece orden MARKET de entrada (flecha)
- [ ] Después del fill, aparecen 2 líneas:
  - Línea verde arriba (TP a +4 puntos / +16 ticks)
  - Línea roja abajo (SL a -3 puntos / -12 ticks)
- [ ] Ambas órdenes están vinculadas (OCO bracket)

---

### 6. Esperar Salida (TP o SL)

**En NinjaTrader Output Window:**
```
[AAStrategyBidirect] Execution: Exit | Order: Sell 1 Limit | State: Filled | Price: 25324.50
[AAStrategyBidirect] *** EXIT FILLED at 25324.50 (TARGET) ***
[AAStrategyBidirect] Sent EXIT to server: TARGET @ 25324.50
```

**En Python console:**
```
[EXIT] Received from NinjaTrader: TARGET @ 25324.50
[ORDER] Exit logged: TARGET @ 25324.50
```

**Verificar en CSV:**
```csv
date;time;bid;ask;price;volume;side;shape;order_type;entry_price;exit_price;exit_tag
20251111;142345.123;;;;25320.50;1;ASK;d_shape;LONG;25320.50;;
20251111;142347.456;;;;25324.50;1;ASK;;;25324.50;TARGET
```

---

### 7. Generar Gráfico Interactivo

**Terminal 2:**
```bash
python utils/plot_tick_server.py
```

**Verificar en el gráfico HTML:**
- [ ] Puntitos rojos/verdes en las detecciones (d_shape/p_shape)
- [ ] Triángulo verde-up en LONG entry
- [ ] Triángulo rojo-down en SHORT entry
- [ ] Cuadrado verde vacío en TARGET exit
- [ ] Cuadrado rojo vacío en STOP exit
- [ ] Línea punteada conectando entry → exit

---

## Problemas Conocidos y Soluciones

### Problema 1: "Order status is CancelPending"

**Causa**: TP/SL colocadas antes del fill de entrada

**Solución**: Ya corregido en AAStrategyBidirect.cs
- Espera `OrderState.Filled` en `OnExecutionUpdate()`
- Solo después coloca TP y SL

### Problema 2: No se ven órdenes OCO bracket

**Posibles causas**:
1. SetProfitTarget/SetStopLoss no funciona correctamente
2. Estrategia no está en modo "Enabled"
3. Insufficient buying power

**Debugging**:
- Revisar NinjaTrader Output Window para logs detallados
- Verificar que aparezcan mensajes "Setting LONG TP/SL: TP=16 ticks, SL=12 ticks"
- Verificar en NinjaTrader Tools → Account Data → Orders que las órdenes existan

### Problema 3: Python no recibe EXIT

**Debugging**:
```python
# En tick_server_bidirect.py, añadir más logs en handle_strategy_client():
print(f"[DEBUG] Received from strategy: {line}")
```

**En AAStrategyBidirect.cs, verificar**:
- `networkStream` no es null
- `isConnected` es true
- JSON se forma correctamente

### Problema 4: Gráfico no muestra puntitos/triángulos

**Causa**: CSV sin columnas de órdenes (usando tick_server.py en vez de tick_server_bidirect.py)

**Solución**: Verificar que Python console diga:
```
[INFO] Using bidirectional CSV (with order tracking)
```

Si dice "Using regular CSV", significa que tick_server_bidirect.py no está corriendo.

---

## Archivos Modificados Hoy

### 1. `ninja/AAStrategyBidirect.cs`
- ✅ Conecta en `State.DataLoaded` (Realtime + Playback)
- ✅ Logs detallados en `OnExecutionUpdate()`
- ✅ Espera fill antes de colocar TP/SL

### 2. `utils/plot_tick_server.py`
- ✅ Prioriza `tick_server_bidirect_*.csv` sobre `tick_server_*.csv`
- ✅ Muestra puntitos rojos/verdes (detecciones)
- ✅ Muestra triángulos verdes/rojos (entries)
- ✅ Muestra cuadrados verdes/rojos (exits)

### 3. `strat_absortion/tick_server_bidirect.py`
- ✅ CSV con columnas: order_type, entry_price, exit_price, exit_tag
- ✅ Dual-socket: puerto 55555 (ticks) + 55556 (strategy)
- ✅ Envía PATTERN a NinjaTrader
- ✅ Recibe EXIT de NinjaTrader

---

## Siguiente Sesión (Lunes)

### Objetivo Principal:
Verificar que el ciclo completo funcione:
```
1. Python detecta patrón
2. Python envía PATTERN a NinjaTrader
3. NinjaTrader ejecuta MARKET entry
4. NinjaTrader espera fill
5. NinjaTrader coloca TP y SL (OCO bracket visible en gráfico)
6. TP o SL se ejecuta
7. NinjaTrader envía EXIT a Python
8. Python registra exit en CSV
9. Gráfico muestra cuadrados de salida
```

### Esperado en Gráfico de NinjaTrader:
- Flecha entrada MARKET
- Línea verde TP a +4 puntos
- Línea roja SL a -3 puntos
- Órdenes OCO vinculadas (cuando una se ejecuta, la otra se cancela)

### Esperado en Gráfico de Python:
- Puntitos rojos/verdes (detecciones)
- Triángulos verdes/rojos (entries)
- Cuadrados verdes/rojos (exits)
- Líneas punteadas conectando entry → exit

---

**Última actualización**: 2025-11-09 (Domingo)
**Próximo test**: Lunes en horario de mercado
