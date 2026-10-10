# Mis cuentas

Academia, Baile y Personal desde el móvil y el ordenador.

La versión web admite **una cuenta privada de Supabase para compartir las mismas cuentas entre dispositivos**. El inicio de sesión y el guardado necesitan un proyecto configurado; consulta [SUPABASE.md](SUPABASE.md) para activarlo.

Sin configuración de Supabase, la app conserva el modo local: cada navegador guarda sus propios datos. La pantalla indica claramente ese modo. La versión Python original para escritorio también se conserva y sigue siendo local.

## Con Supabase

- Inicia sesión con la misma cuenta en el móvil y el ordenador.
- Los cambios se confirman en Supabase y se consultan al actualizar o volver a la app.
- Si otro dispositivo cambió las cuentas, la app avisa antes de sobrescribirlas.
- Sin conexión puedes consultar una copia anterior, pero no guardar cambios.
- Descarga respaldos regularmente. Restaurar sustituye las cuentas compartidas de todos los dispositivos.
- La demo permanece local y separada de tus cuentas.

Para configurar proyecto, usuario, permisos y publicación sigue [Activar tus cuentas compartidas](SUPABASE.md). La integración no crea proyectos ni contrata servicios automáticamente.

## Publicación y datos actuales

La web se publica con `.github/workflows/pages.yml`. Se necesitan las variables públicas `SUPABASE_URL` y `SUPABASE_PUBLISHABLE_KEY` en GitHub y GitHub Actions como origen de Pages. La publicación se omite si faltan esas variables.

Antes de activar la nube, descarga un respaldo de la versión local. Después inicia sesión y restáuralo desde Configuración; conserva el original y comprueba los saldos. Los datos previos no se borran ni se suben automáticamente.

Puedes añadir la web a la pantalla de inicio del móvil. Usa un navegador actualizado. Tras publicar una nueva versión, cierra sus pestañas anteriores y vuelve a abrirla para activar la actualización.

## Desarrollo en Codex

Python 3.12, Node y Chromium/Playwright para las pruebas. La versión Python local no requiere dependencias externas.

```bash
python3 -m unittest discover -s tests -v
node --test tests/test_import.mjs
python3 scripts/build_pages.py --local
python3 -m http.server 8080 --directory site --bind 127.0.0.1
```

El constructor descarga Pyodide y SQLite fijados, verifica SHA-256 y copia solo los archivos del programa a `site/`. No abras la web con `file://`: necesita HTTP local o HTTPS.

Para las pruebas de navegador:

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m playwright install chromium
python3 tests/browser_smoke.py
```

En Codex puedes usar `CHROMIUM_EXECUTABLE=/usr/bin/chromium python3 tests/browser_smoke.py`. Las pruebas de PostgreSQL y sincronización están documentadas en [SUPABASE.md](SUPABASE.md).

Para la versión original Python usa datos aislados:

```bash
python3 app.py --data-dir /workspace/mis-cuentas-dev-data --no-browser
```

Consulta [LEEME.md](LEEME.md) para el funcionamiento contable y [Abrir.command](Abrir.command) para la versión local en macOS. Para compartir cuentas desde el ordenador, utiliza la versión web con Supabase.

Los CSV de `ejemplos/` son ficticios. No subas extractos reales, bases SQLite, respaldos, contraseñas ni claves administrativas al repositorio.

### Presupuesto mensual

En **Presupuesto**, elige el mes que vas a presupuestar. La base es tu parte de los ingresos cobrados el mes anterior, después de retenciones, sin restar gastos de actividad ni personales. Los cobros pendientes y los traspasos internos no se suman. Los registros antiguos pendientes de revisar su reparto tampoco se incluyen hasta confirmarlos en Actividad.

Añade categorías de gasto Personal (o crea otras), reparte sus porcentajes y pulsa **Guardar presupuesto**. Puedes dejar dinero sin asignar, pero no superar el 100 % ni repetir categorías. La cantidad inicial queda fijada al primer guardado; después puedes editar los porcentajes. La tabla compara el presupuesto guardado con los gastos personales del mes de actividad y muestra disponible o exceso. Las categorías sin presupuesto se indican aparte.

El presupuesto se comparte mediante Supabase y se incluye en los respaldos existentes. Esta actualización no requiere ejecutar otro SQL. Banco y Liquidaciones se han ocultado, junto con los saldos bancarios y pendientes del resumen; los registros históricos se conservan.
