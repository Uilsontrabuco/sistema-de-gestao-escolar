# 7&7 Gestão Escolar CAJ — evolução de 10/09/2026

> Registro da primeira etapa, preservado como histórico. A evolução posterior com servidor, login, importações e validação está descrita em `ENTREGA-VALIDACAO.md`; as instruções atuais estão em `README.md`.

## Estado encontrado

Os três arquivos existentes foram lidos integralmente antes das alterações: `index.html`, `app.css` e `app.js`. Não havia backend, dependências, controle Git, testes ou instruções AGENTS.md na pasta. A aplicação é JavaScript puro, com navegação em memória e persistência em `localStorage`, sob a chave `seven_caj_school_v1`. A chave antiga `seven_tasks_v1` alimenta a migração de tarefas.

Matrículas já possuía criação, edição e exclusão de lançamentos com atualização dos quantitativos das turmas. Esses fluxos foram mantidos. Responsáveis e Relatórios eram telas de espera. A importação anterior apenas armazenava o nome de um arquivo; não lia suas células. Permissões eram apresentadas sem aplicação na interface.

Nenhum dado do navegador em uso foi substituído. Os testes automatizados usam dados de teste exclusivamente em memória, sem comunicação com o armazenamento do navegador. A navegação visual foi verificada em uma origem local separada, sem criar cadastros.

## Alterações por módulo

| Módulo | Evolução |
| --- | --- |
| Painel Executivo | Cards compactos, meta com realizado/percentual/faltante, vagas por turma e excedentes separados, gráfico dos últimos seis meses, ocupação por turma, orçamento, inadimplência, solicitações, benefícios e alertas derivados. Estados vazios sem valores inventados. |
| Matrículas | Preservados lançamento, edição e estorno. Quantidade inteira positiva, data obrigatória, checagem de saldo antes de editar/excluir, percentuais acima de 100% exibidos corretamente, filtros e integração com relatórios. |
| Turmas e vagas | Cards de capacidade operacional, alunos, vagas e excedentes; busca e filtro de situação; campos numéricos não negativos; vagas disponíveis nunca negativas. |
| Benefícios | Indicadores de ativos/inativos e quantidade ativa, busca e situação; CRUD existente preservado. A quantidade pode conter sobreposição entre benefícios, sem ser apresentada como alunos únicos. |
| Solicitações | Indicadores de status e atrasos com data local, busca/filtro, consulta do histórico de mudanças e descrição. Fluxo e edição originais preservados. |
| Orçamento | Orçado, realizado, saldo e execução integrados; novas despesas guardam data, descrição, valor e responsável; consulta do histórico sem inventar detalhes de despesas antigas. |
| Inadimplência | Indicadores agregados integrados ao painel e relatório, validação de valores e contagens e data de atualização nas novas edições autorizadas. Os registros antigos de nomes de arquivos permanecem disponíveis. |
| Responsáveis | Cadastro e edição de contatos reais, vínculo e referência textual opcional do aluno; busca, indicadores e relatório. Cadastro condicionado à permissão explícita de edição. |
| Usuários | Dados exibidos com escape de HTML; permissões existentes aplicadas aos controles de edição. Limite da segurança local explicado na tela. Não foi criada administração fictícia. |
| Relatórios | Resumo executivo, turmas, histórico de matrículas, orçamento, benefícios, solicitações, inadimplência e responsáveis. CSV com proteção contra fórmulas, busca, impressão e exportação JSON de backup. O CSV considera a busca ativa. |
| Tarefas e Equipe | Funcionalidades anteriores mantidas. Lista vazia de tarefas não reintroduz mais tarefas antigas durante normalização. |

## Melhorias compartilhadas

- Identidade azul/amarelo, ajustes da marca e menor espaçamento, tabelas roláveis e grades responsivas.
- Rótulos de formulário associados aos campos, estados de foco, diálogo acessível, Escape, ciclo de foco, avisos anunciados e menu móvel fechado fora da navegação por teclado.
- Falhas de gravação restauram o estado em memória confirmado e não exibem sucesso.
- Cada alteração salva mantém a versão anterior em `seven_caj_school_v1_backup`. É uma única versão anterior, não um histórico completo. Relatórios permite exportar um backup JSON completo.
- Atualização por eventos de armazenamento entre abas; edição aberta diante de alteração externa bloqueia novos salvamentos até recarregar.
- A interface informa que os dados são locais. Não afirma sincronização com nuvem.
- Importação de planilhas identificada como pendente, sem registrar novas falsas importações.

## Arquivos

- `index.html`: acessibilidade estrutural e carregamento da evolução incremental.
- `app.js`: ajustes pontuais nos fluxos existentes, integração e inicialização após o carregamento das extensões.
- `app.css`: estilos responsivos, impressão e identidade.
- `enhancements.js`: painel, relatórios, responsáveis, indicadores, histórico, validação e persistência.
- `tests/regression.cjs`: testes isolados sem dependências externas.
- `DESENVOLVIMENTO.md`: este registro.

## Verificação

Executar na pasta do projeto:

```powershell
node --check app.js
node --check enhancements.js
node tests/regression.cjs
```

Os 11 testes cobrem renderização vazia, migração, criação/edição/estorno de matrícula, meta e relatórios, quantidades inválidas, vagas/excedentes, despesas, permissões, escape e falha de armazenamento.

Verificação visual realizada no navegador do aplicativo: abertura de todos os módulos, console sem erros de JavaScript, painel em desktop e largura de 390 px sem transbordamento horizontal, menu móvel, modal de meta rejeitando valor negativo e troca do tipo de relatório. A instalação do agent-browser falhou por falta de espaço em disco; utilizou-se o navegador já disponível. Downloads e impressão não foram validados de ponta a ponta. Testes em memória não substituem validação futura com uma cópia autorizada de dados reais.

## Limites e próximas melhorias

1. Implementar backend, autenticação, autorização no servidor e política administrativa. Hoje o primeiro perfil de `users` representa o perfil local; não existe login ou troca autenticada. O perfil original não recebeu novas permissões: Responsáveis exige `Editar responsáveis`, Inadimplência exige `Editar inadimplência` e administração exige `Administrar usuários`. A interface não é uma barreira de segurança contra acesso pelo console.
2. Implementar importação real com mapeamento, prévia, validação e confirmação antes de gravar. Os nomes de arquivos antigos não comprovam importação de valores.
3. Criar restauração assistida de backup com prévia e recuperação por versão. Manter a mesma origem do navegador para acessar dados locais existentes: outro endereço, porta ou navegador utiliza outro armazenamento.
4. Introduzir ano letivo, período financeiro e metas segmentadas sem reclassificar silenciosamente registros antigos. Atualmente contadores são totais registrados; o gráfico usa apenas lançamentos datados dos últimos seis meses.
5. Evoluir de quantidades para alunos identificados e vínculos estruturados com responsáveis. A referência textual atual não altera matrículas nem os totais de inadimplência.
6. Conciliar títulos, pagamentos e inadimplência por responsável. Hoje os valores financeiros de inadimplência são informados manualmente; não são calculados a partir de pagamentos.
7. Adicionar paginação e testes de acessibilidade, impressão e exportação em navegadores diferentes, usando uma cópia autorizada de dados reais. Depois, consolidar gradualmente a camada incremental em módulos, mantendo testes de regressão.
