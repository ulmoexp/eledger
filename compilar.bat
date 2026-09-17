@echo off
REM Genera dist\Movimientos.exe con PyInstaller.
REM TIENE QUE EJECUTARSE EN WINDOWS: un .exe solo se puede compilar en Windows.
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

if not exist "app\.venv\Scripts\python.exe" (
  echo.
  echo *** Falta el entorno. Ejecuta primero  instalar.bat  ***
  echo.
  pause
  exit /b 1
)
set "PY=app\.venv\Scripts\python.exe"

echo Comprobando que las pruebas pasan antes de compilar...
"%PY%" pruebas\probar.py
if errorlevel 1 (
  echo.
  echo *** Hay pruebas que fallan. NO compilo. ***
  echo Arregla eso antes de generar un ejecutable para repartir.
  echo.
  pause
  exit /b 1
)

echo.
echo Instalando PyInstaller si hace falta...
"%PY%" -m pip install --upgrade pyinstaller --quiet
if errorlevel 1 goto error

echo.
echo Compilando. Esto tarda varios minutos.
"%PY%" -m PyInstaller movimientos.spec --clean --noconfirm
if errorlevel 1 goto error

if not exist "dist\Movimientos.exe" goto error

echo.
echo ============================================================
echo  Listo:  dist\Movimientos.exe
echo.
echo  Para repartirlo, crea una carpeta con:
echo     Movimientos.exe    (de dist\)
echo     LEEME.txt
echo     GUIA.pdf
echo     CHANGELOG.md
echo  y comprimela. El resto se crea solo al ejecutarlo.
echo.
echo  LEE COMPILAR.md antes de darselo a nadie: hay un par de cosas
echo  que conviene avisar sobre los antivirus.
echo ============================================================
echo.
pause
exit /b 0

:error
echo.
echo *** La compilacion ha fallado. Lee el mensaje de arriba. ***
echo.
pause
exit /b 1
