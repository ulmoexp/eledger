# Informe de usuario simulado: Raúl, el que viene de otra app

Versión probada: 2.12.1 (Linux, `instalar.sh` + `ejecutar.sh`).

## 1. Perfil y qué intenté

Raúl, 45 años, comercial y algo manitas (sé editar un JSON si tengo un ejemplo delante). Vengo de una app de finanzas del móvil que ahora es de pago. Tengo dos ficheros:

- `export_otra_app_2026-06-30.csv`: de abril a junio, con columnas `date,description,category,amount` y MIS categorías (Salario, Vivienda, Facturas, Supermercado, Restaurantes, Transporte, Ocio).
- `Extracto_cuenta_jul-sep_2026.xlsx`: el extracto del banco de julio a septiembre, con `Fecha, Concepto, Cargo, Abono, Saldo` (importes en texto con formato español, «750,00»). El título de la hoja dice «Movimientos tarjeta», aunque es la cuenta.

Leí el LEEME.txt, la GUIA.pdf entera y la web (portada, guía, reglas). Instalé, que fue bien a la primera («Listo. Ya puedes usar ejecutar.sh»). Después:
(a) metí el extracto; (b) metí el CSV de la otra app; (c) intenté quedarme con mis nombres de categoría, de dos maneras; (d) comprobé la devolución de NATURGY de junio; y probé a traerme las categorías antiguas con `categoria_manual`.

## 2. Dónde me atasqué

### 2.1 El extracto del banco con Cargo/Abono no se lee (FALLO, bloqueante)

Lo esperaba porque la web dice «De cualquier banco, también neobancos» y la guía, que «se resuelven solos: la fila de cabecera (esté donde esté), los nombres de columna según banco (Importe, Importe de la operación, Cantidad…)». No dice nada de bancos que separan el importe en dos columnas.

Lo que pasó: `entrada/Extracto_cuenta_jul-sep_2026.xlsx` → `./ejecutar.sh`:

```
   · Extracto_cuenta_jul-sep_2026.xlsx: ✗ no se ha podido leer (el motivo, en los avisos del final)
⚠️  No he podido leer Extracto_cuenta_jul-sep_2026.xlsx
    'Extracto_cuenta_jul-sep_2026.xlsx': no localizo las columnas ['importe'].
    Cabecera detectada: ['Fecha', 'Concepto', 'Cargo', 'Abono', 'Saldo']
```

El diagnóstico (`app/.venv/bin/python app/bank_io.py entrada/...`) confirma `mapeo: {'fecha': 0, 'descripcion': 1}`. Para este caso la guía manda a «añade el nombre a ALIAS_COLUMNAS en bank_io.py». Eso es tocar el programa, cuando en otra página dice «app/ la herramienta. No hay que tocarla». Y, además, un alias no arregla un importe que viene partido en dos columnas.

**Apaño que hice**: abrí el Excel y añadí una columna `Importe` = Abono − Cargo (negativo para los cargos). Con eso lo leyó bien a la primera: `→ cuenta (columna «saldo»)`, 42 movimientos, y `🧮 Cuadra con el banco: 5.064,91 € a 27/09/2026, igual que el extracto.` Los signos quedaron bien: lo de Cargo sale como gasto. El título «Movimientos tarjeta» no le confundió. Pero el apaño tendría que repetirlo cada trimestre, y es justo lo que la guía promete que no hace falta («No hay que preparar nada»).

### 2.2 Traerme el histórico de la otra app: la guía no dice nada

No hay ni una línea en la guía ni en la web sobre migrar desde otra app o importar un histórico ya categorizado. Lo probé a ciegas, soltando el CSV en `entrada/`, y funcionó mejor de lo que esperaba:

```
   · export_otra_app_2026-06-30.csv: formato=texto, cabecera en fila 1, 43 movimientos (0 filas descartadas)
     → cuenta (sin pistas claras, asumo cuenta)
➕ 43 movimientos nuevos.
```

Pero la columna `category` del CSV se ignora **en silencio**, sin avisar. Las categorías las vuelven a poner las reglas de la base. Para recuperar las mías tuve que copiarlas a mano (lo hice con un script, un usuario normal lo haría con copiar y pegar) en la columna `categoria_manual` de `datos/historico.xlsx`. Eso funcionó bien (ver 3.5).

## 3. Errores y comportamientos raros

### 3.1 Mensaje contradictorio cuando no se puede leer el único fichero (FALLO, menor)
Si `entrada/` tiene solo el extracto Cargo/Abono y todavía no hay histórico, el final dice:
```
❌ No hay histórico y la carpeta 'entrada/' está vacía.
   Suelta ahí los ficheros que te descargues del banco, ...
```
La carpeta NO está vacía: el fichero está ahí y no se ha podido leer. Un usuario novato puede pensar que lo ha dejado en el sitio equivocado.

### 3.2 Dos etiquetas con el mismo texto: el programa se cae y deja el histórico degradado (FALLO, serio)
Quería juntar Luz/Agua y Fibra/movil en una sola columna «Facturas», como en mi app. Puse en `ajustes/categorias.json`:
```json
"etiquetas": {"Piso":"Vivienda","Comida":"Supermercado","Luz/Agua":"Facturas","Fibra/movil":"Facturas","Ingresos":"Salario"}
```
`./ejecutar.sh` → código de salida 2 y:
```
── Resultado ───────────────────────────────────────────────────

── Avisos (1) ──────────────────────────────────────────────────
⚠️  ... «Ingresos» en etiquetas no es una categoría de gasto ...
❌ float() argument must be a string or a real number, not 'Series'
```
El mensaje no dice qué hice mal. Y lo peor: `datos/historico.xlsx` queda **reescrito a medias**. Las hojas pasan a estar en otro orden (`['MOVIMIENTOS','RESUMEN','_meta']` en vez de `RESUMEN` primero), RESUMEN tiene 0 gráficos (antes 3), no tiene formato de moneda ni paneles fijos, y lleva dos columnas «Facturas». Si lo ejecutas otra vez, esa versión degradada entra además en `datos/copias/` (`historico_20260925_091647.xlsx`, 12.661 bytes frente a los 16.438 de la buena). Los movimientos no se pierden (siguen los 85). Al quitar la etiqueta repetida y volver a ejecutar, el histórico se regenera bien, con sus 3 gráficos. Aun así, lo esperado sería un aviso claro («dos categorías con la misma etiqueta») y no tocar el histórico.

### 3.3 Saldo inicial negativo sin ningún comentario (RARO, puede que no sea fallo)
Con el CSV sin saldo más el extracto con saldo:
```
💰 Saldo inicial detectado: -1.550,83 €
```
Y el Acumulado de abril sale en −412,81 €. Tiene lógica: toma el saldo de julio y resta lo de abril-junio del CSV, que ha tomado por la misma cuenta. Pero yo no estaba en números rojos. Sospecho que a la exportación de mi otra app le faltan movimientos, y la herramienta no puede saberlo. Echo en falta un aviso cuando el saldo inicial deducido es negativo, del tipo «¿te falta algún movimiento anterior?».

### 3.4 «Cargos que se repiten»: Vodafone «desde 06/2026» (RARO)
`RECIBO VODAFONE · 35,00 € mensual · desde 06/2026`, pero hay recibos de Vodafone de 35 € en abril y mayo (del CSV, escritos «Recibo Vodafone»). El alquiler y Spotify, que vienen igual, sí salen «desde 04/2026». No sé por qué. Puede que los días del mes (8, 6, 11…) no le cuadren como mensual.

### 3.5 Cosas que fueron bien (sin fallo)
- **Nada desaparece de los totales** al cambiar las categorías. Con solo renombrar en `categorias.json` (sin reglas todavía), lo que no tiene regla cae en «Otros» o en «Salario». Total Gastos y Balance salen idénticos al céntimo en todas las pruebas (sep: gastos 1.074,79, ingresos 2.150,00, balance +1.075,21). El aviso es claro: `«Supermercado» está en categorias.json pero ninguna regla la asigna: su columna saldrá siempre a 0.`
- **(d) Devolución de NATURGY**: con mis reglas (`"naturgy": "Facturas"`), junio queda en Facturas 31,02 = 35,00 + 44,22 − 48,20. Resta, como debe. Con las categorías de fábrica sale Luz/Agua −3,98 en junio, en negativo, tal como explica la guía.
  Ojo: en el paso intermedio sin reglas, la devolución (+48,20) se contó como **Salario** e ingresos de junio = 2.198,20. Se arregla en cuanto pones la regla, pero no avisa de que una devolución ha ido a ingresos.
- **Cerrojo de `categoria_manual`**: puse «Restaurante» (sin s) a propósito en una fila y lo ignoró con un aviso muy claro: `Las he IGNORADO y he dejado que manden las reglas, para que no desaparezcan de los totales sin avisar.`
- **Solapes con otra capitalización**: un CSV de la otra app con «Recibo Alquiler C/ Mayor 12» del 01/07, que ya estaba como «RECIBO ALQUILER C/ MAYOR 12» en el extracto, no se duplicó (`87 movimientos ya estaban`).
- `app/reglas.py` para probar reglas es muy útil. Pequeña pega: si pasas varios textos y números mezclados, toma el último número como importe para todos y el «48.2» lo trata como una descripción. La guía dice «un número al final», así que fue culpa mía (preferencia).

## 4. Lo que no entendí de la guía, la web y los mensajes

- **Cómo usar MIS nombres de categoría.** La guía ofrece dos vías y no dice cuál elegir:
  1. Cambiar los nombres en `categorias.json` y poner reglas: `Reglas: 6 tuyas + 107 de la base. 119 reglas de la base descartadas: apuntan a categorías que no tienes en categorias.json. (… mercadona, carrefour, endesa, iberdrola, movistar …)`. Es decir, al usar «Supermercado» pierdo Mercadona, Carrefour, Endesa… y para recuperarlas tengo que repetir a mano más de 100 claves de la base. No se explica en ningún sitio que ese es el precio.
  2. `etiquetas`: solo cambia el rótulo del RESUMEN. La columna G de MOVIMIENTOS sigue diciendo «Comida», «Piso»… y no permite juntar dos categorías en una (y si lo intentas, se cae: 3.2).
- La etiqueta para «Ingresos» solo vale con `desglosar_ingresos`. El aviso lo explica bien, pero en la guía está escondido en una frase.
- La guía manda editar `bank_io.py` (ALIAS_COLUMNAS, PISTAS_…), mientras LEEME y la guía dicen que `app/` no se toca y que «se reemplaza entera con cada versión». Si lo edito, lo pierdo al actualizar.
- «asumo cuenta» para el CSV de la otra app: me pareció bien, pero no sé qué pasaría si el CSV mezclara cuenta y tarjeta.

## 5. Lo que echo en falta

1. **Soporte de Cargo/Abono** (o Debe/Haber) en dos columnas. Muchos bancos españoles lo usan. Es lo único que me impidió usarlo «tal cual».
2. **Una sección «Si vienes de otra app»** en la guía: que el CSV se puede meter, que su columna de categoría se ignora y cómo pasarla a `categoria_manual`. Mejor aún, que leyera una columna `categoria`/`category` del fichero y la usara como `categoria_manual` si coincide con `categorias.json`.
3. **Un mapeo de categorías**: poder decir «Comida → Supermercado», «Luz/Agua + Fibra/movil → Facturas», de modo que las reglas de la base sigan valiendo con mis nombres, sin repetir 119 claves.
4. Validar `etiquetas` duplicadas antes de escribir nada, y no reescribir el histórico si algo falla a mitad.
5. Un aviso cuando el saldo inicial deducido sale negativo.

## 6. Valoración: 6/10

Lo bueno de verdad: instalación sin problemas, cuadra con el banco al céntimo y ningún movimiento se pierde de los totales, pruebe lo que pruebe (los cerrojos funcionan y avisan con mensajes claros). La devolución resta donde debe, y el CSV de la otra app entró sin tocarlo y sin duplicados.

Lo que baja la nota: mi banco (Cargo/Abono) no se lee sin retocar el Excel, y la web promete «cualquier banco». La migración desde otra app no aparece en la documentación. Quedarme con mis categorías cuesta mucho más de lo esperado: o pierdo 119 reglas de la base, o solo cambio los rótulos. Y un intento razonable con `etiquetas` hace caer el programa y deja el histórico sin formato ni gráficos.

Esperaba una tarde; me ha costado un par de horas y un script, y un usuario sin mano con Excel se habría quedado en el primer paso.
