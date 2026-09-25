# Informe de piloto: Daniel (estudiante, una cuenta en un neobanco, CSV en inglés)

Versión probada: 2.12.1 (sale en la primera línea al ejecutar). Linux, lanzadores `.sh`.

## 1. Perfil y qué intenté

Tengo 20 años, estudio ADE y tengo una sola cuenta en un neobanco. Me bajé `n26-csv-transactions.csv` (julio a septiembre de 2026, 65 movimientos, cabeceras en inglés: `Date,Payee,...,Amount (EUR)`). Entré por la portada de la web, leí «Cómo se usa» y el LEEME.txt, y solo abrí la GUIA.pdf cuando algo no salió.

Pasos:
1. `./instalar.sh`: sin problemas, «Listo. Ya puedes usar ejecutar.sh».
2. `./ejecutar.sh` sin nada. Crea `ajustes/`, `entrada/`, `datos/` y `salida/`, y dice que suelte ahí los ficheros. Bien.
3. Copié el CSV a `entrada/` y volví a ejecutar. **No lo lee** (ver 2.1).
4. Cambié a mano la cabecera `Payee` por `Concepto` y ahí ya entró todo.
5. Añadí mis reglas y dos categorías nuevas (`Cafes`, `A domicilio`), las probé con `python3 app/reglas.py` y reprocesé.

Tiempo total: unos 15 minutos. Casi todo se fue en el CSV que no se leía.

## 2. Dónde me atasqué

### 2.1 El CSV del neobanco no se lee (FALLO, el que más pesa)
La portada dice: «De cualquier banco, también neobancos, o solo tarjetas. Reconoce el formato real de cada extracto». Mi primer objetivo era no tocar nada, y no se cumplió:

```
   · n26-csv-transactions.csv: ✗ no se ha podido leer (el motivo, en los avisos del final)
⚠️  No he podido leer n26-csv-transactions.csv
    'n26-csv-transactions.csv': no localizo las columnas ['descripcion'].
    Cabecera detectada: ['Date', 'Payee', 'Account number', 'Transaction
    type', 'Payment reference', 'Amount (EUR)', ...]
```
El diagnóstico (`app/.venv/bin/python app/bank_io.py entrada/n26-csv-transactions.csv`) muestra `mapeo: {'fecha': 0, 'importe': 5}`. O sea, `Date` y `Amount (EUR)` sí los reconoce y el que falla es `Payee`. Seguramente también faltaría `Payment reference` como concepto alternativo.

Para esto la guía (página 17) dice: «añade el nombre a ALIAS_COLUMNAS en bank_io.py». Eso es editar código Python y no lo voy a hacer. Además, al actualizar se borra `app/` y perdería el cambio. Lo arreglé renombrando la cabecera en el CSV, pero eso lo tendría que repetir con cada descarga.

### 2.2 El mensaje final dice que `entrada/` está vacía, y no lo está (FALLO menor)
En esa misma ejecución fallida, después del aviso, sale:
```
❌ No hay histórico y la carpeta 'entrada/' está vacía.
```
Pero el CSV estaba en `entrada/`. Lo que pasa es que no se ha podido leer. Con prisa, lo último que lees es esa línea y te hace pensar que lo copiaste mal. Reproducir: con la carpeta recién instalada, meter el CSV original (con `Payee`) en `entrada/` y ejecutar `./ejecutar.sh`.

## 3. Errores o comportamientos raros

- **La clasificación por defecto de los Bizum no encaja con un estudiante** (no es fallo: es la regla base de fábrica). Sin reglas mías:
  - `Bizum a MARIO piso gastos` (-120 €) → **Ocio**, por la regla `bizum` de la base. En «Cargos que se repiten» aparece como «1.440,00 €/año · Ocio». Es mi parte del piso.
  - `Bizum de LUCAS cena` → **Ingresos**. En septiembre los ingresos salían en 1.834,08 € en vez de 1.800 €, y en julio en 327,68 € en vez de 300 €.
  La guía lo avisa («Un Bizum que recibes es un ingreso»), así que funciona como está documentado. Pero para mi caso es justo lo contrario de lo que quiero.
- **Ocio sale en negativo después de mi arreglo** (no es fallo, está documentado). Con `"=cena": "Ocio"`, los Bizum de Lucas restan de Ocio: julio -22,19 €, agosto -37,09 €, septiembre -28,59 €. Pasa porque las cenas las pagué con otra cosa y no están en este extracto. La guía explica que «una categoría que acabe a favor sale negativa». Aun así, ver «Ocio -37,09» la primera vez desconcierta.
- **Glovo cae en Ocio** en la base (`glovo`, `just eat` y `uber eats` → Ocio), igual que el café del bar (`=bar` → Ocio). Así que en el resumen de fábrica no se puede separar café de comida a domicilio. Es preferencia, no fallo.
- **Movimientos con fecha futura**: el CSV trae el 26/09 y el 27/09, y hoy es 25/09. Entran sin ningún comentario. No sé si es un problema (a lo mejor son pendientes del banco). Lo apunto como curiosidad.
- `python3 app/reglas.py "Bizum de LUCAS cena" 6.89 "CAFE BAR UNIVERSIDAD"` interpreta el `6.89` como otro texto («6.89 -> Otros [sin regla]»), porque el importe tiene que ir el último. Fue culpa mía, la guía lo dice («Si pones un número al final»). Y sin importe, un Bizum sale como «Ingresos», que puede confundir.

### Lo que fue bien (resultado de cada objetivo)
- **(a) Leer el CSV sin tocar nada: NO.** Tuve que renombrar `Payee`. Después de eso lo detectó solo: «formato=texto, cabecera en fila 1, 65 movimientos (0 filas descartadas)».
- **(b) Padres y beca como ingreso: SÍ**, incluso sin reglas, porque lo que entra y no tiene regla cae en Ingresos. Además, el bloque «Sin clasificar» me dio la línea exacta: `añade a rules.json:  "padres": {"+": "PON_TU_CATEGORIA"}`. Muy útil. **Que los Bizum de amigos no inflen los ingresos: SÍ, pero deduciéndolo yo.** Con `"=cena": "Ocio"` los ingresos quedan en 300 / 300 / 1.800 €, que es lo real. Me basé en el recuadro «Las devoluciones NO necesitan regla de signo». La guía no trata este caso directamente.
- **(c) Los dos cafés iguales del 09/09: SÍ.** Salen las dos líneas de -1,30 € (con `n_rep` 0 y 1) más la de -1,33 €. Al reprocesar no se duplican: «65 movimientos ya estaban... no se cuentan dos veces».
- **(d) Zalando y su devolución: SÍ.** Los dos caen en `Otros` por la regla `zalando` de la base, y Otros en agosto queda en 0. Perfecto, sin hacer nada.
- **(e) Cafés y comida a domicilio al mes: SÍ, pero después de configurarlo.** Con las categorías `Cafes` y `A domicilio` en `categorias.json` y sus reglas, el RESUMEN muestra cafés 20,35 / 18,41 / 20,07 € y a domicilio 34,67 / 25,52 / 30,95 €. Con la configuración de fábrica, no: todo va mezclado en Ocio.
- La instalación, el primer arranque que crea las carpetas, `reglas.py` para probar sin reprocesar, el aviso de que el Acumulado no es mi saldo y los 3 gráficos del RESUMEN funcionaron bien y se entienden.

## 4. Lo que no entendí de la guía, la web o los mensajes

- «añade el nombre a ALIAS_COLUMNAS en bank_io.py»: no sé qué es eso ni dónde está, y no es algo que haga un usuario.
- «→ cuenta (sin pistas claras, asumo cuenta)»: me asusta un poco. ¿Qué pasaría si lo asumiera mal? Como solo tengo una cuenta, me da igual.
- `mes_ajustado` y `columna_mes: "mes_ajustado"`: tuve que leer para ver que no me afecta (solo mueve «nomina» y «pension»). La transferencia de mis padres del 01/08 se queda en agosto. Me parece bien, pero no sé si en mi caso debería moverse al mes anterior.
- «Fuera del balance»: no lo necesito, pero sale como columna y no sé si tengo que hacer algo con ella.

## 5. Lo que echo en falta

1. **Que lea el CSV de N26 (y de otros neobancos en inglés) de serie**: `Payee` / `Payment reference` como concepto. Y si no reconoce una columna, que haya una forma de indicarlo desde `ajustes/` en vez de editar `bank_io.py`.
2. **Un apartado en la guía sobre «Bizum de amigos que te devuelven dinero»**, con la receta: regla sin signo a la categoría del gasto, o `categoria_manual`. La guía menciona «BIZUM A MARTA que un mes es la parte del alquiler y otro una cena», que es justo mi caso, pero solo para corregir líneas sueltas.
3. Una pista en la guía o la web de cómo separar «cafés» o «comida a domicilio» del resto de Ocio (crear una categoría y declararla en `categorias.json`). Lo acabé haciendo, pero tuve que juntar dos apartados distintos.
4. **Lo que me sobra**: para mi perfil, el LEEME y la guía dedican mucho espacio a la tarjeta y a `exclude_patterns.json` («Lo primero que deberías configurar»), a `cuentas.json`, a la sincronización con tu propio Excel y a `mes_contable`. Nada de eso me aplica. Estaría bien un «si solo tienes una cuenta, sáltate esto». La portada web sí es corta y va al grano, y eso me gustó.

## 6. Valoración: 6/10

Una vez que el CSV entra, la herramienta hace lo que promete. Los duplicados legítimos se respetan, la devolución de Zalando se anula sola, «Sin clasificar» te da la línea para pegar y el resumen con categorías propias responde a mi pregunta de cafés y Glovo. Sería un 8.

Le quito puntos porque **mi primer objetivo (leer el CSV sin tocar nada) falló** en un banco que la portada da a entender que está soportado. La solución oficial es editar código, y el mensaje final encima me decía que la carpeta estaba vacía. Un usuario impaciente como yo lo habría dejado en el minuto 3. Además, la configuración de fábrica de los Bizum (piso → Ocio, cenas → Ingresos) me daba unas cifras de ingresos y de ocio falsas hasta que escribí mis propias reglas.
