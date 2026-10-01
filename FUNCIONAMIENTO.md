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
que era la forma antigua de trabajar. Lo que haya en `entrada/` con otra
extensión (un PDF, un ZIP) no se lee, pero se nombra por pantalla («no es un
extracto del banco»), para que se sepa que se ha visto. Un fichero vacío (0
bytes, una descarga que no terminó) se salta con un aviso que pide volver a
descargarlo.

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
Los sinónimos incluyen los de los neobancos en inglés ("date", "description",
"payee", "amount"). Si no hay columna de importe pero sí **dos columnas, una
de lo que sale y otra de lo que entra** ("cargo"/"abono", "debe"/"haber"),
reconocidas solo por coincidencia exacta, el importe es lo que entra menos
lo que sale, venga el cargo en positivo o en negativo.

**La categoría que trae el fichero.** Si la cabecera tiene una columna
"categoria" o "category" (coincidencia exacta), se lee también. Solo se usa
si `categorias.json` tiene `importar_categorias` y el nombre del fichero casa
con su patrón `fichero` (misma sintaxis que `cuentas.json`): es para el
export de otra app de finanzas, y un banco que trae su propia "Categoría" no
puede pisar las reglas sin que el usuario lo haya pedido. Cada valor se
traduce con `traducir` (sin mayúsculas ni acentos); el que ya se llama como
una categoría declarada vale tal cual. Lo traducido va a `categoria_manual`
(3.5), así que manda sobre las reglas y se puede corregir a mano; lo que no
se sabe traducir se queda con las reglas y se avisa de qué valores eran. Sin
esa configuración, solo se dice por pantalla que el fichero trae categoría.

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

Si se declara **después** de haber ejecutado, las filas del histórico que no
tienen cuenta la reciben a partir de su fichero de origen (columna `origen`),
y así no se duplican con las mismas releídas de `entrada/`. Solo se rellena,
nunca se cambia una cuenta ya puesta. Si el histórico ya se había duplicado
por esto (versión 2.12.0), las parejas repetidas se quitan, quedándose con la
que tenga una corrección manual, y se dice por pantalla.

**Un fichero que no casa con ninguna cuenta declarada.** Con `cuentas.json`
declarado, un fichero cuyo nombre no casa con ningún patrón sería una cuenta
más, sin identificar. Si la mitad o más de sus movimientos (misma fecha,
concepto, importe y tipo, contando las repeticiones) ya están en una cuenta
declarada, del histórico o de otro fichero de esta misma ejecución, es otra
descarga de esa cuenta con otro nombre (el «movimientos (1).xls» de volver a
bajarla): **no se lee**, y se avisa de que se renombre. Si no se parece a
ninguna, entra como una cuenta sin identificar.

**Dos cuentas o tarjetas sin declarar.** Sin `cuentas.json`, si dos ficheros
del mismo tipo cubren al menos 7 días en común y, en esas fechas (con al
menos 3 movimientos cada uno), comparten menos de la mitad de sus
movimientos, no son dos descargas de lo mismo: se avisa de que hay que
declararlas y, si ya se ha fundido algún cargo idéntico de las dos, de
cuánto falta en los totales. La línea de «ya estaban» lo señala, y
el aviso del recibo de la tarjeta remite a declararlas: con cargos fundidos,
una tarjeta deja de sumar lo que paga su recibo.

### 3.3 Cargar el histórico

- **Antes que nada** (de hecho, antes incluso de leer los extractos), mira si
  el histórico, `movimientos_limpios.xlsx` o `movimientos_excluidos.xlsx`
  están **abiertos** en otro programa. Lo sabe por el fichero de bloqueo que
  dejan al lado Excel (`~$historico.xlsx`) y OnlyOffice o LibreOffice
  (`.~lock.historico.xlsx#`), y en Windows además porque el sistema no deja
  abrirlo para escribir. Si lo están, pide guardarlos y cerrarlos: Intro
  vuelve a comprobarlo y sigue en cuanto estén cerrados; **C** los deja
  abiertos y guarda el resultado en una copia (3.8); **S** sigue igualmente,
  y solo se ofrece cuando la única pista es el fichero de bloqueo (puede ser
  un resto de un programa que se cerró en falso). Se hace antes de leer para
  que lo que se acabe de guardar en `categoria_manual` entre en esta misma
  ejecución. **No cierra nunca el programa que lo tiene abierto**: con
  OnlyOffice no hay forma fiable, y con Excel podría llevarse por delante
  otros libros o cambios que no se querían guardar. Sin nadie delante para
  contestar, lo abierto va directamente a copia.
- Si `historico.xlsx` lo escribió una **versión más nueva** del programa que
  la que se está ejecutando, **se planta** sin tocar nada: podría tener
  columnas que esta versión no conoce y se perderían al guardar.
- Si lo escribió una versión más antigua, se le aplican las **migraciones**
  pendientes (columnas que se han ido añadiendo con las versiones) y se dice
  por pantalla qué se ha actualizado.
- Si no hay histórico ni ficheros en `entrada/`, se para con un mensaje
  explicando qué hacer. Si hay ficheros pero no se ha podido leer ninguno,
  lo dice así (no que la carpeta esté vacía) y remite a los avisos.

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
corrección manual ya escrita no se pierde al volver a leer el extracto. La
excepción es una categoría importada (3.2) para un movimiento que ya estaba
sin corrección: se pasa a la fila del histórico, para que activar
`importar_categorias` después de la primera ejecución también sirva. Por
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
   `mes_contable.json` (de fábrica, "nomina" y "pension") y, por defecto,
   son ingresos:
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

Al final, lo excluido se separa de lo que cuenta. Los totales que siguen
usan solo lo que cuenta; el saldo de la cuenta (3.6 y el Acumulado de 3.7)
usa también lo excluido, porque el banco sí lo aplicó. El histórico guarda
las dos cosas.

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

**Cuadre con el banco.** Con ese saldo de partida, recorre los días en orden
sumando los movimientos de cuenta (también los excluidos: el banco sí los
aplicó) y, cada día que el extracto trae saldo, comprueba que el calculado
coincide con el del banco. Dentro de un día no se sabe el orden, pero el
saldo al cerrarlo tiene que ser el de *alguna* de sus filas, y con eso basta.
Si en algún punto deja de coincidir, apunta la fecha y la diferencia: es un
movimiento que falta o sobra desde el día anterior con saldo, casi siempre
un hueco entre dos extractos. Si al final vuelve a coincidir (los saltos
se compensan: un movimiento con la fecha cambiada entre dos extractos, por
ejemplo), no dice «no cuadra», sino que al final cuadra y en qué fechas se
separó. Si el saldo de partida no se ha podido calcular, no compara nada
(no hay con qué). Si no cuadra y los movimientos de una cuenta sin declarar
vienen de varios ficheros, añade que, si son de cuentas distintas, se
declaren en `cuentas.json`: mezcladas como una sola, sus saldos no pueden
cuadrar.

**Sin saldo conocido** (el extracto no trae la columna, o ningún día es
inequívoco) el Acumulado parte de 0 y **no es el saldo**, sino lo que ha
variado la cuenta. Se avisa al final, y la pantalla y el título del gráfico
lo llaman «desde el primer movimiento» en vez de «saldo».

### 3.7 Construir el resumen mensual

Una fila por mes (agrupando por el mes ajustado, o por el real si así se
configura en `categorias.json`):

```
cada categoría de gasto  = lo gastado en ella ese mes, en positivo
Total Gastos             = suma de las categorías de gasto
Ingresos                 = suma de las categorías de ingreso
Balance                  = Ingresos - Total Gastos
Fuera del balance        = lo que movió la cuenta sin ser gasto ni ingreso
Acumulado                = Acumulado del mes anterior + Balance
                           + Fuera del balance
```

- Los gastos salen en positivo **dándoles la vuelta al signo, no con valor
  absoluto**. Una categoría en la que ese mes entró más de lo que salió (una
  devolución grande) sale **negativa**, que es lo correcto. Con valor
  absoluto, una devolución se disfrazaría de gasto.
- Las categorías **neutras** (traspasos entre cuentas propias) no entran en
  ningún total: no es dinero que entre ni salga.
- El **Acumulado es el saldo real de la cuenta** al cerrar el mes: saldo
  inicial más todos los movimientos de cuenta hasta ese mes, cuenten o no en
  el Balance. Con varias cuentas, la suma de todas.
- **Fuera del balance** es la diferencia entre lo que se movió la cuenta y el
  Balance: traspasos a cuentas que no están en la herramienta (neutros), lo
  excluido (el recibo de la tarjeta, por ejemplo) y el desfase de la tarjeta
  (la compra cuenta en el Balance el mes que se hace, pero el banco la carga
  en la cuenta después). No se suma a partir de esas piezas, sino que se
  saca por diferencia, así que la fila cuadra siempre. Un mes con solo
  traspasos o excluidos también tiene fila: la cuenta se movió.
- Sin ningún movimiento de cuenta (solo tarjeta) no hay saldo que seguir: el
  Acumulado es la suma de los Balances y Fuera del balance es 0.
- Hasta la 2.11 el Acumulado era la suma de los Balances más el saldo
  inicial, y había dos columnas más, Extras y Deuda (el Acumulado del mes
  anterior partido por su signo). Se despegaba del banco con cada traspaso
  y cada excluido, sin avisar. Si `orden_resumen` sigue pidiendo Extras o
  Deuda, se avisa de que ya no existen.
- Personalizable sin tocar el cálculo, en `categorias.json`: textos de columna
  distintos del nombre interno (`etiquetas`), qué columnas salen y en qué
  orden (`orden_resumen`), y una columna por categoría de ingreso además del
  total (`desglosar_ingresos`). El cálculo siempre trabaja con los nombres
  internos; el cambio de nombre es lo último que se hace, ya para mostrarlo.

### 3.8 Guardar

Lo que siga abierto (3.3), o lo que resulte bloqueado justo al guardar
porque se ha abierto entre medias, **no falla**: se escribe en una copia al
lado, con fecha y hora (`datos/historico (copia 2026-09-24 10.32.05).xlsx`),
y se avisa bien claro de que el original **no se ha actualizado**. La copia
es solo para consultar: la herramienta nunca la lee, así que lo escrito en
su `categoria_manual` no cuenta. No se pierde nada, porque los extractos
siguen en `entrada/` y la siguiente ejecución con el original cerrado lo
pone al día. En ese caso no se hace copia de seguridad del histórico (no se
ha tocado).

1. **Copia de seguridad** del histórico anterior en `datos/copias/`, con fecha
   y hora en el nombre, **solo si su hoja MOVIMIENTOS es distinta de la de la
   última copia** (el resto del fichero sale de ella); si no, la última ya lo
   guarda. Siempre que tenga hojas añadidas a mano, porque el aviso dice que
   están en la copia. Se conservan las últimas 10 (configurable en
   `sincronizar.json`); las más antiguas se borran.
2. **`datos/historico.xlsx`**, reescrito entero (apartado 6). Se escribe en
   un fichero temporal al lado (`.historico.xlsx.escribiendo.xlsx`) y solo
   al terminar sustituye al de verdad, así que un fallo a mitad no deja el
   histórico a medias. Las hojas que el usuario le haya añadido a mano no
   pasan al nuevo: se avisa, diciendo en qué copia de seguridad están.
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
   ajustado, el saldo inicial detectado, los totales del último mes, el
   Acumulado y si cuadra con el saldo del extracto (3.6). Si puede que el recibo de la tarjeta esté contando gastos dos
   veces, se señala aquí mismo, junto a los totales, para no fiarse de ellos
   sin saberlo.
4. **Cargos que se repiten** (apartado 5.2), si hay.
5. **Sin clasificar** (apartado 5.3), si hay.
6. **Avisos**, todos juntos y contados: categorías que no cuadran,
   correcciones manuales inválidas, ficheros que no se han podido leer, el
   saldo que no cuadra con el banco (con las fechas en que se rompe), la
   sincronización que no se ha hecho, el recibo de la tarjeta (5.1)... Se
   van guardando durante la ejecución y salen al final, en vez de en el
   momento en que se detectan: antes aparecían mezclados con todo, a menudo
   lo primero de la pantalla, que es justo donde menos se leen.

**Importes.** Siempre en formato español, como los da el banco:
`5.000,00 €`, y con signo cuando importa (`+800,00 €`). El formato de
Python es el inglés (`5,000.00`); la conversión la hace `euros()` en
`reglas.py`.

**Colores.** En una terminal de verdad, los títulos de cada bloque salen en
negrita y color, lo que ha ido bien (✅) en verde, los avisos en amarillo,
los errores (❌, ✗) en rojo y lo secundario (motivos, notas, ejemplos) en
gris. El balance y el Acumulado del último mes, verdes si van a favor y
rojos si van en contra. Si la salida va a un fichero u otro programa, o
existe la variable `NO_COLOR`, sale sin ningún color. En la consola clásica
de Windows hay que activar antes el modo que entiende los colores; si no se
puede, también sale sin color, nunca con códigos raros a la vista.

**Al terminar bien**, la ventana no se cierra sola. Ofrece:

```
   1      Abrir el histórico  (datos/historico.xlsx)
   2      Abrir la carpeta  datos/
   3      Excluir el recibo de la tarjeta  («pago tarjeta credito»)
   4      Clasificar lo que falta  (2 grupos)
   5      Ejecutar de nuevo
   Intro  Cerrar
```

Las opciones 3 y 4 solo salen cuando hay algo que ofrecer, y los números se
corren si no están.

Se pueden elegir varias opciones seguidas; Intro cierra. Abre el fichero o la
carpeta con el programa que tenga asignado el sistema (Excel, el
explorador...). Si el resultado ha ido a una copia (3.8), la opción 1 abre la
copia. **Ejecutar de nuevo** vuelve a hacerlo todo desde el principio en la
misma ventana, releyendo también `ajustes/`: sirve para ver al momento el
efecto de una corrección en `categoria_manual` o en las reglas.

**El asistente** (desde la 2.15.0) escribe por la persona lo que los informes
le dicen que pegue en `ajustes/`. Era lo que más costaba a quien no se
maneja con ficheros: añadir una línea a un JSON sin dejarse la coma de la de
antes.
- **Excluir el recibo de la tarjeta**: sale siempre que 5.1 haya dejado el
  aviso de que la tarjeta puede contar doble. La clave que propone sale de
  5.1, segura o no; si 5.1 no dio con el recibo, de un grupo de 5.3 que lo
  parezca; y si no hay ninguna, se escribe un trozo del concepto (se guarda
  en minúsculas y sin tildes, como lo compara el motor).
  - **Antes de añadir nada**, enseña qué movimientos de la cuenta excluiría,
    con el mismo motor que `Excluidor`. Si la clave no es la segura de 5.1,
    pide comprobar que todos son el recibo.
  - No acepta un texto de menos de 4 letras ni uno que no case con nada.
  - **O** prueba otro texto. Hay que contestar **S** para escribir: Intro,
    que es lo que se pulsa por costumbre para cerrar, no escribe nada.
- **Clasificar lo que falta**: recorre los grupos de 5.3 que tienen una
  regla segura, los mismos que el informe propone pegar. En cada uno enseña
  las categorías numeradas:
  - lo que sale: las de gastos y las neutras;
  - lo que entra: las de ingresos y las neutras.
  
  Con el número se escribe la regla (`{"+": ...}` si entra, como en el
  informe). Intro salta el grupo y 0 termina; lo que no se ha llegado a
  ver sigue en el menú.

Cómo escribe (`anadir_regla` y `anadir_exclusion`, en `reglas.py`):
- **Inserta una línea al final** del objeto o la lista, con la coma que le
  falte a la anterior. No reescribe el fichero: comentarios, orden, líneas
  en blanco, el BOM y los saltos de línea de Windows del Bloc de notas se
  quedan como estaban.
- **Comprueba antes de guardar.** Vuelve a leer el resultado y comprueba
  que solo ha cambiado eso. Si no cuadra, o la clave ya existía (aunque sea
  un `null` que apaga una regla de la base), no escribe: lo dice y enseña
  la línea para pegarla a mano.
- **Antes, una copia.** Deja el fichero tal como estaba en `datos/copias/`
  (`rules_AAAAMMDD_HHMMSS.json`), y escribe en un temporal que luego
  sustituye al de verdad.

Lo nuevo se nota al ejecutar de nuevo. Como el histórico se reclasifica
entero, la regla vale también para lo antiguo. Por eso, cuando ya no queda
nada que ofrecer, pregunta «¿Lo hago ya?» (Intro = sí).

**Si algo falla**, primero salen los avisos que ya hubiera (pueden explicar
el error), luego un mensaje con ❌ en lenguaje llano, y la ventana espera:
Intro cierra, y **R** vuelve a ejecutar (para después de arreglar lo que
fallaba sin tener que volver a abrirlo).

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

Se miran primero las del usuario y luego las de la base. En la base, los
**ingresos van primero** y solo para el lado positivo (nómina, pensión,
paro...): así una «NOMINA COLEGIO…» o una «NOMINA MERCADONA» no se la lleva
la regla de gasto de «colegio» o «mercadona», que antes iba delante. De la base solo
entran las claves que el usuario no haya escrito ya, así que para cambiar
cualquier regla de la base basta con repetirla en la propia. Para
**apagarla** sin sustituirla, se repite con valor `null`.

Una regla de la base que apunte a una categoría que el usuario **no tiene**
en su `categorias.json` se descarta (se dice cuántas por pantalla). Si no, esos
movimientos acabarían en una categoría que no es columna de nada. Desde la
2.13.0, **una regla propia** así (una errata: «Sofware») también se descarta,
con un aviso que nombra la regla; y si su clave era la misma que una de la
base, la de la base vuelve a aplicarse.

**Equivalencias.** `categorias.json` puede declarar `equivalencias`
(`{"Luz/Agua": "Facturas"}`): antes de comprobar si una regla de la base
apunta a una categoría declarada, su categoría se traduce con ellas. Así
quien junta dos categorías de fábrica en una suya no pierde las reglas de
la base de ninguna de las dos. Solo cuentan las que apuntan a una categoría
declarada; las demás se avisan.

**Qué hay en la base.** Solo nombres y conceptos que significan lo mismo para
cualquiera en España: cadenas de supermercados, gasolineras, operadores,
comercializadoras, plataformas, cadenas de restauración, aseguradoras de
salud, tiendas online, y conceptos bancarios como nómina, préstamo, alquiler
o IBI. Desde la 2.12.1, también los pagos a Hacienda y la cuota de autónomos,
en la categoría **Impuestos** que trae la plantilla de `categorias.json`
(quien actualiza y no la tiene no pierde nada: esas reglas se descartan y
los cargos siguen en Otros). Lo que también puede ser un cobro (la comunidad
de propietarios, a la que factura un autónomo) solo clasifica el lado del
cargo. Nada que dependa de la vida de alguien (su casero, su colegio, sus
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
colapsados y el guion como un espacio. "NÓMINA" y "nomina" son lo mismo, y
la regla "basic fit" encuentra tanto «BASIC FIT» como «BASIC-FIT».

| Clave | Casa con... | Para qué |
|---|---|---|
| `mercadona` | una palabra que **empiece** así. | Lo normal. `veterin` pilla VETERINARIO, y `dia` ya no pilla MEDIA MARKT. |
| `=dia` | la **palabra completa** exacta. | Claves cortas y ambiguas: `=bar` no pilla BARCELONA. |
| `~dia` | en **cualquier sitio**, aunque sea dentro de otra palabra. | Casos raros; es el comportamiento antiguo que daba problemas. |
| `re:...` | una expresión regular. | Casos muy raros. |
| `_loquesea` | nada: se ignora. | Comentarios dentro del JSON. |

**Gana la primera regla que casa**, en el orden del fichero. El orden importa.

Si ninguna casa, un **gasto** va a **Otros** y lo que **entra** va a la
categoría de ingreso del catálogo («Ingresos», o la primera declarada). En
los dos casos queda marcado como "sin regla" (distinto de un movimiento que
una regla manda a Otros a propósito) y sale en el informe de sin clasificar.
Hasta la 2.12.0 lo que entraba también iba a Otros: al ser de gasto, restaba,
y un cobro sin regla dejaba el mes con gastos negativos.

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
qué regla casa y de qué capa viene, o si se excluiría. Admite varios
conceptos, y cada importe va con el concepto que tiene delante. Sin argumentos, pasa
los ejemplos de las trampas conocidas (MEDIA MARKT, NAVIDAD, BARCELONA...).

---

## 5. Los tres informes automáticos

Los tres son solo por pantalla. Ninguno cambia nada en los ficheros: proponen,
y quien decide es el usuario.

### 5.1 El recibo de la tarjeta

Solo se activa si hay movimientos de tarjeta, **también de cuenta**, y
`exclude_patterns.json` está vacío. Con cualquier patrón puesto, se da por
resuelto. Sin ningún extracto de cuenta (solo tarjetas, una de débito, un
neobanco) no hay recibo que pueda contarse dos veces, y no se dice nada.

Para cada mes de tarjeta suma lo que debe la tarjeta ese mes (ya descontadas
las devoluciones), y busca en la cuenta **un único cargo** por ese mismo
importe, con 2 céntimos de margen, entre el día 1 de ese mes y 45 días después
de que acabe. Si hay más de un candidato ese mes, no elige: descarta el mes.
Si el total de todas las tarjetas no cuadra con ningún cargo y hay más de
una tarjeta (por su cuenta de `cuentas.json` o, sin ella, por el fichero del
que sale cada movimiento), repite la búsqueda con lo de cada tarjeta por
separado, sin usar dos veces el mismo cargo.

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
por **palabra común**, lo que sale y lo que entra **por separado**: en cada
vuelta se elige la palabra que más importe (en valor absoluto) arrastra
entre los que quedan, se forma su grupo y se sacan del reparto (un
movimiento nunca está en dos grupos). Se descartan las palabras de relleno del
banco ("compra", "pago", "recibo", "tarjeta", "transferencia"...), los números
sueltos y las palabras de menos de 3 letras. Un abono que lleva la palabra de
un grupo de cargos es su devolución y se une a ese grupo, porque la regla que
se proponga para el comercio debe cogerla también.

Se enseñan los 10 grupos que más suman, con un ejemplo y una línea lista para
pegar en `rules.json`. Un grupo de dinero que **entra** (cobros, recargas) se
marca como tal, con su importe en positivo, y la regla que se le propone es
solo para el lado positivo (`{"+": ...}`). El recibo de la tarjeta que ya ha
señalado 5.1 no aparece aquí: la solución es excluirlo, no darle categoría.
Si 5.1 no lo ha encontrado, un grupo de cargos cuyos conceptos llevan todos
"tarjeta", "visa", "liquidacion"... tampoco recibe sugerencia de categoría:
se dice que parece el recibo y que hay que excluirlo.
La palabra sugerida se comprueba con el propio motor de
reglas: **solo se propone si no casaría con ningún movimiento que ya tiene
categoría por otra regla**. Si ninguna palabra del grupo es segura, lo dice y
pide revisarlo a mano.

Los grupos con línea propuesta son los que el asistente del menú final
(3.9) ofrece clasificar con un número, sin tocar el JSON.

---

## 6. El Excel que genera

`datos/historico.xlsx` tiene tres hojas.

**MOVIMIENTOS** — el histórico completo, incluidos los excluidos. Todas
las cabeceras van en verde salvo la de `categoria_manual`, en naranja: es
la única columna que se escribe a mano, y la guía la señala así.

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

**RESUMEN** — la tabla del apartado 3.7 y, debajo, tres gráficos, uno
encima de otro:

1. **Acumulado**: el saldo de la cuenta mes a mes (línea).
2. **Ingresos y gastos** de cada mes (barras, una junto a otra).
3. **Gasto medio al mes por categoría**, de más a menos (barras
   horizontales, un solo color). No son barras apiladas por categoría a
   propósito: con diez categorías serían diez colores, y pasadas ocho ya no
   se distinguen. Las categorías que en conjunto quedan a cero o a favor no
   salen.

Cada uno sale solo si sus columnas siguen en el resumen (`orden_resumen`
puede haberlas quitado). Los dos primeros apuntan a las celdas de la tabla
y llevan además una copia de los valores dentro; el tercero lleva las
medias solo dentro, porque no están en ninguna celda (añadir una fila de
totales cambiaría la tabla que leen la sincronización y las fórmulas de
cada cual).

Funcionan en Microsoft Excel, OnlyOffice y LibreOffice. Hubo un gráfico del
Acumulado entre la 2.5.0 y la 2.10.1 que en OnlyOffice salía con los meses
en el eje vertical y sin línea, y se quitó en la 2.11.0. La causa se
encontró en la 2.12.0 renderizando el fichero con el motor de OnlyOffice:
la librería que escribe el Excel pone los dos ejes a la izquierda; Excel y
LibreOffice lo pasan por alto y OnlyOffice lo obedece. Ahora cada eje se
coloca en su sitio a mano. La copia de los valores dentro es de la 2.9.0:
sin ella, OnlyOffice lo dibujaba vacío.

**CUENTAS** — solo si hay al menos dos cuentas o tarjetas declaradas en
`cuentas.json` (con una sería repetir RESUMEN). Por mes y por cada una: lo
gastado (`· gastos`, en positivo como en RESUMEN), lo que entró (`·
ingresos`, solo si alguna vez entró algo) y, para las cuentas cuyo saldo de
partida se conoce, el saldo al cerrar el mes (`· saldo`, con todos sus
movimientos, excluidos incluidos). Mismas categorías que RESUMEN, así que
las cuentas juntas suman lo mismo que Total Gastos e Ingresos; un traspaso
entre ellas no es gasto de ninguna. Lo que no casa con ninguna cuenta sale
como «(sin identificar)». Va en su propia hoja para no cambiar RESUMEN ni lo
que lean de él `orden_resumen` y las fórmulas de cada cual.

Orden de las hojas: **RESUMEN primero** (y es la que se ve al abrir el
fichero), luego CUENTAS si la hay, MOVIMIENTOS y por último _meta.

**_meta** — qué versión escribió el fichero, cuándo y con cuántos
movimientos. Es lo que permite migrar un histórico antiguo y negarse a tocar
uno de una versión más nueva.

Las dos hojas visibles llevan formato (cabecera verde, importes en euros,
bandas, primera fila y columna fijas). Cualquier texto que empiece por `=` se
guarda como texto, para que Excel no lo tome por una fórmula (hay reglas que
se llaman `=dia`).

`salida/movimientos_limpios.xlsx` son esas siete columnas más origen, regla y
cuenta,
solo de lo que cuenta: es lo que se pega en una hoja propia si no se usa la
sincronización.

---

## 7. Sincronizar con la contabilidad propia

Opcional (`sincronizar.json`; sin fichero indicado, no hace nada). Vuelca los
movimientos que cuentan (o todos, si se pide) en **una hoja concreta** de un
`.xlsx` del usuario, a partir de la fila y columna indicadas, conservando el
resto del libro (fórmulas de otras hojas, formatos, gráficos, imágenes).

**Qué columnas.** Sin `columnas`, las siete de siempre (fecha a categoria)
con esos nombres. Con `columnas` (`{"Tu cabecera": "campo"}`), solo esas, en
ese orden y con esas cabeceras; fecha, descripcion e importe son
obligatorias, porque sin ellas no se reconoce un movimiento en la hoja.

**Dos modos.**
- **tabla** (el de siempre): la hoja es de la herramienta. El bloque se
  vacía y se reescribe entero en cada ejecución, siempre clasificado con las
  reglas de hoy. Es lo que describe el resto de este apartado.
- **añadir**: la hoja es del usuario, con sus cabeceras y lo que haya metido
  a mano. La cabecera de la esquina tiene que ser la de `columnas` (sin
  mayúsculas ni acentos), o estar vacía con la hoja vacía debajo (la primera
  vez se escribe). Cada fila se reconoce por fecha + concepto (sin
  mayúsculas ni acentos) + importe + número de repetición, también si se
  tecleó como texto («02/06/2026», «-64,35»). Se añaden debajo de la última
  fila con algo, en orden de fecha, solo los movimientos que no están; lo que
  ya hay no se mueve, no se reescribe y no se borra nunca (y por eso tampoco
  se reclasifica si cambia una regla). Un movimiento del banco que el
  usuario borre de su hoja vuelve en la siguiente ejecución, porque sigue en
  el histórico. Si alguno de los añadidos es anterior al último que había,
  se dice, porque queda al final. Las filas nuevas toman el formato de
  número de la última que ya había (sus fechas, sus euros), y si entra una
  categoría que la hoja no tenía en ninguna fila, se avisa: un total por
  categoría de la hoja no la recogería.

Se niega a escribir, y lo explica, si:
- el fichero es `.xlsm` (perdería las macros) o no es `.xlsx`;
- el libro tiene tablas dinámicas o macros (no sobreviven a la reescritura);
- la hoja de destino tiene **alguna fórmula** en cualquier parte (señal de que
  se ha apuntado a la hoja equivocada);
- en la esquina configurada hay una **tabla del usuario**: alguna celda de
  la fila de cabecera tiene un texto que no es el nombre de la columna que
  va ahí, o la cabecera está vacía y hay datos debajo. El bloque se vacía y
  se reescribe entero en cada ejecución (no se añade debajo), así que
  escribir borraría esa tabla;
- el fichero está abierto en otro programa: por su fichero de bloqueo
  (`~$…` de Excel, `.~lock.…#` de LibreOffice y OnlyOffice) o, en Windows,
  porque el sistema no deja abrirlo para escribir.

Un fichero indicado solo por su nombre se busca en la carpeta de la
herramienta (la que contiene `entrada/` y `ajustes/`).

Si volcar no cambia ninguna celda (no hay nada nuevo), **no guarda ni hace
copia**: antes cada ejecución gastaba una, y a las diez se perdía la
anterior a la primera sincronización. Si hay cambios, antes de escribir hace
una copia de seguridad del libro en `datos/copias/`.
Si esta vez hay menos filas que la anterior, borra las sobrantes, **salvo**
que haya datos del usuario a los lados del bloque volcado (notas, por
ejemplo): entonces solo las vacía, para no llevarse esos datos.

**Las notas siguen a su movimiento.** Lo que el usuario tenga a los lados
de una fila que es un movimiento volcado (con fecha e importe) se recuerda
por fecha + concepto + importe + número de repetición, y tras reescribir el
bloque se vuelve a poner junto a ese movimiento: si entra uno más antiguo,
las notas no se quedan una fila por encima de lo que anotaban. Nunca pisa
otra nota; si el sitio está ocupado o el movimiento ya no se vuelca, la
deja donde estaba y avisa (y la copia de seguridad la conserva tal cual).
Lo que esté junto a filas que no son movimientos no se mueve.

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
- Regla de la base o propia a una categoría no declarada → descartada (la
  propia, con aviso que la nombra).
- Etiqueta que dejaría dos columnas del resumen con el mismo nombre →
  ignorada y avisada.
- Con cuentas declaradas, otra descarga de una cuenta con un nombre que no
  casa → no se lee (3.2). Sin declararlas, dos ficheros del mismo tipo que
  no se parecen → aviso.
- Corrección manual con una categoría que no existe → ignorada y avisada.
- Nombre desconocido en `orden_resumen` → ignorado y avisado.
- El asistente del menú final (3.9) solo deja elegir, por número, categorías
  declaradas en `categorias.json` → no puede escribir una regla a una
  categoría que no suma.

**Contra perder datos:**
- Copia de seguridad del histórico antes de cada escritura, que además se
  hace en un temporal y solo al final sustituye al de verdad.
- Histórico escrito por una versión más nueva → no se toca.
- Histórico ilegible → se para en vez de empezar de cero y sobrescribirlo.
- La migración desde la versión antigua copia todo antes de mover y nunca
  pisa un fichero existente.
- La sincronización se niega ante cualquier duda (apartado 7).
- El asistente copia `rules.json` / `exclude_patterns.json` en
  `datos/copias/` antes de escribir, solo añade una línea, no pisa una clave
  que ya exista y no guarda nada que no haya comprobado (3.9).

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
