# Informe de Carmen (usuaria simulada, versión 2.14.0)

## 1. Perfil y qué intenté

Soy Carmen, 49 años, funcionaria. Llevo años con mi propio Excel (`mi_contabilidad.xlsx`): la hoja «Datos» (Fecha, Concepto, Importe, Categoría) con junio metido a mano, y la hoja «Totales» con `=SUMIF(Datos!D:D,A2,Datos!C:C)`. No quiero el Excel de la herramienta. Lo único que quiero es dejar de copiar y pegar.

Solo leí LEEME.txt, GUIA.pdf, la web y los comentarios de `ajustes/sincronizar.json`. Pasos:
1. `./instalar.sh`: sin problemas («Listo. Ya puedes usar ejecutar.sh»).
2. Dejé `extracto_julio_sept.xls` en `entrada/` y ejecuté una vez sin sincronizar, para ver qué categorías pone. Crea `ajustes/` sola.
3. El comentario del JSON dice «DÉJALO VACÍO hasta que hayas probado sobre una copia», así que copié mi fichero como `eledger/copia_contabilidad.xlsx` y en `ajustes/sincronizar.json` puse:
   `"archivo": "copia_contabilidad.xlsx", "hoja": "Datos", "modo": "añadir", "columnas": {"Fecha":"fecha","Concepto":"descripcion","Importe":"importe","Categoría":"categoria"}`.
   Esa línea de `columnas` es la que trae la guía, y coincide justo con mis cabeceras. Muy cómodo.
4. Probé los puntos (b) a (f), y además dos casos que me preocupaban: que yo ya hubiera tecleado a mano alguna fila de julio, y que borrara sin querer una fila del banco.

## 2. Dónde me atasqué

En ningún sitio de verdad. Me costó un poco decidir entre «tabla» y «añadir», pero la tabla de la guía lo deja claro: «añadir · Quien lleva años con su propia hoja y solo quiere dejar de copiar y pegar». Eso soy yo.

Un pequeño titubeo: la guía y la web no dicen en ningún momento «prueba primero sobre una copia». Eso solo aparece dentro del JSON («DÉJALO VACÍO hasta que hayas probado sobre una copia»). Lo vi porque abrí el JSON. Si hubiera seguido solo la guía, habría apuntado directamente a mi fichero bueno. Para ser justa, la herramienta hace una copia de seguridad antes de escribir.

## 3. Errores o comportamientos raros

No he encontrado ningún fallo que rompa nada. Esto es lo que me llamó la atención:

- **(Preferencia / cosa rara) El formato de las filas nuevas no es el de las mías.** Mis fechas de junio están en `yyyy-mm-dd` y mis importes en `General`. Las filas que añade salen con `DD/MM/YYYY` y `#,##0.00 €`. Los valores son correctos (fechas de verdad, números de verdad) y las sumas no cambian, pero la hoja queda con dos aspectos. Lo esperable sería que copiara el formato de mi última fila. Se reproduce con la primera ejecución con sincronización; se ve inspeccionando `number_format` de A5 frente a A6 y de C5 frente a C6.
- **(Cosa rara, menor) Se gasta una copia de `historico_*.xlsx` en cada ejecución, aunque no haya nada nuevo.** Ejecuté 12 veces seguidas sin cambiar nada:
  - Mi fichero: `ningún movimiento nuevo que añadir, no lo he tocado`, el md5 no cambia y no se gasta ninguna copia. Perfecto.
  - En cambio, `datos/copias/` recibe un `historico_AAAAMMDD_HHMMSS.xlsx` nuevo cada vez, y al llegar a 10 se borran los más antiguos. Si un día meto una regla mala y luego ejecuto diez veces «para probar», pierdo la copia del histórico de antes del error.
  - A mí no me afecta, porque no uso el histórico, pero no casa con la frase de la guía «Si no hay nada nuevo, el fichero no se toca y no se gasta ninguna». Esa frase habla de mi fichero, pero leída de pasada parece que vale para todo.
  - Lo bueno: la poda va por fichero, y mi `copia_contabilidad_*.xlsx` no se borró por culpa de las del histórico.
- **(Detalle de texto)** `1 añadidos debajo`, en plural con uno solo.
- **(Comportamiento documentado, que menciono porque me sorprendió un poco)** Si borro una fila del banco, vuelve, pero al final de la hoja, no en su sitio por fecha. Ejemplo: borré FARMACIA del 22/07 y reapareció en la fila 35, después de septiembre. La guía dice «se añaden debajo», así que es coherente. Mis SUMIF no dependen del orden.

## 4. Lo que no entendí de la guía, la web o los mensajes

- Casi todo lo entendí. Los mensajes por pantalla son claros. El del fichero abierto me pareció muy bueno: «'copia_contabilidad.xlsx' está abierto en otro programa. Guárdalo, ciérralo y vuelve a ejecutar… (lo sé por .~lock.copia_contabilidad.xlsx#; si NO lo tienes abierto, es un resto de un cierre en falso: bórralo) Tu fichero de contabilidad NO se ha tocado.»
- La tabla «Los seguros» menciona «Tienes notas tuyas al lado de los movimientos: se recolocan junto a su movimiento aunque entren otros por medio». En modo añadir nunca entra nada «por medio», porque todo va debajo. No sé si esa fila vale para los dos modos o solo para el modo tabla.
- La chuleta dice «Pulsa 1 para abrir el histórico». Para mí, que no quiero el histórico, sobra, pero es comprensible.

## 5. Lo que echo en falta

- **Un aviso cuando escribe en mi hoja una categoría que no aparece en mis Totales, o al menos que no aparece en las filas que ya había.**
  - La herramienta me ha puesto «Higiene» (farmacia, 103,38 €) y «Fibra/movil» (Jazztel, 114 €), que yo no tengo en «Totales». Mis totales no fallan, pero esos 217 € no salen en ningún total y nadie me lo dice.
  - Lo descubrí solo porque miré las filas una a una. Me bastaría con una línea del tipo «categorías nuevas en tu hoja que no usabas: Higiene, Fibra/movil».
  - Es una preferencia: la herramienta no tiene por qué conocer mi hoja de totales.
- Que la guía (sección «Sincronizar») diga en voz alta lo de «prueba primero con una copia», y no solo el JSON.
- Que las filas nuevas copien el formato de la fila de encima (ver punto 3).

## 6. Lo que salió bien (comprobado)

- **(b) Mis filas de junio siguen intactas** (filas 2 a 5, mismos valores y formato). Las 30 filas de julio a septiembre van justo debajo, en mis columnas A-D, con mis cabeceras. El libro recalculado con LibreOffice (`soffice --headless --convert-to xlsx`) da estos totales, y los comprobé a mano:

  | Categoría | Total | Comprobación a mano |
  |---|---|---|
  | Piso | -2448 | 4 × 612 |
  | Luz/Agua | -248,87 | 55,10 + 56,99 + 71,46 + 65,32 |
  | Comida | -795,49 | 64,35 + 178,15 + 240,64 + 312,35 |
  | Ingresos | 6960 | 4 × 1740 |

  Mis fórmulas siguen siendo fórmulas.
- **(c)** Cambié JAZZTEL de julio (fila 11) de «Fibra/movil» a «Luz/Agua» y volví a ejecutar. Salió «ningún movimiento nuevo que añadir, no lo he tocado», el md5 del fichero es idéntico, mi cambio sigue ahí y no hay duplicados. Luz/Agua pasa a -286,87 (= -248,87 - 38). Correcto.
- **(d)** Mi nota en E13 («esto fue lo del tobillo») sigue en su fila después de volver a ejecutar. También siguió pegada a su FARMACIA después de que yo borrara la fila de encima y la herramienta la volviera a añadir abajo.
- **(e)** Con `.~lock.copia_contabilidad.xlsx#` presente no escribe y lo explica (ver la cita del punto 4). Al quitar el lock, escribe normal.
- **Filas tecleadas a mano:** en otra copia metí a mano «02/07/2026 · Recibo hipoteca · -612» (con otras mayúsculas) y «10/07/2026 · RECIBO ENDESA · -56,99». Salió «28 añadidos debajo»: reconoció las dos y no las duplicó. Esto me da mucha tranquilidad.
- **(f)** Con mi fichero no se gasta ninguna copia si no hay nada nuevo (con el histórico sí, ver punto 3).
- Mi fichero original de `descargas/` no se tocó en ningún momento.

## 7. ¿Dejaría de copiar y pegar? (g)

**Sí.** Hace exactamente lo que yo hacía a mano: pega debajo, en mis columnas y con mis nombres de categoría (casi todas coinciden con las mías: Piso, Luz/Agua, Comida, Ingresos). No duplica, respeta mis cambios y mis notas, y se niega a escribir si tengo el fichero abierto.

Antes de fiarme del todo haría dos cosas:
1. Revisar las categorías que no uso (Higiene, Fibra/movil): o las añado a Totales, o cambio las reglas en `ajustes/rules.json` para que vayan a las mías.
2. Aceptar que las filas nuevas tengan otro formato de fecha, o cambiarlo yo una vez.

## 8. Valoración: 8,5 / 10

Lo importante (no romper mi libro, no duplicar, no pisar mis cambios, avisar si está abierto) funciona a la primera y siguiendo solo la documentación, sin tocar código. Le quito puntos por detalles:
- el formato distinto en las filas nuevas;
- que ningún aviso me diga que hay categorías que mis totales no recogen;
- la copia del histórico que se gasta en cada ejecución sin cambios;
- que la recomendación de probar sobre una copia solo esté dentro del JSON.

Ninguno de estos puntos es un fallo que pierda datos.
