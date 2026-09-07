#requires -Version 5.1

[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "High")]
param(
    [Parameter(Mandatory = $true)]
    [string]$Environment,

    [Parameter(Mandatory = $true)]
    [string]$EnvFile,

    [Parameter(Mandatory = $true)]
    [string]$CandidateBackendImage,

    [Parameter(Mandatory = $true)]
    [string]$CandidateFrontendImage,

    [Parameter(Mandatory = $true)]
    [string]$PreviousBackendImage,

    [Parameter(Mandatory = $true)]
    [string]$PreviousFrontendImage,

    [Parameter(Mandatory = $true)]
    [string]$BaseUrl,

    [Parameter(Mandatory = $true)]
    [string]$EvidenceFile,

    [Parameter(Mandatory = $true)]
    [string]$ConfirmTarget,

    [switch]$ValidateOnly,
    [switch]$Execute
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$DigestPattern = "^.+@sha256:[0-9a-f]{64}$"
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
$PlannedSteps = @(
    "disable_real_capabilities",
    "deploy_previous_image_digests",
    "verify_health"
)

function Assert-StagingTarget {
    if ($Environment -ne "staging" -or $ConfirmTarget -ne "staging") {
        throw "This rollback command is staging-only; Environment and ConfirmTarget must both equal staging."
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

function Resolve-ComposeCommand {
    $standalone = Get-Command "docker-compose" -ErrorAction SilentlyContinue
    if ($null -ne $standalone) {
        return [PSCustomObject]@{ Executable = $standalone.Source; Prefix = @() }
    }

    $docker = Get-Command "docker" -ErrorAction SilentlyContinue
    if ($null -eq $docker) {
        throw "Docker Compose is required for a live staging rollback."
    }
    return [PSCustomObject]@{ Executable = $docker.Source; Prefix = @("compose") }
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

function Set-DisabledCapabilities {
    foreach ($name in $DisabledCapabilityVariables) {
        Set-Item -LiteralPath "Env:$name" -Value "false"
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
        [string[]]$CompletedSteps,
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
        evidence_type = "staging_rollback_drill"
        generated_at_utc = [DateTime]::UtcNow.ToString("o")
        environment = "staging"
        status = $Status
        production_release = $false
        candidate_backend_image = $CandidateBackendImage
        candidate_frontend_image = $CandidateFrontendImage
        previous_backend_image = $PreviousBackendImage
        previous_frontend_image = $PreviousFrontendImage
        planned_steps = $PlannedSteps
        completed_steps = $CompletedSteps
        health_checks = $HealthChecks
    }
    $evidence | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $EvidenceFile -Encoding UTF8
}

Assert-StagingTarget
if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
    throw "The staging environment file does not exist."
}
Assert-ImmutableImage -Name "CandidateBackendImage" -Reference $CandidateBackendImage
Assert-ImmutableImage -Name "CandidateFrontendImage" -Reference $CandidateFrontendImage
Assert-ImmutableImage -Name "PreviousBackendImage" -Reference $PreviousBackendImage
Assert-ImmutableImage -Name "PreviousFrontendImage" -Reference $PreviousFrontendImage
if ($CandidateBackendImage -eq $PreviousBackendImage -or $CandidateFrontendImage -eq $PreviousFrontendImage) {
    throw "Rollback images must differ from the candidate image digests."
}

$baseUri = $null
if (-not [Uri]::TryCreate($BaseUrl, [UriKind]::Absolute, [ref]$baseUri) -or $baseUri.Scheme -ne "https") {
    throw "BaseUrl must be an absolute HTTPS URL."
}

if ($ValidateOnly) {
    Write-Evidence -Status "validated" -CompletedSteps @() -HealthChecks @()
    Write-Output "Staging rollback plan validated; production_release=false."
    exit 0
}
if (-not $Execute) {
    throw "A live rollback requires -Execute; use -ValidateOnly for a non-mutating plan check."
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

$completedSteps = @()
try {
    Set-DisabledCapabilities
    $env:BACKEND_IMAGE = $CandidateBackendImage
    $env:FRONTEND_IMAGE = $CandidateFrontendImage
    if ($PSCmdlet.ShouldProcess("staging", "disable all real capabilities before image rollback")) {
        Invoke-Compose -Command $compose -Arguments ($composeArguments + @(
            "up", "-d", "--no-build", "backend", "worker", "jobs", "agent-worker"
        ))
    }
    $completedSteps += "disable_real_capabilities"

    $env:BACKEND_IMAGE = $PreviousBackendImage
    $env:FRONTEND_IMAGE = $PreviousFrontendImage
    if ($PSCmdlet.ShouldProcess("staging", "deploy previous immutable application image digests")) {
        Invoke-Compose -Command $compose -Arguments ($composeArguments + @(
            "pull", "backend", "worker", "jobs", "agent-worker", "frontend"
        ))
        Invoke-Compose -Command $compose -Arguments ($composeArguments + @(
            "up", "-d", "--no-build", "backend", "worker", "jobs", "agent-worker", "frontend", "proxy"
        ))
    }
    $completedSteps += "deploy_previous_image_digests"
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
$completedSteps += "verify_health"
Write-Evidence -Status "passed" -CompletedSteps $completedSteps -HealthChecks $healthChecks
Write-Output "Staging rollback drill passed; production_release=false."
