import copy
import json
import tempfile
import unittest
import uuid
from pathlib import Path

import psycopg
from cloud_bridge import export_snapshot
from finance import FinanceStore, seed_demo
from supabase_support import TestDatabase, ACTOR_A, ACTOR_B


def snapshot(demo=False, income=None):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'accounts.sqlite3'
        store = FinanceStore(path)
        if demo: seed_demo(store)
        if income:
            store.transaction({'date': '2026-09-10', 'account_id': 'personal', 'area': 'personal',
                'kind': 'income', 'value': income, 'description': 'Prueba grande'})
        store.close()
        return json.loads(export_snapshot(path))


class SupabaseSQLTests(unittest.TestCase):
    def setUp(self): self.db = TestDatabase()
    def tearDown(self): self.db.close()

    def test_private_rows_and_same_local_ids_for_two_users(self):
        self.db.commit(ACTOR_A, 0, snapshot(income='10'))
        self.db.commit(ACTOR_B, 0, snapshot(income='20'))
        a = self.db.load(ACTOR_A)['snapshot']['tables']
        b = self.db.load(ACTOR_B)['snapshot']['tables']
        self.assertEqual(a['transactions'][0]['amount'], 1000)
        self.assertEqual(b['transactions'][0]['amount'], 2000)
        rows = self.db.query(ACTOR_A, 'select distinct owner_id::text from public.mc_transactions')
        self.assertEqual(rows, [(ACTOR_A,)])

    def test_anonymous_and_direct_writes_are_denied(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            self.db.query(None, 'select public.mc_load()', role='anon')
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            self.db.query(ACTOR_A, 'insert into public.mc_head(owner_id) values(%s)', [ACTOR_A])
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            self.db.query(ACTOR_A, 'select public.mc_snapshot(%s)', [ACTOR_B])

    def test_stale_revision_does_not_overwrite_accounts(self):
        original = snapshot(income='10')
        self.db.commit(ACTOR_A, 0, original)
        newer = copy.deepcopy(original)
        newer['tables']['accounts'][0]['name'] = 'Actualizado desde el móvil'
        self.db.commit(ACTOR_A, 1, newer)
        with self.assertRaisesRegex(psycopg.Error, 'MC_CONFLICT'):
            self.db.commit(ACTOR_A, 1, original)
        self.assertEqual(self.db.load(ACTOR_A)['revision'], 2)
        self.assertEqual(self.db.load(ACTOR_A)['snapshot']['tables']['accounts'][0]['name'], 'Actualizado desde el móvil')

    def test_retry_is_idempotent_and_changed_retry_is_rejected(self):
        data = snapshot()
        operation = str(uuid.uuid4())
        self.db.commit(ACTOR_A, 0, data, operation)
        replay = self.db.commit(ACTOR_A, 0, data, operation)
        self.assertTrue(replay['replayed'])
        self.assertEqual(self.db.load(ACTOR_A)['revision'], 1)
        data['tables']['accounts'][0]['name'] = 'No es el mismo reintento'
        with self.assertRaisesRegex(psycopg.Error, 'MC_INVALID_RETRY'):
            self.db.commit(ACTOR_A, 0, data, operation)

    def test_invalid_foreign_key_rolls_back_all_tables_and_revision(self):
        good = snapshot(income='10')
        self.db.commit(ACTOR_A, 0, good)
        bad = copy.deepcopy(good)
        bad['tables']['accounts'][0]['name'] = 'No debe guardarse'
        bad['tables']['transactions'][0]['account_id'] = 'cuenta-otra-persona'
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            self.db.commit(ACTOR_A, 1, bad)
        state = self.db.load(ACTOR_A)
        self.assertEqual(state['revision'], 1)
        self.assertNotEqual(state['snapshot']['tables']['accounts'][0]['name'], 'No debe guardarse')

    def test_bigint_preserves_money_and_all_demo_tables(self):
        data = snapshot(demo=True, income='999999999,99')
        self.db.commit(ACTOR_A, 0, data)
        restored = self.db.load(ACTOR_A)['snapshot']['tables']
        self.assertEqual(len(restored), 14)
        for table, rows in data['tables'].items():
            self.assertCountEqual(restored[table], rows)
        self.assertIn(99999999999, [row['amount'] for row in restored['transactions']])

    def test_restore_keeps_private_previous_snapshot(self):
        self.db.commit(ACTOR_A, 0, snapshot(income='10'))
        self.db.commit(ACTOR_A, 1, snapshot(income='20'), restore=True)
        previous = self.db.rpc(ACTOR_A, 'mc_backup', {'p_kind': 'restore'})
        self.assertEqual(previous['tables']['transactions'][0]['amount'], 1000)
        with self.assertRaisesRegex(psycopg.Error, 'MC_NO_BACKUP'):
            self.db.rpc(ACTOR_B, 'mc_backup', {'p_kind': 'restore'})

    def test_invalid_allocation_is_rejected_atomically(self):
        data = snapshot(demo=True)
        self.db.commit(ACTOR_A, 0, data)
        bad = copy.deepcopy(data)
        bad['tables']['entry_links'][0]['amount'] = 100000000000
        with self.assertRaisesRegex(psycopg.Error, 'MC_INVALID_ALLOCATION'):
            self.db.commit(ACTOR_A, 1, bad)
        self.assertEqual(self.db.load(ACTOR_A)['revision'], 1)


if __name__ == '__main__': unittest.main(verbosity=2)
