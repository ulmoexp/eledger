"""
exportar.py — Genera un ZIP para dar a otra persona, SIN tus datos.

POR QUÉ EXISTE
--------------
Si comprimes la carpeta tal cual, repartes tu vida entera. Y no es solo el
histórico: `ajustes/rules.json` es un retrato bastante fino de una persona
—el colegio de los hijos, el veterinario, el gimnasio, el casero, la mutua— y
`exclude_patterns.json` suele llevar los dígitos de la tarjeta.

Así que esto no funciona por lista de exclusiones, sino al revés: **parte de
cero y copia solo lo que está autorizado**. Un fichero nuevo que aparezca en la
carpeta el día de mañana no se cuela por olvido; simplemente no entra.

Lo que se lleva:
    app/            el programa, con la base de reglas y las plantillas
    ejecutar.*      los lanzadores
    LEEME.txt       instrucciones
    GUIA.pdf        la guía
    CHANGELOG.md    qué cambió en cada versión
    LICENSE         la licencia (MIT)
    pruebas/        opcional (--con-pruebas)

Lo que NO se lleva, en ningún caso:
    entrada/  salida/  datos/  ajustes/

Quien lo reciba, al ejecutar por primera vez, se creará su propia configuración
a partir de las plantillas.

    python app/exportar.py                 genera el ZIP
    python app/exportar.py --con-pruebas   incluye también pruebas/
"""

from __future__ import annotations

import datetime as dt
import sys
import zipfile
from pathlib import Path

import rutas

# Lista BLANCA. Solo esto sale de la carpeta.
CARPETAS_PERMITIDAS = ["app"]
CARPETAS_OPCIONALES = {"--con-pruebas": "pruebas"}
FICHEROS_PERMITIDOS = ["ejecutar.bat", "ejecutar.command", "ejecutar.sh",
                       "exportar.bat", "exportar.command", "exportar.sh",
                       "instalar.bat", "instalar.command", "instalar.sh",
                       "compilar.bat", "eledger.spec", "requisitos.txt",
                       "LEEME.txt", "GUIA.pdf", "CHANGELOG.md", "COMPILAR.md",
                       "TRASPASO.md", "LICENSE"]

# Cuando esto corre dentro del .exe no hay carpeta app/ que copiar: el programa
# ES el ejecutable. Se reparte él y las cuatro cosas que lo acompañan.
FICHEROS_EXE = ["LEEME.txt", "GUIA.pdf", "CHANGELOG.md"]

# Dentro de app/ tampoco vale todo: los .pyc y las cachés no pintan nada.
EXTENSIONES_FUERA = {".pyc", ".pyo", ".log", ".tmp"}
NOMBRES_FUERA = {"__pycache__", ".venv", ".git", ".DS_Store", "Thumbs.db",
                 "build", "dist"}

# Estas nunca, pase lo que pase. Es un segundo cerrojo por si alguien añade
# algo a la lista blanca sin pensarlo.
CARPETAS_PROHIBIDAS = {"entrada", "salida", "datos", "ajustes", "copias",
                       "tarjetas"}

# Mac y Linux arrancan estos por doble clic ejecutándolos de verdad (a
# diferencia de .bat, que Windows abre por asociación de tipo de fichero), así
# que necesitan el bit de ejecución. Si quien genera el ZIP lo hace desde
# Windows, el sistema de ficheros de origen no tiene ese concepto y
# zipfile.write() no lo pondría solo: se fuerza aquí a mano para que el ZIP
# sea correcto pase lo que pase en la máquina donde se generó.
LANZADORES_EJECUTABLES = {"instalar.sh", "ejecutar.sh", "exportar.sh",
                          "instalar.command", "ejecutar.command",
                          "exportar.command"}

# Y los saltos de línea, por el mismo motivo: dependen de dónde se genere el
# ZIP. .gitattributes los deja bien al descargar el repositorio, pero una
# copia de trabajo que no se ha vuelto a descargar puede tenerlos mal (ya
# pasó: los .bat del primer ZIP iban con los de Linux). Un .bat solo con LF
# puede fallar en cmd de formas raras, y un .sh con CRLF no arranca en bash
# (lee el \r como parte del comando). Se fuerzan aquí, pase lo que pase.
SALTO_WINDOWS, SALTO_UNIX = b"\r\n", b"\n"


def _con_saltos(datos: bytes, salto: bytes) -> bytes:
    return datos.replace(b"\r\n", b"\n").replace(b"\n", salto)


def _admisible(ruta: Path) -> bool:
    partes = set(ruta.parts)
    if partes & NOMBRES_FUERA or partes & CARPETAS_PROHIBIDAS:
        return False
    if ruta.suffix.lower() in EXTENSIONES_FUERA:
        return False
    return True


def _recoger(con_pruebas: bool):
    """Devuelve la lista de (ruta_absoluta, ruta_dentro_del_zip)."""
    if rutas.CONGELADO:
        ejecutable = Path(sys.executable)
        piezas = [(ejecutable, Path(ejecutable.name))]
        for nombre in FICHEROS_EXE:
            f = rutas.RAIZ / nombre
            if f.is_file():
                piezas.append((f, Path(nombre)))
        return piezas

    carpetas = list(CARPETAS_PERMITIDAS)
    if con_pruebas:
        carpetas.append("pruebas")

    piezas = []
    for nombre in carpetas:
        base = rutas.RAIZ / nombre
        if not base.is_dir():
            continue
        for f in sorted(base.rglob("*")):
            if not f.is_file():
                continue
            relativa = f.relative_to(rutas.RAIZ)
            if _admisible(relativa):
                piezas.append((f, relativa))

    for nombre in FICHEROS_PERMITIDOS:
        f = rutas.RAIZ / nombre
        if f.is_file():
            piezas.append((f, Path(nombre)))
    return piezas


def _revisar(piezas) -> list[str]:
    """
    Última comprobación antes de escribir: que no se haya colado nada.

    Sirve de poco confiar en que la lista blanca esté bien si nadie la mira.
    Esto vuelve a pasar por encima de lo ya recogido, con otro criterio.
    """
    problemas = []
    for origen, destino in piezas:
        raiz = destino.parts[0]
        if raiz in CARPETAS_PROHIBIDAS:
            problemas.append(str(destino))
        elif destino.suffix.lower() in (".xlsx", ".xls", ".xlsm", ".csv") \
                and destino.parts[0] != "pruebas":
            problemas.append(f"{destino} (parece un fichero de datos)")
    return problemas


def exportar(con_pruebas=False) -> Path:
    version = rutas.version()
    sello = dt.datetime.now().strftime("%Y%m%d")
    destino = rutas.RAIZ / f"eledger_v{version}_{sello}.zip"

    piezas = _recoger(con_pruebas)
    if not piezas:
        raise RuntimeError("No he encontrado nada que exportar. ¿Está app/ en su "
                           "sitio?")

    problemas = _revisar(piezas)
    if problemas:
        raise RuntimeError(
            "Se ha colado algo que no debería salir de aquí:\n   · "
            + "\n   · ".join(problemas)
            + "\n   No he creado el ZIP. Revisa exportar.py antes de repartir nada.")

    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for origen, relativa in piezas:
            arcname = str(relativa).replace("\\", "/")
            es_bat = relativa.suffix.lower() == ".bat"
            if relativa.name in LANZADORES_EJECUTABLES or es_bat:
                info = zipfile.ZipInfo.from_file(origen, arcname)
                info.compress_type = zipfile.ZIP_DEFLATED
                with open(origen, "rb") as f:
                    datos = f.read()
                if es_bat:
                    datos = _con_saltos(datos, SALTO_WINDOWS)
                else:
                    info.external_attr = (0o755 & 0xFFFF) << 16
                    datos = _con_saltos(datos, SALTO_UNIX)
                z.writestr(info, datos)
            else:
                z.write(origen, arcname)

    return destino


def main():
    con_pruebas = "--con-pruebas" in sys.argv
    print(f"Exportando la versión {rutas.version()}...\n")

    destino = exportar(con_pruebas)
    with zipfile.ZipFile(destino) as z:
        nombres = z.namelist()

    print(f"✅ {destino.name}")
    print(f"   {len(nombres)} ficheros · {destino.stat().st_size / 1024:.0f} KB")
    print(f"   en {rutas.RAIZ}\n")
    if rutas.CONGELADO:
        print("Lleva el ejecutable, la guía y el changelog.")
    else:
        print("Lleva el programa, la guía y unas reglas de partida genéricas.")
    print("NO lleva tu histórico, ni tus copias, ni tus reglas, ni lo que tengas")
    print("en entrada/ o salida/. Quien lo reciba se creará su configuración al")
    print("ejecutarlo por primera vez.\n")
    if not con_pruebas:
        print("Con  --con-pruebas  se incluye también la carpeta pruebas/.")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        main()
    except Exception as e:
        print(f"\n❌ {e}")
        sys.exit(1)
