#requires -Version 7.0

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Capture', 'VerifyRestore', 'VerifyUnchanged', 'VerifyRecoverableCurrent')][string]$Mode,
    [Parameter(Mandatory = $true)][string]$SnapshotFile,
    [Parameter(Mandatory = $true)][string]$CandidateBackendImage,
    [Parameter(Mandatory = $true)][string]$FrontendImage,
    [Parameter(Mandatory = $true)][string]$RetrievalModelImage,
    [Parameter(Mandatory = $true)][string]$PreviousBackendImage,
    [Parameter(Mandatory = $true)][string]$PreviousFrontendImage,
    [Parameter(Mandatory = $true)][string]$PreviousRetrievalModelImage,
    [string]$RestoreMode
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-RunningConfig([string]$Service, [bool]$AllowStopped = $false) {
    $statusArgument = @(if ($AllowStopped) { '--all' })
    $ids = @(& docker ps @statusArgument --filter 'label=com.docker.compose.project=crm-staging' `
        --filter "label=com.docker.compose.service=$Service" --format '{{.ID}}')
    if ($LASTEXITCODE -ne 0 -or $ids.Count -ne 1 -or $ids[0] -cnotmatch '^[0-9a-f]{12,64}$') {
        throw 'The staging service is not unique or available.'
    }
    $raw = & docker inspect --format '{{json .Config}}' $ids[0]
    if ($LASTEXITCODE -ne 0) { throw 'The pre-window staging config is unavailable.' }
    try { return ($raw -join '') | ConvertFrom-Json -ErrorAction Stop }
    catch { throw 'The pre-window staging config is invalid.' }
}

function Get-Environment([object]$Config) {
    $values = @{}
    foreach ($entry in @($Config.Env)) {
        $text = [string]$entry
        $separator = $text.IndexOf('=')
        if ($separator -le 0) { throw 'The pre-window staging environment is invalid.' }
        $key = $text.Substring(0, $separator)
        if ($values.ContainsKey($key)) { throw 'The pre-window staging environment has duplicate keys.' }
        $values[$key] = $text.Substring($separator + 1)
    }
    return $values
}

function Get-RunningState {
    $backend = Get-RunningConfig 'backend'
    $frontend = Get-RunningConfig 'frontend'
    $retrieval = Get-RunningConfig 'retrieval-model-service'
    if ([string]$backend.Image -cne $PreviousBackendImage -or
        [string]$frontend.Image -cne $PreviousFrontendImage -or
        [string]$retrieval.Image -cne $PreviousRetrievalModelImage) {
        throw 'The previous images do not match the running pre-window services.'
    }
    $environment = Get-Environment $backend
    $manualSend = $environment['REAL_TIKTOK_MESSAGE_WRITE_ENABLED'] -ceq 'true'
    $conversation = [string]$environment['TIKTOK_MESSAGE_WRITE_ALLOWED_CONVERSATION_ID']
    $translation = [string]$environment['WORKSPACE_MESSAGE_TRANSLATION_ENABLED']
    $webhook = [string]$environment['REAL_TIKTOK_WEBHOOK_ENABLED']
    $read = [string]$environment['REAL_TIKTOK_READ_ENABLED']
    $embedding = [string]$environment['EMBEDDING_ENABLED']
    if (-not $embedding) { $embedding = 'false' }
    if ($translation -cnotin @('true', 'false') -or $webhook -cnotin @('true', 'false') -or
        $read -cne $webhook -or
        $embedding -cne 'false' -or
        ($manualSend -and $conversation -cnotmatch '^[0-9]{1,30}$') -or
        (-not $manualSend -and $conversation) -or
        $environment['LLM_ENABLED'] -cne 'false' -or
        $environment['SSE_LOAD_TEST_ENABLED'] -cne 'false' -or
        $environment['CHAT_QUERY_LIMIT'] -cne '10') {
        throw 'The pre-window staging mode cannot be safely restored.'
    }
    foreach ($disabled in @(
        'ALLOW_MOCK_PLATFORM_ADAPTERS', 'REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED',
        'LLM_LIVE_EVAL', 'AI_TRANSLATION_ENABLED', 'AI_MARKETING_ENABLED', 'AUTO_REPLY_ENABLED'
    )) {
        if ($environment[$disabled] -cne 'false') {
            throw 'The pre-window staging mode has an unsupported capability.'
        }
    }
    return [ordered]@{
        manual_send_enabled = $manualSend
        webhook_read_enabled = ($webhook -ceq 'true')
        allowed_conversation_id = $conversation
        workspace_translation_enabled = ($translation -ceq 'true')
    }
}

function Resolve-RestoreMode([bool]$ManualSend, [bool]$WebhookRead, [bool]$Translation) {
    if ($ManualSend -and $WebhookRead) { return 'RestoreManualSend' }
    if (-not $ManualSend -and $WebhookRead -and $Translation) { return 'RestoreReadAndTranslation' }
    if (-not $ManualSend -and -not $WebhookRead -and -not $Translation) { return 'RestoreDefault' }
    throw 'The pre-window runtime has no reviewed restore mode.'
}

$images = [ordered]@{
    candidate_backend = $CandidateBackendImage
    candidate_frontend = $FrontendImage
    candidate_retrieval = $RetrievalModelImage
    previous_backend = $PreviousBackendImage
    previous_frontend = $PreviousFrontendImage
    previous_retrieval = $PreviousRetrievalModelImage
}

if ($Mode -ceq 'Capture') {
    if ($RestoreMode) { throw 'Capture cannot select a restore mode.' }
    if (Test-Path -LiteralPath $SnapshotFile) { throw 'The pre-window snapshot already exists.' }
    $state = Get-RunningState
    $null = Resolve-RestoreMode $state.manual_send_enabled $state.webhook_read_enabled `
        $state.workspace_translation_enabled
    $snapshot = [ordered]@{ schema_version = 1; images = $images }
    foreach ($key in $state.Keys) { $snapshot[$key] = $state[$key] }
    $snapshot | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $SnapshotFile -Encoding utf8 -NoNewline
    & chmod 0600 $SnapshotFile
    if ($LASTEXITCODE -ne 0) { throw 'The pre-window snapshot cannot be protected.' }
    Write-Output 'pre_window_snapshot_captured'
    return
}

if (-not (Test-Path -LiteralPath $SnapshotFile -PathType Leaf)) {
    throw 'The pre-window snapshot is missing.'
}
try { $snapshot = Get-Content -LiteralPath $SnapshotFile -Raw | ConvertFrom-Json -ErrorAction Stop }
catch { throw 'The pre-window snapshot is invalid.' }
if ($snapshot.schema_version -cne 1 -or
    $snapshot.manual_send_enabled -isnot [bool] -or
    $snapshot.webhook_read_enabled -isnot [bool] -or
    $snapshot.workspace_translation_enabled -isnot [bool] -or
    ($snapshot.manual_send_enabled -and [string]$snapshot.allowed_conversation_id -cnotmatch '^[0-9]{1,30}$') -or
    (-not $snapshot.manual_send_enabled -and [string]$snapshot.allowed_conversation_id)) {
    throw 'The pre-window snapshot has an invalid runtime mode.'
}
foreach ($key in $images.Keys) {
    if ([string]$snapshot.images.$key -cne $images[$key]) {
        throw 'The requested image digests do not match the pre-window snapshot.'
    }
}

if ($Mode -ceq 'VerifyUnchanged') {
    if ($RestoreMode) { throw 'Runtime comparison cannot select a restore mode.' }
    $state = Get-RunningState
    foreach ($key in $state.Keys) {
        if ($snapshot.$key -cne $state[$key]) {
            throw 'The staging runtime changed after the pre-window snapshot.'
        }
    }
    Write-Output 'pre_window_runtime_unchanged'
    return
}

if ($Mode -ceq 'VerifyRecoverableCurrent') {
    if ($RestoreMode) { throw 'Runtime comparison cannot select a restore mode.' }
    $backend = Get-RunningConfig 'backend' $true
    $frontend = Get-RunningConfig 'frontend' $true
    $retrieval = Get-RunningConfig 'retrieval-model-service' $true
    if ([string]$backend.Image -cnotin @($CandidateBackendImage, $PreviousBackendImage) -or
        [string]$frontend.Image -cnotin @($FrontendImage, $PreviousFrontendImage) -or
        [string]$retrieval.Image -cnotin @($RetrievalModelImage, $PreviousRetrievalModelImage)) {
        throw 'The staging runtime contains an image outside this G5 window.'
    }
    $environment = Get-Environment $backend
    $common = @{
        APP_ENV = 'staging'; LLM_ENABLED = 'true'; EMBEDDING_ENABLED = 'true'
        SSE_LOAD_TEST_ENABLED = 'true'; CHAT_QUERY_LIMIT = '60'
        REAL_TIKTOK_READ_ENABLED = 'false'; REAL_TIKTOK_WEBHOOK_ENABLED = 'false'
        REAL_TIKTOK_MESSAGE_WRITE_ENABLED = 'false'
        REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED = 'false'
        WORKSPACE_MESSAGE_TRANSLATION_ENABLED = 'false'
        ALLOW_MOCK_PLATFORM_ADAPTERS = 'false'; LLM_LIVE_EVAL = 'false'
        AI_TRANSLATION_ENABLED = 'false'; AI_MARKETING_ENABLED = 'false'
        AUTO_REPLY_ENABLED = 'false'
    }
    $g5Mode = [string]$backend.Image -ceq $CandidateBackendImage
    if ($g5Mode) {
        foreach ($key in $common.Keys) {
            if ($environment[$key] -cne $common[$key]) { $g5Mode = $false; break }
        }
        if ([string]$environment['TIKTOK_MESSAGE_WRITE_ALLOWED_CONVERSATION_ID']) { $g5Mode = $false }
    }
    $previousMode = [string]$backend.Image -ceq $PreviousBackendImage -and
        $environment['LLM_ENABLED'] -ceq 'false' -and
        $environment['SSE_LOAD_TEST_ENABLED'] -ceq 'false' -and
        $environment['CHAT_QUERY_LIMIT'] -ceq '10' -and
        $environment['REAL_TIKTOK_READ_ENABLED'] -ceq ([string]$snapshot.webhook_read_enabled).ToLowerInvariant() -and
        $environment['REAL_TIKTOK_WEBHOOK_ENABLED'] -ceq ([string]$snapshot.webhook_read_enabled).ToLowerInvariant() -and
        $environment['REAL_TIKTOK_MESSAGE_WRITE_ENABLED'] -ceq ([string]$snapshot.manual_send_enabled).ToLowerInvariant() -and
        [string]$environment['TIKTOK_MESSAGE_WRITE_ALLOWED_CONVERSATION_ID'] -ceq [string]$snapshot.allowed_conversation_id -and
        $environment['WORKSPACE_MESSAGE_TRANSLATION_ENABLED'] -ceq ([string]$snapshot.workspace_translation_enabled).ToLowerInvariant()
    if ($previousMode) {
        $embedding = [string]$environment['EMBEDDING_ENABLED']
        if (-not $embedding) { $embedding = 'false' }
        $previousMode = $embedding -ceq 'false'
        foreach ($key in @('ALLOW_MOCK_PLATFORM_ADAPTERS', 'REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED',
                'LLM_LIVE_EVAL', 'AI_TRANSLATION_ENABLED', 'AI_MARKETING_ENABLED', 'AUTO_REPLY_ENABLED')) {
            if ($environment[$key] -cne 'false') { $previousMode = $false }
        }
    }
    if (-not $g5Mode -and -not $previousMode) {
        throw 'The staging backend mode is outside this G5 window.'
    }
    Write-Output 'g5_window_runtime_recoverable'
    return
}

if ($RestoreMode -cnotin @('RestoreDefault', 'RestoreReadAndTranslation', 'RestoreManualSend')) {
    throw 'A reviewed restore mode is required.'
}
$expectedMode = Resolve-RestoreMode $snapshot.manual_send_enabled $snapshot.webhook_read_enabled `
    $snapshot.workspace_translation_enabled
if ($RestoreMode -cne $expectedMode) {
    throw 'The requested restore mode does not match the pre-window snapshot.'
}
Write-Output ([string]$snapshot.workspace_translation_enabled).ToLowerInvariant()
