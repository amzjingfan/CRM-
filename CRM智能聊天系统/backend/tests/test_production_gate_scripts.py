"""staging 生产门禁和回滚脚本的失败关闭契约测试。"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT_SCRIPT = PROJECT_ROOT / "scripts" / "Test-StagingProductionGates.ps1"
ROLLBACK_SCRIPT = PROJECT_ROOT / "scripts" / "Invoke-StagingRollbackDrill.ps1"
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")

BACKEND_IMAGE = "ghcr.io/cp11-gh/crm-backend@sha256:" + "a" * 64
FRONTEND_IMAGE = "ghcr.io/cp11-gh/crm-frontend@sha256:" + "b" * 64
PREVIOUS_BACKEND_IMAGE = "ghcr.io/cp11-gh/crm-backend@sha256:" + "c" * 64
PREVIOUS_FRONTEND_IMAGE = "ghcr.io/cp11-gh/crm-frontend@sha256:" + "d" * 64
SECRET_SENTINEL = "must-not-appear-in-command-output-or-evidence"


def run_powershell(script: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """使用当前平台可用的 PowerShell 执行脚本并捕获低敏输出。"""
    assert POWERSHELL is not None, "PowerShell is required for production gate tests"
    assert script.exists(), f"missing production gate script: {script}"
    return subprocess.run(
        [POWERSHELL, "-NoLogo", "-NoProfile", "-File", str(script), *arguments],
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
        text=True,
        timeout=30,
    )


@pytest.fixture
def staging_env_file(tmp_path: Path) -> Path:
    """创建只含测试值的仓库外环境文件样本，不使用开发机真实配置。"""
    env_file = tmp_path / "crm-staging.env"
    env_file.write_text(
        "\n".join(
            [
                "DATABASE_URL=postgresql+asyncpg://crm:test@postgres:5432/crm",
                "REDIS_URL=redis://redis:6379/0",
                "MINIO_ENDPOINT=minio:9000",
                "MINIO_ACCESS_KEY=test-access",
                f"MINIO_SECRET_KEY={SECRET_SENTINEL}",
                "JWT_SECRET_KEY=test-jwt-key-with-at-least-32-characters",
                "CORS_ORIGINS=https://staging.example.com",
                "PUBLIC_BASE_URL=https://staging.example.com",
                "PUBLIC_API_BASE_URL=https://staging.example.com/v1",
                "TIKTOK_EGRESS_IP=203.0.113.10",
                "TIKTOK_OAUTH_REDIRECT_URI=https://www.hophorsefit.com/v1/integrations/tiktok/oauth/callback",
                "POSTGRES_DB=crm",
                "POSTGRES_USER=crm",
                "POSTGRES_PASSWORD=test-postgres-password",
                "TLS_CERT_DIR=/secure/test-certs",
                "POSTGRES_IMAGE=pgvector/pgvector:0.8.0-pg16@sha256:" + "1" * 64,
                "REDIS_IMAGE=redis:7.4.2-alpine@sha256:" + "2" * 64,
                "MINIO_IMAGE=minio/minio:RELEASE.2025-04-22T22-12-26Z@sha256:" + "3" * 64,
                "NGINX_IMAGE=nginx:1.27.5-alpine@sha256:" + "4" * 64,
                "REAL_TIKTOK_READ_ENABLED=false",
                "REAL_TIKTOK_WEBHOOK_ENABLED=false",
                "REAL_TIKTOK_MESSAGE_WRITE_ENABLED=false",
                "REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED=false",
                "LLM_ENABLED=false",
                "LLM_LIVE_EVAL=false",
                "AI_TRANSLATION_ENABLED=false",
                "AI_MARKETING_ENABLED=false",
                "AUTO_REPLY_ENABLED=false",
                "ALLOW_MOCK_PLATFORM_ADAPTERS=false",
            ]
        ),
        encoding="utf-8",
    )
    return env_file


def test_preflight_rejects_production_environment(tmp_path: Path) -> None:
    """本任务的运维脚本不得被误用于 production。"""
    result = run_powershell(
        PREFLIGHT_SCRIPT,
        "-Environment",
        "production",
        "-EnvFile",
        str(tmp_path / "missing.env"),
        "-BackendImage",
        BACKEND_IMAGE,
        "-FrontendImage",
        FRONTEND_IMAGE,
        "-BaseUrl",
        "https://production.example.com",
        "-EvidenceFile",
        str(tmp_path / "evidence.json"),
        "-ConfirmTarget",
        "production",
        "-ValidateOnly",
    )

    assert result.returncode != 0
    assert "staging" in (result.stdout + result.stderr).lower()


def test_preflight_rejects_floating_application_image(
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """候选部署必须拒绝 latest 或普通版本标签。"""
    result = run_powershell(
        PREFLIGHT_SCRIPT,
        "-Environment",
        "staging",
        "-EnvFile",
        str(staging_env_file),
        "-BackendImage",
        "ghcr.io/cp11-gh/crm-backend:latest",
        "-FrontendImage",
        FRONTEND_IMAGE,
        "-BaseUrl",
        "https://staging.example.com",
        "-EvidenceFile",
        str(tmp_path / "evidence.json"),
        "-ConfirmTarget",
        "staging",
        "-ValidateOnly",
    )

    assert result.returncode != 0
    assert "digest" in (result.stdout + result.stderr).lower()


def test_validate_only_writes_redacted_preflight_evidence(
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """静态预检证据只能包含变量名和摘要，不能回显环境值。"""
    evidence_file = tmp_path / "preflight-evidence.json"
    result = run_powershell(
        PREFLIGHT_SCRIPT,
        "-Environment",
        "staging",
        "-EnvFile",
        str(staging_env_file),
        "-BackendImage",
        BACKEND_IMAGE,
        "-FrontendImage",
        FRONTEND_IMAGE,
        "-BaseUrl",
        "https://staging.example.com",
        "-EvidenceFile",
        str(evidence_file),
        "-ConfirmTarget",
        "staging",
        "-ValidateOnly",
    )

    combined_output = result.stdout + result.stderr
    assert result.returncode == 0, combined_output
    assert SECRET_SENTINEL not in combined_output
    assert SECRET_SENTINEL not in evidence_file.read_text(encoding="utf-8")
    evidence = json.loads(evidence_file.read_text(encoding="utf-8-sig"))
    assert evidence["status"] == "validated"
    assert evidence["production_release"] is False


def test_preflight_rejects_floating_external_image(
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """仓库外环境文件不得把已固定的基础设施镜像降级为浮动标签。"""
    source = staging_env_file.read_text(encoding="utf-8")
    staging_env_file.write_text(
        source.replace(
            "NGINX_IMAGE=nginx:1.27.5-alpine@sha256:" + "4" * 64,
            "NGINX_IMAGE=nginx:latest",
        ),
        encoding="utf-8",
    )
    result = run_powershell(
        PREFLIGHT_SCRIPT,
        "-Environment",
        "staging",
        "-EnvFile",
        str(staging_env_file),
        "-BackendImage",
        BACKEND_IMAGE,
        "-FrontendImage",
        FRONTEND_IMAGE,
        "-BaseUrl",
        "https://staging.example.com",
        "-EvidenceFile",
        str(tmp_path / "evidence.json"),
        "-ConfirmTarget",
        "staging",
        "-ValidateOnly",
    )

    assert result.returncode != 0
    assert "digest" in (result.stdout + result.stderr).lower()


def test_preflight_live_path_forces_capabilities_off_before_deploy() -> None:
    """即使 runner 已有同名变量，候选部署也必须主动覆盖为 false。"""
    source = PREFLIGHT_SCRIPT.read_text(encoding="utf-8-sig")
    live_path = source[source.index("$savedEnvironment") :]

    assert "Set-DisabledCapabilities" in live_path
    assert live_path.index("Set-DisabledCapabilities") < live_path.index(
        "$env:BACKEND_IMAGE = $BackendImage"
    )


def test_rollback_plan_disables_capabilities_before_switching_images(
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """回滚计划必须先紧急关闭真实能力，再切换历史镜像摘要。"""
    evidence_file = tmp_path / "rollback-evidence.json"
    result = run_powershell(
        ROLLBACK_SCRIPT,
        "-Environment",
        "staging",
        "-EnvFile",
        str(staging_env_file),
        "-CandidateBackendImage",
        BACKEND_IMAGE,
        "-CandidateFrontendImage",
        FRONTEND_IMAGE,
        "-PreviousBackendImage",
        PREVIOUS_BACKEND_IMAGE,
        "-PreviousFrontendImage",
        PREVIOUS_FRONTEND_IMAGE,
        "-BaseUrl",
        "https://staging.example.com",
        "-EvidenceFile",
        str(evidence_file),
        "-ConfirmTarget",
        "staging",
        "-ValidateOnly",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert SECRET_SENTINEL not in (result.stdout + result.stderr)
    evidence = json.loads(evidence_file.read_text(encoding="utf-8-sig"))
    assert evidence["planned_steps"] == [
        "disable_real_capabilities",
        "deploy_previous_image_digests",
        "verify_health",
    ]
    assert evidence["production_release"] is False
