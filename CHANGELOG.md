# Cambios

Lo primero que hace falta saber cuando algo va mal es **qué versión tienes**.
Sale al ejecutar, en la primera línea, y queda grabada en la hoja `_meta` de
`datos/historico.xlsx`.

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
