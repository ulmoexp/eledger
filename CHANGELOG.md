# Cambios

Lo primero que hace falta saber cuando algo va mal es **qué versión tienes**.
Sale al ejecutar, en la primera línea, y queda grabada en la hoja `_meta` de
`datos/historico.xlsx`.

---

## 2.13.0

Arreglos de la segunda ronda del piloto con usuarios simulados.

- **Con varias cuentas declaradas, volver a descargar un extracto con otro
  nombre ya no lo duplica.** Un «movimientos (1).xls» que no casaba con
  ninguna cuenta de `cuentas.json` entraba como una cuenta más y todo lo
  suyo contaba dos veces, con el cuadre en verde. Ahora, si sus
  movimientos ya están en una cuenta declarada, no se lee y se avisa de
  que lo renombres.
- **Dos tarjetas (o cuentas) sin declarar: se avisa.** Un cargo idéntico el
  mismo día en las dos (dos cafés iguales, uno en cada tarjeta) se contaba
  una sola vez sin decir nada. Ahora, si dos ficheros del mismo tipo cubren
  las mismas fechas sin parecerse, se avisa de cuánto falta y de que hay
  que declararlas en `cuentas.json`.
- **Cobrar de una comunidad de propietarios es un ingreso.** La regla de
  fábrica de la comunidad no miraba el signo, y un autónomo que factura a
  una comunidad veía esos cobros en Piso, restando. Ahora solo clasifica
  los cargos.
- **Una regla tuya con una categoría mal escrita se descarta**, como ya se
  hacía con las de la base. Antes se aplicaba y el movimiento se salía de
  Total Gastos para ir a «Fuera del balance». Ahora sigue con las demás
  reglas y el aviso dice qué regla es.
- **Dos etiquetas con el mismo nombre ya no rompen el programa.** Además de
  caerse, dejaban el histórico a medias (sin gráficos ni formato). Ahora
  la etiqueta que choca se ignora y se avisa; y el histórico se escribe
  aparte y solo se pone en su sitio al terminar, así que un fallo a mitad
  ya no lo estropea.
- **Sincronización con tu fichero:**
  - no escribe encima de una tabla tuya: si en la esquina configurada hay
    otras cabeceras (tu hoja de siempre), se niega y explica qué columnas
    escribiría. Antes la reescribía entera y tus fórmulas pasaban a sumar
    otra cosa;
  - detecta que el fichero está abierto en LibreOffice, OnlyOffice o Excel
    y no escribe;
  - si no hay nada nuevo, no toca el fichero ni gasta una copia de
    seguridad (antes, a las diez ejecuciones se perdía la copia buena).
- **Se leen más formatos:** el importe en dos columnas (Cargo y Abono, Debe
  y Haber) y los CSV de neobancos con la columna «Payee» (N26).
- **Detección del recibo de la tarjeta con dos tarjetas:** busca el recibo
  de cada una por separado, y un grupo que parece ese recibo ya no recibe
  en «Sin clasificar» la sugerencia de ponerle categoría.
- **«Sin clasificar» con dinero que entra** propone lo común a todos los
  cobros («transf») en vez del nombre de un solo cliente, y la devolución
  de una compra va en el grupo de su comercio.
- Mensajes y detalles:
  - si hay ficheros en `entrada/` pero ninguno se puede leer, lo dice (antes
    decía que la carpeta estaba vacía);
  - una hoja que añadas a mano al histórico avisa de que no se conserva y
    de en qué copia está;
  - el impuesto de vehículos del ayuntamiento tiene regla (Transporte);
  - `reglas.py` admite varios conceptos, cada uno con su importe:
    `"BIZUM DE X" 25 "BIZUM A Y" -18`.
- Guía: cuentas.json también para tarjetas, qué columnas escribe la
  sincronización y que la hoja es solo suya, a qué carpeta es relativo
  `archivo`, el precio de renombrar categorías, la categoría Impuestos y
  cómo tratar los Bizum de amigos que te devuelven una cena.

---

## 2.12.1

Arreglos que salieron de un piloto con usuarios simulados.

- **Declarar `cuentas.json` después de la primera ejecución ya no duplica
  el histórico.** Antes, todos los movimientos pasaban a contar dos veces y
  la única salida era borrar el histórico. Ahora los que ya estaban reciben
  su cuenta según el fichero del que salieron. Si tu histórico ya se había
  duplicado así, se arregla solo en la próxima ejecución.
- **Lo que entra sin ninguna regla va a Ingresos**, no a «Otros». Un cobro o
  una recarga sin regla restaban de los gastos y dejaban meses con «gastos»
  negativos. Siguen saliendo en «Sin clasificar» para que les pongas regla.
- **Una nómina se reconoce aunque el pagador sea un colegio o un
  supermercado.** «NOMINA COLEGIO…» caía en Hijos y «NOMINA MERCADONA» en
  Comida, porque esas reglas iban delante en la base.
- **Sincronización: tus notas siguen a su movimiento.** Si tenías notas al
  lado de los movimientos en tu fichero de contabilidad y entraba uno más
  antiguo, cada nota se quedaba en su fila y pasaba a acompañar al
  movimiento de al lado, sin avisar. Ahora se recolocan junto al suyo.
- **Sin columna de saldo, el Acumulado ya no se llama «saldo».** Empieza en
  0 y es lo que ha variado la cuenta; se avisa, y la pantalla y el gráfico
  lo llaman «desde el primer movimiento».
- Mensajes más claros:
  - un error de formato en un JSON de `ajustes/` dice qué fichero, qué
    línea y qué suele ser (antes salía en inglés y sin fichero), y se
    acepta el UTF-8 del Bloc de notas;
  - un fichero vacío pide volver a descargarlo, y lo que no es un extracto
    (un PDF) se nombra por pantalla en vez de ignorarse en silencio;
  - al repetir una ejecución ya no dice «extractos que se solapan»;
  - si no cuadra con el banco y hay varios ficheros de cuenta sin declarar,
    sugiere `cuentas.json`;
  - el recibo de la tarjeta ya no sale también en «Sin clasificar» con un
    consejo contrario, y los grupos de dinero que entra se marcan como tal;
  - se avisa de `orden_resumen` sin «Mes» y de etiquetas para columnas que
    no existen, y se nombran las reglas de la base descartadas;
  - el resultado guardado en una copia ya no sale con un ✅ verde;
  - en Linux, el instalador ya dice `ejecutar.sh`.
- De fábrica, la pensión también cuenta en el mes anterior (como la
  nómina), y Telefónica va a Fibra/móvil.
- **Categoría nueva, Impuestos**, en la plantilla: pagos a Hacienda (renta,
  IVA, IRPF) y cuota de autónomos. Si ya usas la herramienta, añádela a tu
  `categorias.json` (en `gastos`) para tenerla; si no, esos cargos siguen en
  «Otros» como hasta ahora.
- Las reglas encuentran el concepto aunque el banco escriba un guion donde
  tu regla tiene un espacio: `basic fit` encuentra «BASIC-FIT».
- Si falta la carpeta del programa, los lanzadores ya no ponen de ejemplo
  `ajustes/rules.json`, que no viene en el ZIP.

---

## 2.12.0

- **El Acumulado es ahora el saldo real de tu cuenta** al cerrar cada mes, el
  mismo que te da el banco. Antes era el saldo inicial más la suma de los
  Balances, y se despegaba del banco sin avisar: cada traspaso a otra cuenta
  tuya (que no es gasto) y cada movimiento excluido (el recibo de la
  tarjeta) salían de la cuenta sin restar del Acumulado, y el error se
  arrastraba mes a mes. Con varios traspasos, la diferencia podía llegar a
  miles de euros.
- **Columna nueva, Fuera del balance**, entre Balance y Acumulado: lo que
  movió la cuenta sin ser gasto ni ingreso (traspasos, lo excluido y las
  compras con tarjeta que el banco aún no ha cargado). Cada fila cuadra a
  ojo: Acumulado del mes anterior + Balance + Fuera del balance.
- **Fuera las columnas Extras y Deuda.** Eran el Acumulado del mes anterior
  partido por su signo, que ya se lee en la fila de arriba. Si las tenías en
  `orden_resumen`, se avisa de que ya no existen; quítalas de ahí.
- **Comprueba que cuadra con el banco.** Si el extracto trae saldo, se
  compara día a día con el calculado. Si cuadra, lo dice; si no, avisa de en
  qué fechas deja de cuadrar y por cuánto (casi siempre, un extracto que
  falta entre medias).
- **Ya no falla con el histórico abierto.** Antes de empezar mira si el
  histórico (o `movimientos_limpios.xlsx`) está abierto en Excel u
  OnlyOffice y te pide guardarlo y cerrarlo; en cuanto lo cierras y pulsas
  Intro, sigue. Si prefieres dejarlo abierto (tecla C), el resultado se
  guarda en una copia con fecha al lado, y se avisa de que el histórico de
  verdad no se ha actualizado. No cierra nunca tu hoja de cálculo por su
  cuenta: podrías perder cambios. En Mac y Linux, además, evita que al
  guardar desde la hoja de cálculo pises sin saberlo el resultado nuevo.
- **Vuelven los gráficos a la hoja RESUMEN**, debajo de la tabla: el
  Acumulado mes a mes, los ingresos y gastos de cada mes, y el gasto medio
  al mes por categoría. Se ven en Microsoft Excel, OnlyOffice y
  LibreOffice. El de la 2.10 salía mal en OnlyOffice por cómo se escribían
  sus ejes; está resuelto.
- **Los importes de la pantalla, en formato español**: `5.000,00 €` en vez
  de `5,000.00 €`, como los escribe tu banco.
- **La cabecera de `categoria_manual` es naranja** en la hoja MOVIMIENTOS,
  como decía la guía: es la única columna que escribes tú. Hasta ahora era
  verde como todas.
- Arreglos menores de texto: «1 mes» en vez de «1 meses»; en Linux, el
  aviso de que falta una librería manda a `instalar.sh` (antes decía
  `instalar.command`, que es el de Mac); y si falta `xlrd`, se pide volver a
  lanzar el instalador en vez de un `pip install` que la dejaba fuera del
  entorno de la herramienta.
- **Ejecutar de nuevo**, opción 3 del menú final, para ver al momento el
  efecto de una corrección sin cerrar la ventana. Tras un error, la R hace
  lo mismo.

---

## 2.11.1

- **Todo lo que se descarga se llama ahora `eledger`**: el programa compilado
  para Windows es `eledger.exe` (antes `Movimientos.exe`) y el ZIP que genera
  `exportar.bat` sale como `eledger_v2.11.1_<fecha>.zip`. El nombre en
  pantalla sigue siendo Movimientos bancarios; lo que cambia es el nombre de
  los ficheros, para que se vea de dónde salen.
- Si ya tenías el `.exe`, reemplázalo por el nuevo y borra el viejo: son el
  mismo programa con otro nombre, y tener los dos solo lleva a ejecutar el
  que no toca.

---

## 2.11.0

- **Fuera el gráfico de la hoja RESUMEN.** En OnlyOffice seguía saliendo
  mal incluso tras el arreglo de la 2.9.0, y mejor no enseñar nada que
  enseñarlo mal. La tabla no cambia: el Acumulado sigue siendo su última
  columna.
- **Colores en la pantalla**, para que se lea mejor: títulos de cada bloque
  destacados, lo que ha ido bien en verde, los avisos en amarillo, los
  errores en rojo y lo secundario en gris. Solo en una ventana de terminal:
  si la salida va a un fichero, o existe la variable `NO_COLOR`, sale sin
  color, igual que antes. Sin nada que instalar.

---

## 2.10.1

- **El ZIP para repartir lleva siempre los saltos de línea correctos**:
  los de Windows en los `.bat` y los de Linux/Mac en los `.sh` y
  `.command`, generes el ZIP donde lo generes. Antes dependían de la copia
  de la que saliera, y un ZIP podía llevar `.bat` que fallasen en Windows o
  `.sh` que no arrancasen en Linux.

---

## 2.10.0

- **Base de reglas ampliada** con cadenas genéricas de toda España:
  supermercados regionales (Bonpreu, bonÀrea, Gadis, Froiz, Condis,
  Caprabo, Covirán, HiperDino, Spar...), gasolineras low cost, peajes,
  trenes, autobuses y aerolíneas, alquiler de coches, comercializadoras de
  luz y agua, operadores de móvil y fibra, IBI y alarmas, plataformas y
  cines, cadenas de restauración y gimnasios, seguros de salud, tiendas de
  mascotas, financieras y tiendas online. Todas van a las categorías que
  trae la plantilla.
- Ingresos que solo cuentan si son positivos: paro (SEPE), pensión (INSS o
  «pensión») y devoluciones de Hacienda (AEAT).
- **Arreglado el orden de la base**: el alquiler de un coche caía en Piso,
  un pedido de Uber Eats en Transporte, una clínica veterinaria en Higiene y
  Amazon Prime en Otros. Gana la primera regla que casa, así que las
  concretas van ahora antes que las generales que las contienen.
- **Retiradas de la base** tres reglas que mandaban las transferencias que
  haces a «Transferencias internas»: dinero que envías no va por fuerza a
  otra cuenta tuya, y marcado como neutro desaparecía del gasto.
  Si alguna tuya sí lo es, decláralo en tu `rules.json`.

---

## 2.9.0

- **El gráfico de RESUMEN salía vacío en OnlyOffice** (y en cualquier
  programa que no lo recalcule al abrir). Ahora lleva sus valores dentro,
  además de la referencia a las celdas, y los meses van como texto.
- El gráfico va **debajo de la tabla**, no a su derecha.
- `historico.xlsx` **se abre por RESUMEN**: es la primera hoja y la que se ve
  al abrir. MOVIMIENTOS va después.
- **La ventana ya no se cierra sola al terminar**, tampoco con el `.exe`. Al
  acabar bien, ofrece abrir el histórico, abrir su carpeta o cerrar. Si algo
  falla, espera a que se pulse Intro.
- **La pantalla se lee mejor**: va por bloques (qué ha leído, resultado,
  cargos que se repiten, sin clasificar) y **los avisos salen juntos al
  final**, contados, en vez de mezclados con todo y muchas veces lo primero.
  Si el recibo de la tarjeta podría estar contando gastos dos veces, se
  señala junto a los totales y el detalle va con los avisos.

---

## 2.8.0

- **Cargos que se repiten.** Al terminar, se listan por pantalla los cargos
  que pasan cada mes o cada año con un importe parecido (suscripciones,
  cuotas, seguros), con lo que suman al año al precio de hoy y de más a
  menos. Solo informa: no dice qué hacer con ninguno. Un anual aparece con
  dos cargos, así que hace falta algo más de un año de histórico para verlo.
  Lo que se ha dejado de cobrar ya no sale.

---

## 2.7.0

- **Desglosar los ingresos en RESUMEN.** Nuevo campo opcional en
  `categorias.json`: `"desglosar_ingresos": true` da a cada categoría de
  ingreso su propia columna, justo antes del total **Ingresos**, que sigue
  ahí y sigue sumando lo mismo. Sin el campo, una sola columna como siempre.
  La categoría que se llama `Ingresos` (la de la plantilla, la que asignan
  las reglas de la base) sale como **Otros ingresos**, para no chocar con el
  total; con ese nombre se la cita también en `etiquetas` y `orden_resumen`.
- Se avisa por pantalla si una categoría se llama igual que otra columna del
  resumen (por ejemplo un gasto llamado `Balance`): una de las dos no se
  vería. Y si `orden_resumen` pide una categoría de ingreso sin haber
  activado el desglose, el aviso lo dice en vez de tratarla como una errata.
- Arreglado: si `orden_resumen` quitaba `Total Gastos`, `Ingresos`,
  `Balance` o `Acumulado`, el Excel se guardaba bien pero la ejecución
  acababa con un error al enseñar el resumen por pantalla, y se saltaba el
  listado de movimientos sin clasificar. Ahora se enseña solo lo que haya.

---

## 2.6.0

- **Linux, documentado y funcionando de verdad.** `instalar.sh`,
  `ejecutar.sh` y `exportar.sh` ya existían pero no se mencionaban en
  `LEEME.txt`, `README.md` ni la web. Además tenían el mismo fallo que los
  `.command` de Mac: ninguno de los dos llevaba el permiso de ejecución, así
  que el doble clic no los arrancaba en un ZIP recién descomprimido.
  `exportar.py` ahora fuerza ese permiso al generar el ZIP repartible,
  **sin importar en qué sistema operativo se genere** (Windows no tiene ese
  concepto de permisos, así que antes se perdía si el ZIP se creaba ahí).
- Los propios ficheros del repositorio (`.sh` y `.command`) llevan ya el
  bit de ejecución, para que un `git clone` o la descarga directa de GitHub
  también funcionen a la primera.

---

## 2.5.0

- **Personalizar la hoja RESUMEN.** Dos campos opcionales nuevos en
  `categorias.json`: `etiquetas` (nombre interno → texto de columna, para
  cambiar cómo se ve una columna sin arriesgar el cuadre letra-por-letra con
  `rules.json`) y `orden_resumen` (qué columnas salen y en qué orden,
  incluidas las de sistema como `Balance` o `Acumulado`, antes fijas al
  final). Sin ninguno de los dos, el resumen sale exactamente igual que
  siempre. Un nombre mal escrito en `orden_resumen` avisa por pantalla, no
  rompe la ejecución.
- La hoja RESUMEN incluye ahora un gráfico de línea de **Acumulado**, para
  ver de un vistazo si vas bien o vas mal. Sin anotaciones ni consejos
  generados: solo el gráfico.

---

## 2.4.0

- **Identificador de cuenta en la deduplicación** (hito A3 del roadmap). Dos
  cuentas del mismo tipo con un movimiento idéntico el mismo día se fusionaban
  en una: ahora se declara en `ajustes/cuentas.json` un patrón (misma
  sintaxis que `rules.json`) contra el NOMBRE DEL FICHERO, y cada cuenta
  declarada da filas propias. Sin declarar nada, el comportamiento es el de
  siempre: nadie con una sola cuenta nota ningún cambio.
- El saldo inicial (2.3.0) ahora se calcula **por cuenta** y se suma: con dos
  cuentas declaradas, cada una arrastra su propio saldo de partida.
- El histórico guarda la cuenta de cada fila (columna nueva, al final, no
  desplaza nada de A–L). Los históricos antiguos se migran solos, sin
  identificar (no se puede saber a toro pasado de qué cuenta era cada fila).
- Primera versión pública: repositorio abierto bajo licencia MIT
  (`LICENSE`), `README.md` para GitHub, y el ZIP repartible (`exportar.py`)
  lleva ahora la licencia dentro.

---

## 2.3.0

- **Saldo inicial de la cuenta.** Si el extracto trae columna de saldo, el
  `Acumulado` del resumen parte del saldo real que tenía la cuenta antes del
  primer movimiento, en vez de partir siempre de 0. Se detecta solo (no hace
  falta configurar nada) y se avisa por pantalla de qué saldo ha usado.
  Sin columna de saldo, o sin movimientos de cuenta (solo tarjeta), el
  comportamiento es el de siempre: `Acumulado` empieza en 0.
- Si el primer día con movimientos de cuenta trae más de uno, no se adivina
  el orden en que el banco los aplicó: se busca el primer día sin ambigüedad
  (uno solo) y se resta desde ahí lo de los días anteriores. Si ningún día es
  inequívoco, se prefiere partir de 0 antes que arriesgar un saldo inventado.
- El histórico guarda ahora el saldo de cada fila de cuenta (columna nueva,
  al final, no desplaza nada de las columnas A–L). Los históricos antiguos se
  migran solos; como el saldo de lo que ya pasó no puede recuperarse a toro
  pasado, esa primera vez el Acumulado sigue partiendo de 0 hasta que haya
  algún movimiento nuevo con saldo.

---

## 2.2.0

- **Detección del recibo de la tarjeta** (hito A2 del roadmap, el fallo #1
  del programa: si la cuenta paga la tarjeta y no se excluye ese recibo,
  cada gasto cuenta dos veces). Si `exclude_patterns.json` está vacío y hay
  movimientos de tarjeta, se busca en la cuenta un cargo que cuadre (con 2
  céntimos de tolerancia) con lo que suma la tarjeta ese mes, dentro de una
  ventana de hasta 45 días tras el cierre del mes, y se propone la parte fija
  del texto para pegar en `exclude_patterns.json` (sin el número de
  referencia, que cambia cada mes). Un mes con más de un cargo que cuadra se
  descarta en vez de adivinar, y la clave se valida contra el resto de los
  movimientos de cuenta antes de proponerla. Con cualquier patrón ya puesto
  en `exclude_patterns.json`, no dice nada.
- `GUIA.pdf` se genera ahora con las fuentes Lato + DejaVu (instalables con
  `apt install fonts-lato fonts-dejavu`) en vez de con Poppins, que solo
  existía en la carpeta personal de quien la escribió la primera vez y no se
  podía reproducir en otra máquina.

---

## 2.1.0

- **Informe de «esto no sé clasificarlo»** (hito A1 del roadmap). Al terminar,
  si quedan movimientos que han caído en Otros sin que ninguna regla casara
  (no cuenta lo que una regla manda explícitamente a Otros, eso ya está
  clasificado), se agrupan por la palabra más repetida, se ordenan por
  importe de mayor a menor y se enseñan los 10 grupos más gordos, cada uno
  con una línea lista para pegar en `rules.json`.
- La clave que se sugiere se valida antes de proponerla: se comprueba con el
  propio motor de reglas que no capturaría ningún movimiento que ya tiene
  categoría por otra regla. Si la palabra más repetida del grupo colisiona
  (p.ej. "barcelona" dentro de un movimiento que ya clasifica "taxi"), se
  prueba con otra palabra del mismo grupo; si todas colisionan, no se sugiere
  nada y se avisa de que hay que revisarlo a mano.
- El relleno típico del banco (compra, pago, recibo, tarj, tarjeta,
  transferencia) y los números sueltos (referencias, dígitos de tarjeta)
  nunca se proponen como clave.

---

## 2.0.1

- Los lanzadores comprueban que la carpeta está completa antes de hacer nada.
  Si se descargan los ficheros de uno en uno se pierden las carpetas y todo
  queda plano; `instalar.bat` creaba entonces un `app\.venv` dentro de una
  carpeta `app\` vacía (porque `python -m venv` crea las carpetas intermedias),
  y al ejecutar salía un «No such file or directory» que no explicaba nada.
  Ahora se detecta el caso y se dice qué hacer.

---

## 2.0.0

Reorganización de carpetas, reglas en dos capas y red de pruebas. **Al
actualizar, la primera ejecución recoloca la carpeta sola** y hace una copia de
todo lo anterior en `datos/copias/antes_de_migrar_<fecha>/`.

### Carpetas

- El programa vive en `app/`. Los datos, en `entrada/`, `salida/`, `datos/` y
  `ajustes/`. Para actualizar basta con reemplazar `app/` y `GUIA.pdf`.
- `rutas.py` centraliza dónde va cada cosa. Antes todo era relativo al
  directorio actual y solo funcionaba porque el lanzador hacía `cd` primero;
  ahora da igual desde dónde se ejecute.
- Migración automática desde la versión anterior, con copia previa. Si un
  fichero ya existe en su destino no se pisa: se avisa y se deja al usuario
  decidir.
- Los `.py` sueltos que queden en la raíz tras actualizar se señalan, pero no
  se borran solos.

### Reglas

- **Dos capas.** `ajustes/rules.json` son las tuyas y mandan;
  `app/rules_base.json` trae las cadenas conocidas en toda España y se
  reemplaza con cada versión. Para cambiar una regla de la base, repite la
  clave en la tuya; para apagarla, ponla a `null`.
- **Reglas según el signo:** `{"+": "Ingresos", "-": "Ocio"}`. Arregla el caso
  del Bizum, donde los recibidos restaban de Ocio y el mes salía barato sin
  motivo. También se puede dar un solo lado, y los movimientos del otro signo
  siguen buscando en las reglas de más abajo.
- Una regla de la base que apunte a una categoría que no está en tu
  `categorias.json` se descarta. Si se aplicara, esos movimientos no contarían
  en ninguna columna del resumen y el total descuadraría en silencio.
- `python app/reglas.py "TEXTO" -25` acepta un importe y marca de qué capa
  sale cada regla.

### Mes contable

- Se configura en `ajustes/mes_contable.json` (`dias`, `palabras`,
  `solo_ingresos`). Antes estaba fijo dentro del código.
- **Mira el signo:** la prestación que cobras de la mutua se va al mes
  anterior, pero el recibo que le pagas no. Antes se movían los dos.
- Al actualizar se conserva la lista anterior (`nomina` y `mutua`) para que los
  totales no cambien. Una instalación nueva arranca solo con `nomina`.

### Correcciones

- Una `categoria_manual` con una categoría que no existe **ya no se aplica**.
  Antes se aplicaba y el movimiento acababa en una categoría fantasma: no
  contaba como gasto, ni como ingreso, ni como excluido, y desaparecía de los
  totales con un aviso fácil de pasar por alto.
- `sincronizar.py` ya no borra filas enteras si tienes datos propios fuera de
  las columnas volcadas. Antes, una columna de notas al lado de la tabla se
  perdía en cuanto un mes traía menos filas que el anterior.
- `build_guia.py` tenía incrustada una ruta absoluta de la máquina donde se
  escribió; en otro ordenador fallaba. Ahora publica al lado del LEEME.
- El modo de comprobación de `reglas.py` leía la configuración del directorio
  actual, así que desde la raíz del proyecto daba «sin regla» en todo.

### Versionado

- Fichero `app/VERSION` y hoja `_meta` en `datos/historico.xlsx` con la versión
  que lo generó, la fecha y las columnas.
- Los parches del tipo «si la columna no existe, créala» pasan a ser
  migraciones explícitas, numeradas y contadas por pantalla al aplicarse.
- Si el histórico lo escribió una versión **más nueva** que la que ejecutas, el
  programa se planta en vez de escribirlo: podría tener columnas que esta
  versión no conoce y se perderían.

### Repartir la herramienta

- `exportar.bat` genera un ZIP con el programa, la guía y plantillas genéricas,
  **sin** `entrada/`, `salida/`, `datos/` ni `ajustes/`. Funciona por lista
  blanca: copia solo lo autorizado, así que un fichero nuevo no se cuela por
  olvido. Antes de escribir el ZIP vuelve a revisar lo recogido y se planta si
  algo huele a datos.
- Se limpiaron de datos reales los ficheros que se reparten: la batería de
  ejemplo de `reglas.py`, el stub de `xlrd`, las plantillas y los ejemplos de la
  guía llevaban un bar, unos importes y los dígitos de una tarjeta sacados de un
  extracto de verdad.
- Las pruebas ya no arrancan con la configuración personal del usuario, sino con
  las plantillas: dan el mismo resultado en cualquier máquina y no hay datos de
  nadie escritos en ellas.
- Ampliada `rules_base.json` con las cadenas genéricas que faltaban (Bizum,
  mutua, hospital, O2, Ticketmaster, concesionarios).

### Instalación y reparto

- `instalar.bat` crea un entorno propio en `app/.venv` e instala ahí las
  librerías, sin tocar el Python del sistema. Los lanzadores lo usan si existe.
- Si faltan las librerías, sale un mensaje que dice qué hacer en vez de un
  traceback de Python.
- `compilar.bat` y `movimientos.spec` generan `Movimientos.exe` con PyInstaller,
  para quien no ha usado nunca una terminal. Hay que compilarlo **en Windows**.
  Se niega a compilar si alguna prueba falla.
- El `.exe` guarda los datos y la configuración **en su propia carpeta**, no
  dentro: los JSON se siguen pudiendo editar con el bloc de notas.
- `COMPILAR.md` explica el proceso y los falsos positivos de antivirus, que con
  PyInstaller son frecuentes y conviene avisar de antemano.

### Pruebas

- Carpeta `pruebas/` con 46 casos y 200 comprobaciones, y un `probar.bat` de
  doble clic. Cubre los cinco formatos de banco, las trampas de las reglas, la
  deduplicación, la migración, la semilla de configuración y los tres casos de
  `sincronizar.py`.
- Son de caja negra: montan una carpeta temporal, ejecutan el programa entero y
  comprueban el Excel resultante. No tocan tus datos.
- Un caso barre todo lo que se reparte buscando rastros de configuración
  personal, comparándolo con `rules_base.json` para distinguir lo genérico de lo
  que identifica a alguien.

---

## Antes de 2.0.0

No hay registro por versiones. El proyecto se desarrolló sin numerar y lo que
se sabe de esa etapa está en `TRASPASO.md`: lectura de los cinco formatos que
los bancos llaman `.xls`, deduplicación con `n_rep`, columna
`categoria_manual`, coincidencia por límite de palabra en las reglas, resumen
mensual con acumulado, y volcado opcional al fichero de contabilidad.

Un histórico sin hoja `_meta` se considera de esta etapa y se trata como
`1.0.0`.
