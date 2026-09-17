"""
historico.py — Acumula los movimientos entre ejecuciones y construye el resumen
mensual por categorías.

Idea de fondo: el histórico guarda los movimientos EN CRUDO (fecha, descripción,
importe, tipo, origen). La categoría NO se congela, se vuelve a calcular en cada
ejecución. Así, cuando afines rules.json, todo el histórico se reclasifica solo
en vez de arrastrar para siempre las decisiones viejas.
"""

from __future__ import annotations

import os

import pandas as pd

from reglas import normalizar

HOJA_MOVIMIENTOS = "MOVIMIENTOS"
HOJA_RESUMEN = "RESUMEN"
HOJA_META = "_meta"

# Versión que se supone en un histórico sin hoja _meta, es decir, uno escrito
# antes de que existiera el versionado.
VERSION_SIN_SELLO = "1.0.0"

# Lo que identifica a un movimiento. 'n_rep' distingue repeticiones legítimas
# (dos cargos idénticos el mismo día en el mismo sitio son dos gastos reales).
#
# 'categoria_manual' es la única columna del fichero que TÚ puedes escribir.
# Sirve para corregir una línea suelta que ninguna regla puede distinguir: el
# Bizum que un mes es un regalo y otro la parte del alquiler. Se lee del
# histórico anterior y se conserva, ejecución tras ejecución.
COLUMNAS_CRUDAS = ["fecha", "descripcion", "importe", "tipo", "origen", "n_rep",
                   "categoria_manual", "saldo"]

# Valor especial de 'categoria_manual' para sacar una línea de los totales.
MARCA_EXCLUIDO = "(excluido)"


def _clave(df: pd.DataFrame) -> pd.Series:
    return (pd.to_datetime(df["fecha"]).dt.strftime("%Y-%m-%d") + "|"
            + df["descripcion"].map(normalizar) + "|"
            + df["importe"].astype(float).round(2).map("{:.2f}".format) + "|"
            + df["tipo"].astype(str))


# =====================================================================
# VERSIONADO DEL HISTÓRICO
# =====================================================================
#
# El histórico es un fichero que sobrevive a las versiones del programa, así
# que hay que saber quién lo escribió. Antes esto se apañaba con parches del
# tipo «si la columna no existe, créala», que funcionan pero no dejan rastro y
# se acumulan sin que nadie sepa cuáles siguen haciendo falta.
#
# Con el sello de versión en la hoja _meta pasan a ser migraciones explícitas:
# cada una dice de qué versión a cuál lleva, se aplica una sola vez y se cuenta
# por pantalla cuando se aplica.

def _numero(v: str) -> tuple:
    """'2.0.0' -> (2, 0, 0). Para poder comparar versiones."""
    partes = []
    for trozo in str(v).split("."):
        digitos = "".join(c for c in trozo if c.isdigit())
        partes.append(int(digitos) if digitos else 0)
    while len(partes) < 3:
        partes.append(0)
    return tuple(partes[:3])


def _añadir_categoria_manual(df):
    """1.0.0 -> 1.1.0. La columna que el usuario puede escribir a mano."""
    if "categoria_manual" in df.columns:
        return df, False
    df["categoria_manual"] = ""
    return df, True


def _añadir_saldo(df):
    """2.2.0 -> 2.3.0. El saldo que traía el extracto de cuenta en cada fila,
    si lo traía: en blanco para lo que ya hubiera, que no puede saberse a
    toro pasado. calcular_saldo_inicial() en process.py ya sabe vivir sin
    él (usa 0 si no encuentra ninguno)."""
    if "saldo" in df.columns:
        return df, False
    df["saldo"] = pd.NA
    return df, True


# (versión en la que se introdujo, qué hace, función)
MIGRACIONES = [
    ("1.1.0", "añadida la columna «categoria_manual»", _añadir_categoria_manual),
    ("2.3.0", "añadida la columna «saldo»", _añadir_saldo),
]


def migrar(df, version_origen: str):
    """Aplica las migraciones pendientes. Devuelve (df, lista de aplicadas)."""
    origen = _numero(version_origen)
    aplicadas = []
    for destino, descripcion, funcion in MIGRACIONES:
        if origen >= _numero(destino):
            continue
        df, hecha = funcion(df)
        if hecha:
            aplicadas.append(descripcion)
    return df, aplicadas


def leer_meta(ruta) -> dict:
    """Lee la hoja _meta. Devuelve {} si el fichero no la tiene."""
    try:
        meta = pd.read_excel(ruta, sheet_name=HOJA_META)
    except Exception:
        return {}
    if meta.empty or len(meta.columns) < 2:
        return {}
    clave, valor = meta.columns[0], meta.columns[1]
    return {str(k).strip(): str(v).strip()
            for k, v in zip(meta[clave], meta[valor])}


def comprobar_version(ruta, version_programa: str) -> None:
    """
    Se planta si el histórico lo escribió una versión MÁS NUEVA que esta.

    Podría tener columnas que esta versión no conoce, y al guardar se
    perderían sin que nadie dijera nada. Ante la duda, no se escribe: es la
    misma regla que sigue sincronizar.py con tu fichero de contabilidad.
    """
    sello = leer_meta(ruta).get("version")
    if not sello:
        return
    if _numero(sello) <= _numero(version_programa):
        return
    raise RuntimeError(
        f"El histórico lo escribió la versión {sello} y esta es la "
        f"{version_programa}.\n"
        f"   Una versión antigua podría cargarse columnas que la nueva añadió, "
        f"así que no lo toco.\n"
        f"   Usa la versión {sello} o posterior, o restaura una copia de "
        f"datos/copias/ si quieres seguir con esta.")


# =====================================================================
# CARGA Y FUSIÓN
# =====================================================================

def cargar(ruta: str) -> pd.DataFrame:
    """Lee el histórico previo. Devuelve una tabla vacía si aún no existe."""
    vacio = pd.DataFrame(columns=COLUMNAS_CRUDAS)
    if not os.path.exists(ruta):
        return vacio
    try:
        df = pd.read_excel(ruta, sheet_name=HOJA_MOVIMIENTOS)
    except Exception as e:
        print(f"⚠️  No he podido leer el histórico ({e}). Empiezo de cero, "
              f"pero NO lo sobreescribo hasta que lo revises.")
        raise

    df, aplicadas = migrar(df, leer_meta(ruta).get("version", VERSION_SIN_SELLO))
    for descripcion in aplicadas:
        print(f"🔧 Histórico actualizado: {descripcion}")

    faltan = [c for c in COLUMNAS_CRUDAS if c not in df.columns]
    if faltan:
        raise RuntimeError(
            f"Al histórico '{ruta}' le faltan columnas: {faltan}. "
            f"Si lo has editado a mano, restaura una copia o bórralo para "
            f"reconstruirlo desde 'entrada/'.")

    df = df[COLUMNAS_CRUDAS].copy()
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["categoria_manual"] = df["categoria_manual"].fillna("").astype(str).str.strip()
    # si el fichero ha pasado por Excel u OnlyOffice, n_rep puede volver como
    # 0.0 en vez de 0, y entonces la clave de duplicados dejaría de casar
    df["n_rep"] = pd.to_numeric(df["n_rep"], errors="coerce").fillna(0).astype(int)
    # a diferencia de n_rep, aquí NO se rellena con 0: un saldo desconocido y
    # uno de 0 € son cosas distintas para calcular_saldo_inicial().
    df["saldo"] = pd.to_numeric(df["saldo"], errors="coerce")
    return df


def fusionar(historico: pd.DataFrame, nuevos: list[pd.DataFrame]):
    """
    Añade al histórico lo que no estuviera ya. Devuelve (tabla, nuevos, repetidos).

    Los extractos que descargas se solapan: si bajas abril y luego abril+mayo,
    abril viene dos veces. Eso se detecta aquí.
    """
    preparados = []
    for df in nuevos:
        df = df.copy()
        df["n_rep"] = df.groupby(_clave(df)).cumcount()
        df["categoria_manual"] = ""
        preparados.append(df[COLUMNAS_CRUDAS])

    entrantes = (pd.concat(preparados, ignore_index=True) if preparados
                 else pd.DataFrame(columns=COLUMNAS_CRUDAS))

    todo = pd.concat([historico, entrantes], ignore_index=True)
    if todo.empty:
        return todo, 0, 0

    # el histórico va primero en el concat, así que keep="first" conserva
    # la categoria_manual ya escrita en lugar de pisarla con la fila entrante
    todo["_k"] = _clave(todo) + "#" + todo["n_rep"].astype(str)
    antes = len(todo)
    todo = todo.drop_duplicates(subset="_k", keep="first")

    ya_estaban = len(historico)
    anadidos = len(todo) - ya_estaban
    repetidos = antes - len(todo)

    todo = (todo.drop(columns="_k")
            .sort_values(["fecha", "descripcion"])
            .reset_index(drop=True))
    return todo, anadidos, repetidos


# =====================================================================
# RESUMEN MENSUAL
# =====================================================================

def construir_resumen(df: pd.DataFrame, catalogo, saldo_inicial: float = 0.0) -> pd.DataFrame:
    """
    Matriz mes × categoría, con los totales y el arrastre entre meses.

    Los gastos se muestran en positivo (se les da la vuelta al signo, no se usa
    valor absoluto: si una categoría acaba en positivo por una devolución, se ve
    como negativa en vez de disfrazarse de gasto).

        Total Gastos = suma de las categorías de gasto
        Ingresos     = suma de las categorías de ingreso
        Balance      = Ingresos - Total Gastos
        Extras       = lo que se arrastra a favor del mes anterior
        Deuda        = lo que se arrastra en contra del mes anterior
        Acumulado    = Extras - Deuda + Balance

    saldo_inicial es de dónde parte el Acumulado antes del primer mes: 0 si no
    se conoce el saldo real de la cuenta en ese punto (lo decide
    calcular_saldo_inicial() en process.py), o ese saldo si se conoce. No hace
    falta ningún caso especial para el primer mes: Deuda y Extras salen solos
    del signo de saldo_inicial, igual que saldrían del arrastre de cualquier
    otro mes.
    """
    col_mes = catalogo.columna_mes
    if df.empty:
        return pd.DataFrame()

    piv = df.pivot_table(index=col_mes, columns="categoria",
                         values="importe", aggfunc="sum")

    filas = []
    acumulado = float(saldo_inicial)
    for mes in sorted(piv.index):
        fila = {"Mes": mes}

        total_gastos = 0.0
        for cat in catalogo.gastos:
            v = -float(piv.at[mes, cat]) if cat in piv.columns and pd.notna(piv.at[mes, cat]) else 0.0
            fila[cat] = round(v, 2)
            total_gastos += v

        ingresos = 0.0
        for cat in catalogo.ingresos:
            if cat in piv.columns and pd.notna(piv.at[mes, cat]):
                ingresos += float(piv.at[mes, cat])

        balance = ingresos - total_gastos

        fila["Deuda"] = round(max(-acumulado, 0.0), 2)
        fila["Extras"] = round(max(acumulado, 0.0), 2)
        fila["Total Gastos"] = round(total_gastos, 2)
        fila["Ingresos"] = round(ingresos, 2)
        fila["Balance"] = round(balance, 2)

        acumulado += balance
        fila["Acumulado"] = round(acumulado, 2)

        filas.append(fila)

    orden = (["Mes"] + catalogo.gastos
             + ["Deuda", "Extras", "Total Gastos", "Ingresos", "Balance", "Acumulado"])
    return pd.DataFrame(filas)[orden]


# =====================================================================
# ESCRITURA
# =====================================================================

def _meta(version: str, movimientos: pd.DataFrame) -> pd.DataFrame:
    """
    La hoja _meta: quién escribió este fichero y cuándo.

    Va la última y con nombre que empieza por «_» para que quede claro que no
    es para leerla a diario. Sirve para dos cosas: saber qué versión reportar
    cuando algo va mal, y decidir qué migraciones aplicar al abrirlo.
    """
    import datetime as _dt

    filas = [
        ("version", version),
        ("generado", _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("movimientos", str(len(movimientos))),
        ("columnas", ", ".join(str(c) for c in movimientos.columns)),
        ("_aviso", "Hoja generada por el programa. No hace falta tocarla."),
    ]
    return pd.DataFrame(filas, columns=["clave", "valor"])


def _texto_seguro(ws):
    """Excel toma por fórmula cualquier texto que empiece por '='."""
    for fila in ws.iter_rows():
        for celda in fila:
            if celda.data_type == "f":
                celda.value = str(celda.value)
                celda.data_type = "s"


def guardar(ruta: str, movimientos: pd.DataFrame, resumen: pd.DataFrame,
            catalogo, version: str = VERSION_SIN_SELLO) -> None:
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    with pd.ExcelWriter(ruta, engine="openpyxl") as writer:
        movimientos.to_excel(writer, sheet_name=HOJA_MOVIMIENTOS, index=False)
        if not resumen.empty:
            resumen.to_excel(writer, sheet_name=HOJA_RESUMEN, index=False)
        _meta(version, movimientos).to_excel(
            writer, sheet_name=HOJA_META, index=False)

    from openpyxl import load_workbook
    wb = load_workbook(ruta)

    verde = PatternFill("solid", fgColor="1F7A5C")
    suave = PatternFill("solid", fgColor="EDF2F0")
    blanco = Font(color="FFFFFF", bold=True, size=10)
    borde = Border(bottom=Side(style="thin", color="D5DBD9"))

    for nombre in wb.sheetnames:
        ws = wb[nombre]
        _texto_seguro(ws)
        for celda in ws[1]:
            celda.fill = verde
            celda.font = blanco
            celda.alignment = Alignment(horizontal="center", vertical="center",
                                        wrap_text=True)
        ws.freeze_panes = "B2"
        ws.row_dimensions[1].height = 28

    # --- movimientos: anchos y formatos
    ws = wb[HOJA_MOVIMIENTOS]
    anchos = {"fecha": 11, "descripcion": 42, "importe": 12, "tipo": 10,
              "mes": 10, "mes_ajustado": 13, "categoria": 22, "origen": 24,
              "regla": 22, "n_rep": 7, "excluido": 10, "saldo": 12}
    for i, col in enumerate(movimientos.columns, 1):
        ws.column_dimensions[get_column_letter(i)].width = anchos.get(col, 14)
        if col in ("importe", "saldo"):
            for c in ws[get_column_letter(i)][1:]:
                c.number_format = '#,##0.00 €'
        if col == "fecha":
            for c in ws[get_column_letter(i)][1:]:
                c.number_format = "DD/MM/YYYY"

    # --- resumen: bandas, euros y realce de Balance
    if not resumen.empty:
        ws = wb[HOJA_RESUMEN]
        ws.column_dimensions["A"].width = 11
        for i in range(2, len(resumen.columns) + 1):
            ws.column_dimensions[get_column_letter(i)].width = 13
        destacadas = {"Total Gastos", "Ingresos", "Balance", "Acumulado"}
        for i, col in enumerate(resumen.columns, 1):
            letra = get_column_letter(i)
            for j, c in enumerate(ws[letra][1:], start=2):
                if i > 1:
                    c.number_format = '#,##0.00 €'
                c.border = borde
                if col in destacadas:
                    c.font = Font(bold=True, size=10)
                if j % 2 == 0 and col not in destacadas:
                    c.fill = suave

    wb.save(ruta)
    wb.close()
