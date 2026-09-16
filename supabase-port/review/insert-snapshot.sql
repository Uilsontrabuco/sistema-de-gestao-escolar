-- TEMPLATE ADMINISTRATIVO PARAMETRIZADO. NÃO EXECUTADO.
-- Executar apenas após validar owner, autorização, schema e RLS.
-- Parâmetros posicionais enviados por driver seguro, nunca interpolados em SQL.
-- $1: versão aprovada positiva; $2: data REAL do fechamento;
-- $3: UUID do administrador responsável; $4: referência documental;
-- $5: SHA-256 do arquivo privado original; $6: payload JSON integral validado.
-- Não assumir data de aprovação nem inventar metadados ausentes.
insert into public.teaching_cost_snapshots
  (year,version,status,closed_at,created_by,source_ref,source_sha256,payload)
values (2027,$1::integer,'approved',$2::timestamptz,$3::uuid,$4::text,$5::text,$6::jsonb)
on conflict (year,version) do nothing;
-- Conferir em leitura se a versão já existente corresponde ao hash/payload esperado.
-- Nunca substituir uma versão divergente. Nenhuma carga de financial_evidence fictícia.
