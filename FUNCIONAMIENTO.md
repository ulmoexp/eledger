# Cómo funciona por dentro

Documentación para quien mantiene la herramienta. No es la guía de uso
(`GUIA.pdf` y la web cuentan cómo se usa) ni una explicación del código
(`TRASPASO.md` es para eso). Es la respuesta a "¿qué hacía exactamente la
herramienta cuando...?", con el detalle suficiente para no tener que abrir
el código para acordarse.

Si algo de aquí deja de ser verdad, se corrige aquí en el mismo cambio que
lo cambia.

---

## 1. Las ideas que lo gobiernan todo

- **Todo es local.** Ni una conexión de red, en ningún momento. Lee ficheros
  de una carpeta y escribe ficheros en otra. No hay cuenta, ni servidor, ni
  telemetría. Es la promesa central del producto, no una característica más.
- **El histórico guarda los movimientos en crudo y la clasificación se
  recalcula entera en cada ejecución.** Nada queda "congelado" con la
  categoría que tenía el día que entró: si cambias una regla, todo el
  histórico hacia atrás se reclasifica solo, sin volver a descargar nada.
- **Mejor callarse que equivocarse.** Todo lo que la herramienta *propone*
  (una regla, una exclusión, un cargo recurrente) solo aparece cuando está
  razonablemente segura. Si duda, no dice nada o pide que lo mires a mano.
- **Avisar en vez de romper.** Una configuración mal escrita produce un aviso
  por pantalla y la ejecución sigue. Solo se planta cuando seguir podría
  destruir datos (ver el apartado 8).
- **Nada se pierde en silencio.** El fallo más peligroso de una herramienta
  así es un movimiento que desaparece de los totales sin que nadie lo note.
  Cada vía por la que eso podría pasar tiene un cerrojo (apartado 8).

---

## 2. Las carpetas

| Carpeta | Qué contiene | Quién la escribe |
|---|---|---|
| `entrada/` | Los extractos tal cual se bajan del banco. | El usuario. La herramienta solo la lee; nunca borra nada de aquí. |
| `salida/` | Dos Excel regenerados en cada ejecución. | La herramienta. Borrable sin miedo. |
| `datos/` | `historico.xlsx` y `copias/` (copias de seguridad). | La herramienta. **Es lo único insustituible.** |
| `ajustes/` | Los ficheros JSON de configuración del usuario. | El usuario. La herramienta solo crea los que falten. |
| `app/` | El programa, la base de reglas, las plantillas y el número de versión. | Nadie en uso normal. Se reemplaza entero al actualizar. |

**Actualizar = reemplazar `app/` y `GUIA.pdf`.** Las otras cuatro carpetas no
se tocan jamás. Todo el diseño de carpetas existe para que esa frase sea
cierta.

Las rutas se calculan siempre desde la ubicación del propio programa, no
desde donde esté abierta la consola: da igual cómo se lance, escribe siempre
en su propia carpeta. En el `.exe` compilado, las carpetas del usuario van
junto al `.exe`, no en la carpeta temporal donde este se descomprime.

---

## 3. Una ejecución, paso a paso

Esto es lo que ocurre, en este orden, cada vez que se hace doble clic en
`ejecutar`.

### 3.1 Preparar la carpeta

1. **Crea las carpetas que falten** (`entrada/`, `salida/`, `datos/`,
   `datos/copias/`, `ajustes/`).
2. **Migración desde la versión antigua**, si hace falta. La primera versión
   tenía todo suelto en una sola carpeta. Si encuentra ficheros de entonces
   (histórico, reglas, etc.) sueltos en la raíz, hace una copia de todo en
   `datos/copias/antes_de_migrar_<fecha>/` y los mueve a su sitio nuevo. Si
   en el sitio nuevo ya existe un fichero con ese nombre, **no pisa nada**:
   deja el viejo donde está y avisa. También avisa (sin borrarlo) si queda
   código antiguo suelto en la raíz.
3. **Siembra la configuración.** Cada JSON de `ajustes/` que no exista se
   copia desde las plantillas de `app/`. Nunca sobrescribe uno existente.
   Un caso especial: si esto es una actualización (ya había histórico) y el
   fichero del mes contable se acaba de crear, se rellena con las palabras
   que antes venían fijas en el programa, para que los totales de quien
   actualiza no cambien sin avisar.
4. **Carga la configuración** y enseña la versión y cuántas reglas hay
   (propias y de la base, y cuáles están apagadas o descartadas).
5. **Comprueba que las categorías cuadran** entre `rules.json` y
   `categorias.json` (apartado 8) y avisa de lo que no cuadre.

### 3.2 Leer los extractos

**Qué ficheros se leen.** Todos los de `entrada/` con una extensión conocida
(`.xls`, `.xlsx`, `.xlsm`, `.csv`, `.txt`, `.tsv`, `.ods`, `.htm`, `.html`).
Se ignoran los que empiezan por `.`, `_` o `~$` (ocultos, desactivados a
propósito o temporales de Excel abiertos). Por compatibilidad, también se leen
un `movimientos.*` suelto en la raíz y lo que haya en una carpeta `tarjetas/`,
que era la forma antigua de trabajar.

**Formato real, no extensión.** Los bancos españoles llaman `.xls` a cinco
cosas distintas. La herramienta mira los primeros bytes del fichero y decide:

| Lo que es en realidad | Cómo lo reconoce |
|---|---|
| Excel 97-2003 de verdad (BIFF) | Firma binaria de contenedor OLE2, o BIFF antiguo sin contenedor. |
| Excel moderno (xlsx) o OpenDocument (ods) | Es un ZIP; mira dentro para distinguir uno de otro. |
| Tabla HTML renombrada | Empieza por etiquetas HTML o contiene una tabla en los primeros 4 KB. |
| XML de Excel 2003 (SpreadsheetML) | Empieza por una declaración XML que menciona "spreadsheet". |
| Texto (CSV/TSV) | Texto legible. El separador se deduce contando cuál (`;`, tabulador, `,` o `|`) aparece de forma más regular en las primeras 40 líneas. |

La codificación del texto (utf-8, cp1252, latin-1...) también se deduce: se
prueba la que declare el propio fichero y, si no, las habituales de la banca
española en orden.

**Dónde empiezan los datos.** Casi todos los extractos traen un preámbulo
(nombre del banco, número de cuenta, fechas...) antes de la tabla. La
herramienta busca, en las primeras 60 filas de cada tabla, la fila que mejor
parece una cabecera con **fecha, concepto e importe**, comparando cada celda
con una lista de sinónimos (p. ej. "fecha operación", "fecha valor",
"concepto", "detalle", "importe de la operación", "cantidad"...). Una
coincidencia exacta puntúa más que una parcial. Si hay varias tablas u hojas,
se queda con la que tiene más filas de datos debajo de su cabecera. Si
encuentra una columna de **saldo**, también se la guarda (es opcional).

**Convertir los valores.**
- Importes en formato español y sus variantes: `1.234,56 €`, `-45,00`,
  `(45,00)` y `45,00-` como negativos, y una heurística para decidir si el
  punto o la coma son decimales o separadores de miles.
- Fechas: `dd/mm/aaaa` (día primero, siempre), ISO `aaaa-mm-dd`, `15 abr 2026`
  con el mes en letra, y el número de serie de Excel.
- Se descartan las filas sin fecha válida, sin importe o sin concepto
  (líneas de totales, separadores, pies de página). Por pantalla se dice
  cuántas filas se han descartado de cada fichero.

**¿Cuenta o tarjeta?** Cada fichero se etiqueta como `cuenta` o `tarjeta`:
1. Si tiene columna de saldo, es una cuenta (es la pista más fiable).
2. Si tiene columnas típicas de tarjeta ("importe de la operación",
   "número de tarjeta"...), es tarjeta.
3. Si el contenido no decide, mira el nombre del fichero ("tarjeta", "visa",
   "crédito"... frente a "cuenta", "extracto", "corriente"...).
4. Sin ninguna pista, asume cuenta.

Por pantalla se dice qué ha decidido y **por qué**.

**¿De qué cuenta?** Solo si el usuario tiene varias cuentas y lo ha
declarado en `cuentas.json`: un patrón contra el **nombre del fichero** asigna
un identificador de cuenta. Sin declarar nada, todos los ficheros son de la
misma "cuenta sin nombre", que es el comportamiento de siempre.

### 3.3 Cargar el histórico

- Si `historico.xlsx` lo escribió una **versión más nueva** del programa que
  la que se está ejecutando, **se planta** sin tocar nada: podría tener
  columnas que esta versión no conoce y se perderían al guardar.
- Si lo escribió una versión más antigua, se le aplican las **migraciones**
  pendientes (columnas que se han ido añadiendo con las versiones) y se dice
  por pantalla qué se ha actualizado.
- Si no hay histórico ni ficheros en `entrada/`, se para con un mensaje
  explicando qué hacer.

### 3.4 Juntar sin duplicar

Los extractos se solapan (bajas abril, luego abril+mayo). Cada movimiento se
identifica por:

> fecha + concepto (normalizado) + importe + cuenta/tarjeta + identificador
> de cuenta + **número de repetición**

El número de repetición resuelve el caso difícil: dos cargos **idénticos** el
mismo día en el mismo sitio (dos cafés) son dos gastos reales, no un
duplicado. Dentro de un mismo fichero se numeran (0, 1, 2...), así que el
segundo café tiene otra identidad. Pero el mismo café descargado en dos
ficheros distintos tiene la misma identidad y solo cuenta una vez.

El **nombre del fichero no forma parte de la identidad**, a propósito: si no,
dos descargas solapadas con nombres distintos duplicarían todo.

Si ya estaba en el histórico, gana la fila del histórico, así que una
corrección manual ya escrita no se pierde al volver a leer el extracto. Por
pantalla se dice cuántos movimientos son nuevos y cuántos ya estaban.

### 3.5 Clasificar (desde cero, todo el histórico)

Para cada movimiento, en este orden:

1. **¿Se excluye?** Si su concepto casa con algún patrón de
   `exclude_patterns.json`, queda marcado como excluido. **No se borra**: se
   guarda en el histórico marcado, para que quitar un patrón lo recupere.
   El caso típico es el recibo con el que la cuenta paga la tarjeta: si no se
   excluye, cada gasto de la tarjeta cuenta dos veces.
2. **Mes y mes contable.** Cada movimiento tiene su mes real y un "mes
   ajustado". El ajustado solo cambia para los movimientos que caen en los
   primeros días del mes (3 por defecto), contienen una de las palabras de
   `mes_contable.json` (típicamente "nómina") y, por defecto, son ingresos:
   esos se mueven al mes anterior, porque la nómina que entra el día 1 es
   con la que se ha vivido el mes que acaba. Lo del signo importa: la
   prestación que se cobra de una mutua sí es del mes anterior, pero la cuota
   que se le paga el día 2 no.
3. **Categoría por reglas.** Ver el apartado 4.
4. **Corrección manual.** Si en el histórico la columna `categoria_manual` de
   esa fila tiene algo escrito, manda sobre todo lo anterior. Puede ser una
   categoría (la aplica, y de paso "des-excluye" la fila si estaba excluida)
   o `(excluido)` (la saca de los totales). Si lo escrito no es una categoría
   declarada, **se ignora** y se avisa: aplicarla haría que ese movimiento
   desapareciera de los totales.

Al final, lo excluido se separa de lo que cuenta. Todos los cálculos que
siguen usan solo lo que cuenta; el histórico guarda las dos cosas.

### 3.6 Saldo inicial

Si los extractos de cuenta traen columna de saldo, el Acumulado del resumen
parte del **dinero real que había en la cuenta** antes del primer movimiento
conocido, en vez de partir de 0.

El saldo de cada fila es el que queda *después* de ese movimiento. Invertirlo
es fácil si ese día solo hubo un movimiento, pero ambiguo si hubo varios (no
se sabe en qué orden los aplicó el banco). Así que busca el primer día con
saldo conocido y **un solo movimiento**, deshace ese movimiento y resta
también todo lo de los días anteriores (esos se pueden sumar sin importar el
orden). Si no hay ningún día así de limpio, usa 0 antes que inventar.

Con varias cuentas declaradas, lo calcula para cada una por separado y suma.
Las tarjetas no tienen saldo y no aportan nada aquí.

### 3.7 Construir el resumen mensual

Una fila por mes (agrupando por el mes ajustado, o por el real si así se
configura en `categorias.json`):

```
cada categoría de gasto  = lo gastado en ella ese mes, en positivo
Total Gastos             = suma de las categorías de gasto
Ingresos                 = suma de las categorías de ingreso
Balance                  = Ingresos - Total Gastos
Extras                   = lo que se arrastra a favor de los meses anteriores
Deuda                    = lo que se arrastra en contra de los meses anteriores
Acumulado                = Extras - Deuda + Balance
```

- Los gastos salen en positivo **dándoles la vuelta al signo, no con valor
  absoluto**. Una categoría en la que ese mes entró más de lo que salió (una
  devolución grande) sale **negativa**, que es lo correcto. Con valor
  absoluto, una devolución se disfrazaría de gasto.
- Las categorías **neutras** (traspasos entre cuentas propias) no entran en
  ningún total: no es dinero que entre ni salga.
- Extras y Deuda son el Acumulado del mes anterior partido por su signo; en
  un mes solo uno de los dos tiene valor. El primer mes parte del saldo
  inicial.
- Personalizable sin tocar el cálculo, en `categorias.json`: textos de columna
  distintos del nombre interno (`etiquetas`), qué columnas salen y en qué
  orden (`orden_resumen`), y una columna por categoría de ingreso además del
  total (`desglosar_ingresos`). El cálculo siempre trabaja con los nombres
  internos; el cambio de nombre es lo último que se hace, ya para mostrarlo.

### 3.8 Guardar

1. **Copia de seguridad** del histórico anterior en `datos/copias/`, con fecha
   y hora en el nombre. Se conservan las últimas 10 (configurable en
   `sincronizar.json`); las más antiguas se borran.
2. **`datos/historico.xlsx`**, reescrito entero (apartado 6).
3. **`salida/movimientos_limpios.xlsx`**: solo lo que cuenta.
4. **`salida/movimientos_excluidos.xlsx`**: solo lo excluido, con qué patrón
   lo excluyó (solo si hay algo excluido).
5. **Sincronización**, si está configurada: vuelca los movimientos
   directamente en una hoja del fichero de contabilidad propio del usuario
   (apartado 7). Si falla, avisa y deja ese fichero intacto; el resto de la
   ejecución ya está guardado.

### 3.9 Lo que se cuenta por pantalla

La pantalla va por bloques, siempre en este orden:

1. **Cabecera**: nombre y versión (siempre la primera línea: es lo primero
   que hace falta saber si algo va mal), lo que haya hecho la preparación de
   la carpeta (3.1) y cuántas reglas hay.
2. **Leyendo entrada/**: cada fichero con su formato, dónde estaba la
   cabecera, cuántos movimientos y si es cuenta o tarjeta (y por qué). Luego,
   cuántos había en el histórico, cuántos son nuevos y cuántos repetidos.
3. **Resultado**: dónde se ha guardado cada cosa, la sincronización,
   cuántos movimientos y excluidos, de qué fecha a qué fecha, el mes contable
   ajustado, el saldo inicial detectado, y los totales del último mes y el
   Acumulado. Si puede que el recibo de la tarjeta esté contando gastos dos
   veces, se señala aquí mismo, junto a los totales, para no fiarse de ellos
   sin saberlo.
4. **Cargos que se repiten** (apartado 5.2), si hay.
5. **Sin clasificar** (apartado 5.3), si hay.
6. **Avisos**, todos juntos y contados: categorías que no cuadran,
   correcciones manuales inválidas, ficheros que no se han podido leer, la
   sincronización que no se ha hecho, el recibo de la tarjeta (5.1)... Se
   van guardando durante la ejecución y salen al final, en vez de en el
   momento en que se detectan: antes aparecían mezclados con todo, a menudo
   lo primero de la pantalla, que es justo donde menos se leen.

**Al terminar bien**, la ventana no se cierra sola. Ofrece:

```
   1      Abrir el histórico  (datos/historico.xlsx)
   2      Abrir la carpeta  datos/
   Intro  Cerrar
```

Se pueden elegir varias opciones seguidas; Intro cierra. Abre el fichero o la
carpeta con el programa que tenga asignado el sistema (Excel, el
explorador...).

**Si algo falla**, primero salen los avisos que ya hubiera (pueden explicar
el error), luego un mensaje con ❌ en lenguaje llano, y la ventana espera a
que se pulse Intro.

El menú y las esperas solo ocurren **si hay una persona delante** (se ha
abierto con doble clic o desde una consola). Si la salida va a otro programa
(las pruebas, un script), no pregunta nada, para no quedarse esperando para
siempre.

**Los lanzadores** (`ejecutar.*`) no vuelven a pausar cuando el programa
termina bien o con un error ya explicado (la herramienta sale con un código
que lo indica), para que no haya que pulsar dos veces. Solo pausan ellos si el
programa ni siquiera ha podido arrancar (falta Python, falta la carpeta
`app/`...). Con el `.exe` no hay lanzador: es el propio programa el que
espera.

---

## 4. Cómo se decide la categoría

### Las dos capas

- **Las reglas del usuario** (`ajustes/rules.json`): mandan siempre. Nunca se
  tocan al actualizar.
- **La base** (`app/rules_base.json`): comercios y conceptos conocidos en toda
  España. Viene con el programa y se reemplaza entera con cada versión.

Se miran primero las del usuario y luego las de la base. De la base solo
entran las claves que el usuario no haya escrito ya, así que para cambiar
cualquier regla de la base basta con repetirla en la propia. Para
**apagarla** sin sustituirla, se repite con valor `null`.

Una regla de la base que apunte a una categoría que el usuario **no tiene**
en su `categorias.json` se descarta (se dice cuántas por pantalla). Si no, esos
movimientos acabarían en una categoría que no es columna de nada.

**Qué hay en la base.** Solo nombres y conceptos que significan lo mismo para
cualquiera en España: cadenas de supermercados, gasolineras, operadores,
comercializadoras, plataformas, cadenas de restauración, aseguradoras de
salud, tiendas online, y conceptos bancarios como nómina, préstamo, alquiler
o IBI. Nada que dependa de la vida de alguien (su casero, su colegio, sus
transferencias). Tampoco lo ambiguo: `renta` (la de Hacienda o la del piso),
`credito` (el recibo de la tarjeta), `paypal` (lo que importa es el comercio
que va detrás), los seguros genéricos (coche, casa o vida) o las marcas que
son a la vez luz y gasolinera sin forma de distinguirlas por el concepto.

**El orden dentro de la base**: las claves concretas van antes que las
generales que las contienen (`alquiler de vehiculos` antes que `alquiler`,
`uber eats` antes que `uber`, `clinica veterinaria` antes que `clinica`,
`amazon prime` antes que `amazon`). Si no, la general gana siempre. Hay una
prueba que fija estos casos.

### Cómo casa una regla

El concepto se normaliza antes de comparar: minúsculas, sin tildes, espacios
colapsados. "NÓMINA" y "nomina" son lo mismo.

| Clave | Casa con... | Para qué |
|---|---|---|
| `mercadona` | una palabra que **empiece** así. | Lo normal. `veterin` pilla VETERINARIO, y `dia` ya no pilla MEDIA MARKT. |
| `=dia` | la **palabra completa** exacta. | Claves cortas y ambiguas: `=bar` no pilla BARCELONA. |
| `~dia` | en **cualquier sitio**, aunque sea dentro de otra palabra. | Casos raros; es el comportamiento antiguo que daba problemas. |
| `re:...` | una expresión regular. | Casos muy raros. |
| `_loquesea` | nada: se ignora. | Comentarios dentro del JSON. |

**Gana la primera regla que casa**, en el orden del fichero. El orden importa.

Si ninguna casa, el movimiento va a **Otros** y queda marcado como "sin
regla" (distinto de un movimiento que una regla manda a Otros a propósito).

### Según el signo

El valor de una regla puede ser distinto según el importe sea positivo o
negativo: `{"+": "Ingresos", "-": "Ocio"}`. Solo hace falta cuando el cobro
y el pago son **conceptos distintos** (un Bizum recibido frente a uno
enviado). Para una devolución de una compra no hace falta: que el abono reste
de la misma categoría es justo lo correcto.

Si la regla solo define un lado (`{"-": "Otros"}`), los movimientos del otro
signo siguen buscando en las reglas siguientes.

### Probar una regla sin procesar nada

`python app/reglas.py "CONCEPTO DE PRUEBA" -25` dice qué categoría saldría,
qué regla casa y de qué capa viene, o si se excluiría. Sin argumentos, pasa
los ejemplos de las trampas conocidas (MEDIA MARKT, NAVIDAD, BARCELONA...).

---

## 5. Los tres informes automáticos

Los tres son solo por pantalla. Ninguno cambia nada en los ficheros: proponen,
y quien decide es el usuario.

### 5.1 El recibo de la tarjeta

Solo se activa si hay movimientos de tarjeta y `exclude_patterns.json` está
vacío. Con cualquier patrón puesto, se da por resuelto.

Para cada mes de tarjeta suma lo que debe la tarjeta ese mes (ya descontadas
las devoluciones), y busca en la cuenta **un único cargo** por ese mismo
importe, con 2 céntimos de margen, entre el día 1 de ese mes y 45 días después
de que acabe. Si hay más de un candidato ese mes, no elige: descarta el mes.

Con los cargos encontrados, extrae la parte del concepto que **no cambia** de
un mes a otro (quitando las referencias numéricas) y la propone como patrón de
exclusión, **solo si** tiene al menos 5 caracteres y no casa con ningún otro
movimiento de la cuenta. Si no es segura, enseña lo encontrado y pide
añadirlo a mano.

### 5.2 Cargos que se repiten

Suscripciones, cuotas, seguros, préstamos: lo que se cobra cada mes o cada
año por un importe parecido.

- Solo mira **gastos de categorías de gasto**. Un traspaso mensual a una
  cuenta de ahorro (categoría neutra) es regular, pero no se "paga".
- Agrupa por el **concepto entero** después de quitarle los números (la
  referencia del recibo, fechas...). Así, recibos con referencia distinta cada
  mes van juntos, pero "PAYPAL *NETFLIX" y "PAYPAL *SPOTIFY" no.
- En cada grupo, parte del **último cargo** y va hacia atrás mientras se
  cumplan dos cosas a la vez con el anterior:
  - **Intervalo regular**: 26-35 días (mensual) o 350-380 días (anual). El
    margen cubre meses de 28 a 31 días y recibos que el banco pasa al lunes
    siguiente por caer en fin de semana.
  - **Importe parecido**: diferencia de hasta el 15% o 3 € (lo que sea
    mayor), cargo a cargo. Permite subidas de precio normales.
- Hacen falta al menos **3 cargos seguidos** para mensual y **2** para anual
  (exigir 3 anuales obligaría a tener tres años de histórico para ver un
  seguro).
- Tiene que **seguir vivo**: si el último cargo es más antiguo que un periodo
  (más el margen) respecto al último movimiento del histórico, se da por dado
  de baja y no sale.
- Ordena por **lo que suma al año al precio del último cargo** (mensual × 12,
  anual × 1), que es lo que hace visible el peso real de un cargo pequeño.
  Enseña los 10 que más suman y el total.

Restricción de producto, no de estilo: **el informe nunca opina**. Dice qué se
repite y cuánto suma; no dice "deberías cancelarlo". Un alquiler o un
gimnasio que se usa salen igual que una suscripción olvidada.

Limitaciones conocidas: un comercio que mete letras que cambian en el concepto
(códigos alfanuméricos) no se agrupa; una prima que sube más del 15% de golpe
corta la serie en ese punto; un anual necesita algo más de un año de
histórico para aparecer. Los márgenes están fijados con datos de prueba y
pendientes de afinar con extractos reales.

### 5.3 Lo que se ha quedado sin clasificar

Los movimientos que ninguna regla ha sabido clasificar se reparten en grupos
por **palabra común**: en cada vuelta se elige la palabra que más importe
arrastra entre los que quedan, se forma su grupo y se sacan del reparto (un
movimiento nunca está en dos grupos). Se descartan las palabras de relleno del
banco ("compra", "pago", "recibo", "tarjeta", "transferencia"...), los números
sueltos y las palabras de menos de 3 letras.

Se enseñan los 10 grupos que más suman, con un ejemplo y una línea lista para
pegar en `rules.json`. La palabra sugerida se comprueba con el propio motor de
reglas: **solo se propone si no casaría con ningún movimiento que ya tiene
categoría por otra regla**. Si ninguna palabra del grupo es segura, lo dice y
pide revisarlo a mano.

---

## 6. El Excel que genera

`datos/historico.xlsx` tiene tres hojas.

**MOVIMIENTOS** — el histórico completo, incluidos los excluidos:

| Columna | Qué es |
|---|---|
| fecha, descripcion, importe | Tal cual los traía el banco (ya convertidos). |
| tipo | `cuenta` o `tarjeta`. |
| mes, mes_ajustado | El mes real y el mes contable. |
| categoria | La calculada en esta ejecución, o `(excluido)`. |
| categoria_manual | **La única columna que el usuario escribe a mano.** Se conserva entre ejecuciones. |
| excluido | Si cuenta o no. |
| origen | De qué fichero salió (informativo, no forma parte de la identidad). |
| regla | Qué clave lo clasificó, qué patrón lo excluyó, `(manual)`, o vacío si no casó nada. |
| n_rep | El número de repetición del apartado 3.4. |
| saldo | El saldo que traía el extracto de cuenta en esa fila, si lo traía. |
| cuenta | El identificador de `cuentas.json`, o vacío. |

Las siete primeras columnas (de fecha a categoria) están siempre en ese orden,
porque hay hojas de usuario con fórmulas que apuntan a ellas por posición.

**RESUMEN** — la tabla del apartado 3.7, con un gráfico de línea del
Acumulado **debajo**, a dos filas de la tabla. Sin anotaciones ni texto
generado: solo el gráfico. El gráfico lleva dentro una copia de sus valores
y de los meses, además de la referencia a las celdas: Excel lo recalcula al
abrir, pero otros programas (OnlyOffice) lo dibujan con esa copia, y sin
ella salía vacío.

Orden de las hojas: **RESUMEN primero** (y es la que se ve al abrir el
fichero), luego MOVIMIENTOS y por último _meta.

**_meta** — qué versión escribió el fichero, cuándo y con cuántos
movimientos. Es lo que permite migrar un histórico antiguo y negarse a tocar
uno de una versión más nueva.

Las dos hojas visibles llevan formato (cabecera verde, importes en euros,
bandas, primera fila y columna fijas). Cualquier texto que empiece por `=` se
guarda como texto, para que Excel no lo tome por una fórmula (hay reglas que
se llaman `=dia`).

`salida/movimientos_limpios.xlsx` son esas siete columnas más origen y regla,
solo de lo que cuenta: es lo que se pega en una hoja propia si no se usa la
sincronización.

---

## 7. Sincronizar con la contabilidad propia

Opcional (`sincronizar.json`; sin fichero indicado, no hace nada). Vuelca los
movimientos que cuentan (o todos, si se pide) en **una hoja concreta** de un
`.xlsx` del usuario, a partir de la fila y columna indicadas, conservando el
resto del libro (fórmulas de otras hojas, formatos, gráficos, imágenes).

Se niega a escribir, y lo explica, si:
- el fichero es `.xlsm` (perdería las macros) o no es `.xlsx`;
- el libro tiene tablas dinámicas o macros (no sobreviven a la reescritura);
- la hoja de destino tiene **alguna fórmula** en cualquier parte (señal de que
  se ha apuntado a la hoja equivocada);
- el fichero está abierto en otro programa.

Antes de escribir hace una copia de seguridad del libro en `datos/copias/`.
Si esta vez hay menos filas que la anterior, borra las sobrantes, **salvo**
que haya datos del usuario a los lados del bloque volcado (notas, por
ejemplo): entonces solo las vacía, para no llevarse esos datos.

---

## 8. Las protecciones

**Contra movimientos que desaparecen de los totales** (el fallo más
traicionero, porque el Excel cuadra por dentro y nadie se entera):
- Categorías de `rules.json` y `categorias.json` que no coinciden **letra por
  letra** → aviso, incluyendo el caso de que solo se diferencien en una tilde
  o una mayúscula ("Higiene" frente a "higiene" suma 0).
- Categoría que asigna una regla pero no está declarada → aviso.
- Categoría declarada que ninguna regla asigna → aviso (su columna saldrá a 0).
- Categoría repetida, o que se llama igual que otra columna del resumen → aviso.
- Regla de la base a una categoría no declarada → descartada.
- Corrección manual con una categoría que no existe → ignorada y avisada.
- Nombre desconocido en `orden_resumen` → ignorado y avisado.

**Contra perder datos:**
- Copia de seguridad del histórico antes de cada escritura.
- Histórico escrito por una versión más nueva → no se toca.
- Histórico ilegible → se para en vez de empezar de cero y sobrescribirlo.
- La migración desde la versión antigua copia todo antes de mover y nunca
  pisa un fichero existente.
- La sincronización se niega ante cualquier duda (apartado 7).

**Contra filtrar datos personales:** ver el apartado 9, "exportar".

---

## 9. Las otras piezas

- **Instalar** (`instalar.bat/.command/.sh`): crea un entorno de Python propio
  dentro de `app/` e instala ahí las librerías (pandas, openpyxl, xlrd), sin
  tocar el Python del sistema. Comprueba antes que la carpeta esté completa
  (el error típico es descargar los ficheros sueltos y perder las carpetas).
- **Ejecutar** (`ejecutar.*`): usa ese entorno si existe y lanza el programa.
- **Exportar** (`exportar.*`): genera un ZIP para dar la herramienta a otra
  persona **sin ningún dato del usuario**. Funciona por **lista blanca**: solo
  entra lo autorizado (el programa, los lanzadores, la guía, el changelog, la
  licencia). `entrada/`, `salida/`, `datos/` y `ajustes/` no entran nunca, y
  una segunda comprobación aborta el ZIP si se hubiera colado algo que parezca
  un fichero de datos. Los lanzadores de Mac y Linux se marcan como
  ejecutables dentro del ZIP aunque se genere desde Windows, y los saltos de
  línea se fuerzan: los de Windows en los `.bat` y los de Linux/Mac en los
  `.sh` y `.command`, vengan como vengan en la copia de origen. Quien lo recibe
  obtiene su propia configuración desde las plantillas la primera vez.
- **Diagnóstico de un extracto**: `python app/bank_io.py fichero.xls` enseña
  qué formato es en realidad, las primeras filas de cada tabla, dónde ve la
  cabecera y qué columnas ha reconocido. No modifica nada.
- **La versión** vive en `app/VERSION`, sale en la primera línea de cada
  ejecución y queda grabada en la hoja `_meta`.

---

## 10. Lo que NO hace

- No se conecta a internet ni al banco. Los extractos se bajan a mano.
- No usa IA ni "aprende": clasifica solo con reglas que se pueden leer.
- No modifica ni borra los ficheros de `entrada/`.
- No opina sobre en qué se gasta el dinero, ni da consejos.
- No hace presupuestos hacia delante: es retrospectivo, clasifica lo que ya
  pasó.
- No es contabilidad de partida doble ni multidivisa.
