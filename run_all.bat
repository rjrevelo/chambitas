@echo off
REM ============================================================
REM  TU CHAMBITA — Ejecutor automático (Windows)
REM  Uso: doble clic o desde el Programador de tareas de Windows
REM ============================================================

REM ── 1. Ir al directorio del proyecto ────────────────────────
cd /d "%~dp0"

REM ── 2. Crear carpeta de logs si no existe ───────────────────
if not exist logs mkdir logs

REM ── 3. (Opcional) Activar entorno virtual si existe ─────────
REM  Descomenta la línea siguiente si usas un venv llamado "venv":
REM call venv\Scripts\activate.bat

REM ── 4. Construir nombre del log con fecha actual ─────────────
REM  Formato: logs\run_YYYY-MM-DD.log
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set DT=%%I
set LOGFILE=logs\run_%DT:~0,4%-%DT:~4,2%-%DT:~6,2%.log

REM ── 5. Ejecutar el orquestador y guardar log ─────────────────
echo. >> "%LOGFILE%"
echo ============================================================ >> "%LOGFILE%"
echo Ejecucion: %date% %time% >> "%LOGFILE%"
echo ============================================================ >> "%LOGFILE%"

python run_all.py >> "%LOGFILE%" 2>&1

REM ── 6. Pausa solo si se ejecutó manualmente (doble clic) ─────
REM  Comenta esta línea si lo usas con el Programador de tareas:
REM pause
