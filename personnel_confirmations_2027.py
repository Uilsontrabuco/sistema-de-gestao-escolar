"""Confirmações do gestor, separadas da folha histórica e do custo orçado."""
from copy import deepcopy

SOURCE = 'Confirmação direta do usuário em 21/09/2026; RETOMADA-2027-PESSOAL.md'
CONFIRMATIONS = (
    ('952', 'Jailane Ramise Limoeiro da Cruz', 'SUBSTITUICAO', '679', None),
    ('953', 'Veroneide Martins Silva', 'ADICIONAL', None, None),
    ('955', 'Paula Araujo Dias', 'ADICIONAL', None, 'G3 B'),
)


def personnel_evidence():
    return deepcopy(dict(
        source=SOURCE,
        rows=[dict(employeeId=code, name=name, role='Auxiliar de Serviços Gerais',
                   monthlySalaryCents=169050, salaryStatus='CONFIRMADO_PELO_USUARIO',
                   weeklyHours=44, hoursStatus='PREMISSA_ADMINISTRATIVA_APROVADA',
                   hoursSource='Aprovação administrativa comunicada pelo usuário em 22/09/2026',
                   positionKind=kind, replacesEmployeeId=replaces, className=room,
                   totalEmployerCostCents=None, budgetCoverageCents=None,
                   appliedAdditionalCostCents=0,
                   pending='Demais verbas, encargos individuais e cobertura nominal no orçamento; jornada de 44h aprovada')
              for code, name, kind, replaces, room in CONFIRMATIONS],
        salarySumCents=507150,
        treatment='Composição nominal informada; não é acréscimo ao orçamento. '
                  'Jailane substitui Romilton, um único posto. '
                  'Custo total e cobertura pendentes não foram presumidos zero.',
    ))


def personnel_note():
    return ('Confirmação do gestor em 21/09/2026: Paula, Jailane e Veroneide são '
            'Auxiliares de Serviços Gerais, com salário mensal de R$ 1.690,50 cada. '
            'Paula não deve ser classificada como estagiária. Jailane substitui Romilton, '
            'sem duplicar o posto. Jornada de 44 horas semanais aprovada administrativamente '
            'em 22/09/2026 para as três. Permanecem pendentes demais verbas, encargos individuais '
            'e cobertura nominal no orçamento. Os salários não foram adicionados '
            'automaticamente ao custo já alocado.')
