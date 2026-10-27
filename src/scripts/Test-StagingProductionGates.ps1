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

    [string]$DocumentParserImage,

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
    [switch]$Deploy,
    [switch]$EnableTikTokWebhookRead,
    [switch]$EnableTikTokManualSend,
    [string]$AllowedTikTokConversationId,
    [string]$AllowedTikTokStoreIds,
    [switch]$EnableWorkspaceTranslation,
    [switch]$EnableAgentDebug,
    [switch]$EnableG5SSELoadTest,
    [switch]$EnableDocumentIngestion,
    [switch]$EnableG2WebhookProbe,
    [string]$G2ProbeMode,
    [string]$G2ProbeRunId,
    [string]$G2ProbeStoreId,
    [string]$G2ProbeConversationId,
    [string]$G2ProbeExpiresAt,
    [string]$PreWindowSnapshotFile
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
    "TIKTOK_CONVERSATION_SYNC_ENABLED",
    "REAL_TIKTOK_WEBHOOK_ENABLED",
    "REAL_TIKTOK_MESSAGE_WRITE_ENABLED",
    "REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED",
    "LLM_ENABLED",
    "LLM_LIVE_EVAL",
    "AI_TRANSLATION_ENABLED",
    "AI_MARKETING_ENABLED",
    "AUTO_REPLY_ENABLED"
)
$WebhookReadCapabilities = @("REAL_TIKTOK_READ_ENABLED", "REAL_TIKTOK_WEBHOOK_ENABLED")
$G2ProbeVariables = @(
    "G2_WEBHOOK_PROBE_MODE", "G2_WEBHOOK_PROBE_RUN_ID", "G2_WEBHOOK_PROBE_STORE_ID",
    "G2_WEBHOOK_PROBE_CONVERSATION_ID", "G2_WEBHOOK_PROBE_EXPIRES_AT"
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
        if ($name -eq "TIKTOK_CONVERSATION_SYNC_ENABLED" -and -not $Values.ContainsKey($name)) {
            continue
        }
        if (-not $Values.ContainsKey($name) -or $Values[$name].Trim().ToLowerInvariant() -ne "false") {
            throw "Staging preflight requires $name=false."
        }
    }
    if ($Values.ContainsKey("SSE_LOAD_TEST_ENABLED") -and
        $Values["SSE_LOAD_TEST_ENABLED"].Trim().ToLowerInvariant() -ne "false") {
        throw "Staging preflight requires SSE_LOAD_TEST_ENABLED=false outside the reviewed overlay."
    }
    if ($Values.ContainsKey("WORKSPACE_MESSAGE_TRANSLATION_ENABLED") -and
        $Values["WORKSPACE_MESSAGE_TRANSLATION_ENABLED"].Trim().ToLowerInvariant() -ne "false") {
        throw "Staging preflight requires WORKSPACE_MESSAGE_TRANSLATION_ENABLED=false outside the reviewed overlay."
    }
    if ($Values.ContainsKey("AGENT_DEBUG_ENABLED") -and
        $Values["AGENT_DEBUG_ENABLED"].Trim().ToLowerInvariant() -ne "false") {
        throw "Staging preflight requires AGENT_DEBUG_ENABLED=false outside the reviewed overlay."
    }
    foreach ($name in $G2ProbeVariables) {
        if ($Values.ContainsKey($name) -and -not [string]::IsNullOrEmpty($Values[$name])) {
            throw "G2 Webhook probe target must not be stored in the staging environment file."
        }
    }
    if (($EnableG5SSELoadTest -or $EnableWorkspaceTranslation -or $EnableAgentDebug) -and (
        -not $Values.ContainsKey("LLM_PRIMARY_PROVIDER") -or $Values["LLM_PRIMARY_PROVIDER"].Trim() -cne "deepseek" -or
        -not $Values.ContainsKey("LLM_PRIMARY_MODEL") -or [string]::IsNullOrWhiteSpace($Values["LLM_PRIMARY_MODEL"]) -or
        -not $Values.ContainsKey("DEEPSEEK_API_KEY") -or [string]::IsNullOrWhiteSpace($Values["DEEPSEEK_API_KEY"])
    )) {
        throw "Staging model mode requires an approved DeepSeek model and a configured API key."
    }
}

function Assert-G2ProbeServiceEnvironment {
    param(
        [Parameter(Mandatory = $true)]$EnvironmentValues,
        [Parameter(Mandatory = $true)][string]$ServiceName,
        [Parameter(Mandatory = $true)][hashtable]$ExpectedValues
    )
    foreach ($name in $G2ProbeVariables) {
        $actualValue = if ($EnvironmentValues -is [System.Collections.IDictionary]) {
            $EnvironmentValues[$name]
        } else {
            $property = $EnvironmentValues.PSObject.Properties[$name]
            if ($null -eq $property) { "" } else { $property.Value }
        }
        $actual = [string]$actualValue
        $expected = if ($ServiceName -ceq "backend" -and $ExpectedValues.ContainsKey($name)) {
            [string]$ExpectedValues[$name]
        } else { "" }
        if ($name -ceq "G2_WEBHOOK_PROBE_EXPIRES_AT" -and $expected) {
            $actualExpiry = [DateTimeOffset]::MinValue
            $expectedExpiry = [DateTimeOffset]::MinValue
            $actualValid = if ($actualValue -is [DateTime]) {
                $actualExpiry = [DateTimeOffset]$actualValue
                $true
            } else { [DateTimeOffset]::TryParse($actual, [ref]$actualExpiry) }
            if ($actualValid -and
                [DateTimeOffset]::TryParse($expected, [ref]$expectedExpiry) -and
                $actualExpiry.ToUnixTimeSeconds() -eq $expectedExpiry.ToUnixTimeSeconds()) {
                continue
            }
        }
        if ($actual -cne $expected -and -not ($expected -ceq "" -and $name -ceq "G2_WEBHOOK_PROBE_MODE" -and
            $actual -ceq "off")) {
            throw "G2 Webhook probe runtime target differs from reviewed backend-only window: $ServiceName/$name"
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

function Assert-ExternalMinerUAssets {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$GitCheckoutRoot
    )
    if (-not [System.IO.Path]::IsPathRooted($Path) -or
        -not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "MINERU_ASSET_DIR must be an existing absolute server directory."
    }
    Assert-NoReparsePointInPath -Path $Path
    $resolved = (Resolve-Path -LiteralPath $Path).Path
    $checkout = (Resolve-Path -LiteralPath $GitCheckoutRoot).Path
    $prefix = $checkout.TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar) +
        [IO.Path]::DirectorySeparatorChar
    if ($resolved.Equals($checkout, [StringComparison]::OrdinalIgnoreCase) -or
        $resolved.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "MINERU_ASSET_DIR must be outside the Git checkout."
    }
    if (-not (Get-ChildItem -LiteralPath $resolved -Force | Select-Object -First 1)) {
        throw "MINERU_ASSET_DIR is empty."
    }
    return $resolved
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
        [Parameter(Mandatory = $true)][string]$ExpectedEgressSecretDir,
        [string]$ExpectedMinerUAssetDir,
        [switch]$EnableDocumentIngestion,
        [switch]$EnableTikTokWebhookRead,
        [switch]$EnableTikTokManualSend,
        [string]$AllowedTikTokConversationId,
        [string]$AllowedTikTokStoreIds,
        [switch]$EnableWorkspaceTranslation,
        [switch]$EnableAgentDebug,
        [switch]$EnableG5SSELoadTest,
        [Parameter(Mandatory = $true)][hashtable]$G2ProbeExpected
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
    if ($EnableG5SSELoadTest -or $EnableAgentDebug) {
        $backendTokenProperty = $Config.services.backend.environment.PSObject.Properties["RETRIEVAL_MODEL_SERVICE_TOKEN"]
        $retrievalTokenProperty = $retrievalService.environment.PSObject.Properties["RETRIEVAL_MODEL_SERVICE_TOKEN"]
        $backendToken = if ($null -eq $backendTokenProperty) { "" } else { [string]$backendTokenProperty.Value }
        $retrievalToken = if ($null -eq $retrievalTokenProperty) { "" } else { [string]$retrievalTokenProperty.Value }
        if ($backendToken.Length -lt 32 -or $backendToken -cne $retrievalToken) {
            throw "G5 backend and retrieval model service must share a valid internal model token."
        }
    }
    if ($EnableDocumentIngestion) {
        $documentService = $Config.services.PSObject.Properties["document-parser"].Value
        $documentMounts = @($documentService.volumes)
        foreach ($mount in @(@{ target = "/models"; source = $ExpectedModelAssetDir },
                @{ target = "/opt/mineru"; source = $ExpectedMinerUAssetDir })) {
            $matches = @($documentMounts | Where-Object {
                [string]$_.target -ceq $mount.target -and [string]$_.source -ceq $mount.source -and
                [string]$_.type -ceq "bind" -and $_.read_only -eq $true
            })
            if ($matches.Count -ne 1) { throw "Document worker must use reviewed read-only model assets." }
        }
        $documentToken = [string]$documentService.environment.RETRIEVAL_MODEL_SERVICE_TOKEN
        $retrievalToken = [string]$retrievalService.environment.RETRIEVAL_MODEL_SERVICE_TOKEN
        if ($documentToken.Length -lt 32 -or $documentToken -cne $retrievalToken) {
            throw "Document worker and retrieval model service must share a valid internal token."
        }
        if ([string]$documentService.environment.MINERU_MODEL_SOURCE -cne "local" -or
            [string]$documentService.environment.HF_HUB_OFFLINE -cne "1" -or
            [string]$documentService.environment.EMBEDDING_ENABLED -cne "true" -or
            [string]$documentService.environment.APP_ENV -cne "staging" -or
            $documentService.read_only -ne $true -or
            ($null -ne $documentService.PSObject.Properties["ports"] -and
             @($documentService.ports).Count -ne 0)) {
            throw "Document worker offline and private runtime contract failed."
        }
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
        Assert-G2ProbeServiceEnvironment -EnvironmentValues $applicationEnvironment `
            -ServiceName $serviceName -ExpectedValues $G2ProbeExpected
        if ([string]$applicationEnvironment.APP_ENV -ne "staging") {
            throw "Production Compose must set APP_ENV=staging for service: $serviceName"
        }
        foreach ($capabilityName in $DisabledCapabilityVariables) {
            $expectedValue = if ($EnableTikTokWebhookRead -and
                (($serviceName -in @("backend", "worker") -and $capabilityName -in $WebhookReadCapabilities) -or
                 ($serviceName -eq "worker" -and $capabilityName -eq "TIKTOK_CONVERSATION_SYNC_ENABLED"))) {
                "true"
            } else { "false" }
            if ($EnableG5SSELoadTest -and $serviceName -ceq "backend" -and $capabilityName -ceq "LLM_ENABLED") {
                $expectedValue = "true"
            }
            if ($EnableTikTokManualSend -and $serviceName -ceq "backend" -and
                $capabilityName -ceq "REAL_TIKTOK_MESSAGE_WRITE_ENABLED") {
                $expectedValue = "true"
            }
            if ([string]$applicationEnvironment.$capabilityName -cne $expectedValue) {
                throw "Staging Compose capability does not match reviewed mode: $serviceName/$capabilityName"
            }
        }
        $allowedProperty = $applicationEnvironment.PSObject.Properties["TIKTOK_MESSAGE_WRITE_ALLOWED_CONVERSATION_ID"]
        $allowedActual = if ($null -eq $allowedProperty) { "" } else { [string]$allowedProperty.Value }
        $allowedExpected = if ($EnableTikTokManualSend -and $serviceName -ceq "backend") {
            $AllowedTikTokConversationId
        } else { "" }
        if ($allowedActual -cne $allowedExpected) {
            throw "Staging Compose manual send target does not match reviewed mode: $serviceName"
        }
        $storeProperty = $applicationEnvironment.PSObject.Properties["TIKTOK_MESSAGE_WRITE_ALLOWED_STORE_IDS"]
        $storeActual = if ($null -eq $storeProperty) { "" } else { [string]$storeProperty.Value }
        $storeExpected = if ($EnableTikTokManualSend -and $serviceName -ceq "backend") {
            $AllowedTikTokStoreIds
        } else { "" }
        if ($storeActual -cne $storeExpected) {
            throw "Staging Compose manual send target does not match reviewed mode: $serviceName"
        }
        $expectedEmbedding = if (($EnableG5SSELoadTest -or $EnableAgentDebug) -and $serviceName -ceq "backend") { "true" } else { "false" }
        $embeddingProperty = $applicationEnvironment.PSObject.Properties["EMBEDDING_ENABLED"]
        $actualEmbedding = if ($null -eq $embeddingProperty) { "false" } else { [string]$embeddingProperty.Value }
        if ([string]::IsNullOrEmpty($actualEmbedding)) { $actualEmbedding = "false" }
        if ($actualEmbedding -cne $expectedEmbedding) {
            throw "Staging Compose embedding capability does not match reviewed mode: $serviceName"
        }
        $debugProperty = $applicationEnvironment.PSObject.Properties["AGENT_DEBUG_ENABLED"]
        $actualDebug = if ($null -eq $debugProperty) { "false" } else { [string]$debugProperty.Value }
        $expectedDebug = if ($EnableAgentDebug -and $serviceName -ceq "backend") { "true" } else { "false" }
        if ($actualDebug -cne $expectedDebug) {
            throw "Staging Compose Agent debug capability does not match reviewed mode: $serviceName"
        }
        $expectedTranslation = if ($EnableWorkspaceTranslation -and $serviceName -ceq "backend") { "true" } else { "false" }
        if ([string]$applicationEnvironment.WORKSPACE_MESSAGE_TRANSLATION_ENABLED -cne $expectedTranslation) {
            throw "Staging Compose translation capability does not match reviewed mode: $serviceName"
        }
        $expectedSSE = if ($EnableG5SSELoadTest -and $serviceName -ceq "backend") { "true" } else { "false" }
        if ([string]$applicationEnvironment.SSE_LOAD_TEST_ENABLED -cne $expectedSSE) {
            throw "Staging Compose SSE capability does not match reviewed mode: $serviceName"
        }
        if ($serviceName -ceq "backend") {
            $expectedLimit = if ($EnableG5SSELoadTest) { "60" } else { "10" }
            if ([string]$applicationEnvironment.CHAT_QUERY_LIMIT -cne $expectedLimit) {
                throw "Staging Compose query limit does not match reviewed mode."
            }
            if ($EnableG5SSELoadTest -and (
                [string]$applicationEnvironment.LLM_PRIMARY_PROVIDER -cne "deepseek" -or
                [string]::IsNullOrWhiteSpace([string]$applicationEnvironment.LLM_PRIMARY_MODEL) -or
                [string]::IsNullOrWhiteSpace([string]$applicationEnvironment.DEEPSEEK_API_KEY)
            )) {
                throw "Staging Compose DeepSeek configuration does not match reviewed mode."
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

function Assert-RunningStagingMode {
    param(
        [Parameter(Mandatory = $true)]$Command,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$ExpectedBackendImage,
        [switch]$EnableTikTokWebhookRead,
        [switch]$EnableTikTokManualSend,
        [string]$AllowedTikTokConversationId,
        [string]$AllowedTikTokStoreIds,
        [switch]$EnableWorkspaceTranslation,
        [switch]$EnableAgentDebug,
        [switch]$EnableG5SSELoadTest,
        [Parameter(Mandatory = $true)][hashtable]$G2ProbeExpected
    )

    # 仅从运行容器提取白名单开关；完整 Env 包含密钥，不可写入日志或证据。
    foreach ($serviceName in @("backend", "worker", "jobs", "agent-worker")) {
        $containerLines = & $Command.Executable @($Command.Prefix + $Arguments + @("ps", "-q", $serviceName)) 2>$null
        $containerId = ($containerLines -join "").Trim()
        if ($LASTEXITCODE -ne 0 -or $containerId -cnotmatch '^[A-Za-z0-9][A-Za-z0-9_.-]{3,127}$') {
            throw "Staging runtime container lookup failed: $serviceName"
        }
        $configLines = & $Command.Executable inspect --format '{{json .Config}}' $containerId 2>$null
        if ($LASTEXITCODE -ne 0) {
            throw "Staging runtime config lookup failed: $serviceName"
        }
        try {
            $runtime = ($configLines -join "") | ConvertFrom-Json -ErrorAction Stop
            $runtimeEnvironment = @{}
            foreach ($assignment in @($runtime.Env)) {
                $entry = [string]$assignment
                $separator = $entry.IndexOf("=")
                if ($separator -le 0) { throw "invalid assignment" }
                $name = $entry.Substring(0, $separator)
                if ($runtimeEnvironment.ContainsKey($name)) { throw "duplicate assignment" }
                $runtimeEnvironment[$name] = $entry.Substring($separator + 1)
            }
        }
        catch {
            throw "Staging runtime config is invalid: $serviceName"
        }
        if ([string]$runtime.Image -cne $ExpectedBackendImage) {
            throw "Staging runtime image does not match the reviewed digest: $serviceName"
        }
        if ($runtimeEnvironment["APP_ENV"] -cne "staging") {
            throw "Staging runtime capability does not match reviewed mode: $serviceName"
        }
        Assert-G2ProbeServiceEnvironment -EnvironmentValues $runtimeEnvironment `
            -ServiceName $serviceName -ExpectedValues $G2ProbeExpected
        foreach ($capabilityName in $DisabledCapabilityVariables) {
            $expectedValue = if ($EnableTikTokWebhookRead -and
                (($serviceName -in @("backend", "worker") -and $capabilityName -in $WebhookReadCapabilities) -or
                 ($serviceName -eq "worker" -and $capabilityName -eq "TIKTOK_CONVERSATION_SYNC_ENABLED"))) {
                "true"
            } else { "false" }
            if ($EnableG5SSELoadTest -and $serviceName -ceq "backend" -and $capabilityName -ceq "LLM_ENABLED") {
                $expectedValue = "true"
            }
            if ($EnableTikTokManualSend -and $serviceName -ceq "backend" -and
                $capabilityName -ceq "REAL_TIKTOK_MESSAGE_WRITE_ENABLED") {
                $expectedValue = "true"
            }
            if ($runtimeEnvironment[$capabilityName] -cne $expectedValue) {
                throw "Staging runtime capability does not match reviewed mode: $serviceName/$capabilityName"
            }
        }
        $allowedActual = [string]$runtimeEnvironment["TIKTOK_MESSAGE_WRITE_ALLOWED_CONVERSATION_ID"]
        $allowedExpected = if ($EnableTikTokManualSend -and $serviceName -ceq "backend") {
            $AllowedTikTokConversationId
        } else { "" }
        if ($allowedActual -cne $allowedExpected) {
            throw "Staging runtime manual send target does not match reviewed mode: $serviceName"
        }
        $storeActual = [string]$runtimeEnvironment["TIKTOK_MESSAGE_WRITE_ALLOWED_STORE_IDS"]
        $storeExpected = if ($EnableTikTokManualSend -and $serviceName -ceq "backend") {
            $AllowedTikTokStoreIds
        } else { "" }
        if ($storeActual -cne $storeExpected) {
            throw "Staging runtime manual send target does not match reviewed mode: $serviceName"
        }
        $expectedEmbedding = if (($EnableG5SSELoadTest -or $EnableAgentDebug) -and $serviceName -ceq "backend") { "true" } else { "false" }
        $actualEmbedding = [string]$runtimeEnvironment["EMBEDDING_ENABLED"]
        if ([string]::IsNullOrEmpty($actualEmbedding)) { $actualEmbedding = "false" }
        if ($actualEmbedding -cne $expectedEmbedding) {
            throw "Staging runtime embedding capability does not match reviewed mode: $serviceName"
        }
        $actualDebug = [string]$runtimeEnvironment["AGENT_DEBUG_ENABLED"]
        if ([string]::IsNullOrEmpty($actualDebug)) { $actualDebug = "false" }
        $expectedDebug = if ($EnableAgentDebug -and $serviceName -ceq "backend") { "true" } else { "false" }
        if ($actualDebug -cne $expectedDebug) {
            throw "Staging runtime Agent debug capability does not match reviewed mode: $serviceName"
        }
        $expectedTranslation = if ($EnableWorkspaceTranslation -and $serviceName -ceq "backend") { "true" } else { "false" }
        if ($runtimeEnvironment["WORKSPACE_MESSAGE_TRANSLATION_ENABLED"] -cne $expectedTranslation) {
            throw "Staging runtime translation capability does not match reviewed mode: $serviceName"
        }
        $expectedSSE = if ($EnableG5SSELoadTest -and $serviceName -ceq "backend") { "true" } else { "false" }
        if ($runtimeEnvironment["SSE_LOAD_TEST_ENABLED"] -cne $expectedSSE) {
            throw "Staging runtime capability does not match reviewed mode: $serviceName/SSE_LOAD_TEST_ENABLED"
        }
        if ($serviceName -ceq "backend") {
            $expectedLimit = if ($EnableG5SSELoadTest) { "60" } else { "10" }
            if ($runtimeEnvironment["CHAT_QUERY_LIMIT"] -cne $expectedLimit) {
                throw "Staging runtime query limit does not match reviewed mode."
            }
        }
    }
}

function Assert-RunningDocumentWorker {
    param(
        [Parameter(Mandatory = $true)]$Command,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$ExpectedImage,
        [Parameter(Mandatory = $true)][string]$ExpectedToken
    )
    $lines = & $Command.Executable @($Command.Prefix + $Arguments + @("ps", "-q", "document-parser")) 2>$null
    $containerId = ($lines -join "").Trim()
    if ($LASTEXITCODE -ne 0 -or $containerId -cnotmatch '^[A-Za-z0-9][A-Za-z0-9_.-]{3,127}$') {
        throw "Staging document worker container lookup failed."
    }
    $lines = & $Command.Executable inspect --format '{{json .}}' $containerId 2>$null
    if ($LASTEXITCODE -ne 0) { throw "Staging document worker inspect failed." }
    try {
        $container = ($lines -join "") | ConvertFrom-Json -ErrorAction Stop
        $runtimeEnvironment = @{}
        foreach ($assignment in @($container.Config.Env)) {
            $entry = [string]$assignment
            $separator = $entry.IndexOf("=")
            if ($separator -le 0) { throw "invalid assignment" }
            $runtimeEnvironment[$entry.Substring(0, $separator)] = $entry.Substring($separator + 1)
        }
    }
    catch { throw "Staging document worker inspect result is invalid." }
    if ($container.Config.Image -cne $ExpectedImage -or $container.State.Running -ne $true -or
        $container.HostConfig.ReadonlyRootfs -ne $true -or
        $runtimeEnvironment["APP_ENV"] -cne "staging" -or
        $runtimeEnvironment["EMBEDDING_ENABLED"] -cne "true" -or
        $runtimeEnvironment["MINERU_MODEL_SOURCE"] -cne "local" -or
        $runtimeEnvironment["HF_HUB_OFFLINE"] -cne "1" -or
        $runtimeEnvironment["RETRIEVAL_MODEL_SERVICE_TOKEN"] -cne $ExpectedToken) {
        throw "Staging document worker runtime differs from the reviewed digest or offline mode."
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
        document_ingestion_enabled = [bool]$EnableDocumentIngestion
        document_parser_image = if ($EnableDocumentIngestion) { $DocumentParserImage } else { $null }
        mineru_assets_validated = [bool]$EnableDocumentIngestion
        external_model_assets_validated = $true
        compose_project = "crm-staging"
        docker_transport = "rootless_unix_socket"
        database_migration = $MigrationStatus
        rootless_overlay_sha256 = (Get-FileHash -LiteralPath $rootlessOverlay -Algorithm SHA256).Hash.ToLowerInvariant()
        tiktok_egress_overlay_sha256 = (Get-FileHash -LiteralPath $egressOverlay -Algorithm SHA256).Hash.ToLowerInvariant()
        tiktok_webhook_read_enabled = [bool]$EnableTikTokWebhookRead
        g2_webhook_probe_enabled = [bool]$EnableG2WebhookProbe
        g2_webhook_probe_mode = if ($EnableG2WebhookProbe) { $G2ProbeMode } else { "off" }
        tiktok_manual_send_enabled = [bool]$EnableTikTokManualSend
        tiktok_manual_send_target = if (-not $EnableTikTokManualSend) { "disabled" }
            elseif ($AllowedTikTokStoreIds) { "store" } else { "conversation" }
        tiktok_manual_send_store_count = if ($AllowedTikTokStoreIds) {
            @($AllowedTikTokStoreIds.Split(',')).Count
        } else { 0 }
        g5_sse_load_test_enabled = [bool]$EnableG5SSELoadTest
        workspace_message_translation_enabled = [bool]$EnableWorkspaceTranslation
        agent_debug_enabled = [bool]$EnableAgentDebug
        backend_query_limit = if ($EnableG5SSELoadTest) { 60 } else { 10 }
        runtime_mode_verified = ($Status -ceq "passed")
        validated_variable_names = @($RequiredVariables + $DisabledCapabilityVariables | Sort-Object -Unique)
        health_checks = $HealthChecks
    }
    if ($EnableTikTokWebhookRead) {
        $evidence["tiktok_webhook_read_overlay_sha256"] =
            (Get-FileHash -LiteralPath $webhookReadOverlay -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    if ($EnableG2WebhookProbe) {
        $evidence["g2_webhook_probe_overlay_sha256"] =
            (Get-FileHash -LiteralPath $g2ProbeOverlay -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    if ($EnableTikTokManualSend) {
        $evidence["tiktok_manual_send_overlay_sha256"] =
            (Get-FileHash -LiteralPath $manualSendOverlay -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    if ($EnableG5SSELoadTest) {
        $evidence["g5_sse_load_test_overlay_sha256"] =
            (Get-FileHash -LiteralPath $g5SSEOverlay -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    if ($EnableWorkspaceTranslation) {
        $evidence["workspace_translation_overlay_sha256"] =
            (Get-FileHash -LiteralPath $translationOverlay -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    if ($EnableAgentDebug) {
        $evidence["agent_debug_overlay_sha256"] =
            (Get-FileHash -LiteralPath $agentDebugOverlay -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    if ($null -ne $EgressVerification) {
        $evidence["tiktok_egress"] = $EgressVerification
    }
    $evidence | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $EvidenceFile -Encoding UTF8
}

Assert-StagingTarget
Assert-RootlessDockerHost -Value $DockerHost
if ($EnableTikTokWebhookRead -and $EnableG5SSELoadTest) {
    throw "G2 Webhook read and G5 SSE modes cannot be combined."
}
$g2ProbeExpected = @{}
if ($EnableG2WebhookProbe) {
    $probeExpiry = [DateTimeOffset]::MinValue
    if (-not $EnableTikTokWebhookRead -or $EnableG5SSELoadTest -or
        $G2ProbeMode -cnotin @("before_commit_503", "after_commit_503") -or
        $G2ProbeRunId -cnotmatch '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' -or
        $G2ProbeStoreId -cnotmatch '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' -or
        $G2ProbeConversationId -cnotmatch '^[0-9]{1,30}$' -or
        -not [DateTimeOffset]::TryParse($G2ProbeExpiresAt, [ref]$probeExpiry) -or
        $probeExpiry -le [DateTimeOffset]::UtcNow -or
        $probeExpiry -gt [DateTimeOffset]::UtcNow.AddMinutes(30)) {
        throw "G2 Webhook probe requires a complete staging-only target expiring within 30 minutes."
    }
    if ($Deploy -and -not $PreWindowSnapshotFile) {
        throw "G2 Webhook probe deployment requires an exact pre-window restore snapshot."
    }
    $g2ProbeExpected = @{
        G2_WEBHOOK_PROBE_MODE = $G2ProbeMode
        G2_WEBHOOK_PROBE_RUN_ID = $G2ProbeRunId
        G2_WEBHOOK_PROBE_STORE_ID = $G2ProbeStoreId
        G2_WEBHOOK_PROBE_CONVERSATION_ID = $G2ProbeConversationId
        G2_WEBHOOK_PROBE_EXPIRES_AT = $G2ProbeExpiresAt
    }
}
elseif ($G2ProbeMode -or $G2ProbeRunId -or $G2ProbeStoreId -or $G2ProbeConversationId -or $G2ProbeExpiresAt) {
    throw "G2 Webhook probe target requires explicit probe mode."
}
if ($EnableTikTokManualSend) {
    $storeIdsValid = $false
    if ($AllowedTikTokStoreIds) {
        $storeIds = @($AllowedTikTokStoreIds.Split(','))
        $storeIdsValid = $AllowedTikTokStoreIds.Length -le 4096 -and
            @($storeIds | Where-Object { $_ -cnotmatch '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' }).Count -eq 0 -and
            @($storeIds | Sort-Object -Unique).Count -eq $storeIds.Count
    }
    if (-not $EnableTikTokWebhookRead -or $EnableG5SSELoadTest -or
        ([bool]$AllowedTikTokConversationId -eq [bool]$AllowedTikTokStoreIds) -or
        ($AllowedTikTokConversationId -and $AllowedTikTokConversationId -cnotmatch '^[0-9]{1,30}$') -or
        ($AllowedTikTokStoreIds -and -not $storeIdsValid)) {
        throw "Staging manual send requires Webhook read mode and exactly one reviewed conversation or store list."
    }
}
elseif ($AllowedTikTokConversationId -or $AllowedTikTokStoreIds) {
    throw "A manual send target requires explicit manual send mode."
}
if ($EnableWorkspaceTranslation -and $EnableG5SSELoadTest) {
    throw "Workspace translation and G5 SSE modes cannot be combined."
}
$BackendImage = Assert-ImmutableImage -Name "BackendImage" -Reference $BackendImage -Repository "ghcr.io/cp11-gh/crm-backend"
$FrontendImage = Assert-ImmutableImage -Name "FrontendImage" -Reference $FrontendImage -Repository "ghcr.io/cp11-gh/crm-frontend"
$RetrievalModelImage = Assert-ImmutableImage -Name "RetrievalModelImage" -Reference $RetrievalModelImage `
    -Repository "ghcr.io/cp11-gh/crm-retrieval-model-service"
if ($EnableDocumentIngestion) {
    $DocumentParserImage = Assert-ImmutableImage -Name "DocumentParserImage" -Reference $DocumentParserImage `
        -Repository "ghcr.io/cp11-gh/crm-document-parser"
}
elseif ($DocumentParserImage) {
    throw "DocumentParserImage requires EnableDocumentIngestion."
}

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
$mineruAssetDir = ""
if ($EnableDocumentIngestion) {
    if (-not $environmentValues.ContainsKey("MINERU_ASSET_DIR")) {
        throw "MINERU_ASSET_DIR is required for document ingestion."
    }
    $mineruAssetDir = Assert-ExternalMinerUAssets -Path $environmentValues["MINERU_ASSET_DIR"] `
        -GitCheckoutRoot $gitCheckoutRoot
    if (-not $environmentValues.ContainsKey("RETRIEVAL_MODEL_SERVICE_TOKEN") -or
        $environmentValues["RETRIEVAL_MODEL_SERVICE_TOKEN"].Length -lt 32) {
        throw "Document ingestion requires a valid internal model token."
    }
}
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
$webhookReadOverlay = Join-Path $sourceRoot "compose/docker-compose.rootless-staging-webhook.yml"
$g2ProbeOverlay = Join-Path $sourceRoot "compose/docker-compose.rootless-staging-g2-probe.yml"
$manualSendOverlay = Join-Path $sourceRoot "compose/docker-compose.rootless-staging-manual-send.yml"
$g5SSEOverlay = Join-Path $sourceRoot "compose/docker-compose.rootless-staging-g5-sse.yml"
$translationOverlay = Join-Path $sourceRoot "compose/docker-compose.rootless-staging-translation.yml"
$agentDebugOverlay = Join-Path $sourceRoot "compose/docker-compose.rootless-staging-agent-debug.yml"
if (-not (Test-Path -LiteralPath $egressOverlay -PathType Leaf)) {
    throw "The repository-fixed TikTok egress overlay does not exist."
}
if (-not (Test-Path -LiteralPath $rootlessOverlay -PathType Leaf)) {
    throw "The repository-fixed Rootless staging overlay does not exist."
}
if ($EnableTikTokWebhookRead -and -not (Test-Path -LiteralPath $webhookReadOverlay -PathType Leaf)) {
    throw "The repository-fixed staging Webhook read overlay does not exist."
}
if ($EnableG2WebhookProbe -and -not (Test-Path -LiteralPath $g2ProbeOverlay -PathType Leaf)) {
    throw "The repository-fixed staging G2 probe overlay does not exist."
}
if ($EnableTikTokManualSend -and -not (Test-Path -LiteralPath $manualSendOverlay -PathType Leaf)) {
    throw "The repository-fixed staging manual send overlay does not exist."
}
if ($EnableG5SSELoadTest -and -not (Test-Path -LiteralPath $g5SSEOverlay -PathType Leaf)) {
    throw "The repository-fixed staging G5 SSE overlay does not exist."
}
if ($EnableWorkspaceTranslation -and -not (Test-Path -LiteralPath $translationOverlay -PathType Leaf)) {
    throw "The repository-fixed staging translation overlay does not exist."
}
if ($EnableAgentDebug -and -not (Test-Path -LiteralPath $agentDebugOverlay -PathType Leaf)) {
    throw "The repository-fixed staging Agent debug overlay does not exist."
}

$savedEnvironment = @{}
$deploymentLock = $null
foreach ($name in @($DisabledCapabilityVariables + $G2ProbeVariables + @(
    "BACKEND_IMAGE",
    "FRONTEND_IMAGE",
    "RETRIEVAL_MODEL_ASSET_DIR",
    "RETRIEVAL_MODEL_SERVICE_IMAGE",
    "DOCUMENT_PARSER_IMAGE",
    "MINERU_ASSET_DIR",
    "COMPOSE_PROFILES",
    "TIKTOK_EGRESS_IMAGE",
    "TIKTOK_EGRESS_SECRET_DIR",
    "TLS_CERT_DIR",
    "DOCKER_HOST",
    "DOCKER_CONTEXT",
    "TIKTOK_MESSAGE_WRITE_ALLOWED_CONVERSATION_ID"
    "TIKTOK_MESSAGE_WRITE_ALLOWED_STORE_IDS"
))) {
    $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
}
try {
    # DOCKER_CONTEXT 的优先级高于 DOCKER_HOST，必须在所有 Docker 调用前清空。
    $env:DOCKER_HOST = $DockerHost
    [Environment]::SetEnvironmentVariable("DOCKER_CONTEXT", $null, "Process")
    [Environment]::SetEnvironmentVariable("COMPOSE_PROFILES", $null, "Process")
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
    if ($EnableDocumentIngestion) {
        $composeArguments += @("--profile", "document")
    }
    if ($EnableTikTokWebhookRead) {
        $composeArguments += @("-f", (Resolve-Path -LiteralPath $webhookReadOverlay).Path)
    }
    if ($EnableG2WebhookProbe) {
        $composeArguments += @("-f", (Resolve-Path -LiteralPath $g2ProbeOverlay).Path)
    }
    if ($EnableTikTokManualSend) {
        $composeArguments += @("-f", (Resolve-Path -LiteralPath $manualSendOverlay).Path)
    }
    if ($EnableG5SSELoadTest) {
        $composeArguments += @("-f", (Resolve-Path -LiteralPath $g5SSEOverlay).Path)
    }
    if ($EnableWorkspaceTranslation) {
        $composeArguments += @("-f", (Resolve-Path -LiteralPath $translationOverlay).Path)
    }
    if ($EnableAgentDebug) {
        $composeArguments += @("-f", (Resolve-Path -LiteralPath $agentDebugOverlay).Path)
    }
    Set-DisabledCapabilities
    [Environment]::SetEnvironmentVariable("TIKTOK_MESSAGE_WRITE_ALLOWED_CONVERSATION_ID", $AllowedTikTokConversationId, "Process")
    [Environment]::SetEnvironmentVariable("TIKTOK_MESSAGE_WRITE_ALLOWED_STORE_IDS", $AllowedTikTokStoreIds, "Process")
    foreach ($name in $G2ProbeVariables) {
        [Environment]::SetEnvironmentVariable($name, $g2ProbeExpected[$name], "Process")
    }
    $env:BACKEND_IMAGE = $BackendImage
    $env:FRONTEND_IMAGE = $FrontendImage
    $env:RETRIEVAL_MODEL_ASSET_DIR = $modelAssetDir
    $env:RETRIEVAL_MODEL_SERVICE_IMAGE = $configuredRetrievalModelImage
    if ($EnableDocumentIngestion) {
        $env:DOCUMENT_PARSER_IMAGE = $DocumentParserImage
        $env:MINERU_ASSET_DIR = $mineruAssetDir
    }
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
    if ($EnableDocumentIngestion) { $expectedImages["document-parser"] = $DocumentParserImage }
    Assert-ProductionComposeContract -Config $config -ExpectedImages $expectedImages `
        -ExpectedModelAssetDir $modelAssetDir -ExpectedEgressSecretDir $egressSecretDir `
        -ExpectedMinerUAssetDir $mineruAssetDir -EnableDocumentIngestion:$EnableDocumentIngestion `
        -EnableTikTokWebhookRead:$EnableTikTokWebhookRead -EnableG5SSELoadTest:$EnableG5SSELoadTest `
        -EnableTikTokManualSend:$EnableTikTokManualSend -AllowedTikTokConversationId $AllowedTikTokConversationId `
        -AllowedTikTokStoreIds $AllowedTikTokStoreIds `
        -EnableWorkspaceTranslation:$EnableWorkspaceTranslation -EnableAgentDebug:$EnableAgentDebug `
        -G2ProbeExpected $g2ProbeExpected

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
    $lockRoot = if ($IsWindows) { [System.IO.Path]::GetTempPath() } else { '/run/user/1004' }
    $lockPath = Join-Path $lockRoot 'crm-staging-deploy.lock'
    try {
        $deploymentLock = [System.IO.File]::Open(
            $lockPath, [System.IO.FileMode]::OpenOrCreate,
            [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None
        )
    }
    catch [System.IO.IOException] { throw 'Another staging deployment holds the deployment lock.' }
    if ($PreWindowSnapshotFile) {
        try { $snapshot = Get-Content -LiteralPath $PreWindowSnapshotFile -Raw | ConvertFrom-Json -ErrorAction Stop }
        catch { throw 'The G5 pre-window snapshot cannot be read under the deployment lock.' }
        $snapshotStoreProperty = $snapshot.PSObject.Properties['allowed_store_ids']
        $snapshotStoreIds = if ($null -eq $snapshotStoreProperty) { '' } else { [string]$snapshotStoreProperty.Value }
        $snapshotArgs = @{
            SnapshotFile = $PreWindowSnapshotFile
            CandidateBackendImage = [string]$snapshot.images.candidate_backend
            FrontendImage = [string]$snapshot.images.candidate_frontend
            RetrievalModelImage = [string]$snapshot.images.candidate_retrieval
            PreviousBackendImage = [string]$snapshot.images.previous_backend
            PreviousFrontendImage = [string]$snapshot.images.previous_frontend
            PreviousRetrievalModelImage = [string]$snapshot.images.previous_retrieval
        }
        if ($EnableG5SSELoadTest -or $EnableG2WebhookProbe) {
            if ($BackendImage -cne $snapshotArgs.CandidateBackendImage -or
                $FrontendImage -cne $snapshotArgs.FrontendImage -or
                $RetrievalModelImage -cne $snapshotArgs.RetrievalModelImage) {
                throw 'G5 deploy images differ from the pre-window snapshot.'
            }
            & (Join-Path $PSScriptRoot 'Assert-StagingG5RestoreSnapshot.ps1') `
                -Mode VerifyUnchanged @snapshotArgs | Out-Null
        }
        else {
            if ($BackendImage -cne $snapshotArgs.PreviousBackendImage -or
                $FrontendImage -cne $snapshotArgs.PreviousFrontendImage -or
                $RetrievalModelImage -cne $snapshotArgs.PreviousRetrievalModelImage) {
                throw 'Restore images differ from the pre-window snapshot.'
            }
            $restoreMode = if ($EnableTikTokManualSend) { 'RestoreManualSend' }
                elseif ($EnableTikTokWebhookRead -and $EnableWorkspaceTranslation) { 'RestoreReadAndTranslation' }
                else { 'RestoreDefault' }
            $translation = & (Join-Path $PSScriptRoot 'Assert-StagingG5RestoreSnapshot.ps1') `
                -Mode VerifyRestore -RestoreMode $restoreMode @snapshotArgs
            if ($translation -cne ([string][bool]$EnableWorkspaceTranslation).ToLowerInvariant() -or
                $AllowedTikTokConversationId -cne [string]$snapshot.allowed_conversation_id -or
                $AllowedTikTokStoreIds -cne $snapshotStoreIds) {
                throw 'Restore capabilities differ from the pre-window snapshot.'
            }
            & (Join-Path $PSScriptRoot 'Assert-StagingG5RestoreSnapshot.ps1') `
                -Mode VerifyRecoverableCurrent @snapshotArgs | Out-Null
        }
        if (-not $?) { throw 'The staging runtime changed before the locked G5 operation.' }
    }
    # 同一 backend 摘要被多个服务共享，只拉取一次；逐镜像限次重试避免慢链路并发传输放大临时断连。
    $pullServices = @("tiktok-egress", "frontend", "retrieval-model-service")
    if ($EnableDocumentIngestion) { $pullServices += "document-parser" }
    Invoke-ComposePullsWithRetry -Command $compose -Arguments $composeArguments -Services $pullServices
    if ($EnableDocumentIngestion) {
        & $compose.Executable run --rm --network none --read-only `
            --mount "type=bind,src=$mineruAssetDir,dst=/opt/mineru,readonly" `
            --entrypoint mineru-kit $DocumentParserImage models verify --tier basic --small-backend onnx
        if ($LASTEXITCODE -ne 0) { throw "MinerU Basic ONNX local model verification failed." }
    }
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
    $applicationServices = @("backend", "worker", "jobs", "agent-worker", "frontend", "proxy",
        "retrieval-model-service")
    if ($EnableDocumentIngestion) { $applicationServices += "document-parser" }
    Invoke-Compose -Command $compose -Arguments ($composeArguments + @(
        "up", "-d", "--no-build", "--wait", "--wait-timeout", "600"
    ) + $applicationServices)
    # backend 重建会更换容器 IP；重启内层 Nginx，避免继续连接旧上游并等待其恢复健康。
    Invoke-Compose -Command $compose -Arguments ($composeArguments + @("restart", "proxy"))
    Invoke-Compose -Command $compose -Arguments ($composeArguments + @(
        "up", "-d", "--no-build", "--wait", "--wait-timeout", "600", "proxy"
    ))

    Assert-RunningStagingMode -Command $compose -Arguments $composeArguments -ExpectedBackendImage $BackendImage `
        -EnableTikTokWebhookRead:$EnableTikTokWebhookRead -EnableG5SSELoadTest:$EnableG5SSELoadTest `
        -EnableTikTokManualSend:$EnableTikTokManualSend -AllowedTikTokConversationId $AllowedTikTokConversationId `
        -AllowedTikTokStoreIds $AllowedTikTokStoreIds `
        -EnableWorkspaceTranslation:$EnableWorkspaceTranslation -EnableAgentDebug:$EnableAgentDebug `
        -G2ProbeExpected $g2ProbeExpected
    if ($EnableDocumentIngestion) {
        Assert-RunningDocumentWorker -Command $compose -Arguments $composeArguments `
            -ExpectedImage $DocumentParserImage -ExpectedToken $environmentValues["RETRIEVAL_MODEL_SERVICE_TOKEN"]
    }

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
    if ($null -ne $deploymentLock) { $deploymentLock.Dispose() }
    foreach ($name in $savedEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], "Process")
    }
}
