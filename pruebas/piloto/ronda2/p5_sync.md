# Informe de piloto: Carmen (sincronizar con mi propio Excel)

Versión probada: **2.12.1** (sale en la primera línea: «Movimientos bancarios · versión 2.12.1»). Linux, lanzadores `.sh`.

## 1. Perfil y qué intenté

Soy Carmen, 49 años, funcionaria. Llevo mis cuentas en `mi_contabilidad.xlsx`: hoja «Datos» (Fecha, Concepto, Importe, Categoría) con junio metido a mano, y hoja «Totales» con `=SUMIF(Datos!D:D,A2,Datos!C:C)` por categoría. No quiero el Excel de la herramienta, solo dejar de copiar y pegar. La portada dice: «Rellena tu propio Excel. Si ya llevas tus cuentas en una hoja, vuelca ahí los movimientos sin tocar tus fórmulas ni tus notas».

Lo que hice:
1. Leí LEEME.txt, la sección «Sincronizar con tu contabilidad» de GUIA.pdf (págs. 13-15) y la de la web.
2. `./instalar.sh` sin problemas. Primera ejecución con `extracto_julio_sept.xls` en `entrada/`: 30 movimientos, «Cuadra con el banco». Todo claro.
3. Configuré `ajustes/sincronizar.json` sobre una **copia** (lo aconseja el propio JSON: «DÉJALO VACÍO hasta que hayas probado sobre una copia»): `archivo: "copia_contabilidad.xlsx"` (en la carpeta del programa), `hoja: "Datos"`.
4. Probé los seguros (hoja mal escrita, apuntar a «Totales»), luego `fila_inicial: 6` para no pisar junio, adapté mis fórmulas, añadí una nota, forcé movimientos nuevos por medio y probé con el fichero abierto (lock de LibreOffice y de Excel).

## 2. Dónde me atasqué

**a) Primera sincronización: me borró junio y me dejó los Totales a cero, sin avisar.**
Esperaba que se añadieran julio-septiembre debajo de mis filas de junio (eso entiendo por «volcar» y por «En vez de copiar y pegar cada mes»). Con la configuración de ejemplo (`fila_inicial: 1`, `columna_inicial: 1`) y `hoja: "Datos"`, la salida fue solo:

```
📗 copia_contabilidad.xlsx · hoja Datos: 30 filas escritas
   copia de seguridad en .../datos/copias/copia_contabilidad_20260925_091519.xlsx
```

y ningún aviso. Al abrir la copia:
- Mis 4 filas de junio **habían desaparecido**.
- Mis cabeceras «Fecha, Concepto, Importe, Categoría» se habían cambiado por `fecha, descripcion, importe, tipo, mes, mes_ajustado, categoria`.
- La columna D ya no es la categoría sino `tipo` («cuenta»), así que mis `SUMIF(Datos!D:D,...)` dan **0 en todas las categorías** (recalculado con LibreOffice: `('Piso', 0), ('Luz/Agua', 0), ('Comida', 0), ('Ingresos', 0)`; en el original daban -612 / -55,1 / -64,35 / 1740).

Las fórmulas «sobreviven» en sentido literal (siguen escritas), pero dejan de dar bien. Nada en la guía me avisaba de que la hoja de destino se **reescribe entera** desde la esquina indicada, ni de que la herramienta pone **sus** columnas y **sus** cabeceras. Lo más parecido es la fila «El histórico encoge… Las filas sobrantes se eliminan», que solo se entiende después de que te haya pasado.

**b) No puedo elegir qué columnas escribe ni en qué orden.** No hay ninguna opción documentada para decir «la categoría va en D» ni para renombrar cabeceras. Solo `fila_inicial` y `columna_inicial` (que además **no aparecen en la web**, solo en el PDF y en el JSON).

**c) Cómo lo adapté (funciona, pero me ha costado):** `fila_inicial: 6` (justo debajo de junio) y cambiar las fórmulas de Totales a `=SUMIF(Datos!D:D,A2,Datos!C:C)+SUMIF(Datos!G:G,A2,Datos!C:C)`. Resultado: junio intacto en A1:D5, en la fila 6 una segunda cabecera de la herramienta y debajo julio-sept (y después las filas que añadí). Totales correctos (Piso -2448 = 4×612, Ingresos 6960 = 4×1740, Luz/Agua -243,58 comprobado a mano). Queda feo (dos cabeceras distintas en la misma hoja) y una usuaria como yo no llega a esto sola sin saber de fórmulas.

**d) «Si está en la misma carpeta, basta el nombre»** (comentario del JSON): ¿misma carpeta que qué, que `ajustes/sincronizar.json` o que el programa? Probé poniendo el fichero en la carpeta principal y funcionó; con ruta absoluta también.

## 3. Errores o comportamientos raros

**FALLO 1 (grave): el fichero abierto NO se detecta; se escribe igualmente.** La guía dice: «El libro está abierto en OnlyOffice o Excel → Se avisa de que lo cierres. No se escribe a medias.» Reproducción:
```
cd eledger
touch '.~lock.copia_contabilidad.xlsx#'          # como LibreOffice
./ejecutar.sh
→ 📗 copia_contabilidad.xlsx · hoja Datos: 32 filas escritas
```
El md5 del fichero cambia (3936056c… → d5392b22…). Lo mismo con contenido realista del lock (`Carmen,carmen,pc-carmen,25.09.2026 09:20,...`), con el lock de Excel `~$copia_contabilidad.xlsx`, y con el fichero en otra carpeta y ruta absoluta. En cambio, con `datos/.~lock.historico.xlsx#` el histórico SÍ se detecta («datos/historico.xlsx estaba abierto: el resultado está en … (copia …).xlsx»). O sea, la protección existe para el histórico pero no para mi fichero, al menos en Linux/LibreOffice. En la vida real, si guardo en LibreOffice después, pisaría lo que ha escrito la herramienta (o al revés). No he podido probar en Windows con Excel real.

**FALLO 2 (grave, consecuencia de 2a): borra filas que no son suyas sin decir nada.** Si la hoja de destino tiene filas que no están en el histórico (mis 4 de junio), las sobrescribe sin aviso. La herramienta ya sabe emparejar filas con movimientos (lo hace con las notas), así que podría decir «hay 4 filas en tu hoja que no vienen del histórico; no escribo» o al menos avisar.

**FALLO 3 (agrava el 2): la única copia con mis datos de junio desaparece a las 10 ejecuciones.** Cada ejecución reescribe el fichero y hace una copia **aunque no haya nada nuevo** (el md5 cambia en cada pasada). Con `copias_de_seguridad: 10`, tras 10 ejecuciones la copia `copia_contabilidad_20260925_091519.xlsx` (la única que tenía junio) se borró. Quien no haya trabajado sobre una copia y no se dé cuenta a tiempo pierde sus filas para siempre.

**Raro (menor):** dos ejecuciones en el mismo segundo generan copias con el mismo nombre (vi `..._091644.xlsx` en dos ejecuciones seguidas); la segunda pisa a la primera. Y las copias de dos ficheros distintos llamados igual (uno en `eledger/` y otro en `descargas/prueba/`) se mezclan en la misma rotación.

**Raro (menor, solo en el histórico):** en `MOVIMIENTOS` del histórico, el 28/08 hay tres movimientos y la columna `saldo` sale 2467.48, 2447.3, 2522.21: están ordenados por descripción, no en el orden del banco, y el saldo parece saltar. No afecta a mi fichero (la columna saldo no se sincroniza).

**Lo que funcionó bien (no son fallos):**
- Hoja mal escrita (`hoja: "Banco"`): «El libro no tiene ninguna hoja llamada «Banco». Hojas disponibles: Datos, Totales. Tu fichero de contabilidad NO se ha tocado.» Perfecto.
- Apuntar a «Totales»: «La hoja «Totales» contiene fórmulas (B2, B3, B4, B5...). No la sobreescribo». El fichero no cambió (mismo md5). Perfecto.
- **Notas (objetivo d):** puse «cumple de Lucía, pagué yo la tarta» en H junto a COMPRA CONSUM 12/07 -88,83. Al volver a ejecutar sigue ahí. Añadí dos movimientos de julio anteriores (05/07 y 09/07, con un CSV de tarjeta de prueba) y la nota se movió de la fila 9 a la 11, junto a su movimiento: «ℹ️ 1 notas tuyas recolocadas junto a su movimiento (han entrado movimientos por medio).» Muy bien. Incluso mi cabecera «Mis notas» en H6 se conservó.
- Formatos: mis celdas de junio mantienen su formato; las nuevas salen con `DD/MM/YYYY` y `#,##0.00 €`. Mi fichero original en `descargas/` nunca se tocó.
- Las categorías de la base (Piso, Luz/Agua, Comida, Ingresos) coinciden con las mías sin configurar nada. Aparecen además «Higiene» y «Fibra/movil», que tendría que añadir a Totales.
- (Por el CSV de prueba) saltó el aviso de doble conteo de tarjeta comparando 20,55 € con un cargo de FARMACIA de 20,56 €: falso positivo provocado por mi prueba, lo cuento solo como curiosidad; el aviso es prudente («No encuentro una clave segura que proponer»).

## 4. Lo que no entendí de la guía / web / mensajes

- Que la sincronización **sustituye** el contenido de la hoja desde la esquina indicada y no **añade**. Es lo más importante y no está dicho.
- Qué columnas escribe exactamente. La guía de «Uso en Excel» habla de «columnas A-G» y de `C = importe · G = categoria · F = mes_ajustado`, pero en la sección de sincronizar no se dice que esas mismas 7 columnas, con esas cabeceras, van a ir a mi hoja.
- La portada promete «sin tocar tus fórmulas ni tus notas». Técnicamente cierto, pero mis fórmulas quedaron dando 0. Me sentí engañada.
- La web no menciona `fila_inicial` ni `columna_inicial` ni lo de las notas; el PDF sí.
- En la tabla de seguros se habla de «OnlyOffice o Excel»; no sé si LibreOffice está contemplado (para el histórico sí lo está).
- «Si está en la misma carpeta, basta el nombre»: ¿qué carpeta?

## 5. Lo que echo en falta

- Un modo **«añadir debajo de lo que ya tengo»** (o que la guía diga claramente que no existe y proponga el truco de `fila_inicial`).
- Poder **elegir y ordenar las columnas** y sus cabeceras (p. ej. `"columnas": {"Fecha": "fecha", "Concepto": "descripcion", "Importe": "importe", "Categoría": "categoria"}`), o como mínimo no escribir cabecera.
- Un aviso antes de pisar filas que no vienen del histórico.
- Que si no hay nada nuevo no reescriba el fichero ni gaste una copia de seguridad; o que la primera copia (la de antes de la primera sincronización) no se rote nunca.
- Un ejemplo en la guía partiendo de un Excel típico «Fecha, Concepto, Importe, Categoría + hoja de totales», que es exactamente el caso de quien quiere usar esto.

## 6. Valoración: 5/10

Lo que hace, lo hace con cuidado: los seguros de hoja mal escrita y hoja con fórmulas son ejemplares, los mensajes son claros y las notas se recolocan de verdad. Pero para mi caso concreto (tener ya un Excel con datos y fórmulas), la primera sincronización siguiendo la documentación me borró junio y me dejó los totales a cero sin un solo aviso, y la protección de «fichero abierto» no funcionó con LibreOffice. Si no hubiera trabajado sobre una copia, me habría llevado un susto serio.

**¿Dejaría de copiar y pegar? (objetivo f)** Todavía no. Con el apaño (`fila_inicial` debajo de junio + fórmulas que suman D y G) funciona y los totales dan bien, pero: tengo que aceptar las columnas de la herramienta en vez de las mías, una segunda cabecera en mitad de la hoja, y no me fío de que escriba estando el fichero abierto. Si hubiera modo «añadir» con mis columnas y el aviso de fichero abierto funcionara, sí lo usaría cada mes sin dudar.

Distinción: **fallos** = 1 (lock no detectado), 2 (pisa filas ajenas sin aviso), 3 (la copia buena se rota al reescribir sin cambios), y la documentación que no dice que la hoja se reescribe. **Preferencias** = elegir columnas/cabeceras, modo añadir, que la web incluya `fila_inicial`.
