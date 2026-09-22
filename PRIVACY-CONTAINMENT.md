# Auditoria e contenção de privacidade — 22/09/2026

O repositório foi confirmado público pela API anônima do GitHub. A branch
`codex/pe-2027-fechamento-20260922` apontava para
`8be76a1433a71181b91162bc32a05ef30c1f4e99`, idêntico ao checkout auditado.

Foram examinados 187 arquivos do checkout, 40 commits locais alcançáveis e
409 objetos, com conferência dos quatro ponteiros de branches públicas.
Não havia tags, pull requests ou releases na consulta pública. A inspeção
abrangeu literais de código, snapshots JSON, documentos, XML da planilha de
teste e versões históricas. O inventário contém somente caminhos, categorias
e contagens: `PRIVACY-AUDIT-20260922.json`.

## Resultado

- 51 arquivos classificados como privados na versão original: 49 retirados
  do índice e 2 módulos de código saneados (`services.py`, `pe_full_audit.py`).
- 43 caminhos com identificadores pessoais no histórico. A branch auditada
  e as duas branches `recovery/validated-*` contêm versões afetadas.
- Nenhum segredo privilegiado confirmado. As ocorrências analisadas eram
  credenciais sintéticas de testes, padrões de conexão ou uma chave pública
  de cliente. Não foram usados tokens encontrados para autenticar em serviços.
- Os snapshots agregados e os relatórios internos também foram retirados
  por conterem informações operacionais/financeiras internas.
- Nenhuma alteração no banco, matrículas, benefícios, descontos, PE ou deploy.

As classificações refletem a inspeção estática efetuada, incluindo padrões de
credenciais e identificadores extraídos dos registros. Não constituem garantia
de detecção de qualquer segredo arbitrário ou de ausência de cópias externas.

## Preservação e execução local

Todos os arquivos originais e um bundle com o histórico anterior foram
copiados para uma pasta de salvaguarda fora do repositório; os arquivos foram
verificados por hash. As cópias retiradas do índice permanecem também em seus
caminhos locais, ignoradas pelo Git e excluídas dos uploads pela `.vercelignore`.

O código público usa `private_artifacts.py` e a variável
`SCHOOL_PRIVATE_DATA_DIR`, com padrão local `private/runtime/`. A configuração
privada foi provisionada localmente, sem mudar os snapshots. Os módulos
`personnel_projection.py`, `personnel_evidence.py`, `teaching_projection.py`
e `scripts/approved_preview.py` preservam as interfaces/lógica necessárias e
obtêm os registros fora do código público.

Um clone público não contém dados de produção. As funcionalidades que precisam
desses dados exigem provisionamento privado explícito e falham quando ele
falta; não são preenchidas com valores inventados. Não publicar esta versão
antes de definir e validar esse provisionamento no ambiente de destino.

Validação: sintaxe Python; importação da aplicação em cópia sem arquivos
privados, com conexões de rede e SQLite bloqueadas; quatro testes sintéticos;
igualdade das evidências privadas antes/depois; leitura e integridade do
snapshot aprovado; igualdade byte a byte dos quatro snapshots preservados.
Não foi executado recálculo de PE nem teste contra produção. A suíte operacional
completa não foi executada: parte dela depende das evidências privadas.

## Operação pendente — requer aprovação humana

O commit local de saneamento não elimina versões públicas anteriores.
Nenhum push, force-push ou reescrita foi realizado. A exposição pública permanece.

Após aprovação, usar um clone espelho isolado e recente, com salvaguarda, para:

1. Expurgar de todas as referências afetadas os 49 caminhos listados em
   `PRIVACY-PURGE-PATHS.txt`, inclusive eventuais nomes históricos/renomeados.
2. Substituir somente os literais/comentários pessoais nas versões históricas
   de `services.py` e `pe_full_audit.py`, preservando sua lógica. Manter as
   substituições com valores privados exclusivamente fora do Git.
3. Usar `git-filter-repo --sensitive-data-removal`, revisar a árvore saneada,
   reaplicar o commit de saneamento se necessário e repetir a auditoria de
   todos os objetos/referências. Não remover integralmente os dois módulos
   legítimos nem efetuar um push espelho indiscriminado.
4. Conferir se os ponteiros remotos continuam iguais aos auditados e coordenar
   a pausa de colaboração. Só então publicar as referências reescritas com
   proteção contra alterações remotas concorrentes, após aprovação explícita.
5. Solicitar ao GitHub Support a remoção de objetos/visualizações em cache
   ainda acessíveis. Orientar colaboradores a refazer clones e impedir a
   reintrodução do histórico antigo. Cópias já baixadas por terceiros não
   podem ser recolhidas por uma reescrita.

A mudança temporária de visibilidade para privado é uma contenção adicional
recomendada, mas não foi executada. Antes de qualquer publicação remota,
garantir que integrações de deploy não disparem automaticamente: o usuário
proibiu novo deploy.

Referência: [GitHub — Removing sensitive data from a repository](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository).
