@echo off
REM ============================================================
REM Script para copiar AASender.cs a carpeta de NinjaTrader 8
REM ============================================================

echo.
echo ============================================================
echo Copiando AASender.cs a NinjaTrader 8 Indicators
echo ============================================================
echo.

REM Ruta origen
set SOURCE=%~dp0ninja\AASender.cs

REM Ruta destino (NinjaTrader 8 Indicators)
set DEST=%USERPROFILE%\Documents\NinjaTrader 8\bin\Custom\Indicators\AASender.cs

REM Verificar que existe el archivo origen
if not exist "%SOURCE%" (
    echo [ERROR] No se encontro el archivo origen: %SOURCE%
    pause
    exit /b 1
)

REM Verificar que existe la carpeta destino
if not exist "%USERPROFILE%\Documents\NinjaTrader 8\bin\Custom\Indicators\" (
    echo [ERROR] No se encontro la carpeta de NinjaTrader 8 Indicators
    echo Ruta esperada: %USERPROFILE%\Documents\NinjaTrader 8\bin\Custom\Indicators\
    pause
    exit /b 1
)

REM Hacer backup si ya existe
if exist "%DEST%" (
    echo [INFO] Archivo existente encontrado, creando backup...
    set BACKUP=%DEST%.backup_%date:~-4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%%time:~6,2%
    set BACKUP=%BACKUP: =0%
    copy "%DEST%" "!BACKUP!" > nul
    echo [OK] Backup creado: !BACKUP!
)

REM Copiar archivo
echo [INFO] Copiando archivo...
copy /Y "%SOURCE%" "%DEST%"

if %ERRORLEVEL% equ 0 (
    echo.
    echo [OK] AASender.cs copiado exitosamente!
    echo.
    echo Destino: %DEST%
    echo.
    echo ============================================================
    echo IMPORTANTE: Debes recompilar en NinjaTrader
    echo ============================================================
    echo 1. Abre NinjaTrader 8
    echo 2. Ve a: Tools ^> NinjaScript ^> Edit NinjaScript ^> Indicator
    echo 3. Busca AASender.cs en la lista
    echo 4. Presiona F5 para compilar
    echo 5. Si hay errores, revisa la ventana "Compile"
    echo ============================================================
    echo.
) else (
    echo [ERROR] Fallo al copiar el archivo
    pause
    exit /b 1
)

pause
