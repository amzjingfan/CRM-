#requires -Version 5.1
param(
    [string]$ApiBaseUrl = "http://localhost:8000/v1",
    [ValidateRange(1, 65535)]
    [int]$Port = 3000,
    [switch]$InstallDependencies
)

$ErrorActionPreference = "Stop"

$sourceRoot = Split-Path -Parent $PSScriptRoot
$frontendDirectory = Join-Path $sourceRoot "frontend"
$nodeModulesDirectory = Join-Path $frontendDirectory "node_modules"

if (-not (Get-Command node.exe -ErrorAction SilentlyContinue)) {
    throw "未找到 Node.js。请先安装项目要求的 Node.js 20 LTS。"
}

if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw "未找到 npm。请确认 Node.js 20 LTS 已正确安装并加入 PATH。"
}

if (-not (Test-Path -LiteralPath $nodeModulesDirectory -PathType Container)) {
    if (-not $InstallDependencies) {
        throw "前端依赖尚未安装。请先运行 npm ci，或使用 -InstallDependencies 参数。"
    }

    Push-Location $frontendDirectory
    try {
        npm ci
        if ($LASTEXITCODE -ne 0) {
            throw "npm ci 执行失败，请检查 npm registry 或企业代理配置。"
        }
    }
    finally {
        Pop-Location
    }
}

# 本地启动仅用于 Docker 镜像源不可达时的开发降级。API 地址只在当前进程中生效，
# 脚本退出后立即清理，避免污染开发者的全局环境变量。
$env:NEXT_PUBLIC_API_BASE_URL = $ApiBaseUrl
Push-Location $frontendDirectory
try {
    npm run dev -- --hostname 0.0.0.0 --port $Port
    if ($LASTEXITCODE -ne 0) {
        throw "Next.js 开发服务异常退出，退出码：$LASTEXITCODE"
    }
}
finally {
    Pop-Location
    Remove-Item Env:NEXT_PUBLIC_API_BASE_URL -ErrorAction SilentlyContinue
}
