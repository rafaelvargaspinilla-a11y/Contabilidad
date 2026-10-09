#!/usr/bin/env python3
"""Construye una web estática sin incluir bases, extractos ni credenciales."""
import argparse
import hashlib
import json
import shutil
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.27.7'
RUNTIME = {
    'pyodide.js': 'b4cb23a53aba19c221659b9fb40a2f18281d685691dc06647fb0afd0681baf98',
    'pyodide.asm.js': '6b4c90de5b7172873f04f21884d0e9d2274e305fe32116558fe3e4fbe3618d51',
    'pyodide.asm.wasm': 'a50dd1843f805a0b7c45b61037ee0d7b26dfe85efe0e18ef95a34ad24e401f5f',
    'python_stdlib.zip': '16611534726e5d8ac2bd8f926410b2dcb8d6f49aa24913463533b457a2115c16',
    'pyodide-lock.json': '9c45b916001a750f4102fc287494f3eab215909c7535c626a20db80fd6333e2c',
    'sqlite3-1.0.0-cp312-cp312-pyodide_2024_0_wasm32.whl': '43061928762b03482676a1e11dcef99a003148e59fe914b6a3e41180c382cfc3',
}
ASSETS = ('app.js', 'style.css', 'business-ui.mjs', 'import-utils.mjs', 'transport.mjs',
          'browser-entry.mjs', 'browser-worker.js', 'manifest.webmanifest', 'icon.svg')


def build(output, cache):
    output, cache = output.resolve(), cache.resolve()
    if output == ROOT or ROOT.is_relative_to(output) or output == cache or cache.is_relative_to(output):
        raise ValueError('El directorio de salida no puede contener el proyecto ni la caché.')
    if output.exists() and any(output.iterdir()):
        if not (output / '.generated-by-build-pages').is_file():
            raise ValueError('La salida contiene archivos ajenos; elige un directorio vacío.')
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / '.generated-by-build-pages').touch()
    cache.mkdir(parents=True, exist_ok=True)
    (output / 'runtime').mkdir()
    for name, expected in RUNTIME.items():
        cached = cache / name
        data = cached.read_bytes() if cached.exists() else b''
        if hashlib.sha256(data).hexdigest() != expected:
            url = f'https://cdn.jsdelivr.net/pyodide/v{VERSION}/full/{name}'
            data = urllib.request.urlopen(url, timeout=90).read()
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError(f'La verificación de integridad falló: {name}')
            cached.write_bytes(data)
        (output / 'runtime' / name).write_bytes(data)
    for name in ASSETS:
        shutil.copyfile(ROOT / 'static' / name, output / name)
    (output / 'python').mkdir()
    for name in ('core.py', 'finance.py', 'browser_api.py'):
        shutil.copyfile(ROOT / name, output / 'python' / name)
    html = (ROOT / 'static' / 'index.html').read_text()
    html = html.replace('href="/style.css"', 'href="./style.css"')
    html = html.replace('src="/app.js"', 'src="./browser-entry.mjs"')
    html = html.replace('<title>Mis cuentas · Local</title>', '<title>Mis cuentas</title><meta name="theme-color" content="#142b31"><link rel="manifest" href="./manifest.webmanifest"><link rel="icon" href="./icon.svg">')
    (output / 'index.html').write_text(html)
    (output / '.nojekyll').touch()
    files = sorted(p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file() and not p.name.startswith('.'))
    digest = hashlib.sha256()
    for name in files:
        digest.update(name.encode())
        digest.update((output / name).read_bytes())
    version = digest.hexdigest()[:16]
    urls = ['./'] + ['./' + name for name in files]
    worker = """// Caché del programa; los datos contables permanecen en IndexedDB.
const PREFIX = 'mis-cuentas:' + new URL('.', self.location.href).pathname + ':';
const CACHE = PREFIX + 'VERSION';
const FILES = FILE_LIST;
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(FILES)));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith(PREFIX) && key !== CACHE).map(key => caches.delete(key)))));
});
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin || !url.pathname.startsWith(new URL('.', self.location.href).pathname)) return;
  event.respondWith(caches.open(CACHE).then(async cache => (await cache.match(event.request, {ignoreSearch: true})) || fetch(event.request)));
});
""".replace('VERSION', version).replace('FILE_LIST', json.dumps(urls))
    (output / 'sw.js').write_text(worker)
    print(f'Web estática preparada: {output} ({len(files)} archivos, integridad verificada).')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / 'site')
    parser.add_argument('--runtime-cache', type=Path, default=ROOT / '.runtime-cache')
    args = parser.parse_args()
    build(args.output, args.runtime_cache)
