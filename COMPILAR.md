# Compilar el ejecutable

Para dárselo a alguien que **no ha usado nunca una terminal**. Con el `.exe` no
hay que instalar Python ni saber qué es `pip`: se descomprime una carpeta y se
hace doble clic.

Esto **solo se puede hacer en Windows**. PyInstaller no compila para Windows
desde Mac ni desde Linux; empaqueta el intérprete de la máquina donde se ejecuta.

---

## Cómo se hace

1. `instalar.bat` — crea el entorno y las librerías (si ya lo hiciste, sáltalo).
2. `compilar.bat` — pasa las pruebas, compila y deja `dist\Movimientos.exe`.

Tarda varios minutos y el resultado pesa **60–80 MB**. Es lo que hay: dentro va
el intérprete de Python entero y pandas, que solo, ya son unos 40 MB.

`compilar.bat` **se niega a compilar si alguna prueba falla**. Es a propósito:
un ejecutable que se reparte y falla no se arregla mandando un parche, hay que
volver a mandar 70 MB y explicar por qué.

## Qué repartir

Una carpeta con cuatro ficheros:

```
Movimientos/
├── Movimientos.exe     ← de dist\
├── LEEME.txt
├── GUIA.pdf
└── CHANGELOG.md
```

Comprímela y mándala. Al ejecutar por primera vez, el `.exe` crea `entrada/`,
`salida/`, `datos/` y `ajustes/` **en su propia carpeta**, y rellena `ajustes/`
con las plantillas genéricas.

Los JSON de `ajustes/` quedan fuera del `.exe` a propósito, para que se puedan
abrir con el bloc de notas. Un ejecutable que se lo traga todo dejaría al
usuario sin poder tocar sus propias reglas, que es justo lo que más se toca.

> No metas dentro tu `ajustes/` ni tu `datos/`. Si quieres repartir la versión
> con código en vez del `.exe`, usa `exportar.bat`, que ya se encarga.

## Los antivirus van a quejarse

**Cuéntalo de antemano.** Windows Defender y varios antivirus dan falsos
positivos con los ejecutables de PyInstaller. No es que el programa haga nada
raro: el arranque de PyInstaller —descomprimirse en una carpeta temporal y
ejecutarse desde ahí— se parece a lo que hace cierto malware, y los antivirus
puntúan el patrón, no el contenido.

Es más probable cuanto más nuevo sea el ejecutable, porque nadie lo ha visto
antes. Qué esperar y qué decir:

- **SmartScreen** («Windows protegió tu PC») en la primera ejecución. Se pasa
  con *Más información → Ejecutar de todas formas*. Sale por no estar firmado
  digitalmente, y firmar cuesta dinero y un certificado a nombre de alguien.
- **El antivirus lo pone en cuarentena.** Hay que añadir una excepción para la
  carpeta. Si es el ordenador de la empresa de quien lo recibe, puede que no
  tenga permiso: en ese caso, mejor la vía con Python.
- Si te preocupa antes de mandarlo, súbelo a **virustotal.com** y mira cuántos
  motores lo marcan. Dos o tres de setenta y tantos es lo normal.

El `.spec` desactiva UPX por esto mismo: comprimir el ejecutable reduce el
tamaño pero dispara todavía más detecciones.

## Mantén las dos vías

Conserva la instalación con `instalar.bat`, no la sustituyas por el `.exe`.

Para ti y para cualquier cambio, recompilar cada vez es inviable: son varios
minutos por cada retoque de una regla. Con el entorno normal, `ejecutar.bat`
responde al instante y `probar.bat` también.

El `.exe` es solo para repartir a quien no va a tocar el código.

## Si falla la compilación

| Qué sale | Qué hacer |
|---|---|
| `ModuleNotFoundError` al ejecutar el .exe | Falta una librería que PyInstaller no ha detectado. Añádela a `hiddenimports` en `movimientos.spec` y recompila. |
| El .exe arranca y se cierra al instante | Ejecútalo desde la terminal (`cmd`, arrastra el .exe y pulsa Intro) para ver el error. La ventana se cierra porque se acabó el programa. |
| Se crean las carpetas en un sitio raro | `rutas.py` calcula la raíz desde `sys.executable` cuando está compilado. Si mueves el .exe, se lleva sus carpetas: tiene que estar en la misma carpeta que ellas. |
| Pesa mucho más de 80 MB | Mira `excludes` en el `.spec`. Si el entorno tiene matplotlib o scipy instalados, conviene que estén ahí listados. |
