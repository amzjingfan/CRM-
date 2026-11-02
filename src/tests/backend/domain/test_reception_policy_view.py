"""接待投递资格只作当前配置投影，不能冒充实际送达。"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.reception import service
from app.reception.schemas import PolicyCreate, PolicyUpdate
from app.shared.config.settings import Settings


def row(**changes):
    return SimpleNamespace(
        **{
            "id": uuid.uuid4(),
            "kind": "welcome",
            "name": "Welcome",
            "content": "您好",
            "content_en": "Hello",
            "delivery_mode": "auto",
            "welcome_idle_hours": 24,
            "revision": 1,
            "authorized_by": uuid.uuid4(),
            "timeout_minutes": None,
            "valid_from": None,
            "valid_to": None,
            "schedule": None,
            "enabled": True,
            "sort_order": 0,
            "store_ids": [uuid.uuid4()],
            **changes,
        }
    )


def configure(monkeypatch, policy, master=True):
    current = Settings(_env_file=None).model_copy(
        update={"real_tiktok_automation_enabled": master, "auto_reply_enabled": True}
    )
    monkeypatch.setattr(service, "get_settings", lambda: current)
    monkeypatch.setattr(service, "_ensure_stores", AsyncMock())
    monkeypatch.setattr(service, "_ensure_permission", AsyncMock())
    monkeypatch.setattr(service, "_permission_store_ids", AsyncMock(return_value=set(policy.store_ids)))
    monkeypatch.setattr(service, "query_policies", AsyncMock(return_value=([policy], 1)))
    monkeypatch.setattr(service, "visible_policy", AsyncMock(return_value=policy))
    return current


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "master,auto_reply,mode,enabled,expected",
    [
        (True, True, "auto", True, True),
        (False, True, "auto", True, False),
        (True, False, "auto", True, False),
        (True, True, "preview", True, False),
        (True, True, "off", True, False),
        (True, True, "auto", False, False),
    ],
)
async def test_list_projects_current_master_and_mode_without_claiming_delivery(
    monkeypatch, master, auto_reply, mode, enabled, expected
):
    policy = row(delivery_mode=mode, enabled=enabled)
    current = configure(monkeypatch, policy, master)
    current.auto_reply_enabled = auto_reply
    page = await service.list_policies(
        object(), SimpleNamespace(id=uuid.uuid4()), policy.store_ids[0], "welcome", 1, 20
    )
    result = page.items[0]
    assert result.delivery_enabled is expected
    assert result.authorized_by == policy.authorized_by
    assert "send_performed" not in result.model_dump()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["create", "update"])
async def test_replay_recomputes_master_and_current_policy_but_preserves_original_authorizer(monkeypatch, operation):
    policy = row()
    current = configure(monkeypatch, policy)
    origin = uuid.uuid4()
    stored = {**vars(policy), "authorized_by": str(origin), "delivery_enabled": False}
    monkeypatch.setattr(service, "_replay", AsyncMock(return_value=stored))
    actor = SimpleNamespace(id=uuid.uuid4())
    create = PolicyCreate(
        kind="welcome", name="Welcome", content="Hello", enabled=True, delivery_mode="auto", store_ids=policy.store_ids
    )
    session = SimpleNamespace(refresh=AsyncMock())

    async def replay():
        if operation == "create":
            return await service.create_policy(session, actor, create, "same-key")
        return await service.update_policy(session, actor, policy.id, PolicyUpdate(enabled=True), "same-key")

    assert (await replay()).delivery_enabled is True
    assert (await replay()).authorized_by == origin
    stored["delivery_enabled"] = True
    current.auto_reply_enabled = False
    assert (await replay()).delivery_enabled is False
    current.auto_reply_enabled = True
    current.real_tiktok_automation_enabled = False
    assert (await replay()).delivery_enabled is False
    current.real_tiktok_automation_enabled = True
    policy.enabled = False
    assert (await replay()).delivery_enabled is False
    assert stored["delivery_enabled"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["create", "update"])
async def test_fresh_write_projects_qualification_and_returns_authorizing_user(monkeypatch, operation):
    policy = row()
    configure(monkeypatch, policy)
    monkeypatch.setattr(service, "_replay", AsyncMock(return_value=None))
    committed = []

    async def commit(*args, **kwargs):
        committed.append(kwargs["response_body"])
        return kwargs["response_body"]

    monkeypatch.setattr(service, "_commit", commit)
    session = SimpleNamespace(add=Mock(), refresh=AsyncMock())
    actor = SimpleNamespace(id=uuid.uuid4())
    if operation == "create":
        result = await service.create_policy(
            session,
            actor,
            PolicyCreate(
                kind="welcome",
                name="Welcome",
                content="Hello",
                enabled=True,
                delivery_mode="auto",
                store_ids=policy.store_ids,
            ),
            "new-key",
        )
    else:
        result = await service.update_policy(session, actor, policy.id, PolicyUpdate(enabled=True), "new-key")
    assert result.delivery_enabled is True and result.authorized_by == actor.id
    assert committed[0]["delivery_enabled"] is True and committed[0]["authorized_by"] == str(actor.id)


@pytest.mark.asyncio
async def test_commit_race_replay_is_projected_against_current_policy(monkeypatch):
    policy = row()
    configure(monkeypatch, policy)
    origin = policy.authorized_by
    stored = {**vars(policy), "delivery_enabled": False}
    monkeypatch.setattr(service, "_replay", AsyncMock(return_value=None))

    async def concurrent_replay(*args, **kwargs):
        policy.enabled = False
        return stored

    monkeypatch.setattr(service, "_commit", concurrent_replay)
    result = await service.update_policy(
        SimpleNamespace(refresh=AsyncMock()),
        SimpleNamespace(id=uuid.uuid4()),
        policy.id,
        PolicyUpdate(enabled=True),
        "concurrent-key",
    )
    assert result.delivery_enabled is False and result.authorized_by == origin
