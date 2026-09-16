-- SQL FINAL REVISADO. NÃO EXECUTADO. Baseado no schema real informado pelo usuário.
-- Não reaplicar supabase_schema.sql. Nenhuma migração de dados.
begin;
create table if not exists public.teaching_cost_snapshots (
  year integer not null check (year = 2027),
  version integer not null check (version > 0),
  status text not null check (status in ('draft','approved')),
  closed_at timestamptz not null,
  created_at timestamptz not null default now(),
  created_by uuid not null references auth.users(id),
  source_ref text not null check (length(trim(source_ref)) > 0),
  source_sha256 text not null check (source_sha256 ~ '^[a-f0-9]{64}$'),
  payload jsonb not null,
  primary key (year,version),
  check ((payload->>'target_year')::integer is not distinct from year),
  check ((payload->>'validated_cost_cents')::bigint is not distinct from 2567735::bigint),
  check ((payload->'summary'->>'reconciled_professors')::integer is not distinct from 50),
  check (jsonb_array_length(payload->'classes') is not distinct from 41)
);
create table if not exists public.financial_evidence (
  year integer not null,
  version integer not null check (version > 0),
  snapshot_version integer not null,
  status text not null check (status in ('draft','approved')),
  closed_at timestamptz not null,
  created_at timestamptz not null default now(),
  created_by uuid not null references auth.users(id),
  source_ref text not null check (length(trim(source_ref)) > 0),
  source_sha256 text not null check (source_sha256 ~ '^[a-f0-9]{64}$'),
  payload jsonb not null,
  primary key (year,version),
  foreign key (year,snapshot_version) references public.teaching_cost_snapshots(year,version),
  check ((payload->>'year')::integer is not distinct from year)
);
create index if not exists financial_evidence_snapshot_idx on public.financial_evidence(year,snapshot_version);
alter table public.teaching_cost_snapshots enable row level security;
alter table public.financial_evidence enable row level security;
-- Remove apenas privilégios dos papéis de navegador nas duas tabelas novas.
revoke all on public.teaching_cost_snapshots, public.financial_evidence from public, anon, authenticated;
grant select on public.teaching_cost_snapshots, public.financial_evidence to authenticated;

-- Reexecução: mantém políticas compatíveis; divergências interrompem a transação.
do $policies$
declare
  t text;
  p text;
  existing record;
begin
  for t,p in select * from (values
    ('teaching_cost_snapshots','teaching_snapshot_master_read'),
    ('financial_evidence','financial_evidence_master_read')
  ) as expected(table_name,policy_name)
  loop
    if exists (select 1 from pg_catalog.pg_policies
      where schemaname='public' and tablename=t and policyname<>p) then
      raise exception 'Política inesperada em %. Revisar antes de aplicar.', t;
    end if;
    select * into existing from pg_catalog.pg_policies
      where schemaname='public' and tablename=t and policyname=p;
    if found then
      if existing.cmd <> 'SELECT'
        or existing.roles <> array['authenticated']::name[]
        or existing.permissive <> 'PERMISSIVE'
        or existing.with_check is not null
        or lower(regexp_replace(existing.qual, '\s+|\(|\)|::text|public\.', '', 'g'))
           is distinct from 'status=''approved''andis_master' then
        raise exception 'Política incompatível em %. Nenhuma substituição automática.', t;
      end if;
    else
      execute format(
        'create policy %I on public.%I for select to authenticated using (status = %L and public.is_master())',
        p,t,'approved'
      );
    end if;
  end loop;
end;
$policies$;
commit;
