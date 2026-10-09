import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import Store, cents


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.s = Store(Path(self.temp.name)/'test.sqlite3')

    def tearDown(self):
        self.s.close()
        self.temp.cleanup()

    def tx(self, area, kind, value, **kw):
        return self.s.transaction({'date':'2026-09-10','area':area,'account_id':area,'kind':kind,
                                   'description':'Prueba','value':value,**kw})

    def move(self, kind, value):
        return self.s.move({'date':'2026-09-10','from_account':'academia','to_account':'personal',
                            'kind':kind,'value':value,'description':'Pago'})

    def summary(self):
        return self.s.state('2026-09')['summary']

    def test_distribution_is_received_but_not_second_global_income(self):
        self.tx('academia','income','5000')
        self.tx('academia','expense','2000')
        self.tx('personal','expense','400')
        self.move('distribution','1000')
        x=self.summary()
        self.assertEqual(x['academia']['result'],300000)
        self.assertEqual(x['academia']['distributed'],100000)
        self.assertEqual(x['personal']['received'],100000)
        self.assertEqual(x['personal']['personal_margin'],60000)
        self.assertEqual(x['all']['income'],500000)
        self.assertEqual(x['all']['expense'],240000)
        self.assertEqual(x['all']['result'],260000)
        self.assertEqual(x['all']['cashflow'],260000)

    def test_remuneration_reduces_business_and_is_personal_income(self):
        self.tx('academia','income','5000')
        self.move('remuneration','1000')
        x=self.summary()
        self.assertEqual(x['academia']['expense'],100000)
        self.assertEqual(x['personal']['income'],100000)
        self.assertEqual(x['personal']['received'],0)
        self.assertEqual(x['all']['result'],500000)

    def test_transfers_funding_and_reimbursement_do_not_change_results(self):
        for kind in ('transfer','funding','reimbursement'):
            self.move(kind,'100')
        x=self.summary()
        self.assertTrue(all(a['result']==0 for a in x.values()))
        self.assertEqual(x['personal']['cashflow'],30000)
        self.assertEqual(x['all']['cashflow'],0)

    def test_refund_reduces_expense_without_creating_income(self):
        self.tx('personal','expense','100')
        self.tx('personal','expense','25',refund=True)
        x=self.summary()['personal']
        self.assertEqual(x['income'],0)
        self.assertEqual(x['expense'],7500)

    def test_duplicate_import_is_flagged_and_undo_is_scoped(self):
        p={'text':'Fecha;Concepto;Importe;ID\n10/09/2026;Cobro;1.234,56;B1\n11/09/2026;Pago;-20,50;B2\n',
           'delimiter':';','account_id':'academia','area':'academia',
           'mapping':{'date':'Fecha','description':'Concepto','amount':'Importe','bank_id':'ID'}}
        preview=self.s.preview_csv(p)
        self.assertEqual(preview['rows'][0]['amount'],123456)
        self.assertFalse(any(r['duplicate'] for r in preview['rows']))
        self.s.import_rows({'name':'ejemplo','rows':preview['rows']})
        again=self.s.preview_csv(p)
        self.assertTrue(all(r['duplicate'] and not r['selected'] for r in again['rows']))
        self.tx('personal','income','10')
        batch=self.s.state('2026-09')['batches'][0]['id']
        self.s.undo_import({'id':batch})
        self.assertEqual(len(self.s.state('2026-09')['transactions']),1)

    def test_matching_rows_in_single_file_are_preserved(self):
        p={'text':'fecha;importe;concepto\n10/09/2026;-5,00;Café\n10/09/2026;-5,00;Café\n',
           'account_id':'personal','area':'personal','mapping':{'date':'fecha','amount':'importe','description':'concepto'}}
        rows=self.s.preview_csv(p)['rows']
        self.assertEqual(len(rows),2)
        self.assertNotEqual(rows[0]['source_key'],rows[1]['source_key'])
        self.s.import_rows({'name':'two coffees','rows':rows})
        self.assertEqual(self.summary()['personal']['expense'],1000)

    def test_link_existing_imports_eliminates_double_counting(self):
        a=self.tx('academia','expense','1000')
        b=self.tx('personal','income','1000')
        self.s.link_existing({'ids':[a,b],'kind':'distribution'})
        x=self.summary()
        self.assertEqual(x['academia']['expense'],0)
        self.assertEqual(x['personal']['received'],100000)
        self.assertEqual(x['all']['income'],0)
        self.s.delete({'id':a})
        self.assertEqual(len(self.s.state('2026-09')['transactions']),0)

    def test_internal_move_is_atomic_on_invalid_date(self):
        self.s.add_account({'id':'personal','name':'Personal','area':'personal','opening':'0','opening_date':'2026-09-15'})
        with self.assertRaises(ValueError): self.move('distribution','1000')
        self.assertEqual(len(self.s.state('2026-09')['transactions']),0)

    def test_area_and_bank_account_are_independent(self):
        self.tx('academia','expense','100',account_id='personal')
        self.assertEqual(self.summary()['academia']['expense'],10000)
        self.assertEqual(self.summary()['personal']['expense'],0)

    def test_shares_are_monthly_and_cannot_exceed_100_percent(self):
        self.s.save_shares({'month':'2026-09','area':'academia','shares':[{'person_id':'me','percent':'16'}]})
        self.assertEqual(self.s.state('2026-09')['shares'][0]['bps'],1600)
        self.assertEqual(self.s.state('2026-10')['shares'],[])
        with self.assertRaises(ValueError):
            self.s.save_shares({'month':'2026-09','area':'academia','shares':[{'person_id':'me','percent':'101'}]})
        self.assertEqual(self.s.state('2026-09')['shares'][0]['bps'],1600)

    def test_backup_can_be_reopened_with_same_totals(self):
        self.tx('baile','income','875.60')
        target=Path(self.temp.name)/'copy.sqlite3'
        self.s.backup(target)
        other=Store(target)
        try:self.assertEqual(other.state('2026-09')['summary'],self.summary())
        finally:other.close()

    def test_money_precision(self):
        self.assertEqual(cents('1.234,56'),123456)
        self.assertEqual(cents('1,234.56'),123456)
        self.assertEqual(cents('(20,50)'),-2050)
        self.assertEqual(cents('0.10')+cents('0.20'),30)
        for value in ('NaN','Infinity','1.234'):
            with self.assertRaises(ValueError):cents(value)


if __name__=='__main__':unittest.main()
