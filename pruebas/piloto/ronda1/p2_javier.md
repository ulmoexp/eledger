# Informe de uso: Javier (versión 2.12.0, Linux)

## 1. Perfil y qué intenté

Tengo 34 años y soy programador. Me gusta dejar las herramientas a mi gusto. Tengo una cuenta (me bajé dos CSV que se solapan en agosto: `extracto_jul_ago.csv` y `extracto_ago_sep.csv`) y una VISA (`tarjeta_visa_2026.xlsx`). Tengo perro, voy al gimnasio y hago cursos online.

Leí LEEME.txt, GUIA.pdf (con pdftotext), la web (portada, guía y reglas), los JSON de `ajustes/` y `app/rules_base.json`. Hice lo siguiente, en orden:

1. Ejecuté `./instalar.sh`, luego `./ejecutar.sh` con `entrada/` vacía, y después con los tres ficheros.
2. Creé las categorías `Mascotas` y `Formacion`, con sus reglas.
3. Separé los Bizum: los recibidos como ingreso y los enviados como Ocio.
4. Apagué la regla `hipoteca` de la base.
5. Personalicé el resumen con `etiquetas`, `orden_resumen` y `desglosar_ingresos`.
6. Escribí en `categoria_manual` una categoría, un `(excluido)` y una categoría con tilde puesta a propósito.
7. Revisé los gráficos leyendo el XML de `xl/charts/`.
8. Probé reglas con `app/reglas.py`.

**Casi todo funcionó a la primera.** Los objetivos 1, 2, 3, 4, 6, 7 y 8 salieron bien. El 5 también, pero con un tropiezo.

## 2. Dónde me atasqué

- **El resumen se quedó sin la columna de meses (objetivo 5).** Escribí `orden_resumen` con las columnas que quería, sin incluir `"Mes"`, porque no sabía que había que ponerla. En la guía no hay ningún ejemplo de `orden_resumen`: solo dice *«Qué columnas salen y en qué orden, incluidas las de sistema (Balance, Acumulado...)»*. El RESUMEN salió así, sin ningún aviso:
  `['Nomina', 'Bizum', 'Ingresos', 'Total Gastos', 'Piso', ...]` y filas como `[2380, 40, 2420, 1070.75, ...]`. No se sabe a qué mes corresponde cada fila. Añadiendo `"Mes"` al principio se arregla. Los gráficos siguieron bien porque apuntan a la columna A, pero la tabla no se entendía. **Fallo** en la documentación y en la validación: hace falta un ejemplo completo y un aviso si falta `Mes`.
- **No sabía los nombres exactos de las columnas de sistema.** Los saqué probando: `Mes`, `Total Gastos`, `Ingresos`, `Balance`, `Fuera del balance`, `Acumulado` y `Otros ingresos`. Si escribes uno mal sí avisa: *«Balanc» en orden_resumen no es ni una columna de sistema ni una categoría declarada: se ignora.*, lo cual está bien. Aun así, la lista debería venir en la guía o en el propio `categorias.json`.
- **Cambiar «Perros» por «Mascotas».** Hice lo evidente: renombré `Perros` en `categorias.json` y escribí mis reglas con `Mascotas`. Al ejecutar salió *«4 reglas de la base descartadas: apuntan a categorías que no tienes en categorias.json.»*, pero **no decía cuáles**. Lo supe después con `reglas.py`, que sí las lista: *«descartadas ...: kiwoko, zooplus, miscota, mascota»*. Hasta entonces, una compra en Kiwoko se habría ido a Otros sin que yo me enterara. Luego vi que lo previsto era dejar `Perros` y usar `etiquetas` para renombrarla, pero nada me orientó hacia eso.

## 3. Errores o comportamientos raros

1. **Un `orden_resumen` sin `"Mes"` produce un resumen sin meses y no avisa** (**fallo**). Para reproducirlo: en `ajustes/categorias.json`, poner `"orden_resumen": ["Nomina","Bizum","Ingresos","Total Gastos","Piso", ... ,"Balance","Acumulado"]` y ejecutar `./ejecutar.sh`. La cabecera de RESUMEN empieza por `Nomina` y no hay ninguna columna con el mes.
2. **Las `etiquetas` con una clave que no existe se ignoran sin avisar** (**fallo menor**, y además incoherente con `orden_resumen`, que sí avisa). Con `"etiquetas": {"Mascota": "x", "Balance": "Ahorro del mes", "Ingresos": "Total ingresos"}` no sale ningún aviso y ninguna de las tres tiene efecto. Lo de `Mascota` es una errata mía que nadie me señaló. Que no se puedan renombrar `Balance` ni el total `Ingresos` puede ser una decisión de diseño, pero entonces debería avisar o decirlo la guía.
3. **El recuento de reglas descartadas en `ejecutar.sh` no dice cuáles son** (**fallo menor**). Solo sale *«4 reglas de la base descartadas»*, mientras que `reglas.py` da la lista. Además esa línea sale arriba y no dentro de «Avisos», que es donde la guía dice que se juntan.
4. **`reglas.py` sin importe aplica el lado `+` de una regla con signo** (**raro**). `python3 app/reglas.py "BIZUM A CARLOS"` devuelve `-> Ingresos [bizum · base]`, y con mi regla devuelve `-> Bizum`. Da por hecho que el movimiento es positivo y no lo dice. Esperaba algo como «Bizum (+) / Ocio (−), pon un importe».
5. **La guía dice `python app/reglas.py`, pero en mi Linux no existe `python`** (**fallo de documentación**). `which python` no devuelve nada; solo hay `python3`. Pasa lo mismo con el comentario `_probar` de `rules.json`. En la sección de diagnóstico la guía sí da la ruta por sistema (`app/.venv/bin/python`). Con `python3` funciona, y además sin necesitar el venv.
6. **Mensaje engañoso al volver a ejecutar** (**menor**). En la segunda ejecución, sin ficheros nuevos, sale *«🔁 51 movimientos ya estaban (extractos que se solapan)»*. No se solapan: son los mismos ficheros, que ya estaban en el histórico.
7. **`instalar.sh` en Linux termina con** *«Listo. Ya puedes usar  ejecutar.command»*. En Linux es `ejecutar.sh` (**menor**).
8. **«Cargos que se repiten» muestra el nombre interno** (`Fibra/movil`) y no mi etiqueta (`Internet y móvil`). Es **menor** y probablemente una **preferencia**.
9. **Aviso de tarjeta que no puedo quitar.** Mi cuenta no paga la VISA con ningún recibo en estos extractos, pero cada ejecución repite *«⚠️ Ojo: puede que los gastos de la tarjeta se estén contando dos veces»*. No hay manera documentada de decirle «ya lo he revisado, no hay recibo». Es **preferencia/diseño**, pero acostumbra a ignorar los avisos.

## 4. Lo que no entendí de la guía, la web o los mensajes

- `orden_resumen`: qué nombres acepta y que `Mes` también es una columna de las que se pueden quitar.
- `etiquetas` junto con `desglosar_ingresos`: la guía dice que la categoría `Ingresos` pasa a llamarse *«Otros ingresos»* en etiquetas y en orden_resumen, y efectivamente es así (`"Otros ingresos": "Varios"` funcionó). Pero una etiqueta sobre el total `Ingresos` no hace nada y tampoco lo dice. Me costó dos ejecuciones entenderlo.
- El título del aviso por la errata de orden_resumen es *«Las categorías de rules.json y categorias.json no cuadran»* y termina con *«o el resumen no cuadrará»*. El problema real era una columna mal escrita en `orden_resumen`, que no tiene nada que ver con rules.json ni hace que los totales descuadren. El título despista.
- «Fuera del balance»: no lo entendí hasta que hice la cuenta. En julio sale +122,41, que son exactamente las compras con tarjeta que aún no ha cobrado el banco. La guía lo explica bien; en el Excel no hay ninguna nota.

## 5. Lo que echo en falta

- Un `categorias.json` de ejemplo **completo**, con `etiquetas`, `orden_resumen` y `desglosar_ingresos` rellenos, en la guía o como comentario `_ejemplo` dentro del propio fichero, como hace `rules.json`.
- Una forma de **renombrar una categoría de la base** para que sus reglas la sigan: por ejemplo, que al descartar reglas de `Perros` sugiera *«¿quieres una etiqueta en vez de renombrar?»*.
- En el aviso de `categoria_manual` con tilde (*«Correcciones manuales con una categoría que no existe: Formación»*) una sugerencia del tipo «¿querías decir Formacion?». En otro sitio la guía presume de detectar diferencias de tilde; aquí no lo hace.
- Que `basic fit` también encuentre `BASIC-FIT`. `reglas.py "BASIC-FIT"` devuelve `-> Otros [sin regla]`, y los bancos suelen escribirlo con guion.
- Poder silenciar el aviso de la tarjeta cuando no hay recibo.
- Es una **preferencia**: el ZIP del usuario trae `TRASPASO.md`, `COMPILAR.md`, `compilar.bat` y `eledger.spec`, que son del desarrollador y me hicieron dudar de qué tenía que abrir. También echo en falta que RESUMEN tuviera fórmulas en vez de valores: al corregir `categoria_manual` en Excel hay que volver a ejecutar para verlo, aunque la guía lo avisa.

## Lo que fue bien (para que conste)

- La instalación funcionó a la primera. Con `entrada/` vacía el mensaje es claro y crea `ajustes/` con plantillas comentadas.
- **Agosto no se duplica**: *«🔁 10 movimientos ya estaban (extractos que se solapan); no se cuentan dos veces.»*. Salen 41 movimientos, que es la cuenta correcta. Leyó bien el CSV en Latin-1 con `;` y el xlsx con la cabecera en la fila 3, y detectó cuál es la cuenta y cuál la tarjeta sin que yo hiciera nada.
- *«🧮 Cuadra con el banco: 9.582,27 € a 28/09/2026, igual que el extracto.»*. El saldo inicial (5.120 €) se detecta solo. Esto da mucha confianza.
- Bizum ya viene separado por signo en la base. Lo cambié a `{"+": "Bizum", "-": "Ocio"}` con una categoría de ingreso propia y funcionó.
- Con `"hipoteca": null` la regla se apaga. La ejecución lo confirma (*«Apagadas con null: hipoteca»*) y el movimiento pasa a `Prestamos` por la regla `prestamo`.
- Mascotas y Formacion suman en el resumen: Mascotas 145,51 / 144,13 / 84,61 y Formacion 14,99 en agosto.
- `categoria_manual` hace lo que dice: `Formacion` se aplica con regla `(manual)`, y `(excluido)` saca la fila de los totales sin romper el Acumulado. Lo mal escrito se ignora con un aviso claro y la celda se conserva para que la corrija.
- Hay copias de seguridad automáticas en `datos/copias/` en cada ejecución.
- Los gráficos existen y siguen mi orden de columnas personalizado:
  - chart1, «Acumulado (saldo de la cuenta)»: línea sobre `RESUMEN!$Q`.
  - chart2, «Ingresos y gastos»: barras sobre `$E` (Ingresos) y `$F` (Total Gastos).
  - chart3, «Gasto medio al mes por categoría»: usa mis etiquetas, por ejemplo «Perro 🐕» con 124,75.

  Es la información que busco: cuánto ahorro al mes y en qué se me va.
- `reglas.py` es rápido y útil. Marca `· base` en las reglas de la base, acepta un importe y lista las reglas apagadas y las descartadas. La batería de casos trampa sin argumentos enseña cómo funciona el límite de palabra. Ojo: `"curso"` me pilló «CURSOR AI»; está documentado y lo resolví con `=curso`.

## 6. Valoración: 8/10

La base es muy sólida: deduplicación, cuadre con el banco, avisos contra los descuadres, `categoria_manual` y reglas por capas funcionan como se describe. Además la guía explica el porqué de las cosas, cosa que agradezco. Le quito puntos por la personalización del resumen, que es justo lo que más me interesa como usuario exigente. Está poco documentada (no hay ejemplo ni lista de nombres de sistema) y tiene dos agujeros sin aviso: `orden_resumen` sin `Mes` y etiquetas con una clave que no existe. También resta que renombrar una categoría de la base deje reglas descartadas sin decir cuáles. Ninguno de estos problemas cambia los totales, pero van contra la filosofía de «avisar siempre» que el propio producto defiende.
