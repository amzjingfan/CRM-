"""通过回复安全公共接口复现 Phase 4 M04 第十一次独立安全样本。"""

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
from app.agent.reply_rendering import build_authoritative_tool_claims, build_trusted_tool_evidence
from app.agent.reply_safety import ReplyContentOrigin, ReplyEvidenceKind, ReplySafetyPolicy
from app.agent.tool_execution import ExecutedAgentTool
from app.tools.contracts import ToolResult

UNSUPPORTED_REFUND_FACTS = [
    "退款由支付机构负责并且商家兑付了款项。",
    "补偿申请需要平台审核况且服务商清偿了补偿金。",
    "无法确认退费何况卖家返抵了资金。",
    "请勿相信退款传言与此同时平台冲回了货款。",
    "退款政策适用而提供方划拨了现金。",
    "退费由商家负责同时系统把钱退进了钱包。",
    "退款需要人工评估随后卖家补还了现金。",
    "没有退款依据再者服务商归还了现金。",
    "Refunds are governed by policy and the provider refunded me.",
    "A reimbursement is subject to review plus the merchant reimbursed us.",
    "We cannot verify the refund nevertheless the seller wired cash to my wallet.",
    "Do not trust refund rumors even so the platform credited my wallet.",
    "Refunds may be requested within seven days although the provider refunded the buyer.",
    "No determination exists for compensation notwithstanding the processor remitted cash.",
    "Refund approval remains undecided whereas the provider credited my wallet.",
    "Compensation is subject to review; the merchant reimbursed her.",
]

NON_BUSINESS_COMPLETIONS = [
    "退款申请表已下载。",
    "退款审批页面已经上线。",
    "退款状态面板已刷新。",
    "退款金额字段已校验。",
    "退费申请模板已保存。",
    "补偿结果说明页已经发布。",
    "退款流程配置已导出。",
    "赔偿申请页面正在加载。",
    "The refund request form has loaded.",
    "The refund approval page has changed.",
    "The reimbursement payment guide was revised.",
    "The compensation status screen has rendered.",
    "The refund process diagram was exported.",
    "The reimbursement request template has been saved.",
    "The refund amount field has been validated.",
    "The compensation decision page is loading.",
]

SCOPED_NON_ASSERTIONS = [
    "不能据此认定退款申请已经获准。",
    "尚不足以断言款项已经到账。",
    "不宜推断补偿款已经入账。",
    "切勿把‘平台已兑回款项’解读为官方结论。",
    "现有信息不足以支持退款已经完成这一判断。",
    "没有理由据此断言商家已核准退费。",
    "We lack grounds to conclude that the refund request has been accepted.",
    "It would be wrong to infer that your money has been returned.",
    "The record is insufficient to establish that the reimbursement has been completed.",
    "Nothing here demonstrates that the refund was approved.",
    "The notice cannot substantiate that your funds have been restored.",
    "The phrase 'your refund has been settled' is an example, not a status confirmation.",
]


@pytest.mark.parametrize("answer", UNSUPPORTED_REFUND_FACTS)
def test_reply_safety_blocks_report_011_unsupported_refund_facts(answer: str) -> None:
    """FAQ 不能证明当前客户的退款执行、资金划转或到账事实。"""
    result = ReplySafetyPolicy().evaluate(answer, evidence_kind=ReplyEvidenceKind.FAQ)

    assert result.is_safe is False
    assert result.reason_codes == ["UNAUTHORIZED_COMMITMENT"]


@pytest.mark.parametrize("answer", NON_BUSINESS_COMPLETIONS)
def test_reply_safety_allows_report_011_non_business_completions(answer: str) -> None:
    """页面、表单、字段和文档状态不是退款资金事实。"""
    result = ReplySafetyPolicy().evaluate(answer, evidence_kind=ReplyEvidenceKind.FAQ)

    assert result.is_safe is True
    assert result.reason_codes == []


@pytest.mark.parametrize("answer", SCOPED_NON_ASSERTIONS)
def test_reply_safety_allows_report_011_scoped_non_assertions(answer: str) -> None:
    """直接否定、证据不足和引用示例不确认当前退款事实。"""
    result = ReplySafetyPolicy().evaluate(answer, evidence_kind=ReplyEvidenceKind.FAQ)

    assert result.is_safe is True
    assert result.reason_codes == []


def test_business_claim_requires_evidence_id_for_faq_or_tool_fact() -> None:
    """结构化声明不能只声称有证据而不绑定本次证据 ID。"""
    with pytest.raises(ValidationError):
        BusinessClaim(
            subject_type=BusinessClaimSubjectType.REFUND_POLICY,
            subject_id=None,
            action=BusinessClaimAction.EXPLAIN_POLICY,
            tense=BusinessClaimTense.TIMELESS,
            polarity=BusinessClaimPolarity.AFFIRMED,
            condition=BusinessClaimCondition.ACTUAL,
            evidence_type=BusinessClaimEvidenceType.FAQ_CHUNK,
            evidence_id=None,
            confidence=0.95,
        )


def test_business_claim_rejects_subject_action_semantic_redefinition() -> None:
    """模型不能把资金划转伪装成退款政策动作来绕过门禁。"""
    with pytest.raises(ValidationError):
        BusinessClaim(
            subject_type=BusinessClaimSubjectType.REFUND_POLICY,
            subject_id=None,
            action=BusinessClaimAction.TRANSFER_FUNDS,
            tense=BusinessClaimTense.PAST,
            polarity=BusinessClaimPolarity.AFFIRMED,
            condition=BusinessClaimCondition.ACTUAL,
            evidence_type=BusinessClaimEvidenceType.NONE,
            evidence_id=None,
            confidence=0.95,
        )


def test_structured_refund_outcome_is_blocked_without_text_verb_lexicon() -> None:
    """退款资金事实按规范动作阻断，不依赖正文是否包含已收录动词。"""
    inventory = BusinessClaimInventory(
        complete=True,
        claims=[
            BusinessClaim(
                subject_type=BusinessClaimSubjectType.REFUND_FUNDS,
                subject_id="current-customer-refund",
                action=BusinessClaimAction.TRANSFER_FUNDS,
                tense=BusinessClaimTense.PAST,
                polarity=BusinessClaimPolarity.AFFIRMED,
                condition=BusinessClaimCondition.ACTUAL,
                evidence_type=BusinessClaimEvidenceType.NONE,
                evidence_id=None,
                confidence=0.97,
            )
        ],
    )

    result = ReplySafetyPolicy().evaluate(
        "The provider frobnicated the customer's balance.",
        evidence_kind=ReplyEvidenceKind.FAQ,
        claim_inventory=inventory,
    )

    assert result.is_safe is False
    assert result.reason_codes == ["UNAUTHORIZED_COMMITMENT"]


def test_structured_faq_policy_must_bind_current_citation() -> None:
    """FAQ 政策说明只能绑定本次检索命中的 chunk。"""
    import uuid

    chunk_id = uuid.uuid4()
    inventory = BusinessClaimInventory(
        complete=True,
        claims=[
            BusinessClaim(
                subject_type=BusinessClaimSubjectType.REFUND_POLICY,
                subject_id=None,
                action=BusinessClaimAction.EXPLAIN_POLICY,
                tense=BusinessClaimTense.TIMELESS,
                polarity=BusinessClaimPolarity.AFFIRMED,
                condition=BusinessClaimCondition.ACTUAL,
                evidence_type=BusinessClaimEvidenceType.FAQ_CHUNK,
                evidence_id=chunk_id,
                confidence=0.91,
            )
        ],
    )

    allowed = ReplySafetyPolicy().evaluate(
        "退款申请需要平台审核。",
        evidence_kind=ReplyEvidenceKind.FAQ,
        claim_inventory=inventory,
        faq_evidence_ids={chunk_id},
    )
    denied = ReplySafetyPolicy().evaluate(
        "退款申请需要平台审核。",
        evidence_kind=ReplyEvidenceKind.FAQ,
        claim_inventory=inventory,
        faq_evidence_ids=set(),
    )

    assert allowed.is_safe is True
    assert denied.is_safe is False
    assert "INVALID_BUSINESS_CLAIM_EVIDENCE" in denied.reason_codes


def test_structured_tool_fact_must_bind_matching_successful_tool_call() -> None:
    """实时物流事实必须绑定本次成功的物流查询，而不是任意工具。"""
    import uuid

    tool_call_id = uuid.uuid4()
    inventory = BusinessClaimInventory(
        complete=True,
        claims=[
            BusinessClaim(
                subject_type=BusinessClaimSubjectType.LOGISTICS,
                subject_id="trusted-order-id",
                action=BusinessClaimAction.REPORT_STATUS,
                tense=BusinessClaimTense.PRESENT,
                polarity=BusinessClaimPolarity.AFFIRMED,
                condition=BusinessClaimCondition.ACTUAL,
                evidence_type=BusinessClaimEvidenceType.TOOL_CALL,
                evidence_id=tool_call_id,
                confidence=0.94,
            )
        ],
    )

    store_id = uuid.uuid4()
    allowed = ReplySafetyPolicy().evaluate(
        "订单正在运输中。",
        evidence_kind=ReplyEvidenceKind.TOOL,
        claim_inventory=inventory,
        successful_tool_evidence={
            tool_call_id: TrustedToolEvidence(
                tool_name="query_logistics",
                store_id=store_id,
                subject_ids=frozenset({"trusted-order-id"}),
            )
        },
    )
    denied = ReplySafetyPolicy().evaluate(
        "订单正在运输中。",
        evidence_kind=ReplyEvidenceKind.TOOL,
        claim_inventory=inventory,
        successful_tool_evidence={
            tool_call_id: TrustedToolEvidence(
                tool_name="query_customer_profile",
                store_id=store_id,
                subject_ids=frozenset({"trusted-order-id"}),
            )
        },
    )

    assert allowed.is_safe is True
    assert denied.is_safe is False
    assert "INVALID_BUSINESS_CLAIM_EVIDENCE" in denied.reason_codes


def test_model_authored_claim_inventory_cannot_authorize_automatic_delivery() -> None:
    """模型自报 complete=true 不能把自由文本升级为自动发送授权。"""
    inventory = BusinessClaimInventory(complete=True, claims=[])

    result = ReplySafetyPolicy().evaluate(
        "补偿需审核，财务方完成了向买家的价值返置。",
        evidence_kind=ReplyEvidenceKind.FAQ,
        claim_inventory=inventory,
    )

    assert result.automatic_delivery_allowed is False


def test_tool_evidence_must_bind_claimed_business_object() -> None:
    """订单 A 的工具证据不能被订单 B 的声明借用。"""
    import uuid

    store_id = uuid.uuid4()
    tool_call_id = uuid.uuid4()
    evidence = {
        tool_call_id: {
            "tool_name": "query_logistics",
            "store_id": store_id,
            "subject_ids": ["ORDER-A"],
            "mocked": False,
        }
    }

    def inventory(subject_id: str) -> BusinessClaimInventory:
        return BusinessClaimInventory(
            complete=True,
            claims=[
                BusinessClaim(
                    subject_type=BusinessClaimSubjectType.LOGISTICS,
                    subject_id=subject_id,
                    action=BusinessClaimAction.REPORT_STATUS,
                    tense=BusinessClaimTense.PRESENT,
                    polarity=BusinessClaimPolarity.AFFIRMED,
                    condition=BusinessClaimCondition.ACTUAL,
                    evidence_type=BusinessClaimEvidenceType.TOOL_CALL,
                    evidence_id=tool_call_id,
                    confidence=0.95,
                )
            ],
        )

    allowed = ReplySafetyPolicy().evaluate(
        "订单正在运输中。",
        evidence_kind=ReplyEvidenceKind.TOOL,
        claim_inventory=inventory("ORDER-A"),
        successful_tool_evidence=evidence,  # type: ignore[arg-type]
    )
    denied = ReplySafetyPolicy().evaluate(
        "订单 B 正在运输中。",
        evidence_kind=ReplyEvidenceKind.TOOL,
        claim_inventory=inventory("ORDER-B"),
        successful_tool_evidence=evidence,  # type: ignore[arg-type]
    )
    denied_cross_store = ReplySafetyPolicy().evaluate(
        "订单正在运输中。",
        evidence_kind=ReplyEvidenceKind.TOOL,
        claim_inventory=inventory("ORDER-A"),
        successful_tool_evidence=evidence,  # type: ignore[arg-type]
        expected_store_id=uuid.uuid4(),
    )

    assert allowed.is_safe is True
    assert denied.is_safe is False
    assert "INVALID_BUSINESS_CLAIM_EVIDENCE" in denied.reason_codes
    assert denied_cross_store.is_safe is False
    assert "INVALID_BUSINESS_CLAIM_EVIDENCE" in denied_cross_store.reason_codes


@pytest.mark.parametrize(
    ("subject_type", "action", "polarity", "condition"),
    [
        (
            BusinessClaimSubjectType.SHIPPING_ADDRESS,
            BusinessClaimAction.UPDATE,
            BusinessClaimPolarity.AFFIRMED,
            BusinessClaimCondition.CONDITIONAL,
        ),
        (
            BusinessClaimSubjectType.COUPON,
            BusinessClaimAction.SEND,
            BusinessClaimPolarity.NEGATED,
            BusinessClaimCondition.ACTUAL,
        ),
    ],
)
def test_high_risk_claim_with_non_actual_or_non_affirmed_scope_fails_closed(
    subject_type: BusinessClaimSubjectType,
    action: BusinessClaimAction,
    polarity: BusinessClaimPolarity,
    condition: BusinessClaimCondition,
) -> None:
    """写操作声明的否定或条件作用域不能被当成已验证事实。"""
    import uuid

    store_id = uuid.uuid4()
    tool_call_id = uuid.uuid4()
    subject_id = "trusted-subject"
    tool_name = (
        "update_shipping_address" if subject_type == BusinessClaimSubjectType.SHIPPING_ADDRESS else "send_coupon"
    )
    inventory = BusinessClaimInventory(
        complete=True,
        claims=[
            BusinessClaim(
                subject_type=subject_type,
                subject_id=subject_id,
                action=action,
                tense=BusinessClaimTense.PRESENT,
                polarity=polarity,
                condition=condition,
                evidence_type=BusinessClaimEvidenceType.TOOL_CALL,
                evidence_id=tool_call_id,
                confidence=0.95,
            )
        ],
    )

    result = ReplySafetyPolicy().evaluate(
        "该业务动作的作用域需要人工确认。",
        evidence_kind=ReplyEvidenceKind.TOOL,
        claim_inventory=inventory,
        successful_tool_evidence={
            tool_call_id: TrustedToolEvidence(
                tool_name=tool_name,  # type: ignore[arg-type]
                store_id=store_id,
                subject_ids=frozenset({subject_id}),
            )
        },
        expected_store_id=store_id,
    )

    assert result.is_safe is False
    assert "AMBIGUOUS_BUSINESS_CLAIM_SCOPE" in result.reason_codes


def test_current_order_status_rejects_future_tense_even_with_matching_evidence() -> None:
    """查询工具只证明当前状态，不能把它扩展为未来订单结果。"""
    import uuid

    store_id = uuid.uuid4()
    tool_call_id = uuid.uuid4()
    inventory = BusinessClaimInventory(
        complete=True,
        claims=[
            BusinessClaim(
                subject_type=BusinessClaimSubjectType.ORDER,
                subject_id="ORDER-A",
                action=BusinessClaimAction.REPORT_STATUS,
                tense=BusinessClaimTense.FUTURE,
                polarity=BusinessClaimPolarity.AFFIRMED,
                condition=BusinessClaimCondition.ACTUAL,
                evidence_type=BusinessClaimEvidenceType.TOOL_CALL,
                evidence_id=tool_call_id,
                confidence=0.99,
            )
        ],
    )

    result = ReplySafetyPolicy().evaluate(
        "订单明天将完成。",
        evidence_kind=ReplyEvidenceKind.TOOL,
        claim_inventory=inventory,
        successful_tool_evidence={
            tool_call_id: TrustedToolEvidence(
                tool_name="query_order",
                store_id=store_id,
                subject_ids=frozenset({"ORDER-A"}),
            )
        },
        expected_store_id=store_id,
    )

    assert result.is_safe is False
    assert "BUSINESS_CLAIM_TENSE_MISMATCH" in result.reason_codes


def test_delivery_time_promise_is_a_first_class_high_risk_claim() -> None:
    """承诺送达时间必须进入结构化声明，并在没有专用证据端口时失败关闭。"""
    inventory = BusinessClaimInventory(
        complete=True,
        claims=[
            BusinessClaim(
                subject_type=BusinessClaimSubjectType.PROMISE_TIME,
                subject_id="ORDER-A",
                action=BusinessClaimAction.PROMISE,
                tense=BusinessClaimTense.FUTURE,
                polarity=BusinessClaimPolarity.AFFIRMED,
                condition=BusinessClaimCondition.ACTUAL,
                evidence_type=BusinessClaimEvidenceType.NONE,
                evidence_id=None,
                confidence=0.98,
            )
        ],
    )

    result = ReplySafetyPolicy().evaluate(
        "订单保证明天送达。",
        evidence_kind=ReplyEvidenceKind.TOOL,
        claim_inventory=inventory,
    )

    assert result.is_safe is False
    assert "UNAUTHORIZED_COMMITMENT" in result.reason_codes


def test_inventory_rejects_conflicting_polarity_for_same_business_claim() -> None:
    """同一主体和动作不能借不同证据或时态同时声明相反结果。"""
    import uuid

    with pytest.raises(ValidationError):
        BusinessClaimInventory(
            complete=True,
            claims=[
                BusinessClaim(
                    subject_type=BusinessClaimSubjectType.REFUND_POLICY,
                    subject_id=None,
                    action=BusinessClaimAction.EXPLAIN_POLICY,
                    tense=BusinessClaimTense.TIMELESS,
                    polarity=BusinessClaimPolarity.AFFIRMED,
                    condition=BusinessClaimCondition.ACTUAL,
                    evidence_type=BusinessClaimEvidenceType.FAQ_CHUNK,
                    evidence_id=uuid.uuid4(),
                    confidence=0.95,
                ),
                BusinessClaim(
                    subject_type=BusinessClaimSubjectType.REFUND_POLICY,
                    subject_id=None,
                    action=BusinessClaimAction.EXPLAIN_POLICY,
                    tense=BusinessClaimTense.PRESENT,
                    polarity=BusinessClaimPolarity.NEGATED,
                    condition=BusinessClaimCondition.ACTUAL,
                    evidence_type=BusinessClaimEvidenceType.FAQ_CHUNK,
                    evidence_id=uuid.uuid4(),
                    confidence=0.95,
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
def test_faq_cannot_prove_current_customer_instance_action(
    subject_type: BusinessClaimSubjectType,
    action: BusinessClaimAction,
) -> None:
    """有效 FAQ 引用也不能证明当前客户的查询、提交或展示结果。"""
    import uuid

    chunk_id = uuid.uuid4()
    inventory = BusinessClaimInventory(
        complete=True,
        claims=[
            BusinessClaim(
                subject_type=subject_type,
                subject_id="CURRENT-OBJECT",
                action=action,
                tense=BusinessClaimTense.PRESENT,
                polarity=BusinessClaimPolarity.AFFIRMED,
                condition=BusinessClaimCondition.ACTUAL,
                evidence_type=BusinessClaimEvidenceType.FAQ_CHUNK,
                evidence_id=chunk_id,
                confidence=0.99,
            )
        ],
    )

    result = ReplySafetyPolicy().evaluate(
        "当前客户实例动作已经完成。",
        evidence_kind=ReplyEvidenceKind.FAQ,
        claim_inventory=inventory,
        faq_evidence_ids={chunk_id},
    )

    assert result.is_safe is False
    assert result.reason_codes


def test_instance_query_rejects_future_tense_without_tool_mapping() -> None:
    """实例查询只能描述当前动作，不能使用未来时态绕过证据门禁。"""
    inventory = BusinessClaimInventory(
        complete=True,
        claims=[
            BusinessClaim(
                subject_type=BusinessClaimSubjectType.ORDER,
                subject_id="ORDER-A",
                action=BusinessClaimAction.QUERY,
                tense=BusinessClaimTense.FUTURE,
                polarity=BusinessClaimPolarity.AFFIRMED,
                condition=BusinessClaimCondition.ACTUAL,
                evidence_type=BusinessClaimEvidenceType.NONE,
                evidence_id=None,
                confidence=0.99,
            )
        ],
    )

    result = ReplySafetyPolicy().evaluate(
        "系统未来会查询订单。",
        evidence_kind=ReplyEvidenceKind.TOOL,
        claim_inventory=inventory,
    )

    assert result.is_safe is False
    assert "BUSINESS_CLAIM_TENSE_MISMATCH" in result.reason_codes


@pytest.mark.parametrize(
    ("tool_name", "data", "expected_subject", "expected_action"),
    [
        (
            "query_customer_profile",
            {
                "customer_id": "00000000-0000-0000-0000-000000000001",
                "tags": [],
                "order_count": 2,
                "total_spend": "99.00",
            },
            BusinessClaimSubjectType.CUSTOMER_PROFILE,
            BusinessClaimAction.REPORT_STATUS,
        ),
        (
            "update_shipping_address",
            {
                "order_id": "00000000-0000-0000-0000-000000000002",
                "status": "pending_confirmation",
                "mocked": True,
            },
            BusinessClaimSubjectType.SHIPPING_ADDRESS,
            BusinessClaimAction.SUBMIT_REQUEST,
        ),
        (
            "send_coupon",
            {
                "issuance_id": "00000000-0000-0000-0000-000000000003",
                "coupon_code": "WELCOME10",
                "status": "issued",
                "mocked": True,
            },
            BusinessClaimSubjectType.COUPON,
            BusinessClaimAction.SEND,
        ),
        (
            "send_platform_message",
            {
                "message_id": "00000000-0000-0000-0000-000000000004",
                "status": "sent",
                "mocked": False,
            },
            BusinessClaimSubjectType.PLATFORM_MESSAGE,
            BusinessClaimAction.SEND,
        ),
    ],
)
def test_authoritative_claims_cover_all_supported_high_risk_tool_results(
    tool_name: str,
    data: dict[str, object],
    expected_subject: BusinessClaimSubjectType,
    expected_action: BusinessClaimAction,
) -> None:
    """服务端应为画像、地址、优惠和平台消息生成对象级可信声明。"""
    import uuid

    tool_call_id = uuid.uuid4()
    inventory = build_authoritative_tool_claims(
        [
            ExecutedAgentTool(
                tool_name=tool_name,  # type: ignore[arg-type]
                result=ToolResult(
                    tool_call_id=tool_call_id,
                    status="succeeded",
                    data=data,
                    mocked=bool(data.get("mocked", False)),
                ),
            )
        ]
    )

    assert len(inventory.claims) == 1
    claim = inventory.claims[0]
    assert claim.subject_type == expected_subject
    assert claim.action == expected_action
    assert claim.evidence_type == BusinessClaimEvidenceType.TOOL_CALL
    assert claim.evidence_id == tool_call_id
    assert claim.confidence == 1.0


def test_authoritative_claims_reject_incomplete_tool_output() -> None:
    """权威声明生成点必须再次拒绝缺少强类型必填字段的成功结果。"""
    import uuid

    inventory = build_authoritative_tool_claims(
        [
            ExecutedAgentTool(
                tool_name="query_order",
                result=ToolResult(
                    tool_call_id=uuid.uuid4(),
                    status="succeeded",
                    data={
                        "order_id": "00000000-0000-0000-0000-000000000001",
                        "status": "paid",
                    },
                ),
            )
        ]
    )

    assert inventory.claims == []


def test_versioned_read_replay_summary_remains_trusted_tool_evidence() -> None:
    """低敏只读重放须恢复声明与对象证据，不能仅把状态改成成功。"""
    import uuid

    store_id = uuid.uuid4()
    tool_call_id = uuid.uuid4()
    order_id = uuid.uuid4()
    execution = ExecutedAgentTool(
        tool_name="query_logistics",
        source_store_id=store_id,
        result=ToolResult(
            tool_call_id=tool_call_id,
            status="succeeded",
            data={"order_id": str(order_id), "tracking_status": "in_transit"},
            replayed=True,
            replay_contract_version=1,
        ),
    )

    inventory = build_authoritative_tool_claims([execution])
    evidence = build_trusted_tool_evidence([execution])

    assert len(inventory.claims) == 1
    assert inventory.claims[0].subject_id == str(order_id)
    assert inventory.claims[0].evidence_id == tool_call_id
    assert evidence[tool_call_id].subject_ids == frozenset({str(order_id)})


def test_read_replay_without_known_contract_version_fails_closed() -> None:
    """替代端口只设置 replayed 不能绕过完整工具输出校验。"""
    import uuid

    execution = ExecutedAgentTool(
        tool_name="query_order",
        source_store_id=uuid.uuid4(),
        result=ToolResult(
            tool_call_id=uuid.uuid4(),
            status="succeeded",
            data={"order_id": str(uuid.uuid4()), "status": "paid"},
            replayed=True,
        ),
    )

    assert build_authoritative_tool_claims([execution]).claims == []
    assert build_trusted_tool_evidence([execution]) == {}


def test_tool_evidence_uses_execution_source_store_instead_of_current_workflow_store() -> None:
    """证据必须保留执行来源店铺，不能在策略入口被当前工作流重新贴标。"""
    import uuid

    origin_store_id = uuid.uuid4()
    execution = ExecutedAgentTool(
        tool_name="query_order",
        source_store_id=origin_store_id,
        result=ToolResult(
            tool_call_id=uuid.uuid4(),
            status="succeeded",
            data={
                "order_id": str(uuid.uuid4()),
                "external_order_id": "EXT-PROVENANCE-001",
                "status": "pending",
                "payment_status": "pending",
                "fulfillment_status": "unfulfilled",
                "currency": "USD",
                "total_amount": "10.00",
                "ordered_at": None,
            },
        ),
    )

    evidence = build_trusted_tool_evidence([execution])
    inventory = build_authoritative_tool_claims([execution])
    current_workflow_store_id = uuid.uuid4()
    result = ReplySafetyPolicy().evaluate(
        "订单当前正在处理中。",
        evidence_kind=ReplyEvidenceKind.TOOL,
        successful_tools={"query_order"},
        claim_inventory=inventory,
        successful_tool_evidence=evidence,
        content_origin=ReplyContentOrigin.TRUSTED_TOOL_TEMPLATE,
        expected_store_id=current_workflow_store_id,
    )

    assert evidence[execution.result.tool_call_id].store_id == origin_store_id
    assert result.is_safe is False
    assert result.automatic_delivery_allowed is False
    assert "INVALID_BUSINESS_CLAIM_EVIDENCE" in result.reason_codes


def test_tool_evidence_without_execution_source_fails_closed() -> None:
    """旧替身未携带执行店铺时不得生成可授权的可信证据。"""
    import uuid

    execution = ExecutedAgentTool(
        tool_name="query_order",
        result=ToolResult(
            tool_call_id=uuid.uuid4(),
            status="succeeded",
            data={
                "order_id": str(uuid.uuid4()),
                "external_order_id": "EXT-MISSING-PROVENANCE",
                "status": "pending",
                "payment_status": "pending",
                "fulfillment_status": "unfulfilled",
                "currency": "USD",
                "total_amount": "10.00",
                "ordered_at": None,
            },
        ),
    )

    assert build_trusted_tool_evidence([execution]) == {}


def test_mock_address_submission_claim_is_blocked_by_structured_policy() -> None:
    """Mock 地址提交属于写动作，即使措辞未命中文本规则也不能视为真实完成。"""
    import uuid

    store_id = uuid.uuid4()
    tool_call_id = uuid.uuid4()
    order_id = uuid.uuid4()
    execution = ExecutedAgentTool(
        tool_name="update_shipping_address",
        source_store_id=store_id,
        result=ToolResult(
            tool_call_id=tool_call_id,
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
    evidence = build_trusted_tool_evidence([execution])

    result = ReplySafetyPolicy().evaluate(
        "地址调整请求已递交至渠道处理队列。",
        evidence_kind=ReplyEvidenceKind.TOOL,
        successful_tools={"update_shipping_address"},
        claim_inventory=inventory,
        successful_tool_evidence=evidence,
        content_origin=ReplyContentOrigin.MODEL_GENERATED,
        expected_store_id=store_id,
    )

    assert result.is_safe is False
    assert "MOCK_COMPLETION_CLAIM" in result.reason_codes


def test_trusted_tool_template_without_claim_inventory_fails_closed() -> None:
    """可信来源标签不能替代结构化声明，缺少清单时不得授权自动交付。"""
    result = ReplySafetyPolicy().evaluate(
        "Your order is currently being processed.",
        evidence_kind=ReplyEvidenceKind.TOOL,
        successful_tools={"query_order"},
        claim_inventory=None,
        content_origin=ReplyContentOrigin.TRUSTED_TOOL_TEMPLATE,
    )

    assert result.is_safe is False
    assert result.automatic_delivery_allowed is False
    assert "BUSINESS_CLAIM_INVENTORY_MISSING" in result.reason_codes


@pytest.mark.parametrize(
    ("tool_name", "summary"),
    [
        (
            "update_shipping_address",
            {"order_id": "00000000-0000-0000-0000-000000000501", "status": "pending_confirmation"},
        ),
        (
            "send_coupon",
            {"issuance_id": "00000000-0000-0000-0000-000000000502", "status": "issued"},
        ),
        (
            "send_platform_message",
            {"message_id": "00000000-0000-0000-0000-000000000503", "status": "sent"},
        ),
    ],
)
def test_replayed_mock_write_with_incomplete_summary_fails_closed(
    tool_name: str,
    summary: dict[str, object],
) -> None:
    """替代端口返回成功重放摘要时，Agent 仍须保留 Mock 写动作阻断语义。"""
    import uuid

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
    assert result.automatic_delivery_allowed is False
    assert "MOCK_COMPLETION_CLAIM" in result.reason_codes
