"""
sincronizar.py — Vuelca los movimientos directamente en tu fichero de contabilidad.

Escribe SOLO en la hoja de datos que le indiques. El resto del libro (fórmulas,
formato condicional, celdas combinadas, colores, anchos, gráficos, imágenes,
validación de datos) se conserva: está comprobado.

Lo que NO sobrevive a una reescritura son las tablas dinámicas y las macros.
Por eso, antes de tocar nada, el módulo inspecciona el libro y se niega a
escribir si encuentra alguna de las dos.

Se configura en sincronizar.json. Si ese fichero no existe, no se hace nada.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import zipfile

import pandas as pd

# Dónde van las copias de seguridad. process.py la fija a datos/copias/ al
# arrancar; el valor por defecto solo sirve si alguien importa este módulo
# suelto para probar algo.
CARPETA_COPIAS = "copias"


def fijar_carpeta_copias(carpeta) -> None:
    global CARPETA_COPIAS
    CARPETA_COPIAS = str(carpeta)


# =====================================================================
# CONFIGURACIÓN
# =====================================================================

class Config:
    def __init__(self, datos: dict, raiz=None):
        self.archivo = str(datos.get("archivo", "")).strip()
        # Quien escriba «contabilidad.xlsx» en el JSON se refiere al de la
        # carpeta del programa, no al del directorio desde el que se lance la
        # consola. Las rutas absolutas se respetan tal cual.
        self.raiz = os.path.abspath(raiz) if raiz else os.path.abspath(".")
        self.hoja = datos.get("hoja", "MOVIMIENTOS")
        self.fila_inicial = int(datos.get("fila_inicial", 1))
        self.columna_inicial = int(datos.get("columna_inicial", 1))
        self.incluir_excluidos = bool(datos.get("incluir_excluidos", False))
        self.copias_de_seguridad = int(datos.get("copias_de_seguridad", 10))

    @property
    def activa(self) -> bool:
        return bool(self.archivo)

    @property
    def ruta(self) -> str:
        """El fichero de destino, ya resuelto contra la raíz del programa."""
        if not self.archivo:
            return ""
        if os.path.isabs(self.archivo):
            return self.archivo
        return os.path.join(self.raiz, self.archivo)

    @classmethod
    def desde_json(cls, ruta, raiz=None):
        if not os.path.exists(ruta):
            return cls({}, raiz)
        from reglas import leer_json
        datos = {k: v for k, v in leer_json(ruta).items() if not k.startswith("_")}
        return cls(datos, raiz)


# =====================================================================
# COMPROBACIONES PREVIAS
# =====================================================================

def revisar_libro(ruta: str) -> tuple[list[str], list[str]]:
    """
    Mira dentro del .xlsx antes de tocarlo.
    Devuelve (motivos_para_no_escribir, avisos_informativos).
    """
    if not os.path.exists(ruta):
        return ([f"No encuentro el fichero de contabilidad: {ruta}"], [])

    ext = os.path.splitext(ruta)[1].lower()
    if ext == ".xlsm":
        return (["El fichero es .xlsm (con macros). Las macros se perderían al "
                 "reescribirlo. Guárdalo como .xlsx si no las usas."], [])
    if ext != ".xlsx":
        return ([f"Solo sé escribir en ficheros .xlsx, y este es {ext}. "
                 f"Ábrelo y guárdalo como .xlsx."], [])

    try:
        nombres = zipfile.ZipFile(ruta).namelist()
    except zipfile.BadZipFile:
        return ([f"'{ruta}' no parece un .xlsx válido."], [])

    bloqueos, avisos = [], []
    if any("pivotTable" in n or "pivotCache" in n for n in nombres):
        bloqueos.append("El libro tiene TABLAS DINÁMICAS: se perderían al reescribirlo.")
    if any("vbaProject" in n for n in nombres):
        bloqueos.append("El libro tiene MACROS: se perderían al reescribirlo.")

    if any(n.startswith("xl/charts/") for n in nombres):
        avisos.append("tiene gráficos (se conservan, pero repásalos la primera vez)")
    if any(n.startswith("xl/media/") for n in nombres):
        avisos.append("tiene imágenes (se conservan, pero repásalas la primera vez)")

    return bloqueos, avisos


def revisar_hoja(ws) -> list[str]:
    """
    La hoja de destino tiene que ser de datos, no de cálculo.

    Este es el seguro más importante: si por una errata apuntas a la hoja de
    totales, aquí se detecta que hay fórmulas y no se borra nada.

    Se mira la hoja ENTERA, no solo el bloque que se va a volcar: una fórmula
    en cualquier parte de la hoja significa que no es una hoja de datos, y a la
    mínima duda es mejor no escribir. Por eso no recibe la esquina del bloque.
    """
    formulas = []
    for fila in ws.iter_rows():
        for celda in fila:
            if celda.data_type == "f":
                formulas.append(celda.coordinate)
                if len(formulas) >= 5:
                    break
        if len(formulas) >= 5:
            break

    if formulas:
        return [f"La hoja «{ws.title}» contiene fórmulas ({', '.join(formulas)}...). "
                f"No la sobreescribo: la hoja de destino debe ser solo datos. "
                f"Comprueba el nombre de la hoja en sincronizar.json."]
    return []


# =====================================================================
# COPIA DE SEGURIDAD
# =====================================================================

def copia_de_seguridad(ruta: str, maximo: int) -> str:
    os.makedirs(CARPETA_COPIAS, exist_ok=True)
    base = os.path.splitext(os.path.basename(ruta))[0]
    sello = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = os.path.join(CARPETA_COPIAS, f"{base}_{sello}.xlsx")
    shutil.copy2(ruta, destino)

    if maximo > 0:
        previas = sorted(f for f in os.listdir(CARPETA_COPIAS)
                         if f.startswith(base + "_") and f.endswith(".xlsx"))
        for vieja in previas[:-maximo]:
            os.remove(os.path.join(CARPETA_COPIAS, vieja))

    return destino


# =====================================================================
# ESCRITURA
# =====================================================================

def _limpiar_bloque(ws, fila_inicial, columna_inicial, ancho):
    """Vacía lo que hubiera antes, sin tocar los estilos ni el resto de la hoja."""
    for fila in ws.iter_rows(min_row=fila_inicial,
                             min_col=columna_inicial,
                             max_col=columna_inicial + ancho - 1):
        for celda in fila:
            celda.value = None


def _hay_datos_fuera_del_bloque(ws, columna_inicial, ancho, desde_fila) -> bool:
    """
    ¿Hay algo escrito a los lados de las columnas que volcamos, de la fila
    `desde_fila` hacia abajo?

    Importa porque el recorte de filas sobrantes borra la FILA ENTERA, no solo
    el bloque. Si el usuario tiene una columna de notas al lado de los datos,
    borrar la fila se la lleva por delante.
    """
    primera = columna_inicial
    ultima = columna_inicial + ancho - 1
    for fila in ws.iter_rows(min_row=desde_fila):
        for celda in fila:
            if celda.value is None:
                continue
            if celda.column < primera or celda.column > ultima:
                return True
    return False


# --- notas del usuario al lado de los movimientos ---
# El bloque se vacía y se reescribe en orden de fecha, pero lo que el usuario
# escribe a los lados («regalo mamá» junto a un cargo) se quedaba en su número
# de fila. Bastaba con que entrara un movimiento más antiguo para que todo lo
# de debajo bajara una fila y cada nota acabara junto al movimiento de al
# lado, sin ningún aviso. Ahora cada nota se recuerda por el movimiento al que
# acompaña y se vuelve a poner a su lado.

def _clave_fila(fecha, descripcion, importe):
    """(fecha, concepto, importe) de una fila volcada, o None si la fila no
    parece un movimiento (sin fecha o sin importe): lo que el usuario tenga
    junto a otras cosas no se toca."""
    if not hasattr(fecha, "strftime"):
        return None
    try:
        imp = round(float(importe), 2)
    except (TypeError, ValueError):
        return None
    return fecha.strftime("%Y-%m-%d"), str(descripcion or "").strip(), imp


def _con_repeticion(claves):
    """Dos movimientos idénticos el mismo día son dos: se numeran, igual que
    en el histórico, para que cada nota vuelva a SU movimiento."""
    vistos, salida = {}, []
    for k in claves:
        if k is None:
            salida.append(None)
            continue
        n = vistos.get(k, 0)
        vistos[k] = n + 1
        salida.append((k, n))
    return salida


def _leer_notas(ws, f0, c0, ancho, cols):
    """{movimiento: (fila, {columna: valor})} de lo escrito a los lados."""
    if not all(c in cols for c in ("fecha", "descripcion", "importe")):
        return {}
    cf, cd, ci = (c0 + cols.index(c) for c in ("fecha", "descripcion", "importe"))
    filas = list(range(f0 + 1, ws.max_row + 1))
    claves = _con_repeticion([_clave_fila(ws.cell(r, cf).value, ws.cell(r, cd).value,
                                          ws.cell(r, ci).value) for r in filas])
    notas = {}
    for r, k in zip(filas, claves):
        if k is None:
            continue
        lados = {c.column: c.value for c in ws[r]
                 if c.value is not None and not c0 <= c.column < c0 + ancho}
        if lados:
            notas[k] = (r, lados)
    return notas


def _recolocar_notas(ws, notas, df, f0):
    """Pone cada nota junto a su movimiento. Nunca pisa otra: si el sitio
    está ocupado, la deja donde estaba. Devuelve (movidas, sin_su_movimiento,
    sin_sitio)."""
    claves = _con_repeticion([_clave_fila(r["fecha"], r["descripcion"], r["importe"])
                              for _, r in df.iterrows()])
    destino = {k: f0 + 1 + i for i, k in enumerate(claves) if k is not None}
    mover = {k: v for k, v in notas.items() if k in destino and destino[k] != v[0]}
    huerfanas = sum(1 for k in notas if k not in destino)

    for r, lados in mover.values():
        for c in lados:
            ws.cell(r, c).value = None
    sin_sitio = 0
    for k, (r, lados) in mover.items():
        fila = destino[k]
        if any(ws.cell(fila, c).value is not None for c in lados):
            sin_sitio += 1
            if all(ws.cell(r, c).value is None for c in lados):
                for c, v in lados.items():
                    ws.cell(r, c).value = v
            continue
        for c, v in lados.items():
            ws.cell(fila, c).value = v
    return len(mover) - sin_sitio, huerfanas, sin_sitio


def escribir(cfg: Config, df: pd.DataFrame) -> tuple[str, int]:
    """Vuelca df en la hoja indicada. Devuelve (ruta_de_la_copia, filas escritas)."""
    from openpyxl import load_workbook

    bloqueos, avisos = revisar_libro(cfg.ruta)
    if bloqueos:
        raise RuntimeError("No sincronizo con tu fichero de contabilidad:\n   · "
                           + "\n   · ".join(bloqueos))
    for a in avisos:
        print(f"   ℹ️  El libro {a}")

    try:
        wb = load_workbook(cfg.ruta)
    except PermissionError:
        raise RuntimeError(f"'{cfg.archivo}' está abierto en otro programa. "
                           f"Ciérralo y vuelve a ejecutar.")

    if cfg.hoja not in wb.sheetnames:
        wb.close()
        raise RuntimeError(f"El libro no tiene ninguna hoja llamada «{cfg.hoja}». "
                           f"Hojas disponibles: {', '.join(wb.sheetnames)}.")

    ws = wb[cfg.hoja]
    problemas = revisar_hoja(ws)
    if problemas:
        wb.close()
        raise RuntimeError("No sincronizo:\n   · " + "\n   · ".join(problemas))

    copia = copia_de_seguridad(cfg.ruta, cfg.copias_de_seguridad)

    notas = _leer_notas(ws, cfg.fila_inicial, cfg.columna_inicial,
                        len(df.columns), list(df.columns))
    _limpiar_bloque(ws, cfg.fila_inicial, cfg.columna_inicial, len(df.columns))

    f0, c0 = cfg.fila_inicial, cfg.columna_inicial
    for j, nombre in enumerate(df.columns):
        ws.cell(row=f0, column=c0 + j, value=str(nombre))

    for i, (_, registro) in enumerate(df.iterrows(), start=1):
        for j, nombre in enumerate(df.columns):
            valor = registro[nombre]
            celda = ws.cell(row=f0 + i, column=c0 + j)
            if isinstance(valor, pd.Timestamp):
                celda.value = valor.to_pydatetime()
                celda.number_format = "DD/MM/YYYY"
            elif pd.isna(valor):
                celda.value = None
            elif isinstance(valor, (int, float)) and not isinstance(valor, bool):
                celda.value = float(valor)
                if nombre == "importe":
                    celda.number_format = '#,##0.00 €'
            else:
                texto = str(valor)
                celda.value = texto
                if texto.startswith("="):        # que no lo tome por fórmula
                    celda.data_type = "s"

    if notas:
        movidas, huerfanas, sin_sitio = _recolocar_notas(ws, notas, df, f0)
        if movidas:
            print(f"   ℹ️  {movidas} notas tuyas recolocadas junto a su movimiento "
                  f"(han entrado movimientos por medio).")
        if huerfanas or sin_sitio:
            print(f"   ⚠️  {huerfanas + sin_sitio} notas tuyas no he podido "
                  f"ponerlas junto a su movimiento (ya no se vuelca, o el sitio\n"
                  f"      estaba ocupado): se han quedado donde estaban. Están "
                  f"como antes en la copia {copia}.")

    # Si esta vez hay menos filas que la anterior, no basta con vaciarlas: se
    # eliminan, o la hoja arrastra para siempre el rango usado más grande.
    #
    # Pero delete_rows borra la FILA ENTERA. Si el usuario tiene datos propios
    # a la derecha (o a la izquierda) del bloque volcado, se los llevaría por
    # delante. En ese caso se prefiere dejar las filas: ya han quedado vacías
    # en las columnas que nos tocan, y lo único que se pierde es el recorte del
    # rango usado, que es cosmético. Perder las notas del usuario no lo es.
    ultima = f0 + len(df)
    if ws.max_row > ultima:
        if _hay_datos_fuera_del_bloque(ws, c0, len(df.columns), ultima + 1):
            print(f"   ℹ️  Por debajo de la fila {ultima} hay datos tuyos fuera "
                  f"de las columnas que vuelco.")
            print(f"      He vaciado esas filas en el bloque volcado, pero no las "
                  f"he borrado, para no llevarme lo demás.")
        else:
            ws.delete_rows(ultima + 1, ws.max_row - ultima)

    try:
        wb.save(cfg.ruta)
    except PermissionError:
        raise RuntimeError(f"No he podido guardar '{cfg.archivo}': está abierto en "
                           f"otro programa. Tu copia de seguridad está en {copia}.")
    finally:
        wb.close()

    return copia, len(df)