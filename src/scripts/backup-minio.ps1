#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory,
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

$resolvedOutput = [System.IO.Path]::GetFullPath($OutputDirectory)
if (-not (Test-Path -LiteralPath $resolvedOutput -PathType Container)) {
    New-Item -ItemType Directory -Path $resolvedOutput -Force | Out-Null
}
& docker @composeArguments cp minio:/data/. $resolvedOutput
if ($LASTEXITCODE -ne 0) { throw "MinIO 备份失败" }
Write-Host "MinIO 备份已写入 $resolvedOutput"
