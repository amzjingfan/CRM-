#requires -Version 5.1
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "High")]
param(
    [Parameter(Mandatory = $true)]
    [string]$InputDirectory,
    [Parameter(Mandatory = $true)]
    [ValidateSet("crm-minio")]
    [string]$ConfirmTarget,
    [string]$ComposeFile,
    [string]$ProjectName
)

$sourceRoot = Split-Path -Parent $PSScriptRoot
$defaultComposeFile = Join-Path $sourceRoot "compose/docker-compose.yml"
$composeArguments = @("compose")
if ([string]::IsNullOrWhiteSpace($ComposeFile) -and [string]::IsNullOrWhiteSpace($env:COMPOSE_FILE)) {
    if (-not (Test-Path -LiteralPath $defaultComposeFile -PathType Leaf)) {
        throw "Compose file not found: $defaultComposeFile"
    }
    $composeArguments += @("-f", $defaultComposeFile)
}
elseif (-not [string]::IsNullOrWhiteSpace($ComposeFile)) {
    $composeArguments += @("-f", $ComposeFile)
}
if (-not [string]::IsNullOrWhiteSpace($ProjectName)) {
    $composeArguments += @("--project-name", $ProjectName)
}

$resolvedInput = (Resolve-Path -LiteralPath $InputDirectory -ErrorAction Stop).Path
if (-not $PSCmdlet.ShouldProcess("MinIO target '$ConfirmTarget'", "restore objects from '$resolvedInput'")) { return }
& docker @composeArguments cp "$resolvedInput/." minio:/data
if ($LASTEXITCODE -ne 0) { throw "MinIO 恢复失败" }
Write-Host "MinIO 恢复完成；同名对象已覆盖，请执行对象数量与 FAQ 文件抽样校验。"
