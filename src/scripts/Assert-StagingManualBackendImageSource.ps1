#requires -Version 7.0

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('CheckOnly', 'DeployG5', 'ReconcileFixture', 'RestoreDefault', 'RestoreReadAndTranslation', 'RestoreManualSend', 'RollbackPrevious')]
    [string]$Mode,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{40}$')][string]$SourceSha,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{40}$')][string]$ImageRevisionSha,
    [Parameter(Mandatory = $true)][string]$Token
)

if ($ImageRevisionSha -ceq $SourceSha) { return }
if ($Mode -cnotin @('CheckOnly', 'DeployG5', 'ReconcileFixture',
        'RestoreDefault', 'RestoreReadAndTranslation', 'RestoreManualSend')) {
    throw 'A recovery image must match its reviewed source commit.'
}

# 证据提交可推进 main；只有镜像提交是祖先且全部后端构建输入未变时才允许复用。
try {
    $headers = @{ Authorization = "Bearer $Token"; Accept = 'application/vnd.github+json' }
    $compare = Invoke-RestMethod `
        -Uri "https://api.github.com/repos/CP11-gh/CRM/compare/${ImageRevisionSha}...${SourceSha}" `
        -Headers $headers
    if ($compare.status -cne 'ahead' -or [int]$compare.behind_by -ne 0 -or [int]$compare.ahead_by -lt 1) {
        throw 'The image commit is not an ancestor of current main.'
    }
    $identities = @()
    foreach ($sha in @($ImageRevisionSha, $SourceSha)) {
        $tree = Invoke-RestMethod -Uri "https://api.github.com/repos/CP11-gh/CRM/git/trees/${sha}?recursive=1" `
            -Headers $headers
        if ($tree.truncated -ne $false) { throw 'The Git tree response is incomplete.' }
        $parts = @()
        foreach ($part in @(
            @{ path = 'src/backend'; type = 'tree' },
            @{ path = 'src/docker/Dockerfile.backend'; type = 'blob' }
        )) {
            $entries = @($tree.tree | Where-Object { $_.path -ceq $part.path -and $_.type -ceq $part.type })
            if ($entries.Count -ne 1 -or $entries[0].sha -cnotmatch '^[0-9a-f]{40}$') {
                throw 'A backend build input is missing from the Git tree.'
            }
            $parts += [string]$entries[0].sha
        }
        $identities += [pscustomobject]@{ backend = $parts[0]; dockerfile = $parts[1] }
    }
    if ($identities[0].backend -cne $identities[1].backend -or
        $identities[0].dockerfile -cne $identities[1].dockerfile) {
        throw 'Backend build inputs differ from the candidate image commit.'
    }
}
catch {
    throw 'The candidate backend revision could not be verified against current main.'
}
