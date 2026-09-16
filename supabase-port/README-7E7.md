# 7&7 — Guia de publicação e Supabase

## Banco de dados
1. Abra o projeto no Supabase.
2. Vá em **SQL Editor**.
3. Execute `supabase_schema.sql`.
4. Em Authentication, crie os usuários do sistema. O frontend deve usar o Supabase Auth em produção.

## Segurança
- Use somente a chave `anon/public` no navegador.
- Nunca exponha `service_role`.
- As políticas RLS do schema limitam os dados ao perfil do usuário.

## Vercel
Publique a pasta do projeto como site estático. Para uma versão de produção, configure as variáveis `NEXT_PUBLIC_SUPABASE_URL` e `NEXT_PUBLIC_SUPABASE_ANON_KEY` (ou os equivalentes usados pelo framework) e substitua a autenticação de demonstração por Supabase Auth.
