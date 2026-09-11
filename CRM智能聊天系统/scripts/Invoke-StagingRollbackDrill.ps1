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
    [string]$CandidateRetrievalModelImage,

    [Parameter(Mandatory = $true)]
    [string]$PreviousBackendImage,

    [Parameter(Mandatory = $true)]
    [string]$PreviousFrontendImage,

    [Parameter(Mandatory = $true)]
    [string]$PreviousRetrievalModelImage,

    [Parameter(Mandatory = $true)]
    [string]$BaseUrl,

    [Parameter(Mandatory = $true)]
    [string]$EvidenceFile,

    [Parameter(Mandatory = $true)]
    [string]$ConfirmTarget,

    [Parameter(Mandatory = $true)]
    [AllowEmptyString()]
    [string]$DockerHost,

    [switch]$ValidateOnly,
    [switch]$Execute
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RequiredEnvironmentVariables = @(
    "RETRIEVAL_MODEL_ASSET_DIR",
    "RETRIEVAL_MODEL_SERVICE_IMAGE",
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

function Assert-RootlessDockerHost {
    param([Parameter(Mandatory = $true)][AllowEmptyString()][string]$Value)

    # Staging 只能通过 crmdeploy 用户的 Rootless daemon，不能回退到系统或 TCP Docker。
    if ($Value -cne "unix:///run/user/1004/docker.sock") {
        throw "DockerHost must identify the crmdeploy rootless Docker host."
    }
}

function Assert-ImmutableImage {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string]$Reference,
        [Parameter(Mandatory = $true)]
        [string]$Repository,
        [switch]$AllowTag
    )

    $tagPattern = if ($AllowTag) { "(?::[A-Za-z0-9_][A-Za-z0-9_.-]{0,127})?" } else { "" }
    $pattern = "^$([Regex]::Escape($Repository))$tagPattern@sha256:[0-9a-f]{64}$"
    if ($Reference -match "[^\x21-\x7e]" -or $Reference -notmatch $pattern) {
        throw "$Name must use the approved repository and an immutable sha256 digest."
    }
    return $Reference
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

    foreach ($name in $RequiredEnvironmentVariables) {
        if (-not $Values.ContainsKey($name) -or [string]::IsNullOrWhiteSpace($Values[$name])) {
            throw "Required staging variable is missing: $name"
        }
    }
    foreach ($name in $DisabledCapabilityVariables) {
        if (-not $Values.ContainsKey($name) -or $Values[$name].Trim().ToLowerInvariant() -ne "false") {
            throw "Staging rollback requires $name=false."
        }
    }
}

function Assert-NoReparsePointInPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    $currentPath = [System.IO.Path]::GetFullPath($Path)
    while ($true) {
        $item = Get-Item -LiteralPath $currentPath -Force
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "External model asset paths must not contain a symbolic link or reparse point."
        }
        $parent = [System.IO.Directory]::GetParent($currentPath)
        if ($null -eq $parent) {
            break
        }
        $currentPath = $parent.FullName
    }
}

function Assert-ExternalModelAssets {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$GitCheckoutRoot
    )

    if (-not [System.IO.Path]::IsPathRooted($Path)) {
        throw "RETRIEVAL_MODEL_ASSET_DIR must be an absolute server path."
    }
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "RETRIEVAL_MODEL_ASSET_DIR does not exist or is not a directory."
    }
    Assert-NoReparsePointInPath -Path $Path

    $resolvedPath = (Resolve-Path -LiteralPath $Path).Path
    $resolvedGitCheckoutRoot = (Resolve-Path -LiteralPath $GitCheckoutRoot).Path
    $checkoutPrefix = $resolvedGitCheckoutRoot.TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    ) + [System.IO.Path]::DirectorySeparatorChar
    if ($resolvedPath.Equals($resolvedGitCheckoutRoot, [StringComparison]::OrdinalIgnoreCase) -or
        $resolvedPath.StartsWith($checkoutPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "RETRIEVAL_MODEL_ASSET_DIR must be outside the Git checkout."
    }

    foreach ($relativePath in @(
        "bge-m3/config.json",
        "bge-m3/pytorch_model.bin",
        "bge-m3/tokenizer.json",
        "bge-reranker-large/config.json",
        "bge-reranker-large/model.safetensors",
        "bge-reranker-large/tokenizer.json"
    )) {
        $assetPath = Join-Path $resolvedPath $relativePath
        if (-not (Test-Path -LiteralPath $assetPath -PathType Leaf)) {
            throw "External model asset directory is missing a required model asset file."
        }
        Assert-NoReparsePointInPath -Path $assetPath
    }
    return $resolvedPath
}

function Resolve-GitCheckoutRoot {
    param([Parameter(Mandatory = $true)][string]$ProjectRoot)

    $git = Get-Command "git" -ErrorAction SilentlyContinue
    if ($null -eq $git) {
        throw "Git is required to resolve the staging checkout boundary."
    }
    $rootLines = & $git.Source -C $ProjectRoot rev-parse --show-toplevel
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to resolve the staging Git checkout root."
    }
    $root = ($rootLines -join [Environment]::NewLine).Trim()
    if ([string]::IsNullOrWhiteSpace($root) -or -not (Test-Path -LiteralPath $root -PathType Container)) {
        throw "Git returned an invalid staging checkout root."
    }
    return (Resolve-Path -LiteralPath $root).Path
}

function Resolve-ComposeCommand {
    $docker = Get-Command "docker" -ErrorAction SilentlyContinue
    if ($null -eq $docker) {
        throw "Docker CLI with the Compose v2 plugin is required for a staging rollback."
    }
    & $docker.Source compose version *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose v2 plugin is required for health-aware staging rollback."
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
        [Environment]::SetEnvironmentVariable($name, "false", "Process")
    }
}

function Get-ProductionComposeConfig {
    param(
        [Parameter(Mandatory = $true)]$Command,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $jsonLines = & $Command.Executable @($Command.Prefix + $Arguments + @("config", "--format", "json"))
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose config validation failed with exit code $LASTEXITCODE."
    }
    try {
        return ($jsonLines -join [Environment]::NewLine) | ConvertFrom-Json
    }
    catch {
        throw "Docker Compose config did not return valid JSON."
    }
}

function Assert-ProductionComposeContract {
    param(
        [Parameter(Mandatory = $true)]$Config,
        [Parameter(Mandatory = $true)][hashtable]$ExpectedImages,
        [Parameter(Mandatory = $true)][string]$ExpectedModelAssetDir
    )

    foreach ($serviceName in $ExpectedImages.Keys) {
        $serviceProperty = $Config.services.PSObject.Properties[$serviceName]
        if ($null -eq $serviceProperty) {
            throw "Production Compose is missing required service: $serviceName"
        }
        $service = $serviceProperty.Value
        if ([string]$service.image -ne $ExpectedImages[$serviceName]) {
            throw "Production Compose resolved an unexpected image for service: $serviceName"
        }
        $buildProperty = $service.PSObject.Properties["build"]
        if ($null -ne $buildProperty -and $null -ne $buildProperty.Value) {
            throw "Production Compose must not retain a local build for service: $serviceName"
        }
    }

    $retrievalService = $Config.services.PSObject.Properties["retrieval-model-service"].Value
    $modelMount = @($retrievalService.volumes) | Where-Object { [string]$_.target -eq "/models" }
    if ($modelMount.Count -ne 1 -or [string]$modelMount[0].type -ne "bind" -or
        [string]$modelMount[0].source -ne $ExpectedModelAssetDir -or $modelMount[0].read_only -ne $true) {
        throw "Production Compose must mount the reviewed external model directory read-only at /models."
    }
    if ([string]$retrievalService.environment.RETRIEVAL_MODEL_VERIFY_HASHES -ne "true") {
        throw "Production retrieval model service must enable startup weight hash verification."
    }

    foreach ($serviceName in @("backend", "worker", "jobs", "agent-worker")) {
        $applicationEnvironment = $Config.services.PSObject.Properties[$serviceName].Value.environment
        if ([string]$applicationEnvironment.APP_ENV -ne "staging") {
            throw "Production Compose must set APP_ENV=staging for service: $serviceName"
        }
        foreach ($capabilityName in $DisabledCapabilityVariables) {
            if ([string]$applicationEnvironment.$capabilityName -ne "false") {
                throw "Production Compose must fail closed for capability: $capabilityName"
            }
        }
    }

    $proxyService = $Config.services.PSObject.Properties["proxy"].Value
    if (@($proxyService.ports).Count -ne 1) {
        throw "Production Compose proxy must bind only the required loopback ports."
    }
    $proxyBinding = @($proxyService.ports)[0]
    if ([string]$proxyBinding.host_ip -ne "127.0.0.1" -or
        [string]$proxyBinding.published -ne "10080" -or
        [string]$proxyBinding.target -ne "80") {
        throw "Production Compose proxy must bind only the required loopback ports."
    }

    $proxyVolumes = @($proxyService.volumes)
    if ($proxyVolumes.Count -ne 1) {
        throw "Production Compose proxy must mount only the tunnel Nginx configuration."
    }
    $proxyConfigMount = $proxyVolumes[0]
    if ([string]$proxyConfigMount.type -ne "bind" -or
        [IO.Path]::GetFileName([string]$proxyConfigMount.source) -ne "nginx-tunnel.conf" -or
        [string]$proxyConfigMount.target -ne "/etc/nginx/nginx.conf" -or
        $proxyConfigMount.read_only -ne $true) {
        throw "Production Compose proxy must mount only the tunnel Nginx configuration."
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
        candidate_retrieval_model_image = $CandidateRetrievalModelImage
        previous_backend_image = $PreviousBackendImage
        previous_frontend_image = $PreviousFrontendImage
        previous_retrieval_model_image = $PreviousRetrievalModelImage
        external_model_assets_validated = $true
        compose_project = "crm-staging"
        docker_transport = "rootless_unix_socket"
        rootless_overlay_sha256 = (Get-FileHash -LiteralPath $rootlessOverlay -Algorithm SHA256).Hash.ToLowerInvariant()
        planned_steps = $PlannedSteps
        completed_steps = $CompletedSteps
        health_checks = $HealthChecks
    }
    $evidence | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $EvidenceFile -Encoding UTF8
}

Assert-StagingTarget
Assert-RootlessDockerHost -Value $DockerHost
$CandidateBackendImage = Assert-ImmutableImage -Name "CandidateBackendImage" -Reference $CandidateBackendImage `
    -Repository "ghcr.io/cp11-gh/crm-backend"
$CandidateFrontendImage = Assert-ImmutableImage -Name "CandidateFrontendImage" -Reference $CandidateFrontendImage `
    -Repository "ghcr.io/cp11-gh/crm-frontend"
$CandidateRetrievalModelImage = Assert-ImmutableImage -Name "CandidateRetrievalModelImage" `
    -Reference $CandidateRetrievalModelImage -Repository "ghcr.io/cp11-gh/crm-retrieval-model-service"
$PreviousBackendImage = Assert-ImmutableImage -Name "PreviousBackendImage" -Reference $PreviousBackendImage `
    -Repository "ghcr.io/cp11-gh/crm-backend"
$PreviousFrontendImage = Assert-ImmutableImage -Name "PreviousFrontendImage" -Reference $PreviousFrontendImage `
    -Repository "ghcr.io/cp11-gh/crm-frontend"
$PreviousRetrievalModelImage = Assert-ImmutableImage -Name "PreviousRetrievalModelImage" `
    -Reference $PreviousRetrievalModelImage -Repository "ghcr.io/cp11-gh/crm-retrieval-model-service"
if ($CandidateBackendImage -eq $PreviousBackendImage -or
    $CandidateFrontendImage -eq $PreviousFrontendImage -or
    $CandidateRetrievalModelImage -eq $PreviousRetrievalModelImage) {
    throw "Rollback images must differ from the candidate image digests."
}

$environmentValues = Read-EnvironmentFile -Path $EnvFile
Assert-EnvironmentContract -Values $environmentValues
$projectRoot = Split-Path -Parent $PSScriptRoot
$gitCheckoutRoot = Resolve-GitCheckoutRoot -ProjectRoot $projectRoot
$modelAssetDir = Assert-ExternalModelAssets -Path $environmentValues["RETRIEVAL_MODEL_ASSET_DIR"] `
    -GitCheckoutRoot $gitCheckoutRoot
$externalImageRepositories = @{
    "POSTGRES_IMAGE" = "pgvector/pgvector"
    "REDIS_IMAGE" = "redis"
    "MINIO_IMAGE" = "minio/minio"
    "NGINX_IMAGE" = "nginx"
}
$validatedExternalImages = @{}
foreach ($name in $externalImageRepositories.Keys) {
    $validatedExternalImages[$name] = Assert-ImmutableImage -Name $name -Reference $environmentValues[$name] `
        -Repository $externalImageRepositories[$name] -AllowTag
}

$baseUri = $null
if (-not [Uri]::TryCreate($BaseUrl, [UriKind]::Absolute, [ref]$baseUri) -or $baseUri.Scheme -ne "https") {
    throw "BaseUrl must be an absolute HTTPS URL."
}

$rootlessOverlay = Join-Path $projectRoot "docker-compose.rootless-staging.yml"
if (-not (Test-Path -LiteralPath $rootlessOverlay -PathType Leaf)) {
    throw "The repository-fixed Rootless staging overlay does not exist."
}
$savedEnvironment = @{}
foreach ($name in @($DisabledCapabilityVariables + @(
    "BACKEND_IMAGE",
    "FRONTEND_IMAGE",
    "RETRIEVAL_MODEL_ASSET_DIR",
    "RETRIEVAL_MODEL_SERVICE_IMAGE",
    "DOCKER_HOST",
    "DOCKER_CONTEXT"
))) {
    $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
}

$completedSteps = @()
try {
    # DOCKER_CONTEXT 的优先级高于 DOCKER_HOST，必须在所有 Docker 调用前清空。
    $env:DOCKER_HOST = $DockerHost
    [Environment]::SetEnvironmentVariable("DOCKER_CONTEXT", $null, "Process")
    $compose = Resolve-ComposeCommand
    $composeArguments = @(
        "--project-name", "crm-staging",
        "--profile", "ai",
        "--env-file", (Resolve-Path -LiteralPath $EnvFile).Path,
        "-f", (Join-Path $projectRoot "docker-compose.yml"),
        "-f", (Join-Path $projectRoot "docker-compose.prod.yml"),
        "-f", (Resolve-Path -LiteralPath $rootlessOverlay).Path
    )
    Set-DisabledCapabilities
    $env:BACKEND_IMAGE = $CandidateBackendImage
    $env:FRONTEND_IMAGE = $CandidateFrontendImage
    $env:RETRIEVAL_MODEL_ASSET_DIR = $modelAssetDir
    $env:RETRIEVAL_MODEL_SERVICE_IMAGE = $CandidateRetrievalModelImage

    $config = Get-ProductionComposeConfig -Command $compose -Arguments $composeArguments
    $expectedImages = @{
        "postgres" = $validatedExternalImages["POSTGRES_IMAGE"]
        "redis" = $validatedExternalImages["REDIS_IMAGE"]
        "minio" = $validatedExternalImages["MINIO_IMAGE"]
        "backend" = $CandidateBackendImage
        "worker" = $CandidateBackendImage
        "jobs" = $CandidateBackendImage
        "agent-worker" = $CandidateBackendImage
        "retrieval-model-service" = $CandidateRetrievalModelImage
        "frontend" = $CandidateFrontendImage
        "proxy" = $validatedExternalImages["NGINX_IMAGE"]
    }
    Assert-ProductionComposeContract -Config $config -ExpectedImages $expectedImages `
        -ExpectedModelAssetDir $modelAssetDir

    if ($ValidateOnly) {
        Write-Evidence -Status "validated" -CompletedSteps @() -HealthChecks @()
        Write-Output "Staging rollback inputs and merged Compose config validated; production_release=false."
        return
    }
    if (-not $Execute) {
        throw "A live rollback requires -Execute; use -ValidateOnly for a non-mutating plan check."
    }
    if (-not $PSCmdlet.ShouldProcess("staging", "disable real capabilities and deploy previous immutable images")) {
        Write-Evidence -Status "not_executed" -CompletedSteps @() -HealthChecks @()
        Write-Output "Staging rollback was not executed; production_release=false."
        return
    }

    Invoke-Compose -Command $compose -Arguments ($composeArguments + @(
        "up", "-d", "--no-build", "--wait", "--wait-timeout", "600", "backend", "worker", "jobs", "agent-worker"
    ))
    $completedSteps += "disable_real_capabilities"

    $env:BACKEND_IMAGE = $PreviousBackendImage
    $env:FRONTEND_IMAGE = $PreviousFrontendImage
    $env:RETRIEVAL_MODEL_SERVICE_IMAGE = $PreviousRetrievalModelImage
    Invoke-Compose -Command $compose -Arguments ($composeArguments + @(
        "pull", "backend", "worker", "jobs", "agent-worker", "frontend", "retrieval-model-service"
    ))
    Invoke-Compose -Command $compose -Arguments ($composeArguments + @(
        "up", "-d", "--no-build", "--wait", "--wait-timeout", "600", "backend", "worker", "jobs", "agent-worker",
        "frontend", "proxy", "retrieval-model-service"
    ))
    $completedSteps += "deploy_previous_image_digests"

    $healthChecks = @(
        [ordered]@{ path = "/healthz"; status_code = Test-HealthEndpoint -Uri ($BaseUrl.TrimEnd("/") + "/healthz") },
        [ordered]@{ path = "/v1/health"; status_code = Test-HealthEndpoint -Uri ($BaseUrl.TrimEnd("/") + "/v1/health") },
        [ordered]@{ path = "/v1/health/ready"; status_code = Test-HealthEndpoint -Uri ($BaseUrl.TrimEnd("/") + "/v1/health/ready") }
    )
    $completedSteps += "verify_health"
    Write-Evidence -Status "passed" -CompletedSteps $completedSteps -HealthChecks $healthChecks
    Write-Output "Staging rollback drill passed; production_release=false."
}
finally {
    foreach ($name in $savedEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], "Process")
    }
}
