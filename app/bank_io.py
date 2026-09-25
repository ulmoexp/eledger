"""
bank_io.py — Lectura universal de extractos bancarios.

100% local: no hace ninguna conexión de red, no escribe temporales fuera
de la carpeta del proyecto, no envía nada a ningún sitio.

El problema que resuelve: los bancos españoles llaman ".xls" a cosas muy
distintas. Este módulo mira los bytes reales del fichero (no la extensión)
y elige el lector correcto:

  - OLE2 / BIFF  -> .xls "de verdad" (Excel 97-2003)   [requiere xlrd]
  - ZIP / PK     -> en realidad es .xlsx renombrado    [openpyxl]
  - <html>       -> tabla HTML renombrada a .xls       [parser propio]
  - <?xml ...>   -> SpreadsheetML 2003                 [parser propio]
  - texto plano  -> CSV/TSV renombrado                 [csv de stdlib]

Uso típico:
    from bank_io import leer_tabla_bancaria
    df = leer_tabla_bancaria("movimientos.xls",
                             requeridas=("fecha", "concepto", "importe"))
"""

from __future__ import annotations

import csv
import datetime as _dt
import io
import os
import re
import unicodedata
import zipfile
from html.parser import HTMLParser
from xml.etree import ElementTree as ET

import pandas as pd


# =====================================================================
# 1. DETECCIÓN DE FORMATO REAL (por contenido, no por extensión)
# =====================================================================

def detectar_formato(ruta: str) -> str:
    """Devuelve: 'xls_biff' | 'xlsx' | 'html' | 'xml_ss' | 'texto' | 'ods' | 'desconocido'."""
    with open(ruta, "rb") as fh:
        cabecera = fh.read(8192)

    if cabecera[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "xls_biff"                      # contenedor OLE2 (Excel 97-2003)

    if cabecera[:4] == b"PK\x03\x04":
        # xlsx y ods son ambos ZIP; hay que mirar dentro
        try:
            with zipfile.ZipFile(ruta) as z:
                nombres = z.namelist()
            if any(n.startswith("xl/") for n in nombres):
                return "xlsx"
            if "content.xml" in nombres:
                return "ods"
        except zipfile.BadZipFile:
            pass
        return "xlsx"

    if cabecera[:2] == b"\x09\x00" or cabecera[:2] == b"\x09\x04":
        return "xls_biff"                      # BIFF2/BIFF4 "crudo", sin OLE

    muestra = cabecera.decode("latin-1", errors="replace").lstrip("\ufeff \t\r\n").lower()

    if muestra.startswith("<?xml"):
        return "xml_ss" if "spreadsheet" in muestra else "html"
    if muestra.startswith(("<html", "<!doctype html", "<table", "<meta", "<head")):
        return "html"
    if "<table" in muestra[:4000]:
        return "html"

    # ¿es texto legible? entonces CSV/TSV
    try:
        cabecera.decode("utf-8")
        return "texto"
    except UnicodeDecodeError:
        pass
    if sum(1 for b in cabecera if b == 0) == 0:
        return "texto"

    return "desconocido"


def _decodificar(datos: bytes) -> str:
    """Los bancos españoles usan utf-8, cp1252 o latin-1 sin avisar."""
    m = re.search(rb'charset=["\']?\s*([\w\-]+)', datos[:4096], re.I)
    candidatos = []
    if m:
        candidatos.append(m.group(1).decode("ascii", "ignore"))
    candidatos += ["utf-8-sig", "utf-8", "cp1252", "latin-1"]
    for enc in candidatos:
        try:
            return datos.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return datos.decode("latin-1", errors="replace")


# =====================================================================
# 2. LECTORES POR FORMATO -> lista de tablas "crudas" (list[list[str]])
# =====================================================================

class _ExtractorTablasHTML(HTMLParser):
    """Parser de tablas HTML con la librería estándar (sin lxml ni bs4)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tablas: list[list[list[str]]] = []
        self._pila: list[list[list[str]]] = []
        self._fila: list[str] | None = None
        self._celda: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._pila.append([])
        elif tag == "tr" and self._pila:
            self._fila = []
        elif tag in ("td", "th") and self._fila is not None:
            self._celda = []
        elif tag == "br" and self._celda is not None:
            self._celda.append(" ")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._celda is not None:
            self._fila.append("".join(self._celda).strip())
            self._celda = None
        elif tag == "tr" and self._fila is not None:
            if self._celda is not None:          # celda sin cerrar
                self._fila.append("".join(self._celda).strip())
                self._celda = None
            if self._pila:
                self._pila[-1].append(self._fila)
            self._fila = None
        elif tag == "table" and self._pila:
            tabla = self._pila.pop()
            if tabla:
                self.tablas.append(tabla)

    def handle_data(self, data):
        if self._celda is not None:
            self._celda.append(data.replace("\xa0", " "))

    def close(self):
        super().close()
        while self._pila:                        # tablas sin </table>
            tabla = self._pila.pop()
            if tabla:
                self.tablas.append(tabla)


def _leer_html(ruta: str) -> list[list[list[str]]]:
    texto = _decodificar(open(ruta, "rb").read())
    p = _ExtractorTablasHTML()
    p.feed(texto)
    p.close()
    return p.tablas


def _leer_xml_spreadsheet(ruta: str) -> list[list[list[str]]]:
    """SpreadsheetML 2003 (<?xml ...><Workbook xmlns='...:spreadsheet'>)."""
    NS = "{urn:schemas-microsoft-com:office:spreadsheet}"
    raiz = ET.parse(ruta).getroot()
    tablas = []
    for hoja in raiz.iter(f"{NS}Worksheet"):
        for tabla in hoja.iter(f"{NS}Table"):
            filas = []
            for fila in tabla.iter(f"{NS}Row"):
                celdas, col = [], 0
                for celda in fila.iter(f"{NS}Cell"):
                    idx = celda.get(f"{NS}Index")
                    if idx:                       # celdas vacías saltadas
                        col = int(idx) - 1
                        while len(celdas) < col:
                            celdas.append("")
                    datos = celda.find(f"{NS}Data")
                    celdas.append("" if datos is None else "".join(datos.itertext()).strip())
                    col += 1
                filas.append(celdas)
            if filas:
                tablas.append(filas)
    return tablas


def _leer_texto(ruta: str) -> list[list[list[str]]]:
    texto = _decodificar(open(ruta, "rb").read())
    # el sniffer de csv falla con ficheros con preámbulo, así que contamos a mano
    lineas = [l for l in texto.splitlines() if l.strip()][:40]
    mejor, mejor_score = ";", -1
    for sep in (";", "\t", ",", "|"):
        cuentas = [l.count(sep) for l in lineas]
        if not cuentas or max(cuentas) == 0:
            continue
        moda = max(set(cuentas), key=cuentas.count)
        score = moda * sum(1 for c in cuentas if c == moda)
        if moda and score > mejor_score:
            mejor, mejor_score = sep, score
    filas = list(csv.reader(io.StringIO(texto), delimiter=mejor))
    return [[[c.strip() for c in f] for f in filas]] if filas else []


def _leer_xls_biff(ruta: str) -> list[list]:
    try:
        import xlrd
    except ImportError:
        raise RuntimeError(
            f"'{os.path.basename(ruta)}' es un .xls real (Excel 97-2003) y hace "
            "falta la librería 'xlrd' para leerlo.\n"
            "   Vuelve a lanzar el instalador (instalar.bat, .command o .sh):\n"
            "   la instala en el entorno de la herramienta."
        )
    import datetime as _dt

    libro = xlrd.open_workbook(ruta, formatting_info=False, on_demand=False)
    tablas = []
    for hoja in libro.sheets():
        filas = []
        for r in range(hoja.nrows):
            fila = []
            for c in range(hoja.ncols):
                celda = hoja.cell(r, c)
                if celda.ctype == xlrd.XL_CELL_DATE:
                    try:
                        y, mo, d, h, mi, s = xlrd.xldate_as_tuple(celda.value, libro.datemode)
                        fila.append(_dt.datetime(y or 1900, mo or 1, d or 1, h, mi, s))
                    except (ValueError, xlrd.XLDateError):
                        fila.append("")
                elif celda.ctype == xlrd.XL_CELL_NUMBER:
                    # se conserva como float; parsear_* ya trata números nativos
                    fila.append(float(celda.value))
                elif celda.ctype == xlrd.XL_CELL_BOOLEAN:
                    fila.append("1" if celda.value else "0")
                elif celda.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_ERROR, xlrd.XL_CELL_BLANK):
                    fila.append("")
                else:
                    fila.append(str(celda.value).strip())
            filas.append(fila)
        if filas:
            tablas.append(filas)
    return tablas


def _leer_zip_excel(ruta: str, motor: str) -> list[list]:
    hojas = pd.read_excel(ruta, sheet_name=None, header=None, engine=motor)
    tablas = []
    for df in hojas.values():
        filas = []
        for fila in df.where(pd.notna(df), "").values.tolist():
            filas.append([v.strip() if isinstance(v, str) else v for v in fila])
        if filas:
            tablas.append(filas)
    return tablas


_LECTORES = {
    "xls_biff": _leer_xls_biff,
    "xlsx": lambda r: _leer_zip_excel(r, "openpyxl"),
    "ods": lambda r: _leer_zip_excel(r, "odf"),
    "html": _leer_html,
    "xml_ss": _leer_xml_spreadsheet,
    "texto": _leer_texto,
}


def leer_tablas_crudas(ruta: str) -> tuple[str, list[list[list[str]]]]:
    """Devuelve (formato_detectado, lista de tablas como listas de listas de str)."""
    fmt = detectar_formato(ruta)
    if fmt not in _LECTORES:
        raise RuntimeError(
            f"No reconozco el formato de '{os.path.basename(ruta)}'. "
            "Ábrelo con un editor de texto para ver qué es realmente."
        )
    return fmt, _LECTORES[fmt](ruta)


# =====================================================================
# 3. LOCALIZAR LA FILA DE CABECERA Y MAPEAR COLUMNAS
# =====================================================================

def normalizar_cabecera(texto) -> str:
    """'Importe de la Operación (€)' -> 'importe de la operacion'."""
    t = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    t = t.lower().replace("\n", " ")
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# Sinónimos por columna, EN ORDEN DE PREFERENCIA.
# Amplía estas listas cuando aparezca un banco con nombres nuevos.
ALIAS_COLUMNAS = {
    "fecha": [
        "fecha operacion", "fecha de operacion", "fecha de la operacion",
        "f operacion", "fecha movimiento", "fecha contable", "fecha compra",
        "fecha", "fecha valor", "f valor", "date",
    ],
    "descripcion": [
        "concepto", "concepto ampliado", "descripcion", "descripcion ampliada",
        "detalle", "comercio", "establecimiento", "movimiento", "observaciones",
        "concepto comun", "description", "payee", "counterparty",
    ],
    "importe": [
        "importe de la operacion", "importe operacion", "importe eur",
        "importe en euros", "importe", "importe movimiento", "cantidad",
        "euros", "amount",
    ],
    # opcional: no está en `requeridas`, así que su ausencia nunca hace fallar
    # la lectura. Cuando aparece, es lo que permite calcular_saldo_inicial()
    # en process.py: con qué dinero empezaba la cuenta antes del primer
    # movimiento que se tiene.
    "saldo": ["saldo", "saldo posterior", "saldo disponible"],
}

# Algunos bancos no dan un importe con signo sino DOS columnas: lo que sale
# (Cargo, Debe) y lo que entra (Abono, Haber). Solo se usan si no hay columna
# de importe, y solo por coincidencia EXACTA: «cargo» a secas aparece dentro
# de cabeceras que no son importes («tipo de cargo», «fecha de cargo»).
# La categoría que ya trae el fichero (el export de otra app de finanzas).
# Solo se usa si el usuario lo pide en categorias.json (importar_categorias):
# hay bancos que exportan su propia «Categoría», y no puede pisar las reglas
# sin que nadie lo haya decidido. Solo coincidencia exacta.
ALIAS_CATEGORIA = ["categoria", "category", "categoria del movimiento"]

ALIAS_CARGO = ["cargo", "cargos", "debe", "debito", "debit", "importe cargo"]
ALIAS_ABONO = ["abono", "abonos", "haber", "credito", "credit", "importe abono"]


def _columna_exacta(cabecera, alias) -> int | None:
    normalizadas = [normalizar_cabecera(c) for c in cabecera]
    for a in alias:
        if a in normalizadas:
            return normalizadas.index(a)
    return None


def _puntuar_fila_cabecera(fila, requeridas) -> int:
    normalizadas = [normalizar_cabecera(c) for c in fila]
    puntos = 0
    for campo in requeridas:
        alias = ALIAS_COLUMNAS[campo]
        if any(n == a for n in normalizadas for a in alias):
            puntos += 2                                    # coincidencia exacta
        elif any(a in n for n in normalizadas if n for a in alias):
            puntos += 1                                    # coincidencia parcial
    return puntos


def localizar_cabecera(tabla, requeridas, max_filas=60) -> int:
    """Índice de la fila que hace de cabecera. -1 si no la encuentra."""
    mejor, mejor_p = -1, 0
    for i, fila in enumerate(tabla[:max_filas]):
        p = _puntuar_fila_cabecera(fila, requeridas)
        if p > mejor_p:
            mejor, mejor_p = i, p
    return mejor if mejor_p >= len(requeridas) else -1


def mapear_columnas(cabecera, requeridas) -> dict:
    """{'fecha': 0, 'descripcion': 2, 'importe': 5}"""
    normalizadas = [normalizar_cabecera(c) for c in cabecera]
    usadas, mapa = set(), {}
    for campo in requeridas:
        elegido = None
        for alias in ALIAS_COLUMNAS[campo]:                 # exacto primero
            for i, n in enumerate(normalizadas):
                if n == alias and i not in usadas:
                    elegido = i
                    break
            if elegido is not None:
                break
        if elegido is None:                                 # luego parcial
            for alias in ALIAS_COLUMNAS[campo]:
                for i, n in enumerate(normalizadas):
                    if n and alias in n and i not in usadas:
                        elegido = i
                        break
                if elegido is not None:
                    break
        if elegido is not None:
            usadas.add(elegido)
            mapa[campo] = elegido
    return mapa


# =====================================================================
# 4. CONVERSIÓN DE VALORES (formato español)
# =====================================================================

_RE_LIMPIEZA = re.compile(r"[^\d,.\-+()]")


def parsear_importe(valor):
    """'1.234,56 €' -> 1234.56 ; '(45,00)' -> -45.0 ; '12,50-' -> -12.5"""
    if valor is None or isinstance(valor, float) and pd.isna(valor):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)

    s = str(valor).strip()
    if not s:
        return None

    negativo = s.startswith("(") and s.endswith(")") or s.endswith("-")
    s = _RE_LIMPIEZA.sub("", s).strip("()")
    if s.endswith("-"):
        s = s[:-1]
    if s.startswith("-"):
        negativo = True
        s = s[1:]
    s = s.lstrip("+")
    if not s:
        return None

    # Heurística de separadores, sesgada a formato español (coma decimal):
    #   "1.234,56" -> mixto: manda el símbolo más a la derecha
    #   "1,50"     -> coma única = decimal
    #   "1,234,567"-> comas múltiples = miles
    #   "1.234"    -> punto único con 3 cifras detrás = miles
    #   "12.50"    -> punto único con != 3 cifras detrás = decimal
    tiene_punto, tiene_coma = "." in s, "," in s
    if tiene_punto and tiene_coma:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif tiene_coma:
        s = s.replace(",", ".") if s.count(",") == 1 else s.replace(",", "")
    elif tiene_punto:
        if s.count(".") > 1 or len(s.split(".")[-1]) == 3:
            s = s.replace(".", "")

    try:
        n = float(s)
    except ValueError:
        return None
    return -n if negativo else n


def parsear_fecha(valor):
    """Acepta datetime, 'dd/mm/aaaa', 'aaaa-mm-dd', '15 abr 2026' y serial de Excel."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return pd.NaT
    if isinstance(valor, (pd.Timestamp, _dt.datetime, _dt.date)):
        return pd.Timestamp(valor)
    if isinstance(valor, (int, float)):
        # serial de Excel devuelto como número crudo
        if 20000 < valor < 60000:
            return pd.Timestamp("1899-12-30") + pd.to_timedelta(float(valor), unit="D")
        return pd.NaT
    s = str(valor).strip()
    if not s:
        return pd.NaT

    # serial de Excel (por si un lector devolvió el número crudo)
    if re.fullmatch(r"\d{5}(\.\d+)?", s):
        try:
            return pd.Timestamp("1899-12-30") + pd.to_timedelta(float(s), unit="D")
        except (ValueError, OverflowError):
            pass

    MESES = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
             "jul": 7, "ago": 8, "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12}
    m = re.match(r"^(\d{1,2})[\s\-/]*([a-zA-ZáéíóúÁÉÍÓÚ]{3,})[\s\-/]*(\d{2,4})$", s)
    if m:
        mes = MESES.get(normalizar_cabecera(m.group(2))[:3])
        if mes:
            anio = int(m.group(3))
            anio += 2000 if anio < 100 else 0
            try:
                return pd.Timestamp(year=anio, month=mes, day=int(m.group(1)))
            except ValueError:
                return pd.NaT

    # ISO (aaaa-mm-dd) no debe pasar por dayfirst o se invierte
    if re.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}", s):
        return pd.to_datetime(s, errors="coerce")

    return pd.to_datetime(s, dayfirst=True, errors="coerce")


def _importe_de_dos_columnas(cargo, abono):
    """Lo que entra menos lo que sale. Hay bancos que ponen el cargo en
    positivo y otros en negativo: cuenta lo que vale, no el signo que traiga.
    Las dos vacías es una fila sin importe (None), no un movimiento de 0 €."""
    c, a = parsear_importe(cargo), parsear_importe(abono)
    if c is None and a is None:
        return None
    return abs(a or 0.0) - abs(c or 0.0)


# =====================================================================
# 5. FUNCIÓN PRINCIPAL
# =====================================================================

def leer_tabla_bancaria(ruta: str, requeridas=("fecha", "descripcion", "importe"),
                        verbose: bool = True) -> pd.DataFrame:
    """
    Lee cualquier extracto bancario y devuelve un DataFrame con las columnas
    'fecha' (datetime), 'descripcion' (str) e 'importe' (float), más 'saldo'
    (float, NaN si el extracto no trae esa columna).
    """
    nombre = os.path.basename(ruta)
    # una descarga que no terminó deja un fichero de 0 bytes, que se leía
    # «bien» como texto y acababa mandando a editar el código
    if os.path.getsize(ruta) == 0:
        raise RuntimeError(
            f"'{nombre}' está vacío (0 bytes): la descarga no terminó bien.\n"
            "   Vuelve a descargarlo del banco.")
    fmt, tablas = leer_tablas_crudas(ruta)

    candidatas = []
    for tabla in tablas:
        i = localizar_cabecera(tabla, requeridas)
        if i < 0 and "importe" in requeridas:
            # sin columna de importe la cabecera puntúa de menos; con Cargo y
            # Abono, se busca sin exigir el importe
            sin_importe = tuple(c for c in requeridas if c != "importe")
            j = localizar_cabecera(tabla, sin_importe)
            if j >= 0 and _columna_exacta(tabla[j], ALIAS_CARGO) is not None \
                    and _columna_exacta(tabla[j], ALIAS_ABONO) is not None:
                i = j
        if i >= 0:
            candidatas.append((len(tabla) - i, i, tabla))
    if not candidatas:
        raise RuntimeError(
            f"'{nombre}' se ha podido abrir (formato: {fmt}), pero no encuentro "
            f"las columnas de fecha, concepto e importe.\n"
            "   Puede que no sea un extracto de movimientos. Si lo es, tu banco usa "
            "otros nombres\n   de columna: mira «Cuando algo no sale» en la guía."
        )

    _, idx_cab, tabla = max(candidatas)          # la tabla con más datos útiles
    cabecera = tabla[idx_cab]
    mapa = mapear_columnas(cabecera, requeridas)
    cargo_abono = None
    if "importe" not in mapa:
        cargo = _columna_exacta(cabecera, ALIAS_CARGO)
        abono = _columna_exacta(cabecera, ALIAS_ABONO)
        if cargo is not None and abono is not None:
            cargo_abono = (cargo, abono)
    faltan = [c for c in requeridas
              if c not in mapa and not (c == "importe" and cargo_abono)]
    if faltan:
        raise RuntimeError(
            f"'{nombre}': no localizo las columnas {faltan}. "
            f"Cabecera detectada: {[c for c in cabecera if str(c).strip()]}"
        )

    # el saldo es opcional: si el banco no lo trae, la lectura no falla, solo
    # no se podrá calcular el saldo inicial de la cuenta más adelante.
    mapa_saldo = mapear_columnas(cabecera, ("saldo",))
    if "saldo" in mapa_saldo and mapa_saldo["saldo"] not in mapa.values():
        mapa["saldo"] = mapa_saldo["saldo"]

    col_categoria = _columna_exacta(cabecera, ALIAS_CATEGORIA)
    if col_categoria in mapa.values():
        col_categoria = None

    registros = []
    for fila in tabla[idx_cab + 1:]:
        if not any(str(c).strip() for c in fila if c is not None):
            continue
        reg = {}
        for campo, col in mapa.items():
            reg[campo] = fila[col] if col < len(fila) else None
        if cargo_abono:
            reg["importe"] = _importe_de_dos_columnas(
                *(fila[c] if c < len(fila) else None for c in cargo_abono))
        if col_categoria is not None and col_categoria < len(fila):
            reg["categoria_fichero"] = fila[col_categoria]
        registros.append(reg)

    df = pd.DataFrame(registros, columns=list(requeridas) + ["saldo", "categoria_fichero"])
    df["fecha"] = df["fecha"].map(parsear_fecha)
    if not cargo_abono:
        df["importe"] = df["importe"].map(parsear_importe)
    df["saldo"] = df["saldo"].map(parsear_importe)
    df["descripcion"] = df["descripcion"].map(
        lambda v: "" if v is None else str(v).strip()
    )
    df["categoria_fichero"] = df["categoria_fichero"].map(
        lambda v: "" if v is None or (isinstance(v, float) and pd.isna(v))
        else str(v).strip())

    antes = len(df)
    df = df.dropna(subset=["fecha", "importe"])
    df = df[df["descripcion"].str.strip().ne("") & df["descripcion"].ne("nan")]

    df.attrs["formato"] = fmt
    df.attrs["fichero"] = nombre
    df.attrs["fila_cabecera"] = idx_cab
    df.attrs["cabecera"] = [normalizar_cabecera(c) for c in cabecera if str(c).strip()]

    if verbose:
        print(f"   · {nombre}: formato={fmt}, cabecera en fila {idx_cab + 1}, "
              f"{len(df)} movimientos ({antes - len(df)} filas descartadas)")
    return df.reset_index(drop=True)


# =====================================================================
# 5b. ¿ES UN EXTRACTO DE CUENTA O DE TARJETA?
# =====================================================================

# Pistas por CONTENIDO (nombres de columna). Mandan sobre el nombre del fichero.
# Los mismos alias que ALIAS_COLUMNAS["saldo"]: una columna de saldo es la
# pista más fiable de que esto es una cuenta y no una tarjeta.
PISTAS_CUENTA_COL = tuple(ALIAS_COLUMNAS["saldo"])
PISTAS_TARJETA_COL = ("importe de la operacion", "importe operacion",
                      "numero de tarjeta", "tarjeta")

# Pistas por NOMBRE DE FICHERO, solo si el contenido no ha decidido.
PISTAS_TARJETA_NOMBRE = ("tarjeta", "credito", "crédito", "visa", "mastercard", "amex")
PISTAS_CUENTA_NOMBRE = ("cuenta", "movimiento", "extracto", "corriente")


def detectar_tipo(df) -> tuple[str, str]:
    """
    Decide si un extracto ya leído es de 'cuenta' o de 'tarjeta'.
    Devuelve (tipo, motivo) para poder explicarlo por pantalla.
    """
    cabecera = df.attrs.get("cabecera", [])
    nombre = normalizar_cabecera(df.attrs.get("fichero", ""))

    for col in cabecera:
        if col in PISTAS_CUENTA_COL:
            return "cuenta", f"columna «{col}»"
    for col in cabecera:
        if any(p in col for p in PISTAS_TARJETA_COL):
            return "tarjeta", f"columna «{col}»"

    for p in PISTAS_TARJETA_NOMBRE:
        if p in nombre:
            return "tarjeta", f"el nombre contiene «{p}»"
    for p in PISTAS_CUENTA_NOMBRE:
        if p in nombre:
            return "cuenta", f"el nombre contiene «{p}»"

    return "cuenta", "sin pistas claras, asumo cuenta"


# =====================================================================
# 6. DIAGNÓSTICO — python bank_io.py <fichero>
# =====================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Uso: python bank_io.py <fichero_del_banco>")
        raise SystemExit(1)

    for ruta in sys.argv[1:]:
        print(f"\n=== {ruta} ===")
        try:
            fmt, tablas = leer_tablas_crudas(ruta)
            print(f"Formato real: {fmt}   (extensión: {os.path.splitext(ruta)[1]})")
            print(f"Tablas/hojas encontradas: {len(tablas)}")
            for n, t in enumerate(tablas):
                print(f"\n-- tabla {n}: {len(t)} filas --")
                for i, fila in enumerate(t[:12]):
                    print(f"  [{i}] {fila[:8]}")
                i = localizar_cabecera(t, ("fecha", "descripcion", "importe"))
                print(f"  cabecera detectada: fila {i}" if i >= 0
                      else "  cabecera detectada: NINGUNA")
                if i >= 0:
                    print(f"  mapeo: {mapear_columnas(t[i], ('fecha','descripcion','importe'))}")
        except Exception as e:
            print(f"ERROR: {e}")
