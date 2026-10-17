#requires -Version 7.0

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet('ContentCheck', 'ContentPrepare', 'RenewCredentials', 'VectorizeG5')][string]$Mode,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{40}$')][string]$SourceSha,
    [Parameter(Mandatory = $true)][string]$BackendImage,
    [Parameter(Mandatory = $true)][string]$ReviewRoot,
    [Parameter(Mandatory = $true)][string]$EnvironmentFile,
    [Parameter(Mandatory = $true)][string]$DockerHost,
    [Parameter(Mandatory = $true)][string]$EvidenceFile,
    [string]$ConfirmContent,
    [string]$RuntimeBackendSourceSha
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (($Mode -ceq 'ContentPrepare' -and $ConfirmContent -cne 'prepare-50-isolated-g5-messages') -or
    ($Mode -ceq 'RenewCredentials' -and $ConfirmContent -cne 'renew-50-existing-g5-tokens') -or
    ($Mode -ceq 'VectorizeG5' -and $ConfirmContent -cne 'vectorize-one-isolated-g5-faq') -or
    ($Mode -ceq 'ContentCheck' -and $ConfirmContent)) {
    throw 'Exact G5 content confirmation is required only for the selected write mode.'
}
if (($Mode -ceq 'VectorizeG5' -and $RuntimeBackendSourceSha -cnotmatch '^[0-9a-f]{40}$') -or
    ($Mode -cne 'VectorizeG5' -and $RuntimeBackendSourceSha)) {
    throw 'Runtime backend source SHA is required only for exact G5 vectorization.'
}

function Assert-PrivatePath([string]$Path, [bool]$Directory) {
    $item = Get-Item -LiteralPath $Path -Force
    $metadata = (& stat -c '%u:%a' $Path 2>$null).Trim()
    if ($LASTEXITCODE -ne 0 -or $item.LinkType -or $item.PSIsContainer -ne $Directory -or
        $metadata -cnotmatch '^1004:[0-7]{3,4}$' -or
        ([Convert]::ToInt32($metadata.Split(':')[1], 8) -band 63) -ne 0) {
        throw 'A protected staging path is unsafe.'
    }
}

if ($BackendImage -cnotmatch '^ghcr\.io/cp11-gh/crm-backend@sha256:[0-9a-f]{64}$' -or
    $DockerHost -cne 'unix:///run/user/1004/docker.sock' -or
    $EnvironmentFile -cne '/home/crmdeploy/config/crm-staging.env' -or
    $ReviewRoot -cnotmatch '^/home/crmdeploy/src/crm-reviewed-source-[a-z0-9-]+$' -or
    $EvidenceFile -cnotmatch '^/home/crmdeploy/\.cache/crm-g5-manual/[a-z0-9-]+/content\.json$') {
    throw 'Manual G5 content target is invalid.'
}
if ($IsWindows -or (& id -u).Trim() -cne '1004') { throw 'G5 content requires crmdeploy staging Linux.' }

try {
    $image = @((& docker --host $DockerHost image inspect $BackendImage 2>$null) -join "`n" | ConvertFrom-Json)
    $expectedImageRevision = if ($Mode -ceq 'VectorizeG5') { $RuntimeBackendSourceSha } else { $SourceSha }
    if ($LASTEXITCODE -ne 0 -or $image.Count -ne 1 -or
        @($image[0].RepoDigests) -cnotcontains $BackendImage -or
        $image[0].Config.Labels.'org.opencontainers.image.revision' -cne $expectedImageRevision) {
        throw 'The local backend does not match the reviewed source and digest.'
    }
    $containers = @(& docker --host $DockerHost ps --filter 'label=com.docker.compose.project=crm-staging' `
        --filter 'label=com.docker.compose.service=backend' --format '{{.ID}}' 2>$null)
    if ($LASTEXITCODE -ne 0 -or $containers.Count -ne 1) { throw 'Expected one staging backend.' }
    $container = $containers[0]
    $runningImage = (& docker --host $DockerHost inspect --format '{{.Config.Image}}' $container 2>$null).Trim()
    if ($LASTEXITCODE -ne 0 -or $runningImage -cne $BackendImage) {
        throw 'The running backend differs from the reviewed digest.'
    }

    Assert-PrivatePath $EnvironmentFile $false
    $databaseLines = @()
    foreach ($line in Get-Content -LiteralPath $EnvironmentFile -Encoding utf8) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#')) { continue }
        $separator = $trimmed.IndexOf('=')
        if ($separator -gt 0 -and $trimmed.Substring(0, $separator).Trim() -ceq 'DATABASE_URL') {
            $databaseLines += $trimmed.Substring($separator + 1)
        }
    }
    if ($databaseLines.Count -ne 1 -or [string]::IsNullOrWhiteSpace($databaseLines[0])) {
        throw 'Protected staging database target is missing or ambiguous.'
    }
    $databaseSha = [Convert]::ToHexString(
        [Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($databaseLines[0]))
    ).ToLowerInvariant()
    $runningDatabaseSha = (& docker --host $DockerHost exec $container python -B -c `
        'import hashlib, os; print(hashlib.sha256(os.environ["DATABASE_URL"].encode()).hexdigest())' 2>$null).Trim()
    if ($LASTEXITCODE -ne 0 -or $runningDatabaseSha -cne $databaseSha) {
        throw 'Running backend database differs from protected staging configuration.'
    }

    $privateDir = '/home/crmdeploy/.cache/crm-g5-fixtures'
    Assert-PrivatePath '/home/crmdeploy/.cache' $true
    Assert-PrivatePath $privateDir $true
    $items = @(Get-ChildItem -LiteralPath $privateDir -Force)
    & (Join-Path $PSScriptRoot 'Assert-StagingG5PrivateFileSet.ps1') -Mode $Mode `
        -NamesJson (ConvertTo-Json -InputObject @($items | ForEach-Object { $_.Name }) -Compress)
    if (-not $?) { throw 'G5 private fixture files differ from the exact allowed batch.' }
    foreach ($item in $items) { Assert-PrivatePath (Join-Path $privateDir $item.Name) $false }

    $serviceContract = (& docker --host $DockerHost exec $container python -B -c `
        'import inspect; from app.knowledge_base.service import create_entry, set_entry_status; print(int(all("commit" in inspect.signature(fn).parameters for fn in (create_entry, set_entry_status))))' 2>$null).Trim()
    if ($LASTEXITCODE -ne 0 -or $serviceContract -cne '1') { throw 'The running knowledge contract differs.' }
    $runtimeKeySha = (& docker --host $DockerHost exec $container python -B -c `
        'import hashlib; from app.shared.config.settings import get_settings; print(hashlib.sha256(get_settings().jwt_secret_key.encode()).hexdigest())' 2>$null).Trim()
    $runtimeAlgorithm = (& docker --host $DockerHost exec $container python -B -c `
        'from app.shared.config.settings import get_settings; print(get_settings().jwt_algorithm)' 2>$null).Trim()
    if ($LASTEXITCODE -ne 0 -or $runtimeKeySha -cnotmatch '^[0-9a-f]{64}$' -or
        $runtimeAlgorithm -cnotin @('HS256', 'HS384', 'HS512')) {
        throw 'Running signing configuration is unavailable.'
    }

    $source = Join-Path $ReviewRoot 'src/backend'
    if (-not (Test-Path -LiteralPath (Join-Path $source 'scripts/prepare_sse_staging_content.py') -PathType Leaf)) {
        throw 'Reviewed G5 source is missing.'
    }
    $mount = "type=bind,source=$privateDir,target=/opt/crm-g5-credentials"
    if ($Mode -cne 'RenewCredentials') { $mount += ',readonly' }
    $action = switch ($Mode) {
        'ContentPrepare' { '--prepare-content' }
        'RenewCredentials' { '--renew-credentials' }
        'VectorizeG5' { '--vectorize-one' }
        default { '--check-only' }
    }
    $arguments = @(
        '--host', $DockerHost, 'run', '--rm', '--pull=never', '--read-only',
        '--network', "container:$container", '--user', '0:0', '--env-file', $EnvironmentFile,
        '-e', 'APP_ENV=staging', '-e', 'AUTH_COOKIE_SECURE=true',
        '-e', 'LLM_ENABLED=false', '-e', 'LLM_LIVE_EVAL=false',
        '-e', 'REAL_TIKTOK_READ_ENABLED=false', '-e', 'REAL_TIKTOK_WEBHOOK_ENABLED=false',
        '-e', 'REAL_TIKTOK_MESSAGE_WRITE_ENABLED=false', '-e', 'REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED=false',
        '-e', 'AI_TRANSLATION_ENABLED=false', '-e', 'AI_MARKETING_ENABLED=false',
        '-e', 'AUTO_REPLY_ENABLED=false',
        '-e', "EMBEDDING_ENABLED=$(if ($Mode -ceq 'VectorizeG5') { 'true' } else { 'false' })",
        '-e', 'DEEPSEEK_API_KEY=',
        '-e', "EXPECTED_RUNTIME_JWT_SHA256=$runtimeKeySha",
        '-e', "EXPECTED_RUNTIME_JWT_ALGORITHM=$runtimeAlgorithm",
        '-e', 'PYTHONPATH=/opt/crm-g5-source:/app',
        '--workdir', '/opt/crm-g5-source',
        '--mount', "type=bind,source=$source,target=/opt/crm-g5-source,readonly",
        '--mount', $mount, '--entrypoint', 'python', $BackendImage,
        '-B', '-m', 'scripts.prepare_sse_staging_content', $action,
        '--source-credentials-file', '/opt/crm-g5-credentials/g5-38852775454-2.json',
        '--credentials-file', '/opt/crm-g5-credentials/g5-38852775454-3.json',
        '--expected-database-sha256', $databaseSha
    )
    $output = & docker @arguments 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'G5 operation failed or outcome is unknown.' }
    $report = ($output -join "`n") | ConvertFrom-Json -ErrorAction Stop
    $evidence = switch ($Mode) {
        'ContentCheck' {
            if ($report.mode -cne 'check_only' -or $report.fixture_state -cnotin @('original', 'prepared') -or
                $report.credentials_state -cnotin @('original', 'renewed') -or
                $report.matched_sessions -ne 50 -or $report.provider_calls -ne 0 -or $report.database_writes -ne 0 -or
                ($report.credentials_state -ceq 'renewed') -ne (Test-Path -LiteralPath (Join-Path $privateDir 'g5-38852775454-3.json'))) {
                throw 'Read-only G5 result is inconclusive.'
            }
            @{ mode = 'check_only'; fixture_state = $report.fixture_state; knowledge_ready = [bool]$report.knowledge_ready;
                credentials_state = $report.credentials_state; matched_sessions = 50; provider_calls = 0; database_writes = 0 }
        }
        'ContentPrepare' {
            if ($report.mode -cne 'prepare_content' -or $report.updated_sessions -ne 50 -or
                $report.synthetic_faq -ne 1 -or $report.provider_calls -ne 0) {
                throw 'G5 content preparation outcome is inconclusive.'
            }
            @{ mode = 'prepare_content'; updated_sessions = 50; synthetic_faq = 1; provider_calls = 0 }
        }
        'RenewCredentials' {
            if ($report.mode -cne 'renew_credentials' -or $report.rotated_tokens -ne 50 -or
                $report.provider_calls -ne 0 -or $report.database_writes -ne 0) {
                throw 'G5 credential renewal outcome is inconclusive.'
            }
            Assert-PrivatePath (Join-Path $privateDir 'g5-38852775454-3.json') $false
            @{ mode = 'renew_credentials'; rotated_tokens = 50; provider_calls = 0; database_writes = 0 }
        }
        'VectorizeG5' {
            if ($report.mode -cne 'vectorize_one' -or $report.matched_sessions -ne 50 -or
                $report.synthetic_faq -ne 1 -or $report.local_embedding_documents -ne 1 -or
                $report.deepseek_calls -ne 0 -or $report.knowledge_ready -ne $true) {
                throw 'G5 vector outcome is inconclusive.'
            }
            @{ mode = 'vectorize_one'; matched_sessions = 50; synthetic_faq = 1;
                local_embedding_documents = 1; deepseek_calls = 0; knowledge_ready = $true }
        }
    }
    $evidence | ConvertTo-Json -Compress | Set-Content -LiteralPath $EvidenceFile -Encoding utf8NoBOM
    & chmod 0600 $EvidenceFile
    if ($LASTEXITCODE -ne 0) { throw 'Unable to protect G5 evidence.' }
    Write-Output "Manual G5 content mode=$Mode verified; evidence=$EvidenceFile."
}
catch {
    throw 'Manual G5 content failed or outcome is unknown; retain private files and reconcile read-only before retry.'
}
