# Recuperação de produção — continuidade de 15/09/2026

## Resultado

Código e dados encontrados foram preservados. Nenhum arquivo preexistente de aplicação foi alterado, nenhuma configuração de produção foi modificada e nenhum dado foi migrado. Publicação bloqueada por acesso Vercel ainda não restabelecido e por duas bases locais divergentes que não devem ser mescladas por suposição.

## 1. Salvaguarda da versão candidata

Backup integral criado antes de outras alterações em:

`C:\Users\Uilson Trabuco\Desktop\7e7-salvaguarda-20260915\projeto`

309 arquivos, 113.123.857 bytes. Manifesto SHA-256 na pasta da salvaguarda. Todos os hashes da origem e da cópia coincidiram. Uma conferência posterior dos 309 arquivos originais também não encontrou alterações.

A cópia principal apresenta CreationTime concentrado em 15/09 às 16:40:39–40, com LastWriteTime preservado de 10 a 15/09. Isso é compatível com cópia/restauração de arquivos anteriores, mas não identifica o autor ou mecanismo da restauração. O histórico do Codex, os relatórios, as suítes e o hash do snapshot financeiro corroboram a continuidade do trabalho. Não há .git na pasta principal; não é correto atribuir às alterações locais o commit remoto de 09/09.

## 2. Repositório e diferenças

Remoto: https://github.com/Uilsontrabuco/sistema-de-gestao-escolar

Checkout preservado: `recovery/github-main-20260915`, branch main, commit `08db894673bf82c102f05dc9ba2bfe29c1eccc87`, de 09/09/2026 às 15:32:29 (-03:00). O histórico remoto tem quatro commits e somente três arquivos: index.html, README-7E7.md e supabase_schema.sql.

O HTML original preservado corresponde ao checkout, normalizando quebras de linha. A versão local contém implementações posteriores que não estão nesse commit:

| Área | Implementações/evidências locais adicionais |
|---|---|
| Carga Horária | services.py, teaching_cost.py, fontes documentais e testes de extração, durações e conciliação |
| Custeio Docente | fechamento docente, referência de tarifas 2027, testes de integridade e consulta protegida |
| Rateio | teaching_pools.py; decisões finais do 5º ano/G5 e compartilhamentos; conservação de centavos/minutos e prevenção de duplicidade |
| Orçamento/PE | break_even.js, financial_integration.py, tratamento de evidências e ausência de mensalização presumida |
| Matrículas/Turmas | domain.js, professional.js, backend e testes de quantitativos, capacidade, permissões e auditoria |
| Solicitações | funcionalidades locais/backend, autorização e testes; módulo legado também preservado na portabilidade |
| Inadimplência | módulo e importação/persistência local; preservação do módulo legado na versão Supabase |
| Backend local | server.py, SQLite, autenticação/autorização e rotas /api, inexistentes no checkout remoto |
| Portabilidade Supabase | supabase-port/index.html, finance-2027.js, finance-2027-ui.js, testes, configuração Vercel e SQL revisado |

Os módulos antigos já existiam no HTML remoto; a tabela descreve a evolução local, não afirma que todos foram criados do zero. O inventário filtrado em `recovery/audit-20260915/inventario-codigo.json` registra 63 caminhos de código/testes/documentação, sendo 62 adicionais e index.html modificado. Materiais privados, fontes, saídas, backups e caches não foram classificados como arquivos publicáveis.

Nenhum commit foi criado: a condição do item 9 exige confirmação de repositório, Supabase, dados e Vercel antes de commit/push/deploy. O checkout e a cópia recente continuam separados para evitar publicar dados privados ou substituir o histórico por uma pasta sem Git.

## 3. Código efetivamente publicado

GET da URL https://sistema-de-gestao-escolar-woad.vercel.app/ retornou HTTP 200 e 44.329 bytes.

SHA-256: `9059caddceec6cb124107e294dfd06230cf5752138da386058aec6b47e748ac1`.

O conteúdo corresponde ao HTML remoto de 09/09 e ao original preservado. Não corresponde à portabilidade recente; finance-2027.js não está presente. O HTML publicado usa localStorage para os módulos escolares e só referencia profiles na integração Supabase identificada.

O endpoint embutido contém a referência `pvsdlqsppfbfleepylfxc`, de 21 caracteres. A API Supabase rejeitou essa referência por tamanho inválido (exige 20). Não é evidência de um segundo projeto Supabase válido. A cópia offline do localStorage da origem publicada não contém as configurações seven7_supabase_url/seven7_supabase_anon entre as chaves encontradas. Isso aponta para a configuração embutida inválida como problema do login, mas não substitui um teste de autenticação real.

## 4. Supabase acessível e dados

Único projeto listado pela conexão: `pvsdlqspxfbfeepylfxc`, ACTIVE_HEALTHY. Corresponde ao projeto do transporte anterior: os 43 blocos presentes coincidem com o snapshot local.

Contagens exatas, consultadas em transações somente de leitura:

| Tabela/grupo | Registros |
|---|---:|
| profiles | 2 |
| turmas | 0 |
| alunos | 0 |
| solicitacoes | 0 |
| beneficios_matricula | 0 |
| orcamento_contas / orcamento_importacoes | 0 / 0 |
| inadimplencia_importacoes / inadimplencia_indicadores | 0 / 0 |
| teaching_cost_snapshots / financial_evidence | 0 / 0 |

Conclusão: este é o destino comprovado do trabalho administrativo anterior, mas não contém a base escolar. A versão publicada armazena esses módulos no navegador; duas bases foram efetivamente encontradas ali. Não foi comprovada exclusão de registros nem existência de outro banco remoto com os dados. Nenhuma cópia entre projetos foi feita.

## 5. Transporte 43/84

- Snapshot original: 10.908.137 bytes, SHA-256 `199b5c813e50988bbb2f6eb8e8d2771a97a9c62a117277a12678f1ae0beb20c9`.
- Blocos de 131.072 bytes, exceto o último, com 29.161 bytes.
- Presentes: sequências 0 a 42, total de 5.636.096 bytes.
- Faltantes: sequências 43 a 83 inclusive, 41 blocos e 5.272.041 bytes.
- Todos os 43 hashes remotos correspondem ao trecho exato do snapshot local.
- Todos os bytes faltantes existem no arquivo local; não há necessidade de inventar conteúdo.
- Metadados e hashes registrados em `recovery/audit-20260915/chunks-remotos.json` e `transporte-validado.json`, sem conteúdo privado.

A transferência não foi completada. O cadastro de turmas precisa ser reconciliado com os dados reais e as condições de produção ainda não estão satisfeitas. Staging, registros e políticas permaneceram intactos.

## 6. Chrome: preservação e descoberta das bases

Perfil localizado: Default. Antes da análise, foi feita cópia estável do banco localStorage em:

`C:\Users\Uilson Trabuco\Desktop\7e7-chrome-salvaguarda-20260915`

11 arquivos, 6.506.874 bytes, hashes de origem/cópia conferidos. O arquivo LOCK, vazio e usado exclusivamente como trava de execução, não foi copiado. O Chrome permaneceu aberto: trata-se de uma cópia consistente dos arquivos persistidos conferidos, sem garantia sobre alterações ainda só em memória. Não foram copiados bancos de cookies, senhas ou histórico de navegação.

Como o localStorage usa um banco compartilhado entre origens, seus arquivos foram preservados integralmente; a análise filtrou somente chaves conhecidas do 7&7. O leitor offline verificou o manifesto de arquivos ativos, os checksums dos blocos/registros e a decodificação JSON. Nenhuma escrita foi feita no perfil original. Exportações privadas dos dois estados ficaram junto da salvaguarda, fora do Git e de qualquer publicação.

| Origem/chave | Conteúdo encontrado | Comparação |
|---|---|---|
| Site histórico, 77state | 41 turmas; 624 matrículas; 2 solicitações; 2 benefícios; 2 importações | Solicitações, benefícios e importações diferem do estado inicial. Turmas, usuários, orçamento, responsáveis e indicadores de inadimplência coincidem com os valores iniciais do HTML |
| Arquivo local, seven_caj_school_v1 | 41 turmas; 625 matrículas; 27 novas e 598 rematrículas; capacidade total 1.103 | Uma turma tem 10 matrículas em vez de 9 na versão publicada. Histórico de lançamentos vazio; não há evidência suficiente para decidir automaticamente qual total é oficial |

A base do arquivo local não possui academicYears nem breakEven e não contém lançamentos de solicitações, benefícios ou importações. Portanto, não substitui integralmente a base do site. A versão do site também não substitui automaticamente a matrícula adicional da base local. Nenhuma mesclagem foi feita.

Hashes SHA-256 das exportações UTF-8:

- Site: `dc3198fe69211ffd93223f25338fbc84ed54553c25a42631dbb5e286c89953c1`.
- Arquivo local: `8701f1f26c1b06be23899e2c78c608c8c44caa791cc90559e246b3879cc4cd64`.

Esses dados demonstram alterações salvas, mas não certificam administrativamente se cada registro é real ou de teste.

## 7. Identificação da Vercel e reconexão

O status oficial do commit no GitHub aponta para:

https://vercel.com/uilsontrabuco/sistema-de-gestao-escolar/8nR6jBZTZarWUEFZ5T2bJqvEX3VM

O deployment GitHub 6356692657 registra ambiente Production, status success e SHA 08db894673bf82c102f05dc9ba2bfe29c1eccc87. URL registrada:

https://sistema-de-gestao-escolar-ivjla0rfq-uilsontrabuco.vercel.app

Isso identifica historicamente conta/equipe, projeto e versão publicada. Porém, a conexão Vercel disponível retorna lista vazia e 404 para o projeto e para o deployment exato. Não há autenticação CLI Vercel nos caminhos padrão consultados. Nenhum projeto duplicado foi criado.

O usuário autorizou reconexão. A busca do gerenciador confirma Vercel instalada/habilitada; não há ferramenta de reconexão OAuth disponível nesta sessão. Foi apresentado o fluxo manual seguro pelos detalhes de Vercel na área de plugins instalados, sem pedir tokens ou senhas. Após a confirmação da reconexão, será necessário verificar novamente o projeto e o deployment antes de qualquer alteração.

## 8. Testes finais e preservação

Suítes repetidas nesta continuidade, sem modificar código de aplicação:

| Grupo | Aprovados | Falhas |
|---|---:|---:|
| Python | 133 | 0 |
| JavaScript: domínio/regressão/custeio/operacional/Supabase | 83 | 0 |
| SQL estático | 9 | 0 |
| **Total** | **225** | **0** |

Sintaxe Python: 19 arquivos aprovados. A suíte JavaScript inclui validação dos scripts inline e módulos financeiros. Autenticação/rotas são verificadas com fixtures/mocks e HTTP local temporário; não se declarou homologação real do login publicado ou de RLS com identidades reais.

A portabilidade é estática, com buildCommand vazio e sem script build/lint/type-check. Nenhum build/deploy Vercel foi executado. As regras 40/45/50 minutos, tarifas 2027 e fechamento de R$ 25.677,35 semanais continuam preservadas.

## 9. Pendências humanas indispensáveis

1. Concluir a reconexão Vercel com uma conta que efetivamente acessa o projeto identificado. Ainda não houve confirmação de conclusão desse fluxo.
2. Decisão expressa do usuário: manter ambas as bases e conferir antes de migrar. As origens de 624/625 matrículas permanecem separadas; a escolha administrativa do total vigente fica para essa conferência. Nenhuma migração está autorizada antes dela.

Depois disso: homologar identidade/configuração real, revisar uma conciliação explícita preservando registros das duas origens, preparar a integração Git apenas de arquivos publicáveis e repetir as verificações afetadas. A existência do snapshot local permite retomar seus blocos, mas não autoriza inventar turmas, evidências financeiras ou vínculos.

## 10. Alterações desta continuidade

Criados: salvaguardas externas, exportações privadas, metadados de diagnóstico, dois utilitários de leitura/comparação offline e este relatório. Nenhum arquivo anterior de aplicação foi alterado.

Commit: não criado. Push: não realizado. Deploy: não realizado. URL final nova: inexistente. Smoke pós-deploy: não aplicável. URL histórica continua respondendo HTTP 200 com código antigo.
