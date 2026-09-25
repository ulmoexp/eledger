@echo off
REM Prepara la herramienta la primera vez: crea un entorno propio en app\.venv
REM e instala ahi las librerias, sin tocar el Python del sistema.
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
  echo     esta_carpeta\app\rules_base.json
  echo.
  pause
  exit /b 1
)

echo Buscando Python...
python --version >nul 2>&1
if errorlevel 1 (
  echo.
  echo *** No encuentro Python. ***
  echo.
  echo Instalalo desde https://www.python.org/downloads/
  echo IMPORTANTE: marca la casilla "Add Python to PATH" durante la instalacion.
  echo Luego cierra esta ventana y vuelve a ejecutar instalar.bat.
  echo.
  pause
  exit /b 1
)
python --version

echo.
echo Creando el entorno en app\.venv ...
python -m venv "app\.venv"
if errorlevel 1 goto error

echo.
echo Instalando librerias. Esto tarda un par de minutos la primera vez.
"app\.venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
"app\.venv\Scripts\python.exe" -m pip install -r requisitos.txt
if errorlevel 1 goto error

echo.
echo Comprobando que todo arranca...
"app\.venv\Scripts\python.exe" -c "import pandas, openpyxl; print('   pandas', pandas.__version__, '- openpyxl', openpyxl.__version__)"
if errorlevel 1 goto error

echo.
echo ============================================================
echo  Listo. Ya puedes usar  ejecutar.bat
echo.
echo  1. Deja los extractos del banco en la carpeta  entrada\
echo  2. Doble clic en  ejecutar.bat
echo  3. Abre  datos\historico.xlsx
echo ============================================================
echo.
pause
exit /b 0

:error
echo.
echo *** Algo ha fallado. Lee el mensaje de arriba. ***
echo Si el problema persiste, borra la carpeta app\.venv y vuelve a intentarlo.
echo.
pause
exit /b 1
