"""Intercambio tipado entre SQLite y las tablas PostgreSQL de Supabase."""
import json
import sqlite3
from pathlib import Path

from finance import FinanceStore

TABLES = ('accounts', 'categories', 'people', 'preferences', 'courses', 'batches',
          'audit', 'shares', 'transactions', 'rules', 'entries', 'entry_links',
          'settlements', 'external_cash')
SCHEMA_VERSION = 1


def export_snapshot(path):
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        tables = {}
        for table in TABLES:
            keys = [row['name'] for row in db.execute(f'PRAGMA table_info({table})') if row['pk']]
            tables[table] = [dict(row) for row in db.execute(f'SELECT * FROM {table} ORDER BY {",".join(keys)}')]
    return json.dumps({'schema_version': SCHEMA_VERSION, 'tables': tables}, ensure_ascii=False)


def import_snapshot(path, snapshot_json):
    snapshot = json.loads(snapshot_json)
    if snapshot.get('schema_version') != SCHEMA_VERSION or set(snapshot.get('tables', {})) != set(TABLES):
        raise ValueError('Versión o estructura de las cuentas no compatible.')
    path = Path(path)
    if path.exists():
        path.unlink()
    store = FinanceStore(path)
    try:
        with store.db:
            for table in reversed(TABLES):
                store.db.execute(f'DELETE FROM {table}')
            for table in TABLES:
                columns = [row['name'] for row in store.db.execute(f'PRAGMA table_info({table})')]
                rows = snapshot['tables'][table]
                if not isinstance(rows, list):
                    raise ValueError('Tabla de cuentas inválida.')
                for row in rows:
                    if set(row) != set(columns):
                        raise ValueError('Campos de cuentas no compatibles.')
                    store.db.execute(f'INSERT INTO {table} ({",".join(columns)}) VALUES ({",".join("?" for _ in columns)})', [row[c] for c in columns])
            if store.db.execute('PRAGMA foreign_key_check').fetchone():
                raise ValueError('Hay referencias inválidas en las cuentas.')
    finally:
        store.close()
