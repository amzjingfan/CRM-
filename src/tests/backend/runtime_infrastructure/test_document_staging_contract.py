"""文档解析 Worker 的独立 staging 配置边界。"""

from pathlib import Path

import yaml

SOURCE_ROOT = Path(__file__).resolve().parents[3]


COMPOSE = SOURCE_ROOT / "compose"
GATE = SOURCE_ROOT / "scripts" / "Test-StagingProductionGates.ps1"


def test_document_worker_is_opt_in_and_uses_private_services() -> None:
    base = yaml.safe_load((COMPOSE / "docker-compose.yml").read_text("utf-8"))["services"]
    worker = base["document-parser"]
    assert worker["profiles"] == ["document"]
    assert "ports" not in worker
    assert worker["depends_on"]["retrieval-model-service"]["condition"] == "service_healthy"
    assert worker["environment"]["MINERU_MODEL_SOURCE"] == "local"
    assert worker["environment"]["HF_HUB_OFFLINE"] == "1"
    assert worker["environment"]["EMBEDDING_ENABLED"] == "true"


def test_production_document_worker_is_cpu_bounded_and_private() -> None:
    source = (COMPOSE / "docker-compose.prod.yml").read_text("utf-8")
    assert yaml.compose(source) is not None
    worker = source.split("  document-parser:\n", 1)[1].split("  frontend:\n", 1)[0]
    for value in (
        "read_only: true",
        "cap_drop: [ALL]",
        "mem_limit: 8g",
        "cpus: 2",
        "/opt/mineru/models/.locks:size=1048576,mode=1777",
    ):
        assert value in worker
    assert worker.count("read_only: true") == 3
    assert "MINERU_ASSET_DIR" in worker
    assert "TIKTOK_OAUTH_REDIRECT_URI: ${TIKTOK_OAUTH_REDIRECT_URI:?TIKTOK_OAUTH_REDIRECT_URI is required}" in worker
    assert "ports:" not in worker
    assert "env_file: !reset []" in worker


def test_staging_gate_requires_document_digest_and_assets_when_enabled() -> None:
    source = GATE.read_text("utf-8")
    for value in (
        "EnableDocumentIngestion",
        "DocumentParserImage",
        "ghcr.io/cp11-gh/crm-document-parser",
        "MINERU_ASSET_DIR",
        '"--profile", "document"',
        '"document-parser"',
        "Assert-RunningDocumentWorker",
    ):
        assert value in source
