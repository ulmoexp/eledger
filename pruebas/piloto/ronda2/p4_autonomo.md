# Informe del piloto — Manolo, electricista autónomo (versión 2.12.1)

## 1. Perfil y qué intenté

Manolo, 52 años, electricista autónomo con un empleado. Una sola cuenta de empresa
(`Movimientos_cuenta_empresa.xls`, 49 movimientos, julio a septiembre de 2026). No soy nada técnico,
pero me apaño con Excel.

Lo que hice:
1. Leí `LEEME.txt`, `GUIA.pdf` y la web (portada y «Reglas»).
2. `./instalar.sh`: sin problemas ("Listo. Ya puedes usar ejecutar.sh").
3. Copié el extracto en `entrada/` y ejecuté `./ejecutar.sh` sin tocar nada.
4. Vi el resultado, retoqué `ajustes/rules.json` y `ajustes/categorias.json` siguiendo la guía y volví a ejecutar.
5. Saqué las cifras del trimestre del Excel y comprobé el saldo.

Configuración final que me puse (resumida):
- `rules.json`: `"transf. de": {"+": "Facturas cobradas"}`, `"bricomart": "Material"`, `"leroy merlin": "Material"`,
  `"gasolinera": "Gasoil"`, `"impuesto vehiculos": "Impuestos"`, `"alquiler nave": "Nave"`, `"gestoria": "Gestoria"`,
  `"seguro rc": "Seguros"`.
- `categorias.json`: gastos `Material, Gasoil, Nave, Gestoria, Seguros, Impuestos, Otros`; ingresos
  `Facturas cobradas, Ingresos`; `"desglosar_ingresos": true`.

## 2. Dónde me atasqué

**No me atasqué de verdad en nada**: con la guía llegué a todo. Lo que más me costó:

- **El primer resumen tenía «Piso» en negativo y no entendía por qué.** Julio salía `Piso -3160.05`
  y agosto `-986.45`. Mi negocio no tiene piso. Tuve que ir a la hoja MOVIMIENTOS y mirar la columna
  «regla» para descubrirlo (ver fallo 3.1). La guía sí dice que un negativo es «una categoría que acaba
  el mes a favor», pero yo lo que pensé es que estaba roto.
- **Cómo separar las facturas cobradas.** El bloque «Sin clasificar» me propuso para las transferencias
  `añade a rules.json:  "antonio": {"+": "PON_TU_CATEGORIA"}`. Antonio Ruiz es UN cliente; si le
  hago caso, cada cliente nuevo cae otra vez sin clasificar. Me lo tuve que inventar yo: `"transf. de"`.
  Además, esa sugerencia no incluía las transferencias de la Comunidad de Propietarios, porque esas ya
  «tenían regla» (la de Piso), así que ni siquiera aparecían como pendientes.

## 3. Errores o comportamientos raros

### 3.1 FALLO: los cobros de un cliente «Comunidad de Propietarios» restan del gasto en Piso, sin aviso
- Fichero: `descargas/Movimientos_cuenta_empresa.xls`, configuración de fábrica, `./ejecutar.sh`.
- Movimientos: `TRANSF. DE COMUNIDAD PROP. SOL FRA 2026-76  +1.774,93`, `... FRA 2026-79 +1.835,12`,
  `... FRA 2026-47 +1.436,45`.
- `app/.venv/bin/python app/reglas.py "TRANSF. DE COMUNIDAD PROP. SOL FRA 2026-76" 1774.93` →
  `Piso  [comunidad prop · base]`.
- Resultado: RESUMEN de fábrica con `Piso` = `-3160.05` (julio) y `-986.45` (agosto); 5.046,50 € de
  facturación metidos como «devolución» de un gasto, y fuera de Ingresos. El Balance total cuadra, pero
  el reparto está mal y la pantalla no dice nada (no sale en «Sin clasificar» porque sí tiene regla).
- Por qué pasa: la base trae `"comunidad prop": "Piso"` sin signo. Para un particular está bien (paga la
  cuota), pero un ingreso de una comunidad casi nunca es devolver la cuota: es un cobro (administrador,
  autónomo que trabaja para comunidades, derrama devuelta...). Sugerencia: `{"-": "Piso"}` en la base, como
  ya se hace con `aeat` y `tgss`.

### 3.2 Comportamiento raro: probar varias reglas con importe en `reglas.py`
- `app/.venv/bin/python app/reglas.py "TRANSF. DE COMUNIDAD PROP..." 1774.93 "DEVOLUCION BRICOMART TICKET" 62.30 "GASOLINERA REPSOL" -60 ...`
- Salida: todos los conceptos con `2.000,00 €` (el último número) y cada número suelto como un concepto más:
  `1774.93   2.000,00 €  ->  Ingresos  [sin regla]`.
- La guía avisa de que el número va «al final», así que no es fallo, pero es lo natural probar
  «concepto importe concepto importe». Preferencia: que acepte pares, o que avise.

### 3.3 Muro de reglas descartadas al quitar categorías de casa
Al dejar solo mis categorías de negocio, `reglas.py` me soltó una lista de unas 200 reglas descartadas
(mercadona, netflix, colegio, veterin...). `ejecutar.sh` lo resume mejor:
`198 reglas de la base descartadas: apuntan a categorías que no tienes en categorias.json.`
Me asustó un poco la primera vez («¿he roto algo?»), pero tiene sentido. Preferencia: que diga que es
normal si has quitado categorías a propósito.

### 3.4 Cosas que fueron bien (sin fallo)
- Detectó el formato (`formato=html`) y que era cuenta (`columna «saldo»`) sin hacer nada.
- Los pagos a Hacienda `AEAT MODELO 130 2T 2026` y `AEAT MODELO 303 2T 2026` fueron solos a **Impuestos**,
  y `DEVOLUCION AEAT IRPF 2025 +612,00` a **Ingresos**. Con `desglosar_ingresos` sale en «Otros
  ingresos», separada de «Facturas cobradas». Objetivo (a) cumplido.
- El impuesto de vehículos (`IMPUESTO VEHICULOS AYTO`) no lo pillaba ninguna regla (salió en «Sin
  clasificar»); con una regla mía fue a Impuestos.
- Segunda ejecución: `49 movimientos ya estaban ... no se cuentan dos veces`. Perfecto.

## 4. Lo que no entendí de la guía / web / mensajes

- La guía no nombra la categoría **Impuestos** en ningún sitio (busqué «impuesto», «autónomo»,
  «trimestre» en el PDF: cero resultados), aunque viene en `categorias.json` de fábrica. Me enteré leyendo
  `rules_base.json`, donde pone que «el impuesto del coche (=dgt) [va] a Transporte». Yo lo quería en
  Impuestos; lo arreglé con una regla, pero la guía no me lo habría dicho.
- La **cuota de autónomos** va a Impuestos. Para mí está bien, aunque mi gestor la considera Seguridad
  Social y no impuesto. Preferencia, no fallo.
- «Una categoría suma 0 € en el resumen: el texto del criterio de la fórmula...». En mi RESUMEN no hay
  fórmulas, son números fijos. No sé a qué fórmula se refiere (supongo que a mi propio Excel).
- `desglosar_ingresos`: me costó entender que la categoría que se llama «Ingresos» pasa a mostrarse como
  «Otros ingresos». Al ver la hoja, lo entendí.
- La guía es de casa (piso, hijos, perros, nómina). Ningún ejemplo para autónomos: cómo separar cobros
  de clientes, qué hacer con el IVA...

## 5. Lo que echo en falta

- **Totales por trimestre.** Es lo que me pide el gestor. RESUMEN va por meses y tuve que sumar yo
  tres filas. Tercer trimestre (julio-septiembre 2026), sacado del RESUMEN:
  - **Total facturado (Facturas cobradas): 4.272,45 + 4.341,54 + 3.770,20 = 12.384,19 €**
  - **Total material: 1.158,58 + 1.284,65 + 1.073,47 = 3.516,70 €** (ya descontada la devolución de Bricomart)
  - Aviso: son cobros por banco, con IVA incluido y por fecha de cobro, no de factura. El gestor lo
    sabrá, pero la herramienta no lo dice en ningún sitio.
- Una fila de total (o de trimestre) al pie del RESUMEN.
- Un ejemplo de `categorias.json` «para autónomo» en la guía.

## Comprobaciones pedidas

- **(c) Devolución Bricomart**: sí resta. `DEVOLUCION BRICOMART TICKET +62,30` → Material
  (regla `bricomart`). Material septiembre = 354,63 + 168,35 + 301,58 + 54,73 + 256,48 − 62,30 =
  **1.073,47 €**, que es lo que pone el RESUMEN. Sin regla, la primera vez caía en Ingresos, pero la
  sugerencia de «Sin clasificar» (`"bricomart"`, 7 mov., 1.844,19 € netos) ya la incluía y lo arregló.
- **(e) Saldo**: `🧮 Cuadra con el banco: 10.812,36 € a 28/09/2026, igual que el extracto.` El Acumulado
  de septiembre en RESUMEN es 10.812,36 y el último saldo del extracto también. Parte de
  `Saldo inicial detectado: 6.200,00 €`. Muy bien explicado.
- **(f) «Cargos que se repiten»**: **me sirve**. Me salen 4: alquiler de la nave (5.400 €/año), cuota de
  autónomos (3.840 €/año), gestoría (726 €/año) y seguro RC (494,40 €/año); `suman 10.460,40 € al año`.
  Es mi coste fijo anual y no lo tenía sumado. Pega pequeña: mete la cuota de autónomos, que no es un
  «cargo» que yo pueda quitar, en la misma suma que el resto. No confunde, pero el total «al año» me
  sonó a «lo que te podrías ahorrar» y no es el caso. Y con 3 meses de datos no puede ver lo trimestral
  (303/130); lo entiendo.

## 6. Valoración: 7/10

Lo bueno: se instala y funciona a la primera, lee el extracto sin tocarlo, cuadra el saldo con el banco
y lo dice claro, no duplica, y los impuestos y la devolución de la renta salen bien de fábrica. Con la
guía pude crear mis categorías de negocio en 10 minutos.

Le quito puntos por: (1) el **fallo** de la Comunidad de Propietarios, que me metía más de 5.000 € de
facturación como «Piso» en negativo sin avisar. Si no llego a mirar, le paso al gestor una cifra mal;
(2) la sugerencia «antonio» para las transferencias, que no sirve para un negocio con varios clientes; y
(3) que no hay trimestres ni guía para autónomos (**preferencias**). Para mi caso de uso es muy
aprovechable, pero hay que revisar la hoja MOVIMIENTOS la primera vez.
