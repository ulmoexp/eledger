# Informe de uso: Irene (cuenta conjunta y dos tarjetas)

Versión probada: **2.12.1** (sale en la primera línea: «Movimientos bancarios · versión 2.12.1»). Linux, lanzadores `.sh`.

## 1. Perfil y qué intenté

Soy Irene, 38 años, administrativa. Llevo las cuentas de casa con mi pareja en Excel y no sé programar. Tenemos:
- `movimientos_cuenta_conjunta.csv`: la cuenta conjunta. Aquí entran las dos nóminas y se pagan la hipoteca, los recibos, el súper y las liquidaciones de las tarjetas.
- `Tarjeta_1111_movimientos.xls` (la mía) y `Tarjeta_2222_movimientos.xls` (la de mi pareja). En realidad son XML de Office.

Pasos que seguí:
1. Leí LEEME.txt, GUIA.pdf y la web.
2. Lancé `instalar.sh`. Fue bien a la primera: «Listo. Ya puedes usar ejecutar.sh».
3. Ejecuté `ejecutar.sh` sin nada. Me creó `entrada/` y `ajustes/`, y me dijo que soltara los ficheros ahí. El mensaje es claro.
4. Solté los tres ficheros sin configurar nada (1.ª ejecución).
5. Excluí las liquidaciones en `exclude_patterns.json`, declaré las tres cuentas en `cuentas.json` y volví a ejecutar (2.ª ejecución).
6. Revisé `datos/historico.xlsx` con openpyxl y pandas, e hice algunas pruebas más.

Configuración final:
```json
// exclude_patterns.json
["liquidacion tarjeta 1111", "liquidacion tarjeta 2222"]
// cuentas.json
{"conjunta": "conjunta", "1111": "tarjeta Irene", "2222": "tarjeta pareja"}
```

Cómo quedaron mis seis objetivos:
| Objetivo | Resultado |
|---|---|
| (a) Nada contado dos veces | **Sí**, pero las liquidaciones tuve que encontrarlas yo (ver 3.2) |
| (b) Gasto de cada tarjeta por separado | **A medias.** La columna `cuenta` lo permite, pero el RESUMEN no lo desglosa y mi hoja de fórmulas se borró (ver 3.3) |
| (c) Los 4 cafés del 14/08 | **Sin `cuentas.json` salen 2 de 4** (fallo 3.1). Con `cuentas.json` salen los 4 |
| (d) La devolución de PRIMARK | **Bien.** Resta de «Otros» y no cuenta como ingreso |
| (e) Cargos que se repiten | **Bien en lo que sale**: ni súper ni cafetería. Falta Orange (ver 3.4) |
| (f) Acumulado frente al saldo del banco | **Bien.** «🧮 Cuadra con el banco: 7.819,74 € a 28/09/2026, igual que el extracto.» |

## 2. Dónde me atasqué

- **Las liquidaciones de las tarjetas.** LEEME y la guía prometen que si dejo `exclude_patterns.json` vacío, la herramienta «busca en la cuenta un cargo que cuadre con lo que suma la tarjeta ese mes y propone la línea lista para pegar aquí». Conmigo no lo hizo: «DOS VECES y no lo he sabido encontrar solo». Al final miré el CSV y escribí los patrones yo. Me costó poco porque el concepto es obvio («LIQUIDACION TARJETA 1111»), pero esperaba la ayuda prometida.
- **Ver el gasto de cada tarjeta.** No sabía si `cuentas.json` servía para tarjetas. La guía dice «Solo hace falta si tienes más de una cuenta del mismo tipo (dos cuentas corrientes, por ejemplo)» y la web dice «Varias cuentas del mismo banco». No habla de dos tarjetas. Lo probé y funciona: cada fichero sale con «· cuenta: tarjeta Irene» o «· cuenta: tarjeta pareja», y la columna N de MOVIMIENTOS se rellena. Pero ni la hoja RESUMEN ni la pantalla desglosan por cuenta. Lo tengo que montar yo, y lo que monté se borró (3.3).

## 3. Errores o comportamientos raros

### 3.1 FALLO: sin `cuentas.json`, dos cafés reales desaparecen sin avisar
- **Cómo reproducirlo:** carpeta nueva, los tres ficheros en `entrada/`, `ajustes/` de fábrica, `./ejecutar.sh`.
- **Salida:** «🔁 2 movimientos ya estaban (en el histórico o en otro extracto); no se cuentan dos veces. ➕ 115 movimientos nuevos.» Entre los tres ficheros hay 35 + 36 + 46 = 117 movimientos.
- **Lo que pasa:** en el histórico, el 14/08 solo quedan los 2 cafés de 2,60 € de `Tarjeta_1111`. Los 2 de `Tarjeta_2222` se han tomado por duplicados, y son cafés reales.
- **Cómo lo comprobé:** según el histórico, la tarjeta 2222 gastó 241,21 € en agosto, pero el banco le liquidó 246,41 € el 02/09. La diferencia es 5,20 €, justo los dos cafés perdidos.
- **Qué cuesta:** una pareja con dos tarjetas del mismo banco puede perder gastos sin enterarse. El mensaje suena a buena noticia («no se cuentan dos veces»). La web promete «no cuenta nada dos veces», y la guía dice «Dos cargos idénticos el mismo día en el mismo sitio son dos gastos reales», aunque luego aclara que se descartan si vienen de ficheros distintos. Con dos tarjetas eso es justo lo habitual.
- **Cómo se arregla:** declarando `cuentas.json`. En la siguiente ejecución recuperó los 2 que faltaban («➕ 2 movimientos nuevos») y ahora salen **4 cafés** (n_rep 0 y 1 en cada tarjeta). Pero nada me dirigió a `cuentas.json`: lo busqué porque tenía ese objetivo. Echo en falta un aviso cuando se descartan como duplicados movimientos que vienen de dos ficheros del mismo tipo.

### 3.2 FALLO: con dos tarjetas no detecta el recibo de la tarjeta
- **Cómo reproducirlo:** los tres ficheros y `exclude_patterns.json` vacío. Da igual si `cuentas.json` está declarado o no.
- **Salida:** «⚠️ Tienes movimientos de tarjeta y ningún patrón en exclude_patterns.json … DOS VECES y no lo he sabido encontrar solo.»
- **Lo que pasa:** los importes cuadran al céntimo con cada tarjeta por separado. En julio, la tarjeta 1111 suma 200,47 € y hay un cargo de 200,47 € el 02/08. La tarjeta 2222 suma 263,52 € y hay un cargo de 263,52 € ese mismo día.
- **Prueba de control:** con solo la conjunta y la tarjeta 1111, sí lo encuentra: «2026-07: la tarjeta suma 200,47 € y tu cuenta tiene un cargo de 200,47 € el 02/08/2026 («LIQUIDACION TARJETA 1111»)». Así que falla al haber dos tarjetas. Por lo que veo desde fuera, parece que junta las dos tarjetas y ya no cuadra con ningún cargo.
- **Menor:** incluso con una sola tarjeta dice «No encuentro una clave segura que proponer … añádelo tú a mano». La guía promete «propone la línea lista para pegar aquí».
- **Relacionado, y peligroso:** en la 1.ª ejecución, «Sin clasificar» me propone `añade a rules.json: "liquidacion": "PON_TU_CATEGORIA"`. Si le hago caso, clasifico el recibo de la tarjeta como gasto en vez de excluirlo, y cuento las compras dos veces. Una persona novata lo haría.

### 3.3 FALLO: una hoja mía dentro de `historico.xlsx` se borra sin avisar
- **Cómo reproducirlo:** abro `datos/historico.xlsx` y añado una hoja `TARJETAS` con `=-SUMIFS(MOVIMIENTOS!C:C;MOVIMIENTOS!N:N;"tarjeta Irene";MOVIMIENTOS!F:F;A2)`, una columna por tarjeta. Guardo y ejecuto `./ejecutar.sh`.
- **Resultado:** el libro vuelve a tener solo `['RESUMEN', 'MOVIMIENTOS', '_meta']`. Por pantalla no sale nada sobre la hoja perdida.
- **Lo que sí hay:** la hoja se conserva en `datos/copias/historico_20260925_091653.xlsx`.
- **Lo que dice la guía:** solo avisa de que «El resto de la hoja se regenera», refiriéndose a MOVIMIENTOS. No dice que las hojas añadidas se pierdan. Para alguien que usa Excel, lo natural es añadir su pestaña al histórico. Me faltó un aviso o una frase clara del tipo «no añadas hojas aquí; usa sincronizar.json».

### 3.4 Raro: Orange no sale en «Cargos que se repiten»
- **Los datos:** «RECIBO ORANGE ESPAGNE» cuesta 54,95 € los tres meses (20/07, 17/08 y 22/09) y se clasifica como `Fibra/movil [orange · base]`.
- **Lo que sale:** la lista trae hipoteca, escuela infantil, Iberdrola (cuyo importe cambia) y Mapfre, pero no Orange. Es la suscripción más clara que tenemos. No sé por qué.
- **Lo que está bien:** no aparecen ni el súper ni la cafetería.

### 3.5 Contadores confusos (preferencia)
- En la 2.ª ejecución pone «🔁 115 movimientos ya estaban … ➕ 2 movimientos nuevos» y, justo después, «113 movimientos · 4 excluidos». Tuve que echar cuentas para ver que 113 + 4 = 117.
- En la 1.ª ejecución, «115 movimientos · 0 excluidos» no deja ver que faltan 2.

### 3.6 Menor: el importe del probador se aplica a todos los conceptos
- `python3 app/reglas.py "LIQUIDACION TARJETA 1111" "RECIBO ORANGE ESPAGNE" "DEVOLUCION PRIMARK" 24.99` asigna 24,99 € a los tres conceptos.
- Se puede entender, pero lo que yo quería era poner el importe solo al último.

## 4. Lo que no entendí de la guía, la web y los mensajes

- **Si `cuentas.json` vale para tarjetas.** La guía y la web solo hablan de «cuentas» y de «dos cuentas corrientes». Además, la clave es un trozo del nombre del fichero: no sabía si «1111» casaría dentro de `Tarjeta_1111_…`, con el guion bajo delante. Casó.
- **Los números del RESUMEN.** «Fuera del balance» sale 463,99 € en julio y −78,61 € en septiembre. Tras leer la guía («las compras con tarjeta que el banco todavía no ha cargado») lo entendí. Julio es lo que gastamos con las tarjetas y aún no se ha liquidado. Pero un número negativo ahí asusta.
- **Hipoteca y seguro en «Piso».** La hipoteca va a «Piso» y la categoría «Prestamos» se queda a 0. Tiene sentido, pero me pregunté para qué es «Prestamos». Es una preferencia, no un fallo.
- **`movimientos_limpios.xlsx` no trae la columna `cuenta`.** Sus columnas son fecha, descripcion, importe, tipo, mes, mes_ajustado, categoria, origen y regla. Si pego eso en mi Excel, como dice la guía, no puedo separar la tarjeta mía de la de mi pareja. Solo `historico.xlsx` tiene la columna N.

## 5. Lo que echo en falta

1. Un desglose por cuenta o tarjeta en RESUMEN, o una línea por pantalla del tipo «tarjeta Irene: 312,87 € en agosto», cuando hay `cuentas.json`.
2. Que el detector del recibo funcione con dos tarjetas, emparejando cada liquidación con su tarjeta.
3. Un aviso cuando se descartan como «ya estaban» movimientos que vienen de dos ficheros distintos del mismo tipo, con una sugerencia de declarar `cuentas.json`.
4. Una frase en la guía: «dos tarjetas del mismo banco también cuentan como dos cuentas».
5. Que `movimientos_limpios.xlsx` traiga también la columna `cuenta`, al final para no mover A–G.
6. Que avise, o que no borre, si añado hojas al histórico.

## 6. Valoración: 7/10

**Lo que funcionó bien:**
- Instalar y ejecutar, sin tropiezos.
- Los tres formatos se leyeron solos, incluido el «.xls» que es XML.
- La devolución de PRIMARK resta donde debe y no cuenta como ingreso.
- El Acumulado cuadra al céntimo con el saldo del banco (7.819,74 €), y el mensaje «🧮 Cuadra con el banco» da mucha confianza.
- «Cargos que se repiten» no se inventa recibos.
- Con `cuentas.json` salen los 4 cafés y cada movimiento lleva su tarjeta.

**Por qué no le pongo más:**
- En nuestro caso, que es muy habitual (una pareja con dos tarjetas), la configuración de fábrica **pierde gastos reales en silencio** (3.1).
- La ayuda para detectar el recibo de la tarjeta no funciona con dos tarjetas (3.2).
- Separar el gasto de cada uno me obliga a montar fórmulas, y si las pongo en el histórico se borran (3.3).

Con los avisos del punto 5 le pondría un 9.
