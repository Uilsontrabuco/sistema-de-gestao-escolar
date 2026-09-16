-- PROPOSTA CONDICIONADA, NÃO EXECUTADA.
-- Primeiro registrar o resultado de inspect-authorization.sql em arquivo protegido.
-- Validar em Supabase de teste antes de produção. Nenhuma mudança de owner/ACL.
begin;
do $preflight$
declare
  f record;
  c record;
  normalized_body text;
begin
  select p.*,r.rolname,r.rolsuper,r.rolbypassrls,l.lanname into strict f
    from pg_catalog.pg_proc p
    join pg_catalog.pg_roles r on r.oid=p.proowner
    join pg_catalog.pg_language l on l.oid=p.prolang
    where p.oid='public.is_master()'::regprocedure;
  select * into strict c from pg_catalog.pg_class where oid='public.profiles'::regclass;
  if f.rolname <> 'postgres' or f.lanname <> 'sql'
    or f.pronargs <> 0 or f.prorettype <> 'boolean'::regtype then
    raise exception 'Owner ou assinatura exige revisão administrativa; nenhuma alteração aplicada';
  end if;
  if not (f.rolsuper or f.rolbypassrls or (f.proowner=c.relowner and not c.relforcerowsecurity))
    or not has_table_privilege(f.proowner,c.oid,'SELECT') then
    raise exception 'Owner não pode consultar profiles sem recursão';
  end if;
  if pg_has_role('authenticated',f.proowner,'MEMBER') or pg_has_role('anon',f.proowner,'MEMBER') then
    raise exception 'Papéis de navegador não podem assumir o owner';
  end if;
  if not has_function_privilege('authenticated',f.oid,'EXECUTE') then
    raise exception 'Privilégios de execução precisam ser revisados separadamente';
  end if;
  normalized_body := lower(regexp_replace(f.prosrc,'\s+|\(|\)|;','','g'));
  if normalized_body <> 'selectexistsselect1frompublic.profilespwherep.id=auth.uidandp.role=''master''andp.ativo=true' then
    raise exception 'Definição difere da confirmação; nenhuma substituição automática';
  end if;
end;
$preflight$;
alter function public.is_master() set search_path = '';
alter function public.is_master() security definer;
commit;
