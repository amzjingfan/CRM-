[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet('Enter', 'Restore')][string]$Mode,
    [Parameter(Mandatory = $true)][string]$DockerHost,
    [Parameter(Mandatory = $true)][string]$ConfigPath,
    [Parameter(Mandatory = $true)][string]$BackupPath
)

$ErrorActionPreference = 'Stop'
if ($DockerHost -cne 'unix:///run/user/1004/docker.sock') {
    throw 'Only the crmdeploy Rootless Docker socket may be tuned.'
}
$runnerUid = (& id -u).Trim()
if ($LASTEXITCODE -ne 0 -or $runnerUid -cne '1004') {
    throw 'Only the crmdeploy staging runner may tune Rootless Docker.'
}
if ([IO.Path]::GetFullPath($ConfigPath) -ceq [IO.Path]::GetFullPath($BackupPath)) {
    throw 'The daemon configuration and recovery backup must be separate paths.'
}
$configDirectory = Split-Path -Parent $ConfigPath
$directoryCreated = $false
if (-not (Test-Path -LiteralPath $configDirectory -PathType Container)) {
    if ($Mode -ne 'Enter') { throw 'The Rootless Docker configuration directory is missing.' }
    $parentDirectory = Split-Path -Parent $configDirectory
    if (-not (Test-Path -LiteralPath $parentDirectory -PathType Container)) {
        throw 'The parent Rootless Docker configuration directory is missing.'
    }
    $parentItem = Get-Item -LiteralPath $parentDirectory -Force
    if (($parentItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'The Rootless Docker configuration parent cannot be a symlink.'
    }
    New-Item -ItemType Directory -Path $configDirectory | Out-Null
    $directoryCreated = $true
    if (-not $IsWindows) {
        & chmod 700 $configDirectory
        if ($LASTEXITCODE -ne 0) { throw 'Unable to protect the new Rootless Docker configuration directory.' }
    }
}
foreach ($path in @($configDirectory, $ConfigPath, $BackupPath)) {
    if (Test-Path -LiteralPath $path) {
        $item = Get-Item -LiteralPath $path -Force
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'Symlinks are not allowed in the staging Docker config transaction.'
        }
    }
}

$savedDockerHost = [Environment]::GetEnvironmentVariable('DOCKER_HOST', 'Process')
$savedDockerContext = [Environment]::GetEnvironmentVariable('DOCKER_CONTEXT', 'Process')
$env:DOCKER_HOST = $DockerHost
[Environment]::SetEnvironmentVariable('DOCKER_CONTEXT', $null, 'Process')
try {
    $active = (& systemctl --user is-active docker.service).Trim()
    if ($LASTEXITCODE -ne 0 -or $active -cne 'active') {
        throw 'The crmdeploy Rootless Docker service is not active.'
    }
    $reloadCommand = (& systemctl --user show docker.service -p ExecReload --value).Trim()
    if ($LASTEXITCODE -ne 0 -or $reloadCommand -notmatch '\bHUP\b') {
        throw 'The Rootless Docker service does not expose a HUP reload action.'
    }

    function Get-DaemonIdentity {
        $pidText = (& systemctl --user show docker.service -p MainPID --value).Trim()
        if ($LASTEXITCODE -ne 0 -or $pidText -notmatch '^[1-9][0-9]*$') {
            throw 'Unable to identify the Rootless Docker daemon.'
        }
        $daemonId = (& docker info --format '{{.ID}}').Trim()
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($daemonId)) {
            throw 'The Rootless Docker daemon is unavailable.'
        }
        return @{ pid = $pidText; id = $daemonId }
    }

    function Assert-Reloaded([hashtable]$Before) {
        & systemctl --user reload docker.service | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw 'Rootless Docker rejected the configuration reload.'
        }
        $after = Get-DaemonIdentity
        if ($after.pid -cne $Before.pid -or $after.id -cne $Before.id) {
            throw 'Rootless Docker restarted or changed identity during reload.'
        }
    }

    function Get-Hash([byte[]]$Bytes) {
        return [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($Bytes)).ToLowerInvariant()
    }

    function Restore-Configuration {
        if (-not (Test-Path -LiteralPath $BackupPath -PathType Leaf)) {
            throw 'The staging Docker recovery backup is missing.'
        }
        $recovery = Get-Content -LiteralPath $BackupPath -Raw | ConvertFrom-Json
        if ($recovery.version -ne 1 -or $recovery.modified_sha256 -cnotmatch '^[0-9a-f]{64}$') {
            throw 'The staging Docker recovery backup is invalid.'
        }
        [byte[]]$original = [Convert]::FromBase64String([string]$recovery.original_base64)
        $originalHash = Get-Hash $original
        if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
            throw 'The temporary Rootless Docker configuration disappeared.'
        }
        $currentHash = Get-Hash ([IO.File]::ReadAllBytes($ConfigPath))
        if ($currentHash -cne $recovery.modified_sha256 -and $currentHash -cne $originalHash) {
            throw 'The Rootless Docker configuration changed during prefetch; recovery backup retained.'
        }
        $before = Get-DaemonIdentity
        if ($currentHash -cne $originalHash) {
            if ($recovery.original_exists) {
                $restoreTemp = "$ConfigPath.restore-$([guid]::NewGuid().ToString('N'))"
                try {
                    [IO.File]::WriteAllBytes($restoreTemp, $original)
                    if (-not $IsWindows) {
                        if ($recovery.original_mode -notmatch '^[0-7]{3,4}$') { throw 'Original config mode is invalid.' }
                        & chmod $recovery.original_mode $restoreTemp
                        if ($LASTEXITCODE -ne 0) { throw 'Unable to restore the original config mode.' }
                    }
                    [IO.File]::Move($restoreTemp, $ConfigPath, $true)
                }
                finally {
                    if (Test-Path -LiteralPath $restoreTemp) { Remove-Item -LiteralPath $restoreTemp }
                }
            }
            else {
                Remove-Item -LiteralPath $ConfigPath
            }
        }
        Assert-Reloaded $before
        Remove-Item -LiteralPath $BackupPath
        if ($recovery.directory_created -and
            @(Get-ChildItem -LiteralPath $configDirectory -Force).Count -eq 0) {
            Remove-Item -LiteralPath $configDirectory
        }
        Write-Output 'Original Rootless Docker download configuration restored; daemon identity unchanged.'
    }

    if ($Mode -eq 'Restore') {
        Restore-Configuration
        return
    }
    if (Test-Path -LiteralPath $BackupPath) {
        throw 'A staging Docker recovery backup already exists; restore it before a new prefetch.'
    }
    $before = Get-DaemonIdentity
    $originalExists = Test-Path -LiteralPath $ConfigPath -PathType Leaf
    [byte[]]$original = [byte[]]::new(0)
    if ($originalExists) { $original = [IO.File]::ReadAllBytes($ConfigPath) }
    $originalMode = $null
    if ($originalExists -and -not $IsWindows) {
        $originalMode = (& stat -c '%a' -- $ConfigPath).Trim()
        if ($LASTEXITCODE -ne 0 -or $originalMode -notmatch '^[0-7]{3,4}$') {
            throw 'Unable to record the original Rootless Docker config mode.'
        }
    }
    $config = if ($originalExists) { [Text.Encoding]::UTF8.GetString($original) | ConvertFrom-Json -AsHashtable } else { @{} }
    if ($null -eq $config -or $config -isnot [System.Collections.IDictionary]) {
        throw 'Rootless Docker daemon.json must contain a JSON object.'
    }
    $config['max-concurrent-downloads'] = 1
    [byte[]]$modified = [Text.Encoding]::UTF8.GetBytes(($config | ConvertTo-Json -Depth 50))
    $recovery = [ordered]@{
        version = 1
        original_exists = $originalExists
        directory_created = $directoryCreated
        original_base64 = [Convert]::ToBase64String($original)
        original_mode = $originalMode
        modified_sha256 = Get-Hash $modified
    }
    $configTemp = "$ConfigPath.enter-$([guid]::NewGuid().ToString('N'))"
    $backupTemp = "$BackupPath.enter-$([guid]::NewGuid().ToString('N'))"
    try {
        [IO.File]::WriteAllBytes($configTemp, $modified)
        [IO.File]::WriteAllText($backupTemp, ($recovery | ConvertTo-Json -Compress))
        if (-not $IsWindows) {
            & chmod 600 $configTemp $backupTemp
            if ($LASTEXITCODE -ne 0) { throw 'Unable to protect the staging Docker config backup.' }
        }
        [IO.File]::Move($backupTemp, $BackupPath)
        [IO.File]::Move($configTemp, $ConfigPath, $true)
        try {
            Assert-Reloaded $before
        }
        catch {
            Restore-Configuration
            throw
        }
        Write-Output 'Rootless Docker download concurrency set to one; daemon identity unchanged.'
    }
    finally {
        foreach ($path in @($configTemp, $backupTemp)) {
            if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path }
        }
    }
}
finally {
    [Environment]::SetEnvironmentVariable('DOCKER_HOST', $savedDockerHost, 'Process')
    [Environment]::SetEnvironmentVariable('DOCKER_CONTEXT', $savedDockerContext, 'Process')
    if ($directoryCreated -and -not (Test-Path -LiteralPath $BackupPath) -and
        (Test-Path -LiteralPath $configDirectory -PathType Container) -and
        @(Get-ChildItem -LiteralPath $configDirectory -Force).Count -eq 0) {
        Remove-Item -LiteralPath $configDirectory
    }
}
