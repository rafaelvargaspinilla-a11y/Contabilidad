"""Adaptador local para el navegador; reutiliza el motor contable original."""
import json
import sqlite3
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from finance import FinanceStore, seed_demo

METHODS = {
    'transaction': 'transaction', 'move': 'move', 'link': 'link_existing',
    'delete': 'delete', 'account': 'add_account', 'category': 'add_category',
    'person': 'add_person', 'shares': 'save_shares', 'rule': 'add_rule',
    'remove-rule': 'remove_rule', 'csv-preview': 'preview_csv', 'import': 'import_rows',
    'undo-import': 'undo_import', 'entry': 'save_entry', 'course': 'save_course',
    'preferences': 'save_preferences', 'cash': 'record_cash', 'delete-entry': 'delete_entry',
    'reconcile': 'reconcile', 'unlink': 'unlink', 'external-unpaid': 'mark_external_unpaid',
    'settlement': 'settle', 'delete-settlement': 'delete_settlement', 'classify-bank': 'classify_bank',
}


def validate_restore(path):
    """No modificar la base actual si el archivo no es un respaldo válido."""
    db = sqlite3.connect(f'{Path(path).as_uri()}?mode=ro', uri=True)
    try:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('El respaldo no pasa la comprobación de integridad.')
        db.execute('SELECT id,date,amount FROM transactions LIMIT 1')
        db.execute('SELECT id,name,area FROM accounts LIMIT 1')
    finally:
        db.close()
    store = FinanceStore(path)
    try:
        store.state(date.today().strftime('%Y-%m'))
    finally:
        store.close()


def handle_request(path, payload_json='null'):
    url = urlsplit(path)
    payload = json.loads(payload_json)
    query = parse_qs(url.query)
    action = url.path.removeprefix('/api/')
    if action == 'session':
        return json.dumps({'csrf': 'browser-local'})
    mode = (payload or {}).get('mode', query.get('mode', ['real'])[0])
    if mode not in ('real', 'demo'):
        raise ValueError('Modo inválido.')
    store = FinanceStore(Path('/data') / f'{mode}.sqlite3')
    try:
        if mode == 'demo':
            seed_demo(store)
        if action == 'state' and payload is None:
            result = store.state(query.get('month', [date.today().strftime('%Y-%m')])[0])
            result['data_path'] = 'Guardado en este navegador · ' + ('Mis datos' if mode == 'real' else 'Ejemplo')
        elif action in METHODS and payload is not None:
            result = {'ok': True, 'result': getattr(store, METHODS[action])(payload)}
        elif action in ('export', 'export-activity', 'backup') and payload is None:
            target = Path('/data/download')
            if action == 'backup':
                if target.exists():
                    target.unlink()
                store.backup(target)
                name, mime = 'cuentas-respaldo.sqlite3', 'application/octet-stream'
            else:
                target.write_bytes(store.export_csv() if action == 'export' else store.export_activity())
                name, mime = ('movimientos.csv' if action == 'export' else 'actividad-y-repartos.csv'), 'text/csv;charset=utf-8'
            result = {'download_path': str(target), 'filename': name, 'mime': mime}
        else:
            raise ValueError('Operación no disponible en la versión de navegador.')
        return json.dumps(result, ensure_ascii=False)
    finally:
        store.close()
