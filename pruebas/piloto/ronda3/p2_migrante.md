# Informe de Raúl: me paso de la app del móvil a Movimientos bancarios 2.14.0

## 1. Perfil y qué intenté

Soy Raúl, 45 años, comercial. Me apaño con el ordenador y sé editar un JSON si tengo un ejemplo delante. Vengo de una app del móvil que ha empezado a cobrar. Tengo dos ficheros:

- `export_otra_app_2026-06-30.csv`: abril a junio, con las categorías de la otra app (Salario, Vivienda, Facturas, Supermercado, Restaurantes, Ocio, Transporte). Columnas `date,description,category,amount`, sin saldo.
- `Extracto_cuenta_jul-sep_2026.xlsx`: julio a septiembre. Tiene las columnas Cargo, Abono y Saldo, y en la primera fila un título que dice «Movimientos tarjeta».

Pasos que di, en este orden:

1. Leí LEEME.txt y GUIA.pdf, y ejecuté `./instalar.sh`. Fue bien a la primera: «Listo. Ya puedes usar ejecutar.sh».
2. Metí los dos ficheros en `entrada/` tal cual y ejecuté `./ejecutar.sh`.
3. Configuré `importar_categorias` como explica el apartado «Si vienes de otra app».
4. Junté la luz y el móvil en «Facturas».
5. Probé dos etiquetas con el mismo texto.
6. Revisé la devolución de Naturgy.
7. Cuadré los totales a mano contra la hoja MOVIMIENTOS con pandas.

## 2. Dónde me atasqué

No me atasqué de verdad en ningún momento. Lo que más me costó fue decidir qué hacer con las columnas Luz/Agua y Fibra/movil:

- **Esperaba** que la herramienta me ofreciera juntarlas, por ejemplo con un «esta categoría ahora se llama Facturas».
- **Lo que pasa:** la guía lo descarta a propósito. Dice: «Para juntar dos categorías, lleva sus reglas a una.»
- **Lo que hice:** puse en `rules.json` `"naturgy": "Facturas"` y `"vodafone": "Facturas"`, y quité Luz/Agua y Fibra/movil de `gastos`.
- **Lo que me encontré después:** al arrancar sale «31 reglas de la base descartadas: apuntan a categorías que no tienes en categorias.json. (endesa, iberdrola, repsol luz, holaluz, octopus, …)». Así que si algún día me cambio a Endesa o a Movistar, ese recibo irá a Otros: `python app/reglas.py "RECIBO ENDESA"` da `Otros [sin regla]`. Por lo menos avisa, y la guía ya lo advierte en «Renombrar una categoría tiene un precio». Pero para tenerlo como en la otra app tendría que copiar a mano 31 claves en mi `rules.json`. No es un fallo, pero sí trabajo.

## 3. Errores o comportamientos raros

**3.1 Fallo menor: el aviso dice que una columna saldrá a 0 cuando no sale a 0.**
- Cómo reproducirlo: añadir «Facturas» y «Restaurantes» a `gastos` y configurar `importar_categorias` con el export, todavía sin reglas en `rules.json`. Luego ejecutar.
- Lo que sale:
  > «Facturas» está en categorias.json pero ninguna regla la asigna: su columna saldrá siempre a 0.
  > Sigo adelante, pero revísalo o el resumen no cuadrará.
- Lo que pasa de verdad: en el RESUMEN, Facturas vale 76,84 en abril, 83,41 en mayo y 36,08 en junio, y Restaurantes también tiene valores, porque lo importado va a `categoria_manual`. El aviso ignora lo que viene de `importar_categorias` o de `categoria_manual`. A mí me asustó: pensé que la importación no había funcionado.

**3.2 Raro: el saldo inicial sale negativo.**
- Qué pasa: en la primera ejecución sale «💰 Saldo inicial detectado: -1.556,24 €», con el texto «Lo que tenía tu cuenta antes del primer movimiento que hay».
- De dónde sale: el saldo del xlsx de julio se echa hacia atrás a través de los movimientos del CSV de la otra app, que no trae saldo. La cuenta cuadra: el Acumulado a junio da 1.800, justo el saldo real antes del 02/07, y «🧮 Cuadra con el banco: 5.159,66 € a 28/09/2026».
- Por qué es raro: yo no tenía -1.556 € en abril. Seguramente al export de la otra app le faltan movimientos, o no cubría todo. Estaría bien un aviso del tipo «el saldo inicial se ha calculado hacia atrás sobre un fichero sin columna de saldo». No sé si es un fallo o una limitación esperable.

**3.3 Raro: una etiqueta casi igual pasa el control.**
- Qué hice: `"etiquetas": {"Fibra/movil": "facturas "}` (en minúscula y con un espacio al final), teniendo ya una categoría Facturas.
- Lo que pasa: lo acepta sin avisar, y el RESUMEN queda con dos columnas que a simple vista se llaman igual: `'facturas '` y `'Facturas'`. Con el texto exacto sí lo detecta (ver punto (d) más abajo).

**3.4 Cosmético:** en la lista de reglas descartadas aparece `digi ` con un espacio al final.

**3.5 Detalle de la importación:** si quito `Salario` de `traducir` después de haber importado, avisa «Salario: no están en «traducir» … Esos movimientos se quedan con lo que digan tus reglas». Pero las nóminas de abril a junio siguen con `categoria_manual = Ingresos` de la importación anterior. Aquí no cambia nada, porque la regla también da Ingresos. Aun así, el mensaje no describe exactamente lo que pasa: lo importado una vez se queda.

## 4. Lo que no entendí de la guía, la web o los mensajes

- «etiquetas … para cambiar cómo se ve una columna sin arriesgar el cuadre letra-por-letra»: tuve que leerlo dos veces para entender que etiquetas solo cambia el nombre de la columna y no sirve para juntar dos. La frase del final, «Para juntar dos categorías, lleva sus reglas a una», es la que me lo aclaró. Estaría mejor al principio.
- La guía no dice si, al traducir, conviene crear mis categorías (Restaurantes, Facturas) o usar las de fábrica (Ocio, Luz/Agua). Lo deduje yo.
- La web (`guia/index.html`) explica la importación en un párrafo, bien. La portada `index.html` no menciona que se pueda venir de otra app, y es justo lo que buscaría alguien como yo.

## 5. Lo que echo en falta (preferencias, no fallos)

- Poder decir «la categoría de fábrica Luz/Agua, para mí es Facturas» y que las reglas de la base la sigan, en vez de perder 31 reglas. Por ejemplo, un alias de categoría en `categorias.json`.
- Una plantilla o ejemplo completo de `importar_categorias` con las categorías típicas de las apps del móvil (Salario→Ingresos, Restaurantes→Ocio…).
- Que la pantalla, después de importar, diga cuántos movimientos han ido a cada categoría traducida. Ahora solo pone «→ 43 con la categoría del fichero».

## Resultado de cada objetivo

| Objetivo | Resultado |
|---|---|
| (a) Leer los dos ficheros tal cual | **Bien.** El xlsx va a «cuenta (columna «saldo»)» aunque el título diga «Movimientos tarjeta». Cargo sale negativo y Abono positivo. El CSV da «cuenta (sin pistas claras, asumo cuenta)» y encima me sugiere: «(trae una columna de categoría; si es el export de otra app, mira importar_categorias en la guía)». Muy bien. El saldo cuadra con el banco, pero ver el punto 3.2. |
| (b) Conservar las categorías de la otra app | **Bien.** Con `"importar_categorias": {"fichero": "export", "traducir": {"Salario": "Ingresos", "Vivienda": "Piso", "Supermercado": "Comida"}}` más Restaurantes y Facturas declaradas, sale «→ 43 con la categoría del fichero». Se aplicó aunque los movimientos ya estuvieran en el histórico. En `regla` pone «(manual)». Una corrección mía a mano en categoria_manual (un Burger King de abril a Ocio) se respetó en la siguiente ejecución. |
| (c) Luz y móvil juntas en Facturas | **Conseguido** siguiendo la guía (reglas a Facturas y quitar Luz/Agua y Fibra/movil). Lo comprobé con pandas sobre MOVIMIENTOS: Total Gastos por mes es idéntico antes y después (1037,29 / 1035,95 / 1020,52 / 1022,81 / 1036,41 / 1031,12) y coincide con la suma de los importes que no son ingresos. No desaparece nada. El coste son las 31 reglas descartadas (punto 2). |
| (d) Dos etiquetas con el mismo texto | **Se comporta como dice la guía.** Aviso claro: «La etiqueta «Suministros» de «Luz/Agua» se llama igual que la columna de «Fibra/movil»: … la ignoro y «Luz/Agua» sale con su nombre. Para juntar dos categorías en una, lleva sus reglas a la misma categoría.» Con «Facturas» (que ya existía) avisa igual. Solo se escapan las variantes con mayúsculas o espacios (punto 3.3). |
| (e) La devolución de la luz de junio | **Bien.** «Devolucion Adeudo Naturgy» de +48,20 resta: Facturas de junio = 35 + 49,28 − 48,20 = 36,08. Antes de importar, con las reglas de fábrica, Luz/Agua de junio daba 1,08, también correcto. No se disfraza de gasto. |
| (f) Coste de la migración | Unos 20-30 minutos, con la guía y tres ediciones de JSON. Esperaba más. Lo que más costó fue entender lo de etiquetas frente a reglas y decidir qué hacer con las reglas de la base. |

## 6. Valoración: 8/10

- **A favor:** lee los dos ficheros sin tocar nada, el Cargo/Abono y el saldo salen bien, y la propia pantalla me señala `importar_categorias`. La importación respeta mis correcciones, la devolución resta como debe, no se pierde ningún movimiento de los totales y los avisos de etiquetas duplicadas son claros.
- **En contra:** el aviso falso de «columna saldrá siempre a 0» (el único fallo claro), el saldo inicial negativo sin explicación, y que juntar categorías obliga a perder o a copiar a mano las reglas de la base.
