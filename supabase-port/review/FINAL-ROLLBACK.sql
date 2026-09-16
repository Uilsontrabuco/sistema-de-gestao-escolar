-- SOMENTE SE NECESSARIO, em execucao separada; NAO executar depois de um sucesso normal.
-- Restaura SECURITY INVOKER/proconfig NULL, conforme estado original confirmado.
-- A recursao original pode voltar; isto nao e uma alternativa segura para publicar.
-- ACL e corpo nao foram alterados pelo principal e continuam preservados.
BEGIN;
SET LOCAL lock_timeout='5s';
DO $rollback$
DECLARE f record;
BEGIN
  PERFORM pg_catalog.pg_advisory_xact_lock(772027,1);
  IF current_user <> 'postgres' OR session_user <> 'postgres' THEN
    RAISE EXCEPTION 'Rollback requer SQL Editor administrativo como postgres.';
  END IF;
  SELECT p.*,r.rolname INTO STRICT f FROM pg_catalog.pg_proc p
    JOIN pg_catalog.pg_roles r ON r.oid=p.proowner WHERE p.oid='public.is_master()'::regprocedure;
  IF f.rolname <> 'postgres' OR f.prorettype <> 'boolean'::regtype
     OR lower(regexp_replace(f.prosrc,'\s+|\(|\)|;','','g')) IS DISTINCT FROM
       'selectexistsselect1frompublic.profilespwherep.id=auth.uidandp.role=''master''andp.ativo=true'
     OR NOT ((NOT f.prosecdef AND f.proconfig IS NULL)
         OR (f.prosecdef AND f.proconfig=ARRAY['search_path=""']::text[])) THEN
    RAISE EXCEPTION 'Funcao divergiu; rollback automatico interrompido.';
  END IF;
  ALTER FUNCTION public.is_master() SECURITY INVOKER;
  ALTER FUNCTION public.is_master() RESET search_path;
END;
$rollback$;
COMMIT;
-- Nenhuma tabela, politica, linha financeira, usuario ou perfil e removido.
