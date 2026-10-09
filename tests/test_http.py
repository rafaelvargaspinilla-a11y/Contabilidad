"""Comprobaciones integradas con servidor y base temporal; sin datos reales."""
import http.cookiejar
import io
import json
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import Handler, Server
from core import Store


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = Server(('127.0.0.1', 0), self.temp.name)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': 0.01}, daemon=True)
        self.thread.start()
        self.origin = self.server.origin
        self.client = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        with self.client.open(self.origin + '/start?key=' + self.server.bootstrap) as r:
            self.assertEqual(r.status, 200)
            self.assertIn(b'Mis cuentas', r.read())
        self.csrf = self.get('/api/session')['csrf']

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def get(self, path):
        with self.client.open(self.origin + path) as r:
            return json.load(r)

    def post(self, path, data, headers=None):
        h = {'Content-Type': 'application/json', 'Origin': self.origin, 'X-CSRF-Token': self.csrf}
        if headers:
            h.update(headers)
        req = urllib.request.Request(self.origin + path, data=json.dumps(data).encode(), headers=h)
        with self.client.open(req) as r:
            return json.load(r)

    def test_private_access_requires_session_origin_and_token(self):
        anonymous = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with self.assertRaises(urllib.error.HTTPError) as error:
            anonymous.open(self.origin + '/api/state')
        self.assertEqual(error.exception.code, 401)
        for headers in ({'X-CSRF-Token': 'wrong'}, {'Origin': 'https://example.com'}, {'Host': 'example.com'}):
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.post('/api/person', {'name': 'No debe guardarse'}, headers)
            self.assertEqual(error.exception.code, 403)
        self.assertEqual(len(self.get('/api/state')['people']), 1)
        for path in ('/app.js', '/style.css', '/business-ui.mjs', '/import-utils.mjs'):
            with self.client.open(self.origin + path) as r:
                self.assertEqual(r.status, 200)
                self.assertIn("connect-src 'self'", r.headers['Content-Security-Policy'])
                if path.endswith(('.js','.mjs')):
                    self.assertIn('javascript', r.headers['Content-Type'])

    def test_course_invoice_and_iso_cash_through_http(self):
        course=self.post('/api/course', {'name':'Estadística', 'year':2026, 'semester':1, 'ownership':'own'})['result']
        invoice=self.post('/api/entry', {'date':'2026-09-10','period':'2026-09','area':'academia',
            'kind':'income','course_id':course,'gross_value':'1000','tax_percent':'15'})['result']
        csv={'text':'Fecha;Concepto;Importe\n2026-09-23T12:05:00Z;Factura ejemplo;850,00\n',
            'account_id':'personal','area':'academia','date_format':'ymd',
            'mapping':{'date':'Fecha','description':'Concepto','amount':'Importe'}}
        rows=self.post('/api/csv-preview',csv)['result']['rows']
        rows[0]['entry_id']=invoice
        self.post('/api/import',{'name':'ISO','rows':rows})
        state=self.get('/api/state?month=2026-09')
        self.assertEqual(len(state['finance']['entries']),1)
        self.assertEqual(state['finance']['summary']['all']['my_available'],85000)
        self.assertEqual(state['finance']['entries'][0]['pending'],0)
        with self.client.open(self.origin+'/api/export-activity') as r:
            self.assertIn('Estadística',r.read().decode('utf-8-sig'))

    def test_csv_and_payments_use_real_database_without_touching_demo(self):
        demo_before = self.get('/api/state?mode=demo&month=2026-09')
        self.assertGreater(len(demo_before['transactions']), 0)
        self.assertEqual(self.get('/api/state?mode=real&month=2026-09')['transactions'], [])
        payload = {'text': 'Fecha;Concepto;Importe\n10/09/2026;Curso;1000,00\n11/09/2026;Profesor;-200,00\n',
                   'account_id': 'academia', 'area': 'academia',
                   'mapping': {'date': 'Fecha', 'description': 'Concepto', 'amount': 'Importe'}}
        preview = self.post('/api/csv-preview', payload)['result']
        self.assertTrue(all(r['selected'] and not r['error'] for r in preview['rows']))
        self.post('/api/import', {'rows': preview['rows'], 'name': 'prueba.csv'})
        self.post('/api/move', {'date': '2026-09-15', 'from_account': 'academia', 'to_account': 'personal',
                                'kind': 'distribution', 'value': '300', 'description': 'Mi reparto'})
        self.post('/api/transaction', {'date': '2026-09-16', 'account_id': 'personal', 'area': 'personal',
                                       'kind': 'expense', 'value': '50', 'description': 'Compra'})
        state = self.get('/api/state?mode=real&month=2026-09')
        self.assertEqual(state['summary']['academia']['result'], 80000)
        self.assertEqual(state['summary']['personal']['personal_margin'], 25000)
        self.assertEqual(state['summary']['all']['result'], 75000)
        self.assertTrue(all(not r['selected'] for r in self.post('/api/csv-preview', payload)['result']['rows']))
        demo_after = self.get('/api/state?mode=demo&month=2026-09')
        self.assertEqual(demo_after['transactions'], demo_before['transactions'])

    def test_invalid_import_rolls_back_whole_batch(self):
        row = {'date': '2026-09-10', 'account_id': 'academia', 'area': 'academia',
               'kind': 'income', 'amount': 20000, 'description': 'Curso'}
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.post('/api/import', {'name': 'invalid.csv', 'rows': [row, {**row, 'amount': 0}]})
        self.assertEqual(error.exception.code, 400)
        state = self.get('/api/state?month=2026-09')
        self.assertEqual(state['transactions'], [])
        self.assertEqual(state['batches'], [])

    def test_export_and_backup_preserve_data(self):
        self.post('/api/transaction', {'date': '2026-09-10', 'account_id': 'baile', 'area': 'baile',
                                       'kind': 'income', 'value': '875,60', 'description': '=1+1'})
        with self.client.open(self.origin + '/api/export') as r:
            csv = r.read().decode('utf-8-sig')
        self.assertIn("'=1+1", csv)
        self.assertIn('875,60', csv)
        with self.client.open(self.origin + '/api/backup') as r:
            backup = Path(self.temp.name) / 'restored.sqlite3'
            backup.write_bytes(r.read())
        db = sqlite3.connect(backup)
        try:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(db.execute('SELECT SUM(amount) FROM transactions WHERE active=1').fetchone()[0], 87560)
        finally:
            db.close()

    def test_ai_payload_only_sends_totals_to_loopback(self):
        store = Store(Path(self.temp.name) / 'ai-test.sqlite3')
        try:
            store.transaction({'date': '2026-09-10', 'account_id': 'personal', 'area': 'personal',
                               'kind': 'expense', 'value': '15', 'description': 'CONCEPTO_PRIVADO_NO_ENVIAR'})
            with patch('app.urllib.request.build_opener') as build:
                opener = build.return_value
                opener.open.return_value = io.BytesIO(b'{"response":"Respuesta de prueba"}')
                response = Handler.ask_ai(None, store, {'model': 'qwen3.5:4b', 'month': '2026-09', 'question': 'Resume mis gastos'})
                self.assertEqual(response, 'Respuesta de prueba')
                req = opener.open.call_args.args[0]
                self.assertEqual(req.full_url, 'http://127.0.0.1:11434/api/generate')
                self.assertEqual(build.call_args.args[0].proxies, {})
                prompt = json.loads(req.data)['prompt']
                self.assertNotIn('CONCEPTO_PRIVADO_NO_ENVIAR', prompt)
                self.assertIn('1500', prompt)
            with self.assertRaises(ValueError):
                Handler.ask_ai(None, store, {'model': 'some-cloud-model', 'question': 'Hola'})
        finally:
            store.close()


if __name__ == '__main__':
    unittest.main()
