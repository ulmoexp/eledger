"""
rutas.py — Dónde vive cada cosa.

POR QUÉ EXISTE
--------------
Hasta ahora todo eran rutas relativas al directorio actual, y funcionaba solo
porque el lanzador hacía `cd` a la carpeta del programa antes de ejecutar. Con
el código dentro de `app/` eso se rompe: `historico.xlsx` acabaría dentro de
`app/` o donde estuviera la consola.

Aquí todo cuelga de RAIZ, que se calcula desde la posición de ESTE fichero. Así
da igual desde dónde se ejecute: `python app/process.py`, doble clic en el
lanzador, o `python C:\\loquesea\\app\\process.py` desde otra unidad.

EL REPARTO DE CARPETAS
----------------------
    entrada/    tú pones aquí los extractos del banco
    salida/     se genera. Borrable sin miedo.
    datos/      historico.xlsx y copias/. INSUSTITUIBLE.
    ajustes/    tu configuración
    app/        la herramienta. Se reemplaza entera al actualizar.

La regla que lo justifica: actualizar = borrar `app/` y `GUIA.pdf` y copiar los
nuevos. Las otras cuatro carpetas no se tocan jamás.
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
import sys
from pathlib import Path

# ¿Estamos dentro del .exe compilado con PyInstaller?
CONGELADO = bool(getattr(sys, "frozen", False))

if CONGELADO:
    # PyInstaller descomprime el programa en una carpeta temporal (_MEIPASS) y
    # deja el .exe donde el usuario lo haya puesto. Son dos sitios distintos y
    # hay que distinguirlos:
    #   RECURSOS -> lo que viene DENTRO del .exe (plantillas, base de reglas)
    #   RAIZ     -> la carpeta del .exe, donde van los datos del usuario
    # Si se confundieran, la configuración se escribiría en una carpeta
    # temporal que Windows borra al cerrar, y cada ejecución empezaría de cero.
    RECURSOS = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    RAIZ = Path(sys.executable).resolve().parent
    APP = RECURSOS
else:
    APP = Path(__file__).resolve().parent
    RECURSOS = APP
    RAIZ = APP.parent

PLANTILLAS = RECURSOS / "plantillas"
VERSION_FICHERO = RECURSOS / "VERSION"

ENTRADA = RAIZ / "entrada"
SALIDA = RAIZ / "salida"
DATOS = RAIZ / "datos"
AJUSTES = RAIZ / "ajustes"
COPIAS = DATOS / "copias"

CARPETAS = [ENTRADA, SALIDA, DATOS, AJUSTES, COPIAS]

# --- ficheros ---
HISTORICO = DATOS / "historico.xlsx"
LIMPIOS = SALIDA / "movimientos_limpios.xlsx"
EXCLUIDOS = SALIDA / "movimientos_excluidos.xlsx"

# Las reglas van en dos capas: las tuyas mandan, la base rellena. La base vive
# en app/ porque se reemplaza entera con cada versión; las tuyas en ajustes/
# porque no se tocan jamás.
REGLAS = AJUSTES / "rules.json"
REGLAS_BASE = RECURSOS / "rules_base.json"
EXCLUSIONES = AJUSTES / "exclude_patterns.json"
CATEGORIAS = AJUSTES / "categorias.json"
SINCRONIZAR = AJUSTES / "sincronizar.json"
MES_CONTABLE = AJUSTES / "mes_contable.json"
CUENTAS = AJUSTES / "cuentas.json"

CONFIGURACION = [REGLAS, EXCLUSIONES, CATEGORIAS, SINCRONIZAR, MES_CONTABLE, CUENTAS]

# Compatibilidad con la forma antigua de trabajar, ahora relativa a RAIZ.
NOMBRE_CUENTA_LEGADO = "movimientos"
CARPETA_TARJETAS_LEGADO = RAIZ / "tarjetas"


def version() -> str:
    """La versión de la herramienta, leída de app/VERSION."""
    try:
        v = VERSION_FICHERO.read_text(encoding="utf-8").strip()
        return v or "0.0.0"
    except OSError:
        return "0.0.0"


def asegurar_carpetas() -> None:
    """Crea las carpetas que falten. Se llama en cada arranque."""
    for c in CARPETAS:
        c.mkdir(parents=True, exist_ok=True)


def resolver(ruta) -> Path:
    """
    Una ruta escrita por el usuario en un JSON, resuelta contra RAIZ.

    Importa para `archivo` de sincronizar.json: quien escriba ahí
    «contabilidad.xlsx» espera que sea el de la carpeta del programa, no el del
    directorio desde el que se haya lanzado la consola.
    """
    p = Path(str(ruta).strip())
    return p if p.is_absolute() else (RAIZ / p)


def relativa(ruta) -> str:
    """Para mensajes por pantalla: 'datos/historico.xlsx' en vez del absolutorio."""
    try:
        return str(Path(ruta).resolve().relative_to(RAIZ))
    except ValueError:
        return str(ruta)


# =====================================================================
# SEMILLA — la configuración que falte se copia de app/plantillas/
# =====================================================================

def sembrar_configuracion() -> list[str]:
    """
    Copia a ajustes/ las plantillas de los ficheros de configuración que no
    existan. Devuelve los nombres copiados, para poder decirlo por pantalla.

    Solo copia lo que FALTA: nunca pisa lo que el usuario ya tenga escrito.
    """
    copiados = []
    for destino in CONFIGURACION:
        if destino.exists():
            continue
        origen = PLANTILLAS / destino.name
        if not origen.exists():
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origen, destino)
        copiados.append(destino.name)
    return copiados


# Antes de que el mes contable fuera configurable, estas dos palabras estaban
# fijas dentro del código. Quien viene de esa versión tiene que conservar el
# mismo comportamiento: si perdiera «mutua», la prestación que cobra el día 1
# se contabilizaría en otro mes y su resumen cambiaría sin avisar de nada.
PALABRAS_MES_HEREDADAS = ["nomina", "mutua"]


def conservar_mes_contable_heredado() -> bool:
    """
    Deja el mes_contable.json recién creado con el comportamiento de antes.

    Solo se llama cuando ya había un histórico, es decir, cuando esto es una
    actualización y no una instalación nueva. En una instalación nueva la
    plantilla genérica (solo «nomina») es la que vale.
    """
    if not MES_CONTABLE.exists():
        return False
    datos = json.loads(MES_CONTABLE.read_text(encoding="utf-8"))
    if datos.get("palabras") == PALABRAS_MES_HEREDADAS:
        return False
    datos["palabras"] = list(PALABRAS_MES_HEREDADAS)
    MES_CONTABLE.write_text(
        json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


# =====================================================================
# MIGRACIÓN — de la carpeta plana antigua a la estructura nueva
# =====================================================================

# Qué había suelto en la raíz y a dónde va ahora.
_LEGADO = [
    ("historico.xlsx", DATOS),
    ("rules.json", AJUSTES),
    ("exclude_patterns.json", AJUSTES),
    ("categorias.json", AJUSTES),
    ("sincronizar.json", AJUSTES),
    ("mes_contable.json", AJUSTES),
    ("movimientos_limpios.xlsx", SALIDA),
    ("movimientos_excluidos.xlsx", SALIDA),
]

# Ficheros del programa que quedan sueltos en la raíz tras actualizar. No se
# tocan (borrar código de alguien sin permiso es pasarse), pero se avisa: si
# quedan ahí y se ejecuta el lanzador viejo, correría la versión antigua.
_CODIGO_VIEJO = ["process.py", "bank_io.py", "reglas.py", "historico.py",
                 "sincronizar.py", "build_guia.py"]


def hay_algo_que_migrar() -> bool:
    if any((RAIZ / n).is_file() for n, _ in _LEGADO):
        return True
    return (RAIZ / "copias").is_dir()


def migrar_desde_raiz() -> list[str]:
    """
    Mueve a su sitio lo que encuentre suelto en la raíz, haciendo antes una
    copia de todo. Devuelve las líneas a mostrar por pantalla.

    Se ejecuta sola, una vez, al arrancar. No hace falta ningún script aparte:
    quien actualiza descomprime encima y ejecuta como siempre.

    Regla de oro: si el destino YA existe, no se pisa nada. Se avisa y se deja
    el fichero viejo donde está, para que sea el usuario quien decida.
    """
    if not hay_algo_que_migrar():
        return []

    asegurar_carpetas()
    sello = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    respaldo = COPIAS / f"antes_de_migrar_{sello}"
    respaldo.mkdir(parents=True, exist_ok=True)

    lineas = ["He reorganizado la carpeta. Esto pasa una sola vez.",
              f"Copia de todo lo anterior en: {relativa(respaldo)}"]
    movidos, conflictos = [], []

    for nombre, destino_dir in _LEGADO:
        origen = RAIZ / nombre
        if not origen.is_file():
            continue
        shutil.copy2(origen, respaldo / nombre)
        destino = destino_dir / nombre
        if destino.exists():
            conflictos.append(nombre)
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(origen), str(destino))
        movidos.append(f"{nombre} -> {relativa(destino)}")

    # la carpeta de copias antigua, si la había
    copias_viejas = RAIZ / "copias"
    if copias_viejas.is_dir() and copias_viejas.resolve() != COPIAS.resolve():
        n = 0
        for f in copias_viejas.iterdir():
            if f.is_file() and not (COPIAS / f.name).exists():
                shutil.move(str(f), str(COPIAS / f.name))
                n += 1
        if n:
            movidos.append(f"{n} copias de seguridad -> {relativa(COPIAS)}")
        try:
            copias_viejas.rmdir()
        except OSError:
            pass

    for m in movidos:
        lineas.append(f"  · {m}")

    if conflictos:
        lineas.append("")
        lineas.append("OJO: estos ya existían en su sitio nuevo, así que NO los he "
                      "tocado.")
        lineas.append("Los de la raíz son los viejos; míralos y bórralos cuando "
                      "estés seguro:")
        for c in conflictos:
            lineas.append(f"  · {c}")

    sueltos = [n for n in _CODIGO_VIEJO if (RAIZ / n).is_file()]
    if sueltos:
        lineas.append("")
        lineas.append("En la raíz queda código de la versión anterior. El que vale "
                      "ahora es el de app/.")
        lineas.append("Puedes borrar estos sin miedo (y el ejecutar.bat viejo, si "
                      "no lo he reemplazado ya):")
        lineas.append("  · " + ", ".join(sueltos))

    return lineas
