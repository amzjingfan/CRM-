#requires -Version 5.1
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$sourceRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $sourceRoot "config/.env"
$envTemplate = Join-Path $sourceRoot "config/.env.example"
$composeFile = Join-Path $sourceRoot "compose/docker-compose.yml"

foreach ($path in @($envTemplate, $composeFile)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required local startup asset is missing: $path"
    }
}
if (-not (Test-Path -LiteralPath $envFile -PathType Leaf)) {
    throw "Create src/config/.env from src/config/.env.example before starting the project."
}

$docker = Get-Command docker -ErrorAction SilentlyContinue
if ($null -ne $docker) {
    & $docker.Source compose version *> $null
}
if ($null -ne $docker -and $LASTEXITCODE -eq 0) {
    $executable = $docker.Source
    $prefix = @("compose")
}
else {
    $standalone = Get-Command docker-compose -ErrorAction SilentlyContinue
    if ($null -eq $standalone) {
        throw "Docker Compose is required."
    }
    & $standalone.Source version *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose is unavailable."
    }
    $executable = $standalone.Source
    $prefix = @()
}

& $executable @($prefix + @(
    "--project-name", "crm",
    "--env-file", $envFile,
    "-f", $composeFile,
    "up", "-d", "--build"
))
if ($LASTEXITCODE -ne 0) {
    throw "Local project startup failed with exit code $LASTEXITCODE."
}
