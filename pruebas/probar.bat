@echo off
REM Comprueba que la herramienta sigue funcionando. No toca tus datos:
REM cada prueba se hace en una carpeta temporal aparte.
chcp 65001 >nul
cd /d "%~dp0"
python probar.py %*
if errorlevel 1 (
  echo.
  echo *** Hay comprobaciones que FALLAN. No repartas esta version. ***
)
echo.
pause
