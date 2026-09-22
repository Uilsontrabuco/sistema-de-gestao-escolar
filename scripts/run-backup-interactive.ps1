[CmdletBinding()]
param(
    [string]$DestinationRoot = 'D:\Backups-7e7',
    [string]$PostgresBin = 'D:\Backups-7e7\tools\postgresql-17.11\bin'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

Write-Host 'Use os dados do Session pooler exibidos em Supabase > Connect.'
$env:PGHOST = Read-Host 'PGHOST (somente o host, sem postgresql://)'
$env:PGPORT = Read-Host 'PGPORT (normalmente 5432)'
$env:PGDATABASE = Read-Host 'PGDATABASE (normalmente postgres)'
$env:PGUSER = Read-Host 'PGUSER'
$env:PGSSLMODE = 'require'
$securePassword = Read-Host 'Senha do banco (não será exibida nem salva)' -AsSecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
try {
    $env:PGPASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    & (Join-Path $PSScriptRoot 'backup-supabase.ps1') -DestinationRoot $DestinationRoot -PostgresBin $PostgresBin
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    $securePassword = $null
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:PGHOST -ErrorAction SilentlyContinue
    Remove-Item Env:PGPORT -ErrorAction SilentlyContinue
    Remove-Item Env:PGDATABASE -ErrorAction SilentlyContinue
    Remove-Item Env:PGUSER -ErrorAction SilentlyContinue
    Remove-Item Env:PGSSLMODE -ErrorAction SilentlyContinue
}
