@echo off
REM Genera un ZIP para dar a otra persona, SIN tus datos personales.
chcp 65001 >nul
cd /d "%~dp0"

REM ---------------------------------------------------------------
REM Comprobar que la carpeta esta completa ANTES de nada.
REM Sin esto, "python -m venv app\.venv" crea la carpeta app\ el solo
REM y el error que sale despues no dice nada util.
REM ---------------------------------------------------------------
if not exist "app\process.py" (
  echo.
  echo *** Falta la carpeta app\ con el programa. ***
  echo.
  echo Esta carpeta esta incompleta. Lo mas habitual es haber descargado
  echo los ficheros de uno en uno: asi se pierden las carpetas y todo
  echo queda plano.
  echo.
  if exist "process.py" (
    echo He visto process.py suelto aqui, asi que es justo eso lo que ha pasado.
    echo.
  )
  echo Que hacer:
  echo   1. Borra la carpeta  app  si existe ^(solo tendra un .venv vacio^).
  echo   2. Descomprime el ZIP completo, que ya trae las carpetas hechas.
  echo   3. Ejecuta instalar.bat desde la carpeta que sale del ZIP.
  echo.
  echo Tiene que quedar asi:
  echo     esta_carpeta\instalar.bat
  echo     esta_carpeta\app\process.py
  echo     esta_carpeta\ajustes\rules.json
  echo.
  pause
  exit /b 1
)

set "PY=python"
if exist "app\.venv\Scripts\python.exe" set "PY=app\.venv\Scripts\python.exe"

"%PY%" app\exportar.py %*
if errorlevel 1 (
  echo.
  echo *** No se ha creado el ZIP. Lee el mensaje de arriba. ***
)
echo.
pause
