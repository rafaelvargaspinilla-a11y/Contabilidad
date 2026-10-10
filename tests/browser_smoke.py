"""Pruebas reales de la web estática en una ruta como la de GitHub Pages."""
import functools
import http.server
import json
import os
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (ROOT / 'site' / 'index.html').exists():
            raise RuntimeError('Ejecuta primero python3 scripts/build_pages.py')
        cls.directory = tempfile.TemporaryDirectory()
        Path(cls.directory.name, 'Contabilidad').symlink_to(ROOT / 'site', target_is_directory=True)
        cls.server = http.server.ThreadingHTTPServer(
            ('127.0.0.1', 0), functools.partial(QuietHandler, directory=cls.directory.name))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}/Contabilidad/'
        cls.playwright = sync_playwright().start()
        options = {'headless': True}
        if os.environ.get('CHROMIUM_EXECUTABLE'):
            options['executable_path'] = os.environ['CHROMIUM_EXECUTABLE']
        cls.browser = cls.playwright.chromium.launch(**options)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.directory.cleanup()

    def setUp(self):
        self.contexts = []
        self.errors = []

    def tearDown(self):
        for context in self.contexts:
            context.close()
        self.assertEqual(self.errors, [])

    def page(self, width=1280, context=None):
        if context is None:
            context = self.browser.new_context(viewport={'width': width, 'height': 900})
            self.contexts.append(context)
        page = context.new_page()
        page.on('pageerror', lambda error: self.errors.append(str(error)))
        page.goto(self.url)
        page.locator('h1').wait_for(timeout=60000)
        return page

    def request(self, page, path, payload=None):
        return page.evaluate('async ([path,payload]) => misCuentasBrowser.request(path,payload)', [path, payload])

    def add_income(self, page, description='Ingreso de prueba', value='123,45'):
        return self.request(page, '/api/transaction', {
            'mode': 'real', 'date': '2026-09-10', 'account_id': 'personal',
            'area': 'personal', 'kind': 'income', 'value': value, 'description': description})

    def state(self, page, mode='real'):
        return self.request(page, f'/api/state?mode={mode}&month=2026-09')

    def test_budget_ui_month_names_and_saved_comparison(self):
        page = self.page(390)
        self.add_income(page, value='1000')
        page.locator('#month').select_option('2026-10')
        page.locator('[data-page="budget"]').click()
        page.locator('[data-action="budget-add"]').click()
        category = self.state(page)['categories']
        category = next(c['id'] for c in category if c['area']=='personal' and c['kind']=='expense')
        page.locator('[data-budget-category="0"]').select_option(category)
        page.locator('[data-budget-percent="0"]').fill('100')
        page.locator('#budget-form button[type="submit"]').click()
        page.get_by_role('heading', name='Presupuesto frente a gasto real').wait_for()
        self.assertIn('1000,00', page.locator('#content').inner_text())
        self.assertEqual(page.locator('[data-page="transactions"],[data-page="settlements"]').count(), 0)
        self.assertIn('Octubre', page.locator('#month option:checked').inner_text())
        page.reload()
        page.locator('h1').wait_for(timeout=60000)
        self.assertEqual(self.request(page, '/api/state?mode=real&month=2026-10')['budget']['saved']['amount'], 100000)
        self.assertFalse(page.evaluate('document.documentElement.scrollWidth > innerWidth'))

    def test_simple_activity_form_defaults_and_summary(self):
        page = self.page(390)
        page.locator('#month').select_option('2026-09')
        page.locator('#new-tx').click()
        self.assertEqual(page.locator('dialog [name="holder"],dialog [name="cash_status"],dialog [name="account_id"]').count(), 0)
        self.assertFalse(page.locator('#act-method').is_visible())
        self.assertFalse(page.locator('dialog [name="description"]').evaluate('(el)=>el.required'))
        page.locator('#act-area').select_option('baile')
        page.locator('#act-kind').select_option('income')
        page.locator('#act-gross').fill('100')
        page.locator('dialog button[type="submit"]').click()
        page.wait_for_function('!document.querySelector("dialog").open')
        entry = self.state(page)['finance']['entries'][0]
        self.assertEqual((entry['description'],entry['my_bps'],entry['paid'],entry['pending']), ('Ingreso de Baile',5000,10000,0))
        self.assertEqual(self.state(page)['transactions'][0]['account_id'], 'baile')
        page.locator('[data-area="personal"]').click()
        self.assertEqual(page.get_by_role('heading', name='El detalle del mes').count(),0)
        page.locator('[data-area="all"]').click()
        self.assertEqual(page.get_by_role('heading', name='El detalle del mes').count(),1)
        self.assertEqual(page.locator('#content [data-action="export-activity"],#content [data-action="backup"]').count(),0)
        self.assertFalse(page.evaluate('document.documentElement.scrollWidth > innerWidth'))

    def test_external_course_is_selected_without_manual_method(self):
        page = self.page()
        course = self.request(page, '/api/course', {'mode':'real','name':'Externa','year':2026,'semester':1,'ownership':'external','teacher_percent':'60'})['result']
        page.locator('#month').select_option('2026-09')
        page.locator('#new-tx').click()
        page.locator('#act-area').select_option('academia')
        page.locator('#act-kind').select_option('income')
        page.locator('#act-course').select_option(course)
        page.locator('#act-gross').fill('1000')
        page.locator('dialog button[type="submit"]').click()
        page.wait_for_function('!document.querySelector("dialog").open')
        entry = self.state(page)['finance']['entries'][0]
        self.assertEqual((entry['method'],entry['teacher_bps'],entry['my_income'],entry['paid']), ('external',6000,6800,100000))
        page.locator('[data-page="activity"]').click()
        page.locator('[data-action="edit-entry"]').click()
        page.locator('dialog [name="description"]').fill('Nombre corregido')
        page.locator('dialog button[type="submit"]').click()
        page.wait_for_function('!document.querySelector("dialog").open')
        entry = self.state(page)['finance']['entries'][0]
        self.assertEqual((entry['teacher_bps'],entry['my_income'],entry['paid']), (6000,6800,100000))

    def test_mobile_navigation_form_and_layout(self):
        page = self.page(390)
        for width in (320, 390, 768, 1280):
            page.set_viewport_size({'width': width, 'height': 900})
            self.assertFalse(page.evaluate('document.documentElement.scrollWidth > innerWidth'), width)
        page.set_viewport_size({'width': 390, 'height': 844})
        page.locator('[data-page="courses"]').click()
        page.locator('[data-action="new-course"]').click()
        page.locator('dialog input[name="name"]').fill('Álgebra móvil')
        page.locator('dialog input[name="year"]').fill('2026')
        page.locator('dialog select[name="semester"]').select_option('1')
        page.locator('dialog button[type="submit"]').click()
        page.wait_for_function('!document.querySelector("dialog").open')
        self.assertTrue(any(c['name'] == 'Álgebra móvil' for c in self.state(page)['finance']['courses']))
        page.reload()
        page.locator('h1').wait_for(timeout=60000)
        self.assertTrue(any(c['name'] == 'Álgebra móvil' for c in self.state(page)['finance']['courses']))
        self.assertEqual(page.locator('[data-page="ai"]').count(), 0)

    def test_accounting_csv_persistence_and_demo_isolation(self):
        page = self.page()
        course = self.request(page, '/api/course', {'mode': 'real', 'name': 'Estadística',
            'year': 2026, 'semester': 1, 'ownership': 'own'})['result']
        entry = self.request(page, '/api/entry', {'mode': 'real', 'date': '2026-09-10',
            'period': '2026-09', 'area': 'academia', 'kind': 'income', 'course_id': course,
            'gross_value': '1000', 'tax_percent': '15'})['result']
        preview = self.request(page, '/api/csv-preview', {'mode': 'real',
            'text': 'Fecha;Concepto;Importe\n2026-09-23T12:05:00Z;Factura ejemplo;850,00\n',
            'account_id': 'personal', 'area': 'academia', 'date_format': 'ymd',
            'mapping': {'date': 'Fecha', 'description': 'Concepto', 'amount': 'Importe'}})['result']
        preview['rows'][0]['entry_id'] = entry
        self.request(page, '/api/import', {'mode': 'real', 'name': 'ejemplo', 'rows': preview['rows']})
        state = self.state(page)
        self.assertEqual(state['finance']['summary']['all']['my_available'], 85000)
        self.assertEqual(state['finance']['entries'][0]['pending'], 0)
        self.assertGreater(len(self.state(page, 'demo')['transactions']), 0)
        page.reload()
        page.locator('h1').wait_for(timeout=60000)
        self.assertEqual(self.state(page)['finance']['summary']['all']['my_available'], 85000)
        self.assertEqual(len(self.state(page)['transactions']), 1)

    def test_backup_download_restore_and_separate_devices(self):
        desktop, mobile = self.page(), self.page(390)
        self.add_income(desktop)
        self.assertEqual(self.state(mobile)['transactions'], [])
        desktop.locator('[data-page="settings"]').click()
        with desktop.expect_download() as download:
            desktop.locator('[data-action="backup"]').click()
        path = download.value.path()
        with sqlite3.connect(path) as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(db.execute('SELECT SUM(amount) FROM transactions WHERE active=1').fetchone()[0], 12345)
        mobile.locator('[data-page="settings"]').click()
        mobile.locator('#restore-file').set_input_files(path)
        mobile.once('dialog', lambda dialog: dialog.accept())
        mobile.locator('[data-action="restore"]').click()
        mobile.locator('#toast').filter(has_text='Respaldo restaurado').wait_for()
        self.assertEqual(self.state(mobile)['transactions'][0]['amount'], 12345)
        error = mobile.evaluate("""async () => {
          try { await misCuentasBrowser.restore(new File(['No es una base'], 'invalido.sqlite3'), 'real'); }
          catch(error) { return error.message; }
        }""")
        self.assertTrue(error)
        self.assertEqual(self.state(mobile)['transactions'][0]['amount'], 12345)
        with mobile.expect_download() as previous:
            mobile.locator('[data-action="before-restore"]').click()
        with sqlite3.connect(previous.value.path()) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM transactions').fetchone()[0], 0)

    def test_two_tabs_do_not_overwrite_each_other(self):
        first = self.page()
        second = self.page(context=first.context)
        payload = {'mode': 'real', 'date': '2026-09-10', 'account_id': 'personal',
            'area': 'personal', 'kind': 'income', 'value': '10', 'description': 'Primera pestaña'}
        first.evaluate('(payload) => { window.inflight = misCuentasBrowser.request("/api/transaction",payload); }', payload)
        self.add_income(second, 'Segunda pestaña', '20')
        first.evaluate('async () => await window.inflight')
        state = self.state(first)
        self.assertEqual(len(state['transactions']), 2)
        self.assertEqual(sum(t['amount'] for t in state['transactions']), 3000)

    def test_offline_reload_preserves_accounts(self):
        page = self.page()
        self.add_income(page)
        page.evaluate('async () => { await navigator.serviceWorker.ready; }')
        page.reload()
        page.locator('h1').wait_for(timeout=60000)
        self.assertTrue(page.evaluate('!!navigator.serviceWorker.controller'))
        page.context.set_offline(True)
        page.reload()
        page.locator('h1').wait_for(timeout=60000)
        self.assertEqual(self.state(page)['transactions'][0]['amount'], 12345)
        self.add_income(page, 'Sin conexión', '5')
        self.assertEqual(sum(t['amount'] for t in self.state(page)['transactions']), 12845)


if __name__ == '__main__':
    unittest.main(verbosity=2)
