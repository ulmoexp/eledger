"""
probar.py — Comprueba que la herramienta sigue haciendo lo que debe.

CÓMO FUNCIONA (y por qué así)
-----------------------------
Las pruebas son de CAJA NEGRA: para cada caso se prepara una carpeta temporal
con una copia del programa y de la configuración, se sueltan ahí los ficheros
de banco falsos, se ejecuta `python process.py` como un proceso aparte y se
comprueba el `historico.xlsx` que sale.

No se importa ningún módulo de la herramienta. Eso tiene tres ventajas que
importan para lo que viene después:

  1. No hace falta tocar `process.py` para poder probarlo. Hoy carga la
     configuración al importarse, así que unas pruebas que hicieran
     `import process` obligarían a refactorizarlo ANTES de tener la red de
     seguridad, que es justo el orden que queremos evitar.
  2. Sobreviven a la reestructuración de carpetas: cuando el código se mueva a
     `app/`, basta cambiar las constantes RUTAS_APP / RUTAS_CONFIG de abajo.
  3. Sobreviven al cambio de la API de `Clasificador.clasificar()`: comprueban
     resultados, no funciones internas.

Uso:
    python probar.py              todos los casos
    python probar.py dedup mes    solo los casos cuyo nombre contenga eso
    python probar.py -v           deja las carpetas temporales para mirarlas
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fixtures as fx  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
AQUI = Path(__file__).resolve().parent

# --- Estructura de carpetas -------------------------------------------
# Si vuelve a cambiar el reparto de carpetas, esto es lo único que hay que
# tocar de todo el fichero.
DIR_APP = "app"
DIR_AJUSTES = "ajustes"
DIR_DATOS = "datos"
DIR_SALIDA = "salida"
DIR_ENTRADA = "entrada"
DIR_PLANTILLAS = "app/plantillas"

MODULOS = ["process.py", "bank_io.py", "reglas.py", "historico.py",
           "sincronizar.py", "rutas.py"]
# La capa base de reglas viaja dentro de app/, no en ajustes/.
APP_DATOS = ["rules_base.json", "VERSION"]
CONFIG = ["rules.json", "exclude_patterns.json", "categorias.json",
          "sincronizar.json", "mes_contable.json", "cuentas.json"]

LANZADOR = "app/process.py"

# La exclusión que usan los casos de prueba. Inventada: en la vida real aquí va
# el recibo con que tu cuenta paga la tarjeta, con los dígitos de la tuya.
PATRONES_EXCLUSION = ["liquidacion tarjeta"]

CONSERVAR = "-v" in sys.argv or "--conservar" in sys.argv
FILTROS = [a for a in sys.argv[1:] if not a.startswith("-")]

_resultados = []
_casos = []


# =====================================================================
# ANDAMIAJE
# =====================================================================

def caso(nombre, descripcion):
    """Registra una función como caso de prueba."""
    def envoltorio(fn):
        _casos.append((nombre, descripcion, fn))
        return fn
    return envoltorio


class Entorno:
    """Una carpeta temporal con el programa, su configuración y su entrada."""

    def __init__(self, nombre, plano=False):
        """
        plano=True monta la carpeta a la ANTIGUA (todo suelto en la raíz),
        para poder probar que la migración automática la recoloca bien.
        """
        self.nombre = nombre
        self.dir = Path(tempfile.mkdtemp(prefix=f"prueba_{nombre}_"))

        (self.dir / DIR_APP).mkdir(parents=True)
        (self.dir / DIR_PLANTILLAS).mkdir(parents=True)
        for f in MODULOS + APP_DATOS:
            shutil.copy2(RAIZ / DIR_APP / f, self.dir / DIR_APP / f)
        for f in CONFIG:
            shutil.copy2(RAIZ / DIR_PLANTILLAS / f, self.dir / DIR_PLANTILLAS / f)

        # La configuración de partida sale de las PLANTILLAS, no de ajustes/.
        # Dos razones: las pruebas dan el mismo resultado en cualquier máquina,
        # sin depender de las reglas que cada cual tenga escritas; y este
        # fichero se reparte con el programa, así que no puede llevar datos de
        # nadie. Lo que se necesite para un caso concreto, se escribe en él.
        destino = self.dir if plano else (self.dir / DIR_AJUSTES)
        destino.mkdir(parents=True, exist_ok=True)
        for f in CONFIG:
            origen = RAIZ / DIR_PLANTILLAS / f
            if origen.exists():
                shutil.copy2(origen, destino / f)
        (destino / "exclude_patterns.json").write_text(
            json.dumps(PATRONES_EXCLUSION, ensure_ascii=False, indent=2),
            encoding="utf-8")

        self.entrada = self.dir / DIR_ENTRADA
        self.entrada.mkdir()
        self.salidas = []

    # --- dónde queda cada cosa ---
    @property
    def ajustes(self):
        return self.dir / DIR_AJUSTES

    @property
    def datos(self):
        return self.dir / DIR_DATOS

    @property
    def salida(self):
        return self.dir / DIR_SALIDA

    # --- configuración ---
    def leer_config(self, nombre):
        return json.loads((self.ajustes / nombre).read_text(encoding="utf-8"))

    def escribir_config(self, nombre, datos):
        self.ajustes.mkdir(parents=True, exist_ok=True)
        (self.ajustes / nombre).write_text(
            json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")

    def regla_al_principio(self, clave, categoria):
        """Inserta una regla la primera, que es la que gana. Si la clave ya
        existía, la de arriba manda (un dict conserva la posición de la clave
        pero se quedaría con el último valor, así que hay que descartarla)."""
        datos = self.leer_config("rules.json")
        nuevo = {"_sintaxis": datos.get("_sintaxis", ""), clave: categoria}
        nuevo.update({k: v for k, v in datos.items()
                      if k not in ("_sintaxis", clave)})
        self.escribir_config("rules.json", nuevo)

    def preparar_exportacion(self):
        """Copia lo que exportar.py espera encontrar en la raíz."""
        shutil.copy2(RAIZ / DIR_APP / "exportar.py",
                     self.dir / DIR_APP / "exportar.py")
        for f in ("LEEME.txt", "CHANGELOG.md", "GUIA.pdf", "LICENSE",
                  "ejecutar.bat", "ejecutar.command", "ejecutar.sh",
                  "exportar.bat", "exportar.command", "exportar.sh"):
            origen = RAIZ / f
            if origen.exists():
                shutil.copy2(origen, self.dir / f)

    def exportar(self, *args):
        proc = subprocess.run(
            [sys.executable, os.path.join(DIR_APP, "exportar.py"), *args],
            cwd=self.dir, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=180)
        self.ultimo_codigo = proc.returncode
        return (proc.stdout or "") + (proc.stderr or "")

    def instalar_stub_xlrd(self):
        """Copia el stub como 'xlrd.py' para que `import xlrd` lo encuentre."""
        shutil.copy2(AQUI / "xlrd_stub.py", self.dir / DIR_APP / "xlrd.py")

    # --- ejecución ---
    def ejecutar(self, desde=None):
        """`desde` permite lanzarlo con el directorio actual en otro sitio, que
        es justo lo que rutas.py tiene que hacer irrelevante."""
        objetivo = (str(self.dir / LANZADOR) if desde
                    else LANZADOR.replace("/", os.sep))
        proc = subprocess.run(
            [sys.executable, objetivo], cwd=(desde or self.dir),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=180)
        salida = (proc.stdout or "") + (proc.stderr or "")
        self.salidas.append(salida)
        self.ultimo_codigo = proc.returncode
        return salida

    def vaciar_entrada(self):
        for f in self.entrada.iterdir():
            f.unlink()

    # --- lectura de resultados ---
    @property
    def ruta_historico(self):
        return self.datos / "historico.xlsx"

    def historico(self):
        import pandas as pd
        return pd.read_excel(self.ruta_historico, sheet_name="MOVIMIENTOS")

    def resumen(self):
        import pandas as pd
        return pd.read_excel(self.ruta_historico, sheet_name="RESUMEN")

    def libro_historico(self):
        from openpyxl import load_workbook
        return load_workbook(self.ruta_historico)

    def limpiar(self):
        if not CONSERVAR:
            shutil.rmtree(self.dir, ignore_errors=True)


def comprobar(condicion, titulo, detalle=""):
    _resultados.append((bool(condicion), titulo, "" if condicion else detalle))


def categoria_de(df, texto):
    """Categoría del (único) movimiento cuya descripción contiene `texto`."""
    filas = df[df["descripcion"].str.contains(texto, case=False, na=False)]
    if len(filas) != 1:
        return f"<{len(filas)} coincidencias para «{texto}»>"
    return filas.iloc[0]["categoria"]


def campo_de(df, texto, columna):
    filas = df[df["descripcion"].str.contains(texto, case=False, na=False)]
    if len(filas) != 1:
        return f"<{len(filas)} coincidencias para «{texto}»>"
    return filas.iloc[0][columna]


# =====================================================================
# DATOS DE PRUEBA
# =====================================================================

# Abril completo. Los importes son redondos para poder cuadrar a mano:
#   Comida     150   (mercadona 100 + dia 50)
#   Otros      560   (media markt 200 + guardia civil 30 + navidad 20
#                     + barcelona 300 + abp 10)
#   Piso        40   (seguro de VIDA)
#   Transporte  60   (repsol)
#   ------------------------------------------------
#   Total Gastos 810 · Ingresos 2000 · Balance +1190
#
# Y una línea excluida de 500 que NO debe entrar en ningún total.
ABRIL = [
    ("05/04/2026", "NOMINA EMPRESA FICTICIA SL", 2000.00),
    ("07/04/2026", "COMPRA MERCADONA MADRID", -100.00),
    ("09/04/2026", "MEDIA MARKT ONLINE", -200.00),
    ("11/04/2026", "SUPERMERCADOS DIA MADRID", -50.00),
    ("13/04/2026", "GUARDIA CIVIL MULTA", -30.00),
    ("15/04/2026", "CESTA DE NAVIDAD", -20.00),
    ("17/04/2026", "BARCELONA HOTEL", -300.00),
    ("19/04/2026", "ABP CONSULTING", -10.00),
    ("21/04/2026", "SEGURO DE VIDA MAPFRE", -40.00),
    ("23/04/2026", "LIQUIDACION TARJETA CREDITO", -500.00),
    ("25/04/2026", "REPSOL E.S. LAS ROZAS", -60.00),
]

TOTAL_GASTOS_ABRIL = 810.00
INGRESOS_ABRIL = 2000.00


# =====================================================================
# CASOS
# =====================================================================

@caso("formatos", "Los cuatro formatos que la banca llama .xls")
def prueba_formatos(e):
    # Ojo: un movimiento por formato, pero con la descripción CAMBIADA en cada
    # uno. Si los cuatro fueran idénticos, la deduplicación los tomaría por el
    # mismo movimiento descargado cuatro veces (que es su trabajo) y aquí
    # parecería que el lector ha fallado.
    fx.escribir_html(e.entrada / "cuenta_html.xls",
                     [("07/04/2026", "COMPRA MERCADONA MADRID", -10.00)])
    fx.escribir_xml_ss(e.entrada / "tarjeta_xml.xls",
                       [("07/04/2026", "COMPRA CARREFOUR MADRID", -10.00)])
    fx.escribir_csv(e.entrada / "cuenta_csv.xls",
                    [("07/04/2026", "COMPRA LIDL MADRID", -10.00)])
    fx.escribir_xlsx(e.entrada / "cuenta_xlsx.xls",
                     [("07/04/2026", "COMPRA AHORRAMAS MADRID", -10.00)])

    salida = e.ejecutar()
    for fmt in ("formato=html", "formato=xml_ss", "formato=texto", "formato=xlsx"):
        comprobar(fmt in salida, f"se detecta {fmt}", salida)

    df = e.historico()
    comprobar(len(df) == 4, "4 movimientos leídos (uno por formato)",
              f"leídos {len(df)}")
    comprobar(set(df["categoria"]) == {"Comida"},
              "los cuatro se clasifican igual", str(set(df['categoria'])))
    comprobar(abs(df["importe"].sum() + 40.00) < 0.005,
              "los importes en formato español se leen bien",
              f"suma {df['importe'].sum()}")


@caso("tipo", "Cuenta y tarjeta se distinguen por el contenido")
def prueba_tipo(e):
    uno = [("07/04/2026", "COMPRA MERCADONA MADRID", -10.00)]
    fx.escribir_html(e.entrada / "a.xls", uno, cabecera_saldo=True)
    fx.escribir_xml_ss(e.entrada / "b.xls", uno, tarjeta=True)
    e.ejecutar()

    df = e.historico()
    comprobar(set(df["tipo"]) == {"cuenta", "tarjeta"},
              "una cuenta y una tarjeta", str(set(df["tipo"])))


@caso("biff", "La ruta .xls BIFF, con el stub de xlrd")
def prueba_biff(e):
    fx.escribir_biff_falso(e.entrada / "extracto_banco.xls")
    e.instalar_stub_xlrd()
    salida = e.ejecutar()

    comprobar("formato=xls_biff" in salida, "se detecta el contenedor OLE2", salida)
    df = e.historico()
    comprobar(len(df) == 8, "8 movimientos del stub", f"leídos {len(df)}")
    comprobar(categoria_de(df, "NOMINA") == "Ingresos",
              "las fechas serial de xlrd se traducen y clasifica bien",
              str(categoria_de(df, "NOMINA")))


@caso("trampas", "Las trampas de la coincidencia por subcadena")
def prueba_trampas(e):
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL)
    e.ejecutar()
    df = e.historico()

    esperado = {
        "MEDIA MARKT": "Otros",        # contiene 'dia'  -> NO es Comida
        "GUARDIA CIVIL": "Otros",      # contiene 'dia'
        "NAVIDAD": "Otros",            # contiene 'vida' -> NO es Piso
        "BARCELONA": "Otros",          # contiene 'bar'  -> NO es Ocio
        "ABP CONSULTING": "Otros",     # contiene 'bp'   -> NO es Transporte
        "SUPERMERCADOS DIA": "Comida",  # '=dia' sí debe casar
        "SEGURO DE VIDA": "Piso",      # '=vida' sí debe casar
        "MERCADONA": "Comida",
        "REPSOL": "Transporte",
        "NOMINA": "Ingresos",
    }
    for texto, cat in esperado.items():
        real = categoria_de(df, texto)
        comprobar(real == cat, f"«{texto}» -> {cat}", f"salió {real}")


@caso("exclusion", "Lo excluido se guarda pero no cuenta")
def prueba_exclusion(e):
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL)
    e.ejecutar()
    df = e.historico()

    comprobar(len(df) == len(ABRIL), "el histórico guarda TODO, excluidos incluidos",
              f"{len(df)} de {len(ABRIL)}")
    fila = df[df["descripcion"].str.contains("LIQUIDACION TARJETA")]
    comprobar(len(fila) == 1 and bool(fila.iloc[0]["excluido"]),
              "la liquidación de la tarjeta queda marcada como excluida")
    comprobar(fila.iloc[0]["regla"] == "liquidacion tarjeta",
              "la regla que lo saca queda anotada",
              str(fila.iloc[0]["regla"]))

    res = e.resumen()
    comprobar(abs(res.iloc[0]["Total Gastos"] - TOTAL_GASTOS_ABRIL) < 0.005,
              "los 500 € excluidos no suman en Total Gastos",
              f"salió {res.iloc[0]['Total Gastos']}")


@caso("totales", "Los totales del resumen mensual")
def prueba_totales(e):
    # sin columna de saldo a propósito: este caso es sobre los totales por
    # categoría, no sobre el saldo inicial (que tiene sus propios casos).
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL, cabecera_saldo=False)
    e.ejecutar()
    res = e.resumen()

    comprobar(len(res) == 1, "un solo mes", f"{len(res)} meses")
    f = res.iloc[0]
    comprobar(f["Mes"] == "2026-04", "el mes es 2026-04", str(f["Mes"]))
    comprobar(abs(f["Comida"] - 150) < 0.005, "Comida = 150", str(f["Comida"]))
    comprobar(abs(f["Otros"] - 560) < 0.005, "Otros = 560", str(f["Otros"]))
    comprobar(abs(f["Piso"] - 40) < 0.005, "Piso = 40", str(f["Piso"]))
    comprobar(abs(f["Transporte"] - 60) < 0.005, "Transporte = 60",
              str(f["Transporte"]))
    comprobar(abs(f["Total Gastos"] - TOTAL_GASTOS_ABRIL) < 0.005,
              "Total Gastos = 810", str(f["Total Gastos"]))
    comprobar(abs(f["Ingresos"] - INGRESOS_ABRIL) < 0.005,
              "Ingresos = 2000", str(f["Ingresos"]))
    comprobar(abs(f["Balance"] - 1190) < 0.005, "Balance = +1190",
              str(f["Balance"]))
    comprobar(abs(f["Acumulado"] - 1190) < 0.005, "Acumulado = +1190",
              str(f["Acumulado"]))
    comprobar(abs(f["Deuda"]) < 0.005 and abs(f["Extras"]) < 0.005,
              "el primer mes no arrastra nada")


@caso("saldo-inicial", "El Acumulado parte del saldo real de la cuenta, no de 0")
def prueba_saldo_inicial(e):
    # escribir_html simula el saldo real de la cuenta partiendo de 5000 € y
    # aplicando cada movimiento en el orden dado (ver fixtures.py).
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL[:3])   # nomina + 2 compras
    salida = e.ejecutar()
    res = e.resumen()

    comprobar("Saldo inicial detectado" in salida and "5,000.00" in salida,
              "lo dice por pantalla", salida)

    f = res.iloc[0]
    balance = float(f["Balance"])
    comprobar(abs(f["Acumulado"] - (5000 + balance)) < 0.005,
              "Acumulado = saldo inicial + balance del mes, no solo el balance",
              str(f["Acumulado"]))
    comprobar(abs(f["Extras"] - 5000) < 0.005 and abs(f["Deuda"]) < 0.005,
              "el primer mes ya arrastra el saldo con que empezaba la cuenta",
              f"Extras={f['Extras']} Deuda={f['Deuda']}")


@caso("saldo-inicial-sin-cuenta", "Sin movimientos de cuenta, el Acumulado sigue en 0")
def prueba_saldo_inicial_sin_cuenta(e):
    # solo tarjeta: no hay saldo de cuenta que leer, así que ni se menciona.
    fx.escribir_xml_ss(e.entrada / "tarjeta.xls", [("05/04/2026", "COMPRA A", -20.00)],
                       tarjeta=True)
    salida = e.ejecutar()
    res = e.resumen()

    comprobar("Saldo inicial detectado" not in salida,
              "no hay cuenta de la que sacar un saldo", salida)
    comprobar(abs(res.iloc[0]["Acumulado"] - res.iloc[0]["Balance"]) < 0.005,
              "Acumulado = Balance a secas, como siempre", str(res.iloc[0]["Acumulado"]))


@caso("saldo-inicial-sin-columna", "Cuenta sin columna de saldo: se sigue empezando en 0")
def prueba_saldo_inicial_sin_columna(e):
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL[:3], cabecera_saldo=False)
    salida = e.ejecutar()
    res = e.resumen()

    comprobar("Saldo inicial detectado" not in salida,
              "sin columna de saldo no hay nada que detectar", salida)
    comprobar(abs(res.iloc[0]["Acumulado"] - res.iloc[0]["Balance"]) < 0.005,
              "Acumulado = Balance a secas", str(res.iloc[0]["Acumulado"]))


@caso("saldo-inicial-ambiguo-resoluble", "Dos movimientos el primer día no impiden calcularlo")
def prueba_saldo_inicial_ambiguo_resoluble(e):
    # el primer DÍA trae dos movimientos: no se sabe en qué orden los aplicó
    # el banco, así que ese día no puede ser el ancla. El segundo día solo
    # trae uno, y desde ahí sí se puede restar lo del primero (con o sin
    # saber su orden interno, la suma del día es la misma).
    datos = [("01/04/2026", "COMPRA A", -30.00),
             ("01/04/2026", "COMPRA B", -20.00),
             ("02/04/2026", "COMPRA C", -10.00)]
    fx.escribir_html(e.entrada / "cuenta.xls", datos)
    salida = e.ejecutar()

    # saldo real antes de TODO: 5000 (lo fija fixtures.escribir_html)
    comprobar("Saldo inicial detectado: 5,000.00" in salida,
              "resuelve el ambiguo apoyándose en el día siguiente, sin ambigüedad",
              salida)


@caso("saldo-inicial-totalmente-ambiguo", "Si NINGÚN día es inequívoco, no se arriesga")
def prueba_saldo_inicial_totalmente_ambiguo(e):
    # los dos únicos días con saldo tienen más de un movimiento cada uno: no
    # hay ancla segura en ningún sitio, así que mejor 0 que un cuadre inventado.
    datos = [("01/04/2026", "COMPRA A", -30.00),
             ("01/04/2026", "COMPRA B", -20.00),
             ("02/04/2026", "COMPRA C", -10.00),
             ("02/04/2026", "COMPRA D", -5.00)]
    fx.escribir_html(e.entrada / "cuenta.xls", datos)
    salida = e.ejecutar()
    res = e.resumen()

    comprobar("Saldo inicial detectado" not in salida,
              "ningún día es inequívoco, así que no propone nada", salida)
    comprobar(abs(res.iloc[0]["Acumulado"] - res.iloc[0]["Balance"]) < 0.005,
              "Acumulado = Balance a secas, sin arriesgar un saldo inventado",
              str(res.iloc[0]["Acumulado"]))


@caso("saldo-inicial-migracion", "Un histórico viejo sin columna «saldo» se actualiza")
def prueba_saldo_inicial_migracion(e):
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL[:3])
    e.ejecutar()
    antes = len(e.historico())

    import pandas as pd
    movimientos = pd.read_excel(e.ruta_historico, sheet_name="MOVIMIENTOS")
    movimientos = movimientos.drop(columns=["saldo"])
    with pd.ExcelWriter(e.ruta_historico, engine="openpyxl") as w:
        movimientos.to_excel(w, sheet_name="MOVIMIENTOS", index=False)

    e.vaciar_entrada()
    salida = e.ejecutar()

    comprobar("«saldo»" in salida and "actualizado" in salida,
              "dice qué migración ha aplicado", salida)
    df = e.historico()
    comprobar(len(df) == antes, "sin perder movimientos", f"{len(df)} en vez de {antes}")
    comprobar("saldo" in df.columns, "y la columna vuelve a estar")
    comprobar("Saldo inicial detectado" not in salida,
              "el saldo viejo no puede recuperarse a toro pasado, así que "
              "esta vez el Acumulado vuelve a partir de 0", salida)


@caso("dedup-cuenta", "Dos cuentas declaradas no fusionan un movimiento idéntico")
def prueba_dedup_cuenta(e):
    e.escribir_config("cuentas.json",
                      {"principal": "principal", "secundaria": "secundaria"})
    igual = [("07/04/2026", "COMPRA MERCADONA MADRID", -10.00)]
    fx.escribir_html(e.entrada / "principal_042026.xls", igual)
    fx.escribir_html(e.entrada / "secundaria_042026.xls", igual)
    salida = e.ejecutar()

    df = e.historico()
    comprobar(len(df) == 2, "las dos cuentas dan DOS filas, no una fusionada",
              f"{len(df)} filas")
    comprobar(set(df["cuenta"]) == {"principal", "secundaria"},
              "cada fila queda marcada con la cuenta que le tocaba",
              str(set(df["cuenta"])))
    comprobar("cuenta: principal" in salida and "cuenta: secundaria" in salida,
              "y se avisa por pantalla de la cuenta detectada", salida)


@caso("dedup-cuenta-sin-declarar", "Sin declarar cuentas, el comportamiento es el de siempre")
def prueba_dedup_cuenta_sin_declarar(e):
    # regresión: el efecto lateral que documenta TRASPASO.md (dos cuentas del
    # mismo tipo con un cargo idéntico se fusionan) sigue igual si no se
    # configura ajustes/cuentas.json. Es a propósito: nadie nota un cambio de
    # comportamiento por no haber tocado un fichero que no sabía que existía.
    igual = [("07/04/2026", "COMPRA MERCADONA MADRID", -10.00)]
    fx.escribir_html(e.entrada / "cuenta_a.xls", igual)
    fx.escribir_html(e.entrada / "cuenta_b.xls", igual)
    salida = e.ejecutar()

    df = e.historico()
    comprobar(len(df) == 1,
              "sin ajustes/cuentas.json, las dos siguen fusionándose en una",
              f"{len(df)} filas")
    comprobar("cuenta:" not in salida, "y no se menciona ninguna cuenta", salida)


@caso("cuentas-migracion", "Un histórico viejo sin columna «cuenta» se actualiza")
def prueba_cuentas_migracion(e):
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL[:3])
    e.ejecutar()
    antes = len(e.historico())

    import pandas as pd
    movimientos = pd.read_excel(e.ruta_historico, sheet_name="MOVIMIENTOS")
    movimientos = movimientos.drop(columns=["cuenta"])
    with pd.ExcelWriter(e.ruta_historico, engine="openpyxl") as w:
        movimientos.to_excel(w, sheet_name="MOVIMIENTOS", index=False)

    e.vaciar_entrada()
    salida = e.ejecutar()

    comprobar("«cuenta»" in salida and "actualizado" in salida,
              "dice qué migración ha aplicado", salida)
    df = e.historico()
    comprobar(len(df) == antes, "sin perder movimientos", f"{len(df)} en vez de {antes}")
    comprobar("cuenta" in df.columns, "y la columna vuelve a estar")
    # una celda vacía escrita en Excel vuelve como NaN en una lectura a
    # pelo como esta (sin pasar por historico.cargar(), que sí la limpia)
    comprobar(set(df["cuenta"].fillna("")) == {""},
              "todo lo viejo queda sin identificar: no se puede saber a toro "
              "pasado de qué cuenta era", str(set(df["cuenta"])))


@caso("saldo-por-cuenta", "Con varias cuentas, el saldo inicial se calcula de cada una")
def prueba_saldo_por_cuenta(e):
    e.escribir_config("cuentas.json", {"principal": "principal", "ahorro": "ahorro"})
    fx.escribir_html(e.entrada / "principal_042026.xls",
                     [("05/04/2026", "COMPRA MERCADONA MADRID", -100.00)])
    fx.escribir_html(e.entrada / "ahorro_042026.xls",
                     [("05/04/2026", "TRASPASO DESDE PRINCIPAL", 200.00)])
    salida = e.ejecutar()
    res = e.resumen()

    comprobar("Saldo inicial detectado en 2 cuentas" in salida, "avisa de las dos",
              salida)
    comprobar("principal: 5,000.00" in salida and "ahorro: 5,000.00" in salida,
              "cada una con SU PROPIO saldo (5000 €, fijado por fixtures.py)",
              salida)
    # 5000+5000 de saldo inicial, -100 de gasto ese mes (el traspaso entre
    # las dos propias cuentas es neutro: no suma como ingreso, ver rules_base)
    comprobar(abs(res.iloc[0]["Acumulado"] - 9900) < 0.005,
              "el Acumulado combinado suma las dos cuentas más el balance",
              str(res.iloc[0]["Acumulado"]))


@caso("gastos-signo", "Una devolución sale en negativo, no disfrazada de gasto")
def prueba_signo(e):
    # Comida: -100 de compra y +150 de devolución -> la categoría acaba a favor.
    # Debe salir como -50, NO como +50 (eso es lo que hacía ABS()).
    datos = [("07/04/2026", "COMPRA MERCADONA MADRID", -100.00),
             ("09/04/2026", "DEVOLUCION MERCADONA MADRID", 150.00)]
    fx.escribir_html(e.entrada / "cuenta.xls", datos)
    e.ejecutar()
    res = e.resumen()

    comprobar(abs(res.iloc[0]["Comida"] + 50) < 0.005,
              "Comida sale a -50, no a +50", str(res.iloc[0]["Comida"]))


@caso("dedup", "Dos descargas que se solapan no duplican movimientos")
def prueba_dedup(e):
    abril = ABRIL[:5]
    abril_y_mayo = ABRIL[:5] + [("03/05/2026", "COMPRA LIDL MADRID", -25.00)]

    fx.escribir_html(e.entrada / "descarga_1.xls", abril)
    e.ejecutar()
    comprobar(len(e.historico()) == 5, "primera descarga: 5 movimientos")

    e.vaciar_entrada()
    fx.escribir_html(e.entrada / "descarga_2.xls", abril_y_mayo)
    salida = e.ejecutar()

    df = e.historico()
    comprobar(len(df) == 6, "la segunda descarga solo añade el nuevo",
              f"quedaron {len(df)}")
    comprobar("5 movimientos ya estaban" in salida,
              "avisa de los 5 repetidos", salida)


@caso("repetido", "Dos cargos idénticos el mismo día son dos gastos reales")
def prueba_repetido(e):
    datos = [("07/04/2026", "COMPRA MERCADONA MADRID", -10.00),
             ("07/04/2026", "COMPRA MERCADONA MADRID", -10.00)]
    fx.escribir_html(e.entrada / "cuenta.xls", datos)
    e.ejecutar()

    df = e.historico()
    comprobar(len(df) == 2, "se conservan los dos", f"quedó {len(df)}")
    comprobar(sorted(df["n_rep"].tolist()) == [0, 1],
              "n_rep los distingue (0 y 1)", str(df["n_rep"].tolist()))

    # y al volver a descargar el mismo extracto, siguen siendo dos
    e.vaciar_entrada()
    fx.escribir_html(e.entrada / "cuenta_otra_vez.xls", datos)
    e.ejecutar()
    comprobar(len(e.historico()) == 2,
              "una segunda descarga no los convierte en cuatro",
              f"quedaron {len(e.historico())}")


@caso("reclasificar", "Afinar las reglas reclasifica el histórico entero")
def prueba_reclasificar(e):
    # Un nombre que ni la base ni tus reglas conocen, para que empiece en Otros.
    datos = [("07/04/2026", "ESTUDIO ZURRIOLA", -30.00)]
    fx.escribir_html(e.entrada / "cuenta.xls", datos)
    e.ejecutar()
    comprobar(categoria_de(e.historico(), "ZURRIOLA") == "Otros",
              "sin regla, cae en Otros",
              str(categoria_de(e.historico(), "ZURRIOLA")))

    # se añade la regla y se ejecuta CON LA ENTRADA VACÍA
    e.vaciar_entrada()
    e.regla_al_principio("zurriola", "Ocio")
    e.ejecutar()

    df = e.historico()
    comprobar(len(df) == 1, "no se pierde ni se duplica nada", f"{len(df)} filas")
    comprobar(categoria_de(df, "ZURRIOLA") == "Ocio",
              "la regla nueva se aplica hacia atrás sin los .xls originales",
              str(categoria_de(df, "ZURRIOLA")))


@caso("informe-agrupa", "El informe de sin clasificar agrupa, ordena y limita a 10")
def prueba_informe_agrupa(e):
    # 12 comercios ajenos a la base, cada uno con un importe distinto y sin
    # ninguna otra palabra en común entre ellos (el "compra" de delante es
    # relleno y se descarta), para que cada uno forme su propio grupo y el
    # orden por importe sea inequívoco.
    nombres = ["zafiro", "yodo", "xenon", "uva", "tango", "sierra",
              "romeo", "quebec", "papaya", "oscar", "noviembre", "mikonos"]
    datos = [(f"{10 + i:02d}/04/2026", f"COMPRA {n.upper()} TIENDA{i}", -(120 - i * 10))
             for i, n in enumerate(nombres)]
    fx.escribir_html(e.entrada / "cuenta.xls", datos)
    salida = e.ejecutar()

    comprobar("sin ninguna regla" in salida, "avisa de lo sin clasificar", salida)
    comprobar("12 grupos" in salida, "cuenta los 12 grupos que hay",
              salida)
    comprobar("se muestran los 10" in salida,
              "avisa de que solo enseña los 10 de más importe", salida)

    comprobar("ZAFIRO" in salida and "YODO" in salida,
              "los dos grupos más gordos aparecen")
    comprobar("NOVIEMBRE" not in salida and "MIKONOS" not in salida,
              "los dos más pequeños se quedan fuera de los 10")
    comprobar(salida.find("ZAFIRO") < salida.find("OSCAR"),
              "van de más a menos importe (zafiro=120 antes que oscar=30)")
    comprobar('"zafiro": "PON_TU_CATEGORIA"' in salida,
              "trae una línea lista para pegar en rules.json", salida)


@caso("informe-otros-por-regla", "Otros por una regla explícita no es «sin clasificar»")
def prueba_informe_otros_por_regla(e):
    # amazon->Otros ya está en rules_base.json: es "Otros por regla", no por
    # defecto, y por tanto NO tiene que aparecer en el informe aunque su
    # categoría final sea la misma que la de lo que sí queda sin clasificar.
    datos = [("07/04/2026", "AMAZON MKTPLACE PAGO", -200.00),
             ("09/04/2026", "MISTERIOSA TIENDA RARA", -50.00)]
    fx.escribir_html(e.entrada / "cuenta.xls", datos)
    salida = e.ejecutar()

    comprobar("AMAZON" not in salida,
              "lo clasificado por una regla (aunque sea a Otros) no sale en el informe",
              salida)
    comprobar("MISTERIOSA TIENDA RARA" in salida,
              "lo que de verdad no casa con ninguna regla sí sale", salida)


@caso("informe-validacion", "La clave sugerida se valida contra lo ya clasificado")
def prueba_informe_validacion(e):
    # Grupo A: "barcelona" es la palabra más repetida, pero ya aparece dentro
    # de un movimiento que otra regla ("taxi") clasifica. Pegar "barcelona"
    # tal cual reclasificaría ese movimiento en silencio, así que el informe
    # tiene que descartarla y ofrecer otra palabra del mismo grupo ("hotel").
    #
    # Grupo B: las cuatro palabras de la única fila aparecen también en un
    # movimiento que ya clasifica la regla "renfe". Ninguna es segura, así que
    # el informe no debe sugerir nada para ese grupo.
    datos = [
        ("05/04/2026", "TAXI BARCELONA AEROPUERTO", -25.00),
        ("06/04/2026", "RENFE CERCANIAS RETRASO ESTACION AVISO", -12.00),
        ("10/04/2026", "BARCELONA HOTEL RESERVA", -30.00),
        ("11/04/2026", "BARCELONA HOTEL RESERVA", -25.00),
        ("12/04/2026", "BARCELONA HOTEL RESERVA", -20.00),
        ("13/04/2026", "BARCELONA SOUVENIR TIENDA", -15.00),
        ("14/04/2026", "CERCANIAS RETRASO ESTACION AVISO", -40.00),
    ]
    fx.escribir_html(e.entrada / "cuenta.xls", datos)
    salida = e.ejecutar()

    comprobar('"barcelona": "PON_TU_CATEGORIA"' not in salida,
              "no sugiere «barcelona»: capturaría el movimiento del taxi", salida)
    comprobar('"hotel": "PON_TU_CATEGORIA"' in salida,
              "pero sí sugiere otra palabra del mismo grupo, que no colisiona",
              salida)
    comprobar('"cercanias": "PON_TU_CATEGORIA"' not in salida
              and '"retraso": "PON_TU_CATEGORIA"' not in salida
              and '"estacion": "PON_TU_CATEGORIA"' not in salida
              and '"aviso": "PON_TU_CATEGORIA"' not in salida,
              "y si TODAS las palabras del grupo colisionan, no sugiere ninguna",
              salida)
    comprobar("revísalo a mano" in salida,
              "y lo dice, en vez de callarse sin más", salida)


@caso("informe-relleno", "El relleno del banco y los números no se sugieren como clave")
def prueba_informe_relleno(e):
    datos = [("07/04/2026", "PAGO TARJ 000456 CLUB DEPORTIVO", -15.00),
             ("08/04/2026", "PAGO TARJ 000456 CLUB DEPORTIVO", -15.00),
             ("09/04/2026", "PAGO TARJ 000456 CLUB DEPORTIVO", -15.00)]
    fx.escribir_html(e.entrada / "cuenta.xls", datos)
    salida = e.ejecutar()

    comprobar('"pago"' not in salida and '"tarj"' not in salida
              and '"000456"' not in salida,
              "ni el relleno del banco ni el número de referencia se sugieren",
              salida)
    comprobar('"deportivo": "PON_TU_CATEGORIA"' in salida
              or '"club": "PON_TU_CATEGORIA"' in salida,
              "y sí una palabra de verdad del concepto", salida)


@caso("informe-vacio", "Sin nada sin clasificar, el informe no se muestra")
def prueba_informe_vacio(e):
    datos = [("07/04/2026", "COMPRA MERCADONA MADRID", -10.00),
             ("09/04/2026", "COMPRA CARREFOUR MADRID", -10.00)]
    fx.escribir_html(e.entrada / "cuenta.xls", datos)
    salida = e.ejecutar()

    comprobar("sin ninguna regla" not in salida,
              "no aparece nada si todo está clasificado", salida)


@caso("tarjeta-detecta", "Detecta el recibo con que la cuenta paga la tarjeta")
def prueba_tarjeta_detecta(e):
    e.escribir_config("exclude_patterns.json", [])   # precondición: vacío

    tarjeta = [("05/04/2026", "COMPRA A", -50.00),
              ("12/04/2026", "COMPRA B", -30.25),
              ("20/04/2026", "COMPRA C", -15.05)]     # total -95.30
    fx.escribir_xml_ss(e.entrada / "tarjeta.xls", tarjeta, tarjeta=True)

    cuenta = [("01/04/2026", "NOMINA EMPRESA FICTICIA SL", 2000.00),
             ("05/05/2026", "LIQUIDACION TARJETA VISA 778899", -95.30)]
    fx.escribir_html(e.entrada / "cuenta.xls", cuenta, cabecera_saldo=True)

    salida = e.ejecutar()

    comprobar("ningún patrón en" in salida, "avisa de que no hay exclusiones",
              salida)
    comprobar("2026-04" in salida and "95.30" in salida,
              "identifica el mes y el importe que cuadra", salida)
    comprobar('"liquidacion tarjeta visa"' in salida,
              "propone la parte fija del recibo, sin el número de referencia",
              salida)


@caso("tarjeta-ya-excluido", "No propone nada si ya hay exclusiones puestas")
def prueba_tarjeta_ya_excluido(e):
    # el propio andamiaje de pruebas deja "liquidacion tarjeta credito" puesto
    # por defecto: es justo la precondición de "ya resuelto".
    tarjeta = [("05/04/2026", "COMPRA A", -50.00)]
    fx.escribir_xml_ss(e.entrada / "tarjeta.xls", tarjeta, tarjeta=True)
    cuenta = [("05/05/2026", "LIQUIDACION TARJETA CREDITO 778899", -50.00)]
    fx.escribir_html(e.entrada / "cuenta.xls", cuenta, cabecera_saldo=True)

    salida = e.ejecutar()

    comprobar("ningún patrón en" not in salida,
              "no dice nada: se asume que ya está resuelto", salida)


@caso("tarjeta-sin-tarjeta", "Sin movimientos de tarjeta, no hay nada que detectar")
def prueba_tarjeta_sin_tarjeta(e):
    e.escribir_config("exclude_patterns.json", [])
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL[:2], cabecera_saldo=True)
    salida = e.ejecutar()

    comprobar("ningún patrón en" not in salida,
              "no hay tarjeta que pueda duplicarse, así que calla", salida)


@caso("tarjeta-ambigua", "Un mes con dos cargos que cuadran no propone nada")
def prueba_tarjeta_ambigua(e):
    e.escribir_config("exclude_patterns.json", [])

    tarjeta = [("05/04/2026", "COMPRA A", -50.00)]
    fx.escribir_xml_ss(e.entrada / "tarjeta.xls", tarjeta, tarjeta=True)

    # dos cargos de cuenta por el mismo importe en la ventana: no hay forma de
    # saber cuál es el recibo, así que no se debe proponer ninguno.
    cuenta = [("07/05/2026", "PAGO ALQUILER PISO", -50.00),
             ("09/05/2026", "LIQUIDACION TARJETA", -50.00)]
    fx.escribir_html(e.entrada / "cuenta.xls", cuenta, cabecera_saldo=True)

    salida = e.ejecutar()

    comprobar("ningún patrón en" in salida, "sigue avisando de la precondición",
              salida)
    comprobar("no lo he sabido encontrar" in salida,
              "pero no adivina entre los dos candidatos ambiguos", salida)
    comprobar("Añade esto a exclude_patterns.json" not in salida,
              "y no llega a proponer ninguna clave", salida)


@caso("tarjeta-tolerancia", "Tolera céntimos de redondeo, pero no una diferencia real")
def prueba_tarjeta_tolerancia(e):
    e.escribir_config("exclude_patterns.json", [])

    tarjeta = [("05/04/2026", "COMPRA A", -40.00),      # abril: -40.00
              ("05/05/2026", "COMPRA B", -60.00)]       # mayo:  -60.00
    fx.escribir_xml_ss(e.entrada / "tarjeta.xls", tarjeta, tarjeta=True)

    cuenta = [
        ("06/05/2026", "LIQUIDACION TARJETA ABRIL 111222", -40.02),  # 2 cent.: sí
        ("06/06/2026", "LIQUIDACION TARJETA MAYO 333444", -60.10),   # 10 cent.: no
    ]
    fx.escribir_html(e.entrada / "cuenta.xls", cuenta, cabecera_saldo=True)

    salida = e.ejecutar()

    comprobar("2026-04" in salida and "40.00" in salida,
              "el cuadre a 2 céntimos sí se acepta (redondeo)", salida)
    comprobar("2026-05:" not in salida,
              "el cuadre a 10 céntimos no, no es un simple redondeo", salida)


@caso("tarjeta-varios-meses", "La clave sugerida no arrastra el número de referencia")
def prueba_tarjeta_varios_meses(e):
    e.escribir_config("exclude_patterns.json", [])

    tarjeta = [("05/04/2026", "COMPRA A", -70.00), ("06/04/2026", "COMPRA B", -50.00),
              ("05/05/2026", "COMPRA C", -80.00)]
    fx.escribir_xml_ss(e.entrada / "tarjeta.xls", tarjeta, tarjeta=True)

    # la referencia (los números) cambia de un mes a otro; lo demás, no.
    cuenta = [
        ("03/05/2026", "ADEUDO TARJETA 445566 LIQUIDACION ABRIL", -120.00),
        ("03/06/2026", "ADEUDO TARJETA 998877 LIQUIDACION MAYO", -80.00),
    ]
    fx.escribir_html(e.entrada / "cuenta.xls", cuenta, cabecera_saldo=True)

    salida = e.ejecutar()

    comprobar("2026-04" in salida and "2026-05" in salida,
              "encuentra el recibo de los dos meses", salida)
    comprobar('"adeudo tarjeta"' in salida,
              "la clave es lo que de verdad se repite, sin el número ni las "
              "palabras que solo aparecían en un mes", salida)


@caso("iso", "Las fechas aaaa-mm-dd no se invierten")
def prueba_iso(e):
    datos = [("02/04/2026", "COMPRA MERCADONA MADRID", -10.00)]
    fx.escribir_csv(e.entrada / "cuenta.xls", datos, fechas_iso=True)
    e.ejecutar()

    fecha = e.historico().iloc[0]["fecha"]
    comprobar((fecha.day, fecha.month) == (2, 4),
              "2026-04-02 es 2 de abril, no 4 de febrero",
              f"salió {fecha:%d/%m/%Y}")


@caso("mes", "El mes contable mueve las nóminas de los días 1-3")
def prueba_mes(e):
    datos = [("01/05/2026", "NOMINA EMPRESA FICTICIA SL", 2000.00),
             ("05/05/2026", "COMPRA MERCADONA MADRID", -10.00)]
    fx.escribir_html(e.entrada / "cuenta.xls", datos)
    e.ejecutar()

    df = e.historico()
    comprobar(campo_de(df, "NOMINA", "mes") == "2026-05",
              "el mes real de la nómina sigue siendo mayo")
    comprobar(campo_de(df, "NOMINA", "mes_ajustado") == "2026-04",
              "el mes contable la manda a abril",
              str(campo_de(df, "NOMINA", "mes_ajustado")))
    comprobar(campo_de(df, "MERCADONA", "mes_ajustado") == "2026-05",
              "la compra del día 5 no se mueve")

    res = e.resumen()
    abril = res[res["Mes"] == "2026-04"]
    comprobar(len(abril) == 1 and abs(abril.iloc[0]["Ingresos"] - 2000) < 0.005,
              "el resumen agrupa por el mes contable")


@caso("manual", "La columna categoria_manual manda sobre las reglas")
def prueba_manual(e):
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL)
    e.ejecutar()

    # se escribe a mano en la columna H, como haría el usuario en OnlyOffice
    from openpyxl import load_workbook
    wb = load_workbook(e.ruta_historico)
    ws = wb["MOVIMIENTOS"]
    escritas = 0
    for fila in ws.iter_rows(min_row=2):
        desc = str(fila[1].value)
        if "BARCELONA" in desc:
            fila[7].value = "Ocio"                  # categoría válida
            escritas += 1
        elif "MEDIA MARKT" in desc:
            fila[7].value = "(excluido)"            # sacar de los totales
            escritas += 1
        elif "ABP" in desc:
            fila[7].value = "Categoria Inventada"   # errata
            escritas += 1
    wb.save(e.ruta_historico)
    wb.close()
    comprobar(escritas == 3, "preparadas las 3 correcciones manuales")

    e.vaciar_entrada()
    salida = e.ejecutar()
    df = e.historico()

    comprobar(categoria_de(df, "BARCELONA") == "Ocio",
              "una categoría válida fuerza la categoría",
              str(categoria_de(df, "BARCELONA")))
    comprobar(campo_de(df, "BARCELONA", "regla") == "(manual)",
              "y queda anotado como (manual)")
    comprobar(bool(campo_de(df, "MEDIA MARKT", "excluido")),
              "«(excluido)» saca la línea de los totales")
    comprobar(categoria_de(df, "GUARDIA CIVIL") == "Otros",
              "las líneas sin corrección siguen mandándolas las reglas")

    # Una categoría que no existe en categorias.json NO se aplica: si se
    # aplicara, el movimiento desaparecería de todas las columnas del resumen
    # sin restar de ningún total, y el Excel descuadraría en silencio.
    comprobar(categoria_de(df, "ABP") == "Otros",
              "una categoría mal escrita se ignora y mandan las reglas",
              str(categoria_de(df, "ABP")))
    comprobar("Categoria Inventada" in salida,
              "pero avisa por pantalla de la errata", salida)

    # y la corrección escrita se conserva entre ejecuciones
    comprobar(campo_de(df, "BARCELONA", "categoria_manual") == "Ocio",
              "la corrección sobrevive a la siguiente ejecución")

    res = e.resumen()
    # Otros pierde BARCELONA (300, se va a Ocio) y MEDIA MARKT (200, excluido)
    comprobar(abs(res.iloc[0]["Otros"] - 60) < 0.005,
              "Otros baja a 60", str(res.iloc[0]["Otros"]))
    comprobar(abs(res.iloc[0]["Ocio"] - 300) < 0.005,
              "Ocio sube a 300", str(res.iloc[0]["Ocio"]))


@caso("texto-igual", "Una clave que empieza por '=' no se guarda como fórmula")
def prueba_texto_igual(e):
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL)
    e.ejecutar()

    wb = e.libro_historico()
    ws = wb["MOVIMIENTOS"]
    encontrada = None
    for fila in ws.iter_rows(min_row=2):
        if "SUPERMERCADOS DIA" in str(fila[1].value):
            encontrada = fila[10]                    # columna K = regla
    comprobar(encontrada is not None, "localizada la fila de DIA")
    if encontrada is not None:
        comprobar(encontrada.value == "=dia",
                  "la regla «=dia» se guarda tal cual", repr(encontrada.value))
        comprobar(encontrada.data_type != "f",
                  "y NO como fórmula (si no, Excel la dejaría en 0)",
                  f"data_type={encontrada.data_type}")
    wb.close()


@caso("columnas", "El orden de las columnas del histórico no cambia")
def prueba_columnas(e):
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL)
    e.ejecutar()

    esperado = ["fecha", "descripcion", "importe", "tipo", "mes", "mes_ajustado",
                "categoria", "categoria_manual", "excluido", "origen", "regla",
                "n_rep", "saldo", "cuenta"]
    real = list(e.historico().columns)
    comprobar(real == esperado,
              "A-G fijas para las fórmulas del usuario, lo demás detrás",
              f"salió {real}")

    limpios = None
    import pandas as pd
    limpios = list(pd.read_excel(e.salida / "movimientos_limpios.xlsx").columns)
    comprobar(limpios[:7] == esperado[:7],
              "movimientos_limpios.xlsx manda A-G", f"salió {limpios}")


@caso("catalogo", "Se avisa si rules.json y categorias.json no cuadran")
def prueba_catalogo(e):
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL[:2])
    e.regla_al_principio("mercadona", "Comidas")   # sobra una 's'
    salida = e.ejecutar()

    comprobar("Comidas" in salida, "detecta la categoría inventada", salida)
    comprobar("no cuadran" in salida, "y lo dice claramente", salida)


@caso("sync-basico", "El volcado al fichero de contabilidad")
def prueba_sync_basico(e):
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL)
    fx.escribir_destino(e.dir / "contabilidad.xlsx", filas_previas=30)
    cfg = e.leer_config("sincronizar.json")
    cfg["archivo"] = "contabilidad.xlsx"
    e.escribir_config("sincronizar.json", cfg)

    salida = e.ejecutar()
    comprobar("filas escritas" in salida, "dice que ha escrito", salida)

    from openpyxl import load_workbook
    wb = load_workbook(e.dir / "contabilidad.xlsx")
    ws = wb["MOVIMIENTOS"]
    comprobar(ws["A1"].value == "fecha" and ws["G1"].value == "categoria",
              "escribe la cabecera A-G")
    # 10 movimientos (11 menos el excluido) + cabecera
    comprobar(ws.max_row == 11,
              "no quedan filas fantasma de los datos anteriores",
              f"max_row={ws.max_row}")
    wb.close()

    comprobar((e.datos / "copias").is_dir(), "hace copia de seguridad antes")


@caso("sync-columnas", "El recorte de filas no se lleva las columnas de al lado")
def prueba_sync_columnas(e):
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL[:3])
    fx.escribir_destino(e.dir / "contabilidad.xlsx", notas_en_columna="J",
                        filas_previas=30)
    cfg = e.leer_config("sincronizar.json")
    cfg["archivo"] = "contabilidad.xlsx"
    e.escribir_config("sincronizar.json", cfg)

    e.ejecutar()

    from openpyxl import load_workbook
    wb = load_workbook(e.dir / "contabilidad.xlsx")
    ws = wb["MOVIMIENTOS"]
    comprobar(ws["J1"].value == "mis notas" and ws["J25"].value == "nota 25",
              "las notas de la columna J siguen ahí",
              f"J1={ws['J1'].value!r} J25={ws['J25'].value!r}")
    comprobar(ws["A10"].value is None,
              "y el bloque A-G sí queda limpio por debajo de los datos",
              f"A10={ws['A10'].value!r}")
    wb.close()


@caso("sync-formulas", "No se escribe en una hoja con fórmulas")
def prueba_sync_formulas(e):
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL[:3])
    fx.escribir_destino(e.dir / "contabilidad.xlsx", formula=True)
    cfg = e.leer_config("sincronizar.json")
    cfg["archivo"] = "contabilidad.xlsx"
    e.escribir_config("sincronizar.json", cfg)

    salida = e.ejecutar()
    comprobar("rmulas" in salida and "NO se ha tocado" in salida,
              "se niega y lo explica", salida)

    from openpyxl import load_workbook
    wb = load_workbook(e.dir / "contabilidad.xlsx")
    comprobar(wb["MOVIMIENTOS"]["A20"].value == "=SUM(C2:C10)",
              "el fichero del usuario queda intacto")
    wb.close()
    comprobar((e.ruta_historico).exists(),
              "y el resto del proceso termina igual")


@caso("sin-nada", "Sin histórico y sin entrada, un error entendible")
def prueba_sin_nada(e):
    salida = e.ejecutar()
    comprobar(e.ultimo_codigo != 0, "termina con error")
    comprobar("Traceback" not in salida, "sin traceback en la cara del usuario",
              salida)
    comprobar("entrada" in salida, "y dice qué hacer", salida)


@caso("migracion", "La carpeta antigua se recoloca sola, sin perder nada")
def prueba_migracion(e):
    # Fase 1: se genera un histórico de verdad, con la configuración suelta en
    # la raíz como la tenía la versión antigua.
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL)
    e.ejecutar()
    comprobar(e.ruta_historico.exists(), "arranca aunque la config esté suelta")
    movimientos_antes = len(e.historico())

    # Fase 2: se deshace la mudanza a mano, para dejar la carpeta exactamente
    # como la tenía el usuario antes: todo suelto en la raíz.
    import shutil
    shutil.move(str(e.ruta_historico), str(e.dir / "historico.xlsx"))
    shutil.move(str(e.salida / "movimientos_limpios.xlsx"),
                str(e.dir / "movimientos_limpios.xlsx"))
    for f in ("rules.json", "exclude_patterns.json", "categorias.json",
              "sincronizar.json"):
        shutil.move(str(e.ajustes / f), str(e.dir / f))
    shutil.rmtree(e.datos)
    shutil.rmtree(e.ajustes)
    (e.dir / "copias").mkdir()
    (e.dir / "copias" / "historico_20260101_000000.xlsx").write_bytes(b"copia vieja")
    e.vaciar_entrada()

    salida = e.ejecutar()

    comprobar("reorganizado" in salida, "avisa de que ha reorganizado", salida)
    comprobar(e.ruta_historico.exists(),
              "el histórico acaba en datos/")
    comprobar(not (e.dir / "historico.xlsx").exists(),
              "y ya no está suelto en la raíz")
    comprobar(len(e.historico()) == movimientos_antes,
              "con los mismos movimientos que antes",
              f"{len(e.historico())} en vez de {movimientos_antes}")
    comprobar((e.ajustes / "rules.json").exists()
              and not (e.dir / "rules.json").exists(),
              "la configuración acaba en ajustes/")
    comprobar((e.salida / "movimientos_limpios.xlsx").exists(),
              "y las salidas en salida/")
    comprobar((e.datos / "copias" / "historico_20260101_000000.xlsx").exists(),
              "las copias antiguas se conservan")

    respaldos = list((e.datos / "copias").glob("antes_de_migrar_*"))
    comprobar(len(respaldos) == 1, "hace una copia de todo ANTES de mover nada",
              f"{len(respaldos)} respaldos")
    if respaldos:
        guardado = {f.name for f in respaldos[0].iterdir()}
        comprobar("historico.xlsx" in guardado and "rules.json" in guardado,
                  "y en ese respaldo está lo importante", str(sorted(guardado)))

    # y no vuelve a migrar en la siguiente ejecución
    otra = e.ejecutar()
    comprobar("reorganizado" not in otra,
              "la segunda vez ya no dice nada: la mudanza es de una sola vez",
              otra)


@caso("migracion-conflicto", "Si el fichero ya existe en su sitio, no se pisa")
def prueba_migracion_conflicto(e):
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL[:2])
    e.ejecutar()

    # el usuario tenía una copia vieja de rules.json suelta en la raíz
    (e.dir / "rules.json").write_text('{"mercadona": "Otros"}', encoding="utf-8")
    e.vaciar_entrada()
    salida = e.ejecutar()

    comprobar((e.dir / "rules.json").exists(),
              "el fichero viejo de la raíz NO se toca")
    comprobar("rules.json" in salida and "NO los he tocado" in salida,
              "y se avisa de cuál es, para que decida el usuario", salida)
    comprobar(categoria_de(e.historico(), "MERCADONA") == "Comida",
              "manda el de ajustes/, no el viejo de la raíz",
              str(categoria_de(e.historico(), "MERCADONA")))


@caso("semilla", "Una instalación nueva se crea su propia configuración")
def prueba_semilla(e):
    import shutil
    shutil.rmtree(e.ajustes)                      # como recién descomprimido
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL[:2])
    salida = e.ejecutar()

    comprobar("rules.json" in salida and "genéric" in salida,
              "avisa de que ha creado la configuración de partida", salida)
    for f in ("rules.json", "exclude_patterns.json", "categorias.json",
              "sincronizar.json", "mes_contable.json", "cuentas.json"):
        comprobar((e.ajustes / f).exists(), f"se crea {f}")

    comprobar(categoria_de(e.historico(), "MERCADONA") == "Comida",
              "y las reglas de partida ya clasifican lo evidente",
              str(categoria_de(e.historico(), "MERCADONA")))
    comprobar("no cuadran" not in salida,
              "la plantilla de reglas cubre todas las categorías declaradas",
              salida)

    # las plantillas no pueden llevar datos personales de nadie
    texto = (e.ajustes / "exclude_patterns.json").read_text(encoding="utf-8")
    import json as _json
    patrones = [p for p in _json.loads(texto) if not p.startswith("_")]
    comprobar(patrones == [],
              "la plantilla de exclusiones viene vacía, solo con instrucciones",
              str(patrones))


@caso("semilla-respeta", "La semilla no pisa lo que ya hay escrito")
def prueba_semilla_respeta(e):
    e.regla_al_principio("mercadona", "Ocio")     # una regla propia y rara
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL[:2])
    e.ejecutar()

    comprobar(categoria_de(e.historico(), "MERCADONA") == "Ocio",
              "la configuración del usuario sobrevive al arranque",
              str(categoria_de(e.historico(), "MERCADONA")))


@caso("cwd", "Funciona desde cualquier directorio")
def prueba_cwd(e):
    import tempfile as _tmp
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL[:3])
    otro = Path(_tmp.mkdtemp(prefix="otro_sitio_"))
    try:
        e.ejecutar(desde=otro)
        comprobar(e.ruta_historico.exists(),
                  "el histórico va a datos/, no al directorio desde el que se lanza")
        comprobar(not (otro / "historico.xlsx").exists()
                  and not (otro / "datos").exists(),
                  "no ensucia el directorio actual",
                  str([p.name for p in otro.iterdir()]))
        comprobar(len(e.historico()) == 3, "y los datos son los que tocan")
    finally:
        shutil.rmtree(otro, ignore_errors=True)


@caso("sitios", "Cada fichero acaba en su carpeta")
def prueba_sitios(e):
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL)
    e.ejecutar()

    comprobar((e.datos / "historico.xlsx").exists(), "datos/historico.xlsx")
    comprobar((e.salida / "movimientos_limpios.xlsx").exists(),
              "salida/movimientos_limpios.xlsx")
    comprobar((e.salida / "movimientos_excluidos.xlsx").exists(),
              "salida/movimientos_excluidos.xlsx (hay una línea excluida)")
    sueltos = [f.name for f in e.dir.iterdir()
               if f.is_file() and f.suffix in (".xlsx", ".json")]
    comprobar(sueltos == [], "y no queda nada suelto en la raíz", str(sueltos))


@caso("capas", "Tus reglas mandan sobre la base")
def prueba_capas(e):
    datos = [("07/04/2026", "COMPRA MERCADONA MADRID", -100.00),   # solo en la base
             ("09/04/2026", "PEPE GARCIA ALQUILER", -700.00)]      # solo tuya
    fx.escribir_html(e.entrada / "cuenta.xls", datos)
    e.escribir_config("rules.json", {"pepe garcia": "Piso"})
    salida = e.ejecutar()

    df = e.historico()
    comprobar(categoria_de(df, "PEPE GARCIA") == "Piso",
              "una regla tuya que la base no tiene",
              str(categoria_de(df, "PEPE GARCIA")))
    comprobar(categoria_de(df, "MERCADONA") == "Comida",
              "y la base cubre lo que tú no has escrito",
              str(categoria_de(df, "MERCADONA")))
    comprobar("1 tuyas" in salida and "de la base" in salida,
              "dice de dónde salen las reglas activas", salida)


@caso("capas-gana", "Repetir una clave de la base la cambia")
def prueba_capas_gana(e):
    fx.escribir_html(e.entrada / "cuenta.xls",
                     [("07/04/2026", "COMPRA MERCADONA MADRID", -100.00)])
    e.escribir_config("rules.json", {"mercadona": "Otros"})
    e.ejecutar()

    comprobar(categoria_de(e.historico(), "MERCADONA") == "Otros",
              "la tuya gana sin tener que tocar la base",
              str(categoria_de(e.historico(), "MERCADONA")))


@caso("capas-null", "Un null apaga una regla de la base")
def prueba_capas_null(e):
    fx.escribir_html(e.entrada / "cuenta.xls",
                     [("07/04/2026", "NETFLIX.COM", -13.99)])
    e.escribir_config("rules.json", {"netflix": None})
    salida = e.ejecutar()

    comprobar(categoria_de(e.historico(), "NETFLIX") == "Otros",
              "apagada la regla, cae en Otros",
              str(categoria_de(e.historico(), "NETFLIX")))
    comprobar("Apagadas con null" in salida and "netflix" in salida,
              "y se dice cuáles están apagadas", salida)


@caso("capas-categoria", "La base no puede inventar categorías que no tienes")
def prueba_capas_categoria(e):
    # el usuario se queda con menos categorías de las que trae la base
    e.escribir_config("categorias.json", {
        "gastos": ["Comida", "Otros"],
        "ingresos": ["Ingresos"],
        "neutras": ["Transferencias internas"],
        "columna_mes": "mes_ajustado"})
    e.escribir_config("rules.json", {})
    fx.escribir_html(e.entrada / "cuenta.xls",
                     [("07/04/2026", "COMPRA MERCADONA MADRID", -100.00),
                      ("09/04/2026", "MOVISTAR FIBRA", -45.00)])
    salida = e.ejecutar()

    df = e.historico()
    comprobar(categoria_de(df, "MOVISTAR") == "Otros",
              "una regla de la base a «Fibra/movil» se descarta: esa categoría "
              "no existe aquí", str(categoria_de(df, "MOVISTAR")))
    comprobar("descartadas" in salida, "y se dice cuántas", salida)
    comprobar("no cuadran" not in salida,
              "sin inundar de avisos por reglas que no ha escrito el usuario",
              salida)

    res = e.resumen()
    comprobar(abs(res.iloc[0]["Total Gastos"] - 145) < 0.005,
              "y los 45 € siguen contando en el total, en Otros",
              str(res.iloc[0]["Total Gastos"]))


@caso("signo", "Un Bizum recibido no es lo mismo que uno enviado")
def prueba_signo(e):
    datos = [("07/04/2026", "BIZUM A MARTA CENA", -18.00),
             ("09/04/2026", "BIZUM DE MARTA ALQUILER", 350.00)]
    fx.escribir_html(e.entrada / "cuenta.xls", datos)
    e.escribir_config("rules.json",
                      {"bizum": {"+": "Ingresos", "-": "Ocio"}})
    e.ejecutar()

    df = e.historico()
    comprobar(categoria_de(df, "BIZUM A MARTA") == "Ocio",
              "el enviado es gasto", str(categoria_de(df, "BIZUM A MARTA")))
    comprobar(categoria_de(df, "BIZUM DE MARTA") == "Ingresos",
              "el recibido es ingreso", str(categoria_de(df, "BIZUM DE MARTA")))

    res = e.resumen()
    # Las columnas de gasto se muestran en positivo (ver el caso gastos-signo).
    comprobar(abs(res.iloc[0]["Ocio"] - 18) < 0.005,
              "Ocio son 18 € de gasto, no 332 € a favor",
              str(res.iloc[0]["Ocio"]))
    comprobar(abs(res.iloc[0]["Ingresos"] - 350) < 0.005,
              "y los 350 € cuentan como ingreso",
              str(res.iloc[0]["Ingresos"]))


@caso("signo-un-lado", "Una regla de un solo signo deja pasar el otro")
def prueba_signo_un_lado(e):
    datos = [("07/04/2026", "AMAZON EU COMPRA", -75.00),
             ("09/04/2026", "AMAZON EU DEVOLUCION", 75.00)]
    fx.escribir_html(e.entrada / "cuenta.xls", datos)
    e.escribir_config("rules.json", {"amazon": {"-": "Otros"},
                                     "devolucion": "Ingresos"})
    df = None
    e.ejecutar()
    df = e.historico()

    comprobar(categoria_de(df, "AMAZON EU COMPRA") == "Otros",
              "el cargo lo pilla la regla", str(categoria_de(df, "AMAZON EU COMPRA")))
    comprobar(categoria_de(df, "AMAZON EU DEVOLUCION") == "Ingresos",
              "el abono la ignora y sigue buscando más abajo",
              str(categoria_de(df, "AMAZON EU DEVOLUCION")))


@caso("signo-devolucion", "Una devolución normal NO necesita regla de signo")
def prueba_signo_devolucion(e):
    # Que un abono de Mercadona reste de Comida es lo correcto: es la
    # devolución del mismo gasto. El signo solo hace falta cuando el positivo
    # es un concepto distinto del negativo.
    datos = [("07/04/2026", "COMPRA MERCADONA MADRID", -100.00),
             ("09/04/2026", "MERCADONA DEVOLUCION", 30.00)]
    fx.escribir_html(e.entrada / "cuenta.xls", datos)
    e.ejecutar()

    res = e.resumen()
    comprobar(abs(res.iloc[0]["Comida"] - 70) < 0.005,
              "Comida queda en 70 € netos, sin tocar ninguna regla",
              str(res.iloc[0]["Comida"]))


@caso("mes-signo", "El mes contable mira el signo")
def prueba_mes_signo(e):
    datos = [("01/05/2026", "PRESTACION MUTUA", 800.00),
             ("02/05/2026", "RECIBO MUTUA", -95.00)]
    fx.escribir_html(e.entrada / "cuenta.xls", datos)
    e.escribir_config("mes_contable.json",
                      {"dias": 3, "palabras": ["mutua"], "solo_ingresos": True})
    e.escribir_config("rules.json", {"mutua": {"+": "Ingresos", "-": "Higiene"}})
    e.ejecutar()

    df = e.historico()
    comprobar(campo_de(df, "PRESTACION MUTUA", "mes_ajustado") == "2026-04",
              "la prestación que cobras sí se va al mes anterior",
              str(campo_de(df, "PRESTACION MUTUA", "mes_ajustado")))
    comprobar(campo_de(df, "RECIBO MUTUA", "mes_ajustado") == "2026-05",
              "la cuota que pagas NO: es un gasto del mes en que se paga",
              str(campo_de(df, "RECIBO MUTUA", "mes_ajustado")))


@caso("mes-config", "El ajuste de mes se puede afinar y apagar")
def prueba_mes_config(e):
    datos = [("01/05/2026", "NOMINA EMPRESA FICTICIA SL", 2000.00)]
    fx.escribir_html(e.entrada / "cuenta.xls", datos)
    e.escribir_config("mes_contable.json", {"dias": 0, "palabras": ["nomina"]})
    e.ejecutar()

    comprobar(campo_de(e.historico(), "NOMINA", "mes_ajustado") == "2026-05",
              "con dias=0 no se mueve nada",
              str(campo_de(e.historico(), "NOMINA", "mes_ajustado")))


@caso("mes-heredado", "Actualizar no cambia el mes contable de quien ya tenía datos")
def prueba_mes_heredado(e):
    # Antes, «nomina» y «mutua» estaban fijas dentro del código. Al pasar a
    # configuración, quien actualiza no puede perder «mutua» sin enterarse: su
    # prestación del día 1 cambiaría de mes y el resumen bailaría solo.
    (e.ajustes / "mes_contable.json").unlink(missing_ok=True)
    fx.escribir_html(e.entrada / "cuenta.xls",
                     [("05/04/2026", "COMPRA MERCADONA MADRID", -10.00)])
    e.ejecutar()                                   # crea el histórico
    (e.ajustes / "mes_contable.json").unlink(missing_ok=True)

    e.vaciar_entrada()
    fx.escribir_html(e.entrada / "cuenta2.xls",
                     [("01/05/2026", "MUTUA PRESTACION", 1200.00)])
    salida = e.ejecutar()

    cfg = e.leer_config("mes_contable.json")
    comprobar(cfg["palabras"] == ["nomina", "mutua"],
              "al actualizar se conserva la lista de antes", str(cfg["palabras"]))
    comprobar("mes contable" in salida and "no cambien" in salida,
              "y se explica por qué está ahí", salida)
    comprobar(campo_de(e.historico(), "MUTUA", "mes_ajustado") == "2026-04",
              "la prestación sigue contando en el mes de siempre",
              str(campo_de(e.historico(), "MUTUA", "mes_ajustado")))


@caso("mes-nuevo", "Una instalación nueva arranca con la lista genérica")
def prueba_mes_nuevo(e):
    import shutil
    shutil.rmtree(e.ajustes)
    fx.escribir_html(e.entrada / "cuenta.xls",
                     [("05/04/2026", "COMPRA MERCADONA MADRID", -10.00)])
    salida = e.ejecutar()

    cfg = e.leer_config("mes_contable.json")
    comprobar(cfg["palabras"] == ["nomina"],
              "sin histórico previo no hay nada heredado que conservar",
              str(cfg["palabras"]))
    comprobar("no cambien" not in salida,
              "y no se le cuenta al usuario nuevo una historia que no es la suya",
              salida)


@caso("meta", "El histórico lleva grabada la versión que lo escribió")
def prueba_meta(e):
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL[:3])
    e.ejecutar()

    import pandas as pd
    hojas = pd.ExcelFile(e.ruta_historico).sheet_names
    comprobar("_meta" in hojas, "hay hoja _meta", str(hojas))
    comprobar(hojas.index("_meta") == len(hojas) - 1,
              "y va la última, para no estorbar", str(hojas))

    meta = pd.read_excel(e.ruta_historico, sheet_name="_meta")
    datos = dict(zip(meta.iloc[:, 0], meta.iloc[:, 1]))
    esperada = (RAIZ / DIR_APP / "VERSION").read_text(encoding="utf-8").strip()
    comprobar(str(datos.get("version")).strip() == esperada,
              f"la versión coincide con app/VERSION ({esperada})",
              str(datos.get("version")))
    comprobar(str(datos.get("movimientos")).strip() == "3",
              "y cuenta los movimientos", str(datos.get("movimientos")))


@caso("version-arranque", "La versión sale por pantalla al ejecutar")
def prueba_version_arranque(e):
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL[:2])
    salida = e.ejecutar()
    esperada = (RAIZ / DIR_APP / "VERSION").read_text(encoding="utf-8").strip()
    comprobar(esperada in salida.splitlines()[0],
              "en la primera línea: es lo primero que hace falta saber si algo "
              "va mal", salida.splitlines()[0] if salida else "(sin salida)")


@caso("migrar-historico", "Un histórico viejo sin categoria_manual se actualiza")
def prueba_migrar_historico(e):
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL)
    e.ejecutar()
    antes = len(e.historico())

    # se rebaja el fichero a como lo dejaba la versión de antes del versionado:
    # sin hoja _meta y sin la columna categoria_manual
    import pandas as pd
    from openpyxl import load_workbook
    movimientos = pd.read_excel(e.ruta_historico, sheet_name="MOVIMIENTOS")
    movimientos = movimientos.drop(columns=["categoria_manual"])
    with pd.ExcelWriter(e.ruta_historico, engine="openpyxl") as w:
        movimientos.to_excel(w, sheet_name="MOVIMIENTOS", index=False)

    e.vaciar_entrada()
    salida = e.ejecutar()

    comprobar("categoria_manual" in salida and "actualizado" in salida,
              "dice qué migración ha aplicado", salida)
    df = e.historico()
    comprobar(len(df) == antes, "sin perder movimientos",
              f"{len(df)} en vez de {antes}")
    comprobar("categoria_manual" in df.columns, "y la columna vuelve a estar")

    esperada = (RAIZ / DIR_APP / "VERSION").read_text(encoding="utf-8").strip()
    meta = pd.read_excel(e.ruta_historico, sheet_name="_meta")
    datos = dict(zip(meta.iloc[:, 0], meta.iloc[:, 1]))
    comprobar(str(datos.get("version")).strip() == esperada,
              "el fichero queda sellado con la versión actual")

    # y no se repite la migración en la siguiente ejecución
    otra = e.ejecutar()
    comprobar("Histórico actualizado" not in otra,
              "la migración se aplica una sola vez", otra)


@caso("version-futura", "No se toca un histórico escrito por una versión más nueva")
def prueba_version_futura(e):
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL[:3])
    e.ejecutar()

    # alguien lo abrió con una versión posterior y volvió a esta
    import pandas as pd
    movimientos = pd.read_excel(e.ruta_historico, sheet_name="MOVIMIENTOS")
    meta = pd.read_excel(e.ruta_historico, sheet_name="_meta")
    meta.iloc[0, 1] = "99.0.0"
    with pd.ExcelWriter(e.ruta_historico, engine="openpyxl") as w:
        movimientos.to_excel(w, sheet_name="MOVIMIENTOS", index=False)
        meta.to_excel(w, sheet_name="_meta", index=False)
    antes = e.ruta_historico.read_bytes()

    e.vaciar_entrada()
    salida = e.ejecutar()

    comprobar(e.ultimo_codigo != 0, "se planta en vez de escribir")
    comprobar("99.0.0" in salida and "copia" in salida,
              "dice qué versión hace falta y cómo salir del paso", salida)
    comprobar(e.ruta_historico.read_bytes() == antes,
              "y el fichero queda intacto")
    comprobar("Traceback" not in salida, "sin traceback en la cara del usuario",
              salida)


@caso("changelog", "El CHANGELOG documenta la versión que se reparte")
def prueba_changelog(e):
    ruta = RAIZ / "CHANGELOG.md"
    comprobar(ruta.exists(), "existe CHANGELOG.md en la raíz")
    if ruta.exists():
        esperada = (RAIZ / DIR_APP / "VERSION").read_text(encoding="utf-8").strip()
        texto = ruta.read_text(encoding="utf-8")
        comprobar(f"## {esperada}" in texto,
                  f"y tiene una entrada para la versión {esperada}",
                  "no encontrada")


TOKEN_PRIVADO = "ZZPRIVADOZZ"


@caso("exportar", "El ZIP para repartir no lleva datos de nadie")
def prueba_exportar(e):
    import zipfile

    # una carpeta con vida dentro: histórico, salidas, reglas personales
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL)
    e.escribir_config("rules.json", {f"bar {TOKEN_PRIVADO}": "Ocio"})
    e.escribir_config("exclude_patterns.json", [f"recibo {TOKEN_PRIVADO}"])
    e.ejecutar()
    comprobar(e.ruta_historico.exists(), "hay un histórico que proteger")

    e.preparar_exportacion()
    salida = e.exportar()
    comprobar(e.ultimo_codigo == 0, "el exportador termina bien", salida)

    zips = list(e.dir.glob("*.zip"))
    comprobar(len(zips) == 1, "se crea un ZIP", f"{len(zips)} encontrados")
    if not zips:
        return

    with zipfile.ZipFile(zips[0]) as z:
        nombres = z.namelist()
        contenido = b"".join(z.read(n) for n in nombres
                             if not n.lower().endswith(".pdf"))

    prohibidas = [n for n in nombres
                  if n.split("/")[0] in ("datos", "ajustes", "entrada", "salida")]
    comprobar(prohibidas == [],
              "sin datos/, ajustes/, entrada/ ni salida/", str(prohibidas))
    comprobar(TOKEN_PRIVADO.encode() not in contenido,
              "y sin rastro de las reglas personales dentro de ningún fichero")
    excel = [n for n in nombres
             if n.lower().endswith((".xlsx", ".xls", ".csv"))]
    comprobar(excel == [], "ni un solo fichero de datos", str(excel))

    comprobar("app/process.py" in nombres and "app/rules_base.json" in nombres,
              "pero sí el programa entero")
    comprobar(any(n.startswith("app/plantillas/") for n in nombres),
              "y las plantillas de configuración")
    comprobar("GUIA.pdf" in nombres and "CHANGELOG.md" in nombres,
              "más la guía y el changelog")
    comprobar("LICENSE" in nombres, "y la licencia", str(nombres))
    comprobar(not any(".pyc" in n or "__pycache__" in n for n in nombres),
              "sin cachés de Python")

    version = (RAIZ / DIR_APP / "VERSION").read_text(encoding="utf-8").strip()
    comprobar(version in zips[0].name,
              "el nombre del ZIP lleva la versión", zips[0].name)


@caso("exportar-pruebas", "La carpeta pruebas/ solo va si se pide")
def prueba_exportar_pruebas(e):
    import zipfile

    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL[:2])
    e.ejecutar()
    e.preparar_exportacion()
    shutil.copytree(AQUI, e.dir / "pruebas", dirs_exist_ok=True)

    e.exportar()
    with zipfile.ZipFile(next(e.dir.glob("*.zip"))) as z:
        sin = z.namelist()
    comprobar(not any(n.startswith("pruebas/") for n in sin),
              "por defecto no se incluye")

    for z in e.dir.glob("*.zip"):
        z.unlink()
    e.exportar("--con-pruebas")
    with zipfile.ZipFile(next(e.dir.glob("*.zip"))) as z:
        con = z.namelist()
    comprobar(any(n.startswith("pruebas/") for n in con),
              "con --con-pruebas sí")


@caso("exportar-funciona", "Lo exportado arranca en otro ordenador")
def prueba_exportar_funciona(e):
    import tempfile as _tmp
    import zipfile

    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL)
    e.escribir_config("rules.json", {f"bar {TOKEN_PRIVADO}": "Ocio"})
    e.ejecutar()
    e.preparar_exportacion()
    e.exportar()

    destino = Path(_tmp.mkdtemp(prefix="recibido_"))
    try:
        with zipfile.ZipFile(next(e.dir.glob("*.zip"))) as z:
            z.extractall(destino)
        (destino / "entrada").mkdir(exist_ok=True)
        fx.escribir_html(destino / "entrada" / "extracto.xls",
                         [("05/04/2026", "NOMINA EMPRESA FICTICIA SL", 1500.00),
                          ("07/04/2026", "COMPRA CARREFOUR MADRID", -50.00)])

        proc = subprocess.run(
            [sys.executable, os.path.join(DIR_APP, "process.py")], cwd=destino,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=180)
        salida = (proc.stdout or "") + (proc.stderr or "")

        comprobar(proc.returncode == 0, "arranca sin errores", salida)
        comprobar("0 tuyas" in salida,
                  "quien lo recibe empieza sin reglas propias", salida)
        comprobar((destino / "datos" / "historico.xlsx").exists(),
                  "y genera su histórico")

        import pandas as pd
        df = pd.read_excel(destino / "datos" / "historico.xlsx",
                           sheet_name="MOVIMIENTOS")
        comprobar(len(df) == 2, "con sus movimientos", f"{len(df)} filas")
        comprobar(categoria_de(df, "CARREFOUR") == "Comida",
                  "clasificados con las reglas de la base",
                  str(categoria_de(df, "CARREFOUR")))
    finally:
        shutil.rmtree(destino, ignore_errors=True)


@caso("sin-datos-personales", "Ningún fichero repartible lleva datos reales")
def prueba_sin_datos_personales(e):
    """
    Barrido de todo lo que sale de aquí buscando cosas que solo pueden venir de
    un extracto de verdad. Es un cinturón además de los tirantes de exportar.py:
    ahí se controla QUÉ carpetas salen, y aquí QUÉ hay escrito dentro.

    SI ESTE CASO FALLA, mira el token que señala y decide:

      · Es una cadena conocida en toda España (una eléctrica, una cadena de
        supermercados, un banco) -> añádela a app/rules_base.json. Además de
        callar el aviso, mejora la clasificación de quien instale esto.
      · Es una palabra común que has usado como regla y que también aparece en
        el código en otro sentido -> igual: al ponerla en la base deja de
        considerarse tuya.
      · Identifica a alguien o a algún sitio concreto -> es una fuga de verdad.
        Quítala del fichero que se señala y usa un ejemplo inventado.
    """
    import json as _json

    reparto = [RAIZ / DIR_APP, RAIZ / "pruebas"]
    ficheros = []
    for base in reparto:
        ficheros += [f for f in base.rglob("*")
                     if f.is_file() and f.suffix in (".py", ".json", ".txt", ".md")
                     and "__pycache__" not in f.parts]
    ficheros += [RAIZ / "LEEME.txt", RAIZ / "CHANGELOG.md"]

    # Lo que hay escrito en la configuración de este usuario: comercios,
    # personas, los dígitos de su tarjeta.
    #
    # Para saber qué es personal y qué no, se compara con app/rules_base.json:
    # lo que ya está en la base es una cadena conocida en toda España y no
    # identifica a nadie. Así el criterio se mantiene solo cuando la base
    # crezca, en vez de depender de una lista escrita a mano que se queda vieja.
    base = (RAIZ / DIR_APP / "rules_base.json").read_text(encoding="utf-8").lower()

    suyo = set()
    for nombre in ("rules.json", "exclude_patterns.json"):
        ruta = RAIZ / DIR_AJUSTES / nombre
        if not ruta.exists():
            continue
        datos = _json.loads(ruta.read_text(encoding="utf-8"))
        claves = datos if isinstance(datos, list) else datos.keys()
        for k in claves:
            k = str(k)
            if k.startswith("_"):          # comentarios dentro del JSON
                continue
            k = k.lstrip("=~").strip().lower()
            if len(k) < 5 or k.startswith("re:") or k in base:
                continue
            suyo.add(k)

    fugas = []
    for f in ficheros:
        if not f.exists():
            continue
        texto = f.read_text(encoding="utf-8", errors="ignore").lower()
        for token in suyo:
            if token in texto:
                fugas.append(f"{f.relative_to(RAIZ)}: «{token}»")

    comprobar(fugas == [],
              "nada de tu configuración aparece en el código ni en las plantillas",
              "\n".join(sorted(set(fugas))[:12]))


@caso("congelado", "Dentro del .exe, los datos van junto al ejecutable")
def prueba_congelado(e):
    """
    PyInstaller descomprime el programa en una carpeta temporal y deja el .exe
    donde el usuario lo puso. Si rutas.py confundiera las dos, la configuración
    se escribiría en la temporal, Windows la borraría al cerrar y cada
    ejecución empezaría de cero sin que nadie entendiera por qué.

    No hace falta compilar nada para probarlo: basta con fingir las tres
    señales que deja PyInstaller (sys.frozen, sys._MEIPASS y sys.executable).
    """
    guion = (
        "import sys\n"
        "sys.frozen = True\n"
        "sys._MEIPASS = r'{recursos}'\n"
        "sys.executable = r'{exe}'\n"
        "sys.path.insert(0, r'{app}')\n"
        "import rutas\n"
        "print('RAIZ=' + str(rutas.RAIZ))\n"
        "print('HISTORICO=' + str(rutas.HISTORICO))\n"
        "print('BASE=' + str(rutas.REGLAS_BASE))\n"
        "print('PLANTILLAS=' + str(rutas.PLANTILLAS))\n"
    ).format(recursos=str(e.dir / "temporal_de_windows"),
             exe=str(e.dir / "Movimientos.exe"),
             app=str(e.dir / DIR_APP))

    proc = subprocess.run([sys.executable, "-c", guion], capture_output=True,
                          text=True, encoding="utf-8", timeout=60)
    salida = (proc.stdout or "") + (proc.stderr or "")
    valores = dict(l.split("=", 1) for l in proc.stdout.strip().splitlines()
                   if "=" in l)

    comprobar(proc.returncode == 0, "rutas.py arranca en modo congelado", salida)
    comprobar(valores.get("RAIZ") == str(e.dir),
              "la raíz es la carpeta del .exe", valores.get("RAIZ", salida))
    comprobar(valores.get("HISTORICO") == str(e.dir / "datos" / "historico.xlsx"),
              "el histórico va junto al .exe, no a la carpeta temporal",
              valores.get("HISTORICO", salida))
    comprobar("temporal_de_windows" in valores.get("BASE", ""),
              "pero la base de reglas sale de dentro del ejecutable",
              valores.get("BASE", salida))
    comprobar("temporal_de_windows" in valores.get("PLANTILLAS", ""),
              "y las plantillas también", valores.get("PLANTILLAS", salida))


@caso("empaquetado", "La receta de compilación apunta a lo que existe")
def prueba_empaquetado(e):
    spec = RAIZ / "movimientos.spec"
    comprobar(spec.exists(), "hay un movimientos.spec")
    if not spec.exists():
        return
    texto = spec.read_text(encoding="utf-8")

    for recurso in ("rules_base.json", "VERSION", "plantillas"):
        comprobar(recurso in texto, f"empaqueta {recurso}")
        comprobar((RAIZ / DIR_APP / recurso).exists(),
                  f"y {recurso} existe de verdad en app/")
    comprobar("process.py" in texto, "el punto de entrada es process.py")
    comprobar("upx=False" in texto,
              "UPX desactivado: comprimir dispara más falsos positivos")
    comprobar("console=True" in texto,
              "con consola: toda la información sale por pantalla")

    for fichero in ("compilar.bat", "instalar.bat", "requisitos.txt",
                    "COMPILAR.md"):
        comprobar((RAIZ / fichero).exists(), f"existe {fichero}")

    requisitos = (RAIZ / "requisitos.txt").read_text(encoding="utf-8")
    for lib in ("pandas", "openpyxl", "xlrd"):
        comprobar(lib in requisitos, f"requisitos.txt incluye {lib}")


@caso("lanzadores", "Los lanzadores usan el entorno propio si existe")
def prueba_lanzadores(e):
    for nombre in ("ejecutar.bat", "ejecutar.command", "ejecutar.sh",
                   "exportar.bat", "instalar.bat"):
        comprobar((RAIZ / nombre).exists(), f"existe {nombre}")

    bat = (RAIZ / "ejecutar.bat").read_text(encoding="utf-8", errors="ignore")
    comprobar(".venv" in bat and "app\\process.py" in bat,
              "ejecutar.bat prefiere app\\.venv y lanza process.py")
    comprobar("instalar.bat" in bat,
              "y si falta una librería, dice qué ejecutar")

    sh = (RAIZ / "ejecutar.sh").read_text(encoding="utf-8")
    comprobar(".venv/bin/python" in sh and "app/process.py" in sh,
              "y el de Mac hace lo mismo")

    # Si alguien descarga los ficheros de uno en uno se pierden las carpetas y
    # todo queda plano. «python -m venv app\.venv» crea entonces la carpeta app\
    # el solo, y el error que salía después no decía nada útil.
    for nombre in ("instalar.bat", "ejecutar.bat", "exportar.bat",
                   "compilar.bat", "instalar.sh", "ejecutar.sh", "exportar.sh"):
        texto = (RAIZ / nombre).read_text(encoding="utf-8", errors="ignore")
        comprobar("process.py" in texto and "incompleta" in texto,
                  f"{nombre} avisa si la carpeta está incompleta")


# =====================================================================
# EJECUCIÓN
# =====================================================================

def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    casos = [c for c in _casos
             if not FILTROS or any(f.lower() in c[0].lower() for f in FILTROS)]
    if not casos:
        print(f"Ningún caso coincide con {FILTROS}. Disponibles: "
              f"{', '.join(c[0] for c in _casos)}")
        return 1

    print(f"\nProbando la herramienta ({len(casos)} casos)\n" + "=" * 66)
    fallos_totales = 0

    for nombre, descripcion, fn in casos:
        marca = len(_resultados)
        entorno = Entorno(nombre, plano=nombre.startswith("migracion"))
        try:
            fn(entorno)
        except Exception as ex:
            import traceback
            comprobar(False, f"el caso «{nombre}» ha reventado",
                      traceback.format_exc())

        nuevos = _resultados[marca:]
        fallos = [r for r in nuevos if not r[0]]
        fallos_totales += len(fallos)
        icono = "OK  " if not fallos else "FALLA"
        print(f"\n[{icono}] {nombre} — {descripcion}")
        for ok, titulo, detalle in nuevos:
            print(f"    {'·' if ok else 'x'} {titulo}")
            if not ok and detalle:
                sangrado = "\n".join("        " + l
                                     for l in detalle.strip().splitlines()[:14])
                print(sangrado)
        if fallos and CONSERVAR:
            print(f"    carpeta conservada: {entorno.dir}")
        entorno.limpiar()

    total = len(_resultados)
    print("\n" + "=" * 66)
    if fallos_totales:
        print(f"{total - fallos_totales} de {total} comprobaciones bien, "
              f"{fallos_totales} MAL.")
        print("Vuelve a ejecutar con  -v  para conservar las carpetas y mirarlas.")
    else:
        print(f"Las {total} comprobaciones han ido bien.")
    return 1 if fallos_totales else 0


if __name__ == "__main__":
    sys.exit(main())
