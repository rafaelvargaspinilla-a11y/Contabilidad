# Mis cuentas local · v0.2

**También hay una versión para navegador, móvil y ordenador: modo local o cuentas compartidas mediante Supabase.** Consulta [README.md](README.md) para abrirla, publicarla en GitHub Pages y trasladar cuentas mediante respaldos. Las instrucciones siguientes corresponden a la versión Python original para escritorio.

Academia, Baile y Personal en una aplicación local. Esta versión añade asignaturas por mes y cuatrimestre, retenciones, reparto por registro y conciliación con el banco. No contiene conexión bancaria, publicidad, analítica ni recursos remotos. Los extractos se procesan en el ordenador donde ejecutas la app. La IA es opcional y llama exclusivamente a tu Ollama en `127.0.0.1:11434`.

## Actualizar desde la versión anterior

1. En la versión anterior, pulsa **Descargar respaldo** y conserva ese archivo.
2. Cierra la aplicación anterior pulsando **Control+C** en su ventana de Terminal.
3. Descomprime el ZIP nuevo en otra carpeta y abre su archivo **Abrir.command**. Conserva todos los archivos de esa carpeta juntos.
4. La app utiliza la misma base local de **Mis datos**; no tienes que copiar ni importar de nuevo tus transacciones. Antes de migrar una base antigua con movimientos, crea además un respaldo `antes-v02-...sqlite3`.
5. Los ingresos/gastos antiguos se mantienen en Banco y aparecen en **Actividad** como **REVISAR REPARTO**. Abre cada uno, confirma área, bruto, retención y porcentaje, y guarda. Hasta confirmarlo, no se incluye en el nuevo resultado económico. No se aplica retroactivamente un porcentaje sin tu revisión.

Los traspasos que ya estaban vinculados se conservan como internos. La antigua estimación de reparto mensual queda guardada en la base y sus respaldos, pero el nuevo resumen utiliza los porcentajes de cada actividad. La demo nueva tiene su propia base, separada de la demo anterior y de tus datos reales.

## Abrir en un Mac M4

Necesitas **Python 3.9 o posterior**. Si la primera versión ya te funcionaba, utiliza el mismo entorno. No necesitas Docker, Node, instalar paquetes de Python ni elegir un binario Intel/ARM de esta app: el código funciona con Python en Apple Silicon.

Si falta Python, puedes obtener el instalador para macOS en [python.org](https://www.python.org/downloads/macos/).

Abre **Abrir.command** con doble clic. Mantén Terminal abierto mientras trabajas. Si el lanzador no se ejecuta, abre Terminal, escribe `cd `, arrastra la carpeta descomprimida, pulsa Enter y ejecuta:

```bash
python3 app.py
```

La dirección habitual es `127.0.0.1:8765`; si ese puerto está ocupado, se elige uno libre. Puede convivir con Actual Budget en el puerto 5007. Se abre automáticamente el navegador con la sesión local: inicia desde el lanzador, no desde un enlace antiguo. Cerrar la pestaña no detiene el servidor; usa **Control+C** en Terminal. No abras dos versiones sobre la misma base a la vez.

## Prueba rápida con datos ficticios

En el selector superior, cambia **Mis datos** por **Explorar ejemplo**. Revisa **Resumen**, **Asignaturas**, **Actividad** y **Liquidaciones**. La demo se crea en el mes de apertura si pertenece a un cuatrimestre; en junio, julio o agosto utiliza septiembre del curso anterior. Puedes cambiar el mes arriba.

La demo inicial contiene estos cálculos:

| Registro | Cálculo de tu parte | Resultado para ti |
| --- | --- | ---: |
| Asignatura propia | 1.000 € brutos − 15 % de retención | 850,00 € |
| Asignatura externa | 1.000 € cobrados; profesor 65 %, academia 35 %; tú 17 % del margen de academia | 59,50 € |
| Gasto general de academia | 100 € × 17 % | −17,00 € |
| **Academia** | Suma de los anteriores | **892,50 €** |
| Evento de baile compartido | 300 € × 50 % | 150,00 € |
| Privada individual | 80 € × 100 % | 80,00 € |
| Sala compartida | 100 € × 50 % | −50,00 € |
| **Baile** | Suma de los anteriores | **180,00 €** |
| Gasto personal | 120 € × 100 % | −120,00 € |
| **Vista conjunta** | Tus partes de las tres áreas | **952,50 €** |

La demo supone que tú has cobrado/pagado todos esos importes. El banco muestra más dinero que tu resultado porque contiene cantidades pendientes de entregar al socio, pareja y profesor. Las liquidaciones registran esas entregas sin crear un segundo gasto.

Vuelve a **Mis datos** para trabajar con tus cuentas. Modificar la demo no modifica tus datos reales.

## Academia

### Asignaturas propias

En **Asignaturas → Nueva asignatura**, indica nombre, año inicial del curso y cuatrimestre:

- Curso 2026–2027, primer cuatrimestre: septiembre–diciembre de 2026.
- Curso 2026–2027, segundo cuatrimestre: enero–mayo de 2027.

Cada cuatrimestre puede tener asignaturas diferentes. Pulsa una celda de la tabla para registrar el ingreso de esa asignatura en ese mes. Introduce el **bruto de tu factura** y la retención que figure en ella. La retención inicial es **15 %**, editable en Configuración y en cada registro. Tu participación en una asignatura propia es siempre **100 %**.

Se conservan bruto, retención y líquido por separado. La retención no se registra como gasto de explotación. «Tu resultado tras retenciones» indica la parte que te corresponde después de esas retenciones; no representa una liquidación fiscal definitiva.

Puedes añadir más de un registro para una asignatura en un mes; la tabla los suma. Si hay varios, la celda abre la actividad del mes para revisarlos.

### Asignaturas de profesores externos

Crea una asignatura con tipo **Profesor externo**. Configura qué porcentaje se lleva el profesor; la academia conserva el resto. El **65 % del profesor es un valor de ejemplo**: ajústalo a vuestro acuerdo antes de introducir los ingresos.

Introduce todo lo cobrado a los alumnos para ese mes. La app calcula, en este orden:

1. Parte del profesor sobre el ingreso total.
2. Margen que conserva la academia.
3. Tu **17 % de ese margen**, o el porcentaje que hayas configurado.

El porcentaje del profesor puede variar por asignatura y por ingreso mensual. **No vuelvas a registrar esa parte como un gasto general**: ya está descontada en el cálculo. Cuando le pagues, utiliza **Liquidaciones → Profesor externo** y selecciona el ingreso asociado. Esta versión permite liquidar al profesor una vez registrado el cobro completo de ese ingreso.

### Gastos generales

En **Actividad → Nuevo registro**, elige Academia, gasto y **General compartido**. Introduce el gasto completo; por defecto te atribuye el **17 %**. Un gasto exclusivo tuyo puede marcarse como **Individual**, al 100 %.

Los porcentajes de Configuración se aplican a los nuevos registros. Cada registro conserva sus porcentajes históricos. Cambiar el acuerdo de una asignatura o el porcentaje general no recalcula meses anteriores.

## Baile

Categorías de ingresos disponibles: **Clases presenciales, Productos online, Clases privadas y Eventos**, además de las categorías previas y las que quieras crear en Configuración.

Tanto los ingresos como los gastos admiten:

- **Individual**: 100 % para ti.
- **Compartido**: 50 % por defecto para ti y 50 % para tu pareja; puedes editar el porcentaje del registro.

Indica quién cobra o paga el importe completo: **Yo / cuenta que gestiono** o **Socio / pareja**. Esto permite calcular el saldo de reparto entre vosotros. En un registro de 300 € al 50 %, si cobras tú, quedan 150 € pendientes de entregar; si cobra tu pareja, quedan 150 € pendientes de recibir.

## Actividad y banco: cómo evitar duplicados

**Actividad** recoge el mes al que corresponde cada ingreso o gasto y calcula tu parte. **Banco** recoge el dinero real que entra o sale de las cuentas. La cuenta y el área son independientes: puedes pagar un gasto de Academia desde una cuenta Personal.

Al crear una actividad:

- **Pendiente**: guarda el ingreso/gasto sin inventar un movimiento bancario. Úsalo si todavía no se ha cobrado o si vas a importar el extracto después.
- **Ya cobrado / pagado completo**: si pagas/cobras tú, añade un movimiento a la cuenta seleccionada. Si lo hace tu socio o pareja, registra ese cobro/pago sin mover tus cuentas.

En **Actividad**, los botones **Cobrar/Pagar** admiten importes parciales y su fecha efectiva. Si el dinero ya está importado, no utilices esos botones: ve a **Banco → Conciliar** y vincula el movimiento existente.

Ejemplo: anota una factura de 1.000 € brutos con 15 % de retención como pendiente. Al importar los 850 € del banco, vincúlalos a esa factura. Quedará cobrada y el ingreso solo contará una vez.

Un movimiento bancario puede repartirse entre varias actividades pendientes, y una actividad puede cobrarse con varios movimientos. Al conciliar se sustituye la actividad automática procedente del banco. La app rechaza asignaciones superiores al movimiento o al importe pendiente; si alguna parte falla, no guarda esa operación a medias.

Editar el bruto o la retención no altera el importe real del banco. Si corriges el sentido o quién cobró un registro ya vinculado, desvincúlalo primero. Puedes corregir una entrada importada como ingreso a **Gasto / devolución**, manteniendo el mismo signo positivo.

## Importar un extracto

1. Exporta un **CSV** del banco. También se admiten TSV/TXT. Si tienes XLSX, guárdalo como CSV UTF-8 desde Excel o Numbers. No hay lectura directa de XLSX/PDF.
2. En **Importar extracto**, selecciona el archivo y pulsa **Leer columnas**. Ajusta codificación, separador o filas iniciales si hace falta, y vuelve a leer las columnas.
3. Relaciona fecha, concepto e importe. Si usas entradas/salidas separadas, deja la columna de importe con signo sin usar.
4. Elige la cuenta real y un área inicial. Se admiten **año-mes-día**, como `2026-09-23`, y fechas con hora, como `2026-09-23 10:30:00` o `2026-09-23T10:30:00Z`. Las fechas ISO se reconocen también con las opciones día/mes/año o mes/día/año. Se conserva el día escrito en el extracto, sin desplazarlo por la zona horaria.
5. Previsualiza. En cada fila puedes cambiar **Academia / Baile / Personal, categoría, reparto, porcentaje y asignatura** antes de guardar. Cambiar el área conserva la cuenta y el importe, y elimina una categoría incompatible.
6. Elige **Crear actividad**, **Solo banco / pendiente de vincular** o **Vincular** a una actividad pendiente. Para repartir una fila entre varias actividades, impórtala como Solo banco y usa Conciliar después.
7. Revisa fechas, signos y posibles duplicados. Se desmarcan las coincidencias detectadas. Un ID bancario estable mejora la detección; fecha, importe y concepto son una comprobación orientativa, no infalible.
8. Importa y compara el saldo con tu extracto.

**El banco contiene el líquido, no necesariamente el bruto de la factura.** Una actividad nueva creada desde un CSV empieza con retención cero; la app no deduce una retención desconocida. Si existe retención, vincula el cobro a tu factura pendiente o completa el bruto y la retención después en Actividad.

Las reglas de Configuración asignan categorías por texto del concepto y área. No se usa IA para clasificar automáticamente. Tras cambiar un área en la previsualización se buscan las reglas de esa nueva área.

Puedes deshacer un lote desde Importar extracto. Se anulan sus movimientos y las actividades automáticas sin otros vínculos. Las actividades que creaste por separado se conservan y quedan pendientes de cobro/pago. Si un lote tiene traspasos internos vinculados, anúlalos primero para no dejar una sola mitad.

`ejemplos/mixto-iso.csv` contiene tres movimientos ficticios de septiembre de 2026: asigna la plataforma a Academia compartida al 17 %, el evento a Baile compartido al 50 % y el supermercado a Personal. Sobre una base vacía, tu resultado será **113 €** y el cambio bancario **180 €**. Los otros CSV incluidos son ejemplos de la versión anterior; sus repartos se deben revisar.

## Lo que recibes en Personal y las liquidaciones

En Resumen, **Dinero recibido en Personal** muestra los pagos internos registrados desde Academia y Baile. Esa recepción no se vuelve a sumar a tu resultado: tu parte de la actividad ya está calculada.

- Si todavía no está registrado el pago entre tus cuentas, ve a **Banco → Pago interno**. Se crean las dos mitades juntas.
- Si importaste ambas mitades, selecciónalas en **Vista conjunta → Banco → Vincular 2 seleccionados**. Deben tener la misma fecha, importes opuestos y cuentas distintas. Si las fechas no coinciden, déjalas como Solo banco para revisarlas; no crees otro pago encima.
- Para entregar/recibir dinero a tu socio o pareja utiliza **Liquidaciones**. Puedes crear un movimiento nuevo o utilizar uno ya importado cuyo signo e importe coincidan.
- Para pagar la parte calculada del profesor externo, utiliza una liquidación de profesorado asociada a la asignatura. Si el socio cobró a los alumnos y tú pagaste al profesor, el saldo con el socio se ajusta también.

El saldo de reparto es acumulado hasta el cierre del mes según los cobros, pagos y liquidaciones registrados. No crea deudas jurídicas ni órdenes de pago: es una herramienta de seguimiento. Los pendientes de Actividad muestran su situación actual, incluso si se cobraron en un mes posterior.

Anular una actividad conserva su banco y lo deja sin asignar. Anular una liquidación también anula su movimiento bancario asociado; el diálogo avisa antes de hacerlo.

## Tus datos, copias y restauración

La base real en macOS está en:

```text
~/Library/Application Support/MisCuentasLocal/cuentas.sqlite3
```

La demo nueva está en `demo-v02.sqlite3`. Las copias al iniciar están en `respaldos`. **Descargar respaldo** incluye movimientos, actividad, asignaturas, porcentajes, categorías, reglas y liquidaciones. Los CSV de exportación son para consultar, no sustituyen al respaldo completo.

Guarda las exportaciones en una carpeta local si no quieres sincronizarlas. La app no cifra la base ni las copias; el cifrado del disco y de las unidades de respaldo depende de tu configuración. Escucha solo en loopback y exige sesión, origen local y token para escribir.

Para restaurar, cierra la app y ejecuta desde su carpeta:

```bash
python3 app.py --restore "/ruta/a/cuentas-respaldo.sqlite3"
```

Se valida el archivo y se guarda una copia previa antes de reemplazar **Mis datos**. Una copia en el mismo disco no protege frente a la pérdida del equipo; conserva también un respaldo independiente.

## IA local opcional

La aplicación funciona sin IA. El asistente explica los totales calculados del mes y no modifica registros.

Si ya tienes Ollama local, abre **Asistente local** y selecciona un modelo instalado compatible. Como punto de partida para tu M4 con 16 GB se incluye `qwen3.5:4b`; no se ha medido su rendimiento en tu equipo. El modelo se instala por separado, por ejemplo:

```bash
ollama pull qwen3.5:4b
```

La app solo llama a `127.0.0.1:11434`, ignora proxies y no admite nombres de modelos cloud. Envía totales y tu pregunta, sin extractos, conceptos, cuentas ni nombres de personas. Ollama es un programa independiente: configura también sus funciones de nube según la [documentación oficial](https://docs.ollama.com/faq). Descarga para Mac: [ollama.com](https://ollama.com/download/mac).

## Comprobaciones y límites

Se han comprobado **37 pruebas de Python y 3 de JavaScript**, incluidos cálculos, retenciones, fechas ISO, importación mixta, conciliación, anulaciones, migración, copias y rutas HTTP. También se verifica la sintaxis del JavaScript y del lanzador. Las pruebas usan datos ficticios y una respuesta simulada de Ollama.

No se ha podido completar la prueba visual: el navegador de pruebas bloquea el acceso al servidor local. Tampoco se ha probado en un Mac físico ni con tus extractos reales o un modelo de IA ejecutándose. La app no está firmada/notarizada como aplicación nativa de macOS.

- Moneda de trabajo: euros; utiliza importes liquidados en euros.
- Los importes se guardan en céntimos y los repartos se redondean por registro; el resto queda en la otra parte para conservar el total.
- No calcula IVA, declaraciones, amortizaciones, facturas legales ni nóminas. Registra los importes y retenciones de tus documentos; la app no decide qué tipo te corresponde.
- Un registro externo corresponde a un profesor y un registro compartido a una contraparte. Si hay varios, sepáralos en registros.
- No hay conexión bancaria, sincronización entre equipos ni aplicación móvil.

Para repetir las pruebas o abrir una base aislada:

```bash
python3 -m unittest discover -s tests -v
# Solo para desarrollo, si tienes Node; no hace falta para usar la app:
node --test tests/test_import.mjs
# Base de prueba independiente:
python3 app.py --data-dir ./datos-prueba
```
