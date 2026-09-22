[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$BackupDirectory,

    [Parameter(Mandatory = $false)]
    [string]$PostgresBin = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$directory = [System.IO.Path]::GetFullPath($BackupDirectory)
$archive = Join-Path $directory 'seven7-postgres.backup'
$manifest = Join-Path $directory 'backup-manifest.json'
if (-not (Test-Path -LiteralPath $archive -PathType Leaf)) { throw 'Arquivo de backup não encontrado.' }
if (-not (Test-Path -LiteralPath $manifest -PathType Leaf)) { throw 'Manifesto não encontrado.' }

$pgRestore = if ($PostgresBin) {
    Join-Path $PostgresBin 'pg_restore.exe'
} else {
    (Get-Command pg_restore -ErrorAction Stop).Source
}
if (-not (Test-Path -LiteralPath $pgRestore -PathType Leaf)) { throw 'pg_restore não encontrado.' }

$recorded = Get-Content -Raw -LiteralPath $manifest | ConvertFrom-Json
$actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash.ToLowerInvariant()
if ($actualHash -ne $recorded.sha256) { throw 'SHA-256 divergente; o backup pode estar corrompido.' }

$catalog = & $pgRestore '--list' $archive
if ($LASTEXITCODE -ne 0) { throw "pg_restore --list encerrou com código $LASTEXITCODE." }
foreach ($schema in @('seven7_app', 'public')) {
    if (($catalog -join "`n") -notmatch [regex]::Escape($schema)) {
        throw "Schema obrigatório ausente no catálogo: $schema."
    }
}

[pscustomobject]@{
    archive = $archive
    bytes = (Get-Item -LiteralPath $archive).Length
    sha256 = $actualHash
    catalog_entries = @($catalog).Count
    valid = $true
    restore_performed = $false
}
