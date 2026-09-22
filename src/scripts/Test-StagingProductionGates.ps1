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
    [string]$RetrievalModelImage,

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
    [switch]$Deploy
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

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
    "TIKTOK_EGRESS_SECRET_DIR",
    "TIKTOK_OAUTH_REDIRECT_URI",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
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
$StagingTlsInterpolationSentinel = "/__crm_staging_tls_not_used__"

function Assert-StagingTarget {
    if ($Environment -ne "staging" -or $ConfirmTarget -ne "staging") {
        throw "This command is staging-only; Environment and ConfirmTarget must both equal staging."
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

function Assert-NoReparsePointInPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    $currentPath = [System.IO.Path]::GetFullPath($Path)
    while ($true) {
        $item = Get-Item -LiteralPath $currentPath -Force
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "External runtime paths must not contain a symbolic link or reparse point."
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

function Assert-ExternalEgressSecretDirectory {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$GitCheckoutRoot
    )

    if (-not [System.IO.Path]::IsPathRooted($Path)) {
        throw "TIKTOK_EGRESS_SECRET_DIR must be an absolute server path."
    }
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "TIKTOK_EGRESS_SECRET_DIR does not exist or is not a directory."
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
        throw "TIKTOK_EGRESS_SECRET_DIR must be outside the Git checkout."
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
        throw "Docker CLI with the Compose v2 plugin is required for a staging run."
    }
    & $docker.Source compose version *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose v2 plugin is required for health-aware staging deployment."
    }
    return [PSCustomObject]@{ Executable = $docker.Source; Prefix = @("compose") }
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
        [Parameter(Mandatory = $true)][string]$ExpectedModelAssetDir,
        [Parameter(Mandatory = $true)][string]$ExpectedEgressSecretDir
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

    $egressService = $Config.services.PSObject.Properties["tiktok-egress"].Value
    $egressPorts = $egressService.PSObject.Properties["ports"]
    if ($null -ne $egressPorts -and @($egressPorts.Value).Count -ne 0) {
        throw "TikTok egress helper must not publish ports."
    }
    if ([string]$egressService.user -cne "0:0") {
        throw "TikTok egress helper must run as container root under Rootless Docker."
    }
    if ($egressService.read_only -ne $true) {
        throw "TikTok egress helper must use a read-only root filesystem."
    }
    $egressMounts = @($egressService.volumes)
    if ($egressMounts.Count -ne 1 -or [string]$egressMounts[0].type -ne "bind" -or
        [string]$egressMounts[0].source -ne $ExpectedEgressSecretDir -or
        [string]$egressMounts[0].target -ne "/run/secrets/tiktok-egress" -or
        $egressMounts[0].read_only -ne $true) {
        throw "TikTok egress helper must mount only the reviewed secret directory read-only."
    }
    $egressNetworks = @($egressService.networks.PSObject.Properties.Name)
    if ($egressNetworks.Count -ne 1 -or $egressNetworks[0] -cne "tiktok-egress") {
        throw "TikTok egress helper must join only the dedicated network."
    }
    $droppedCapabilities = @($egressService.cap_drop)
    if ($droppedCapabilities.Count -ne 1 -or [string]$droppedCapabilities[0] -cne "ALL") {
        throw "TikTok egress helper must drop all capabilities."
    }
    $securityOptions = @($egressService.security_opt)
    if ($securityOptions.Count -ne 1 -or [string]$securityOptions[0] -cne "no-new-privileges:true") {
        throw "TikTok egress helper must set no-new-privileges."
    }

    foreach ($serviceName in @("backend", "worker", "jobs", "agent-worker")) {
        $applicationService = $Config.services.PSObject.Properties[$serviceName].Value
        $applicationEnvironment = $applicationService.environment
        if ([string]$applicationEnvironment.APP_ENV -ne "staging") {
            throw "Production Compose must set APP_ENV=staging for service: $serviceName"
        }
        foreach ($capabilityName in $DisabledCapabilityVariables) {
            if ([string]$applicationEnvironment.$capabilityName -ne "false") {
                throw "Production Compose must fail closed for capability: $capabilityName"
            }
        }
        if ($serviceName -in @("backend", "worker", "jobs")) {
            if ([string]$applicationEnvironment.TIKTOK_EGRESS_PROXY_URL -cne "socks5h://tiktok-egress:1080") {
                throw "TikTok application services must use the fixed egress proxy."
            }
            $applicationNetworks = @($applicationService.networks.PSObject.Properties.Name | Sort-Object)
            if ($applicationNetworks.Count -ne 2 -or $applicationNetworks[0] -cne "default" -or
                $applicationNetworks[1] -cne "tiktok-egress") {
                throw "TikTok application services must join default and egress networks."
            }
            $dependsOn = $applicationService.PSObject.Properties["depends_on"]
            $egressDependency = if ($null -eq $dependsOn) {
                $null
            }
            else {
                $dependsOn.Value.PSObject.Properties["tiktok-egress"]
            }
            if ($null -eq $egressDependency -or [string]$egressDependency.Value.condition -cne "service_healthy") {
                throw "TikTok application services must wait for the egress helper health check."
            }
            $applicationVolumes = $applicationService.PSObject.Properties["volumes"]
            if ($null -ne $applicationVolumes -and
                @($applicationVolumes.Value | Where-Object { [string]$_.target -eq "/run/secrets/tiktok-egress" }).Count -ne 0) {
                throw "TikTok application services must not mount egress SSH secrets."
            }
        }
    }

    $proxyService = $Config.services.PSObject.Properties["proxy"].Value
    if (@($proxyService.ports).Count -ne 1) {
        throw "Staging Compose proxy must expose exactly one loopback HTTP port."
    }
    $proxyBinding = @($proxyService.ports)[0]
    if ([string]$proxyBinding.host_ip -ne "127.0.0.1" -or
        [string]$proxyBinding.published -ne "18081" -or
        [string]$proxyBinding.target -ne "80") {
        throw "Staging Compose proxy must expose exactly one loopback HTTP port."
    }

    $proxyVolumes = @($proxyService.volumes)
    if ($proxyVolumes.Count -ne 1) {
        throw "Staging Compose proxy must mount exactly one read-only tunnel Nginx configuration."
    }
    $proxyConfigMount = $proxyVolumes[0]
    if ([string]$proxyConfigMount.type -ne "bind" -or
        [IO.Path]::GetFileName([string]$proxyConfigMount.source) -ne "nginx-tunnel.conf" -or
        [string]$proxyConfigMount.target -ne "/etc/nginx/nginx.conf" -or
        $proxyConfigMount.read_only -ne $true) {
        throw "Staging Compose proxy must mount exactly one read-only tunnel Nginx configuration."
    }
}

function Invoke-TikTokEgressVerification {
    param(
        [Parameter(Mandatory = $true)]$Command,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$ExpectedIp
    )

    $jsonLines = & $Command.Executable @($Command.Prefix + $Arguments + @(
        "run", "--rm", "--no-deps", "backend", "python", "scripts/verify_tiktok_egress.py"
    ))
    if ($LASTEXITCODE -ne 0) {
        throw "TikTok egress verification failed with exit code $LASTEXITCODE."
    }
    try {
        $result = ($jsonLines -join [Environment]::NewLine) | ConvertFrom-Json
    }
    catch {
        throw "TikTok egress verifier did not return valid JSON."
    }
    $propertyNames = @($result.PSObject.Properties.Name | Sort-Object)
    $expectedNames = @("configured_ip", "observed_ip", "schema_version", "status")
    if (Compare-Object -ReferenceObject $expectedNames -DifferenceObject $propertyNames) {
        throw "TikTok egress verifier returned an unexpected schema."
    }
    if ([int]$result.schema_version -ne 1 -or [string]$result.status -cne "ok" -or
        [string]$result.configured_ip -cne $ExpectedIp -or [string]$result.observed_ip -cne $ExpectedIp) {
        throw "TikTok egress verifier result does not match the configured IP."
    }
    return [ordered]@{
        status = "passed"
        configured_ip = [string]$result.configured_ip
        observed_ip = [string]$result.observed_ip
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

function Invoke-ComposePullsWithRetry {
    param(
        [Parameter(Mandatory = $true)]$Command,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string[]]$Services,
        [ValidateRange(1, 5)][int]$MaxAttempts = 3,
        [ValidateRange(1, 60)][int]$RetryDelaySeconds = 5
    )

    foreach ($service in $Services) {
        for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
            & $Command.Executable @($Command.Prefix + $Arguments + @("pull", $service))
            $exitCode = $LASTEXITCODE
            if ($exitCode -eq 0) {
                break
            }
            if ($attempt -eq $MaxAttempts) {
                throw "Docker Compose pull for $service failed after $MaxAttempts attempts with exit code $exitCode."
            }
            Write-Warning "Docker Compose pull for $service failed with exit code $exitCode; retrying attempt $($attempt + 1) of $MaxAttempts."
            Start-Sleep -Seconds $RetryDelaySeconds
        }
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
        [object[]]$HealthChecks,
        [string]$MigrationStatus = "not_executed",
        [AllowNull()][object]$EgressVerification = $null
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
        retrieval_model_image = $RetrievalModelImage
        external_model_assets_validated = $true
        compose_project = "crm-staging"
        docker_transport = "rootless_unix_socket"
        database_migration = $MigrationStatus
        rootless_overlay_sha256 = (Get-FileHash -LiteralPath $rootlessOverlay -Algorithm SHA256).Hash.ToLowerInvariant()
        tiktok_egress_overlay_sha256 = (Get-FileHash -LiteralPath $egressOverlay -Algorithm SHA256).Hash.ToLowerInvariant()
        validated_variable_names = @($RequiredVariables + $DisabledCapabilityVariables | Sort-Object -Unique)
        health_checks = $HealthChecks
    }
    if ($null -ne $EgressVerification) {
        $evidence["tiktok_egress"] = $EgressVerification
    }
    $evidence | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $EvidenceFile -Encoding UTF8
}

Assert-StagingTarget
Assert-RootlessDockerHost -Value $DockerHost
$BackendImage = Assert-ImmutableImage -Name "BackendImage" -Reference $BackendImage -Repository "ghcr.io/cp11-gh/crm-backend"
$FrontendImage = Assert-ImmutableImage -Name "FrontendImage" -Reference $FrontendImage -Repository "ghcr.io/cp11-gh/crm-frontend"
$RetrievalModelImage = Assert-ImmutableImage -Name "RetrievalModelImage" -Reference $RetrievalModelImage `
    -Repository "ghcr.io/cp11-gh/crm-retrieval-model-service"

$baseUri = $null
if (-not [Uri]::TryCreate($BaseUrl, [UriKind]::Absolute, [ref]$baseUri) -or $baseUri.Scheme -ne "https") {
    throw "BaseUrl must be an absolute HTTPS URL."
}

$environmentValues = Read-EnvironmentFile -Path $EnvFile
Assert-EnvironmentContract -Values $environmentValues
$sourceRoot = Split-Path -Parent $PSScriptRoot
$gitCheckoutRoot = Resolve-GitCheckoutRoot -ProjectRoot $sourceRoot
$modelAssetDir = Assert-ExternalModelAssets -Path $environmentValues["RETRIEVAL_MODEL_ASSET_DIR"] `
    -GitCheckoutRoot $gitCheckoutRoot
$egressSecretDir = Assert-ExternalEgressSecretDirectory -Path $environmentValues["TIKTOK_EGRESS_SECRET_DIR"] `
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
$configuredRetrievalModelImage = Assert-ImmutableImage -Name "RETRIEVAL_MODEL_SERVICE_IMAGE" `
    -Reference $environmentValues["RETRIEVAL_MODEL_SERVICE_IMAGE"] `
    -Repository "ghcr.io/cp11-gh/crm-retrieval-model-service"
if ($configuredRetrievalModelImage -ne $RetrievalModelImage) {
    throw "RETRIEVAL_MODEL_SERVICE_IMAGE must equal the reviewed RetrievalModelImage input."
}

$egressOverlay = Join-Path $sourceRoot "compose/docker-compose.tiktok-egress.yml"
$rootlessOverlay = Join-Path $sourceRoot "compose/docker-compose.rootless-staging.yml"
if (-not (Test-Path -LiteralPath $egressOverlay -PathType Leaf)) {
    throw "The repository-fixed TikTok egress overlay does not exist."
}
if (-not (Test-Path -LiteralPath $rootlessOverlay -PathType Leaf)) {
    throw "The repository-fixed Rootless staging overlay does not exist."
}

$savedEnvironment = @{}
foreach ($name in @($DisabledCapabilityVariables + @(
    "BACKEND_IMAGE",
    "FRONTEND_IMAGE",
    "RETRIEVAL_MODEL_ASSET_DIR",
    "RETRIEVAL_MODEL_SERVICE_IMAGE",
    "TIKTOK_EGRESS_IMAGE",
    "TIKTOK_EGRESS_SECRET_DIR",
    "TLS_CERT_DIR",
    "DOCKER_HOST",
    "DOCKER_CONTEXT"
))) {
    $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
}
try {
    # DOCKER_CONTEXT 的优先级高于 DOCKER_HOST，必须在所有 Docker 调用前清空。
    $env:DOCKER_HOST = $DockerHost
    [Environment]::SetEnvironmentVariable("DOCKER_CONTEXT", $null, "Process")
    $compose = Resolve-ComposeCommand
    $composeArguments = @(
        "--project-name", "crm-staging",
        "--profile", "ai",
        "--env-file", (Resolve-Path -LiteralPath $EnvFile).Path,
        "-f", (Join-Path $sourceRoot "compose/docker-compose.yml"),
        "-f", (Join-Path $sourceRoot "compose/docker-compose.prod.yml"),
        "-f", (Resolve-Path -LiteralPath $egressOverlay).Path,
        "-f", (Resolve-Path -LiteralPath $rootlessOverlay).Path
    )
    Set-DisabledCapabilities
    $env:BACKEND_IMAGE = $BackendImage
    $env:FRONTEND_IMAGE = $FrontendImage
    $env:RETRIEVAL_MODEL_ASSET_DIR = $modelAssetDir
    $env:RETRIEVAL_MODEL_SERVICE_IMAGE = $configuredRetrievalModelImage
    $env:TIKTOK_EGRESS_IMAGE = $BackendImage
    $env:TIKTOK_EGRESS_SECRET_DIR = $egressSecretDir
    # Compose 会在合并 rootless override 前先展开 production 文件；此值只用于通过必填展开，最终配置不得挂载它。
    $env:TLS_CERT_DIR = $StagingTlsInterpolationSentinel

    $config = Get-ProductionComposeConfig -Command $compose -Arguments $composeArguments
    $expectedImages = @{
        "postgres" = $validatedExternalImages["POSTGRES_IMAGE"]
        "redis" = $validatedExternalImages["REDIS_IMAGE"]
        "minio" = $validatedExternalImages["MINIO_IMAGE"]
        "tiktok-egress" = $BackendImage
        "backend" = $BackendImage
        "worker" = $BackendImage
        "jobs" = $BackendImage
        "agent-worker" = $BackendImage
        "retrieval-model-service" = $configuredRetrievalModelImage
        "frontend" = $FrontendImage
        "proxy" = $validatedExternalImages["NGINX_IMAGE"]
    }
    Assert-ProductionComposeContract -Config $config -ExpectedImages $expectedImages `
        -ExpectedModelAssetDir $modelAssetDir -ExpectedEgressSecretDir $egressSecretDir

    if ($ValidateOnly) {
        Write-Evidence -Status "validated" -HealthChecks @()
        Write-Output "Staging production gate inputs and merged Compose config validated; production_release=false."
        return
    }

    if (-not $Deploy) {
        throw "A live run requires -Deploy; use -ValidateOnly for a non-mutating preflight."
    }

    if (-not $PSCmdlet.ShouldProcess("staging", "deploy immutable application image digests")) {
        Write-Evidence -Status "not_executed" -HealthChecks @()
        Write-Output "Staging deployment was not executed; production_release=false."
        return
    }
    # 同一 backend 摘要被多个服务共享，只拉取一次；逐镜像限次重试避免慢链路并发传输放大临时断连。
    Invoke-ComposePullsWithRetry -Command $compose -Arguments $composeArguments -Services @(
        "tiktok-egress", "frontend", "retrieval-model-service"
    )
    Invoke-Compose -Command $compose -Arguments ($composeArguments + @(
        "up", "-d", "--no-build", "--wait", "--wait-timeout", "600", "postgres", "redis", "minio"
    ))
    Invoke-Compose -Command $compose -Arguments ($composeArguments + @(
        "up", "-d", "--no-build", "--wait", "--wait-timeout", "600", "tiktok-egress"
    ))
    $egressVerification = Invoke-TikTokEgressVerification -Command $compose -Arguments $composeArguments `
        -ExpectedIp $environmentValues["TIKTOK_EGRESS_IP"]
    Invoke-Compose -Command $compose -Arguments ($composeArguments + @(
        "run", "--rm", "--no-deps", "backend", "alembic", "upgrade", "head"
    ))
    Invoke-Compose -Command $compose -Arguments ($composeArguments + @(
        "run", "--rm", "--no-deps", "backend", "alembic", "current", "--check-heads"
    ))
    Invoke-Compose -Command $compose -Arguments ($composeArguments + @(
        "up", "-d", "--no-build", "--wait", "--wait-timeout", "600", "backend", "worker", "jobs", "agent-worker",
        "frontend", "proxy", "retrieval-model-service"
    ))

    $healthChecks = @(
        [ordered]@{ path = "/healthz"; status_code = Test-HealthEndpoint -Uri ($BaseUrl.TrimEnd("/") + "/healthz") },
        [ordered]@{ path = "/v1/health"; status_code = Test-HealthEndpoint -Uri ($BaseUrl.TrimEnd("/") + "/v1/health") },
        [ordered]@{ path = "/v1/health/ready"; status_code = Test-HealthEndpoint -Uri ($BaseUrl.TrimEnd("/") + "/v1/health/ready") }
    )
    Write-Evidence -Status "passed" -HealthChecks $healthChecks -MigrationStatus "heads_applied" `
        -EgressVerification $egressVerification
    Write-Output "Staging production gate deployment and health verification passed; production_release=false."
}
finally {
    foreach ($name in $savedEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], "Process")
    }
}
