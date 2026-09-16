-- 7&7 — esquema inicial de produção
create extension if not exists pgcrypto;

do $$ begin
  create type public.user_role as enum ('master','promotora','comum');
exception when duplicate_object then null; end $$;
do $$ begin
  create type public.request_status as enum ('pendente','em_andamento','concluido','cancelado');
exception when duplicate_object then null; end $$;
do $$ begin
  create type public.benefit_status as enum ('pendente','entregue','cancelado');
exception when duplicate_object then null; end $$;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  nome text not null,
  email text,
  role public.user_role not null default 'comum',
  setor text,
  ativo boolean not null default true,
  created_at timestamptz not null default now()
);

create table if not exists public.turmas (
  id uuid primary key default gen_random_uuid(),
  serie text not null,
  turma text not null,
  capacidade integer not null default 0,
  matriculados integer not null default 0,
  constraint turmas_capacidade_chk check (capacidade >= 0),
  constraint turmas_matriculados_chk check (matriculados >= 0)
);

create table if not exists public.alunos (
  id uuid primary key default gen_random_uuid(),
  nome text not null,
  tipo_matricula text not null default 'novo',
  turma_id uuid references public.turmas(id) on delete set null,
  data_matricula date not null default current_date,
  responsavel_nome text,
  responsavel_telefone text,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now()
);

create table if not exists public.solicitacoes (
  id uuid primary key default gen_random_uuid(),
  protocolo text not null unique,
  titulo text not null,
  descricao text,
  setor_destino text,
  status public.request_status not null default 'pendente',
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.beneficios_matricula (
  id uuid primary key default gen_random_uuid(),
  aluno_id uuid references public.alunos(id) on delete cascade,
  responsavel_nome text,
  turma text,
  beneficio text not null,
  valor numeric(12,2) not null default 0,
  foto_url text,
  status public.benefit_status not null default 'pendente',
  data_matricula date not null default current_date,
  entregue_em timestamptz,
  assinatura_url text,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now()
);

create table if not exists public.orcamento_contas (
  id uuid primary key default gen_random_uuid(),
  ano integer not null,
  conta text not null,
  subconta text,
  orcado numeric(14,2) not null default 0,
  realizado numeric(14,2) not null default 0,
  unique (ano, conta, subconta)
);

create table if not exists public.orcamento_importacoes (
  id uuid primary key default gen_random_uuid(),
  nome_arquivo text not null,
  hash_arquivo text,
  data_importacao timestamptz not null default now(),
  usuario_id uuid references auth.users(id) on delete set null,
  status text not null default 'processado',
  total_lancado numeric(14,2) not null default 0
);

create table if not exists public.inadimplencia_importacoes (
  id uuid primary key default gen_random_uuid(),
  nome_arquivo text not null,
  tipo text not null check (tipo in ('financeira','contabil','devedores')),
  data_referencia date,
  data_importacao timestamptz not null default now(),
  usuario_id uuid references auth.users(id) on delete set null
);

create table if not exists public.inadimplencia_indicadores (
  id uuid primary key default gen_random_uuid(),
  importacao_id uuid references public.inadimplencia_importacoes(id) on delete cascade,
  percentual numeric(8,3),
  valor_devido numeric(14,2),
  qtd_responsaveis integer,
  qtd_alunos integer,
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;
alter table public.turmas enable row level security;
alter table public.alunos enable row level security;
alter table public.solicitacoes enable row level security;
alter table public.beneficios_matricula enable row level security;
alter table public.orcamento_contas enable row level security;
alter table public.orcamento_importacoes enable row level security;
alter table public.inadimplencia_importacoes enable row level security;
alter table public.inadimplencia_indicadores enable row level security;

create or replace function public.is_master()
returns boolean language sql stable as $$
  select exists(select 1 from public.profiles p where p.id = auth.uid() and p.role = 'master' and p.ativo = true);
$$;

create or replace function public.is_promotora()
returns boolean language sql stable as $$
  select exists(select 1 from public.profiles p where p.id = auth.uid() and p.role = 'promotora' and p.ativo = true);
$$;

-- Master vê tudo. Lívia (promotora) vê e altera apenas matrícula/turmas/benefícios/solicitações.
drop policy if exists profiles_master on public.profiles;
create policy profiles_master on public.profiles for all using (public.is_master()) with check (public.is_master());
drop policy if exists turmas_staff_read on public.turmas;
create policy turmas_staff_read on public.turmas for select using (public.is_master() or public.is_promotora());
drop policy if exists turmas_master_write on public.turmas;
create policy turmas_master_write on public.turmas for all using (public.is_master()) with check (public.is_master());
drop policy if exists alunos_staff on public.alunos;
create policy alunos_staff on public.alunos for select using (public.is_master() or public.is_promotora());
drop policy if exists alunos_write on public.alunos;
create policy alunos_write on public.alunos for insert with check (public.is_master() or public.is_promotora());
drop policy if exists alunos_update on public.alunos;
create policy alunos_update on public.alunos for update using (public.is_master() or public.is_promotora()) with check (public.is_master() or public.is_promotora());
drop policy if exists alunos_delete_master on public.alunos;
create policy alunos_delete_master on public.alunos for delete using (public.is_master());
drop policy if exists solicitacoes_staff on public.solicitacoes;
create policy solicitacoes_staff on public.solicitacoes for all using (public.is_master() or created_by = auth.uid()) with check (public.is_master() or created_by = auth.uid());
drop policy if exists beneficios_staff on public.beneficios_matricula;
create policy beneficios_staff on public.beneficios_matricula for all using (public.is_master() or public.is_promotora()) with check (public.is_master() or public.is_promotora());
drop policy if exists budget_master on public.orcamento_contas;
create policy budget_master on public.orcamento_contas for all using (public.is_master()) with check (public.is_master());
drop policy if exists budget_import_master on public.orcamento_importacoes;
create policy budget_import_master on public.orcamento_importacoes for all using (public.is_master()) with check (public.is_master());
drop policy if exists inad_master on public.inadimplencia_importacoes;
create policy inad_master on public.inadimplencia_importacoes for all using (public.is_master()) with check (public.is_master());
drop policy if exists inad_indicator_master on public.inadimplencia_indicadores;
create policy inad_indicator_master on public.inadimplencia_indicadores for all using (public.is_master()) with check (public.is_master());
