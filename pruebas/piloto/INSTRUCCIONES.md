# Piloto de usuarios simulados

Cinco o más «usuarios» (subagentes de Claude Code) prueban la herramienta como
lo haría alguien que la acaba de descargar: con el ZIP de la release, la web y
sus extractos, **sin ver el código**. Cada uno escribe un informe con el mismo
formato y luego se agrupan por gravedad.

Sirve para encontrar instrucciones confusas, mensajes que no se entienden y
fallos que las pruebas no cubren porque nadie pensó en ese uso. **No sustituye**
a extractos reales (una IA inventa los formatos) ni a probar en Windows.

La ronda 1 (25/09/2026, sobre la 2.12.0) está en `ronda1/` y resumida en
`HALLAZGOS_1.md`: lo que se arregló en la 2.12.1 y lo que se descartó a
propósito. Léelo antes de lanzar otra, para no volver sobre lo mismo.

## Cómo lanzarlo

1. Genera el ZIP de la versión a probar: `app/.venv/bin/python app/exportar.py`.
   `generar.py` coge el `eledger_v*.zip` más nuevo de la raíz.
2. Prepara las carpetas en el **scratchpad** de la sesión (no en el repo):

   ```
   app/.venv/bin/python pruebas/piloto/generar.py <scratchpad>/piloto
   ```

   Cada perfil queda en su carpeta con `eledger/` (la release), `web/` y
   `descargas/`.
3. Lanza un subagente `general-purpose` por perfil, en paralelo y en segundo
   plano, con el texto común de abajo más el bloque de su perfil.
4. Cuando acaben todos, **comprueba en el código** cada fallo grave antes de
   contárselo al usuario: un perfil puede equivocarse o exagerar.
5. Agrupa lo repetido y ordena por gravedad: primero lo que da cifras mal sin
   avisar (el fallo recurrente del proyecto), luego lo que confunde.

Coste: cada perfil gasta unos 75.000–100.000 tokens y tarda unos 4 minutos.

## Texto común para cada perfil

> Vas a hacer de USUARIO SIMULADO de una herramienta de escritorio para dar
> feedback de producto. No eres revisor de código: eres la persona descrita
> abajo, que se ha descargado la herramienta y la usa por primera vez.
>
> **Tu carpeta** (lo único que existe para ti): `<ruta del perfil>`, con
> `eledger/` (el ZIP de la release descomprimido), `web/` (la web en HTML:
> `index.html`, `guia/index.html`, `reglas.html`) y `descargas/` (lo que te
> has bajado del banco).
>
> **Reglas del juego:**
> - NO salgas de tu carpeta ni leas nada del repositorio ni de otros perfiles.
> - NO leas el código fuente (`eledger/app/*.py`) ni `TRASPASO.md` ni
>   `COMPILAR.md`: queremos saber si basta la documentación de usuario. Sí
>   puedes leer LEEME.txt, GUIA.pdf (`pdftotext -layout`), la web, los JSON de
>   `ajustes/`, `app/rules_base.json` y la salida del programa. Para ver o
>   crear Excel, usa openpyxl/pandas con `eledger/app/.venv/bin/python`.
> - Estás en Linux: lanzadores `.sh`. No verás el menú final interactivo.
> - Instalar necesita internet (lo hace `instalar.sh`): permitido.
> - Compórtate como tu persona. Si te atascas, apúntalo y sigue con lo que
>   puedas.
>
> **Al terminar, escribe `informe.md` en tu carpeta**, en español, concreto,
> con citas literales: 1. Perfil y qué intenté. 2. Dónde me atasqué (qué
> esperaba, qué pasó, cita). 3. Errores o comportamientos raros (cómo
> reproducirlos: fichero, comando, salida). 4. Lo que no entendí de la
> guía/web/mensajes. 5. Lo que echo en falta. 6. Valoración de 1 a 10 y por
> qué. Distingue «fallo» de «preferencia». No inventes problemas; si algo fue
> bien, dilo. Tu respuesta final: un resumen de 5-8 líneas del informe.

## Perfiles de la ronda 1 (los que genera hoy `generar.py`)

| Carpeta | Persona | Qué pone a prueba |
|---|---|---|
| `p1_lucia` | 58 años, profesora, no técnica | HTML + XML; recibo de tarjeta sin excluir; cambiar una categoría con la guía |
| `p2_javier` | 34, programador | CSV cp1252 solapado, xlsx real; categorías propias, signo, `null`, etiquetas, orden, desglose, `categoria_manual`, gráficos |
| `p3_marta` | 41, autónoma | dos cuentas del mismo banco con traspasos, facturas, IVA, cuota, Bizum |
| `p4_pedro` | 71, jubilado | CSV sin saldo, pensión el día 1-2, recibos fijos, histórico abierto (crear `.~lock.historico.xlsx#`) |
| `p5_ana` | 27, enfermera | llega por la portada; neobanco en inglés con punto decimal, PDF y fichero vacío, sincronización, exportar |

Los objetivos concretos de cada uno están en la primera sección de su informe
en `ronda1/`.

## Para la ronda 2 (pendiente)

- **Perfiles nuevos**, para que no vayan por caminos ya conocidos: una pareja
  con cuenta conjunta y dos tarjetas; alguien que viene de otra app; un
  estudiante con un único neobanco; un autónomo de verdad (con la categoría
  Impuestos de la 2.12.1); alguien que solo quiere la sincronización con su
  Excel.
- **Repetir Marta y Ana**, con los mismos objetivos, para confirmar que lo
  suyo sigue arreglado (histórico duplicado al declarar cuentas, ingresos sin
  regla, notas de la sincronización).
- **Datos más realistas** en `generar.py`: varias compras al mes en el mismo
  súper con importes y días variados, recibos que cambian de día, devoluciones,
  algún cargo duplicado de verdad (dos cafés iguales el mismo día).
