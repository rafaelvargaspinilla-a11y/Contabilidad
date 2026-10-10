"""Escenarios de gestión y migración. Todos los importes son ficticios."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import Store, bank_date
from finance import FinanceStore, proportion


class FinanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'cuentas.sqlite3'
        self.s = FinanceStore(self.path)

    def tearDown(self):
        self.s.close()
        self.temp.cleanup()

    def entry(self, **kw):
        return self.s.save_entry(dict(period='2026-09', date='2026-09-10', area='academia',
            kind='income', description='Ejemplo', gross_value='1000', **kw))

    def activity(self, **kw):
        payload = dict(period='2026-09', date='2026-09-10', area='academia',
            kind='income', description='Ejemplo', gross_value='1000')
        payload.update(kw)
        return self.s.save_entry(payload)

    def course(self, **kw):
        payload = dict(name='Asignatura', year=2026, semester=1, ownership='own')
        payload.update(kw)
        return self.s.save_course(payload)

    def state(self, period='2026-09'):
        return self.s.state(period)

    def get(self, ident):
        return next(e for e in self.state()['finance']['entries'] if e['id']==ident)

    def bank(self, **kw):
        p = dict(date='2026-09-10', area='personal', account_id='personal', kind='income',
                 description='Banco', value='850')
        p.update(kw)
        return self.s.transaction(p)

    def row(self, **kw):
        p = dict(date='2026-09-10', area='academia', account_id='personal', kind='income',
                 description='Extracto', amount=85000)
        p.update(kw)
        return p

    def test_own_external_and_general_cost_use_different_bases(self):
        own = self.course()
        ext = self.course(name='Externa', ownership='external', teacher_percent='65')
        invoice = self.activity(course_id=own, tax_percent='15', cash_status='paid', account_id='academia')
        external = self.activity(course_id=ext, cash_status='paid', account_id='academia')
        self.activity(kind='expense', gross_value='100', cash_status='paid', account_id='academia')
        e = self.get(invoice)
        self.assertEqual((e['my_bps'], e['gross'], e['withholding'], e['paid']), (10000,100000,15000,85000))
        e = self.get(external)
        self.assertEqual((e['teacher'],e['margin'],e['my_income']), (65000,35000,5950))
        x = self.state()
        self.assertEqual(x['finance']['summary']['academia']['my_available'], 89250)
        self.assertEqual(sum(t['amount'] for t in x['transactions']), 175000)
        self.assertEqual(x['finance']['balances']['academia'], -20750)

    def test_dance_shares_and_settlement_never_change_result(self):
        self.activity(area='baile', method='shared', gross_value='300', cash_status='paid', account_id='baile')
        self.activity(area='baile', method='individual', gross_value='80', cash_status='paid', account_id='baile')
        self.activity(area='baile', kind='expense', method='shared', gross_value='100', cash_status='paid', account_id='baile')
        self.assertEqual(self.state()['finance']['summary']['baile']['my_available'], 18000)
        self.assertEqual(self.state()['finance']['balances']['baile'], -10000)
        self.s.settle(dict(area='baile',date='2026-09-20',value='100',account_id='baile'))
        x=self.state()
        self.assertEqual(x['finance']['summary']['baile']['my_available'], 18000)
        self.assertEqual(x['finance']['balances']['baile'], 0)
        self.assertEqual(sum(t['amount'] for t in x['transactions']), 18000)

    def test_partner_cash_is_dated_and_does_not_enter_my_bank(self):
        ident=self.activity(area='baile', method='shared', holder='partner', gross_value='300')
        self.s.record_cash(dict(id=ident,cash_date='2026-10-01',cash_value='200'))
        self.assertEqual(self.state()['finance']['balances']['baile'],0)
        self.assertEqual(self.state('2026-10')['finance']['balances']['baile'],10000)
        self.assertEqual(self.state()['transactions'],[])
        self.s.settle(dict(area='baile',date='2026-10-02',value='100',direction='from_partner',account_id='baile'))
        self.assertEqual(self.state('2026-10')['finance']['balances']['baile'],0)
        self.assertEqual(self.get(ident)['pending'],10000)

    def test_rates_are_snapshots_and_terms_enforce_academic_year(self):
        ext=self.course(ownership='external', teacher_percent='65')
        first=self.activity(course_id=ext)
        self.s.save_preferences(dict(my_share='20',tax='19',teacher_share='60'))
        self.course(id=ext,ownership='external',teacher_percent='70')
        second=self.activity(course_id=ext)
        self.assertEqual((self.get(first)['my_bps'],self.get(first)['teacher_bps']),(1700,6500))
        self.assertEqual((self.get(second)['my_bps'],self.get(second)['teacher_bps']),(2000,7000))
        second_term=self.course(name='Segundo',semester=2)
        with self.assertRaises(ValueError): self.activity(course_id=second_term)
        self.activity(course_id=second_term,period='2027-01',date='2027-01-10')
        with self.assertRaises(ValueError): self.course(id=ext,ownership='external',semester=2)

    def test_import_net_invoice_links_without_counting_twice(self):
        ident=self.activity(tax_percent='15')
        self.s.import_rows(dict(name='ISO.csv',rows=[self.row(entry_id=ident)]))
        self.assertEqual(len(self.state()['finance']['entries']),1)
        self.assertEqual(self.get(ident)['pending'],0)
        self.assertEqual(self.state()['finance']['summary']['all']['my_available'],85000)
        batch=self.state()['batches'][0]['id']
        self.s.undo_import(dict(id=batch))
        self.assertEqual(self.get(ident)['pending'],85000)
        self.assertEqual(self.state()['transactions'],[])

    def test_one_receipt_can_cover_several_subjects_and_partial_payments(self):
        a=self.activity(gross_value='100',tax_percent='15')
        b=self.activity(gross_value='200',tax_percent='15')
        tx=self.bank(value='200')
        self.s.reconcile(dict(tx_id=tx,replace_automatic=True,links=[dict(entry_id=a,value='85'),dict(entry_id=b,value='115')]))
        self.assertEqual(len(self.state()['finance']['entries']),2)
        self.assertEqual((self.get(a)['pending'],self.get(b)['pending']),(0,5500))
        tx2=self.bank(value='55',date='2026-09-20')
        self.s.reconcile(dict(tx_id=tx2,replace_automatic=True,links=[dict(entry_id=b,value='55')]))
        self.assertEqual(self.get(b)['pending'],0)
        self.assertEqual(self.state()['finance']['summary']['all']['my_available'],25500)

    def test_bad_reconciliation_restores_automatic_entry_and_links(self):
        a=self.activity(gross_value='100')
        tx=self.bank(value='200')
        before=self.state()
        with self.assertRaises(ValueError):
            self.s.reconcile(dict(tx_id=tx,replace_automatic=True,links=[dict(entry_id=a,value='80'),dict(entry_id=a,value='50')]))
        after=self.state()
        self.assertEqual(before['finance'],after['finance'])
        self.assertEqual(before['transactions'],after['transactions'])

    def test_mixed_import_retains_account_and_distinct_shares(self):
        rows=[self.row(area='academia',kind='expense',amount=-10000,activity=dict(method='shared',my_percent='17')),
              self.row(area='baile',kind='income',amount=30000,activity=dict(method='shared',my_percent='50')),
              self.row(area='personal',kind='expense',amount=-2000)]
        self.s.import_rows(dict(name='mix',rows=rows))
        x=self.state()
        self.assertTrue(all(t['account_id']=='personal' for t in x['transactions']))
        self.assertEqual([x['finance']['summary'][a]['my_available'] for a in ('academia','baile','personal','all')],[-1700,15000,-2000,11300])

    def test_invalid_external_import_rolls_back_whole_batch(self):
        with self.assertRaises(ValueError):
            self.s.import_rows(dict(name='bad',rows=[self.row(),self.row(activity=dict(method='external'))]))
        x=self.state()
        self.assertEqual(x['transactions'],[])
        self.assertEqual(x['finance']['entries'],[])
        self.assertEqual(x['batches'],[])

    def test_create_paid_activity_failure_rolls_back_activity(self):
        with self.assertRaises(ValueError): self.activity(cash_status='paid',account_id='does-not-exist')
        self.assertEqual(self.state()['finance']['entries'],[])

    def test_internal_transfer_removes_bank_activity_but_not_cash(self):
        a=self.bank(area='academia',account_id='academia',kind='expense',value='100')
        b=self.bank(value='100')
        self.s.link_existing(dict(ids=[a,b],kind='distribution'))
        x=self.state()
        self.assertEqual(x['finance']['summary']['all']['my_available'],0)
        self.assertEqual(x['finance']['entries'],[])
        self.assertEqual(x['summary']['personal']['received'],10000)
        self.assertEqual(sum(t['amount'] for t in x['transactions']),0)

    def test_teacher_payout_is_neutral_and_cross_payer_adjusts_partner_balance(self):
        ext=self.course(ownership='external',teacher_percent='65')
        ident=self.activity(course_id=ext,holder='partner',cash_status='paid')
        self.assertEqual(self.state()['finance']['balances']['academia'],5950)
        self.s.settle(dict(area='academia',role='teacher',entry_id=ident,date='2026-09-12',value='650',holder='me',account_id='academia'))
        x=self.state()
        self.assertEqual(x['finance']['balances']['academia'],70950)
        self.assertEqual(x['finance']['summary']['academia']['my_available'],5950)
        with self.assertRaises(ValueError):
            self.s.settle(dict(area='academia',role='teacher',entry_id=ident,date='2026-09-12',value='1',account_id='academia'))

    def test_refund_reduces_my_share_and_counterparty_balance(self):
        self.activity(area='baile',kind='expense',method='shared',gross_value='50',refund=True,cash_status='paid',account_id='baile')
        x=self.state()
        self.assertEqual(x['finance']['summary']['baile']['my_available'],2500)
        self.assertEqual(x['finance']['balances']['baile'],-2500)
        self.assertEqual(x['transactions'][0]['amount'],5000)

    def test_imported_positive_amount_can_be_corrected_to_expense_refund(self):
        self.bank(area='personal',value='25')
        ident=self.state()['finance']['entries'][0]['id']
        self.activity(id=ident,area='personal',kind='expense',refund=True,gross_value='25')
        e=self.get(ident)
        self.assertEqual((e['paid'],e['pending'],e['my_expense']),(2500,0,-2500))
        self.assertEqual(len(self.state()['transactions']),1)

    def test_migration_keeps_bank_and_requests_review_with_backup(self):
        self.s.close()
        self.path.unlink()
        old=Store(self.path)
        old.transaction(dict(date='2026-09-10',area='academia',account_id='academia',kind='income',description='Antiguo',value='1000'))
        old.close()
        self.s=FinanceStore(self.path)
        x=self.state()
        self.assertEqual(len(x['transactions']),1)
        self.assertEqual(x['finance']['summary']['academia']['review'],1)
        self.assertEqual(x['finance']['summary']['all']['my_available'],0)
        self.assertEqual(len(list(self.path.parent.glob('antes-v02-*.sqlite3'))),1)
        ident=x['finance']['entries'][0]['id']
        self.activity(id=ident,gross_value='1000',tax_percent='0')
        self.assertEqual(self.state()['finance']['summary']['all']['my_available'],100000)
        self.s.close()
        self.s=FinanceStore(self.path)
        self.assertEqual(len(self.state()['finance']['entries']),1)

    def test_backup_and_export_include_activity_without_formula_injection(self):
        course=self.course()
        self.activity(course_id=course,description='=1+1',tax_percent='15')
        target=self.path.with_name('copy.sqlite3')
        self.s.backup(target)
        other=FinanceStore(target)
        try:self.assertEqual(other.state('2026-09')['finance'],self.state()['finance'])
        finally:other.close()
        exported=self.s.export_activity().decode('utf-8-sig')
        self.assertIn("'=1+1",exported)
        self.assertIn('850',exported)

    def test_half_cent_allocations_conserve_remainder(self):
        ext=self.course(ownership='external',teacher_percent='50')
        ident=self.activity(course_id=ext,gross_value='0.03',my_percent='50')
        e=self.get(ident)
        self.assertEqual((e['teacher'],e['margin'],e['my_income'],e['other_income']),(2,1,1,0))
        self.assertEqual(proportion(-3,5000),-2)

    def test_iso_dates_and_timestamps_keep_calendar_day(self):
        for text in ('2026-09-23','2026-09-23 08:13:05','2026-09-23T23:50:00Z','2026-09-23T00:05:00.123+02:00'):
            for order in ('ymd','dmy','mdy'):
                self.assertEqual(bank_date(text,order),'2026-09-23')
        self.assertEqual(bank_date('23/09/2026'),'2026-09-23')
        self.assertEqual(bank_date('09/23/2026','mdy'),'2026-09-23')
        self.assertEqual(bank_date('2026/09/23','ymd'),'2026-09-23')
        for text in ('2026-02-30','2026-09-23T99:00:00','23/09/26garbage'):
            with self.assertRaises(ValueError):bank_date(text)

    def test_csv_iso_roundtrip_duplicate_detection(self):
        p=dict(text='Date;Description;Amount\n2026-09-23 10:20:05;Cafe;-2,50\n',account_id='personal',area='personal',
               date_format='ymd',mapping=dict(date='Date',description='Description',amount='Amount'))
        rows=self.s.preview_csv(p)['rows']
        self.assertEqual(rows[0]['date'],'2026-09-23')
        self.s.import_rows(dict(name='ISO',rows=rows))
        self.assertTrue(self.s.preview_csv(p)['rows'][0]['duplicate'])

    def test_budget_received_not_profit_or_transfers_and_locked_base(self):
        self.activity(cash_status='paid', account_id='academia', tax_percent='15')
        self.activity(kind='expense', gross_value='200', cash_status='paid', account_id='academia')
        self.activity(gross_value='500')  # Pending is not received.
        category = self.s.rows("SELECT id FROM categories WHERE area='personal' AND kind='expense'")[0]['id']
        self.assertEqual(self.s.state('2026-10')['budget']['received'], 85000)
        self.s.save_budget(dict(month='2026-10', allocations=[dict(category_id=category, percent='60')]))
        self.activity(gross_value='100', cash_status='paid', account_id='academia', tax_percent='0')
        self.s.save_budget(dict(month='2026-10', allocations=[dict(category_id=category, percent='100')]))
        self.assertEqual(self.s.state('2026-10')['budget']['saved']['amount'], 85000)
        self.assertEqual(self.s.state('2026-10')['budget']['received'], 95000)
        self.s.close()
        self.s = FinanceStore(self.path)
        self.assertEqual(self.s.state('2026-10')['budget']['saved']['allocations'][0]['bps'], 10000)

    def test_budget_rejects_duplicate_categories_and_excess(self):
        category = self.s.rows("SELECT id FROM categories WHERE area='personal' AND kind='expense'")[0]['id']
        for rows in ([dict(category_id=category, percent='101')],
                     [dict(category_id=category, percent='40')]*2):
            with self.assertRaises(ValueError):
                self.s.save_budget(dict(month='2026-10', allocations=rows))
        self.assertIsNone(self.s.state('2026-10')['budget']['saved'])


if __name__=='__main__':unittest.main()
