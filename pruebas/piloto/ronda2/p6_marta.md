# Informe de Marta (piloto p6), versión 2.12.1

## 1. Perfil y qué intenté

Soy Marta, 41 años, diseñadora autónoma. Me manejo con el ordenador pero no programo. Tengo dos cuentas en el mismo banco: la del negocio (`cuenta_negocio_3T2026.xls`) y la personal (`cuenta_personal_3T2026.xls`). Cada mes paso 1.200 € de una a otra. Lo hice todo en Linux con los `.sh`.

Lo que hice, en este orden:
1. `instalar.sh` y después `ejecutar.sh` con `entrada/` vacía.
2. Copié los dos extractos a `entrada/` sin tocar ningún ajuste y ejecuté.
3. Leí «cuentas.json · si tienes más de una cuenta» en la GUIA.pdf, declaré las dos cuentas y ejecuté otra vez.
4. Añadí mis categorías (Facturas, Autonomos y Software; Impuestos ya venía de fábrica) y mis reglas, y ajusté los Bizum. A propósito, escribí mal una categoría para ver qué pasaba.
5. Además, probé en una copia de la carpeta qué pasa si el banco me da un fichero con otro nombre (`movimientos (1).xls`).

## 2. Dónde me atasqué

Casi en ningún sitio. La instalación y la primera ejecución fueron limpias. Con la carpeta vacía el mensaje es claro: «❌ No hay histórico y la carpeta 'entrada/' está vacía. Suelta ahí los ficheros…».

- **Primera ejecución con las dos cuentas mezcladas.** Al principio me asusté: «⚠️ No cuadra con el banco: el extracto dice 4.658,23 € a 29/09/2026 y el cálculo da 3.380,96 €», y debajo una lista de fechas con importes que no entiendo («19/07/2026: +4.370,78 €»). El mensaje acaba bien («Son 2 ficheros de cuenta. Si son de cuentas DISTINTAS […] decláralas en ajustes/cuentas.json»), pero lo primero que se lee es una lista de descuadres que habla de un extracto que «falta». Eso despista cuando no falta nada. Es una **preferencia**: yo pondría la pista de cuentas.json en primer lugar cuando hay más de un fichero de cuenta.
- **Los Bizum.** La guía dice «Un Bizum que recibes es un ingreso». Para mí no lo es: son amigos que me devuelven su parte de una cena o de un regalo. Probé `"bizum": "Ocio"` para los dos signos y el Ocio me salió **negativo** (−57,99 en julio). La guía avisa de que pasa, así que no es un fallo, pero no sabía qué hacer. Al final creé una categoría de ingreso «Bizum amigos» con `{"+": "Bizum amigos", "-": "Ocio"}` y activé `desglosar_ingresos`, para que Facturas tuviera su propia columna. Echo en falta que la guía proponga algo para el caso de «pagar a medias».

## 3. Errores o comportamientos raros

### FALLO grave: si un extracto no casa con ninguna cuenta declarada, se duplica sin avisar
- Cómo reproducirlo: con `cuentas.json` = `{"negocio":"negocio","personal":"personal"}` y el histórico ya cargado, copia el mismo extracto del negocio como `entrada/movimientos (1).xls` y ejecuta.
- Qué pasa: «➕ 16 movimientos nuevos». El histórico pasa de 52 a 68 filas, y esas 16 tienen `cuenta` vacía. El resumen cree que hay 3 cuentas: «(sin identificar): 3.400,00 €», y el Acumulado sube a 11.439,19 € cuando lo real es 6.780,96 €. Además, las tres cuentas dicen «🧮 Cuadra con el banco», así que da una tranquilidad falsa, y no sale ningún aviso de que ese fichero no casaba con ninguna cuenta.
- Por qué me preocupa: el LEEME dice «Con el nombre y la extensión que traigan. No hay que renombrar nada» y «da igual si dos descargas se solapan». Pero en cuanto declaras cuentas, hay que renombrar siempre, y si se te olvida una vez se duplica. Mi banco descarga todo como «movimientos.xls».

### FALLO: una categoría mal escrita en MI regla no se descarta, y el gasto desaparece de los totales
- Cómo reproducirlo: `"adobe": "Sofware"` (falta la t) en `rules.json`, con `Software` declarada en `categorias.json`.
- Qué pasa: Adobe queda con categoría «Sofware», fuera de Total Gastos (−60,49 €/mes), y aparece en «Fuera del balance» (−60,49). También desaparece de «Cargos que se repiten» y no sale en «Sin clasificar». El Acumulado sigue cuadrando, pero el gasto del mes queda 60,49 € por debajo.
- A favor: sí avisa, y bien. «⚠️ Las categorías de rules.json y categorias.json no cuadran · «Sofware» se asigna en rules.json pero no está en categorias.json: esos movimientos no aparecerán en ninguna columna del resumen».
- En contra: la guía dice otra cosa. Dice: «Si la categoría es nueva, declárala también en categorias.json […]: si no, las reglas que la usan **se descartan** y se avisa al ejecutar». Con las reglas de la base sí pasa («15 reglas de la base descartadas»), pero con las mías no. Yo esperaba que se descartara y que Adobe siguiera en «Otros».

### Rareza menor: el probador de reglas con varios conceptos
- Comando: `app/.venv/bin/python app/reglas.py "BIZUM DE PABLO REGALO" 25 "BIZUM A SARA BAR" -8 "SEG SOCIAL REGIMEN AUTONOMOS" -294`
- Salida: usa −294 para todos los conceptos y trata «25» y «-8» como si fueran conceptos: «25  -294,00 €  ->  Otros [sin regla]». La guía solo enseña un concepto con un importe, así que es más una expectativa mía que un fallo, pero confunde.

### Cosas que funcionaron bien (comprobado)
- **(a) Declarar las cuentas DESPUÉS no duplica.** 52 filas antes y 52 después (16 negocio, 36 personal, ninguna sin cuenta). Mensajes: «🏦 52 movimientos del histórico, asignados a su cuenta según ajustes/cuentas.json» y «➕ Ningún movimiento nuevo». Además hizo una copia en `datos/copias/`.
- **(b) Los traspasos de 1.200 €.** Van a «Transferencias internas» (neutra) sin que yo haga nada. No suman ni en gastos ni en ingresos: los Ingresos de julio son 2.281,75 = facturas + Bizum, sin los 1.200. Y «Fuera del balance» queda en 0 porque salida y entrada se compensan.
- **(c) Nada que entra sin regla resta de los gastos.** Las facturas sin regla fueron a «Ingresos» y no a «Otros». No hubo gastos negativos salvo el Ocio de mi prueba de Bizum, y ese lo provoqué yo.
- **(d) Los saldos cuadran** en cuanto declaras las cuentas: «🧮 Cuadra con el banco (negocio): 4.658,23 €» y «(personal): 2.122,73 €». Es lo mismo que dicen los extractos. El Acumulado (6.780,96) es la suma de los dos.
- Impuestos ya existía y el IVA (AEAT 303) cayó ahí solo. La cuota de autónomos también iba a Impuestos, y la moví a mi categoría Autonomos repitiendo la clave. Funcionó a la primera.
- Las sugerencias de «Sin clasificar» traen la línea lista para pegar (`"norte": {"+": "PON_TU_CATEGORIA"}`). Muy útil.

## 4. Lo que no entendí de la guía, la web o los mensajes

- La guía explica cuentas.json solo como un problema de deduplicación: «un movimiento idéntico el mismo día en dos cuentas distintas se cuenta una sola vez». No dice que, sin declararlas, **los saldos nunca cuadran** (eso lo dice el programa, no la guía). Tampoco dice que a partir de entonces **todos** los ficheros tienen que llevar el trozo del nombre, ni qué pasa si alguno no lo lleva.
- «Misma sintaxis que rules.json: inicio de palabra». Dudé si «negocio» contaría como inicio de palabra en `cuenta_negocio_3T2026` (va detrás de un guion bajo). Funcionó, pero la guía no lo aclara.
- El mensaje «15 reglas de la base descartadas: apuntan a categorías que no tienes» aparece en cada ejecución por haber quitado Hijos y Perros, que no me hacen falta. Al principio pensé que había roto algo.

## 5. Lo que echo en falta

- Un aviso cuando hay cuentas declaradas y un fichero no casa con ninguna, o que el programa pregunte a qué cuenta pertenece. Mejor aún, que la distinga por el saldo o el contenido y no por el nombre.
- Ver el resumen por cuenta (negocio y personal por separado), o al menos el saldo de cada una por mes. Como autónoma, lo que me importa es el resultado del negocio.
- Una sugerencia en la guía para los Bizum de «pagar a medias».
- Que una regla mía con una categoría mal escrita se trate igual que las de la base: descartarla y dejar el movimiento en Otros.

## 6. Valoración: 7/10

Hace bien lo importante: lee los dos extractos sin tocar nada, deja los traspasos fuera, cuadra al céntimo con el banco y no duplica al declarar las cuentas tarde. Los mensajes son claros y te dicen qué pegar. Resto puntos por el fallo del nombre de fichero, que en mi caso es real (mi banco lo llama todo «movimientos.xls») y encima dice «Cuadra con el banco» con el dinero duplicado. También por la contradicción entre la guía y el programa con las categorías mal escritas.
