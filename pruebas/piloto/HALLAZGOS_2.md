# Ronda 2 del piloto (25/09/2026, sobre la 2.12.1)

Siete perfiles: cinco nuevos más Marta y Ana repitiendo. Notas de 7 (pareja),
6 (viene de otra app), 6 (estudiante), 7 (autónomo), 5 (solo sincronización),
7 (Marta) y 8 (Ana): media 6,6, igual que la ronda 1. Informes completos en
`ronda2/`. Lo marcado «comprobado» se reprodujo a mano o se vio en el código.

## Lo arreglado en la 2.12.1 sigue arreglado

- Declarar `cuentas.json` después de la primera ejecución ya no duplica
  (Marta: 52 filas antes y después) y los saldos cuadran por cuenta.
- Lo que entra sin regla va a Ingresos: ni gastos negativos ni «Otros»
  restando (Marta, Ana).
- Las notas de la sincronización siguen a su movimiento al meter un mes
  anterior (Ana; también Carmen).
- PDF y fichero vacío, con mensajes que se entienden (Ana).
- El súper y la cafetería ya no salen en «Cargos que se repiten» con compras
  frecuentes (pareja): lo descartado en la ronda 1 era, en efecto, un
  artefacto de los datos.

## Graves: cifras mal sin avisar

| Fallo | Quién | Comprobado |
|---|---|---|
| Con `cuentas.json` declarado, un extracto cuyo nombre no casa con ninguna cuenta (`movimientos (1).xls`) entra como tercera cuenta «(sin identificar)»: 16 movimientos duplicados, Acumulado inflado, y aun así «🧮 Cuadra con el banco» en verde para las tres. Choca con «No hay que renombrar nada» del LEEME | Marta | Sí, reproducido |
| La regla de la base `"comunidad prop": "Piso"` no mira el signo: los cobros de un cliente «TRANSF. DE COMUNIDAD PROP. …» caen en Piso (Piso negativo, facturación fuera de Ingresos). No sale en «Sin clasificar» porque sí tiene regla | autónomo | Sí, `reglas.py` |
| Sin `cuentas.json`, dos tarjetas con un cargo idéntico el mismo día (dos cafés en cada una) se fusionan: salen 2 de 4, sin aviso. Es el comportamiento documentado para cuentas, pero la guía solo habla de `cuentas.json` para «dos cuentas corrientes» y quien tiene dos tarjetas no sabe que lo necesita | pareja | Coincide con la regla de deduplicación de CLAUDE.md |
| Dos categorías con la misma etiqueta en `etiquetas` tiran el programa (`float() argument must be … not 'Series'`) y dejan `historico.xlsx` reescrito a medias: sin gráficos, sin formato, hojas en otro orden. La versión rota acaba en `datos/copias/` en la siguiente ejecución | viene de otra app | Sí, reproducido |
| Sincronización con una hoja que ya tiene datos del usuario en la esquina configurada: la reescribe entera (borra las filas de junio metidas a mano, cambia las cabeceras) y las SUMIF de su hoja de totales pasan a dar 0. Ningún documento dice que la hoja se reescribe ni qué columnas escribe | Carmen | Por diseño la hoja es solo de la herramienta; falla el aviso y la documentación |

## Menores o de documentación

- **Formatos que no se leen:** N26 (`Payee` no es alias de descripción) y
  bancos con `Cargo`/`Abono` en dos columnas. La guía manda editar
  `ALIAS_COLUMNAS` en `bank_io.py` (código, se pierde al actualizar, y no
  sirve para el importe partido). La web promete «cualquier banco» y
  «neobancos». Comprobado en `ALIAS_COLUMNAS`.
- **«La carpeta 'entrada/' está vacía»** cuando hay ficheros pero ninguno se
  ha podido leer (estudiante, otra app). Comprobado: `process.py`, el
  `FileNotFoundError` tras `leer_entrada()`.
- **Sincronización, fichero abierto:** solo se detecta por `PermissionError`,
  así que un `.~lock…#` de LibreOffice o un `~$…` no lo paran (Carmen). En
  Windows con Excel el guardado sí falla; hay que probarlo allí.
- **Sincronización, copias:** se hace una en cada ejecución aunque no haya
  nada nuevo; tras 10 ejecuciones se pierde la única copia anterior a la
  primera sincronización (Carmen). Comprobado: `escribir()` copia siempre.
  `_copias` dice `copias/` y están en `datos/copias/` (Ana).
- **`"archivo"` de `sincronizar.json`**: no dice a qué carpeta es relativo
  (a `eledger/`). Repetido de la ronda 1 (Ana, Carmen).
- **Regla del usuario a una categoría mal escrita:** la guía dice que «se
  descartan», pero se aplica: el movimiento sale del Total Gastos y pasa a
  «Fuera del balance». Sí hay aviso claro al ejecutar y el Acumulado cuadra
  (Marta). Comprobado. O la guía o el comportamiento, pero no los dos.
- **Detector del recibo de la tarjeta con dos tarjetas:** «no lo he sabido
  encontrar solo» aunque cada liquidación cuadra con su tarjeta; y «Sin
  clasificar» sugiere una regla para `liquidacion`, que contaría las compras
  dos veces (pareja).
- **Aviso de doble conteo con tarjeta de débito** en cada ejecución; ya
  descartado en la ronda 1 como a propósito, pero Ana vuelve a quejarse.
- **`IMPUESTO VEHICULOS AYTO`** sin regla en la base; la guía no nombra la
  categoría Impuestos ni tiene ejemplo de autónomo (autónomo).
- **Renombrar categorías** en `categorias.json` descarta ~120 reglas de la
  base sin que la guía avise del precio; `etiquetas` solo cambia rótulos
  (otra app).
- **Bizum de amigos que devuelven cenas** cuentan como ingreso; falta una
  receta en la guía (estudiante, Marta).
- **`reglas.py` con varios conceptos e importes** aplica el último importe a
  todos (autónomo, Marta).
- **Una hoja propia añadida a `historico.xlsx`** se pierde al volver a
  ejecutar, sin aviso (pareja). Es coherente con que el histórico se
  regenera, pero no se dice.
- «Sin clasificar» propone el nombre de un cliente (`"antonio"`) en vez de un
  patrón común (`"transf. de"`) (autónomo).

## Peticiones de producto (no fallos)

Gasto por tarjeta o por cuenta en el RESUMEN (pareja, y Marta otra vez); modo
«añadir debajo» y columnas elegibles en la sincronización (Carmen); importar
el histórico de otra app con sus categorías (entra como CSV, pero la
categoría se ignora); totales por trimestre (autónomo).

## Artefactos del generador

- Fechas hasta el 28/09 con «hoy» a 25/09 (estudiante lo señala): lo produce
  `frecuentes()`, no el programa.
- Vodafone «desde 06/2026» y el saldo inicial negativo del perfil de otra
  app: el CSV de la otra app no trae saldo y mezcla meses; sin investigar.
- La hipoteca de la pareja y la eléctrica de otra app se generaron con
  «RECIBO …» delante; en `generar.py` pasaron a «ADEUDO …» porque chocaban
  con reglas del propio usuario en `sin-datos-personales`.
