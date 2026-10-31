#requires -Version 5.1
param(
    [switch]$KeepDatabase,
    [ValidateRange(1024, 65535)][int]$TestPort = 5433,
    [ValidatePattern("^[a-z0-9][a-z0-9_-]*$")][string]$ProjectName = "crm-postgres-test-$PID",
    [string[]]$PytestArgs = @("-q", "-rs")
)

$ErrorActionPreference = "Stop"

$sourceRoot = Split-Path -Parent $PSScriptRoot
$backendDirectory = Join-Path $sourceRoot "backend"
$composeFile = Join-Path $sourceRoot "compose/docker-compose.yml"
$testDatabaseUrl = "postgresql+asyncpg://crm_test:crm_test@127.0.0.1:$TestPort/crm_test"
$previousTestPort = $env:POSTGRES_TEST_PORT
$env:POSTGRES_TEST_PORT = [string]$TestPort

Push-Location $sourceRoot
try {
    docker compose -p $ProjectName -f $composeFile --profile test up -d --wait postgres-test
    if ($LASTEXITCODE -ne 0) {
        throw "隔离 PostgreSQL 测试库启动失败。"
    }

    $env:DATABASE_URL = $testDatabaseUrl
    $env:TEST_DATABASE_URL = $testDatabaseUrl
    $env:AGENT_TEMPLATE_RUNTIME_TEST_DATABASE_URL = $testDatabaseUrl

    Push-Location $backendDirectory
    try {
        # 迁移和测试共用同一个隔离数据库，确保 pgvector、表结构和索引与正式环境一致。
        uv run --frozen alembic upgrade head
        if ($LASTEXITCODE -ne 0) {
            throw "测试数据库迁移失败。"
        }

        uv run --frozen pytest -c pyproject.toml @PytestArgs
        if ($LASTEXITCODE -ne 0) {
            throw "后端测试失败。"
        }
    }
    finally {
        Pop-Location
    }
}
finally {
    Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
    Remove-Item Env:TEST_DATABASE_URL -ErrorAction SilentlyContinue
    Remove-Item Env:AGENT_TEMPLATE_RUNTIME_TEST_DATABASE_URL -ErrorAction SilentlyContinue

    if (-not $KeepDatabase) {
        # postgres-test 使用 tmpfs，只包含自动化测试数据；停止并删除该精确服务
        # 可以避免 5433 端口长期占用，不会触碰开发数据库 postgres。
        docker compose -p $ProjectName -f $composeFile --profile test stop postgres-test | Out-Null
        docker compose -p $ProjectName -f $composeFile --profile test rm -f postgres-test | Out-Null
    }

    $env:POSTGRES_TEST_PORT = $previousTestPort
    Pop-Location
}
