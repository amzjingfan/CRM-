"""独立知识服务 Alembic 链测试。"""

import os
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_knowledge_alembic_generates_independent_offline_sql() -> None:
    """独立迁移配置应能不连库生成完整基线 SQL。"""
    environment = os.environ.copy()
    environment["KNOWLEDGE_DATABASE_URL"] = (
        "postgresql+asyncpg://knowledge_migration:test-only@localhost:5432/company_knowledge"
    )
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "knowledge_alembic.ini", "upgrade", "head", "--sql"],
        cwd=BACKEND_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "CREATE TABLE kb_applications" in result.stdout
    assert "CREATE TABLE kb_content_versions" in result.stdout
    assert "CREATE TABLE kb_audit_events" in result.stdout
    assert "CREATE TABLE stores" not in result.stdout
    assert "CREATE TABLE users" not in result.stdout


def test_knowledge_alembic_has_separate_script_location() -> None:
    """CRM Alembic 历史不得承载知识服务迁移。"""
    config_text = (BACKEND_ROOT / "knowledge_alembic.ini").read_text(encoding="utf-8")

    assert "script_location = knowledge_migrations" in config_text
    assert "script_location = migrations" not in config_text
