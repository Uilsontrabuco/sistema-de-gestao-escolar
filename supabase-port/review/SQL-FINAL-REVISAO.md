# SQL final revisado — não executado

Fonte da validação: informações do Supabase real confirmadas pelo usuário. public.profiles tem id uuid e role user_role; perfil master; RLS ativa; profiles_master usa is_master() em USING/WITH CHECK. As duas tabelas financeiras ainda não existem. Não foi feita uma inspeção remota adicional nem alterada a função existente.

Arquivo autorizado para futura revisão/aplicação: additive-schema.sql.

- Duas tabelas novas: teaching_cost_snapshots e financial_evidence, com CREATE TABLE IF NOT EXISTS.
- Duas políticas SELECT para authenticated, usando somente public.is_master() e status approved.
- PK composta (year,version) nas duas tabelas; FK para auth.users(id) nos metadados e FK das evidências para a versão exata do fechamento.
- Um índice adicional para a FK financeira; os índices de PK já cobrem consultas por exercício/versão.
- RLS habilitada somente nas duas tabelas novas.
- Privilégios dos papéis PUBLIC/anon/authenticated nas duas tabelas são reduzidos a SELECT de authenticated, sujeito a RLS. Nenhuma escrita pelo navegador, inclusive para Master.
- Nenhuma alteração nas nove tabelas existentes, profiles_master ou is_master(). Não cria helper alternativo de autorização.
- Sem DROP, TRUNCATE, DELETE, desativação de RLS, SQL de carga ou política de escrita.

## Revisão das propostas anteriores

profiles-rls-prerequisite.sql foi CANCELADO e convertido em comentários sem comandos executáveis. Não deve ser aplicado. Helpers finance_is_master e finance_reject_mutation e os triggers anteriormente propostos foram removidos do SQL final. O versionamento continua por PK/FK/metadados e ausência de escrita do navegador; não há bloqueio por trigger para administradores do banco. Correções administrativas devem acrescentar versões, preservando o histórico, conforme o procedimento de carga a ser aprovado.

## Idempotência e limites

Tabelas e índice usam IF NOT EXISTS; a habilitação de RLS e concessões são repetíveis. O bloco de políticas consulta pg_policies: cria somente as políticas ausentes, mantém as equivalentes e interrompe a transação se houver política extra ou incompatível. Nenhuma política existente é substituída.

O script é idempotente sobre o estado informado e sobre sua própria reexecução. IF NOT EXISTS não reconcilia uma tabela criada por outro processo com estrutura diferente. Se o estado mudar antes da aplicação, conferir novamente colunas, PK/FK e índices; não presumir compatibilidade.

O funcionamento e a permissão de execução de public.is_master() para authenticated devem ser validados com sessões reais. Não se modifica a função nem seus privilégios neste script. A revisão estática não substitui essa validação. O proprietário administrativo pode ter privilégios além dos papéis do navegador, conforme o funcionamento normal do PostgreSQL.

## Ordem futura de aplicação e validação

1. Revisar este único SQL no projeto correto e confirmar que as duas tabelas continuam ausentes; preservar backup/metadados. Não aplicar o schema original ou o pré-requisito cancelado.
2. Quando houver autorização explícita, executar additive-schema.sql completo como administrador em uma transação. Erro interrompe a operação; não prosseguir com comandos parciais.
3. Conferir duas tabelas, colunas/metadados, PK/FK, índice, RLS ativa e duas políticas SELECT para authenticated usando is_master(). Conferir que profiles, profiles_master e is_master() permaneceram iguais.
4. Validar privilégios por metadados: sem escrita para anon/authenticated, sem leitura financeira para anon; testar leitura autorizada Master e negação para demais perfis com sessões de teste, sem inserir registros nesta etapa.
5. Reexecutar o mesmo script em ambiente de teste para verificar idempotência e contagem de objetos invariável.
6. Executar os testes locais e as consultas mockadas da aplicação. Snapshot permanece NÃO INSERIDO; carga e homologação com dados exigem autorização posterior.

Validação local concluída: 47 testes aprovados, incluindo as asserções atualizadas de SQL e cancelamento da alteração de perfis. Nenhum SQL executado, escrita Supabase, commit, push ou deploy.
