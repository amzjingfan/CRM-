#requires -Version 5.1
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "High")]
param(
    [Parameter(Mandatory = $true)]
    [string]$InputFile,
    [Parameter(Mandatory = $true)]
    [string]$Database,
    [Parameter(Mandatory = $true)]
    [string]$ConfirmTarget,
    [string]$DatabaseUser = "crm",
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

$resolvedInput = (Resolve-Path -LiteralPath $InputFile -ErrorAction Stop).Path
if ($ConfirmTarget -cne $Database) { throw "目标确认不匹配：ConfirmTarget 必须与 Database 完全一致" }
if (-not $PSCmdlet.ShouldProcess("PostgreSQL database '$Database'", "restore from '$resolvedInput'")) { return }
Get-Content -LiteralPath $resolvedInput -Raw -Encoding utf8 | & docker @composeArguments exec -T postgres psql --set ON_ERROR_STOP=on --username $DatabaseUser --dbname $Database
if ($LASTEXITCODE -ne 0) { throw "PostgreSQL 恢复失败；请保持业务服务停止并检查数据库日志" }
Write-Host "PostgreSQL 恢复完成，请立即执行迁移版本与业务抽样校验。"
