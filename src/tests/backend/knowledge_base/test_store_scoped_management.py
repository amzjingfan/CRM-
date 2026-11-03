"""知识写操作不能借用其他店铺的查看权限。"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.auth import store_access
from app.knowledge_base import service
from app.knowledge_base.schemas import CategoryCreate, CategoryUpdate
from app.shared.exceptions.errors import AppError, ErrorCode


@pytest.mark.asyncio
async def test_create_category_denies_store_without_manage_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    target_store = uuid.uuid4()
    user = SimpleNamespace(id=uuid.uuid4())
    session = SimpleNamespace()

    async def scoped_stores(_session: object, _user: object, permission_code: str | None = None) -> set[uuid.UUID]:
        return set() if permission_code == "knowledge.manage" else {target_store}

    monkeypatch.setattr(store_access, "allowed_store_ids", scoped_stores)
    payload = CategoryCreate(store_id=target_store, name="Policy", code="policy")

    with pytest.raises(AppError) as denied:
        await service.create_category(session, user, payload)

    assert denied.value.code == ErrorCode.RESOURCE_NOT_FOUND


@pytest.mark.asyncio
async def test_update_category_denies_resource_without_manage_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    target_store = uuid.uuid4()
    category_id = uuid.uuid4()
    user = SimpleNamespace(id=uuid.uuid4())
    category = SimpleNamespace(id=category_id, store_id=target_store, name="Original")
    session = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())

    async def scoped_stores(_session: object, _user: object, permission_code: str | None = None) -> set[uuid.UUID]:
        return set() if permission_code == "knowledge.manage" else {target_store}

    async def find_category(_session: object, _id: uuid.UUID, stores: set[uuid.UUID]) -> object | None:
        return category if target_store in stores else None

    monkeypatch.setattr(service, "allowed_store_ids", scoped_stores)
    monkeypatch.setattr(service, "find_category", find_category)

    with pytest.raises(AppError) as denied:
        await service.update_category(session, user, category_id, CategoryUpdate(name="Changed"))

    assert denied.value.code == ErrorCode.RESOURCE_NOT_FOUND
    session.commit.assert_not_awaited()
