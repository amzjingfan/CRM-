"""REAL-AI-02 第四次独立安全复测。

验证只读重放 v1 契约、当前权限复核、结构化证据来源和失败关闭边界。
测试只使用合成 UUID 与状态，不接触真实客户数据、模型或平台。
"""

import time
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.business_claims import BusinessClaimSubjectType
from app.agent.reply_rendering import (
    build_authoritative_tool_claims,
    build_trusted_tool_evidence,
    build_trusted_tool_template,
)
from app.agent.reply_safety import ReplyContentOrigin, ReplyEvidenceKind, ReplySafetyPolicy
from app.agent.tool_execution import ExecutedAgentTool
from app.tools import executor as executor_module
from app.tools.contracts import ToolExecutionContext, ToolInvocation, ToolResult
from app.tools.executor import SqlAlchemyToolExecutor

READ_CASES = [
    (
        "query_order",
        {"order_id": "ORDER-READ-004"},
        "orders.view",
        {"order_id": "00000000-0000-0000-0000-000000000701", "status": "paid"},
    ),
    (
        "query_logistics",
        {"order_id": "ORDER-READ-004"},
        "orders.view",
        {
            "order_id": "00000000-0000-0000-0000-000000000702",
            "tracking_status": "in_transit",
        },
    ),
    (
        "query_customer_profile",
        {"customer_id": "00000000-0000-0000-0000-000000000703"},
        "workspace.view",
        {"customer_id": "00000000-0000-0000-0000-000000000703", "order_count": 2},
    ),
]


def invocation(
    tool_name: str,
    arguments: dict[str, object],
    permission: str,
    *,
    permissions: set[str] | None = None,
) -> ToolInvocation:
    """构造仅包含测试所需身份和权限的受控调用。"""
    return ToolInvocation(
        tool_name=tool_name,  # type: ignore[arg-type]
        idempotency_key=f"real-ai02-004-{uuid.uuid4().hex}",
        arguments=arguments,
        context=ToolExecutionContext(
            store_id=uuid.uuid4(),
            actor_type="agent",
            permissions={permission} if permissions is None else permissions,
        ),
    )


def replay_call(summary: dict[str, object], *, mocked: bool = False) -> SimpleNamespace:
    """构造已持久化的成功低敏调用记录。"""
    return SimpleNamespace(
        id=uuid.uuid4(),
        status="succeeded",
        output_summary=summary,
        error_code=None,
        mocked=mocked,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(("tool_name", "arguments", "permission", "summary"), READ_CASES)
async def test_def_real_ai02_004_read_replay_uses_versioned_low_sensitive_contract(
    monkeypatch: pytest.MonkeyPatch,
    tool_name: str,
    arguments: dict[str, object],
    permission: str,
    summary: dict[str, object],
) -> None:
    """三个只读工具的合法低敏快照必须恢复为带版本的成功结果。"""
    monkeypatch.setattr(
        executor_module,
        "begin_tool_call",
        AsyncMock(return_value=(replay_call(summary), True, time.perf_counter())),
    )

    result = await SqlAlchemyToolExecutor(Mock(spec=AsyncSession)).execute(invocation(tool_name, arguments, permission))

    assert result.status == "succeeded"
    assert result.data == summary
    assert result.error_code is None
    assert result.replayed is True
    assert result.replay_contract_version == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(("tool_name", "arguments", "permission", "summary"), READ_CASES)
async def test_read_replay_rechecks_revoked_permission_without_rewriting_history(
    monkeypatch: pytest.MonkeyPatch,
    tool_name: str,
    arguments: dict[str, object],
    permission: str,
    summary: dict[str, object],
) -> None:
    """权限撤销后不得返回历史摘要，也不得覆盖原成功审计终态。"""
    finish = AsyncMock()
    monkeypatch.setattr(
        executor_module,
        "begin_tool_call",
        AsyncMock(return_value=(replay_call(summary), True, time.perf_counter())),
    )
    monkeypatch.setattr(executor_module, "finish_tool_call", finish)

    result = await SqlAlchemyToolExecutor(Mock(spec=AsyncSession)).execute(
        invocation(tool_name, arguments, permission, permissions=set())
    )

    assert result.status == "failed"
    assert result.error_code == "TOOL_PERMISSION_DENIED"
    assert result.data is None
    assert result.replayed is True
    assert result.replay_contract_version is None
    finish.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(("tool_name", "arguments", "permission", "summary"), READ_CASES)
async def test_read_replay_rejects_extra_sensitive_or_uncontracted_fields(
    monkeypatch: pytest.MonkeyPatch,
    tool_name: str,
    arguments: dict[str, object],
    permission: str,
    summary: dict[str, object],
) -> None:
    """低敏快照夹带任何契约外字段时必须失败关闭。"""
    polluted = dict(summary)
    polluted["uncontracted_sensitive_value"] = "MUST-NOT-BE-REPLAYED"
    monkeypatch.setattr(
        executor_module,
        "begin_tool_call",
        AsyncMock(return_value=(replay_call(polluted), True, time.perf_counter())),
    )

    result = await SqlAlchemyToolExecutor(Mock(spec=AsyncSession)).execute(invocation(tool_name, arguments, permission))

    assert result.status == "failed"
    assert result.error_code == "TOOL_OUTPUT_INVALID"
    assert result.data is None
    assert result.replayed is True
    assert result.replay_contract_version is None


@pytest.mark.parametrize(("tool_name", "_arguments", "_permission", "summary"), READ_CASES)
def test_agent_revalidates_low_sensitive_replay_before_creating_claims(
    tool_name: str,
    _arguments: dict[str, object],
    _permission: str,
    summary: dict[str, object],
) -> None:
    """带 v1 标识的严格快照才可生成同店铺对象级声明和可信证据。"""
    store_id = uuid.uuid4()
    execution = ExecutedAgentTool(
        tool_name=tool_name,  # type: ignore[arg-type]
        source_store_id=store_id,
        result=ToolResult(
            tool_call_id=uuid.uuid4(),
            status="succeeded",
            data=summary,
            replayed=True,
            replay_contract_version=1,
        ),
    )

    inventory = build_authoritative_tool_claims([execution])
    evidence = build_trusted_tool_evidence([execution])

    assert len(inventory.claims) == 1
    assert inventory.claims[0].evidence_id == execution.result.tool_call_id
    assert evidence[execution.result.tool_call_id].store_id == store_id
    assert evidence[execution.result.tool_call_id].subject_ids == {
        str(summary.get("order_id") or summary.get("customer_id"))
    }


@pytest.mark.parametrize(
    ("replayed", "version"),
    [(False, None), (True, None), (False, 1)],
)
def test_low_sensitive_summary_without_complete_replay_identity_is_not_trusted(
    replayed: bool,
    version: int | None,
) -> None:
    """缺失任一重放身份条件时，低敏摘要不能绕过完整 DTO 校验。"""
    execution = ExecutedAgentTool(
        tool_name="query_order",
        source_store_id=uuid.uuid4(),
        result=ToolResult(
            tool_call_id=uuid.uuid4(),
            status="succeeded",
            data={"order_id": str(uuid.uuid4()), "status": "paid"},
            replayed=replayed,
            replay_contract_version=version,  # type: ignore[arg-type]
        ),
    )

    assert build_authoritative_tool_claims([execution]).claims == []
    assert build_trusted_tool_evidence([execution]) == {}
    assert build_trusted_tool_template([execution], "zh-CN") is None


def test_unknown_replay_contract_version_is_rejected_at_type_boundary() -> None:
    """未知契约版本不能进入 Agent 结果模型。"""
    with pytest.raises(ValidationError):
        ToolResult(
            tool_call_id=uuid.uuid4(),
            status="succeeded",
            data={"order_id": str(uuid.uuid4()), "status": "paid"},
            replayed=True,
            replay_contract_version=2,  # type: ignore[arg-type]
        )


def test_write_tool_cannot_borrow_read_replay_contract() -> None:
    """写工具即使伪造 v1 标识也不能进入只读低敏声明入口。"""
    execution = ExecutedAgentTool(
        tool_name="send_platform_message",
        source_store_id=uuid.uuid4(),
        result=ToolResult(
            tool_call_id=uuid.uuid4(),
            status="succeeded",
            data={"message_id": str(uuid.uuid4()), "status": "sent", "mocked": True},
            mocked=True,
            replayed=True,
            replay_contract_version=1,
        ),
    )

    assert build_authoritative_tool_claims([execution]).claims == []
    assert build_trusted_tool_evidence([execution]) == {}


def test_read_replay_does_not_prove_fields_absent_from_snapshot() -> None:
    """订单重放只能证明对象和有限状态，不能虚构金额或外部订单号。"""
    order_id = uuid.uuid4()
    execution = ExecutedAgentTool(
        tool_name="query_order",
        source_store_id=uuid.uuid4(),
        result=ToolResult(
            tool_call_id=uuid.uuid4(),
            status="succeeded",
            data={"order_id": str(order_id), "status": "paid"},
            replayed=True,
            replay_contract_version=1,
        ),
    )

    inventory = build_authoritative_tool_claims([execution])
    evidence = build_trusted_tool_evidence([execution])

    assert len(inventory.claims) == 1
    assert inventory.claims[0].subject_type == BusinessClaimSubjectType.ORDER
    assert inventory.claims[0].subject_id == str(order_id)
    assert evidence[execution.result.tool_call_id].subject_ids == {str(order_id)}
    assert "EXTERNAL-ORDER" not in evidence[execution.result.tool_call_id].subject_ids


def test_read_replay_cross_store_evidence_still_fails_closed() -> None:
    """合法 v1 快照也不能跨店铺取得安全或自动交付授权。"""
    source_store_id = uuid.uuid4()
    current_store_id = uuid.uuid4()
    execution = ExecutedAgentTool(
        tool_name="query_order",
        source_store_id=source_store_id,
        result=ToolResult(
            tool_call_id=uuid.uuid4(),
            status="succeeded",
            data={"order_id": str(uuid.uuid4()), "status": "paid"},
            replayed=True,
            replay_contract_version=1,
        ),
    )
    inventory = build_authoritative_tool_claims([execution])
    evidence = build_trusted_tool_evidence([execution])

    result = ReplySafetyPolicy().evaluate(
        "订单当前状态已由系统记录。",
        evidence_kind=ReplyEvidenceKind.TOOL,
        successful_tools={"query_order"},
        claim_inventory=inventory,
        successful_tool_evidence=evidence,
        content_origin=ReplyContentOrigin.TRUSTED_TOOL_TEMPLATE,
        expected_store_id=current_store_id,
    )

    assert result.is_safe is False
    assert result.automatic_delivery_allowed is False
    assert "INVALID_BUSINESS_CLAIM_EVIDENCE" in result.reason_codes


def test_unknown_status_snapshot_cannot_generate_authoritative_status_claim() -> None:
    """低敏 Schema 合法但状态不在固定枚举时，不得生成权威状态声明或模板。"""
    execution = ExecutedAgentTool(
        tool_name="query_order",
        source_store_id=uuid.uuid4(),
        result=ToolResult(
            tool_call_id=uuid.uuid4(),
            status="succeeded",
            data={"order_id": str(uuid.uuid4()), "status": "unexpected_state"},
            replayed=True,
            replay_contract_version=1,
        ),
    )

    assert build_authoritative_tool_claims([execution]).claims == []
    assert build_trusted_tool_template([execution], "zh-CN") is None
