"""REAL-AI-02 第三次独立复测样本。

重点验证 DEF-REAL-AI02-003 的历史重放失败关闭、新写结果摘要校验、
Mock 空声明阻断，并检查修复是否破坏只读查询工具的安全重试语义。
"""

import time
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.business_claims import BusinessClaimInventory
from app.agent.reply_safety import ReplyContentOrigin, ReplyEvidenceKind, ReplySafetyPolicy
from app.tools import executor as executor_module
from app.tools.contracts import ToolExecutionContext, ToolInvocation
from app.tools.executor import SqlAlchemyToolExecutor, ToolDispatchOutcome

WRITE_CASES = [
    (
        "update_shipping_address",
        {
            "order_id": "ORDER-003-ADDRESS",
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
        {
            "order_id": "00000000-0000-0000-0000-000000000501",
            "status": "pending_confirmation",
            "mocked": True,
        },
    ),
    (
        "send_coupon",
        {
            "customer_id": "00000000-0000-0000-0000-000000000502",
            "coupon_code": "RETEST003",
            "description": None,
            "expires_at": None,
        },
        "coupons.issue",
        {
            "issuance_id": "00000000-0000-0000-0000-000000000503",
            "coupon_code": "RETEST003",
            "status": "issued",
            "mocked": True,
        },
    ),
    (
        "send_platform_message",
        {
            "conversation_id": "00000000-0000-0000-0000-000000000504",
            "content": "已人工批准的复测消息",
        },
        "workspace.reply",
        {
            "message_id": "00000000-0000-0000-0000-000000000505",
            "status": "sent",
            "mocked": True,
        },
    ),
]


def invocation(
    tool_name: str,
    arguments: dict[str, object],
    permission: str,
    *,
    key: str | None = None,
) -> ToolInvocation:
    """构造只含最小授权信息的受控工具调用。"""
    return ToolInvocation(
        tool_name=tool_name,  # type: ignore[arg-type]
        idempotency_key=key or f"real-ai02-003-{uuid.uuid4().hex}",
        arguments=arguments,
        context=ToolExecutionContext(
            store_id=uuid.uuid4(),
            actor_type="agent",
            permissions={permission},
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(("tool_name", "arguments", "permission", "summary"), WRITE_CASES)
async def test_complete_write_summary_can_be_replayed_without_sensitive_body(
    monkeypatch: pytest.MonkeyPatch,
    tool_name: str,
    arguments: dict[str, object],
    permission: str,
    summary: dict[str, object],
) -> None:
    """补齐后的低敏摘要必须可恢复完整强类型结果且不含消息或地址正文。"""
    call = SimpleNamespace(
        id=uuid.uuid4(),
        status="succeeded",
        output_summary=summary,
        error_code=None,
        mocked=True,
    )
    monkeypatch.setattr(
        executor_module,
        "begin_tool_call",
        AsyncMock(return_value=(call, True, time.perf_counter())),
    )

    result = await SqlAlchemyToolExecutor(Mock(spec=AsyncSession)).execute(invocation(tool_name, arguments, permission))

    assert result.status == "succeeded"
    assert result.data == summary
    assert result.mocked is True
    assert result.replayed is True
    serialized = str(result.data)
    assert "测试地址" not in serialized
    assert "已人工批准的复测消息" not in serialized


@pytest.mark.asyncio
@pytest.mark.parametrize(("tool_name", "arguments", "permission", "summary"), WRITE_CASES)
async def test_historical_incomplete_write_summary_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tool_name: str,
    arguments: dict[str, object],
    permission: str,
    summary: dict[str, object],
) -> None:
    """历史成功摘要缺字段时必须返回 unknown，禁止伪造成功或自动重试。"""
    incomplete = dict(summary)
    incomplete.pop("mocked", None)
    call = SimpleNamespace(
        id=uuid.uuid4(),
        status="succeeded",
        output_summary=incomplete,
        error_code=None,
        mocked=True,
    )
    monkeypatch.setattr(
        executor_module,
        "begin_tool_call",
        AsyncMock(return_value=(call, True, time.perf_counter())),
    )

    result = await SqlAlchemyToolExecutor(Mock(spec=AsyncSession)).execute(invocation(tool_name, arguments, permission))

    assert result.status == "unknown"
    assert result.error_code == "TOOL_RESULT_UNKNOWN"
    assert result.data is None
    assert result.mocked is True
    assert result.replayed is True


@pytest.mark.asyncio
@pytest.mark.parametrize(("tool_name", "arguments", "permission", "summary"), WRITE_CASES)
async def test_new_write_success_persists_only_schema_complete_replay_summary(
    monkeypatch: pytest.MonkeyPatch,
    tool_name: str,
    arguments: dict[str, object],
    permission: str,
    summary: dict[str, object],
) -> None:
    """首次写成功必须先通过完整输出 Schema，再保存可重放摘要。"""
    call = SimpleNamespace(id=uuid.uuid4())
    finish = AsyncMock()
    monkeypatch.setattr(
        executor_module,
        "begin_tool_call",
        AsyncMock(return_value=(call, False, time.perf_counter())),
    )
    monkeypatch.setattr(executor_module, "finish_tool_call", finish)
    executor = SqlAlchemyToolExecutor(Mock(spec=AsyncSession))
    monkeypatch.setattr(
        executor,
        "_dispatch",
        AsyncMock(
            return_value=ToolDispatchOutcome(
                status="succeeded",
                data=summary,
                output_summary=summary,
                mocked=True,
            )
        ),
    )

    result = await executor.execute(invocation(tool_name, arguments, permission))

    assert result.status == "succeeded"
    assert result.data == summary
    assert finish.await_args.args[4] == summary


@pytest.mark.parametrize(
    "answer",
    [
        "渠道已处理完毕，请稍后查看。",
        "This request was completed on the channel side.",
        "相关操作现已落地。",
    ],
)
def test_mock_result_without_authoritative_claims_blocks_alternate_wording(answer: str) -> None:
    """Mock 结果缺少对象级声明时，任何替代表述都必须使用统一原因码失败关闭。"""
    result = ReplySafetyPolicy().evaluate(
        answer,
        evidence_kind=ReplyEvidenceKind.TOOL,
        successful_tools={"send_platform_message"},
        has_mock_result=True,
        claim_inventory=BusinessClaimInventory(complete=True, claims=[]),
        content_origin=ReplyContentOrigin.MODEL_GENERATED,
    )

    assert result.is_safe is False
    assert result.automatic_delivery_allowed is False
    assert "MOCK_COMPLETION_CLAIM" in result.reason_codes


QUERY_CASES = [
    (
        "query_order",
        {"order_id": "ORDER-QUERY-003"},
        "orders.view",
        {"order_id": "00000000-0000-0000-0000-000000000601", "status": "paid"},
    ),
    (
        "query_logistics",
        {"order_id": "ORDER-QUERY-003"},
        "orders.view",
        {
            "order_id": "00000000-0000-0000-0000-000000000602",
            "tracking_status": "in_transit",
        },
    ),
    (
        "query_customer_profile",
        {"customer_id": "00000000-0000-0000-0000-000000000603"},
        "workspace.view",
        {"customer_id": "00000000-0000-0000-0000-000000000603", "order_count": 2},
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("tool_name", "arguments", "permission", "summary"), QUERY_CASES)
async def test_repeated_read_tool_remains_safely_retryable(
    monkeypatch: pytest.MonkeyPatch,
    tool_name: str,
    arguments: dict[str, object],
    permission: str,
    summary: dict[str, object],
) -> None:
    """只读工具按既有契约允许安全重试，不应被低敏审计摘要误判为输出无效。"""
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

    result = await SqlAlchemyToolExecutor(Mock(spec=AsyncSession)).execute(invocation(tool_name, arguments, permission))

    assert result.status == "succeeded"
    assert result.error_code is None
    assert result.replayed is True
