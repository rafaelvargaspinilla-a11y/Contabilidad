# Mis cuentas

Academia, Baile y Personal desde el móvil y el ordenador. La versión web funciona en el navegador: **cada dispositivo conserva sus propias cuentas**, sin servidor de datos ni sincronización automática. El código se publica en GitHub Pages; tus cuentas y extractos no se suben a GitHub.

## Abrir en el móvil o el ordenador

Cuando GitHub Pages esté publicado, abre la dirección que aparece en **Settings → Pages** del repositorio. Usa un navegador actualizado: Safari, Chrome, Edge o Firefox. Puedes añadir la página a la pantalla de inicio desde el menú del navegador. La primera apertura descarga el programa y puede tardar; las siguientes reutilizan la caché. Después de que termine de preparar la caché, también puedes abrirla sin conexión.

Se guardan los cambios en este navegador, dentro de este dispositivo. La app no tiene cuentas de usuario ni contraseña porque no hay una base de datos compartida en Internet. Cualquier persona con acceso a ese navegador puede acceder a las cuentas guardadas: protege el dispositivo.

**Descarga respaldos regularmente.** Borrar los datos del sitio, cambiar de navegador, usar navegación privada o perder el dispositivo puede hacer que pierdas las cuentas. El almacenamiento del navegador y las copias automáticas no sustituyen un respaldo descargado. El navegador puede tratar la app añadida a inicio como un almacenamiento distinto.

## Llevar tus cuentas a otro dispositivo

1. En el dispositivo de origen, abre **Configuración → Descargar respaldo**.
2. Traslada el archivo `.sqlite3` al otro dispositivo por el medio que prefieras.
3. Abre la app allí y ve a **Configuración → Restaurar un respaldo**.
4. Elige el archivo, pulsa **Restaurar respaldo** y confirma.

Restaurar sustituye la base seleccionada (**Mis datos** o **Explorar ejemplo**); no fusiona movimientos. Se conserva una copia del estado anterior, descargable desde **Copia anterior a restaurar**. Solo la última copia previa se conserva. También hay una copia automática del estado previo a la primera operación del día; su botón descarga la última disponible.

Los respaldos son compatibles con la versión original para Mac. Para migrar desde ella, descarga primero su respaldo y restáuralo en la web. Ollama sigue disponible en la versión Python local; la versión web no incluye ese asistente.

## Publicar con GitHub Pages

La configuración de publicación está en `.github/workflows/pages.yml`.

1. En GitHub, abre **Settings → Pages → Build and deployment** y elige **GitHub Actions** como origen.
2. En **Actions → Publicar Mis cuentas**, ejecuta **Run workflow** sobre `main`, si el último envío no la publicó todavía.
3. Espera a que las tareas pasen y abre la dirección que aparece en Pages.

Los cambios posteriores enviados a `main` se comprueban y publican automáticamente. No se necesita un servidor contratado ni un dominio propio. La disponibilidad gratuita de Pages depende del plan y de la visibilidad del repositorio; no hagas público un repositorio privado sin revisarlo. La web distribuida contiene el programa, nunca tu base financiera.

## Desarrollo en Codex

Python 3.12 y Node para las pruebas. No hay dependencias externas para ejecutar la versión Python local.

```bash
python3 -m unittest discover -s tests -v
node --test tests/test_import.mjs
python3 scripts/build_pages.py
python3 -m http.server 8080 --directory site --bind 127.0.0.1
```

El constructor descarga una versión fijada de Pyodide y SQLite, verifica SHA-256 y prepara solo los archivos del programa en `site/`. No abras `index.html` con `file://`: los workers y el almacenamiento necesitan HTTP local o HTTPS.

Para comprobar la versión web con un navegador real:

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m playwright install chromium
python3 tests/browser_smoke.py
```

Si ya tienes Chromium instalado, puedes usar `CHROMIUM_EXECUTABLE=/usr/bin/chromium python3 tests/browser_smoke.py`.

La versión original de escritorio se conserva:

```bash
python3 app.py --data-dir /workspace/mis-cuentas-dev-data --no-browser
```

Consulta [LEEME.md](LEEME.md) para el funcionamiento contable y [Abrir.command](Abrir.command) para abrir la versión local en macOS. Los CSV en `ejemplos/` contienen datos ficticios. No subas extractos reales, bases, respaldos ni contraseñas al repositorio.
