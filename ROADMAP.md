# Roadmap

Dos partes. **Primero el producto, después la web**: una web enseña lo que hay,
y hoy hay dos cosas que cualquiera que la descargue se va a encontrar de frente.

Cada hito es pequeño a propósito: se implementa, se valida y se cierra. Ninguno
depende del siguiente.

Supuestos: repositorio público en GitHub, en español, público pequeño
(gente que quiere llevar sus cuentas y no va a tocar código).

---

## Parte A — Producto

### A1. Informe de «esto no sé clasificarlo» ✅ cerrado

Al terminar, listar los movimientos que han caído en `Otros`, ordenados por
importe, agrupando los que comparten palabras. Con una línea sugerida para
pegar en `rules.json`.

*Por qué:* hoy afinar las reglas es adivinar. Esto lo convierte en un bucle
guiado: ejecutas, ves lo gordo que falta, pegas dos líneas, vuelves a ejecutar.
Es la mejora con más efecto por menos código.

*Hecho cuando:* con un extracto sin reglas, el informe señala los tres gastos
mayores sin clasificar y la regla propuesta funciona al pegarla.

### A2. Detección del recibo de la tarjeta ✅ cerrado

Si `exclude_patterns.json` está vacío y hay movimientos de tarjeta, buscar en
la cuenta cargos cuyo importe cuadre con la suma de la tarjeta de ese mes y
proponerlos como candidatos.

*Por qué:* es el fallo número uno y el único que produce números falsos en
silencio. Sin excluirlo, cada gasto de la tarjeta cuenta dos veces. Hoy depende
de que la persona lea el LEEME.

*Hecho cuando:* con un par de extractos de ejemplo, propone el recibo correcto
y no propone nada cuando ya hay exclusiones puestas.

### A3. Identificador de cuenta en la deduplicación ✅ cerrado

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

### B1. Preparar el terreno ⏳ parcial

Repositorio público, licencia (MIT vale), primera release con el ZIP y el
`.exe` adjuntos, y decidir el nombre y el dominio.

*Hecho cuando:* alguien puede descargar la herramienta desde una URL.

*Estado (22/09/2026):* release **v2.10.1** publicada con el ZIP y el `.exe`
de Windows. Falta solo que el usuario ponga el repo en **público** (sigue
privado, así que la descarga solo funciona para él) y actualizar las notas
de la release, que aún anuncian el `.exe` como «más adelante». Ver
`TRASPASO.md` §5.

### B2. Portada ✅ contenido cerrado

Una página. Qué hace, para quién, y **la privacidad arriba del todo**: todo se
procesa en tu ordenador, no hay servidor, no hay cuenta, no sale nada a
internet. Dos o tres capturas del Excel resultante. Botón de descarga.

*Por qué:* alguien va a dar sus movimientos bancarios a esto. Si la primera
pantalla no responde «¿dónde acaban mis datos?», no pasa de ahí.

*Hecho cuando:* se entiende qué es y se descarga sin hacer scroll de más.

*Estado:* contenido y diseño comiteados en `eledger-web`. El botón de
descarga apunta a la release de GitHub — no funciona de verdad hasta que B1
tenga una release publicada.

### B3. La guía, en HTML ✅ contenido cerrado

Pasar el contenido de `GUIA.pdf` a páginas web. El PDF se sigue generando para
llevarlo dentro del ZIP.

*Por qué:* un PDF no se busca en Google ni se abre bien en el móvil, y la guía
es donde está la respuesta a casi todo.

*Hecho cuando:* se puede enlazar una sección concreta y se lee bien en móvil.

*Ojo:* se genera desde la misma fuente que el PDF, o los dos se separan en tres
versiones. Contenido deliberadamente recortado frente al PDF (ver B4 y el
propio `eledger-web`): la web vende «simple», el PDF puede ser exhaustivo.

### B4. Página de reglas ✅ contenido cerrado

La sintaxis explicada con ejemplos, las trampas del límite de palabra, las
reglas por signo, y cómo contribuir a la base (enlaza con A4).

*Hecho cuando:* alguien escribe su primera regla sin preguntar nada.

*Estado:* `reglas.html` es ahora la referencia canónica de sintaxis (la guía
enlaza aquí en vez de repetirla). «Cómo contribuir a la base» queda como
«próximamente», sin enlazar a un proceso que no existe hasta que A4 se haga.

### B5. Publicar

Desplegar, comprobar en móvil, y dejarlo. Sin analítica: sería incoherente con
lo que dice la portada.

*Estado:* pendiente — `eledger-web` ya es público pero Pages sigue sin
activar (22/09/2026). Activarlo es una acción del usuario, no de la IA (ver `CLAUDE.md` de `eledger-web`: nunca se hace `git push` ni se toca
la configuración de GitHub desde aquí).

---

## Orden sugerido

```
A1 → A2 → B1 → B2 → B3 → (A3 / A4 / B4 según haga falta)
```

A1 y A2 primero porque cambian lo que la web tiene que contar. B1 antes que B2
porque una portada sin descarga no sirve de nada.

## Lo que se ha hecho fuera de este roadmap

Este documento es el plan original, no un registro de cambios — para eso está
`CHANGELOG.md`. Alguna mejora ha salido de conversaciones con el usuario sin
mapear a ningún hito de aquí (p. ej. personalizar columnas de RESUMEN y el
gráfico de Acumulado, en la 2.5.0): mirar ahí para lo que no aparezca en esta
lista. Hasta ahora:

- **2.5.0** — personalizar columnas de RESUMEN (`etiquetas`, `orden_resumen`)
  y gráfico de Acumulado (quitado en la 2.11.0).
- **2.7.0** — desglosar los ingresos por categoría en RESUMEN
  (`desglosar_ingresos`).
- **2.8.0** — informe de cargos que se repiten (suscripciones, cuotas,
  seguros), solo por pantalla y sin opinar. Salió del estudio de mercado como
  el hueco más claro en herramientas de este tipo.
- **2.9.0** — arreglos tras la primera prueba en Windows: gráfico vacío en
  OnlyOffice y debajo de la tabla, el histórico se abre por RESUMEN, la
  ventana no se cierra sola (menú final) y pantalla por bloques con los
  avisos al final.
- **2.10.0** — base de reglas ampliada con cadenas genéricas de toda España,
  arreglado el orden de la base y retiradas tres reglas de transferencias
  que eran de una contabilidad concreta.
- **2.10.1** — el ZIP para repartir fuerza los saltos de línea de cada
  lanzador (salió al preparar la primera release).
- **2.11.0** — fuera el gráfico de RESUMEN (en OnlyOffice seguía saliendo
  mal: mejor nada que algo mal) y colores en la salida del terminal.
- **2.12.0** — el Acumulado pasa a ser el saldo real de la cuenta (no
  cuadraba con el banco en cuanto había traspasos o excluidos), columna
  Fuera del balance, fuera Extras y Deuda, y cuadre día a día contra el
  saldo del extracto. También: no falla con el histórico abierto (pide
  cerrarlo o guarda en una copia) y opción «Ejecutar de nuevo».

## Lo que queda fuera a propósito

- **Nada de subir extractos a la web.** Ni siquiera «procesado en el navegador»:
  la promesa de privacidad deja de ser verificable de un vistazo.
- **Probador de reglas en la web.** Tentador, pero obligaría a reescribir el
  motor en JavaScript y acabaría desviándose del de Python sin que nadie lo
  note. Si se hace algún día, con casos de prueba compartidos entre los dos.
- **Multiidioma, blog, newsletter, versión de pago.** No hasta que haya alguien
  usándolo.
