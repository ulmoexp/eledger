# Instrucciones del proyecto

Herramienta local para clasificar movimientos bancarios. Procesa extractos que
el usuario descarga del banco y produce un Excel con histórico y resumen
mensual. Todo local, sin red.

Documentos: `TRASPASO.md` (cómo funciona y qué hay pendiente), `ROADMAP.md`
(qué toca ahora), `CHANGELOG.md`, `COMPILAR.md`, y `FUNCIONAMIENTO.md` (qué
hace la herramienta por dentro, sin código: la referencia del propio
desarrollador para acordarse de cómo funciona algo).

## Publicar: qué se puede y qué no

**Nada de `git push` por iniciativa propia.** Los commits se crean; el push
lo hace el usuario, salvo en el caso de abajo.

**La única excepción (autorizada el 23/09/2026): el comando `/release`.**
Ahí sí se comitea, se hace `git push origin master` y se crea la release en
GitHub **como borrador**, con el ZIP de `exportar.py` y las notas escritas.
El proceso entero está en la skill global `release`
(`~/.claude/skills/release/SKILL.md`).

Sigue siendo del usuario, y no se hace ni aunque parezca razonable en el
momento: **publicar** la release (se queda en borrador hasta que él le dé al
botón), compilar y adjuntar el `.exe` (necesita Windows), hacer público el
repo y activar Pages. Fuera de `/release`, para pushear hay que pedírselo.

**La web (`/root/proyectos/eledger-web`) se publica aparte, en Surge**
(https://eledger.surge.sh, desde el 01/10/2026). Ni el push de ese repo ni
una release de este la actualizan: hace falta `./publicar.sh` allí. Si un
cambio aquí afecta a lo que cuenta la web (funciones, instalación,
descargas), recuérdale al usuario que la web también hay que actualizarla
y publicarla en Surge.

## Antes y después de cada cambio

```
python pruebas/probar.py        128 casos, 464 comprobaciones, ~2 min
```

Ejecútalas **antes** para tener la línea base y **después** para saber qué se
ha roto. No des nada por bueno sin pasarlas. Son de caja negra: ejecutan
`app/process.py` como proceso aparte y comprueban el Excel resultante, así que
sobreviven a refactorizaciones.

Si cambias la estructura de carpetas, las constantes están agrupadas al
principio de `pruebas/probar.py`.

## Reglas que no se negocian

**Todo en español**, incluidos nombres de funciones y variables nuevos.

**Comentarios que expliquen el porqué**, no lo que ya se ve en el código. Sigue
el estilo de los módulos existentes.

**Nada de datos personales en `app/` ni en `pruebas/`.** Esas carpetas se
reparten. Ni nombres de comercios reales del usuario, ni importes de su
extracto, ni los dígitos de su tarjeta, ni siquiera como ejemplo. El caso
`sin-datos-personales` lo vigila; si falla, su docstring explica qué hacer.

**Verifica sobre datos reales, no solo con las pruebas.** Las dos regresiones
más serias del proyecto se detectaron comparando la salida antes y después, no
leyendo el código.

## Trampas conocidas

**Descuadres silenciosos.** Es el fallo recurrente: un movimiento acaba en una
categoría que no es columna de ninguna suma del resumen y desaparece de los
totales sin restar de nada. Hay tres cerrojos puestos (`categoria_manual`
inválida se ignora, reglas —de la base o propias— a categorías no declaradas se descartan,
`Catalogo.validar()` avisa). **Si abres una vía nueva por la que pueda salir
una categoría, ponle su cerrojo.**

**Los bancos llaman `.xls` a cinco formatos distintos** (HTML, XML
SpreadsheetML, CSV, xlsx real y BIFF). `detectar_formato()` mira los primeros
bytes. No lo simplifiques a mirar la extensión.

**Las reglas casan por límite de palabra**, no por subcadena: `dia` no pilla
MEDIA MARKT, `vida` no pilla NAVIDAD, `bar` no pilla BARCELONA. Hay un caso de
prueba por trampa.

**El resumen muestra los gastos en positivo** (es `-suma`). Una categoría que
acabe a favor sale negativa. No lo "arregles": hubo un `ABS()` que disfrazaba
las devoluciones de gasto.

**Excel toma por fórmula cualquier texto que empiece por `=`**, y hay reglas
que se llaman `=dia`. Lo evita `_texto_seguro()`.

**Deduplicación:** clave `fecha|descripción|importe|tipo|cuenta` más `n_rep`.
`origen` no entra a propósito. `cuenta` (hito A3) se declara en
`ajustes/cuentas.json`, por patrón contra el NOMBRE DEL FICHERO; sin
declarar nada es `""` para todos y el comportamiento es el de siempre (dos
cuentas del mismo tipo con un movimiento idéntico se fusionan).

## Al terminar un cambio de comportamiento

1. Actualiza `CHANGELOG.md`.
2. Sube `app/VERSION`.
3. Si cambia el formato del histórico, añade la migración en `historico.py`
   (lista `MIGRACIONES`), no un parche del tipo "si la columna no existe".
4. Regenera la guía: `python app/build_guia.py`.
5. Si cambia lo que la herramienta hace (no solo cómo está escrito), corrige
   `FUNCIONAMIENTO.md`: tiene que seguir describiendo el comportamiento real.
6. Si no corresponde a ningún hito, anótalo en `ROADMAP.md`, en «Lo que se ha
   hecho fuera de este roadmap».

## Windows

Los `.bat` son parte del producto y el público objetivo usa Windows. Las
pruebas verifican su contenido, no que Windows los ejecute. Si tocas un
lanzador, hay que probarlo en Windows de verdad.
