import json
import tempfile
import unittest
from pathlib import Path

from cloud_bridge import export_snapshot, import_snapshot
from finance import FinanceStore, seed_demo
from scripts.build_pages import cloud_config
from unittest.mock import patch


class CloudBridgeTests(unittest.TestCase):
    def test_roundtrip_preserves_accounts_activity_and_calculations(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / 'original.sqlite3'
            restored = Path(directory) / 'restored.sqlite3'
            store = FinanceStore(original)
            seed_demo(store)
            before = store.state('2026-09')
            store.close()
            snapshot = export_snapshot(original)
            import_snapshot(restored, snapshot)
            self.assertEqual(json.loads(export_snapshot(restored)), json.loads(snapshot))
            store = FinanceStore(restored)
            after = store.state('2026-09')
            store.close()
            for key, value in before['finance'].items():
                if isinstance(value, list): self.assertCountEqual(value, after['finance'][key])
                else: self.assertEqual(value, after['finance'][key])

    def test_invalid_relationship_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / 'original.sqlite3'
            store = FinanceStore(original)
            store.transaction({'date': '2026-09-10', 'account_id': 'personal', 'area': 'personal',
                'kind': 'income', 'value': '10', 'description': 'Prueba'})
            store.close()
            snapshot = json.loads(export_snapshot(original))
            snapshot['tables']['transactions'][0]['account_id'] = 'cuenta-inexistente'
            with self.assertRaises(Exception):
                import_snapshot(Path(directory) / 'candidate.sqlite3', json.dumps(snapshot))
            self.assertEqual(len(json.loads(export_snapshot(original))['tables']['transactions']), 1)

    def test_configuration_rejects_admin_keys_and_partial_configuration(self):
        with patch.dict('os.environ', {'SUPABASE_URL': 'https://example.supabase.co',
                                    'SUPABASE_PUBLISHABLE_KEY': 'sb_secret_no_publicar'}):
            with self.assertRaises(ValueError): cloud_config()
        with patch.dict('os.environ', {'SUPABASE_URL': 'https://example.supabase.co',
                                    'SUPABASE_PUBLISHABLE_KEY': ''}):
            with self.assertRaises(ValueError): cloud_config()


if __name__ == '__main__':
    unittest.main()
