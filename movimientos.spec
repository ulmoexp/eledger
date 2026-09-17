# -*- mode: python ; coding: utf-8 -*-
"""
movimientos.spec — Receta para compilar el .exe con PyInstaller.

    compilar.bat        (o: pyinstaller movimientos.spec --clean)

QUÉ GENERA
----------
Un único `dist/Movimientos.exe`. Los datos NO van dentro: el .exe crea
`entrada/`, `salida/`, `datos/` y `ajustes/` en la carpeta donde esté puesto, y
esos JSON se pueden abrir y editar con el bloc de notas como siempre. Era la
decisión pendiente en el traspaso, y va por aquí porque un .exe que se lo traga
todo deja al usuario sin poder tocar sus propias reglas.

Lo que sí viaja dentro del .exe es lo que pertenece al programa: la base de
reglas, las plantillas de configuración y el fichero VERSION. Se descomprimen en
una carpeta temporal al arrancar, y `rutas.py` sabe distinguir esa carpeta
(RECURSOS) de la del usuario (RAIZ).

DÓNDE SE PONE EL .exe
---------------------
En una carpeta suya, junto al LEEME y la GUIA. Al ejecutarlo por primera vez se
creará el resto. Para actualizar, se reemplaza el .exe y ya.
"""

from pathlib import Path

RAIZ = Path(SPECPATH)
APP = RAIZ / "app"

# Lo que va empaquetado dentro. Destino "." = la raíz de la carpeta temporal,
# que es donde rutas.py busca RECURSOS.
datos = [
    (str(APP / "rules_base.json"), "."),
    (str(APP / "VERSION"), "."),
    (str(APP / "plantillas"), "plantillas"),
]

a = Analysis(
    [str(APP / "process.py")],
    pathex=[str(APP)],
    binaries=[],
    datas=datos,
    # xlrd solo hace falta para los .xls BIFF de verdad. Si está instalado en el
    # entorno al compilar, entra; si no, PyInstaller lo omite sin quejarse y el
    # programa avisa por pantalla cuando se topa con uno.
    hiddenimports=["xlrd", "openpyxl.cell._writer"],
    hookspath=[],
    runtime_hooks=[],
    # Fuera lo que solo abulta: pandas arrastra matplotlib y compañía si los
    # encuentra, y aquí no se dibuja nada.
    excludes=["matplotlib", "tkinter", "scipy", "IPython", "notebook",
              "PyQt5", "PySide2", "sphinx", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Movimientos",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX dispara todavía más falsos positivos de antivirus
    runtime_tmpdir=None,
    console=True,       # hace falta: toda la información sale por pantalla
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
