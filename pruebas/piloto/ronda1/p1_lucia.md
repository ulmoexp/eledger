# Informe de usuaria simulada: Lucía (58 años, profesora)

Versión probada: 2.12.0 (Linux, lanzadores `.sh`).

## 1. Perfil y qué intenté

Soy profesora, nunca he abierto una terminal y no sé qué es un JSON. Tengo una cuenta y una tarjeta de crédito del mismo banco. Me bajé `Movimientos_cuenta_20260930.xls` y `Tarjeta_4321_jul-sep.xls` (de julio a septiembre). Quería:
1. instalar y sacar mi primer resumen;
2. ver si los totales me cuadran y si algo se cuenta dos veces;
3. pasar la peluquería de «Higiene» a «Otros»;
4. volver a ejecutar.

Todo eso lo conseguí al final, pero por el camino salió un fallo gordo (mi nómina entraba como gasto de «Hijos») que el programa no me avisó, y hubo un par de sitios donde yo sola me habría quedado atascada.

## 2. Dónde me atasqué

**a) La carpeta `entrada/` no existe al descomprimir.**
- Qué esperaba: el LEEME dice «Descarga los extractos del banco y déjalos en la carpeta entrada/». Esperaba encontrarla.
- Qué pasó: en el ZIP no está. Solo aparece después de ejecutar una vez, y esa primera vez sale «❌ No hay histórico y la carpeta 'entrada/' está vacía.» El mensaje sí me dice qué hacer, así que se arregla solo, pero la primera impresión es de que me falta algo.
- Esto es una preferencia (no es un fallo): que la carpeta venga ya en el ZIP, o que el LEEME diga «la primera vez, ejecuta y se crea».

**b) Añadir la exclusión de la tarjeta: me equivoqué con la coma y el error no se entiende.**
- Qué esperaba: el aviso final me decía, muy bien explicado, «Añade esto a exclude_patterns.json:  "liquidacion tarjeta credito"». Lo pegué al final de la lista, como haría cualquiera.
- Qué pasó: se me olvidó la coma de la línea anterior (no sabía que hacía falta) y el programa solo dijo:
  `❌ Expecting ',' delimiter: line 7 column 1 (char 558)`
  El mensaje está en inglés, no dice en qué fichero está el problema y no explica que falta una coma. Yo, como Lucía, no habría sabido seguir.
- Esto es un fallo de usabilidad: el mensaje debería decir en qué fichero está, en qué línea y, en español, «probablemente falta una coma al final de la línea anterior».

**c) Editar ficheros JSON en general.**
Ni la guía ni la web dicen con qué se abre un `.json` (el Bloc de notas, por ejemplo), ni que cada línea lleva coma salvo la última, ni que las comillas son obligatorias. Busqué «bloc de notas», «notepad» y «coma» en la guía y en la web: no aparece nada. Para una persona como yo, este es el paso más difícil de toda la herramienta.

## 3. Errores o comportamientos raros

**Fallo 1 (grave): mi nómina se clasifica como gasto de «Hijos».**
- Cómo reproducirlo: con `ajustes/rules.json` vacío (tal como viene), ejecutar `./ejecutar.sh` con el extracto de cuenta. El movimiento `NOMINA COLEGIO EJEMPLO +1650` cae en «Hijos» por la regla de la base `colegio`. Comprobado con la herramienta de la guía:
  `NOMINA COLEGIO EJEMPLO   1.650,00 €  ->  Hijos   [colegio · base]`
  En `app/rules_base.json`, `"colegio": "Hijos"` (línea 201) va antes que `"nomina": "Ingresos"` (línea 233), así que la regla del colegio casa primero. Y como no distingue el signo, captura también un ingreso.
- Consecuencia en RESUMEN (primera ejecución):
  - `Hijos = -1650` en junio, julio y agosto.
  - `Ingresos = 0` en todos los meses.
  - `Total Gastos = -584,27` en julio y `-335,97` en agosto (¡un gasto total negativo!).
  - En pantalla: «Último mes (2026-09): gastos 1.298,92 € · ingresos 0,00 €».
- El Balance y el Acumulado sí salen bien («🧮 Cuadra con el banco»), y eso da una falsa sensación de que todo está correcto.
- Cualquier nómina de un colegio o de otro sitio que la base conozca le pasaría lo mismo, y los profesores somos muchos.
- Ningún aviso lo señala, aunque es justo el tipo de descuadre que el programa dice vigilar: una categoría de gasto que acaba el mes a favor por 1.650 € no es una devolución.
- Lo arreglé añadiendo `"nomina": "Ingresos"` a mi `rules.json`. Solo di con ello porque me extrañó que no tuviera ingresos.
- Propuesta: que la regla `colegio` solo se aplique a importes negativos (`{"-": "Hijos"}`), y/o un aviso cuando una categoría de gasto sale muy en positivo.

**Rareza 2: el mensaje del instalador en Linux habla del lanzador de Mac.**
Al terminar `./instalar.sh` sale: «Listo. Ya puedes usar  ejecutar.command». En Linux el fichero es `ejecutar.sh`. Es un fallo menor de texto.

**Rareza 3: «4 meses» cuando yo he metido 3.**
Sale «del 01/07/2026 al 26/09/2026  (4 meses)» y en RESUMEN aparece una fila `2026-06`. Tiene explicación: la nómina del 1 de julio se pasa a junio por el «mes contable». Pero la pantalla solo dice «1 con el mes contable ajustado» y no explica que por eso aparece junio. Me descolocó. No es un fallo; es un mensaje mejorable.

**Rareza 4: el texto al volver a ejecutar.**
Al repetir la ejecución con los mismos ficheros sale «🔁 38 movimientos ya estaban (extractos que se solapan)». No se solapaban: simplemente los había procesado antes. Es menor: el texto no es falso del todo, pero confunde.

**Rareza 5: «Cargos que se repiten» incluye el supermercado y el cajero.**
Sale «989,76 €/año · … · COMPRA MERCADONA», «CARREFOUR MARKET» y «RETIRADA CAJERO». La web lo presenta como «Detecta suscripciones, cuotas y seguros». Que el Mercadona me salga ahí como si fuera una cuota es raro, y el total de «10.878,24 € al año» mezcla cosas muy distintas. Esto lo pongo como preferencia, no como fallo.

**Rareza 6: la consola propone clasificar la liquidación de la tarjeta.**
En la misma pantalla, «Sin clasificar» me propone `añade a rules.json:  "liquidacion": "PON_TU_CATEGORIA"`, y el aviso de más abajo me dice que la excluya. Son dos consejos contradictorios para el mismo movimiento. Si hubiera hecho caso al primero (está más arriba), seguiría contándola dos veces.

**Lo que fue bien:**
- La instalación funcionó a la primera.
- Reconoció solo los dos formatos: «formato=html … → cuenta (columna «saldo»)» y «formato=xml_ss … → tarjeta».
- El aviso de doble conteo es muy claro: «la tarjeta suma 190,53 € y tu cuenta tiene un cargo de 190,53 € el 02/08/2026 («LIQUIDACION TARJETA CREDITO 4321»)» y da la línea exacta para pegar. Esto es justo lo que necesitaba. Además, el aviso «⚠️ Ojo: puede que los gastos de la tarjeta se estén contando dos veces» aparece junto al resultado, no escondido.
- Tras excluirla: «36 movimientos · 2 excluidos». Los gastos de septiembre bajan de 1.298,92 € a 1.085,49 €.
- «Cuadra con el banco: 4.194,71 € a 22/09/2026, igual que el extracto.»
- Cambiar la peluquería fue fácil siguiendo la guía («Para cambiar una regla de la base, repite esa misma clave en la tuya»): añadí `"peluqueria": "Otros"` y al volver a ejecutar Higiene quedó solo con la farmacia y la peluquería pasó a Otros. La columna `regla` del Excel dice `peluqueria`, lo que ayuda a entender el porqué.
- Resultado final: julio 1.065,73 € de gastos, agosto 1.123,50 €. Esto sí me cuadra.

## 4. Lo que no entendí

- **«Fuera del balance»**: en septiembre sale `-4,45`. La guía dice que son «traspasos…, lo que has excluido… y las compras con tarjeta que el banco todavía no ha cargado». La explicación es correcta, pero un número negativo pequeño en una columna con ese nombre no me dice nada. No sabría si es un error.
- **La guía está pensada para alguien técnico.** Frases como «añádelos a PISTAS_CUENTA_COL o PISTAS_TARJETA_COL en bank_io.py», «"re:..." Expresión regular» o «Ejecuta el diagnóstico… app/.venv/bin/python app/bank_io.py» me asustan. Además, el LEEME dice «app/ la herramienta. No hace falta tocar nada de aquí».
- **El comando para probar reglas no funciona tal cual.** La guía y el propio `rules.json` dicen `python app/reglas.py "…"`. En mi Linux da `python: command not found`. Solo funciona con `app/.venv/bin/python app/reglas.py`. Esto es un fallo de documentación, al menos en Linux.
- **Qué quiere decir «PON_TU_CATEGORIA»** y qué categorías puedo poner. Hay que ir a `categorias.json` a mirarlas. Estaría bien que la pantalla listara las categorías disponibles.
- **Por qué `mes_contable` mueve «nomina» y no me lo pregunta**: yo cobro el día 31, así que el ajuste solo me afecta cuando el banco paga tarde. Lo entendí leyendo, pero no a la primera.

## 5. Lo que echo en falta

- Una forma de cambiar reglas y exclusiones sin tocar JSON (aunque sea un asistente que pregunte «¿añado esta línea por ti? (s/n)» cuando detecta el recibo de la tarjeta).
- Una sección de la guía titulada algo como «Cómo editar los ajustes»: con qué programa se abre, un ejemplo antes/después con la coma, y qué hacer si sale un error.
- Mensajes de error en español que nombren el fichero y la línea.
- Un aviso cuando una categoría de gasto termina el mes con un saldo grande a favor (lo que me pasó con «Hijos»).
- En la pantalla, una frase que diga por qué aparece un mes que no he metido (junio).

## 6. Valoración: 6/10

Lo esencial funciona: lee mis ficheros sin tocarlos, detecta y explica el doble conteo de la tarjeta y cuadra con el banco. Cambiar la peluquería fue fácil.
Pero de fábrica mi nómina salía como gasto de «Hijos» sin ningún aviso, y editar los JSON (la coma, el error en inglés) me habría dejado atascada sin ayuda.
