"""验证 LangGraph FAQ 工作流的状态、置信度和保守降级。"""

import uuid
from collections import deque
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.agent.errors import LLMErrorCode, LLMFailureStage, LLMProviderError
from app.agent.prompt_registry import BusinessPromptId
from app.agent.providers.base import OutputT, ProviderResult, StructuredRequest
from app.agent.rag import RagRetrievalResult
from app.agent.reply_policy import AgentReplyProfile, CustomerLanguage, ReplyTone
from app.agent.repository import AgentRunStart, AgentWorkflowRunCompletion
from app.agent.schemas import (
    AgentAction,
    AgentRunStatus,
    AgentToolRuntimeContext,
    AgentWorkflowCommand,
    ApprovedToolAction,
    ClassificationState,
    FaqAnswerModelOutput,
    GroundingReviewOutput,
    IntentInferenceResult,
    IntentModelOutput,
    IntentName,
    ToolAnswerModelOutput,
    ToolGroundingReviewOutput,
    WorkflowTerminalState,
)
from app.agent.security import PromptSafetyState, evaluate_prompt_safety
from app.agent.tool_execution import AgentToolBatchResult, ExecutedAgentTool
from app.agent.translation import TranslationBundleModelOutput, TranslationService
from app.agent.workflow import AgentWorkflowExecutionError, AgentWorkflowService
from app.agent.workflow_prompt import (
    FAQ_ANSWER_SYSTEM_PROMPT,
    TOOL_ANSWER_SYSTEM_PROMPT,
    build_faq_answer_prompt,
)
from app.knowledge_base.schemas import (
    KnowledgeCustomerScope,
    KnowledgePublicationApproval,
    KnowledgeRetrievalHit,
    KnowledgeSafetyMetadata,
    KnowledgeStatementType,
)
from app.tools.contracts import ToolResult

TEST_STORE_ID = uuid.uuid4()
TEST_APPROVER_ID = uuid.uuid4()


def empty_claim_inventory() -> BusinessClaimInventory:
    """为不涉及高风险业务事实的旧工作流样本提供完整空清单。"""
    return BusinessClaimInventory(complete=True, claims=[])


def logistics_tool_data(
    external_order_id: str = "ORDER-2026-001",
    tracking_status: str = "in_transit",
) -> dict[str, object]:
    """构造通过全栈强类型输出契约的最小物流结果。"""
    return {
        "order_id": str(uuid.uuid5(uuid.NAMESPACE_URL, external_order_id)),
        "external_order_id": external_order_id,
        "tracking_number": None,
        "tracking_status": tracking_status,
        "shipped_at": None,
        "delivered_at": None,
    }


class FixedClassifier:
    """返回固定意图结果，不创建嵌套 agent_run。"""

    provider_name = "fake-llm"
    model_name = "fake-intent"

    def __init__(self, output: IntentModelOutput) -> None:
        self.output = output

    async def infer(self, command: AgentWorkflowCommand, *, agent_run_id: uuid.UUID | None) -> IntentInferenceResult:
        return IntentInferenceResult(
            output=self.output,
            provider=self.provider_name,
            model=self.model_name,
            prompt_version="intent-classifier-v1.0.1",
            input_tokens=10,
            output_tokens=4,
            latency_ms=5,
        )


class FixedRagService:
    """返回固定检索结果，并记录是否被调用。"""

    def __init__(self, result: RagRetrievalResult) -> None:
        self.result = result
        self.calls = 0

    async def retrieve(self, session: AsyncSession, store_id: uuid.UUID, query: str) -> RagRetrievalResult:
        self.calls += 1
        return self.result


class ScriptedGenerator:
    """按节点顺序返回结构化答案和复核结果。"""

    def __init__(self, outcomes: list[BaseModel | dict[str, Any] | LLMProviderError]) -> None:
        self.outcomes = deque(outcomes)
        self.requests: list[StructuredRequest] = []

    async def generate(
        self,
        request: StructuredRequest,
        response_schema: type[OutputT],
    ) -> ProviderResult[OutputT]:
        self.requests.append(request)
        outcome = self.outcomes.popleft()
        if isinstance(outcome, LLMProviderError):
            raise outcome
        output = response_schema.model_validate(outcome)
        return ProviderResult(
            provider="fake-llm",
            model="fake-answer",
            parsed_output=output,
            input_tokens=20,
            output_tokens=8,
            latency_ms=7,
            provider_request_id="fake-generation",
        )


class MemoryWorkflowRecorder:
    """保存完整工作流终态，不访问数据库。"""

    def __init__(self) -> None:
        self.run_id = uuid.uuid4()
        self.started: AgentRunStart | None = None
        self.completed: AgentWorkflowRunCompletion | None = None
        self.failed: tuple[AgentRunStatus, AgentAction, str] | None = None
        self.failure_stage: LLMFailureStage | None = None
        self.output_failure_kind: str | None = None

    async def start(self, values: AgentRunStart) -> uuid.UUID:
        self.started = values
        return self.run_id

    async def complete_workflow(self, run_id: uuid.UUID, result: AgentWorkflowRunCompletion) -> None:
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
        *,
        failure_stage: LLMFailureStage | None = None,
        output_failure_kind: str | None = None,
    ) -> None:
        assert run_id == self.run_id
        self.failed = (status, action, error_code)
        self.failure_stage = failure_stage
        self.output_failure_kind = output_failure_kind


class ScriptedToolService:
    """按节点顺序返回工具批次，避免单元测试访问业务数据库。"""

    def __init__(self, batches: list[AgentToolBatchResult]) -> None:
        self.batches = deque(batches)
        self.required: list[list[str]] = []

    async def execute_required(
        self,
        command: AgentWorkflowCommand,
        *,
        agent_run_id: uuid.UUID,
        required_tools: list[str],
    ) -> AgentToolBatchResult:
        self.required.append(required_tools)
        batch = self.batches.popleft()
        # 生产 AgentToolService 会在调用创建时固定执行店铺。测试替身也必须
        # 模拟这一可信边界，避免用缺失来源的结果意外获得或失去事实授权。
        batch.results = [
            item if item.source_store_id is not None else replace(item, source_store_id=command.store_id)
            for item in batch.results
        ]
        return batch


def command(message: str = "退货期限是多久？") -> AgentWorkflowCommand:
    """构造可信业务服务传入的最小上下文。"""
    return AgentWorkflowCommand(
        store_id=TEST_STORE_ID,
        conversation_id=uuid.uuid4(),
        trigger_message_id=uuid.uuid4(),
        message=message,
        history=[],
        language="zh-CN",
        trace_id="trace-workflow",
    )


def approved_knowledge_metadata(
    statement_type: KnowledgeStatementType = KnowledgeStatementType.POLICY,
    customer_scope: KnowledgeCustomerScope = KnowledgeCustomerScope.GENERIC,
) -> KnowledgeSafetyMetadata:
    """构造测试知识当前版本的人工审批元数据。"""
    return KnowledgeSafetyMetadata(
        statement_type=statement_type,
        customer_scope=customer_scope,
        publication_approval=KnowledgePublicationApproval.APPROVED_FOR_INTERNAL_REVIEW,
        approved_by=TEST_APPROVER_ID,
        approved_at=datetime.now(UTC),
        store_id=TEST_STORE_ID,
        document_version=1,
        approved_document_version=1,
    )


def retrieval(score: float = 0.92) -> RagRetrievalResult:
    """构造一条当前版本 FAQ 命中。"""
    hit = KnowledgeRetrievalHit(
        document_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        category_id=uuid.uuid4(),
        document_version=1,
        chunk_index=0,
        content="问题：退货期限\n答案：签收后七天内可申请退货。",
        token_count=30,
        score=score,
        source_label="退货政策",
        safety_metadata=approved_knowledge_metadata(),
    )
    return RagRetrievalResult(
        hits=[hit],
        top_score=score,
        context_tokens=30,
        embedding_provider="fake",
        embedding_model="fake-1536",
        embedding_input_tokens=5,
        embedding_latency_ms=2,
    )


def test_g5_faq_prompt_sanitizes_source_label_before_provider() -> None:
    from scripts.prepare_sse_staging_fixture import (
        G5_SYNTHETIC_ANSWER,
        G5_SYNTHETIC_ANSWER_V2,
        G5_SYNTHETIC_QUESTION,
    )

    hit = (
        retrieval()
        .hits[0]
        .model_copy(
            update={
                "source_label": "g5-synthetic-only",
                "content": f"问题：{G5_SYNTHETIC_QUESTION}\n答案：{G5_SYNTHETIC_ANSWER}",
            }
        )
    )
    prompt = build_faq_answer_prompt(command(G5_SYNTHETIC_QUESTION), [hit], "en")

    assert '"source_label": "[SENSITIVE_ID]"' in prompt
    assert "g5-synthetic-only" not in prompt
    previous_hit = hit.model_copy(update={"content": f"问题：{G5_SYNTHETIC_QUESTION}\n答案：{G5_SYNTHETIC_ANSWER_V2}"})
    previous_prompt = build_faq_answer_prompt(command(G5_SYNTHETIC_QUESTION), [previous_hit], "en")
    assert (
        evaluate_prompt_safety(previous_prompt, business_prompt_id=BusinessPromptId.FAQ_ANSWER).state
        != PromptSafetyState.ALLOWED
    )
    assert (
        evaluate_prompt_safety(prompt, business_prompt_id=BusinessPromptId.FAQ_ANSWER).state
        == PromptSafetyState.ALLOWED
    )


def service(
    *,
    message_intent: IntentModelOutput,
    rag_result: RagRetrievalResult,
    outcomes: list[BaseModel | dict[str, Any] | LLMProviderError],
    tool_batches: list[AgentToolBatchResult] | None = None,
    enable_translation: bool = False,
) -> tuple[AgentWorkflowService, FixedRagService, ScriptedGenerator, MemoryWorkflowRecorder]:
    """组装完全离线的工作流测试实例。"""
    rag = FixedRagService(rag_result)
    generator = ScriptedGenerator(outcomes)
    recorder = MemoryWorkflowRecorder()
    workflow = AgentWorkflowService(
        classifier=FixedClassifier(message_intent),
        rag_service=rag,
        generator=generator,
        run_recorder=recorder,
        tool_service=ScriptedToolService(tool_batches) if tool_batches is not None else None,
        translation_service=TranslationService(generator) if enable_translation else None,
        auto_reply_threshold=0.80,
        human_review_threshold=0.60,
    )
    return workflow, rag, generator, recorder


@pytest.mark.asyncio
async def test_untyped_published_faq_cannot_authorize_automatic_delivery() -> None:
    """知识发布不等于事实审批；未类型化 FAQ 必须转人工并隐藏草稿。"""
    rag_result = retrieval(0.92)
    rag_result.hits[0].safety_metadata = KnowledgeSafetyMetadata.unapproved(
        store_id=TEST_STORE_ID,
        document_version=1,
    )
    chunk_id = rag_result.hits[0].chunk_id
    workflow, _, _, recorder = service(
        message_intent=IntentModelOutput(
            intent=IntentName.RETURN_POLICY,
            confidence=0.94,
            classification_state=ClassificationState.CLASSIFIED,
        ),
        rag_result=rag_result,
        outcomes=[
            FaqAnswerModelOutput(
                answer="签收后七天内可申请退货。",
                citation_chunk_ids=[chunk_id],
                grounding_confidence=0.90,
                answer_language="zh-CN",
                needs_human=False,
                business_claims=empty_claim_inventory(),
            ),
            GroundingReviewOutput(
                is_safe=True,
                is_grounded=True,
                business_claims_consistent=True,
                confidence=0.88,
                reason_codes=[],
            ),
        ],
    )

    result = await workflow.run(cast_session(), command())

    assert result.terminal_state == WorkflowTerminalState.TRANSFERRED
    assert result.action == AgentAction.TRANSFER_HUMAN
    assert result.final_confidence == 0.0
    assert result.send_performed is False
    assert result.draft_reply is None
    assert "KNOWLEDGE_SAFETY_METADATA_UNAPPROVED" in result.safety_reason_codes
    assert recorder.completed is not None
    assert "TRANSFERRED" in recorder.completed.state_path


@pytest.mark.parametrize(
    ("statement_type", "customer_scope", "answer", "expected_terminal", "draft_visible"),
    [
        (
            KnowledgeStatementType.CUSTOMER_INSTANCE_FACT,
            KnowledgeCustomerScope.SPECIFIC_CUSTOMER,
            "退款协议词典服务于开发；收单冲销后，付款主体的账户购买力已经恢复正常。",
            WorkflowTerminalState.TRANSFERRED,
            False,
        ),
        (
            KnowledgeStatementType.TECHNICAL_ARTIFACT,
            KnowledgeCustomerScope.NONE,
            "退费 Protobuf 描述符保存在模式中心。",
            WorkflowTerminalState.HUMAN_REVIEW,
            True,
        ),
        (
            KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
            KnowledgeCustomerScope.GENERIC,
            "“退款款项已经到账”这一主张仍需证据裁定。",
            WorkflowTerminalState.HUMAN_REVIEW,
            True,
        ),
    ],
)
@pytest.mark.asyncio
async def test_structured_knowledge_type_controls_complete_workflow_visibility(
    statement_type: KnowledgeStatementType,
    customer_scope: KnowledgeCustomerScope,
    answer: str,
    expected_terminal: WorkflowTerminalState,
    draft_visible: bool,
) -> None:
    """完整工作流必须使用审批类型，而不是重新猜测自然语言语义。"""
    rag_result = retrieval(0.92)
    hit = rag_result.hits[0]
    hit.content = f"问题：测试知识\n答案：{answer}"
    hit.safety_metadata = KnowledgeSafetyMetadata(
        statement_type=statement_type,
        customer_scope=customer_scope,
        publication_approval=KnowledgePublicationApproval.APPROVED_FOR_INTERNAL_REVIEW,
        approved_by=TEST_APPROVER_ID,
        approved_at=datetime.now(UTC),
        store_id=TEST_STORE_ID,
        document_version=1,
        approved_document_version=1,
    )
    workflow, _, _, _ = service(
        message_intent=IntentModelOutput(
            intent=IntentName.RETURN_POLICY,
            confidence=0.94,
            classification_state=ClassificationState.CLASSIFIED,
        ),
        rag_result=rag_result,
        outcomes=[
            FaqAnswerModelOutput(
                answer=answer,
                citation_chunk_ids=[hit.chunk_id],
                grounding_confidence=0.90,
                answer_language="zh-CN",
                needs_human=False,
                business_claims=empty_claim_inventory(),
            ),
            GroundingReviewOutput(
                is_safe=True,
                is_grounded=True,
                business_claims_consistent=True,
                confidence=0.88,
                reason_codes=[],
            ),
        ],
    )

    result = await workflow.run(cast_session(), command())

    assert result.terminal_state == expected_terminal
    assert result.send_performed is False
    assert (result.draft_reply == answer) is draft_visible
    if statement_type == KnowledgeStatementType.CUSTOMER_INSTANCE_FACT:
        assert "KNOWLEDGE_CUSTOMER_FACT_REQUIRES_TOOL" in result.safety_reason_codes


@pytest.mark.parametrize(
    "answer",
    [
        "退款FAQ术语表刚完成校对。",
        "系统未确认任何退款已经到账。",
        "历史案例中曾出现退款到账，但本订单尚无结论。",
        "“款项已退回”只是示例字段，不代表当前订单状态。",
        "The phrase funds returned is sample copy, not a status confirmation.",
        "We cannot determine whether your reimbursement was approved.",
        "返款知识条目已完成归档。",
        "截图不足以证明赔付款已经入账。",
        "关于补偿到账的说法仍未经核实。",
        "The refund help-center entry went live today.",
        "This record cannot establish that the compensation payment reached your account.",
        "If a reimbursement were approved, the status page would display a notice.",
    ],
)
@pytest.mark.asyncio
async def test_exact_faq_legitimate_refund_context_remains_reviewable(answer: str) -> None:
    """逐字 FAQ 的合法非业务结论应保留给人工复核，不能被词法命中清空。"""
    rag_result = retrieval(0.99)
    hit = rag_result.hits[0].model_copy(
        update={
            "content": f"问题：相关政策\n答案：{answer}",
            "safety_metadata": approved_knowledge_metadata(
                KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
                KnowledgeCustomerScope.GENERIC,
            ),
        }
    )
    rag_result = replace(rag_result, hits=[hit], top_score=0.99)
    workflow, _, _, _ = service(
        message_intent=IntentModelOutput(
            intent=IntentName.RETURN_POLICY,
            confidence=0.99,
            classification_state=ClassificationState.CLASSIFIED,
        ),
        rag_result=rag_result,
        outcomes=[
            FaqAnswerModelOutput(
                answer=answer,
                citation_chunk_ids=[hit.chunk_id],
                grounding_confidence=0.99,
                answer_language="en" if answer.isascii() else "zh-CN",
                needs_human=False,
                business_claims=empty_claim_inventory(),
            ),
            GroundingReviewOutput(
                is_safe=True,
                is_grounded=True,
                business_claims_consistent=True,
                confidence=0.99,
                reason_codes=[],
            ),
        ],
    )

    result = await workflow.run(
        cast_session(), command("Please explain your policy." if answer.isascii() else "请说明相关政策。")
    )

    assert result.terminal_state == WorkflowTerminalState.HUMAN_REVIEW
    assert result.action == AgentAction.HUMAN_REVIEW
    assert result.send_performed is False
    assert result.draft_reply == answer


@pytest.mark.parametrize(
    "answer",
    [
        "系统没有确认这笔退款是否到账况且商家已把款项退回您的账户。",
        "过往工单曾经退款到账此外卖家已经把钱打回买家。",
        "退款帮助文档已经发布况且平台已把钱退回您的账户。",
        "A previous ticket had no outcome moreover the merchant credited the buyer.",
        "The refund guide has been revised moreover the seller credited the buyer.",
        "The compensation label is placeholder copy even so the merchant paid the buyer.",
    ],
)
@pytest.mark.asyncio
async def test_exact_faq_current_refund_fact_is_failed_closed(answer: str) -> None:
    """FAQ 安全前句不能遮蔽后续当前资金事实，工作流必须隐藏危险草稿。"""
    rag_result = retrieval(0.99)
    hit = rag_result.hits[0].model_copy(
        update={
            "content": f"问题：相关政策\n答案：{answer}",
            "safety_metadata": approved_knowledge_metadata(
                KnowledgeStatementType.CUSTOMER_INSTANCE_FACT,
                KnowledgeCustomerScope.SPECIFIC_CUSTOMER,
            ),
        }
    )
    rag_result = replace(rag_result, hits=[hit], top_score=0.99)
    workflow, _, _, _ = service(
        message_intent=IntentModelOutput(
            intent=IntentName.RETURN_POLICY,
            confidence=0.99,
            classification_state=ClassificationState.CLASSIFIED,
        ),
        rag_result=rag_result,
        outcomes=[
            FaqAnswerModelOutput(
                answer=answer,
                citation_chunk_ids=[hit.chunk_id],
                grounding_confidence=0.99,
                answer_language="en" if answer.isascii() else "zh-CN",
                needs_human=False,
                business_claims=empty_claim_inventory(),
            ),
            GroundingReviewOutput(
                is_safe=True,
                is_grounded=True,
                business_claims_consistent=True,
                confidence=0.99,
                reason_codes=[],
            ),
        ],
    )

    result = await workflow.run(
        cast_session(), command("Please explain your policy." if answer.isascii() else "请说明相关政策。")
    )

    assert result.terminal_state == WorkflowTerminalState.TRANSFERRED
    assert result.action == AgentAction.TRANSFER_HUMAN
    assert result.send_performed is False
    assert result.draft_reply is None
    assert "KNOWLEDGE_CUSTOMER_FACT_REQUIRES_TOOL" in result.safety_reason_codes


@pytest.mark.parametrize(
    ("answer", "expected_state", "expected_action", "keeps_draft"),
    [
        (
            "退款术语页已归档，而商户给买家补了一笔钱。",
            WorkflowTerminalState.TRANSFERRED,
            AgentAction.TRANSFER_HUMAN,
            False,
        ),
        (
            "The refund glossary was archived. The vendor settled the buyer in full.",
            WorkflowTerminalState.TRANSFERRED,
            AgentAction.TRANSFER_HUMAN,
            False,
        ),
        (
            "返款百科条目已经上线供坐席查阅。",
            WorkflowTerminalState.HUMAN_REVIEW,
            AgentAction.HUMAN_REVIEW,
            True,
        ),
        (
            "The evidence falls short of establishing that the reimbursement was approved.",
            WorkflowTerminalState.HUMAN_REVIEW,
            AgentAction.HUMAN_REVIEW,
            True,
        ),
    ],
)
@pytest.mark.asyncio
async def test_open_v3_refund_scope_reaches_expected_workflow_state(
    answer: str,
    expected_state: WorkflowTerminalState,
    expected_action: AgentAction,
    keeps_draft: bool,
) -> None:
    """第三批开放语义在完整工作流中必须保持失败关闭和人工草稿边界。"""
    rag_result = retrieval(0.99)
    hit = rag_result.hits[0].model_copy(
        update={
            "content": f"问题：相关政策\n答案：{answer}",
            "safety_metadata": approved_knowledge_metadata(
                KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION
                if keeps_draft
                else KnowledgeStatementType.CUSTOMER_INSTANCE_FACT,
                KnowledgeCustomerScope.GENERIC if keeps_draft else KnowledgeCustomerScope.SPECIFIC_CUSTOMER,
            ),
        }
    )
    rag_result = replace(rag_result, hits=[hit], top_score=0.99)
    workflow, _, _, _ = service(
        message_intent=IntentModelOutput(
            intent=IntentName.RETURN_POLICY,
            confidence=0.99,
            classification_state=ClassificationState.CLASSIFIED,
        ),
        rag_result=rag_result,
        outcomes=[
            FaqAnswerModelOutput(
                answer=answer,
                citation_chunk_ids=[hit.chunk_id],
                grounding_confidence=0.99,
                answer_language="en" if answer.isascii() else "zh-CN",
                needs_human=False,
                business_claims=empty_claim_inventory(),
            ),
            GroundingReviewOutput(
                is_safe=True,
                is_grounded=True,
                business_claims_consistent=True,
                confidence=0.99,
                reason_codes=[],
            ),
        ],
    )

    result = await workflow.run(
        cast_session(), command("Please explain your policy." if answer.isascii() else "请说明相关政策。")
    )

    assert result.terminal_state == expected_state
    assert result.action == expected_action
    assert result.send_performed is False
    if keeps_draft:
        assert result.draft_reply == answer
    else:
        assert result.draft_reply is None


@pytest.mark.parametrize(
    ("answer", "expected_state", "expected_action", "keeps_draft"),
    [
        (
            "退费说明仍在校订，消费者原卡上出现了品牌方退回的货款。",
            WorkflowTerminalState.TRANSFERRED,
            AgentAction.TRANSFER_HUMAN,
            False,
        ),
        (
            "The reimbursement manual is online. Money from the processor is now sitting in the customer's wallet.",
            WorkflowTerminalState.TRANSFERRED,
            AgentAction.TRANSFER_HUMAN,
            False,
        ),
        (
            "返款 OpenAPI 模式定义归属于接口仓库。",
            WorkflowTerminalState.HUMAN_REVIEW,
            AgentAction.HUMAN_REVIEW,
            True,
        ),
        (
            "The reimbursement event schema is read-only metadata for integration tests.",
            WorkflowTerminalState.HUMAN_REVIEW,
            AgentAction.HUMAN_REVIEW,
            True,
        ),
    ],
)
@pytest.mark.asyncio
async def test_open_v5_refund_semantic_roles_reach_expected_workflow_state(
    answer: str,
    expected_state: WorkflowTerminalState,
    expected_action: AgentAction,
    keeps_draft: bool,
) -> None:
    """第四批语义角色修复必须贯穿完整工作流，并继续禁止任何自动发送。"""
    rag_result = retrieval(0.99)
    hit = rag_result.hits[0].model_copy(
        update={
            "content": f"问题：相关政策\n答案：{answer}",
            "safety_metadata": approved_knowledge_metadata(
                KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION
                if keeps_draft
                else KnowledgeStatementType.CUSTOMER_INSTANCE_FACT,
                KnowledgeCustomerScope.GENERIC if keeps_draft else KnowledgeCustomerScope.SPECIFIC_CUSTOMER,
            ),
        }
    )
    rag_result = replace(rag_result, hits=[hit], top_score=0.99)
    workflow, _, _, _ = service(
        message_intent=IntentModelOutput(
            intent=IntentName.RETURN_POLICY,
            confidence=0.99,
            classification_state=ClassificationState.CLASSIFIED,
        ),
        rag_result=rag_result,
        outcomes=[
            FaqAnswerModelOutput(
                answer=answer,
                citation_chunk_ids=[hit.chunk_id],
                grounding_confidence=0.99,
                answer_language="en" if answer.isascii() else "zh-CN",
                needs_human=False,
                business_claims=empty_claim_inventory(),
            ),
            GroundingReviewOutput(
                is_safe=True,
                is_grounded=True,
                business_claims_consistent=True,
                confidence=0.99,
                reason_codes=[],
            ),
        ],
    )

    result = await workflow.run(
        cast_session(), command("Please explain your policy." if answer.isascii() else "请说明相关政策。")
    )

    assert result.terminal_state == expected_state
    assert result.action == expected_action
    assert result.send_performed is False
    if keeps_draft:
        assert result.draft_reply == answer
    else:
        assert result.draft_reply is None
        assert "BUSINESS_CLAIM_INVENTORY_MISMATCH" in result.safety_reason_codes


@pytest.mark.parametrize(
    ("answer", "expected_state", "expected_action", "keeps_draft"),
    [
        (
            "退费页面正在更新；买家的电子账户可用额因网关回补而上升。",
            WorkflowTerminalState.TRANSFERRED,
            AgentAction.TRANSFER_HUMAN,
            False,
        ),
        (
            "The refund help document was reviewed. The customer's bank statement now lists "
            "a merchant-originated repayment.",
            WorkflowTerminalState.TRANSFERRED,
            AgentAction.TRANSFER_HUMAN,
            False,
        ),
        (
            "补偿 JSON 样例仅供联调。",
            WorkflowTerminalState.HUMAN_REVIEW,
            AgentAction.HUMAN_REVIEW,
            True,
        ),
        (
            "Before an independent audit finishes, reimbursement cannot be treated as settled.",
            WorkflowTerminalState.HUMAN_REVIEW,
            AgentAction.HUMAN_REVIEW,
            True,
        ),
        (
            "The refund event descriptor is versioned; the member's payment reserve rebounded "
            "when the gateway canceled the debit.",
            WorkflowTerminalState.TRANSFERRED,
            AgentAction.TRANSFER_HUMAN,
            False,
        ),
        (
            "退费 GraphQL 类型只供客户端生成代码。",
            WorkflowTerminalState.HUMAN_REVIEW,
            AgentAction.HUMAN_REVIEW,
            True,
        ),
        (
            "所谓退款已经补足余额，只是尚未验证的假说。",
            WorkflowTerminalState.HUMAN_REVIEW,
            AgentAction.HUMAN_REVIEW,
            True,
        ),
        (
            "The available evidence is silent on whether reimbursement completed.",
            WorkflowTerminalState.HUMAN_REVIEW,
            AgentAction.HUMAN_REVIEW,
            True,
        ),
        (
            "The reimbursement event ontology is versioned metadata; the purchaser's stored cash position revived "
            "after an acquirer write-back.",
            WorkflowTerminalState.TRANSFERRED,
            AgentAction.TRANSFER_HUMAN,
            False,
        ),
        (
            "The reimbursement schema catalog is a developer artifact; the user's account purchasing capacity "
            "became usable again after a clearing credit.",
            WorkflowTerminalState.TRANSFERRED,
            AgentAction.TRANSFER_HUMAN,
            False,
        ),
        (
            "退款事件本体记录在治理目录中。",
            WorkflowTerminalState.HUMAN_REVIEW,
            AgentAction.HUMAN_REVIEW,
            True,
        ),
        (
            "The audit opinion takes no position on whether reimbursement completed.",
            WorkflowTerminalState.HUMAN_REVIEW,
            AgentAction.HUMAN_REVIEW,
            True,
        ),
    ],
)
@pytest.mark.asyncio
async def test_open_v5_v6_v7_refund_roles_reach_expected_workflow_state(
    answer: str,
    expected_state: WorkflowTerminalState,
    expected_action: AgentAction,
    keeps_draft: bool,
) -> None:
    """第五至七批资金结果和合法语境必须贯穿工作流，并始终禁止自动发送。"""
    rag_result = retrieval(0.99)
    hit = rag_result.hits[0].model_copy(
        update={
            "content": f"问题：相关政策\n答案：{answer}",
            "safety_metadata": approved_knowledge_metadata(
                KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION
                if keeps_draft
                else KnowledgeStatementType.CUSTOMER_INSTANCE_FACT,
                KnowledgeCustomerScope.GENERIC if keeps_draft else KnowledgeCustomerScope.SPECIFIC_CUSTOMER,
            ),
        }
    )
    rag_result = replace(rag_result, hits=[hit], top_score=0.99)
    workflow, _, _, _ = service(
        message_intent=IntentModelOutput(
            intent=IntentName.RETURN_POLICY,
            confidence=0.99,
            classification_state=ClassificationState.CLASSIFIED,
        ),
        rag_result=rag_result,
        outcomes=[
            FaqAnswerModelOutput(
                answer=answer,
                citation_chunk_ids=[hit.chunk_id],
                grounding_confidence=0.99,
                answer_language="en" if answer.isascii() else "zh-CN",
                needs_human=False,
                business_claims=empty_claim_inventory(),
            ),
            GroundingReviewOutput(
                is_safe=True,
                is_grounded=True,
                business_claims_consistent=True,
                confidence=0.99,
                reason_codes=[],
            ),
        ],
    )

    result = await workflow.run(
        cast_session(), command("Please explain your policy." if answer.isascii() else "请说明相关政策。")
    )

    assert result.terminal_state == expected_state
    assert result.action == expected_action
    assert result.send_performed is False
    if keeps_draft:
        assert result.draft_reply == answer
    else:
        assert result.draft_reply is None
        assert "KNOWLEDGE_CUSTOMER_FACT_REQUIRES_TOOL" in result.safety_reason_codes


@pytest.mark.parametrize(
    "answer",
    [
        "补偿仍需审核，财务方完成了向买家的价值返置。",
        "订单当前已经由结算侧撤销并恢复了购买者权益。",
    ],
)
@pytest.mark.asyncio
async def test_published_high_risk_faq_never_becomes_auto_reply(answer: str) -> None:
    """逐字复制受污染 FAQ 也不能绕过未建立的知识审批边界。"""
    rag_result = retrieval(0.99)
    hit = rag_result.hits[0].model_copy(
        update={
            "content": f"问题：当前结果\n答案：{answer}",
            "safety_metadata": approved_knowledge_metadata(
                KnowledgeStatementType.CUSTOMER_INSTANCE_FACT,
                KnowledgeCustomerScope.SPECIFIC_CUSTOMER,
            ),
        }
    )
    rag_result = replace(rag_result, hits=[hit], top_score=0.99)
    workflow, _, _, _ = service(
        message_intent=IntentModelOutput(
            intent=IntentName.RETURN_POLICY,
            confidence=0.99,
            classification_state=ClassificationState.CLASSIFIED,
        ),
        rag_result=rag_result,
        outcomes=[
            FaqAnswerModelOutput(
                answer=answer,
                citation_chunk_ids=[hit.chunk_id],
                grounding_confidence=0.99,
                answer_language="zh-CN",
                needs_human=False,
                business_claims=empty_claim_inventory(),
            ),
            GroundingReviewOutput(
                is_safe=True,
                is_grounded=True,
                business_claims_consistent=True,
                confidence=0.99,
                reason_codes=[],
            ),
        ],
    )

    result = await workflow.run(cast_session(), command("我的退款结果怎么样？"))

    assert result.terminal_state == WorkflowTerminalState.TRANSFERRED
    assert result.action == AgentAction.TRANSFER_HUMAN
    assert result.requires_human is True
    assert result.send_performed is False
    assert result.draft_reply is None
    assert "KNOWLEDGE_CUSTOMER_FACT_REQUIRES_TOOL" in result.safety_reason_codes


@pytest.mark.asyncio
async def test_model_draft_that_differs_from_cited_faq_cannot_become_auto_reply() -> None:
    """即使模型自报空声明且复核误判，FAQ 之外的危险正文也不能自动就绪。"""
    rag_result = retrieval(0.92)
    workflow, _, _, _ = service(
        message_intent=IntentModelOutput(
            intent=IntentName.RETURN_POLICY,
            confidence=0.94,
            classification_state=ClassificationState.CLASSIFIED,
        ),
        rag_result=rag_result,
        outcomes=[
            FaqAnswerModelOutput(
                answer="补偿需审核，财务方完成了向买家的价值返置。",
                citation_chunk_ids=[rag_result.hits[0].chunk_id],
                grounding_confidence=0.99,
                answer_language="zh-CN",
                needs_human=False,
                business_claims=empty_claim_inventory(),
            ),
            GroundingReviewOutput(
                is_safe=True,
                is_grounded=True,
                business_claims_consistent=True,
                confidence=0.99,
                reason_codes=[],
            ),
        ],
    )

    result = await workflow.run(cast_session(), command())

    assert result.action == AgentAction.HUMAN_REVIEW
    assert result.terminal_state == WorkflowTerminalState.HUMAN_REVIEW
    assert result.draft_reply == "补偿需审核，财务方完成了向买家的价值返置。"


@pytest.mark.asyncio
async def test_legacy_refund_text_signal_does_not_hide_reviewable_model_draft() -> None:
    """旧词表命中的合法技术对象应降级人工复核，而不是清空草稿。"""
    rag_result = retrieval(0.92)
    answer = "退款审批工作流已部署。"
    workflow, _, _, _ = service(
        message_intent=IntentModelOutput(
            intent=IntentName.RETURN_POLICY,
            confidence=0.94,
            classification_state=ClassificationState.CLASSIFIED,
        ),
        rag_result=rag_result,
        outcomes=[
            FaqAnswerModelOutput(
                answer=answer,
                citation_chunk_ids=[rag_result.hits[0].chunk_id],
                grounding_confidence=0.99,
                answer_language="zh-CN",
                needs_human=False,
                business_claims=empty_claim_inventory(),
            ),
            GroundingReviewOutput(
                is_safe=True,
                is_grounded=True,
                business_claims_consistent=True,
                confidence=0.99,
                reason_codes=[],
            ),
        ],
    )

    result = await workflow.run(cast_session(), command())

    assert result.action == AgentAction.HUMAN_REVIEW
    assert result.terminal_state == WorkflowTerminalState.HUMAN_REVIEW
    assert result.draft_reply == answer


@pytest.mark.asyncio
async def test_reply_prompt_applies_store_tone_and_explicit_language() -> None:
    """店铺级语气和语言应进入系统 Prompt，并校验模型实际输出语言。"""
    rag_result = retrieval(0.92)
    chunk_id = rag_result.hits[0].chunk_id
    workflow, _, generator, _ = service(
        message_intent=IntentModelOutput(
            intent=IntentName.RETURN_POLICY,
            confidence=0.94,
            classification_state=ClassificationState.CLASSIFIED,
        ),
        rag_result=rag_result,
        outcomes=[
            FaqAnswerModelOutput(
                answer="Returns are available within seven days after delivery.",
                citation_chunk_ids=[chunk_id],
                grounding_confidence=0.90,
                answer_language="en",
                needs_human=False,
                business_claims=empty_claim_inventory(),
            ),
            GroundingReviewOutput(
                is_safe=True,
                is_grounded=True,
                business_claims_consistent=True,
                confidence=0.88,
                reason_codes=[],
            ),
        ],
    )
    workflow_command = command("How long is the return window?").model_copy(
        update={
            "language": "en",
            "reply_profile": AgentReplyProfile(
                tone=ReplyTone.PROFESSIONAL,
                reply_language="en",
                operator_language="en",
                brand_name="Northwind",
            ),
        }
    )

    result = await workflow.run(cast_session(), workflow_command)

    assert result.reply_language == "en"
    assert result.detected_language == CustomerLanguage.EN
    assert generator.requests[0].system_prompt == FAQ_ANSWER_SYSTEM_PROMPT
    assert generator.requests[0].business_prompt_id == BusinessPromptId.FAQ_ANSWER
    assert generator.requests[0].prompt_safety_state.value == "allowed"
    assert generator.requests[1].business_prompt_id == BusinessPromptId.FAQ_GROUNDING_REVIEW
    assert generator.requests[1].prompt_safety_state.value == "allowed"
    assert '"tone": "professional"' in generator.requests[0].user_prompt
    assert '"reply_language": "en"' in generator.requests[0].user_prompt
    assert '"brand_name": "Northwind"' in generator.requests[0].user_prompt


@pytest.mark.asyncio
async def test_deterministic_safety_blocks_unsupported_refund_before_model_review() -> None:
    """无依据退款承诺必须在独立模型复核之前由代码阻断。"""
    rag_result = retrieval(0.92)
    workflow, _, generator, recorder = service(
        message_intent=IntentModelOutput(
            intent=IntentName.RETURN_POLICY,
            confidence=0.94,
            classification_state=ClassificationState.CLASSIFIED,
        ),
        rag_result=rag_result,
        outcomes=[
            FaqAnswerModelOutput(
                answer="我们保证退款并赔偿 100 元。",
                citation_chunk_ids=[rag_result.hits[0].chunk_id],
                grounding_confidence=0.99,
                answer_language="zh-CN",
                needs_human=False,
                business_claims=BusinessClaimInventory(
                    complete=True,
                    claims=[
                        BusinessClaim(
                            subject_type=BusinessClaimSubjectType.REFUND_FUNDS,
                            subject_id="current-refund",
                            action=BusinessClaimAction.EXECUTE,
                            tense=BusinessClaimTense.FUTURE,
                            polarity=BusinessClaimPolarity.AFFIRMED,
                            condition=BusinessClaimCondition.ACTUAL,
                            evidence_type=BusinessClaimEvidenceType.NONE,
                            evidence_id=None,
                            confidence=0.99,
                        )
                    ],
                ),
            )
        ],
    )

    result = await workflow.run(cast_session(), command())

    assert result.action == AgentAction.TRANSFER_HUMAN
    assert result.draft_reply is None
    assert "UNAUTHORIZED_COMMITMENT" in result.safety_reason_codes
    assert len(generator.requests) == 1
    assert recorder.completed is not None
    assert recorder.completed.safety_reason_codes == ["UNAUTHORIZED_COMMITMENT"]


@pytest.mark.asyncio
async def test_workflow_returns_translation_linked_to_trigger_message() -> None:
    """跨语言客服辅助翻译应与触发消息关联，但不改变客户回复语言。"""
    rag_result = retrieval(0.92)
    chunk_id = rag_result.hits[0].chunk_id
    workflow, _, _, recorder = service(
        message_intent=IntentModelOutput(
            intent=IntentName.RETURN_POLICY,
            confidence=0.94,
            classification_state=ClassificationState.CLASSIFIED,
        ),
        rag_result=rag_result,
        outcomes=[
            FaqAnswerModelOutput(
                answer="Returns are available within seven days after delivery.",
                citation_chunk_ids=[chunk_id],
                grounding_confidence=0.90,
                answer_language="en",
                needs_human=False,
                business_claims=empty_claim_inventory(),
            ),
            GroundingReviewOutput(
                is_safe=True,
                is_grounded=True,
                business_claims_consistent=True,
                confidence=0.88,
                reason_codes=[],
            ),
            TranslationBundleModelOutput(
                source_language="en",
                target_language="zh-CN",
                message_translation="退货期限是多久？",
                draft_translation="签收后七天内可以申请退货。",
            ),
        ],
        enable_translation=True,
    )
    workflow_command = command("How long is the return window?").model_copy(
        update={
            "language": "en",
            "reply_profile": AgentReplyProfile(operator_language="zh-CN"),
        }
    )

    result = await workflow.run(cast_session(), workflow_command)

    assert result.customer_translation is not None
    assert result.customer_translation.trigger_message_id == workflow_command.trigger_message_id
    assert result.customer_translation.draft_translation == "签收后七天内可以申请退货。"
    assert result.reply_language == "en"
    assert recorder.completed is not None
    assert "REPLY_TRANSLATED" in recorder.completed.state_path


@pytest.mark.asyncio
async def test_translation_model_failure_fails_workflow_without_success_record() -> None:
    """翻译属于本次模型工作流；模型失败时不能伪装成成功运行。"""
    rag_result = retrieval(0.92)
    chunk_id = rag_result.hits[0].chunk_id
    workflow, _, _, recorder = service(
        message_intent=IntentModelOutput(
            intent=IntentName.RETURN_POLICY,
            confidence=0.94,
            classification_state=ClassificationState.CLASSIFIED,
        ),
        rag_result=rag_result,
        outcomes=[
            FaqAnswerModelOutput(
                answer="Returns are available within seven days after delivery.",
                citation_chunk_ids=[chunk_id],
                grounding_confidence=0.90,
                answer_language="en",
                needs_human=False,
                business_claims=empty_claim_inventory(),
            ),
            GroundingReviewOutput(
                is_safe=True,
                is_grounded=True,
                business_claims_consistent=True,
                confidence=0.88,
                reason_codes=[],
            ),
        ],
        enable_translation=True,
    )

    class FailingTranslationService:
        """只模拟翻译 Provider 超时，验证工作流终态记录。"""

        async def translate_bundle(self, **_: object) -> None:
            raise LLMProviderError(LLMErrorCode.LLM_TIMEOUT, "timeout", retriable=True)

    workflow.translation_service = FailingTranslationService()  # type: ignore[assignment]
    workflow_command = command("How long is the return window?").model_copy(update={"language": "en"})

    with pytest.raises(AgentWorkflowExecutionError) as error_info:
        await workflow.run(cast_session(), workflow_command)

    assert error_info.value.error_code == "LLM_TIMEOUT"
    assert recorder.completed is None
    assert recorder.failed == (AgentRunStatus.TIMEOUT, AgentAction.FAILED, "LLM_TIMEOUT")
    assert recorder.failure_stage == LLMFailureStage.TRANSLATION
    assert recorder.output_failure_kind is None


@pytest.mark.parametrize(
    ("stage", "fail_at_review"),
    [(LLMFailureStage.FAQ_DRAFT, False), (LLMFailureStage.SAFETY_REVIEW, True)],
)
@pytest.mark.asyncio
async def test_invalid_llm_output_records_stage_and_fixed_kind(
    stage: LLMFailureStage,
    fail_at_review: bool,
) -> None:
    """草稿和复核失败时保留固定诊断，且不生成成功终态。"""
    rag_result = retrieval(0.92)
    failure = LLMProviderError(
        LLMErrorCode.LLM_OUTPUT_INVALID,
        "sensitive model output must not be saved",
        retriable=False,
        output_failure_kind="invalid_schema",
    )
    draft = FaqAnswerModelOutput(
        answer="签收后七天内可申请退货。",
        citation_chunk_ids=[rag_result.hits[0].chunk_id],
        grounding_confidence=0.90,
        answer_language="zh-CN",
        needs_human=False,
        business_claims=empty_claim_inventory(),
    )
    workflow, _, _, recorder = service(
        message_intent=IntentModelOutput(
            intent=IntentName.RETURN_POLICY,
            confidence=0.94,
            classification_state=ClassificationState.CLASSIFIED,
        ),
        rag_result=rag_result,
        outcomes=[draft, failure] if fail_at_review else [failure],
    )

    with pytest.raises(AgentWorkflowExecutionError) as error_info:
        await workflow.run(cast_session(), command())

    assert error_info.value.error_code == "LLM_OUTPUT_INVALID"
    assert recorder.failed == (AgentRunStatus.FAILED, AgentAction.FAILED, "LLM_OUTPUT_INVALID")
    assert recorder.failure_stage == stage
    assert recorder.output_failure_kind == "invalid_schema"
    assert recorder.completed is None


@pytest.mark.asyncio
async def test_invalid_classification_output_records_classification_stage() -> None:
    """分类节点失败可与 FAQ 草稿失败区分。"""
    workflow, _, _, recorder = service(
        message_intent=IntentModelOutput(
            intent=IntentName.RETURN_POLICY,
            confidence=0.94,
            classification_state=ClassificationState.CLASSIFIED,
        ),
        rag_result=retrieval(),
        outcomes=[],
    )

    class FailingClassifier:
        provider_name = "fake-llm"
        model_name = "fake-intent"

        async def infer(self, command: AgentWorkflowCommand, *, agent_run_id: uuid.UUID | None) -> None:
            raise LLMProviderError(
                LLMErrorCode.LLM_OUTPUT_INVALID,
                "sensitive output",
                retriable=False,
                output_failure_kind="empty",
            )

    workflow.classifier = FailingClassifier()  # type: ignore[assignment]
    with pytest.raises(AgentWorkflowExecutionError):
        await workflow.run(cast_session(), command())

    assert recorder.failure_stage == LLMFailureStage.CLASSIFICATION
    assert recorder.output_failure_kind == "empty"


@pytest.mark.asyncio
async def test_realtime_logistics_routes_to_tool_required_and_transfer() -> None:
    """实时物流问题不应拿通用 FAQ 猜订单轨迹，也不能在本阶段执行工具。"""
    workflow, rag, generator, _ = service(
        message_intent=IntentModelOutput(
            intent=IntentName.LOGISTICS_QUERY,
            confidence=0.95,
            classification_state=ClassificationState.CLASSIFIED,
        ),
        rag_result=retrieval(),
        outcomes=[],
    )

    result = await workflow.run(cast_session(), command("我的订单 AB123456789 现在到哪里了？"))

    assert result.terminal_state == WorkflowTerminalState.TRANSFERRED
    assert result.required_tools == ["query_logistics"]
    assert result.action == AgentAction.TRANSFER_HUMAN
    assert result.draft_reply is None
    assert rag.calls == 0
    assert generator.requests == []


@pytest.mark.asyncio
async def test_no_knowledge_transfers_without_generating_answer() -> None:
    """无有效 FAQ 时不得调用答案模型制造无依据回复。"""
    empty = RagRetrievalResult(
        hits=[],
        top_score=0,
        context_tokens=0,
        embedding_provider="fake",
        embedding_model="fake-1536",
        embedding_input_tokens=5,
        embedding_latency_ms=2,
    )
    workflow, rag, generator, _ = service(
        message_intent=IntentModelOutput(
            intent=IntentName.SIZE_GUIDE,
            confidence=0.90,
            classification_state=ClassificationState.CLASSIFIED,
        ),
        rag_result=empty,
        outcomes=[],
    )

    result = await workflow.run(cast_session(), command("这个商品怎么选尺码？"))

    assert result.action == AgentAction.TRANSFER_HUMAN
    assert result.final_confidence == 0
    assert rag.calls == 1
    assert generator.requests == []


@pytest.mark.asyncio
async def test_answer_with_unknown_citation_is_rejected_before_review() -> None:
    """模型引用不在 Top 5 中时必须失败关闭，不能让复核模型替它补救。"""
    workflow, _, generator, _ = service(
        message_intent=IntentModelOutput(
            intent=IntentName.RETURN_POLICY,
            confidence=0.90,
            classification_state=ClassificationState.CLASSIFIED,
        ),
        rag_result=retrieval(0.90),
        outcomes=[
            FaqAnswerModelOutput(
                answer="不可信答案",
                citation_chunk_ids=[uuid.uuid4()],
                grounding_confidence=0.95,
                answer_language="zh-CN",
                needs_human=False,
                business_claims=empty_claim_inventory(),
            )
        ],
    )

    result = await workflow.run(cast_session(), command())

    assert result.action == AgentAction.TRANSFER_HUMAN
    assert result.draft_reply is None
    assert len(generator.requests) == 1


@pytest.mark.asyncio
async def test_medium_final_confidence_returns_reviewable_draft() -> None:
    """0.60 到 0.80 的安全答案应保留草稿，但必须由人工复核。"""
    rag_result = retrieval(0.75)
    workflow, _, _, _ = service(
        message_intent=IntentModelOutput(
            intent=IntentName.RETURN_POLICY,
            confidence=0.90,
            classification_state=ClassificationState.CLASSIFIED,
        ),
        rag_result=rag_result,
        outcomes=[
            FaqAnswerModelOutput(
                answer="签收后七天内可以申请退货。",
                citation_chunk_ids=[rag_result.hits[0].chunk_id],
                grounding_confidence=0.78,
                answer_language="zh-CN",
                needs_human=False,
                business_claims=empty_claim_inventory(),
            ),
            GroundingReviewOutput(
                is_safe=True,
                is_grounded=True,
                business_claims_consistent=True,
                confidence=0.74,
                reason_codes=[],
            ),
        ],
    )

    result = await workflow.run(cast_session(), command())

    assert result.terminal_state == WorkflowTerminalState.HUMAN_REVIEW
    assert result.action == AgentAction.HUMAN_REVIEW
    assert result.final_confidence == 0.74
    assert result.requires_human is True
    assert result.draft_reply is not None


@pytest.mark.asyncio
async def test_successful_logistics_tool_generates_grounded_reply_without_platform_send() -> None:
    """实时物流查询成功后可解释结果，但仍不能隐式调用平台发送工具。"""
    query_call_id = uuid.uuid4()
    tool_batch = AgentToolBatchResult(
        results=[
            ExecutedAgentTool(
                tool_name="query_logistics",
                result=ToolResult(
                    tool_call_id=query_call_id,
                    status="succeeded",
                    data=logistics_tool_data(),
                ),
            )
        ]
    )
    workflow, rag, _, recorder = service(
        message_intent=IntentModelOutput(
            intent=IntentName.LOGISTICS_QUERY,
            confidence=0.95,
            classification_state=ClassificationState.CLASSIFIED,
        ),
        rag_result=retrieval(),
        tool_batches=[tool_batch],
        outcomes=[
            ToolAnswerModelOutput(
                answer="订单正在运输中，请继续留意物流更新。",
                tool_call_ids=[query_call_id],
                grounding_confidence=0.91,
                answer_language="zh-CN",
                needs_human=False,
                business_claims=empty_claim_inventory(),
            ),
            ToolGroundingReviewOutput(
                is_safe=True,
                is_grounded=True,
                completion_claim_valid=True,
                business_claims_consistent=True,
                confidence=0.90,
                reason_codes=[],
            ),
        ],
    )
    workflow_command = command("我的订单现在到哪里了？").model_copy(
        update={
            "tool_context": AgentToolRuntimeContext(
                order_id="ORDER-2026-001",
                available_tools={"query_logistics"},
                permissions={"orders.view"},
            )
        }
    )

    result = await workflow.run(cast_session(), workflow_command)

    assert result.terminal_state == WorkflowTerminalState.AUTO_REPLY_READY
    assert result.action == AgentAction.AUTO_REPLY
    assert result.draft_reply == "订单正在运输中，请继续留意物流更新。"
    assert result.citations == []
    assert result.tool_calls[0].tool_call_id == query_call_id
    assert result.required_tools == ["query_logistics"]
    assert result.send_performed is False
    assert rag.calls == 0
    assert recorder.completed is not None
    assert "TOOL_EXECUTED" in recorder.completed.state_path
    assert "TOOL_SAFETY_CHECKED" in recorder.completed.state_path
    assert recorder.completed.business_claim_summaries == [f"logistics:report_status:tool_call:{query_call_id}"]


@pytest.mark.asyncio
async def test_redacted_tool_subject_is_bound_by_code_owned_claim() -> None:
    """模型只见脱敏占位符时，执行层应生成真实对象声明并保留自动模板资格。"""
    query_call_id = uuid.uuid4()
    tool_batch = AgentToolBatchResult(
        results=[
            ExecutedAgentTool(
                tool_name="query_logistics",
                result=ToolResult(
                    tool_call_id=query_call_id,
                    status="succeeded",
                    data=logistics_tool_data(),
                ),
            )
        ]
    )
    workflow, _, generator, recorder = service(
        message_intent=IntentModelOutput(
            intent=IntentName.LOGISTICS_QUERY,
            confidence=0.95,
            classification_state=ClassificationState.CLASSIFIED,
        ),
        rag_result=retrieval(),
        tool_batches=[tool_batch],
        outcomes=[
            ToolAnswerModelOutput(
                answer="订单正在运输中，请继续留意物流更新。",
                tool_call_ids=[query_call_id],
                grounding_confidence=0.91,
                answer_language="zh-CN",
                needs_human=False,
                business_claims=BusinessClaimInventory(
                    complete=True,
                    claims=[
                        BusinessClaim(
                            subject_type=BusinessClaimSubjectType.LOGISTICS,
                            subject_id="[SENSITIVE_ID]",
                            action=BusinessClaimAction.REPORT_STATUS,
                            tense=BusinessClaimTense.PRESENT,
                            polarity=BusinessClaimPolarity.AFFIRMED,
                            condition=BusinessClaimCondition.ACTUAL,
                            evidence_type=BusinessClaimEvidenceType.TOOL_CALL,
                            evidence_id=query_call_id,
                            confidence=0.91,
                        )
                    ],
                ),
            ),
            ToolGroundingReviewOutput(
                is_safe=True,
                is_grounded=True,
                completion_claim_valid=True,
                business_claims_consistent=True,
                confidence=0.90,
                reason_codes=[],
            ),
        ],
    )
    workflow_command = command("我的订单现在到哪里了？").model_copy(
        update={
            "tool_context": AgentToolRuntimeContext(
                order_id="ORDER-2026-001",
                available_tools={"query_logistics"},
                permissions={"orders.view"},
            )
        }
    )

    result = await workflow.run(cast_session(), workflow_command)

    assert result.terminal_state == WorkflowTerminalState.AUTO_REPLY_READY
    assert result.action == AgentAction.AUTO_REPLY
    assert result.draft_reply == "订单正在运输中，请继续留意物流更新。"
    assert "ORDER-2026-001" not in generator.requests[0].user_prompt
    assert "[SENSITIVE_ID]" in generator.requests[0].user_prompt
    assert "claims=[]" in TOOL_ANSWER_SYSTEM_PROMPT
    assert generator.requests[0].system_prompt == TOOL_ANSWER_SYSTEM_PROMPT
    assert generator.requests[0].business_prompt_id == BusinessPromptId.TOOL_ANSWER
    assert generator.requests[0].prompt_safety_state.value == "allowed"
    assert generator.requests[1].business_prompt_id == BusinessPromptId.TOOL_GROUNDING_REVIEW
    assert generator.requests[1].prompt_safety_state.value == "allowed"
    assert recorder.completed is not None
    assert recorder.completed.business_claim_summaries == [f"logistics:report_status:tool_call:{query_call_id}"]


@pytest.mark.asyncio
async def test_logistics_tool_result_cannot_authorize_another_order() -> None:
    """工具返回订单 A 时，模型声明订单 B 必须转人工并隐藏草稿。"""
    query_call_id = uuid.uuid4()
    tool_batch = AgentToolBatchResult(
        results=[
            ExecutedAgentTool(
                tool_name="query_logistics",
                result=ToolResult(
                    tool_call_id=query_call_id,
                    status="succeeded",
                    data=logistics_tool_data("ORDER-A"),
                ),
            )
        ]
    )
    workflow, _, _, _ = service(
        message_intent=IntentModelOutput(
            intent=IntentName.LOGISTICS_QUERY,
            confidence=0.95,
            classification_state=ClassificationState.CLASSIFIED,
        ),
        rag_result=retrieval(),
        tool_batches=[tool_batch],
        outcomes=[
            ToolAnswerModelOutput(
                answer="订单 B 正在运输中。",
                tool_call_ids=[query_call_id],
                grounding_confidence=0.95,
                answer_language="zh-CN",
                needs_human=False,
                business_claims=BusinessClaimInventory(
                    complete=True,
                    claims=[
                        BusinessClaim(
                            subject_type=BusinessClaimSubjectType.LOGISTICS,
                            subject_id="ORDER-B",
                            action=BusinessClaimAction.REPORT_STATUS,
                            tense=BusinessClaimTense.PRESENT,
                            polarity=BusinessClaimPolarity.AFFIRMED,
                            condition=BusinessClaimCondition.ACTUAL,
                            evidence_type=BusinessClaimEvidenceType.TOOL_CALL,
                            evidence_id=query_call_id,
                            confidence=0.95,
                        )
                    ],
                ),
            ),
            ToolGroundingReviewOutput(
                is_safe=True,
                is_grounded=True,
                completion_claim_valid=True,
                business_claims_consistent=True,
                confidence=0.95,
                reason_codes=[],
            ),
        ],
    )
    workflow_command = command("我的订单现在到哪里了？").model_copy(
        update={
            "tool_context": AgentToolRuntimeContext(
                order_id="ORDER-A",
                available_tools={"query_logistics"},
                permissions={"orders.view"},
            )
        }
    )

    result = await workflow.run(cast_session(), workflow_command)

    assert result.action == AgentAction.TRANSFER_HUMAN
    assert result.draft_reply is None
    assert "INVALID_BUSINESS_CLAIM_EVIDENCE" in result.safety_reason_codes


@pytest.mark.asyncio
async def test_failed_tool_never_claims_completion_and_executes_handoff_when_allowed() -> None:
    """查询失败后禁止生成成功话术，并应通过转人工工具更新接管状态。"""
    query_call_id = uuid.uuid4()
    transfer_call_id = uuid.uuid4()
    workflow, _, generator, _ = service(
        message_intent=IntentModelOutput(
            intent=IntentName.LOGISTICS_QUERY,
            confidence=0.95,
            classification_state=ClassificationState.CLASSIFIED,
        ),
        rag_result=retrieval(),
        tool_batches=[
            AgentToolBatchResult(
                results=[
                    ExecutedAgentTool(
                        tool_name="query_logistics",
                        result=ToolResult(
                            tool_call_id=query_call_id,
                            status="timeout",
                            error_code="TOOL_TIMEOUT",
                        ),
                    )
                ]
            ),
            AgentToolBatchResult(
                results=[
                    ExecutedAgentTool(
                        tool_name="transfer_to_human",
                        result=ToolResult(tool_call_id=transfer_call_id, status="succeeded"),
                    )
                ]
            ),
        ],
        outcomes=[],
    )
    workflow_command = command("我的订单现在到哪里了？").model_copy(
        update={
            "tool_context": AgentToolRuntimeContext(
                order_id="ORDER-2026-001",
                available_tools={"query_logistics", "transfer_to_human"},
                permissions={"orders.view", "workspace.transfer"},
            )
        }
    )

    result = await workflow.run(cast_session(), workflow_command)

    assert result.action == AgentAction.TRANSFER_HUMAN
    assert result.draft_reply is None
    assert result.transfer_performed is True
    assert [item.status for item in result.tool_calls] == ["timeout", "succeeded"]
    assert result.required_tools == ["query_logistics", "transfer_to_human"]
    assert generator.requests == []


@pytest.mark.asyncio
async def test_mocked_coupon_result_can_only_enter_human_review() -> None:
    """Mock 发券即使模型置信度很高，也不能被描述为生产动作后自动发送。"""
    coupon_call_id = uuid.uuid4()
    customer_id = uuid.uuid4()
    workflow, _, _, _ = service(
        message_intent=IntentModelOutput(
            intent=IntentName.PRICE_INQUIRY,
            confidence=0.95,
            classification_state=ClassificationState.CLASSIFIED,
        ),
        rag_result=retrieval(),
        tool_batches=[
            AgentToolBatchResult(
                results=[
                    ExecutedAgentTool(
                        tool_name="send_coupon",
                        result=ToolResult(
                            tool_call_id=coupon_call_id,
                            status="succeeded",
                            data={"coupon_code": "CARE20", "status": "issued", "mocked": True},
                            mocked=True,
                        ),
                    )
                ]
            )
        ],
        outcomes=[
            ToolAnswerModelOutput(
                answer="已创建模拟优惠券记录，需要人工确认后才能作为真实发放结果。",
                tool_call_ids=[coupon_call_id],
                grounding_confidence=0.95,
                answer_language="zh-CN",
                needs_human=False,
                business_claims=empty_claim_inventory(),
            ),
            ToolGroundingReviewOutput(
                is_safe=True,
                is_grounded=True,
                completion_claim_valid=True,
                business_claims_consistent=True,
                confidence=0.94,
                reason_codes=[],
            ),
        ],
    )
    workflow_command = command("可以给我一张优惠券吗？").model_copy(
        update={
            "tool_context": AgentToolRuntimeContext(
                customer_id=customer_id,
                available_tools={"send_coupon"},
                permissions={"coupons.issue"},
                approved_actions=[
                    ApprovedToolAction(
                        tool_name="send_coupon",
                        idempotency_key="coupon-approved-workflow",
                        arguments={
                            "customer_id": str(customer_id),
                            "coupon_code": "CARE20",
                            "description": None,
                            "expires_at": None,
                        },
                    )
                ],
            )
        }
    )

    result = await workflow.run(cast_session(), workflow_command)

    assert result.terminal_state == WorkflowTerminalState.HUMAN_REVIEW
    assert result.action == AgentAction.HUMAN_REVIEW
    assert result.requires_human is True
    assert result.tool_calls[0].mocked is True
    assert result.send_performed is False


@pytest.mark.asyncio
async def test_tool_answer_with_unrelated_call_id_is_rejected_before_review() -> None:
    """模型引用其他运行的工具调用时必须失败关闭，不能让复核模型补救。"""
    actual_call_id = uuid.uuid4()
    workflow, _, generator, _ = service(
        message_intent=IntentModelOutput(
            intent=IntentName.LOGISTICS_QUERY,
            confidence=0.95,
            classification_state=ClassificationState.CLASSIFIED,
        ),
        rag_result=retrieval(),
        tool_batches=[
            AgentToolBatchResult(
                results=[
                    ExecutedAgentTool(
                        tool_name="query_logistics",
                        result=ToolResult(
                            tool_call_id=actual_call_id,
                            status="succeeded",
                            data=logistics_tool_data(),
                        ),
                    )
                ]
            )
        ],
        outcomes=[
            ToolAnswerModelOutput(
                answer="不可信工具答案",
                tool_call_ids=[uuid.uuid4()],
                grounding_confidence=0.99,
                answer_language="zh-CN",
                needs_human=False,
                business_claims=empty_claim_inventory(),
            )
        ],
    )
    workflow_command = command("我的订单现在到哪里了？").model_copy(
        update={
            "tool_context": AgentToolRuntimeContext(
                order_id="ORDER-2026-001",
                available_tools={"query_logistics"},
                permissions={"orders.view"},
            )
        }
    )

    result = await workflow.run(cast_session(), workflow_command)

    assert result.action == AgentAction.TRANSFER_HUMAN
    assert result.draft_reply is None
    assert result.tool_calls[0].tool_call_id == actual_call_id
    assert len(generator.requests) == 1


@pytest.mark.asyncio
async def test_invalid_completion_claim_forces_transfer_without_exposing_draft() -> None:
    """工具复核发现虚假完成声明时必须清零置信度并隐藏候选话术。"""
    tool_call_id = uuid.uuid4()
    workflow, _, _, _ = service(
        message_intent=IntentModelOutput(
            intent=IntentName.LOGISTICS_QUERY,
            confidence=0.95,
            classification_state=ClassificationState.CLASSIFIED,
        ),
        rag_result=retrieval(),
        tool_batches=[
            AgentToolBatchResult(
                results=[
                    ExecutedAgentTool(
                        tool_name="query_logistics",
                        result=ToolResult(
                            tool_call_id=tool_call_id,
                            status="succeeded",
                            data=logistics_tool_data(),
                        ),
                    )
                ]
            )
        ],
        outcomes=[
            ToolAnswerModelOutput(
                answer="订单已经送达。",
                tool_call_ids=[tool_call_id],
                grounding_confidence=0.95,
                answer_language="zh-CN",
                needs_human=False,
                business_claims=BusinessClaimInventory(
                    complete=True,
                    claims=[
                        BusinessClaim(
                            subject_type=BusinessClaimSubjectType.LOGISTICS,
                            subject_id="ORDER-2026-001",
                            action=BusinessClaimAction.REPORT_STATUS,
                            tense=BusinessClaimTense.PAST,
                            polarity=BusinessClaimPolarity.AFFIRMED,
                            condition=BusinessClaimCondition.ACTUAL,
                            evidence_type=BusinessClaimEvidenceType.TOOL_CALL,
                            evidence_id=tool_call_id,
                            confidence=0.95,
                        )
                    ],
                ),
            ),
            ToolGroundingReviewOutput(
                is_safe=True,
                is_grounded=False,
                completion_claim_valid=False,
                business_claims_consistent=True,
                confidence=0.95,
                reason_codes=["UNSUPPORTED_COMPLETION_CLAIM"],
            ),
        ],
    )
    workflow_command = command("我的订单现在到哪里了？").model_copy(
        update={
            "tool_context": AgentToolRuntimeContext(
                order_id="ORDER-2026-001",
                available_tools={"query_logistics"},
                permissions={"orders.view"},
            )
        }
    )

    result = await workflow.run(cast_session(), workflow_command)

    assert result.action == AgentAction.TRANSFER_HUMAN
    assert result.final_confidence == 0
    assert result.draft_reply is None


def cast_session() -> AsyncSession:
    """工作流测试的 RAG 端口不访问该占位会话。"""
    return object()  # type: ignore[return-value]
