# Lote administrativo final — preparado, não executado

Este lote substitui as propostas separadas anteriores. Não concatenar `additive-schema.sql`, `correct-authorization.sql`, `insert-snapshot.sql` nem executar o schema original. O código HTML/JavaScript não foi modificado nesta entrega.

## Arquivos e ordem

1. Revisar e executar **somente** `private/FINAL-APLICAR.sql` no SQL Editor como `postgres`. Ele é completo, transacional e contém o payload privado integral; não possui parâmetros pendentes. Falha em qualquer etapa impede o COMMIT do lote. Se o editor mantiver a transação em estado abortado, encerrar com `ROLLBACK;` antes de tentar novamente.
2. Executar `review/FINAL-VALIDAR.sql`, somente leitura. Conferir todas as saídas, não apenas ausência de erro.
3. Validar posteriormente o fluxo com sessões reais já existentes: Master ativo lê a área financeira; demais perfis não leem linhas financeiras; anon não tem privilégio; nenhum navegador escreve. Parsing e mocks não comprovam execução real das políticas.
4. `review/FINAL-ROLLBACK.sql` é somente contingência. Não executar após um sucesso normal. Restaura INVOKER e ausência de configuração de search_path, sem apagar dados. Pode restabelecer a recursão original; não é solução para publicar.

## Decisões

- A função INVOKER reentra na RLS de profiles. DEFINER usa o owner postgres, mas o lote verifica que esse owner efetivamente pode ler profiles sem RLS antes de alterar a função. Preserva exatamente corpo, owner, auth.uid(), assinatura, retorno e ACL; define apenas SECURITY DEFINER e search_path vazio. Não concede BYPASSRLS a ninguém.
- EXECUTE efetivo de anon/authenticated foi confirmado, mas a origem completa das ACL e todas as dependências de políticas PUBLIC não foram fornecidas. Não revogar EXECUTE evita quebrar dependências existentes. A execução anônima desse predicado não concede leitura financeira. As novas tabelas revogam todos os privilégios de PUBLIC/anon e oferecem a authenticated apenas SELECT, condicionado a status approved e is_master().
- Duas tabelas, duas políticas SELECT, duas PK compostas e um índice adicional da FK. Não altera profiles, profiles_master, auth nem dados dos módulos existentes.
- `created_by` é FK nullable para auth.users: o SQL Editor pode não fornecer auth.uid(). Não se inventa identidade. `recorded_by` registra session_user real. `closed_at` registra a aprovação administrativa da versão 1 na execução, e não uma data histórica presumida. A referência documental explica essa semântica. A diferença ante a proposta antiga se restringe às tabelas ainda inexistentes.
- Snapshot aprovado 2027, versão administrativa 1, payload integral de 10.908.137 bytes, SHA-256 `199b5c813e50988bbb2f6eb8e8d2771a97a9c62a117277a12678f1ae0beb20c9`. Preserva 2.567.735 centavos semanais, 50 professores, 41 turmas, evidências e rateios validados. Não altera orçamento, folha ou totalExpensesMonthly.
- Nenhuma financial_evidence é inventada/inserida. O PE continua indicando insuficiência quando faltarem fontes reais. Este lote não homologa números financeiros ausentes.
- Reexecução compara estrutura/ACL/índices/políticas com uma impressão de catálogo registrada em comentário das novas tabelas; mudança posterior exige revisão, não adaptação automática. A versão 1 preexistente precisa ter payload/hash/status idênticos. Nenhuma versão é sobrescrita. A impressão é detector de divergência operacional, não proteção contra administrador malicioso.

## Limites e proteção

O script integral contém dados documentais de professores e deve permanecer **privado**, fora de Git e Vercel. O diretório private já está excluído de ambos. O editor poderá armazenar o texto no histórico administrativo do projeto: manter seu acesso restrito aos administradores. O arquivo tem aproximadamente 10,9 MB; eventual limite do editor pode impedir sua submissão. Não fragmentar a transação para contornar um erro.

O rollback conserva ACL pois o principal não a modifica. Configurações divergentes impedem rollback automático. Não houve execução PostgreSQL, teste real de RLS, alteração Supabase, commit, push ou deploy. As informações de produção são as confirmadas pelo usuário; validação local não equivale à homologação da execução em produção.

Os testes `final_sql_static.py` fazem somente parsing PostgreSQL/PLpgSQL e verificações estáticas. O parser pglast foi instalado em diretório temporário; não é dependência da aplicação.
