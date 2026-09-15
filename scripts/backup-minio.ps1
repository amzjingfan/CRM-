#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory
)

$resolvedOutput = [System.IO.Path]::GetFullPath($OutputDirectory)
if (-not (Test-Path -LiteralPath $resolvedOutput -PathType Container)) {
    New-Item -ItemType Directory -Path $resolvedOutput -Force | Out-Null
}
docker compose cp minio:/data/. $resolvedOutput
if ($LASTEXITCODE -ne 0) { throw "MinIO 备份失败" }
Write-Host "MinIO 备份已写入 $resolvedOutput"
