# Portabilidade do custeio / PE 2027

Estado consolidado mais recente: review/LOTE-FINAL.md. São 51 testes locais aprovados. Configuração embutida removida; conexão permanece pelo mecanismo de configuração pública do navegador. A correção de is_master() está preparada e condicionada à introspecção real do owner, sem aplicação.

SQL/RLS vigente: review/SQL-FINAL-REVISAO.md. A autorização final usa public.is_master() existente e não altera perfis. Propostas anteriores de correção de perfis estão canceladas.

Atualização: a revisão pré-publicação removeu o login de demonstração, versionou as tabelas propostas e ampliou a bateria para 47 testes. Consulte REVISAO-PRE-PUBLICACAO.md para o estado atual; os achados e a proposta inicial abaixo registram a etapa anterior.

## Origem confirmada

Repositório: https://github.com/Uilsontrabuco/sistema-de-gestao-escolar

Branch de origem: main. Commit consultado: `08db894673bf82c102f05dc9ba2bfe29c1eccc87`.

O index.html original importado é idêntico, byte a byte, ao HTML publicado em https://sistema-de-gestao-escolar-woad.vercel.app/ na verificação desta execução. SHA-256: `9059caddceec6cb124107e294dfd06230cf5752138da386058aec6b47e748ac1`.

Importado pelo arquivo oficial da main do GitHub. O executável Git local não dispõe de remote-https; esta pasta não contém histórico .git. Antes do commit, aplicar os arquivos revisados a um checkout normal deste mesmo commit/repositório, preservando o histórico. Não fazer git init e force-push desta pasta.

## Arquitetura efetivamente encontrada

HTML/JavaScript estático, Supabase JS v2, autenticação signInWithPassword, perfil em profiles e configuração existente em window.SEVEN7_CONFIG/localStorage. A aplicação já contém 41 turmas no cadastro inicial.

O Supabase é usado para autenticação e profiles. Os módulos originais persistem state em `localStorage['77state']`; não foi encontrado CRUD Supabase para esses módulos no index.html original. Não houve migração automática nem substituição desse armazenamento.

Schema versionado: profiles, turmas, alunos, solicitacoes, beneficios_matricula, orcamento_contas, orcamento_importacoes, inadimplencia_importacoes e inadimplencia_indicadores. Papéis master, promotora e comum. O schema original permaneceu byte a byte intacto e NÃO foi executado.

## Inventário portado

| Trabalho validado | Destino / tratamento |
|---|---|
| Fechamento docente | Snapshot integral privado, sem recalcular tarifas: 50 professores, 41 turmas, 2.567.735 centavos semanais, 0 pendências/duplicidade |
| Aulas e rateios | Preservados no snapshot: 40/45/50 minutos, frações financeiras, evidências, pools e 42 observações documentais |
| 5º ano | Frações da regra aprovada preservadas; nos compartilhamentos maiores, a parcela destinada ao par do 5º ano continua igualmente dividida, sem dobrar a aula |
| Tarifas FII/EM | R$ 26,11 / R$ 38,50 preservados, sem reajuste novo |
| Custeio por turma | Vinculação única por nome canônico ao cadastro turmas; exige exatamente 41 IDs e nomes únicos; não cria turma |
| Conciliação | Valida soma das turmas, parcelas únicas, rateios exatos em BigInt e duração documental |
| Financeiro / PE | JavaScript puro; valores em centavos; PE arredondado para cima; sem nova adição de docência ao orçamento |
| Receita | 11 mensalidades; matrícula separada; dados individualizados prevalecem; bolsas e descontos explícitos, sem valores padrão |
| Mensalização | Continua não determinada; custo orçamentário mensal documentado permite calcular PE independentemente disso |
| Interface | Consulta adicional Custeio / PE 2027, protegida por sessão Supabase e perfil Master ativo, sem alterar módulos existentes |

Nenhum código Python/SQLite foi levado ao runtime de produção. O Python em tests/preview.py serve apenas a prévia local isolada, excluída da publicação.

## Arquivos

- index.html: correção de um fechamento `};` ausente no objeto de configuração (erro sintático já presente na publicação), mais referências aos dois scripts novos. Valores de configuração não alterados.
- finance-2027.js: cálculo, validação do fechamento e consultas Supabase exclusivamente de leitura.
- finance-2027-ui.js: consulta adicional, permissão Master e limpeza dos dados exibidos no logout.
- .vercelignore / vercel.json: exclusão e bloqueio de arquivos privados, SQL e testes na publicação estática.
- .gitignore: impede inclusão acidental de private, .env e configurações locais.
- package.json / tests/finance.test.cjs: testes isolados com mocks, sem dependências npm adicionais.
- tests/preview.py: navegador de QA com SDK remoto removido e Supabase simulado; somente loopback.
- review/additive-schema.sql: proposta de DUAS tabelas adicionais, não executada.
- private/teaching-cost-2027.json: fechamento integral, fora de Git e deploy. Guardar em armazenamento institucional protegido; não publicar no repositório público.
- private/upstream-index.html e upstream.json: referência de regressão/proveniência, excluída de Git/deploy.

## Contrato das evidências financeiras

A nova consulta lê `teaching_cost_snapshots.payload` e `financial_evidence.payload`, ambos por year=2027. Essas tabelas não existem no schema versionado original. A proposta cria somente as novas tabelas, com SELECT para authenticated condicionado ao Master, sem autorização de escrita ao frontend. Não modifica tabelas/políticas existentes.

O snapshot docente deve ser disponibilizado por um procedimento administrativo revisado, preservando o arquivo integral e seus hashes. Nenhum carregamento remoto foi realizado. Não há botão de importação ou escrita no novo módulo.

`financial_evidence.payload` deve conter year=2027, status=verified, source documental e classes vinculadas pelos UUIDs reais de turmas. Cada evidência monetária exige status=verified, source, period=monthly e amountCents inteiro. Matrícula usa period=year e fica separada da receita mensal. Não usar totais anuais como mensais.

Campos gerais: totalExpenses (despesa mensal consolidada já contendo pessoal), enrollmentRevenue (matrículas do ano) e classes. Cada classe requer:

- classId: UUID real.
- population: year, studentCount, status e source comprovando o exercício; quantidade deve coincidir com turmas.matriculados.
- recurringRevenue: fonte mensal líquida; preferir students com id, tuitionCents e discountBasisPoints documentados. Agregado somente com studentCount coincidente e fonte explícita. Não adicionar matrícula. Receita deve estar na base econômica aprovada; não aplicar inadimplência duas vezes.
- totalCost: custo mensal total já incluindo docência quando ela está no orçamento; economicSourceId identifica uma parcela econômica exclusiva. Uma fonte repetida entre turmas bloqueia ambas até conciliar seu rateio.
- otherDirect / indirect: opcionais, componentes informativos do total, nunca nova adição automática ao totalCost.

Não foram criadas evidências financeiras fictícias para produção. Exemplos numéricos existem somente nos testes excluídos do deploy. Sem evidência mensal/população válida, PE e resultado permanecem não determinados.

## Testes

38 testes Node aprovados, zero falhas finais. Cobrem fechamento, tarifas, durações, rateios, duplicidade, ano, população, mensalidade/matrícula, descontos, PE, fontes econômicas repetidas, permissão Master, negação por RLS simulada, login/logout existentes e preservação dos scripts/schema originais.

Sintaxe dos scripts inline e novos validada. Prévia de navegador em localhost com Supabase simulado: consulta renderiza R$ 25.677,35, 41 turmas, diferença e acréscimo R$ 0,00; ausência de evidências aparece como não determinada; console sem erros. Os 165 testes da cópia anterior não foram promovidos a testes Supabase nem somados a esta bateria.

## Segurança e impedimentos para publicação

1. **Schema real/RLS ainda não inspecionados:** não executar supabase_schema.sql. O schema versionado possui policies de profiles que chamam is_master(), função que volta a consultar profiles; essa estrutura exige conferir possível recursão de RLS e leitura do próprio perfil, especialmente de promotora/comum. Os mocks não certificam policies reais. A proposta de tabelas novas depende dessa revisão.
2. **Login de demonstração herdado:** existem credenciais de demonstração embutidas e fallback quando não há cliente Supabase. Nenhum valor é reproduzido neste relatório. O fluxo foi preservado conforme solicitado, mas precisa ser desativado antes de homologar produção. Se alguma senha de demonstração tiver sido reutilizada em conta real, trocar essa senha no provedor com segurança.
3. **Módulos operacionais locais:** a persistência original é localStorage. É necessário comparar esses dados com turmas/alunos no Supabase; esta portabilidade não presume que sejam sincronizados. Não apaga, substitui ou migra nenhum deles.
4. **Snapshot/evidências protegidos ainda não disponibilizados no banco:** o frontend consulta, não escreve. Revisar a proposta aditiva, as permissões e o carregamento administrativo antes de habilitar o módulo em produção.
5. **Credenciais:** não detectado literal service_role/JWT administrativo, chave privada ou sb_secret na importação auditada. A configuração pública existente foi preservada; nenhum segredo novo foi adicionado. Não usar service_role no navegador.
6. **Publicação:** confirmar Root Directory da Vercel para o checkout correto e validar exclusões de arquivos privados antes de upload. Nenhuma configuração remota foi alterada.

O código portado passou nos testes isolados, mas NÃO está liberado para produção enquanto esses impedimentos não forem resolvidos. Não houve commit, push, deploy, SQL executado ou alteração de dados reais.
