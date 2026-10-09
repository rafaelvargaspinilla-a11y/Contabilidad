# Activar tus cuentas compartidas

El código está preparado para Supabase. Para activar el acceso compartido necesitas crear tu proyecto y configurar los siguientes pasos. No hay ninguna cuenta financiera alojada en Supabase mientras no lo hagas.

## 1. Crear el proyecto

En [Supabase](https://supabase.com/dashboard), crea un proyecto. Elige una región cercana, por ejemplo una región europea, y conserva la contraseña de la base de datos de forma segura: no la envíes al chat ni la pongas en GitHub.

Consulta las condiciones del plan elegido, incluidos límites, pausas por inactividad y opciones de respaldo. Esta aplicación no contrata ningún servicio automáticamente.

## 2. Preparar la base de datos

Abre **SQL Editor** en tu proyecto y ejecuta el contenido completo de:

[`supabase/migrations/202610090001_accounts.sql`](supabase/migrations/202610090001_accounts.sql).

Se aplica una vez, sobre un proyecto nuevo. Si aparece un error, no borres ni sustituyas tablas existentes: revisa el error antes de continuar. La migración está en una transacción, por lo que una ejecución incompleta no deja la mitad de las tablas creadas.

Se crean las 14 tablas contables, permisos privados y funciones de guardado. Los registros se separan por tu identidad de Supabase; el navegador no puede escribir directamente en las tablas. No desactives Row Level Security ni cambies los permisos para resolver un error de acceso.

## 3. Crear tu acceso

En **Authentication → Users → Add user**, crea tu usuario con correo y contraseña. Usa una contraseña de al menos 8 caracteres, única para esta cuenta. Configura el correo como confirmado si utilizas la creación administrativa de usuario.

La aplicación no ofrece registros públicos. Una vez creado tu usuario, puedes desactivar nuevas altas en la configuración de Auth si solo la vas a usar tú.

En la configuración de URL de Authentication, añade la dirección final de GitHub Pages, incluida la ruta del repositorio y la barra final. Para este repositorio, la dirección prevista sin dominio personalizado es:

`https://rafaelvargaspinilla-a11y.github.io/Contabilidad/`

Verifica la dirección que GitHub muestre en **Settings → Pages**; si utilizas un dominio personalizado, usa su dirección real. Configúrala como **Site URL** y como dirección de redirección permitida.

La recuperación de contraseña depende de que Supabase pueda enviar correo a tu dirección. Comprueba sus ajustes de correo/SMTP y sus restricciones vigentes. La entrega real de esos mensajes no se ha probado en tu proyecto.

## 4. Conectar GitHub Pages

Busca en tu proyecto la **Project URL** y una **publishable key** (`sb_publishable_…`). También se admite la antigua clave pública `anon`. Nunca utilices `service_role`, una clave `sb_secret_…`, la contraseña de PostgreSQL ni un token de administración.

En el repositorio de GitHub, abre **Settings → Secrets and variables → Actions → Variables** y crea estas variables:

| Nombre | Valor |
| --- | --- |
| `SUPABASE_URL` | URL HTTPS del proyecto, sin rutas añadidas. |
| `SUPABASE_PUBLISHABLE_KEY` | Clave publicable o `anon`. |

Estos dos valores están diseñados para aparecer en la web. La privacidad depende del inicio de sesión y de las políticas de la base de datos; una clave administrativa no debe publicarse.

Activa **GitHub Actions** como origen en **Settings → Pages** y ejecuta **Actions → Publicar Mis cuentas → Run workflow**, sobre `main`.

El flujo ejecuta las pruebas y genera la web. La publicación se omite si no están configuradas ambas variables. No interpreta una configuración incompleta como un servicio de sincronización operativo.

Cuando termine, cierra las pestañas anteriores de la app y vuelve a abrirla para activar su nueva versión. Debe aparecer la pantalla **Entrar**. Si ves **Modo local**, todavía estás usando una versión sin la configuración de Supabase.

## 5. Pasar tus cuentas actuales

Antes de cambiar de versión, descarga un respaldo desde la app original de Mac o desde la versión local del navegador. Los archivos originales y la base local anterior no se borran ni se suben automáticamente.

Inicia sesión y ve a **Configuración → Restaurar un respaldo → Mis datos**. Elige el archivo SQLite y confirma. Esa acción sustituye las cuentas compartidas de todos tus dispositivos. Después comprueba saldos, movimientos, retenciones y repartos; conserva el respaldo original.

Inicia sesión con la misma cuenta en el móvil y el ordenador. **Explorar ejemplo** sigue separado y se guarda localmente: la demo no se sube a tus cuentas reales.

## Uso diario

- Los cambios confirmados se guardan en Supabase. La app actualiza los datos al volver a ella, al recuperar la conexión y al pulsar **Actualizar**.
- Si otro dispositivo modificó las cuentas mientras estabas trabajando, el guardado se rechaza con un aviso. Actualiza, revisa y vuelve a introducir la operación; no se sobrescriben automáticamente cambios ajenos.
- Si se pierde la conexión al guardar, pulsa **Actualizar** antes de repetir. El identificador de operación evita duplicados aunque el servidor ya hubiera guardado el cambio.
- Sin conexión puedes consultar una copia previa y descargarla. No se permiten cambios ni restauraciones en las cuentas compartidas. La app indica cuándo se actualizó esa copia; puede estar desactualizada.
- **Cerrar sesión** elimina los tokens y la copia contable de esa sesión en el navegador. También avisa a otras pestañas. La base compartida sigue en Supabase.

## Respaldos

**Descargar respaldo** produce un SQLite compatible con el motor original. Puede descargarse desde la copia local sin conexión; si necesitas el estado más reciente, actualiza primero con Internet.

Supabase conserva una copia previa a la primera modificación de cada día UTC cuando ya existían cuentas compartidas y otra previa a la última restauración. Los botones correspondientes descargan esas copias con conexión. Estas dos copias se reemplazan con el tiempo; no constituyen un historial ilimitado.

**Descargar operación no confirmada** permite conservar el intento que fue rechazado por conflicto o quedó pendiente. Ese archivo no demuestra que el cambio esté guardado en la nube y no debe restaurarse sin comparar primero el estado compartido.

Los respaldos descargados contienen información privada y no están cifrados por la aplicación. Guárdalos de forma segura; no los subas al repositorio.

## Diseño y límites de esta primera integración

El motor Python y SQLite se conserva en el navegador para mantener exactamente los cálculos y el formato de los respaldos. El guardado exporta registros de las 14 tablas y los escribe en tablas PostgreSQL normalizadas, en una única transacción, con una revisión por cuenta. PostgreSQL comprueba propietario, referencias, tipos, importes, porcentajes, categorías y asignaciones.

Es una integración pensada para las cuentas personales actuales. Cada guardado transmite el conjunto completo de registros; no es una sincronización incremental ni una fusión automática de ediciones. Se limita el documento de guardado a 15 MiB. Al crecer el historial habrá que revisar rendimiento y cuotas antes de ampliar el uso.

La interfaz no usa una clave administrativa. La demo permanece local. El service worker solo guarda el programa, no las respuestas de Auth ni de la base de datos. La copia sin conexión pertenece a cada usuario y proyecto.

## Pruebas y desarrollo

Las pruebas de PostgreSQL usan una base temporal independiente, usuarios ficticios y roles equivalentes a los de Supabase. Las de navegador usan PostgreSQL real y un servidor de protocolo Auth de prueba; no sustituyen una comprobación del proyecto alojado, sus políticas de Auth, sus claves y su correo.

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m playwright install chromium
python3 scripts/build_pages.py --local
python3 -m unittest discover -s tests -v
node --test tests/test_import.mjs
python3 tests/browser_smoke.py

# Base exclusivamente de prueba en este ordenador:
docker run -d --name mis-cuentas-postgres -e POSTGRES_HOST_AUTH_METHOD=trust -p 127.0.0.1:55432:5432 postgres:17-alpine
PYTHONPATH=. python3 tests/supabase_sql.py
PYTHONPATH=. python3 tests/supabase_browser.py
docker stop mis-cuentas-postgres
```

En Codex, si se utiliza Chromium del sistema, antepone `CHROMIUM_EXECUTABLE=/usr/bin/chromium` a las pruebas de navegador. No apuntes `MISCUENTAS_TEST_DATABASE_URL` a una base real: el usuario de pruebas crea y elimina bases temporales.

Para construir la web conectada, define `SUPABASE_URL` y `SUPABASE_PUBLISHABLE_KEY` en el entorno y ejecuta `python3 scripts/build_pages.py`. `--local` ignora esas variables expresamente para pruebas. Sin ninguna variable, la construcción también funciona en modo local.
