"""仓库工程根布局契约。"""

import json

from _support import REPOSITORY_ROOT, SOURCE_ROOT, TESTS_ROOT


def test_backend_tests_use_central_test_root() -> None:
    assert (SOURCE_ROOT / "tests" / "backend").is_dir()
    assert not (SOURCE_ROOT / "backend" / "tests").exists()


def test_frontend_tests_use_central_test_root() -> None:
    assert (TESTS_ROOT / "frontend" / "contract").is_dir()
    assert not (SOURCE_ROOT / "frontend" / "tests").exists()


def test_postgres_integration_tests_have_one_category() -> None:
    assert (TESTS_ROOT / "integration" / "postgres").is_dir()
    assert not list((TESTS_ROOT / "integration").glob("test_*.py"))


def test_engineering_assets_live_under_src() -> None:
    """工程与运行资产必须只从单一 src 工程根提供。"""
    required = (
        "backend",
        "frontend",
        "tests",
        "scripts",
        "deploy",
        "docker",
        "compose",
        "config/.env.example",
    )
    assert all((SOURCE_ROOT / path).exists() for path in required)
    forbidden = (
        "backend",
        "frontend",
        "tests",
        "scripts",
        "deploy",
        "Dockerfile.backend",
        "docker-compose.yml",
    )
    assert all(not (REPOSITORY_ROOT / path).exists() for path in forbidden)
    assert not (SOURCE_ROOT / "deploy/cloudflared/config.example.yml").exists()

    ignore_source = (REPOSITORY_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "/src/deploy/models/bge-m3/" in ignore_source
    assert "/src/deploy/models/bge-reranker-large/" in ignore_source
    assert "\n/deploy/models/bge-m3/" not in ignore_source
    assert "\n/deploy/models/bge-reranker-large/" not in ignore_source

    env_example = (SOURCE_ROOT / "config/.env.example").read_text(encoding="utf-8")
    assert "src/deploy/staging/rootless/README.md" in env_example
    assert "# deploy/staging/rootless/README.md" not in env_example


def test_local_startup_entrypoint_uses_source_relative_compose_assets() -> None:
    """本地启动入口必须固定工程根、环境模板和 Compose 项目身份。"""
    startup_script = SOURCE_ROOT / "scripts/start-local.ps1"
    assert startup_script.is_file()
    startup_source = startup_script.read_text(encoding="utf-8-sig")
    assert 'Join-Path $sourceRoot "config/.env"' in startup_source
    assert 'Join-Path $sourceRoot "compose/docker-compose.yml"' in startup_source
    assert '"--project-name", "crm"' in startup_source

    compose_source = (SOURCE_ROOT / "compose/docker-compose.yml").read_text(encoding="utf-8")
    assert compose_source.startswith("name: crm\n")
    assert "image: ${BACKEND_DEV_IMAGE:-crm-backend:local}" in compose_source
    assert "image: ${BACKEND_IMAGE:-crm-backend:local}" not in compose_source
    assert "  minio-init:\n" in compose_source
    assert "condition: service_completed_successfully" in compose_source
    assert "mc mb --ignore-existing" in compose_source
    assert "start_period: 90s" in compose_source
    for required_path in (
        "context: ../backend",
        "context: ../frontend",
        "dockerfile: ../docker/Dockerfile.backend",
        "dockerfile: ../docker/Dockerfile.frontend",
        "path: ../config/.env",
        "../deploy/models:/models:ro",
    ):
        assert required_path in compose_source


def test_operational_scripts_bind_the_relocated_compose_file() -> None:
    """备份恢复入口不得依赖当前目录向上猜测 Compose 文件。"""
    for name in (
        "backup-postgres.ps1",
        "backup-minio.ps1",
        "restore-postgres.ps1",
        "restore-minio.ps1",
    ):
        source = (SOURCE_ROOT / "scripts" / name).read_text(encoding="utf-8-sig")
        assert "$sourceRoot = Split-Path -Parent $PSScriptRoot" in source
        assert 'Join-Path $sourceRoot "compose/docker-compose.yml"' in source
        assert "$env:COMPOSE_FILE" in source
        assert "@composeArguments" in source

    readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
    assert "docker-compose config --services" not in readme
    assert "docker-compose up -d --no-deps --force-recreate backend" not in readme
    assert "共享记忆文档/" not in readme
    assert "架构师/" not in readme
    assert "测试工程师/" not in readme
    assert "项目根 `.env`" not in readme
    assert "开发 `.env`" not in readme

    staging_readme = (SOURCE_ROOT / "deploy/staging/rootless/README.md").read_text(encoding="utf-8")
    assert "架构师/" not in staging_readme
    assert "测试工程师/" not in staging_readme

    model_manifest = json.loads((SOURCE_ROOT / "deploy/models/model-manifest.json").read_text(encoding="utf-8"))
    for key in ("quality_gate_report", "capacity_gate_report"):
        report = model_manifest[key]
        assert report.startswith("release/evidence/retrieval/")
        assert (REPOSITORY_ROOT / report).is_file()


def test_automation_uses_canonical_src_paths() -> None:
    """CI、镜像发布和 staging 门禁不得引用已移除的根级工程路径。"""
    ci_source = (REPOSITORY_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "working-directory: src/backend" in ci_source
    assert "working-directory: src/frontend" in ci_source
    assert "cache-dependency-path: src/frontend/package-lock.json" in ci_source

    publish_source = (REPOSITORY_ROOT / ".github/workflows/publish-images.yml").read_text(encoding="utf-8")
    for required_path in (
        "context: src/backend",
        "context: src/frontend",
        "file: src/docker/Dockerfile.backend",
        "file: src/docker/Dockerfile.frontend.prod",
        "file: src/docker/Dockerfile.model-service",
    ):
        assert required_path in publish_source

    staging_source = (REPOSITORY_ROOT / ".github/workflows/staging-gates.yml").read_text(encoding="utf-8")
    assert "./src/scripts/Test-StagingProductionGates.ps1" in staging_source
    assert "./src/scripts/Invoke-StagingRollbackDrill.ps1" in staging_source
