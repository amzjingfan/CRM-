[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Environment,
    [Parameter(Mandatory = $true)][string]$ConfirmTarget,
    [Parameter(Mandatory = $true)][string]$DockerHost,
    [Parameter(Mandatory = $true)][string]$EvidenceFile,
    [Parameter(Mandatory = $true)][string]$CandidateBackendImage,
    [Parameter(Mandatory = $true)][string]$CandidateFrontendImage,
    [Parameter(Mandatory = $true)][string]$CandidateRetrievalModelImage,
    [Parameter(Mandatory = $true)][string]$PreviousBackendImage,
    [Parameter(Mandatory = $true)][string]$PreviousFrontendImage,
    [Parameter(Mandatory = $true)][string]$PreviousRetrievalModelImage,
    [string]$ResumableOciScript
)

$ErrorActionPreference = "Stop"
if ($Environment -cne "staging" -or $ConfirmTarget -cne "staging") {
    throw "Image prefetch is staging-only."
}
if ($DockerHost -cne "unix:///run/user/1004/docker.sock") {
    throw "Image prefetch requires the crmdeploy Rootless Docker socket."
}

$images = @(
    @{ repository = "ghcr.io/cp11-gh/crm-backend"; reference = $CandidateBackendImage },
    @{ repository = "ghcr.io/cp11-gh/crm-frontend"; reference = $CandidateFrontendImage },
    @{ repository = "ghcr.io/cp11-gh/crm-retrieval-model-service"; reference = $CandidateRetrievalModelImage },
    @{ repository = "ghcr.io/cp11-gh/crm-backend"; reference = $PreviousBackendImage },
    @{ repository = "ghcr.io/cp11-gh/crm-frontend"; reference = $PreviousFrontendImage },
    @{ repository = "ghcr.io/cp11-gh/crm-retrieval-model-service"; reference = $PreviousRetrievalModelImage }
)
foreach ($image in $images) {
    $expected = "^$([regex]::Escape($image.repository))@sha256:[0-9a-f]{64}$"
    if ($image.reference -cnotmatch $expected) {
        throw "All staging images must use the reviewed GHCR repository and an immutable lowercase SHA-256 digest."
    }
}
for ($index = 0; $index -lt 3; $index++) {
    if ($images[$index].reference -ceq $images[$index + 3].reference) {
        throw "Candidate and previous image digests must differ."
    }
}
if (Test-Path -LiteralPath $EvidenceFile) {
    throw "Image prefetch evidence path already exists; use a unique path for each attempt."
}

function Test-LocalImageDigest {
    param([Parameter(Mandatory = $true)][string]$Reference)

    $digestJson = & docker image inspect --format '{{json .RepoDigests}}' $Reference 2>$null
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace([string]$digestJson)) {
        return $false
    }
    $repoDigests = @($digestJson | ConvertFrom-Json)
    return ($repoDigests -ccontains $Reference)
}

$savedDockerHost = [Environment]::GetEnvironmentVariable("DOCKER_HOST", "Process")
$savedDockerContext = [Environment]::GetEnvironmentVariable("DOCKER_CONTEXT", "Process")
try {
    $env:DOCKER_HOST = $DockerHost
    [Environment]::SetEnvironmentVariable("DOCKER_CONTEXT", $null, "Process")
    for ($index = 0; $index -lt $images.Count; $index++) {
        $image = $images[$index]
        Write-Output "Checking immutable staging image $($index + 1)/$($images.Count): $($image.reference)"
        if (Test-LocalImageDigest -Reference $image.reference) {
            Write-Output "Exact image digest is already available locally."
            continue
        }
        if ($index -in @(2, 5) -and -not [string]::IsNullOrWhiteSpace($ResumableOciScript)) {
            if (-not (Test-Path -LiteralPath $ResumableOciScript -PathType Leaf)) {
                throw "Verified resumable OCI source is missing."
            }
            if ([string]::IsNullOrWhiteSpace($env:DOCKER_CONFIG)) {
                throw "GHCR Docker credentials are unavailable for resumable OCI transfer."
            }
            Write-Output "Fetching immutable retrieval image $($index + 1)/$($images.Count) through verified resumable OCI ranges."
            & python3 -u $ResumableOciScript `
                --image $image.reference `
                --docker-config (Join-Path $env:DOCKER_CONFIG 'config.json') `
                --cache-dir '/home/crmdeploy/.cache/crm-ghcr-prefetch' `
                --ctr-socket '/run/user/1004/docker/containerd/containerd.sock' `
                --workers 8
            if ($LASTEXITCODE -ne 0 -or -not (Test-LocalImageDigest -Reference $image.reference)) {
                throw "Verified resumable OCI import failed for image $($index + 1)/$($images.Count): $($image.reference)"
            }
            Write-Output "Exact imported retrieval image digest verified."
            continue
        }
        for ($attempt = 1; $attempt -le 3; $attempt++) {
            Write-Output "Pulling immutable staging image $($index + 1)/$($images.Count), attempt $attempt/3."
            & docker pull $image.reference | Out-Null
            $pullExit = $LASTEXITCODE
            if ($pullExit -eq 0) {
                if (-not (Test-LocalImageDigest -Reference $image.reference)) {
                    throw "Pulled staging image digest does not match the requested reference."
                }
                break
            }
            if (Test-LocalImageDigest -Reference $image.reference) {
                break
            }
            if ($attempt -eq 3) {
                throw "Immutable staging image pull failed after three attempts for image $($index + 1)/$($images.Count): $($image.reference)"
            }
            Write-Output "Immutable pull failed; retrying the same digest."
            Start-Sleep -Seconds (2 * $attempt)
        }
        Write-Output "Exact pulled image digest verified."
    }
    $evidence = [ordered]@{
        evidence_type = "staging_rollback_image_prefetch"
        status = "passed"
        environment = "staging"
        image_count = $images.Count
        image_references = @($images | ForEach-Object { $_.reference })
        service_mutation = $false
        production_release = $false
        observed_at_utc = [DateTime]::UtcNow.ToString("o")
    }
    $parent = Split-Path -Parent $EvidenceFile
    if (-not [string]::IsNullOrWhiteSpace($parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    $evidence | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $EvidenceFile -Encoding utf8
    Write-Output "Six immutable staging images are available locally; no services were changed."
}
finally {
    [Environment]::SetEnvironmentVariable("DOCKER_HOST", $savedDockerHost, "Process")
    [Environment]::SetEnvironmentVariable("DOCKER_CONTEXT", $savedDockerContext, "Process")
}
