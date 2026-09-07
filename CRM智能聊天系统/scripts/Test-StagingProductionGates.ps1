#requires -Version 5.1

[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "High")]
param(
    [Parameter(Mandatory = $true)]
    [string]$Environment,

    [Parameter(Mandatory = $true)]
    [string]$EnvFile,

    [Parameter(Mandatory = $true)]
    [string]$BackendImage,

    [Parameter(Mandatory = $true)]
    [string]$FrontendImage,

    [Parameter(Mandatory = $true)]
    [string]$BaseUrl,

    [Parameter(Mandatory = $true)]
    [string]$EvidenceFile,

    [Parameter(Mandatory = $true)]
    [string]$ConfirmTarget,

    [switch]$ValidateOnly,
    [switch]$Deploy
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$DigestPattern = "^.+@sha256:[0-9a-f]{64}$"
$RequiredVariables = @(
    "DATABASE_URL",
    "REDIS_URL",
    "MINIO_ENDPOINT",
    "MINIO_ACCESS_KEY",
    "MINIO_SECRET_KEY",
    "JWT_SECRET_KEY",
    "CORS_ORIGINS",
    "PUBLIC_BASE_URL",
    "PUBLIC_API_BASE_URL",
    "TIKTOK_EGRESS_IP",
    "TIKTOK_OAUTH_REDIRECT_URI",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "TLS_CERT_DIR",
    "POSTGRES_IMAGE",
    "REDIS_IMAGE",
    "MINIO_IMAGE",
    "NGINX_IMAGE"
)
$DisabledCapabilityVariables = @(
    "ALLOW_MOCK_PLATFORM_ADAPTERS",
    "REAL_TIKTOK_READ_ENABLED",
    "REAL_TIKTOK_WEBHOOK_ENABLED",
    "REAL_TIKTOK_MESSAGE_WRITE_ENABLED",
    "REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED",
    "LLM_ENABLED",
    "LLM_LIVE_EVAL",
    "AI_TRANSLATION_ENABLED",
    "AI_MARKETING_ENABLED",
    "AUTO_REPLY_ENABLED"
)

function Assert-StagingTarget {
    if ($Environment -ne "staging" -or $ConfirmTarget -ne "staging") {
        throw "This command is staging-only; Environment and ConfirmTarget must both equal staging."
    }
}

function Assert-ImmutableImage {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string]$Reference
    )

    if ($Reference -notmatch $DigestPattern) {
        throw "$Name must use an immutable repository@sha256 digest."
    }
}

function Read-EnvironmentFile {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "The staging environment file does not exist."
    }

    $values = @{}
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }
        $separator = $trimmed.IndexOf("=")
        if ($separator -le 0) {
            throw "The staging environment file contains an invalid assignment."
        }
        $key = $trimmed.Substring(0, $separator).Trim()
        $value = $trimmed.Substring($separator + 1)
        $values[$key] = $value
    }
    return $values
}

function Assert-EnvironmentContract {
    param([Parameter(Mandatory = $true)][hashtable]$Values)

    foreach ($name in $RequiredVariables) {
        if (-not $Values.ContainsKey($name) -or [string]::IsNullOrWhiteSpace($Values[$name])) {
            throw "Required staging variable is missing: $name"
        }
    }
    foreach ($name in $DisabledCapabilityVariables) {
        if (-not $Values.ContainsKey($name) -or $Values[$name].Trim().ToLowerInvariant() -ne "false") {
            throw "Staging preflight requires $name=false."
        }
    }
}

function Resolve-ComposeCommand {
    $standalone = Get-Command "docker-compose" -ErrorAction SilentlyContinue
    if ($null -ne $standalone) {
        return [PSCustomObject]@{ Executable = $standalone.Source; Prefix = @() }
    }

    $docker = Get-Command "docker" -ErrorAction SilentlyContinue
    if ($null -eq $docker) {
        throw "Docker Compose is required for a live staging run."
    }
    return [PSCustomObject]@{ Executable = $docker.Source; Prefix = @("compose") }
}

function Set-DisabledCapabilities {
    foreach ($name in $DisabledCapabilityVariables) {
        Set-Item -LiteralPath "Env:$name" -Value "false"
    }
}

function Invoke-Compose {
    param(
        [Parameter(Mandatory = $true)]$Command,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    & $Command.Executable @($Command.Prefix + $Arguments)
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose command failed with exit code $LASTEXITCODE."
    }
}

function Test-HealthEndpoint {
    param([Parameter(Mandatory = $true)][string]$Uri)

    $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 20
    if ($response.StatusCode -lt 200 -or $response.StatusCode -ge 300) {
        throw "Health endpoint returned a non-success status."
    }
    return [int]$response.StatusCode
}

function Write-Evidence {
    param(
        [Parameter(Mandatory = $true)][string]$Status,
        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [object[]]$HealthChecks
    )

    $parent = Split-Path -Parent $EvidenceFile
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $evidence = [ordered]@{
        schema_version = 1
        evidence_type = "staging_production_gate_preflight"
        generated_at_utc = [DateTime]::UtcNow.ToString("o")
        environment = "staging"
        status = $Status
        production_release = $false
        backend_image = $BackendImage
        frontend_image = $FrontendImage
        validated_variable_names = @($RequiredVariables + $DisabledCapabilityVariables | Sort-Object -Unique)
        health_checks = $HealthChecks
    }
    $evidence | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $EvidenceFile -Encoding UTF8
}

Assert-StagingTarget
Assert-ImmutableImage -Name "BackendImage" -Reference $BackendImage
Assert-ImmutableImage -Name "FrontendImage" -Reference $FrontendImage

$baseUri = $null
if (-not [Uri]::TryCreate($BaseUrl, [UriKind]::Absolute, [ref]$baseUri) -or $baseUri.Scheme -ne "https") {
    throw "BaseUrl must be an absolute HTTPS URL."
}

$environmentValues = Read-EnvironmentFile -Path $EnvFile
Assert-EnvironmentContract -Values $environmentValues
foreach ($name in @("POSTGRES_IMAGE", "REDIS_IMAGE", "MINIO_IMAGE", "NGINX_IMAGE")) {
    Assert-ImmutableImage -Name $name -Reference $environmentValues[$name]
}

if ($ValidateOnly) {
    Write-Evidence -Status "validated" -HealthChecks @()
    Write-Output "Staging production gate inputs validated; production_release=false."
    exit 0
}

if (-not $Deploy) {
    throw "A live run requires -Deploy; use -ValidateOnly for a non-mutating preflight."
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$compose = Resolve-ComposeCommand
$composeArguments = @(
    "--env-file", (Resolve-Path -LiteralPath $EnvFile).Path,
    "-f", (Join-Path $projectRoot "docker-compose.yml"),
    "-f", (Join-Path $projectRoot "docker-compose.prod.yml")
)

$savedEnvironment = @{}
foreach ($name in @($DisabledCapabilityVariables + @("BACKEND_IMAGE", "FRONTEND_IMAGE"))) {
    $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
}
try {
    Set-DisabledCapabilities
    $env:BACKEND_IMAGE = $BackendImage
    $env:FRONTEND_IMAGE = $FrontendImage

    Invoke-Compose -Command $compose -Arguments ($composeArguments + @("config", "--services"))
    if ($PSCmdlet.ShouldProcess("staging", "deploy immutable application image digests")) {
        Invoke-Compose -Command $compose -Arguments ($composeArguments + @(
            "pull", "backend", "worker", "jobs", "agent-worker", "frontend"
        ))
        Invoke-Compose -Command $compose -Arguments ($composeArguments + @(
            "up", "-d", "--no-build", "backend", "worker", "jobs", "agent-worker", "frontend", "proxy"
        ))
    }
}
finally {
    foreach ($name in $savedEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], "Process")
    }
}

$healthChecks = @(
    [ordered]@{ path = "/healthz"; status_code = Test-HealthEndpoint -Uri ($BaseUrl.TrimEnd("/") + "/healthz") },
    [ordered]@{ path = "/v1/health"; status_code = Test-HealthEndpoint -Uri ($BaseUrl.TrimEnd("/") + "/v1/health") },
    [ordered]@{ path = "/v1/health/ready"; status_code = Test-HealthEndpoint -Uri ($BaseUrl.TrimEnd("/") + "/v1/health/ready") }
)
Write-Evidence -Status "passed" -HealthChecks $healthChecks
Write-Output "Staging production gate deployment and health verification passed; production_release=false."
