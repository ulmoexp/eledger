# Informe de piloto: Irene (pareja, cuenta conjunta + dos tarjetas)

Versión probada: 2.14.0 (Linux, `ejecutar.sh`). Salidas de cada ejecución guardadas en `run1.txt` … `run4.txt`.

## 1. Perfil y qué intenté

Soy Irene, 38 años, administrativa. Llevo las cuentas de casa con mi pareja: una cuenta conjunta (`movimientos_cuenta_conjunta.csv`) y una tarjeta de crédito cada uno (`Tarjeta_1111_movimientos.xls` la mía y `Tarjeta_2222_movimientos.xls` la suya), que se liquidan en la conjunta a principios de mes. Sé usar Excel, pero no programo.

Pasos que seguí:
1. Leí LEEME.txt y GUIA.pdf. Ejecuté `instalar.sh`: fue bien y terminó con «Listo. Ya puedes usar ejecutar.sh».
2. Copié los tres ficheros a `entrada/` sin tocar nada de la configuración y ejecuté (run1).
3. Seguí el primer aviso y declaré las dos tarjetas en `ajustes/cuentas.json` (run2).
4. Seguí el segundo aviso y añadí `"liquidacion tarjeta"` a `exclude_patterns.json` (run3).
5. Declaré también la conjunta en `cuentas.json` para que tuviera nombre propio en la hoja CUENTAS (run4).

Resultado de cada objetivo:

| Objetivo | Resultado |
|---|---|
| (a) Los avisos dicen qué hacer | Sí, si se siguen en el orden en que salen (ver §2) |
| (b) Cafés del 14/08 | Antes: **2** (se perdían 5,20 €). Después de declarar las tarjetas: **4**, dos en cada tarjeta |
| (c) Gasto de cada tarjeta y saldo de la conjunta, mes a mes | Sí, en la hoja CUENTAS. Cuadra con RESUMEN al céntimo en los tres meses |
| (d) Excluir el recibo de las tarjetas | Sí, con la línea que propone el programa. Agosto baja de 3.109,98 a 2.598,13 € y septiembre de 3.021,29 a 2.547,23 € |
| (e) La devolución de PRIMARK resta | Sí. `DEVOLUCION PRIMARK +24,99` va a Otros (regla `primark`) y resta del gasto de agosto |
| (f) El Acumulado cuadra con el banco | Sí: 7.376,64 €, igual que el último saldo del CSV. El programa lo dice: «🧮 Cuadra con el banco: 7.376,64 € a 28/09/2026, igual que el extracto.» |

Comprobé a mano las sumas de las tarjetas con los ficheros originales. Tarjeta 1111: julio 253,25, agosto 241,60, septiembre 239,51. Tarjeta 2222: julio 263,80, agosto 232,46, septiembre 207,02. Coinciden con la hoja CUENTAS, y cada mes coincide con la LIQUIDACION del mes siguiente.

CUENTAS al final (run4):

| Mes | conjunta · gastos | conjunta · ingresos | conjunta · saldo | tarjeta Irene · gastos | tarjeta pareja · gastos |
|---|---|---|---|---|---|
| 2026-07 | 2137,48 | 3510 | 5572,52 | 253,25 | 263,80 |
| 2026-08 | 2124,07 | 3510 | 6441,40 | 241,60 | 232,46 |
| 2026-09 | 2100,70 | 3510 | 7376,64 | 239,51 | 207,02 |

La suma de las tres columnas de gastos da el Total Gastos de RESUMEN: 2654,53 / 2598,13 / 2547,23.

## 2. Dónde me atasqué

No me llegué a atascar del todo, pero hubo un momento de duda en la primera ejecución. El aviso del recibo decía:

> · 2026-07: la tarjeta (Tarjeta_1111_movimientos.xls) suma 253,25 € … («LIQUIDACION TARJETA 1111»)
> · 2026-07: la tarjeta (Tarjeta_2222_movimientos.xls) suma 263,80 € … («LIQUIDACION TARJETA 2222»)
> · 2026-08: la tarjeta (Tarjeta_1111_movimientos.xls) suma 241,60 € … («LIQUIDACION TARJETA 1111»)
> No encuentro una clave segura que proponer (podría excluir algún otro movimiento tuyo); añádelo tú a mano con lo que ves arriba.

- Qué esperaba: la línea lista para pegar que promete la guía («propone la línea lista para pegar aquí»).
- Qué pasó: no la dio. Además solo encontró 3 de los 4 recibos: falta el de agosto de la tarjeta 2222 (232,46 €). La causa es el otro aviso: los dos cafés perdidos hacen que la tarjeta 2222 sume 5,20 € menos en agosto (227,26 €) y ya no cuadra con el recibo.
- Qué hice: seguí primero el aviso de `cuentas.json` y volví a ejecutar. Entonces sí salieron los 4 recibos y la propuesta: `Añade esto a exclude_patterns.json:  "liquidacion tarjeta"`.

Si hubiera hecho caso a LEEME («Lo primero que deberías configurar … exclude_patterns.json») y hubiera escrito el patrón a mano antes que `cuentas.json`, también habría salido bien. Pero me habría quedado la duda de por qué faltaba un recibo. El mensaje no dice que las dos cosas están relacionadas.

## 3. Errores o comportamientos raros

1. **(Fallo leve) La propuesta del recibo depende de haber arreglado antes `cuentas.json`, y no lo avisa.**
   - Cómo reproducirlo: `ajustes/` de fábrica, los tres ficheros en `entrada/`, `./ejecutar.sh`.
   - Qué sale: la lista de recibos sin «2026-08 … tarjeta 2222 … 232,46», y «No encuentro una clave segura que proponer».
   - Qué debería salir: algo como «declara primero las tarjetas (aviso anterior) y vuelve a ejecutar: así podré proponerte la línea». O que el propio aviso de las tarjetas diga que por su culpa uno de los recibos no cuadra.
2. **(Detalle) Un mensaje confuso en la primera ejecución, con el histórico vacío:** «🔁 2 movimientos ya estaban (en el histórico o en otro extracto); no se cuentan dos veces.» Eran mis dos cafés reales de la tarjeta 2222. Leído así parece algo bueno, cuando en realidad se estaban perdiendo 5,20 €. El aviso del final sí lo explica bien («Aquí ha pasado con 2: faltan 5,20 € en los totales»).
3. **(Detalle) La carpeta `entrada/` no viene en el ZIP.** El paso 1 de LEEME dice «déjalos en la carpeta entrada/», pero la carpeta no existe hasta la primera ejecución. Tuve que crearla yo. Comprobé que si ejecutas sin ella, la crea sola y dice «la carpeta 'entrada/' está vacía», así que no pasa nada grave.

Lo que funcionó bien:
- El aviso de las dos tarjetas es muy claro: dice qué pasa, cuánto dinero y qué fichero tocar.
- Declarar `"1111"` y `"2222"` funcionó a la primera, aunque en el nombre del fichero van pegados a un guion bajo (`Tarjeta_1111_…`).
- Al volver a ejecutar, los movimientos que ya estaban en el histórico se asignaron solos a su cuenta: «🏦 69 movimientos del histórico, asignados a su cuenta según ajustes/cuentas.json.»
- Nada se duplicó al ejecutar varias veces.
- El saldo inicial (4.200,00 €) lo detectó solo.

## 4. Lo que no entendí de la guía, la web o los mensajes

- **«Fuera del balance».** En julio sale +517,05 y en agosto −42,99. La guía lo explica («las compras con tarjeta que el banco todavía no ha cargado en la cuenta»). Lo entendí después de pensarlo un rato, pero a primera vista un número positivo en julio, cuando todavía no había recibo excluido, desconcierta.
- **Si hay que declarar también la cuenta conjunta.** La guía dice que `cuentas.json` es para «más de una cuenta o tarjeta del mismo tipo», y no queda claro si hay que declarar la conjunta. Si no la declaras, en CUENTAS sale como «(sin identificar) · gastos / ingresos / saldo». Funciona, pero queda feo. Al declararla como `"conjunta"` sale con su nombre.
- **El aviso remite a «Varias cuentas o tarjetas».** En el PDF el apartado se titula «cuentas.json · varias cuentas o tarjetas». Se encuentra igual.
- **Cómo lanzar el programa de probar reglas.** La guía dice «En Mac y Linux, escribe python3», mientras que para el diagnóstico usa `app/.venv/bin/python`. No sé cuál tengo que usar. No lo necesité.

## 5. Lo que echo en falta (preferencias, no fallos)

- **La columna `cuenta` en `salida/movimientos_limpios.xlsx`.** Solo trae fecha…categoria más origen y regla. Si quiero hacer mis propias sumas por persona en mi Excel, tengo que filtrar por el nombre del fichero (`origen`).
- **Que la hoja CUENTAS separe devoluciones de gastos, o lo diga.** «tarjeta pareja · gastos» de agosto (232,46) ya lleva restada la devolución de PRIMARK. Me parece bien, pero la cabecera dice «gastos».
- **Más protagonismo para `cuentas.json` en LEEME.** «Lo primero que deberías configurar» solo habla del recibo. Una línea del tipo «si tenéis una tarjeta cada uno, declara también cuentas.json» me habría ahorrado una vuelta.

## 6. Valoración: 8,5 / 10

Conseguí los seis objetivos solo con la documentación y los avisos, sin tocar código:
- 4 cafés, no 2.
- Recibos excluidos y gastos sin inflar.
- Devolución restando.
- Acumulado igual al banco.
- Gasto por persona en CUENTAS, cuadrando con RESUMEN.

Los avisos dicen qué fichero tocar y cuánto dinero está en juego, que es lo que más valoro. No le doy más nota por el orden de los avisos: en la primera ejecución no me dio la línea del recibo y me dejó con un recibo sin encontrar, sin decirme que era culpa del otro aviso. Y hay algún mensaje del resumen, el de «2 movimientos ya estaban», que a primera vista tranquiliza cuando no debería.
