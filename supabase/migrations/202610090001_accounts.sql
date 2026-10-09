-- Generado por scripts/generate_supabase_schema.py; revisar antes de aplicar.

begin;

create table public.mc_head (owner_id uuid primary key references auth.users(id) on delete cascade, revision bigint not null default 0, updated_at timestamptz not null default now());

create table public.mc_operations (owner_id uuid not null references auth.users(id) on delete cascade, operation_id uuid not null, revision bigint not null, digest text not null, primary key(owner_id,operation_id));

create table public.mc_backups (owner_id uuid not null references auth.users(id) on delete cascade, kind text not null check(kind in ('daily','restore')), saved_at timestamptz not null default now(), snapshot jsonb not null, primary key(owner_id,kind));

create table public.mc_accounts (
  owner_id uuid not null references auth.users(id) on delete cascade,
  "id" text not null,
  "name" text not null,
  "area" text not null,
  "opening" bigint not null,
  "opening_date" date not null,
  primary key(owner_id,"id"),
  check("opening" between -100000000000 and 100000000000),
  check(area in ('academia','baile','personal'))
);

create table public.mc_categories (
  owner_id uuid not null references auth.users(id) on delete cascade,
  "id" text not null,
  "name" text not null,
  "area" text not null,
  "kind" text not null,
  primary key(owner_id,"id"),
  unique(owner_id,area,kind,name),
  check(area in ('academia','baile','personal'))
);

create table public.mc_people (
  owner_id uuid not null references auth.users(id) on delete cascade,
  "id" text not null,
  "name" text not null,
  "is_me" bigint not null,
  primary key(owner_id,"id"),
  unique(owner_id,name),
  check("is_me" in (0,1))
);

create table public.mc_preferences (
  owner_id uuid not null references auth.users(id) on delete cascade,
  "key" text not null,
  "value" text not null,
  primary key(owner_id,"key")
);

create table public.mc_courses (
  owner_id uuid not null references auth.users(id) on delete cascade,
  "id" text not null,
  "name" text not null,
  "year" bigint not null,
  "semester" bigint not null,
  "ownership" text not null,
  "teacher" text not null,
  "teacher_bps" bigint not null,
  "active" bigint not null,
  primary key(owner_id,"id"),
  check("teacher_bps" between 0 and 10000),
  check("active" in (0,1)),
  check(year between 2000 and 2200),
  check(semester in (1,2)),
  check(ownership in ('own','external'))
);

create table public.mc_batches (
  owner_id uuid not null references auth.users(id) on delete cascade,
  "id" text not null,
  "name" text not null,
  "created" text not null,
  "active" bigint not null,
  primary key(owner_id,"id"),
  check("active" in (0,1))
);

create table public.mc_audit (
  owner_id uuid not null references auth.users(id) on delete cascade,
  "id" bigint not null,
  "created" text not null,
  "action" text not null,
  "detail" text not null,
  primary key(owner_id,"id")
);

create table public.mc_shares (
  owner_id uuid not null references auth.users(id) on delete cascade,
  "month" text not null,
  "area" text not null,
  "person_id" text not null,
  "bps" bigint not null,
  primary key(owner_id,"month","area","person_id"),
  foreign key(owner_id,"person_id") references public.mc_people(owner_id,"id") deferrable initially deferred,
  check("month" ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
  check("bps" between 0 and 10000),
  check(area in ('academia','baile','personal'))
);

create table public.mc_transactions (
  owner_id uuid not null references auth.users(id) on delete cascade,
  "id" text not null,
  "date" date not null,
  "account_id" text not null,
  "area" text not null,
  "kind" text not null,
  "category_id" text,
  "description" text not null,
  "notes" text not null,
  "amount" bigint not null,
  "link_id" text,
  "person_id" text,
  "batch_id" text,
  "source_key" text,
  "active" bigint not null,
  "created" text not null,
  primary key(owner_id,"id"),
  foreign key(owner_id,"batch_id") references public.mc_batches(owner_id,"id") deferrable initially deferred,
  foreign key(owner_id,"person_id") references public.mc_people(owner_id,"id") deferrable initially deferred,
  foreign key(owner_id,"category_id") references public.mc_categories(owner_id,"id") deferrable initially deferred,
  foreign key(owner_id,"account_id") references public.mc_accounts(owner_id,"id") deferrable initially deferred,
  check("amount" between -100000000000 and 100000000000),
  check("active" in (0,1)),
  check(area in ('academia','baile','personal')),
  check(amount<>0),
  check(kind in ('income','expense','distribution','transfer','funding','reimbursement','remuneration'))
);

create table public.mc_rules (
  owner_id uuid not null references auth.users(id) on delete cascade,
  "id" text not null,
  "term" text not null,
  "area" text not null,
  "category_id" text not null,
  primary key(owner_id,"id"),
  foreign key(owner_id,"category_id") references public.mc_categories(owner_id,"id") deferrable initially deferred,
  check(area in ('academia','baile','personal'))
);

create table public.mc_entries (
  owner_id uuid not null references auth.users(id) on delete cascade,
  "id" text not null,
  "period" text not null,
  "date" date not null,
  "area" text not null,
  "kind" text not null,
  "method" text not null,
  "course_id" text,
  "description" text not null,
  "category_id" text,
  "gross" bigint not null,
  "tax_bps" bigint not null,
  "withholding" bigint not null,
  "my_bps" bigint not null,
  "teacher_bps" bigint not null,
  "holder" text not null,
  "external_paid" bigint not null,
  "refund" bigint not null,
  "source" text not null,
  "review" bigint not null,
  "notes" text not null,
  "active" bigint not null,
  "created" text not null,
  primary key(owner_id,"id"),
  foreign key(owner_id,"category_id") references public.mc_categories(owner_id,"id") deferrable initially deferred,
  foreign key(owner_id,"course_id") references public.mc_courses(owner_id,"id") deferrable initially deferred,
  check("period" ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
  check("gross" between -100000000000 and 100000000000),
  check("tax_bps" between 0 and 10000),
  check("withholding" between -100000000000 and 100000000000),
  check("my_bps" between 0 and 10000),
  check("teacher_bps" between 0 and 10000),
  check("external_paid" between -100000000000 and 100000000000),
  check("refund" in (0,1)),
  check("review" in (0,1)),
  check("active" in (0,1)),
  check(area in ('academia','baile','personal')),
  check(gross>0 and withholding>=0 and withholding<gross and external_paid>=0),
  check(kind in ('income','expense')),
  check(holder in ('me','partner')),
  check(method in ('own','external','shared','individual')),
  check(withholding=round(gross::numeric*tax_bps/10000)),
  check(refund=0 or kind='expense'),
  check(tax_bps=0 or (kind='income' and my_bps=10000 and method<>'external')),
  check(method not in ('own','individual') or (my_bps=10000 and teacher_bps=0)),
  check(method='external' or teacher_bps=0),
  check(area<>'personal' or (method='individual' and my_bps=10000 and holder='me' and course_id is null)),
  check(method<>'external' or course_id is not null)
);

create table public.mc_entry_links (
  owner_id uuid not null references auth.users(id) on delete cascade,
  "entry_id" text not null,
  "tx_id" text not null,
  "amount" bigint not null,
  primary key(owner_id,"entry_id","tx_id"),
  foreign key(owner_id,"tx_id") references public.mc_transactions(owner_id,"id") deferrable initially deferred,
  foreign key(owner_id,"entry_id") references public.mc_entries(owner_id,"id") deferrable initially deferred,
  check("amount" between -100000000000 and 100000000000),
  check(amount>0)
);

create table public.mc_settlements (
  owner_id uuid not null references auth.users(id) on delete cascade,
  "id" text not null,
  "date" date not null,
  "area" text not null,
  "role" text not null,
  "direction" text not null,
  "amount" bigint not null,
  "holder" text not null,
  "entry_id" text,
  "tx_id" text,
  "notes" text not null,
  "active" bigint not null,
  primary key(owner_id,"id"),
  foreign key(owner_id,"tx_id") references public.mc_transactions(owner_id,"id") deferrable initially deferred,
  foreign key(owner_id,"entry_id") references public.mc_entries(owner_id,"id") deferrable initially deferred,
  check("amount" between -100000000000 and 100000000000),
  check("active" in (0,1)),
  check(area in ('academia','baile','personal')),
  check(amount>0),
  check(role in ('partner','teacher')),
  check(direction in ('to_partner','from_partner')),
  check(holder in ('me','partner')),
  check((role='teacher' and entry_id is not null) or (role='partner' and entry_id is null))
);

create table public.mc_external_cash (
  owner_id uuid not null references auth.users(id) on delete cascade,
  "id" text not null,
  "entry_id" text not null,
  "date" date not null,
  "amount" bigint not null,
  primary key(owner_id,"id"),
  foreign key(owner_id,"entry_id") references public.mc_entries(owner_id,"id") deferrable initially deferred,
  check("amount" between -100000000000 and 100000000000),
  check(amount>0)
);

alter table public.mc_head enable row level security;

revoke all on public.mc_head from anon, authenticated;

grant select on public.mc_head to authenticated;

create policy own_rows on public.mc_head for select to authenticated using ((select auth.uid())=owner_id);

alter table public.mc_operations enable row level security;

revoke all on public.mc_operations from anon, authenticated;

grant select on public.mc_operations to authenticated;

create policy own_rows on public.mc_operations for select to authenticated using ((select auth.uid())=owner_id);

alter table public.mc_backups enable row level security;

revoke all on public.mc_backups from anon, authenticated;

grant select on public.mc_backups to authenticated;

create policy own_rows on public.mc_backups for select to authenticated using ((select auth.uid())=owner_id);

alter table public.mc_accounts enable row level security;

revoke all on public.mc_accounts from anon, authenticated;

grant select on public.mc_accounts to authenticated;

create policy own_rows on public.mc_accounts for select to authenticated using ((select auth.uid())=owner_id);

alter table public.mc_categories enable row level security;

revoke all on public.mc_categories from anon, authenticated;

grant select on public.mc_categories to authenticated;

create policy own_rows on public.mc_categories for select to authenticated using ((select auth.uid())=owner_id);

alter table public.mc_people enable row level security;

revoke all on public.mc_people from anon, authenticated;

grant select on public.mc_people to authenticated;

create policy own_rows on public.mc_people for select to authenticated using ((select auth.uid())=owner_id);

alter table public.mc_preferences enable row level security;

revoke all on public.mc_preferences from anon, authenticated;

grant select on public.mc_preferences to authenticated;

create policy own_rows on public.mc_preferences for select to authenticated using ((select auth.uid())=owner_id);

alter table public.mc_courses enable row level security;

revoke all on public.mc_courses from anon, authenticated;

grant select on public.mc_courses to authenticated;

create policy own_rows on public.mc_courses for select to authenticated using ((select auth.uid())=owner_id);

alter table public.mc_batches enable row level security;

revoke all on public.mc_batches from anon, authenticated;

grant select on public.mc_batches to authenticated;

create policy own_rows on public.mc_batches for select to authenticated using ((select auth.uid())=owner_id);

alter table public.mc_audit enable row level security;

revoke all on public.mc_audit from anon, authenticated;

grant select on public.mc_audit to authenticated;

create policy own_rows on public.mc_audit for select to authenticated using ((select auth.uid())=owner_id);

alter table public.mc_shares enable row level security;

revoke all on public.mc_shares from anon, authenticated;

grant select on public.mc_shares to authenticated;

create policy own_rows on public.mc_shares for select to authenticated using ((select auth.uid())=owner_id);

alter table public.mc_transactions enable row level security;

revoke all on public.mc_transactions from anon, authenticated;

grant select on public.mc_transactions to authenticated;

create policy own_rows on public.mc_transactions for select to authenticated using ((select auth.uid())=owner_id);

alter table public.mc_rules enable row level security;

revoke all on public.mc_rules from anon, authenticated;

grant select on public.mc_rules to authenticated;

create policy own_rows on public.mc_rules for select to authenticated using ((select auth.uid())=owner_id);

alter table public.mc_entries enable row level security;

revoke all on public.mc_entries from anon, authenticated;

grant select on public.mc_entries to authenticated;

create policy own_rows on public.mc_entries for select to authenticated using ((select auth.uid())=owner_id);

alter table public.mc_entry_links enable row level security;

revoke all on public.mc_entry_links from anon, authenticated;

grant select on public.mc_entry_links to authenticated;

create policy own_rows on public.mc_entry_links for select to authenticated using ((select auth.uid())=owner_id);

alter table public.mc_settlements enable row level security;

revoke all on public.mc_settlements from anon, authenticated;

grant select on public.mc_settlements to authenticated;

create policy own_rows on public.mc_settlements for select to authenticated using ((select auth.uid())=owner_id);

alter table public.mc_external_cash enable row level security;

revoke all on public.mc_external_cash from anon, authenticated;

grant select on public.mc_external_cash to authenticated;

create policy own_rows on public.mc_external_cash for select to authenticated using ((select auth.uid())=owner_id);

create index mc_transactions_date on public.mc_transactions(owner_id,date,active);

create index mc_entries_period on public.mc_entries(owner_id,period,active);

create unique index mc_settlement_tx on public.mc_settlements(owner_id,tx_id) where active=1 and tx_id is not null;


create function public.mc_snapshot(p_owner uuid) returns jsonb
language plpgsql security definer set search_path='' as $$
declare result jsonb := '{}'::jsonb; t text; rows jsonb;
begin
  if auth.uid() is null or auth.uid()<>p_owner then raise exception 'MC_LOGIN'; end if;
  foreach t in array array['accounts','categories','people','preferences','courses','batches','audit','shares','transactions','rules','entries','entry_links','settlements','external_cash'] loop
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
  delete from public.mc_external_cash where owner_id=uid;
  delete from public.mc_settlements where owner_id=uid;
  delete from public.mc_entry_links where owner_id=uid;
  delete from public.mc_entries where owner_id=uid;
  delete from public.mc_rules where owner_id=uid;
  delete from public.mc_transactions where owner_id=uid;
  delete from public.mc_shares where owner_id=uid;
  delete from public.mc_audit where owner_id=uid;
  delete from public.mc_batches where owner_id=uid;
  delete from public.mc_courses where owner_id=uid;
  delete from public.mc_preferences where owner_id=uid;
  delete from public.mc_people where owner_id=uid;
  delete from public.mc_categories where owner_id=uid;
  delete from public.mc_accounts where owner_id=uid;
  if jsonb_typeof(p_snapshot->'tables'->'accounts') is distinct from 'array' then raise exception 'MC_INVALID'; end if;
  insert into public.mc_accounts(owner_id,"id","name","area","opening","opening_date") select uid,"id","name","area","opening","opening_date" from jsonb_to_recordset(p_snapshot->'tables'->'accounts') as rows("id" text,"name" text,"area" text,"opening" bigint,"opening_date" date);
  if jsonb_typeof(p_snapshot->'tables'->'categories') is distinct from 'array' then raise exception 'MC_INVALID'; end if;
  insert into public.mc_categories(owner_id,"id","name","area","kind") select uid,"id","name","area","kind" from jsonb_to_recordset(p_snapshot->'tables'->'categories') as rows("id" text,"name" text,"area" text,"kind" text);
  if jsonb_typeof(p_snapshot->'tables'->'people') is distinct from 'array' then raise exception 'MC_INVALID'; end if;
  insert into public.mc_people(owner_id,"id","name","is_me") select uid,"id","name","is_me" from jsonb_to_recordset(p_snapshot->'tables'->'people') as rows("id" text,"name" text,"is_me" bigint);
  if jsonb_typeof(p_snapshot->'tables'->'preferences') is distinct from 'array' then raise exception 'MC_INVALID'; end if;
  insert into public.mc_preferences(owner_id,"key","value") select uid,"key","value" from jsonb_to_recordset(p_snapshot->'tables'->'preferences') as rows("key" text,"value" text);
  if jsonb_typeof(p_snapshot->'tables'->'courses') is distinct from 'array' then raise exception 'MC_INVALID'; end if;
  insert into public.mc_courses(owner_id,"id","name","year","semester","ownership","teacher","teacher_bps","active") select uid,"id","name","year","semester","ownership","teacher","teacher_bps","active" from jsonb_to_recordset(p_snapshot->'tables'->'courses') as rows("id" text,"name" text,"year" bigint,"semester" bigint,"ownership" text,"teacher" text,"teacher_bps" bigint,"active" bigint);
  if jsonb_typeof(p_snapshot->'tables'->'batches') is distinct from 'array' then raise exception 'MC_INVALID'; end if;
  insert into public.mc_batches(owner_id,"id","name","created","active") select uid,"id","name","created","active" from jsonb_to_recordset(p_snapshot->'tables'->'batches') as rows("id" text,"name" text,"created" text,"active" bigint);
  if jsonb_typeof(p_snapshot->'tables'->'audit') is distinct from 'array' then raise exception 'MC_INVALID'; end if;
  insert into public.mc_audit(owner_id,"id","created","action","detail") select uid,"id","created","action","detail" from jsonb_to_recordset(p_snapshot->'tables'->'audit') as rows("id" bigint,"created" text,"action" text,"detail" text);
  if jsonb_typeof(p_snapshot->'tables'->'shares') is distinct from 'array' then raise exception 'MC_INVALID'; end if;
  insert into public.mc_shares(owner_id,"month","area","person_id","bps") select uid,"month","area","person_id","bps" from jsonb_to_recordset(p_snapshot->'tables'->'shares') as rows("month" text,"area" text,"person_id" text,"bps" bigint);
  if jsonb_typeof(p_snapshot->'tables'->'transactions') is distinct from 'array' then raise exception 'MC_INVALID'; end if;
  insert into public.mc_transactions(owner_id,"id","date","account_id","area","kind","category_id","description","notes","amount","link_id","person_id","batch_id","source_key","active","created") select uid,"id","date","account_id","area","kind","category_id","description","notes","amount","link_id","person_id","batch_id","source_key","active","created" from jsonb_to_recordset(p_snapshot->'tables'->'transactions') as rows("id" text,"date" date,"account_id" text,"area" text,"kind" text,"category_id" text,"description" text,"notes" text,"amount" bigint,"link_id" text,"person_id" text,"batch_id" text,"source_key" text,"active" bigint,"created" text);
  if jsonb_typeof(p_snapshot->'tables'->'rules') is distinct from 'array' then raise exception 'MC_INVALID'; end if;
  insert into public.mc_rules(owner_id,"id","term","area","category_id") select uid,"id","term","area","category_id" from jsonb_to_recordset(p_snapshot->'tables'->'rules') as rows("id" text,"term" text,"area" text,"category_id" text);
  if jsonb_typeof(p_snapshot->'tables'->'entries') is distinct from 'array' then raise exception 'MC_INVALID'; end if;
  insert into public.mc_entries(owner_id,"id","period","date","area","kind","method","course_id","description","category_id","gross","tax_bps","withholding","my_bps","teacher_bps","holder","external_paid","refund","source","review","notes","active","created") select uid,"id","period","date","area","kind","method","course_id","description","category_id","gross","tax_bps","withholding","my_bps","teacher_bps","holder","external_paid","refund","source","review","notes","active","created" from jsonb_to_recordset(p_snapshot->'tables'->'entries') as rows("id" text,"period" text,"date" date,"area" text,"kind" text,"method" text,"course_id" text,"description" text,"category_id" text,"gross" bigint,"tax_bps" bigint,"withholding" bigint,"my_bps" bigint,"teacher_bps" bigint,"holder" text,"external_paid" bigint,"refund" bigint,"source" text,"review" bigint,"notes" text,"active" bigint,"created" text);
  if jsonb_typeof(p_snapshot->'tables'->'entry_links') is distinct from 'array' then raise exception 'MC_INVALID'; end if;
  insert into public.mc_entry_links(owner_id,"entry_id","tx_id","amount") select uid,"entry_id","tx_id","amount" from jsonb_to_recordset(p_snapshot->'tables'->'entry_links') as rows("entry_id" text,"tx_id" text,"amount" bigint);
  if jsonb_typeof(p_snapshot->'tables'->'settlements') is distinct from 'array' then raise exception 'MC_INVALID'; end if;
  insert into public.mc_settlements(owner_id,"id","date","area","role","direction","amount","holder","entry_id","tx_id","notes","active") select uid,"id","date","area","role","direction","amount","holder","entry_id","tx_id","notes","active" from jsonb_to_recordset(p_snapshot->'tables'->'settlements') as rows("id" text,"date" date,"area" text,"role" text,"direction" text,"amount" bigint,"holder" text,"entry_id" text,"tx_id" text,"notes" text,"active" bigint);
  if jsonb_typeof(p_snapshot->'tables'->'external_cash') is distinct from 'array' then raise exception 'MC_INVALID'; end if;
  insert into public.mc_external_cash(owner_id,"id","entry_id","date","amount") select uid,"id","entry_id","date","amount" from jsonb_to_recordset(p_snapshot->'tables'->'external_cash') as rows("id" text,"entry_id" text,"date" date,"amount" bigint);
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


revoke all on function public.mc_snapshot(uuid) from public,anon,authenticated;

revoke all on function public.mc_load() from public,anon,authenticated;

grant execute on function public.mc_load() to authenticated;

revoke all on function public.mc_backup(text) from public,anon,authenticated;

grant execute on function public.mc_backup(text) to authenticated;

revoke all on function public.mc_commit(bigint,uuid,jsonb,boolean) from public,anon,authenticated;

grant execute on function public.mc_commit(bigint,uuid,jsonb,boolean) to authenticated;

commit;
