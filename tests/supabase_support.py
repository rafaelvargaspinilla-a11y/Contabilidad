"""PostgreSQL aislado con roles Auth para verificar SQL y protocolo del cliente."""
import json
import os
import uuid
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[1]
ACTOR_A = '11111111-1111-4111-8111-111111111111'
ACTOR_B = '22222222-2222-4222-8222-222222222222'


class TestDatabase:
    def __init__(self):
        self.admin_dsn = os.environ.get('MISCUENTAS_TEST_DATABASE_URL', 'postgresql://postgres@127.0.0.1:55432/postgres')
        self.name = 'mis_cuentas_test_' + uuid.uuid4().hex
        with psycopg.connect(self.admin_dsn, autocommit=True) as connection:
            for role in ('anon', 'authenticated'):
                if not connection.execute('select 1 from pg_roles where rolname=%s', [role]).fetchone():
                    connection.execute(sql.SQL('create role {}').format(sql.Identifier(role)))
            connection.execute(sql.SQL('create database {}').format(sql.Identifier(self.name)))
        self.dsn = psycopg.conninfo.make_conninfo(self.admin_dsn, dbname=self.name)
        with psycopg.connect(self.dsn, autocommit=True) as connection:
            connection.execute("create schema auth; create table auth.users(id uuid primary key); create function auth.uid() returns uuid language sql stable as $$ select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid $$; grant usage on schema auth to anon,authenticated; grant execute on function auth.uid() to anon,authenticated;")
            connection.execute('insert into auth.users values(%s),(%s)', [ACTOR_A, ACTOR_B])
            connection.execute((ROOT / 'supabase/migrations/202610090001_accounts.sql').read_text())

    def close(self):
        with psycopg.connect(self.admin_dsn, autocommit=True) as connection:
            connection.execute(sql.SQL('drop database {} with (force)').format(sql.Identifier(self.name)))

    def query(self, actor, query, parameters=(), role='authenticated'):
        with psycopg.connect(self.dsn) as connection:
            connection.execute(sql.SQL('set local role {}').format(sql.Identifier(role)))
            connection.execute("select set_config('request.jwt.claim.sub',%s,true)", [actor or ''])
            cursor = connection.execute(query, parameters)
            return cursor.fetchall() if cursor.description else []

    def load(self, actor):
        return self.query(actor, 'select public.mc_load()')[0][0]

    def commit(self, actor, revision, snapshot, operation=None, restore=False):
        return self.query(actor, 'select public.mc_commit(%s,%s,%s,%s)',
            [revision, operation or str(uuid.uuid4()), Jsonb(snapshot), restore])[0][0]

    def rpc(self, actor, name, payload):
        if name == 'mc_load': return self.load(actor)
        if name == 'mc_commit': return self.commit(actor, payload['p_expected_revision'], payload['p_snapshot'], payload['p_operation_id'], payload.get('p_restore', False))
        if name == 'mc_backup': return self.query(actor, 'select public.mc_backup(%s)', [payload['p_kind']])[0][0]
        raise ValueError('RPC no permitida en la prueba.')
