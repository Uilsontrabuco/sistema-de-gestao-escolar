-- MODELO DE MONTAGEM LOCAL. NAO executar este modelo: usar private/FINAL-APLICAR.sql.
-- O arquivo completo contem evidencias privadas; NAO publicar no Git/Vercel.
-- Data de registro/aprovacao administrativa = horario real desta transacao.
-- Nao representa uma data historica de fechamento que nao foi comprovada.
-- EXECUTE existente da funcao e preservado: politicas legadas PUBLIC dependem dela.
-- anon continua sem qualquer privilegio nas tabelas financeiras novas.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

DO $installation$
DECLARE
  ledger jsonb := $validated_ledger$__VALIDATED_LEDGER_JSON__$validated_ledger$::jsonb;
  source_hash constant text := '__VALIDATED_LEDGER_SHA256__';
  marker constant text := '7e7-finance-2027-v1:';
  f record;
  c record;
  policy_before jsonb;
  table_name text;
  object_id oid;
  fingerprint text;
  existing_snapshot record;
BEGIN
  -- Serializa reexecucoes deste instalador; nao modifica dados da escola.
  PERFORM pg_catalog.pg_advisory_xact_lock(772027, 1);
  IF current_user <> 'postgres' OR session_user <> 'postgres' THEN
    RAISE EXCEPTION 'Executar somente como postgres no SQL Editor administrativo.';
  END IF;
  SELECT p.*, r.rolname, r.rolsuper, r.rolbypassrls, l.lanname INTO STRICT f
    FROM pg_catalog.pg_proc p
    JOIN pg_catalog.pg_roles r ON r.oid = p.proowner
    JOIN pg_catalog.pg_language l ON l.oid = p.prolang
    WHERE p.oid = 'public.is_master()'::regprocedure;
  SELECT * INTO STRICT c FROM pg_catalog.pg_class WHERE oid = 'public.profiles'::regclass;
  IF f.rolname <> 'postgres' OR f.lanname <> 'sql' OR f.pronargs <> 0
     OR f.prorettype <> 'boolean'::regtype OR f.proretset
     OR NOT c.relrowsecurity OR c.relforcerowsecurity THEN
    RAISE EXCEPTION 'Owner, assinatura ou RLS diverge da confirmacao.';
  END IF;
  IF NOT (f.rolsuper OR f.rolbypassrls OR f.proowner = c.relowner)
     OR NOT has_table_privilege(f.proowner, c.oid, 'SELECT') THEN
    RAISE EXCEPTION 'Owner nao consegue ler profiles sem reentrar na RLS.';
  END IF;
  IF pg_has_role('authenticated', f.proowner, 'MEMBER')
     OR pg_has_role('anon', f.proowner, 'MEMBER') THEN
    RAISE EXCEPTION 'Papel de navegador pode assumir o owner; interrompido.';
  END IF;
  IF NOT has_function_privilege('authenticated', f.oid, 'EXECUTE')
     OR NOT has_function_privilege('anon', f.oid, 'EXECUTE') THEN
    RAISE EXCEPTION 'EXECUTE diverge do estado informado; nenhuma ACL sera substituida.';
  END IF;
  IF lower(regexp_replace(f.prosrc, '\s+|\(|\)|;', '', 'g')) IS DISTINCT FROM
    'selectexistsselect1frompublic.profilespwherep.id=auth.uidandp.role=''master''andp.ativo=true' THEN
    RAISE EXCEPTION 'Corpo de is_master diverge; nao substituir automaticamente.';
  END IF;
  IF NOT ((NOT f.prosecdef AND f.proconfig IS NULL)
       OR (f.prosecdef AND f.proconfig = ARRAY['search_path=""']::text[])) THEN
    RAISE EXCEPTION 'Configuracao da funcao nao e a original nem a final esperada.';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_attribute
     WHERE attrelid=c.oid AND attname='id' AND atttypid='uuid'::regtype AND NOT attisdropped)
     OR NOT EXISTS (SELECT 1 FROM pg_catalog.pg_attribute
     WHERE attrelid=c.oid AND attname='role' AND atttypid='public.user_role'::regtype AND NOT attisdropped)
     OR NOT EXISTS (SELECT 1 FROM pg_catalog.pg_attribute
     WHERE attrelid=c.oid AND attname='ativo' AND atttypid='boolean'::regtype AND NOT attisdropped) THEN
    RAISE EXCEPTION 'Campos de autorizacao divergentes.';
  END IF;
  SELECT to_jsonb(p) INTO STRICT policy_before FROM pg_catalog.pg_policies p
    WHERE schemaname='public' AND tablename='profiles' AND policyname='profiles_master';
  IF policy_before->>'cmd' <> 'ALL' OR policy_before->>'permissive' <> 'PERMISSIVE'
     OR policy_before->'roles' <> '["public"]'::jsonb
     OR regexp_replace(policy_before->>'qual','\s+|\(|\)|public\.','','g') IS DISTINCT FROM 'is_master'
     OR regexp_replace(policy_before->>'with_check','\s+|\(|\)|public\.','','g') IS DISTINCT FROM 'is_master' THEN
    RAISE EXCEPTION 'profiles_master diverge da politica confirmada.';
  END IF;
  IF (ledger->>'target_year')::integer IS DISTINCT FROM 2027
    OR (ledger->>'validated_cost_cents')::bigint IS DISTINCT FROM 2567735::bigint
    OR (ledger->'summary'->>'reconciled_professors')::integer IS DISTINCT FROM 50
    OR jsonb_array_length(ledger->'classes') IS DISTINCT FROM 41
    OR (ledger->>'conflicted_cost_cents')::bigint IS DISTINCT FROM 0::bigint
    OR (ledger->>'unassigned_cost_cents')::bigint IS DISTINCT FROM 0::bigint
    OR (ledger->'summary'->>'unexplained_cost_cents')::bigint IS DISTINCT FROM 0::bigint
    OR (ledger->'summary'->>'financial_duplicates')::integer IS DISTINCT FROM 0
    OR (SELECT sum((v->>'weekly_cost')::numeric) FROM jsonb_array_elements(ledger->'classes') v)
       IS DISTINCT FROM 25677.35::numeric THEN
    RAISE EXCEPTION 'Payload nao corresponde ao fechamento validado.';
  END IF;

  -- IF NOT EXISTS sozinho nao detecta schema divergente. Objetos ja presentes
  -- precisam ter a assinatura catalogal registrada por ESTE instalador.
  IF (to_regclass('public.teaching_cost_snapshots') IS NULL)
     <> (to_regclass('public.financial_evidence') IS NULL) THEN
    RAISE EXCEPTION 'Estado parcial das tabelas; nenhuma adaptacao automatica.';
  END IF;
  FOREACH table_name IN ARRAY ARRAY['teaching_cost_snapshots','financial_evidence'] LOOP
    object_id := to_regclass(format('public.%I',table_name));
    IF object_id IS NOT NULL THEN
      SELECT md5(jsonb_build_object(
        'relation',(SELECT to_jsonb(r) - 'relpages' - 'reltuples' - 'relallvisible' - 'relallfrozen' - 'relfrozenxid' - 'relminmxid' - 'relfilenode' FROM pg_catalog.pg_class r WHERE r.oid=object_id),
        'columns',(SELECT jsonb_agg(jsonb_build_array(a.attname,a.atttypid,a.atttypmod,a.attnotnull,a.attidentity,a.attgenerated,pg_get_expr(d.adbin,d.adrelid),a.attacl) ORDER BY a.attnum) FROM pg_catalog.pg_attribute a LEFT JOIN pg_catalog.pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum WHERE a.attrelid=object_id AND a.attnum>0 AND NOT a.attisdropped),
        'constraints',(SELECT jsonb_agg(jsonb_build_array(k.conname,pg_get_constraintdef(k.oid),k.convalidated) ORDER BY k.conname) FROM pg_catalog.pg_constraint k WHERE k.conrelid=object_id),
        'indexes',(SELECT jsonb_agg(jsonb_build_array(pg_get_indexdef(i.indexrelid),i.indisvalid,i.indisready) ORDER BY i.indexrelid) FROM pg_catalog.pg_index i WHERE i.indrelid=object_id),
        'policies',(SELECT jsonb_agg(to_jsonb(p) ORDER BY p.policyname) FROM pg_catalog.pg_policies p WHERE p.schemaname='public' AND p.tablename=table_name),
        'triggers',(SELECT jsonb_agg(pg_get_triggerdef(t.oid) ORDER BY t.tgname) FROM pg_catalog.pg_trigger t WHERE t.tgrelid=object_id AND NOT t.tgisinternal)
      )::text) INTO fingerprint;
      IF obj_description(object_id,'pg_class') IS DISTINCT FROM marker || fingerprint THEN
        RAISE EXCEPTION 'Tabela % preexistente sem assinatura compativel. Nenhum objeto sera sobrescrito.', table_name;
      END IF;
    END IF;
  END LOOP;

  -- Unica alteracao de objeto preexistente: configuracao da funcao. Corpo, owner,
  -- assinatura, ACL, profiles, profiles_master e auth permanecem intocados.
  ALTER FUNCTION public.is_master() SET search_path = '';
  ALTER FUNCTION public.is_master() SECURITY DEFINER;

  CREATE TABLE IF NOT EXISTS public.teaching_cost_snapshots (
    year integer NOT NULL CHECK (year=2027),
    version integer NOT NULL CHECK (version>0),
    status text NOT NULL CHECK (status IN ('draft','approved')),
    closed_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by uuid REFERENCES auth.users(id),
    recorded_by name NOT NULL DEFAULT session_user,
    source_ref text NOT NULL CHECK (length(trim(source_ref))>0),
    source_sha256 text NOT NULL CHECK (source_sha256 ~ '^[a-f0-9]{64}$'),
    payload jsonb NOT NULL,
    PRIMARY KEY (year,version),
    CHECK ((payload->>'target_year')::integer IS NOT DISTINCT FROM year),
    CHECK ((payload->>'validated_cost_cents')::bigint IS NOT DISTINCT FROM 2567735::bigint),
    CHECK ((payload->'summary'->>'reconciled_professors')::integer IS NOT DISTINCT FROM 50),
    CHECK (jsonb_array_length(payload->'classes') IS NOT DISTINCT FROM 41)
  );
  CREATE TABLE IF NOT EXISTS public.financial_evidence (
    year integer NOT NULL,
    version integer NOT NULL CHECK (version>0),
    snapshot_version integer NOT NULL,
    status text NOT NULL CHECK (status IN ('draft','approved')),
    closed_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by uuid REFERENCES auth.users(id),
    recorded_by name NOT NULL DEFAULT session_user,
    source_ref text NOT NULL CHECK (length(trim(source_ref))>0),
    source_sha256 text NOT NULL CHECK (source_sha256 ~ '^[a-f0-9]{64}$'),
    payload jsonb NOT NULL,
    PRIMARY KEY (year,version),
    FOREIGN KEY (year,snapshot_version) REFERENCES public.teaching_cost_snapshots(year,version),
    CHECK ((payload->>'year')::integer IS NOT DISTINCT FROM year)
  );
  CREATE INDEX IF NOT EXISTS financial_evidence_snapshot_idx
    ON public.financial_evidence(year,snapshot_version);
  ALTER TABLE public.teaching_cost_snapshots ENABLE ROW LEVEL SECURITY;
  ALTER TABLE public.financial_evidence ENABLE ROW LEVEL SECURITY;
  REVOKE ALL ON public.teaching_cost_snapshots, public.financial_evidence FROM PUBLIC, anon, authenticated;
  GRANT SELECT ON public.teaching_cost_snapshots, public.financial_evidence TO authenticated;
  IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_policy WHERE polrelid='public.teaching_cost_snapshots'::regclass AND polname='teaching_snapshot_master_read') THEN
    CREATE POLICY teaching_snapshot_master_read ON public.teaching_cost_snapshots
      FOR SELECT TO authenticated USING (status='approved' AND public.is_master());
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_policy WHERE polrelid='public.financial_evidence'::regclass AND polname='financial_evidence_master_read') THEN
    CREATE POLICY financial_evidence_master_read ON public.financial_evidence
      FOR SELECT TO authenticated USING (status='approved' AND public.is_master());
  END IF;

  -- Versao 1: registro administrativo desta aprovacao, com payload integral.
  -- SQL Editor nao identifica necessariamente uma pessoa em auth.uid(). NULL
  -- conserva essa ausencia; recorded_by registra o papel real, sem UUID inventado.
  SELECT * INTO existing_snapshot FROM public.teaching_cost_snapshots WHERE year=2027 AND version=1;
  IF FOUND THEN
    IF existing_snapshot.payload IS DISTINCT FROM ledger
       OR existing_snapshot.source_sha256 IS DISTINCT FROM source_hash
       OR existing_snapshot.status IS DISTINCT FROM 'approved' THEN
      RAISE EXCEPTION 'Versao 1 ja existe com conteudo diferente; nao sera substituida.';
    END IF;
  ELSE
    INSERT INTO public.teaching_cost_snapshots
      (year,version,status,closed_at,created_by,source_ref,source_sha256,payload)
    VALUES (2027,1,'approved',transaction_timestamp(),auth.uid(),
      'Fechamento validado 2027; resultado.json integral. closed_at = aprovacao administrativa deste registro; data historica nao inferida.',
      source_hash,ledger);
  END IF;
  -- Nenhuma financial_evidence ficticia e inserida; PE exige fontes reais.

  IF policy_before IS DISTINCT FROM (SELECT to_jsonb(p) FROM pg_catalog.pg_policies p
      WHERE schemaname='public' AND tablename='profiles' AND policyname='profiles_master')
     OR NOT (SELECT relrowsecurity AND NOT relforcerowsecurity FROM pg_catalog.pg_class WHERE oid='public.profiles'::regclass)
     OR f.prosrc IS DISTINCT FROM (SELECT prosrc FROM pg_catalog.pg_proc WHERE oid=f.oid)
     OR f.proacl IS DISTINCT FROM (SELECT proacl FROM pg_catalog.pg_proc WHERE oid=f.oid) THEN
    RAISE EXCEPTION 'Objeto protegido mudou; transacao interrompida.';
  END IF;
  FOREACH table_name IN ARRAY ARRAY['teaching_cost_snapshots','financial_evidence'] LOOP
    object_id := to_regclass(format('public.%I',table_name));
    IF has_table_privilege('anon',object_id,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
       OR has_any_column_privilege('anon',object_id,'SELECT,INSERT,UPDATE,REFERENCES')
       OR has_table_privilege('authenticated',object_id,'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
       OR has_any_column_privilege('authenticated',object_id,'INSERT,UPDATE,REFERENCES')
       OR NOT has_table_privilege('authenticated',object_id,'SELECT') THEN
      RAISE EXCEPTION 'Permissoes financeiras efetivas excessivas em %; abortado.',table_name;
    END IF;
    SELECT md5(jsonb_build_object(
      'relation',(SELECT to_jsonb(r) - 'relpages' - 'reltuples' - 'relallvisible' - 'relallfrozen' - 'relfrozenxid' - 'relminmxid' - 'relfilenode' FROM pg_catalog.pg_class r WHERE r.oid=object_id),
      'columns',(SELECT jsonb_agg(jsonb_build_array(a.attname,a.atttypid,a.atttypmod,a.attnotnull,a.attidentity,a.attgenerated,pg_get_expr(d.adbin,d.adrelid),a.attacl) ORDER BY a.attnum) FROM pg_catalog.pg_attribute a LEFT JOIN pg_catalog.pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum WHERE a.attrelid=object_id AND a.attnum>0 AND NOT a.attisdropped),
      'constraints',(SELECT jsonb_agg(jsonb_build_array(k.conname,pg_get_constraintdef(k.oid),k.convalidated) ORDER BY k.conname) FROM pg_catalog.pg_constraint k WHERE k.conrelid=object_id),
      'indexes',(SELECT jsonb_agg(jsonb_build_array(pg_get_indexdef(i.indexrelid),i.indisvalid,i.indisready) ORDER BY i.indexrelid) FROM pg_catalog.pg_index i WHERE i.indrelid=object_id),
      'policies',(SELECT jsonb_agg(to_jsonb(p) ORDER BY p.policyname) FROM pg_catalog.pg_policies p WHERE p.schemaname='public' AND p.tablename=table_name),
      'triggers',(SELECT jsonb_agg(pg_get_triggerdef(t.oid) ORDER BY t.tgname) FROM pg_catalog.pg_trigger t WHERE t.tgrelid=object_id AND NOT t.tgisinternal)
    )::text) INTO fingerprint;
    EXECUTE format('COMMENT ON TABLE public.%I IS %L',table_name,marker || fingerprint);
  END LOOP;
END;
$installation$;
COMMIT;
