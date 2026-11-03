"""主管知识权限随部门店铺归属变化，且不借用其他店铺角色。"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.auth import store_access


@pytest.mark.asyncio
async def test_supervisor_knowledge_manage_covers_department_stores(monkeypatch: pytest.MonkeyPatch) -> None:
    assigned_store, sibling_store, outside_store = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    user = SimpleNamespace(id=uuid.uuid4())
    session = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [("supervisor", assigned_store)]))
    )
    department_stores = AsyncMock(return_value={assigned_store, sibling_store})
    monkeypatch.setattr(store_access, "_department_supervisor_store_ids", department_stores)

    allowed = await store_access.allowed_store_ids_for_permission(session, user, "knowledge.manage")

    assert allowed == {assigned_store, sibling_store}
    assert outside_store not in allowed
    assert "knowledge.manage" in session.execute.await_args.args[0].compile().params.values()


@pytest.mark.asyncio
async def test_supervisor_loses_knowledge_scope_when_department_membership_is_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assigned_store = uuid.uuid4()
    user = SimpleNamespace(id=uuid.uuid4())
    session = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [("supervisor", assigned_store)]))
    )
    monkeypatch.setattr(store_access, "_department_supervisor_store_ids", AsyncMock(return_value=set()))

    assert await store_access.allowed_store_ids_for_permission(session, user, "knowledge.manage") == set()


@pytest.mark.asyncio
async def test_removed_supervisor_role_does_not_expand_knowledge_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    supervisor_store = uuid.uuid4()
    user = SimpleNamespace(id=uuid.uuid4())
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [])))
    department_stores = AsyncMock(return_value={supervisor_store})
    monkeypatch.setattr(store_access, "_department_supervisor_store_ids", department_stores)

    assert await store_access.allowed_store_ids_for_permission(session, user, "knowledge.manage") == set()
    department_stores.assert_not_awaited()
