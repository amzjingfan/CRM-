"""Agent 文件绑定必须限制在当前店铺可用的通用导入文件。"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agent_management import service
from app.agent_management.schemas import AgentConfigUpdate
from app.shared.exceptions.errors import AppError


class FakeSession:
    def __init__(self, found: list[uuid.UUID]):
        self.found = found
        self.sql = ""

    async def scalars(self, query):  # type: ignore[no-untyped-def]
        self.sql = str(query)
        return SimpleNamespace(all=lambda: self.found)


@pytest.mark.asyncio
async def test_file_bindings_are_store_scoped_and_exclude_archived_deleted() -> None:
    store_id, first, second = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    session = FakeSession([first, second])
    result = await service.validate_knowledge_file_ids(session, store_id, [first, second, first])  # type: ignore[arg-type]
    assert result == [first, second]
    assert "knowledge_files.store_id" in session.sql
    assert "knowledge_files.archived_at IS NULL" in session.sql
    assert "knowledge_files.deleted_at IS NULL" in session.sql


@pytest.mark.asyncio
async def test_missing_or_foreign_file_binding_fails_closed() -> None:
    with pytest.raises(AppError):
        await service.validate_knowledge_file_ids(
            FakeSession([]),
            uuid.uuid4(),
            [uuid.uuid4()],  # type: ignore[arg-type]
        )


def test_binding_files_requires_knowledge_view_permission() -> None:
    file_id = uuid.uuid4()
    agent_only = SimpleNamespace(roles=[SimpleNamespace(code="operator", permissions=[])])
    with pytest.raises(AppError) as error:
        service.require_knowledge_view_for_binding(agent_only, [file_id])  # type: ignore[arg-type]
    assert error.value.status_code == 403

    reader = SimpleNamespace(
        roles=[SimpleNamespace(code="operator", permissions=[SimpleNamespace(code="knowledge.view")])]
    )
    service.require_knowledge_view_for_binding(reader, [file_id])  # type: ignore[arg-type]
    service.require_knowledge_view_for_binding(agent_only, [])  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_operations_agent_cannot_be_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    config = SimpleNamespace(knowledge_scope={"agent_type": "operations"}, status="disabled")
    monkeypatch.setattr(service, "get_config", AsyncMock(return_value=config))
    with pytest.raises(AppError):
        await service.set_config_status(AsyncMock(), SimpleNamespace(), uuid.uuid4(), "enabled")  # type: ignore[arg-type]
    assert config.status == "disabled"


@pytest.mark.asyncio
async def test_switching_to_operations_disables_active_service(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(UTC)
    config = SimpleNamespace(
        id=uuid.uuid4(),
        store_id=uuid.uuid4(),
        name="服务 Agent",
        code="service_agent",
        description=None,
        status="enabled",
        enabled_tools=["query_order"],
        knowledge_scope={"mode": "store_ready_faq", "agent_type": "service"},
        created_at=now,
        updated_at=now,
    )
    monkeypatch.setattr(service, "get_config", AsyncMock(return_value=config))
    session = SimpleNamespace(add=lambda _: None, commit=AsyncMock(), refresh=AsyncMock())
    user = SimpleNamespace(id=uuid.uuid4())
    result = await service.update_config(
        session,
        user,
        config.id,
        AgentConfigUpdate(agent_type="operations"),  # type: ignore[arg-type]
    )
    assert result.agent_type == "operations"
    assert result.status == "disabled"
