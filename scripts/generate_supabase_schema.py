#!/usr/bin/env python3
"""Genera la migración PostgreSQL a partir del esquema contable original."""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cloud_bridge import TABLES
from finance import FinanceStore


def generate():
    sql = ["-- Generado por scripts/generate_supabase_schema.py; revisar antes de aplicar.",
           "begin;", "create table public.mc_head (owner_id uuid primary key references auth.users(id) on delete cascade, revision bigint not null default 0, updated_at timestamptz not null default now());",
           "create table public.mc_operations (owner_id uuid not null references auth.users(id) on delete cascade, operation_id uuid not null, revision bigint not null, digest text not null, primary key(owner_id,operation_id));",
           "create table public.mc_backups (owner_id uuid not null references auth.users(id) on delete cascade, kind text not null check(kind in ('daily','restore')), saved_at timestamptz not null default now(), snapshot jsonb not null, primary key(owner_id,kind));"]
    records = {}
    with tempfile.TemporaryDirectory() as directory:
        store = FinanceStore(Path(directory) / 'schema.sqlite3')
        for table in TABLES:
            info = [dict(row) for row in store.db.execute(f'PRAGMA table_info({table})')]
            types = {row['name']: ('bigint' if row['type'] == 'INTEGER' else 'text') for row in info}
            for name in ('date', 'opening_date'):
                if name in types:
                    types[name] = 'date'
            records[table] = types
            fields = ['owner_id uuid not null references auth.users(id) on delete cascade']
            for row in info:
                name = row['name']
                required = ' not null' if row['notnull'] or row['pk'] else ''
                fields.append(f'"{name}" {types[name]}{required}')
            pk = [r['name'] for r in sorted(info, key=lambda r: r['pk']) if r['pk']]
            fields.append('primary key(owner_id,' + ','.join(f'"{c}"' for c in pk) + ')')
            for row in store.db.execute(f'PRAGMA foreign_key_list({table})'):
                fields.append(f'foreign key(owner_id,"{row["from"]}") references public.mc_{row["table"]}(owner_id,"{row["to"]}") deferrable initially deferred')
            if table == 'categories':
                fields.append('unique(owner_id,area,kind,name)')
            if table == 'people':
                fields.append('unique(owner_id,name)')
            for name in types:
                if name in ('active', 'refund', 'review', 'is_me'):
                    fields.append(f'check("{name}" in (0,1))')
                if name.endswith('_bps') or name == 'bps':
                    fields.append(f'check("{name}" between 0 and 10000)')
                if name in ('amount', 'opening', 'gross', 'withholding', 'external_paid'):
                    fields.append(f'check("{name}" between -100000000000 and 100000000000)')
                if name in ('month', 'period'):
                    fields.append(f'check("{name}" ~ \'^[0-9]{{4}}-(0[1-9]|1[0-2])$\')')
            if 'area' in types:
                fields.append("check(area in ('academia','baile','personal'))")
            if table in ('entry_links', 'external_cash', 'settlements'):
                fields.append('check(amount>0)')
            if table == 'entries':
                fields += ['check(gross>0 and withholding>=0 and withholding<gross and external_paid>=0)',
                           "check(kind in ('income','expense'))", "check(holder in ('me','partner'))",
                           "check(method in ('own','external','shared','individual'))",
                           'check(withholding=round(gross::numeric*tax_bps/10000))',
                           "check(refund=0 or kind='expense')",
                           "check(tax_bps=0 or (kind='income' and my_bps=10000 and method<>'external'))",
                           "check(method not in ('own','individual') or (my_bps=10000 and teacher_bps=0))",
                           "check(method='external' or teacher_bps=0)",
                           "check(area<>'personal' or (method='individual' and my_bps=10000 and holder='me' and course_id is null))",
                           "check(method<>'external' or course_id is not null)"]
            if table == 'transactions':
                fields += ['check(amount<>0)', "check(kind in ('income','expense','distribution','transfer','funding','reimbursement','remuneration'))"]
            if table == 'settlements':
                fields += ["check(role in ('partner','teacher'))", "check(direction in ('to_partner','from_partner'))", "check(holder in ('me','partner'))",
                           "check((role='teacher' and entry_id is not null) or (role='partner' and entry_id is null))"]
            if table == 'courses':
                fields += ['check(year between 2000 and 2200)', 'check(semester in (1,2))', "check(ownership in ('own','external'))"]
            sql.append(f'create table public.mc_{table} (\n  ' + ',\n  '.join(fields) + '\n);')
        store.close()
    for table in ('head', 'operations', 'backups', *TABLES):
        sql += [f'alter table public.mc_{table} enable row level security;',
                f'revoke all on public.mc_{table} from anon, authenticated;',
                f'grant select on public.mc_{table} to authenticated;',
                f'create policy own_rows on public.mc_{table} for select to authenticated using ((select auth.uid())=owner_id);']
    sql += ['create index mc_transactions_date on public.mc_transactions(owner_id,date,active);',
            'create index mc_entries_period on public.mc_entries(owner_id,period,active);',
            'create unique index mc_settlement_tx on public.mc_settlements(owner_id,tx_id) where active=1 and tx_id is not null;']
    sql.append("""
create function public.mc_snapshot(p_owner uuid) returns jsonb
language plpgsql security definer set search_path='' as $$
declare result jsonb := '{}'::jsonb; t text; rows jsonb;
begin
  if auth.uid() is null or auth.uid()<>p_owner then raise exception 'MC_LOGIN'; end if;
  foreach t in array array[TABLE_LIST] loop
    execute format('select coalesce(jsonb_agg(to_jsonb(r)-''owner_id''),''[]''::jsonb) from public.mc_%I r where owner_id=$1',t) into rows using p_owner;
    result:=jsonb_set(result,array[t],rows);
  end loop;
  return jsonb_build_object('schema_version',1,'tables',result);
end $$;

create function public.mc_load() returns jsonb
language plpgsql security definer set search_path='' as $$
declare uid uuid:=auth.uid(); h public.mc_head;
begin
  if uid is null then raise exception 'MC_LOGIN'; end if;
  select * into h from public.mc_head where owner_id=uid for share;
  if not found then return jsonb_build_object('revision',0,'snapshot',null,'updated_at',null); end if;
  return jsonb_build_object('revision',h.revision,'snapshot',public.mc_snapshot(uid),'updated_at',h.updated_at);
end $$;

create function public.mc_backup(p_kind text) returns jsonb
language plpgsql security definer set search_path='' as $$
declare result jsonb;
begin
  if auth.uid() is null then raise exception 'MC_LOGIN'; end if;
  select snapshot into result from public.mc_backups where owner_id=auth.uid() and kind=p_kind;
  if result is null then raise exception 'MC_NO_BACKUP'; end if;
  return result;
end $$;

create function public.mc_commit(p_expected_revision bigint,p_operation_id uuid,p_snapshot jsonb,p_restore boolean default false) returns jsonb
language plpgsql security definer set search_path='' as $$
declare uid uuid:=auth.uid(); current_revision bigint; prior public.mc_operations; old_snapshot jsonb; digest text:=md5(p_snapshot::text);
begin
  if uid is null then raise exception 'MC_LOGIN'; end if;
  if p_expected_revision is null or p_expected_revision<0 or p_operation_id is null or p_snapshot->>'schema_version' is distinct from '1' or jsonb_typeof(p_snapshot->'tables') is distinct from 'object' or octet_length(p_snapshot::text)>15728640 then raise exception 'MC_INVALID'; end if;
  insert into public.mc_head(owner_id) values(uid) on conflict do nothing;
  select revision into current_revision from public.mc_head where owner_id=uid for update;
  select * into prior from public.mc_operations where owner_id=uid and operation_id=p_operation_id;
  if found then
    if prior.digest<>digest then raise exception 'MC_INVALID_RETRY'; end if;
    return jsonb_build_object('revision',prior.revision,'replayed',true);
  end if;
  if current_revision<>p_expected_revision then raise exception 'MC_CONFLICT'; end if;
  if (select count(*) from jsonb_object_keys(p_snapshot->'tables'))<>14 then raise exception 'MC_INVALID'; end if;
  if current_revision>0 then
    old_snapshot:=public.mc_snapshot(uid);
    insert into public.mc_backups(owner_id,kind,snapshot) values(uid,'daily',old_snapshot)
      on conflict(owner_id,kind) do update set snapshot=excluded.snapshot,saved_at=now()
      where (public.mc_backups.saved_at at time zone 'UTC')::date < (now() at time zone 'UTC')::date;
    if p_restore then
      insert into public.mc_backups(owner_id,kind,snapshot) values(uid,'restore',old_snapshot)
        on conflict(owner_id,kind) do update set snapshot=excluded.snapshot,saved_at=now();
    end if;
  end if;
  DELETE_STATEMENTS
  INSERT_STATEMENTS
  -- Control en servidor de cobros y asignaciones, además de las restricciones y FK.
  if exists (
    select 1 from public.mc_entries e where e.owner_id=uid and e.active=1 and
    e.external_paid + coalesce((select sum(l.amount) from public.mc_entry_links l join public.mc_transactions t on t.owner_id=l.owner_id and t.id=l.tx_id where l.owner_id=uid and l.entry_id=e.id and t.active=1),0)>e.gross-e.withholding
  ) or exists (
    select 1 from public.mc_transactions t where t.owner_id=uid and t.active=1 and
    coalesce((select sum(l.amount) from public.mc_entry_links l where l.owner_id=uid and l.tx_id=t.id),0)>abs(t.amount)
  ) then raise exception 'MC_INVALID_ALLOCATION'; end if;
  if exists(select 1 from public.mc_shares where owner_id=uid group by month,area having sum(bps)>10000)
  or exists(
    select 1 from public.mc_entries e where e.owner_id=uid and e.active=1 and
    coalesce((select sum(s.amount) from public.mc_settlements s where s.owner_id=uid and s.entry_id=e.id and s.active=1 and s.role='teacher'),0)>round(e.gross::numeric*e.teacher_bps/10000)
  ) then raise exception 'MC_INVALID_ALLOCATION'; end if;
  if exists(
    select 1 from public.mc_entries e join public.mc_categories c on c.owner_id=e.owner_id and c.id=e.category_id
    where e.owner_id=uid and (c.area<>e.area or c.kind<>e.kind)
  ) or exists(
    select 1 from public.mc_transactions t join public.mc_categories c on c.owner_id=t.owner_id and c.id=t.category_id
    where t.owner_id=uid and (c.area<>t.area or c.kind<>t.kind)
  ) or exists(
    select 1 from public.mc_transactions t join public.mc_accounts a on a.owner_id=t.owner_id and a.id=t.account_id
    where t.owner_id=uid and t.date<a.opening_date
  ) or exists(
    select 1 from public.mc_entries e join public.mc_courses c on c.owner_id=e.owner_id and c.id=e.course_id
    where e.owner_id=uid and (e.area<>'academia' or e.kind<>'income' or e.method<>c.ownership or not
      ((c.semester=1 and e.period between c.year::text||'-09' and c.year::text||'-12') or
       (c.semester=2 and e.period between (c.year+1)::text||'-01' and (c.year+1)::text||'-05')))
  ) then raise exception 'MC_INVALID'; end if;
  set constraints all immediate;
  update public.mc_head set revision=current_revision+1,updated_at=now() where owner_id=uid;
  insert into public.mc_operations values(uid,p_operation_id,current_revision+1,digest);
  return jsonb_build_object('revision',current_revision+1,'replayed',false);
end $$;
""")
    inserts = []
    for table, columns in records.items():
        column_list = ','.join(f'"{name}"' for name in columns)
        shape = ','.join(f'"{name}" {typ}' for name, typ in columns.items())
        inserts.append(f"if jsonb_typeof(p_snapshot->'tables'->'{table}') is distinct from 'array' then raise exception 'MC_INVALID'; end if;\n  insert into public.mc_{table}(owner_id,{column_list}) select uid,{column_list} from jsonb_to_recordset(p_snapshot->'tables'->'{table}') as rows({shape});")
    sql[-1] = sql[-1].replace('TABLE_LIST', ','.join(f"'{t}'" for t in TABLES))
    sql[-1] = sql[-1].replace('DELETE_STATEMENTS', '\n  '.join(f'delete from public.mc_{t} where owner_id=uid;' for t in reversed(TABLES)))
    sql[-1] = sql[-1].replace('INSERT_STATEMENTS', '\n  '.join(inserts))
    sql += ["revoke all on function public.mc_snapshot(uuid) from public,anon,authenticated;"]
    for function in ('mc_load()', 'mc_backup(text)', 'mc_commit(bigint,uuid,jsonb,boolean)'):
        sql += [f'revoke all on function public.{function} from public,anon,authenticated;',
                f'grant execute on function public.{function} to authenticated;']
    sql += ['commit;']
    return '\n\n'.join(sql) + '\n'


if __name__ == '__main__':
    target = ROOT / 'supabase' / 'migrations' / '202610090001_accounts.sql'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(generate())
    print('Migración generada:', target.relative_to(ROOT))
