"""Registro de caja en céntimos. Solo biblioteca estándar de Python."""
import csv
import hashlib
import io
import json
import re
import sqlite3
import uuid
from collections import Counter
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

AREAS = ('academia', 'baile', 'personal')
NAMES = {'academia': 'Academia', 'baile': 'Baile', 'personal': 'Personal'}
KINDS = ('income', 'expense', 'distribution', 'transfer', 'funding', 'reimbursement', 'remuneration')


class AtomicConnection(sqlite3.Connection):
    """Los contextos anidados se confirman juntos, mediante savepoints."""
    def __enter__(self):
        scopes = getattr(self, '_scopes', [])
        name = 'sp_' + uuid.uuid4().hex
        self.execute('SAVEPOINT ' + name)
        scopes.append(name)
        self._scopes = scopes
        return self

    def __exit__(self, kind, value, traceback):
        name = self._scopes.pop()
        if kind is not None:
            self.execute('ROLLBACK TO ' + name)
        self.execute('RELEASE ' + name)
        return False


def cents(value):
    s = str(value).strip().replace('€', '').replace('\u00a0', '').replace(' ', '')
    negative = s.startswith('(') and s.endswith(')')
    if negative:
        s = '-' + s[1:-1]
    if ',' in s:
        if '.' in s and s.rfind('.') > s.rfind(','):
            s = s.replace(',', '')
        else:
            s = s.replace('.', '').replace(',', '.')
    try:
        n = Decimal(s)
        if not n.is_finite() or abs(n) > Decimal('1000000000') or n * 100 != (n * 100).to_integral_value():
            raise ValueError()
        return int(n * 100)
    except (InvalidOperation, ValueError):
        raise ValueError('Importe inválido. Usa hasta dos decimales, por ejemplo 1.234,56 o 1234.56.')


def valid_date(value):
    return date.fromisoformat(str(value)).isoformat()


def clean(value, limit=500):
    return str(value or '').strip()[:limit]


def bank_date(value, order='dmy'):
    """Fecha de calendario del extracto, sin desplazarla por la zona horaria."""
    text = clean(value, 100)
    if order not in ('dmy', 'mdy', 'ymd'):
        raise ValueError('Selecciona un formato de fecha válido.')
    # ISO no tiene ambigüedad día/mes: admitirlo con cualquiera de las opciones.
    if re.match(r'^\d{4}-\d{2}-\d{2}(?:[Tt ]|$)', text):
        iso = text[:-1] + '+00:00' if text.endswith(('Z', 'z')) else text
        try:
            return datetime.fromisoformat(iso).date().isoformat()
        except ValueError:
            raise ValueError('Fecha u hora no válida: ' + text)
    formats = {
        'dmy': ('%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y'),
        'mdy': ('%m/%d/%Y', '%m-%d-%Y', '%m/%d/%y'),
        'ymd': ('%Y/%m/%d',),
    }
    for pattern in formats[order]:
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            pass
    raise ValueError('Fecha no reconocida: ' + text)


def fingerprint(account, when, amount, description, occurrence=1, bank_id=''):
    parts = [account, 'bank', bank_id] if bank_id else [account, when, amount, ' '.join(description.lower().split()), occurrence]
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode()).hexdigest()


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=15, factory=AtomicConnection)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS accounts (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, area TEXT NOT NULL,
          opening INTEGER NOT NULL DEFAULT 0, opening_date TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS categories (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, area TEXT NOT NULL, kind TEXT NOT NULL,
          UNIQUE(area,kind,name));
        CREATE TABLE IF NOT EXISTS people (
          id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, is_me INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS shares (
          month TEXT NOT NULL, area TEXT NOT NULL, person_id TEXT NOT NULL REFERENCES people(id),
          bps INTEGER NOT NULL CHECK(bps>=0 AND bps<=10000), PRIMARY KEY(month,area,person_id));
        CREATE TABLE IF NOT EXISTS batches (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, created TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS transactions (
          id TEXT PRIMARY KEY, date TEXT NOT NULL, account_id TEXT NOT NULL REFERENCES accounts(id),
          area TEXT NOT NULL, kind TEXT NOT NULL, category_id TEXT REFERENCES categories(id),
          description TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '', amount INTEGER NOT NULL,
          link_id TEXT, person_id TEXT REFERENCES people(id), batch_id TEXT REFERENCES batches(id),
          source_key TEXT, active INTEGER NOT NULL DEFAULT 1, created TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS tx_date ON transactions(date,active);
        CREATE INDEX IF NOT EXISTS tx_source ON transactions(source_key);
        CREATE TABLE IF NOT EXISTS rules (
          id TEXT PRIMARY KEY, term TEXT NOT NULL, area TEXT NOT NULL, category_id TEXT NOT NULL REFERENCES categories(id));
        CREATE TABLE IF NOT EXISTS audit (
          id INTEGER PRIMARY KEY, created TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL);
        ''')
        if not self.db.execute('SELECT 1 FROM accounts LIMIT 1').fetchone():
            for a in AREAS:
                self.db.execute('INSERT INTO accounts VALUES (?,?,?,?,?)', (a, 'Cuenta ' + NAMES[a], a, 0, '2000-01-01'))
            catalog = {
              'academia': {'income': ['Cursos', 'Otros ingresos'], 'expense': ['Profesores', 'Plataformas', 'Publicidad', 'Gestoría', 'Otros gastos']},
              'baile': {'income': ['Clases', 'Privadas', 'Eventos'], 'expense': ['Salas', 'Desplazamientos', 'Formación', 'Otros gastos']},
              'personal': {'income': ['Otros ingresos'], 'expense': ['Vivienda', 'Supermercado', 'Restaurantes', 'Transporte', 'Ocio', 'Suscripciones', 'Salud', 'Otros gastos']}}
            for area, kinds in catalog.items():
                for kind, names in kinds.items():
                    for name in names:
                        self.db.execute('INSERT INTO categories VALUES (?,?,?,?)', (uuid.uuid4().hex, name, area, kind))
            self.db.execute('INSERT OR IGNORE INTO people VALUES (?,?,?)', ('me', 'Yo', 1))
        self.db.commit()

    def close(self):
        self.db.close()

    def rows(self, sql, args=()):
        return [dict(x) for x in self.db.execute(sql, args)]

    def log(self, action, detail):
        self.db.execute('INSERT INTO audit(created,action,detail) VALUES (?,?,?)', (datetime.now().isoformat(), action, json.dumps(detail, ensure_ascii=False)))

    def category(self, area, kind, name):
        r = self.db.execute('SELECT id FROM categories WHERE area=? AND kind=? AND name=?', (area, kind, name)).fetchone()
        return r[0] if r else None

    def add_category(self, p):
        area, kind, name = p.get('area'), p.get('kind'), clean(p.get('name'), 80)
        if area not in AREAS or kind not in ('income', 'expense') or not name:
            raise ValueError('Indica área, tipo y nombre de la categoría.')
        with self.db:
            self.db.execute('INSERT INTO categories VALUES (?,?,?,?)', (uuid.uuid4().hex, name, area, kind))

    def add_account(self, p):
        name, area = clean(p.get('name'), 80), p.get('area')
        if not name or area not in AREAS:
            raise ValueError('Indica nombre y titular/área de la cuenta.')
        opening, day = cents(p.get('opening', '0')), valid_date(p.get('opening_date'))
        ident = p.get('id')
        with self.db:
            if ident:
                old = self.db.execute('SELECT * FROM accounts WHERE id=?', (ident,)).fetchone()
                if not old:
                    raise ValueError('Cuenta inexistente.')
                if old['area'] != area:
                    raise ValueError('El área titular de una cuenta creada no se modifica. Crea otra cuenta.')
                if self.db.execute('SELECT 1 FROM transactions WHERE account_id=? AND active=1 AND date<?', (ident, day)).fetchone():
                    raise ValueError('Hay movimientos anteriores a ese saldo inicial. Elige una fecha anterior.')
                self.db.execute('UPDATE accounts SET name=?,opening=?,opening_date=? WHERE id=?', (name, opening, day, ident))
            else:
                self.db.execute('INSERT INTO accounts VALUES (?,?,?,?,?)', (uuid.uuid4().hex, name, area, opening, day))
            self.log('account', {'id': ident, 'name': name})

    def add_person(self, p):
        name = clean(p.get('name'), 80)
        if not name:
            raise ValueError('Escribe un nombre.')
        with self.db:
            self.db.execute('INSERT INTO people VALUES (?,?,0)', (uuid.uuid4().hex, name))

    def validate_transaction(self, p, linked=False):
        area, kind = p.get('area'), p.get('kind')
        when = valid_date(p.get('date'))
        if area not in AREAS or kind not in KINDS:
            raise ValueError('Área o tipo inválido.')
        account = self.db.execute('SELECT * FROM accounts WHERE id=?', (p.get('account_id'),)).fetchone()
        if not account:
            raise ValueError('Selecciona una cuenta.')
        if when < account['opening_date']:
            raise ValueError('La fecha del movimiento es anterior al saldo inicial de la cuenta.')
        amount = p.get('amount')
        if type(amount) is not int or not amount or abs(amount) > 100000000000:
            raise ValueError('El importe debe ser distinto de cero.')
        if kind == 'income' and amount < 0:
            raise ValueError('Un ingreso debe ser positivo.')
        cat = p.get('category_id') or None
        if cat:
            c = self.db.execute('SELECT * FROM categories WHERE id=?', (cat,)).fetchone()
            if not c or c['area'] != area or c['kind'] != kind:
                raise ValueError('La categoría no corresponde al área y tipo elegidos.')
        if not linked and kind not in ('income', 'expense', 'distribution'):
            raise ValueError('Utiliza el formulario de pagos internos para ese tipo.')
        if not linked and kind == 'distribution':
            if amount >= 0 or area == 'personal' or not p.get('person_id') or p.get('person_id') == 'me':
                raise ValueError('El reparto externo requiere un destinatario distinto de ti y un área de actividad.')
        if p.get('person_id') and not self.db.execute('SELECT 1 FROM people WHERE id=?', (p['person_id'],)).fetchone():
            raise ValueError('Destinatario inexistente.')
        description = clean(p.get('description'), 200)
        if not description:
            raise ValueError('Escribe un concepto.')
        return (when, account['id'], area, kind, cat, description, clean(p.get('notes'), 1000), amount)

    def _insert(self, p, linked=False):
        fields = self.validate_transaction(p, linked)
        ident = uuid.uuid4().hex
        self.db.execute('''INSERT INTO transactions
        (id,date,account_id,area,kind,category_id,description,notes,amount,link_id,person_id,batch_id,source_key,created)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (ident, *fields, p.get('link_id'), p.get('person_id') or None,
                                               p.get('batch_id'), p.get('source_key'), datetime.now().isoformat()))
        return ident

    def transaction(self, p):
        p = dict(p)
        if 'value' in p:
            n = abs(cents(p['value']))
            p['amount'] = -n if p.get('kind') in ('expense', 'distribution') and not p.get('refund') else n
        with self.db:
            if p.get('id'):
                old = self.db.execute('SELECT * FROM transactions WHERE id=? AND active=1', (p['id'],)).fetchone()
                if not old or old['link_id']:
                    raise ValueError('Para cambiar un pago vinculado, anúlalo y créalo de nuevo.')
                fields = self.validate_transaction(p)
                self.db.execute('''UPDATE transactions SET date=?,account_id=?,area=?,kind=?,category_id=?,description=?,notes=?,amount=?,person_id=? WHERE id=?''', (*fields, p.get('person_id') or None, p['id']))
                ident = p['id']
                self.log('edit', dict(old))
            else:
                ident = self._insert(p)
                self.log('create', {'id': ident})
        return ident

    def move(self, p):
        amount = abs(cents(p.get('value')))
        when = valid_date(p.get('date'))
        src = self.db.execute('SELECT * FROM accounts WHERE id=?', (p.get('from_account'),)).fetchone()
        dst = self.db.execute('SELECT * FROM accounts WHERE id=?', (p.get('to_account'),)).fetchone()
        kind = p.get('kind')
        if not src or not dst or src['id'] == dst['id'] or not amount:
            raise ValueError('Selecciona dos cuentas distintas y un importe mayor que cero.')
        if kind not in ('transfer', 'distribution', 'funding', 'reimbursement', 'remuneration'):
            raise ValueError('Tipo de pago interno inválido.')
        if kind == 'distribution' and (src['area'] == 'personal' or dst['area'] != 'personal'):
            raise ValueError('Un reparto hacia ti va de Academia/Baile a Personal.')
        if kind == 'remuneration' and (src['area'] == 'personal' or dst['area'] != 'personal'):
            raise ValueError('La retribución va de Academia/Baile a Personal.')
        link = uuid.uuid4().hex
        person = 'me' if kind in ('distribution', 'remuneration') else None
        with self.db:
            for account, value in ((src, -amount), (dst, amount)):
                self._insert({'date': when, 'account_id': account['id'], 'area': account['area'], 'kind': kind,
                              'amount': value, 'description': clean(p.get('description')) or 'Pago interno',
                              'link_id': link, 'person_id': person, 'notes': clean(p.get('notes'))}, linked=True)
            self.log('move', {'link_id': link})
        return link

    def link_existing(self, p):
        ids = list(dict.fromkeys(p.get('ids', [])))
        if len(ids) != 2:
            raise ValueError('Selecciona exactamente dos movimientos, uno por cada cuenta.')
        rows = self.rows('SELECT * FROM transactions WHERE id IN (?,?) AND active=1', ids)
        if len(rows) != 2 or any(x['link_id'] for x in rows) or rows[0]['amount'] + rows[1]['amount'] != 0 or rows[0]['account_id'] == rows[1]['account_id']:
            raise ValueError('Deben ser movimientos sin vínculo, de cuentas distintas e importes opuestos iguales.')
        src = next(x for x in rows if x['amount'] < 0)
        dst = next(x for x in rows if x['amount'] > 0)
        kind = p.get('kind')
        if kind not in ('transfer', 'distribution', 'funding', 'reimbursement', 'remuneration'):
            raise ValueError('Tipo inválido.')
        if kind in ('distribution', 'remuneration') and (src['area'] == 'personal' or dst['area'] != 'personal'):
            raise ValueError('El reparto/retribución requiere salida de actividad y entrada en Personal.')
        if src['date'] != dst['date']:
            raise ValueError('Para vincularlos, usa la misma fecha de operación en ambos (conserva la fecha valor original en notas).')
        link = uuid.uuid4().hex
        with self.db:
            for r in rows:
                self.db.execute('UPDATE transactions SET kind=?,category_id=NULL,link_id=?,person_id=? WHERE id=?',
                                (kind, link, 'me' if kind in ('distribution','remuneration') else None, r['id']))
            self.log('link', {'before': rows, 'link_id': link})

    def delete(self, p):
        with self.db:
            r = self.db.execute('SELECT * FROM transactions WHERE id=? AND active=1', (p.get('id'),)).fetchone()
            if not r:
                raise ValueError('Movimiento inexistente.')
            if r['link_id']:
                self.db.execute('UPDATE transactions SET active=0 WHERE link_id=?', (r['link_id'],))
            else:
                self.db.execute('UPDATE transactions SET active=0 WHERE id=?', (r['id'],))
            self.log('delete', dict(r))

    def save_shares(self, p):
        month, area = p.get('month'), p.get('area')
        valid_date(str(month) + '-01')
        if area not in ('academia', 'baile'):
            raise ValueError('Selecciona una actividad.')
        values = [(x['person_id'], cents(x['percent'])) for x in p.get('shares', [])]
        if any(n < 0 or n > 10000 for _, n in values) or sum(n for _, n in values) > 10000:
            raise ValueError('Los porcentajes deben sumar como máximo el 100 %.')
        if len({i for i, _ in values}) != len(values):
            raise ValueError('Hay destinatarios repetidos.')
        with self.db:
            self.db.execute('DELETE FROM shares WHERE month=? AND area=?', (month, area))
            for person, n in values:
                self.db.execute('INSERT INTO shares VALUES (?,?,?,?)', (month, area, person, n))
            self.log('shares', {'area': area, 'month': month, 'shares': values})

    def add_rule(self, p):
        term, area, cat = clean(p.get('term'), 100), p.get('area'), p.get('category_id')
        c = self.db.execute('SELECT * FROM categories WHERE id=?', (cat,)).fetchone()
        if not term or not c or area != c['area']:
            raise ValueError('Elige un texto y una categoría del área.')
        with self.db:
            self.db.execute('INSERT INTO rules VALUES (?,?,?,?)', (uuid.uuid4().hex, term, area, cat))

    def remove_rule(self, p):
        with self.db:
            self.db.execute('DELETE FROM rules WHERE id=?', (p.get('id'),))

    def preview_csv(self, p):
        text = p.get('text', '').lstrip('\ufeff')
        if len(text) > 8_000_000:
            raise ValueError('Máximo 8 MB por archivo.')
        skip = max(0, min(100, int(p.get('skip', 0))))
        lines = text.splitlines(keepends=True)[skip:]
        text = ''.join(lines)
        delimiter = p.get('delimiter')
        if delimiter not in (';', ',', '\t', '|'):
            try:
                delimiter = csv.Sniffer().sniff(text[:8000], delimiters=';,\t|').delimiter
            except csv.Error:
                delimiter = ';'
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        headers = reader.fieldnames or []
        if not headers or len(headers) != len(set(headers)):
            raise ValueError('No se detectan cabeceras únicas. Revisa separador y filas iniciales.')
        raw = list(reader)
        if len(raw) > 10000:
            raise ValueError('Máximo 10.000 filas por importación.')
        if not p.get('mapping'):
            return {'headers': headers, 'sample': raw[:5], 'delimiter': delimiter, 'count': len(raw)}
        m, output, occurrences = p['mapping'], [], Counter()
        account, area = p.get('account_id'), p.get('area')
        rules = self.rows('SELECT r.*,c.kind FROM rules r JOIN categories c ON c.id=r.category_id WHERE r.area=? ORDER BY length(r.term) DESC', (area,))
        existing = {r['source_key'] for r in self.rows('SELECT source_key FROM transactions WHERE active=1 AND account_id=?', (account,))}
        manual = {(r['date'],r['amount'],' '.join(r['description'].lower().split())) for r in self.rows('SELECT date,amount,description FROM transactions WHERE active=1 AND account_id=?', (account,))}
        seen_keys = set()
        for index, r in enumerate(raw):
            item = {'row': index + skip + 2, 'selected': True, 'error': None}
            try:
                day = bank_date(r.get(m.get('date')), p.get('date_format', 'dmy'))
                if m.get('amount'):
                    amount = cents(r.get(m['amount'], ''))
                else:
                    incoming, outgoing = r.get(m.get('inflow'), ''), r.get(m.get('outflow'), '')
                    amount = abs(cents(incoming)) if incoming else 0
                    amount -= abs(cents(outgoing)) if outgoing else 0
                if p.get('flip'):
                    amount = -amount
                desc = clean(r.get(m.get('description')), 200) or 'Sin concepto'
                notes = clean(r.get(m.get('notes')), 1000)
                kind = 'income' if amount > 0 else 'expense'
                cat = None
                for rule in rules:
                    if rule['kind'] == kind and rule['term'].casefold() in desc.casefold():
                        cat = rule['category_id']
                        break
                normalized = ' '.join(desc.lower().split())
                group = (day, amount, normalized)
                occurrences[group] += 1
                source = fingerprint(account, day, amount, desc, occurrences[group], clean(r.get(m.get('bank_id'))))
                duplicate = source in existing or source in seen_keys or group in manual
                seen_keys.add(source)
                item.update({'date': day, 'account_id': account, 'area': area, 'amount': amount, 'kind': kind,
                             'description': desc, 'notes': notes, 'category_id': cat, 'source_key': source,
                             'duplicate': duplicate, 'selected': not duplicate})
                self.validate_transaction(item)
            except (ValueError, TypeError) as exc:
                item['error'], item['selected'] = str(exc), False
            output.append(item)
        return {'rows': output, 'headers': headers, 'count': len(raw), 'delimiter': delimiter}

    def import_rows(self, p):
        rows = p.get('rows', [])
        if not rows or len(rows) > 10000:
            raise ValueError('Selecciona entre 1 y 10.000 movimientos válidos.')
        batch = uuid.uuid4().hex
        with self.db:
            self.db.execute('INSERT INTO batches VALUES (?,?,?,1)', (batch, clean(p.get('name'), 150), datetime.now().isoformat()))
            for r in rows:
                allowed = {k: r.get(k) for k in ('date','account_id','area','amount','kind','description','notes','category_id','source_key')}
                allowed['batch_id'] = batch
                self._insert(allowed)
            self.log('import', {'batch_id': batch, 'count': len(rows)})
        return {'count': len(rows)}

    def undo_import(self, p):
        batch = p.get('id')
        with self.db:
            links = [r['link_id'] for r in self.rows('SELECT DISTINCT link_id FROM transactions WHERE batch_id=? AND active=1 AND link_id IS NOT NULL', (batch,))]
            if links:
                raise ValueError('Este lote contiene pagos vinculados. Anúlalos primero desde Movimientos; se evita dejar una sola mitad del pago.')
            self.db.execute('UPDATE transactions SET active=0 WHERE batch_id=?', (batch,))
            self.db.execute('UPDATE batches SET active=0 WHERE id=?', (batch,))
            self.log('undo_import', {'batch_id': batch})

    def state(self, month):
        valid_date(month + '-01')
        transactions = self.rows('''SELECT t.*,c.name category,a.name account,p.name person FROM transactions t
          JOIN accounts a ON a.id=t.account_id LEFT JOIN categories c ON c.id=t.category_id
          LEFT JOIN people p ON p.id=t.person_id WHERE t.active=1 ORDER BY t.date DESC,t.created DESC''')
        return {'accounts': self.rows('SELECT * FROM accounts ORDER BY area,name'),
                'categories': self.rows('SELECT * FROM categories ORDER BY area,kind,name'),
                'people': self.rows('SELECT * FROM people ORDER BY is_me DESC,name'),
                'transactions': transactions,
                'shares': self.rows('SELECT * FROM shares WHERE month=?', (month,)),
                'rules': self.rows('SELECT r.*,c.name category FROM rules r JOIN categories c ON c.id=r.category_id'),
                'batches': self.rows('SELECT b.*,COUNT(t.id) count FROM batches b LEFT JOIN transactions t ON t.batch_id=b.id AND t.active=1 GROUP BY b.id ORDER BY b.created DESC'),
                'summary': {a: summarize(transactions, month, a) for a in ('all', *AREAS)},
                'data_path': str(self.path)}

    def export_csv(self):
        output = io.StringIO(newline='')
        writer = csv.writer(output, delimiter=';')
        writer.writerow(['id','fecha','cuenta','area','tipo','categoria','concepto','importe_eur','vinculo','destinatario','notas'])
        for r in self.state(date.today().strftime('%Y-%m'))['transactions']:
            cells = [r['id'],r['date'],r['account'],r['area'],r['kind'],r['category'] or '',r['description'],
                     f"{Decimal(r['amount'])/100:.2f}".replace('.', ','),r['link_id'] or '',r['person'] or '',r['notes']]
            # Evitar que una descripción se interprete como fórmula al abrir el CSV.
            for i in (2,5,6,9,10):
                if str(cells[i]).startswith(('=','+','-','@','\t','\r')):
                    cells[i] = "'" + cells[i]
            writer.writerow(cells)
        return ('\ufeff' + output.getvalue()).encode('utf-8')

    def backup(self, dest):
        target = sqlite3.connect(dest)
        try:
            self.db.backup(target)
        finally:
            target.close()


def summarize(transactions, month, area):
    rows = [r for r in transactions if r['date'].startswith(month) and (area == 'all' or r['area'] == area)]
    operational = [r for r in rows if not (area == 'all' and r.get('link_id'))]
    income = sum(r['amount'] for r in operational if r['kind'] == 'income' or (r['kind']=='remuneration' and r['amount']>0))
    expense = -sum(r['amount'] for r in operational if r['kind'] == 'expense' or (r['kind']=='remuneration' and r['amount']<0))
    received = sum(r['amount'] for r in rows if r['kind']=='distribution' and r['amount']>0) if area!='all' else 0
    paid = -sum(r['amount'] for r in rows if r['kind']=='distribution' and r['amount']<0 and (area!='all' or not r.get('link_id')))
    return {'income': income, 'expense': expense, 'result': income - expense,
            'received': received, 'distributed': paid, 'personal_margin': income+received-expense,
            'cashflow': sum(r['amount'] for r in rows), 'uncategorized': sum(1 for r in rows if r['kind'] in ('income','expense') and not r['category_id'])}


def seed_demo(store):
    if store.db.execute('SELECT 1 FROM transactions LIMIT 1').fetchone():
        return
    year, month = date.today().year, date.today().month
    person = 'demo_socio'
    with store.db:
        store.db.execute('INSERT OR IGNORE INTO people VALUES (?,?,0)', (person, 'Otro socio (ejemplo)'))
        store.db.execute("UPDATE accounts SET opening=200000 WHERE area='academia'")
        store.db.execute("UPDATE accounts SET opening=50000 WHERE area='baile'")
        store.db.execute("UPDATE accounts SET opening=300000 WHERE area='personal'")
    for offset in range(3):
        serial = year*12+month-1-offset
        y, m = divmod(serial,12)
        prefix = f'{y:04d}-{m+1:02d}'
        records = [
          ('academia','income','Cursos','Cobros de cursos',620000-offset*40000),
          ('academia','expense','Profesores','Clases de profesores externos',-180000),
          ('academia','expense','Plataformas','Plataformas y vídeo',-24000),
          ('academia','expense','Publicidad','Campañas de captación',-18000),
          ('baile','income','Clases','Clases regulares',130000-offset*8000),
          ('baile','income','Privadas','Clases privadas',45000),
          ('baile','income','Eventos','Evento de baile',30000),
          ('baile','expense','Salas','Alquiler de sala',-22000),
          ('baile','expense','Desplazamientos','Viajes y transporte',-8000),
          ('personal','expense','Vivienda','Vivienda y suministros',-65000),
          ('personal','expense','Supermercado','Compra semanal',-23000),
          ('personal','expense','Restaurantes','Restaurantes y cafés',-12500),
          ('personal','expense','Ocio','Ocio del mes',-9000),
        ]
        for index,(area,kind,category,desc,amount) in enumerate(records):
            store.transaction({'date': prefix+f'-{min(4+index,20):02d}', 'account_id': area, 'area': area,
                               'kind': kind, 'category_id': store.category(area,kind,category),
                               'description': desc+' · DEMO', 'amount': amount})
        store.move({'date':prefix+'-21','from_account':'academia','to_account':'personal','kind':'distribution','value':'1200','description':'Reparto academia · DEMO'})
        store.move({'date':prefix+'-21','from_account':'baile','to_account':'personal','kind':'distribution','value':'1000','description':'Reparto baile · DEMO'})
        store.save_shares({'month':prefix,'area':'academia','shares':[{'person_id':'me','percent':'40'},{'person_id':person,'percent':'60'}]})
        store.save_shares({'month':prefix,'area':'baile','shares':[{'person_id':'me','percent':'100'}]})
