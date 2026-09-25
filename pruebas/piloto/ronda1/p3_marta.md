# Informe de uso · Marta (diseñadora autónoma, dos cuentas)

Versión probada: **2.12.0** (Linux, lanzadores `.sh`).

## 1. Perfil y qué intenté

Tengo 41 años y soy diseñadora autónoma. Me manejo con el ordenador, pero no programo. Tengo dos cuentas en el mismo banco:

- **Negocio**: cobro de facturas, cuota de autónomos, IVA y Adobe.
- **Personal**: alquiler, compra, luz y Bizum con amigos.

Cada mes paso 1.200 € del negocio a la personal. Me bajé los dos extractos del 3T2026 (`cuenta_negocio_3T2026.xls` y `cuenta_personal_3T2026.xls`; en realidad son HTML).

Lo que hice, en orden:

1. Ejecuté `instalar.sh` y luego `ejecutar.sh` con `entrada/` vacía, para que se crearan las carpetas.
2. Copié los dos extractos a `entrada/` **sin tocar nada de configuración**, como haría la primera vez, y lo ejecuté.
3. Leí en la guía lo de `cuentas.json`, declaré mis dos cuentas y volví a ejecutar.
4. Añadí mis reglas y categorías de autónoma: Facturas, Autonomos, Impuestos y Software. También cambié el Bizum.
5. Revisé RESUMEN y MOVIMIENTOS con openpyxl y lo exporté a PDF con LibreOffice para ver los gráficos.
6. Probé dos cosas más:
   - Bizum como categoría neutra en vez de ingreso.
   - Un nombre de categoría mal escrito.

Saldos reales según mis extractos, que es contra lo que comparé:

| Cuenta | Saldo inicial | Saldo final |
|---|---|---|
| Negocio | 3.400,00 € | 4.658,23 € (29/09) |
| Personal | 1.150,00 € | 2.073,92 € (25/09) |
| **Total** | 4.550,00 € | **6.732,15 €** |

## 2. Dónde me atasqué

### 2.1 La primera vez, sin declarar las cuentas, el saldo no cuadra y el mensaje me manda a buscar un extracto que no falta

Esperaba lo que dice la guía de `cuentas.json`: que solo hace falta *«si tienes más de una cuenta del mismo tipo»* y que sirve para que *«un movimiento idéntico el mismo día en dos cuentas distintas»* no se fusione. Como no tengo movimientos idénticos en las dos cuentas, pensé que me lo podía saltar.

Lo que pasó en la primera ejecución:

```
💰 Saldo inicial detectado: 1.150,00 €
   Lo que tenía tu cuenta antes del primer movimiento que hay.
...
   Acumulado (saldo al cierre del mes): +3.332,15 €
   ⚠️  No cuadra con el banco: el extracto dice 4.658,23 € a 29/09/2026
       y el cálculo da 3.332,15 €.
...
    Entre la fecha anterior con saldo y esa, falta un movimiento de ese
    importe (o sobra, si es negativo). Lo normal es un hueco entre dos
    extractos: descarga el que cubra esas fechas y vuelve a ejecutar.
```

- El saldo inicial solo es el de la personal (1.150 €). Se olvida de los 3.400 € del negocio.
- El «saldo del banco» con el que compara es el del negocio (4.658,23 €).
- El consejo es **falso** en mi caso: no me falta ningún extracto.

El programa ya sabe lo que necesita para darse cuenta. Lo dice él mismo en la lectura: dos ficheros `→ cuenta (columna «saldo»)` con saldos que se entrelazan. Aun así no me sugiere `cuentas.json`. Lo encontré porque me leí la guía entera. Otra persona se iría a buscar un extracto que no existe.

### 2.2 Declarar las cuentas DESPUÉS de la primera ejecución me duplicó todo (el problema más grave)

Después de añadir `"negocio": "negocio", "personal": "personal"` a `ajustes/cuentas.json` y volver a ejecutar:

```
📚 Histórico previo: 52 movimientos.
➕ 52 movimientos nuevos.
   104 movimientos · 0 excluidos
💰 Saldo inicial detectado en 3 cuentas (ver ajustes/cuentas.json); ...
   (sin identificar): 1.150,00 €
   negocio: 3.400,00 €
   personal: 1.150,00 €
   Acumulado (saldo al cierre del mes): +10.064,30 €
```

En el RESUMEN salía todo al doble: Piso 1.560 € en cada mes (pago 780 €), Comida y Ocio también al doble y un Acumulado de 10.064,30 € (el real es 6.732,15 €). No hay ningún aviso de que haya duplicados. Solo sale ese «(sin identificar)» y el aviso de siempre de que no cuadra, que de nuevo me manda a descargar un extracto que falta.

Volver a ejecutar no lo arregla: se queda en 104. Como usuaria solo encontré una salida, **borrar `datos/historico.xlsx` y reprocesar**. Pude hacerlo porque todavía tenía los `.xls`. La guía dice que ese fichero es «LO INSUSTITUIBLE», así que borrarlo me dio bastante miedo. Si hubiera tenido meses de histórico cuyos extractos ya no guardo, no sabría cómo salir de ahí sin marcar a mano 52 filas como `(excluido)`.

Además, la columna `origen` de esas filas «sin identificar» guarda el nombre del fichero (`cuenta_negocio_3T2026.xls`). Con el mismo patrón de `cuentas.json` se podría saber de qué cuenta era cada fila. El CHANGELOG 2.4.0 dice *«no se puede saber a toro pasado de qué cuenta era cada fila»*, pero en mi caso sí se podía.

### 2.3 Después de arreglarlo, todo bien

Con el histórico regenerado y las cuentas declaradas:

```
💰 Saldo inicial detectado en 2 cuentas ...
   negocio: 3.400,00 €
   personal: 1.150,00 €
   Acumulado (saldo al cierre del mes): +6.732,15 €
   🧮 Cuadra con el banco (negocio): 4.658,23 € a 29/09/2026, igual que el extracto.
   🧮 Cuadra con el banco (personal): 2.073,92 € a 25/09/2026, igual que el extracto.
```

Comprobé el Acumulado de cada mes a mano: julio 4.856,48 = 3.411,21 + 1.445,27, y agosto 5.809,48 = 4.034,72 + 1.774,76. Cuadra al céntimo.

## 3. Errores o comportamientos raros

**F1 · Fallo · Duplicación al declarar las cuentas después (ver 2.2).**
- Cómo reproducirlo:
  1. Dejar `cuentas.json` como viene y poner los dos extractos en `entrada/`.
  2. Ejecutar `./ejecutar.sh`.
  3. Añadir a `cuentas.json` `{"negocio":"negocio","personal":"personal"}`.
  4. Volver a ejecutar `./ejecutar.sh`.
- Resultado: `104 movimientos`, `Acumulado +10.064,30 €` y todos los gastos al doble. No sale ningún aviso de duplicados.

**F2 · Fallo en el diagnóstico · Con dos cuentas sin declarar, el aviso de descuadre da una causa falsa.**
- Cómo reproducirlo: es la primera ejecución del punto anterior.
- Resultado: dice *«falta un movimiento… descarga el que cubra esas fechas»*, cuando lo que falta es declarar las cuentas. Además lista diferencias sin sentido («19/07/2026: +4.421,61 €», «24/07/2026: -2.256,31 €», «... y 15 más»), que salen de mezclar dos saldos distintos.

**F3 · Fallo menor · El instalador de Linux dice el nombre de Mac.**
- Al terminar `instalar.sh` sale: `Listo. Ya puedes usar  ejecutar.command`. En Linux es `ejecutar.sh`.
- Pasa lo mismo con el mensaje de error de `instalar.sh` y `ejecutar.sh`. Cuando falta `app/`, dice que tiene que quedar `esta_carpeta/ajustes/rules.json`, pero el ZIP no trae `ajustes/`: se crea en la primera ejecución. Puede despistar a alguien que ya está perdido.

**F4 · Fallo menor · El comando de la guía para probar reglas no funciona tal cual en Linux.**
- La guía dice `python app/reglas.py "MEDIA MARKT ONLINE" ...`.
- En mi Linux sale `python: command not found`. Con `python3` sí va.
- En cambio, el diagnóstico de fichero de la misma guía usa `app/.venv/bin/python`. Estaría bien que los dos comandos siguieran el mismo criterio.

**Detalle (no sé si es fallo).** Con el typo `"adobe": "Sofware"`, el aviso dice *«esos movimientos no aparecerán en ninguna columna del resumen»*. La guía dice que esas reglas se descartan, así que en realidad el movimiento cae en la siguiente regla o en «Otros», que sí está en el resumen. El aviso en sí me pareció muy bueno: detectó a la vez el typo y la columna «Software» vacía.

**Lo que fue bien:**
- La detección del formato: el HTML con extensión `.xls` y la codificación windows-1252 se leyeron sin problema.
- La deduplicación al reejecutar (`52 movimientos ya estaban`).
- Los traspasos: la base ya trae `"traspaso": "Transferencias internas"` como neutra, y mis 1.200 € mensuales **no inflan ni ingresos ni gastos**.
- La regla por signo con `=aeat` funciona: `reglas.py "AEAT MODELO 303 IVA 2T" -612,30 → Impuestos`.
- `desglosar_ingresos: true` me da columnas separadas para Facturas y Bizum.

## 4. Lo que no entendí

- **Para qué sirve de verdad `cuentas.json`.** La guía, la web («Si las declaras en cuentas.json, un movimiento idéntico en dos cuentas no se fusiona en uno») y el propio JSON lo venden como algo de deduplicación. Para mí lo importante es otra cosa: **sin él, el saldo y el Acumulado salen mal** en cuanto tienes dos cuentas corrientes con saldo. En la parte «De dónde parte el Acumulado» se menciona de pasada: «Con más de una cuenta declarada en cuentas.json, es la suma de todas». No lo relacioné hasta que vi el fallo.
- **«Saldo inicial … (sin identificar)».** No explica qué significa ni qué tengo que hacer.
- **Los gastos negativos antes de configurar nada.** En la primera ejecución el resumen del último mes decía `gastos -829,50 € · ingresos 93,17 € · balance +922,67 €`. Unos gastos negativos no los entendí. Luego vi el motivo: mis facturas cobradas, al no tener regla, caían en «Otros», que es una categoría de gasto, y restaban. La guía explica que un gasto a favor sale negativo, pero no avisa de que **un cobro sin regla va a «Otros» y resta de los gastos**. Para una autónoma, esa es justo la primera impresión. Ayudó que la lista de «Sin clasificar» mostrara `-7.502,00 € · norte` y `-5.566,00 € · lopez`, con el signo al revés que el resto.
- **La regla base `bizum` manda los Bizum recibidos a «Ingresos».** Con eso, el gráfico «Ingresos y gastos» me mezclaba los 20 € de Pablo con mis facturas. Es una preferencia, pero para mí no son ingresos. Lo resolví de dos maneras y las dos cuadran:
  - Bizum amigos como ingreso aparte, con `desglosar_ingresos`.
  - Bizum amigos como neutra: van a «Fuera del balance» y el Acumulado sigue cuadrando.

## 5. Lo que echo en falta

- **El saldo de cada cuenta en el RESUMEN** (preferencia fuerte). Solo hay un Acumulado, que es la suma de las dos, y el gráfico se titula «Acumulado (saldo de la cuenta)», en singular. Por pantalla sí sale «Cuadra con el banco (negocio) / (personal)», pero en el Excel no veo cuánto tiene cada cuenta a fin de mes. Quiero una columna de Acumulado por cuenta, o un gráfico con una línea por cuenta.
- **Separar el negocio de lo personal en el resumen** (preferencia). Gastos e ingresos van todos juntos. Para saber cuánto gano «de verdad» como autónoma me gustaría filtrar por cuenta, o tener un resumen por cuenta. Ahora tengo que hacerlo yo con SUMAR.SI.CONJUNTO sobre la columna N (`cuenta`).
- **Que el programa me proponga `cuentas.json`** cuando ve dos ficheros de tipo cuenta con saldo propio. Ya propone la línea de `exclude_patterns.json` para la tarjeta; esto sería lo mismo.
- **Una vía segura para asignar la cuenta a las filas «sin identificar»**, usando `origen`, en vez de duplicarlas.
- **Reglas base para autónomos.** Ninguna de mis líneas habituales tenía regla: `SEG SOCIAL REGIMEN AUTONOMOS`, `AEAT MODELO 303` y `ADOBE`. No lo considero un fallo, pero no hay ni una categoría de autónomo (cuota, impuestos) en las de partida.

## 6. Valoración: 6/10

Lo bueno:
- Instalar y obtener el primer resumen fue fácil.
- Los extractos «raros» se leen solos.
- Los traspasos entre mis cuentas no cuentan como ingreso ni como gasto.
- Crear las categorías de autónoma fue sencillo, con un aviso excelente si me equivoco.
- Una vez bien configurado, **el Acumulado cuadra al céntimo con mis dos extractos**, que era lo que más me importaba.
- Los tres gráficos se ven bien en LibreOffice. El de gasto medio por categoría me sirve de verdad: Piso, Autonomos e Impuestos son lo gordo.

Lo que baja la nota:
- Para alguien con dos cuentas, el camino natural (probar primero y configurar después) **duplica el histórico sin avisar**. Los mensajes me mandaron a buscar un extracto que no faltaba.
- Tuve que borrar el fichero que la propia guía llama insustituible.
- No veo el saldo de cada cuenta en el Excel.

Si se arreglan F1 y F2 y el resumen muestra el saldo de cada cuenta, le pondría un 8.
