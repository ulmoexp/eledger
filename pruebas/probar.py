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
                  "instalar.bat", "instalar.command", "instalar.sh",
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
    def ejecutar(self, desde=None, respuestas=None):
        """`desde` permite lanzarlo con el directorio actual en otro sitio, que
        es justo lo que rutas.py tiene que hacer irrelevante.

        `respuestas`: lo que teclearía una persona en el menú final y el
        asistente, una respuesta por línea. Con ellas el programa se comporta
        como si tuviera a alguien delante (ELEDGER_FORZAR_INTERACTIVO); al
        acabarse, es como pulsar Intro: se cierra."""
        objetivo = (str(self.dir / LANZADOR) if desde
                    else LANZADOR.replace("/", os.sep))
        entorno = None
        if respuestas is not None:
            entorno = dict(os.environ, ELEDGER_FORZAR_INTERACTIVO="1")
        proc = subprocess.run(
            [sys.executable, objetivo], cwd=(desde or self.dir),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=180, input=respuestas, env=entorno)
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
    ("07/04/2026", "COMPRA MERCADONA CENTRO", -100.00),
    ("09/04/2026", "MEDIA MARKT ONLINE", -200.00),
    ("11/04/2026", "SUPERMERCADOS DIA CENTRO", -50.00),
    ("13/04/2026", "GUARDIA CIVIL MULTA", -30.00),
    ("15/04/2026", "CESTA DE NAVIDAD", -20.00),
    ("17/04/2026", "BARCELONA HOTEL", -300.00),
    ("19/04/2026", "QBP ASESORES", -10.00),
    ("21/04/2026", "SEGURO DE VIDA MAPFRE", -40.00),
    ("23/04/2026", "LIQUIDACION TARJETA CREDITO", -500.00),
    ("25/04/2026", "REPSOL E.S. AVENIDA", -60.00),
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
                     [("07/04/2026", "COMPRA MERCADONA CENTRO", -10.00)])
    fx.escribir_xml_ss(e.entrada / "tarjeta_xml.xls",
                       [("07/04/2026", "COMPRA CARREFOUR CENTRO", -10.00)])
    fx.escribir_csv(e.entrada / "cuenta_csv.xls",
                    [("07/04/2026", "COMPRA LIDL CENTRO", -10.00)])
    fx.escribir_xlsx(e.entrada / "cuenta_xlsx.xls",
                     [("07/04/2026", "COMPRA AHORRAMAS CENTRO", -10.00)])

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
    uno = [("07/04/2026", "COMPRA MERCADONA CENTRO", -10.00)]
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
        "QBP ASESORES": "Otros",     # contiene 'bp'   -> NO es Transporte
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
    # la liquidación de la tarjeta (-500) está excluida: no es gasto, pero
    # el banco sí la cargó. El Acumulado es lo que hay en la cuenta.
    comprobar(abs(f["Fuera del balance"] + 500) < 0.005,
              "Fuera del balance = -500 (lo excluido que sí salió de la cuenta)",
              str(f["Fuera del balance"]))
    comprobar(abs(f["Acumulado"] - 690) < 0.005,
              "Acumulado = +690 (1190 de balance - 500 excluidos)",
              str(f["Acumulado"]))
    comprobar("Deuda" not in res.columns and "Extras" not in res.columns,
              "sin las columnas Deuda y Extras (quitadas en la 2.12.0)",
              str(list(res.columns)))


@caso("saldo-inicial", "El Acumulado parte del saldo real de la cuenta, no de 0")
def prueba_saldo_inicial(e):
    # escribir_html simula el saldo real de la cuenta partiendo de 5000 € y
    # aplicando cada movimiento en el orden dado (ver fixtures.py).
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL[:3])   # nomina + 2 compras
    salida = e.ejecutar()
    res = e.resumen()

    comprobar("Saldo inicial detectado" in salida and "5.000,00" in salida,
              "lo dice por pantalla", salida)

    f = res.iloc[0]
    balance = float(f["Balance"])
    comprobar(abs(f["Acumulado"] - (5000 + balance)) < 0.005,
              "Acumulado = saldo inicial + balance del mes, no solo el balance",
              str(f["Acumulado"]))
    comprobar("Cuadra con el banco" in salida,
              "y comprueba que acaba donde dice el extracto", salida)


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
    # regresión del piloto: aun así se llamaba «saldo al cierre del mes»
    comprobar("el Acumulado no es tu saldo" in salida
              and "Acumulado (desde el primer movimiento)" in salida
              and "saldo al cierre" not in salida,
              "avisa de que el Acumulado no es su saldo, y no lo llama así", salida)


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
    comprobar("Saldo inicial detectado: 5.000,00" in salida,
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
    igual = [("07/04/2026", "COMPRA MERCADONA CENTRO", -10.00)]
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
    igual = [("07/04/2026", "COMPRA MERCADONA CENTRO", -10.00)]
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
                     [("05/04/2026", "COMPRA MERCADONA CENTRO", -100.00)])
    fx.escribir_html(e.entrada / "ahorro_042026.xls",
                     [("05/04/2026", "TRASPASO DESDE PRINCIPAL", 200.00)])
    salida = e.ejecutar()
    res = e.resumen()

    comprobar("Saldo inicial detectado en 2 cuentas" in salida, "avisa de las dos",
              salida)
    comprobar("principal: 5.000,00" in salida and "ahorro: 5.000,00" in salida,
              "cada una con SU PROPIO saldo (5000 €, fijado por fixtures.py)",
              salida)
    # 5000+5000 de saldo inicial, -100 de gasto y +200 que entran en ahorro.
    # El traspaso es neutro (no es ingreso, ver rules_base), pero la salida
    # de principal no está en estos datos: en los dos bancos hay 10100 €, y
    # eso es lo que tiene que decir el Acumulado (hasta la 2.11 decía 9900).
    comprobar(abs(res.iloc[0]["Acumulado"] - 10100) < 0.005,
              "el Acumulado combinado es la suma de los saldos reales de las dos",
              str(res.iloc[0]["Acumulado"]))


@caso("acumulado-saldo-real", "El Acumulado acaba en el saldo real del banco")
def prueba_acumulado_saldo_real(e):
    # regresión: hasta la 2.11 el Acumulado era saldo inicial + suma de
    # Balances, y se despegaba del banco con cada traspaso a una cuenta que
    # no está aquí (neutro), cada excluido y el desfase de la tarjeta (la
    # compra cuenta el mes que se hace; el recibo, excluido, llega después).
    # Con estos datos daba 6470 € con 1550 € en la cuenta.
    cuenta = [("02/04/2026", "NOMINA EMPRESA SL", 2000.00),
              ("10/04/2026", "COMPRA MERCADONA CENTRO", -100.00),
              ("15/04/2026", "TRASPASO A CUENTA AHORRO", -5000.00),
              ("05/05/2026", "LIQUIDACION TARJETA CREDITO", -300.00),
              ("12/05/2026", "COMPRA MERCADONA CENTRO", -50.00),
              ("08/06/2026", "TRASPASO A CUENTA AHORRO", -100.00)]
    fx.escribir_html(e.entrada / "cuenta.xls", cuenta)
    fx.escribir_xml_ss(e.entrada / "tarjeta.xls",
                       [("20/04/2026", "COMPRA A", -300.00),
                        ("20/05/2026", "COMPRA B", -80.00)], tarjeta=True)
    salida = e.ejecutar()
    res = e.resumen()

    saldo_real = 5000 + sum(i for _, _, i in cuenta)       # 5000 lo fija fixtures
    comprobar(abs(res.iloc[-1]["Acumulado"] - saldo_real) < 0.005,
              f"el último Acumulado es el saldo real ({saldo_real:.2f})",
              str(res.iloc[-1]["Acumulado"]))
    comprobar("2026-06" in set(res["Mes"]),
              "un mes con solo un traspaso también sale: la cuenta se movió",
              str(list(res["Mes"])))

    anterior = 5000.0
    cuadran = True
    for _, f in res.iterrows():
        if abs(anterior + f["Balance"] + f["Fuera del balance"] - f["Acumulado"]) >= 0.005:
            cuadran = False
        anterior = f["Acumulado"]
    comprobar(cuadran, "cada fila cuadra: anterior + Balance + Fuera del balance",
              res.to_string())
    comprobar("Cuadra con el banco" in salida and "No cuadra" not in salida,
              "y lo confirma por pantalla contra el saldo del extracto", salida)


@caso("cuadre-hueco", "Si falta un extracto en medio, dice dónde y por cuánto")
def prueba_cuadre_hueco(e):
    fx.escribir_html(e.entrada / "cuenta_abril.xls",
                     [("02/04/2026", "NOMINA EMPRESA SL", 2000.00),
                      ("10/04/2026", "COMPRA MERCADONA CENTRO", -100.00)])
    # el extracto de junio trae el saldo REAL, que incluye 800 € de un mayo
    # que no se ha descargado: 5000 + 2000 - 100 + 800 - 50
    ruta = e.entrada / "cuenta_junio.xls"
    fx.escribir_html(ruta, [("10/06/2026", "COMPRA MERCADONA CENTRO", -50.00)])
    html = ruta.read_bytes().decode("cp1252").replace("4.950,00", "7.650,00")
    ruta.write_bytes(html.encode("cp1252"))
    salida = e.ejecutar()

    comprobar("No cuadra con el banco" in salida,
              "avisa de que el cálculo y el banco no coinciden", salida)
    comprobar("10/06/2026: +800,00" in salida,
              "dice en qué fecha aparece la diferencia y de cuánto es", salida)
    comprobar(e.ultimo_codigo == 0, "es un aviso, no un error: el resto sale igual",
              salida)


@caso("orden-resumen-retiradas", "Deuda o Extras en orden_resumen: avisa de que ya no existen")
def prueba_orden_resumen_retiradas(e):
    e.escribir_config("categorias.json", {
        "gastos": ["Comida", "Otros"],
        "ingresos": ["Ingresos"],
        "neutras": ["Transferencias internas"],
        "columna_mes": "mes_ajustado",
        "orden_resumen": ["Mes", "Comida", "Deuda", "Extras", "Balance", "Acumulado"]})
    e.escribir_config("rules.json", {"mercadona": "Comida", "nomina": "Ingresos"})
    fx.escribir_html(e.entrada / "cuenta.xls",
                     [("07/04/2026", "COMPRA MERCADONA CENTRO", -100.00)])
    salida = e.ejecutar()

    comprobar("«Deuda» en orden_resumen ya no existe" in salida
              and "«Extras» en orden_resumen ya no existe" in salida,
              "explica que se han quitado, en vez de tomarlas por una errata", salida)
    comprobar(list(e.resumen().columns) == ["Mes", "Comida", "Balance", "Acumulado"],
              "y el resumen sale igual, sin ellas", str(list(e.resumen().columns)))


@caso("historico-abierto", "Con el histórico abierto, el resultado va a una copia y no falla")
def prueba_historico_abierto(e):
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL[:3])
    e.ejecutar()
    antes = len(e.historico())
    copias_antes = len(list((e.datos / "copias").glob("*.xlsx")))

    # lo que deja OnlyOffice o LibreOffice al lado mientras lo tiene abierto.
    # Aquí no hay nadie delante para contestar, así que va directo a copia.
    (e.datos / ".~lock.historico.xlsx#").write_text("bloqueo")
    fx.escribir_html(e.entrada / "cuenta2.xls",
                     [("20/04/2026", "COMPRA MERCADONA CENTRO", -10.00)])
    salida = e.ejecutar()

    comprobar(e.ultimo_codigo == 0, "no falla", salida)
    copias = list(e.datos.glob("historico (copia *).xlsx"))
    comprobar(len(copias) == 1, "deja el resultado en una copia al lado",
              str(list(e.datos.iterdir())))
    comprobar(len(e.historico()) == antes,
              "el histórico de verdad no se toca (lo tiene otro programa)",
              f"{len(e.historico())} filas en vez de {antes}")
    if copias:
        import pandas as pd
        en_copia = pd.read_excel(copias[0], sheet_name="MOVIMIENTOS")
        comprobar(len(en_copia) == antes + 1, "y la copia sí lleva lo nuevo",
                  f"{len(en_copia)} filas")
    comprobar(len(list((e.datos / "copias").glob("*.xlsx"))) == copias_antes,
              "sin copia de seguridad: no se ha tocado nada que respaldar")
    comprobar("NO se ha actualizado" in salida,
              "avisa de que el histórico de verdad sigue sin actualizar", salida)

    # cerrado ya, la siguiente ejecución lo pone al día: nada se ha perdido
    (e.datos / ".~lock.historico.xlsx#").unlink()
    e.ejecutar()
    comprobar(len(e.historico()) == antes + 1,
              "al cerrarlo y volver a ejecutar, el histórico se pone al día",
              f"{len(e.historico())} filas")


@caso("historico-abierto-excel", "También se detecta el fichero de bloqueo de Excel")
def prueba_historico_abierto_excel(e):
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL[:3])
    e.ejecutar()
    (e.datos / "~$historico.xlsx").write_text("bloqueo")
    salida = e.ejecutar()
    comprobar(e.ultimo_codigo == 0 and "estaba abierto" in salida,
              "lo detecta y guarda en copia", salida)


@caso("limpios-abierto", "Si solo está abierto movimientos_limpios, el histórico se guarda normal")
def prueba_limpios_abierto(e):
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL[:3])
    e.ejecutar()
    (e.salida / ".~lock.movimientos_limpios.xlsx#").write_text("bloqueo")
    fx.escribir_html(e.entrada / "cuenta2.xls",
                     [("20/04/2026", "COMPRA MERCADONA CENTRO", -10.00)])
    salida = e.ejecutar()

    comprobar(len(e.historico()) == 4, "el histórico se actualiza como siempre",
              f"{len(e.historico())} filas")
    comprobar(len(list(e.salida.glob("movimientos_limpios (copia *).xlsx"))) == 1,
              "lo que estaba abierto va a una copia", str(list(e.salida.iterdir())))
    comprobar(not list(e.datos.glob("historico (copia *).xlsx")),
              "y el histórico no se duplica", str(list(e.datos.iterdir())))
    comprobar("NO se ha actualizado" not in salida,
              "sin el aviso del histórico, que sí está al día", salida)


@caso("cuadre-intermedio", "Si al final cuadra pero no por el camino, no dice «no cuadra»")
def prueba_cuadre_intermedio(e):
    # fixtures.py calcula el saldo en el orden de la lista: con el día 15
    # detrás del 20, el saldo del banco de esos dos días no casa con el
    # calculado, pero el del último día sí
    fx.escribir_html(e.entrada / "cuenta.xls",
                     [("10/04/2026", "COMPRA MERCADONA CENTRO", -10.00),
                      ("20/04/2026", "REPSOL E.S. AVENIDA", -20.00),
                      ("15/04/2026", "CINE YELMO", -5.00),
                      ("25/04/2026", "COMPRA MERCADONA CENTRO", -7.00)])
    salida = e.ejecutar()

    comprobar("Al final cuadra con el banco" in salida,
              "dice que al final cuadra", salida)
    comprobar("No cuadra con el banco" not in salida,
              "y no que no cuadre: las dos cifras serían la misma", salida)
    comprobar("se separa del saldo del banco" in salida,
              "pero avisa de las fechas en que se separa", salida)


@caso("nomina-antes-que-gasto", "Una nómina de un colegio o de Mercadona es ingreso, no gasto")
def prueba_nomina_antes_que_gasto(e):
    # regresión del piloto de usuarios (2.12.0): los ingresos iban al final
    # de la base, y «colegio» (Hijos) o «mercadona» (Comida) se llevaban la
    # nómina antes. Resultado: Ingresos 0 y un gasto en negativo, sin aviso.
    fx.escribir_html(e.entrada / "cuenta.xls",
                     [("01/04/2026", "NOMINA COLEGIO EJEMPLO", 1650.00),
                      ("02/04/2026", "NOMINA MERCADONA SA", 1200.00),
                      ("10/04/2026", "RECIBO COLEGIO EJEMPLO", -90.00),
                      ("12/04/2026", "COMPRA MERCADONA CENTRO", -60.00)])
    e.ejecutar()
    df = e.historico().set_index("descripcion")

    comprobar(df.at["NOMINA COLEGIO EJEMPLO", "categoria"] == "Ingresos"
              and df.at["NOMINA MERCADONA SA", "categoria"] == "Ingresos",
              "las dos nóminas son ingresos", str(df["categoria"].to_dict()))
    comprobar(df.at["RECIBO COLEGIO EJEMPLO", "categoria"] == "Hijos"
              and df.at["COMPRA MERCADONA CENTRO", "categoria"] == "Comida",
              "y los gastos de esos mismos sitios siguen donde estaban",
              str(df["categoria"].to_dict()))


@caso("ingreso-sin-regla", "Lo que entra sin regla va a Ingresos, no resta de los gastos")
def prueba_ingreso_sin_regla(e):
    # regresión del piloto: un cobro sin regla caía en «Otros», que es de
    # gasto, y dejaba el mes con gastos negativos
    fx.escribir_html(e.entrada / "cuenta.xls",
                     [("03/04/2026", "TRANSF DE ESTUDIO EJEMPLO FACTURA 12", 1210.00),
                      ("05/04/2026", "COMPRA MERCADONA CENTRO", -60.00),
                      ("07/04/2026", "TIENDA DESCONOCIDA SL", -40.00)])
    salida = e.ejecutar()
    f = e.resumen().iloc[0]
    df = e.historico().set_index("descripcion")

    comprobar(df.at["TRANSF DE ESTUDIO EJEMPLO FACTURA 12", "categoria"] == "Ingresos",
              "el cobro sin regla es un ingreso", str(df["categoria"].to_dict()))
    comprobar(df.at["TIENDA DESCONOCIDA SL", "categoria"] == "Otros",
              "un gasto sin regla sigue yendo a Otros", str(df["categoria"].to_dict()))
    comprobar(abs(f["Total Gastos"] - 100) < 0.005 and abs(f["Ingresos"] - 1210) < 0.005,
              "gastos 100 e ingresos 1210, nada en negativo",
              f"{f['Total Gastos']} / {f['Ingresos']}")
    comprobar("Sin clasificar" in salida and "ESTUDIO" in salida,
              "y sigue saliendo en «Sin clasificar», para ponerle regla", salida)


@caso("cuentas-declaradas-tarde", "Declarar cuentas.json después no duplica el histórico")
def prueba_cuentas_declaradas_tarde(e):
    # regresión del piloto: las filas viejas se quedaban sin cuenta y las
    # mismas, releídas, entraban con cuenta: todo sumaba el doble
    fx.escribir_html(e.entrada / "negocio_2026.xls",
                     [("05/04/2026", "COMPRA MERCADONA CENTRO", -100.00)])
    fx.escribir_html(e.entrada / "personal_2026.xls",
                     [("06/04/2026", "COMPRA MERCADONA CENTRO", -30.00)])
    e.ejecutar()
    antes = len(e.historico())

    e.escribir_config("cuentas.json", {"negocio": "negocio", "personal": "personal"})
    salida = e.ejecutar()
    df = e.historico()

    comprobar(len(df) == antes, "los mismos movimientos, no el doble",
              f"{len(df)} en vez de {antes}")
    comprobar(set(df["cuenta"].fillna("")) == {"negocio", "personal"},
              "y cada uno con su cuenta", str(set(df["cuenta"])))
    comprobar("asignados a su cuenta" in salida, "lo dice por pantalla", salida)
    comprobar(abs(e.resumen().iloc[0]["Total Gastos"] - 130) < 0.005,
              "los gastos no se duplican", str(e.resumen().iloc[0]["Total Gastos"]))


@caso("cuentas-cura-duplicados", "Un histórico ya duplicado así se arregla solo")
def prueba_cuentas_cura_duplicados(e):
    # el estado que dejaba la 2.12.0: cada fila dos veces, una sin cuenta y
    # otra con ella. Se fabrica a mano sobre el histórico.
    fx.escribir_html(e.entrada / "negocio_2026.xls",
                     [("05/04/2026", "COMPRA MERCADONA CENTRO", -100.00),
                      ("08/04/2026", "COMPRA LIDL", -20.00)])
    e.ejecutar()
    import pandas as pd
    mov = pd.read_excel(e.ruta_historico, sheet_name="MOVIMIENTOS")
    copia = mov.copy()
    copia["cuenta"] = "negocio"
    # la corrección manual está en la copia VIEJA: es la que debe quedarse
    mov["categoria_manual"] = mov["categoria_manual"].astype(object)
    mov.loc[0, "categoria_manual"] = "Otros"
    with pd.ExcelWriter(e.ruta_historico, engine="openpyxl") as w:
        pd.concat([mov, copia]).to_excel(w, sheet_name="MOVIMIENTOS", index=False)

    e.escribir_config("cuentas.json", {"negocio": "negocio"})
    salida = e.ejecutar()
    df = e.historico()

    comprobar(len(df) == 2, "vuelven a ser dos movimientos", f"{len(df)} filas")
    comprobar("repetidos" in salida, "y dice que ha quitado los repetidos", salida)
    comprobar((df["categoria_manual"].fillna("") == "Otros").sum() == 1,
              "sin perder la corrección manual", str(df["categoria_manual"].tolist()))


@caso("guion-e-impuestos", "BASIC-FIT casa con «basic fit», y los pagos a Hacienda van a Impuestos")
def prueba_guion_e_impuestos(e):
    fx.escribir_html(e.entrada / "cuenta.xls",
                     [("03/04/2026", "RECIBO BASIC-FIT", -29.99),
                      ("10/04/2026", "AEAT MODELO 303 IVA 1T", -612.30),
                      ("20/04/2026", "DEVOLUCION AEAT RENTA 2025", 320.00)])
    e.ejecutar()
    df = e.historico().set_index("descripcion")

    comprobar(df.at["RECIBO BASIC-FIT", "categoria"] == "Ocio",
              "el guion no impide que case la regla con espacio",
              str(df["categoria"].to_dict()))
    comprobar(df.at["AEAT MODELO 303 IVA 1T", "categoria"] == "Impuestos"
              and df.at["DEVOLUCION AEAT RENTA 2025", "categoria"] == "Ingresos",
              "lo que se paga a Hacienda es Impuestos; lo que devuelve, ingreso",
              str(df["categoria"].to_dict()))
    comprobar(abs(e.resumen().iloc[0]["Impuestos"] - 612.30) < 0.005,
              "y tiene su columna en el resumen", str(list(e.resumen().columns)))


@caso("importes-formato", "Los importes de la pantalla van en formato español")
def prueba_importes_formato(e):
    # 5000 € de saldo inicial (lo fija fixtures.py) y una nómina de 2000 €:
    # con el formato de Python saldrían «5,000.00» y «2,000.00», al revés de
    # como los escribe cualquier banco español
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL[:1])
    salida = e.ejecutar()

    comprobar("5.000,00 €" in salida and "2.000,00 €" in salida,
              "miles con punto y decimales con coma", salida)
    comprobar("5,000.00" not in salida and "2,000.00" not in salida,
              "ni rastro del formato inglés", salida)
    comprobar("(1 mes)" in salida, "y «1 mes», no «1 meses»", salida)


@caso("gastos-signo", "Una devolución sale en negativo, no disfrazada de gasto")
def prueba_signo(e):
    # Comida: -100 de compra y +150 de devolución -> la categoría acaba a favor.
    # Debe salir como -50, NO como +50 (eso es lo que hacía ABS()).
    datos = [("07/04/2026", "COMPRA MERCADONA CENTRO", -100.00),
             ("09/04/2026", "DEVOLUCION MERCADONA CENTRO", 150.00)]
    fx.escribir_html(e.entrada / "cuenta.xls", datos)
    e.ejecutar()
    res = e.resumen()

    comprobar(abs(res.iloc[0]["Comida"] + 50) < 0.005,
              "Comida sale a -50, no a +50", str(res.iloc[0]["Comida"]))


@caso("dedup", "Dos descargas que se solapan no duplican movimientos")
def prueba_dedup(e):
    abril = ABRIL[:5]
    abril_y_mayo = ABRIL[:5] + [("03/05/2026", "COMPRA LIDL CENTRO", -25.00)]

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
    datos = [("07/04/2026", "COMPRA MERCADONA CENTRO", -10.00),
             ("07/04/2026", "COMPRA MERCADONA CENTRO", -10.00)]
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
    datos = [("07/04/2026", "PAGO TARJ 000456 ACADEMIA IDIOMAS", -15.00),
             ("08/04/2026", "PAGO TARJ 000456 ACADEMIA IDIOMAS", -15.00),
             ("09/04/2026", "PAGO TARJ 000456 ACADEMIA IDIOMAS", -15.00)]
    fx.escribir_html(e.entrada / "cuenta.xls", datos)
    salida = e.ejecutar()

    comprobar('"pago"' not in salida and '"tarj"' not in salida
              and '"000456"' not in salida,
              "ni el relleno del banco ni el número de referencia se sugieren",
              salida)
    comprobar('"academia": "PON_TU_CATEGORIA"' in salida
              or '"idiomas": "PON_TU_CATEGORIA"' in salida,
              "y sí una palabra de verdad del concepto", salida)


@caso("informe-vacio", "Sin nada sin clasificar, el informe no se muestra")
def prueba_informe_vacio(e):
    datos = [("07/04/2026", "COMPRA MERCADONA CENTRO", -10.00),
             ("09/04/2026", "COMPRA CARREFOUR CENTRO", -10.00)]
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
    comprobar("2026-04" in salida and "95,30 €" in salida,
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

    comprobar("2026-04" in salida and "40,00 €" in salida,
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


# --- el asistente del menú final (2.15.0) ---------------------------------
# Escribe en ajustes/ por la persona lo que el informe le decía que pegara.
# Se le contesta por la entrada estándar (ver Entorno.ejecutar). Datos
# inventados que no casan con ninguna regla de la base: un comercio del que
# sale dinero (zafiro) y un cliente del que entra (yodo).
SIN_CLASIFICAR = [("02/04/2026", "COMPRA ZAFIRO TIENDA", -40.00),
                  ("09/04/2026", "COMPRA ZAFIRO TIENDA", -35.00),
                  ("10/04/2026", "ABONO YODO CLIENTE", 120.00)]
# en el menú: 1 histórico, 2 carpeta, 3 clasificar lo que falta, 4 de nuevo.
# En «¿En qué categoría va?», con las categorías de la plantilla, lo que sale
# ofrece los 12 gastos + la neutra (6 = Comida) y lo que entra, Ingresos +
# la neutra (1 = Ingresos).


@caso("asistente-regla", "El asistente escribe en rules.json la regla elegida y se aplica")
def prueba_asistente_regla(e):
    fx.escribir_html(e.entrada / "cuenta.xls", SIN_CLASIFICAR)
    antes = (e.ajustes / "rules.json").read_text(encoding="utf-8")
    # 3: clasificar · 6: zafiro a Comida · 1: yodo a Ingresos · Intro: aplicarlo ya
    salida = e.ejecutar(respuestas="3\n6\n1\n\n")

    reglas = e.leer_config("rules.json")
    comprobar(reglas.get("zafiro") == "Comida",
              "lo que sale queda como regla fija", reglas)
    comprobar(reglas.get("yodo") == {"+": "Ingresos"},
              "lo que entra queda solo para el lado + (como la sugerencia)", reglas)
    comprobar(list(reglas)[:len(json.loads(antes))] == list(json.loads(antes)),
              "conserva los comentarios y el orden de lo que había, y añade al final",
              list(reglas))
    comprobar(salida.count("── Sin clasificar") == 1,
              "tras «¿Lo hago ya?» vuelve a ejecutar y ya no queda nada sin clasificar",
              salida)
    df = e.historico()
    zafiro = set(df.loc[df["descripcion"].str.contains("ZAFIRO"), "categoria"])
    comprobar(zafiro == {"Comida"},
              "y el histórico ya los clasifica con la regla nueva", zafiro)
    copias = list((e.datos / "copias").glob("rules_*.json"))
    comprobar(len(copias) == 1 and copias[0].read_text(encoding="utf-8") == antes,
              "deja en datos/copias/ el rules.json tal como estaba",
              [c.name for c in copias])


@caso("asistente-solo-declaradas", "El asistente solo deja elegir categorías declaradas")
def prueba_asistente_solo_declaradas(e):
    fx.escribir_html(e.entrada / "cuenta.xls", SIN_CLASIFICAR)
    antes = (e.ajustes / "rules.json").read_bytes()
    # 3: clasificar · 99 y «Comida» escrito a mano no valen · 0: terminar
    salida = e.ejecutar(respuestas="3\n99\nComida\n0\n")

    comprobar("13 Transferencias internas" in salida and " 14 " not in salida,
              "ofrece justo las categorías de categorias.json, numeradas", salida)
    comprobar(salida.count("Escribe un número del 1 al 13") == 2,
              "un número fuera de rango o un nombre escrito vuelven a preguntar", salida)
    comprobar((e.ajustes / "rules.json").read_bytes() == antes,
              "sin una elección válida no se escribe nada")


@caso("asistente-saltar", "Intro salta un grupo y 0 termina, sin escribir nada")
def prueba_asistente_saltar(e):
    fx.escribir_html(e.entrada / "cuenta.xls", SIN_CLASIFICAR)
    antes = (e.ajustes / "rules.json").read_bytes()
    salida = e.ejecutar(respuestas="3\n\n0\n")

    comprobar("Saltado." in salida, "Intro salta el grupo", salida)
    comprobar((e.ajustes / "rules.json").read_bytes() == antes,
              "saltar y terminar no escriben nada")
    comprobar("¿Lo hago ya?" not in salida,
              "sin cambios, no ofrece volver a ejecutar para aplicarlos", salida)
    comprobar("Clasificar lo que falta  (1 grupo)" in salida,
              "el grupo al que no se ha llegado sigue en el menú", salida)


@caso("asistente-exclusion", "El asistente añade el recibo de la tarjeta a exclude_patterns.json")
def prueba_asistente_exclusion(e):
    e.escribir_config("exclude_patterns.json", [])
    tarjeta = [("05/04/2026", "COMPRA A", -50.00),
              ("12/04/2026", "COMPRA B", -30.25),
              ("20/04/2026", "COMPRA C", -15.05)]     # total -95.30
    fx.escribir_xml_ss(e.entrada / "tarjeta.xls", tarjeta, tarjeta=True)
    cuenta = [("01/04/2026", "NOMINA EMPRESA FICTICIA SL", 2000.00),
             ("05/05/2026", "LIQUIDACION TARJETA VISA 778899", -95.30)]
    fx.escribir_html(e.entrada / "cuenta.xls", cuenta, cabecera_saldo=True)

    # menú: 1 histórico, 2 carpeta, 3 excluir el recibo, 4 de nuevo.
    # Intro en la pregunta es NO: es lo que se pulsa por costumbre para cerrar
    e.ejecutar(respuestas="3\n\n")
    comprobar(e.leer_config("exclude_patterns.json") == [],
              "Intro no escribe: hay que decir que sí")

    salida = e.ejecutar(respuestas="3\ns\n\n")
    comprobar(e.leer_config("exclude_patterns.json") == ["liquidacion tarjeta visa"],
              "con «s» añade la clave segura que proponía el aviso",
              e.leer_config("exclude_patterns.json"))
    comprobar(salida.count("ningún patrón en") == 1,
              "y al volver a ejecutar ya no avisa de la tarjeta", salida)
    comprobar(bool(campo_de(e.historico(), "LIQUIDACION", "excluido")),
              "el recibo queda excluido de los totales")


@caso("asistente-exclusion-sin-clave", "Sin clave segura, el asistente deja escribirla y enseña qué excluiría")
def prueba_asistente_exclusion_sin_clave(e):
    # El caso de la vida real: lo que paga la cuenta no cuadra con lo que suma la
    # tarjeta (comisiones, otro periodo), así que el detector no lo
    # encuentra. Antes solo quedaba editar el JSON a mano.
    e.escribir_config("exclude_patterns.json", [])
    tarjeta = [("05/04/2026", "COMPRA A", -50.00),
              ("12/04/2026", "COMPRA B", -30.25),
              ("20/04/2026", "COMPRA C", -15.05)]     # total -95.30
    fx.escribir_xml_ss(e.entrada / "tarjeta.xls", tarjeta, tarjeta=True)
    cuenta = [("01/04/2026", "NOMINA EMPRESA FICTICIA SL", 2000.00),
             ("05/05/2026", "PAGO TARJETA CREDITO 4567", -100.00)]
    fx.escribir_html(e.entrada / "cuenta.xls", cuenta, cabecera_saldo=True)

    # menú: 1 histórico, 2 carpeta, 3 excluir el recibo, 4 de nuevo.
    # «zz» es demasiado corto; «nada parecido» no casa con nada; Intro: dejarlo
    salida = e.ejecutar(respuestas="3\no\nzz\nnada parecido\n\n")
    comprobar("Excluir el recibo de la tarjeta" in salida,
              "la opción sale aunque el detector no haya dado con el recibo", salida)
    comprobar("PAGO TARJETA CREDITO 4567" in salida.split("El pago de la tarjeta")[-1],
              "enseña lo que parece el recibo (la pista de «Sin clasificar»)", salida)
    comprobar("demasiado corto" in salida and "no coincide con ningún movimiento" in salida,
              "un texto muy corto o que no casa con nada no se acepta", salida)
    comprobar(e.leer_config("exclude_patterns.json") == [],
              "dejarlo no escribe nada")

    # O: probar otro texto · lo escribe la persona · S: añadirlo · Intro: aplicarlo
    salida = e.ejecutar(respuestas="3\no\nPago tarjeta crédito\ns\n\n")
    comprobar("excluiría 1 movimiento:" in salida
              and "Comprueba que todos son ese pago" in salida,
              "antes de añadirlo enseña qué excluiría y pide comprobarlo", salida)
    comprobar(e.leer_config("exclude_patterns.json") == ["pago tarjeta credito"],
              "escribe lo tecleado, en minúsculas y sin tildes",
              e.leer_config("exclude_patterns.json"))
    comprobar(bool(campo_de(e.historico(), "PAGO TARJETA", "excluido")),
              "y al volver a ejecutar el recibo queda excluido")


@caso("asistente-exclusion-insegura", "Con una clave que excluiría de más, la enseña y avisa antes de nada")
def prueba_asistente_exclusion_insegura(e):
    e.escribir_config("exclude_patterns.json", [])
    tarjeta = [("05/04/2026", "COMPRA A", -50.00),
              ("12/04/2026", "COMPRA B", -30.25)]     # total -80.25
    fx.escribir_xml_ss(e.entrada / "tarjeta.xls", tarjeta, tarjeta=True)
    # el recibo y otro cargo que comparten la parte fija del concepto
    cuenta = [("01/04/2026", "NOMINA EMPRESA FICTICIA SL", 2000.00),
             ("05/05/2026", "LIQUIDACION TARJETA VISA 778899", -80.25),
             ("09/05/2026", "LIQUIDACION TARJETA VISA CUOTA ANUAL", -30.00)]
    fx.escribir_html(e.entrada / "cuenta.xls", cuenta, cabecera_saldo=True)

    # 3: excluir · Intro: no (es la clave que no es segura)
    salida = e.ejecutar(respuestas="3\n\n")
    tramo = salida.split("── El pago de la tarjeta")[-1]
    comprobar("excluiría 2 movimientos:" in tramo
              and "CUOTA ANUAL" in tramo and "Comprueba que todos son" in tramo,
              "enseña los dos que excluiría, incluido el que no es el recibo, y avisa",
              tramo)
    comprobar(e.leer_config("exclude_patterns.json") == [],
              "sin un sí, no escribe nada")


@caso("asistente-formato", "El asistente respeta el fichero de la persona y no pisa sus reglas")
def prueba_asistente_formato(e):
    fx.escribir_html(e.entrada / "cuenta.xls", SIN_CLASIFICAR)
    # como lo deja el Bloc de notas: BOM y saltos de Windows, con líneas en
    # blanco y una regla suya que apaga «yodo» (null)
    original = ('{\r\n  "_sintaxis": "mi fichero",\r\n\r\n'
                '  "casero pepe": "Piso",\r\n  "yodo": null\r\n}\r\n')
    (e.ajustes / "rules.json").write_bytes(b"\xef\xbb\xbf" + original.encode("utf-8"))
    # 3: clasificar · 6: zafiro a Comida · 1: yodo a Ingresos · N: no aplicar
    salida = e.ejecutar(respuestas="3\n6\n1\nn\n")

    crudo = (e.ajustes / "rules.json").read_bytes()
    texto = crudo[3:].decode("utf-8")
    comprobar(crudo.startswith(b"\xef\xbb\xbf"), "conserva el BOM")
    comprobar(texto == original.replace('"yodo": null\r\n',
                                        '"yodo": null,\r\n  "zafiro": "Comida"\r\n'),
              "solo cambia la coma de la línea de antes y la línea nueva, "
              "con los saltos de Windows", repr(texto))
    comprobar("ya tiene una regla «yodo»" in salida
              and 'Añádelo a mano:  "yodo": {"+": "Ingresos"}' in salida,
              "una clave que ya existe (aunque sea null) no se pisa: lo dice "
              "y enseña la línea", salida)


# --- el pago de la tarjeta visto desde la tarjeta (2.15.0) -----------------
# Algunos bancos apuntan la liquidación en los DOS extractos: el cargo en la
# cuenta y el mismo importe como abono en la tarjeta. Sin excluir el abono,
# contaba como un ingreso. Datos inventados: dos meses de compras, cada uno
# pagado a primeros del siguiente; el abono cae en el mes de compras
# siguiente, que es justo lo que descuadraba la suma neta del mes.
ESPEJO_TARJETA = [("10/04/2026", "COMPRA MERCADONA CENTRO", -50.00),
                  ("20/04/2026", "COMPRA MERCADONA CENTRO", -30.25),   # abril -80,25
                  ("05/05/2026", "PAGO RECIBO 4321", 80.25),
                  ("12/05/2026", "COMPRA MERCADONA CENTRO", -60.00),   # mayo  -60,00
                  ("05/06/2026", "PAGO RECIBO 4321", 60.00)]
ESPEJO_CUENTA = [("01/04/2026", "NOMINA EMPRESA FICTICIA SL", 2000.00),
                 ("05/05/2026", "TARJ.CRDTO 4321 ABRIL", -80.25),
                 ("05/06/2026", "TARJ.CRDTO 4321 MAYO", -60.00)]


def _espejo(e, patrones):
    e.escribir_config("exclude_patterns.json", patrones)
    fx.escribir_xml_ss(e.entrada / "tarjeta.xls", ESPEJO_TARJETA, tarjeta=True)
    fx.escribir_html(e.entrada / "cuenta.xls", ESPEJO_CUENTA, cabecera_saldo=True)


@caso("tarjeta-espejo", "Detecta el pago en los dos extractos: el cargo y su abono en la tarjeta")
def prueba_tarjeta_espejo(e):
    _espejo(e, [])
    salida = e.ejecutar()

    comprobar('Añade esto a exclude_patterns.json:  "tarj.crdto"' in salida,
              "propone excluir el recibo de la cuenta", salida)
    comprobar("2026-04" in salida and "2026-05" in salida,
              "lo encuentra los dos meses, aunque el abono reste en el mes de "
              "compras siguiente", salida)
    comprobar("El mismo pago aparece también en el extracto de la tarjeta" in salida
              and 'Añade también:  "pago recibo"' in salida,
              "y propone excluir también el abono en la tarjeta", salida)


@caso("tarjeta-espejo-tras-cuenta", "Con solo el recibo de la cuenta excluido, avisa del abono en la tarjeta")
def prueba_tarjeta_espejo_tras_cuenta(e):
    # antes, con cualquier patrón puesto, el detector callaba
    _espejo(e, ["tarj.crdto"])
    salida = e.ejecutar()

    comprobar("El pago de la tarjeta está contando como un ingreso" in salida
              and 'Añade esto a exclude_patterns.json:  "pago recibo"' in salida,
              "avisa del abono aunque ya haya un patrón puesto", salida)
    comprobar("Esto parece el recibo" not in salida,
              "no vuelve a pedir lo que ya está excluido", salida)
    comprobar("el pago de la tarjeta está contando como un ingreso" in salida,
              "junto a los totales dice que lo inflado son los ingresos", salida)
    ingresos = e.resumen()["Ingresos"].sum()
    comprobar(abs(ingresos - (2000 + 80.25 + 60)) < 0.01,
              "(y es verdad: sin excluir, el abono suma a Ingresos)", ingresos)


@caso("tarjeta-espejo-resuelto", "Con los dos lados excluidos no avisa y los Ingresos no se inflan")
def prueba_tarjeta_espejo_resuelto(e):
    _espejo(e, ["tarj.crdto", "pago recibo"])
    salida = e.ejecutar()

    comprobar("contando dos veces" not in salida and "ningún patrón en" not in salida,
              "no avisa de nada", salida)
    ingresos = e.resumen()["Ingresos"].sum()
    comprobar(abs(ingresos - 2000) < 0.01,
              "Ingresos es solo la nómina", ingresos)


@caso("tarjeta-espejo-neutro", "El abono con regla a una categoría neutra se da por resuelto")
def prueba_tarjeta_espejo_neutro(e):
    # p. ej. «abono en tarjeta de credito» -> Transferencias internas, en la base
    _espejo(e, ["tarj.crdto"])
    e.regla_al_principio("pago recibo", "Transferencias internas")
    salida = e.ejecutar()

    comprobar("contando dos veces" not in salida,
              "una neutra no suma en ningún sitio: no hace falta excluirlo", salida)


@caso("tarjeta-espejo-casualidad", "Una devolución que coincide con un cargo cualquiera no es el recibo")
def prueba_tarjeta_espejo_casualidad(e):
    e.escribir_config("exclude_patterns.json", [])
    tarjeta = [("05/04/2026", "COMPRA MERCADONA CENTRO", -50.00),
               ("10/04/2026", "DEVOLUCION LIBRERIA", 35.00),     # devolución de verdad
               ("15/04/2026", "COMPRA MERCADONA CENTRO", -30.25)]  # neto -45,25
    fx.escribir_xml_ss(e.entrada / "tarjeta.xls", tarjeta, tarjeta=True)
    cuenta = [("01/04/2026", "NOMINA EMPRESA FICTICIA SL", 2000.00),
              ("12/04/2026", "RECIBO GIMNASIO PUEBLO", -35.00),   # mismo importe, por casualidad
              ("05/05/2026", "LIQUIDACION TARJETA VISA 778899", -45.25)]
    fx.escribir_html(e.entrada / "cuenta.xls", cuenta, cabecera_saldo=True)
    salida = e.ejecutar()

    comprobar('"liquidacion tarjeta visa"' in salida,
              "el recibo de verdad (con la devolución descontada) se sigue encontrando",
              salida)
    comprobar("El mismo pago aparece también" not in salida
              and "GIMNASIO" not in salida.split("── Avisos")[-1],
              "un solo mes y sin cuadre: no toma la devolución y el gimnasio por "
              "el pago de la tarjeta", salida)


@caso("asistente-exclusion-dos-lados", "El asistente excluye el recibo de la cuenta y su abono en la tarjeta")
def prueba_asistente_exclusion_dos_lados(e):
    _espejo(e, [])
    # menú: 1 histórico, 2 carpeta, 3 excluir (2 líneas), 4 de nuevo.
    # S al recibo de la cuenta · S al abono en la tarjeta · Intro: aplicarlo
    salida = e.ejecutar(respuestas="3\ns\ns\n\n")

    comprobar("Excluir el recibo de la tarjeta  (2 líneas)" in salida,
              "el menú dice que son dos líneas", salida)
    comprobar("PAGO RECIBO 4321  (tarjeta)" in salida,
              "la vista previa del abono enseña que es de la tarjeta", salida)
    comprobar(e.leer_config("exclude_patterns.json") == ["tarj.crdto", "pago recibo"],
              "escribe las dos claves", e.leer_config("exclude_patterns.json"))
    ingresos = e.resumen()["Ingresos"].sum()
    comprobar(abs(ingresos - 2000) < 0.01,
              "y al volver a ejecutar los Ingresos ya son solo la nómina", ingresos)


@caso("iso", "Las fechas aaaa-mm-dd no se invierten")
def prueba_iso(e):
    datos = [("02/04/2026", "COMPRA MERCADONA CENTRO", -10.00)]
    fx.escribir_csv(e.entrada / "cuenta.xls", datos, fechas_iso=True)
    e.ejecutar()

    fecha = e.historico().iloc[0]["fecha"]
    comprobar((fecha.day, fecha.month) == (2, 4),
              "2026-04-02 es 2 de abril, no 4 de febrero",
              f"salió {fecha:%d/%m/%Y}")


@caso("mes", "El mes contable mueve las nóminas de los días 1-3")
def prueba_mes(e):
    datos = [("01/05/2026", "NOMINA EMPRESA FICTICIA SL", 2000.00),
             ("05/05/2026", "COMPRA MERCADONA CENTRO", -10.00)]
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
        elif "QBP" in desc:
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
    comprobar(categoria_de(df, "QBP") == "Otros",
              "una categoría mal escrita se ignora y mandan las reglas",
              str(categoria_de(df, "QBP")))
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


@caso("sync-notas-realineadas", "Una nota junto a un movimiento lo sigue si entra otro por medio")
def prueba_sync_notas_realineadas(e):
    # regresión del piloto: la nota se quedaba en su número de fila, y al
    # entrar un movimiento más antiguo pasaba a estar junto al de al lado
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL[:3])
    fx.escribir_destino(e.dir / "contabilidad.xlsx", filas_previas=0)
    cfg = e.leer_config("sincronizar.json")
    cfg["archivo"] = "contabilidad.xlsx"
    e.escribir_config("sincronizar.json", cfg)
    e.ejecutar()

    from openpyxl import load_workbook
    ruta = e.dir / "contabilidad.xlsx"
    wb = load_workbook(ruta)
    ws = wb["MOVIMIENTOS"]
    fila = next(r for r in range(2, ws.max_row + 1)
                if ws.cell(r, 2).value == "COMPRA MERCADONA CENTRO")
    ws.cell(fila, 10).value = "la del cumple"
    wb.save(ruta)
    wb.close()

    fx.escribir_html(e.entrada / "anterior.xls",
                     [("01/04/2026", "RECIBO GIMNASIO", -30.00)])
    salida = e.ejecutar()

    wb = load_workbook(ruta)
    ws = wb["MOVIMIENTOS"]
    junto = {ws.cell(r, 2).value: ws.cell(r, 10).value for r in range(2, ws.max_row + 1)}
    wb.close()
    comprobar(junto.get("COMPRA MERCADONA CENTRO") == "la del cumple",
              "la nota sigue junto a su movimiento", str(junto))
    comprobar(sum(1 for v in junto.values() if v) == 1,
              "y no se ha quedado otra copia en su fila vieja", str(junto))
    comprobar("recolocadas" in salida, "lo dice por pantalla", salida)


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


# --- regresiones de la ronda 2 del piloto (pruebas/piloto/HALLAZGOS_2.md) ---

@caso("cuentas-descarga-sin-patron", "Con cuentas declaradas, otra descarga con otro nombre no se duplica")
def prueba_cuentas_descarga_sin_patron(e):
    # «movimientos (1).xls» no casaba con ninguna cuenta, entraba como una
    # tercera «(sin identificar)» y todo lo suyo sumaba dos veces
    e.escribir_config("cuentas.json", {"negocio": "negocio", "personal": "personal"})
    negocio = [("05/04/2026", "COMPRA MERCADONA CENTRO", -100.00),
               ("08/04/2026", "COMPRA LIDL", -20.00),
               ("12/04/2026", "RECIBO GIMNASIO", -30.00)]
    fx.escribir_html(e.entrada / "negocio_2026.xls", negocio)
    fx.escribir_html(e.entrada / "personal_2026.xls",
                     [("06/04/2026", "COMPRA MERCADONA CENTRO", -30.00)])
    fx.escribir_html(e.entrada / "movimientos (1).xls", negocio)
    salida = e.ejecutar()

    df = e.historico()
    comprobar(len(df) == 4, "la copia con otro nombre no se suma", f"{len(df)} filas")
    comprobar("parece otra descarga de «negocio»" in salida,
              "y se dice cuál es y qué hacer", salida)

    # una cuenta de verdad sin patrón (no se parece a ninguna) sí entra
    e.vaciar_entrada()
    fx.escribir_html(e.entrada / "ahorro.xls",
                     [("09/04/2026", "TRASPASO RECIBIDO", 50.00)])
    e.ejecutar()
    comprobar(len(e.historico()) == 5, "una cuenta distinta sin patrón sí entra",
              f"{len(e.historico())} filas")


@caso("tarjetas-sin-declarar", "Dos tarjetas sin cuentas.json: avisa de lo que se funde")
def prueba_tarjetas_sin_declarar(e):
    comun = [("14/04/2026", "CAFETERIA LA ESQUINA", -2.60)]
    fx.escribir_xml_ss(e.entrada / "tarjeta_1111.xls", comun + [
        ("02/04/2026", "COMPRA A", -10.00), ("10/04/2026", "COMPRA B", -11.00),
        ("20/04/2026", "COMPRA C", -12.00), ("28/04/2026", "COMPRA G", -13.00)],
        tarjeta=True)
    fx.escribir_xml_ss(e.entrada / "tarjeta_2222.xls", comun + [
        ("01/04/2026", "COMPRA D", -20.00), ("11/04/2026", "COMPRA E", -21.00),
        ("21/04/2026", "COMPRA F", -22.00), ("29/04/2026", "COMPRA H", -23.00)],
        tarjeta=True)
    salida = e.ejecutar()
    comprobar("Parecen dos tarjetas distintas" in salida, "avisa", salida)
    comprobar("faltan 2,60 €" in salida, "y dice lo que se ha fundido", salida)

    e.escribir_config("cuentas.json", {"1111": "una", "2222": "otra"})
    e.ejecutar()
    df = e.historico()
    comprobar((df["descripcion"] == "CAFETERIA LA ESQUINA").sum() == 2,
              "declaradas, salen los dos cafés", str(len(df)))


@caso("tarjetas-dos-recibos", "Con dos tarjetas, encuentra el recibo de cada una")
def prueba_tarjetas_dos_recibos(e):
    e.escribir_config("exclude_patterns.json", [])
    e.escribir_config("cuentas.json", {"1111": "una", "2222": "otra", "cuenta": "cuenta"})
    fx.escribir_xml_ss(e.entrada / "tarjeta_1111.xls",
                       [("05/04/2026", "COMPRA A", -50.00)], tarjeta=True)
    fx.escribir_xml_ss(e.entrada / "tarjeta_2222.xls",
                       [("06/04/2026", "COMPRA B", -30.25)], tarjeta=True)
    fx.escribir_html(e.entrada / "cuenta.xls", [
        ("01/04/2026", "NOMINA EMPRESA FICTICIA SL", 2000.00),
        ("02/05/2026", "LIQUIDACION TARJETA 1111", -50.00),
        ("02/05/2026", "LIQUIDACION TARJETA 2222", -30.25)])
    salida = e.ejecutar()
    comprobar("50,00 €" in salida and "30,25 €" in salida
              and '"liquidacion tarjeta"' in salida,
              "los dos recibos y la clave común", salida)


@caso("base-signo-cobros", "Cobrar de una comunidad de propietarios es ingreso; pagarla, Piso")
def prueba_base_signo_cobros(e):
    fx.escribir_html(e.entrada / "cuenta.xls", [
        ("03/04/2026", "TRANSF. DE COMUNIDAD PROP. SOL FRA 12", 900.00),
        ("05/04/2026", "RECIBO COMUNIDAD PROPIETARIOS", -65.00),
        ("12/04/2026", "IMPUESTO VEHICULOS AYTO", -98.40)])
    e.ejecutar()
    df = e.historico()
    comprobar(categoria_de(df, "TRANSF. DE COMUNIDAD") == "Ingresos",
              "el cobro va a Ingresos", str(categoria_de(df, "TRANSF. DE COMUNIDAD")))
    comprobar(categoria_de(df, "RECIBO COMUNIDAD") == "Piso",
              "el recibo sigue en Piso", str(categoria_de(df, "RECIBO COMUNIDAD")))
    comprobar(categoria_de(df, "IMPUESTO VEHICULOS") == "Transporte",
              "el impuesto del coche tiene regla", str(categoria_de(df, "IMPUESTO")))


@caso("cargo-abono", "Un extracto con Cargo y Abono en dos columnas se lee con su signo")
def prueba_cargo_abono(e):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["Extracto"])
    ws.append([])
    ws.append(["Fecha", "Concepto", "Cargo", "Abono", "Saldo"])
    ws.append(["01/04/2026", "NOMINA EMPRESA FICTICIA SL", None, "2.000,00", "7.000,00"])
    ws.append(["07/04/2026", "COMPRA MERCADONA CENTRO", "100,00", None, "6.900,00"])
    ws.append(["08/04/2026", "COMPRA LIDL", "-20,00", None, "6.880,00"])
    wb.save(e.entrada / "extracto.xlsx")
    e.ejecutar()
    df = e.historico().set_index("descripcion")
    comprobar(len(df) == 3, "se leen los tres", str(len(df)))
    comprobar(df.at["NOMINA EMPRESA FICTICIA SL", "importe"] == 2000
              and df.at["COMPRA MERCADONA CENTRO", "importe"] == -100
              and df.at["COMPRA LIDL", "importe"] == -20,
              "lo del Abono entra y lo del Cargo sale, venga con el signo que venga",
              str(df["importe"].to_dict()))


@caso("neobanco-payee", "Un CSV con la columna «Payee» se lee sin tocarlo")
def prueba_neobanco_payee(e):
    (e.entrada / "transactions.csv").write_text(
        "Date,Payee,Account number,Transaction type,Payment reference,Amount (EUR)\n"
        "2026-04-01,Transferencia de PADRES,,Income,,300.00\n"
        "2026-04-03,Mercadona,,Presentment,,-12.50\n", encoding="utf-8")
    e.ejecutar()
    df = e.historico()
    comprobar(len(df) == 2 and categoria_de(df, "Mercadona") == "Comida",
              "se leen y clasifican", str(len(df)))


@caso("entrada-ilegible", "Si nada de entrada/ se puede leer, no dice que esté vacía")
def prueba_entrada_ilegible(e):
    (e.entrada / "rara.csv").write_text("hola;adios\n1;2\n", encoding="utf-8")
    salida = e.ejecutar()
    comprobar("está vacía" not in salida and "no he podido leer ningún" in salida,
              "dice lo que pasa de verdad", salida)


@caso("etiquetas-repetidas", "Dos etiquetas iguales avisan y no dejan el histórico a medias")
def prueba_etiquetas_repetidas(e):
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL)
    cat = e.leer_config("categorias.json")
    cat["etiquetas"] = {"Comida": "Casa", "Piso": "Casa", "Ocio": "Balance",
                        "Transporte": "casa "}
    e.escribir_config("categorias.json", cat)
    salida = e.ejecutar()
    comprobar(e.ultimo_codigo == 0 and "❌" not in salida, "no se cae", salida)
    wb = e.libro_historico()
    columnas = [c.value for c in wb["RESUMEN"][1]]
    comprobar(len(columnas) == len(set(columnas)), "ninguna columna repetida",
              str(columnas))
    comprobar(wb.sheetnames[0] == "RESUMEN" and len(wb["RESUMEN"]._charts) > 0,
              "el histórico sale completo, con sus gráficos", str(wb.sheetnames))
    wb.close()
    comprobar("se llama igual que" in salida, "y avisa de las que ignora", salida)


@caso("regla-categoria-inexistente", "Tu regla a una categoría mal escrita se descarta")
def prueba_regla_categoria_inexistente(e):
    # antes se aplicaba y el movimiento se salía de Total Gastos
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL)
    e.regla_al_principio("mercadona", "Comidas")
    salida = e.ejecutar()
    df = e.historico()
    comprobar(categoria_de(df, "MERCADONA") == "Comida",
              "manda la siguiente regla que casa", str(categoria_de(df, "MERCADONA")))
    comprobar(abs(e.resumen().iloc[0]["Total Gastos"] - TOTAL_GASTOS_ABRIL) < 0.005,
              "los totales no pierden nada", str(e.resumen().iloc[0]["Total Gastos"]))
    comprobar("DESCARTADO" in salida, "y se dice", salida)


@caso("informe-cobros", "Sin clasificar: los cobros proponen lo común, y la devolución va con su comercio")
def prueba_informe_cobros(e):
    fx.escribir_html(e.entrada / "cuenta.xls", [
        ("02/04/2026", "TRANSF. DE CLIENTE UNO FRA 1", 1000.00),
        ("09/04/2026", "TRANSF. DE CLIENTE DOS FRA 2", 300.00),
        ("11/04/2026", "COMPRA FERRETERIA ZOCO", -50.00),
        ("15/04/2026", "DEVOLUCION FERRETERIA ZOCO", 10.00)])
    salida = e.ejecutar()
    comprobar('"uno"' not in salida and '"dos"' not in salida
              and '{"+": "PON_TU_CATEGORIA"}' in salida,
              "no propone el nombre de un solo cliente", salida)
    comprobar("2 mov.  ·  zoco" in salida or "2 mov.  ·  ferreteria" in salida,
              "la devolución va en el grupo de su comercio", salida)


@caso("historico-hoja-propia", "Una hoja añadida al histórico avisa de que se pierde")
def prueba_historico_hoja_propia(e):
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL[:3])
    e.ejecutar()
    wb = e.libro_historico()
    wb.create_sheet("Mis cuentas")
    wb.save(e.ruta_historico)
    wb.close()
    salida = e.ejecutar()
    comprobar("«Mis cuentas» ya no está" in salida and "copias" in salida,
              "avisa y dice dónde está", salida)


def _preparar_sync(e, hoja="MOVIMIENTOS"):
    cfg = e.leer_config("sincronizar.json")
    cfg["archivo"] = "contabilidad.xlsx"
    cfg["hoja"] = hoja
    e.escribir_config("sincronizar.json", cfg)


@caso("sync-esquina-ajena", "No se escribe encima de una tabla del usuario")
def prueba_sync_esquina_ajena(e):
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL[:3])
    from openpyxl import Workbook, load_workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Datos"
    ws.append(["Fecha", "Concepto", "Importe", "Categoría"])
    ws.append(["02/03/2026", "RECIBO A MANO", -10, "Piso"])
    wb.save(e.dir / "contabilidad.xlsx")
    _preparar_sync(e, "Datos")
    salida = e.ejecutar()
    comprobar("no es la mía" in salida and "NO se ha tocado" in salida,
              "se niega y dice por qué", salida)
    wb = load_workbook(e.dir / "contabilidad.xlsx")
    comprobar(wb["Datos"]["B2"].value == "RECIBO A MANO", "lo del usuario sigue ahí")
    wb.close()


@caso("sync-abierto", "No se escribe en el fichero de contabilidad si está abierto")
def prueba_sync_abierto(e):
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL[:3])
    fx.escribir_destino(e.dir / "contabilidad.xlsx", filas_previas=0)
    _preparar_sync(e)
    (e.dir / ".~lock.contabilidad.xlsx#").write_text("x")
    salida = e.ejecutar()
    comprobar("está abierto" in salida and "NO se ha tocado" in salida,
              "se niega", salida)


@caso("sync-sin-cambios", "Sin nada nuevo, ni se reescribe ni gasta una copia")
def prueba_sync_sin_cambios(e):
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL[:3])
    fx.escribir_destino(e.dir / "contabilidad.xlsx", filas_previas=0)
    _preparar_sync(e)
    e.ejecutar()
    copias = lambda: sorted(p.name for p in (e.datos / "copias").glob("contabilidad_*"))
    antes = copias()
    salida = e.ejecutar()
    comprobar("ya estaba al día" in salida, "lo dice", salida)
    comprobar(copias() == antes, "y no hay copia nueva", f"{antes} -> {copias()}")


@caso("reglas-cli-pares", "reglas.py: cada importe va con el concepto de delante")
def prueba_reglas_cli_pares(e):
    e.ejecutar()                         # crea ajustes/
    proc = subprocess.run(
        [sys.executable, os.path.join(DIR_APP, "reglas.py"),
         "BIZUM DE ALGUIEN", "25", "BIZUM A ALGUIEN", "-18,50"],
        cwd=e.dir, capture_output=True, text=True, encoding="utf-8",
        errors="replace")
    lineas = [l for l in proc.stdout.splitlines() if "BIZUM" in l]
    comprobar(len(lineas) == 2 and "25,00" in lineas[0] and "-18,50" in lineas[1]
              and "Ingresos" in lineas[0] and "Ocio" in lineas[1],
              "dos casos, cada uno con su signo", proc.stdout + proc.stderr)


@caso("tarjeta-sin-cuenta", "Solo con tarjetas no hay recibo que avisar")
def prueba_tarjeta_sin_cuenta(e):
    e.escribir_config("exclude_patterns.json", [])
    fx.escribir_xml_ss(e.entrada / "tarjeta_debito.xls",
                       [("05/04/2026", "COMPRA A", -50.00)], tarjeta=True)
    salida = e.ejecutar()
    comprobar("ningún patrón en" not in salida and "contando dos veces" not in salida,
              "sin extracto de cuenta, calla", salida)


@caso("hoja-cuentas", "Con varias cuentas, la hoja CUENTAS reparte gastos, ingresos y saldo")
def prueba_hoja_cuentas(e):
    e.escribir_config("cuentas.json", {"negocio": "negocio", "personal": "personal"})
    fx.escribir_html(e.entrada / "negocio_2026.xls",
                     [("05/04/2026", "NOMINA EMPRESA FICTICIA SL", 1000.00),
                      ("08/04/2026", "COMPRA LIDL", -20.00)])
    fx.escribir_html(e.entrada / "personal_2026.xls",
                     [("06/04/2026", "COMPRA MERCADONA CENTRO", -30.00)])
    salida = e.ejecutar()
    import pandas as pd
    wb = e.libro_historico()
    comprobar(wb.sheetnames[:2] == ["RESUMEN", "CUENTAS"], "va justo detrás de RESUMEN",
              str(wb.sheetnames))
    wb.close()
    c = pd.read_excel(e.ruta_historico, sheet_name="CUENTAS").iloc[0]
    comprobar(c["negocio · gastos"] == 20 and c["personal · gastos"] == 30
              and c["negocio · ingresos"] == 1000,
              "gastos e ingresos de cada una", str(c.to_dict()))
    # fixtures.py parte de 5000 € en cada extracto
    comprobar(abs(c["negocio · saldo"] - 5980) < 0.005
              and abs(c["personal · saldo"] - 4970) < 0.005,
              "y el saldo de cada cuenta", str(c.to_dict()))
    comprobar("personal · ingresos" not in c.index, "sin columnas que son siempre 0",
              str(list(c.index)))
    comprobar("CUENTAS" in salida, "se dice por pantalla", salida)
    limpios = pd.read_excel(e.salida / "movimientos_limpios.xlsx")
    comprobar(list(limpios.columns)[:7] == ["fecha", "descripcion", "importe", "tipo",
                                            "mes", "mes_ajustado", "categoria"]
              and "cuenta" in limpios.columns,
              "movimientos_limpios lleva la cuenta, después de A-G",
              str(list(limpios.columns)))


@caso("hoja-cuentas-una", "Con una sola cuenta no hay hoja CUENTAS")
def prueba_hoja_cuentas_una(e):
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL[:3])
    e.ejecutar()
    wb = e.libro_historico()
    comprobar("CUENTAS" not in wb.sheetnames, "no sale", str(wb.sheetnames))
    wb.close()


def _hoja_propia(ruta):
    """El Excel de siempre de alguien: su cabecera y un mes metido a mano."""
    from openpyxl import Workbook
    import datetime as dt
    wb = Workbook()
    ws = wb.active
    ws.title = "Datos"
    ws.append(["Fecha", "Concepto", "Importe", "Categoría"])
    ws.append([dt.datetime(2026, 3, 2), "RECIBO A MANO", -10, "Piso"])
    ws.append([dt.datetime(2026, 4, 7), "compra mercadona centro", -100, "Comida"])
    wb.save(ruta)


@caso("sync-anadir", "Modo añadir: solo lo nuevo, debajo, sin tocar lo del usuario")
def prueba_sync_anadir(e):
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL[:3])
    _hoja_propia(e.dir / "contabilidad.xlsx")
    cfg = e.leer_config("sincronizar.json")
    cfg.update(archivo="contabilidad.xlsx", hoja="Datos", modo="añadir",
               columnas={"Fecha": "fecha", "Concepto": "descripcion",
                         "Importe": "importe", "Categoría": "categoria"})
    e.escribir_config("sincronizar.json", cfg)
    salida = e.ejecutar()

    from openpyxl import load_workbook
    ws = load_workbook(e.dir / "contabilidad.xlsx")["Datos"]
    filas = list(ws.iter_rows(values_only=True))
    comprobar(filas[1][1] == "RECIBO A MANO" and filas[2][1] == "compra mercadona centro",
              "lo tecleado a mano sigue igual y en su sitio", str(filas[:3]))
    # de los tres de abril, el Mercadona ya estaba (escrito en minúsculas)
    comprobar(len(filas) == 5 and filas[3][1] == "NOMINA EMPRESA FICTICIA SL",
              "se añaden solo los dos que faltan, debajo", str(filas))
    comprobar(filas[3][3] == "Ingresos", "cada dato en su columna", str(filas[3]))
    comprobar(ws.cell(4, 1).number_format == ws.cell(3, 1).number_format,
              "con el formato de las filas que ya había",
              f"{ws.cell(4, 1).number_format!r} / {ws.cell(3, 1).number_format!r}")
    comprobar("no tenía hasta ahora: Ingresos (1)" in salida,
              "y avisa de las categorías que la hoja no usaba", salida)
    comprobar("2 movimientos añadidos debajo" in salida, "lo dice", salida)

    salida = e.ejecutar()
    comprobar("ningún movimiento nuevo" in salida
              and load_workbook(e.dir / "contabilidad.xlsx")["Datos"].max_row == 5,
              "la segunda vez no añade nada", salida)


@caso("sync-anadir-cabecera", "Modo añadir con una cabecera que no cuadra: no escribe")
def prueba_sync_anadir_cabecera(e):
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL[:3])
    _hoja_propia(e.dir / "contabilidad.xlsx")
    cfg = e.leer_config("sincronizar.json")
    cfg.update(archivo="contabilidad.xlsx", hoja="Datos", modo="añadir",
               columnas={"Fecha": "fecha", "Importe": "importe",
                         "Concepto": "descripcion"})
    e.escribir_config("sincronizar.json", cfg)
    salida = e.ejecutar()
    comprobar("no coincide" in salida and "NO se ha tocado" in salida,
              "se niega y dice dónde", salida)


@caso("sync-columnas-propias", "Modo tabla con tus nombres de columna")
def prueba_sync_columnas_propias(e):
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL[:3])
    from openpyxl import Workbook, load_workbook
    wb = Workbook()
    wb.active.title = "MOVIMIENTOS"      # vacía, como la primera vez
    wb.save(e.dir / "contabilidad.xlsx")
    cfg = e.leer_config("sincronizar.json")
    cfg.update(archivo="contabilidad.xlsx",
               columnas={"Día": "fecha", "Qué": "descripcion", "Cuánto": "importe"})
    e.escribir_config("sincronizar.json", cfg)
    e.ejecutar()
    ws = load_workbook(e.dir / "contabilidad.xlsx")["MOVIMIENTOS"]
    comprobar([c.value for c in ws[1]] == ["Día", "Qué", "Cuánto"],
              "tus cabeceras, y solo esas columnas", str([c.value for c in ws[1]]))
    comprobar(ws.max_row == 4, "con los tres movimientos", str(ws.max_row))
    salida = e.ejecutar()
    comprobar("ya estaba al día" in salida, "y la segunda vez la reconoce como suya",
              salida)


@caso("importar-categorias", "Las categorías del export de otra app, solo si se pide")
def prueba_importar_categorias(e):
    (e.entrada / "export_otra_app.csv").write_text(
        "date,description,category,amount\n"
        "2026-04-01,Recibo Casero,Vivienda,-750.00\n"
        "2026-04-03,Cena Con Amigos,Restaurantes,-40.00\n"
        "2026-04-05,Cosa Rara,Varios,-5.00\n", encoding="utf-8")
    salida = e.ejecutar()
    df = e.historico()
    comprobar((df["categoria_manual"].fillna("") == "").all(),
              "sin pedirlo, no se usa", str(df["categoria_manual"].tolist()))
    comprobar("importar_categorias" in salida, "pero se dice que se puede", salida)

    cat = e.leer_config("categorias.json")
    cat["gastos"].append("Varios")
    cat["importar_categorias"] = {"fichero": "export",
                                  "traducir": {"Vivienda": "Piso", "Restaurantes": "Ocio"}}
    e.escribir_config("categorias.json", cat)
    salida = e.ejecutar()
    df = e.historico()
    comprobar(categoria_de(df, "Casero") == "Piso" and categoria_de(df, "Cena") == "Ocio",
              "pedido, se traduce (también lo que ya estaba en el histórico)",
              str(df[["descripcion", "categoria", "categoria_manual"]].values.tolist()))
    comprobar("sin traducir" not in salida and categoria_de(df, "Cosa Rara") == "Varios",
              "la que se llama como una tuya vale sin traducir", salida)
    comprobar("salvo lo que traiga importar_categorias" in " ".join(salida.split()),
              "y el aviso de «saldrá a 0» no lo da por seguro", salida)

    cat["importar_categorias"]["traducir"] = {"Vivienda": "Piso"}
    cat["gastos"].remove("Varios")
    e.escribir_config("categorias.json", cat)
    e.vaciar_entrada()
    (e.entrada / "export_otra_app.csv").write_text(
        "date,description,category,amount\n"
        "2026-05-03,Otra Cena,Restaurantes,-30.00\n", encoding="utf-8")
    salida = e.ejecutar()
    comprobar("Restaurantes" in salida and "sin traducir" in salida,
              "avisa de lo que no sabe traducir", salida)


@caso("equivalencias", "Juntar dos categorías de fábrica en una sin perder sus reglas")
def prueba_equivalencias(e):
    cat = e.leer_config("categorias.json")
    cat["gastos"] = ["Facturas" if g == "Luz/Agua" else g for g in cat["gastos"]
                     if g != "Fibra/movil"]
    cat["equivalencias"] = {"Luz/Agua": "Facturas", "Fibra/movil": "Facturas"}
    e.escribir_config("categorias.json", cat)
    fx.escribir_html(e.entrada / "cuenta.xls", [
        ("05/04/2026", "RECIBO IBERDROLA CLIENTES", -60.00),
        ("08/04/2026", "RECIBO MOVISTAR", -40.00)])
    salida = e.ejecutar()
    df = e.historico()
    comprobar(set(df["categoria"]) == {"Facturas"}, "las dos van a la tuya",
              str(df["categoria"].tolist()))
    comprobar("iberdrola" not in salida.lower().split("descartadas")[-1][:400]
              if "descartadas" in salida else True,
              "sin descartar sus reglas de la base", salida)


@caso("categoria-renombrada", "Quien conserva «Perros» no pierde las reglas de «Mascotas»")
def prueba_categoria_renombrada(e):
    # La plantilla de antes traía «Perros»; la base ahora manda a «Mascotas».
    # Sin la equivalencia implícita, veterinarios y tiendas de animales se
    # descartarían y caerían en Otros sin que nada lo dijera.
    cat = e.leer_config("categorias.json")
    cat["gastos"] = ["Perros" if g == "Mascotas" else g for g in cat["gastos"]]
    e.escribir_config("categorias.json", cat)
    fx.escribir_html(e.entrada / "cuenta.xls", [
        ("05/04/2026", "CLINICA VETERINARIA CENTRO", -45.00),
        ("08/04/2026", "KIWOKO TIENDA", -20.00)])
    salida = e.ejecutar()
    df = e.historico()
    comprobar(set(df["categoria"]) == {"Perros"}, "van a su «Perros» de siempre",
              str(df["categoria"].tolist()))
    comprobar("no cuadran" not in salida and "reglas de la base descartadas" not in salida,
              "sin descartar reglas ni avisos de categorías", salida)


@caso("historico-copias-sin-cambios", "Sin nada nuevo, no se gasta otra copia del histórico")
def prueba_historico_copias_sin_cambios(e):
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL[:3])
    e.ejecutar()
    e.ejecutar()
    copias = lambda: sorted((e.datos / "copias").glob("historico_*.xlsx"))
    antes = copias()
    import time
    time.sleep(1.1)                      # que una copia nueva tuviera otro nombre
    e.ejecutar()
    comprobar(copias() == antes and len(antes) == 1, "la misma copia de antes",
              f"{[c.name for c in antes]} -> {[c.name for c in copias()]}")
    # la copia guarda lo que había ANTES de escribir: la de mayo sale en la
    # ejecución siguiente a la que lo mete
    fx.escribir_html(e.entrada / "mayo.xls", [("03/05/2026", "COMPRA LIDL", -9.00)])
    e.ejecutar()
    time.sleep(1.1)
    e.ejecutar()
    comprobar(len(copias()) == 2, "con algo nuevo, sí", str(len(copias())))


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
    datos = [("07/04/2026", "COMPRA MERCADONA CENTRO", -100.00),   # solo en la base
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
                     [("07/04/2026", "COMPRA MERCADONA CENTRO", -100.00)])
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


@caso("base-orden", "En la base, la regla concreta gana a la general que la contiene")
def prueba_base_orden(e):
    # sin reglas propias: aquí se prueba solo la base, tal cual se reparte
    e.escribir_config("rules.json", {})
    fx.escribir_html(e.entrada / "cuenta.xls", [
        ("02/04/2026", "ALQUILER DE VEHICULOS EUROPCAR", -120.00),
        ("03/04/2026", "TRANSFERENCIA ALQUILER PISO ABRIL", -700.00),
        ("04/04/2026", "UBER EATS PEDIDO", -18.00),
        ("05/04/2026", "UBER BV TRIP", -12.00),
        ("06/04/2026", "CLINICA VETERINARIA SAN ANTON", -45.00),
        ("07/04/2026", "CLINICA DENTAL SONRISA", -60.00),
        ("08/04/2026", "AMAZON PRIME VIDEO", -4.99),
        ("09/04/2026", "AMAZON EU MARKETPLACE", -30.00),
        ("10/04/2026", "SPAR EXPRESS", -15.00),
        ("11/04/2026", "SPARTEX LAVANDERIA", -9.00),
        ("12/04/2026", "IBERIAN JAMONES", -25.00),
        ("14/04/2026", "HOSTAL PENSION LA ESTRELLA", -40.00),
    ])
    e.ejecutar()
    df = e.historico()

    for texto, esperada, por_que in [
        ("EUROPCAR", "Transporte", "alquilar un coche no es el alquiler del piso"),
        ("ALQUILER PISO", "Piso", "y el alquiler del piso sigue en Piso"),
        ("UBER EATS", "Ocio", "un pedido de comida no es un viaje"),
        ("UBER BV", "Transporte", "y un viaje sigue siendo Transporte"),
        ("VETERINARIA", "Mascotas", "una clínica veterinaria no es la del médico"),
        ("CLINICA DENTAL", "Higiene", "y el dentista sigue en Higiene"),
        ("AMAZON PRIME", "Ocio", "la suscripción no es una compra de Amazon"),
        ("AMAZON EU", "Otros", "y la compra sigue en Otros"),
        ("SPAR EXPRESS", "Comida", "=spar pilla el supermercado"),
        ("SPARTEX", "Otros", "pero no otra palabra que empiece igual"),
        ("IBERIAN", "Otros", "=iberia no pilla IBERIAN"),
        ("HOSTAL PENSION", "Otros", "pension solo es ingreso si es positiva"),
    ]:
        comprobar(categoria_de(df, texto) == esperada, por_que,
                  f"{texto}: {categoria_de(df, texto)}")


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
                     [("07/04/2026", "COMPRA MERCADONA CENTRO", -100.00),
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


@caso("resumen-personalizado", "orden_resumen y etiquetas cambian el Excel sin tocar el cálculo")
def prueba_resumen_personalizado(e):
    e.escribir_config("categorias.json", {
        "gastos": ["Comida", "Otros"],
        "ingresos": ["Ingresos"],
        "neutras": ["Transferencias internas"],
        "columna_mes": "mes_ajustado",
        "etiquetas": {"Comida": "🍔 Comida"},
        "orden_resumen": ["Mes", "Comida", "Otros", "Balance", "Acumulado"]})
    e.escribir_config("rules.json", {"mercadona": "Comida", "nomina": "Ingresos"})
    fx.escribir_html(e.entrada / "cuenta.xls",
                     [("07/04/2026", "COMPRA MERCADONA CENTRO", -100.00),
                      ("09/04/2026", "NOMINA EMPRESA SL", 2000.00)])
    e.ejecutar()

    res = e.resumen()
    comprobar(list(res.columns) == ["Mes", "🍔 Comida", "Otros", "Balance", "Acumulado"],
              "las columnas salen en el orden pedido, con la etiqueta puesta",
              str(list(res.columns)))
    comprobar(abs(res.iloc[0]["🍔 Comida"] - 100) < 0.005,
              "el cálculo sigue siendo el mismo bajo el nombre nuevo",
              str(res.iloc[0]["🍔 Comida"]))


@caso("resumen-orden-invalido", "Un nombre mal escrito en orden_resumen avisa, no rompe")
def prueba_resumen_orden_invalido(e):
    e.escribir_config("categorias.json", {
        "gastos": ["Comida", "Otros"],
        "ingresos": ["Ingresos"],
        "neutras": ["Transferencias internas"],
        "columna_mes": "mes_ajustado",
        "orden_resumen": ["Mes", "Komida", "Balance"]})
    e.escribir_config("rules.json", {"mercadona": "Comida"})
    fx.escribir_html(e.entrada / "cuenta.xls",
                     [("07/04/2026", "COMPRA MERCADONA CENTRO", -100.00)])
    salida = e.ejecutar()

    comprobar("Komida" in salida and "orden_resumen" in salida,
              "avisa del nombre que no reconoce", salida)
    res = e.resumen()
    comprobar(list(res.columns) == ["Mes", "Balance"],
              "y el resto del orden pedido sí se aplica", str(list(res.columns)))
    comprobar("❌" not in salida,
              "quitar Total Gastos o Ingresos del resumen no rompe el final de "
              "la ejecución", salida)


# dos categorías de ingreso, la de siempre («Ingresos», que es la que asigna
# la base) y una más concreta: el caso normal de quien quiere desglosar.
CATEGORIAS_DOS_INGRESOS = {
    "gastos": ["Comida", "Otros"],
    "ingresos": ["Nomina", "Ingresos"],
    "neutras": ["Transferencias internas"],
    "columna_mes": "mes_ajustado"}
MOVIMIENTOS_DOS_INGRESOS = [("07/04/2026", "COMPRA MERCADONA CENTRO", -100.00),
                            ("09/04/2026", "NOMINA EMPRESA SL", 2000.00),
                            ("12/04/2026", "BIZUM DE AMIGA ALQUILER", 350.00)]
REGLAS_DOS_INGRESOS = {"mercadona": "Comida", "nomina": "Nomina",
                       "bizum": {"+": "Ingresos", "-": "Otros"}}


@caso("resumen-sin-desglose", "Sin desglosar_ingresos, una sola columna Ingresos como siempre")
def prueba_resumen_sin_desglose(e):
    e.escribir_config("categorias.json", CATEGORIAS_DOS_INGRESOS)
    e.escribir_config("rules.json", REGLAS_DOS_INGRESOS)
    fx.escribir_html(e.entrada / "cuenta.xls", MOVIMIENTOS_DOS_INGRESOS)
    e.ejecutar()

    res = e.resumen()
    comprobar("Nomina" not in res.columns and "Otros ingresos" not in res.columns,
              "las categorías de ingreso no tienen columna propia",
              str(list(res.columns)))
    comprobar(abs(res.iloc[0]["Ingresos"] - 2350) < 0.005,
              "y el total suma las dos", str(res.iloc[0]["Ingresos"]))


@caso("resumen-desglose-ingresos", "desglosar_ingresos da una columna a cada categoría de ingreso")
def prueba_resumen_desglose_ingresos(e):
    e.escribir_config("categorias.json",
                      {**CATEGORIAS_DOS_INGRESOS, "desglosar_ingresos": True})
    e.escribir_config("rules.json", REGLAS_DOS_INGRESOS)
    fx.escribir_html(e.entrada / "cuenta.xls", MOVIMIENTOS_DOS_INGRESOS)
    salida = e.ejecutar()

    res = e.resumen()
    comprobar(list(res.columns)[-7:] == ["Total Gastos", "Nomina", "Otros ingresos",
                                         "Ingresos", "Balance", "Fuera del balance",
                                         "Acumulado"],
              "una columna por categoría, justo antes del total que suman; la "
              "categoría «Ingresos» sale como «Otros ingresos» para no chocar "
              "con el total", str(list(res.columns)))
    f = res.iloc[0]
    comprobar(abs(f["Nomina"] - 2000) < 0.005 and abs(f["Otros ingresos"] - 350) < 0.005,
              "cada una con lo suyo", f"{f['Nomina']} / {f['Otros ingresos']}")
    comprobar(abs(f["Ingresos"] - 2350) < 0.005 and abs(f["Balance"] - 2250) < 0.005,
              "y el total y el balance no cambian por desglosar",
              f"{f['Ingresos']} / {f['Balance']}")
    comprobar("se llama igual" not in salida,
              "sin avisos: el choque de nombres ya está resuelto", salida)


@caso("resumen-desglose-personalizado", "Las columnas de ingreso admiten etiquetas y orden_resumen")
def prueba_resumen_desglose_personalizado(e):
    e.escribir_config("categorias.json", {
        **CATEGORIAS_DOS_INGRESOS, "desglosar_ingresos": True,
        "etiquetas": {"Nomina": "💶 Nómina", "Otros ingresos": "Resto"},
        "orden_resumen": ["Mes", "Nomina", "Otros ingresos", "Ingresos"]})
    e.escribir_config("rules.json", REGLAS_DOS_INGRESOS)
    fx.escribir_html(e.entrada / "cuenta.xls", MOVIMIENTOS_DOS_INGRESOS)
    salida = e.ejecutar()

    res = e.resumen()
    comprobar(list(res.columns) == ["Mes", "💶 Nómina", "Resto", "Ingresos"],
              "se ordenan y se renombran por su nombre de columna",
              str(list(res.columns)))
    comprobar("orden_resumen" not in salida,
              "sin avisos de nombres desconocidos", salida)


@caso("resumen-desglose-avisos", "Nombres de columna que chocan o no existen sin desglosar avisan")
def prueba_resumen_desglose_avisos(e):
    # sin el flag, pedir una categoría de ingreso en orden_resumen no hace nada
    e.escribir_config("categorias.json", {
        **CATEGORIAS_DOS_INGRESOS, "orden_resumen": ["Mes", "Nomina", "Ingresos"]})
    e.escribir_config("rules.json", REGLAS_DOS_INGRESOS)
    fx.escribir_html(e.entrada / "cuenta.xls", MOVIMIENTOS_DOS_INGRESOS)
    salida = e.ejecutar()
    comprobar("desglosar_ingresos" in salida,
              "avisa de que falta activar el desglose", salida)

    # con el flag, una categoría que ya se llama «Otros ingresos» choca con
    # la columna que toma «Ingresos»: se avisa, y el total sigue cuadrando
    e.escribir_config("categorias.json", {
        **CATEGORIAS_DOS_INGRESOS, "desglosar_ingresos": True,
        "ingresos": ["Otros ingresos", "Ingresos"]})
    e.escribir_config("rules.json", {"nomina": "Otros ingresos",
                                     "bizum": {"+": "Ingresos", "-": "Otros"}})
    salida = e.ejecutar()
    comprobar("se llama igual" in salida and "Otros ingresos" in salida,
              "avisa del choque de nombres", salida)
    comprobar(abs(e.resumen().iloc[0]["Ingresos"] - 2350) < 0.005,
              "y el total no pierde nada", str(e.resumen().iloc[0]["Ingresos"]))


@caso("resumen-primero", "El histórico se abre por RESUMEN")
def prueba_resumen_primero(e):
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL)
    e.ejecutar()

    from openpyxl import load_workbook
    wb = load_workbook(e.ruta_historico)
    comprobar(wb.sheetnames[0] == "RESUMEN" and wb.sheetnames[-1] == "_meta",
              "RESUMEN es la primera hoja (y _meta sigue la última)",
              str(wb.sheetnames))
    comprobar(wb.active.title == "RESUMEN", "y la que se ve al abrir",
              wb.active.title)
    # la guía dice «la cabecera naranja» para señalar la única columna que
    # se escribe a mano: hasta la 2.12.0 era verde como todas
    ws = wb["MOVIMIENTOS"]
    colores = {c.value: c.fill.fgColor.rgb for c in ws[1]}
    comprobar(str(colores.get("categoria_manual", "")).endswith("B4531A")
              and not str(colores.get("categoria", "")).endswith("B4531A"),
              "categoria_manual lleva la cabecera naranja, y solo ella", str(colores))
    wb.close()


def _xml_graficos(ruta):
    import zipfile
    with zipfile.ZipFile(ruta) as z:
        return [z.read(n).decode("utf-8") for n in sorted(z.namelist())
                if n.startswith("xl/charts/chart")]


@caso("graficos", "Los gráficos de RESUMEN se ven también en OnlyOffice")
def prueba_graficos(e):
    datos = ABRIL + [("05/05/2026", "COMPRA MERCADONA CENTRO", -80.00)]
    fx.escribir_html(e.entrada / "cuenta.xls", datos)
    e.ejecutar()
    xmls = _xml_graficos(e.ruta_historico)

    comprobar(len(xmls) == 3, "tres: Acumulado, ingresos y gastos, y por categoría",
              f"{len(xmls)} gráficos")
    # la causa del gráfico roto de la 2.10 (quitado en la 2.11): openpyxl
    # escribe los dos ejes a la izquierda; OnlyOffice lo obedece y pone los
    # meses en vertical, sin línea. Cada eje tiene que ir en su sitio.
    import re
    posiciones = [(re.search(r'<catAx>.*?<axPos val="(.)"', x).group(1),
                   re.search(r'<valAx>.*?<axPos val="(.)"', x).group(1))
                  for x in xmls]
    comprobar(posiciones and all(cat != val for cat, val in posiciones),
              "cada eje en un lado distinto, no los dos a la izquierda",
              f"(categorías, valores): {posiciones}")
    # sin la copia de los valores dentro, OnlyOffice lo dibujaba vacío (2.9.0)
    comprobar(all("<numCache>" in x or "<numLit>" in x for x in xmls),
              "todos llevan los valores dentro, no solo la referencia a celdas")
    comprobar("<numLit>" in xmls[2] and "Comida" in xmls[2],
              "el de categorías lleva sus medias escritas dentro", xmls[2][:300])


@caso("graficos-orden-resumen", "Sin Acumulado en orden_resumen, no hay gráfico de Acumulado")
def prueba_graficos_orden_resumen(e):
    e.escribir_config("categorias.json", {
        "gastos": ["Comida", "Otros"],
        "ingresos": ["Ingresos"],
        "neutras": ["Transferencias internas"],
        "columna_mes": "mes_ajustado",
        "orden_resumen": ["Mes", "Comida", "Otros", "Total Gastos", "Ingresos"]})
    e.escribir_config("rules.json", {"mercadona": "Comida", "nomina": "Ingresos"})
    fx.escribir_html(e.entrada / "cuenta.xls",
                     [("07/04/2026", "COMPRA MERCADONA CENTRO", -100.00),
                      ("09/04/2026", "NOMINA EMPRESA SL", 2000.00)])
    salida = e.ejecutar()
    xmls = _xml_graficos(e.ruta_historico)

    comprobar(e.ultimo_codigo == 0, "no falla", salida)
    comprobar(len(xmls) == 2 and not any("Acumulado" in x for x in xmls),
              "solo los dos que tienen sus columnas en el resumen",
              f"{len(xmls)} gráficos")


@caso("pantalla-orden", "Por pantalla: versión arriba, avisos juntos al final")
def prueba_pantalla_orden(e):
    e.escribir_config("rules.json", {"mercadona": "Categoria Inventada"})
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL)
    salida = e.ejecutar()

    comprobar("Avisos (" in salida, "hay un bloque de avisos", salida)
    comprobar("Avisos (" in salida
              and salida.index("✅") < salida.index("Avisos (")
              < salida.index("Categoria Inventada"),
              "después del resultado: ni mezclado con él ni lo primero de todo",
              salida)
    comprobar(e.ultimo_codigo == 0 and "¿Y ahora?" not in salida,
              "sin nadie delante no pregunta nada (no se queda esperando)",
              salida[-300:])


@caso("sin-color", "Con la salida capturada no sale ningún código de color")
def prueba_sin_color(e):
    # Los colores (2.11.0) son solo para una terminal de verdad. Aquí la
    # salida se captura, igual que cuando alguien la redirige a un fichero:
    # un solo código colado ensuciaría el texto y rompería las comprobaciones
    # de otros casos que buscan frases exactas. Se fuerza a que haya de todo
    # por pantalla: resultado, sin clasificar y un aviso.
    e.escribir_config("rules.json", {"mercadona": "Categoria Inventada"})
    fx.escribir_html(e.entrada / "cuenta.xls", ABRIL)
    salida = e.ejecutar()
    comprobar("✅" in salida and "Avisos (" in salida,
              "la ejecución ha contado de todo", salida)
    comprobar("\x1b[" not in salida, "y sin ningún código de color",
              repr(salida[:500]))


def _meses(dia, concepto, importes, año=2026, desde_mes=1):
    """Un cargo al mes, el mismo día, con los importes dados (uno por mes)."""
    return [(f"{dia:02d}/{desde_mes + i:02d}/{año}", concepto, imp)
            for i, imp in enumerate(importes)]


@caso("recurrentes-mensual", "Un cargo de cada mes sale, con lo que suma al año al precio de hoy")
def prueba_recurrentes_mensual(e):
    e.escribir_config("rules.json", {"netflix": "Ocio", "gimnasio": "Ocio",
                                     "mercadona": "Comida"})
    # sube de precio a mitad; la referencia del recibo cambia cada mes; el
    # de marzo pasa el día 2 en vez del 1 (fin de semana)
    datos = (_meses(3, "NETFLIX.COM", [-12.99, -12.99, -12.99, -13.99, -13.99, -13.99])
             + [(f"{d}/{m:02d}/2026", f"RECIBO GIMNASIO REF {m}{m}731", -35.00)
                for d, m in (("01", 2), ("02", 3), ("01", 4), ("01", 5), ("01", 6))]
             + [("20/06/2026", "COMPRA MERCADONA CENTRO", -60.00)])
    fx.escribir_html(e.entrada / "cuenta.xls", datos)
    salida = e.ejecutar()

    comprobar("🔁 2 cargos que se repiten" in salida,
              "encuentra los dos, y nada más", salida)
    comprobar("167,88 €/año" in salida and "13,99 € mensual" in salida,
              "al importe de hoy (13,99 × 12), no al antiguo", salida)
    comprobar("420,00 €/año" in salida,
              "y agrupa el recibo aunque la referencia cambie cada mes", salida)
    comprobar(salida.index("420,00 €/año") < salida.index("167,88 €/año"),
              "de más a menos coste al año", salida)
    for palabra in ("deberías", "cancela", "ahorra"):
        comprobar(palabra not in salida.lower(),
                  f"sin opinar: no dice «{palabra}»", salida)


@caso("recurrentes-no", "Lo que no es un cargo regular no sale")
def prueba_recurrentes_no(e):
    datos = (
        # la compra: muchas veces, fechas e importes irregulares
        [(f"{d:02d}/{m:02d}/2026", "COMPRA MERCADONA CENTRO", -(40 + d + m))
         for m in range(1, 7) for d in (4, 11, 19, 26)]
        # solo dos cargos: todavía no es una serie
        + _meses(5, "SPOTIFY", [-10.99, -10.99], desde_mes=5)
        # cada mes, pero con importes que no se parecen de nada
        + _meses(8, "CINE YELMO", [-9.00, -45.00, -18.00, -80.00])
        # regular, pero es un traspaso a otra cuenta tuya, no un gasto
        + _meses(1, "TRASPASO A AHORRO", [-200.0] * 6)
        # regular... hasta que se dio de baja en febrero
        + _meses(10, "HBO MAX", [-8.99] * 4, año=2025, desde_mes=9)
        + _meses(10, "HBO MAX", [-8.99, -8.99])
        # el de control: este sí, para saber que el informe se ha ejecutado
        + _meses(3, "NETFLIX.COM", [-13.99] * 6))
    e.escribir_config("rules.json", {"mercadona": "Comida", "spotify": "Ocio",
                                     "cine": "Ocio", "traspaso": "Transferencias internas",
                                     "hbo": "Ocio", "netflix": "Ocio"})
    fx.escribir_html(e.entrada / "cuenta.xls", datos)
    salida = e.ejecutar()

    comprobar("🔁 1 cargo que se repite" in salida and "NETFLIX" in salida,
              "solo sale el de control", salida)
    informe = salida[salida.find("🔁"):]
    for concepto in ("MERCADONA", "SPOTIFY", "CINE", "TRASPASO", "HBO"):
        comprobar(concepto not in informe, f"{concepto} no sale", informe)


@caso("recurrentes-anual", "Un seguro anual sale con solo dos cargos")
def prueba_recurrentes_anual(e):
    e.escribir_config("rules.json", {"seguro hogar": "Piso",
                                     "mercadona": "Comida"})
    datos = [("15/03/2025", "SEGURO HOGAR POLIZA 88123", -280.00),
             ("14/03/2026", "SEGURO HOGAR POLIZA 88124", -295.00),
             ("20/06/2026", "COMPRA MERCADONA CENTRO", -60.00)]
    fx.escribir_html(e.entrada / "cuenta.xls", datos)
    salida = e.ejecutar()

    comprobar("295,00 €/año" in salida and "anual" in salida,
              "sale como anual, al importe del último", salida)


@caso("signo", "Un Bizum recibido no es lo mismo que uno enviado")
def prueba_signo(e):
    datos = [("07/04/2026", "BIZUM A AMIGA CENA", -18.00),
             ("09/04/2026", "BIZUM DE AMIGA ALQUILER", 350.00)]
    fx.escribir_html(e.entrada / "cuenta.xls", datos)
    e.escribir_config("rules.json",
                      {"bizum": {"+": "Ingresos", "-": "Ocio"}})
    e.ejecutar()

    df = e.historico()
    comprobar(categoria_de(df, "BIZUM A AMIGA") == "Ocio",
              "el enviado es gasto", str(categoria_de(df, "BIZUM A AMIGA")))
    comprobar(categoria_de(df, "BIZUM DE AMIGA") == "Ingresos",
              "el recibido es ingreso", str(categoria_de(df, "BIZUM DE AMIGA")))

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
    datos = [("07/04/2026", "COMPRA MERCADONA CENTRO", -100.00),
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
                     [("05/04/2026", "COMPRA MERCADONA CENTRO", -10.00)])
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
                     [("05/04/2026", "COMPRA MERCADONA CENTRO", -10.00)])
    salida = e.ejecutar()

    cfg = e.leer_config("mes_contable.json")
    # «pension» entra en la plantilla en la 2.12.1: la cobra el día 1 o 2 y
    # es la del mes anterior, igual que la nómina (salió en el piloto)
    comprobar(cfg["palabras"] == ["nomina", "pension"],
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
    # 2 = "ya lo he explicado y he esperado a que se leyera": los lanzadores
    # lo usan para no pedir que se pulse una tecla dos veces
    comprobar(e.ultimo_codigo == 2, "con el código de error ya explicado",
              str(e.ultimo_codigo))
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
    # los saltos de línea al revés de como deben ir, como en una copia de
    # trabajo que no se ha vuelto a descargar: el ZIP tiene que salir bien igual
    bat, sh = e.dir / "ejecutar.bat", e.dir / "ejecutar.sh"
    bat.write_bytes(bat.read_bytes().replace(b"\r\n", b"\n"))
    sh.write_bytes(sh.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    salida = e.exportar()
    comprobar(e.ultimo_codigo == 0, "el exportador termina bien", salida)

    zips = list(e.dir.glob("*.zip"))
    comprobar(len(zips) == 1, "se crea un ZIP", f"{len(zips)} encontrados")
    if not zips:
        return

    with zipfile.ZipFile(zips[0]) as z:
        en_zip_bat = z.read("ejecutar.bat")
        en_zip_sh = z.read("ejecutar.sh")
    comprobar(b"\r\n" in en_zip_bat
              and en_zip_bat.count(b"\n") == en_zip_bat.count(b"\r\n"),
              "los .bat van con saltos de Windows, vengan como vengan")
    comprobar(b"\r" not in en_zip_sh,
              "y los .sh sin \\r, que bash no los arranca")

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

    with zipfile.ZipFile(zips[0]) as z:
        for nombre in ("instalar.sh", "ejecutar.sh", "exportar.sh",
                       "instalar.command", "ejecutar.command",
                       "exportar.command"):
            modo = z.getinfo(nombre).external_attr >> 16
            comprobar(modo & 0o111 != 0,
                      f"{nombre} lleva el permiso de ejecución dentro del ZIP "
                      f"(da igual el sistema operativo donde se generó)",
                      oct(modo))

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
                          ("07/04/2026", "COMPRA CARREFOUR CENTRO", -50.00)])

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
             exe=str(e.dir / "eledger.exe"),
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
    spec = RAIZ / "eledger.spec"
    comprobar(spec.exists(), "hay un eledger.spec")
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
              "y el de Linux hace lo mismo")

    # el programa ya espera él solo (menú final, o "Pulsa Intro" si falla) y
    # sale con 0 o 2; si el lanzador volviera a pausar en esos casos, habría
    # que pulsar dos veces. El número tiene que ser el mismo en los tres sitios.
    proceso = (RAIZ / DIR_APP / "process.py").read_text(encoding="utf-8")
    comprobar("CODIGO_ERROR_EXPLICADO = 2" in proceso
              and '"%CODIGO%"=="2"' in bat and "-eq 2" in sh,
              "los lanzadores no pausan otra vez si el programa ya lo ha hecho")
    comprobar(sh == (RAIZ / "ejecutar.command").read_text(encoding="utf-8"),
              "ejecutar.command y ejecutar.sh son el mismo")

    # Mac y Linux ejecutan estos por doble clic de verdad (a diferencia de
    # .bat, que Windows abre por asociación): sin el bit +x no arrancan.
    import os as _os
    for nombre in ("instalar.sh", "ejecutar.sh", "exportar.sh",
                   "instalar.command", "ejecutar.command", "exportar.command"):
        comprobar(_os.access(RAIZ / nombre, _os.X_OK),
                  f"{nombre} tiene permiso de ejecución en el repositorio")

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
