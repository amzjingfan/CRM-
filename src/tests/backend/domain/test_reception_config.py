"""基础接待配置只保存文本，不形成自动发送。"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.auth.dependencies import get_current_user
from app.main import app
from app.reception import service
from app.reception.schemas import GroupView, PolicyCreate, ReplyCreate
from app.shared.config.settings import get_settings
from app.shared.database.session import get_db_session


def test_reception_routes_are_separate_from_campaigns() -> None:
    paths = TestClient(app).get("/openapi.json").json()["paths"]
    for resource in ("groups", "replies", "policies"):
        collection = paths[f"/v1/marketing/reception/{resource}"]
        item = paths[f"/v1/marketing/reception/{resource}/{{item_id}}"]
        assert {"get", "post"}.issubset(collection)
        assert {"patch", "delete"}.issubset(item)
        for method in (collection["post"], item["patch"], item["delete"]):
            assert any(
                parameter["name"] == "Idempotency-Key" and parameter["required"] for parameter in method["parameters"]
            )


def test_reply_rejects_media_oversize_and_invalid_shortcut() -> None:
    payload = {
        "store_id": uuid.uuid4(),
        "scope": "personal",
        "group_id": uuid.uuid4(),
        "shortcut": "1",
        "messages": ["Hello"],
    }
    assert ReplyCreate(**payload).messages == ["Hello"]
    assert ReplyCreate.model_validate(payload | {"shortcut": "Welcome"}).shortcut == "welcome"
    for change in (
        {"messages": ["x" * 2001]},
        {"messages": ["a"] * 6},
        {"messages": [{"type": "image", "url": "https://example.invalid/a"}]},
        {"shortcut": "/1"},
        {"tags": ["a", "b", "c", "d"]},
    ):
        with pytest.raises(ValidationError):
            ReplyCreate.model_validate(payload | change)


def test_policy_rejects_invalid_time_and_autodelivery() -> None:
    now = datetime.now(UTC)
    payload = {
        "kind": "timeout",
        "name": "After delay",
        "content": "Hello",
        "timeout_minutes": 30,
        "store_ids": [uuid.uuid4()],
        "valid_from": now,
        "valid_to": now + timedelta(days=1),
    }
    assert PolicyCreate(**payload).enabled is False
    for change in (
        {"timeout_minutes": 0},
        {"valid_to": now - timedelta(days=1)},
        {"store_ids": []},
        {"delivery_enabled": True},
        {"kind": "welcome", "timeout_minutes": 30},
    ):
        with pytest.raises(ValidationError):
            PolicyCreate.model_validate(payload | change)


def test_group_http_requires_csrf_and_idempotency_key(monkeypatch: pytest.MonkeyPatch) -> None:
    store_id, user_id, group_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    async def current_user() -> object:
        return object()

    async def session() -> object:
        yield object()

    create = AsyncMock(
        return_value=GroupView(
            id=group_id, store_id=store_id, scope="personal", owner_user_id=user_id, name="Test", sort_order=0
        )
    )
    monkeypatch.setattr(service, "create_group", create)
    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_db_session] = session
    try:
        client = TestClient(app)
        path = "/v1/marketing/reception/groups"
        payload = {"store_id": str(store_id), "scope": "personal", "name": "Test"}
        origin = get_settings().cors_origin_list[0]
        headers = {"Origin": origin, "Idempotency-Key": "group-once"}
        client.cookies.set("crm_csrf_token", "test-csrf")
        assert client.post(path, json=payload, headers=headers).status_code == 403
        no_key = client.post(path, json=payload, headers={"Origin": origin, "X-CSRF-Token": "test-csrf"})
        assert no_key.status_code == 422
        response = client.post(path, json=payload, headers=headers | {"X-CSRF-Token": "test-csrf"})
        assert response.status_code == 200
        assert response.json()["data"]["id"] == str(group_id)
        create.assert_awaited_once()
    finally:
        app.dependency_overrides.clear()
