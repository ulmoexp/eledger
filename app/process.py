"""
process.py — Unifica, limpia, clasifica y acumula movimientos de cuenta y tarjetas.

Uso normal:
    1. suelta los ficheros del banco en la carpeta  entrada/
    2. doble clic en  ejecutar.bat  (Windows)  o  ejecutar.command  (Mac)
       o bien, desde la terminal:  python app/process.py

Todo el procesamiento es local; no se conecta a internet.
"""

import difflib
import json
import os
import re
import subprocess
import sys
import textwrap

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
from reglas import Catalogo, Clasificador, Excluidor, IdentificadorCuentas, compilar, normalizar

# La consola de Windows usa cp1252 por defecto y revienta con acentos y símbolos.
try:
    sys.stdout.reconfigure(encoding="utf-8")
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
    nada, o se quedaría esperando para siempre."""
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


def menu_final():
    """
    Al terminar bien, la ventana se queda abierta hasta que se decida qué
    hacer. Con el .exe no hay lanzador que haga una pausa, y la ventana se
    cerraba sola antes de poder leer nada.
    """
    if not _interactiva():
        return
    opciones = {}
    if rutas.HISTORICO.exists():
        opciones["1"] = (f"Abrir el histórico  ({rutas.relativa(rutas.HISTORICO)})",
                         rutas.HISTORICO)
        opciones["2"] = (f"Abrir la carpeta  {rutas.relativa(rutas.DATOS)}/",
                         rutas.DATOS)
    if not opciones:
        _esperar("\nPulsa Intro para cerrar...")
        return

    seccion("¿Y ahora?")
    for tecla, (texto, _) in opciones.items():
        print(f"   {titular(tecla)}      {texto}")
    print(f"   {titular('Intro')}  Cerrar")
    while True:
        eleccion = _esperar("\n   > ")
        if not eleccion:
            return
        if eleccion not in opciones:
            print("   Escribe 1 o 2, o pulsa Intro para cerrar.")
            continue
        try:
            _abrir(opciones[eleccion][1])
            print("   Abierto. Puedes elegir otra opción, o Intro para cerrar.")
        except Exception as e:
            print(rojo(f"   No he podido abrirlo ({e}). Está en "
                       f"{opciones[eleccion][1]}"))


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
        categorias_validas=set(catalogo.todas))
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
            dfs.append(df)
        except Exception as e:
            print(f"   · {nombre}: " + rojo("✗ no se ha podido leer")
                  + gris(" (el motivo, en los avisos del final)"))
            avisar(f"No he podido leer {nombre}", str(e).splitlines())
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
    saldo_banco, saldo_calculado, saltos)}, donde saltos es la lista de
    (fecha, diferencia) en que el cálculo deja de coincidir con el banco.
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
        resultado[id_cuenta] = (ultima_fecha, saldo_banco, calculado, saltos)
    return resultado


def informar_cuadre(cuadre):
    """Una línea si cuadra; si no, en qué fechas se rompe y por cuánto."""
    if not cuadre:
        return
    varias = len(cuadre) > 1
    for id_cuenta, (fecha, banco, calculado, saltos) in sorted(cuadre.items()):
        nombre = f" ({id_cuenta or 'sin identificar'})" if varias else ""
        if not saltos and abs(banco - calculado) < _TOLERANCIA_CUADRE:
            print(verde(f"   🧮 Cuadra con el banco{nombre}: {calculado:,.2f} € "
                        f"a {fecha:%d/%m/%Y}, igual que el extracto."))
            continue

        print(amarillo(f"   ⚠️  No cuadra con el banco{nombre}: el extracto dice "
                       f"{banco:,.2f} € a {fecha:%d/%m/%Y}\n       y el "
                       f"cálculo da {calculado:,.2f} €. Mira los avisos del final."))
        lineas = [f"Diferencia final: {banco - calculado:+,.2f} € "
                  f"(saldo del banco menos el calculado). Aparece en:"]
        for f, dif in saltos[:_MAX_SALTOS_MOSTRADOS]:
            lineas.append(f"· {f:%d/%m/%Y}: {dif:+,.2f} €")
        if len(saltos) > _MAX_SALTOS_MOSTRADOS:
            lineas.append(f"· ... y {len(saltos) - _MAX_SALTOS_MOSTRADOS} más")
        lineas += [
            "Entre la fecha anterior con saldo y esa, falta un movimiento de "
            "ese importe (o sobra, si es negativo). Lo normal es un hueco "
            "entre dos extractos: descarga el que cubra esas fechas y vuelve "
            "a ejecutar.",
            "Hasta entonces, el Acumulado del resumen arrastra esa diferencia."]
        avisar(f"El saldo calculado no cuadra con el del banco{nombre}", lineas)


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

    seccion("Sin clasificar")
    print(f"ℹ️  {len(sin_regla)} movimientos sin ninguna regla, en "
          f"{len(grupos)} grupos por palabra común:")
    if len(grupos) > _MAX_GRUPOS_SIN_CLASIFICAR:
        print(gris(f"   (se muestran los {_MAX_GRUPOS_SIN_CLASIFICAR} de más importe)"))
    print()

    for palabra, filas in mostrados:
        total = -filas["importe"].sum()
        ejemplo = filas["descripcion"].mode().iloc[0]
        print(f"   {total:>10,.2f} €  ·  {len(filas):>3} mov.  ·  {palabra}")
        print(gris(f"      ej: {ejemplo}"))
        sugerida = _sugerir_regla(filas, palabra, normalizados)
        if sugerida:
            print(f'      añade a rules.json:  "{sugerida}": '
                  f'"{_PLACEHOLDER_CATEGORIA}"')
        else:
            print(gris("      (ninguna palabra de este grupo es segura de sugerir "
                       "sin pisar otra regla; revísalo a mano)"))
        print()


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


def _meses_tarjeta(todo):
    """(mes -> importe neto) de cada mes con movimientos de tarjeta. Neto y
    con signo: lo que de verdad debe la tarjeta ese mes, ya restadas las
    devoluciones que haya habido dentro del propio mes de tarjeta."""
    tarjeta = todo[todo["tipo"] == "tarjeta"]
    return tarjeta.groupby("mes")["importe"].sum()


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


def detectar_recibo_tarjeta(todo):
    """Hito A2 del roadmap. Solo actúa si exclude_patterns.json está vacío:
    con cualquier patrón ya puesto se asume resuelto, sea o no el de la
    tarjeta (así lo pide el roadmap, y evitar el aviso es tan fácil como
    excluir el recibo, que es justo lo que se está pidiendo).

    No imprime nada: deja el aviso para el final, con los demás, y devuelve
    si lo ha dejado, para poder señalarlo junto a los totales."""
    if excluidor.patrones:
        return False
    tarjeta_por_mes = _meses_tarjeta(todo)
    if tarjeta_por_mes.empty:
        return False

    cuenta = todo[todo["tipo"] == "cuenta"]
    candidatos = {}
    for mes, importe in tarjeta_por_mes.items():
        fila = _candidato_liquidacion(cuenta, mes, importe)
        if fila is not None:
            candidatos[mes] = fila

    titulo = ("Tienes movimientos de tarjeta y ningún patrón en "
              "exclude_patterns.json")
    if not candidatos:
        avisar(titulo, [
            "Si tu cuenta paga la tarjeta con un recibo, cada gasto se está "
            "contando DOS VECES y no lo he sabido encontrar solo.",
            "Revísalo a mano: LEEME.txt explica cómo excluirlo."])
        return True

    lineas = ["Si no se excluye, cada gasto de la tarjeta cuenta DOS VECES. "
              "Esto parece el recibo:"]
    for mes, fila in sorted(candidatos.items()):
        lineas.append(f"· {mes}: la tarjeta suma {-tarjeta_por_mes[mes]:,.2f} € y "
                      f"tu cuenta tiene un cargo de {-fila['importe']:,.2f} € el "
                      f"{fila['fecha']:%d/%m/%Y}  («{fila['descripcion']}»)")

    ya_usadas = {f.name for f in candidatos.values()}
    otras = [normalizar(d) for i, d in cuenta["descripcion"].items()
            if i not in ya_usadas]

    clave = _clave_liquidacion([f["descripcion"] for f in candidatos.values()])
    segura = False
    if len(clave) >= _LONGITUD_MINIMA_CLAVE_RECIBO:
        patron, _ = compilar(clave)
        segura = not any(patron.search(d) for d in otras)

    if segura:
        lineas.append(f'Añade esto a exclude_patterns.json:  "{clave}"')
    else:
        lineas.append("No encuentro una clave segura que proponer (podría "
                      "excluir algún otro movimiento tuyo); añádelo tú a mano "
                      "con lo que ves arriba.")
    avisar(titulo, lineas)
    return True


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
          f"{total:,.2f} € al año:")
    if len(encontrados) > _MAX_RECURRENTES:
        print(gris(f"   (se muestran los {_MAX_RECURRENTES} que más suman)"))
    print()
    for al_año, cadencia, importe, desde, ultimo in encontrados[:_MAX_RECURRENTES]:
        print(f"   {al_año:>10,.2f} €/año  ·  {importe:,.2f} € {cadencia}  ·  "
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
        print(f"   {len(clasificador.descartadas_de_base)} reglas de la base "
              f"descartadas: apuntan a categorías que no tienes en "
              f"categorias.json.")

    avisos = catalogo.validar(clasificador)
    if avisos:
        avisar("Las categorías de rules.json y categorias.json no cuadran",
               [f"· {a}" for a in avisos]
               + ["Sigo adelante, pero revísalo o el resumen no cuadrará."])

    seccion(f"Leyendo {rutas.relativa(rutas.ENTRADA)}/")
    nuevos = leer_entrada()
    if not nuevos:
        print(gris("   (no hay ficheros nuevos)"))

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
        print("\n" + rojo("❌ No hay ningún movimiento que procesar."))
        return

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
    # la cuenta entera, excluidos incluidos: el banco sí los aplicó, y el
    # Acumulado es lo que hay en la cuenta, no lo que suma el Balance
    resumen = hist.construir_resumen(df, catalogo, saldo_inicial,
                                     todo[todo["tipo"] == "cuenta"])
    if os.path.exists(rutas.HISTORICO):
        sync.copia_de_seguridad(rutas.HISTORICO, cfg_sync.copias_de_seguridad)
    hist.guardar(rutas.HISTORICO, todo[COLUMNAS_HISTORICO], resumen, catalogo,
                 version=rutas.version())
    guardar_excel(df[COLUMNAS_BASE + ["origen", "regla"]], rutas.LIMPIOS)
    if not excluidos.empty:
        guardar_excel(excluidos[["fecha", "descripcion", "importe", "tipo",
                                 "origen", "regla"]], rutas.EXCLUIDOS)

    print(verde(f"✅ {rutas.relativa(rutas.HISTORICO)}  ·  hojas {hist.HOJA_RESUMEN} y "
                f"{hist.HOJA_MOVIMIENTOS}"))
    print(f"   {rutas.relativa(rutas.LIMPIOS)}  " + gris("·  lo que pegas en A-G"))

    # --- volcado directo en el fichero de contabilidad ---
    if cfg_sync.activa:
        try:
            a_volcar = todo if cfg_sync.incluir_excluidos else df
            copia, filas = sync.escribir(cfg_sync, a_volcar[COLUMNAS_BASE])
            print(verde(f"📗 {cfg_sync.archivo} · hoja {cfg_sync.hoja}: "
                        f"{filas} filas escritas"))
            print(gris(f"   copia de seguridad en {copia}"))
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
              f"  ({len(resumen)} meses)")

    ajustadas = (df["mes"] != df["mes_ajustado"]).sum()
    if ajustadas:
        print(f"   {ajustadas} con el mes contable ajustado"
              f"  (el resumen agrupa por '{catalogo.columna_mes}')")

    # ruido de coma flotante aparte: solo cuenta lo que de verdad se detectó
    detectados = {c: s for c, s in saldos_por_cuenta.items() if abs(s) >= 0.005}
    if len(detectados) == 1:
        print(f"\n💰 Saldo inicial detectado: {next(iter(detectados.values())):,.2f} €")
        print(gris("   Lo que tenía tu cuenta antes del primer movimiento que hay. "
                   "El Acumulado\n   del resumen parte de ahí, no de 0."))
    elif detectados:
        print(f"\n💰 Saldo inicial detectado en {len(detectados)} cuentas "
              f"(ver ajustes/cuentas.json); el Acumulado del resumen parte "
              f"de la suma:")
        for id_cuenta, saldo in sorted(detectados.items()):
            print(f"   {id_cuenta or '(sin identificar)'}: {saldo:,.2f} €")

    # si se están contando dos veces los gastos de la tarjeta, que se sepa
    # ANTES de fiarse de las cifras de abajo (el detalle, con los avisos)
    doble_tarjeta = detectar_recibo_tarjeta(todo)

    # orden_resumen puede haber quitado cualquiera de estas columnas del
    # resumen: se enseña solo lo que haya. Pedirlas a pelo rompía aquí,
    # DESPUÉS de guardar, y se saltaba el informe de sin clasificar de abajo.
    if not resumen.empty:
        ult = resumen.iloc[-1]

        # las cifras con signo, verdes o rojas según el signo: un «total» en
        # verde fijo pintaría de buena noticia un mes en negativo
        def cifra(valor, formato):
            texto = f"{valor:{formato}} €"
            if "+" not in formato:
                return negrita(texto)
            return verde(texto) if valor >= 0 else rojo(texto)

        partes = [f"{texto} {cifra(ult[col], formato)}"
                  for col, texto, formato in (("Total Gastos", "gastos", ",.2f"),
                                              ("Ingresos", "ingresos", ",.2f"),
                                              ("Balance", "balance", "+,.2f"))
                  if col in resumen.columns]
        mes = f" ({ult['Mes']})" if "Mes" in resumen.columns else ""
        if partes:
            print(f"\n   Último mes{mes}:  " + " · ".join(partes))
        if "Acumulado" in resumen.columns:
            print(f"   Acumulado (saldo al cierre del mes): "
                  f"{cifra(ult['Acumulado'], '+,.2f')}")
        if doble_tarjeta:
            print("\n" + amarillo("   ⚠️  Ojo: puede que los gastos de la tarjeta "
                                  "se estén contando dos veces. Mira los avisos "
                                  "del final."))

    informar_cuadre(comprobar_cuadre(todo))

    informe_recurrentes(df, catalogo.gastos)
    informe_sin_clasificar(df)
    # los avisos, lo último antes de salir: juntos, contados y separados de
    # lo demás, que es lo que se lee cuando la ejecución termina
    mostrar_avisos()


# ========= RUN =========
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # los avisos que ya hubiera pueden explicar el error: van antes, para
        # que el ❌ sea lo último que se ve
        mostrar_avisos()
        print("\n" + rojo(f"❌ {e}"))
        if _interactiva():
            _esperar("\nPulsa Intro para cerrar...")
        sys.exit(CODIGO_ERROR_EXPLICADO)
    menu_final()
