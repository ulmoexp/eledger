@echo off
REM Procesa los extractos que haya en entrada\ y actualiza datos\historico.xlsx.
chcp 65001 >nul
cd /d "%~dp0"

REM Si existe el entorno propio creado por instalar.bat, se usa ese Python.
REM Asi la herramienta no depende de lo que haya instalado en el sistema.
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

"%PY%" app\process.py %*
set "CODIGO=%errorlevel%"

REM 0 = ha ido bien y 2 = error ya explicado: en los dos casos el programa ya
REM ha esperado a que se leyera todo (menu final o "Pulsa Intro"), y pausar
REM aqui otra vez obligaria a pulsar dos veces. Cualquier otro codigo es que
REM ni siquiera ha podido arrancar (Python roto o ausente): aqui si se para.
if "%CODIGO%"=="0" exit /b 0
if "%CODIGO%"=="2" exit /b 2
echo.
echo *** Algo ha ido mal. Lee el mensaje de arriba. ***
echo Si dice que falta pandas o openpyxl, ejecuta primero  instalar.bat
echo.
pause
exit /b %CODIGO%
