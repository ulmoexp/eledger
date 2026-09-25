"""
reglas.py — Motor de clasificación y exclusión.

Cambia la coincidencia por subcadena "a pelo" (que hacía que MEDIA MARKT
cayera en Comida por contener "dia", o NAVIDAD en Piso por contener "vida")
por una coincidencia con límite de palabra, y añade tres modos explícitos.

SINTAXIS DE LAS CLAVES en rules.json / exclude_patterns.json
-------------------------------------------------------------------
  "mercadona"   INICIO DE PALABRA (modo por defecto).
                La clave debe empezar donde empieza una palabra, pero
                puede continuar. Así "veterin" sigue pillando
                "VETERINARIO", y "dia" ya NO pilla "MEDIA".

  "=dia"        PALABRA COMPLETA.
                Solo casa si además termina en final de palabra.
                Para claves cortas y ambiguas: =dia, =bar, =bp, =o2, =vida.

  "~dia"        EN CUALQUIER SITIO (el comportamiento antiguo).
                Úsalo solo si de verdad quieres pillar la clave dentro
                de otra palabra.

  "re:^abono"   EXPRESIÓN REGULAR, para casos raros.

  "_lo_que_sea" Las claves que empiezan por "_" se ignoran: sirven
                para dejar comentarios dentro del JSON.

Además el texto se normaliza sin acentos, así que "NÓMINA" casa con
"nomina" y "CLÍNICA" con "clinica".

El orden del fichero importa: gana la PRIMERA regla que casa.

QUÉ SE PUEDE PONER COMO VALOR
-------------------------------------------------------------------
  "mercadona": "Comida"

        Lo de siempre: casa, y va a esa categoría.

  "bizum": {"+": "Ingresos", "-": "Ocio"}

        SEGÚN EL SIGNO. Un Bizum que recibes es un ingreso; uno que
        envías es un gasto. Con un solo texto para los dos, los
        recibidos restaban de Ocio y el mes salía barato.

        Ojo: esto NO hace falta para las devoluciones. Si te devuelven
        una compra del Mercadona, que ese abono reste de Comida es
        exactamente lo correcto. El signo solo hace falta cuando el
        positivo es un concepto DISTINTO del negativo, no cuando es la
        devolución del mismo.

  "amazon": {"-": "Otros"}

        Solo un lado. Los movimientos del otro signo siguen buscando
        en las reglas de más abajo.

  "netflix": null

        APAGA la regla. Sirve para desactivar una de la base sin tener
        que editar la base: repites la clave en tu fichero con null.

LAS DOS CAPAS
-------------------------------------------------------------------
  ajustes/rules.json     las TUYAS. Mandan. No se tocan al actualizar.
  app/rules_base.json    la BASE que viene con el programa: cadenas
                         conocidas en toda España. Se reemplaza entera
                         con cada versión nueva.

De la base solo entran las claves que tú no hayas escrito ya, así que
para cambiar cualquiera basta con repetirla en la tuya.

Para ver qué hace una descripción concreta, y de qué capa sale:

    python app/reglas.py "BIZUM DE MARTA" 25
"""

from __future__ import annotations

import json
import os
import re
import unicodedata


def normalizar(texto) -> str:
    """'COMPRA NÓMINA  S.L.' -> 'compra nomina s.l.'; 'BASIC-FIT' -> 'basic fit'.

    El guion cuenta como espacio: unos bancos escriben «BASIC-FIT» y otros
    «BASIC FIT», y la regla «basic fit» no encontraba el primero. Se aplica
    igual al texto y a la clave de la regla, así que «basic-fit» también
    sigue valiendo como clave.
    """
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[\s\-]+", " ", t.lower()).strip()


def leer_json(ruta):
    """
    Lee un fichero de ajustes/. Un error de formato (una coma que falta, una
    que sobra tras la última regla) salía como «Expecting ',' delimiter: line
    7 column 1», en inglés y sin decir de qué fichero: justo lo que se
    encuentra quien edita su primer JSON. Aquí se dice en cuál, en qué línea
    y qué suele ser. utf-8-sig acepta además el BOM que pone el Bloc de notas
    de Windows al guardar, que por sí solo ya hacía fallar la lectura.
    """
    with open(ruta, "r", encoding="utf-8-sig") as f:
        texto = f.read()
    try:
        return json.loads(texto)
    except json.JSONDecodeError as e:
        lineas = texto.splitlines()
        linea = lineas[e.lineno - 1].strip() if 0 < e.lineno <= len(lineas) else ""
        nombre = os.path.join(os.path.basename(os.path.dirname(str(ruta))),
                              os.path.basename(str(ruta)))
        raise RuntimeError(
            f"{nombre} tiene un error de formato en la línea {e.lineno}"
            + (f":  {linea}" if linea else "") + "\n"
            "   Suele ser una coma que falta al final de la línea de antes, una "
            "que sobra\n   después de la última línea, o unas comillas sin "
            "cerrar.\n   Corrígelo y vuelve a ejecutar.") from None


def euros(valor, signo=False, ancho=0) -> str:
    """
    5000 -> '5.000,00 €'; con signo, '+800,00 €'. El formato de Python es el
    inglés (5,000.00) y quien usa esto lee sus importes como se los da el
    banco. ancho alinea a la derecha la cifra, sin contar el símbolo.
    """
    cifra = f"{valor:{'+' if signo else ''},.2f}"
    cifra = cifra.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{cifra:>{ancho}} €"


_INICIO = r"(?<![0-9a-z])"
_FIN = r"(?![0-9a-z])"


def compilar(clave: str) -> tuple[re.Pattern, str]:
    """Devuelve (patrón compilado, modo)."""
    if clave.startswith("re:"):
        return re.compile(clave[3:], re.IGNORECASE), "regex"
    if clave.startswith("="):
        return re.compile(_INICIO + re.escape(normalizar(clave[1:])) + _FIN), "palabra"
    if clave.startswith("~"):
        return re.compile(re.escape(normalizar(clave[1:]))), "libre"
    return re.compile(_INICIO + re.escape(normalizar(clave))), "prefijo"


class Regla:
    """Una regla ya compilada, con de dónde sale y qué categoría produce."""

    __slots__ = ("patron", "valor", "clave", "modo", "origen")

    def __init__(self, patron, valor, clave, modo, origen):
        self.patron = patron
        self.valor = valor        # str, o {"+": ..., "-": ...}
        self.clave = clave
        self.modo = modo
        self.origen = origen      # "tuya" | "base"

    @property
    def por_signo(self) -> bool:
        return isinstance(self.valor, dict)

    def categoria(self, importe):
        """
        La categoría que produce esta regla para un importe dado.

        Devuelve None si la regla NO aplica a ese signo, y entonces se sigue
        buscando en las reglas siguientes. Así `{"-": "Ocio"}` significa
        «clasifica solo los cargos, y de los abonos que se encargue otra».
        """
        if not self.por_signo:
            return self.valor
        lado = "+" if (importe is None or importe >= 0) else "-"
        return self.valor.get(lado) or None

    @property
    def categorias_posibles(self) -> list:
        if self.por_signo:
            return [c for c in self.valor.values() if c]
        return [self.valor] if self.valor else []


class Clasificador:
    """
    Dos capas de reglas:

      · las TUYAS      ajustes/rules.json    nunca se tocan al actualizar
      · la BASE        app/rules_base.json   se reemplaza con cada versión

    Las tuyas se miran primero, así que siempre ganan. De la base solo entran
    las claves que tú no hayas escrito ya, lo que significa que para cambiar
    cualquier regla de la base basta con repetir esa clave en la tuya.
    """

    def __init__(self, reglas: dict, por_defecto: str = "Otros", base: dict = None,
                 categorias_validas=None, por_defecto_positivo: str | None = None):
        self.por_defecto = por_defecto
        # Lo que entra sin ninguna regla (un cobro, una recarga) no puede ir a
        # «Otros», que es de gasto: restaba y dejaba el mes con gastos
        # negativos. Va a la categoría de ingreso que diga el catálogo; sin
        # ella (None), a por_defecto como siempre.
        self.por_defecto_positivo = por_defecto_positivo
        self.reglas = []
        self.descartadas_de_base = []
        self.desactivadas = []

        propias = {k: v for k, v in (reglas or {}).items() if not k.startswith("_")}

        for clave, valor in propias.items():
            # valor null = «esta clave no clasifica nada». Sirve para apagar una
            # regla de la base sin tener que editar la base.
            if valor is None:
                self.desactivadas.append(clave)
                continue
            patron, modo = compilar(clave)
            self.reglas.append(Regla(patron, valor, clave, modo, "tuya"))

        for clave, valor in (base or {}).items():
            if clave.startswith("_") or clave in propias:
                continue
            if valor is None:
                continue
            patron, modo = compilar(clave)
            regla = Regla(patron, valor, clave, modo, "base")

            # Una regla de la base que apunte a una categoría que este usuario no
            # tiene declarada se DESCARTA en silencio (se cuentan aparte). Si se
            # dejara pasar, esos movimientos caerían en una categoría que no es
            # columna de ninguna suma del resumen: no contarían como gasto ni
            # como ingreso, y el total descuadraría sin que nada lo dijera.
            if categorias_validas is not None:
                posibles = regla.categorias_posibles
                if posibles and not all(c in categorias_validas for c in posibles):
                    self.descartadas_de_base.append(clave)
                    continue
            self.reglas.append(regla)

    # --- cuentas, para poder decirlo por pantalla ---
    @property
    def n_propias(self) -> int:
        return sum(1 for r in self.reglas if r.origen == "tuya")

    @property
    def n_base(self) -> int:
        return sum(1 for r in self.reglas if r.origen == "base")

    def clasificar(self, descripcion, importe=None) -> tuple[str, str]:
        """Devuelve (categoria, clave_que_ha_casado)."""
        cat, clave, _ = self.clasificar_detalle(descripcion, importe)
        return cat, clave

    def clasificar_detalle(self, descripcion, importe=None) -> tuple[str, str, str]:
        """Como clasificar(), pero diciendo también de qué capa sale la regla."""
        texto = normalizar(descripcion)
        for r in self.reglas:
            if not r.patron.search(texto):
                continue
            categoria = r.categoria(importe)
            if categoria is None:
                continue          # la regla no aplica a este signo: sigue buscando
            return categoria, r.clave, r.origen
        if importe is not None and importe > 0 and self.por_defecto_positivo:
            return self.por_defecto_positivo, "", ""
        return self.por_defecto, "", ""

    @classmethod
    def desde_json(cls, ruta, por_defecto="Otros", ruta_base=None,
                   categorias_validas=None, por_defecto_positivo=None):
        propias = leer_json(ruta)
        base = {}
        if ruta_base and os.path.exists(ruta_base):
            base = leer_json(ruta_base)
        return cls(propias, por_defecto, base, categorias_validas,
                   por_defecto_positivo)


class Catalogo:
    """
    Las categorías que espera la hoja de resumen, y su papel en los totales.

    Existe para atajar el fallo más traicionero de todo el montaje: si el texto
    de rules.json y el criterio de la fórmula de Excel no coinciden letra por
    letra, la celda devuelve 0 y no avisa nadie. «Higiene» y «Limpieza/Higiene»
    son categorías distintas; «Luz/agua» y «Luz/Agua» también.

    Dos campos opcionales personalizan cómo se ve RESUMEN sin tocar cómo se
    calcula: 'etiquetas' (nombre interno -> texto de columna, para no tener
    que arriesgar el cuadre letra-por-letra solo por cambiar cómo se ve una
    columna) y 'orden_resumen' (qué columnas salen y en qué orden, incluidas
    las de sistema como Balance o Acumulado, hoy fijas al final). Ninguno de
    los dos existía antes de esta versión: si no se ponen, el resumen sale
    exactamente igual que siempre.

    Un tercero, 'desglosar_ingresos', da a cada categoría de ingreso su propia
    columna además del total Ingresos (por defecto no: una sola columna, como
    siempre).
    """

    COLUMNAS_SISTEMA = ["Mes", "Total Gastos", "Ingresos", "Balance",
                        "Fuera del balance", "Acumulado"]

    # Quitadas en la 2.12.0: eran el Acumulado del mes anterior partido por
    # su signo, lo mismo que ya se lee en la fila de arriba. Quien las tenga
    # en orden_resumen merece saber que se han ido a propósito, no un «no
    # es una columna» que le haga buscar una errata que no existe.
    COLUMNAS_RETIRADAS = ["Deuda", "Extras"]

    # La categoría de ingreso de la plantilla y de rules_base.json se llama
    # «Ingresos», igual que la columna del total. Al desglosar, las dos no
    # pueden compartir nombre, y obligar a renombrar la categoría supondría
    # reescribir en rules.json todas las reglas de la base que la asignan. Así
    # que su columna propia toma este nombre, que es lo que de verdad es: lo
    # que entra y no tiene una categoría de ingreso más concreta.
    COLUMNA_OTROS_INGRESOS = "Otros ingresos"

    def __init__(self, datos: dict):
        self.gastos = list(datos.get("gastos", []))
        self.ingresos = list(datos.get("ingresos", []))
        self.neutras = list(datos.get("neutras", []))
        self.columna_mes = datos.get("columna_mes", "mes_ajustado")
        self.etiquetas = dict(datos.get("etiquetas", {}))
        # None = sin personalizar (orden de siempre). Una lista, aunque esté
        # vacía, significa que el usuario SÍ ha decidido qué mostrar.
        self.orden_resumen = datos.get("orden_resumen")
        self.desglosar_ingresos = datos.get("desglosar_ingresos", False) is True

    @property
    def todas(self):
        return self.gastos + self.ingresos + self.neutras

    @property
    def ingreso_por_defecto(self) -> str | None:
        """Adónde va lo que ENTRA sin ninguna regla: «Ingresos» si existe (la
        de la plantilla y de la base), si no la primera de ingresos, y None
        si no hay ninguna declarada. Siempre una categoría que suma."""
        if "Ingresos" in self.ingresos:
            return "Ingresos"
        return self.ingresos[0] if self.ingresos else None

    @property
    def columnas_ingreso(self) -> dict:
        """Categoría de ingreso -> nombre de su columna en RESUMEN, o vacío si
        no se desglosan. Ese nombre de columna es también el que se usa en
        'orden_resumen' y en 'etiquetas'."""
        if not self.desglosar_ingresos:
            return {}
        return {c: (self.COLUMNA_OTROS_INGRESOS if c == "Ingresos" else c)
                for c in self.ingresos}

    def etiqueta(self, categoria: str) -> str:
        """El texto que se ve en la columna, o el nombre interno si no se ha
        declarado uno propio en 'etiquetas'."""
        return self.etiquetas.get(categoria, categoria)

    @classmethod
    def desde_json(cls, ruta):
        return cls({k: v for k, v in leer_json(ruta).items() if not k.startswith("_")})

    def validar(self, clasificador) -> list[str]:
        """Devuelve la lista de avisos (vacía si todo cuadra)."""
        producidas = set()
        for r in clasificador.reglas:
            producidas.update(r.categorias_posibles)
        producidas.add(clasificador.por_defecto)
        if clasificador.por_defecto_positivo:
            producidas.add(clasificador.por_defecto_positivo)
        declaradas = set(self.todas)
        avisos = []

        # 1) mismo nombre salvo tildes o mayúsculas: casi siempre es una errata
        for pr in sorted(producidas - declaradas):
            for de in declaradas - producidas:
                if normalizar(pr) == normalizar(de):
                    avisos.append(
                        f"«{pr}» (rules.json) y «{de}» (categorias.json) solo se "
                        f"diferencian en tildes o mayúsculas. Para Excel son "
                        f"categorías distintas: la columna sumaría 0.")
                    break

        casi = {normalizar(x) for x in declaradas}
        for pr in sorted(producidas - declaradas):
            if normalizar(pr) not in casi:
                avisos.append(
                    f"«{pr}» se asigna en rules.json pero no está en categorias.json: "
                    f"esos movimientos no aparecerán en ninguna columna del resumen.")

        casi_pr = {normalizar(x) for x in producidas}
        for de in sorted(declaradas - producidas):
            if normalizar(de) not in casi_pr:
                avisos.append(
                    f"«{de}» está en categorias.json pero ninguna regla la asigna: "
                    f"su columna saldrá siempre a 0.")

        repes = {c for c in self.todas if self.todas.count(c) > 1}
        for c in sorted(repes):
            avisos.append(f"«{c}» aparece más de una vez en categorias.json.")

        # Cada columna del resumen es una clave de la misma fila: si una
        # categoría se llama como otra columna (un gasto «Balance», o una
        # categoría de ingreso «Otros ingresos» junto a «Ingresos» al
        # desglosar), una pisa a la otra al construirla y desaparece del
        # Excel. Los totales no cambian, pero la columna se pierde sin avisar.
        ocupadas = set(self.COLUMNAS_SISTEMA)
        for col in self.gastos + list(self.columnas_ingreso.values()):
            if col in ocupadas and col not in repes:
                avisos.append(
                    f"«{col}» se llama igual que otra columna del resumen: "
                    f"solo se verá una de las dos. Cámbiale el nombre en "
                    f"categorias.json y en rules.json.")
            ocupadas.add(col)

        # orden_resumen es opcional: si no se declara, no hay nada que
        # validar (el orden de siempre no puede tener nombres mal escritos).
        if self.orden_resumen is not None:
            conocidas = (set(self.COLUMNAS_SISTEMA) | set(self.gastos)
                         | set(self.columnas_ingreso.values()))
            for nombre in self.orden_resumen:
                if nombre in conocidas:
                    continue
                if nombre in self.COLUMNAS_RETIRADAS:
                    avisos.append(
                        f"«{nombre}» en orden_resumen ya no existe desde la "
                        f"2.12.0 (era el Acumulado del mes anterior, que ya se "
                        f"ve en la fila de arriba). Quítala de ahí.")
                elif nombre in self.ingresos or nombre == self.COLUMNA_OTROS_INGRESOS:
                    avisos.append(
                        f"«{nombre}» en orden_resumen es una categoría de "
                        f"ingreso, y solo tienen columna propia con "
                        f"\"desglosar_ingresos\": true. Se ignora.")
                else:
                    avisos.append(
                        f"«{nombre}» en orden_resumen no es ni una columna de "
                        f"sistema ni una categoría declarada: se ignora.")
            # sin «Mes» el resumen sale sin la columna que dice de qué mes es
            # cada fila; es legal, pero casi nunca a propósito
            if "Mes" not in self.orden_resumen:
                avisos.append(
                    "orden_resumen no incluye «Mes»: el resumen saldrá sin la "
                    "columna de los meses. Si no es a propósito, ponla la primera.")

        # una etiqueta para una columna que no existe se ignoraba en silencio,
        # cuando una errata en orden_resumen sí avisaba
        propias = set(self.gastos) | set(self.columnas_ingreso.values())
        for nombre in self.etiquetas:
            if nombre not in propias:
                avisos.append(
                    f"«{nombre}» en etiquetas no es una categoría de gasto ni una "
                    f"columna de ingreso desglosada: esa etiqueta no se usa. "
                    f"(Las columnas de sistema, como Balance, no se renombran.)")

        return avisos


class Excluidor:
    def __init__(self, patrones: list):
        self.patrones = [(compilar(p)[0], p) for p in patrones if not p.startswith("_")]

    def excluir(self, descripcion) -> tuple[bool, str]:
        texto = normalizar(descripcion)
        for patron, clave in self.patrones:
            if patron.search(texto):
                return True, clave
        return False, ""

    @classmethod
    def desde_json(cls, ruta):
        return cls(leer_json(ruta))


class IdentificadorCuentas:
    """
    De qué cuenta es cada fichero, para poder distinguir dos cuentas del
    mismo tipo en la deduplicación (ver TRASPASO.md, hito A3). Se declara en
    ajustes/cuentas.json: un patrón, con la MISMA SINTAXIS que rules.json,
    pero que casa contra el NOMBRE DEL FICHERO, no contra la descripción de
    un movimiento.

    Sin ningún patrón que case, la cuenta es "" para todo el mundo: es
    justo el comportamiento de siempre, así que quien no declare nada no
    nota ningún cambio.
    """

    def __init__(self, patrones: dict):
        self.reglas = []
        propias = {k: v for k, v in (patrones or {}).items() if not k.startswith("_")}
        for clave, valor in propias.items():
            if not valor:
                continue
            patron, _ = compilar(clave)
            self.reglas.append((patron, str(valor)))

    def identificar(self, nombre_fichero) -> str:
        texto = normalizar(nombre_fichero)
        for patron, cuenta in self.reglas:
            if patron.search(texto):
                return cuenta
        return ""

    @classmethod
    def desde_json(cls, ruta):
        if not os.path.exists(ruta):
            return cls({})
        return cls(leer_json(ruta))


# ========= COMPROBACIÓN =========
# python app/reglas.py                          los ejemplos de siempre
# python app/reglas.py "BIZUM DE MARTA"         una descripción
# python app/reglas.py "BIZUM DE MARTA" 25      con importe, para ver el signo
if __name__ == "__main__":
    import sys

    # Se leen de ajustes/ y app/, no del directorio actual: así funciona igual
    # desde la raíz del proyecto que desde dentro de app/.
    import rutas

    cat = Catalogo.desde_json(rutas.CATEGORIAS)
    clf = Clasificador.desde_json(rutas.REGLAS, ruta_base=rutas.REGLAS_BASE,
                                  categorias_validas=set(cat.todas),
                                  por_defecto_positivo=cat.ingreso_por_defecto)
    exc = Excluidor.desde_json(rutas.EXCLUSIONES)

    argumentos = sys.argv[1:]
    importe = None
    if len(argumentos) >= 2:
        try:
            importe = float(argumentos[-1].replace(",", "."))
            argumentos = argumentos[:-1]
        except ValueError:
            pass

    if argumentos:
        casos = [(t, importe) for t in argumentos]
    else:
        casos = [
            ("MEDIA MARKT ONLINE", -200.0), ("SUPERMERCADOS DIA MADRID", -50.0),
            ("GUARDIA CIVIL", -30.0), ("BAR LA ESQUINA", -18.0),
            ("BARCELONA HOTEL", -300.0), ("CESTA DE NAVIDAD", -20.0),
            ("SEGURO DE VIDA MAPFRE", -40.0), ("BP OIL ESPANA", -55.0),
            ("ABP CONSULTING", -10.0), ("NÓMINA EMPRESA SL", 2000.0),
            ("CLÍNICA DENTAL", -90.0), ("REPSOL E.S. LAS ROZAS", -60.0),
            ("BIZUM A MARTA CENA", -18.0), ("BIZUM DE MARTA CENA", 18.0),
            ("DEVOLUCION MERCADONA", 12.0),
        ]

    print(f"Reglas activas: {clf.n_propias} tuyas + {clf.n_base} de la base")
    # El ejemplo de exclusión se construye con TU primer patrón, en vez de
    # llevarlo escrito aquí: este fichero se reparte y no puede saber nada de ti.
    if not sys.argv[1:] and exc.patrones:
        casos.append((f"UN MOVIMIENTO CON «{exc.patrones[0][1].upper()}» DENTRO",
                      -500.0))
    if clf.desactivadas:
        print(f"Apagadas con null: {', '.join(clf.desactivadas)}")
    if clf.descartadas_de_base:
        print(f"De la base, descartadas por apuntar a una categoría que no tienes "
              f"en categorias.json: {', '.join(clf.descartadas_de_base)}")
    print()

    ancho = max(len(t) for t, _ in casos)
    for texto, imp in casos:
        etiqueta = f"{texto:<{ancho}}"
        if imp is not None:
            etiqueta += f"  {euros(imp, ancho=9)}"
        fuera, cl_exc = exc.excluir(texto)
        if fuera:
            print(f"{etiqueta}  ->  EXCLUIDO           [{cl_exc}]")
            continue
        categoria, clave, origen = clf.clasificar_detalle(texto, imp)
        marca = clave or "sin regla"
        if origen == "base":
            marca += " · base"
        print(f"{etiqueta}  ->  {categoria:<24} [{marca}]")
