# Informe de Ana (27 años, enfermera). eledger 2.12.0 en Linux

## 1. Perfil y qué intenté

Uso el móvil para todo. Tengo una tarjeta de un neobanco (CSV en inglés, tal cual sale de la app) y una tarjeta de débito de un banco español (`.xls`). No tengo extracto de "cuenta de toda la vida". Llevo mis cuentas en un Excel muy sencillo.

Lo que hice:
1. Leí la portada (`web/index.html`), la guía web y `LEEME.txt`. Ejecuté `./instalar.sh` y luego `./ejecutar.sh`.
2. Eché en `entrada/` todo lo que tenía en Descargas: el CSV del neobanco, `tarjeta_debito.xls`, `Recibo_alquiler_julio.pdf` y `extracto_vacio.xls` (0 bytes).
3. Creé `eledger/mis_cuentas.xlsx`, con una hoja MOVIMIENTOS vacía y otra RESUMEN con `=-SUMIF(MOVIMIENTOS!G:G,"Comida",MOVIMIENTOS!C:C)` y otras fórmulas parecidas. Puse `"archivo": "mis_cuentas.xlsx"` en `ajustes/sincronizar.json` y volví a ejecutar.
4. Clasifiqué mis recargas ("Top-Up") y añadí un extracto de junio (más antiguo) para ver cómo se comporta la sincronización cuando entran datos nuevos.
5. Ejecuté `./exportar.sh` para pasárselo a una amiga y miré qué había dentro del ZIP.

**Lo que fue bien, y bastante:**
- El CSV del neobanco se lee **perfecto**: importes con punto decimal (`400.00` → 400, `-10.99` → -10,99), fechas con hora (`2026-07-01 10:15:00` → 01/07/2026) y signos correctos. Las comisiones no aparecen porque este CSV no trae esa columna.
- El `.xls` de la tarjeta, que en realidad es XML, se detecta solo: `formato=xml_ss, cabecera en fila 3, 9 movimientos`, `→ tarjeta (columna «importe de la operacion»)`.
- Si ejecuto otra vez, no se duplica nada: `🔁 27 movimientos ya estaban`.
- El Acumulado (+696,49 € al final) coincide con lo que me queda en el neobanco.
- La sincronización funciona y **mis fórmulas de RESUMEN siguen intactas**. Las recalculé en LibreOffice y dan el resultado correcto. Además hace una copia de seguridad de mi fichero antes de cada escritura.
- El seguro contra fórmulas funciona: puse una fórmula en MOVIMIENTOS y se negó con un mensaje claro: «La hoja «MOVIMIENTOS» contiene fórmulas (I2...). No la sobreescribo … Tu fichero de contabilidad NO se ha tocado.»
- La exportación es limpia: 34 ficheros, entre ellos programa, guía, plantillas genéricas y lanzadores. No lleva `ajustes/`, `datos/`, `entrada/`, `salida/` ni `mis_cuentas.xlsx`. Busqué "Top-Up", "*1234" y mis notas dentro del ZIP y no aparecen.
- Detecta Spotify como cargo que se repite: «131,88 €/año · 10,99 € mensual». Justo lo que prometía la portada.

## 2. Dónde me atasqué

- **No existía la carpeta `entrada/`.** La portada dice «Deja los extractos del banco, tal cual, en `entrada/`», pero en el ZIP descomprimido no hay `entrada/` ni `ajustes/`. Se crean la primera vez que ejecutas, y esa ejecución termina con «❌ No hay histórico y la carpeta 'entrada/' está vacía». Esperaba encontrar la carpeta nada más descomprimir. Lo resolví ejecutando una vez en vacío.
- **El resumen del primer intento no tenía sentido para mí:** «Último mes (2026-09): gastos -98,68 € · ingresos 0,00 € · balance +98,68 €». ¿Gastos negativos? El motivo es que mis recargas (`Top-Up by *1234`, +400 €) no casaban con ninguna regla, acabaron en **Otros**, que es una categoría de gasto, y restaron de los gastos (Otros = -320,76 en julio). El programa sí me avisó en «Sin clasificar», pero la sugerencia es `"top": "PON_TU_CATEGORIA"` y no me dice qué categoría usar. Encontré `Transferencias internas` leyendo `categorias.json` («Los traspasos entre tus propias cuentas van aquí»). Con eso ya salió bien: «gastos 301,32 € · … · balance -301,32 €».
- **¿`"archivo"` es relativo a qué?** `sincronizar.json` dice «Si está en la misma carpeta, basta el nombre», pero no aclara si es la carpeta de `eledger/` o la de `ajustes/`. Probé con la de `eledger/` y funcionó.

## 3. Errores o comportamientos raros

**F = fallo, P = preferencia**

1. **(F, grave para mí) Mis notas en una columna extra se desalinean.** La herramienta respeta que yo tenga una columna H «mis notas» en MOVIMIENTOS, pero la deja fija por número de fila y no la mueve con su movimiento.
   - Cómo reproducirlo: después de sincronizar, escribe en `H1`=`mis notas` y en `H3`=`regalo mamá` (la fila 3 es Spotify, 02/07). Luego mete en `entrada/` un CSV con un movimiento más antiguo (`2026-06-20 …,Primark,-12.50,…`) y ejecuta.
   - Resultado: «regalo mamá» aparece ahora junto a `Top-Up by *1234 … Transferencias internas`, sin ningún aviso.
   - La guía no dice que no se puedan tener columnas propias, y como la herramienta las conserva, parece que se pueden usar. O se avisa, o se documenta «no escribas nada junto a los datos».
2. **(F) Mensaje del fichero vacío contradictorio y técnico.** Con `extracto_vacio.xls` (0 bytes) sale:
   > 'extracto_vacio.xls' se ha leído bien (formato: texto) pero no encuentro una fila de cabecera con ['fecha', 'descripcion', 'importe']. Añade el nombre que use tu banco a ALIAS_COLUMNAS en bank_io.py.

   No se ha «leído bien»: está vacío. Y me manda a editar código Python. Esperaba algo como «Este fichero está vacío (0 bytes). Vuelve a descargarlo».
3. **(F menor) El PDF se ignora sin decir nada.** `Recibo_alquiler_julio.pdf` no aparece en la lista de «Leyendo entrada/». No pasa nada malo, pero no sé si lo ha visto. La guía solo menciona los PDF cuando `entrada/` se queda vacía («Comprueba que lo que has soltado no es un .zip ni un .pdf»). Me bastaría una línea: «· Recibo_alquiler_julio.pdf: ignorado (los PDF no se leen)».
4. **(F menor) El instalador de Linux me manda al lanzador de Mac.** `./instalar.sh` termina con «Listo. Ya puedes usar ejecutar.command». En Linux es `ejecutar.sh`. Los dos ficheros son idénticos, y se nota.
5. **(Raro) Signo en «Sin clasificar».** Las tres recargas son +400 € cada una, pero salen como «-1.200,00 € · 3 mov. · top». Imagino que usa el criterio de «gasto en positivo», pero para dinero que entra confunde.
6. **(P) Aviso de tarjeta contada dos veces que no me aplica.** «⚠️ Ojo: puede que los gastos de la tarjeta se estén contando dos veces». No tengo extracto de la cuenta que paga la tarjeta, así que no hay doble conteo. Me sale en cada ejecución y no sé cómo decirle «esto no me pasa» sin inventarme un patrón.
7. **(P) El neobanco sale como «cuenta (sin pistas claras, asumo cuenta)».** Es correcto a efectos prácticos, pero la frase no da mucha confianza.
8. **(P) Pequeña incoherencia de ruta.** En `sincronizar.json` pone «copia de seguridad en copias/», pero la copia va a `datos/copias/`. La guía PDF sí lo dice bien.

## 4. Lo que no entendí de la guía, la web o los mensajes

- La portada y la guía hablan de «cuenta y tarjetas» y del «recibo de la tarjeta». Yo no tengo cuenta, solo dos tarjetas. No sabía si la herramienta servía para mi caso. Sirve, pero lo descubrí probando.
- «Fuera del balance» valía 99 € en julio, que resulta ser justo lo de la tarjeta de débito. No entendí por qué mis compras con tarjeta cuentan como gasto y a la vez aparecen «fuera del balance». Lo explica «Cómo se calcula el resumen» («las compras con tarjeta que el banco aún no ha cargado»), pero en mi caso esa tarjeta sí se carga.
- El resumen trae columnas `Hijos`, `Perros`, `Prestamos` que no van conmigo. Entiendo que se cambian en `categorias.json`, pero la primera impresión es de plantilla ajena.

## 5. Lo que echo en falta

- En la portada: **qué bancos o formatos funcionan**, y en concreto si vale un neobanco con el extracto en inglés. Funciona muy bien, así que merece la pena decirlo.
- En la portada: la **sincronización con mi propio Excel** y el **«pásaselo a alguien sin tus datos»**. Son justo las dos cosas que me convencieron y no se mencionan.
- Que el resumen proponga una **categoría concreta** para lo que no se clasifica, sobre todo para recargas o traspasos («¿son traspasos entre tus cuentas? → Transferencias internas»), y que lo que entra de dinero sin clasificar no acabe restando de los gastos en «Otros».
- Que al descomprimir ya estén `entrada/` y `ajustes/`.
- Algo para el móvil, aunque sea una línea que diga cómo pasar al ordenador los extractos que descargo en la app. Sé que es de escritorio, y la portada lo deja claro con «Windows · Mac · Linux».
- (P) El ZIP que se da a otras personas y el de la release llevan `TRASPASO.md`, `COMPILAR.md`, `eledger.spec` y `compilar.bat`. Para mi amiga son ruido.

## 6. Valoración: 7/10

**La portada:** en 30 segundos se entiende qué hace («Tus movimientos bancarios, clasificados sin salir de tu ordenador … te deja un Excel») y que es privada. El ejemplo del resumen ayuda mucho. Lo que no dice es si vale para alguien que solo tiene tarjetas y un neobanco. Por lo que pone, podría pensar que es para gente con «cuenta de toda la vida».

**El uso:** lo difícil funciona de verdad. Lee un CSV en inglés y un «.xls» que es XML sin tocar nada, no duplica, sincroniza con mi Excel sin romper las fórmulas, se niega a escribir cuando debe y la exportación no lleva nada mío.

**Lo que resta:**
- El primer resumen con «gastos -98,68 €» por culpa de las recargas en «Otros». La primera impresión es que la herramienta está mal.
- El desalineado silencioso de mis notas en la sincronización, que es un fallo real.
- El mensaje del fichero vacío, que me manda a tocar `bank_io.py`.
- Que falten `entrada/` y `ajustes/` al descomprimir.
