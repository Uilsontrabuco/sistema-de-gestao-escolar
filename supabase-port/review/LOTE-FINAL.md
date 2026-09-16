# Lote final preparado — não aplicado

As confirmações do usuário sobre schema e função foram preservadas. Falta acesso administrativo real para consultar owner, ACL, search_path, dependências e FORCE RLS; nenhuma conclusão de segurança do owner foi inventada.

## Estado local consolidado

- Prévia isolada verificada: 41 linhas, R$ 25.677,35, logout e formulário de configuração acessível; console sem erros. Nenhuma requisição ao Supabase real.
- 51 testes aprovados, zero falhas locais finais. Não são testes de RLS executados em PostgreSQL real.
- Login de demonstração removido; logout invalida consultas pendentes.
- Configuração Supabase embutida removida sem reproduzir valores. A aplicação usa configuração do navegador; botão Conectar banco de dados disponível no login. Somente HTTPS e chave pública anon/publishable são aceitos; chave privilegiada é rejeitada antes de gravar configuração.
- Credenciais existentes no navegador não foram lidas ou alteradas. Não adicionar valores de acesso ao código/commit.
- Fechamento 2027 integral preservado em private: R$ 25.677,35; 50 professores; 41 turmas; rateios 100%; duplicidade zero.
- Consulta financeira somente de leitura, com resultado indeterminado se faltar fonte suficiente. Módulos e armazenamento legados preservados.

## Sequência administrativa condicionada

1. `inspect-authorization.sql`: somente catálogos; registrar o resultado em arquivo institucional protegido para rollback. Inclui owner, ACL, configurações, definição, dependências e políticas, sem consultar linhas de alunos ou perfis.
2. `correct-authorization.sql`: somente após revisar a introspecção e reproduzir em ambiente de teste. O preflight exige owner postgres apropriado, bypass efetivo sobre profiles, nenhuma associação de anon/authenticated ao owner, EXECUTE existente e corpo lógico exato. Divergência aborta; não altera owner, ACL, assinatura ou corpo. Ajusta somente SECURITY DEFINER e search_path. Não executar a proposta cancelada profiles-rls-prerequisite.sql.
3. Validar com identidades de teste: Master ativo verdadeiro; promotora/comum/inativo falsos; anônimo falso se possuir EXECUTE, ou negação de execução sem qualquer acesso financeiro. Conferir login/profiles sem recursão. Um teste como administrador PostgreSQL sozinho não comprova RLS.
4. `additive-schema.sql`: criar as duas tabelas novas apenas depois de autorização validada. RLS ativa, SELECT somente Master autenticado, sem escrita pelo navegador. Estruturas/políticas divergentes exigem revisão.
5. `insert-snapshot.sql`: template parametrizado, não executado. Requer versão, data real da aprovação, responsável e referência documental. Não inventar data nem responsável. O payload é o fechamento privado integral; comparar SHA-256 e validar antes/depois. Conflito de versão não sobrescreve registro e exige comparação em leitura.
6. Carregar evidências financeiras somente quando reais e comprovadas; não criar receita, mensalização ou rubrica para completar o PE. Validar leitura e restrição financeira com sessões reais. Dados faltantes continuam explicitamente não determinados.

Nenhum script é disparado pelo frontend. Não existe tentativa de conexão administrativa com anon/public key. Não foi utilizado service_role.

## Rollback preparado

A introspecção gera os atributos anteriores necessários, mas o estado real ainda não foi capturado. Antes de confirmar cada transação, qualquer falha permite ROLLBACK. Após eventual correção, restaurar SECURITY e search_path exatamente conforme o registro anterior; isso também restaura o comportamento anterior, inclusive possível recursão. Não inventar o search_path anterior.

As tabelas e dados não devem ser apagados no rollback. Se necessário, suspender a leitura de authenticated nas novas tabelas e manter RLS/histórico, sob autorização administrativa. Não reverter o frontend publicado nesta execução, pois nenhum deploy ocorreu.

## Arquivos adicionais ao conjunto já preparado

review/inspect-authorization.sql, review/correct-authorization.sql, review/insert-snapshot.sql e este documento. index.html e testes foram atualizados para remover configuração embutida e validar chaves públicas; regras financeiras não foram reabertas. private/, .env e configurações locais permanecem fora de Git/deploy.

Pendência operacional única: disponibilizar sessão administrativa autenticada do projeto Supabase real ao ambiente de ferramentas. Até isso ocorrer, owner não verificado, correção não aplicada, tabelas não criadas, snapshot não inserido e RLS real não homologada.

Sem commit, push, deploy ou alterações reais no Supabase.
