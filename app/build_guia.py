#!/usr/bin/env python3
"""Genera GUIA.pdf — guía de uso de la herramienta de movimientos."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, PageBreak,
                               PageTemplate, Paragraph, Spacer, Table, TableStyle)

# ---------------------------------------------------------------- fuentes
# Lato y DejaVu en vez de Poppins: se instalan con un simple
# `apt install fonts-lato fonts-dejavu` en cualquier máquina o CI, mientras
# que Poppins solo estaba en la carpeta personal de "google-fonts" de quien
# escribió esto la primera vez y no se podía reproducir en otra parte.
G = "/usr/share/fonts/truetype/lato/"
D = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(TTFont("Head", G + "Lato-Medium.ttf"))
pdfmetrics.registerFont(TTFont("HeadB", G + "Lato-Bold.ttf"))
pdfmetrics.registerFont(TTFont("Body", D + "DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("BodyB", D + "DejaVuSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("BodyI", D + "DejaVuSans-Oblique.ttf"))
pdfmetrics.registerFont(TTFont("Mono", D + "DejaVuSansMono.ttf"))
pdfmetrics.registerFont(TTFont("MonoB", D + "DejaVuSansMono-Bold.ttf"))

# ---------------------------------------------------------------- paleta
TINTA = colors.HexColor("#1B2027")
GRIS = colors.HexColor("#5C6672")
GRIS_CL = colors.HexColor("#9AA3AE")
ACENTO = colors.HexColor("#0E6B5E")
ACENTO_CL = colors.HexColor("#E4F0ED")
FONDO = colors.HexColor("#F5F6F7")
LINEA = colors.HexColor("#DDE1E5")
AVISO = colors.HexColor("#B4531A")
AVISO_CL = colors.HexColor("#FBF0E6")

ANCHO = A4[0] - 40 * mm

# ---------------------------------------------------------------- estilos
S = {}
S["titulo"] = ParagraphStyle("titulo", fontName="HeadB", fontSize=25, leading=29,
                             textColor=TINTA, spaceAfter=3)
S["subtitulo"] = ParagraphStyle("subtitulo", fontName="Body", fontSize=11.5, leading=16,
                                textColor=GRIS, spaceAfter=0)
S["h1"] = ParagraphStyle("h1", fontName="Head", fontSize=14.5, leading=18,
                         textColor=ACENTO, spaceBefore=0, spaceAfter=5)
S["h2"] = ParagraphStyle("h2", fontName="BodyB", fontSize=10.5, leading=14,
                         textColor=TINTA, spaceBefore=9, spaceAfter=3)
S["p"] = ParagraphStyle("p", fontName="Body", fontSize=9.5, leading=14.5,
                        textColor=TINTA, spaceAfter=6, alignment=TA_LEFT)
S["pmini"] = ParagraphStyle("pmini", parent=S["p"], fontSize=8.6, leading=12.5,
                            textColor=GRIS)
S["celda"] = ParagraphStyle("celda", fontName="Body", fontSize=8.6, leading=12.2,
                            textColor=TINTA)
S["celdaB"] = ParagraphStyle("celdaB", parent=S["celda"], fontName="BodyB")
S["celdaM"] = ParagraphStyle("celdaM", fontName="Mono", fontSize=8.2, leading=12.2,
                             textColor=ACENTO)
S["cab"] = ParagraphStyle("cab", fontName="BodyB", fontSize=8.2, leading=11,
                          textColor=colors.white)
S["code"] = ParagraphStyle("code", fontName="Mono", fontSize=8.6, leading=13.5,
                           textColor=TINTA)
S["paso"] = ParagraphStyle("paso", fontName="Body", fontSize=9.6, leading=14,
                           textColor=TINTA)
S["num"] = ParagraphStyle("num", fontName="HeadB", fontSize=12, leading=14,
                          textColor=ACENTO)
S["pie"] = ParagraphStyle("pie", fontName="Body", fontSize=7.5, textColor=GRIS_CL)


# ---------------------------------------------------------------- bloques
def seccion(*flowables):
    """Mantiene una sección entera en la misma página."""
    items = []
    for f in flowables:
        items.extend(f if isinstance(f, list) else [f])
    return KeepTogether(items)


def h1(texto, regla=True):
    """Encabezado de sección con filete."""
    p = Paragraph(texto, S["h1"])
    if not regla:
        p._h1 = True
        return p
    t = Table([[p]], colWidths=[ANCHO])
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 1.1, ACENTO),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    t._h1 = True
    return t


def p(texto):
    return Paragraph(texto, S["p"])


def codigo(lineas, ancho=ANCHO):
    """Bloque de código monoespaciado con filete lateral."""
    if isinstance(lineas, str):
        lineas = lineas.split("\n")
    cuerpo = "<br/>".join(l.replace(" ", "&nbsp;") for l in lineas)
    t = Table([[Paragraph(cuerpo, S["code"])]], colWidths=[ancho])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), FONDO),
        ("LINEBEFORE", (0, 0), (0, -1), 2.5, ACENTO),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return t


def tabla(cabecera, filas, anchos, estilos=None):
    """Tabla con cabecera oscura y bandas suaves."""
    estilos = estilos or ["celda"] * len(cabecera)
    datos = [[Paragraph(c, S["cab"]) for c in cabecera]]
    for fila in filas:
        datos.append([Paragraph(str(v), S[e]) for v, e in zip(fila, estilos)])
    t = Table(datos, colWidths=anchos, repeatRows=1)
    est = [
        ("BACKGROUND", (0, 0), (-1, 0), ACENTO),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 1), (-1, -2), 0.4, LINEA),
        ("LINEBELOW", (0, -1), (-1, -1), 0.8, LINEA),
    ]
    for i in range(2, len(datos), 2):
        est.append(("BACKGROUND", (0, i), (-1, i), FONDO))
    t.setStyle(TableStyle(est))
    return t


def aviso(titulo, texto, color=AVISO, fondo=AVISO_CL):
    st = ParagraphStyle("av", parent=S["p"], fontSize=8.8, leading=13, spaceAfter=0)
    stt = ParagraphStyle("avt", parent=st, fontName="BodyB", textColor=color,
                         spaceAfter=2)
    t = Table([[Paragraph(titulo, stt)], [Paragraph(texto, st)]], colWidths=[ANCHO])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), fondo),
        ("LINEBEFORE", (0, 0), (0, -1), 2.5, color),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (0, 0), 8),
        ("BOTTOMPADDING", (0, 0), (0, 0), 0),
        ("TOPPADDING", (0, 1), (0, 1), 0),
        ("BOTTOMPADDING", (0, 1), (0, 1), 8),
    ]))
    # entero o nada: una tabla se puede partir entre filas, y el título se
    # quedaba solo al pie de una página con el texto en la siguiente
    return KeepTogether([t])


def pasos(items):
    """Lista numerada con círculos de acento."""
    datos = []
    for i, texto in enumerate(items, 1):
        datos.append([Paragraph(f"{i}", S["num"]), Paragraph(texto, S["paso"])])
    t = Table(datos, colWidths=[10 * mm, ANCHO - 10 * mm])
    est = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for i in range(len(datos) - 1):
        est.append(("LINEBELOW", (1, i), (1, i), 0.4, LINEA))
    t.setStyle(TableStyle(est))
    return t


# ---------------------------------------------------------------- página
def decorar(canvas, doc):
    canvas.saveState()
    if doc.page == 1:
        canvas.setFillColor(ACENTO)
        canvas.rect(0, A4[1] - 8 * mm, A4[0], 8 * mm, stroke=0, fill=1)
    else:
        canvas.setFont("Body", 7.5)
        canvas.setFillColor(GRIS_CL)
        canvas.drawString(20 * mm, A4[1] - 12 * mm, "Movimientos bancarios · guía de uso")
        canvas.setStrokeColor(LINEA)
        canvas.setLineWidth(0.5)
        canvas.line(20 * mm, A4[1] - 14.5 * mm, A4[0] - 20 * mm, A4[1] - 14.5 * mm)
    canvas.setFont("Body", 7.5)
    canvas.setFillColor(GRIS_CL)
    canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, str(doc.page))
    canvas.drawString(20 * mm, 12 * mm, "Uso local · los datos no salen del equipo")
    canvas.restoreState()


# ---------------------------------------------------------------- contenido
E = Spacer(1, 5)
EE = Spacer(1, 11)
story = []

# ---- portada / cabecera
story += [
    Spacer(1, 6 * mm),
    Paragraph("Movimientos bancarios", S["titulo"]),
    Paragraph("Guía de uso · unificación, limpieza y clasificación de extractos",
              S["subtitulo"]),
    Spacer(1, 7 * mm),
]

# la privacidad va lo primero, antes incluso de la chuleta: es la promesa
# central de la herramienta (igual que en la portada y la guía de la web)
story += [
    h1("Privacidad"),
    E,
    p("Todo el procesamiento ocurre en tu ordenador. La herramienta no abre ninguna "
      "conexión de red, no envía datos a ningún servicio y no deja copias fuera de la "
      "carpeta del proyecto. Las únicas librerías externas son "
      "<font face='Mono' size='8.6'>pandas</font>, "
      "<font face='Mono' size='8.6'>openpyxl</font> y "
      "<font face='Mono' size='8.6'>xlrd</font>, todas de lectura y escritura local."),
    p("Si mueves la carpeta a otro ordenador, cópiala entera y vuelve a instalar las "
      "dependencias. No hay nada más que configurar."),
]
story += [EE]

story += [h1("Chuleta"), E]
story += [pasos([
    "Descarga del banco los extractos de <b>cuenta</b> y de <b>tarjeta</b>",
    "Suéltalos en la carpeta <font face='Mono' size='9'>entrada/</font> "
    "<font face='Body' color='#5C6672'>tal cual: sin renombrar, sin convertir, "
    "sin separar por tipo</font>",
    "Doble clic en <font face='Mono' size='9'>ejecutar.bat</font> "
    "<font face='Body' color='#5C6672'>(Windows)</font>, "
    "<font face='Mono' size='9'>ejecutar.command</font> "
    "<font face='Body' color='#5C6672'>(Mac)</font> o "
    "<font face='Mono' size='9'>ejecutar.sh</font> "
    "<font face='Body' color='#5C6672'>(Linux)</font>",
    "Revisa el resumen en pantalla: qué ha leído de cada fichero, el resultado, "
    "lo que se repite y lo que falta por clasificar; los avisos, juntos al final",
    "Elige en el menú: abrir el histórico o su carpeta, <b>clasificar lo que "
    "falta</b> o <b>excluir el recibo de la tarjeta</b> (si hay algo; te pregunta "
    "y escribe los ajustes por ti) o ejecutar de nuevo "
    "<font face='Body' color='#5C6672'>(Intro cierra la ventana)</font>",
    "Abre tu fichero de contabilidad: los movimientos ya están dentro "
    "<font face='Body' color='#5C6672'>(si tienes la sincronización activada)</font>",
])]
story += [EE]

story += [aviso(
    "No hay que preparar nada",
    "Los .xls del banco no se convierten: la herramienta detecta el formato real "
    "mirando el contenido, no la extensión. Tampoco hay que renombrarlos ni separar "
    "cuenta de tarjetas: eso también lo deduce sola.",
    ACENTO, ACENTO_CL)]
story += [EE]

story += [h1("Qué hace"), E]
story += [p(
    "Lee los movimientos de la cuenta y de todas las tarjetas, los junta en una sola "
    "tabla, descarta los movimientos que no quieres contar, los clasifica por "
    "categorías y genera un Excel listo para pegar en tu hoja de cálculo. Al terminar, "
    "te enseña qué cargos se repiten cada mes o cada año (suscripciones, cuotas, "
    "seguros) y cuánto suman al año; sin opinar sobre ninguno. "
    "El Excel se abre con Microsoft Excel, OnlyOffice o LibreOffice.")]

flujo = Table([[
    Paragraph("<b>Entrada</b><br/><font size='8' color='#5C6672'>cuenta + tarjetas<br/>"
              "cualquier formato</font>", S["celda"]),
    Paragraph("→", ParagraphStyle("f", parent=S["celda"], fontSize=13,
                                  textColor=ACENTO, alignment=1)),
    Paragraph("<b>Proceso</b><br/><font size='8' color='#5C6672'>unificar · excluir<br/>"
              "clasificar · ajustar mes</font>", S["celda"]),
    Paragraph("→", ParagraphStyle("f2", parent=S["celda"], fontSize=13,
                                  textColor=ACENTO, alignment=1)),
    Paragraph("<b>Salida</b><br/><font size='8' color='#5C6672'>historico.xlsx<br/>"
              "movimientos_limpios · excluidos</font>", S["celda"]),
]], colWidths=[ANCHO * 0.28, ANCHO * 0.08, ANCHO * 0.28, ANCHO * 0.08, ANCHO * 0.28])
flujo.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (0, 0), FONDO),
    ("BACKGROUND", (2, 0), (2, 0), FONDO),
    ("BACKGROUND", (4, 0), (4, 0), FONDO),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("ALIGN", (1, 0), (1, 0), "CENTER"),
    ("ALIGN", (3, 0), (3, 0), "CENTER"),
    ("TOPPADDING", (0, 0), (-1, -1), 9),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ("LEFTPADDING", (0, 0), (-1, -1), 9),
]))
story += [flujo, EE]

story += [h1("Instalación"), E]
story += [p(
    "Una sola vez: doble clic en <font face='Mono' size='9'>instalar.bat</font> "
    "(en Mac, <font face='Mono' size='9'>instalar.command</font>; en Linux, "
    "<font face='Mono' size='9'>instalar.sh</font>). Tarda un par de "
    "minutos. Prepara las librerías en una carpeta propia dentro de "
    "<font face='Mono' size='8.6'>app/.venv</font>, sin tocar nada de lo que ya "
    "tengas instalado, y a partir de ahí "
    "<font face='Mono' size='8.6'>ejecutar.bat</font> la usa sola.")]
story += [Spacer(1, 5)]
story += [tabla(
    ["Si sale...", "Qué hacer"],
    [["<i>«No encuentro Python»</i>",
      "Instálalo desde <font face='Mono'>python.org/downloads</font> y marca "
      "<b>«Add Python to PATH»</b> durante la instalación. Es la casilla que casi "
      "todo el mundo se salta y sin ella no funciona nada."],
     ["<i>«Falta una librería»</i> al ejecutar",
      "No se ha llegado a instalar. Vuelve a lanzar "
      "<font face='Mono'>instalar.bat</font> y mira si termina sin errores."],
     ["Mac: no deja abrir el fichero",
      "Clic derecho sobre él → <b>Abrir</b>. Solo la primera vez."],
     ["Linux: el doble clic no lo ejecuta",
      "Dale permisos desde una terminal en esa carpeta: "
      "<font face='Mono'>chmod +x instalar.sh &amp;&amp; ./instalar.sh</font>"]],
    [ANCHO * 0.32, ANCHO * 0.68])]
story += [Spacer(1, 5)]
story += [Paragraph(
    "Si lo que te han dado es un <font face='Mono' size='8.6'>eledger.exe</font>, "
    "no hay que instalar nada: doble clic y ya. Y si prefieres hacerlo a mano, "
    "<font face='Mono' size='8.6'>pip install -r requisitos.txt</font> hace lo mismo. "
    "De las tres librerías, <font face='Mono' size='8.6'>xlrd</font> solo hace falta "
    "para los .xls de Excel 97-2003 de verdad; la mayoría de bancos españoles llaman "
    ".xls a un HTML o a un XML y esos se leen sin ella.", S["pmini"])]

story += [h1("Estructura de carpetas"), E]
story += [codigo([
    "proyecto/",
    "├── instalar.bat        ← solo la primera vez",
    "├── ejecutar.bat        ← doble clic para procesar",
    "├── exportar.bat        ← ZIP para dar a alguien, sin tus datos",
    "│   (en Mac, los tres acaban en .command; en Linux, en .sh)",
    "├── LEEME.txt",
    "├── CHANGELOG.md        ← qué cambió en cada versión",
    "├── GUIA.pdf            ← esto que estás leyendo",
    "│",
    "├── entrada/            ← AQUÍ sueltas lo del banco",
    "│   ├── EXTRACTO_2601.xls",
    "│   ├── movimientos (3).xls",
    "│   └── tarjeta_credito.csv",
    "│",
    "├── datos/              ← LO INSUSTITUIBLE",
    "│   ├── historico.xlsx      ← todo lo acumulado",
    "│   └── copias/             ← copias de seguridad",
    "│",
    "├── ajustes/            ← TU configuración",
    "│   ├── rules.json          ← tus reglas",
    "│   ├── exclude_patterns.json",
    "│   ├── categorias.json",
    "│   ├── mes_contable.json",
    "│   ├── cuentas.json        ← solo si tienes varias cuentas",
    "│   └── sincronizar.json",
    "│",
    "├── salida/             ← se regenera cada vez",
    "│   ├── movimientos_limpios.xlsx",
    "│   └── movimientos_excluidos.xlsx",
    "│",
    "└── app/                ← la herramienta. No hay que tocarla.",
    "    ├── rules_base.json     ← reglas que trae el programa",
    "    └── VERSION             ← qué versión tienes",
])]
story += [Spacer(1, 4)]
story += [Paragraph(
    "En el día a día solo tocas <font face='Mono' size='8.2'>entrada/</font>. Los "
    "JSON de <font face='Mono' size='8.2'>ajustes/</font> son los que irás afinando "
    "con el tiempo; <font face='Mono' size='8.2'>app/</font> no se toca salvo que "
    "quieras cambiar el comportamiento. <b><font face='Mono' "
    "size='8.2'>datos/</font> es lo único insustituible</b>: si haces una copia de "
    "seguridad de algo, que sea de esa carpeta. Para actualizar a una versión nueva, "
    "borra <font face='Mono' size='8.2'>app/</font> y <font face='Mono' "
    "size='8.2'>GUIA.pdf</font> y copia los nuevos encima; las otras cuatro carpetas "
    "no se tocan. Si vienes de la versión antigua con todo suelto en una carpeta, la "
    "primera ejecución lo recoloca sola y te dice lo que ha movido.",
    S["pmini"])]
story += [EE]

story += [h1("Formatos de entrada"), E]
story += [p(
    "Los bancos llaman «.xls» a cosas muy distintas. La herramienta mira los primeros "
    "bytes del fichero y elige el lector adecuado, así que no tienes que hacer nada:")]
story += [tabla(
    ["Lo que manda el banco", "Qué es en realidad", "Se lee"],
    [["<font face='Mono'>.xls</font>", "Excel 97-2003 (BIFF)", "sí · requiere xlrd"],
     ["<font face='Mono'>.xls</font>", "una tabla HTML renombrada", "sí"],
     ["<font face='Mono'>.xls</font>", "XML de Office (SpreadsheetML 2003)", "sí"],
     ["<font face='Mono'>.xls</font>", "un CSV renombrado", "sí"],
     ["<font face='Mono'>.xls</font>", "un .xlsx renombrado", "sí"],
     ["<font face='Mono'>.xlsx .csv .ods</font>", "lo que dice la extensión", "sí"]],
    [ANCHO * 0.28, ANCHO * 0.46, ANCHO * 0.26])]
story += [Spacer(1, 6)]
story += [Paragraph(
    "También se resuelven solos: la fila de cabecera (esté donde esté), los nombres de "
    "columna según banco (<i>Importe</i>, <i>Importe de la operación</i>, <i>Cantidad</i>, "
    "y los de los neobancos en inglés: <i>Amount</i>, <i>Description</i>, <i>Payee</i>…), "
    "el importe partido en dos columnas (<i>Cargo</i> y <i>Abono</i>, o <i>Debe</i> y "
    "<i>Haber</i>), los acentos, y los importes en formato español "
    "(<font face='Mono' size='8.2'>1.234,56 €</font>, "
    "<font face='Mono' size='8.2'>(45,00)</font>, "
    "<font face='Mono' size='8.2'>12,50-</font>).", S["pmini"])]
story += [EE]

story += [h1("Cuenta o tarjeta, y extractos repetidos"), E]
story += [p(
    "No tienes que decirle cuál es cuál. Para cada fichero mira los nombres de las "
    "columnas: si hay una de <b>saldo</b> es un extracto de cuenta; si hay una de "
    "<b>importe de la operación</b> es de tarjeta. Si el contenido no lo aclara, "
    "recurre al nombre del fichero. Por pantalla te dice siempre qué ha decidido y "
    "por qué, para que puedas corregirlo si se equivoca.")]
story += [codigo([
    "· EXTRACTO_2601.xls: formato=xls_biff, cabecera en fila 4, 62 movimientos",
    "  → cuenta (columna «saldo»)",
    "· tarjeta_credito.csv: formato=texto, cabecera en fila 3, 28 movimientos",
    "  → tarjeta (columna «importe de la operacion»)",
])]
story += [Spacer(1, 7)]
story += [Paragraph("Extractos que se solapan", S["h2"])]
story += [p(
    "Puedes dejar en <font face='Mono' size='8.6'>entrada/</font> descargas de meses "
    "anteriores sin miedo. Si bajaste abril y luego abril+mayo, los movimientos que "
    "aparecen en ambos ficheros se detectan y se cuentan una sola vez.")]
story += [aviso(
    "Repetido no es lo mismo que duplicado",
    "Dos cargos idénticos el mismo día en el mismo sitio son dos gastos reales, no un "
    "error. Solo se descartan las repeticiones <b>entre ficheros distintos</b>; las "
    "que vienen dentro de un mismo extracto se respetan.",
    ACENTO, ACENTO_CL)]
story += [EE]

story += [h1("Columnas generadas"), E]
story += [tabla(
    ["Col.", "Nombre", "Qué contiene"],
    [["A", "fecha", "fecha de la operación, sin hora"],
     ["B", "descripcion", "el concepto tal cual lo manda el banco"],
     ["C", "importe", "número; negativo = gasto"],
     ["D", "tipo", "<font face='Mono'>cuenta</font> o <font face='Mono'>tarjeta</font>"],
     ["E", "mes", "el mes real de la fecha"],
     ["F", "mes_ajustado", "el mes contable (ver «Ajuste de mes»)"],
     ["G", "categoria", "resultado de aplicar rules.json"],
     ["H", "categoria_manual", "la ÚNICA columna que escribes tú: fuerza una "
      "categoría, o «(excluido)» para sacarla de los totales"],
     ["I", "excluido", "TRUE si exclude_patterns.json o categoria_manual la "
      "sacó de los totales"],
     ["J", "origen", "de qué fichero salió la fila"],
     ["K", "regla", "qué clave de rules.json la clasificó, o «(manual)»"],
     ["L", "n_rep", "0, 1, 2... para distinguir cargos idénticos el mismo día"],
     ["M", "saldo", "el saldo que traía el extracto tras esa fila, si lo "
      "traía (ver «De dónde parte el Acumulado»)"],
     ["N", "cuenta", "el identificador de ajustes/cuentas.json, si tienes "
      "más de una cuenta declarada; en blanco si no"]],
    [ANCHO * 0.08, ANCHO * 0.24, ANCHO * 0.68],
    ["celdaB", "celdaM", "celda"])]
story += [Spacer(1, 7)]
story += [aviso(
    "No cambies el orden de A–G",
    "Las fórmulas de la hoja MOVIMIENTOS apuntan a columnas concretas: C (importe), "
    "F (mes_ajustado) y G (categoria). De H en adelante son de diagnóstico y van al "
    "final justamente para no desplazarlas.")]

story += [h1("Cómo editar los ajustes"), E]
story += [p(
    "Los ficheros de <font face='Mono' size='8.6'>ajustes/</font> son texto. Se abren "
    "con el <b>Bloc de notas</b> en Windows, <b>TextEdit</b> en Mac o cualquier editor "
    "de texto (clic derecho → Abrir con). Con Word no: cambia las comillas y añade "
    "cosas que el programa no entiende.")]
story += [aviso(
    "Lo más habitual no hace falta hacerlo a mano",
    "Al terminar, el menú ofrece <b>Clasificar lo que falta</b> y <b>Excluir el "
    "recibo de la tarjeta</b> cuando hay algo. Te pregunta (eliges la categoría con "
    "un número; del recibo, te enseña antes qué excluiría) y escribe la línea por "
    "ti en rules.json o exclude_patterns.json, sin tocar nada más del fichero. Antes deja una copia de cómo estaba en "
    "<font face='Mono' size='8.2'>datos/copias/</font>. Solo ofrece las categorías "
    "que tienes en categorias.json, así que no puede crear una que no sume.",
    ACENTO, ACENTO_CL)]
story += [Spacer(1, 6)]
story += [p("Para todo lo demás, cuatro cosas que conviene saber:")]
story += [tabla(
    ["Regla", "Por qué"],
    [["<b>Cada línea acaba en coma</b>, salvo la última antes de la llave de cierre",
      "Es el error más común: al añadir una línea al final, la de antes se queda "
      "sin su coma."],
     ["<b>Comillas dobles rectas</b>: <font face='Mono'>\"texto\"</font>",
      "Nunca « » ni “ ”. Los procesadores de texto las cambian solas: por eso, con "
      "el Bloc de notas."],
     ["<b>Las categorías, igual que en categorias.json</b>",
      "Letra a letra y sin tildes: «Luz/Agua», no «Luz/agua»."],
     ["<b>Las líneas que empiezan por _ son comentarios</b>",
      "Se pueden dejar tal cual: explican el fichero y no cuentan."]],
    [ANCHO * 0.42, ANCHO * 0.58])]
story += [Spacer(1, 6)]
story += [codigo([
    '{',
    '  "_sintaxis": "...",',
    '  "casero pepe": "Piso",       ← con coma',
    '  "academia baile": "Hijos"    ← la última, sin coma',
    '}',
])]
story += [Spacer(1, 4)]
story += [Paragraph(
    "Si algo no cuadra, al ejecutar se dice qué fichero y qué línea («tiene un "
    "error de formato en la línea 7»). Casi siempre es la coma de la línea de "
    "antes. Corrígelo, guarda y escribe <b>R</b> para volver a probar sin cerrar la "
    "ventana.", S["pmini"])]
story += [EE]

story += [h1("rules.json · cómo se clasifica"), E]
story += [p(
    "Es un diccionario de <b>texto a buscar → categoría</b>. Gana la <b>primera</b> "
    "regla que casa, así que el orden del fichero importa. La comparación no distingue "
    "mayúsculas ni acentos: <font face='Mono' size='8.6'>nomina</font> encuentra «NÓMINA».")]
story += [Spacer(1, 6)]
story += [Paragraph("Hay dos capas de reglas", S["h2"])]
story += [tabla(
    ["Fichero", "Qué es"],
    [["<font face='Mono'>ajustes/rules.json</font>",
      "<b>Las tuyas.</b> Mandan sobre la base. No se tocan nunca al actualizar."],
     ["<font face='Mono'>app/rules_base.json</font>",
      "<b>La base</b> que viene con el programa: cadenas conocidas en toda España "
      "(Mercadona, Endesa, Movistar, Repsol...). Se reemplaza entera con cada "
      "versión nueva, así que no la edites: lo que escribas ahí se perderá."]],
    [ANCHO * 0.32, ANCHO * 0.68])]
story += [Spacer(1, 5)]
story += [Paragraph(
    "De la base solo entran las claves que tú no hayas escrito ya. Para <b>cambiar</b> "
    "una regla de la base, repite esa misma clave en la tuya. Para <b>apagarla</b>, "
    "ponla a <font face='Mono' size='8.2'>null</font>. Al ejecutar verás una línea "
    "diciendo cuántas reglas hay de cada capa.", S["pmini"])]
story += [Spacer(1, 8)]
story += [Spacer(1, 2)]
story += [tabla(
    ["Cómo se escribe", "Qué significa", "Ejemplo"],
    [["<font face='Mono'>\"mercadona\"</font>",
      "<b>Inicio de palabra</b> (por defecto). Puede continuar, pero tiene que "
      "empezar donde empieza una palabra.",
      "<font face='Mono'>veterin</font> encuentra VETERINARIO"],
     ["<font face='Mono'>\"=dia\"</font>",
      "<b>Palabra completa.</b> Para claves cortas y ambiguas.",
      "<font face='Mono'>=dia</font> encuentra DIA pero no ME<b>DIA</b> MARKT"],
     ["<font face='Mono'>\"~dia\"</font>",
      "<b>En cualquier sitio.</b> Solo si de verdad quieres pillarlo dentro de otra palabra.",
      "<font face='Mono'>~dia</font> encuentra ME<b>DIA</b> MARKT"],
     ["<font face='Mono'>\"re:...\"</font>",
      "<b>Expresión regular</b>, para casos raros.",
      "<font face='Mono'>re:^abono</font>"],
     ["<font face='Mono'>\"_nota\"</font>",
      "Se <b>ignora</b>. Sirve para dejarte comentarios dentro del JSON.",
      "—"]],
    [ANCHO * 0.20, ANCHO * 0.44, ANCHO * 0.36])]
story += [Spacer(1, 8)]
story += [Paragraph("Qué se puede poner como categoría", S["h2"])]
story += [tabla(
    ["Valor", "Qué hace"],
    [["<font face='Mono'>\"Comida\"</font>",
      "Lo normal: casa y va a esa categoría."],
     ["<font face='Mono'>{\"+\": \"Ingresos\", \"-\": \"Ocio\"}</font>",
      "<b>Según el signo.</b> Un Bizum que <i>recibes</i> es un ingreso; uno que "
      "<i>envías</i>, un gasto. Con un solo texto para los dos, los recibidos "
      "restaban de Ocio y el mes salía barato sin motivo."],
     ["<font face='Mono'>{\"-\": \"Otros\"}</font>",
      "Solo un lado. Los movimientos del otro signo ignoran esta regla y siguen "
      "buscando más abajo."],
     ["<font face='Mono'>null</font>",
      "<b>Apaga</b> la regla. Sirve para desactivar una de la base sin editarla."]],
    [ANCHO * 0.34, ANCHO * 0.66])]
story += [Spacer(1, 5)]
story += [aviso(
    "Las devoluciones NO necesitan regla de signo",
    "Si te devuelven una compra del Mercadona, que ese abono reste de Comida es "
    "exactamente lo correcto. El signo solo hace falta cuando el importe positivo es "
    "un concepto <b>distinto</b> del negativo (Bizum recibido / enviado, prestación / "
    "cuota), no cuando es la devolución del mismo gasto.")]
story += [Spacer(1, 5)]
story += [Paragraph(
    "<b>Los Bizum de amigos que te devuelven una cena</b> entran como ingreso con la "
    "regla de fábrica. Si prefieres que resten de lo que gastaste, pon delante una "
    "regla con la palabra que usan tus amigos: con "
    "<font face='Mono' size='8.2'>\"=cena\": \"Ocio\"</font>, el Bizum que envías "
    "para pagar la cena suma a Ocio y el que te devuelven le resta, igual que una "
    "devolución. Si la cena la pagaste con tarjeta, Ocio puede quedar en negativo "
    "ese mes: es correcto.", S["pmini"])]
story += [Spacer(1, 8)]
story += [Paragraph("Añadir reglas", S["h2"])]
story += [codigo([
    '"decathlon": "Ocio",',
    '"=gym":      "Ocio",',
])]
story += [Spacer(1, 5)]
story += [Paragraph(
    "Si la categoría es <b>nueva</b>, declárala también en "
    "<font face='Mono' size='8.2'>categorias.json</font> (como gasto, ingreso o "
    "neutra): si no, las reglas que la usan se descartan y se avisa al ejecutar, "
    "porque no sumaría en ninguna columna del resumen; esos movimientos siguen con "
    "las demás reglas, como si la tuya no estuviera. "
    "Usa <font face='Mono' size='8.2'>=</font> siempre que la palabra sea corta "
    "(3-4 letras) o pueda aparecer dentro de otra. Sin ese marcador, "
    "<font face='Mono' size='8.2'>bar</font> se comería BARCELONA y "
    "<font face='Mono' size='8.2'>vida</font> se comería NAVIDAD.", S["pmini"])]
story += [EE]

story += [h1("Probar una regla sin reprocesar todo"), E]
story += [p("Para ver en qué categoría caería un concepto concreto:")]
story += [codigo([
    'python app/reglas.py "MEDIA MARKT ONLINE" "BAR LA ESQUINA"',
    '',
    'MEDIA MARKT ONLINE  ->  Otros                    [media markt · base]',
    'BAR LA ESQUINA      ->  Ocio                     [=bar · base]',
    '',
    'python app/reglas.py "BIZUM DE MARTA" 25',
    '',
    'BIZUM DE MARTA      25,00 €  ->  Ingresos                 [bizum · base]',
])]
story += [Spacer(1, 4)]
story += [Paragraph(
    "Si pones un número detrás de un concepto, se usa como su importe (puedes poner "
    "varios pares seguidos): es la forma de comprobar las "
    "reglas que dependen del signo. Las reglas que salen de la base aparecen marcadas "
    "con <font face='Mono' size='8.2'>· base</font>. Sin argumentos ejecuta una "
    "batería de casos trampa ya preparada. En Mac y Linux, escribe "
    "<font face='Mono' size='8.2'>python3</font> en vez de "
    "<font face='Mono' size='8.2'>python</font>.", S["pmini"])]
story += [EE]

story += [h1("exclude_patterns.json · qué se descarta"), E]
story += [p(
    "Lista de textos cuyos movimientos no deben contar. Usa la <b>misma sintaxis</b> "
    "que rules.json. Sirve sobre todo para el cargo mensual de la tarjeta, que si no "
    "contarías dos veces: una como recibo en la cuenta y otra como compras sueltas.")]
story += [codigo([
    '[',
    '  "pago recibo 77",',
    '  "tarj.crdto 77"',
    ']',
])]
story += [Spacer(1, 4)]
story += [Paragraph(
    "Las dos líneas del ejemplo son el <b>mismo pago visto desde los dos lados</b>: "
    "algunos bancos lo apuntan como cargo en la cuenta y también como abono, por "
    "el mismo importe, en el extracto de la tarjeta. Hay que excluir las dos: sin "
    "la primera, los gastos de la tarjeta cuentan dos veces; sin la segunda, el "
    "abono cuenta como un ingreso que no lo es.", S["pmini"])]
story += [Spacer(1, 4)]
story += [Paragraph(
    "El <font face='Mono' size='8.2'>77</font> del ejemplo son los dígitos con que "
    "tu banco identifica la tarjeta en el concepto del recibo. Mira tu extracto y "
    "copia los tuyos. El fichero que viene con el programa trae estas instrucciones "
    "dentro y ningún patrón activo: es lo primero que hay que configurar.", S["pmini"])]
story += [Spacer(1, 4)]
story += [Paragraph(
    "No hace falta buscarlas a ojo: al terminar, el script busca en la cuenta un "
    "cargo que cuadre con lo que suma la tarjeta ese mes y, en la tarjeta, un abono "
    "por el mismo importe que ese cargo, y propone las líneas que falten, listas "
    "para pegar aquí. Más fácil: en el menú del final, «Excluir el recibo de la "
    "tarjeta» las añade por ti; si no lo ha encontrado, escribes un trozo del "
    "concepto y te enseña qué excluiría antes de guardarlo. Lo que ya está "
    "excluido no lo vuelve a pedir. Con varias tarjetas, busca el recibo de cada "
    "una. Y si solo tienes tarjetas, sin extracto de la cuenta, no hay recibo que "
    "pueda contarse dos veces: ni avisa.", S["pmini"])]
story += [Spacer(1, 4)]
story += [Paragraph(
    "Lo descartado no se pierde: acaba en "
    "<font face='Mono' size='8.2'>movimientos_excluidos.xlsx</font> para que puedas "
    "comprobar que no se ha ido nada de más.", S["pmini"])]
story += [EE]

story += [h1("cuentas.json · varias cuentas o tarjetas"), E]
story += [p(
    "Solo hace falta si tienes <b>más de una cuenta o tarjeta del mismo tipo</b> (dos "
    "cuentas corrientes, o una tarjeta cada miembro de la pareja). Sin esto, un "
    "movimiento idéntico el mismo día en las dos se cuenta una sola vez, como si "
    "fuera el mismo: dos cafés de 2,60 €, uno en cada tarjeta, serían uno. Si ve dos "
    "ficheros del mismo tipo que cubren las mismas fechas sin parecerse, la "
    "herramienta avisa de que te hace falta.")]
story += [codigo([
    '{',
    '  "principal": "principal",',
    '  "ahorro": "ahorro"',
    '}',
])]
story += [Spacer(1, 4)]
story += [Paragraph(
    "La clave es un trozo del <b>nombre del fichero</b>, no de la descripción de un "
    "movimiento: con el ejemplo de arriba, nombra tus extractos de forma que se "
    "distingan (<font face='Mono' size='8.2'>principal_042026.xls</font>, "
    "<font face='Mono' size='8.2'>ahorro_042026.xls</font>...) y cada uno cae en su "
    "cuenta sola. Misma sintaxis que rules.json.", S["pmini"])]
story += [Spacer(1, 4)]
story += [Paragraph(
    "Vacío (como viene de fábrica), todos los ficheros cuentan como si fueran de la "
    "misma cuenta: es el comportamiento de siempre, y quien solo tiene una cuenta no "
    "nota ningún cambio.", S["pmini"])]
story += [Spacer(1, 5)]
story += [aviso(
    "Una vez declaradas, el nombre del fichero importa",
    "Cada descarga tiene que llevar en el nombre lo que identifica a su cuenta. Un "
    "fichero que no casa con ninguna (el «movimientos (1).xls» de volver a "
    "descargar) cuenta como una cuenta más. Si sus movimientos ya están en una de "
    "las declaradas, es otra descarga de ella con otro nombre: <b>no se lee</b>, para "
    "no contarlo dos veces, y se avisa de que lo renombres.")]

story += [h1("El histórico"), E]
story += [p(
    "<font face='Mono' size='8.6'>historico.xlsx</font> acumula todo lo que has ido "
    "procesando, ejecución tras ejecución. Puedes borrar de "
    "<font face='Mono' size='8.6'>entrada/</font> los extractos viejos: lo que ya "
    "entró, entrado se queda. Se abre por RESUMEN, y tiene además una hoja "
    "<font face='Mono' size='8.6'>_meta</font> con la versión que lo escribió, que "
    "no hace falta tocar:")]
story += [tabla(
    ["Hoja", "Qué contiene"],
    [["<font face='Mono'>RESUMEN</font>",
      "La matriz mes × categoría con los totales, el balance y el saldo de la "
      "cuenta. Debajo, tres gráficos: el Acumulado, los ingresos y gastos de cada "
      "mes, y el gasto medio al mes por categoría."],
     ["<font face='Mono'>CUENTAS</font>",
      "Solo si tienes dos o más cuentas o tarjetas declaradas en "
      "<font face='Mono'>cuentas.json</font>: lo que se gastó y lo que entró en "
      "cada una, mes a mes, y el saldo de cada cuenta al cerrar el mes. Las "
      "cuentas juntas suman lo mismo que RESUMEN; un fichero que no casa con "
      "ninguna sale como «(sin identificar)»."],
     ["<font face='Mono'>MOVIMIENTOS</font>",
      "Todos los movimientos, uno por fila, incluidos los excluidos (marcados en la "
      "columna <font face='Mono'>excluido</font>). La cabecera naranja señala la "
      "única columna que puedes escribir tú."]],
    [ANCHO * 0.26, ANCHO * 0.74])]
story += [Spacer(1, 7)]
story += [aviso(
    "Las categorías no se congelan",
    "El histórico guarda los movimientos en crudo y vuelve a clasificarlos <b>enteros</b> "
    "en cada ejecución. Es decir: cuando afines una regla, el cambio se aplica también "
    "hacia atrás, a meses de los que ya ni tengas el .xls. Por eso conviene no perder "
    "este fichero, y por eso da igual equivocarse con las reglas al principio. La "
    "única excepción es lo que escribas en <font face='Mono'>categoria_manual</font>: "
    "eso sí se respeta.",
    ACENTO, ACENTO_CL)]
story += [Spacer(1, 5)]
story += [Paragraph(
    "Por lo mismo, el fichero se <b>regenera entero</b>: una hoja que le añadas a "
    "mano no llega a la siguiente ejecución (se avisa, y queda en la copia de "
    "<font face='Mono' size='8.2'>datos/copias/</font>). Para tus cálculos, usa un "
    "libro aparte, o la sincronización.", S["pmini"])]
story += [EE]

story += [h1("Corregir un movimiento suelto"), E]
story += [p(
    "Las reglas leen el texto del concepto, no la fecha, así que no pueden distinguir "
    "el <font face='Mono' size='8.6'>BIZUM A MARTA</font> que un mes es la parte del "
    "alquiler y otro una cena. Para esos casos está la columna "
    "<b>categoria_manual</b> de la hoja MOVIMIENTOS.")]
story += [pasos([
    "Abre <font face='Mono' size='9'>datos/historico.xlsx</font>, hoja "
    "<b>MOVIMIENTOS</b>, y busca la línea",
    "En la columna <b>categoria_manual</b> (cabecera naranja) escribe la categoría "
    "que quieras, tal cual aparece en "
    "<font face='Mono' size='9'>categorias.json</font>",
    "Guarda, cierra, y vuelve a ejecutar",
])]
story += [Spacer(1, 7)]
story += [p(
    "Esa línea pasa a esa categoría y ahí se queda. La corrección se conserva entre "
    "ejecuciones, sobrevive a los extractos nuevos y manda sobre cualquier regla. En "
    "la columna <font face='Mono' size='8.6'>regla</font> verás "
    "<font face='Mono' size='8.6'>(manual)</font>, para que luego sepas por qué esa "
    "línea está donde está.")]
story += [tabla(
    ["Qué escribes", "Qué hace"],
    [["Una categoría", "Esa línea pasa a esa categoría, pase lo que pase con las reglas."],
     ["<font face='Mono'>(excluido)</font>",
      "Saca esa línea de los totales, aunque ningún patrón de exclusión la pille."],
     ["Nada (vacío)", "Comportamiento normal: mandan las reglas."],
     ["Algo mal escrito",
      "No se aplica: manda la regla y sale un aviso al ejecutar. Es a propósito: "
      "una categoría que no esté en <font face='Mono'>categorias.json</font> no "
      "sumaría en ninguna columna del resumen, y el total te descuadraría sin que "
      "nada lo dijera."]],
    [ANCHO * 0.28, ANCHO * 0.72])]
story += [Spacer(1, 7)]
story += [aviso(
    "Escribe solo en esa columna",
    "El resto de la hoja se regenera en cada ejecución y perderías el cambio. Si te "
    "equivocas con el nombre de una categoría, se avisa por pantalla. Y por si acaso, "
    "cada vez que el histórico cambia se guarda antes una copia en "
    "<font face='Mono'>datos/copias/</font>.")]
story += [EE]

story += [h1("categorias.json · las columnas del resumen"), E]
story += [p(
    "Declara qué categorías espera tu hoja y qué papel juega cada una. Sirve para dos "
    "cosas: construir la hoja RESUMEN, y avisarte cuando "
    "<font face='Mono' size='8.6'>rules.json</font> y el resumen dejan de estar "
    "sincronizados.")]
story += [tabla(
    ["Bloque", "Qué hace"],
    [["<font face='Mono'>gastos</font>",
      "Una columna cada una. <b>Total Gastos</b> es su suma."],
     ["<font face='Mono'>ingresos</font>", "Suman en la columna <b>Ingresos</b>."],
     ["<font face='Mono'>neutras</font>",
      "Ni gasto ni ingreso: no entran en ningún total. Aquí van los traspasos entre "
      "tus propias cuentas, que no son dinero que salga ni entre."],
     ["<font face='Mono'>columna_mes</font>",
      "<font face='Mono'>mes</font> o <font face='Mono'>mes_ajustado</font>: con cuál "
      "se agrupa el resumen."],
     ["<font face='Mono'>etiquetas</font>",
      "<i>Opcional.</i> Nombre interno → texto de columna, para cambiar cómo se ve "
      "una columna sin arriesgar el cuadre letra-por-letra con rules.json. Dos "
      "columnas no pueden acabar con el mismo nombre: la etiqueta que choque se "
      "ignora y se avisa. Para juntar dos categorías, lleva sus reglas a una."],
     ["<font face='Mono'>orden_resumen</font>",
      "<i>Opcional.</i> Qué columnas salen y en qué orden, incluidas las de sistema "
      "(Balance, Acumulado...), normalmente fijas al final. Sin él, el orden de "
      "siempre."],
     ["<font face='Mono'>desglosar_ingresos</font>",
      "<i>Opcional.</i> Con <font face='Mono'>true</font>, cada categoría de ingreso "
      "tiene su columna, además del total <b>Ingresos</b>. La que se llama "
      "«Ingresos» sale como <b>Otros ingresos</b>, y así se la nombra en "
      "etiquetas y orden_resumen."],
     ["<font face='Mono'>importar_categorias</font>",
      "<i>Opcional.</i> Para quien viene de otra app de finanzas y trae su export "
      "con una columna de categoría: ver «Si vienes de otra app», justo debajo."]],
    [ANCHO * 0.24, ANCHO * 0.76])]
story += [Spacer(1, 7)]
story += [Paragraph("Si vienes de otra app", S["h2"])]
story += [p(
    "Su export (fecha, concepto, importe) se lee como cualquier extracto: déjalo "
    "en <font face='Mono' size='8.6'>entrada/</font> junto a los del banco, y "
    "lo que se solape no se cuenta dos veces. Si además trae una columna de "
    "categoría y quieres conservar lo que ya tenías clasificado, dilo aquí:")]
story += [codigo([
    '"importar_categorias": {',
    '  "fichero": "export",',
    '  "traducir": {"Supermercado": "Comida", "Vivienda": "Piso"}',
    '}',
])]
story += [Spacer(1, 4)]
story += [Paragraph(
    "<font face='Mono' size='8.2'>fichero</font> es un trozo del nombre del "
    "export (como en cuentas.json): solo se usa la categoría de ese fichero, "
    "porque hay bancos que traen la suya y no debe pisar tus reglas. Cada una "
    "se traduce a una tuya; las que ya se llaman igual valen tal cual. Lo "
    "traducido va a <font face='Mono' size='8.2'>categoria_manual</font>, donde "
    "puedes corregirlo, y de lo que no sepa traducir se avisa.", S["pmini"])]
story += [Spacer(1, 7)]
story += [aviso(
    "El fallo que esto evita",
    "Si el texto de una categoría en <font face='Mono'>rules.json</font> no coincide "
    "<b>letra por letra</b> con el del resumen, la columna suma 0 y no protesta nadie. "
    "«Higiene» y «Limpieza/Higiene» son distintas; «Fibra/movil» y «Fibra/móvil» "
    "también. Al arrancar se comparan los dos ficheros y se avisa de las que sobran, "
    "las que faltan y las que solo se diferencian en una tilde o una mayúscula.")]
story += [Spacer(1, 7)]
story += [Paragraph(
    "<b>Renombrar una categoría tiene un precio:</b> las reglas de la base que "
    "apuntaban al nombre viejo se descartan (lo dice al arrancar, con cuántas), y "
    "esos comercios dejan de clasificarse solos. Si solo quieres que la columna se "
    "vea con otro nombre, usa <font face='Mono' size='8.2'>etiquetas</font>. Si "
    "quieres juntar dos de fábrica en una tuya (Luz/Agua y Fibra/movil en "
    "Facturas), declara la tuya y añade "
    "<font face='Mono' size='8.2'>\"equivalencias\": {\"Luz/Agua\": "
    "\"Facturas\", \"Fibra/movil\": \"Facturas\"}</font>: las reglas de la "
    "base que iban a las viejas van a la tuya, y no se pierde ninguna. De "
    "fábrica hay también una categoría <b>Impuestos</b> (pagos a Hacienda y la cuota "
    "de autónomos); si no la quieres, quítala y esos cargos irán a Otros.",
    S["pmini"])]
story += [Spacer(1, 5)]
story += [Paragraph(
    "Por eso los nombres de categoría van <b>sin tildes</b>: así no hay dos maneras de "
    "escribir lo mismo. Y ojo, lo que se declara aquí es el <b>criterio</b> de la "
    "fórmula, no el rótulo de la columna: en tu hoja puedes titularla «Gemeliers» "
    "mientras la fórmula siga buscando <font face='Mono' size='8.2'>Hijos</font>.",
    S["pmini"])]
story += [EE]

story += [h1("Cómo se calcula el resumen"), E]
story += [codigo([
    "Total Gastos      = suma de las categorías de gasto",
    "Ingresos          = suma de las categorías de ingreso",
    "Balance           = Ingresos - Total Gastos",
    "",
    "Fuera del balance = lo que movió la cuenta sin ser gasto ni ingreso",
    "Acumulado         = Acumulado del mes anterior + Balance",
    "                    + Fuera del balance",
])]
story += [Spacer(1, 5)]
story += [Paragraph(
    "<b>Balance</b> es el resultado del mes por sí solo: lo que ha entrado menos lo "
    "que has gastado. <b>Acumulado</b> es el <b>saldo real de tu cuenta</b> al cerrar "
    "el mes, el mismo que te da el banco. <b>Fuera del balance</b> explica la "
    "diferencia entre los dos: traspasos a otras cuentas tuyas, lo que has excluido "
    "(el recibo de la tarjeta, por ejemplo) y las compras con tarjeta que el banco "
    "todavía no ha cargado en la cuenta.", S["pmini"])]
story += [Spacer(1, 5)]
story += [Paragraph(
    "Los gastos se muestran en positivo cambiándoles el signo, no con valor absoluto. "
    "La diferencia importa cuando una categoría acaba el mes en positivo por una "
    "devolución: sale como negativa, en vez de disfrazarse de gasto.", S["pmini"])]
story += [Spacer(1, 5)]
story += [aviso(
    "De dónde parte el Acumulado",
    "Si tu extracto de cuenta trae columna de saldo, el Acumulado del primer mes no "
    "empieza en 0: empieza en el saldo real que tenía la cuenta antes de tu primer "
    "movimiento. Se detecta solo y se avisa por pantalla de qué saldo ha usado. "
    "Después comprueba día a día que el saldo calculado coincide con el del "
    "extracto: si no, te dice en qué fecha deja de cuadrar y por cuánto (casi "
    "siempre falta un extracto entre medias). Sin esa columna empieza en 0 y "
    "<b>no es tu saldo</b>, sino lo que ha variado la cuenta: se avisa, y la pantalla "
    "y el gráfico lo llaman «desde el primer movimiento». Si solo subes extractos de "
    "tarjeta es la suma de los Balances. Con más de una cuenta declarada en "
    "cuentas.json, es la suma de todas.",
    ACENTO, ACENTO_CL)]
story += [EE]

story += [h1("Ajuste de mes · mes_contable.json"), E]
story += [p(
    "Una nómina o una prestación que entra el día 1, 2 o 3 corresponde en realidad al "
    "mes anterior: es con lo que has vivido ese mes. Cuando eso pasa, la columna "
    "<b>mes_ajustado</b> retrocede un mes y la columna <b>mes</b> conserva el valor "
    "real.")]
story += [tabla(
    ["fecha", "descripcion", "importe", "mes", "mes_ajustado"],
    [["02/04/2026", "NOMINA EMPRESA SL", "+2.450,00", "2026-04", "<b>2026-03</b>"],
     ["01/05/2026", "MUTUA PRESTACION", "+1.180,45", "2026-05", "<b>2026-04</b>"],
     ["02/05/2026", "RECIBO MUTUA", "−95,00", "2026-05", "2026-05"],
     ["05/04/2026", "COMPRA MERCADONA", "−62,35", "2026-04", "2026-04"]],
    [ANCHO * 0.15, ANCHO * 0.31, ANCHO * 0.18, ANCHO * 0.18, ANCHO * 0.18],
    ["celdaM", "celda", "celdaM", "celdaM", "celdaM"])]
story += [Spacer(1, 5)]
story += [Paragraph(
    "Fíjate en las dos líneas de la mutua: la <b>prestación que cobras</b> sí se va al "
    "mes anterior, pero el <b>recibo que pagas</b> no. Un gasto pertenece al mes en que "
    "se paga; solo se mueven los ingresos.", S["pmini"])]
story += [Spacer(1, 7)]
# el bloque entero junto: si no, la frase final se quedaba sola arriba de
# la página siguiente
story += [KeepTogether([Paragraph("Cómo se configura", S["h2"]), codigo([
    '{',
    '  "dias": 3,                      ← 0 lo desactiva del todo',
    '  "palabras": ["nomina", "mutua"],',
    '  "solo_ingresos": true           ← déjalo en true',
    '}',
]), Spacer(1, 5), Paragraph(
    "Las palabras van en minúsculas y sin tildes. Si dejas "
    "<font face='Mono' size='8.2'>solo_ingresos</font> en "
    "<font face='Mono' size='8.2'>false</font>, la cuota que le pagas a la mutua se "
    "iría al mes anterior junto con la prestación que cobras de ella, y son dos cosas "
    "distintas.", S["pmini"]), Spacer(1, 5), Paragraph(
    "Para cuadrar tus meses usa siempre <b>mes_ajustado</b>, no <b>mes</b>.", S["pmini"])])]
story += [EE]

story += [h1("Sincronizar con tu contabilidad"), E]
story += [p(
    "En vez de copiar y pegar cada mes, la herramienta puede escribir los movimientos "
    "directamente en tu fichero. Se configura en "
    "<font face='Mono' size='8.6'>sincronizar.json</font>; si ese fichero no existe o "
    "dejas <font face='Mono' size='8.6'>archivo</font> vacío, no se sincroniza nada y "
    "todo funciona como antes. Una ruta sin carpeta (solo el nombre) se busca en la "
    "carpeta de la herramienta, la que tiene <font face='Mono' size='8.6'>entrada/</font> "
    "y <font face='Mono' size='8.6'>ajustes/</font>, no dentro de "
    "<font face='Mono' size='8.6'>ajustes/</font>.")]
story += [codigo([
    '{',
    '  "archivo": "contabilidad.xlsx",',
    '  "hoja": "MOVIMIENTOS",',
    '  "modo": "tabla",',
    '  "columnas": {},',
    '  "fila_inicial": 1,',
    '  "columna_inicial": 1,',
    '  "incluir_excluidos": false,',
    '  "copias_de_seguridad": 10',
    '}',
])]
story += [Spacer(1, 7)]
story += [tabla(
    ["modo", "Para quién", "Qué hace"],
    [["<font face='Mono'>tabla</font>",
      "Quien monta sus fórmulas sobre una hoja aparte.",
      "La hoja es de la herramienta: se reescribe <b>entera</b> en cada ejecución, "
      "siempre al día con tus reglas."],
     ["<font face='Mono'>añadir</font>",
      "Quien lleva años con su propia hoja y solo quiere dejar de copiar y pegar.",
      "La hoja es <b>tuya</b>: solo se añaden debajo los movimientos que falten "
      "(los reconoce por fecha, concepto e importe, también los que tecleaste a "
      "mano). Lo que ya hay no se toca nunca, ni se reclasifica si luego cambias "
      "una regla. Si borras una fila que vino del banco, vuelve."]],
    [ANCHO * 0.14, ANCHO * 0.36, ANCHO * 0.50])]
story += [Spacer(1, 5)]
story += [Paragraph(
    "<font face='Mono' size='8.2'>columnas</font> dice qué se escribe y con qué "
    "cabecera, en su orden; vacío, las siete de siempre. En modo añadir, pon tus "
    "cabeceras tal cual: "
    "<font face='Mono' size='8.2'>{\"Fecha\": \"fecha\", \"Concepto\": "
    "\"descripcion\", \"Importe\": \"importe\", \"Categoría\": "
    "\"categoria\"}</font>. Fecha, concepto e importe no pueden faltar. En modo "
    "añadir, las filas nuevas copian el formato de la última que ya tenías, lo "
    "que escribas a mano (una nota, una categoría cambiada) se queda donde está "
    "porque nada se mueve, y se avisa si entra una categoría que tu hoja no "
    "usaba (tus totales no la recogerían).", S["pmini"])]
story += [Spacer(1, 5)]
story += [Paragraph(
    "<b>La primera vez, sobre una copia</b> de tu fichero: pon su nombre en "
    "<font face='Mono' size='8.2'>archivo</font>, ejecuta y ábrela. Cuando veas "
    "que sale lo que esperas, cambia al fichero de verdad.", S["pmini"])]
story += [Spacer(1, 7)]
story += [aviso(
    "En modo tabla, la hoja es de la herramienta",
    "En cada ejecución se vuelca la tabla <b>entera</b> a partir de la esquina "
    "(<font face='Mono'>fila_inicial</font>, <font face='Mono'>columna_inicial</font>), "
    "con estas columnas: fecha, descripcion, importe, tipo, mes, mes_ajustado y "
    "categoria (o las de <font face='Mono'>columnas</font>). Usa una hoja vacía "
    "para ella y haz que tus fórmulas tiren de ahí (por ejemplo "
    "<font face='Mono'>=SUMIF(Banco!G:G;\"Comida\";Banco!C:C)</font>). Si en la "
    "esquina hay una tabla tuya con otras cabeceras, no se escribe: para tu hoja "
    "de siempre, usa el modo añadir.")]
story += [Spacer(1, 7)]
story += [Paragraph("Qué se conserva de tu libro", S["h2"])]
story += [p(
    "Solo se toca la hoja de datos que indiques. Está comprobado que sobreviven las "
    "fórmulas, el formato condicional, las celdas combinadas, los colores, los formatos "
    "de moneda, los anchos de columna, los paneles inmovilizados, la validación de "
    "datos, los gráficos y las imágenes.")]
story += [aviso(
    "Tablas dinámicas y macros sí se perderían",
    "Son lo único que no sobrevive a una reescritura. Por eso, antes de tocar nada, se "
    "inspecciona tu libro y <b>se cancela la escritura</b> si encuentra alguna de las "
    "dos. Tu fichero se queda como estaba y sigues teniendo "
    "<font face='Mono'>movimientos_limpios.xlsx</font> para copiar y pegar.")]
story += [Spacer(1, 7)]
story += [Paragraph("Los seguros", S["h2"])]
story += [tabla(
    ["Si pasa esto...", "...ocurre esto"],
    [["Apuntas sin querer a la hoja de totales",
      "Se detecta que tiene fórmulas y no se escribe. La hoja de destino debe ser solo "
      "datos."],
     ["El nombre de la hoja está mal escrito",
      "Se cancela y se listan las hojas que sí existen."],
     ["El libro está abierto en OnlyOffice, LibreOffice o Excel",
      "Se avisa de que lo guardes y lo cierres, y no se escribe: al guardar tú "
      "después, se perdería lo volcado."],
     ["En la esquina hay datos tuyos con otras cabeceras",
      "Modo tabla: no se escribe, para no borrarlos. Modo añadir: si la cabecera "
      "no es la de <font face='Mono'>columnas</font>, no se escribe, para no poner "
      "cada dato en la columna que no es."],
     ["Tienes notas tuyas al lado de los movimientos",
      "Se recolocan junto a su movimiento aunque entren otros por medio. Si una ya no "
      "tiene movimiento al que acompañar, se queda donde estaba y se avisa."],
     ["El histórico encoge respecto a la vez anterior",
      "Las filas sobrantes se eliminan, no quedan restos debajo."],
     ["Cualquier otro fallo",
      "Se hace una copia con fecha en <font face='Mono'>datos/copias/</font> ANTES de cada "
      "escritura. Se guardan las 10 últimas. Si no hay nada nuevo, el fichero no se "
      "toca y no se gasta ninguna."]],
    [ANCHO * 0.40, ANCHO * 0.60])]
story += [EE]

story += [h1("Uso en Excel"), E]
story += [p(
    "La hoja RESUMEN ya trae las sumas por mes y categoría. Si prefieres montar "
    "las tuyas en tu propio Excel (pegando <font face='Mono' size='8.6'>"
    "movimientos_limpios.xlsx</font> en las columnas A-G, o con la "
    "sincronización), las columnas están siempre en el mismo sitio, así que tus "
    "fórmulas no se rompen de una versión a otra.")]
story += [codigo(
    '=SUMAR.SI.CONJUNTO(MOVIMIENTOS!C:C;\n'
    '                   MOVIMIENTOS!G:G; "Comida";\n'
    '                   MOVIMIENTOS!F:F; "2026-04")')]
story += [Spacer(1, 4)]
story += [Paragraph(
    "C = importe · G = categoria · F = mes_ajustado. Los gastos salen en "
    "negativo: ponle un <font face='Mono' size='8.2'>-</font> delante si los "
    "quieres en positivo (no uses <font face='Mono' size='8.2'>ABS()</font>, que "
    "hace pasar las devoluciones por gasto). Si Excel te da error en los separadores, cambia "
    "<font face='Mono' size='8.2'>;</font> por <font face='Mono' size='8.2'>,</font> "
    "según tu configuración regional.", S["pmini"])]
story += [Spacer(1, 7)]
story += [aviso(
    "Cuidado con E:E y F:F",
    "Son dos columnas distintas y se parecen mucho: <b>E</b> es el mes real y <b>F</b> "
    "es el mes contable. Si el criterio del mes apunta a <b>E</b>, el ajuste de nóminas "
    "y prestaciones no se aplica y esos ingresos cuentan en el mes en que entraron. "
    "Para que el ajuste sirva de algo, la fórmula tiene que filtrar por <b>F</b>.")]
story += [Spacer(1, 7)]
story += [Paragraph("Totales de un trimestre", S["h2"])]
story += [p(
    "RESUMEN va por meses. Para un trimestre (lo que pide el gestor), suma sus "
    "tres filas: con julio, agosto y septiembre en las filas 8 a 10, "
    "<font face='Mono' size='8.6'>=SUMA(B8:B10)</font> debajo de la columna que "
    "quieras. En tu propio libro, suma las tres fórmulas de arriba, una por mes.")]
story += [Spacer(1, 7)]
story += [Paragraph("Si eres autónomo", S["h2"])]
story += [p(
    "Una receta de partida, para separar lo que facturas del resto y lo que "
    "gastas en el negocio. En <font face='Mono' size='8.6'>categorias.json</font>: "
    "<b>Facturas</b> en <font face='Mono' size='8.6'>ingresos</font> (junto a "
    "Ingresos), <b>Material</b> y <b>Gasoil</b> en "
    "<font face='Mono' size='8.6'>gastos</font>, y "
    "<font face='Mono' size='8.6'>\"desglosar_ingresos\": true</font> para que "
    "Facturas tenga su columna. <b>Impuestos</b> ya viene de fábrica: los "
    "modelos de Hacienda y la cuota de autónomos van ahí solos, y lo que te "
    "devuelve Hacienda cuenta como ingreso. En "
    "<font face='Mono' size='8.6'>rules.json</font>:")]
story += [codigo([
    '"transf. de": {"+": "Facturas"},',
    '"leroy merlin": "Material",',
    '"bricomart":    "Material",',
    '"repsol":       "Gasoil",',
])]
story += [Spacer(1, 4)]
story += [Paragraph(
    "Con el <font face='Mono' size='8.2'>+</font>, solo lo que entra por "
    "transferencia es factura: una transferencia que haces tú sigue buscando "
    "regla más abajo. Las devoluciones de material restan de Material solas. "
    "Si tienes una cuenta para el negocio y otra personal, decláralas en "
    "<font face='Mono' size='8.2'>cuentas.json</font> y tendrás cada una por "
    "separado en la hoja CUENTAS.", S["pmini"])]
story += [EE]

story += [h1("Dárselo a otra persona"), E]
story += [aviso(
    "No comprimas la carpeta",
    "Le estarías dando tu <font face='Mono'>historico.xlsx</font>, tus copias y, "
    "sobre todo, tu <font face='Mono'>rules.json</font>, que es un retrato bastante "
    "fino de tu vida: el colegio de los críos, el veterinario, el gimnasio, el "
    "casero, la mutua. Y tu <font face='Mono'>exclude_patterns.json</font> lleva los "
    "dígitos de tu tarjeta.")]
story += [Spacer(1, 6)]
story += [p(
    "Usa <font face='Mono' size='9'>exportar.bat</font> (en Mac, "
    "<font face='Mono' size='9'>exportar.command</font>; en Linux, "
    "<font face='Mono' size='9'>exportar.sh</font>). Genera un ZIP con el "
    "programa, los lanzadores, esta guía y unas reglas de partida genéricas. Nada "
    "más: no funciona quitando cosas de la carpeta, sino al revés, copiando solo lo "
    "que está autorizado, para que un fichero nuevo no se cuele por olvido.")]
story += [Spacer(1, 4)]
story += [Paragraph(
    "Quien lo reciba, al ejecutarlo por primera vez, se creará su propia "
    "configuración a partir de las plantillas. Lo primero que tendrá que hacer es "
    "poner en <font face='Mono' size='8.2'>exclude_patterns.json</font> el recibo con "
    "que su cuenta paga su tarjeta.", S["pmini"])]
story += [EE]

story += [h1("Versiones"), E]
story += [p(
    "La versión sale en la primera línea al ejecutar, y queda grabada en la hoja "
    "<font face='Mono' size='9'>_meta</font> de "
    "<font face='Mono' size='9'>historico.xlsx</font> junto con la fecha. Es lo "
    "primero que hace falta saber cuando algo no cuadra. "
    "<font face='Mono' size='9'>CHANGELOG.md</font> cuenta qué cambió en cada una.")]
story += [Spacer(1, 4)]
story += [Paragraph(
    "Si abres un histórico escrito por una versión <b>más nueva</b> que la que "
    "tienes, el programa se planta en vez de escribirlo: podría tener columnas que "
    "tu versión no conoce y se perderían. Actualiza, o restaura una copia de "
    "<font face='Mono' size='8.2'>datos/copias/</font>.", S["pmini"])]
story += [EE]

story += [h1("Cuando algo no sale"), E]
story += [tabla(
    ["Síntoma", "Qué hacer"],
    [["<i>«Hay ficheros abiertos»</i>",
      "Tienes el histórico abierto en Excel u OnlyOffice. Si has escrito algo, "
      "guárdalo, cierra el archivo y pulsa Intro: sigue solo. Con <b>C</b> lo dejas "
      "abierto y el resultado va a una copia con fecha al lado, pero el histórico de "
      "verdad no se actualiza hasta que lo ejecutes con él cerrado."],
     ["<i>«La carpeta entrada/ está vacía»</i>",
      "Los ficheros que empiezan por <font face='Mono'>_</font>, "
      "<font face='Mono'>.</font> o <font face='Mono'>~$</font> se ignoran a propósito, "
      "y también los que no tengan una extensión conocida. Comprueba que lo que has "
      "soltado no es un <font face='Mono'>.zip</font> ni un <font face='Mono'>.pdf</font>."],
     ["<i>«no he podido leer ningún extracto de entrada/»</i>",
      "Hay ficheros, pero ninguno se ha podido leer. El motivo de cada uno sale en los "
      "avisos, justo encima."],
     ["Falta un fichero entero",
      "Mira el listado que sale por pantalla: si un fichero no aparece ahí, no se ha "
      "leído. Si aparece con un aviso, el aviso dice por qué."],
     ["Un extracto se ha tomado por el tipo que no era",
      "Por pantalla se indica el motivo de cada decisión. Si tu banco usa nombres "
      "raros, añádelos a <font face='Mono'>PISTAS_CUENTA_COL</font> o "
      "<font face='Mono'>PISTAS_TARJETA_COL</font> en <font face='Mono'>bank_io.py</font>. "
      "Como apaño rápido, mete la palabra «tarjeta» en el nombre del fichero."],
     ["<i>«hace falta la librería xlrd»</i>",
      "Vuelve a lanzar el instalador: la instala en el entorno de la herramienta."],
     ["<i>«no encuentro las columnas de fecha, concepto e importe»</i>",
      "Puede que no sea un extracto. Si lo es, tu banco usa nombres de columna que "
      "no están mapeados: ejecuta el diagnóstico (abajo) y añade el nombre a "
      "<font face='Mono'>ALIAS_COLUMNAS</font> en "
      "<font face='Mono'>bank_io.py</font>."],
     ["<i>«tiene un error de formato en la línea…»</i>",
      "Al editar un JSON de <font face='Mono'>ajustes/</font> falta o sobra una coma, "
      "o hay unas comillas sin cerrar. El mensaje dice qué fichero y qué línea. "
      "Corrígelo y escribe <b>R</b> para volver a probar (ver «Cómo editar los "
      "ajustes»)."],
     ["Demasiadas filas en «Otros»",
      "El script agrupa al final los conceptos sin regla por palabra común, de "
      "mayor a menor importe, con una línea lista para pegar en "
      "<font face='Mono'>rules.json</font>. Más fácil: en el menú del final, "
      "<b>Clasificar lo que falta</b> te pregunta la categoría de cada grupo y "
      "escribe la regla por ti."],
     ["Un movimiento cae en la categoría equivocada",
      "Mira la columna <b>K (regla)</b>: te dice exactamente qué clave lo clasificó. "
      "O bien la afinas con <font face='Mono'>=</font>, o la mueves de sitio en el "
      "JSON, porque gana la primera que casa."],
     ["Una categoría suma 0 € en el resumen",
      "El texto del criterio de la fórmula tiene que coincidir <b>exactamente</b> con "
      "la categoría de <font face='Mono'>rules.json</font>, tilde incluida. "
      "«Higiene» y «Limpieza/Higiene» no son lo mismo."]],
    [ANCHO * 0.34, ANCHO * 0.66])]
story += [EE]

story += [h1("Diagnóstico de un fichero"), E]
story += [p("Enseña qué formato es realmente, dónde está la cabecera y qué columnas ha "
            "reconocido. No modifica nada:")]
story += [codigo([
    "app\\.venv\\Scripts\\python app\\bank_io.py entrada\\movimientos.xls   (Windows)",
    "app/.venv/bin/python app/bank_io.py entrada/movimientos.xls   (Mac, Linux)",
])]

# --------------------------------------------- agrupar secciones
UMBRAL = 340   # pt: por encima de esto, la sección puede partirse


def _alto(flowables):
    total = 0
    for f in flowables:
        try:
            total += f.wrap(ANCHO, 100000)[1]
        except Exception:
            total += 20
    return total


def _cerrar(grupo, salida):
    """Secciones cortas: enteras. Largas: solo el encabezado pegado a su entradilla."""
    if not grupo:
        return
    if len(grupo) == 1:
        salida.append(grupo[0])
    elif _alto(grupo) <= UMBRAL:
        salida.append(KeepTogether(grupo))
    else:
        salida.append(KeepTogether(grupo[:3]))
        salida.extend(grupo[3:])


def agrupar(story):
    """Cada h1 abre una sección."""
    salida, grupo = [], []
    for f in story:
        if getattr(f, "_h1", False):
            _cerrar(grupo, salida)
            grupo = [f]
        elif grupo:
            grupo.append(f)
        else:
            salida.append(f)
    _cerrar(grupo, salida)
    return salida


story = agrupar(story)

# ---------------------------------------------------------------- build
# La guía se escribe siempre al lado de este script, no en el directorio
# actual: así funciona igual desde la terminal que con doble clic.
# La guía se publica en la raíz del proyecto, al lado del LEEME.
SALIDA = str(Path(__file__).resolve().parent.parent / "GUIA.pdf")

doc = BaseDocTemplate(SALIDA, pagesize=A4,
                      leftMargin=20 * mm, rightMargin=20 * mm,
                      topMargin=20 * mm, bottomMargin=18 * mm,
                      title="Movimientos bancarios · guía de uso",
                      author="", subject="Guía de uso")
frame = Frame(doc.leftMargin, doc.bottomMargin, ANCHO,
              A4[1] - 20 * mm - 18 * mm, id="cuerpo",
              leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
doc.addPageTemplates([PageTemplate(id="normal", frames=[frame], onPage=decorar)])
doc.build(story)
print(f"GUIA.pdf generada en {SALIDA}")
