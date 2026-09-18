# Movimientos bancarios

Herramienta local para clasificar tus movimientos bancarios. Lee los
extractos que te descargas del banco (cuenta y tarjeta), los une sin
duplicar, los clasifica por categorías y te deja un Excel con histórico y
resumen mensual.

**Todo se procesa en tu ordenador.** No hay servidor, no hay cuenta, no sale
nada a internet. Es justo lo que hace falta para darle tus movimientos
bancarios a algo: que ese algo no los mande a ningún sitio.

## Cómo se usa

1. Descarga los extractos del banco (cuenta y tarjetas) y déjalos, tal cual,
   en la carpeta `entrada/`.
2. Doble clic en `ejecutar.bat` (Windows) o `ejecutar.command` (Mac).
3. Abre `datos/historico.xlsx`.

Puedes volver a ejecutarlo cuantas veces quieras: lo que ya estuviera no se
duplica, así que da igual si dos descargas se solapan.

La primera vez hace falta `instalar.bat` (o `instalar.command`), que prepara
las librerías necesarias sin tocar nada más de tu sistema. Todo esto está
explicado con más detalle en [`LEEME.txt`](LEEME.txt) y, sección por sección,
en [`GUIA.pdf`](GUIA.pdf).

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
  línea lista para pegar en tus reglas.
- Si tu extracto trae el saldo de la cuenta, el resumen parte de ese saldo
  real en vez de partir de 0.
- Todo el histórico se recalcula en cada ejecución: si afinas una regla, se
  reclasifica hacia atrás sin tener que volver a descargar nada.

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
compartes la carpeta con alguien, usa `exportar.bat` (genera un ZIP con el
programa y unas reglas de partida genéricas, sin nada tuyo dentro) en vez de
comprimir la carpeta entera.

## Si vas a tocar el código

`TRASPASO.md` explica cómo está montado y qué queda pendiente;
`CHANGELOG.md` lleva el registro de cada versión. Antes y después de
cualquier cambio:

```
python pruebas/probar.py
```

## Licencia

[MIT](LICENSE).
