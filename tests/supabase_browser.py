"""Navegadores contra PostgreSQL real y un servidor de protocolo Auth de prueba.

No sustituye la comprobación del proyecto Supabase y su correo en producción.
"""
import functools
import http.server
import json
import os
import shutil
import sqlite3
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

import psycopg
from playwright.sync_api import sync_playwright
import browser_smoke
from supabase_support import TestDatabase, ACTOR_A, ACTOR_B, ROOT


class CloudHandler(http.server.SimpleHTTPRequestHandler):
    database = None
    tokens = {}
    drop_next_commit_response = False
    refresh_count = 0

    def log_message(self, *args): pass

    def reply(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def actor(self):
        return self.tokens.get(self.headers.get('Authorization', '').removeprefix('Bearer '))

    def session(self, actor):
        token = 'test-access-' + uuid.uuid4().hex
        self.tokens[token] = actor
        return {'access_token': token, 'refresh_token': token, 'expires_in': 3600,
                'user': {'id': actor, 'email': 'a@example.test' if actor == ACTOR_A else 'b@example.test'}}

    def do_GET(self):
        if self.path == '/auth/v1/user':
            actor = self.actor()
            return self.reply(200, {'id': actor, 'email': 'a@example.test'}) if actor else self.reply(401, {'message': 'Invalid token'})
        return super().do_GET()

    def do_PUT(self):
        return self.reply(200, {'id': self.actor()}) if self.actor() else self.reply(401, {})

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
        url = urlsplit(self.path)
        if url.path == '/auth/v1/token':
            if parse_qs(url.query).get('grant_type') == ['refresh_token']:
                type(self).refresh_count += 1
                actor = self.tokens.get(payload.get('refresh_token'))
                return self.reply(200, self.session(actor)) if actor else self.reply(400, {})
            actor = {'a@example.test': ACTOR_A, 'b@example.test': ACTOR_B}.get(payload.get('email'))
            if not actor or payload.get('password') != 'test-password': return self.reply(400, {})
            return self.reply(200, self.session(actor))
        if url.path == '/auth/v1/recover': return self.reply(200, {})
        if url.path == '/auth/v1/logout':
            self.tokens.pop(self.headers.get('Authorization', '').removeprefix('Bearer '), None)
            return self.reply(200, {})
        actor = self.actor()
        if not actor: return self.reply(401, {'message': 'Invalid token'})
        try:
            result = self.database.rpc(actor, url.path.removeprefix('/rest/v1/rpc/'), payload)
            if url.path.endswith('/mc_commit') and type(self).drop_next_commit_response:
                type(self).drop_next_commit_response = False
                self.close_connection = True
                self.connection.shutdown(2)
                self.connection.close()
                return
            return self.reply(200, result)
        except psycopg.Error as error:
            return self.reply(400, {'code': error.sqlstate, 'message': str(error)})


class SupabaseBrowserTests(unittest.TestCase):
    request = browser_smoke.BrowserTests.request
    state = browser_smoke.BrowserTests.state
    add_income = browser_smoke.BrowserTests.add_income
    tearDown = browser_smoke.BrowserTests.tearDown

    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        site = Path(cls.directory.name) / 'Contabilidad'
        shutil.copytree(ROOT / 'site', site)
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(CloudHandler, directory=cls.directory.name))
        cls.url = f'http://127.0.0.1:{cls.server.server_port}/Contabilidad/'
        (site / 'cloud-config.json').write_text(json.dumps({'enabled': True, 'url': cls.url.removesuffix('/Contabilidad/'), 'publishableKey': 'sb_publishable_protocol_test'}))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.playwright = sync_playwright().start()
        options = {'headless': True}
        if os.environ.get('CHROMIUM_EXECUTABLE'): options['executable_path'] = os.environ['CHROMIUM_EXECUTABLE']
        cls.browser = cls.playwright.chromium.launch(**options)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.playwright.stop()
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()
        cls.directory.cleanup()

    def setUp(self):
        self.contexts, self.errors = [], []
        self.db = TestDatabase()
        CloudHandler.database = self.db
        CloudHandler.tokens = {}
        CloudHandler.refresh_count = 0
        self.addCleanup(self.db.close)

    def page(self, width=1280, email='a@example.test'):
        context = self.browser.new_context(viewport={'width': width, 'height': 900})
        self.contexts.append(context)
        page = context.new_page()
        page.on('pageerror', lambda error: self.errors.append(str(error)))
        page.goto(self.url)
        page.locator('#cloud-email').wait_for()
        page.locator('#cloud-email').fill(email)
        page.locator('#cloud-password').fill('test-password')
        page.locator('#cloud-login button[type="submit"]').click()
        page.locator('#content h1').wait_for(timeout=60000)
        return page

    def test_budget_syncs_to_second_device(self):
        desktop = self.page()
        self.add_income(desktop)
        self.request(desktop, '/api/entry', {'mode':'real','area':'academia','kind':'expense','period':'2026-09','date':'2026-09-10','gross_value':'100','description':'Gasto de actividad','method':'shared','my_percent':'17'})
        self.request(desktop, '/api/entry', {'mode':'real','area':'personal','kind':'expense','period':'2026-09','date':'2026-09-10','gross_value':'999','description':'Gasto personal'})
        categories = self.state(desktop)['categories']
        category = next(c['id'] for c in categories if c['area']=='personal' and c['kind']=='expense')
        self.request(desktop, '/api/budget', {'mode':'real', 'month':'2026-10', 'allocations':[{'category_id':category, 'percent':'100'}]})
        mobile = self.page(390)
        budget = self.request(mobile, '/api/state?mode=real&month=2026-10')['budget']['saved']
        self.assertEqual(budget['amount'], 10645)
        self.assertEqual(budget['allocations'][0]['bps'], 10000)

    def test_same_accounts_on_phone_and_computer_and_separate_user(self):
        desktop = self.page()
        self.add_income(desktop)
        mobile = self.page(390)
        self.assertEqual(self.state(mobile)['transactions'][0]['amount'], 12345)
        other = self.page(email='b@example.test')
        self.assertEqual(self.state(other)['transactions'], [])
        self.assertFalse(mobile.evaluate('document.documentElement.scrollWidth>innerWidth'))

    def test_concurrent_device_conflict_requires_refresh(self):
        desktop = self.page()
        self.add_income(desktop, 'Primero', '10')
        mobile = self.page(390)
        self.state(desktop)
        self.add_income(desktop, 'Segundo', '20')
        with self.assertRaisesRegex(Exception, 'otro dispositivo'):
            self.add_income(mobile, 'Tercero', '30')
        self.assertEqual(len(self.state(mobile)['transactions']), 2)
        self.add_income(mobile, 'Tercero', '30')
        self.assertEqual(sum(t['amount'] for t in self.state(desktop)['transactions']), 6000)

    def test_lost_response_retries_same_operation_without_duplicate(self):
        page = self.page()
        CloudHandler.drop_next_commit_response = True
        try: self.add_income(page)
        except Exception: pass
        state = self.state(page)
        self.assertEqual(len(state['transactions']), 1)
        self.assertEqual(self.db.load(ACTOR_A)['revision'], 1)

    def test_offline_consultation_blocks_writes(self):
        page = self.page()
        self.add_income(page)
        self.state(page)
        page.evaluate('async () => { await navigator.serviceWorker.ready; }')
        page.reload()
        page.locator('#content h1').wait_for(timeout=60000)
        page.context.set_offline(True)
        page.reload()
        page.locator('#content h1').wait_for(timeout=60000)
        self.assertEqual(self.state(page)['transactions'][0]['amount'], 12345)
        with self.assertRaisesRegex(Exception, 'Sin conexión'):
            self.add_income(page, 'No debe guardarse', '10')
        self.assertEqual(len(self.db.load(ACTOR_A)['snapshot']['tables']['transactions']), 1)
        self.assertTrue(page.locator('#new-tx').is_disabled())

    def test_restore_syncs_and_backup_remains_sqlite_compatible(self):
        desktop = self.page()
        self.add_income(desktop, 'Anterior', '10')
        snapshot = self.request(desktop, '/api/backup')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'backup.sqlite3'
            path.write_bytes(bytes(snapshot['bytes'].values()) if isinstance(snapshot['bytes'], dict) else bytes(snapshot['bytes']))
            with sqlite3.connect(path) as connection:
                self.assertEqual(connection.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.add_income(desktop, 'Después', '20')
            mobile = self.page(390)
            mobile.locator('[data-page="settings"]').click()
            mobile.locator('#restore-file').set_input_files(path)
            mobile.once('dialog', lambda dialog: dialog.accept())
            mobile.locator('[data-action="restore"]').click()
            mobile.locator('#toast').filter(has_text='Respaldo restaurado').wait_for()
            self.assertEqual(len(self.state(desktop)['transactions']), 1)
            prior = self.db.rpc(ACTOR_A, 'mc_backup', {'p_kind': 'restore'})
            self.assertEqual(len(prior['tables']['transactions']), 2)

    def test_logout_removes_tokens_and_account_cache(self):
        page = self.page()
        self.add_income(page)
        self.state(page)
        page.locator('#cloud-logout').click()
        page.locator('#cloud-email').wait_for()
        self.assertFalse(page.evaluate("Object.keys(localStorage).some(k=>k.startsWith('miscuentas-auth:'))"))
        self.assertTrue(page.locator('.shell').is_hidden())
        cached = page.evaluate("""async () => {
          const names=await indexedDB.databases();
          for(const item of names) {
            if(!item.name.includes('11111111-1111-4111-8111-111111111111'))continue;
            const value=await new Promise(resolve=>{
              const request=indexedDB.open(item.name);
              request.onsuccess=()=>{const db=request.result;const q=db.transaction('files').objectStore('files').get('real');q.onsuccess=()=>{resolve(q.result);db.close();};};
            });
            if(value)return true;
          }
          return false;
        }""")
        self.assertFalse(cached)
        page.locator('#cloud-email').fill('b@example.test')
        page.locator('#cloud-password').fill('test-password')
        page.locator('#cloud-login button[type="submit"]').click()
        page.locator('#content h1').wait_for(timeout=60000)
        self.assertEqual(self.state(page)['transactions'], [])

    def test_expired_session_refreshes_once_across_two_tabs(self):
        first = self.page()
        second = first.context.new_page()
        second.goto(self.url)
        second.locator('#content h1').wait_for(timeout=60000)
        for page in (first, second):
            page.evaluate('const originalNow=Date.now; Date.now=()=>originalNow()+3600*1000')
        first.evaluate('window.refreshingTest=misCuentasBrowser.request("/api/state?month=2026-09");')
        self.state(second)
        first.evaluate('async()=>await window.refreshingTest')
        self.assertEqual(CloudHandler.refresh_count, 1)


if __name__ == '__main__': unittest.main(verbosity=2)
