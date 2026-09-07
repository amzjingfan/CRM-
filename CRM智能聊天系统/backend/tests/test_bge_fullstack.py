"""本地 BGE 切换后的全栈运行面和知识库运维契约测试。"""

import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.knowledge_base import service as knowledge_service
from app.main import app
from app.shared import health
from app.shared.config.settings import Settings
from app.shared.exceptions.errors import AppError


class FakeSession:
    """记录服务层事务行为，避免单元测试访问真实数据库。"""

    def __init__(self) -> None:
        self.added: list[object] = []
        self.committed = False

    def add(self, value: object) -> None:
        """记录待写入实体。"""
        self.added.append(value)

    async def commit(self) -> None:
        """记录提交动作。"""
        self.committed = True

    async def refresh(self, _value: object) -> None:
        """模拟 ORM 刷新；本测试只验证状态和事务。"""


def enabled_bge_settings() -> Settings:
    """构造不会读取项目密钥文件的有效本地 BGE 配置。"""
    return Settings(
        _env_file=None,
        EMBEDDING_ENABLED=True,
        EMBEDDING_PROVIDER="local_bge",
        EMBEDDING_MODEL="BAAI/bge-m3",
        EMBEDDING_DIMENSIONS=1024,
        RETRIEVAL_MODEL_SERVICE_TOKEN="unit-test-token-with-at-least-32-characters",
    )


def test_default_rag_threshold_matches_production_calibration() -> None:
    """默认 Dense 门禁必须采用 2026-08-21 真实 BGE 评测校准值。"""
    settings = Settings(_env_file=None)

    assert settings.rag_min_score == pytest.approx(0.52)


def test_enabled_bge_rejects_wrong_database_dimension() -> None:
    """启用本地 BGE 时必须拒绝会造成数据库混写的非 1024 维配置。"""
    with pytest.raises(ValidationError, match="1024"):
        Settings(
            _env_file=None,
            EMBEDDING_ENABLED=True,
            EMBEDDING_PROVIDER="local_bge",
            EMBEDDING_MODEL="BAAI/bge-m3",
            EMBEDDING_DIMENSIONS=1536,
            RETRIEVAL_MODEL_SERVICE_TOKEN="unit-test-token-with-at-least-32-characters",
        )


def test_enabled_bge_requires_strong_internal_token() -> None:
    """启用内部模型服务时必须在进程启动前拒绝空令牌和弱令牌。"""
    with pytest.raises(ValidationError, match="内部模型服务令牌"):
        Settings(
            _env_file=None,
            EMBEDDING_ENABLED=True,
            EMBEDDING_PROVIDER="local_bge",
            EMBEDDING_MODEL="BAAI/bge-m3",
            EMBEDDING_DIMENSIONS=1024,
            RETRIEVAL_MODEL_SERVICE_TOKEN="short",
        )


@pytest.mark.asyncio
async def test_failed_published_entry_can_be_requeued(monkeypatch: pytest.MonkeyPatch) -> None:
    """运营人员只能把已发布且失败的当前 FAQ 重新放回向量队列。"""
    store_id = uuid.uuid4()
    entry_id = uuid.uuid4()
    user = SimpleNamespace(id=uuid.uuid4())
    document = SimpleNamespace(
        id=entry_id,
        store_id=store_id,
        status="published",
        vectorization_status="failed",
        document_version=3,
        publication_approval="approved_for_internal_review",
        statement_type="policy",
    )

    async def fake_allowed_store_ids(_session: object, _user: object) -> set[uuid.UUID]:
        return {store_id}

    async def fake_find_document(_session: object, _entry_id: uuid.UUID, _stores: set[uuid.UUID]) -> object:
        return document

    monkeypatch.setattr(knowledge_service, "allowed_store_ids", fake_allowed_store_ids)
    monkeypatch.setattr(knowledge_service, "find_document", fake_find_document)
    monkeypatch.setattr(knowledge_service, "get_settings", enabled_bge_settings)
    session = FakeSession()

    result = await knowledge_service.retry_entry_vectorization(session, user, entry_id)  # type: ignore[arg-type]

    assert result.vectorization_status == "pending"
    assert session.committed is True
    assert len(session.added) == 1


@pytest.mark.asyncio
async def test_ready_entry_cannot_be_requeued_as_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    """重试入口不得把已经 ready 的 FAQ 随意失效。"""
    store_id = uuid.uuid4()
    document = SimpleNamespace(
        id=uuid.uuid4(),
        store_id=store_id,
        status="published",
        vectorization_status="ready",
        document_version=1,
    )

    async def fake_allowed_store_ids(_session: object, _user: object) -> set[uuid.UUID]:
        return {store_id}

    async def fake_find_document(_session: object, _entry_id: uuid.UUID, _stores: set[uuid.UUID]) -> object:
        return document

    monkeypatch.setattr(knowledge_service, "allowed_store_ids", fake_allowed_store_ids)
    monkeypatch.setattr(knowledge_service, "find_document", fake_find_document)
    monkeypatch.setattr(knowledge_service, "get_settings", enabled_bge_settings)

    with pytest.raises(AppError, match="失败"):
        await knowledge_service.retry_entry_vectorization(  # type: ignore[arg-type]
            FakeSession(),
            SimpleNamespace(id=uuid.uuid4()),
            document.id,
        )


@pytest.mark.asyncio
async def test_vectorization_status_is_store_scoped(monkeypatch: pytest.MonkeyPatch) -> None:
    """向量化汇总必须先校验店铺权限，再返回低敏模型信息。"""
    store_id = uuid.uuid4()
    access_checked: list[uuid.UUID] = []

    async def fake_ensure_store_access(_session: object, _user: object, checked_store_id: uuid.UUID) -> None:
        access_checked.append(checked_store_id)

    async def fake_counts(_session: object, checked_store_id: uuid.UUID) -> dict[str, int]:
        assert checked_store_id == store_id
        return {"pending": 2, "processing": 1, "ready": 4, "failed": 3}

    monkeypatch.setattr(knowledge_service, "ensure_store_access", fake_ensure_store_access)
    monkeypatch.setattr(knowledge_service, "count_vectorization_statuses", fake_counts)
    monkeypatch.setattr(knowledge_service, "get_settings", enabled_bge_settings)

    result = await knowledge_service.get_vectorization_status(  # type: ignore[arg-type]
        object(),
        SimpleNamespace(id=uuid.uuid4()),
        store_id,
    )

    assert access_checked == [store_id]
    assert result.dimensions == 1024
    assert result.counts.failed == 3


@pytest.mark.asyncio
async def test_readiness_checks_model_only_when_embedding_is_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """AI 关闭时不依赖模型服务，启用后模型契约错误必须使就绪检查失败。"""

    async def healthy() -> bool:
        return True

    async def invalid_model(_settings: Settings) -> bool:
        return False

    monkeypatch.setattr(health, "check_database", healthy)
    monkeypatch.setattr(health, "check_redis", healthy)
    monkeypatch.setattr(health, "check_object_storage", healthy)
    monkeypatch.setattr(health, "check_retrieval_model", invalid_model)

    disabled = await health.collect_readiness(Settings(_env_file=None, EMBEDDING_ENABLED=False))
    enabled = await health.collect_readiness(enabled_bge_settings())

    assert disabled.status == "ready"
    assert disabled.components.retrieval_model == "disabled"
    assert enabled.status == "not_ready"
    assert enabled.components.retrieval_model == "error"


def test_openapi_exposes_vectorization_operations() -> None:
    """OpenAPI 必须暴露店铺状态查询和失败重试契约。"""
    paths = TestClient(app).get("/openapi.json").json()["paths"]
    assert "/v1/knowledge/vectorization/status" in paths
    assert "/v1/knowledge/entries/{entry_id}/vectorization/retry" in paths
