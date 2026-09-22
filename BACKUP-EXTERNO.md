# Backup externo do 7&7

Este procedimento produz um arquivo lógico somente leitura do PostgreSQL. Ele não executa restauração, migração ou alteração no Supabase.

## Segredos

As credenciais nunca devem ser gravadas em arquivo ou passadas como parâmetros da linha de comando. Configure apenas no ambiente do processo atual:

- `PGHOST`
- `PGPORT`
- `PGDATABASE`
- `PGUSER`
- `PGPASSWORD`
- `PGSSLMODE=require`

Feche o terminal depois do backup. O script também remove `PGPASSWORD` do próprio processo ao terminar.

Para evitar copiar uma connection string ou senha para arquivos, execute `scripts/run-backup-interactive.ps1` em um PowerShell local. O script solicita host, porta, banco, usuário e senha; a senha é digitada em campo oculto e permanece apenas na memória do processo.

Quando a senha não estiver disponível, `scripts/backup-from-vercel-preview.ps1` pode receber `SEVEN7_DATABASE_URL` exclusivamente por `vercel env run -e preview`. O adaptador valida a identidade do endpoint, separa os campos em memória, remove todas as variáveis Vercel/Supabase sensíveis antes de iniciar `pg_dump` e limpa as variáveis `PG*` ao terminar. Não use `vercel env pull` para esse procedimento.

## Conteúdo

O arquivo solicita os schemas `seven7_app`, `public`, `auth` e `storage`. O catálogo final deve conter obrigatoriamente `seven7_app` e `public`. Qualquer restrição de acesso aos schemas gerenciados `auth` e `storage` deve ser tratada como pendência explícita, nunca ignorada silenciosamente.

## Validação

O backup somente é aceito quando:

- `pg_dump` termina com código zero;
- `pg_restore --list` lê o arquivo;
- o arquivo não está vazio;
- os schemas essenciais aparecem no catálogo;
- o SHA-256 calculado coincide com o manifesto.

O teste de restauração deve ser feito posteriormente apenas em ambiente isolado e descartável.
