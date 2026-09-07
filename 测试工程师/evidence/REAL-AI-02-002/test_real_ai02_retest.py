"""REAL-AI-02 第二次独立安全复测样本。

本文件不复用开发者参数化样本，重点重放首轮两个正式缺陷，
并对来源缺失、跨店铺、Mock 写动作和可信来源伪造做负向变异。
"""

import uuid

import pytest

from app.agent.business_claims import (
    BusinessClaim,
    BusinessClaimAction,
    BusinessClaimCondition,
    BusinessClaimEvidenceType,
    BusinessClaimInventory,
    BusinessClaimPolarity,
    BusinessClaimSubjectType,
    BusinessClaimTense,
)
from app.agent.reply_rendering import (
    build_authoritative_tool_claims,
    build_trusted_tool_evidence,
)
from app.agent.reply_safety import ReplyContentOrigin, ReplyEvidenceKind, ReplySafetyPolicy
from app.agent.schemas import AgentToolRuntimeContext, AgentWorkflowCommand
from app.agent.tool_execution import AgentToolService, ExecutedAgentTool
from app.tools.contracts import ToolInvocation, ToolResult


def order_execution(*, store_id: uuid.UUID | None, mocked: bool = False) -> ExecutedAgentTool:
    """构造通过工具输出 Schema 的订单执行结果。"""
    return ExecutedAgentTool(
        tool_name="query_order",
        source_store_id=store_id,
        result=ToolResult(
            tool_call_id=uuid.uuid4(),
            status="succeeded",
            mocked=mocked,
            data={
                "order_id": str(uuid.uuid4()),
                "external_order_id": "EXT-RETEST-001",
                "status": "paid",
                "payment_status": "paid",
                "fulfillment_status": "pending",
                "currency": "USD",
                "total_amount": "42.00",
                "ordered_at": None,
            },
        ),
    )


def evaluate_execution(
    execution: ExecutedAgentTool,
    *,
    expected_store_id: uuid.UUID,
    answer: str = "业务处理状态已记录。",
):
    """从真实内部构建链路生成声明与证据后执行安全策略。"""
    inventory = build_authoritative_tool_claims([execution])
    evidence = build_trusted_tool_evidence([execution])
    return ReplySafetyPolicy().evaluate(
        answer,
        evidence_kind=ReplyEvidenceKind.TOOL,
        successful_tools={item.tool_name for item in evidence.values()},
        has_mock_result=execution.result.mocked,
        claim_inventory=inventory,
        successful_tool_evidence=evidence,
        mocked_tool_call_ids={execution.result.tool_call_id} if execution.result.mocked else set(),
        content_origin=ReplyContentOrigin.MODEL_GENERATED,
        expected_store_id=expected_store_id,
    )


def test_def_real_ai02_001_preserves_source_and_rejects_cross_store_relabel() -> None:
    """来源店铺 A 的结果进入店铺 B 工作流时必须失败关闭。"""
    source_store_id = uuid.uuid4()
    current_store_id = uuid.uuid4()
    execution = order_execution(store_id=source_store_id)

    evidence = build_trusted_tool_evidence([execution])
    result = evaluate_execution(execution, expected_store_id=current_store_id)

    assert evidence[execution.result.tool_call_id].store_id == source_store_id
    assert result.is_safe is False
    assert result.automatic_delivery_allowed is False
    assert "INVALID_BUSINESS_CLAIM_EVIDENCE" in result.reason_codes


def test_same_store_real_order_evidence_remains_usable() -> None:
    """修复不能破坏同店铺真实查询结果的合法证据链。"""
    store_id = uuid.uuid4()
    result = evaluate_execution(order_execution(store_id=store_id), expected_store_id=store_id)

    assert result.is_safe is True
    assert result.automatic_delivery_allowed is False


def test_missing_execution_source_fails_closed() -> None:
    """旧替身或异常执行缺少来源时不得生成可信证据。"""
    execution = order_execution(store_id=None)
    evidence = build_trusted_tool_evidence([execution])
    result = evaluate_execution(execution, expected_store_id=uuid.uuid4())

    assert evidence == {}
    assert result.is_safe is False
    assert "INVALID_BUSINESS_CLAIM_EVIDENCE" in result.reason_codes


class RecordingExecutor:
    """独立记录受控工具执行上下文。"""

    def __init__(self) -> None:
        self.invocations: list[ToolInvocation] = []

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        self.invocations.append(invocation)
        return ToolResult(
            tool_call_id=uuid.uuid4(),
            status="succeeded",
            mocked=False,
            data={
                "order_id": str(invocation.arguments["order_id"]),
                "external_order_id": "EXT-SOURCE-CAPTURE",
                "tracking_number": None,
                "tracking_status": "in_transit",
                "shipped_at": None,
                "delivered_at": None,
            },
        )


@pytest.mark.asyncio
async def test_controlled_tool_service_captures_store_at_invocation_time() -> None:
    """生产执行服务必须从不可变调用上下文固化来源店铺。"""
    store_id = uuid.uuid4()
    command = AgentWorkflowCommand(
        store_id=store_id,
        conversation_id=uuid.uuid4(),
        trigger_message_id=uuid.uuid4(),
        message="请查询物流。",
        history=[],
        language="zh-CN",
        trace_id="trace-real-ai02-002",
        tool_context=AgentToolRuntimeContext(
            order_id=str(uuid.uuid4()),
            available_tools={"query_logistics"},
            permissions={"orders.view"},
        ),
    )
    executor = RecordingExecutor()
    batch = await AgentToolService(executor).execute_required(
        command,
        agent_run_id=uuid.uuid4(),
        required_tools=["query_logistics"],
    )

    assert len(batch.results) == 1
    assert batch.results[0].source_store_id == store_id
    assert executor.invocations[0].context.store_id == store_id


@pytest.mark.parametrize(
    ("tool_name", "data"),
    [
        (
            "update_shipping_address",
            {
                "order_id": "00000000-0000-0000-0000-000000000301",
                "status": "pending_confirmation",
                "mocked": True,
            },
        ),
        (
            "send_coupon",
            {
                "issuance_id": "00000000-0000-0000-0000-000000000302",
                "coupon_code": "RETEST10",
                "status": "issued",
                "mocked": True,
            },
        ),
        (
            "send_platform_message",
            {
                "message_id": "00000000-0000-0000-0000-000000000303",
                "status": "sent",
                "mocked": True,
            },
        ),
    ],
)
def test_all_mock_write_actions_fail_closed_even_when_outer_flag_is_false(
    tool_name: str,
    data: dict[str, object],
) -> None:
    """Mock 标识位于强类型数据时也必须阻断提交、发送和更新事实。"""
    store_id = uuid.uuid4()
    execution = ExecutedAgentTool(
        tool_name=tool_name,  # type: ignore[arg-type]
        source_store_id=store_id,
        result=ToolResult(
            tool_call_id=uuid.uuid4(),
            status="succeeded",
            data=data,
            mocked=False,
        ),
    )
    inventory = build_authoritative_tool_claims([execution])
    evidence = build_trusted_tool_evidence([execution])
    result = ReplySafetyPolicy().evaluate(
        "渠道动作已经进入处理流程。",
        evidence_kind=ReplyEvidenceKind.TOOL,
        successful_tools={item.tool_name for item in evidence.values()},
        claim_inventory=inventory,
        successful_tool_evidence=evidence,
        content_origin=ReplyContentOrigin.MODEL_GENERATED,
        expected_store_id=store_id,
    )

    assert len(inventory.claims) == 1
    assert result.is_safe is False
    assert result.automatic_delivery_allowed is False
    assert "MOCK_COMPLETION_CLAIM" in result.reason_codes


def test_def_real_ai02_002_address_synonym_cannot_bypass_structured_policy() -> None:
    """地址提交使用文本规则未覆盖的措辞时仍由结构化动作阻断。"""
    store_id = uuid.uuid4()
    execution = ExecutedAgentTool(
        tool_name="update_shipping_address",
        source_store_id=store_id,
        result=ToolResult(
            tool_call_id=uuid.uuid4(),
            status="succeeded",
            mocked=False,
            data={
                "order_id": str(uuid.uuid4()),
                "status": "pending_confirmation",
                "mocked": True,
            },
        ),
    )
    result = evaluate_execution(
        execution,
        expected_store_id=store_id,
        answer="地址调整请求已递交至渠道处理队列。",
    )

    assert "MOCK_COMPLETION_CLAIM" in result.reason_codes
    assert result.is_safe is False


@pytest.mark.parametrize(
    "inventory",
    [None, BusinessClaimInventory(complete=True, claims=[])],
)
def test_trusted_tool_origin_without_nonempty_claims_fails_closed(
    inventory: BusinessClaimInventory | None,
) -> None:
    """调用方不能只伪造可信来源标签取得自动交付授权。"""
    result = ReplySafetyPolicy().evaluate(
        "Your order is being processed.",
        evidence_kind=ReplyEvidenceKind.TOOL,
        successful_tools={"query_order"},
        claim_inventory=inventory,
        content_origin=ReplyContentOrigin.TRUSTED_TOOL_TEMPLATE,
    )

    assert result.is_safe is False
    assert result.automatic_delivery_allowed is False
    assert "BUSINESS_CLAIM_INVENTORY_MISSING" in result.reason_codes


def test_faq_citation_cannot_prove_instance_order_status() -> None:
    """有效 FAQ 引用不能提升为客户实例订单状态证据。"""
    chunk_id = uuid.uuid4()
    claim = BusinessClaim(
        subject_type=BusinessClaimSubjectType.ORDER,
        subject_id="ORDER-FAQ-RETEST",
        action=BusinessClaimAction.REPORT_STATUS,
        tense=BusinessClaimTense.PRESENT,
        polarity=BusinessClaimPolarity.AFFIRMED,
        condition=BusinessClaimCondition.ACTUAL,
        evidence_type=BusinessClaimEvidenceType.FAQ_CHUNK,
        evidence_id=chunk_id,
        confidence=0.99,
    )
    result = ReplySafetyPolicy().evaluate(
        "订单状态已记录。",
        evidence_kind=ReplyEvidenceKind.FAQ,
        claim_inventory=BusinessClaimInventory(complete=True, claims=[claim]),
        faq_evidence_ids={chunk_id},
        content_origin=ReplyContentOrigin.MODEL_GENERATED,
    )

    assert result.is_safe is False
    assert "INVALID_BUSINESS_CLAIM_EVIDENCE" in result.reason_codes


def test_empty_model_inventory_never_grants_automatic_delivery() -> None:
    """空声明模型草稿即使未命中兼容词表，也不能自动发送。"""
    result = ReplySafetyPolicy().evaluate(
        "补偿需审核，财务方完成了向买家的价值返置。",
        evidence_kind=ReplyEvidenceKind.FAQ,
        claim_inventory=BusinessClaimInventory(complete=True, claims=[]),
        content_origin=ReplyContentOrigin.MODEL_GENERATED,
    )

    assert result.automatic_delivery_allowed is False


@pytest.mark.parametrize(
    ("tool_name", "summary"),
    [
        (
            "update_shipping_address",
            {
                "order_id": "00000000-0000-0000-0000-000000000401",
                "status": "pending_confirmation",
            },
        ),
        (
            "send_coupon",
            {
                "issuance_id": "00000000-0000-0000-0000-000000000402",
                "status": "issued",
            },
        ),
        (
            "send_platform_message",
            {
                "message_id": "00000000-0000-0000-0000-000000000403",
                "status": "sent",
            },
        ),
    ],
)
def test_replayed_mock_write_summary_cannot_drop_structured_block(
    tool_name: str,
    summary: dict[str, object],
) -> None:
    """幂等重放的低敏摘要仍必须保留 Mock 写动作失败关闭语义。"""
    store_id = uuid.uuid4()
    execution = ExecutedAgentTool(
        tool_name=tool_name,  # type: ignore[arg-type]
        source_store_id=store_id,
        result=ToolResult(
            tool_call_id=uuid.uuid4(),
            status="succeeded",
            data=summary,
            mocked=True,
            replayed=True,
        ),
    )
    inventory = build_authoritative_tool_claims([execution])
    evidence = build_trusted_tool_evidence([execution])
    result = ReplySafetyPolicy().evaluate(
        "渠道动作已经进入处理流程。",
        evidence_kind=ReplyEvidenceKind.TOOL,
        successful_tools={item.tool_name for item in evidence.values()},
        has_mock_result=True,
        claim_inventory=inventory,
        successful_tool_evidence=evidence,
        mocked_tool_call_ids={execution.result.tool_call_id},
        content_origin=ReplyContentOrigin.MODEL_GENERATED,
        expected_store_id=store_id,
    )

    assert result.is_safe is False
    assert "MOCK_COMPLETION_CLAIM" in result.reason_codes
