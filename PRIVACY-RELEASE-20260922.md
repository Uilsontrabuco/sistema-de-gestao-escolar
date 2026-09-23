# Saneamento e retomada operacional

Código publicado por push normal na branch `codex/pe-2027-fechamento-20260922`: `8ed063e362bc3c973eb9471beba37299300289c2`.

A versão atual exclui os 49 caminhos privados do índice Git e do pacote de implantação. Dois módulos adicionais tiveram literais privados externalizados. As cópias originais continuam preservadas fora do Git. A revisão dos 152 arquivos públicos não encontrou os nomes pessoais usados como referência na auditoria. Não houve force-push nem reescrita histórica; o histórico anteriormente publicado permanece uma pendência de privacidade. O plano está em `PLANO-EXPURGO-HISTORICO-PRIVACIDADE.md`.

Os artefatos necessários ao servidor foram armazenados no schema privado já existente, com acesso público bloqueado e verificação de integridade. Nenhum dado privado foi incorporado ao pacote de implantação. A assinatura do snapshot aprovado dos 41 PEs foi preservada.

Conforme a autorização posterior para retomar benefícios, a base recebeu 1.016 benefícios previstos, com rollback lógico preservado: 902 aguardam matrícula nominal e 114 precisam de conciliação de turma. Nenhum benefício foi ativado automaticamente. Permaneceram 775 matriculados, 41 turmas e capacidade de 1.103 vagas. A versão de estado passou de 4 para 5; a operação restringiu alterações ao campo de benefícios. Portanto, houve atualização autorizada da base, sem alteração da base acadêmica ou dos PEs.

O resumo financeiro exibe os descontos e receitas conhecidos entre os registros classificados. Permanecem 763 matrículas sem classificação financeira comprovada. Ausência de classificação não significa desconto zero.

Validação: 295 testes Python, 92 testes JavaScript e testes estáticos SQL aprovados. Um erro transitório de conexão local ocorreu em uma execução Python; o teste isolado e a repetição integral passaram. Build público validado sem artefatos privados. A candidata exibiu os 41 PEs, as contagens de benefícios e os indicadores financeiros corrigidos; foi promovida para produção. A saúde HTTP da produção respondeu 200 após a promoção. A sessão administrativa foi renovada e a interface de produção exibiu os 41 PEs, os 775 matriculados e as contagens esperadas de benefícios. A assinatura do JavaScript público corresponde à versão local validada. Os quatro caminhos privados testados na aplicação responderam 404. O repositório GitHub continua público.
