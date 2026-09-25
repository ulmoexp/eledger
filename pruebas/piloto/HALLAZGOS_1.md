# Ronda 1 del piloto (25/09/2026, sobre la 2.12.0)

Cinco perfiles; notas de 6, 8, 6, 6 y 7 (media 6,6). Informes completos en
`ronda1/`. Todo lo grave se comprobó en el código antes de arreglarlo.

## Graves: cifras mal sin avisar — arreglados en la 2.12.1

| Fallo | Quién | Qué se hizo |
|---|---|---|
| Declarar `cuentas.json` después de la primera ejecución duplicaba el histórico (la clave de duplicados incluye la cuenta y las filas viejas no la tenían) | Marta | Se rellena la cuenta desde `origen`, solo donde falta; un histórico ya duplicado se cura solo. Casos `cuentas-declaradas-tarde` y `cuentas-cura-duplicados` |
| Lo que entraba sin regla caía en «Otros» (gasto) y dejaba gastos negativos | Marta, Ana | Va a la categoría de ingreso del catálogo. Caso `ingreso-sin-regla` |
| «NOMINA COLEGIO…» caía en Hijos (y «NOMINA MERCADONA» en Comida) | Lucía | Ingresos primero en la base y solo para el lado positivo. Caso `nomina-antes-que-gasto` |
| Sin columna de saldo, el Acumulado se llamaba «saldo» | Pedro | Aviso y etiqueta «desde el primer movimiento». Caso `saldo-inicial-sin-columna` |
| Sincronización: las notas del usuario se quedaban en su fila y acababan junto a otro movimiento | Ana | Se recolocan con su movimiento. Caso `sync-notas-realineadas` |

## Menores — arreglados en la 2.12.1

`instalar.sh` decía `ejecutar.command`; «extractos que se solapan» al repetir;
errores de JSON en inglés y sin fichero; fichero vacío mal explicado; PDF
ignorado en silencio; pista de `cuentas.json` si no cuadra con varios
ficheros; recibo de tarjeta con dos consejos contrarios; grupos de dinero que
entra sin marcar; avisos de `orden_resumen` sin «Mes» y de etiquetas sin
columna; nombres de reglas descartadas; ✅ en una copia; `python` → `python3`
en Mac/Linux en la guía; «pension» en el mes contable de fábrica;
«telefonica» en la base; guion como espacio (`basic fit` / BASIC-FIT);
categoría Impuestos; lanzadores sin `ajustes/rules.json`; portada con
cualquier banco, solo tarjetas y la sincronización.

## Descartados a propósito (no volver sobre ellos sin un motivo nuevo)

- **Súper y cajero en «Cargos que se repiten»**: artefacto de los datos
  inventados (una sola compra al mes, siempre el mismo día). En extractos
  reales hay varias al mes y no pasan el filtro. La transferencia mensual a
  un familiar sí es un cargo recurrente.
- **`entrada/` vacía dentro del ZIP**: chocaría con la prueba que prohíbe
  `entrada/`, `datos/`, `ajustes/` y `salida/` en el ZIP, que es la barrera
  contra repartir datos personales; la carpeta se crea sola al ejecutar.
- **Ficheros de desarrollo en el ZIP** (`TRASPASO.md`, `COMPILAR.md`,
  `compilar.bat`, `eledger.spec`): preferencia de un perfil, no fallo.
- **RESUMEN con valores en vez de fórmulas**: decisión de diseño (el resumen
  se regenera entero en cada ejecución).
- **El aviso del recibo de la tarjeta no se puede silenciar sin excluir
  nada**: a propósito; excluir el recibo es justo lo que pide.
- **Saldo de cada cuenta por separado en RESUMEN** (Marta): petición de
  producto, no fallo. Pendiente de decidir.
