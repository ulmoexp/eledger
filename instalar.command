#!/bin/bash
# Prepara la herramienta: crea un entorno propio en app/.venv e instala ahi las
# librerias, sin tocar el Python del sistema.
cd "$(dirname "$0")"

# Comprobar que la carpeta esta completa ANTES de nada: "python -m venv
# app/.venv" crearia la carpeta app/ el solo y el error posterior no diria nada.
if [ ! -f "app/process.py" ]; then
  echo
  echo "*** Falta la carpeta app/ con el programa. ***"
  echo
  echo "Esta carpeta esta incompleta. Lo mas habitual es haber descargado los"
  echo "ficheros de uno en uno: asi se pierden las carpetas y todo queda plano."
  [ -f "process.py" ] && echo && echo "He visto process.py suelto aqui, asi que es justo eso lo que ha pasado."
  echo
  echo "Descomprime el ZIP completo, que ya trae las carpetas hechas, y ejecuta"
  echo "esto desde la carpeta que sale del ZIP. Tiene que quedar asi:"
  echo "    esta_carpeta/app/process.py"
  echo "    esta_carpeta/ajustes/rules.json"
  echo
  read -r -p "Pulsa Intro para cerrar..."
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "*** No encuentro Python 3. Instalalo desde https://www.python.org/downloads/"
  read -r -p "Pulsa Intro para cerrar..."
  exit 1
fi
python3 --version

echo
echo "Creando el entorno en app/.venv ..."
python3 -m venv "app/.venv" || { echo "Ha fallado la creacion del entorno."; read -r -p "Intro..."; exit 1; }

echo
echo "Instalando librerias. Esto tarda un par de minutos la primera vez."
"app/.venv/bin/python" -m pip install --upgrade pip --quiet
"app/.venv/bin/python" -m pip install -r requisitos.txt || { echo "Ha fallado la instalacion."; read -r -p "Intro..."; exit 1; }

echo
echo "============================================================"
echo " Listo. Ya puedes usar  ejecutar.command"
echo "============================================================"
echo
read -r -p "Pulsa Intro para cerrar..."
