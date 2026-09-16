#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$OutputFile,
    [string]$Database = "crm",
    [string]$DatabaseUser = "crm",
    [string]$ComposeFile,
    [string]$ProjectName
)

$sourceRoot = Split-Path -Parent $PSScriptRoot
$defaultComposeFile = Join-Path $sourceRoot "compose/docker-compose.yml"
$composeArguments = @("compose")
if ([string]::IsNullOrWhiteSpace($ComposeFile) -and [string]::IsNullOrWhiteSpace($env:COMPOSE_FILE)) {
    if (-not (Test-Path -LiteralPath $defaultComposeFile -PathType Leaf)) {
        throw "Compose file not found: $defaultComposeFile"
    }
    $composeArguments += @("-f", $defaultComposeFile)
}
elseif (-not [string]::IsNullOrWhiteSpace($ComposeFile)) {
    $composeArguments += @("-f", $ComposeFile)
}
if (-not [string]::IsNullOrWhiteSpace($ProjectName)) {
    $composeArguments += @("--project-name", $ProjectName)
}

$resolvedParent = [System.IO.Path]::GetFullPath((Split-Path -Parent $OutputFile))
if (-not (Test-Path -LiteralPath $resolvedParent -PathType Container)) {
    New-Item -ItemType Directory -Path $resolvedParent -Force | Out-Null
}
$resolvedOutput = Join-Path $resolvedParent (Split-Path -Leaf $OutputFile)
& docker @composeArguments exec -T postgres pg_dump --clean --if-exists --no-owner --no-privileges --username $DatabaseUser --dbname $Database | Set-Content -LiteralPath $resolvedOutput -Encoding utf8
if ($LASTEXITCODE -ne 0) { throw "PostgreSQL 备份失败" }
Write-Host "PostgreSQL 备份已写入 $resolvedOutput"
