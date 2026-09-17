# Roadmap

Dos partes. **Primero el producto, después la web**: una web enseña lo que hay,
y hoy hay dos cosas que cualquiera que la descargue se va a encontrar de frente.

Cada hito es pequeño a propósito: se implementa, se valida y se cierra. Ninguno
depende del siguiente.

Supuestos: repositorio público en GitHub, en español, público pequeño
(gente que quiere llevar sus cuentas y no va a tocar código).

---

## Parte A — Producto

### A1. Informe de «esto no sé clasificarlo»

Al terminar, listar los movimientos que han caído en `Otros`, ordenados por
importe, agrupando los que comparten palabras. Con una línea sugerida para
pegar en `rules.json`.

*Por qué:* hoy afinar las reglas es adivinar. Esto lo convierte en un bucle
guiado: ejecutas, ves lo gordo que falta, pegas dos líneas, vuelves a ejecutar.
Es la mejora con más efecto por menos código.

*Hecho cuando:* con un extracto sin reglas, el informe señala los tres gastos
mayores sin clasificar y la regla propuesta funciona al pegarla.

### A2. Detección del recibo de la tarjeta

Si `exclude_patterns.json` está vacío y hay movimientos de tarjeta, buscar en
la cuenta cargos cuyo importe cuadre con la suma de la tarjeta de ese mes y
proponerlos como candidatos.

*Por qué:* es el fallo número uno y el único que produce números falsos en
silencio. Sin excluirlo, cada gasto de la tarjeta cuenta dos veces. Hoy depende
de que la persona lea el LEEME.

*Hecho cuando:* con un par de extractos de ejemplo, propone el recibo correcto
y no propone nada cuando ya hay exclusiones puestas.

### A3. Identificador de cuenta en la deduplicación

Añadir `cuenta` a la clave de deduplicación, deducida del fichero o declarada
en `ajustes/`. Migración del histórico incluida.

*Por qué:* ahora mismo dos cuentas corrientes distintas con un cargo idéntico
el mismo día se fusionan en uno. Ya está anotado en el traspaso. Es un bloqueo
real para cualquiera que no tenga exactamente una cuenta.

*Hecho cuando:* dos extractos de cuentas distintas con un movimiento idéntico
dan dos filas, y el histórico anterior sigue leyéndose.

### A4. Base de reglas abierta

`rules_base.json` pasa a ser el fichero al que la gente contribuye por GitHub,
con una plantilla de pull request y una prueba que valide el JSON y que toda
regla apunte a una categoría declarada.

*Por qué:* es lo único del proyecto que mejora solo con que lo use más gente.
Y es lo que da sentido a tener repositorio público.

*Hecho cuando:* hay instrucciones de cómo añadir un comercio y una prueba que
rechaza un JSON mal formado.

> Si hay que recortar, **A1 y A2 son los importantes**. A3 puede esperar a que
> alguien lo necesite, y A4 solo tiene sentido si la web trae gente.

---

## Parte B — Web

Estática, sin base de datos, sin cuentas, sin formularios. El producto se
descarga de GitHub; la web solo explica y enlaza.

### B1. Preparar el terreno

Repositorio público, licencia (MIT vale), primera release con el ZIP y el
`.exe` adjuntos, y decidir el nombre y el dominio.

*Hecho cuando:* alguien puede descargar la herramienta desde una URL.

### B2. Portada

Una página. Qué hace, para quién, y **la privacidad arriba del todo**: todo se
procesa en tu ordenador, no hay servidor, no hay cuenta, no sale nada a
internet. Dos o tres capturas del Excel resultante. Botón de descarga.

*Por qué:* alguien va a dar sus movimientos bancarios a esto. Si la primera
pantalla no responde «¿dónde acaban mis datos?», no pasa de ahí.

*Hecho cuando:* se entiende qué es y se descarga sin hacer scroll de más.

### B3. La guía, en HTML

Pasar el contenido de `GUIA.pdf` a páginas web. El PDF se sigue generando para
llevarlo dentro del ZIP.

*Por qué:* un PDF no se busca en Google ni se abre bien en el móvil, y la guía
es donde está la respuesta a casi todo.

*Hecho cuando:* se puede enlazar una sección concreta y se lee bien en móvil.

*Ojo:* se genera desde la misma fuente que el PDF, o los dos se separan en tres
versiones.

### B4. Página de reglas

La sintaxis explicada con ejemplos, las trampas del límite de palabra, las
reglas por signo, y cómo contribuir a la base (enlaza con A4).

*Hecho cuando:* alguien escribe su primera regla sin preguntar nada.

### B5. Publicar

Desplegar, comprobar en móvil, y dejarlo. Sin analítica: sería incoherente con
lo que dice la portada.

---

## Orden sugerido

```
A1 → A2 → B1 → B2 → B3 → (A3 / A4 / B4 según haga falta)
```

A1 y A2 primero porque cambian lo que la web tiene que contar. B1 antes que B2
porque una portada sin descarga no sirve de nada.

## Lo que queda fuera a propósito

- **Nada de subir extractos a la web.** Ni siquiera «procesado en el navegador»:
  la promesa de privacidad deja de ser verificable de un vistazo.
- **Probador de reglas en la web.** Tentador, pero obligaría a reescribir el
  motor en JavaScript y acabaría desviándose del de Python sin que nadie lo
  note. Si se hace algún día, con casos de prueba compartidos entre los dos.
- **Multiidioma, blog, newsletter, versión de pago.** No hasta que haya alguien
  usándolo.
