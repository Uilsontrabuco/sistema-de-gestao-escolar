# Recuperação e auditoria — 7&7 Gestão Escolar CAJ

Data: 15/09/2026. Publicação bloqueada; nenhuma alteração de código ou banco aplicada nesta execução.

## Recuperação e procedência

- Remoto confirmado: https://github.com/Uilsontrabuco/sistema-de-gestao-escolar
- Proprietário: Uilsontrabuco. Repositório público, não arquivado.
- Única branch remota encontrada: main.
- Último commit: 08db894673bf82c102f05dc9ba2bfe29c1eccc87, de 09/09/2026 às 15:32:29 (America/Sao_Paulo), mensagem `Update supabaseAnonKey in index.html`.
- Histórico remoto: quatro commits; contém README-7E7.md, index.html e supabase_schema.sql.
- Clone recuperado em `C:\Users\Uilson Trabuco\Desktop\7e7-gestao-escolar\recovery\github-main-20260915`. Branch main acompanhando origin/main; árvore de trabalho limpa, sem alterações locais.
- O HTML remoto corresponde ao original preservado em supabase-port/private/upstream-index.html após normalizar quebras de linha. Isso confirma a procedência, mas não significa que o remoto contenha as melhorias posteriores.

A pasta principal estava ausente e reapareceu durante a execução. A tentativa de clone no caminho principal foi cancelada pelo teste de existência antes de escrever. A pasta reaparecida contém Python, JavaScript, testes, referências e a portabilidade Supabase; não contém .git. A origem dessa restauração não foi confirmada nesta execução. Nenhum conteúdo existente foi sobrescrito. Sem .git nessa pasta, não há branch/commit nem diff histórico atribuível às alterações recentes.

## Arquitetura e configuração

- Aplicação local: frontend HTML/CSS/JavaScript; backend Python, SQLite e endpoints /api; dependências declaradas reportlab, pypdf, pdfplumber, openpyxl e Pillow.
- Portabilidade em supabase-port: HTML/JavaScript estático e Supabase JS, Auth, leitura de profiles e consulta financeira protegida para Master ativo.
- Os módulos legados da versão Supabase ainda usam localStorage; não foram migrados automaticamente para o banco.
- Configuração pública do Supabase na versão preparada é fornecida pelo navegador; não há confirmação de valores atualmente salvos em navegadores reais.
- O endpoint embutido no HTML remoto antigo difere do projeto Supabase acessível. A versão preparada já removeu essa configuração embutida; nenhum valor foi copiado para código.
- vercel.json configura aplicação estática, buildCommand vazio e outputDirectory `.`. package.json declara somente test, sem build, lint ou type-check. Não existe build de produção compilado a executar; não se certificou publicação/empacotamento Vercel.
- Diretório private, arquivos de ambiente, SQL e materiais administrativos têm exclusões preparadas na portabilidade. A pasta principal inteira não deve ser publicada como site estático.

## Funcionalidades e regras verificadas

Os testes atuais cobrem Matrículas/Turmas e Vagas, Solicitações, permissões, relatórios, orçamento/receita, Carga Horária, Custeio Docente e Ponto de Equilíbrio. Os testes da portabilidade verificam preservação dos módulos legados e de seu armazenamento, login Supabase mockado, negação de acesso financeiro a perfis não autorizados e invalidação de consultas após logout. Isso não substitui homologação com sessões reais.

- Tarifas 2027 presentes: Educação Infantil e Fundamental I R$ 16,20; Fundamental II R$ 26,11; Ensino Médio R$ 38,50.
- Durações 40/45/50 minutos preservadas nos testes.
- Rateios, conservação de centavos/minutos, rejeição de duplicidade e decisões posteriores para 5º ano/G5 e compartilhamentos presentes e testados.
- Fechamento local validado pelos testes: R$ 25.677,35 semanais, 50 professores e 41 turmas, sem diferença financeira inexplicada ou duplicidade no fechamento testado.
- A pendência histórica de R$ 2.724,94/248 parcelas não foi assumida como pendência atual nem recalculada por estimativa. Existem testes posteriores de decisões finais e fechamento definitivo; eles preservam fontes e alocações previamente confirmadas. Nenhuma regra de negócio foi refeita.
- Snapshot privado: 10.908.137 bytes, SHA-256 `199b5c813e50988bbb2f6eb8e8d2771a97a9c62a117277a12678f1ae0beb20c9`, correspondente ao registro documental. Conteúdo não publicado.
- PE permanece indeterminado quando faltam evidências econômicas; não foi inventada mensalização ou receita.

## Testes desta execução

| Grupo | Aprovados | Falhas finais |
|---|---:|---:|
| Python: unittest discover em tests | 133 | 0 |
| JavaScript domínio | 14 | 0 |
| JavaScript regressão | 11 | 0 |
| JavaScript custeio | 4 | 0 |
| JavaScript operacional | 3 | 0 |
| JavaScript portabilidade Supabase | 51 | 0 |
| SQL estático: final_sql_static.py | 9 | 0 |
| **Total de casos** | **225** | **0** |

O runner Node reportou 57 entradas TAP porque três arquivos agregam internamente 29 casos. A contagem acima explicita esses casos, sem contar novamente os invólucros. Verificação adicional de sintaxe Python: 19 arquivos aprovados. Os testes da portabilidade também compilam scripts inline e módulos novos para verificar sintaxe.

As primeiras tentativas JavaScript e SQL foram bloqueadas por permissões locais de leitura. A repetição autorizada passou sem mudança de código e sem instalar dependências. Testes HTTP Python usam contas e SQLite temporários; nenhuma base escolar real foi usada para escrita.

## Supabase: situação real consultada em leitura

- Projeto acessível: pvsdlqspxfbfeepylfxc, status ACTIVE_HEALTHY.
- Objetos financeiros e seus comentários correspondem ao lote 7e7 documentado; isso relaciona o projeto acessível ao trabalho anterior.
- Contagens exatas: turmas = 0; teaching_cost_snapshots = 0; financial_evidence = 0.
- RLS habilitada nas tabelas públicas listadas. Políticas financeiras SELECT para authenticated exigem status approved e is_master().
- is_master está como SECURITY DEFINER com search_path vazio. Segurança completa e comportamento com identidades reais não foram homologados nesta execução.
- Staging anterior seven7_transport_2027_199b5c81.chunks contém 43 blocos; o histórico documenta 84 blocos esperados. O snapshot definitivo não foi inserido.
- Migration registrada: 20260915141536, seven7_snapshot_transport_begin.
- Nenhuma migration, carga, correção de policy, alteração de configuração ou limpeza foi executada. O staging foi preservado integralmente.

Mesmo que o transporte seja concluído, a consulta financeira exige vínculo com as 41 turmas reais; o cadastro remoto está vazio. Criar turmas ou evidências por suposição violaria os limites da missão. A carga não foi retomada automaticamente.

## Vercel e URL

- Equipe acessível: uilsontrabuco. Consulta de projetos retornou lista vazia.
- Consulta do deployment histórico nessa equipe retornou 404 Deployment not found.
- A URL https://sistema-de-gestao-escolar-woad.vercel.app/ respondeu HTTP 200 a uma consulta HEAD. Isso comprova resposta HTTP, não autenticação ou funcionamento completo.
- Não foi possível confirmar a conta/projeto proprietário, variáveis ou configuração de publicação. Nenhum projeto duplicado foi criado.
- Nenhum deploy executado, portanto não há nova URL nem testes pós-deploy. Nenhuma sessão real de usuário foi criada ou utilizada.

## Alterações realizadas e próximos passos

Únicas adições deliberadas: clone separado do remoto confirmado e este relatório. Nenhum arquivo preexistente de aplicação foi editado. Nenhum commit criado, push ou deploy efetuado.

Para prosseguir com segurança:

1. Confirmar a origem da pasta principal reaparecida, preservando essa cópia e os dados privados. O remoto de 09/09 não substitui as melhorias locais.
2. Disponibilizar acesso à conta/projeto Vercel que realmente possui a URL, sem criar duplicado.
3. Reconciliar as 41 turmas com uma fonte institucional aprovada e confirmar o estado do transporte anterior antes de completar qualquer carga. Não inventar vínculos, receita ou evidências.
4. Homologar autenticação/RLS com identidades autorizadas e configuração real; integrar somente os arquivos publicáveis ao checkout Git após revisão, mantendo dados privados fora do repositório público.
5. Validar o artefato estático e o ambiente de publicação antes de commit/push/deploy, conforme as condições da missão.

A publicação foi interrompida pelas condições críticas não satisfeitas; testes locais aprovados não eliminam os bloqueios de configuração e dados de produção.
