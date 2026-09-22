[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$DestinationRoot = 'D:\Backups-7e7',

    [Parameter(Mandatory = $false)]
    [string]$PostgresBin = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Resolve-Tool([string]$Name) {
    if ($PostgresBin) {
        $candidate = Join-Path $PostgresBin ($Name + '.exe')
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    }
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    throw "Ferramenta PostgreSQL ausente: $Name."
}

function Require-SecretEnvironment {
    $required = @('PGHOST', 'PGPORT', 'PGDATABASE', 'PGUSER', 'PGPASSWORD')
    $missing = @($required | Where-Object { -not [Environment]::GetEnvironmentVariable($_, 'Process') })
    if ($missing.Count -gt 0) {
        throw ('Credenciais não configuradas no ambiente do processo: ' + ($missing -join ', ') + '. Nenhum backup foi iniciado.')
    }
    if ([Environment]::GetEnvironmentVariable('PGSSLMODE', 'Process') -ne 'require') {
        throw 'PGSSLMODE deve estar definido como require no ambiente do processo.'
    }
}

try {
    Require-SecretEnvironment
    $pgDump = Resolve-Tool 'pg_dump'
    $pgRestore = Resolve-Tool 'pg_restore'

    $resolvedRoot = [System.IO.Path]::GetFullPath($DestinationRoot)
    if ($resolvedRoot.StartsWith([System.IO.Path]::GetFullPath((Get-Location).Path), [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'O destino deve ficar fora do repositório.'
    }

    $stamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH-mm-ssZ')
    $destination = Join-Path $resolvedRoot $stamp
    New-Item -ItemType Directory -Path $destination -Force | Out-Null

    $archive = Join-Path $destination 'seven7-postgres.backup'
    $catalog = Join-Path $destination 'seven7-postgres.catalog.txt'
    $manifest = Join-Path $destination 'backup-manifest.json'

    $schemas = @('seven7_app', 'public', 'auth', 'storage')
    $arguments = @(
        '--format=custom',
        '--compress=9',
        '--no-owner',
        '--file', $archive
    )
    foreach ($schema in $schemas) { $arguments += @('--schema', $schema) }

    & $pgDump @arguments
    if ($LASTEXITCODE -ne 0) { throw "pg_dump encerrou com código $LASTEXITCODE." }

    & $pgRestore '--list' $archive | Set-Content -LiteralPath $catalog -Encoding utf8NoBOM
    if ($LASTEXITCODE -ne 0) { throw "pg_restore --list encerrou com código $LASTEXITCODE." }

    $archiveInfo = Get-Item -LiteralPath $archive
    if ($archiveInfo.Length -le 0) { throw 'O arquivo de backup está vazio.' }
    $catalogText = Get-Content -Raw -LiteralPath $catalog
    foreach ($schema in @('seven7_app', 'public')) {
        if ($catalogText -notmatch [regex]::Escape($schema)) {
            throw "O catálogo não contém o schema obrigatório $schema."
        }
    }

    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash.ToLowerInvariant()
    $details = [ordered]@{
        format = 'PostgreSQL custom archive'
        created_at_utc = (Get-Date).ToUniversalTime().ToString('o')
        archive = $archiveInfo.Name
        bytes = $archiveInfo.Length
        sha256 = $hash
        schemas_requested = $schemas
        validation = [ordered]@{
            pg_dump_exit_code = 0
            pg_restore_catalog_exit_code = 0
            archive_nonempty = $true
            required_schemas_in_catalog = @('seven7_app', 'public')
        }
        secrets_embedded_by_script = $false
        restore_performed = $false
    }
    $details | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifest -Encoding utf8NoBOM
    "$hash  $($archiveInfo.Name)" | Set-Content -LiteralPath ($archive + '.sha256') -Encoding ascii

    Write-Output ([pscustomobject]@{
        destination = $destination
        archive_bytes = $archiveInfo.Length
        sha256 = $hash
        validated = $true
    })
}
catch {
    if ((Get-Variable archive -ErrorAction SilentlyContinue) -and (Test-Path -LiteralPath $archive)) {
        Move-Item -LiteralPath $archive -Destination ($archive + '.incomplete') -Force
    }
    throw
}
finally {
    [Environment]::SetEnvironmentVariable('PGPASSWORD', $null, 'Process')
}
