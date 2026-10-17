#requires -Version 7.0

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('CheckOnly', 'DeployG5', 'RestoreDefault', 'RestoreReadAndTranslation', 'RestoreManualSend', 'RollbackPrevious', 'ContentCheck', 'ContentPrepare', 'ReconcileFixture', 'RenewCredentials', 'VectorizeG5')]
    [string]$Mode,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{40}$')][string]$SourceSha,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{40}$')][string]$ResolvedCommitSha,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{40}$')][string]$CurrentMainSha
)

if ($SourceSha -cne $ResolvedCommitSha) {
    throw 'The reviewed source is not a verified repository commit.'
}
if ($Mode -cin @('CheckOnly', 'DeployG5', 'ReconcileFixture', 'VectorizeG5') -and $SourceSha -cne $CurrentMainSha) {
    throw 'A new staging deployment requires the current remote main commit.'
}
# 恢复与内容模式沿用已审核源码和运行镜像 revision；证据合入 main 不应阻断后续检查。
