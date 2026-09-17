#!/bin/bash
# Comprueba que la herramienta sigue funcionando. No toca tus datos.
cd "$(dirname "$0")"
python3 probar.py "$@"
codigo=$?
if [ $codigo -ne 0 ]; then
  echo
  echo "*** Hay comprobaciones que FALLAN. No repartas esta version. ***"
fi
echo
read -r -p "Pulsa Intro para cerrar..."
exit $codigo
