"""验证 SQLAlchemy 工具执行器的超时和输出失败关闭策略。"""

import asyncio
import time
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversations.models import Message
from app.tools import executor as executor_module
from app.tools.contracts import (
    TOOL_DEFINITIONS,
    SendPlatformMessageArguments,
    ToolExecutionContext,
    ToolInvocation,
)
from app.tools.executor import SqlAlchemyToolExecutor, ToolDispatchError, ToolDispatchOutcome


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "arguments", "permission", "expected_status", "expected_error"),
    [
        ("query_order", {"order_id": "ORDER-001"}, "orders.view", "timeout", "TOOL_TIMEOUT"),
        (
            "send_platform_message",
            {"conversation_id": str(uuid.uuid4()), "content": "approved message"},
            "workspace.reply",
            "unknown",
            "TOOL_RESULT_UNKNOWN",
        ),
    ],
)
async def test_timeout_is_failure_closed_without_automatic_write_retry(
    monkeypatch: pytest.MonkeyPatch,
    tool_name: str,
    arguments: dict[str, object],
    permission: str,
    expected_status: str,
    expected_error: str,
) -> None:
    """普通查询超时明确失败，平台写超时则标记结果未知。"""
    call = SimpleNamespace(
        id=uuid.uuid4(),
        status="running",
        output_summary=None,
        error_code=None,
        mocked=False,
    )
    session = Mock(spec=AsyncSession)
    session.rollback = AsyncMock()
    session.get = AsyncMock(return_value=call)
    finish = AsyncMock()
    monkeypatch.setattr(
        executor_module,
        "begin_tool_call",
        AsyncMock(return_value=(call, False, time.perf_counter())),
    )
    monkeypatch.setattr(executor_module, "finish_tool_call", finish)
    definition = TOOL_DEFINITIONS[tool_name]
    monkeypatch.setitem(
        TOOL_DEFINITIONS,
        tool_name,
        definition.model_copy(update={"timeout_ms": 1}),
    )
    executor = SqlAlchemyToolExecutor(session)

    async def slow_dispatch(*_: object) -> ToolDispatchOutcome:
        await asyncio.sleep(0.05)
        raise AssertionError("超时任务不应完成")

    monkeypatch.setattr(executor, "_dispatch", slow_dispatch)
    result = await executor.execute(
        ToolInvocation(
            tool_name=tool_name,  # type: ignore[arg-type]
            idempotency_key=f"timeout-{uuid.uuid4().hex}",
            arguments=arguments,
            context=ToolExecutionContext(
                store_id=uuid.uuid4(),
                actor_type="agent",
                permissions={permission},
            ),
        )
    )

    assert result.status == expected_status
    assert result.error_code == expected_error
    session.rollback.assert_awaited_once()
    finish.assert_awaited_once()


@pytest.mark.asyncio
async def test_invalid_success_output_is_not_exposed_to_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    """执行器内部返回结构不符契约时必须记录失败，不能把污染数据交给 Agent。"""
    call = SimpleNamespace(id=uuid.uuid4())
    session = Mock(spec=AsyncSession)
    monkeypatch.setattr(
        executor_module,
        "begin_tool_call",
        AsyncMock(return_value=(call, False, time.perf_counter())),
    )
    executor = SqlAlchemyToolExecutor(session)
    monkeypatch.setattr(
        executor,
        "_dispatch",
        AsyncMock(
            return_value=ToolDispatchOutcome(
                status="succeeded",
                data={"untrusted": "shape"},
                output_summary=None,
            )
        ),
    )
    finish_after_error = AsyncMock()
    monkeypatch.setattr(executor, "_finish_after_error", finish_after_error)

    result = await executor.execute(
        ToolInvocation(
            tool_name="query_order",
            idempotency_key=f"invalid-output-{uuid.uuid4().hex}",
            arguments={"order_id": "ORDER-001"},
            context=ToolExecutionContext(
                store_id=uuid.uuid4(),
                actor_type="agent",
                permissions={"orders.view"},
            ),
        )
    )

    assert result.status == "failed"
    assert result.error_code == "TOOL_OUTPUT_INVALID"
    assert result.data is None
    finish_after_error.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "arguments", "permission", "summary"),
    [
        (
            "query_order",
            {"order_id": "ORDER-READ-REPLAY"},
            "orders.view",
            {"order_id": str(uuid.uuid4()), "status": "paid"},
        ),
        (
            "query_logistics",
            {"order_id": "ORDER-READ-REPLAY"},
            "orders.view",
            {"order_id": str(uuid.uuid4()), "tracking_status": "in_transit"},
        ),
        (
            "query_customer_profile",
            {"customer_id": str(uuid.uuid4())},
            "workspace.view",
            {"customer_id": str(uuid.uuid4()), "order_count": 2},
        ),
    ],
)
async def test_replayed_read_uses_versioned_low_sensitive_contract(
    monkeypatch: pytest.MonkeyPatch,
    tool_name: str,
    arguments: dict[str, object],
    permission: str,
    summary: dict[str, object],
) -> None:
    """同一 Agent Run 恢复只读调用时，应返回首次查询的低敏事实快照。"""
    call = SimpleNamespace(
        id=uuid.uuid4(),
        status="succeeded",
        output_summary=summary,
        error_code=None,
        mocked=False,
    )
    monkeypatch.setattr(
        executor_module,
        "begin_tool_call",
        AsyncMock(return_value=(call, True, time.perf_counter())),
    )

    result = await SqlAlchemyToolExecutor(Mock(spec=AsyncSession)).execute(
        ToolInvocation(
            tool_name=tool_name,  # type: ignore[arg-type]
            idempotency_key=f"read-replay-{uuid.uuid4().hex}",
            arguments=arguments,
            context=ToolExecutionContext(
                store_id=uuid.uuid4(),
                actor_type="agent",
                permissions={permission},
            ),
        )
    )

    assert result.status == "succeeded"
    assert result.error_code is None
    assert result.data == summary
    assert result.replayed is True
    assert result.replay_contract_version == 1


@pytest.mark.asyncio
async def test_replayed_read_rechecks_current_permission_without_overwriting_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """已撤销查询权限时不得借历史幂等键读取摘要，也不得改写原成功审计。"""
    call = SimpleNamespace(
        id=uuid.uuid4(),
        status="succeeded",
        output_summary={"order_id": str(uuid.uuid4()), "status": "paid"},
        error_code=None,
        mocked=False,
    )
    finish = AsyncMock()
    monkeypatch.setattr(
        executor_module,
        "begin_tool_call",
        AsyncMock(return_value=(call, True, time.perf_counter())),
    )
    monkeypatch.setattr(executor_module, "finish_tool_call", finish)

    result = await SqlAlchemyToolExecutor(Mock(spec=AsyncSession)).execute(
        ToolInvocation(
            tool_name="query_order",
            idempotency_key=f"read-replay-denied-{uuid.uuid4().hex}",
            arguments={"order_id": "ORDER-READ-REPLAY"},
            context=ToolExecutionContext(
                store_id=uuid.uuid4(),
                actor_type="agent",
                permissions=set(),
            ),
        )
    )

    assert result.status == "failed"
    assert result.error_code == "TOOL_PERMISSION_DENIED"
    assert result.data is None
    assert result.replayed is True
    finish.assert_not_awaited()


@pytest.mark.asyncio
async def test_replayed_read_rejects_fields_outside_low_sensitive_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """重放摘要不能夹带完整订单字段来扩大 Agent 可见数据。"""
    call = SimpleNamespace(
        id=uuid.uuid4(),
        status="succeeded",
        output_summary={
            "order_id": str(uuid.uuid4()),
            "status": "paid",
            "external_order_id": "MUST-NOT-REPLAY",
        },
        error_code=None,
        mocked=False,
    )
    monkeypatch.setattr(
        executor_module,
        "begin_tool_call",
        AsyncMock(return_value=(call, True, time.perf_counter())),
    )

    result = await SqlAlchemyToolExecutor(Mock(spec=AsyncSession)).execute(
        ToolInvocation(
            tool_name="query_order",
            idempotency_key=f"read-replay-extra-{uuid.uuid4().hex}",
            arguments={"order_id": "ORDER-READ-REPLAY"},
            context=ToolExecutionContext(
                store_id=uuid.uuid4(),
                actor_type="agent",
                permissions={"orders.view"},
            ),
        )
    )

    assert result.status == "failed"
    assert result.error_code == "TOOL_OUTPUT_INVALID"
    assert result.data is None
    assert result.replayed is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "arguments", "permission", "summary"),
    [
        (
            "update_shipping_address",
            {
                "order_id": "ORDER-REPLAY-ADDRESS",
                "recipient_name": "测试收件人",
                "phone": None,
                "address_line1": "测试地址",
                "address_line2": None,
                "city": "测试城市",
                "region": None,
                "postal_code": "100000",
                "country_code": "CN",
            },
            "orders.address.update",
            {"order_id": str(uuid.uuid4()), "status": "pending_confirmation"},
        ),
        (
            "send_coupon",
            {
                "customer_id": str(uuid.uuid4()),
                "coupon_code": "REPLAY10",
                "description": None,
                "expires_at": None,
            },
            "coupons.issue",
            {"issuance_id": str(uuid.uuid4()), "status": "issued"},
        ),
        (
            "send_platform_message",
            {"conversation_id": str(uuid.uuid4()), "content": "已批准消息"},
            "workspace.reply",
            {"message_id": str(uuid.uuid4()), "status": "sent"},
        ),
    ],
)
async def test_replayed_write_with_incomplete_summary_returns_unknown(
    monkeypatch: pytest.MonkeyPatch,
    tool_name: str,
    arguments: dict[str, object],
    permission: str,
    summary: dict[str, object],
) -> None:
    """历史低敏摘要无法恢复完整写结果时，重放必须返回未知而非伪装成功。"""
    call = SimpleNamespace(
        id=uuid.uuid4(),
        status="succeeded",
        output_summary=summary,
        error_code=None,
        mocked=True,
    )
    session = Mock(spec=AsyncSession)
    monkeypatch.setattr(
        executor_module,
        "begin_tool_call",
        AsyncMock(return_value=(call, True, time.perf_counter())),
    )

    result = await SqlAlchemyToolExecutor(session).execute(
        ToolInvocation(
            tool_name=tool_name,  # type: ignore[arg-type]
            idempotency_key=f"replay-incomplete-{uuid.uuid4().hex}",
            arguments=arguments,
            context=ToolExecutionContext(
                store_id=uuid.uuid4(),
                actor_type="agent",
                permissions={permission},
            ),
        )
    )

    assert result.status == "unknown"
    assert result.error_code == "TOOL_RESULT_UNKNOWN"
    assert result.data is None
    assert result.mocked is True
    assert result.replayed is True


@pytest.mark.asyncio
async def test_write_success_with_invalid_replay_summary_is_marked_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """新写操作在落库前必须验证重放摘要，防止继续制造不可恢复的成功记录。"""
    call = SimpleNamespace(id=uuid.uuid4())
    session = Mock(spec=AsyncSession)
    monkeypatch.setattr(
        executor_module,
        "begin_tool_call",
        AsyncMock(return_value=(call, False, time.perf_counter())),
    )
    finish_after_error = AsyncMock()
    executor = SqlAlchemyToolExecutor(session)
    monkeypatch.setattr(executor, "_finish_after_error", finish_after_error)
    monkeypatch.setattr(
        executor,
        "_dispatch",
        AsyncMock(
            return_value=ToolDispatchOutcome(
                status="succeeded",
                data={"order_id": str(uuid.uuid4()), "status": "pending_confirmation", "mocked": True},
                # 缺少 mocked，不能作为未来幂等重放的强类型结果。
                output_summary={"order_id": str(uuid.uuid4()), "status": "pending_confirmation"},
                mocked=True,
            )
        ),
    )

    result = await executor.execute(
        ToolInvocation(
            tool_name="update_shipping_address",
            idempotency_key=f"invalid-replay-summary-{uuid.uuid4().hex}",
            arguments={
                "order_id": "ORDER-REPLAY-SUMMARY",
                "recipient_name": "测试收件人",
                "phone": None,
                "address_line1": "测试地址",
                "address_line2": None,
                "city": "测试城市",
                "region": None,
                "postal_code": "100000",
                "country_code": "CN",
            },
            context=ToolExecutionContext(
                store_id=uuid.uuid4(),
                actor_type="agent",
                permissions={"orders.address.update"},
            ),
        )
    )

    assert result.status == "unknown"
    assert result.error_code == "TOOL_RESULT_UNKNOWN"
    assert result.data is None
    finish_after_error.assert_awaited_once()


@pytest.mark.asyncio
async def test_uncertain_platform_send_updates_persisted_message_for_manual_reconciliation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """工具超时后已创建消息不能永久停留在 processing。"""
    store_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    key = f"manual-unknown-{uuid.uuid4().hex}"
    message = Message(
        id=uuid.uuid4(),
        store_id=store_id,
        conversation_id=conversation_id,
        platform="tiktok",
        external_message_id=f"pending-{uuid.uuid4()}",
        role="agent",
        direction="outbound",
        content="approved message",
        idempotency_key=key,
        status="processing",
        raw_payload={"delivery_mode": "unknown"},
    )
    call = SimpleNamespace(id=uuid.uuid4())
    session = Mock(spec=AsyncSession)
    session.rollback = AsyncMock()
    session.scalar = AsyncMock(return_value=message)
    session.get = AsyncMock(return_value=call)
    session.add = Mock()
    finish = AsyncMock()
    monkeypatch.setattr(executor_module, "finish_tool_call", finish)
    invocation = ToolInvocation(
        tool_name="send_platform_message",
        idempotency_key=key,
        arguments={"conversation_id": str(conversation_id), "content": "approved message"},
        context=ToolExecutionContext(
            store_id=store_id,
            actor_type="user",
            actor_id=uuid.uuid4(),
            permissions={"workspace.reply"},
            human_confirmed=True,
        ),
    )

    await SqlAlchemyToolExecutor(session)._finish_after_error(
        call.id,
        time.perf_counter(),
        "unknown",
        "TOOL_RESULT_UNKNOWN",
        invocation,
    )

    assert message.status == "unknown"
    assert message.error_code == "TOOL_RESULT_UNKNOWN"
    assert message.raw_payload == {"delivery_mode": "unknown"}
    session.add.assert_called_once()
    finish.assert_awaited_once()


@pytest.mark.asyncio
async def test_real_message_write_is_blocked_until_previous_unknown_is_reconciled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同店铺存在 unknown 时不得继续制造新的真实平台副作用。"""
    store_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    conversation = SimpleNamespace(
        id=conversation_id,
        store_id=store_id,
        platform="tiktok",
        external_conversation_id="710688832392260838",
    )
    channel = SimpleNamespace(status="connected")
    session = Mock(spec=AsyncSession)
    session.scalar = AsyncMock(side_effect=[conversation, channel, store_id, uuid.uuid4()])
    session.add = Mock()
    adapter = SimpleNamespace(real_writes=True)
    monkeypatch.setattr(executor_module, "get_message_adapter", lambda _platform: adapter)
    monkeypatch.setattr(
        executor_module,
        "get_settings",
        lambda: SimpleNamespace(
            real_tiktok_message_write_enabled=True,
            tiktok_message_write_allowed_conversation_id="710688832392260838",
            tiktok_message_write_allowed_store_ids=None,
        ),
    )
    invocation = ToolInvocation(
        tool_name="send_platform_message",
        idempotency_key=str(uuid.uuid4()),
        arguments={"conversation_id": str(conversation_id), "content": "approved message"},
        context=ToolExecutionContext(
            store_id=store_id,
            actor_type="user",
            actor_id=uuid.uuid4(),
            permissions={"workspace.reply"},
            human_confirmed=True,
        ),
    )

    with pytest.raises(ToolDispatchError, match="TOOL_RECONCILIATION_REQUIRED"):
        await SqlAlchemyToolExecutor(session)._send_platform_message(
            invocation,
            uuid.uuid4(),
            SendPlatformMessageArguments(conversation_id=conversation_id, content="approved message"),
        )

    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_direct_tool_send_rejects_store_outside_real_write_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """绕过工作台直接调用工具也不能向未放行店铺创建消息。"""
    store_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    conversation = SimpleNamespace(
        id=conversation_id,
        store_id=store_id,
        platform="tiktok",
        external_conversation_id="710688832392260838",
    )
    session = Mock(spec=AsyncSession)
    session.scalar = AsyncMock(side_effect=[conversation, SimpleNamespace(status="connected")])
    session.add = Mock()
    adapter = SimpleNamespace(real_writes=True, send_message=AsyncMock())
    monkeypatch.setattr(executor_module, "get_message_adapter", lambda _platform: adapter)
    monkeypatch.setattr(
        executor_module,
        "get_settings",
        lambda: SimpleNamespace(
            real_tiktok_message_write_enabled=True,
            tiktok_message_write_allowed_conversation_id=None,
            tiktok_message_write_allowed_store_ids=str(uuid.uuid4()),
        ),
    )
    invocation = ToolInvocation(
        tool_name="send_platform_message",
        idempotency_key=str(uuid.uuid4()),
        arguments={"conversation_id": str(conversation_id), "content": "approved message"},
        context=ToolExecutionContext(
            store_id=store_id,
            actor_type="user",
            actor_id=uuid.uuid4(),
            permissions={"workspace.reply"},
            human_confirmed=True,
        ),
    )

    with pytest.raises(ToolDispatchError, match="TOOL_PLATFORM_DISABLED"):
        await SqlAlchemyToolExecutor(session)._send_platform_message(
            invocation,
            uuid.uuid4(),
            SendPlatformMessageArguments(conversation_id=conversation_id, content="approved message"),
        )
    session.add.assert_not_called()
    adapter.send_message.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("actor_type", "actor_id", "human_confirmed"),
    [
        ("agent", uuid.uuid4(), True),
        ("job", uuid.uuid4(), True),
        ("user", None, True),
        ("user", uuid.uuid4(), False),
    ],
)
async def test_real_message_write_requires_human_user_identity_and_confirmation(
    monkeypatch: pytest.MonkeyPatch,
    actor_type: str,
    actor_id: uuid.UUID | None,
    human_confirmed: bool,
) -> None:
    """真实写入必须同时具备人工用户身份、可审计操作者和当次确认。"""
    store_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    conversation = SimpleNamespace(
        id=conversation_id,
        store_id=store_id,
        platform="tiktok",
        external_conversation_id="710688832392260838",
    )
    channel = SimpleNamespace(status="connected")
    session = Mock(spec=AsyncSession)
    session.scalar = AsyncMock(side_effect=[conversation, channel])
    session.add = Mock()
    adapter = SimpleNamespace(real_writes=True, send_message=AsyncMock())
    monkeypatch.setattr(executor_module, "get_message_adapter", lambda _platform: adapter)
    monkeypatch.setattr(
        executor_module,
        "get_settings",
        lambda: SimpleNamespace(
            real_tiktok_message_write_enabled=True,
            tiktok_message_write_allowed_conversation_id="710688832392260838",
            tiktok_message_write_allowed_store_ids=None,
        ),
    )
    invocation = ToolInvocation(
        tool_name="send_platform_message",
        idempotency_key=str(uuid.uuid4()),
        arguments={"conversation_id": str(conversation_id), "content": "forged approval"},
        context=ToolExecutionContext(
            store_id=store_id,
            actor_type=actor_type,  # type: ignore[arg-type]
            actor_id=actor_id,
            permissions={"workspace.reply"},
            human_confirmed=human_confirmed,
        ),
    )

    with pytest.raises(ToolDispatchError, match="TOOL_HUMAN_CONFIRMATION_REQUIRED"):
        await SqlAlchemyToolExecutor(session)._send_platform_message(
            invocation,
            uuid.uuid4(),
            SendPlatformMessageArguments(conversation_id=conversation_id, content="forged approval"),
        )

    session.add.assert_not_called()
    adapter.send_message.assert_not_awaited()
