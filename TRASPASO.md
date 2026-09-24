# Traspaso

Herramienta local para clasificar movimientos bancarios. Lee los extractos que
el usuario descarga, los acumula sin duplicar, los clasifica por reglas y
produce un Excel con resumen mensual.

**Versión actual: 2.11.1.** Estado: funcionando, con red de pruebas. Los totales
del usuario se han verificado idénticos antes y después de cada cambio.

---

## 1. Lo primero: ejecuta las pruebas

```
python pruebas/probar.py          89 casos, 353 comprobaciones, ~2 min
python pruebas/probar.py dedup    solo los que se llamen así
python pruebas/probar.py -v       conserva las carpetas temporales
```

Son de **caja negra**: montan una carpeta temporal, ejecutan `app/process.py`
como proceso aparte y comprueban el Excel resultante. No importan ningún módulo
de la herramienta, así que sobreviven a refactorizaciones.

Si vas a cambiar algo, ejecútalas antes para tener la línea base y después para
saber qué has roto. **No des nada por bueno sin pasarlas.**

Para tocar la estructura de carpetas, las constantes están agrupadas al
principio de `probar.py` (`DIR_APP`, `MODULOS`, `CONFIG`...); es lo único que
hay que actualizar.

## 2. Estructura

```
proyecto/
├── instalar.bat / ejecutar.bat / exportar.bat / compilar.bat   (+ .command/.sh)
├── LEEME.txt · GUIA.pdf · CHANGELOG.md · COMPILAR.md
├── eledger.spec · requisitos.txt
├── entrada/    lo que el usuario descarga del banco
├── salida/     se regenera cada vez. Borrable.
├── datos/      historico.xlsx + copias/.  INSUSTITUIBLE
├── ajustes/    configuración del usuario (5 JSON)
├── app/        el programa + rules_base.json + plantillas/ + VERSION
└── pruebas/
```

Regla que lo gobierna todo: **actualizar = reemplazar `app/` y `GUIA.pdf`**. Las
otras cuatro carpetas no se tocan jamás.

`app/rutas.py` centraliza dónde vive cada cosa, calculado desde la posición del
propio fichero (o desde `sys.executable` si corre dentro del `.exe`). Nada
depende del directorio actual. Si añades un fichero de configuración, va ahí y
en `CONFIGURACION` para que la semilla lo cree.

## 3. Los módulos

| Fichero | Qué hace |
|---|---|
| `process.py` | Orquesta. `arrancar()` prepara carpetas, migra y siembra; luego lee, clasifica, fusiona, guarda. |
| `bank_io.py` | Detecta el formato por **contenido**, no por extensión, y localiza la fila de cabecera. |
| `reglas.py` | `Clasificador` (dos capas, signo, null), `Excluidor`, `Catalogo`, `IdentificadorCuentas`. |
| `historico.py` | Carga, deduplicación, resumen mensual, escritura con formato, hoja `_meta` y migraciones. |
| `sincronizar.py` | Volcado opcional al fichero de contabilidad del usuario. |
| `rutas.py` | Rutas, migración de la carpeta antigua, semilla de configuración, versión. |
| `exportar.py` | ZIP repartible por lista blanca. |
| `build_guia.py` | Genera `GUIA.pdf`. Ejecutar tras cualquier cambio de comportamiento. |

## 4. Cosas que no son obvias y conviene no romper

**Los bancos españoles llaman `.xls` a cinco cosas distintas** (HTML, XML
SpreadsheetML, CSV, xlsx real y BIFF). `detectar_formato()` mira los primeros
bytes. No lo simplifiques a mirar la extensión.

**Deduplicación:** la clave es `fecha|descripción|importe|tipo|cuenta` más
`n_rep`, un contador de repeticiones dentro del mismo fichero. Eso permite que
dos cargos idénticos el mismo día cuenten como dos, y que dos descargas
solapadas no dupliquen. `origen` **no** entra en la clave, a propósito.
`cuenta` (hito A3, cerrado) sale de `ajustes/cuentas.json`: un patrón contra
el NOMBRE DEL FICHERO, misma sintaxis que `rules.json`. Sin declarar nada es
`""` para todos los ficheros, así que quien tiene una sola cuenta no nota
ningún cambio; quien tiene dos, nombra sus extractos de forma distinguible y
los declara ahí para que un cargo idéntico en las dos no se fusione en uno.

**Las reglas casan por límite de palabra**, no por subcadena. `dia` no pilla
MEDIA MARKT, `vida` no pilla NAVIDAD, `bar` no pilla BARCELONA. Hay casos de
prueba para cada trampa; si alguno falla, has roto el motor.

**Gana la primera regla que casa**, así que el orden importa. Las del usuario se
miran antes que las de la base. Dentro de `rules_base.json`, las claves
concretas van antes que las generales que las contienen (`uber eats` antes
que `uber`, `clinica veterinaria` antes que `clinica`...): hasta la 2.10.0
estaban al revés y nunca se aplicaban. Al añadir una clave a la base, mira
si alguna de más arriba ya la pilla (`python app/reglas.py "TEXTO"`); el
caso `base-orden` fija los conocidos. Y en la base solo va lo genérico: el
caso `sin-datos-personales` salta si una clave de tu `ajustes/rules.json`
aparece en `pruebas/` sin estar en la base.

**Signo:** el valor de una regla puede ser `{"+": ..., "-": ...}`. Solo hace
falta cuando el positivo es un concepto **distinto** del negativo (Bizum
recibido/enviado, prestación/cuota). Para una devolución normal, que el abono
reste de su categoría ya es lo correcto. Hay un caso de prueba que lo fija.

**Descuadres silenciosos.** Es la clase de fallo que más ha aparecido: un
movimiento acaba en una categoría que no es columna de ninguna suma del resumen
y desaparece de los totales sin restar de nada. Hay tres cerrojos: la
`categoria_manual` inválida se ignora, las reglas de la base a categorías no
declaradas se descartan, y `Catalogo.validar()` avisa de desajustes.
**Si añades una vía nueva por la que pueda salir una categoría, ponle su
cerrojo.**

**El resumen muestra los gastos en positivo** (es `-suma`). Una categoría que
acabe a favor sale negativa. No lo "arregles": hubo un `ABS()` que disfrazaba
las devoluciones de gasto.

**Personalizar RESUMEN sin poner en riesgo el cuadre (2.5.0).**
`categorias.json` admite `etiquetas` y `orden_resumen`, pero el cálculo de
`construir_resumen()` sigue trabajando **siempre con el nombre interno de la
categoría** — el renombrado a etiqueta visible es el último paso, ya sobre el
DataFrame terminado. Si algún día el cálculo empezara a usar la etiqueta en
vez del nombre interno, `Catalogo.validar()` dejaría de poder comparar contra
`rules.json` y volvería el fallo de la tilde que cuadra a 0€ que esos avisos
existen para evitar. Un nombre mal escrito en `orden_resumen` se descarta en
silencio al construir el resumen (no rompe la ejecución) y se avisa aparte,
mismo patrón que el resto de avisos de `Catalogo`.

**Desglose de ingresos y el choque «Ingresos» (2.7.0).** Con
`"desglosar_ingresos": true` cada categoría de ingreso tiene columna propia,
pero la categoría de la plantilla y de `rules_base.json` se llama igual que
la columna del total. En vez de obligar a renombrarla (habría que reescribir
todas las reglas de la base que la asignan), su columna se llama
`Catalogo.COLUMNA_OTROS_INGRESOS` («Otros ingresos»), y ese es el nombre
que vale en `etiquetas` y `orden_resumen`. La traducción vive en un solo
sitio, `Catalogo.columnas_ingreso`; no la dupliques. Cualquier otro choque de
nombre de columna lo avisa `Catalogo.validar()`.

**Cargos recurrentes (2.8.0): informar, nunca opinar.** `informe_recurrentes()`
en `process.py` agrupa los gastos por la descripción ENTERA sin números
(para no mezclar «PAYPAL *NETFLIX» con «PAYPAL *SPOTIFY») y recorre cada
grupo hacia atrás desde el último cargo mientras intervalo e importe cuadren.
Solo sale lo que sigue vivo y lo que es de categorías de gasto (un traspaso
mensual a ahorro, neutro, no cuenta). El texto se limita a «esto se repite y
suma X € al año»: nada de «deberías cancelarlo». Es una restricción de
producto, no de estilo, y el caso `recurrentes-mensual` la vigila.

**Pantalla, menú final y código de salida 2 (2.9.0).** Los avisos no se
imprimen al detectarse: se guardan con `avisar()` y salen juntos al final
(`mostrar_avisos()`). Si añades un aviso nuevo, usa `avisar()`, no `print`.
Al terminar bien, `menu_final()` ofrece abrir el histórico o su carpeta, o
ejecutar de nuevo (2.12.0: bucle en el `__main__`, que limpia `_avisos`
entre vueltas; si añades otro estado global que se acumule, límpialo en
`_preparar_otra_vuelta()`); al fallar, se espera a Intro (o R para repetir)
y se sale con `CODIGO_ERROR_EXPLICADO` (2). Los
lanzadores **no** pausan con 0 ni con 2, solo con cualquier otro código (el
programa ni ha arrancado); si cambias ese número, cámbialo en los tres
sitios (el caso `lanzadores` lo vigila). Menú y esperas solo si stdin y
stdout son una terminal: las pruebas capturan la salida y no se cuelgan.
**Probado solo en Linux con una terminal simulada: falta probarlo en
Windows** (doble clic en `ejecutar.bat` y en el `.exe`).

**Colores en pantalla (2.11.0).** Códigos ANSI a mano, sin `colorama`: los
pintores (`titular`, `verde`, `amarillo`, `rojo`, `gris`, `negrita`) están en
la sección PANTALLA de `process.py` y devuelven el texto tal cual si
`_COLOR` es falso, que es lo que pasa sin terminal (las pruebas) o con
`NO_COLOR`. En Windows se activa el modo VT de la consola con `ctypes` al
importar; si falla, sin color. Dos cosas que no romper: **colorear después
de `textwrap.fill`**, nunca antes (contaría los códigos como letras), y
**no meter colores dentro de un texto que se guarde o se compare** (los
avisos se guardan sin color y se pintan al mostrarlos). El caso
`sin-color` vigila que con la salida capturada no salga ni un `\x1b[`.
Si añades un `print` nuevo, usa estos pintores; sin ellos sale sin color,
que tampoco rompe nada. `exportar.py`, `bank_io.py` y `reglas.py` (su modo
de prueba) se han dejado sin color a propósito: son secundarios.
**Probado solo con una terminal simulada (`script`) en Linux: falta
probarlo en Windows** (doble clic en `ejecutar.bat` y en el `.exe`).

**Sin gráfico en RESUMEN (2.11.0).** Hubo uno del Acumulado (2.5.0–2.10.1)
y se quitó: en OnlyOffice salía mal incluso con los valores copiados
dentro. Decisión del usuario: *mejor no mostrar nada que mostrarlo mal*.
No volver a ponerlo sin probarlo en OnlyOffice; el caso `resumen-primero`
comprueba que no hay ningún `xl/charts/` en el fichero.

**Escritura segura:** Excel toma por fórmula cualquier texto que empiece por
`=`, y hay reglas que se llaman `=dia`. `_texto_seguro()` lo evita. Y
`sincronizar.py` se niega a escribir en una hoja con fórmulas, y no borra filas
enteras si hay datos del usuario fuera del bloque volcado.

**Permiso de ejecución de `.sh`/`.command` (2.6.0).** Mac y Linux arrancan
estos lanzadores ejecutándolos de verdad al hacer doble clic (a diferencia de
`.bat`, que Windows abre por asociación de tipo de fichero), así que sin el
bit `+x` no hacen nada. `git` ya los trackea con ese permiso, pero **si algún
día se reemplaza alguno de estos seis ficheros hay que volver a
`chmod +x`** antes de comitear, o el siguiente ZIP los repartirá rotos otra
vez. `exportar.py` no depende de que el sistema de ficheros de origen lo
tenga bien puesto: fuerza `0o755` a mano en `LANZADORES_EJECUTABLES` al
escribir el ZIP, precisamente porque generar el ZIP desde Windows no
preserva permisos que Windows ni siquiera tiene. El caso `lanzadores` vigila
el repositorio y el caso `exportar` vigila el ZIP; si alguno falla después de
tocar estos ficheros, es casi seguro que por esto.

**Saltos de línea de los lanzadores (2.10.1).** Misma idea: `.gitattributes`
pide CRLF para `.bat` y LF para `.sh`/`.command`, pero solo se aplica al
descargar; una copia de trabajo vieja puede tenerlos al revés (el primer ZIP
de release salía con `.bat` solo LF). `exportar.py` los fuerza al escribir
el ZIP (`_con_saltos()`), y el caso `exportar` lo comprueba estropeándolos a
propósito antes de exportar. Para arreglar la copia de trabajo en sí: borrar
los `.bat` y `git checkout --` de ellos.

**Privacidad.** El `rules.json` del usuario es un retrato de su vida. `app/` y
`pruebas/` se reparten, así que **no pueden llevar datos reales**: nada de
nombres de comercios suyos, importes de su extracto ni dígitos de su tarjeta,
ni siquiera como ejemplo. El caso `sin-datos-personales` lo vigila comparando
contra `rules_base.json`; si falla, su docstring explica cómo decidir.

## 5. Lo que queda pendiente

### Hecho: 2.11.0 y 2.11.1 (sesiones del 22 y 23/09/2026)

**2.11.0**: fuera el gráfico de RESUMEN y colores en la salida del terminal
(las dos notas de §4). Los colores, confirmados en Windows por el usuario.

**2.11.1**: lo que se descarga pasa a llamarse `eledger`. El `.exe` es
`eledger.exe` (antes `Movimientos.exe`), la receta es `eledger.spec` y el ZIP
de `exportar.py` sale ya como `eledger_v<ver>_<fecha>.zip`, que es como se
llaman los ficheros de las releases: hasta la 2.11.0 salía
`movimientos_...` y el usuario lo renombraba a mano cada vez.

**Lo que NO se renombró, a propósito:**
- `salida/movimientos_limpios.xlsx` y `movimientos_excluidos.xlsx`: el nombre
  describe lo que hay dentro, que es lo que sirve cuando los tienes abiertos
  al lado de otros Excel. Decisión del usuario (23/09/2026).
- `rutas.NOMBRE_CUENTA_LEGADO = "movimientos"`: no es un fichero nuestro, es
  el `movimientos.xls` que el usuario deja suelto en la carpeta a la manera
  antigua. Tocarlo rompería a quien siga trabajando así.

El nombre en pantalla no cambia: sigue siendo «Movimientos bancarios», con
«eledger» como referencia secundaria.

### Estado de la publicación (23/09/2026)

- Release **v2.11.0** publicada con sus dos ficheros:
  `eledger_v2.11.0_20260923.zip` y `eledger_v2.11.0_20260923.windows.zip`
  (el `.exe`, que en esa versión todavía se llamaba `Movimientos.exe`
  dentro del ZIP). Ojo al nombre: lleva un punto antes de «windows» donde
  la v2.10.1 llevaba un guion bajo.
- Release **v2.10.1**, con sus dos ZIP. Sus notas siguen diciendo que el
  `.exe` «llegará más adelante» cuando ya estaba subido.
- **2.11.1 en borrador** (23/09/2026), con `eledger_v2.11.1_20260923.zip`
  adjunto y las notas escritas. Falta que el usuario compile `eledger.exe`
  con `compilar.bat`, lo adjunte y publique.
- El repo `eledger` sigue **privado**: las releases y el botón «Descargar»
  de la web solo funcionan para él hasta que lo haga público (lo hace él).
  `eledger-web` ya es público, pero **GitHub Pages no está activado**.
- Desde aquí: `/release` puede comitear, pushear y dejar la release en
  borrador (autorizado el 23/09/2026). Publicar, el `.exe`, hacer público el
  repo y Pages siguen siendo del usuario.

1. **Confirmar con el usuario cómo fue el primer `.exe`.** Ya está compilado
   y en la release, pero no sabemos si comprobó lo que había que comprobar:
   que las carpetas se crean junto al `.exe` y no en la temporal, que
   `ajustes/` se rellena con las plantillas, el tamaño (60–80 MB esperado) y
   que la ventana no se cierra sola (menú final). Tampoco hay confirmación de
   `ejecutar.bat` con los cambios de pantalla de la 2.9.0.

2. **Afinar el lado negativo de `mutua`** en `ajustes/rules.json`: está puesto a
   `Higiene` por suposición, el usuario tenía que confirmarlo.

3. **`app/plantillas/rules.json`** viene casi vacío a propósito (la base cubre
   lo genérico). Si con el uso se ve que a los nuevos les falta algo, va a
   `rules_base.json`, no a la plantilla.

4. Ideas menores: un registro de diagnóstico (que **no** incluya descripciones
   de movimientos), y firmar el `.exe` para evitar SmartScreen (cuesta dinero).

5. **Cargos recurrentes: afinar con uso real.** Implementado en 2.8.0 solo
   por consola. Los márgenes (26-35 días, ±15% o ±3 €) están fijados con
   datos inventados; si con extractos reales salen falsos positivos o se
   escapan recibos, se ajustan ahí. Pasar a una hoja `RECURRENTES` en el
   Excel queda aparcado hasta ver que el informe aporta de verdad.

## 6. Cómo trabajar aquí

- El usuario quiere **entender el porqué**, no solo el resultado. Explica las
  decisiones y avisa de los problemas que aún no ha visto: varios de los fallos
  más serios han salido así, no de lo que pedía.
- **Comentarios en el código que expliquen la razón**, no lo que ya se ve. Los
  módulos actuales siguen ese estilo; mantenlo.
- Todo en **español**, incluidos nombres de funciones y variables nuevos.
- **Verifica sobre los datos reales del usuario**, no solo con las pruebas. Dos
  regresiones serias (la palabra `mutua` del mes contable, la columna de notas
  de `sincronizar`) se detectaron comparando la salida antes y después, no
  leyendo el código.
- Al cambiar comportamiento: actualiza `CHANGELOG.md`, sube `app/VERSION`,
  añade la migración en `historico.py` si el formato del histórico cambia, y
  regenera `GUIA.pdf` con `python app/build_guia.py`.
