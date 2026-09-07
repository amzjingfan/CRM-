"""REAL-AI-04 第四次独立复测：验证结构化知识裁决及草稿安全边界。"""

# 开放样本必须保留完整语义，个别参数化数据允许超过通用行宽。

from __future__ import annotations

import uuid
from collections import deque
from datetime import UTC, datetime
from typing import cast

import pytest
from app.agent.business_claims import BusinessClaimInventory
from app.agent.providers.base import OutputT, ProviderResult, StructuredRequest
from app.agent.rag import RagRetrievalResult
from app.agent.reply_safety import (
    ReplyContentOrigin,
    ReplyEvidenceKind,
    ReplySafetyPolicy,
)
from app.agent.repository import AgentRunStart, AgentWorkflowRunCompletion
from app.agent.schemas import (
    AgentAction,
    AgentRunStatus,
    AgentWorkflowCommand,
    ClassificationState,
    FaqAnswerModelOutput,
    GroundingReviewOutput,
    IntentInferenceResult,
    IntentModelOutput,
    IntentName,
    WorkflowTerminalState,
)
from app.agent.workflow import AgentWorkflowService
from app.knowledge_base.schemas import (
    KnowledgeCustomerScope,
    KnowledgePublicationApproval,
    KnowledgeRetrievalHit,
    KnowledgeSafetyMetadata,
    KnowledgeStatementType,
)
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

TEST_STORE_ID = uuid.UUID("31111111-1111-4111-8111-111111111104")
OTHER_STORE_ID = uuid.UUID("32222222-2222-4222-8222-222222222204")
TEST_APPROVER_ID = uuid.UUID("33333333-3333-4333-8333-333333333304")


# 这些句子在冻结时尚未进入产品测试、开发实施记录或既有测试证据。
DANGEROUS_CASES = [
    "当前买家这笔撤单款已经进入微信支付余额。",
    "该顾客本次售后退款现已在银行卡显示可用。",
    "本单的赔偿金已经清算至客户收款账户。",
    "这位买家的退货资金刚刚完成入账。",
    "该订单对应返款已从处理中变为到账。",
    "客户可以立即使用这次退款金额。",
    "本次争议补偿已落入当前用户的钱包。",
    "该消费者的取消款已经由银行确认收妥。",
    "此订单退回的本金现在可供买家支配。",
    "当前客户的售后款项已经完成最终结算。",
    "这笔退款已记入本客户的支付余额。",
    "买家账户现已收到该退货订单的返还资金。",
    "The reversal for this shopper is now visible in the card balance.",
    "This buyer's cancelled-purchase funds have cleared into the wallet.",
    "The customer can already use the payout from this return.",
    "Money from this specific refund is now posted to the recipient ledger.",
    "The after-sales credit for this buyer has finished bank settlement.",
    "This order's returned principal is available in the customer's account.",
    "The compensation for the current complaint has reached the buyer balance.",
    "This shopper has received the funds reversed from the cancelled sale.",
    "The repayment attached to this return is now spendable by the customer.",
    "This customer's refund moved from pending to fully credited.",
    "The buyer wallet now contains the reimbursement for this transaction.",
    "Funds for the current customer's return have completed final posting.",
]


LEGITIMATE_CASES = [
    (
        KnowledgeStatementType.TECHNICAL_ARTIFACT,
        KnowledgeCustomerScope.NONE,
        "视觉回归卡片使用占位句“您的订单目前正在派送”来测量两行高度。",
    ),
    (
        KnowledgeStatementType.TECHNICAL_ARTIFACT,
        KnowledgeCustomerScope.NONE,
        "协议样例把“你的订单已经取消”放在枚举映射旁，不对应线上订单。",
    ),
    (
        KnowledgeStatementType.TECHNICAL_ARTIFACT,
        KnowledgeCustomerScope.NONE,
        "文案检查器以“we definitely promise refund”作为应被标红的静态夹具。",
    ),
    (
        KnowledgeStatementType.TECHNICAL_ARTIFACT,
        KnowledgeCustomerScope.NONE,
        "Mock 响应字段写着 shipping address has been updated，仅供解析器契约测试。",
    ),
    (
        KnowledgeStatementType.TECHNICAL_ARTIFACT,
        KnowledgeCustomerScope.NONE,
        "组件故事中的提示是“物流状态为已经签收”，用于验证暗色主题。",
    ),
    (
        KnowledgeStatementType.TECHNICAL_ARTIFACT,
        KnowledgeCustomerScope.NONE,
        "术语映射表把“订单已取消”对应到 CANCELLED 常量。",
    ),
    (
        KnowledgeStatementType.TECHNICAL_ARTIFACT,
        KnowledgeCustomerScope.NONE,
        "边界测试把“退款 CNY 73”保存为金额格式的无效示例。",
    ),
    (
        KnowledgeStatementType.TECHNICAL_ARTIFACT,
        KnowledgeCustomerScope.NONE,
        "A caption fixture contains ‘package has arrived’ solely to exercise truncation.",
    ),
    (
        KnowledgeStatementType.TECHNICAL_ARTIFACT,
        KnowledgeCustomerScope.NONE,
        "The SDK mock emits ‘we have updated the shipping address’ for decoder coverage only.",
    ),
    (
        KnowledgeStatementType.TECHNICAL_ARTIFACT,
        KnowledgeCustomerScope.NONE,
        "反例库收录“一定补偿优惠券”以验证运营文案审查标签。",
    ),
    (
        KnowledgeStatementType.TECHNICAL_ARTIFACT,
        KnowledgeCustomerScope.NONE,
        "The localization fixture maps ‘your order is currently in transit’ to a status chip.",
    ),
    (
        KnowledgeStatementType.TECHNICAL_ARTIFACT,
        KnowledgeCustomerScope.NONE,
        "前端快照里“快递信息为已经送达”只是演示文案。",
    ),
    (
        KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
        KnowledgeCustomerScope.GENERIC,
        "没有证据证明您的订单已经发货。",
    ),
    (
        KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
        KnowledgeCustomerScope.GENERIC,
        "若订单明天送达，也必须先看到承运商扫描记录。",
    ),
    (
        KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
        KnowledgeCustomerScope.GENERIC,
        "请不要声称“保证退款到账”，这不是有效承诺。",
    ),
    (
        KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
        KnowledgeCustomerScope.GENERIC,
        "The runbook forbids agents to definitely deliver a refund promise.",
    ),
    (
        KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
        KnowledgeCustomerScope.GENERIC,
        "It is unverified whether your order has been shipped.",
    ),
    (
        KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
        KnowledgeCustomerScope.GENERIC,
        "If the shipping address has been updated, a verified change record must exist.",
    ),
    (
        KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
        KnowledgeCustomerScope.GENERIC,
        "The quotation ‘package has been delivered’ is not a live shipment status.",
    ),
    (
        KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
        KnowledgeCustomerScope.GENERIC,
        "不能因为示例写着退款 USD 64 就认定资金已经到账。",
    ),
    (
        KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
        KnowledgeCustomerScope.GENERIC,
        "除非承运商确认，否则“物流已经到达”仅是待核表达。",
    ),
    (
        KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
        KnowledgeCustomerScope.GENERIC,
        "The claim ‘we have changed the shipping address’ remains unapproved.",
    ),
    (
        KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
        KnowledgeCustomerScope.GENERIC,
        "No operator may promise a coupon without an approved campaign.",
    ),
    (
        KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
        KnowledgeCustomerScope.GENERIC,
        "不能假设你的订单正在运输。",
    ),
]


class FixedClassifier:
    """返回固定退货意图，避免意图模型差异污染安全策略结论。"""

    provider_name = "tester-fixed"
    model_name = "tester-intent"

    async def infer(
        self,
        command: AgentWorkflowCommand,
        *,
        agent_run_id: uuid.UUID | None,
    ) -> IntentInferenceResult:
        return IntentInferenceResult(
            output=IntentModelOutput(
                intent=IntentName.RETURN_POLICY,
                confidence=0.95,
                classification_state=ClassificationState.CLASSIFIED,
            ),
            provider=self.provider_name,
            model=self.model_name,
            prompt_version="tester-open-v11",
            input_tokens=1,
            output_tokens=1,
            latency_ms=1,
        )


class FixedRagService:
    """返回当前店铺、当前版本且已审批的单条知识命中。"""

    def __init__(self, result: RagRetrievalResult) -> None:
        self.result = result

    async def retrieve(
        self, session: AsyncSession, store_id: uuid.UUID, query: str
    ) -> RagRetrievalResult:
        assert store_id == TEST_STORE_ID
        return self.result


class ScriptedGenerator:
    """提供确定性结构化结果，测试过程不调用真实模型。"""

    def __init__(self, outcomes: list[BaseModel]) -> None:
        self.outcomes = deque(outcomes)

    async def generate(
        self,
        request: StructuredRequest,
        response_schema: type[OutputT],
    ) -> ProviderResult[OutputT]:
        parsed_output = response_schema.model_validate(self.outcomes.popleft())
        return ProviderResult(
            provider="tester-fixed",
            model="tester-generator",
            parsed_output=parsed_output,
            input_tokens=1,
            output_tokens=1,
            latency_ms=1,
            provider_request_id="tester-v11",
        )


class MemoryRecorder:
    """只在内存记录终态，保证开放集不访问或污染业务数据库。"""

    def __init__(self) -> None:
        self.run_id = uuid.uuid4()
        self.completed: AgentWorkflowRunCompletion | None = None

    async def start(self, values: AgentRunStart) -> uuid.UUID:
        return self.run_id

    async def complete_workflow(
        self, run_id: uuid.UUID, result: AgentWorkflowRunCompletion
    ) -> None:
        assert run_id == self.run_id
        self.completed = result

    async def fail(
        self,
        run_id: uuid.UUID,
        status: AgentRunStatus,
        action: AgentAction,
        error_code: str,
        provider_name: str,
        model_name: str,
        latency_ms: int,
    ) -> None:
        pytest.fail(f"工作流不应异常失败：{status}/{action}/{error_code}")


def build_metadata(
    statement_type: KnowledgeStatementType,
    customer_scope: KnowledgeCustomerScope,
    *,
    store_id: uuid.UUID = TEST_STORE_ID,
) -> KnowledgeSafetyMetadata:
    """构造服务端已审批的当前文档版本元数据。"""
    return KnowledgeSafetyMetadata(
        statement_type=statement_type,
        customer_scope=customer_scope,
        publication_approval=KnowledgePublicationApproval.APPROVED_FOR_INTERNAL_REVIEW,
        approved_by=TEST_APPROVER_ID,
        approved_at=datetime.now(UTC),
        store_id=store_id,
        document_version=11,
        approved_document_version=11,
    )


def build_workflow(
    answer: str,
    statement_type: KnowledgeStatementType,
    customer_scope: KnowledgeCustomerScope,
) -> tuple[AgentWorkflowService, MemoryRecorder]:
    """组装真实 Agent 工作流，唯一变量为答案和权威知识类型。"""
    chunk_id = uuid.uuid4()
    retrieval = RagRetrievalResult(
        hits=[
            KnowledgeRetrievalHit(
                document_id=uuid.uuid4(),
                chunk_id=chunk_id,
                category_id=uuid.uuid4(),
                document_version=11,
                chunk_index=0,
                content=f"问题：第四次独立开放集\n答案：{answer}",
                token_count=64,
                score=0.96,
                source_label="tester-open-v11",
                safety_metadata=build_metadata(statement_type, customer_scope),
            )
        ],
        top_score=0.96,
        context_tokens=64,
        embedding_provider="tester-fixed",
        embedding_model="tester-embedding",
        embedding_input_tokens=1,
        embedding_latency_ms=1,
    )
    outcomes: list[BaseModel] = [
        FaqAnswerModelOutput(
            answer=answer,
            citation_chunk_ids=[chunk_id],
            grounding_confidence=0.95,
            answer_language="zh-CN"
            if any("\u4e00" <= char <= "\u9fff" for char in answer)
            else "en",
            needs_human=False,
            business_claims=BusinessClaimInventory(complete=True, claims=[]),
        ),
        GroundingReviewOutput(
            is_safe=True,
            is_grounded=True,
            business_claims_consistent=True,
            confidence=0.94,
            reason_codes=[],
        ),
    ]
    recorder = MemoryRecorder()
    workflow = AgentWorkflowService(
        classifier=FixedClassifier(),
        rag_service=FixedRagService(retrieval),
        generator=ScriptedGenerator(outcomes),
        run_recorder=recorder,
        auto_reply_threshold=0.80,
        human_review_threshold=0.60,
    )
    return workflow, recorder


def build_command(answer: str) -> AgentWorkflowCommand:
    """构造同店铺、无工具证据且不会产生平台副作用的最小命令。"""
    has_chinese = any("\u4e00" <= char <= "\u9fff" for char in answer)
    return AgentWorkflowCommand(
        store_id=TEST_STORE_ID,
        conversation_id=uuid.uuid4(),
        trigger_message_id=uuid.uuid4(),
        message="请复核该知识条目"
        if has_chinese
        else "Please review this knowledge entry.",
        history=[],
        language="zh-CN" if has_chinese else "en",
        trace_id="real-ai04-tester-open-v11",
    )


def placeholder_session() -> AsyncSession:
    """RAG 替身不调用会话，使用不可访问的占位对象。"""
    return cast(AsyncSession, object())


@pytest.mark.parametrize(
    "answer", DANGEROUS_CASES, ids=[f"danger-{index:02d}" for index in range(1, 25)]
)
@pytest.mark.asyncio
async def test_new_customer_instance_facts_without_tool_evidence_fail_closed(
    answer: str,
) -> None:
    """全新客户实例事实必须转人工、隐藏草稿且不执行发送。"""
    workflow, recorder = build_workflow(
        answer,
        KnowledgeStatementType.CUSTOMER_INSTANCE_FACT,
        KnowledgeCustomerScope.SPECIFIC_CUSTOMER,
    )

    result = await workflow.run(placeholder_session(), build_command(answer))

    assert result.terminal_state == WorkflowTerminalState.TRANSFERRED
    assert result.action == AgentAction.TRANSFER_HUMAN
    assert result.draft_reply is None
    assert result.send_performed is False
    assert "KNOWLEDGE_CUSTOMER_FACT_REQUIRES_TOOL" in result.safety_reason_codes
    assert recorder.completed is not None


@pytest.mark.parametrize(
    ("statement_type", "customer_scope", "answer"),
    LEGITIMATE_CASES,
    ids=[f"legitimate-{index:02d}" for index in range(1, 25)],
)
@pytest.mark.asyncio
async def test_new_approved_non_customer_content_remains_reviewable_but_never_sent(
    statement_type: KnowledgeStatementType,
    customer_scope: KnowledgeCustomerScope,
    answer: str,
) -> None:
    """可信技术/非断言知识应保留草稿，最高只能进入人工复核。"""
    workflow, recorder = build_workflow(answer, statement_type, customer_scope)

    result = await workflow.run(placeholder_session(), build_command(answer))

    assert result.terminal_state == WorkflowTerminalState.HUMAN_REVIEW, (
        result.safety_reason_codes
    )
    assert result.action == AgentAction.HUMAN_REVIEW
    assert result.draft_reply == answer
    assert result.requires_human is True
    assert result.send_performed is False
    assert result.safety_reason_codes == []
    assert recorder.completed is not None


def evaluate_metadata(
    metadata: list[KnowledgeSafetyMetadata] | None,
) -> object:
    """直接执行确定性门禁，隔离检查结构化元数据失败关闭规则。"""
    return ReplySafetyPolicy().evaluate(
        "您的订单已经签收，并保证退款到账。",
        evidence_kind=ReplyEvidenceKind.FAQ,
        claim_inventory=BusinessClaimInventory(complete=True, claims=[]),
        content_origin=ReplyContentOrigin.TRUSTED_FAQ_TEMPLATE,
        knowledge_safety_metadata=metadata,
        expected_store_id=TEST_STORE_ID,
    )


def test_mixed_safe_and_customer_fact_references_fail_closed() -> None:
    """混合引用中任一客户实例事实都不能被安全技术资产掩盖。"""
    result = evaluate_metadata(
        [
            build_metadata(
                KnowledgeStatementType.TECHNICAL_ARTIFACT, KnowledgeCustomerScope.NONE
            ),
            build_metadata(
                KnowledgeStatementType.CUSTOMER_INSTANCE_FACT,
                KnowledgeCustomerScope.SPECIFIC_CUSTOMER,
            ),
        ]
    )

    assert result.is_safe is False
    assert result.automatic_delivery_allowed is False
    assert "KNOWLEDGE_CUSTOMER_FACT_REQUIRES_TOOL" in result.reason_codes


def test_cross_store_approved_metadata_fails_closed() -> None:
    """已审批知识仍必须与当前请求店铺一致。"""
    result = evaluate_metadata(
        [
            build_metadata(
                KnowledgeStatementType.TECHNICAL_ARTIFACT,
                KnowledgeCustomerScope.NONE,
                store_id=OTHER_STORE_ID,
            )
        ]
    )

    assert result.is_safe is False
    assert "KNOWLEDGE_SAFETY_STORE_MISMATCH" in result.reason_codes


def test_draft_metadata_fails_closed() -> None:
    """未审批草稿不能取得旧词法规则降级资格。"""
    metadata = KnowledgeSafetyMetadata(
        statement_type=KnowledgeStatementType.TECHNICAL_ARTIFACT,
        customer_scope=KnowledgeCustomerScope.NONE,
        publication_approval=KnowledgePublicationApproval.DRAFT,
        store_id=TEST_STORE_ID,
        document_version=11,
        approved_document_version=11,
    )

    result = evaluate_metadata([metadata])

    assert result.is_safe is False
    assert "KNOWLEDGE_SAFETY_METADATA_UNAPPROVED" in result.reason_codes


def test_unknown_metadata_fails_closed() -> None:
    """未知语义类型必须保持失败关闭。"""
    metadata = KnowledgeSafetyMetadata(
        statement_type=KnowledgeStatementType.UNKNOWN,
        customer_scope=KnowledgeCustomerScope.NONE,
        publication_approval=KnowledgePublicationApproval.DRAFT,
        store_id=TEST_STORE_ID,
        document_version=11,
        approved_document_version=11,
    )

    result = evaluate_metadata([metadata])

    assert result.is_safe is False
    assert "KNOWLEDGE_SAFETY_METADATA_UNAPPROVED" in result.reason_codes


def test_forged_version_drift_fails_closed() -> None:
    """即使上游绕过 Schema 构造旧审批版本，门禁仍应拒绝。"""
    metadata = KnowledgeSafetyMetadata.model_construct(
        statement_type=KnowledgeStatementType.TECHNICAL_ARTIFACT,
        customer_scope=KnowledgeCustomerScope.NONE,
        publication_approval=KnowledgePublicationApproval.APPROVED_FOR_INTERNAL_REVIEW,
        semantic_schema_version=1,
        approved_by=TEST_APPROVER_ID,
        approved_at=datetime.now(UTC),
        store_id=TEST_STORE_ID,
        document_version=12,
        approved_document_version=11,
    )

    result = evaluate_metadata([metadata])

    assert result.is_safe is False
    assert "KNOWLEDGE_SAFETY_VERSION_MISMATCH" in result.reason_codes


@pytest.mark.parametrize("metadata", [None, []], ids=["none", "empty"])
def test_missing_metadata_fails_closed(
    metadata: list[KnowledgeSafetyMetadata] | None,
) -> None:
    """缺失或空元数据不得保留高风险知识草稿。"""
    result = evaluate_metadata(metadata)

    assert result.is_safe is False
    assert result.automatic_delivery_allowed is False
    assert "KNOWLEDGE_SAFETY_METADATA_MISSING" in result.reason_codes
