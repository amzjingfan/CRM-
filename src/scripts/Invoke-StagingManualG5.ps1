#requires -Version 7.0

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('CheckOnly', 'DeployG5', 'RestoreDefault', 'RollbackPrevious')]
    [string]$Mode,
    [Parameter(Mandatory = $true)][string]$SourceSha,
    [Parameter(Mandatory = $true)][string]$CandidateBackendImage,
    [Parameter(Mandatory = $true)][string]$FrontendImage,
    [Parameter(Mandatory = $true)][string]$RetrievalModelImage,
    [Parameter(Mandatory = $true)][string]$PreviousBackendImage,
    [Parameter(Mandatory = $true)][string]$PreviousFrontendImage,
    [Parameter(Mandatory = $true)][string]$PreviousRetrievalModelImage,
    [Parameter(Mandatory = $true)][string]$ConfirmTarget,
    [Parameter(Mandatory = $true)][string]$EvidenceDirectory,
    [string]$ArchivePath,
    [string]$ArchiveSha256
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$dockerHost = 'unix:///run/user/1004/docker.sock'
$environmentFile = '/home/crmdeploy/config/crm-staging.env'
$baseUrl = 'https://staging.overselfx.com'
$evidenceRoot = '/home/crmdeploy/.cache/crm-g5-manual'

function Assert-Image([string]$Name, [string]$Reference, [string]$Repository) {
    if ($Reference -cnotmatch "^$([regex]::Escape($Repository))@sha256:[0-9a-f]{64}$") {
        throw "$Name must use an immutable digest from the reviewed repository."
    }
}

function Assert-LocalImage([string]$Reference) {
    $raw = & docker image inspect $Reference 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'A reviewed rollback image is absent from Rootless Docker.' }
    $images = @(($raw -join "`n") | ConvertFrom-Json)
    if ($images.Count -ne 1 -or @($images[0].RepoDigests) -cnotcontains $Reference) {
        throw 'A local image does not match its immutable repository digest.'
    }
    return $images[0]
}

if ($ConfirmTarget -cne 'staging') { throw 'ConfirmTarget must equal staging.' }
if ($SourceSha -cnotmatch '^[0-9a-f]{40}$') { throw 'Source SHA must be a full lowercase Git commit.' }
Assert-Image 'CandidateBackendImage' $CandidateBackendImage 'ghcr.io/cp11-gh/crm-backend'
Assert-Image 'FrontendImage' $FrontendImage 'ghcr.io/cp11-gh/crm-frontend'
Assert-Image 'RetrievalModelImage' $RetrievalModelImage 'ghcr.io/cp11-gh/crm-retrieval-model-service'
Assert-Image 'PreviousBackendImage' $PreviousBackendImage 'ghcr.io/cp11-gh/crm-backend'
Assert-Image 'PreviousFrontendImage' $PreviousFrontendImage 'ghcr.io/cp11-gh/crm-frontend'
Assert-Image 'PreviousRetrievalModelImage' $PreviousRetrievalModelImage 'ghcr.io/cp11-gh/crm-retrieval-model-service'
if ($CandidateBackendImage -ceq $PreviousBackendImage) {
    throw 'The candidate backend must differ from the previous backend.'
}
if ([bool]$ArchivePath -ne [bool]$ArchiveSha256 -or
    ($ArchiveSha256 -and $ArchiveSha256 -cnotmatch '^[0-9a-f]{64}$')) {
    throw 'Archive SHA must be a full lowercase SHA-256 paired with ArchivePath.'
}
if ($IsWindows -or (Get-Content /proc/sys/kernel/ostype -ErrorAction SilentlyContinue) -cne 'Linux') {
    throw 'The manual gate requires the staging Linux host.'
}
$uid = (& id -u).Trim()
if ($LASTEXITCODE -ne 0 -or $uid -cne '1004') { throw 'The manual gate requires crmdeploy UID 1004.' }
$reviewRoot = (Resolve-Path -LiteralPath (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))).Path
if ($reviewRoot -cnotmatch '^/home/crmdeploy/src/crm-reviewed-source-[a-z0-9-]+$') {
    throw 'The reviewed source must be in a persistent crmdeploy staging directory.'
}
foreach ($path in @('/home/crmdeploy/src', $reviewRoot)) {
    if (((Get-Item -LiteralPath $path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'The reviewed source path cannot contain a symlink.'
    }
}
if ($ArchivePath) {
    if ($ArchivePath -cnotmatch '^/home/crmdeploy/src/[a-z0-9._-]+\.tar$' -or
        -not (Test-Path -LiteralPath $ArchivePath -PathType Leaf) -or
        ((Get-Item -LiteralPath $ArchivePath -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'The reviewed source archive is unavailable or outside the staging source directory.'
    }
    if ((Get-FileHash -LiteralPath $ArchivePath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $ArchiveSha256) {
        throw 'The reviewed source archive SHA-256 differs from transfer evidence.'
    }
    & python3 (Join-Path $PSScriptRoot 'verify_staging_source_archive.py') `
        --archive $ArchivePath --source $reviewRoot --sha256 $ArchiveSha256
    if ($LASTEXITCODE -ne 0) {
        throw 'The staging source files differ from the reviewed archive SHA-256.'
    }
}
else {
    $checkoutRoot = (& git -C $reviewRoot rev-parse --show-toplevel).Trim()
    $head = (& git -C $reviewRoot rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or $checkoutRoot -cne $reviewRoot -or $head -cne $SourceSha) {
        throw 'The staging checkout does not match the pinned source SHA.'
    }
    $dirtyFiles = @(& git -C $reviewRoot status --porcelain --untracked-files=all)
    if ($LASTEXITCODE -ne 0 -or $dirtyFiles.Count -ne 0) {
        throw 'The reviewed source checkout contains local changes or untracked files.'
    }
    $remote = (& git -C $reviewRoot remote get-url origin).Trim()
    if ($LASTEXITCODE -ne 0 -or $remote -cnotin @(
        'https://github.com/CP11-gh/CRM.git',
        'ssh://git@ssh.github.com:443/CP11-gh/CRM.git'
    )) { throw 'The staging source origin is not the reviewed repository.' }
}
$token = [Environment]::GetEnvironmentVariable('GH_TOKEN', 'Process')
if ([string]::IsNullOrWhiteSpace($token) -and $null -ne (Get-Command gh -ErrorAction SilentlyContinue)) {
    $token = (& gh auth token).Trim()
    if ($LASTEXITCODE -ne 0) { $token = $null }
}
if ([string]::IsNullOrWhiteSpace($token)) { throw 'GitHub read credentials are unavailable.' }
try {
    $commit = Invoke-RestMethod -Uri 'https://api.github.com/repos/CP11-gh/CRM/commits/main' `
        -Headers @{ Authorization = "Bearer $token"; Accept = 'application/vnd.github+json' }
    if ([string]$commit.sha -cne $SourceSha) {
        throw 'The reviewed source is not the current remote main commit.'
    }
}
catch {
    throw 'GitHub main verification failed or the reviewed SHA has changed.'
}
if ($EvidenceDirectory -cnotmatch '^/home/crmdeploy/\.cache/crm-g5-manual/[a-z0-9-]+$') {
    throw 'EvidenceDirectory must be a unique private staging path.'
}
$savedDockerHost = [Environment]::GetEnvironmentVariable('DOCKER_HOST', 'Process')
$savedDockerContext = [Environment]::GetEnvironmentVariable('DOCKER_CONTEXT', 'Process')
$savedDockerConfig = [Environment]::GetEnvironmentVariable('DOCKER_CONFIG', 'Process')
$env:DOCKER_HOST = $dockerHost
[Environment]::SetEnvironmentVariable('DOCKER_CONTEXT', $null, 'Process')
try {
    $dockerInfo = & docker info --format '{{json .SecurityOptions}}'
    if ($LASTEXITCODE -ne 0 -or $dockerInfo -notmatch 'rootless') {
        throw 'The crmdeploy Rootless Docker daemon is unavailable.'
    }
    if (-not (Test-Path -LiteralPath $environmentFile -PathType Leaf)) {
        throw 'The private staging environment file is missing.'
    }
    if ($Mode -ceq 'CheckOnly') {
        Write-Output "Manual G5 source and Rootless target ready; source_sha=$SourceSha; service_mutation=false."
        return
    }
    if (Test-Path -LiteralPath $EvidenceDirectory) {
        throw 'The evidence directory already exists; use a unique path for this attempt.'
    }
    foreach ($path in @('/home/crmdeploy', '/home/crmdeploy/.cache')) {
        $item = Get-Item -LiteralPath $path -Force
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'The private evidence path cannot contain a symlink.'
        }
    }
    if (-not (Test-Path -LiteralPath $evidenceRoot -PathType Container)) {
        New-Item -ItemType Directory -Path $evidenceRoot | Out-Null
        & chmod 0700 $evidenceRoot
        if ($LASTEXITCODE -ne 0) { throw 'Unable to protect the new evidence root.' }
    }
    if (((Get-Item -LiteralPath $evidenceRoot -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'The private evidence root cannot be a symlink.'
    }
    $rootMode = (& stat -c '%a:%u' $evidenceRoot).Trim()
    if ($LASTEXITCODE -ne 0 -or $rootMode -cne '700:1004') {
        throw 'The existing evidence root must be private and owned by crmdeploy.'
    }
    New-Item -ItemType Directory -Path $EvidenceDirectory | Out-Null
    & chmod 0700 $EvidenceDirectory
    if ($LASTEXITCODE -ne 0) { throw 'Unable to protect the evidence directory.' }

    $authDirectory = Join-Path '/run/user/1004' "crm-g5-ghcr-$([guid]::NewGuid().ToString('N'))"
    New-Item -ItemType Directory -Path $authDirectory | Out-Null
    & chmod 0700 $authDirectory
    if ($LASTEXITCODE -ne 0) { throw 'Unable to protect temporary GHCR credentials.' }
    $env:DOCKER_CONFIG = $authDirectory
    try {
        $token | & docker login ghcr.io --username CP11-gh --password-stdin | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'GHCR read login failed.' }

        if ($Mode -ceq 'DeployG5') {
            $configPath = '/home/crmdeploy/.config/docker/daemon.json'
            $backupPath = Join-Path $EvidenceDirectory 'docker-pull-mode.backup'
            try {
                & (Join-Path $PSScriptRoot 'Set-StagingDockerPullMode.ps1') -Mode Enter `
                    -DockerHost $dockerHost -ConfigPath $configPath -BackupPath $backupPath
                & (Join-Path $PSScriptRoot 'Prepare-StagingRollbackImages.ps1') `
                    -Environment staging -ConfirmTarget staging -DockerHost $dockerHost `
                    -EvidenceFile (Join-Path $EvidenceDirectory 'prefetch.json') `
                    -CandidateBackendImage $CandidateBackendImage -CandidateFrontendImage $FrontendImage `
                    -CandidateRetrievalModelImage $RetrievalModelImage `
                    -PreviousBackendImage $PreviousBackendImage -PreviousFrontendImage $PreviousFrontendImage `
                    -PreviousRetrievalModelImage $PreviousRetrievalModelImage `
                    -ResumableOciScript (Join-Path $PSScriptRoot 'prefetch_ghcr_oci.py')
            }
            finally {
                if (Test-Path -LiteralPath $backupPath -PathType Leaf) {
                    & (Join-Path $PSScriptRoot 'Set-StagingDockerPullMode.ps1') -Mode Restore `
                        -DockerHost $dockerHost -ConfigPath $configPath -BackupPath $backupPath
                }
            }
            $candidate = Assert-LocalImage $CandidateBackendImage
            if ($candidate.Config.Labels.'org.opencontainers.image.revision' -cne $SourceSha) {
                throw 'The candidate backend image revision differs from the reviewed source.'
            }
        }
        else {
            $targetImages = if ($Mode -ceq 'RollbackPrevious') {
                @($CandidateBackendImage, $FrontendImage, $RetrievalModelImage,
                    $PreviousBackendImage, $PreviousFrontendImage, $PreviousRetrievalModelImage)
            } else {
                @($CandidateBackendImage, $FrontendImage, $RetrievalModelImage)
            }
            foreach ($reference in $targetImages) {
                $null = Assert-LocalImage $reference
            }
        }

        if ($Mode -ceq 'RollbackPrevious') {
            $rollback = Join-Path $PSScriptRoot 'Invoke-StagingRollbackDrill.ps1'
            $rollbackParameters = @{
                Environment = 'staging'
                EnvFile = $environmentFile
                CandidateBackendImage = $CandidateBackendImage
                CandidateFrontendImage = $FrontendImage
                CandidateRetrievalModelImage = $RetrievalModelImage
                PreviousBackendImage = $PreviousBackendImage
                PreviousFrontendImage = $PreviousFrontendImage
                PreviousRetrievalModelImage = $PreviousRetrievalModelImage
                BaseUrl = $baseUrl
                ConfirmTarget = 'staging'
                DockerHost = $dockerHost
            }
            & $rollback @rollbackParameters -EvidenceFile (Join-Path $EvidenceDirectory 'validate.json') -ValidateOnly
            & $rollback @rollbackParameters -EvidenceFile (Join-Path $EvidenceDirectory 'deploy.json') -Execute -Confirm:$false
            Write-Output "Manual staging rollback passed; source_sha=$SourceSha; evidence=$EvidenceDirectory; production_release=false."
            return
        }

        $gate = Join-Path $PSScriptRoot 'Test-StagingProductionGates.ps1'
        $common = @{
            Environment = 'staging'
            EnvFile = $environmentFile
            BackendImage = $CandidateBackendImage
            FrontendImage = $FrontendImage
            RetrievalModelImage = $RetrievalModelImage
            BaseUrl = $baseUrl
            ConfirmTarget = 'staging'
            DockerHost = $dockerHost
        }
        if ($Mode -ceq 'DeployG5') { $common.EnableG5SSELoadTest = $true }
        & $gate @common -EvidenceFile (Join-Path $EvidenceDirectory 'validate.json') -ValidateOnly
        & $gate @common -EvidenceFile (Join-Path $EvidenceDirectory 'deploy.json') -Deploy -Confirm:$false
        Write-Output "Manual staging operation passed; mode=$Mode; source_sha=$SourceSha; evidence=$EvidenceDirectory; production_release=false."
    }
    finally {
        & docker logout ghcr.io *> $null
        $configFile = Join-Path $authDirectory 'config.json'
        if (Test-Path -LiteralPath $configFile -PathType Leaf) { Remove-Item -LiteralPath $configFile -Force }
        if (@(Get-ChildItem -LiteralPath $authDirectory -Force).Count -eq 0) {
            Remove-Item -LiteralPath $authDirectory
        }
    }
}
finally {
    $token = $null
    [Environment]::SetEnvironmentVariable('DOCKER_HOST', $savedDockerHost, 'Process')
    [Environment]::SetEnvironmentVariable('DOCKER_CONTEXT', $savedDockerContext, 'Process')
    [Environment]::SetEnvironmentVariable('DOCKER_CONFIG', $savedDockerConfig, 'Process')
}
