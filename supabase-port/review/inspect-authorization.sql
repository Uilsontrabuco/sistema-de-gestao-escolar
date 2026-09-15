-- SOMENTE LEITURA. NÃO EXECUTADO. Metadados, sem dados pessoais ou credenciais.
select jsonb_build_object(
  'function',p.oid::regprocedure::text,
  'owner',r.rolname,
  'security_definer',p.prosecdef,
  'settings',p.proconfig,
  'acl',p.proacl::text,
  'definition',pg_get_functiondef(p.oid),
  'owner_superuser',r.rolsuper,
  'owner_bypassrls',r.rolbypassrls,
  'profiles_owner',pg_get_userbyid(c.relowner),
  'profiles_rls',c.relrowsecurity,
  'profiles_force_rls',c.relforcerowsecurity,
  'authenticated_execute',has_function_privilege('authenticated',p.oid,'EXECUTE'),
  'anon_execute',has_function_privilege('anon',p.oid,'EXECUTE'),
  'rollback_security',case when p.prosecdef then 'SECURITY DEFINER' else 'SECURITY INVOKER' end,
  'rollback_search_path',coalesce((
    select 'ALTER FUNCTION public.is_master() SET search_path = ' || quote_literal(substr(setting,13)) || ';'
    from unnest(p.proconfig) setting where setting like 'search_path=%'
  ),'ALTER FUNCTION public.is_master() RESET search_path;')
) as authorization_before
from pg_catalog.pg_proc p
join pg_catalog.pg_roles r on r.oid=p.proowner
join pg_catalog.pg_class c on c.oid='public.profiles'::regclass
where p.oid='public.is_master()'::regprocedure;

select schemaname,tablename,policyname,permissive,roles,cmd,qual,with_check
from pg_catalog.pg_policies
where schemaname='public'
order by tablename,policyname;

select pg_describe_object(d.classid,d.objid,d.objsubid) as dependent_object,d.deptype
from pg_catalog.pg_depend d
where d.refobjid='public.is_master()'::regprocedure
  and d.refclassid='pg_proc'::regclass;

select table_name,column_name,data_type,udt_name,is_nullable,column_default
from information_schema.columns
where table_schema='public'
  and table_name in ('profiles','teaching_cost_snapshots','financial_evidence')
order by table_name,ordinal_position;

select tablename,indexname,indexdef from pg_catalog.pg_indexes
where schemaname='public' and tablename in ('teaching_cost_snapshots','financial_evidence');
