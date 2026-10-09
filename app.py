#!/usr/bin/env python3
"""Servidor privado en 127.0.0.1. Sin servicios externos ni dependencias."""
import argparse
import json
import os
import secrets
import sys
import tempfile
import threading
import urllib.error
import urllib.request
import webbrowser
from datetime import date, datetime
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from finance import FinanceStore as Store, seed_demo

ROOT = Path(__file__).resolve().parent


def data_directory():
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'MisCuentasLocal'
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'MisCuentasLocal'
    return Path.home() / '.local' / 'share' / 'mis-cuentas-local'


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, addr, data_dir):
        super().__init__(addr, Handler)
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.secret = secrets.token_urlsafe(32)
        self.bootstrap = secrets.token_urlsafe(32)
        self.csrf = secrets.token_urlsafe(32)
        self.origin = f'http://127.0.0.1:{self.server_address[1]}'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # No registrar rutas, conceptos, importes ni tokens.
        pass

    def headers_common(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")

    def host_ok(self):
        return self.headers.get('Host') == f'127.0.0.1:{self.server.server_address[1]}'

    def authenticated(self):
        try:
            cookies = SimpleCookie(self.headers.get('Cookie', ''))
            token = cookies['miscuentas'].value if 'miscuentas' in cookies else ''
            return secrets.compare_digest(token, self.server.secret)
        except Exception:
            return False

    def send_bytes(self, data, typ, code=200, filename=None):
        self.send_response(code)
        self.headers_common()
        self.send_header('Content-Type', typ)
        self.send_header('Content-Length', str(len(data)))
        if filename:
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(data)

    def json(self, data, code=200):
        self.send_bytes(json.dumps(data, ensure_ascii=False).encode(), 'application/json; charset=utf-8', code)

    def store(self, mode):
        if mode not in ('real', 'demo'):
            raise ValueError('Modo inválido.')
        s = Store(self.server.data_dir / ('demo-v02.sqlite3' if mode == 'demo' else 'cuentas.sqlite3'))
        if mode == 'demo':
            seed_demo(s)
        return s

    def do_GET(self):
        if not self.host_ok():
            return self.json({'error': 'Host no permitido.'}, 403)
        url = urlsplit(self.path)
        query = parse_qs(url.query)
        if url.path == '/start':
            if not secrets.compare_digest(query.get('key', [''])[0], self.server.bootstrap):
                return self.json({'error': 'Abre la aplicación desde Abrir.command.'}, 403)
            self.send_response(303)
            self.headers_common()
            self.send_header('Set-Cookie', f'miscuentas={self.server.secret}; HttpOnly; SameSite=Strict; Path=/')
            self.send_header('Location', '/')
            self.end_headers()
            return
        if not self.authenticated():
            return self.send_bytes('Abre la aplicación con Abrir.command para iniciar una sesión local.'.encode(), 'text/plain; charset=utf-8', 401)
        assets = {'/': ('index.html','text/html; charset=utf-8'), '/app.js':('app.js','text/javascript; charset=utf-8'), '/business-ui.mjs':('business-ui.mjs','text/javascript; charset=utf-8'), '/transport.mjs':('transport.mjs','text/javascript; charset=utf-8'), '/import-utils.mjs':('import-utils.mjs','text/javascript; charset=utf-8'), '/style.css':('style.css','text/css; charset=utf-8')}
        if url.path in assets:
            name, typ = assets[url.path]
            return self.send_bytes((ROOT/'static'/name).read_bytes(), typ)
        s = None
        try:
            if url.path == '/api/session':
                return self.json({'csrf': self.server.csrf})
            s = self.store(query.get('mode',['real'])[0])
            if url.path == '/api/state':
                return self.json(s.state(query.get('month',[date.today().strftime('%Y-%m')])[0]))
            if url.path == '/api/export':
                return self.send_bytes(s.export_csv(), 'text/csv; charset=utf-8', filename='movimientos.csv')
            if url.path == '/api/export-activity':
                return self.send_bytes(s.export_activity(), 'text/csv; charset=utf-8', filename='actividad-y-repartos.csv')
            if url.path == '/api/backup':
                with tempfile.TemporaryDirectory() as directory:
                    backup = Path(directory)/'cuentas.sqlite3'
                    s.backup(backup)
                    return self.send_bytes(backup.read_bytes(), 'application/octet-stream', filename='cuentas-respaldo.sqlite3')
            return self.json({'error':'Ruta inexistente.'},404)
        except (ValueError, KeyError) as exc:
            return self.json({'error':str(exc)},400)
        finally:
            if s:
                s.close()

    def do_POST(self):
        if not self.host_ok() or not self.authenticated() or self.headers.get('Origin') != self.server.origin or not secrets.compare_digest(self.headers.get('X-CSRF-Token',''), self.server.csrf):
            return self.json({'error':'Solicitud no autorizada. Abre la aplicación desde su acceso directo.'},403)
        s = None
        try:
            n = int(self.headers.get('Content-Length','0'))
            if n < 1 or n > 12_000_000 or self.headers.get('Content-Type','').split(';')[0] != 'application/json':
                raise ValueError('Formato o tamaño de solicitud no válido.')
            p = json.loads(self.rfile.read(n))
            s = self.store(p.get('mode','real'))
            action = urlsplit(self.path).path
            methods = {'/api/transaction':'transaction', '/api/move':'move', '/api/link':'link_existing',
                       '/api/delete':'delete', '/api/account':'add_account', '/api/category':'add_category',
                       '/api/person':'add_person', '/api/shares':'save_shares', '/api/rule':'add_rule',
                       '/api/remove-rule':'remove_rule', '/api/csv-preview':'preview_csv', '/api/import':'import_rows',
                       '/api/undo-import':'undo_import', '/api/entry':'save_entry', '/api/course':'save_course',
                       '/api/preferences':'save_preferences', '/api/cash':'record_cash', '/api/delete-entry':'delete_entry',
                       '/api/reconcile':'reconcile', '/api/unlink':'unlink', '/api/external-unpaid':'mark_external_unpaid',
                       '/api/settlement':'settle','/api/delete-settlement':'delete_settlement','/api/classify-bank':'classify_bank'}
            if action in methods:
                result = getattr(s, methods[action])(p)
                return self.json({'ok':True,'result':result})
            if action == '/api/ai':
                return self.json({'ok': True, 'result': self.ask_ai(s, p)})
            return self.json({'error':'Ruta inexistente.'},404)
        except (ValueError, KeyError, TypeError) as exc:
            self.json({'error':str(exc)},400)
        except Exception as exc:
            import sqlite3
            if isinstance(exc, sqlite3.IntegrityError):
                self.json({'error':'Ya existe ese nombre o la operación contiene una referencia inválida.'},400)
            else:
                self.json({'error':'No se completó la operación. Los cambios de esa operación no se han guardado.'},500)
        finally:
            if s:
                s.close()

    def ask_ai(self, store, p):
        model = str(p.get('model','qwen3.5:4b')).strip()
        if model not in ('qwen3.5:4b','qwen3.5:9b','qwen3:4b','qwen3:8b'):
            raise ValueError('Elige uno de los modelos locales admitidos.')
        month = p.get('month',date.today().strftime('%Y-%m'))
        state = store.state(month)
        summary = state.get('finance',{}).get('summary',state['summary'])
        question = str(p.get('question','')).strip()[:1500]
        if not question:
            raise ValueError('Escribe una pregunta.')
        prompt = ('Eres un ayudante de análisis de caja. Contesta en español, de forma breve. '
                  'Recibes SOLO totales calculados, todos en CÉNTIMOS de euro. No inventes comercios, causas, '
                  'datos ni previsiones. Si faltan datos dilo. Resultado conjunto elimina pagos vinculados. '
                  'my_income y my_expense son las partes atribuidas al usuario; my_available descuenta sus retenciones. '
                  'All ya suma esas partes y los registros personales sin duplicar transferencias. No des asesoramiento fiscal. '
                  'No realices operaciones. Cita el periodo. DATOS: '+json.dumps({'month':month,'areas':summary},ensure_ascii=False)+
                  '\nPREGUNTA: '+question)
        body = json.dumps({'model':model,'prompt':prompt,'stream':False,'think':False,
                           'options':{'num_ctx':4096,'num_predict':1000,'temperature':0.1}}).encode()
        req = urllib.request.Request('http://127.0.0.1:11434/api/generate', data=body, headers={'Content-Type':'application/json'})
        # Ignorar proxies del sistema: esta solicitud solo debe salir por loopback.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        try:
            with opener.open(req, timeout=120) as response:
                result = json.load(response)
            if result.get('error'):
                raise ValueError('Ollama no pudo ejecutar el modelo local.')
            return result.get('response','Sin respuesta.')
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise ValueError('Falta el modelo local. Descárgalo en Ollama antes de usar el asistente.')
            raise ValueError('Ollama devolvió un error. Comprueba que el modelo esté instalado localmente.')
        except (urllib.error.URLError, TimeoutError):
            raise ValueError('No se pudo obtener respuesta de Ollama en tu Mac. Ábrelo o prueba el modelo 4B.')


def main():
    parser = argparse.ArgumentParser(description='Mis cuentas: aplicación financiera exclusivamente local.')
    parser.add_argument('--data-dir', type=Path, default=data_directory())
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--restore', type=Path, help='Restaurar un respaldo antes de abrir (guarda copia previa).')
    args = parser.parse_args()
    os.umask(0o077)
    args.data_dir.mkdir(parents=True, exist_ok=True)
    if args.restore:
        import sqlite3
        source = sqlite3.connect(f'{args.restore.resolve().as_uri()}?mode=ro', uri=True)
        try:
            if source.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('El respaldo no pasa la comprobación de integridad.')
            source.execute('SELECT id,date,amount FROM transactions LIMIT 1')
            live = args.data_dir/'cuentas.sqlite3'
            if live.exists():
                current = Store(live)
                current.backup(args.data_dir/f'antes-restaurar-{datetime.now():%Y%m%d-%H%M%S}.sqlite3')
                current.close()
            target = sqlite3.connect(live)
            try:
                source.backup(target)
            finally:
                target.close()
        finally:
            source.close()
    live = Store(args.data_dir/'cuentas.sqlite3')
    backup_dir = args.data_dir/'respaldos'
    backup_dir.mkdir(exist_ok=True)
    daily = backup_dir/f'cuentas-{date.today().isoformat()}.sqlite3'
    if not daily.exists():
        live.backup(daily)
    live.close()
    try:
        server = Server(('127.0.0.1',args.port),args.data_dir)
    except OSError:
        server = Server(('127.0.0.1',0),args.data_dir)
    url = f'{server.origin}/start?key={server.bootstrap}'
    print('Mis cuentas está funcionando solo en este ordenador.')
    print('Para cerrar, vuelve a esta ventana y pulsa Control+C.')
    if args.no_browser:
        print(url,flush=True)
    else:
        threading.Timer(0.5,lambda:webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nAplicación cerrada. Tus datos están guardados.')
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
