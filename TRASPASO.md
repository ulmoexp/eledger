# Traspaso

Herramienta local para clasificar movimientos bancarios. Lee los extractos que
el usuario descarga, los acumula sin duplicar, los clasifica por reglas y
produce un Excel con resumen mensual.

**Versión actual: 2.6.0.** Estado: funcionando, con red de pruebas. Los totales
del usuario se han verificado idénticos antes y después de cada cambio.

---

## 1. Lo primero: ejecuta las pruebas

```
python pruebas/probar.py          72 casos, 280 comprobaciones, ~2 min
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
├── movimientos.spec · requisitos.txt
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
miran antes que las de la base.

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

**Privacidad.** El `rules.json` del usuario es un retrato de su vida. `app/` y
`pruebas/` se reparten, así que **no pueden llevar datos reales**: nada de
nombres de comercios suyos, importes de su extracto ni dígitos de su tarjeta,
ni siquiera como ejemplo. El caso `sin-datos-personales` lo vigila comparando
contra `rules_base.json`; si falla, su docstring explica cómo decidir.

## 5. Lo que queda pendiente

1. **Compilar el `.exe`.** Todo listo (`compilar.bat`, `movimientos.spec`,
   `COMPILAR.md`), pero **hay que hacerlo en Windows** y no se ha podido
   probar el binario. Lo que sí está probado es que `rutas.py` resuelve bien en
   modo congelado (caso `congelado`, simulando las señales de PyInstaller) y
   que el `.spec` apunta a ficheros que existen. Al compilar por primera vez,
   comprobar: que las carpetas se crean junto al `.exe` y no en la temporal, que
   `ajustes/` se rellena con las plantillas, y el tamaño (60–80 MB esperado).

2. **Afinar el lado negativo de `mutua`** en `ajustes/rules.json`: está puesto a
   `Higiene` por suposición, el usuario tenía que confirmarlo.

3. **`app/plantillas/rules.json`** viene casi vacío a propósito (la base cubre
   lo genérico). Si con el uso se ve que a los nuevos les falta algo, va a
   `rules_base.json`, no a la plantilla.

4. Ideas menores: un registro de diagnóstico (que **no** incluya descripciones
   de movimientos), y firmar el `.exe` para evitar SmartScreen (cuesta dinero).

5. **Desglosar ingresos por categoría en RESUMEN** (llamado "1c" en las
   conversaciones de esta fase). Hoy los ingresos suman en una única columna
   `Ingresos`; falta un flag opt-in en `categorias.json`
   (`"desglosar_ingresos": true`, por defecto `false`) que añada un bucle en
   `construir_resumen()` sobre `catalogo.ingresos` análogo al de gastos, una
   columna por categoría de ingreso. Ya diseñado, sin implementar.

6. **Detección de recibos/cargos recurrentes** (suscripciones, cuotas...).
   Diseño completo (algoritmo, restricciones de producto, casos límite) en
   `/root/.claude/plans/quiero-que-continuemos-con-replicated-dragon.md`,
   sección "Diseño: detección de recibos/cargos recurrentes". Reutiliza
   `normalizar()` y `_sin_numeros()` (ya existen, en `reglas.py` y
   `process.py`), agrupa por descripción enmascarada, exige regularidad de
   intervalos (mensual ≈28-33 días con 3+ apariciones, anual ≈350-380 días
   con 2+), informe por consola ordenado por coste anualizado, sin opinar
   ("esto se repite y suma X€/año", nunca "deberías cancelarlo"). Sin
   implementar.

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
