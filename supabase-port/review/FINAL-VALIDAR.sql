-- SOMENTE LEITURA. Executar depois do COMMIT do principal.
BEGIN TRANSACTION READ ONLY;
SELECT 'funcao' AS verificacao, pg_get_userbyid(p.proowner) AS owner,
  p.prosecdef AS security_definer, p.proconfig AS configuracao,
  has_function_privilege('anon',p.oid,'EXECUTE') AS anon_execute_preservado,
  has_function_privilege('authenticated',p.oid,'EXECUTE') AS authenticated_execute,
  p.prosecdef AND p.proconfig=ARRAY['search_path=""']::text[]
    AND pg_get_userbyid(p.proowner)='postgres' AS configuracao_ok
FROM pg_catalog.pg_proc p WHERE p.oid='public.is_master()'::regprocedure;

SELECT 'profiles' AS verificacao, c.relrowsecurity AS rls, c.relforcerowsecurity AS force_rls,
  p.policyname,p.permissive,p.roles,p.cmd,p.qual,p.with_check,
  c.relrowsecurity AND NOT c.relforcerowsecurity AND p.cmd='ALL'
  AND p.permissive='PERMISSIVE' AND p.roles=ARRAY['public']::name[]
  AND regexp_replace(p.qual,'\s+|\(|\)|public\.','','g')='is_master'
  AND regexp_replace(p.with_check,'\s+|\(|\)|public\.','','g')='is_master' AS preservada
FROM pg_catalog.pg_class c JOIN pg_catalog.pg_policies p
  ON p.schemaname='public' AND p.tablename='profiles' AND p.policyname='profiles_master'
WHERE c.oid='public.profiles'::regclass;

SELECT x.nome, c.oid IS NOT NULL AS existe, c.relrowsecurity AS rls,
  has_table_privilege('anon',c.oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
    OR has_any_column_privilege('anon',c.oid,'SELECT,INSERT,UPDATE,REFERENCES') AS anon_tem_acesso_deve_ser_false,
  has_table_privilege('authenticated',c.oid,'SELECT') AS authenticated_select,
  has_table_privilege('authenticated',c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
    OR has_any_column_privilege('authenticated',c.oid,'INSERT,UPDATE,REFERENCES') AS navegador_escrita_deve_ser_false
FROM (VALUES ('teaching_cost_snapshots'),('financial_evidence')) x(nome)
LEFT JOIN pg_catalog.pg_class c ON c.oid=to_regclass(format('public.%I',x.nome));

SELECT tablename,policyname,roles,cmd,qual,with_check,
  cmd='SELECT' AND roles=ARRAY['authenticated']::name[] AND with_check IS NULL
  AND lower(regexp_replace(qual,'\s+|\(|\)|::text|public\.','','g'))='status=''approved''andis_master' AS politica_ok
FROM pg_catalog.pg_policies WHERE schemaname='public'
  AND tablename IN ('teaching_cost_snapshots','financial_evidence');

SELECT 'quantidades' AS verificacao,
  (SELECT count(*) FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
   WHERE n.nspname='public' AND c.relname IN ('teaching_cost_snapshots','financial_evidence') AND c.relkind='r') AS tabelas_esperado_2,
  (SELECT count(*) FROM pg_catalog.pg_policies WHERE schemaname='public'
   AND tablename IN ('teaching_cost_snapshots','financial_evidence')) AS politicas_esperado_2,
  (SELECT count(*) FROM pg_catalog.pg_policies WHERE schemaname='public'
   AND tablename IN ('teaching_cost_snapshots','financial_evidence') AND cmd<>'SELECT') AS politicas_escrita_esperado_0,
  (SELECT count(*) FROM pg_catalog.pg_indexes WHERE schemaname='public'
   AND tablename IN ('teaching_cost_snapshots','financial_evidence')) AS indices_esperado_3;

SELECT year,version,status,closed_at AS aprovado_no_banco_em,created_at,recorded_by,
  (payload->>'validated_cost_cents')::numeric/100 AS custo_semanal,
  (payload->'summary'->>'reconciled_professors')::integer AS professores,
  jsonb_array_length(payload->'classes') AS turmas,
  (SELECT sum((v->>'weekly_cost')::numeric) FROM jsonb_array_elements(payload->'classes') v) AS soma_turmas,
  payload->>'conflicted_cost_cents' AS conflito_centavos,
  payload->>'unassigned_cost_cents' AS sem_destino_centavos,
  payload->'summary'->>'unexplained_cost_cents' AS diferenca_centavos,
  payload->'summary'->>'financial_duplicates' AS duplicidades,
  source_sha256='199b5c813e50988bbb2f6eb8e8d2771a97a9c62a117277a12678f1ae0beb20c9' AS origem_validada
FROM public.teaching_cost_snapshots WHERE year=2027;

SELECT year,version,count(*) AS quantidade FROM public.teaching_cost_snapshots
GROUP BY year,version HAVING count(*)>1;
SELECT year,version,count(*) AS quantidade FROM public.financial_evidence
GROUP BY year,version HAVING count(*)>1;
SELECT count(*) AS evidencias_financeiras_sem_dados_inventados FROM public.financial_evidence;
COMMIT;
-- Testes de catalogo nao substituem teste posterior de login Master/nao-Master
-- com sessoes reais existentes. Nenhum usuario ou dado e criado por este bloco.
