# Auditoria do rateio docente — 13/09/2026

Resultado: validação reprovada. Implementação preservada; somente testes adicionais e este relatório foram criados. Não houve mensalização, alteração financeira, alteração de banco/schema, Supabase, produção, commit, push ou deploy.

## A. Arquivos e estado inicial

Analisados: services.py (extração, normalização, referência semanal e rateio), tests/test_server.py, tests/test_http.py, tests/regression.cjs, tests/domain.cjs, server.py (estrutura e banco), README.md, references/LEIA-ME.md e inventário dos arquivos locais.

Criados: tests/test_rateio_integrity.py e RELATORIO-RATEIO-2027.md. Saída integral da suíte ampliada: tmp/rateio-python-tests.txt. services.py e tests/test_server.py foram preservados.

git status e git diff não puderam ser executados com sucesso: a pasta fornecida não contém .git. Não é possível estabelecer o diff histórico nem confirmar quais alterações antecederam esta sessão.

## B–E. Ocorrências reais e pendências

244 é a quantidade informada na solicitação, não uma contagem reproduzida nesta sessão. Não estão presentes na pasta o PDF de carga horária, sua extração completa ou o banco operacional. Portanto: ocorrências reais encontradas e quantidade operacionalmente pendente são indeterminadas; nenhuma das 244 foi validada documentalmente nesta sessão; todas as 244 informadas permanecem por conferir. Não foram substituídas por dados sintéticos.

Categorias que exigem conferência: códigos EINFA sem gramática comprovada; EMERE/EMICN/EMICH com seção incompatível com turma agregada; códigos desconhecidos; vínculo operacional ausente; horário/duração não confirmados; participantes com tarifa ausente ou segmentos diferentes. As quantidades por categoria dependem do documento real.

## F–I. Fechamento e conservação

Fixtures para 2, 3, 4 e 7 códigos participantes, cada uma com 40, 45 e 50 minutos: 12 combinações aprovadas. Fração por participante igual a 1/n; soma igual a 100% com tolerância de 1e-12 para ponto flutuante. Percentuais: 50%, 33,333…%, 25% e 14,285714…%, respectivamente. Não se arredondaram os percentuais para somá-los.

Custos conferidos com Decimal: cada ocorrência de Fundamental II conserva exatamente R$ 26,11 em centavos. O resíduo é distribuído deterministicamente entre os primeiros códigos ordenados; a diferença entre parcelas é no máximo R$ 0,01. Isso representa arredondamento do quinhão igualitário, não igualdade exata entre valores monetários já arredondados. Nenhum participante dessas fixtures recebeu o custo integral.

Fixture global de três ocorrências: 3 antes = 3 depois; 135 minutos preservados no professor; R$ 48,60 antes = R$ 48,60 nas turmas e no resumo. Código repetido na mesma ocorrência gera uma única parcela e um único custo.

Conservação de minutos NAS TURMAS reprovada: uma ocorrência de 45 minutos para duas turmas deixa a soma de weekly_minutes das turmas em zero. As parcelas não expõem minutos atribuídos. Logo, a conservação global solicitada ainda não pode ser certificada.

A inexistência de duplicação foi demonstrada apenas nas fixtures válidas acima. Não é possível certificar ausência de duplicações no PDF completo, nem provar que nenhuma das 244 ocorrências desaparece. Código desconhecido provoca exceção e impede a conclusão da auditoria.

## J. Integridade das 41 turmas

A estrutura local inicial contém 41 turmas. O teste compara o estado inteiro antes/depois, a prévia inteira e os 41 identificadores retornados: todos preservados. Capacidade, alunos, matrículas e demais campos não foram modificados. Isso comprova integridade das fixtures locais, não uma leitura do estado atual de produção.

## K–L. Testes

- Suíte Python original: 58 testes, todos aprovados, 15,497 s.
- Suíte Python ampliada: 66 testes, 14,547 s; FAILED (failures=6, errors=1). Os 58 originais continuam aprovados. Dos 8 métodos novos, 3 passam e 5 apresentam problemas; um desses métodos falha em 3 subtestes, explicando as 6 falhas de asserção.
- JavaScript: regression.cjs, 11/11; domain.cjs, 14/14; total 25/25. A primeira tentativa foi bloqueada por EPERM do sandbox; a execução autorizada fora dele passou.
- Nenhum teste foi marcado como expectedFailure ou ignorado para ocultar inconsistências.

## M. Inconsistências e riscos

1. _shared_rateio_target aceita operational_class_id mesmo quando a normalização informa PENDENTE e ainda aplica fallback para turmas agregadas de EM. As três famílias EMERE/EMICN/EMICH receberam R$ 38,50 operacionalmente em cada fixture, quando deveriam manter as parcelas pendentes.
2. O rateio incrementa custo das turmas, mas não seus minutos/aulas proporcionais; também mantém agrupamentos e indicadores da auditoria anterior sem reconciliação completa.
3. summary.shared_lessons_pending é forçado a zero mesmo com participante sem turma. As listas e motivos anteriores de pendência permanecem, tornando resumo e detalhe inconsistentes.
4. O laço de rateio não exige status_temporal CONFIRMADO: uma ocorrência temporalmente pendente recebe rateio.
5. _shared_rate devolve (None, None) para desconhecidos, mas o filtro testa None no conjunto de tuplas. O processamento chega a None * 100 e lança TypeError.
6. As tarifas reajustadas estão declaradas em TEACHING_HOUR_AULA_REAJUSTED_2027, mas _shared_rate repete números literais. Nenhum valor foi criado nesta sessão; a identidade documental com o Orçamento 2027 não pôde ser revalidada sem o original. Não foi aplicada conversão de duração ou mensalização.
7. O denominador usa códigos únicos; códigos diferentes que apontem para uma mesma turma podem representar mais de uma parcela operacional. O conjunto real precisa ser examinado antes de afirmar que código único equivale sempre a turma participante única.

## N. Próximo passo recomendado

Disponibilizar o PDF/extração efetivamente usado e o estado local correspondente às 41 turmas para reproduzir as 244 ocorrências. Na conferência crítica professor por professor, começar pelos cinco defeitos reproduzidos nos testes e pelos vínculos de EM; corrigir essas inconsistências em etapa autorizada e repetir as verificações por ocorrência e globais antes de aprovar qualquer mensalização. Esta sessão encerra na auditoria, conforme solicitado.
