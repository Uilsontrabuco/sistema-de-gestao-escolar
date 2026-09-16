# 7&7 Gestão Escolar CAJ

Aplicação existente evoluída com servidor Python, SQLite, login, permissões e sincronização por eventos. Não há usuários, alunos, turmas ou despesas de demonstração na base real. Ponto de Equilíbrio não faz parte desta versão.

## Iniciar a base real

Na pasta do projeto, com Python 3.11 ou superior:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe server.py --create-admin
.\.venv\Scripts\python.exe server.py
```

O primeiro comando administrativo solicita seu nome, e-mail e senha (mínimo 12 caracteres). Não existe senha padrão. A senha é armazenada com scrypt e salt; as sessões ficam no servidor, com cookie HttpOnly e proteção CSRF.

Abra [Gestão Escolar local](http://127.0.0.1:8765). O banco real será criado em `data/caj.sqlite3` somente quando você executar o servidor/cadastro inicial. As bibliotecas adicionais são usadas para XLSX, PDF e logo; a aplicação não baixa dependências ao ser aberta.

## Dados locais já existentes

Não limpe o armazenamento do navegador. A chave `seven_caj_school_v1` e a migração de tarefas antigas foram mantidas. A leitura não grava automaticamente a migração do modelo.

Os dados locais pertencem à origem onde eram usados (navegador, endereço e porta). Para a migração, inicie o servidor na mesma origem HTTP que você usava, quando aplicável. Em Usuários, um administrador pode revisar e confirmar a migração para uma base compartilhada vazia. As contas de login não são importadas automaticamente e a cópia local permanece preservada.

Se os dados anteriores eram abertos via `file://` ou em outra origem, não faça uma migração vazia: preserve/exporte o backup na origem antiga. A restauração assistida de arquivo de backup entre origens ainda precisa ser implementada; não há substituição automática da base. Contas escolares reais devem ser cadastradas pelo administrador, com permissões explícitas.

### Conferência de matrículas

A meta inicial é **1.065 alunos**, mas pode ser ajustada por um administrador. Total oficial = rematrículas + alunos novos. Saldos antigos sem essa divisão permanecem em `unclassified` e `legacyStudents`, com aviso na interface; contadores globais sem turma ficam em `enrollments.unallocated`. Não são atribuídos arbitrariamente a uma turma ou tipo.

A base inicial de Matrículas 2027 CAJ contém 41 turmas reais, organizadas por etapa. Em cada uma, “Matriculados” é o total da turma; “Alunos novos” é uma parcela desse total e as rematrículas são calculadas por diferença, evitando dupla contagem. A migração substitui apenas as 16 turmas-modelo que estejam vazias, sem lançamentos e sem saldos; turmas e dados existentes permanecem intactos.

Antes de conferir saldos iniciais, verifique se os quantitativos globais sem turma já fazem parte deles, para evitar duplicação na conciliação. A vinculação assistida desses contadores globais depende da conferência dos arquivos reais. A tela não transforma automaticamente números desconhecidos em alunos novos ou rematrículas.

## Usuários e permissões

- Administrador: cadastrar, editar, ativar, desativar e excluir contas; definir permissões; administrar importação, logo e migração.
- Permissões por módulo: visualizar, criar, editar, excluir e aprovar solicitações. Para abrir o módulo, marque Visualizar além das ações desejadas.
- O perfil legado da Lívia mantém Matrículas, Benefícios e Solicitações com visualizar/criar/editar e pode visualizar Turmas e Vagas para consultar os mesmos indicadores. A edição de quantitativos de Matrículas não concede criação/exclusão de turmas, capacidade ou administração.
- Ao cadastrar a conta real da Lívia no servidor, atribua somente esses módulos, conforme a autorização vigente.
- Alterar permissões, desativar ou excluir encerra as sessões daquele usuário. O último administrador ativo é protegido. Exclusão preserva auditoria e identidade histórica.
- Dados escolares só podem ser alterados após autenticação no servidor compartilhado. Aberturas diretas do HTML e indisponibilidade do servidor não usam nem gravam `localStorage`; isso evita cópias divergentes entre usuários.

## Compartilhar entre computadores

SQLite é centralizado no computador do servidor; todos os navegadores autorizados devem acessar **o mesmo servidor**. A sincronização usa SSE e controle de versão para impedir gravações concorrentes silenciosas. Formulários abertos são preservados e solicitam revisão quando chegam alterações externas.

A configuração padrão atende somente `127.0.0.1`. Para uso institucional em rede, configure hospedagem/reverse proxy com HTTPS, certificados, firewall e backup do banco. Configure `CAJ_SECURE_COOKIE=1` no servidor HTTPS. Não publique o diretório do projeto com um servidor estático: o servidor fornecido publica somente os arquivos de interface autorizados, sem banco, referências ou código Python.

Ainda são recomendados revisão de segurança para produção, monitoramento, recuperação de senha e política de retenção/backup. Nenhuma hospedagem foi publicada nesta entrega.

## Importações

Disponíveis no servidor: XLSX, CSV e PDF com texto selecionável. XLS antigo e PDF digitalizado/OCR não estão implementados.

| Uso | Colunas reconhecidas |
| --- | --- |
| Orçamento | Categoria/Conta, Código, Orçado |
| Despesas realizadas | Data, Valor, Descrição/Finalidade; opcionalmente Código, Conta, Subconta, Documento |
| Financeiro | Mês/Competência, Financeira (%); opcionalmente Dívida, Alunos, Responsáveis |
| Contábil | Mês/Competência, Contábil (%); opcionais equivalentes |

Excel lê **somente `DESPESAS 2026`** no orçamento/despesas. CSV/PDF exige confirmação de que representa exclusivamente esse escopo. Despesas realizadas fora de 2026 são rejeitadas. PDFs devem ter tabelas textuais com cabeçalhos reconhecíveis; layouts diferentes exigem adaptação após receber os arquivos reais. Não há reconhecimento livre ou classificação por IA sem validação.

A prévia expira em 30 minutos e fica ligada ao usuário e à versão dos dados. Confirmar aplica as linhas válidas; duplicadas e inválidas não são aplicadas. Dúvidas de categoria ficam em Revisar classificação, sem somar ao realizado. Código/conta exatos e associações previamente confirmadas permitem classificação automática. A confirmação manual registra uma associação para próximas importações.

O identificador do documento deve ser informado quando disponível: a comparação conservadora de data/valor/descrição pode sinalizar duas despesas legítimas semelhantes como duplicadas. Revise o relatório antes de confirmar.

## Documentos e WhatsApp

Relatórios mantêm CSV, backup JSON e impressão pelo PDF institucional; adicionam PDF e XLSX. O PDF repete cabeçalho, rodapé e cabeçalho da tabela. A logo original, quando carregada pelo administrador, é usada no cabeçalho e na marca-d’água central com transparência. Sem a imagem, o PDF registra a pendência e não utiliza uma logo inventada.

Solicitações geram registros na fila de notificações em criação, mudanças de status e detecção de prazo vencido. Os registros ficam **aguardando configuração**, com tentativa de envio vazia. Não existe envio real de WhatsApp nesta versão. Ainda é necessário implementar/configurar o adaptador da API oficial, credenciais, número, templates aprovados, worker de envio e retorno de status. A detecção periódica de vencimento atual ocorre enquanto há sessão conectada; um agendador independente será necessário na publicação.

## Testes

```powershell
node --check app.js
node --check enhancements.js
node --check domain.js
node --check professional.js
node tests/regression.cjs
node tests/domain.cjs
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

Os testes usam fixtures e bancos temporários, nunca `data/caj.sqlite3`. Para QA visual isolado: `python tests/visual_server.py` usa exclusivamente a porta 8877 e um banco temporário removido ao encerrar. As credenciais existentes nesse arquivo são exclusivas de teste; nunca as utilize na instalação real.

Veja `ENTREGA-VALIDACAO.md` para resultados e `references/LEIA-ME.md` para os materiais pendentes.
