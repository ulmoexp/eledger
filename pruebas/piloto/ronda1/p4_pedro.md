# Informe de uso · Pedro (71 años, jubilado) · eledger 2.12.0 en Linux

## 1. Perfil y qué intenté

Soy Pedro, jubilado. Tengo una sola cuenta y cobro la pensión el día 1 o 2 de cada mes (para mí es la del mes anterior). Mi banco solo me deja bajar CSV y sin columna de saldo. Me bajé dos ficheros que se solapan en agosto: `movimientos (1).csv` (julio-agosto) y `movimientos (2).csv` (agosto hasta el 2 de octubre).

Esto es lo que hice:
1. Leí LEEME.txt y GUIA.pdf. Ejecuté `./instalar.sh` y copié los dos CSV a `entrada/` sin renombrarlos.
2. Ejecuté `./ejecutar.sh` y miré `datos/historico.xlsx` (RESUMEN y MOVIMIENTOS).
3. Comprobé en qué mes cae la pensión y si agosto sale duplicado.
4. Miré el bloque «Cargos que se repiten».
5. Simulé que dejaba el Excel abierto: creé `datos/.~lock.historico.xlsx#` y volví a ejecutar, sin terminal interactiva y con ella. Luego «cerré el Excel» (borré el fichero de bloqueo) y seguí.
6. Añadí `"pension"` a `ajustes/mes_contable.json` y ejecuté otra vez.

## 2. Dónde me atasqué

**La pensión no se movió al mes anterior (hasta que cambié un ajuste).**
- **Qué esperaba.** La guía dice: «Una nómina o una prestación que entra el día 1, 2 o 3 corresponde en realidad al mes anterior». Por eso pensé que la pensión se movería sola.
- **Qué pasó.** El `mes_contable.json` que se crea la primera vez solo trae `"palabras": ["nomina"]`. La pensión del 02/10 se quedó en octubre. La consola decía `Último mes (2026-10): gastos 0,00 € · ingresos 1.432,18 € · balance +1.432,18 €`, y en el RESUMEN salía un mes de octubre con 1.432,18 € de ingresos y ningún gasto. Julio, agosto y septiembre tenían cada uno la pensión cobrada ese mismo mes, no la del mes siguiente.
- **Cómo lo arreglé.** Tuve que deducir que había que añadir `"pension"` a `palabras`. Con eso salió `4 con el mes contable ajustado` y el último mes pasó a ser septiembre.
- **Qué es.** Más una **preferencia o carencia de la configuración de partida** que un fallo, porque la guía sí explica cómo se configura. Aun así, para un pensionista es lo primero que hay que tocar y nada se lo dice. La guía pone de ejemplo `["nomina", "mutua"]`, pero la plantilla ni siquiera trae «mutua».

**No sé cuál es mi saldo.** Lo explico en el punto 5.

## 3. Errores o comportamientos raros

**Lo que fue bien, que conste:**
- La instalación funcionó a la primera.
- Los CSV se leyeron sin tocarlos: `formato=texto, cabecera en fila 3`.
- **Agosto no se duplica.** En la primera ejecución salió `🔁 8 movimientos ya estaban (extractos que se solapan); no se cuentan dos veces.` y `➕ 25 movimientos nuevos.` Cuadra: 16 + 17 − 8 = 25.
- El resumen trae tres gráficos.

**a) Excel abierto: funciona bien con terminal (con un matiz).** Lo que hice: `.~lock.historico.xlsx#` en `datos/` y después `./ejecutar.sh`.
- **Con terminal (doble clic).** Sale `── Hay ficheros abiertos ── · datos/historico.xlsx … Intro Ya está cerrado: seguir / C … copia / S Seguir igualmente`. Si pulso Intro con el fichero todavía abierto, dice `Todavía está abierto.` y vuelve a preguntar. Cuando borré el bloqueo y pulsé Intro, salió `✅ Cerrado. Sigo.`: actualizó el histórico y guardó una copia en `datos/copias/historico_20260924_214347.xlsx`. Muy bien, se entiende.
- **Sin terminal (entrada por tubería).** No pregunta nada: escribe directamente `datos/historico (copia 2026-09-24 21.42.24).xlsx`. El aviso final lo explica bien («El histórico de verdad NO se ha actualizado…»).
- **El matiz (fallo menor de mensaje).** La cabecera de resultados dice `✅ datos/historico (copia …).xlsx · hojas RESUMEN y MOVIMIENTOS`. El check verde me hace pensar que todo ha ido bien. Además, esa copia se queda en `datos/`, justo al lado del histórico de verdad, con un nombre casi igual: sería fácil abrir la que no es la próxima vez.

**b) Mensaje engañoso al volver a ejecutar (fallo menor de texto).** Sin ningún fichero nuevo, la segunda ejecución dice `🔁 33 movimientos ya estaban (extractos que se solapan); no se cuentan dos veces.` No es que mis extractos se solapen 33 veces: es que ya estaban en el histórico de antes. La línea anterior (`📚 Histórico previo: 25 movimientos.`) lo aclara, pero el paréntesis confunde.

**c) El Acumulado sale como «saldo al cierre del mes», pero no lo es (fallo de cara al usuario).** Sin columna de saldo, el Acumulado empieza en 0. Aun así:
- la consola dice `Acumulado (saldo al cierre del mes): +4.248,36 €`;
- el gráfico se titula `Acumulado (saldo de la cuenta)`;
- la guía dice «Acumulado es el saldo real de tu cuenta al cerrar el mes, el mismo que te da el banco»;
- la web dice «Cuadra con tu banco. El Acumulado es el saldo real de tu cuenta».

Mi cuenta no tiene 4.248 €. En ninguna ejecución salió un aviso del tipo «tu extracto no trae saldo: el Acumulado empieza en 0 y no es tu saldo». La guía lo menciona, pero enterrado en «De dónde parte el Acumulado»: «Sin esa columna empieza en 0».

**d) El ajuste de mes hace que el Acumulado sea un saldo que nunca existió (raro).** Con `pension` añadida, aparece una fila `2026-06` con Acumulado `1.432,18`. El 30 de junio ese dinero aún no estaba en mi cuenta: entró el 1 de julio. Entiendo por qué pasa (la pensión va a junio porque es la de junio), pero contradice «saldo real al cerrar el mes».

**e) En Linux, `instalar.sh` termina diciendo `Ya puedes usar  ejecutar.command`** (fallo menor). En Linux el fichero se llama `ejecutar.sh`; `.command` es el de Mac.

**f) Clasificaciones dudosas de la base (preferencias):**
- `RECIBO SANITAS SEGURO SALUD` → `Higiene` (regla `sanitas`). Es un seguro médico.
- `RECIBO TELEFONICA` se queda sin clasificar (en `Otros`), aunque la base conoce Movistar.
- `ABONO PENSION INSS` sí va bien a `Ingresos` (regla `=inss`).

## 4. Lo que no entendí

- **«Balance»**: lo intuyo, «lo que entra menos lo que sale». Para mí «balance» suena a saldo, así que al principio lo confundí con el Acumulado.
- **«Fuera del balance»**: no lo habría entendido sin la guía. Además, en mi caso vale siempre 0,00 €, así que es una columna que no me dice nada.
- **«Acumulado»**: pensé que era mi saldo, porque así lo llaman la consola, el gráfico y la web. No lo es (punto 3c).
- **«mes_ajustado» / «mes contable»**: la idea sí la entiendo, porque es justo lo que yo quería. Lo que no vi es que tenía que tocar un JSON para que se aplicara a la pensión.
- **Palabras técnicas** como «regla `=inss`», «JSON», «categoria_manual», «n_rep» o «columnas A–G»: la guía está bien hecha, pero para alguien como yo es mucha información. Me sobran las partes de tarjetas, varias cuentas y sincronizar.
- **Categorías de partida**: «Hijos», «Perros» y «Prestamos» no son mías. No sé si puedo borrarlas sin estropear nada; entiendo que sí, en `categorias.json`, pero me da miedo.

## 5. Lo que echo en falta

1. **Poder decir cuánto tenía en la cuenta un día concreto** (un saldo inicial a mano). Así el Acumulado sería de verdad mi saldo aunque el CSV no traiga esa columna. Sin eso, lo que se pierde es:
   - saber cuánto dinero tengo;
   - comprobar que no falta ningún movimiento entre un extracto y otro (con saldo, la herramienta «comprueba día a día»);
   - que el gráfico «saldo de la cuenta» signifique algo.
2. **Un aviso cuando falta la columna de saldo**, por ejemplo: «Tu extracto no trae saldo: el Acumulado es la suma desde el primer movimiento, no tu saldo real».
3. **Que «pension» (y «prestacion», «mutua») vengan de serie** en `mes_contable.json`, o que el programa lo proponga: «Hay un ingreso fijo que entra el día 1-2: ¿quieres contarlo en el mes anterior?».
4. **Recibos fijos en el Excel, no solo en pantalla.** La lista «Cargos que se repiten» está muy bien: `5 cargos que se repiten; al importe de hoy suman 4.334,76 € al año`. Pero:
   - desaparece al cerrar la ventana, porque el Excel solo tiene RESUMEN, MOVIMIENTOS y _meta;
   - mezcla la transferencia a mi hija (1.800 €/año) con los recibos. Mis recibos de verdad (comunidad, Sanitas, Naturgy y Telefónica) suman 2.534,76 €/año, y esa cuenta la tuve que hacer yo;
   - separar «RECIBO …» de «TRANSFERENCIA …» me ayudaría.
5. **Una hoja «Léeme» o comentarios en la cabecera del RESUMEN**, que expliquen en una frase qué es Balance, Fuera del balance y Acumulado.

## 6. Valoración: 6/10

**A favor:**
- La instalación y la primera ejecución fueron sin tropiezos.
- Leyó mis CSV sin renombrarlos.
- El solapamiento de agosto se resolvió bien y lo explicó.
- El caso del Excel abierto está muy bien resuelto con terminal: pregunta, insiste, sigue al cerrarlo y hace copia de seguridad.
- La lista de cargos que se repiten es justo lo que quería.

**En contra:**
- Mis dos preguntas principales no salieron bien a la primera:
  - la pensión en su mes pide editar un JSON que nadie me dijo que tocara;
  - el saldo que me enseña como «saldo al cierre del mes» no es mi saldo, sin ningún aviso, mientras la web presume de «Cuadra con tu banco».
- Para mi perfil (una cuenta, sin tarjeta, CSV sin saldo), la mitad de la guía no me aplica y la mitad que sí me aplica tuve que descubrirla por mi cuenta.
