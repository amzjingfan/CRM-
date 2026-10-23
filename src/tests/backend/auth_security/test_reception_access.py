"""接待配置的店铺与个人边界。"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.reception import service
from app.shared.exceptions.errors import AppError


@pytest.mark.asyncio
async def test_cross_store_list_is_hidden(monkeypatch: pytest.MonkeyPatch) -> None:
    actor = SimpleNamespace(id=uuid.uuid4(), roles=[])
    session = SimpleNamespace()
    monkeypatch.setattr(service, "allowed_store_ids", AsyncMock(return_value={uuid.uuid4()}))
    with pytest.raises(AppError) as error:
        await service.list_groups(session, actor, uuid.uuid4(), "personal", 1, 20)
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_personal_group_of_other_user_is_hidden(monkeypatch: pytest.MonkeyPatch) -> None:
    store_id = uuid.uuid4()
    actor = SimpleNamespace(id=uuid.uuid4(), roles=[])
    group = SimpleNamespace(id=uuid.uuid4(), store_id=store_id, scope="personal", owner_user_id=uuid.uuid4())
    session = SimpleNamespace()
    monkeypatch.setattr(service, "allowed_store_ids", AsyncMock(return_value={store_id}))
    monkeypatch.setattr(service, "find_group", AsyncMock(return_value=group))
    with pytest.raises(AppError) as error:
        await service.visible_group(session, actor, group.id, "workspace.reply")
    assert error.value.status_code == 404
