# Informe de piloto — Ana (p7)

Versión probada: **2.12.1** (Linux, lanzadores `.sh`).

## 1. Perfil y qué intenté

Soy Ana, 27 años, enfermera. Hago casi todo con el móvil y llevo mis cuentas en un Excel muy sencillo. Tengo:

- una tarjeta de un neobanco: `account-statement_2026-07-01_2026-09-30_es-es_a1b2c3.csv` (en inglés, con punto decimal, tal cual sale de la app; cada mes recargo 400 € con «Top-Up by *1234»);
- una tarjeta de débito de un banco español: `tarjeta_debito.xls` (en realidad es XML);
- y además, en Descargas, `Recibo_alquiler_julio.pdf` y `extracto_vacio.xls` (0 bytes).

Lo que hice:

1. Leí la portada (`web/index.html`), la guía (`GUIA.pdf`) y `LEEME.txt`. Ejecuté `./instalar.sh` (fue bien: «Listo. Ya puedes usar ejecutar.sh») y luego `./ejecutar.sh` con `entrada/` vacía.
2. Copié todo lo de Descargas a `entrada/` sin mirar y volví a ejecutar.
3. Creé `eledger/mis_cuentas.xlsx` con una hoja `MOVIMIENTOS` vacía y una hoja `RESUMEN` con fórmulas `=-SUMIF(MOVIMIENTOS!G:G,"Comida",MOVIMIENTOS!C:C)` (y lo mismo para Ocio, Transporte, Otros e Ingresos). Puse `"archivo": "mis_cuentas.xlsx"` en `ajustes/sincronizar.json` y ejecuté.
4. Escribí notas a mano en la columna H («mis notas») junto a tres movimientos: Primark de −31,77 («uniforme hospital»), Ryanair de −118,97 («vuelo boda Lucía») y FNAC de −55,30 («regalo cumple mamá»). Después creé `entrada/account-statement_2026-06-01_2026-06-30_es-es_f9e8d7.csv` (junio, más antiguo, mismo formato, 4 movimientos: Top-Up de 300, Spotify, Mercadona y Uber Eats) y volví a ejecutar.
5. Además probé por mi cuenta: escribir mal el nombre del archivo en `sincronizar.json`, añadir una regla para el Top-Up olvidándome de la coma, y después corregirla.
6. Ejecuté `./exportar.sh` y miré qué había dentro del ZIP.

## 2. Dónde me atasqué

No me atasqué del todo en ningún momento. Hubo tres sitios en los que dudé:

- **A qué carpeta se refiere `"archivo"`.** En `ajustes/sincronizar.json` pone: *«Ruta a tu .xlsx. Si está en la misma carpeta, basta el nombre.»* ¿En la misma carpeta que qué? El JSON está en `ajustes/`, así que pensé que había que meter el Excel ahí. La guía tampoco lo dice: solo pone el ejemplo `"archivo": "contabilidad.xlsx"`. Probé a ponerlo en `eledger/` (junto a `ejecutar.sh`) y funcionó: la ruta es relativa a la carpeta del programa, no a `ajustes/`. Lo comprobé cuando escribí mal el nombre, porque el aviso enseña la ruta completa: *«No encuentro el fichero de contabilidad: …/p7_ana/eledger/mis_cuenta.xlsx»*. Así que el mensaje de error te saca de dudas, pero la documentación no.
- **Qué hacer con el Top-Up.** La pantalla me dice *«3 movimientos sin ninguna regla»* y me propone `"top": {"+": "PON_TU_CATEGORIA"}`. Pero en el Excel esos movimientos ya salen como **Ingresos**, con la columna `regla` vacía. No entendía por qué algo «sin regla» tenía ya una categoría. En ningún sitio de la guía encontré qué pasa con lo que no casa con ninguna regla (lo que entra va a Ingresos y lo que sale, a Otros, supongo).
- **El aviso de la tarjeta.** Mi tarjeta de débito me cobra cada compra al momento; no hay «recibo de la tarjeta». Aun así, en cada ejecución sale *«⚠️ Ojo: puede que los gastos de la tarjeta se estén contando dos veces»* y *«Tienes movimientos de tarjeta y ningún patrón en exclude_patterns.json»*. No sé cómo decirle «no tengo recibo, no me avises más». La guía dice que *«Con cualquier patrón ya puesto, no dice nada más»*, así que la única forma de callarlo sería inventarme un patrón.

## 3. Errores o comportamientos raros

No encontré ningún **fallo** de verdad: ningún número mal, ni datos perdidos, ni notas movidas. Lo que sí vi:

- **Comportamiento raro / confuso (no es un fallo): la columna «Fuera del balance» y el Acumulado.** Con mis dos ficheros, julio sale con `Fuera del balance = 148,66` (es justo la suma de mis compras con la tarjeta de débito: 25,32 + 63 + 60,34). Cuando marqué el Top-Up como «Transferencias internas», pasó a `548,66`. El Acumulado queda en `+881,69 €`, que no se parece a nada que yo conozca. La guía lo explica (*«las compras con tarjeta que el banco todavía no ha cargado en la cuenta»*), pero en mi caso la cuenta que paga esa tarjeta ni siquiera la he subido. Para alguien como yo, esa columna y el Acumulado sobran o despistan.
- **El neobanco se toma por «cuenta» sin pistas.** Sale *«→ cuenta (sin pistas claras, asumo cuenta)»*. A mí me da igual, porque lo uso como una cuenta, pero lo menciono por si otra persona espera que salga como tarjeta.
- **El aviso del fichero vacío se repite en cada ejecución** mientras siga en `entrada/`. Es lógico, porque ahí sigue, pero podría decir también «bórralo de entrada/».
- **Detalle de texto:** en `sincronizar.json`, `"_copias"` dice *«Cuántas copias de seguridad guardar en copias/»*, pero en realidad se guardan en `datos/copias/` (según el mensaje por pantalla y la guía).
- **Detalle de pantalla:** el aviso de «no encuentro el fichero» parte la ruta a mitad de palabra (`/tmp/claude-0/-root-` / `proyectos-eledger/...`) y repite la idea: el título dice *«No he sincronizado con mis_cuenta.xlsx»* y justo debajo *«No sincronizo con tu fichero de contabilidad:»*.

Para reproducir el aviso con el nombre mal escrito: pon `"archivo": "mis_cuenta.xlsx"` en `ajustes/sincronizar.json` y ejecuta `./ejecutar.sh`.

## Lo que comprobé expresamente

- **(a) Top-Up: correcto.** Las recargas acaban en **Ingresos** (400 al mes), no en Otros. Ningún gasto sale negativo en el RESUMEN: julio da `Otros 117,43`, `Total Gastos 288,53` e `Ingresos 400`. Recalculé mi `mis_cuentas.xlsx` con LibreOffice y da Comida 181,5, Ocio 250,43, Transporte 219,97 y Otros 317,05, todo positivo. (Para mí, en realidad, el Top-Up es dinero mío que paso de mi otro banco, no un ingreso. Añadí `"top": {"+": "Transferencias internas"}` y quedó bien: Ingresos 0 y nada restado de los gastos. Esto es una matización, no un fallo.)
- **(b) Notas tras meter junio: correcto.** Salió *«ℹ️ 3 notas tuyas recolocadas junto a su movimiento (han entrado movimientos por medio).»* Las filas se desplazaron 4 posiciones (Primark pasó de la fila 6 a la 10, Ryanair de la 17 a la 21 y FNAC de la 28 a la 32), y cada nota sigue junto a SU movimiento. Mi cabecera «mis notas» (H1) y mis fórmulas del RESUMEN siguen intactas. Después de otra ejecución con la regla nueva, también siguen en su sitio.
- **(c) PDF y fichero vacío: correcto y comprensible.** Salen *«Recibo_alquiler_julio.pdf: no es un extracto del banco, lo dejo sin leer»* y *«'extracto_vacio.xls' está vacío (0 bytes): la descarga no terminó bien. Vuelve a descargarlo del banco.»* Los entendí a la primera.
- **(d) A qué carpeta es relativo `"archivo"`: no queda claro en la documentación** (ver el apartado 2). Solo lo descubrí por el mensaje de error.

## 4. Lo que no entendí de la guía, la web o los mensajes

- *«Si está en la misma carpeta, basta el nombre»* (en `sincronizar.json`): ¿la misma carpeta que qué?
- Qué categoría recibe un movimiento que no casa con ninguna regla. La pantalla dice «sin ninguna regla», pero el Excel ya le pone «Ingresos».
- «Fuera del balance» y «Acumulado (desde el primer movimiento)». Los leí dos veces y sigo sin saber para qué me sirven con una tarjeta de neobanco y una de débito.
- La guía usa `SUMAR.SI.CONJUNTO(...; ...)` con punto y coma, y yo usé `SUMIF` con comas. Avisa de que el separador depende de la configuración, y está bien que lo avise.
- La portada está bien y es corta. Lo de «Pulsa 1 para abrir el histórico» no lo pude ver en Linux (sin menú interactivo en esta prueba).

## 5. Lo que echo en falta

- Una forma de decir «mi tarjeta no se paga con recibo» para que deje de salir el aviso de contar dos veces sin tener que inventarme un patrón. *(Preferencia fuerte / casi fallo de usabilidad.)*
- Que la guía y `sincronizar.json` digan expresamente «la ruta es relativa a la carpeta del programa (donde está ejecutar.sh), no a ajustes/». Por ejemplo: *«Si lo pones junto a ejecutar.bat, basta el nombre»*. *(Fallo de documentación.)*
- Una línea en la guía sobre adónde va lo que no tiene regla. *(Documentación.)*
- Una pista para los neobancos: «las recargas (Top-Up) suelen ser dinero tuyo que viene de otra cuenta; si no quieres que cuenten como ingreso, mándalas a Transferencias internas». Lo deduje yo, pero mucha gente vería 400 € de «ingresos» y se lo creería. *(Preferencia.)*
- Algo para el móvil, aunque sea ver el resumen. Sé que no es el objetivo. *(Preferencia.)*

## 6. Valoración: 8/10

Lo importante funcionó a la primera y sin tocar nada: leyó un CSV en inglés con punto decimal y un .xls que en realidad es XML. Ignoró el PDF y el fichero vacío con mensajes claros. No me duplicó nada al volver a ejecutar. Rellenó mi propio Excel sin romper mis fórmulas ni mi columna de notas, y las notas siguieron a su movimiento cuando metí un mes anterior. El error de la coma en el JSON está explicadísimo (*«Suele ser una coma que falta al final de la línea de antes…»*). El ZIP de `exportar.sh` no lleva nada mío: ni `mis_cuentas.xlsx`, ni el histórico, ni mis reglas, y la plantilla de `sincronizar.json` va con `"archivo": ""`.

Le quito dos puntos por lo que me dejó dudando. El aviso de «contar dos veces» sale siempre en mi caso y no sé quitarlo. No se explica a qué carpeta es relativa la ruta del archivo. Y el resumen tiene columnas («Fuera del balance», «Acumulado») que, para alguien con solo tarjetas, confunden más que ayudan.
