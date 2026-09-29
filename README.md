# Movimientos bancarios

Herramienta local para clasificar tus movimientos bancarios. Lee los
extractos que te descargas del banco (cuenta y tarjeta), los une sin
duplicar, los clasifica por categorías y te deja un Excel con histórico y
resumen mensual, con gráficos. Se abre con Microsoft Excel, OnlyOffice o
LibreOffice.

**Todo se procesa en tu ordenador.** No hay servidor, no hay cuenta, no sale
nada a internet. Es justo lo que hace falta para darle tus movimientos
bancarios a algo: que ese algo no los mande a ningún sitio.

## Cómo se usa

1. Descarga los extractos del banco (cuenta y tarjetas) y déjalos, tal cual,
   en la carpeta `entrada/`.
2. Doble clic en `ejecutar.bat` (Windows), `ejecutar.command` (Mac) o
   `ejecutar.sh` (Linux).
3. Abre `datos/historico.xlsx`.

Puedes volver a ejecutarlo cuantas veces quieras: lo que ya estuviera no se
duplica, así que da igual si dos descargas se solapan.

La primera vez hace falta `instalar.bat` (`instalar.command` en Mac,
`instalar.sh` en Linux), que prepara las librerías necesarias sin tocar nada
más de tu sistema. En Linux, si el doble clic no lo ejecuta, dale permisos
primero: `chmod +x instalar.sh`. Todo esto está explicado con más detalle en
[`LEEME.txt`](LEEME.txt) y, sección por sección, en [`GUIA.pdf`](GUIA.pdf).

## Descarga

La última versión está en la página de
[**releases**](https://github.com/ulmoexp/eledger/releases). Descarga el ZIP,
descomprímelo entero (no lo abras dentro del propio ZIP) y sigue los tres
pasos de arriba.

## Qué hace

- Detecta el formato real del extracto mirando el contenido, no la
  extensión: los bancos españoles llaman `.xls` a cinco cosas distintas
  (HTML, XML, CSV, xlsx real y BIFF), y esto no se confunde.
- Distingue cuenta de tarjeta, y evita contar dos veces el gasto de la
  tarjeta cuando la cuenta paga su recibo (te avisa solo si detecta el caso).
- Clasifica por categorías con un fichero de reglas tuyo (`rules.json`) más
  una base de comercios conocidos en toda España, que se actualiza con cada
  versión sin tocar las tuyas.
- Al terminar, te dice qué se ha quedado sin clasificar, agrupado y con una
  línea lista para pegar en tus reglas. Y qué cargos se repiten cada mes o
  cada año (suscripciones, cuotas, seguros), con lo que suman al año.
- El Acumulado del resumen es el saldo real de tu cuenta: si el extracto
  trae el saldo, parte de él y comprueba que acaba donde dice el banco.
- Todo el histórico se recalcula en cada ejecución: si afinas una regla, se
  reclasifica hacia atrás sin tener que volver a descargar nada.
- Lee también los CSV de los neobancos (columnas en inglés) y los extractos
  que parten el importe en Cargo y Abono.
- Varias cuentas o tarjetas (`cuentas.json`): nada se fusiona entre ellas, y
  una hoja aparte enseña lo que gasta cada una y su saldo.
- Si ya llevas tus cuentas en tu propio Excel, puede añadir ahí los
  movimientos nuevos, con tus columnas, sin tocar lo que ya tienes.
- Si vienes de otra app de finanzas, su export entra como un extracto más y
  puede conservar las categorías que ya tenías.

## Apoya el proyecto

Es gratis y lo seguirá siendo. Si te resulta útil, puedes enviar lo que
quieras por Lightning (bitcoin) a
**`victoriouscookie143740@getalby.com`**, o escanear el código QR de la
[web](https://ulmoexp.github.io/eledger-web/#apoya). ¿No usas bitcoin? Una
estrella en el repositorio también ayuda.

## Estructura del repositorio

```
app/            el programa (Python) + la base de reglas + las plantillas
pruebas/        red de pruebas de caja negra (python pruebas/probar.py)
ajustes/        tu configuración una vez instalado (no se reparte)
entrada/        donde sueltas los extractos del banco
salida/         se regenera en cada ejecución
datos/          historico.xlsx y sus copias — lo único insustituible
```

`ajustes/`, `entrada/`, `salida/` y `datos/` son tuyos una vez instalado: si
compartes la carpeta con alguien, usa `exportar.bat` (`.command` en Mac,
`.sh` en Linux) en vez de comprimir la carpeta entera — genera un ZIP con
el programa y unas reglas de partida genéricas, sin nada tuyo dentro.

## Si vas a tocar el código

`TRASPASO.md` explica cómo está montado y qué queda pendiente;
`CHANGELOG.md` lleva el registro de cada versión. Antes y después de
cualquier cambio:

```
python pruebas/probar.py
```

## Licencia

[MIT](LICENSE).
