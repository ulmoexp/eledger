# Ronda 3 del piloto (25/09/2026, sobre la 2.14.0)

Solo los tres perfiles que encontraron fallos graves en la ronda 2, para
confirmar los arreglos y probar lo nuevo: la pareja (8,5), Raúl, que viene de
otra app (8), y Carmen, que solo quiere la sincronización (8,5). En la ronda 2
habían puesto 7, 6 y 5. Informes completos en `ronda3/`.

Ningún perfil encontró cifras mal sin avisar ni datos perdidos.

## Confirmado que funciona

- **Pareja:** avisa de las dos tarjetas sin declarar («faltan 5,20 €»); una
  vez declaradas salen los cuatro cafés, propone `"liquidacion tarjeta"` y la
  hoja CUENTAS cuadra con RESUMEN y con el CSV.
- **Raúl:** Cargo/Abono se leen tal cual y el saldo cuadra. Sus categorías
  entran con `importar_categorias`, también en lo que ya estaba en el
  histórico, y una corrección manual posterior se respeta. Las etiquetas
  repetidas avisan y se ignoran.
- **Carmen:** el modo «añadir» deja intactas sus filas de junio y sus
  fórmulas, reconoce las filas tecleadas con otras mayúsculas, respeta su
  cambio de categoría y su nota, no toca el fichero sin nada nuevo y se niega
  con el fichero abierto. «Sí dejaría de copiar y pegar».

## Arreglado después de la ronda (sigue siendo 2.14.0)

| Qué | Quién |
|---|---|
| Sin declarar las tarjetas, el aviso del recibo decía «no encuentro una clave segura» sin decir que la causa eran los cargos fundidos. Ahora remite a `cuentas.json`, y la línea de «ya estaban» avisa de que algunos pueden ser de dos tarjetas | pareja |
| `movimientos_limpios.xlsx` lleva la columna `cuenta` (detrás de A-G) | pareja |
| «Ninguna regla la asigna: su columna saldrá a 0» salía para una categoría que llegaba por `importar_categorias`. Ahora cuenta lo que se traduce y, si hay importación, no lo da por seguro | Raúl |
| Una etiqueta que solo se diferencia en mayúsculas o espacios («facturas ») no contaba como repetida | Raúl |
| Juntar Luz/Agua y Fibra/movil en Facturas descartaba 31 reglas de la base. Ahora `equivalencias` (en `categorias.json`) lleva esas reglas a la categoría nueva | Raúl |
| Clave `"digi "` en la base: el espacio se perdía al normalizar y casaba con «DIGITAL». Ahora es `=digi` | Raúl |
| Saldo inicial negativo sin explicación: se dice por qué suele pasar | Raúl |
| El aviso de «categorías sin traducir» no decía que lo ya importado se queda en categoria_manual | Raúl |
| Modo añadir: las filas nuevas copian el formato de la anterior, y se avisa de categorías que la hoja no usaba (Higiene, Fibra/movil) | Carmen |
| Se hacía una copia de `historico.xlsx` en cada ejecución aunque no hubiera nada nuevo: ahora solo si cambia | Carmen |
| «1 añadidos debajo» | Carmen |
| La guía: «la primera vez, sobre una copia», y cómo quedan las notas en modo añadir | Carmen |
| LEEME: `cuentas.json` también para una tarjeta cada miembro de la pareja | pareja |

## Hecho en la web

- La portada tiene una tarjeta «¿Vienes de otra app?» (Raúl), y la guía web
  explica `importar_categorias` y `equivalencias`.

## Sin tocar, a propósito

- **`entrada/` no viene en el ZIP**: ya descartado en la ronda 1.
- **«Fuera del balance» cuesta entenderlo a primera vista** (pareja): la guía
  lo explica en «Cómo se calcula el resumen». Preferencia, no fallo.
