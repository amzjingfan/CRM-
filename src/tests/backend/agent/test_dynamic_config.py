"""店铺多个 Agent 的发布与启用行为。"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agents.management import config_service as service
from app.agents.management.schemas import AgentConfigCreate, AgentConfigUpdate
from app.shared.exceptions.errors import AppError


def _config(agent_type: str = "service") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        store_id=uuid.uuid4(),
        status="disabled",
        knowledge_scope={"agent_type": agent_type},
        published_version=1,
    )


def test_old_knowledge_scope_input_is_canonicalized_to_explicit_file_only() -> None:
    created = AgentConfigCreate(
        store_id=uuid.uuid4(),
        name="客服",
        code="service",
        knowledge_scope="store_ready_faq",  # type: ignore[arg-type]
    )
    updated = AgentConfigUpdate(knowledge_scope="store_ready_faq")  # type: ignore[arg-type]

    assert created.knowledge_scope == "bound_files_only"
    assert updated.knowledge_scope == "bound_files_only"


@pytest.mark.asyncio
async def test_multiple_published_agents_can_be_enabled_without_runtime_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config()
    monkeypatch.setattr(service, "get_config", AsyncMock(return_value=config))
    lookup = AsyncMock(return_value=SimpleNamespace(ready_for_v2=True))
    monkeypatch.setattr(service, "get_published_agent", lookup)
    monkeypatch.setattr(service, "config_view", lambda item: item)
    session = SimpleNamespace(
        add=lambda _: None,
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )

    result = await service.set_config_status(session, SimpleNamespace(id=uuid.uuid4()), config.id, "enabled")  # type: ignore[arg-type]
    assert result.status == "enabled"
    lookup.assert_awaited_once_with(session, store_id=config.store_id, config_id=config.id)
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_v2_mode_can_enable_published_operations_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _config("operations")
    monkeypatch.setattr(service, "get_config", AsyncMock(return_value=config))
    monkeypatch.setattr(service, "get_published_agent", AsyncMock(return_value=SimpleNamespace(ready_for_v2=True)))
    monkeypatch.setattr(service, "config_view", lambda item: item)
    session = SimpleNamespace(
        add=lambda _: None,
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )

    result = await service.set_config_status(
        session,
        SimpleNamespace(id=uuid.uuid4()),
        config.id,
        "enabled",  # type: ignore[arg-type]
    )
    assert result.status == "enabled"
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_unpublished_agent_cannot_be_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _config()
    monkeypatch.setattr(service, "get_config", AsyncMock(return_value=config))
    monkeypatch.setattr(service, "get_published_agent", AsyncMock(return_value=None))
    session = SimpleNamespace(commit=AsyncMock())

    with pytest.raises(AppError) as error:
        await service.set_config_status(session, SimpleNamespace(id=uuid.uuid4()), config.id, "enabled")  # type: ignore[arg-type]
    assert error.value.status_code == 409
    assert config.status == "disabled"
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_edit_increments_draft_revision_without_changing_published_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config()
    config.name = "物流"
    config.code = "shipping"
    config.description = "旧描述"
    config.enabled_tools = ["query_logistics"]
    config.draft_revision = 1
    monkeypatch.setattr(service, "get_config", AsyncMock(return_value=config))
    monkeypatch.setattr(service, "config_view", lambda item: item)
    session = SimpleNamespace(add=lambda _: None, commit=AsyncMock(), refresh=AsyncMock())

    result = await service.update_config(
        session,
        SimpleNamespace(id=uuid.uuid4()),  # type: ignore[arg-type]
        config.id,
        AgentConfigUpdate(description="新描述"),
    )
    assert result.description == "新描述"
    assert result.draft_revision == 2
    assert result.published_version == 1
