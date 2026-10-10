"""Actividades, reparto económico y conciliación con el registro bancario."""
import csv
import io
import json
import uuid
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from core import AREAS, Store, cents, clean, valid_date


def proportion(amount, bps):
    return int((Decimal(amount) * Decimal(bps) / 10000).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def percent(value):
    result = cents(value)
    if not 0 <= result <= 10000:
        raise ValueError('El porcentaje debe estar entre 0 y 100.')
    return result


def month(value):
    value = str(value or '')
    if len(value) != 7 or valid_date(value + '-01')[:7] != value:
        raise ValueError('Mes inválido: usa año-mes.')
    return value


def entry_values(e):
    """Resultado económico. Las liquidaciones nunca vuelven a ser gasto."""
    income = e['gross'] if e['kind'] == 'income' else 0
    expense = e['gross'] * (-1 if e['refund'] else 1) if e['kind'] == 'expense' else 0
    teacher = proportion(income, e['teacher_bps']) if e['method'] == 'external' else 0
    margin = income - teacher
    mine_income = proportion(margin, e['my_bps'])
    mine_expense = proportion(expense, e['my_bps'])
    tax = e['withholding']
    net = e['gross'] - tax
    return dict(income=income, expense=expense, teacher=teacher, margin=margin,
                my_income=mine_income, my_expense=mine_expense, withholding=tax,
                my_result=mine_income-mine_expense, my_available=mine_income-mine_expense-tax,
                expected=net, other_income=margin-mine_income,
                other_expense=expense-mine_expense)


class FinanceStore(Store):
    def __init__(self, path):
        super().__init__(path)
        if not self.db.execute("SELECT 1 FROM sqlite_master WHERE name='entries'").fetchone() and self.db.execute('SELECT 1 FROM transactions LIMIT 1').fetchone():
            self.backup(self.path.with_name('antes-v02-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.sqlite3'))
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS courses (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, year INTEGER NOT NULL, semester INTEGER NOT NULL,
          ownership TEXT NOT NULL, teacher TEXT NOT NULL DEFAULT '', teacher_bps INTEGER NOT NULL,
          active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS entries (
          id TEXT PRIMARY KEY, period TEXT NOT NULL, date TEXT NOT NULL, area TEXT NOT NULL,
          kind TEXT NOT NULL, method TEXT NOT NULL, course_id TEXT REFERENCES courses(id),
          description TEXT NOT NULL, category_id TEXT REFERENCES categories(id), gross INTEGER NOT NULL,
          tax_bps INTEGER NOT NULL, withholding INTEGER NOT NULL, my_bps INTEGER NOT NULL,
          teacher_bps INTEGER NOT NULL, holder TEXT NOT NULL, external_paid INTEGER NOT NULL DEFAULT 0,
          refund INTEGER NOT NULL DEFAULT 0, source TEXT NOT NULL, review INTEGER NOT NULL DEFAULT 0,
          notes TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1, created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS entry_links (
          entry_id TEXT NOT NULL REFERENCES entries(id), tx_id TEXT NOT NULL REFERENCES transactions(id),
          amount INTEGER NOT NULL CHECK(amount>0), PRIMARY KEY(entry_id,tx_id));
        CREATE TABLE IF NOT EXISTS settlements (
          id TEXT PRIMARY KEY, date TEXT NOT NULL, area TEXT NOT NULL, role TEXT NOT NULL,
          direction TEXT NOT NULL, amount INTEGER NOT NULL, holder TEXT NOT NULL,
          entry_id TEXT REFERENCES entries(id), tx_id TEXT REFERENCES transactions(id),
          notes TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS external_cash (
          id TEXT PRIMARY KEY, entry_id TEXT NOT NULL REFERENCES entries(id), date TEXT NOT NULL, amount INTEGER NOT NULL);
        ''')
        with self.db:
            for key, value in (('my_share','1700'), ('tax','1500'), ('teacher_share','6500')):
                self.db.execute('INSERT OR IGNORE INTO preferences VALUES (?,?)', (key,value))
            for name in ('Clases presenciales','Productos online','Clases privadas'):
                self.db.execute('INSERT OR IGNORE INTO categories VALUES (?,?,?,?)', (uuid.uuid4().hex,name,'baile','income'))
            if not self.db.execute("SELECT 1 FROM preferences WHERE key='migrated_v2'").fetchone():
                for t in self.rows("SELECT * FROM transactions WHERE active=1 AND link_id IS NULL AND kind IN ('income','expense')"):
                    self._from_bank(t, {'review': 1})
                self.db.execute("INSERT INTO preferences VALUES ('migrated_v2','1')")

    def prefs(self):
        return {r['key']:int(r['value']) for r in self.rows("SELECT * FROM preferences WHERE key IN ('my_share','tax','teacher_share')")}

    def save_preferences(self, p):
        values = {k:percent(p[k]) for k in ('my_share','tax','teacher_share')}
        if values['tax'] >= 10000:
            raise ValueError('La retención debe ser inferior al 100 %.')
        with self.db:
            for k,v in values.items():
                self.db.execute('UPDATE preferences SET value=? WHERE key=?',(str(v),k))
            self.log('preferences',values)

    def budget_state(self, month):
        previous = (date.fromisoformat(month+'-01').replace(day=1)).toordinal()-1
        source = date.fromordinal(previous).strftime('%Y-%m')
        total = 0
        for e in self.rows("SELECT * FROM entries WHERE active=1 AND review=0 AND kind='income'"):
            values = entry_values(e)
            received = sum(r['amount'] for r in self.rows("SELECT l.amount FROM entry_links l JOIN transactions t ON t.id=l.tx_id WHERE l.entry_id=? AND t.active=1 AND substr(t.date,1,7)=?", (e['id'], source)))
            received += sum(r['amount'] for r in self.rows("SELECT amount FROM external_cash WHERE entry_id=? AND substr(date,1,7)=?", (e['id'], source)))
            if values['expected']:
                total += int((Decimal(received)*Decimal(values['my_income']-values['withholding'])/values['expected']).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        expenses = sum(entry_values(e)['my_expense'] for e in self.rows(
            "SELECT * FROM entries WHERE active=1 AND review=0 AND kind='expense' AND area IN ('academia','baile') AND period=?", (source,)))
        row = self.db.execute('SELECT value FROM preferences WHERE key=?', ('budget:'+month,)).fetchone()
        saved = json.loads(row['value']) if row else None
        legacy = bool(saved and saved.get('basis_version') != 2)
        if legacy:
            # Preserve the original income and percentages; apply the corrected cost basis.
            saved = dict(saved, income=saved['amount'], business_expenses=expenses,
                         amount=max(0, saved['amount']-expenses), basis_version=2)
        return dict(source=source, received=total, business_expenses=expenses,
                    available=max(0, total-expenses), deficit=max(0, expenses-total),
                    saved=saved, legacy_adjusted=legacy)

    def save_budget(self, p):
        period = month(p.get('month', ''))
        rows = p.get('allocations')
        if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
            raise ValueError('Añade entre 1 y 100 categorías.')
        allocations = []
        for r in rows:
            category = self.db.execute("SELECT id FROM categories WHERE id=? AND area='personal' AND kind='expense'", (r.get('category_id'),)).fetchone()
            if not category:
                raise ValueError('Elige categorías de gasto Personal.')
            allocations.append(dict(category_id=category['id'], bps=percent(r.get('percent', 0))))
        if len({r['category_id'] for r in allocations}) != len(allocations) or sum(r['bps'] for r in allocations) > 10000:
            raise ValueError('No repitas categorías ni superes el 100 %.')
        state = self.budget_state(period)
        saved = state['saved']
        amount = saved['amount'] if saved else state['available']
        budget = dict(amount=amount, source=state['source'], allocations=allocations, basis_version=2,
                      income=saved['income'] if saved else state['received'],
                      business_expenses=saved['business_expenses'] if saved else state['business_expenses'])
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO preferences(key,value) VALUES (?,?)', ('budget:'+period,json.dumps(budget)))
            self.log('budget', dict(month=period, **budget))

    def save_course(self, p):
        name, ownership = clean(p.get('name'),100), p.get('ownership')
        year, semester = int(p.get('year',0)), int(p.get('semester',0))
        if not name or ownership not in ('own','external') or not 2000 <= year <= 2200 or semester not in (1,2):
            raise ValueError('Indica nombre, curso académico, cuatrimestre y tipo de asignatura.')
        bps = percent(p.get('teacher_percent',self.prefs()['teacher_share']/100)) if ownership=='external' else 0
        ident = p.get('id') or uuid.uuid4().hex
        old = self.db.execute('SELECT * FROM courses WHERE id=?',(ident,)).fetchone()
        with self.db:
            if old:
                if any(old[k] != v for k,v in (('ownership',ownership),('year',year),('semester',semester))) and self.db.execute('SELECT 1 FROM entries WHERE course_id=?',(ident,)).fetchone():
                    raise ValueError('Para cambiar tipo o cuatrimestre de una asignatura con registros, crea otra. Conservamos su historial.')
                self.db.execute('UPDATE courses SET name=?,year=?,semester=?,ownership=?,teacher=?,teacher_bps=? WHERE id=?',
                                (name,year,semester,ownership,clean(p.get('teacher'),100),bps,ident))
            else:
                self.db.execute('INSERT INTO courses VALUES (?,?,?,?,?,?,?,1)',(ident,name,year,semester,ownership,clean(p.get('teacher'),100),bps))
            self.log('course',{'id':ident,'teacher_bps':bps})
        return ident

    def _validate_entry(self, p):
        prefs = self.prefs()
        area, kind = p.get('area'), p.get('kind')
        if area not in AREAS or kind not in ('income','expense'):
            raise ValueError('Selecciona área y tipo de actividad.')
        period, day = month(p.get('period')), valid_date(p.get('date'))
        gross = cents(p.get('gross_value'))
        if gross <= 0:
            raise ValueError('El importe bruto/total debe ser mayor que cero.')
        refund = int(bool(p.get('refund'))) if kind=='expense' else 0
        method = p.get('method') or ('own' if kind=='income' and area=='academia' else 'shared' if area=='academia' else 'individual')
        course_id = p.get('course_id') or None
        course = self.db.execute('SELECT * FROM courses WHERE id=?',(course_id,)).fetchone() if course_id else None
        if course_id and (not course or area!='academia' or kind!='income'):
            raise ValueError('La asignatura solo se asigna a un ingreso de Academia.')
        if course:
            method = course['ownership']
            allowed = [f"{course['year']}-{m:02d}" for m in range(9,13)] if course['semester']==1 else [f"{course['year']+1}-{m:02d}" for m in range(1,6)]
            if period not in allowed:
                raise ValueError('El mes no pertenece al cuatrimestre de esa asignatura.')
        if area=='academia' and kind=='income' and method not in ('own','external'):
            raise ValueError('Elige asignatura propia o externa.')
        if area=='academia' and kind=='expense' and method not in ('shared','individual'):
            raise ValueError('Elige gasto compartido o individual.')
        if area=='baile' and method not in ('shared','individual'):
            raise ValueError('En Baile elige individual o compartido.')
        if method=='external' and not course:
            raise ValueError('Selecciona una asignatura externa para calcular el reparto.')
        teacher = percent(p.get('teacher_percent',course['teacher_bps']/100 if course else 0)) if method=='external' else 0
        default_mine = prefs['my_share'] if area=='academia' else 5000
        mine = percent(p.get('my_percent',default_mine/100)) if method in ('external','shared') else 10000
        if area=='personal':
            method, mine, teacher = 'individual',10000,0
        tax = percent(p.get('tax_percent',0)) if kind=='income' and method!='external' else 0
        if tax >= 10000 or (tax and mine!=10000):
            raise ValueError('La retención de esta versión se registra en ingresos íntegramente tuyos; debe ser inferior al 100 %.')
        withheld = proportion(gross,tax)
        cat = p.get('category_id') or None
        category = None
        if cat:
            category = self.db.execute('SELECT * FROM categories WHERE id=?',(cat,)).fetchone()
            if not category or category['area']!=area or category['kind']!=kind:
                raise ValueError('La categoría no corresponde al área y tipo.')
        description = clean(p.get('description'),200) or (course['name']+' · '+period if course else
            category['name'] if category else ('Ingreso' if kind=='income' else 'Devolución' if refund else 'Gasto')+' de '+{'academia':'Academia','baile':'Baile','personal':'Personal'}[area])
        holder = p.get('holder','me')
        if holder not in ('me','partner') or (area=='personal' and holder!='me'):
            raise ValueError('Selecciona quién cobra o paga.')
        return dict(period=period,date=day,area=area,kind=kind,method=method,course_id=course_id,
                    description=description,category_id=cat,gross=gross,tax_bps=tax,withholding=withheld,
                    my_bps=mine,teacher_bps=teacher,holder=holder,refund=refund,notes=clean(p.get('notes'),1000))

    def _insert_entry(self, values, source='manual', review=0):
        ident = uuid.uuid4().hex
        fields = dict(values,id=ident,source=source,review=review,created=datetime.now().isoformat())
        self.db.execute('INSERT INTO entries ('+','.join(fields)+') VALUES ('+','.join('?' for _ in fields)+')',tuple(fields.values()))
        return ident

    def _paid(self, ident):
        row = self.db.execute('SELECT external_paid FROM entries WHERE id=?',(ident,)).fetchone()
        bank = self.db.execute('SELECT COALESCE(SUM(l.amount),0) FROM entry_links l JOIN transactions t ON t.id=l.tx_id WHERE l.entry_id=? AND t.active=1',(ident,)).fetchone()[0]
        return (row[0] if row else 0)+bank

    def _link(self, entry_id, tx_id, amount):
        e = self.db.execute('SELECT * FROM entries WHERE id=? AND active=1',(entry_id,)).fetchone()
        t = self.db.execute('SELECT * FROM transactions WHERE id=? AND active=1',(tx_id,)).fetchone()
        if not e or not t or t['link_id'] or t['kind'] not in ('income','expense') or e['holder']!='me':
            raise ValueError('Selecciona un registro activo cobrado/pagado por ti y un movimiento externo sin vínculo.')
        expected_sign = 1 if e['kind']=='income' or e['refund'] else -1
        if t['amount']*expected_sign<=0:
            raise ValueError('El signo del movimiento no coincide con el registro.')
        used = self.db.execute('SELECT COALESCE(SUM(amount),0) FROM entry_links WHERE tx_id=?',(tx_id,)).fetchone()[0]
        if type(amount) is not int or amount<=0 or used+amount>abs(t['amount']) or self._paid(entry_id)+amount>e['gross']-e['withholding']:
            raise ValueError('El importe supera lo disponible en el banco o lo pendiente del registro.')
        self.db.execute('INSERT INTO entry_links VALUES (?,?,?) ON CONFLICT(entry_id,tx_id) DO UPDATE SET amount=amount+excluded.amount',(entry_id,tx_id,amount))

    def save_entry(self, p):
        values = self._validate_entry(p)
        ident = p.get('id')
        with self.db:
            if ident:
                old = self.db.execute('SELECT * FROM entries WHERE id=? AND active=1',(ident,)).fetchone()
                if not old:
                    raise ValueError('Registro inexistente.')
                if self._paid(ident)>values['gross']-values['withholding']:
                    raise ValueError('El líquido es menor que lo ya cobrado/pagado. Desvincula el cobro o revisa bruto y retención.')
                old_sign=1 if old['kind']=='income' or old['refund'] else -1
                new_sign=1 if values['kind']=='income' or values['refund'] else -1
                if self._paid(ident) and (old['holder']!=values['holder'] or old_sign!=new_sign):
                    raise ValueError('Desvincula primero los cobros/pagos antes de cambiar quién paga o el sentido del movimiento.')
                if self.db.execute('SELECT 1 FROM settlements WHERE entry_id=? AND active=1',(ident,)).fetchone() and any(old[k]!=values[k] for k in ('gross','teacher_bps','method','holder')):
                    raise ValueError('Anula primero los pagos al profesor antes de cambiar este reparto.')
                self.db.execute('UPDATE entries SET '+','.join(k+'=?' for k in values)+',review=0 WHERE id=?',(*values.values(),ident))
                self.log('edit_activity',dict(old))
            else:
                ident = self._insert_entry(values)
                if p.get('cash_status')=='paid':
                    self._record_cash(ident,p)
                self.log('activity',{'id':ident})
        return ident

    def _record_cash(self, ident, p):
        e = dict(self.db.execute('SELECT * FROM entries WHERE id=? AND active=1',(ident,)).fetchone() or {})
        if not e:
            raise ValueError('Registro inexistente.')
        remaining = e['gross']-e['withholding']-self._paid(ident)
        amount = cents(p['cash_value']) if p.get('cash_value') else remaining
        if amount<=0 or amount>remaining:
            raise ValueError('El importe debe ser positivo y no superar lo pendiente.')
        if e['holder']=='partner':
            self.db.execute('UPDATE entries SET external_paid=external_paid+? WHERE id=?',(amount,ident))
            self.db.execute('INSERT INTO external_cash VALUES (?,?,?,?)',(uuid.uuid4().hex,ident,valid_date(p.get('cash_date') or e['date']),amount))
        else:
            tx = super()._insert({'date':p.get('cash_date') or e['date'],'area':e['area'],'account_id':p.get('account_id'),
                'kind':e['kind'],'amount':amount if e['kind']=='income' or e['refund'] else -amount,
                'description':e['description'],'category_id':e['category_id'],'notes':'Cobro/pago manual de actividad'})
            self._link(ident,tx,amount)

    def record_cash(self,p):
        with self.db:
            self._record_cash(p.get('id'),p)
            self.log('record_cash',{'entry':p.get('id')})

    def _from_bank(self, t, options=None):
        options=options or {}
        values=self._validate_entry(dict(area=t['area'],kind=t['kind'],period=options.get('period') or t['date'][:7],
            date=t['date'],gross_value=str(Decimal(abs(t['amount']))/100),description=t['description'],category_id=t.get('category_id'),
            holder='me',refund=t['kind']=='expense' and t['amount']>0,notes=t.get('notes',''),
            **{k:options[k] for k in ('method','course_id','my_percent','teacher_percent') if k in options}))
        ident=self._insert_entry(values,source='bank',review=int(bool(options.get('review'))))
        self._link(ident,t['id'],abs(t['amount']))
        return ident

    def _insert(self,p,linked=False):
        ident=super()._insert(p,linked)
        if not linked and p['kind'] in ('income','expense'):
            t=dict(self.db.execute('SELECT * FROM transactions WHERE id=?',(ident,)).fetchone())
            self._from_bank(t,p.get('activity'))
        return ident

    def transaction(self,p):
        with self.db:
            if p.get('id') and self.db.execute('SELECT 1 FROM entry_links WHERE tx_id=?',(p['id'],)).fetchone():
                raise ValueError('Este movimiento tiene un registro de actividad. Edita el registro desde Actividad; el banco conserva su importe real.')
            return super().transaction(p)

    def _drop_bank_links(self, tx_ids):
        for ident in tx_ids:
            linked=self.rows('SELECT e.id,e.source FROM entries e JOIN entry_links l ON l.entry_id=e.id WHERE l.tx_id=?',(ident,))
            self.db.execute('DELETE FROM entry_links WHERE tx_id=?',(ident,))
            for e in linked:
                if e['source']=='bank' and not self.db.execute('SELECT 1 FROM entry_links WHERE entry_id=?',(e['id'],)).fetchone():
                    self.db.execute('UPDATE entries SET active=0 WHERE id=?',(e['id'],))
            self.db.execute('UPDATE settlements SET active=0 WHERE tx_id=?',(ident,))

    def delete(self,p):
        with self.db:
            t=self.db.execute('SELECT * FROM transactions WHERE id=? AND active=1',(p.get('id'),)).fetchone()
            ids=[r['id'] for r in self.rows('SELECT id FROM transactions WHERE link_id=?',(t['link_id'],))] if t and t['link_id'] else [p.get('id')]
            super().delete(p)
            self._drop_bank_links(ids)

    def delete_entry(self,p):
        with self.db:
            ident=p.get('id')
            if self.db.execute('SELECT 1 FROM settlements WHERE entry_id=? AND active=1',(ident,)).fetchone():
                raise ValueError('Anula primero las liquidaciones del profesor asociadas.')
            self.db.execute('DELETE FROM entry_links WHERE entry_id=?',(ident,))
            self.db.execute('UPDATE entries SET active=0 WHERE id=?',(ident,))
            self.log('void_activity',{'id':ident,'bank_preserved':True})

    def link_existing(self,p):
        with self.db:
            for ident in p.get('ids',[]):
                if self.db.execute("SELECT 1 FROM entries e JOIN entry_links l ON l.entry_id=e.id WHERE l.tx_id=? AND e.source!='bank'",(ident,)).fetchone():
                    raise ValueError('Desvincula este movimiento de su actividad antes de convertirlo en traspaso.')
            super().link_existing(p)
            self._drop_bank_links(p['ids'])

    def import_rows(self,p):
        rows=p.get('rows',[])
        if not rows or len(rows)>10000:
            raise ValueError('Selecciona entre 1 y 10.000 filas válidas.')
        batch=uuid.uuid4().hex
        with self.db:
            self.db.execute('INSERT INTO batches VALUES (?,?,?,1)',(batch,clean(p.get('name'),150),datetime.now().isoformat()))
            for row in rows:
                payload={k:row.get(k) for k in ('date','account_id','area','kind','amount','description','notes','category_id','source_key')}
                payload['batch_id']=batch
                tx=super()._insert(payload)
                if row.get('entry_id'):
                    self._link(row['entry_id'],tx,abs(row['amount']))
                elif row.get('treatment')!='bank_only':
                    self._from_bank({**payload,'id':tx},row.get('activity'))
            self.log('import',{'batch_id':batch,'count':len(rows)})
        return {'count':len(rows)}

    def undo_import(self,p):
        with self.db:
            ids=[r['id'] for r in self.rows('SELECT id FROM transactions WHERE batch_id=? AND active=1',(p.get('id'),))]
            super().undo_import(p)
            self._drop_bank_links(ids)

    def reconcile(self,p):
        """Una fila bancaria puede cubrir varias asignaturas; admite cobros parciales."""
        tx=p.get('tx_id')
        with self.db:
            if p.get('replace_automatic'):
                for r in self.rows('SELECT e.* FROM entries e JOIN entry_links l ON l.entry_id=e.id WHERE l.tx_id=?',(tx,)):
                    if r['source']!='bank':
                        raise ValueError('Este movimiento ya está conciliado con una actividad manual. Desvincúlala primero.')
                self._drop_bank_links([tx])
            for link in p.get('links',[]):
                self._link(link['entry_id'],tx,cents(link['value']))
            self.log('reconcile',{'tx_id':tx})

    def unlink(self,p):
        with self.db:
            self.db.execute('DELETE FROM entry_links WHERE tx_id=? AND entry_id=?',(p.get('tx_id'),p.get('entry_id')))
            self.log('unlink',p)

    def mark_external_unpaid(self,p):
        with self.db:
            self.db.execute('UPDATE entries SET external_paid=0 WHERE id=? AND holder=\'partner\'',(p.get('id'),))
            self.db.execute('DELETE FROM external_cash WHERE entry_id=?',(p.get('id'),))

    def classify_bank(self,p):
        with self.db:
            t=self.db.execute('SELECT * FROM transactions WHERE id=? AND active=1',(p.get('tx_id'),)).fetchone()
            if not t or t['link_id'] or t['kind'] not in ('income','expense') or self.db.execute('SELECT 1 FROM entry_links WHERE tx_id=?',(t['id'],)).fetchone():
                raise ValueError('Elige un ingreso/gasto bancario aún sin asignar.')
            return self._from_bank(dict(t))

    def settle(self,p):
        area,role,direction,holder=p.get('area'),p.get('role','partner'),p.get('direction','to_partner'),p.get('holder','me')
        day=valid_date(p.get('date'));amount=cents(p.get('value'))
        if area not in ('academia','baile') or role not in ('partner','teacher') or direction not in ('to_partner','from_partner') or holder not in ('me','partner') or amount<=0:
            raise ValueError('Revisa área, sentido e importe de la liquidación.')
        entry_id=p.get('entry_id') or None
        if role=='teacher':
            e=self.db.execute("SELECT * FROM entries WHERE id=? AND active=1 AND method='external'",(entry_id,)).fetchone()
            if not e or e['area']!=area:
                raise ValueError('Selecciona un ingreso de asignatura externa.')
            already=self.db.execute('SELECT COALESCE(SUM(amount),0) FROM settlements WHERE entry_id=? AND active=1',(entry_id,)).fetchone()[0]
            if amount+already>proportion(e['gross'],e['teacher_bps']):
                raise ValueError('El pago supera la parte calculada para el profesor.')
            if self._paid(entry_id)<e['gross']-e['withholding']:
                raise ValueError('Registra primero el cobro completo de esta asignatura para liquidar al profesor.')
            direction='to_partner'
        elif entry_id:
            raise ValueError('La liquidación entre socios no lleva asignatura.')
        tx=None
        with self.db:
            if role=='partner' or holder=='me':
                if p.get('tx_id'):
                    t=self.db.execute('SELECT * FROM transactions WHERE id=? AND active=1',(p['tx_id'],)).fetchone()
                    sign=1 if direction=='from_partner' else -1
                    if not t or t['link_id'] or t['amount']!=sign*amount or self.db.execute('SELECT 1 FROM settlements WHERE tx_id=? AND active=1',(t['id'],)).fetchone():
                        raise ValueError('El movimiento bancario no coincide con la liquidación o ya está utilizado.')
                    if self.db.execute("SELECT 1 FROM entry_links l JOIN entries e ON e.id=l.entry_id WHERE l.tx_id=? AND e.source!='bank'",(t['id'],)).fetchone():
                        raise ValueError('Desvincula primero la actividad manual de ese movimiento.')
                    tx=t['id'];self._drop_bank_links([tx])
                    self.db.execute("UPDATE transactions SET kind='transfer',category_id=NULL WHERE id=?",(tx,))
                else:
                    tx=super()._insert({'date':day,'area':area,'account_id':p.get('account_id'),'kind':'transfer',
                        'amount':amount if direction=='from_partner' else -amount,'description':'Liquidación '+('profesor' if role=='teacher' else 'socio/pareja')},linked=True)
            ident=uuid.uuid4().hex
            self.db.execute('INSERT INTO settlements VALUES (?,?,?,?,?,?,?,?,?,?,1)',(ident,day,area,role,direction,amount,holder,entry_id,tx,clean(p.get('notes'),500)))
            self.log('settlement',{'id':ident})
        return ident

    def delete_settlement(self,p):
        with self.db:
            s=self.db.execute('SELECT * FROM settlements WHERE id=? AND active=1',(p.get('id'),)).fetchone()
            if not s:
                raise ValueError('Liquidación inexistente.')
            self.db.execute('UPDATE settlements SET active=0 WHERE id=?',(s['id'],))
            if s['tx_id']:
                self.db.execute('UPDATE transactions SET active=0 WHERE id=?',(s['tx_id'],))

    def state(self, selected_month):
        data=super().state(selected_month)
        entries=self.rows('SELECT e.*,c.name course,c.year,c.semester,c.teacher,cat.name category FROM entries e LEFT JOIN courses c ON c.id=e.course_id LEFT JOIN categories cat ON cat.id=e.category_id WHERE e.active=1 ORDER BY e.period DESC,e.date DESC,e.created DESC')
        links=self.rows('SELECT l.* FROM entry_links l JOIN transactions t ON t.id=l.tx_id WHERE t.active=1')
        for e in entries:
            e.update(entry_values(e));e['paid']=e['external_paid']+sum(l['amount'] for l in links if l['entry_id']==e['id'])
            e['pending']=e['expected']-e['paid']
        settlements=self.rows('SELECT * FROM settlements WHERE active=1 ORDER BY date DESC')
        external_cash=self.rows('SELECT * FROM external_cash')
        tx_dates={t['id']:t['date'] for t in data['transactions']}
        summary={a:dict(income=0,expense=0,teacher=0,margin=0,my_income=0,my_expense=0,withholding=0,my_result=0,my_available=0,pending=0,review=0) for a in ('all',*AREAS)}
        balances={a:0 for a in ('academia','baile')}
        for e in entries:
            if e['period']==selected_month:
                for area in ('all',e['area']):
                    if e['review']:
                        summary[area]['review']+=1
                    else:
                        for k in summary[area]:
                            if k!='review':summary[area][k]+=e[k]
            # Saldo de reparto sobre cobros/pagos registrados hasta el cierre.
            if e['area'] in balances and not e['review'] and e['date']<=selected_month+'-31' and e['paid']:
                paid=sum(c['amount'] for c in external_cash if c['entry_id']==e['id'] and c['date']<=selected_month+'-31')
                paid+=sum(l['amount'] for l in links if l['entry_id']==e['id'] and tx_dates[l['tx_id']]<=selected_month+'-31')
                ratio=Decimal(paid)/e['expected']
                my_net=e['my_income']-e['withholding'] if e['kind']=='income' else e['my_expense']
                other=e['other_income'] if e['kind']=='income' else e['other_expense']
                component=other if e['holder']=='me' else my_net
                allocated=int((Decimal(component)*ratio).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
                sign=(-1 if e['kind']=='income' else 1) if e['holder']=='me' else (1 if e['kind']=='income' else -1)
                balances[e['area']]+=sign*allocated
        by_id={e['id']:e for e in entries}
        for s in settlements:
            if s['date']>selected_month+'-31':continue
            if s['role']=='partner':balances[s['area']]+=s['amount'] if s['direction']=='to_partner' else -s['amount']
            else:
                e=by_id.get(s['entry_id'])
                if e and e['holder']!=s['holder']:
                    balances[s['area']]+=s['amount'] if s['holder']=='me' else -s['amount']
        data['budget']=self.budget_state(selected_month)
        y, m = map(int, selected_month.split('-'))
        data['received']=self.budget_state(f'{y+(m==12):04d}-{m%12+1:02d}')['received']
        data['finance']=dict(entries=entries,courses=self.rows('SELECT * FROM courses ORDER BY year DESC,semester,name'),links=links,
                             settlements=settlements,preferences=self.prefs(),summary=summary,balances=balances)
        return data

    def export_activity(self):
        out=io.StringIO(newline='');writer=csv.writer(out,delimiter=';')
        fields=['period','area','kind','description','course','gross','tax_bps','withholding','my_bps','teacher_bps','my_income','my_expense','my_available','holder','paid','pending','review']
        writer.writerow(fields)
        for e in self.state(date.today().strftime('%Y-%m'))['finance']['entries']:
            row=[]
            for k in fields:
                v=e.get(k) or ''
                if k in ('gross','withholding','my_income','my_expense','my_available','paid','pending','tax_bps','my_bps','teacher_bps'):v=str(Decimal(e[k])/100).replace('.',',')
                elif str(v).startswith(('=','+','-','@','\t','\r')):v="'"+str(v)
                row.append(v)
            writer.writerow(row)
        return ('\ufeff'+out.getvalue()).encode()


def seed_demo(store):
    if store.db.execute("SELECT 1 FROM preferences WHERE key='demo_v2'").fetchone():return
    today=date.today();year=today.year if today.month>=9 else today.year-1
    # Demo en un cuatrimestre válido, con un mes mostrado en la interfaz.
    prefix=f'{year}-09' if today.month not in range(1,6) and today.month not in range(9,13) else today.strftime('%Y-%m')
    sem=1 if int(prefix[5:])>=9 else 2
    with store.db:
        own=store.save_course({'name':'Estadística · DEMO','year':year,'semester':sem,'ownership':'own'})
        external=store.save_course({'name':'Redes móviles · DEMO','year':year,'semester':sem,'ownership':'external','teacher':'Profesor de ejemplo','teacher_percent':'65'})
        second=store.save_course({'name':'Cálculo · DEMO','year':year,'semester':2 if sem==1 else 1,'ownership':'own'})
        common={'date':prefix+'-10','period':prefix,'cash_status':'paid','holder':'me'}
        store.save_entry({**common,'area':'academia','kind':'income','course_id':own,'gross_value':'1000','tax_percent':'15','account_id':'academia'})
        store.save_entry({**common,'area':'academia','kind':'income','course_id':external,'gross_value':'1000','my_percent':'17','teacher_percent':'65','account_id':'academia'})
        store.save_entry({**common,'area':'academia','kind':'expense','method':'shared','description':'Plataformas · DEMO','gross_value':'100','my_percent':'17','account_id':'academia'})
        store.save_entry({**common,'area':'baile','kind':'income','method':'shared','description':'Evento compartido · DEMO','gross_value':'300','my_percent':'50','category_id':store.category('baile','income','Eventos'),'account_id':'baile'})
        store.save_entry({**common,'area':'baile','kind':'income','method':'individual','description':'Privada individual · DEMO','gross_value':'80','category_id':store.category('baile','income','Clases privadas'),'account_id':'baile'})
        store.save_entry({**common,'area':'baile','kind':'expense','method':'shared','description':'Sala compartida · DEMO','gross_value':'100','my_percent':'50','category_id':store.category('baile','expense','Salas'),'account_id':'baile'})
        store.save_entry({**common,'area':'personal','kind':'expense','description':'Supermercado · DEMO','gross_value':'120','account_id':'personal'})
        store.db.execute("INSERT INTO preferences VALUES ('demo_v2',?)",(prefix,))
