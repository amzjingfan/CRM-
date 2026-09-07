"""REAL-AI-02 结构化业务声明独立安全样本。

本文件只调用产品公开的内部类型和策略，不复用开发测试参数化数据。
样本重点验证 FAQ、跨店铺证据、Mock 写操作和残缺工具输出是否失败关闭。
"""

import uuid

import pytest
from pydantic import ValidationError

from app.agent.business_claims import (
    BusinessClaim,
    BusinessClaimAction,
    BusinessClaimCondition,
    BusinessClaimEvidenceType,
    BusinessClaimInventory,
    BusinessClaimPolarity,
    BusinessClaimSubjectType,
    BusinessClaimTense,
    TrustedToolEvidence,
)
from app.agent.reply_rendering import (
    build_authoritative_tool_claims,
    build_trusted_tool_evidence,
)
from app.agent.reply_safety import (
    ReplyContentOrigin,
    ReplyEvidenceKind,
    ReplySafetyPolicy,
)
from app.agent.tool_execution import ExecutedAgentTool
from app.tools.contracts import ToolResult


def make_claim(
    *,
    subject_type: BusinessClaimSubjectType,
    action: BusinessClaimAction,
    subject_id: str | None,
    tense: BusinessClaimTense = BusinessClaimTense.PRESENT,
    polarity: BusinessClaimPolarity = BusinessClaimPolarity.AFFIRMED,
    condition: BusinessClaimCondition = BusinessClaimCondition.ACTUAL,
    evidence_type: BusinessClaimEvidenceType = BusinessClaimEvidenceType.NONE,
    evidence_id: uuid.UUID | None = None,
) -> BusinessClaim:
    """构造单条独立声明，默认表示当前肯定事实。"""
    return BusinessClaim(
        subject_type=subject_type,
        subject_id=subject_id,
        action=action,
        tense=tense,
        polarity=polarity,
        condition=condition,
        evidence_type=evidence_type,
        evidence_id=evidence_id,
        confidence=0.97,
    )


def evaluate_claims(
    claims: list[BusinessClaim],
    *,
    evidence_kind: ReplyEvidenceKind,
    faq_evidence_ids: set[uuid.UUID] | None = None,
    tool_evidence: dict[uuid.UUID, TrustedToolEvidence] | None = None,
    mocked_tool_call_ids: set[uuid.UUID] | None = None,
    expected_store_id: uuid.UUID | None = None,
) -> object:
    """使用不命中文本词表的正文，只测试结构化声明授权边界。"""
    return ReplySafetyPolicy().evaluate(
        "业务处理状态已记录。",
        evidence_kind=evidence_kind,
        successful_tools={item.tool_name for item in (tool_evidence or {}).values()},
        claim_inventory=BusinessClaimInventory(complete=True, claims=claims),
        faq_evidence_ids=faq_evidence_ids,
        successful_tool_evidence=tool_evidence,
        mocked_tool_call_ids=mocked_tool_call_ids,
        content_origin=ReplyContentOrigin.MODEL_GENERATED,
        expected_store_id=expected_store_id,
    )


def test_schema_rejects_unknown_fields() -> None:
    """模型不能通过额外字段扩展声明语义。"""
    with pytest.raises(ValidationError):
        BusinessClaim.model_validate(
            {
                "subject_type": "refund_policy",
                "subject_id": None,
                "action": "explain_policy",
                "tense": "timeless",
                "polarity": "affirmed",
                "condition": "actual",
                "evidence_type": "none",
                "evidence_id": None,
                "confidence": 0.9,
                "platform_confirmed": True,
            }
        )


def test_schema_rejects_illegal_subject_action_pair() -> None:
    """模型不能把退款到账动作伪装成普通订单动作。"""
    with pytest.raises(ValidationError):
        make_claim(
            subject_type=BusinessClaimSubjectType.ORDER,
            action=BusinessClaimAction.RECEIVE_FUNDS,
            subject_id="ORDER-X",
        )


def test_inventory_rejects_conflict_split_across_evidence_and_tense() -> None:
    """不同引用和时态不能拆分同一主体动作的相反命题。"""
    with pytest.raises(ValidationError):
        BusinessClaimInventory(
            complete=True,
            claims=[
                make_claim(
                    subject_type=BusinessClaimSubjectType.REFUND_POLICY,
                    action=BusinessClaimAction.EXPLAIN_POLICY,
                    subject_id=None,
                    tense=BusinessClaimTense.TIMELESS,
                    evidence_type=BusinessClaimEvidenceType.FAQ_CHUNK,
                    evidence_id=uuid.uuid4(),
                ),
                make_claim(
                    subject_type=BusinessClaimSubjectType.REFUND_POLICY,
                    action=BusinessClaimAction.EXPLAIN_POLICY,
                    subject_id=None,
                    tense=BusinessClaimTense.PRESENT,
                    polarity=BusinessClaimPolarity.NEGATED,
                    evidence_type=BusinessClaimEvidenceType.FAQ_CHUNK,
                    evidence_id=uuid.uuid4(),
                ),
            ],
        )


@pytest.mark.parametrize(
    ("subject_type", "action"),
    [
        (BusinessClaimSubjectType.REFUND_REQUEST, BusinessClaimAction.SUBMIT_REQUEST),
        (BusinessClaimSubjectType.ORDER, BusinessClaimAction.QUERY),
        (BusinessClaimSubjectType.LOGISTICS, BusinessClaimAction.QUERY),
        (BusinessClaimSubjectType.CUSTOMER_PROFILE, BusinessClaimAction.QUERY),
        (BusinessClaimSubjectType.SHIPPING_ADDRESS, BusinessClaimAction.QUERY),
        (BusinessClaimSubjectType.COUPON, BusinessClaimAction.DISPLAY),
    ],
)
def test_valid_faq_citation_cannot_prove_customer_instance(
    subject_type: BusinessClaimSubjectType,
    action: BusinessClaimAction,
) -> None:
    """当前检索命中的 FAQ 仍不能证明具体客户实例动作。"""
    chunk_id = uuid.uuid4()
    result = evaluate_claims(
        [
            make_claim(
                subject_type=subject_type,
                action=action,
                subject_id="CURRENT-OBJECT",
                evidence_type=BusinessClaimEvidenceType.FAQ_CHUNK,
                evidence_id=chunk_id,
            )
        ],
        evidence_kind=ReplyEvidenceKind.FAQ,
        faq_evidence_ids={chunk_id},
    )

    assert result.is_safe is False
    assert result.reason_codes


def test_order_evidence_rejects_cross_store_and_cross_object_reuse() -> None:
    """合法工具调用不能跨店铺或跨订单借用。"""
    tool_call_id = uuid.uuid4()
    store_id = uuid.uuid4()
    evidence = {
        tool_call_id: TrustedToolEvidence(
            tool_name="query_order",
            store_id=store_id,
            subject_ids=frozenset({"ORDER-A"}),
        )
    }
    claim = make_claim(
        subject_type=BusinessClaimSubjectType.ORDER,
        action=BusinessClaimAction.REPORT_STATUS,
        subject_id="ORDER-B",
        evidence_type=BusinessClaimEvidenceType.TOOL_CALL,
        evidence_id=tool_call_id,
    )

    wrong_object = evaluate_claims(
        [claim],
        evidence_kind=ReplyEvidenceKind.TOOL,
        tool_evidence=evidence,
        expected_store_id=store_id,
    )
    wrong_store = evaluate_claims(
        [claim.model_copy(update={"subject_id": "ORDER-A"})],
        evidence_kind=ReplyEvidenceKind.TOOL,
        tool_evidence=evidence,
        expected_store_id=uuid.uuid4(),
    )

    assert "INVALID_BUSINESS_CLAIM_EVIDENCE" in wrong_object.reason_codes
    assert "INVALID_BUSINESS_CLAIM_EVIDENCE" in wrong_store.reason_codes


def test_future_order_status_rejects_current_tool_evidence() -> None:
    """当前订单查询不能证明未来状态。"""
    tool_call_id = uuid.uuid4()
    store_id = uuid.uuid4()
    result = evaluate_claims(
        [
            make_claim(
                subject_type=BusinessClaimSubjectType.ORDER,
                action=BusinessClaimAction.REPORT_STATUS,
                subject_id="ORDER-A",
                tense=BusinessClaimTense.FUTURE,
                evidence_type=BusinessClaimEvidenceType.TOOL_CALL,
                evidence_id=tool_call_id,
            )
        ],
        evidence_kind=ReplyEvidenceKind.TOOL,
        tool_evidence={
            tool_call_id: TrustedToolEvidence(
                tool_name="query_order",
                store_id=store_id,
                subject_ids=frozenset({"ORDER-A"}),
            )
        },
        expected_store_id=store_id,
    )

    assert "BUSINESS_CLAIM_TENSE_MISMATCH" in result.reason_codes


def test_delivery_promise_without_dedicated_tool_is_blocked() -> None:
    """订单或物流状态不能扩展为未来送达承诺。"""
    result = evaluate_claims(
        [
            make_claim(
                subject_type=BusinessClaimSubjectType.PROMISE_TIME,
                action=BusinessClaimAction.PROMISE,
                subject_id="ORDER-A",
                tense=BusinessClaimTense.FUTURE,
            )
        ],
        evidence_kind=ReplyEvidenceKind.TOOL,
    )

    assert "UNAUTHORIZED_COMMITMENT" in result.reason_codes


def test_incomplete_successful_tool_output_cannot_create_authoritative_claim() -> None:
    """替代执行端口返回的残缺字典不能提升为权威事实。"""
    inventory = build_authoritative_tool_claims(
        [
            ExecutedAgentTool(
                tool_name="query_order",
                result=ToolResult(
                    tool_call_id=uuid.uuid4(),
                    status="succeeded",
                    data={"order_id": str(uuid.uuid4()), "status": "paid"},
                ),
            )
        ]
    )

    assert inventory.claims == []


def test_real_known_order_result_creates_bound_authoritative_claim() -> None:
    """完整真实订单结果应生成同工具、同对象的权威当前状态声明。"""
    tool_call_id = uuid.uuid4()
    store_id = uuid.uuid4()
    order_id = uuid.uuid4()
    execution = ExecutedAgentTool(
        tool_name="query_order",
        result=ToolResult(
            tool_call_id=tool_call_id,
            status="succeeded",
            data={
                "order_id": str(order_id),
                "external_order_id": "EXT-INDEPENDENT-001",
                "status": "paid",
                "payment_status": "paid",
                "fulfillment_status": "pending",
                "currency": "USD",
                "total_amount": "42.00",
                "ordered_at": None,
            },
        ),
    )
    inventory = build_authoritative_tool_claims([execution])
    evidence = build_trusted_tool_evidence(store_id, [execution])
    result = evaluate_claims(
        inventory.claims,
        evidence_kind=ReplyEvidenceKind.TOOL,
        tool_evidence=evidence,
        expected_store_id=store_id,
    )

    assert len(inventory.claims) == 1
    assert inventory.claims[0].subject_id == str(order_id)
    assert result.is_safe is True


@pytest.mark.parametrize(
    ("tool_name", "data", "expected_reason"),
    [
        (
            "send_coupon",
            {
                "issuance_id": "00000000-0000-0000-0000-000000000201",
                "coupon_code": "TEST10",
                "status": "issued",
                "mocked": True,
            },
            "MOCK_COMPLETION_CLAIM",
        ),
        (
            "send_platform_message",
            {
                "message_id": "00000000-0000-0000-0000-000000000202",
                "status": "sent",
                "mocked": True,
            },
            "MOCK_COMPLETION_CLAIM",
        ),
        (
            "update_shipping_address",
            {
                "order_id": "00000000-0000-0000-0000-000000000203",
                "status": "pending_confirmation",
                "mocked": True,
            },
            "MOCK_COMPLETION_CLAIM",
        ),
    ],
)
def test_all_mock_write_claims_are_explicitly_blocked(
    tool_name: str,
    data: dict[str, object],
    expected_reason: str,
) -> None:
    """Mock 发券、消息和地址请求都不能被解释为真实平台完成。"""
    store_id = uuid.uuid4()
    execution = ExecutedAgentTool(
        tool_name=tool_name,  # type: ignore[arg-type]
        result=ToolResult(
            tool_call_id=uuid.uuid4(),
            status="succeeded",
            data=data,
            # 独立验证数据内 mocked=true 也必须被证据层识别。
            mocked=False,
        ),
    )
    inventory = build_authoritative_tool_claims([execution])
    evidence = build_trusted_tool_evidence(store_id, [execution])
    result = evaluate_claims(
        inventory.claims,
        evidence_kind=ReplyEvidenceKind.TOOL,
        tool_evidence=evidence,
        expected_store_id=store_id,
    )

    assert len(inventory.claims) == 1
    assert expected_reason in result.reason_codes
    assert result.is_safe is False


def test_mock_address_platform_submission_wording_cannot_bypass_structured_policy() -> None:
    """Mock 地址修改不得借助未被文本正则覆盖的措辞伪装成真实平台提交。"""

    store_id = uuid.uuid4()
    order_id = uuid.uuid4()
    execution = ExecutedAgentTool(
        tool_name="update_shipping_address",
        result=ToolResult(
            tool_call_id=uuid.uuid4(),
            status="succeeded",
            data={
                "order_id": str(order_id),
                "status": "pending_confirmation",
                "mocked": True,
            },
            mocked=False,
        ),
    )
    inventory = build_authoritative_tool_claims([execution])
    evidence = build_trusted_tool_evidence(store_id, [execution])

    result = ReplySafetyPolicy().evaluate(
        "地址调整请求已递交至渠道处理队列。",
        evidence_kind=ReplyEvidenceKind.TOOL,
        successful_tools={item.tool_name for item in evidence.values()},
        has_mock_result=True,
        claim_inventory=inventory,
        successful_tool_evidence=evidence,
        content_origin=ReplyContentOrigin.MODEL_GENERATED,
        expected_store_id=store_id,
    )

    assert "MOCK_COMPLETION_CLAIM" in result.reason_codes
    assert result.is_safe is False


def test_model_authored_empty_inventory_never_grants_automatic_delivery() -> None:
    """模型自报空声明不能单独获得自动交付权限。"""
    result = ReplySafetyPolicy().evaluate(
        "普通客服草稿。",
        evidence_kind=ReplyEvidenceKind.FAQ,
        claim_inventory=BusinessClaimInventory(complete=True, claims=[]),
        content_origin=ReplyContentOrigin.MODEL_GENERATED,
    )

    assert result.automatic_delivery_allowed is False


def test_tool_evidence_preserves_the_execution_store_provenance() -> None:
    """工具证据的店铺必须来自执行来源，不能由当前工作流店铺重新标记。"""

    origin_store_id = uuid.uuid4()
    current_workflow_store_id = uuid.uuid4()
    execution = ExecutedAgentTool(
        tool_name="query_order",
        result=ToolResult(
            tool_call_id=uuid.uuid4(),
            status="succeeded",
            data={
                "order_id": str(uuid.uuid4()),
                "external_order_id": "EXT-ORIGIN-STORE",
                "status": "pending",
                "payment_status": "pending",
                "fulfillment_status": "unfulfilled",
                "currency": "USD",
                "total_amount": "10.00",
                "ordered_at": None,
            },
        ),
    )

    evidence = build_trusted_tool_evidence(current_workflow_store_id, [execution])
    recorded = evidence[execution.result.tool_call_id]

    # execution 表示来自 origin_store_id 的替代端口结果；当前实现没有字段
    # 保存这个来源，只能把 current_workflow_store_id 自我赋值给证据。
    assert recorded.store_id == origin_store_id


def test_empty_complete_inventory_cannot_mark_high_risk_model_text_safe() -> None:
    """模型不得用 complete=true、claims=[] 省略高风险业务事实。"""

    result = ReplySafetyPolicy().evaluate(
        "补偿需审核，财务方完成了向买家的价值返置。",
        evidence_kind=ReplyEvidenceKind.FAQ,
        claim_inventory=BusinessClaimInventory(complete=True, claims=[]),
        content_origin=ReplyContentOrigin.MODEL_GENERATED,
    )

    assert result.is_safe is False
    assert "BUSINESS_CLAIM_INVENTORY_MISMATCH" in result.reason_codes


def test_trusted_template_origin_without_claim_inventory_cannot_authorize_delivery() -> None:
    """内部安全策略缺少声明清单时必须失败关闭，即使调用方标记可信模板。"""

    result = ReplySafetyPolicy().evaluate(
        "Your order is currently being processed.",
        evidence_kind=ReplyEvidenceKind.TOOL,
        successful_tools={"query_order"},
        claim_inventory=None,
        content_origin=ReplyContentOrigin.TRUSTED_TOOL_TEMPLATE,
    )

    assert result.automatic_delivery_allowed is False
    assert result.is_safe is False
