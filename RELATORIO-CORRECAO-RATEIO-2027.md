# Correção restrita do rateio docente — 13/09/2026

Implementação corrigida para os casos reproduzidos na auditoria. Os testes existentes de integridade foram preservados e reforçados. As 244 ocorrências reais continuam sem validação documental nesta sessão.

## Causas das seis falhas e do erro

| Resultado anterior | Causa | Correção |
|---|---|---|
| Falha 1: minutos nas turmas, 0 em vez de 45 | Só o custo era incrementado nas turmas | Cada parcela registra allocated_minutes = duração/n e incrementa os minutos e aulas proporcionais da turma conciliada |
| Falha 2: EMERE | Identificador operacional era aceito mesmo com status PENDENTE; havia fallback para turma agregada | Vínculo exige CONCILIADO e fallback removido |
| Falha 3: EMICN | Mesma causa de EMERE | Mesma correção, mantendo parcela pendente |
| Falha 4: EMICH | Mesma causa de EMERE | Mesma correção, mantendo parcela pendente |
| Falha 5: contador 0 em vez de 1 | shared_lessons_pending recebia zero incondicionalmente | Contagem por ocorrência com pendência; vínculos não conciliados contados separadamente |
| Falha 6: horário pendente rateado | O laço compartilhado ignorava status_temporal | Exige CONFIRMADO e duração real de 40, 45 ou 50 minutos |
| Erro: código desconhecido | O filtro procurava None em um conjunto contendo a tupla (None, None), permitindo None * 100 | Validação explícita da tarifa e registro de ocorrência pendente sem alocação |

## Arquivos efetivamente alterados

- services.py: somente auxiliares do rateio e build_teaching_weekly_cost_with_shared_rateio_audit.
- tests/test_server.py: duas expectativas monetárias do teste original corrigidas após explicação ao usuário. O teste exigia indevidamente alocação operacional dos códigos EM pendentes. Agora espera R$ 16,20 nas turmas e R$ 38,50 pendentes, mantendo R$ 54,70 no total.
- tests/test_rateio_integrity.py: preservados os oito métodos anteriores, reforçadas as asserções de minutos e contadores, adicionados três métodos para EINFA, conservação global com pendências e códigos malformados/ausentes/tarifas incompatíveis.
- Criado este relatório. Log da execução final: tmp/rateio-correcao-python-tests.txt. O relatório e o log da auditoria anterior foram preservados.

Não existe .git nesta cópia, conforme a auditoria inicial; não há diff histórico disponível.

## Correções complementares dentro do escopo

As tarifas vêm da constante reajustada de 2027 já existente, sem repetir valores literais no auxiliar e sem alterar o orçamento. Códigos EFUND e EM malformados não recebem tarifa por mero prefixo. EINFA pode conservar a referência do segmento em parcela pendente, mas nunca recebe turma operacional sem gramática comprovada.

As pendências provisórias da auditoria base são reconciliadas, preservando as ocorrências não compartilhadas. Resumos por turma, professor e cobertura refletem as pendências atuais. Minutos e custos conhecidos são separados entre turmas conciliadas e parcelas pendentes. Ocorrências sem condições de rateio ficam em unallocated_occurrences, com motivo e índice de origem; não são descartadas nem recebem valor estimado.

Código repetido na mesma ocorrência é contado uma vez. Códigos distintos que apontem à mesma turma tornam a ocorrência pendente, evitando um denominador ambíguo. Ocorrência sem professor identificado também permanece sem alocação.

## Testes finais

- Python original: 58/58 aprovados na execução integral, incluindo a expectativa corrigida de EM.
- Integridade: 11/11 métodos aprovados; os oito anteriores permanecem presentes.
- Python ampliado: 69/69 aprovados, zero falhas, zero erros.
- JavaScript: regression.cjs 11/11 e domain.cjs 14/14; total 25/25, zero falhas.

Execução Python final: 69 testes em 14,610 s, OK. Uma execução intermediária apresentou WinError 10053 no teste HTTP de autenticação (conexão local interrompida pelo Windows); a repetição integral passou sem alteração desse teste. O log intermediário foi preservado em tmp/rateio-correcao-python-winerror10053.txt.

Comando Python: `python -m unittest discover -s tests -p 'test_*.py' -v`. JavaScript: `node tests/regression.cjs` e `node tests/domain.cjs`. Os testes usam fixtures e bancos temporários.

## Conservação comprovada nas fixtures

As 12 combinações de durações 40/45/50 com 2/3/4/7 participantes passaram. Minutos por parcela têm tolerância absoluta de 1e-9 minuto; frações somam 1 com tolerância de 1e-12. A implementação verifica esses limites por ocorrência. Os testes monetários somam Decimal em centavos, sem tolerância monetária.

| Exemplo | Minutos por participante | Percentual por participante | Custo integral e parcelas, usando Fundamental II |
|---|---|---|---|
| 40 min / 2 | 20 | 50% | R$ 26,11 = 13,06 + 13,05 |
| 45 min / 3 | 15 | 33,333…% | R$ 26,11 = 8,71 + 8,70 + 8,70 |
| 50 min / 4 | 12,5 | 25% | R$ 26,11 = 6,53 + 6,53 + 6,53 + 6,52 |
| 50 min / 7 | 7,142857… | 14,285714…% | R$ 26,11 = 7 × 3,73 |

As diferenças de até um centavo nas parcelas monetárias decorrem exclusivamente da distribuição determinística do resíduo; a fração e os minutos permanecem igualitários. Nas fixtures de muitos participantes, os códigos sem turma disponível têm sua parcela conservada explicitamente como pendente.

Conferência global totalmente conciliada: 3 ocorrências antes = 3 depois; 135 minutos no professor = 135 minutos nas turmas; custo antes R$ 48,60 = custo depois R$ 48,60. Estado de entrada completo e os 41 identificadores permanecem iguais. Contador de pendências = zero e lista de pendências vazia.

Conferência global mista: 4 ocorrências = 3 rateadas + 1 sem tarifa, explicitamente pendente. Das 3 rateadas, 1 é conciliada e 2 mantêm vínculos pendentes (EM e EINFA). Total de ocorrências com pendência = 3. Os 175 minutos de entrada permanecem no professor: 135 reconciliados nas parcelas (operacionais + pendentes) e 40 preservados na ocorrência desconhecida não alocada. Custo conhecido R$ 70,90 = R$ 16,20 operacional + R$ 54,70 pendente. O custo desconhecido permanece não calculado, sem estimativa e sem certificação de um total monetário que o inclua.

## Pendências e limites

EMERE/EMICN/EMICH incompatíveis com turmas agregadas, EINFA sem gramática e turmas ausentes não recebem custo ou minutos operacionais. Havendo tarifa comprovável e duração confirmada, sua parcela matemática permanece pendente para preservar o fechamento. Código desconhecido, tarifa incompatível, horário não confirmado ou duração inválida mantêm a ocorrência inteira pendente, sem alocação. pending_links conta vínculos sem turma conciliada por ocorrência, inclusive códigos desconhecidos; não é a quantidade de códigos únicos em todo o relatório. shared_lessons_pending conta cada ocorrência pendente uma vez.

Não houve alteração das 41 turmas, capacidades, matrículas, mensalidades, receitas, despesas, totalExpensesMonthly, orçamento, fórmulas de Ponto de Equilíbrio, usuários/permissões ou banco/schema/Supabase. A integridade foi verificada nas estruturas locais usadas pelos testes; não foi realizada leitura ou escrita de produção.

A validação das 244 ocorrências ainda depende do PDF/extração original: contagem real, identificação de professor/disciplina/horário, durações, participantes por ocorrência, normalização segura, distribuição real das pendências e reconciliação com as tarifas do documento orçamentário. Os resultados desta sessão não substituem essa conferência.

Trabalho encerrado neste relatório. Sem mensalização, conferência professor por professor, alteração do Ponto de Equilíbrio, deploy, push, commit ou migration.
