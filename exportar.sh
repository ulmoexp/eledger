#!/bin/bash
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

# Si existe el entorno propio creado por instalar.command, se usa ese Python.
PY="python3"
[ -x "app/.venv/bin/python" ] && PY="app/.venv/bin/python"

"$PY" app/exportar.py "$@"
codigo=$?
if [ $codigo -ne 0 ]; then
  echo
  echo "*** Algo ha ido mal. Lee el mensaje de arriba. ***"
fi
echo
read -r -p "Pulsa Intro para cerrar..."
exit $codigo
