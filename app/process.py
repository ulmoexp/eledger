"""
process.py — Unifica, limpia, clasifica y acumula movimientos de cuenta y tarjetas.

Uso normal:
    1. suelta los ficheros del banco en la carpeta  entrada/
    2. doble clic en  ejecutar.bat  (Windows)  o  ejecutar.command  (Mac)
       o bien, desde la terminal:  python app/process.py

Todo el procesamiento es local; no se conecta a internet.
"""

import json
import os
import re
import sys

# Antes que nada, comprobar que están las librerías. Un ModuleNotFoundError con
# su traceback no le dice nada a quien no ha usado una terminal en su vida, y
# esto es lo primero que se encuentra si se salta la instalación.
try:
    import pandas as pd
except ImportError:
    print("\nFalta una librería para poder trabajar con hojas de cálculo.\n")
    if os.name == "nt":
        print("   Cierra esta ventana y haz doble clic en  instalar.bat")
        print("   Es lo que hay que hacer una vez, la primera.\n")
    else:
        print("   Cierra esta ventana y haz doble clic en  instalar.command")
        print("   Es lo que hay que hacer una vez, la primera.\n")
    print("   (Si sabes lo que haces:  pip install -r requisitos.txt)\n")
    sys.exit(1)

import historico as hist
import sincronizar as sync
from bank_io import detectar_tipo, leer_tabla_bancaria
import rutas
from reglas import Catalogo, Clasificador, Excluidor, compilar, normalizar

# La consola de Windows usa cp1252 por defecto y revienta con acentos y símbolos.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ========= CONFIG =========
# Todas las rutas viven en rutas.py y cuelgan de la carpeta del programa, no
# del directorio actual. Así da igual desde dónde se lance esto.
EXTENSIONES = (".xls", ".xlsx", ".xlsm", ".csv", ".txt", ".tsv", ".ods", ".htm", ".html")

# Columnas A-G: NO cambiar el orden, las fórmulas de la hoja MOVIMIENTOS
# apuntan a columnas concretas.
COLUMNAS_BASE = ["fecha", "descripcion", "importe", "tipo",
                 "mes", "mes_ajustado", "categoria"]
COLUMNAS_HISTORICO = COLUMNAS_BASE + ["categoria_manual", "excluido",
                                      "origen", "regla", "n_rep"]

# ========= REGLAS =========
# Se cargan dentro de main(), NO al importar el módulo: antes hay que dejar las
# carpetas en su sitio y migrar lo que venga de la versión antigua, porque si
# no, ajustes/ podría no existir todavía cuando se intente leer.
clasificador = excluidor = catalogo = cfg_sync = cfg_mes = None


def cargar_configuracion():
    global clasificador, excluidor, catalogo, cfg_sync, cfg_mes
    catalogo = Catalogo.desde_json(rutas.CATEGORIAS)
    # El catálogo primero: el clasificador lo necesita para descartar las reglas
    # de la base que apunten a categorías que este usuario no tiene declaradas.
    clasificador = Clasificador.desde_json(
        rutas.REGLAS, ruta_base=rutas.REGLAS_BASE,
        categorias_validas=set(catalogo.todas))
    excluidor = Excluidor.desde_json(rutas.EXCLUSIONES)
    cfg_sync = sync.Config.desde_json(rutas.SINCRONIZAR, raiz=rutas.RAIZ)
    cfg_mes = MesContable.desde_json(rutas.MES_CONTABLE)


# ========= ESCRITURA SEGURA =========
def guardar_excel(df, ruta):
    """Excel toma por fórmula cualquier texto que empiece por '='. Esto lo evita."""
    df.to_excel(ruta, index=False)
    from openpyxl import load_workbook

    wb = load_workbook(ruta)
    hist._texto_seguro(wb.active)
    wb.save(ruta)
    wb.close()


# ========= AJUSTE DE MES CONTABLE =========
class MesContable:
    """
    Qué movimientos cuentan para el mes anterior.

    La nómina que entra el día 1 es, en la práctica, la del mes que acaba: es
    con lo que has vivido. Se mueve solo ella, no todo el día 1.
    """

    def __init__(self, datos: dict):
        self.dias = int(datos.get("dias", 3))
        self.palabras = [normalizar(p) for p in datos.get("palabras", ["nomina"])]
        self.solo_ingresos = bool(datos.get("solo_ingresos", True))

    @classmethod
    def desde_json(cls, ruta):
        if not os.path.exists(ruta):
            return cls({})
        with open(ruta, "r", encoding="utf-8") as f:
            return cls({k: v for k, v in json.load(f).items()
                        if not k.startswith("_")})

    def aplica(self, descripcion, fecha, importe) -> bool:
        if self.dias <= 0 or fecha.day > self.dias:
            return False
        # El signo importa: la PRESTACIÓN que cobras de la mutua sí es del mes
        # anterior, pero la CUOTA que le pagas no. Sin esta condición, un recibo
        # domiciliado el día 2 se contabilizaba en el mes equivocado.
        if self.solo_ingresos and importe is not None and importe <= 0:
            return False
        desc = normalizar(descripcion)
        return any(p in desc for p in self.palabras)


def ajustar_mes(row):
    if cfg_mes.aplica(row["descripcion"], row["fecha"], row.get("importe")):
        return str((row["fecha"] - pd.DateOffset(months=1)).to_period("M"))
    return row["mes"]


# ========= LOCALIZAR FICHEROS DE ENTRADA =========
def _es_temporal(nombre):
    return nombre.startswith((".", "~$", "_"))


def _admisible(nombre):
    return not _es_temporal(nombre) and os.path.splitext(nombre)[1].lower() in EXTENSIONES


def localizar_ficheros():
    encontrados = []
    if rutas.ENTRADA.is_dir():
        encontrados += [str(rutas.ENTRADA / f)
                        for f in sorted(os.listdir(rutas.ENTRADA)) if _admisible(f)]

    # --- compatibilidad hacia atrás ---
    # Quien tenía «movimientos.xls» y «tarjetas/» sueltos en la carpeta sigue
    # pudiendo trabajar así, pero ahora se buscan en la raíz del programa y no
    # en el directorio desde el que se ejecute la consola.
    encontrados += [str(rutas.RAIZ / f)
                    for f in sorted(os.listdir(rutas.RAIZ))
                    if _admisible(f)
                    and os.path.splitext(f)[0].lower() == rutas.NOMBRE_CUENTA_LEGADO]
    if rutas.CARPETA_TARJETAS_LEGADO.is_dir():
        encontrados += [str(rutas.CARPETA_TARJETAS_LEGADO / f)
                        for f in sorted(os.listdir(rutas.CARPETA_TARJETAS_LEGADO))
                        if _admisible(f)]
    return encontrados


def leer_entrada():
    """Lee todo lo que haya en entrada/. Puede devolver lista vacía sin error:
    si el histórico ya tiene datos, una ejecución sin ficheros nuevos es válida."""
    dfs = []
    for ruta in localizar_ficheros():
        try:
            df = leer_tabla_bancaria(ruta)
            if df.empty:
                print("     ⚠️  sin movimientos utilizables, lo salto")
                continue
            tipo, motivo = detectar_tipo(df)
            df["tipo"] = tipo
            df["origen"] = os.path.basename(ruta)
            print(f"     → {tipo} ({motivo})")
            dfs.append(df)
        except Exception as e:
            print(f"   ⚠️  Error leyendo {os.path.basename(ruta)}: {e}")
    return dfs


# ========= CLASIFICACIÓN =========
def clasificar(df, categorias_validas=None):
    """
    Se recalcula ENTERO en cada ejecución, también sobre el histórico viejo, para
    que afinar rules.json o exclude_patterns.json reclasifique todo hacia atrás.

    Devuelve TODAS las filas, marcando las excluidas en vez de tirarlas: excluir
    es una regla, y las reglas cambian. Si se borraran del histórico, el día que
    quites un patrón de exclusión esos movimientos ya no estarían para recuperar.
    """
    df = df.copy()
    df["descripcion"] = df["descripcion"].astype(str)
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.normalize()

    marcas = df["descripcion"].map(excluidor.excluir)
    df["excluido"] = [m[0] for m in marcas]
    regla_exclusion = [m[1] for m in marcas]

    df["mes"] = df["fecha"].dt.to_period("M").astype(str)
    df["mes_ajustado"] = df.apply(ajustar_mes, axis=1) if not df.empty else df["mes"]

    # El importe va con la descripción: hay reglas que dependen del signo
    # (un Bizum recibido es un ingreso; uno enviado, un gasto).
    resultado = df.apply(
        lambda f: clasificador.clasificar(f["descripcion"], f["importe"]), axis=1)
    df["categoria"] = [r[0] for r in resultado]
    df["regla"] = [r[1] for r in resultado]

    # en las excluidas manda el patrón que las sacó, no la categoría
    fuera = df["excluido"]
    df.loc[fuera, "regla"] = [r for r, e in zip(regla_exclusion, fuera) if e]

    # --- correcciones puntuales escritas a mano en historico.xlsx ---
    # Mandan sobre todo lo anterior. Son para la línea suelta que ninguna regla
    # puede distinguir, porque las reglas leen el texto y no la fecha.
    manual = df["categoria_manual"].fillna("").astype(str).str.strip()

    # Una categoría mal escrita se IGNORA (mandan las reglas). Si se aplicara,
    # el movimiento acabaría en una categoría que no es columna de ninguna
    # suma del resumen: no contaría como gasto, ni como ingreso, ni como
    # excluido. Simplemente se evaporaría de los totales sin restar de nada, y
    # el Excel descuadraría en silencio. Quien la ha escrito recibe el aviso
    # por pantalla desde main().
    if categorias_validas is not None:
        manual = manual.where(manual.isin(categorias_validas), "")

    forzado = manual.ne("")
    a_excluir = forzado & manual.eq(hist.MARCA_EXCLUIDO)
    a_categoria = forzado & ~manual.eq(hist.MARCA_EXCLUIDO)

    df.loc[a_excluir, "excluido"] = True
    df.loc[a_categoria, "excluido"] = False      # también sirve para reactivar
    df.loc[a_categoria, "categoria"] = manual[a_categoria]
    df.loc[forzado, "regla"] = "(manual)"

    df.loc[df["excluido"], "categoria"] = hist.MARCA_EXCLUIDO

    return df.sort_values("fecha").reset_index(drop=True)


# ========= INFORME DE LO SIN CLASIFICAR (hito A1 del roadmap) =========
# Palabras que mete el banco en cualquier concepto y que no identifican
# ningún comercio: aunque sean la palabra que más se repita, no sirven como
# clave de regla.
_PALABRAS_RELLENO = {"compra", "pago", "recibo", "tarj", "tarjeta",
                     "transferencia"}
_MAX_GRUPOS_SIN_CLASIFICAR = 10
_PLACEHOLDER_CATEGORIA = "PON_TU_CATEGORIA"


def _palabras_candidatas(descripcion) -> set:
    """Palabras de una descripción que podrían servir de clave de regla: sin
    relleno del banco y sin números sueltos (referencias, dígitos de tarjeta).
    Se trabaja sobre el texto ya normalizado (sin acentos, en minúsculas), que
    es justo lo que compara el motor de reglas."""
    texto = normalizar(descripcion)
    return {p for p in re.findall(r"[a-z0-9]+", texto)
            if p not in _PALABRAS_RELLENO and not p.isdigit() and len(p) >= 3}


def _agrupar_sin_clasificar(sin_regla):
    """
    Reparte los movimientos sin regla en grupos disjuntos, palabra a palabra:
    en cada vuelta se elige la que más importe arrastra ENTRE LOS QUE QUEDAN,
    se le lleva ese grupo entero y se saca del reparto. Así ningún movimiento
    cuenta en dos grupos a la vez.

    Un movimiento cuya descripción no deja ninguna palabra aprovechable (todo
    relleno o números) se queda fuera: no hay nada razonable que sugerirle.
    """
    candidatas = {i: _palabras_candidatas(fila["descripcion"])
                 for i, fila in sin_regla.iterrows()}
    pendientes = set(candidatas)
    grupos = []

    while pendientes:
        gasto = {}
        filas_de = {}
        for i in pendientes:
            for palabra in candidatas[i]:
                gasto[palabra] = gasto.get(palabra, 0.0) - sin_regla.at[i, "importe"]
                filas_de.setdefault(palabra, []).append(i)
        if not gasto:
            break
        mejor = max(gasto, key=lambda p: (gasto[p], len(filas_de[p]), p))
        indices = filas_de[mejor]
        grupos.append((mejor, sin_regla.loc[indices]))
        pendientes -= set(indices)

    return grupos


def _palabras_del_grupo(grupo, palabra_principal):
    """Las palabras candidatas del grupo: primero la que lo formó (está en
    TODAS sus filas, por construcción), luego el resto por cuántas filas
    cubren, de más a menos."""
    conteo = {}
    for _, fila in grupo.iterrows():
        for palabra in _palabras_candidatas(fila["descripcion"]):
            conteo[palabra] = conteo.get(palabra, 0) + 1
    resto = sorted((p for p in conteo if p != palabra_principal),
                   key=lambda p: (-conteo[p], p))
    return [palabra_principal] + resto


def _sugerir_regla(grupo, palabra_principal, descripciones_clasificadas):
    """
    Prueba las palabras del grupo, empezando por la que lo formó, y devuelve
    la primera que el propio motor de reglas (compilar(), de reglas.py) NO
    haría casar con ningún movimiento que ya tiene categoría por otra regla.
    None si ninguna es segura.

    Es el cerrojo que evita el fallo que dio pie a este informe: sugerir "dia"
    y arrastrar MEDIA MARKT o GUARDIA CIVIL. Agrupar ya va por palabra
    completa (_palabras_candidatas), pero una palabra suelta puede seguir
    casando por delante con OTRA descripción por el modo prefijo de
    compilar() (p.ej. "barcelona" también aparece dentro de un movimiento que
    ya clasifica la regla "taxi"). Sin este paso, pegar la sugerencia podría
    cambiar en silencio la categoría de movimientos que ya estaban bien.
    """
    for palabra in _palabras_del_grupo(grupo, palabra_principal):
        patron, _ = compilar(palabra)
        if not any(patron.search(d) for d in descripciones_clasificadas):
            return palabra
    return None


def informe_sin_clasificar(df):
    """
    Hito A1 del roadmap: qué se ha quedado en Otros SIN que ninguna regla
    casara. `regla == ""` es justo eso (ver clasificar()): por construcción
    implica categoria == por_defecto. Una regla que apunte a Otros a propósito
    deja «regla» rellena con su clave, así que no entra aquí: eso ya está
    clasificado, no es "esto no sé qué es".
    """
    sin_regla = df[df["regla"] == ""]
    if sin_regla.empty:
        return

    grupos = _agrupar_sin_clasificar(sin_regla)
    if not grupos:
        return

    # de más a menos importe, con el mismo criterio que el resto del resumen:
    # en positivo (-suma), sin ABS() que disfrace un grupo que acabe a favor.
    grupos.sort(key=lambda g: g[1]["importe"].sum())
    mostrados = grupos[:_MAX_GRUPOS_SIN_CLASIFICAR]

    # universo contra el que se valida cada clave sugerida: todo lo que YA
    # tiene categoría por una regla de verdad, no por una corrección manual
    # (esa manda igual, así que da igual si la nueva clave también la toca).
    clasificados = df.loc[~df["regla"].isin(("", "(manual)")), "descripcion"]
    normalizados = [normalizar(d) for d in clasificados]

    print(f"\nℹ️  {len(sin_regla)} movimientos sin ninguna regla, en "
          f"{len(grupos)} grupos por palabra común:")
    if len(grupos) > _MAX_GRUPOS_SIN_CLASIFICAR:
        print(f"   (se muestran los {_MAX_GRUPOS_SIN_CLASIFICAR} de más importe)")
    print()

    for palabra, filas in mostrados:
        total = -filas["importe"].sum()
        ejemplo = filas["descripcion"].mode().iloc[0]
        print(f"   {total:>10,.2f} €  ·  {len(filas):>3} mov.  ·  {palabra}")
        print(f"      ej: {ejemplo}")
        sugerida = _sugerir_regla(filas, palabra, normalizados)
        if sugerida:
            print(f'      añade a rules.json:  "{sugerida}": '
                  f'"{_PLACEHOLDER_CATEGORIA}"')
        else:
            print("      (ninguna palabra de este grupo es segura de sugerir "
                  "sin pisar otra regla; revísalo a mano)")
        print()


# ========= MAIN =========
def arrancar():
    """
    Deja la carpeta lista antes de tocar nada más.

    El orden importa: primero se crean las carpetas, luego se recoge lo que
    hubiera suelto de la versión antigua, luego se rellena la configuración que
    falte, y solo entonces se carga. Si se cargara antes, en una instalación
    recién descomprimida no habría ni ajustes/ que leer.
    """
    rutas.asegurar_carpetas()
    sync.fijar_carpeta_copias(rutas.COPIAS)

    lineas = rutas.migrar_desde_raiz()
    if lineas:
        print("📦 " + lineas[0])
        for l in lineas[1:]:
            print(f"   {l}")
        print()

    # Si ya hay histórico, esto es una actualización y no una instalación nueva.
    # La diferencia importa para el mes contable (ver más abajo).
    actualizacion = rutas.HISTORICO.exists()

    sembrados = rutas.sembrar_configuracion()
    if sembrados:
        print(f"🌱 Configuración de partida creada en "
              f"'{rutas.relativa(rutas.AJUSTES)}/': {', '.join(sembrados)}")
        print(f"   Son reglas genéricas. Ábrelas y añade lo tuyo: tu casero, los "
              f"comercios de tu barrio,")
        print(f"   y sobre todo el recibo con que tu cuenta paga la tarjeta en "
              f"exclude_patterns.json.\n")

    if "mes_contable.json" in sembrados and actualizacion:
        if rutas.conservar_mes_contable_heredado():
            print(f"🗓️  El ajuste de mes contable ahora se configura en "
                  f"'{rutas.relativa(rutas.MES_CONTABLE)}'.")
            print(f"   Antes estaba fijo dentro del programa. Lo he dejado como "
                  f"estaba (nómina y mutua) para que")
            print(f"   tus totales no cambien. Ábrelo si quieres afinarlo.\n")

    cargar_configuracion()


def main():
    arrancar()

    print(f"Movimientos bancarios · versión {rutas.version()}")
    print(f"Reglas: {clasificador.n_propias} tuyas + {clasificador.n_base} de la "
          f"base.")
    if clasificador.desactivadas:
        print(f"   Apagadas con null: {', '.join(clasificador.desactivadas)}")
    if clasificador.descartadas_de_base:
        print(f"   {len(clasificador.descartadas_de_base)} reglas de la base "
              f"descartadas: apuntan a categorías que no tienes en "
              f"categorias.json.")
        print(f"   ({', '.join(clasificador.descartadas_de_base[:6])}"
              f"{'...' if len(clasificador.descartadas_de_base) > 6 else ''})")
    print()

    avisos = catalogo.validar(clasificador)
    if avisos:
        print("⚠️  Las categorías de rules.json y categorias.json no cuadran:\n")
        for a in avisos:
            print(f"   · {a}")
        print("\n   Sigo adelante, pero revísalo o el resumen no cuadrará.\n")

    print(f"Leyendo ficheros de '{rutas.relativa(rutas.ENTRADA)}/'...\n")
    nuevos = leer_entrada()

    hist.comprobar_version(rutas.HISTORICO, rutas.version())
    previo = hist.cargar(rutas.HISTORICO)
    if not previo.empty:
        print(f"\n📚 Histórico previo: {len(previo)} movimientos.")
    elif not nuevos:
        raise FileNotFoundError(
            f"No hay histórico y la carpeta '{rutas.relativa(rutas.ENTRADA)}/' está vacía.\n"
            f"   Suelta ahí los ficheros que te descargues del banco, con el nombre\n"
            f"   y la extensión que traigan, y vuelve a ejecutar.")

    crudos, anadidos, repetidos = hist.fusionar(previo, nuevos)
    if repetidos:
        print(f"🔁 {repetidos} movimientos ya estaban (extractos que se solapan); "
              f"no se cuentan dos veces.")
    if anadidos:
        print(f"➕ {anadidos} movimientos nuevos.")
    elif nuevos:
        print("➕ Ningún movimiento nuevo: ya estaba todo en el histórico.")

    if crudos.empty:
        print("❌ No hay ningún movimiento que procesar.")
        return

    validas = set(catalogo.todas) | {hist.MARCA_EXCLUIDO}
    todo = clasificar(crudos, validas)

    manuales = todo.loc[todo["categoria_manual"].ne(""), "categoria_manual"]
    invalidas = sorted(set(manuales) - validas)
    if invalidas:
        print(f"\n⚠️  Correcciones manuales con una categoría que no existe: "
              f"{', '.join(invalidas)}")
        print(f"   Tiene que ser una de categorias.json, o «{hist.MARCA_EXCLUIDO}» "
              f"para sacarla de los totales.")
        print(f"   Las he IGNORADO y he dejado que manden las reglas, para que no "
              f"desaparezcan de los totales sin avisar. Corrige la columna "
              f"categoria_manual y vuelve a ejecutar.")
    df = todo[~todo["excluido"]].reset_index(drop=True)      # lo que cuenta
    excluidos = todo[todo["excluido"]].reset_index(drop=True)

    # --- salidas ---
    # el histórico guarda TODO (incluido lo excluido); el resumen y el fichero
    # que pegas en Excel, solo lo que cuenta.
    resumen = hist.construir_resumen(df, catalogo)
    if os.path.exists(rutas.HISTORICO):
        sync.copia_de_seguridad(rutas.HISTORICO, cfg_sync.copias_de_seguridad)
    hist.guardar(rutas.HISTORICO, todo[COLUMNAS_HISTORICO], resumen, catalogo,
                 version=rutas.version())
    guardar_excel(df[COLUMNAS_BASE + ["origen", "regla"]], rutas.LIMPIOS)
    if not excluidos.empty:
        guardar_excel(excluidos[["fecha", "descripcion", "importe", "tipo",
                                 "origen", "regla"]], rutas.EXCLUIDOS)

    # --- resumen en pantalla ---
    # --- volcado directo en el fichero de contabilidad ---
    if cfg_sync.activa:
        print()
        try:
            a_volcar = todo if cfg_sync.incluir_excluidos else df
            copia, filas = sync.escribir(cfg_sync, a_volcar[COLUMNAS_BASE])
            print(f"📗 {cfg_sync.archivo} · hoja {cfg_sync.hoja}: {filas} filas escritas")
            print(f"   copia de seguridad en {copia}")
        except Exception as e:
            print(f"⚠️  {e}")
            print("   Tu fichero de contabilidad NO se ha tocado. "
                  "Usa movimientos_limpios.xlsx mientras tanto.")

    print(f"\n✅ {rutas.relativa(rutas.HISTORICO)}  ·  hojas {hist.HOJA_MOVIMIENTOS} y {hist.HOJA_RESUMEN}")
    print(f"   {rutas.relativa(rutas.LIMPIOS)}  ·  lo que pegas en A-G")
    print(f"\n   {len(df)} movimientos · {len(excluidos)} excluidos")
    if not df.empty:
        print(f"   del {df['fecha'].min():%d/%m/%Y} al {df['fecha'].max():%d/%m/%Y}"
              f"  ({len(resumen)} meses)")

    ajustadas = (df["mes"] != df["mes_ajustado"]).sum()
    if ajustadas:
        print(f"   {ajustadas} con el mes contable ajustado"
              f"  (el resumen agrupa por '{catalogo.columna_mes}')")

    if not resumen.empty:
        print()
        ult = resumen.iloc[-1]
        print(f"   Último mes ({ult['Mes']}):  gastos {ult['Total Gastos']:,.2f} € · "
              f"ingresos {ult['Ingresos']:,.2f} € · balance {ult['Balance']:+,.2f} €")
        print(f"   Acumulado desde el principio: {ult['Acumulado']:+,.2f} €")

    informe_sin_clasificar(df)


# ========= RUN =========
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ {e}")
        sys.exit(1)
