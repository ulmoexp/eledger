"""
process.py — Unifica, limpia, clasifica y acumula movimientos de cuenta y tarjetas.

Uso normal:
    1. suelta los ficheros del banco en la carpeta  entrada/
    2. doble clic en  ejecutar.bat  (Windows)  o  ejecutar.command  (Mac)
       o bien, desde la terminal:  python app/process.py

Todo el procesamiento es local; no se conecta a internet.
"""

import datetime as dt
import difflib
import json
import os
import re
import subprocess
import sys
import textwrap
from typing import NamedTuple

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
        # Mac y Linux comparten os.name, pero no el lanzador
        lanzador = "instalar.command" if sys.platform == "darwin" else "instalar.sh"
        print(f"   Cierra esta ventana y haz doble clic en  {lanzador}")
        print("   Es lo que hay que hacer una vez, la primera.\n")
    print("   (Si sabes lo que haces:  pip install -r requisitos.txt)\n")
    # la ventana no se cierra hasta que se ha leído (ver menu_final())
    if sys.stdin.isatty() and sys.stdout.isatty():
        try:
            input("Pulsa Intro para cerrar...")
        except EOFError:
            pass
    sys.exit(2)

import historico as hist
import sincronizar as sync
from bank_io import detectar_tipo, leer_tabla_bancaria
import rutas
from reglas import (Catalogo, Clasificador, Excluidor, IdentificadorCuentas,
                    anadir_exclusion, anadir_regla, compilar, euros, leer_json,
                    normalizar)

# La consola de Windows usa cp1252 por defecto y revienta con acentos y símbolos.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
# Y lo que se teclea en el asistente, igual: con la entrada por tubería (las
# pruebas, al compilar en Windows) llegaba en cp1252 y «crédito» se leía
# «crÃ©dito». Desde la consola de verdad Python ya lo lee bien; esto solo
# hace que valga igual venga de donde venga.
try:
    sys.stdin.reconfigure(encoding="utf-8")
except Exception:
    pass

# ========= PANTALLA =========
# Lo que se cuenta por pantalla va en bloques, en este orden: lo que va
# haciendo, el resultado, lo que ha encontrado (los informes) y, al final,
# juntos y contados, los avisos. Antes cada aviso salía en cuanto se
# detectaba, mezclado con todo lo demás y a menudo lo primero de la
# pantalla: justo donde menos se lee y donde más asusta sin motivo.
_avisos = []

# Código de salida cuando el propio programa ya ha explicado el error y ha
# esperado a que se leyera. Los lanzadores lo usan para no pedir otra vez
# «Pulsa una tecla»: solo esperan ellos si el programa ni siquiera ha podido
# arrancar (Python roto, falta un fichero).
CODIGO_ERROR_EXPLICADO = 2


def _preparar_color() -> bool:
    """
    Colores solo si hay una persona mirando una terminal de verdad y no ha
    pedido lo contrario con NO_COLOR (la convención de no-color.org). Con la
    salida capturada (las pruebas, un fichero) no sale ni un código: esos
    textos se comparan y se leen tal cual.

    La consola clásica de Windows (conhost, la del doble clic en .bat y en el
    .exe) no interpreta los códigos hasta que se le activa el modo VT. Si eso
    falla por lo que sea, sin color: se vería basura como «←[1;36m».
    """
    if os.environ.get("NO_COLOR"):
        return False
    try:
        if not sys.stdout.isatty():
            return False
    except (AttributeError, ValueError):
        return False
    if os.name == "nt":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            salida = kernel32.GetStdHandle(-11)              # STD_OUTPUT_HANDLE
            modo = ctypes.c_uint32()
            if not kernel32.GetConsoleMode(salida, ctypes.byref(modo)):
                return False
            ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            if not modo.value & ENABLE_VIRTUAL_TERMINAL_PROCESSING:
                if not kernel32.SetConsoleMode(
                        salida, modo.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING):
                    return False
        except Exception:
            return False
    return True


_COLOR = _preparar_color()


def _pintar(codigo):
    """
    Los 16 colores básicos, no los de 24 bits: son los que respeta el tema de
    cada terminal (fondo claro u oscuro) y los que entiende cualquier consola.
    Gris (90) en vez de «atenuado» (2): conhost no sabe atenuar.

    Se colorea línea a línea: un texto partido con textwrap sigue igual de
    bien si luego se corta o se vuelve a partir, sin arrastrar el color a lo
    que venga detrás.
    """
    def pintar(texto):
        if not _COLOR:
            return texto
        return "\n".join(f"\x1b[{codigo}m{linea}\x1b[0m" if linea else linea
                         for linea in str(texto).split("\n"))
    return pintar


titular = _pintar("1;36")      # secciones y teclas del menú: negrita, acento
verde = _pintar("32")          # lo que ha salido bien
amarillo = _pintar("33")       # avisos
rojo = _pintar("31")           # errores
gris = _pintar("90")           # lo secundario: motivos, rutas, notas
negrita = _pintar("1")


def avisar(titulo, lineas=()):
    """Guarda un aviso para enseñarlo al final, con los demás."""
    _avisos.append((titulo, list(lineas)))


def seccion(titulo, pintar=titular):
    print("\n" + pintar(f"── {titulo} {'─' * max(3, 60 - len(titulo))}") + "\n")


def mostrar_avisos():
    if not _avisos:
        return
    seccion(f"Avisos ({len(_avisos)})", pintar=amarillo)
    for titulo, lineas in _avisos:
        # el color DESPUÉS de partir las líneas: textwrap contaría los códigos
        # como letras y cortaría antes de tiempo
        print(amarillo(textwrap.fill(f"⚠️  {titulo}", 78, subsequent_indent="    ")))
        for linea in lineas:
            # las viñetas llevan una sangría más en las líneas partidas, para
            # que se vea dónde empieza cada punto
            sangria = "      " if linea.startswith("· ") else "    "
            print(textwrap.fill(linea, 78, initial_indent="    ",
                                subsequent_indent=sangria))
        print()


def _interactiva() -> bool:
    """Hay una persona delante: se ha abierto con doble clic o desde una
    consola. Con la salida redirigida (las pruebas, un script) no se pregunta
    nada, o se quedaría esperando para siempre.

    ELEDGER_FORZAR_INTERACTIVO=1 hace como si la hubiera. Es SOLO para las
    pruebas, que así pueden contestar al asistente por la entrada estándar."""
    if os.environ.get("ELEDGER_FORZAR_INTERACTIVO") == "1":
        return True
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False


def _esperar(texto="Pulsa Intro para cerrar..."):
    try:
        return input(texto).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _abrir(ruta):
    """Abre un fichero o una carpeta con el programa que tenga asignado el
    sistema (Excel, el explorador...), sin esperar a que se cierre."""
    if os.name == "nt":
        os.startfile(str(ruta))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(ruta)])
    else:
        subprocess.Popen(["xdg-open", str(ruta)], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)


OTRA_VEZ = "otra vez"


class Propuesta(NamedTuple):
    """Un grupo de lo sin clasificar con su regla ya validada, tal cual la
    imprime informe_sin_clasificar() como «añade a rules.json»."""
    clave: str            # la que ha dado por segura _sugerir_regla()
    entra: bool           # dinero que entra: la regla es solo para el lado +
    palabra: str          # la que formó el grupo, la que se ve en el informe
    movimientos: int
    importe: float        # lo que suma el grupo, en positivo
    ejemplo: str


class ExclusionPropuesta(NamedTuple):
    """Una línea que conviene excluir para que la tarjeta no cuente doble."""
    lado: str             # "cuenta": el recibo con que la cuenta paga la
                          # tarjeta; "tarjeta": el mismo pago, visto desde el
                          # extracto de la tarjeta (sale como un ingreso)
    clave: str | None     # la que se propone, o None si no hay ninguna
    segura: bool          # no casa con ningún otro movimiento
    ejemplos: list        # descripciones, para enseñarlas


class RecibosTarjeta(NamedTuple):
    """Lo que deja detectar_recibo_tarjeta()."""
    aviso: bool           # ha dejado el aviso: algún lado está sin excluir
    descripciones: set    # las de los dos lados, para que el informe de sin
                          # clasificar no les proponga una categoría
    propuestas: list      # de ExclusionPropuesta, solo de lo que falta


class Pendientes(NamedTuple):
    """Lo que el asistente del menú final puede escribir por la persona."""
    reglas: list          # de Propuesta
    tarjeta: bool         # ha salido el aviso de que la tarjeta cuenta doble
    exclusiones: list     # de ExclusionPropuesta
    movimientos: list     # (fecha, descripcion, importe, tipo) de todo, para
                          # enseñar con qué casaría una clave antes de añadirla


def _categorias_para(entra) -> list:
    """Las que se ofrecen en el asistente: solo las declaradas en
    categorias.json. Es el cerrojo de esta vía: eligiendo por número no hay
    forma de escribir una regla a una categoría que no suma en ningún sitio.
    A lo que sale, gastos; a lo que entra, ingresos; a los dos, las neutras
    (un traspaso a tu propia cuenta de ahorro puede ir en cualquier sentido)."""
    base = catalogo.ingresos if entra else catalogo.gastos
    return list(dict.fromkeys(base + catalogo.neutras))


def _imprimir_en_columnas(textos, ancho_total=76):
    ancho = max(len(t) for t in textos) + 3
    por_fila = max(1, ancho_total // ancho)
    for i in range(0, len(textos), por_fila):
        print("   " + "".join(t.ljust(ancho) for t in textos[i:i + por_fila]).rstrip())


def _excluiria(clave, movimientos) -> list:
    """Los movimientos que esa clave excluiría, de la cuenta Y de la
    tarjeta: Excluidor no mira el tipo. Mismo motor (compilar sobre el texto
    normalizado) que el de verdad."""
    patron, _ = compilar(clave)
    return [m for m in movimientos if patron.search(normalizar(m[1]))]


_PRESENTACION_EXCLUSION = {
    "cuenta": "Este cargo de tu cuenta parece el recibo con que pagas la tarjeta.\n"
              "Si no se excluye, cada gasto de la tarjeta cuenta DOS VECES:",
    "tarjeta": "Y esto, en el extracto de la tarjeta, es el mismo pago visto desde la\n"
               "tarjeta. Si no se excluye, cuenta como un INGRESO que no lo es:",
}


def _una_exclusion(propuesta, movimientos) -> bool:
    """Pregunta por una línea: enseña qué excluiría la clave antes de
    añadirla, y deja probar otro texto. Devuelve si la ha escrito."""
    ruta = rutas.relativa(rutas.EXCLUSIONES)
    clave = propuesta.clave
    while True:
        if not clave:
            texto = _esperar("   Escribe un trozo del concepto, tal como sale en tu "
                             "extracto\n   (Intro = dejarlo): ")
            if not texto:
                print(gris("   No he tocado nada."))
                return False
            clave = normalizar(texto)
            if len(clave) < 4:
                print("   Es demasiado corto: excluiría de más. Prueba con algo más largo.")
                clave = None
                continue
        casan = _excluiria(clave, movimientos)
        if not casan:
            print(f"   «{clave}» no coincide con ningún movimiento de tus extractos. "
                  f"Prueba con otro trozo.")
            clave = None
            continue
        plural = "s" if len(casan) != 1 else ""
        print(f"   «{clave}» excluiría {len(casan)} movimiento{plural}:")
        for fecha, descripcion, importe, tipo in sorted(casan, key=lambda m: m[0])[:5]:
            de = "  (tarjeta)" if tipo == "tarjeta" else ""
            print(gris(f"      {fecha:%d/%m/%Y}  {euros(importe, ancho=10)}  "
                       f"{descripcion}{de}"))
        if len(casan) > 5:
            print(gris(f"      … y {len(casan) - 5} más"))
        if not (clave == propuesta.clave and propuesta.segura):
            print(amarillo("   Comprueba que todos son ese pago: lo excluido no "
                           "cuenta en ningún total."))
        respuesta = _esperar(f"   ¿Lo añado a {ruta}? (S = sí, O = probar otro "
                             f"texto, Intro = no) ").lower()
        if respuesta in ("o", "otro"):
            clave = None
            continue
        if respuesta not in ("s", "si", "sí"):
            print(gris("   No he tocado nada."))
            return False
        motivo = anadir_exclusion(rutas.EXCLUSIONES, clave, rutas.COPIAS)
        if motivo is None:
            print(verde(f'   ✓ Añadido a {ruta}:  "{clave}"'))
            return True
        print(rojo(f"   No lo he escrito: {ruta} {motivo}."))
        print(f'   Añádelo a mano:  "{clave}"')
        return False


def asistente_exclusion(p) -> int:
    """
    Ayuda a excluir el pago de la tarjeta, que según el banco sale en uno o
    en los dos extractos: el recibo en la cuenta (los gastos de la tarjeta
    contarían DOS VECES) y, en algunos, el mismo pago como abono en el de la
    tarjeta (contaría como un ingreso). Sale siempre que haya salido el
    aviso de la tarjeta, con clave propuesta o sin ella: si no la hay, se
    escribe un trozo del concepto. Antes de añadir nada enseña qué excluiría.
    Hay que decir que sí con todas las letras: Intro, que es lo que se pulsa
    por costumbre para cerrar, no escribe. Devuelve cuántas ha escrito.
    """
    seccion("El pago de la tarjeta")
    propuestas = p.exclusiones or [ExclusionPropuesta("cuenta", None, False, [])]
    escritas = 0
    for propuesta in propuestas:
        print(_PRESENTACION_EXCLUSION[propuesta.lado])
        for descripcion in propuesta.ejemplos:
            print(gris(f"   {descripcion}"))
        print()
        escritas += _una_exclusion(propuesta, p.movimientos)
        print()
    return escritas


def asistente_reglas(propuestas) -> tuple[int, list]:
    """
    Recorre los grupos de lo sin clasificar y, para cada uno, deja elegir la
    categoría por número y escribe la regla en rules.json. Devuelve (cuántas
    ha escrito, las propuestas a las que no se ha llegado por terminar antes).
    """
    ruta = rutas.relativa(rutas.REGLAS)
    seccion("Clasificar lo que falta")
    escritas = 0
    for n, p in enumerate(propuestas, 1):
        entra = "  ·  entra" if p.entra else ""
        print(f"{titular(f'{n}/{len(propuestas)}')}  «{p.palabra}»  ·  "
              f"{p.movimientos} mov.  ·  {euros(p.importe)}{entra}")
        print(gris(f"     ej: {p.ejemplo}"))
        categorias = _categorias_para(p.entra)
        if not categorias:
            print(gris("     (no hay ninguna categoría declarada para esto en "
                       "categorias.json)\n"))
            continue
        print("¿En qué categoría va?")
        _imprimir_en_columnas([f"{i:>2} {c}" for i, c in enumerate(categorias, 1)])
        print(gris("   Intro = saltar este grupo  ·  0 = terminar"))
        while True:
            eleccion = _esperar("   > ")
            if eleccion == "" or eleccion == "0":
                break
            if eleccion.isdigit() and 1 <= int(eleccion) <= len(categorias):
                break
            print(f"   Escribe un número del 1 al {len(categorias)}, Intro para "
                  f"saltar o 0 para terminar.")
        if eleccion == "0":
            print()
            return escritas, list(propuestas[n - 1:])
        if eleccion == "":
            print(gris("   Saltado.\n"))
            continue
        categoria = categorias[int(eleccion) - 1]
        # lo que entra, solo para el lado +: es la misma regla que propone el
        # informe, para no arrastrar cargos que se llamen igual
        valor = {"+": categoria} if p.entra else categoria
        linea = f'"{p.clave}": {json.dumps(valor, ensure_ascii=False)}'
        motivo = anadir_regla(rutas.REGLAS, p.clave, valor, rutas.COPIAS)
        if motivo is None:
            escritas += 1
            print(verde(f"   ✓ Añadido a {ruta}:  {linea}\n"))
        else:
            print(rojo(f"   No lo he escrito: {ruta} {motivo}."))
            print(f"   Añádelo a mano:  {linea}\n")
    return escritas, []


def menu_final(historico=None, pendientes=None):
    """
    Al terminar bien, la ventana se queda abierta hasta que se decida qué
    hacer. Con el .exe no hay lanzador que haga una pausa, y la ventana se
    cerraba sola antes de poder leer nada.

    historico es el fichero que se ha escrito de verdad: si el original
    estaba abierto, la copia, que es lo que tiene sentido abrir ahora.
    pendientes (Pendientes) añade las opciones del asistente: excluir el
    recibo de la tarjeta y clasificar lo que falta, escribiendo los JSON por
    la persona. Solo salen si hay algo que ofrecer.
    Devuelve OTRA_VEZ si se ha pedido ejecutar de nuevo.
    """
    if not _interactiva():
        return None
    historico = historico or rutas.HISTORICO
    tarjeta = bool(pendientes and pendientes.tarjeta)
    por_clasificar = list(pendientes.reglas) if pendientes else []
    cambios = 0

    while True:
        opciones = {}

        def opcion(texto, accion, objetivo=None):
            opciones[str(len(opciones) + 1)] = (texto, accion, objetivo)

        if historico.exists():
            opcion(f"Abrir el histórico  ({rutas.relativa(historico)})",
                   "abrir", historico)
            opcion(f"Abrir la carpeta  {rutas.relativa(rutas.DATOS)}/",
                   "abrir", rutas.DATOS)
        if tarjeta:
            exclusiones = pendientes.exclusiones
            detalle = (f"  ({len(exclusiones)} líneas)" if len(exclusiones) > 1
                       else f"  («{exclusiones[0].clave}»)"
                       if exclusiones and exclusiones[0].clave else "")
            opcion("Excluir el recibo de la tarjeta" + detalle, "excluir")
        if por_clasificar:
            grupos = "1 grupo" if len(por_clasificar) == 1 else f"{len(por_clasificar)} grupos"
            opcion(f"Clasificar lo que falta  ({grupos})", "clasificar")
        # lo normal tras abrir el histórico es corregir algo (categoria_manual,
        # una regla) y querer ver el efecto: sin esto había que cerrar la
        # ventana y volver a hacer doble clic
        opcion("Ejecutar de nuevo" + ("  (para aplicar lo que has añadido)"
                                      if cambios else ""), "otra")

        seccion("¿Y ahora?")
        for tecla, (texto, _, _) in opciones.items():
            print(f"   {titular(tecla)}      {texto}")
        print(f"   {titular('Intro')}  Cerrar")
        teclas = list(opciones)
        while True:
            eleccion = _esperar("\n   > ")
            if not eleccion:
                return None
            if eleccion not in opciones:
                validas = (teclas[0] if len(teclas) == 1
                           else f"{', '.join(teclas[:-1])} o {teclas[-1]}")
                print(f"   Escribe {validas}, o pulsa Intro para cerrar.")
                continue
            _, accion, objetivo = opciones[eleccion]
            if accion != "abrir":
                break
            try:
                _abrir(objetivo)
                print("   Abierto. Puedes elegir otra opción, o Intro para cerrar.")
            except Exception as e:
                print(rojo(f"   No he podido abrirlo ({e}). Está en {objetivo}"))

        if accion == "otra":
            return OTRA_VEZ
        if accion == "excluir":
            cambios += asistente_exclusion(pendientes)
            tarjeta = False
        elif accion == "clasificar":
            escritas, por_clasificar = asistente_reglas(por_clasificar)
            cambios += escritas
        # Una regla o una exclusión nuevas solo se notan al volver a
        # ejecutar (el histórico se recalcula entero, así que también
        # reclasifica lo antiguo). Si ya no queda nada que ofrecer, se
        # pregunta directamente; si queda, se vuelve al menú.
        if cambios and not tarjeta and not por_clasificar:
            respuesta = _esperar("\n   Se aplica al ejecutar de nuevo. "
                                 "¿Lo hago ya? (Intro = sí, N = no) ").lower()
            if respuesta not in ("n", "no"):
                return OTRA_VEZ


def _preparar_otra_vuelta():
    """Lo que main() deja acumulado entre ejecuciones. La configuración no
    hace falta: main() la vuelve a leer, y así entra lo que se haya
    corregido en ajustes/ entre medias."""
    _avisos.clear()
    print("\n\n")


# ========= CONFIG =========
# Todas las rutas viven en rutas.py y cuelgan de la carpeta del programa, no
# del directorio actual. Así da igual desde dónde se lance esto.
EXTENSIONES = (".xls", ".xlsx", ".xlsm", ".csv", ".txt", ".tsv", ".ods", ".htm", ".html")

# Columnas A-G: NO cambiar el orden, las fórmulas de la hoja MOVIMIENTOS
# apuntan a columnas concretas.
COLUMNAS_BASE = ["fecha", "descripcion", "importe", "tipo",
                 "mes", "mes_ajustado", "categoria"]
COLUMNAS_HISTORICO = COLUMNAS_BASE + ["categoria_manual", "excluido",
                                      "origen", "regla", "n_rep", "saldo", "cuenta"]

# ========= REGLAS =========
# Se cargan dentro de main(), NO al importar el módulo: antes hay que dejar las
# carpetas en su sitio y migrar lo que venga de la versión antigua, porque si
# no, ajustes/ podría no existir todavía cuando se intente leer.
clasificador = excluidor = catalogo = cfg_sync = cfg_mes = identificador_cuentas = None


def cargar_configuracion():
    global clasificador, excluidor, catalogo, cfg_sync, cfg_mes, identificador_cuentas
    catalogo = Catalogo.desde_json(rutas.CATEGORIAS)
    # El catálogo primero: el clasificador lo necesita para descartar las reglas
    # de la base que apunten a categorías que este usuario no tiene declaradas.
    clasificador = Clasificador.desde_json(
        rutas.REGLAS, ruta_base=rutas.REGLAS_BASE,
        categorias_validas=set(catalogo.todas),
        por_defecto_positivo=catalogo.ingreso_por_defecto,
        equivalencias=catalogo.equivalencias)
    excluidor = Excluidor.desde_json(rutas.EXCLUSIONES)
    identificador_cuentas = IdentificadorCuentas.desde_json(rutas.CUENTAS)
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


# ========= FICHEROS ABIERTOS =========
# Lo normal es tener el histórico abierto en Excel u OnlyOffice mientras se
# corrige categoria_manual, y volver a ejecutar sin cerrarlo. En Windows eso
# fallaba al GUARDAR, con todo ya calculado. En Mac y Linux era peor: no
# fallaba nada, y al guardar después desde la hoja de cálculo se pisaba el
# resultado nuevo con la versión vieja, sin enterarse.
#
# No se cierra el programa que lo tiene abierto, a propósito: con OnlyOffice
# o LibreOffice no hay forma fiable, y con Excel podría llevarse por delante
# otros libros o cambios que no se querían guardar. Guardar y cerrar lo hace
# la persona, que es quien sabe si lo que tiene escrito vale.

# Cómo se sabe si un fichero está abierto (esta_abierto) vive en
# sincronizar.py: lo usan también para el fichero de contabilidad.
esta_abierto = sync.esta_abierto


def ruta_de_copia(ruta):
    """«historico (copia 2026-09-24 10.32.05).xlsx», al lado del original.
    Nunca pisa otra: dos ejecuciones en el mismo segundo no pierden nada."""
    sello = dt.datetime.now().strftime("%Y-%m-%d %H.%M.%S")
    destino = ruta.with_name(f"{ruta.stem} (copia {sello}){ruta.suffix}")
    n = 2
    while destino.exists():
        destino = ruta.with_name(f"{ruta.stem} (copia {sello} {n}){ruta.suffix}")
        n += 1
    return destino


def comprobar_abiertos(rutas_salida):
    """
    Antes de leer nada: si alguna salida está abierta, pide guardarla y
    cerrarla. Tiene que ser ANTES de leer el histórico, no al guardar: así
    lo que se acabe de escribir en categoria_manual y se guarde ahora entra
    en esta misma ejecución.

    Devuelve el conjunto de rutas que hay que escribir en una copia porque
    siguen abiertas (vacío si todo está cerrado). Sin nadie delante para
    contestar, lo abierto va directamente a copia.
    """
    abiertos = {r: m for r in rutas_salida if (m := esta_abierto(r))}
    if not abiertos:
        return set()
    if not _interactiva():
        return set(abiertos)

    while abiertos:
        seccion("Hay ficheros abiertos", pintar=amarillo)
        for r in abiertos:
            print(f"   · {rutas.relativa(r)}")
        print("\n   Si has escrito algo en ellos (categoria_manual, por ejemplo), "
              "GUÁRDALO\n   y cierra el archivo.\n")
        print(f"   {titular('Intro')}  Ya está cerrado: seguir")
        print(f"   {titular('C')}      Dejarlo abierto y guardar el resultado "
              f"en una copia")
        # un fichero de bloqueo sin bloqueo del sistema puede ser un resto de
        # un cierre en falso: sin esta salida, se preguntaría para siempre
        solo_restos = all(m != "sistema" for m in abiertos.values())
        if solo_restos:
            print(f"   {titular('S')}      Seguir igualmente " + gris(
                "(si estás seguro de que está cerrado:\n"
                "          a veces queda el fichero de bloqueo de un programa\n"
                "          que se cerró en falso)"))
        eleccion = _esperar("\n   > ").lower()
        if eleccion == "c":
            return set(abiertos)
        if eleccion == "s" and solo_restos:
            return set()
        abiertos = {r: m for r in abiertos if (m := esta_abierto(r))}
        if abiertos:
            print(amarillo("\n   Todavía está abierto."))
    print(verde("   ✅ Cerrado. Sigo."))
    return set()


def guardar_o_copiar(ruta, escribir, en_copia, copiados):
    """
    Escribe con escribir(destino) en ruta o, si está en en_copia o resulta
    estar bloqueado justo ahora (se ha abierto después de comprobarlo), en
    una copia al lado. Devuelve dónde ha quedado y lo apunta en copiados.
    """
    if ruta not in en_copia:
        try:
            escribir(ruta)
            return ruta
        except PermissionError:
            pass
    destino = ruta_de_copia(ruta)
    escribir(destino)
    copiados[ruta] = destino
    return destino


def avisar_copias(copiados):
    """Que quede claro que lo de verdad NO se ha actualizado: una copia que
    pasa por el histórico es justo el descuadre silencioso que se evita."""
    if not copiados:
        return
    for original, copia in copiados.items():
        print(amarillo(f"   ⚠️  {rutas.relativa(original)} estaba abierto: el "
                       f"resultado está en\n       {rutas.relativa(copia)}"))
    lineas = [f"· {rutas.relativa(o)} → {rutas.relativa(c)}"
              for o, c in copiados.items()]
    if rutas.HISTORICO in copiados:
        lineas.append(
            "El histórico de verdad NO se ha actualizado: la copia es solo para "
            "consultar. No se pierde nada, porque los extractos siguen en "
            "entrada/. Ciérralo y vuelve a ejecutar (opción «Ejecutar de "
            "nuevo») para ponerlo al día; luego puedes borrar la copia.")
        lineas.append(
            "Lo que escribas en categoria_manual de la COPIA no se lee: "
            "escríbelo en el histórico de verdad.")
    avisar("Resultado guardado en una copia porque el original estaba abierto",
           lineas)


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
        return cls({k: v for k, v in leer_json(ruta).items()
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
    # lo que no es un extracto (un PDF, un ZIP) se ignoraba sin decir nada,
    # y quien lo había dejado ahí no sabía si se había leído
    if rutas.ENTRADA.is_dir():
        for f in sorted(os.listdir(rutas.ENTRADA)):
            if not _es_temporal(f) and not _admisible(f) \
                    and (rutas.ENTRADA / f).is_file():
                print(f"   · {f}: " + gris("no es un extracto del banco, lo dejo "
                                           "sin leer"))
    for ruta in localizar_ficheros():
        nombre = os.path.basename(ruta)
        try:
            df = leer_tabla_bancaria(ruta)
            if df.empty:
                print(gris("     → sin movimientos utilizables, lo salto"))
                avisar(f"{nombre} no tiene ningún movimiento utilizable",
                       ["Lo he saltado. Si debería tenerlos, mira el diagnóstico "
                        "de la guía («Cuando algo no sale»)."])
                continue
            tipo, motivo = detectar_tipo(df)
            df["tipo"] = tipo
            df["origen"] = os.path.basename(ruta)
            cuenta = identificador_cuentas.identificar(os.path.basename(ruta))
            df["cuenta"] = cuenta
            # solo se dice algo si HAY una cuenta identificada: sin
            # ajustes/cuentas.json configurado (el caso normal), no aporta
            # nada repetir "cuenta: " vacío en cada línea.
            extra = f" · cuenta: {cuenta}" if cuenta else ""
            print(f"     → {tipo} " + gris(f"({motivo}){extra}"))
            importar_categorias(df, nombre)
            dfs.append(df)
        except Exception as e:
            print(f"   · {nombre}: " + rojo("✗ no se ha podido leer")
                  + gris(" (el motivo, en los avisos del final)"))
            avisar(f"No he podido leer {nombre}", str(e).splitlines())
    return dfs


def importar_categorias(df, nombre):
    """
    El export de otra app de finanzas trae ya su categoría. Si en
    categorias.json se ha pedido (importar_categorias, con qué ficheros y
    cómo se traduce cada una), va a categoria_manual: es lo que ya habías
    decidido tú en la otra app, y ahí se puede corregir como cualquier otra.

    Solo con esa configuración: hay bancos que exportan su propia columna
    «Categoría», y no puede pisar tus reglas sin que lo hayas decidido. Lo
    que no se traduce a una categoría tuya se queda con las reglas, y se
    avisa de qué valores eran.
    """
    trae = df["categoria_fichero"].ne("")
    imp = catalogo.importar
    valido = (isinstance(imp, dict) and isinstance(imp.get("traducir"), dict)
              and str(imp.get("fichero", "")).strip())
    if not trae.any():
        return
    if not valido or not compilar(str(imp["fichero"]))[0].search(normalizar(nombre)):
        print(gris("     (trae una columna de categoría; si es el export de otra "
                   "app, mira importar_categorias en la guía)"))
        return
    validas = set(catalogo.todas) | {hist.MARCA_EXCLUIDO}
    # la que ya se llama como una tuya vale tal cual, sin traducirla
    traducir = {normalizar(c): c for c in catalogo.todas}
    traducir.update({normalizar(k): v for k, v in imp["traducir"].items()
                     if v in validas})
    traducida = df["categoria_fichero"].map(lambda c: traducir.get(normalizar(c), ""))
    df["categoria_manual"] = traducida
    print(f"     → {int(traducida.ne('').sum())} con la categoría del fichero "
          + gris("(importar_categorias)"))
    sin = sorted(set(df.loc[trae & traducida.eq(""), "categoria_fichero"]))
    if sin:
        avisar(f"{nombre}: categorías sin traducir", [
            f"{', '.join(sin)}: no están en «traducir» de importar_categorias "
            f"(o apuntan a una categoría que no tienes). Esos movimientos se "
            f"quedan con lo que digan tus reglas.",
            "Lo que ya se importó antes está en categoria_manual y se queda "
            "ahí aunque quites su traducción: bórralo en esa columna si "
            "quieres que manden las reglas."])


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


# ========= SALDO INICIAL DE LA CUENTA =========
# Si el extracto trae columna de saldo, el Acumulado del resumen puede partir
# del saldo real de la cuenta en vez de partir de 0. Sin esto, alguien que
# empieza a usar la herramienta con 10.000 € ya en la cuenta ve un Acumulado
# que arranca en 0 y no vuelve a coincidir con su banco hasta que lo entiende.
def calcular_saldo_inicial(todo) -> dict:
    """
    El saldo de cada cuenta (ver ajustes/cuentas.json) justo ANTES de su
    primer movimiento conocido: {"": 5000.0} si solo hay una (o ninguna
    declarada, el caso normal), {"principal": 5000.0, "ahorro": 800.0} con
    varias. 0.0 para una cuenta sin saldo conocido (solo tarjeta, un extracto
    sin columna de saldo, o el caso ambiguo de _saldo_inicial_una_cuenta):
    mismo comportamiento que hasta ahora, esa cuenta no arrastra nada.

    Cada cuenta se calcula POR SEPARADO: mezclar movimientos de cuentas
    distintas para decidir "qué pasó primero" sería tan inventado como
    adivinar el orden dentro de un mismo día.
    """
    cuenta_mov = todo[todo["tipo"] == "cuenta"]
    return {id_cuenta: _saldo_inicial_una_cuenta(grupo) or 0.0
            for id_cuenta, grupo in cuenta_mov.groupby("cuenta")}


def cuentas_sin_saldo(todo) -> list:
    """Las cuentas (su identificador, "" si no hay cuentas.json) cuyo saldo
    de partida no se conoce: su extracto no trae saldo, o ningún día es
    inequívoco. Para ellas el Acumulado parte de 0 y no es su saldo."""
    cuenta_mov = todo[todo["tipo"] == "cuenta"]
    return sorted(id_cuenta for id_cuenta, grupo in cuenta_mov.groupby("cuenta")
                  if _saldo_inicial_una_cuenta(grupo) is None)


def _saldo_inicial_una_cuenta(movimientos):
    """
    El único sitio delicado es el primer DÍA con más de un movimiento: el
    saldo que trae cada fila es el que queda TRAS ella, y sin saber el orden
    real en que el banco los aplicó ese día no se puede invertir uno
    cualquiera con garantías. Por eso se busca el primer día que tenga saldo
    conocido y UN SOLO movimiento (sin ambigüedad posible) y se resta desde
    ahí lo de los días anteriores, que si son días completos enteros sí se
    pueden sumar sin importar el orden dentro de cada uno. Si ni un solo día
    es así de simple, mejor 0.0 que un cuadre inventado.

    Devuelve None (no 0.0) cuando no se sabe: para el Acumulado da igual,
    pero comprobar_cuadre() no puede comparar con el banco partiendo de un
    saldo que no es el real.
    """
    con_saldo = movimientos[movimientos["saldo"].notna()]
    if con_saldo.empty:
        return None

    un_solo_movimiento = con_saldo.groupby("fecha").size()
    fechas_sin_ambiguedad = sorted(un_solo_movimiento[un_solo_movimiento == 1].index)
    if not fechas_sin_ambiguedad:
        return None

    ancla_fecha = fechas_sin_ambiguedad[0]
    ancla = con_saldo[con_saldo["fecha"] == ancla_fecha].iloc[0]
    anteriores = movimientos.loc[movimientos["fecha"] < ancla_fecha, "importe"].sum()
    return float(ancla["saldo"] - ancla["importe"] - anteriores)


# ========= CUENTAS DEL HISTÓRICO =========
def asignar_cuentas_pendientes(previo) -> int:
    """
    Rellena la cuenta de las filas del histórico que no la tienen, a partir
    de su fichero de origen, con lo declarado HOY en cuentas.json. Devuelve
    cuántas ha rellenado.

    Sin esto, declarar las cuentas después de la primera ejecución duplicaba
    el histórico entero: las filas viejas se quedaban con cuenta "" y las
    mismas, releídas de entrada/, entraban con cuenta "negocio"; la clave de
    duplicados las veía distintas y todo sumaba el doble, sin aviso y sin
    arreglo (salvo borrar el histórico). Con la cuenta rellenada, las viejas
    y las nuevas vuelven a ser la misma, y fusionar() se queda con una. Eso
    también cura un histórico que ya se hubiera duplicado así.

    Solo rellena, NUNCA pisa una cuenta ya puesta: si se cambia o se vacía
    cuentas.json, dos movimientos idénticos de cuentas distintas no pueden
    acabar fusionados en uno por reasignarlos.
    """
    if previo.empty or not identificador_cuentas.reglas:
        return 0
    sin_cuenta = previo["cuenta"].eq("")
    nuevas = previo.loc[sin_cuenta, "origen"].fillna("").astype(str).map(
        identificador_cuentas.identificar)
    previo.loc[nuevas.index, "cuenta"] = nuevas
    return int(nuevas.ne("").sum())


# ========= FICHEROS QUE NO CASAN CON SU CUENTA =========
# La clave de duplicados lleva la cuenta (hito A3). Eso tiene dos caras:
#   · con cuentas.json declarado, un fichero cuyo nombre no casa con ningún
#     patrón (el «movimientos (1).xls» de volver a descargar) entraba como
#     una cuenta más, sin identificar, y TODO lo suyo se sumaba dos veces;
#     el cuadre ni se inmutaba, porque esa «cuenta» cuadra consigo misma.
#   · sin declararlo, dos tarjetas (o cuentas) con un cargo idéntico el
#     mismo día se funden en uno, que es lo documentado, pero quien tiene
#     dos tarjetas no sabía que le tocaba declararlas.
_PARECIDO_MINIMO = 0.5        # fracción de movimientos compartidos a partir
                              # de la cual dos ficheros son la misma cuenta
_SOLAPE_MINIMO_DIAS = 7       # por debajo, dos ficheros consecutivos (julio y
                              # agosto) no dicen nada de si son la misma


def _claves_sin_cuenta(df) -> pd.Series:
    """La clave de duplicados sin la cuenta, con su número de repetición:
    dos cafés iguales el mismo día son dos claves, no una."""
    base = hist._clave(df.assign(cuenta=""))
    return base + "#" + base.groupby(base).cumcount().astype(str)


def apartar_copias_sin_cuenta(previo, nuevos):
    """
    Con cuentas declaradas, un fichero que no casa con ninguna y cuyos
    movimientos ya están (en su mayoría) en una cuenta declarada es otra
    descarga de esa cuenta con otro nombre: NO se lee, y se dice cómo
    arreglarlo. Si no se parece a ninguna, es una cuenta más y entra como
    siempre.
    """
    if not identificador_cuentas.reglas:
        return nuevos
    conocidas = {}
    for df in [previo] + list(nuevos):
        con_cuenta = df[df["cuenta"].ne("")]
        for cuenta, grupo in con_cuenta.groupby("cuenta"):
            conocidas.setdefault(cuenta, set()).update(_claves_sin_cuenta(grupo))
    if not conocidas:
        return nuevos

    quedan = []
    for df in nuevos:
        if df.empty or (df["cuenta"] != "").any():
            quedan.append(df)
            continue
        claves = set(_claves_sin_cuenta(df))
        cuenta, comunes = max(((c, len(claves & k)) for c, k in conocidas.items()),
                              key=lambda x: x[1])
        if comunes < _PARECIDO_MINIMO * len(claves):
            quedan.append(df)
            continue
        nombre = df["origen"].iloc[0]
        print(f"     " + amarillo(f"⚠️  {nombre}: parece otra descarga de "
                                  f"«{cuenta}»; no lo leo"))
        avisar(f"No he leído {nombre}: parece otra descarga de «{cuenta}»", [
            f"Su nombre no casa con ninguna cuenta de "
            f"{rutas.relativa(rutas.CUENTAS)}, y {comunes} de sus {len(claves)} "
            f"movimientos ya están en «{cuenta}». Si lo leyera, entraría como "
            f"una cuenta aparte y todo lo suyo se contaría dos veces.",
            f"Renómbralo para que lleve lo que identifica a «{cuenta}» en el "
            f"nombre (o añade un patrón para él en cuentas.json) y vuelve a "
            f"ejecutar."])
    return quedan


def avisar_cuentas_sin_declarar(nuevos):
    """
    Sin cuentas.json: dos ficheros del mismo tipo que cubren las mismas
    fechas pero casi no comparten movimientos no son dos descargas de lo
    mismo, sino dos tarjetas (o cuentas). Se avisa, con lo que se ha
    fundido si ya ha pasado. Devuelve (hay aviso, cuántos se han fundido):
    lo usan la línea de «ya estaban» y el aviso del recibo de la tarjeta.
    """
    hay, fundidos = False, 0
    if identificador_cuentas.reglas or len(nuevos) < 2:
        return hay, fundidos
    for i, a in enumerate(nuevos):
        for b in nuevos[i + 1:]:
            if a.empty or b.empty or a["tipo"].iloc[0] != b["tipo"].iloc[0]:
                continue
            desde = max(a["fecha"].min(), b["fecha"].min())
            hasta = min(a["fecha"].max(), b["fecha"].max())
            if (hasta - desde).days < _SOLAPE_MINIMO_DIAS:
                continue
            en_a = a[(a["fecha"] >= desde) & (a["fecha"] <= hasta)]
            en_b = b[(b["fecha"] >= desde) & (b["fecha"] <= hasta)]
            menor = min(len(en_a), len(en_b))
            if menor < 3:
                continue
            claves_a = _claves_sin_cuenta(en_a)
            comunes = set(claves_a) & set(_claves_sin_cuenta(en_b))
            if len(comunes) >= _PARECIDO_MINIMO * menor:
                continue
            tipo = a["tipo"].iloc[0]
            que = "tarjetas" if tipo == "tarjeta" else "cuentas"
            lineas = [f"«{a['origen'].iloc[0]}» y «{b['origen'].iloc[0]}» "
                      f"cubren las mismas fechas pero casi no comparten "
                      f"movimientos: no son dos descargas de lo mismo. Sin "
                      f"declararlas, un cargo idéntico el mismo día en las dos "
                      f"(dos cafés iguales, uno en cada tarjeta) se cuenta "
                      f"UNA sola vez."]
            hay = True
            fundidos += len(comunes)
            if comunes:
                fundido = -en_a.loc[claves_a.isin(comunes).values, "importe"].sum()
                lineas.append(f"Aquí ha pasado con {len(comunes)}: faltan "
                              f"{euros(fundido)} en los totales.")
            lineas.append(f"Decláralas en {rutas.relativa(rutas.CUENTAS)}, con "
                          f"una parte del nombre de cada fichero (la guía lo "
                          f"explica en «Varias cuentas o tarjetas»).")
            avisar(f"Parecen dos {que} distintas sin declarar", lineas)
    return hay, fundidos


# ========= CUADRE CON EL SALDO DEL BANCO =========
# El Acumulado del resumen es saldo inicial + movimientos de cuenta. Si falta
# alguno (un hueco entre dos extractos, una fila que el lector ha descartado,
# dos movimientos idénticos de verdad fusionados como duplicados), el
# Acumulado se despega del banco para siempre, en silencio. Pero el propio
# extracto trae el saldo tras cada movimiento: basta con compararlo.
_TOLERANCIA_CUADRE = 0.005
_MAX_SALTOS_MOSTRADOS = 5


def comprobar_cuadre(todo) -> dict:
    """
    Para cada cuenta con saldo en el extracto: {cuenta: (ultima_fecha,
    saldo_banco, saldo_calculado, saltos, n_ficheros)}, donde saltos es la
    lista de (fecha, diferencia) en que el cálculo deja de coincidir con el
    banco, y n_ficheros de cuántos extractos salen sus movimientos.
    Sin saltos y con los dos saldos iguales, cuadra.

    Se compara día a día, no fila a fila: dentro de un día el orden en que el
    banco aplicó los movimientos no se conoce, pero el saldo al cerrar el día
    tiene que ser el de ALGUNA de sus filas (la última que aplicó).
    """
    resultado = {}
    cuenta_mov = todo[todo["tipo"] == "cuenta"]
    for id_cuenta, grupo in cuenta_mov.groupby("cuenta"):
        inicial = _saldo_inicial_una_cuenta(grupo)
        if inicial is None:
            continue

        calculado = inicial
        desfase = 0.0          # banco - calculado, tras el último salto visto
        saltos = []
        saldo_banco = ultima_fecha = None
        for fecha, dia in grupo.groupby("fecha", sort=True):
            calculado += dia["importe"].sum()
            candidatos = dia["saldo"].dropna()
            if candidatos.empty:
                continue
            desfases = candidatos - calculado
            if not ((desfases - desfase).abs() < _TOLERANCIA_CUADRE).any():
                # el más cercano al desfase anterior: con varias filas en el
                # día, es la lectura que menos salto supone
                nuevo = float(desfases.loc[(desfases - desfase).abs().idxmin()])
                saltos.append((fecha, nuevo - desfase))
                desfase = nuevo
            saldo_banco = calculado + desfase
            ultima_fecha = fecha
        resultado[id_cuenta] = (ultima_fecha, saldo_banco, calculado, saltos,
                                grupo["origen"].nunique())
    return resultado


def informar_cuadre(cuadre):
    """Una línea si cuadra; si no, en qué fechas se rompe y por cuánto."""
    if not cuadre:
        return
    varias = len(cuadre) > 1
    for id_cuenta, (fecha, banco, calculado, saltos, n_ficheros) in sorted(cuadre.items()):
        nombre = f" ({id_cuenta or 'sin identificar'})" if varias else ""
        if not saltos and abs(banco - calculado) < _TOLERANCIA_CUADRE:
            print(verde(f"   🧮 Cuadra con el banco{nombre}: {euros(calculado)} "
                        f"a {fecha:%d/%m/%Y}, igual que el extracto."))
            continue

        # si el final coincide, los saltos se han compensado entre sí: decir
        # «no cuadra: 8.670,85 € contra 8.670,85 €» parecía una contradicción
        acaba_bien = abs(banco - calculado) < _TOLERANCIA_CUADRE
        if acaba_bien:
            print(amarillo(f"   ⚠️  Al final cuadra con el banco{nombre} "
                           f"({euros(banco)} a {fecha:%d/%m/%Y}), pero no en\n"
                           f"       todas las fechas. Mira los avisos del final."))
            lineas = ["Hay fechas en que el saldo calculado se separa del saldo del "
                      "banco y luego vuelve a coincidir. Aparece en:"]
        else:
            print(amarillo(f"   ⚠️  No cuadra con el banco{nombre}: el extracto dice "
                           f"{euros(banco)} a {fecha:%d/%m/%Y}\n       y el "
                           f"cálculo da {euros(calculado)}. Mira los avisos del final."))
            lineas = [f"Diferencia final: {euros(banco - calculado, signo=True)} "
                      f"(saldo del banco menos el calculado). Aparece en:"]
        for f, dif in saltos[:_MAX_SALTOS_MOSTRADOS]:
            lineas.append(f"· {f:%d/%m/%Y}: {euros(dif, signo=True)}")
        if len(saltos) > _MAX_SALTOS_MOSTRADOS:
            lineas.append(f"· ... y {len(saltos) - _MAX_SALTOS_MOSTRADOS} más")
        if acaba_bien:
            lineas.append(
                "Los totales del final están bien. Lo normal es un movimiento "
                "con la fecha cambiada entre dos extractos, o dos del mismo "
                "día que el banco aplicó en otro orden.")
        else:
            lineas += [
                "Entre la fecha anterior con saldo y esa, falta un movimiento de "
                "ese importe (o sobra, si es negativo). Lo normal es un hueco "
                "entre dos extractos: descarga el que cubra esas fechas y vuelve "
                "a ejecutar.",
                "Hasta entonces, el Acumulado del resumen arrastra esa diferencia."]
            # dos cuentas sin declarar se mezclan como si fueran una, y cada
            # saldo del banco contradice al otro: la causa no es un hueco
            if id_cuenta == "" and n_ficheros > 1:
                lineas.append(
                    f"Son {n_ficheros} ficheros de cuenta. Si son de cuentas "
                    f"DISTINTAS (no descargas de la misma), decláralas en "
                    f"ajustes/cuentas.json: sin eso se mezclan como una sola "
                    f"y los saldos no pueden cuadrar.")
        titulo = ("El saldo calculado se separa del saldo del banco en algunas fechas"
                  if acaba_bien else "El saldo calculado no cuadra con el del banco")
        avisar(f"{titulo}{nombre}", lineas)


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
                # en valor absoluto: se llama con un solo signo cada vez (ver
                # informe_sin_clasificar), y con el signo tal cual, en lo que
                # ENTRA ganaba la palabra de MENOS importe (el nombre de un
                # solo cliente en vez de lo común a todos sus cobros)
                gasto[palabra] = gasto.get(palabra, 0.0) + abs(sin_regla.at[i, "importe"])
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


# Palabras de un recibo de tarjeta: con tarjeta y sin nada excluido, un grupo
# así es el recibo, y ponerle categoría contaría las compras dos veces.
_PALABRAS_RECIBO_TARJETA = {"tarjeta", "tarj", "visa", "mastercard",
                            "liquidacion", "liq"}


def _parece_recibo_tarjeta(filas) -> bool:
    return all(set(re.findall(r"[a-z]+", normalizar(d))) & _PALABRAS_RECIBO_TARJETA
               for d in filas["descripcion"]) and filas["importe"].sum() < 0


def informe_sin_clasificar(df, ignorar=frozenset(), tarjeta_sin_excluir=False):
    """
    Hito A1 del roadmap: qué se ha quedado en Otros SIN que ninguna regla
    casara. `regla == ""` es justo eso (ver clasificar()): por construcción
    implica categoria == por_defecto (o, si entra dinero, la categoría de
    ingreso por defecto del catálogo). Una regla que apunte a Otros a propósito
    deja «regla» rellena con su clave, así que no entra aquí: eso ya está
    clasificado, no es "esto no sé qué es".

    ignorar: descripciones que otro aviso ya resuelve (el recibo de la
    tarjeta, que hay que excluir, no clasificar).

    tarjeta_sin_excluir: hay tarjeta y nada excluido, pero el detector no ha
    dado con el recibo. Un grupo que lo parezca no recibe sugerencia de
    categoría, que era el consejo contrario al del aviso de la tarjeta.

    Devuelve (las propuestas que ha impreso como «añade a rules.json», las
    mismas y ni una más; y (clave, ejemplo) del primer grupo que parece el
    recibo de la tarjeta, o None), para que el asistente del menú final
    ofrezca las reglas y, si el detector no lo encontró, ese recibo.
    """
    propuestas = []
    recibo_en_grupo = None
    sin_regla = df[(df["regla"] == "") & ~df["descripcion"].isin(ignorar)]
    if sin_regla.empty:
        return propuestas, recibo_en_grupo

    # lo que sale y lo que entra, cada uno por su lado: una palabra común a
    # un cobro y a un cargo no hace de ellos un grupo, y la regla que se
    # propone es distinta para cada lado
    # Excepción: un abono con la palabra de un grupo de cargos es su
    # devolución («DEVOLUCION BRICOMART») y va con él, porque la regla que se
    # propone para ese comercio también debe cogerla.
    grupos = _agrupar_sin_clasificar(sin_regla[sin_regla["importe"] < 0])
    entra = sin_regla[sin_regla["importe"] >= 0]
    for n, (palabra, filas) in enumerate(grupos):
        suyas = [i for i in entra.index
                 if palabra in _palabras_candidatas(entra.at[i, "descripcion"])]
        if suyas:
            grupos[n] = (palabra, pd.concat([filas, entra.loc[suyas]]))
            entra = entra.drop(index=suyas)
    grupos += _agrupar_sin_clasificar(entra)
    if not grupos:
        return propuestas, recibo_en_grupo

    # de más a menos importe, con el mismo criterio que el resto del resumen:
    # en positivo (-suma), sin ABS() que disfrace un grupo que acabe a favor.
    grupos.sort(key=lambda g: g[1]["importe"].sum())
    mostrados = grupos[:_MAX_GRUPOS_SIN_CLASIFICAR]

    # universo contra el que se valida cada clave sugerida: todo lo que YA
    # tiene categoría por una regla de verdad, no por una corrección manual
    # (esa manda igual, así que da igual si la nueva clave también la toca).
    clasificados = df.loc[~df["regla"].isin(("", "(manual)")), "descripcion"]
    normalizados = [normalizar(d) for d in clasificados]

    seccion("Sin clasificar")
    print(f"ℹ️  {len(sin_regla)} movimientos sin ninguna regla, en "
          f"{len(grupos)} grupos por palabra común:")
    if len(grupos) > _MAX_GRUPOS_SIN_CLASIFICAR:
        print(gris(f"   (se muestran los {_MAX_GRUPOS_SIN_CLASIFICAR} de más importe)"))
    print()

    for palabra, filas in mostrados:
        total = -filas["importe"].sum()
        ejemplo = filas["descripcion"].mode().iloc[0]
        # un grupo de dinero que ENTRA (cobros, recargas) salía como un gasto
        # en negativo, sin más: se dice qué es, y la regla que se propone es
        # solo para el lado positivo, para no arrastrar cargos con el mismo
        # nombre
        entra = total < 0
        cifra = euros(-total if entra else total, ancho=10)
        tipo = "  ·  entra" if entra else ""
        print(f"   {cifra}  ·  {len(filas):>3} mov.  ·  {palabra}{tipo}")
        print(gris(f"      ej: {ejemplo}"))
        sugerida = _sugerir_regla(filas, palabra, normalizados)
        if tarjeta_sin_excluir and _parece_recibo_tarjeta(filas):
            print("      parece el recibo de la tarjeta: exclúyelo en "
                  "exclude_patterns.json, no le pongas categoría")
        elif sugerida and entra:
            print(f'      añade a rules.json:  "{sugerida}": '
                  f'{{"+": "{_PLACEHOLDER_CATEGORIA}"}}')
        elif sugerida:
            print(f'      añade a rules.json:  "{sugerida}": '
                  f'"{_PLACEHOLDER_CATEGORIA}"')
        else:
            print(gris("      (ninguna palabra de este grupo es segura de sugerir "
                       "sin pisar otra regla; revísalo a mano)"))
        print()
        if tarjeta_sin_excluir and _parece_recibo_tarjeta(filas):
            if sugerida and recibo_en_grupo is None:
                recibo_en_grupo = (sugerida, ejemplo)
        elif sugerida:
            propuestas.append(Propuesta(sugerida, entra, palabra, len(filas),
                                        -total if entra else total, ejemplo))

    return propuestas, recibo_en_grupo


# ========= DETECCIÓN DEL RECIBO DE LA TARJETA (hito A2 del roadmap) =========
# El fallo #1 del programa (ver LEEME.txt): si la cuenta paga la tarjeta con
# un recibo sin excluir, cada gasto de la tarjeta cuenta DOS VECES (una en el
# extracto de la tarjeta, otra en el de la cuenta) y el resumen infla los
# gastos en silencio.
#
# Aquí se prioriza no equivocarse antes que acertar siempre: un mes con más
# de un cargo que cuadra se descarta entero en vez de adivinar cuál es
# (_candidato_liquidacion), y la clave que se sugiere se valida contra el
# resto de los movimientos de cuenta antes de proponerla, igual que en
# informe_sin_clasificar(). Proponer una exclusión que se lleve por delante
# un gasto real sería peor que no proponer nada.
_TOLERANCIA_RECIBO = 0.02           # 2 céntimos: cubre el redondeo de sumar
                                    # muchos apuntes en coma flotante, sin
                                    # abrirse a cuadres que no lo son de verdad.
_MARGEN_DIAS_LIQUIDACION = 45       # del día 1 del mes de la tarjeta a 45 días
                                    # después de que acabe ese mes: cubre
                                    # liquidar dentro del mismo mes o a
                                    # principios del siguiente sin saber el
                                    # día de corte real de cada banco.
_LONGITUD_MINIMA_CLAVE_RECIBO = 5   # por debajo de esto no hay frase de
                                    # verdad que proponer, solo una letra o
                                    # dos sueltas.
_MARGEN_DIAS_ESPEJO = 10            # entre el cargo en la cuenta y el mismo
                                    # pago abonado en la tarjeta: los bancos
                                    # lo apuntan el mismo día o casi.


def _espejos(tarjeta, cuenta) -> dict:
    """
    {fila de tarjeta: fila de cuenta} de cada abono en la tarjeta con el
    MISMO importe, de signo contrario, que un cargo de la cuenta a pocos
    días, y solo si ese cargo es el único que encaja. Es el pago de la
    tarjeta visto desde los dos lados: lo que sale de la cuenta entra en la
    tarjeta. Algunos bancos («CARGO TARJETA …» en la cuenta y «PAGO
    RECIBO …» en la tarjeta) lo apuntan en los dos extractos, y el abono, sin
    excluir, contaba como un ingreso. Se busca por importe y no por el
    nombre, que cambia de un banco a otro.
    """
    pares = {}
    cargos = cuenta[cuenta["importe"] < 0]
    for i, fila in tarjeta[tarjeta["importe"] > 0].iterrows():
        cerca = cargos[
            ((cargos["fecha"] - fila["fecha"]).abs() <= pd.Timedelta(days=_MARGEN_DIAS_ESPEJO))
            & ((cargos["importe"] + fila["importe"]).abs() <= _TOLERANCIA_RECIBO + 1e-9)
            & ~cargos.index.isin(list(pares.values()))]
        if len(cerca) == 1:
            pares[i] = cerca.index[0]
    return pares


def _candidato_liquidacion(cuenta, mes, importe_tarjeta):
    """
    La fila de cuenta, si hay UNA sola, cuyo importe cuadra (con tolerancia)
    con lo que debe la tarjeta ese mes, dentro de la ventana de liquidación.
    Los dos son un GASTO, así que llevan el MISMO signo (negativo), no signos
    opuestos: la tarjeta dice que gastaste 95,30 € y la cuenta paga 95,30 €.

    Ambiguo (más de una fila encaja) o ninguna -> None. Mejor no proponer
    nada que proponer lo que no toca.
    """
    inicio = pd.Timestamp(mes + "-01")
    fin = inicio + pd.offsets.MonthEnd(1) + pd.Timedelta(days=_MARGEN_DIAS_LIQUIDACION)
    en_ventana = cuenta[(cuenta["fecha"] >= inicio) & (cuenta["fecha"] <= fin)]
    # el +1e-9 es solo para que sumar en coma flotante no eche fuera un
    # cuadre que a céntimos SÍ lo es (-40.02 - -40.00 da 0.020000000000003,
    # no 0.02 exactos, y por 3e-15 no puede quedar fuera de la tolerancia).
    encaja = en_ventana[(en_ventana["importe"] - importe_tarjeta).abs()
                        <= _TOLERANCIA_RECIBO + 1e-9]
    return encaja.iloc[0] if len(encaja) == 1 else None


def _sin_numeros(texto):
    """Cada tramo de dígitos (la referencia del recibo, que cambia de un mes
    a otro) se cambia por DOS espacios, para poder distinguirlo luego (con
    \\s{2,}) de un simple espacio entre dos palabras que sí son fijas."""
    return re.sub(r"\d+", "  ", texto)


def _clave_liquidacion(descripciones):
    """
    La parte del texto que NO cambia de un mes a otro. Con más de una
    descripción, se queda con lo que tengan en común todas (la referencia,
    que sí cambia, ya se ha marcado aparte con _sin_numeros); con una sola,
    con el trozo más largo que le queda tras quitar la referencia.

    Se conserva tal cual aparece en el texto original, sin reordenar ni
    pegar palabras que no estaban juntas: si se uniera "tarjeta" y "credito"
    saltándose el número de en medio, la clave ya no encontraría ese hueco el
    mes que viene, que va a traer OTRO número.
    """
    limpias = [_sin_numeros(normalizar(d)) for d in descripciones]
    comun = limpias[0]
    for otra in limpias[1:]:
        i, _, n = difflib.SequenceMatcher(None, comun, otra).find_longest_match(
            0, len(comun), 0, len(otra))
        comun = comun[i:i + n]
    trozos = re.split(r"\s{2,}", comun)
    return max(trozos, key=len).strip()


def detectar_recibo_tarjeta(todo, sin_declarar=False) -> RecibosTarjeta:
    """
    Hito A2 del roadmap: el pago con que la cuenta liquida la tarjeta, que
    sin excluir hace contar dos veces sus gastos. Se busca de dos maneras,
    las dos por importe (el nombre cambia de un banco a otro):

    - el cargo de la cuenta que cuadra con lo que suma la tarjeta en el mes
      (_candidato_liquidacion);
    - los espejos (_espejos): un abono en la tarjeta por el mismo importe que
      un cargo de la cuenta. Dan los DOS lados del pago, y también el recibo
      de las tarjetas de pago aplazado, que no cuadra con lo que suma el mes.
      Para no tomar por el recibo una devolución que coincida por casualidad
      con un cargo cualquiera, un espejo vale si su cargo es también el que
      cuadra con el mes, o si los hay en dos meses distintos o más.

    Cada lado se da por resuelto si sus filas ya están excluidas (o, el de
    la tarjeta, si caen en una categoría neutra, que no suma en ningún
    sitio). Antes, con cualquier patrón puesto se callaba todo: excluido el
    recibo de la cuenta, nada avisaba del abono en la tarjeta, que seguía
    inflando los Ingresos. Sin nada detectado y con patrones puestos sí se
    sigue dando por resuelto, como pedía el roadmap.

    No imprime nada: deja el aviso para el final, con los demás.
    """
    nada = RecibosTarjeta(False, set(), [])
    tarjeta = todo[todo["tipo"] == "tarjeta"]
    # Sin ningún extracto de cuenta no hay recibo que pueda contarse dos
    # veces: quien solo tiene tarjetas (una de débito, un neobanco) recibía
    # el aviso en cada ejecución sin poder hacer nada con él.
    cuenta = todo[todo["tipo"] == "cuenta"]
    if tarjeta.empty or cuenta.empty:
        return nada

    espejos = _espejos(tarjeta, cuenta)
    # lo que suma la tarjeta, SIN los abonos del pago: si no, el del mes
    # anterior resta de las compras de este y la suma ya no cuadra con su
    # recibo (siguen contando las devoluciones de verdad). Y si así un mes
    # no cuadra, se prueba con la suma entera: el «espejo» podía ser una
    # devolución de verdad que coincidía por casualidad con otro cargo, y
    # esa sí la descuenta el banco del recibo.
    compras = tarjeta.drop(index=list(espejos))
    tarjeta_por_mes = compras.groupby("mes")["importe"].sum()
    neto_por_mes = tarjeta.groupby("mes")["importe"].sum()
    # Con dos tarjetas, cada una se liquida con su propio recibo y la suma de
    # las dos no cuadra con ninguno: se prueba primero el total del mes y,
    # si no, cada tarjeta por separado (por su cuenta declarada o, sin
    # cuentas.json, por el fichero del que sale).
    cual = compras["cuenta"].where(compras["cuenta"].ne(""), compras["origen"])
    por_tarjeta = compras.groupby([cual, "mes"])["importe"].sum()
    varias = cual.nunique() > 1
    candidatos = {}
    usadas = set()
    for mes, importe in tarjeta_por_mes.items():
        fila = _candidato_liquidacion(cuenta, mes, importe)
        if fila is None and abs(neto_por_mes[mes] - importe) > _TOLERANCIA_RECIBO:
            importe = neto_por_mes[mes]
            fila = _candidato_liquidacion(cuenta, mes, importe)
        if fila is not None:
            candidatos[("", mes)] = (fila, importe)
            usadas.add(fila.name)
            continue
        if not varias:
            continue
        for (id_tarjeta, mes_t), importe_t in por_tarjeta.items():
            if mes_t != mes:
                continue
            fila = _candidato_liquidacion(cuenta.drop(index=list(usadas)),
                                          mes, importe_t)
            if fila is not None:
                candidatos[(id_tarjeta, mes)] = (fila, importe_t)
                usadas.add(fila.name)

    meses_espejo = {tarjeta.at[i, "mes"] for i in espejos}
    confirmados = {i: j for i, j in espejos.items()
                   if j in usadas or len(meses_espejo) >= 2}
    lado_cuenta = set(usadas) | set(confirmados.values())
    lado_tarjeta = set(confirmados)

    titulo = ("Tienes movimientos de tarjeta y ningún patrón en "
              "exclude_patterns.json")
    # con tarjetas sin declarar fundidas, alguna deja de cuadrar con su
    # recibo; se decía «no encuentro una clave segura» sin decir por qué
    pista = ([f"Primero declara tus tarjetas en {rutas.relativa(rutas.CUENTAS)} "
              f"(ver el aviso de las dos tarjetas): con cargos de las dos fundidos "
              f"en uno, la tarjeta ya no suma lo que paga su recibo y no lo "
              f"encuentro."] if sin_declarar else [])
    if not lado_cuenta and not lado_tarjeta:
        if excluidor.patrones:
            return nada
        avisar(titulo, [
            "Si tu cuenta paga la tarjeta con un recibo, cada gasto se está "
            "contando DOS VECES y no lo he sabido encontrar solo.",
            "Revísalo a mano: LEEME.txt explica cómo excluirlo."] + pista)
        return RecibosTarjeta(True, set(), [])

    descripciones = {todo.at[i, "descripcion"] for i in lado_cuenta | lado_tarjeta}
    neutras = set(catalogo.neutras)
    falta_cuenta = sorted(i for i in lado_cuenta if not todo.at[i, "excluido"])
    falta_tarjeta = sorted(i for i in lado_tarjeta if not todo.at[i, "excluido"]
                           and todo.at[i, "categoria"] not in neutras)
    if not falta_cuenta and not falta_tarjeta:
        return RecibosTarjeta(False, descripciones, [])

    # la clave de cada lado, validada contra TODO lo demás (cuenta y
    # tarjeta): Excluidor no mira el tipo, así que una clave que casara con
    # una compra de la tarjeta se la llevaría por delante
    otras = [normalizar(d) for i, d in todo["descripcion"].items()
             if i not in lado_cuenta and i not in lado_tarjeta]

    def clave_de(filas):
        clave = _clave_liquidacion([todo.at[i, "descripcion"] for i in filas])
        if len(clave) < _LONGITUD_MINIMA_CLAVE_RECIBO:
            return None, False
        patron, _ = compilar(clave)
        return clave, not any(patron.search(d) for d in otras)

    lineas = []
    propuestas = []
    por_fila = {f.name: (k, imp) for k, (f, imp) in candidatos.items()}
    if falta_cuenta:
        lineas.append("Si no se excluye, cada gasto de la tarjeta cuenta DOS VECES. "
                      "Esto parece el recibo:")
        for i in sorted(falta_cuenta, key=lambda i: todo.at[i, "fecha"]):
            fila = todo.loc[i]
            if i in por_fila:
                (id_tarjeta, mes), importe = por_fila[i]
                de = f" ({id_tarjeta})" if id_tarjeta else ""
                lineas.append(f"· {mes}: la tarjeta{de} suma {euros(-importe)} y "
                              f"tu cuenta tiene un cargo de {euros(-fila['importe'])} el "
                              f"{fila['fecha']:%d/%m/%Y}  («{fila['descripcion']}»)")
            else:
                lineas.append(f"· {fila['fecha']:%d/%m/%Y}: tu cuenta paga "
                              f"{euros(-fila['importe'])} y ese mismo importe entra en "
                              f"la tarjeta  («{fila['descripcion']}»)")
        clave, segura = clave_de(lado_cuenta)
        if segura:
            lineas.append(f'Añade esto a exclude_patterns.json:  "{clave}"')
        else:
            lineas.append("No encuentro una clave segura que proponer (podría "
                          "excluir algún otro movimiento tuyo); añádelo tú a mano "
                          "con lo que ves arriba.")
        propuestas.append(ExclusionPropuesta(
            "cuenta", clave, segura,
            sorted({todo.at[i, "descripcion"] for i in falta_cuenta})[:3]))
    if falta_tarjeta:
        suma = sum(todo.at[i, "importe"] for i in falta_tarjeta)
        lineas.append(f"El mismo pago aparece también en el extracto de la tarjeta, "
                      f"como un abono: sin excluirlo, cuenta como un ingreso que no "
                      f"lo es ({euros(suma)} en total):")
        for i in sorted(falta_tarjeta, key=lambda i: todo.at[i, "fecha"])[:3]:
            fila = todo.loc[i]
            lineas.append(f"· {fila['fecha']:%d/%m/%Y}: {euros(fila['importe'], signo=True)}"
                          f"  («{fila['descripcion']}»)")
        clave, segura = clave_de(lado_tarjeta)
        if segura:
            lineas.append(f'Añade también:  "{clave}"' if falta_cuenta else
                          f'Añade esto a exclude_patterns.json:  "{clave}"')
        else:
            lineas.append("Para esta no encuentro una clave segura; añádela tú a "
                          "mano con lo que ves arriba.")
        propuestas.append(ExclusionPropuesta(
            "tarjeta", clave, segura,
            sorted({todo.at[i, "descripcion"] for i in falta_tarjeta})[:3]))

    if not falta_cuenta:
        titulo = "El pago de la tarjeta está contando como un ingreso"
    elif excluidor.patrones:
        # hay patrones, pero no cubren lo que se ha encontrado
        titulo = "Puede que la tarjeta se esté contando dos veces"
    avisar(titulo, lineas + pista)
    return RecibosTarjeta(True, descripciones, propuestas)


# ========= CARGOS QUE SE REPITEN (suscripciones, cuotas, seguros) =========
# Un cargo pequeño y olvidado ("solo son 8,99 €") pesa de verdad cuando se ve
# lo que suma al año. Este informe solo dice eso: qué se repite y cuánto suma.
# NUNCA opina ("deberías cancelarlo"): un alquiler o un gimnasio que sí se usa
# salen igual que una suscripción olvidada, y la decisión es de quien lo lee.
# Opinar es justo lo que diferencia a una app de "consejos" de un Excel propio.
#
# Mismo principio que A1 y A2: mejor callarse que equivocarse. Por eso se
# exige a la vez regularidad en las fechas y estabilidad en el importe, y
# un grupo que no cumple las dos cosas no sale, aunque "parezca" recurrente.
_CADENCIAS = (
    # (nombre, días mínimos y máximos entre dos cargos, cargos mínimos, veces al año)
    # El margen de días cubre que el banco pase un recibo del día 1 al lunes
    # siguiente si cae en fin de semana, y los meses de 28 a 31 días.
    ("mensual", 26, 35, 3, 12),
    # Anual con solo DOS cargos: exigir tres obligaría a tener tres años de
    # histórico para ver un seguro, que es justo el caso que más interesa.
    ("anual", 350, 380, 2, 1),
)
_TOLERANCIA_RELATIVA_RECURRENTE = 0.15   # una suscripción sube de precio, un
_TOLERANCIA_ABSOLUTA_RECURRENTE = 3.0    # seguro varía la prima: lo que sea
                                         # mayor de los dos, de cargo a cargo.
_MAX_RECURRENTES = 10


def _clave_recurrente(descripcion):
    """La descripción sin lo que cambia de un cargo a otro (la referencia del
    recibo, la fecha que meten algunos bancos en el concepto). Se agrupa por
    el texto ENTERO que queda, no por una palabra suelta como en A1: así
    «PAYPAL *NETFLIX» y «PAYPAL *SPOTIFY» no acaban en el mismo grupo."""
    return " ".join(_sin_numeros(normalizar(descripcion)).split())


def _importe_parecido(a, b):
    margen = max(_TOLERANCIA_ABSOLUTA_RECURRENTE,
                 _TOLERANCIA_RELATIVA_RECURRENTE * max(abs(a), abs(b)))
    return abs(a - b) <= margen


def _serie_recurrente(cargos, ultima_fecha):
    """
    Si los cargos de un grupo (ordenados por fecha) terminan en una serie
    regular, devuelve (cadencia, veces_al_año, serie); si no, None.

    Se recorre HACIA ATRÁS desde el último cargo mientras intervalo e importe
    sigan cuadrando: lo que importa es lo que se paga hoy, así que un precio
    antiguo muy distinto, o un hueco de hace un año, no tiran abajo una
    suscripción que lleva meses regular. Y la serie tiene que seguir viva:
    si el último cargo queda más lejos de la fecha del histórico de lo que
    toca, eso ya se dio de baja y no hay nada que contar.
    """
    fechas = list(cargos["fecha"])
    importes = list(cargos["importe"])
    if len(fechas) < 2:
        return None
    ultimo_intervalo = (fechas[-1] - fechas[-2]).days
    for nombre, minimo, maximo, cargos_minimos, veces in _CADENCIAS:
        if not minimo <= ultimo_intervalo <= maximo:
            continue
        if (ultima_fecha - fechas[-1]).days > maximo:
            return None
        inicio = len(fechas) - 1
        while (inicio > 0
               and minimo <= (fechas[inicio] - fechas[inicio - 1]).days <= maximo
               and _importe_parecido(importes[inicio], importes[inicio - 1])):
            inicio -= 1
        serie = cargos.iloc[inicio:]
        return (nombre, veces, serie) if len(serie) >= cargos_minimos else None
    return None


def informe_recurrentes(df, categorias_gasto):
    """
    Cargos que se repiten con regularidad: cada mes o cada año, mismo
    concepto y un importe parecido. Solo gastos, y solo de las categorías de
    gasto: un traspaso mensual a tu cuenta de ahorro (neutra) también es
    regular, pero no es algo que se "pague".

    Ordenado por lo que suma al año al importe del ÚLTIMO cargo, que es el
    precio de hoy, no por la cuota suelta: 8,99 €/mes se ve como 107,88 €/año.
    """
    gastos = df[(df["importe"] < 0) & df["categoria"].isin(categorias_gasto)]
    if gastos.empty:
        return
    ultima_fecha = df["fecha"].max()

    encontrados = []
    for _, cargos in gastos.groupby(gastos["descripcion"].map(_clave_recurrente)):
        resultado = _serie_recurrente(cargos.sort_values("fecha"), ultima_fecha)
        if resultado is None:
            continue
        cadencia, veces, serie = resultado
        ultimo = serie.iloc[-1]
        encontrados.append((-ultimo["importe"] * veces, cadencia,
                            -ultimo["importe"], serie["fecha"].iloc[0], ultimo))
    if not encontrados:
        return

    encontrados.sort(key=lambda e: -e[0])
    total = sum(e[0] for e in encontrados)
    cuantos = ("1 cargo que se repite" if len(encontrados) == 1
               else f"{len(encontrados)} cargos que se repiten")
    seccion("Cargos que se repiten")
    print(f"🔁 {cuantos}; al importe de hoy suma{'n' if len(encontrados) > 1 else ''} "
          f"{euros(total)} al año:")
    if len(encontrados) > _MAX_RECURRENTES:
        print(gris(f"   (se muestran los {_MAX_RECURRENTES} que más suman)"))
    print()
    for al_año, cadencia, importe, desde, ultimo in encontrados[:_MAX_RECURRENTES]:
        print(f"   {euros(al_año, ancho=10)}/año  ·  {euros(importe)} {cadencia}  ·  "
              f"desde {desde:%m/%Y}  ·  {ultimo['categoria']}")
        print(f"      {ultimo['descripcion']}")


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
    # la cabecera primero: la versión es lo primero que hace falta saber si
    # algo va mal, y lo que arrancar() tenga que contar va debajo
    titulo = f"Movimientos bancarios · versión {rutas.version()}"
    print(negrita(titulo))
    print(negrita("═" * len(titulo)) + "\n")

    arrancar()

    print(f"Reglas: {clasificador.n_propias} tuyas + {clasificador.n_base} de la "
          f"base.")
    if clasificador.desactivadas:
        print(f"   Apagadas con null: {', '.join(clasificador.desactivadas)}")
    if clasificador.descartadas_de_base:
        descartadas = clasificador.descartadas_de_base
        print(f"   {len(descartadas)} reglas de la base descartadas: apuntan a "
              f"categorías que no tienes en categorias.json.")
        # sin los nombres no había forma de saber qué comercios se quedaban
        # sin regla (p. ej. las tiendas de animales al renombrar «Mascotas»)
        muestra = ", ".join(descartadas[:8])
        resto = f" y {len(descartadas) - 8} más" if len(descartadas) > 8 else ""
        print(gris(f"   ({muestra}{resto})"))

    avisos = catalogo.validar(clasificador)
    if avisos:
        avisar("Las categorías de rules.json y categorias.json no cuadran",
               [f"· {a}" for a in avisos]
               + ["Sigo adelante, pero revísalo o el resumen no cuadrará."])

    en_copia = comprobar_abiertos([rutas.HISTORICO, rutas.LIMPIOS, rutas.EXCLUIDOS])

    seccion(f"Leyendo {rutas.relativa(rutas.ENTRADA)}/")
    nuevos = leer_entrada()
    if not nuevos:
        print(gris("   (no hay ficheros nuevos)"))

    hist.comprobar_version(rutas.HISTORICO, rutas.version())
    previo = hist.cargar(rutas.HISTORICO)
    if not previo.empty:
        print(f"\n📚 Histórico previo: {len(previo)} movimientos.")
    elif not nuevos:
        # «está vacía» cuando había ficheros que no se han podido leer
        # mandaba a buscar el problema donde no estaba
        carpeta = rutas.relativa(rutas.ENTRADA)
        hay_algo = rutas.ENTRADA.is_dir() and any(
            not _es_temporal(f) and (rutas.ENTRADA / f).is_file()
            for f in os.listdir(rutas.ENTRADA))
        if hay_algo:
            raise FileNotFoundError(
                f"No hay histórico y no he podido leer ningún extracto de "
                f"'{carpeta}/'.\n"
                f"   El motivo de cada fichero está en los avisos de arriba.")
        raise FileNotFoundError(
            f"No hay histórico y la carpeta '{carpeta}/' está vacía.\n"
            f"   Suelta ahí los ficheros que te descargues del banco, con el nombre\n"
            f"   y la extensión que traigan, y vuelve a ejecutar.")

    asignadas = asignar_cuentas_pendientes(previo)
    if asignadas:
        print(f"🏦 {asignadas} movimientos del histórico, asignados a su cuenta "
              f"según {rutas.relativa(rutas.CUENTAS)}.")
        antes = len(previo)
        previo = hist.quitar_duplicados(previo)
        if len(previo) < antes:
            print(f"🧹 {antes - len(previo)} estaban repetidos (se habían "
                  f"duplicado al declarar las cuentas): quitados.")

    nuevos = apartar_copias_sin_cuenta(previo, nuevos)
    sin_declarar, fundidos = avisar_cuentas_sin_declarar(nuevos)

    crudos, anadidos, repetidos = hist.fusionar(previo, nuevos)
    if repetidos:
        # «ya estaban» cubre los dos casos: en el histórico (volver a
        # ejecutar con los mismos ficheros) o en otro extracto que se solapa.
        # Decir solo «se solapan» confundía al repetir una ejecución.
        print(f"🔁 {repetidos} movimientos ya estaban (en el histórico o en otro "
              f"extracto); no se cuentan dos veces.")
        # «ya estaban» sonaba a todo en orden justo cuando se estaban
        # perdiendo cargos de dos tarjetas distintas
        if fundidos:
            print(amarillo(f"   ⚠️  De ellos, {fundidos} pueden ser cargos distintos "
                           f"de dos tarjetas o cuentas: mira los avisos del final."))
    if anadidos:
        print(f"➕ {anadidos} movimientos nuevos.")
    elif nuevos:
        print("➕ Ningún movimiento nuevo: ya estaba todo en el histórico.")

    if crudos.empty:
        print("\n" + rojo("❌ No hay ningún movimiento que procesar."))
        return None, None

    validas = set(catalogo.todas) | {hist.MARCA_EXCLUIDO}
    todo = clasificar(crudos, validas)

    manuales = todo.loc[todo["categoria_manual"].ne(""), "categoria_manual"]
    invalidas = sorted(set(manuales) - validas)
    if invalidas:
        avisar(f"Correcciones manuales con una categoría que no existe: "
               f"{', '.join(invalidas)}", [
                   f"Tiene que ser una de categorias.json, o "
                   f"«{hist.MARCA_EXCLUIDO}» para sacarla de los totales.",
                   "Las he IGNORADO y he dejado que manden las reglas, para que "
                   "no desaparezcan de los totales sin avisar. Corrige la "
                   "columna categoria_manual y vuelve a ejecutar."])
    df = todo[~todo["excluido"]].reset_index(drop=True)      # lo que cuenta
    excluidos = todo[todo["excluido"]].reset_index(drop=True)

    # --- salidas ---
    # el histórico guarda TODO (incluido lo excluido); el resumen y el fichero
    # que pegas en Excel, solo lo que cuenta.
    seccion("Resultado")
    saldos_por_cuenta = calcular_saldo_inicial(todo)
    saldo_inicial = sum(saldos_por_cuenta.values())
    sin_saldo = cuentas_sin_saldo(todo)
    # el Acumulado solo es «tu saldo» si se conoce el de partida de TODAS
    # las cuentas; si falta alguno (o solo hay tarjetas), es la variación
    # desde el primer movimiento, y así se tiene que llamar
    saldo_real = not sin_saldo and (todo["tipo"] == "cuenta").any()
    # la cuenta entera, excluidos incluidos: el banco sí los aplicó, y el
    # Acumulado es lo que hay en la cuenta, no lo que suma el Balance
    resumen = hist.construir_resumen(df, catalogo, saldo_inicial,
                                     todo[todo["tipo"] == "cuenta"])
    por_cuenta = hist.construir_por_cuenta(df, catalogo, todo[todo["tipo"] == "cuenta"],
                                           saldos_por_cuenta, sin_saldo)
    # la copia de seguridad solo si se va a tocar el de verdad: si el
    # resultado va a una copia, el histórico queda como estaba
    copia_historico = None
    ajenas = hist.hojas_ajenas(rutas.HISTORICO)
    if os.path.exists(rutas.HISTORICO) and rutas.HISTORICO not in en_copia:
        # Sin nada nuevo desde la última copia, no se hace otra: antes cada
        # ejecución gastaba una, y con diez seguidas se perdía la última
        # que de verdad era distinta.
        ultima = sync.ultima_copia(rutas.HISTORICO)
        # (con hojas propias sí: el aviso dice que están en la copia)
        if ultima and not ajenas and hist.mismos_movimientos(rutas.HISTORICO, ultima):
            copia_historico = ultima
        else:
            copia_historico = sync.copia_de_seguridad(rutas.HISTORICO,
                                                      cfg_sync.copias_de_seguridad)
    copiados = {}
    historico_escrito = guardar_o_copiar(
        rutas.HISTORICO,
        lambda r: hist.guardar(r, todo[COLUMNAS_HISTORICO], resumen, catalogo,
                               version=rutas.version(), saldo_real=saldo_real,
                               por_cuenta=por_cuenta),
        en_copia, copiados)
    limpios_escrito = guardar_o_copiar(
        rutas.LIMPIOS,
        lambda r: guardar_excel(df[COLUMNAS_BASE + ["origen", "regla", "cuenta"]], r),
        en_copia, copiados)
    if not excluidos.empty:
        guardar_o_copiar(
            rutas.EXCLUIDOS,
            lambda r: guardar_excel(excluidos[["fecha", "descripcion", "importe",
                                               "tipo", "origen", "regla"]], r),
            en_copia, copiados)

    # en una copia no es un éxito del todo: el histórico de verdad no se ha
    # actualizado, y un ✅ verde lo hacía pasar por bueno
    pintar, marca = ((verde, "✅") if historico_escrito == rutas.HISTORICO
                     else (amarillo, "⚠️ "))
    hojas = [hist.HOJA_RESUMEN] + ([hist.HOJA_CUENTAS] if not por_cuenta.empty
                                   else []) + [hist.HOJA_MOVIMIENTOS]
    print(pintar(f"{marca} {rutas.relativa(historico_escrito)}  ·  hojas "
                 f"{', '.join(hojas[:-1])} y {hojas[-1]}"))
    print(f"   {rutas.relativa(limpios_escrito)}  " + gris("·  lo que pegas en A-G"))
    avisar_copias(copiados)
    if ajenas and historico_escrito == rutas.HISTORICO:
        cuales = ", ".join(f"«{h}»" for h in ajenas)
        avisar(f"{rutas.relativa(rutas.HISTORICO)} se regenera entero: {cuales} "
               f"ya no está", [
                   f"Lo que añadas a mano al histórico (salvo la columna "
                   f"categoria_manual) no se conserva de una ejecución a otra. "
                   f"Está en la copia {rutas.relativa(copia_historico)}.",
                   "Para tus propios cálculos, usa un libro aparte que tire de "
                   "este, o la sincronización (ajustes/sincronizar.json)."])

    # --- volcado directo en el fichero de contabilidad ---
    if cfg_sync.activa:
        try:
            a_volcar = todo if cfg_sync.incluir_excluidos else df
            copia, filas = sync.escribir(cfg_sync, a_volcar[COLUMNAS_BASE])
            destino = f"📗 {cfg_sync.archivo} · hoja {cfg_sync.hoja}: "
            if copia:
                if cfg_sync.modo == "añadir":
                    que = ("1 movimiento añadido debajo" if filas == 1
                           else f"{filas} movimientos añadidos debajo")
                else:
                    que = f"{filas} filas escritas"
                print(verde(f"{destino}{que}"))
                print(gris(f"   copia de seguridad en {rutas.relativa(copia)}"))
            elif cfg_sync.modo == "añadir":
                print(verde(f"{destino}ningún movimiento nuevo que añadir, "
                            f"no lo he tocado"))
            else:
                print(verde(f"{destino}ya estaba al día ({filas} filas), no lo "
                            f"he tocado"))
        except Exception as e:
            print(f"📗 {cfg_sync.archivo}: " + rojo("✗ no sincronizado")
                  + gris(" (el motivo, en los avisos del final)"))
            avisar(f"No he sincronizado con {cfg_sync.archivo}",
                   str(e).splitlines()
                   + ["Tu fichero de contabilidad NO se ha tocado. Usa "
                      "movimientos_limpios.xlsx mientras tanto."])

    print(f"\n   {len(df)} movimientos · {len(excluidos)} excluidos")
    if not df.empty:
        print(f"   del {df['fecha'].min():%d/%m/%Y} al {df['fecha'].max():%d/%m/%Y}"
              f"  ({len(resumen)} {'mes' if len(resumen) == 1 else 'meses'})")

    ajustadas = (df["mes"] != df["mes_ajustado"]).sum()
    if ajustadas:
        print(f"   {ajustadas} con el mes contable ajustado"
              f"  (el resumen agrupa por '{catalogo.columna_mes}')")

    # ruido de coma flotante aparte: solo cuenta lo que de verdad se detectó
    detectados = {c: s for c, s in saldos_por_cuenta.items() if abs(s) >= 0.005}
    if len(detectados) == 1:
        print(f"\n💰 Saldo inicial detectado: {euros(next(iter(detectados.values())))}")
        print(gris("   Lo que tenía tu cuenta antes del primer movimiento que hay. "
                   "El Acumulado\n   del resumen parte de ahí, no de 0."))
    elif detectados:
        print(f"\n💰 Saldo inicial detectado en {len(detectados)} cuentas "
              f"(ver ajustes/cuentas.json); el Acumulado del resumen parte "
              f"de la suma:")
        for id_cuenta, saldo in sorted(detectados.items()):
            print(f"   {id_cuenta or '(sin identificar)'}: {euros(saldo)}")
    # un saldo de partida negativo casi siempre es un fichero SIN saldo (un
    # export antiguo) delante del primero que lo trae: se calcula hacia
    # atrás a través de él, y si ese fichero no es de la misma cuenta, o le
    # faltan movimientos, el número sale raro sin que nada lo explique
    if any(v < 0 for v in detectados.values()):
        print(gris("   Es negativo. Si tu cuenta no estaba en números rojos, "
                   "algún fichero sin columna de saldo\n   va antes del primero "
                   "que la trae, y el cálculo hacia atrás lo arrastra: el saldo "
                   "del\n   final sí es el del banco."))
    if sin_saldo:
        cuales = ("de tu cuenta" if sin_saldo == [""] else
                  "de " + ", ".join(c or "(sin identificar)" for c in sin_saldo))
        avisar(f"No sé el saldo {cuales}: el Acumulado no es tu saldo", [
            "El extracto no trae columna de saldo (o todos sus días tienen "
            "varios movimientos y no se puede deducir). Así que el Acumulado "
            "empieza en 0: es lo que ha variado la cuenta desde el primer "
            "movimiento, no el dinero que tienes.",
            "Si tu banco deja descargar el extracto con la columna Saldo, "
            "úsalo y se arregla solo."])

    # si se están contando dos veces los gastos de la tarjeta, que se sepa
    # ANTES de fiarse de las cifras de abajo (el detalle, con los avisos)
    recibos = detectar_recibo_tarjeta(todo, sin_declarar)
    doble_tarjeta = recibos.aviso
    # si lo único que falta es el abono en la tarjeta, lo que se infla son
    # los ingresos, no los gastos
    solo_abono = bool(recibos.propuestas) and all(
        p.lado == "tarjeta" for p in recibos.propuestas)

    # orden_resumen puede haber quitado cualquiera de estas columnas del
    # resumen: se enseña solo lo que haya. Pedirlas a pelo rompía aquí,
    # DESPUÉS de guardar, y se saltaba el informe de sin clasificar de abajo.
    if not resumen.empty:
        ult = resumen.iloc[-1]

        # las cifras con signo, verdes o rojas según el signo: un «total» en
        # verde fijo pintaría de buena noticia un mes en negativo
        def cifra(valor, signo=False):
            texto = euros(valor, signo=signo)
            if not signo:
                return negrita(texto)
            return verde(texto) if valor >= 0 else rojo(texto)

        partes = [f"{texto} {cifra(ult[col], signo)}"
                  for col, texto, signo in (("Total Gastos", "gastos", False),
                                            ("Ingresos", "ingresos", False),
                                            ("Balance", "balance", True))
                  if col in resumen.columns]
        mes = f" ({ult['Mes']})" if "Mes" in resumen.columns else ""
        if partes:
            print(f"\n   Último mes{mes}:  " + " · ".join(partes))
        if "Acumulado" in resumen.columns:
            etiqueta = ("saldo al cierre del mes" if saldo_real
                        else "desde el primer movimiento")
            print(f"   Acumulado ({etiqueta}): "
                  f"{cifra(ult['Acumulado'], signo=True)}")
        if doble_tarjeta and solo_abono:
            print("\n" + amarillo("   ⚠️  Ojo: el pago de la tarjeta está contando "
                                  "como un ingreso. Mira los avisos del final."))
        elif doble_tarjeta:
            print("\n" + amarillo("   ⚠️  Ojo: puede que los gastos de la tarjeta "
                                  "se estén contando dos veces. Mira los avisos "
                                  "del final."))

    informar_cuadre(comprobar_cuadre(todo))

    informe_recurrentes(df, catalogo.gastos)
    propuestas, recibo_en_grupo = informe_sin_clasificar(
        df, ignorar=recibos.descripciones,
        tarjeta_sin_excluir=doble_tarjeta and not recibos.descripciones)
    # los avisos, lo último antes de salir: juntos, contados y separados de
    # lo demás, que es lo que se lee cuando la ejecución termina
    mostrar_avisos()
    # lo que el asistente del menú final puede escribir por la persona
    # si el detector no lo encontró, pero un grupo de lo sin clasificar
    # lo parece, su clave es la mejor pista que hay
    exclusiones = list(recibos.propuestas)
    if (doble_tarjeta and recibo_en_grupo
            and not any(p.lado == "cuenta" for p in exclusiones)):
        clave, ejemplo = recibo_en_grupo
        exclusiones.insert(0, ExclusionPropuesta("cuenta", clave, False, [ejemplo]))
    movimientos = todo[["fecha", "descripcion", "importe", "tipo"]]
    pendientes = Pendientes(propuestas, doble_tarjeta, exclusiones,
                            list(movimientos.itertuples(index=False, name=None)))
    return historico_escrito, pendientes


# ========= RUN =========
if __name__ == "__main__":
    while True:
        try:
            escrito, pendientes = main()
        except Exception as e:
            # los avisos que ya hubiera pueden explicar el error: van antes,
            # para que el ❌ sea lo último que se ve
            mostrar_avisos()
            print("\n" + rojo(f"❌ {e}"))
            # tras un error también: lo habitual es arreglarlo (una coma en
            # un JSON, un extracto que faltaba) y querer probar otra vez
            if (_interactiva() and _esperar(
                    "\nPulsa Intro para cerrar, o escribe R y pulsa Intro para "
                    "ejecutar de nuevo... ").lower() == "r"):
                _preparar_otra_vuelta()
                continue
            sys.exit(CODIGO_ERROR_EXPLICADO)
        if menu_final(escrito, pendientes) != OTRA_VEZ:
            break
        _preparar_otra_vuelta()
