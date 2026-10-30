"""同一账号在不同店铺的角色不能互相借用操作权限。"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.store_access import allowed_store_ids_for_permission
from app.shared.exceptions.errors import AppError, ErrorCode
from app.tools import executor as tool_executor
from app.tools.executor import SqlAlchemyToolExecutor, ToolDispatchError
from app.workspace import service as workspace_service


@pytest.mark.asyncio
async def test_reply_scope_uses_the_role_on_each_store() -> None:
    store_a, store_b = uuid.uuid4(), uuid.uuid4()
    user = SimpleNamespace(id=uuid.uuid4())
    session = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [("agent", store_b)])),
    )

    allowed = await allowed_store_ids_for_permission(session, user, "workspace.reply")

    assert allowed == {store_b}
    query = session.execute.await_args.args[0]
    assert "workspace.reply" in query.compile().params.values()
    assert store_a not in allowed


@pytest.mark.asyncio
async def test_permission_without_store_assignment_grants_no_store() -> None:
    user = SimpleNamespace(id=uuid.uuid4())
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [])))

    assert await allowed_store_ids_for_permission(session, user, "workspace.reply") == set()


@pytest.mark.asyncio
async def test_global_admin_keeps_all_active_store_access() -> None:
    store_a, store_b = uuid.uuid4(), uuid.uuid4()
    user = SimpleNamespace(id=uuid.uuid4())
    session = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [("admin", None)])),
        scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: [store_a, store_b])),
    )

    assert await allowed_store_ids_for_permission(session, user, "workspace.reply") == {store_a, store_b}


@pytest.mark.asyncio
async def test_workspace_list_only_queries_stores_with_view_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    supervisor_store, agent_store = uuid.uuid4(), uuid.uuid4()
    user = SimpleNamespace(id=uuid.uuid4())
    session = Mock(spec=AsyncSession)

    async def scoped_stores(_session: object, _user: object, permission_code: str | None = None) -> set[uuid.UUID]:
        return {agent_store} if permission_code == "workspace.view" else {supervisor_store, agent_store}

    listing = AsyncMock(return_value=([], 0))
    monkeypatch.setattr(workspace_service, "allowed_store_ids", scoped_stores)
    monkeypatch.setattr(workspace_service, "supervised_store_ids", AsyncMock(return_value={agent_store}))
    monkeypatch.setattr(workspace_service, "list_conversations", listing)
    monkeypatch.setattr(workspace_service, "unread_message_total", AsyncMock(return_value=0))

    await workspace_service.get_session_list(session, user, "all", None, None, None, 1, 20)

    assert listing.await_args.args[1] == {agent_store}


@pytest.mark.asyncio
async def test_manual_send_checks_reply_scope_of_the_conversation_store(monkeypatch: pytest.MonkeyPatch) -> None:
    supervisor_store, agent_store = uuid.uuid4(), uuid.uuid4()
    user = SimpleNamespace(id=uuid.uuid4())
    session = Mock(spec=AsyncSession)

    async def scoped_stores(_session: object, _user: object, permission_code: str | None = None) -> set[uuid.UUID]:
        return {agent_store} if permission_code == "workspace.reply" else {supervisor_store, agent_store}

    lookup = AsyncMock(return_value=None)
    monkeypatch.setattr(workspace_service, "allowed_store_ids", scoped_stores)
    monkeypatch.setattr(workspace_service, "find_conversation", lookup)

    with pytest.raises(AppError) as denied:
        await workspace_service.send_agent_message(session, user, uuid.uuid4(), "hello", "request-1", confirmed=True)

    assert denied.value.code == ErrorCode.RESOURCE_NOT_FOUND
    assert lookup.await_args.args[2] == {agent_store}


@pytest.mark.asyncio
async def test_manual_transfer_checks_transfer_scope_of_the_conversation_store(monkeypatch: pytest.MonkeyPatch) -> None:
    other_store, own_store = uuid.uuid4(), uuid.uuid4()
    user = SimpleNamespace(id=uuid.uuid4())
    session = Mock(spec=AsyncSession)

    async def scoped_stores(_session: object, _user: object, permission_code: str | None = None) -> set[uuid.UUID]:
        return {own_store} if permission_code == "workspace.transfer" else {other_store, own_store}

    lookup = AsyncMock(return_value=None)
    monkeypatch.setattr(workspace_service, "allowed_store_ids", scoped_stores)
    monkeypatch.setattr(workspace_service, "find_conversation", lookup)

    with pytest.raises(AppError) as denied:
        await workspace_service.transfer_session(session, user, uuid.uuid4(), "handoff", None, "request-2")

    assert denied.value.code == ErrorCode.RESOURCE_NOT_FOUND
    assert lookup.await_args.args[2] == {own_store}


@pytest.mark.asyncio
async def test_order_lookup_checks_view_scope_of_the_order_store(monkeypatch: pytest.MonkeyPatch) -> None:
    other_store, own_store = uuid.uuid4(), uuid.uuid4()
    user = SimpleNamespace(id=uuid.uuid4())
    session = Mock(spec=AsyncSession)

    async def scoped_stores(_session: object, _user: object, permission_code: str | None = None) -> set[uuid.UUID]:
        return {own_store} if permission_code == "workspace.view" else {other_store, own_store}

    lookup = AsyncMock(return_value=None)
    monkeypatch.setattr(workspace_service, "allowed_store_ids", scoped_stores)
    monkeypatch.setattr(workspace_service, "find_order", lookup)

    with pytest.raises(AppError) as denied:
        await workspace_service.get_order(session, user, "order-1")

    assert denied.value.code == ErrorCode.RESOURCE_NOT_FOUND
    assert lookup.await_args.args[2] == {own_store}


@pytest.mark.asyncio
async def test_assignee_list_checks_transfer_scope_of_the_conversation_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    other_store, own_store = uuid.uuid4(), uuid.uuid4()
    user = SimpleNamespace(id=uuid.uuid4())
    session = Mock(spec=AsyncSession)

    async def scoped_stores(_session: object, _user: object, permission_code: str | None = None) -> set[uuid.UUID]:
        return {own_store} if permission_code == "workspace.transfer" else {other_store, own_store}

    lookup = AsyncMock(return_value=None)
    monkeypatch.setattr(workspace_service, "allowed_store_ids", scoped_stores)
    monkeypatch.setattr(workspace_service, "find_conversation", lookup)

    with pytest.raises(AppError) as denied:
        await workspace_service.list_session_assignees(session, user, uuid.uuid4())

    assert denied.value.code == ErrorCode.RESOURCE_NOT_FOUND
    assert lookup.await_args.args[2] == {own_store}


@pytest.mark.asyncio
@pytest.mark.parametrize("permission_code", ["workspace.reply", "workspace.transfer"])
async def test_tool_execution_rechecks_store_permission_after_preflight(
    monkeypatch: pytest.MonkeyPatch, permission_code: str
) -> None:
    actor_id, store_id = uuid.uuid4(), uuid.uuid4()
    session = Mock(spec=AsyncSession)
    session.get = AsyncMock(return_value=SimpleNamespace(id=actor_id, status="active"))
    scope = AsyncMock(return_value=set())
    monkeypatch.setattr(tool_executor, "allowed_store_ids", scope)
    invocation = SimpleNamespace(context=SimpleNamespace(actor_type="user", actor_id=actor_id))
    conversation = SimpleNamespace(store_id=store_id, assigned_user_id=actor_id)

    with pytest.raises(ToolDispatchError) as denied:
        await SqlAlchemyToolExecutor(session)._verify_user_owner(invocation, conversation, permission_code)

    assert denied.value.error_code == "TOOL_OWNER_MISMATCH"
    scope.assert_awaited_once_with(session, session.get.return_value, permission_code)
