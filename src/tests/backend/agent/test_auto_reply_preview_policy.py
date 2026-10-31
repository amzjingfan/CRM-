"""店铺级预演策略默认关闭，修改必须有权限、版本和可运行 Agent。"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.management import auto_reply_preview
from app.agents.management.auto_reply_preview import AutoReplyPreviewUpdate
from app.shared.exceptions.errors import AppError
from app.stores.models import Store


@pytest.mark.asyncio
async def test_preview_policy_enables_only_with_published_agent_and_records_actor(monkeypatch) -> None:
    store_id, actor_id = uuid.uuid4(), uuid.uuid4()
    store = Store(id=store_id, name="测试店", code="test", status="active", metadata_json={})
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[store, uuid.uuid4()]), add=MagicMock(), commit=AsyncMock())
    user = SimpleNamespace(id=actor_id)
    monkeypatch.setattr(auto_reply_preview, "allowed_store_ids", AsyncMock(return_value={store_id}))

    policy = await auto_reply_preview.set_policy(
        session, user, store_id, AutoReplyPreviewUpdate(enabled=True, expected_revision=0)
    )
    assert policy.enabled and policy.revision == 1 and policy.mode == "review_preview"
    assert store.metadata_json["agent_auto_reply_preview"] == {
        "enabled": True,
        "revision": 1,
        "actor_id": str(actor_id),
    }
    session.add.assert_called_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_preview_policy_rejects_cross_store_and_stale_revision(monkeypatch) -> None:
    store_id = uuid.uuid4()
    session = SimpleNamespace(scalar=AsyncMock(), add=MagicMock(), commit=AsyncMock())
    user = SimpleNamespace(id=uuid.uuid4())
    monkeypatch.setattr(auto_reply_preview, "allowed_store_ids", AsyncMock(return_value=set()))
    with pytest.raises(AppError):
        await auto_reply_preview.set_policy(
            session, user, store_id, AutoReplyPreviewUpdate(enabled=True, expected_revision=0)
        )
    session.scalar.assert_not_awaited()

    store = Store(
        id=store_id,
        name="测试店",
        code="test",
        status="active",
        metadata_json={"agent_auto_reply_preview": {"enabled": False, "revision": 2, "actor_id": None}},
    )
    session.scalar = AsyncMock(return_value=store)
    monkeypatch.setattr(auto_reply_preview, "allowed_store_ids", AsyncMock(return_value={store_id}))
    with pytest.raises(AppError):
        await auto_reply_preview.set_policy(
            session, user, store_id, AutoReplyPreviewUpdate(enabled=True, expected_revision=1)
        )
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_preview_cannot_enable_for_operator_without_workspace_access(monkeypatch) -> None:
    store_id = uuid.uuid4()
    store = Store(id=store_id, name="测试店", code="test", status="active", metadata_json={})
    session = SimpleNamespace(scalar=AsyncMock(return_value=store), add=MagicMock(), commit=AsyncMock())
    user = SimpleNamespace(id=uuid.uuid4())

    async def scoped_stores(_session, _user, permission):
        return {store_id} if permission == "agent.manage" else set()

    monkeypatch.setattr(auto_reply_preview, "allowed_store_ids", scoped_stores)
    with pytest.raises(AppError):
        await auto_reply_preview.set_policy(
            session, user, store_id, AutoReplyPreviewUpdate(enabled=True, expected_revision=0)
        )
    session.commit.assert_not_awaited()
