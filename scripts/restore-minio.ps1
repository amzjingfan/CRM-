#requires -Version 5.1
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "High")]
param(
    [Parameter(Mandatory = $true)]
    [string]$InputDirectory,
    [Parameter(Mandatory = $true)]
    [ValidateSet("crm-minio")]
    [string]$ConfirmTarget
)

$resolvedInput = (Resolve-Path -LiteralPath $InputDirectory -ErrorAction Stop).Path
if (-not $PSCmdlet.ShouldProcess("MinIO target '$ConfirmTarget'", "restore objects from '$resolvedInput'")) { return }
docker compose cp "$resolvedInput/." minio:/data
if ($LASTEXITCODE -ne 0) { throw "MinIO 恢复失败" }
Write-Host "MinIO 恢复完成；同名对象已覆盖，请执行对象数量与 FAQ 文件抽样校验。"
