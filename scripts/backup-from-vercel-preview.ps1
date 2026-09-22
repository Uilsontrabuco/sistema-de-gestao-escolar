[CmdletBinding()]
param(
    [string]$DestinationRoot = 'D:\Backups-7e7',
    [string]$PostgresBin = 'D:\Backups-7e7\tools\postgresql-17.11\bin'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$databaseUrl = [Environment]::GetEnvironmentVariable('SEVEN7_DATABASE_URL', 'Process')
if (-not $databaseUrl) {
    throw 'SEVEN7_DATABASE_URL não foi injetada no subprocesso. Nenhum backup foi iniciado.'
}

try {
    try {
        $uri = [Uri]$databaseUrl
        if ($uri.Scheme -notin @('postgres', 'postgresql') -or -not $uri.Host) {
            throw 'invalid'
        }
        $separator = $uri.UserInfo.IndexOf(':')
        if ($separator -lt 1) { throw 'invalid' }
        $pgUser = [Uri]::UnescapeDataString($uri.UserInfo.Substring(0, $separator))
        $pgPassword = [Uri]::UnescapeDataString($uri.UserInfo.Substring($separator + 1))
        $pgDatabase = [Uri]::UnescapeDataString($uri.AbsolutePath.TrimStart('/'))
        if (-not $pgPassword -or -not $pgDatabase) { throw 'invalid' }
        $pgHost = $uri.Host
        $pgPort = if ($uri.IsDefaultPort) { '5432' } else { [string]$uri.Port }
    }
    catch {
        throw 'A connection string injetada é inválida. O valor não foi exibido nem persistido.'
    }

    if ($pgHost -ne 'db.pvsdlqspxfbfeepylfxc.supabase.co' -and $pgHost -notmatch '^aws-[0-9]+-sa-east-1\.pooler\.supabase\.com$') {
        throw 'O host injetado não pertence ao endpoint Supabase aprovado para o 7&7.'
    }
    if ($pgUser -ne 'postgres' -and $pgUser -ne 'postgres.pvsdlqspxfbfeepylfxc') {
        throw 'O usuário injetado não pertence ao projeto Supabase aprovado para o 7&7.'
    }

    # Elimina do processo todos os segredos trazidos pela Vercel antes de
    # iniciar qualquer ferramenta externa. Somente PG* mínimos são recriados.
    $sensitiveNames = @(
        'SEVEN7_DATABASE_URL', 'SEVEN7_SUPABASE_SECRET_KEY', 'SEVEN7_SUPABASE_URL',
        'POSTGRES_URL', 'POSTGRES_URL_NON_POOLING', 'POSTGRES_PRISMA_URL',
        'POSTGRES_PASSWORD', 'POSTGRES_USER', 'POSTGRES_HOST', 'POSTGRES_DATABASE',
        'DATABASE_URL', 'SUPABASE_SECRET_KEY', 'SUPABASE_SERVICE_ROLE_KEY',
        'SUPABASE_ANON_KEY', 'SUPABASE_PUBLISHABLE_KEY', 'SUPABASE_JWT_SECRET',
        'SUPABASE_URL', 'NEXT_PUBLIC_SUPABASE_URL', 'NEXT_PUBLIC_SUPABASE_ANON_KEY',
        'NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY', 'VERCEL_OIDC_TOKEN'
    )
    foreach ($name in $sensitiveNames) {
        [Environment]::SetEnvironmentVariable($name, $null, 'Process')
    }
    $databaseUrl = $null
    $uri = $null

    [Environment]::SetEnvironmentVariable('PGHOST', $pgHost, 'Process')
    [Environment]::SetEnvironmentVariable('PGPORT', $pgPort, 'Process')
    [Environment]::SetEnvironmentVariable('PGDATABASE', $pgDatabase, 'Process')
    [Environment]::SetEnvironmentVariable('PGUSER', $pgUser, 'Process')
    [Environment]::SetEnvironmentVariable('PGPASSWORD', $pgPassword, 'Process')
    [Environment]::SetEnvironmentVariable('PGSSLMODE', 'require', 'Process')
    $pgPassword = $null

    & (Join-Path $PSScriptRoot 'backup-supabase.ps1') -DestinationRoot $DestinationRoot -PostgresBin $PostgresBin
}
finally {
    foreach ($name in @('PGHOST','PGPORT','PGDATABASE','PGUSER','PGPASSWORD','PGSSLMODE','PGOPTIONS')) {
        [Environment]::SetEnvironmentVariable($name, $null, 'Process')
    }
    $databaseUrl = $null
    $pgPassword = $null
}
