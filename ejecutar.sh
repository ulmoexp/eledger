#!/bin/bash
cd "$(dirname "$0")"
# Procesa los extractos que haya en entrada/ y actualiza datos/historico.xlsx.

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
  echo "    esta_carpeta/app/rules_base.json"
  echo
  read -r -p "Pulsa Intro para cerrar..."
  exit 1
fi

# Si existe el entorno propio creado por instalar.command, se usa ese Python.
PY="python3"
[ -x "app/.venv/bin/python" ] && PY="app/.venv/bin/python"

"$PY" app/process.py "$@"
codigo=$?

# 0 = ha ido bien y 2 = error ya explicado: en los dos casos el programa ya
# ha esperado a que se leyera todo (menu final o "Pulsa Intro"), y pausar
# aqui otra vez obligaria a pulsar dos veces. Cualquier otro codigo es que ni
# siquiera ha podido arrancar (Python roto o ausente): aqui si se para.
if [ $codigo -eq 0 ] || [ $codigo -eq 2 ]; then
  exit $codigo
fi
echo
echo "*** Algo ha ido mal. Lee el mensaje de arriba. ***"
echo "Si dice que falta pandas u openpyxl, ejecuta primero el instalar"
echo "(instalar.command en Mac, instalar.sh en Linux)."
echo
read -r -p "Pulsa Intro para cerrar..."
exit $codigo
