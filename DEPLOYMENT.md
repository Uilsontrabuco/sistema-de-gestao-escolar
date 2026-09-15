# 7&7 — versão recuperada

O aplicativo completo usa o frontend existente e o domínio Python existente. Na Vercel, `api/index.py` utiliza `CloudStore`: os dados ficam no Postgres do Supabase, não no disco temporário da função.

## Configuração do servidor

Usa `POSTGRES_URL` (ou `DATABASE_URL`) e `SUPABASE_SECRET_KEY` já configuradas no projeto Vercel. `SUPABASE_URL` ou `NEXT_PUBLIC_SUPABASE_URL`, quando presente, deve identificar o projeto recuperado. Não colocar valores de credenciais no repositório.

O backend verifica a identidade do banco pelo marcador da recuperação. Ausência de configuração, schema ou estado causa indisponibilidade explícita; não há criação automática de banco vazio. Autenticação usa Supabase Auth, sessões de aplicação revogáveis, cookies HttpOnly/Secure/SameSite e proteção CSRF. Perfis e permissões são consultados no backend.

## Dados preservados

A recuperação reconciliou 41 turmas e 625 matrículas agregadas por auditoria e relato humano contemporâneo. Não foram criados alunos individuais para representar contagens agregadas. O snapshot docente aprovado mantém 40/45/50 minutos e o fechamento semanal validado.

Solicitações e entregas do formato anterior ficam disponíveis como registros recuperados. A fonte antiga não contém todos os vínculos necessários ao fluxo novo; nenhum destinatário, aprovação ou desconto foi inventado. Valores de orçamento recuperados do navegador permanecem identificados como não certificados. Evidência ausente não equivale a zero e não autoriza PE definitivo.

## Verificação e publicação

Validar primeiro um Preview usando as variáveis existentes. `/api/health` verifica acesso ao banco correto e ao serviço de autenticação sem retornar credenciais. O campo `commit` permite conferir a versão publicada. Validar login, autorizações, consulta e recarregamento antes de promover para main.

Os testes originais de documentos exigem fixtures privadas locais. Essas fixtures, backups, recovery, dumps e dados do navegador não pertencem ao Git ou ao bundle Vercel. Os testes unitários adicionais do runtime ficam em `tests/test_cloud_runtime.py`.

As migrations aplicadas nesta recuperação estão registradas no Supabase. Não reaplicar o esquema inicial como recuperação e não apagar schemas privados. A área de transporte e as fontes da recuperação foram preservadas. Rollback de código não deve apagar nem substituir dados.

Este arquivo não declara homologação nem liberação de produção.
