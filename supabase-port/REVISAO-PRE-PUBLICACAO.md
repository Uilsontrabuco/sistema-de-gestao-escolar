# Revisão final pré-publicação — 7&7

Atualização posterior com schema real informado: a proposta de alteração de perfis foi cancelada. O SQL final usa exclusivamente public.is_master() existente, sem helpers alternativos ou triggers. Consulte review/SQL-FINAL-REVISAO.md e review/additive-schema.sql; eles substituem as propostas de SQL/RLS descritas abaixo.

Revisão exclusivamente local da versão Supabase portada. Nenhum SQL executado, nenhuma escrita Supabase, migração, commit, push ou deploy. Este relatório atualiza as pendências locais descritas em PORTABILIDADE.md.

## A — Login

O bypass estava no final de `index.html:doLogin`: quando não havia cliente Supabase, comparava entradas com credenciais literais e usava um usuário de `state.users` para abrir a aplicação, inclusive como Master. Esse ramo foi removido, sem reproduzir seus valores. A mensagem da tela de login também foi atualizada.

O caminho real permanece: signInWithPassword → profiles pelo ID autenticado → verificação de ativo → papel autorizado. Sem cliente Supabase, não há login local. O cadastro legado de usuários não é utilizado para autenticar. Testes confirmam que as entradas anteriormente aceitas não criam sessão sem Supabase. Se alguma senha de demonstração tiver sido reutilizada em conta real, sua troca deve ser feita no Supabase, nunca pelo chat.

## B — Persistência por módulo

| Módulo | Classificação atual | Armazenamento / observação |
|---|---|---|
| Login, sessão e perfil de autorização | PRODUÇÃO SUPABASE | Supabase Auth e profiles; preservados |
| Configuração de conexão | LOCALSTORAGE LEGADO | Nomes seven7_supabase_url / seven7_supabase_anon; configuração pública, sem valores neste relatório |
| Matrículas e quantitativos | LOCALSTORAGE LEGADO; NECESSITA MIGRAÇÃO FUTURA | 77state.classes/imports/responsibles; nenhuma migração nesta entrega |
| Turmas/capacidades na interface antiga | LOCALSTORAGE LEGADO | 77state.classes; preservado integralmente |
| Benefícios | LOCALSTORAGE LEGADO; NECESSITA MIGRAÇÃO FUTURA | 77state.benefits |
| Solicitações | LOCALSTORAGE LEGADO; NECESSITA MIGRAÇÃO FUTURA | 77state.requests |
| Orçamento/importações | LOCALSTORAGE LEGADO; NECESSITA MIGRAÇÃO FUTURA | 77state.budget/imports |
| Inadimplência | LOCALSTORAGE LEGADO; NECESSITA MIGRAÇÃO FUTURA | 77state.delinq/imports |
| Responsáveis | LOCALSTORAGE LEGADO; NECESSITA MIGRAÇÃO FUTURA | 77state.responsibles |
| Cadastro/lista de usuários na interface antiga | LOCALSTORAGE LEGADO; NECESSITA MIGRAÇÃO FUTURA | 77state.users; não cria conta Auth nem concede papel Supabase |
| Dashboard e relatórios antigos | SOMENTE LEITURA de LOCALSTORAGE LEGADO | Derivados de state; exportações não sincronizam com Supabase |
| Nova consulta Custeio / PE 2027 | SOMENTE LEITURA SUPABASE | profiles, turmas e as duas tabelas propostas; não usa 77state como fallback financeiro |

As funções de persistência, cadastros e módulos legados não foram alteradas. A nova área não possui insert/update/upsert/delete/rpc/setItem. Nenhum dado de localStorage é copiado para Supabase ou sobrescrito. Na homologação real, divergência entre cadastro Supabase e cadastro legado deve ser documentada; não é corrigida automaticamente. Migração futura dos módulos legados é trabalho separado, não pré-requisito para esta consulta somente de leitura quando os dados Supabase estiverem comprovados.

## C — Tabelas propostas

| Propriedade | teaching_cost_snapshots | financial_evidence |
|---|---|---|
| Finalidade | Fechamento docente auditável e versionado | Fontes documentadas do PE, vinculadas a uma versão do fechamento |
| Colunas comuns | year integer; version integer; status text (draft/approved); closed_at timestamptz; created_at timestamptz; created_by uuid; source_ref text; source_sha256 text; payload jsonb | As mesmas colunas |
| Coluna adicional | — | snapshot_version integer |
| PK | (year, version) | (year, version) |
| FK | created_by → auth.users(id) | created_by → auth.users(id); (year,snapshot_version) → teaching_cost_snapshots(year,version) |
| Índices | PK btree, suficiente para versão mais recente por exercício | PK btree e financial_evidence_snapshot_idx(year,snapshot_version) |
| Integridade | Exercício 2027, versão positiva, hash SHA-256, fechamento 2.567.735 centavos, 50 professores, 41 turmas | Exercício consistente com payload, versão positiva, vínculo com fechamento existente |
| Histórico | UPDATE/DELETE bloqueados por trigger; correções exigem nova versão | Mesma regra |

Não há FK nas referências de turmas dentro do JSON. O código exige correspondência única com os UUIDs e nomes das 41 turmas e bloqueia cálculos quando os vínculos divergem. O administrador deve verificar essas referências antes do carregamento.

## D–E — SQL e RLS

**SQL necessário: SIM. RLS necessária: SIM. Nenhum executado.**

- `review/additive-schema.sql`: cria somente as duas tabelas novas, metadados, índices, FKs, políticas e triggers de imutabilidade. Não altera registros existentes.
- `review/profiles-rls-prerequisite.sql`: correção CONDICIONAL. Só aplicar se a inspeção confirmar que as funções/policies reais reproduzem a recursão do schema versionado. Mantém as condições existentes de Master/Promotora e permite ao usuário ler apenas seu próprio perfil ativo para login.
- Não reaplicar `supabase_schema.sql` nem executar scripts cegamente quando objetos já existirem.

| Perfil | SELECT nas novas tabelas | INSERT/UPDATE/DELETE |
|---|---|---|
| Master autenticado e ativo | Somente versões approved | Proibidos no navegador |
| Promotora / comum / inativo | Proibido | Proibidos |
| Anônimo | Proibido | Proibidos |

A estrutura existente não possui papel financeiro independente. Não foi criado nem concedido um. Helpers SECURITY DEFINER usam schema explícito, search_path vazio, proprietário administrativo confiável e nenhum parâmetro de usuário. A função nova verifica somente o usuário autenticado, evitando consultar profiles sob a policy recursiva. RLS permanece habilitada; nenhuma política pública de escrita foi criada.

## Armazenamento e aprovação das versões

1. Preservar o arquivo fechado em armazenamento institucional restrito. `private/teaching-cost-2027.json` permanece integral e fora de Git/deploy; não publicar o JSON no site.
2. Registrar a data real do fechamento em closed_at, versão positiva, administrador responsável em created_by, referência documental e SHA-256 do arquivo original. Não usar uma data inventada ou inferida como data de aprovação.
3. Após backup e revisão do SQL, um administrador do banco carrega a versão aprovada por procedimento controlado. Não existe carga automática no aplicativo nem permissão de escrita do navegador.
4. O payload conserva rateios, aulas, tarifas, professores, origens, evidências e observações documentais. Não adicionar CPF, contatos, senhas ou outros dados pessoais desnecessários.
5. Evidências financeiras recebem sua própria versão e FK para a versão exata do fechamento. Não sobrescrever versões: até uma aprovação de draft deve gerar uma nova versão approved, preservando o histórico anterior.
6. A consulta seleciona a versão approved mais recente. Evidências apontando para outro fechamento não alimentam PE; o custeio semanal continua disponível.

O SHA-256 registra a proveniência do arquivo carregado; sua conferência com o payload é parte do procedimento administrativo de carga. Não foi feita carga remota nesta revisão.

## PE e integridade

R$ 25.677,35 semanal, 41 turmas e 50 professores preservados. Diferença R$ 0,00; rateios 100%; duplicidade zero. Sem mensalização presumida. O custo mensal consolidado comprovado é usado sem acrescentar o custeio docente novamente. Custos anuais não são tratados como mensais. Receitas individualizadas com descontos/bolsas têm precedência sobre agregados; matrícula fica separada das 11 mensalidades. Valores sem evidência, vínculos incoerentes ou população não comprovada deixam PE indeterminado.

A interface mostra explicitamente “Dados insuficientes para o PE geral” quando necessário. Logout limpa os resultados e invalida respostas de consultas em andamento.

## F — Testes locais

**47 testes executados, 47 aprovados, zero falhas finais.** Incluem autenticação real mockada, remoção do bypass, autorização Master, rejeição de anônimo/inativo/outros perfis, fechamento/rateios/valores, população/capacidade, receita/matrícula, PE, versões, ausência de escrita, preservação dos módulos/localStorage e resposta após logout.

Sintaxe de todos os scripts inline e dos módulos novos aprovada. SQL foi revisado e verificado estaticamente; não houve execução nem certificação das policies reais. Prévia isolada no navegador confirmou 41 linhas, R$ 25.677,35, aviso de dados insuficientes, logout e console sem erros. Nenhuma chamada dessa prévia foi ao Supabase real.

## G–I — Preservações

- R$ 25.677,35: SIM.
- 41 turmas: SIM.
- 50 professores: SIM.
- Snapshot de fechamento não alterado.

## J — Ações controladas restantes no Supabase

1. Conferir schema, funções e policies reais; fazer backup protegido antes de qualquer aplicação.
2. Aplicar o pré-requisito de perfis SOMENTE se necessário e revisar as duas tabelas aditivas antes de aplicá-las.
3. Carregar o snapshot aprovado e as evidências financeiras de 2027, com metadados, versões e fontes reais. Comprovar mensalidades/bolsas, alunos, despesa mensal e composição da folha, sem duplicidade.
4. Testar RLS com sessões Master, promotora/comum, inativo e anônimo, preferencialmente primeiro em ambiente Supabase de teste, incluindo negação de escrita nas novas tabelas.
5. Fazer a homologação real somente em leitura. Qualquer divergência com o armazenamento legado deve ser informada, sem migração automática.

## K — Arquivos preparados para futuro commit

index.html; finance-2027.js; finance-2027-ui.js; .gitignore; .vercelignore; vercel.json; package.json; tests/finance.test.cjs; tests/preview.py; review/additive-schema.sql; review/profiles-rls-prerequisite.sql; PORTABILIDADE.md; REVISAO-PRE-PUBLICACAO.md.

Excluir private/, .env e .vercel/. Os testes documentais locais exigem o snapshot e a referência original guardados em private, fornecidos por canal institucional protegido; não colocá-los no GitHub público. Nenhum dado real integra os fixtures numéricos de PE.

O SQL original e README original não foram alterados. Esta pasta continua sendo uma importação da main; aplicar o conjunto revisado sobre um checkout normal do repositório antes do futuro commit, sem force-push ou recriação de histórico.

## L — Encerramento

Nenhum SQL real, alteração de RLS real, escrita Supabase, commit, push ou deploy. As pendências locais desta revisão foram resolvidas; a integração real depende exclusivamente das ações controladas de Supabase acima. Não é declaração de homologação da base real já concluída.
