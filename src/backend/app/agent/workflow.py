"""使用 LangGraph 编排可追踪、无平台副作用的 FAQ 单 Agent 工作流。"""

import asyncio
import logging
import operator
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, Protocol, TypedDict, cast

from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.business_claims import BusinessClaimInventory
from app.agent.embeddings import EmbeddingErrorCode, EmbeddingProviderError
from app.agent.errors import LLMErrorCode, LLMFailureStage, LLMOutputFailureKind, LLMOutputSchemaIssue, LLMProviderError
from app.agent.prompt_registry import BusinessPromptId
from app.agent.providers.base import OutputT, ProviderResult, StructuredRequest
from app.agent.rag import RagRetrievalResult
from app.agent.reply_policy import CustomerLanguage, SupportedLanguage, detect_customer_language, resolve_reply_language
from app.agent.reply_rendering import (
    bind_redacted_tool_claims,
    build_authoritative_tool_claims,
    build_trusted_tool_evidence,
    render_trusted_faq_reply,
    render_trusted_tool_reply,
)
from app.agent.reply_safety import ReplyContentOrigin, ReplyEvidenceKind, ReplySafetyPolicy
from app.agent.repository import (
    AgentDecisionReason,
    AgentRunStart,
    AgentWorkflowRunCompletion,
    AgentWorkflowRunRecorder,
)
from app.agent.retrieval_models import RerankingErrorCode, RerankingProviderError
from app.agent.schemas import (
    AgentAction,
    AgentCitation,
    AgentRunStatus,
    AgentToolCallView,
    AgentWorkflowCommand,
    AgentWorkflowResult,
    ClassificationState,
    FaqAnswerModelOutput,
    GroundingReviewOutput,
    IntentInferenceResult,
    IntentModelOutput,
    IntentName,
    RequiredToolName,
    ToolAnswerModelOutput,
    ToolGroundingReviewOutput,
    WorkflowTerminalState,
)
from app.agent.service import build_input_summary
from app.agent.tool_execution import AgentToolBatchResult, ExecutedAgentTool
from app.agent.tool_routing import detect_required_tools
from app.agent.translation import TRANSLATION_PROMPT_VERSION, TranslationBundleResult, TranslationService
from app.agent.workflow_prompt import (
    FAQ_ANSWER_PROMPT_VERSION,
    FAQ_ANSWER_SYSTEM_PROMPT,
    GROUNDING_REVIEW_PROMPT_VERSION,
    GROUNDING_REVIEW_SYSTEM_PROMPT,
    TOOL_ANSWER_PROMPT_VERSION,
    TOOL_ANSWER_SYSTEM_PROMPT,
    TOOL_GROUNDING_REVIEW_PROMPT_VERSION,
    TOOL_GROUNDING_REVIEW_SYSTEM_PROMPT,
    WORKFLOW_PROMPT_VERSION,
    build_faq_answer_prompt,
    build_grounding_review_prompt,
    build_tool_answer_prompt,
    build_tool_grounding_review_prompt,
)
from app.knowledge_base.schemas import KnowledgeRetrievalHit

logger = logging.getLogger(__name__)


class IntentInferenceClient(Protocol):
    """完整工作流复用分类能力时禁止创建嵌套 agent_run。"""

    @property
    def provider_name(self) -> str:
        """返回当前主分类 Provider。"""
        ...

    @property
    def model_name(self) -> str:
        """返回当前主分类模型。"""
        ...

    async def infer(
        self,
        command: AgentWorkflowCommand,
        *,
        agent_run_id: uuid.UUID | None,
    ) -> IntentInferenceResult:
        """返回结构化意图推断。"""
        ...


class RagClient(Protocol):
    """工作流可使用的 FAQ 检索契约。"""

    async def retrieve(
        self,
        session: AsyncSession,
        store_id: uuid.UUID,
        query: str,
    ) -> RagRetrievalResult:
        """返回当前店铺的发布知识。"""
        ...


class StructuredGenerator(Protocol):
    """答案与复核节点共用的结构化生成契约。"""

    async def generate(
        self,
        request: StructuredRequest,
        response_schema: type[OutputT],
    ) -> ProviderResult[OutputT]:
        """生成并校验指定 Pydantic 类型。"""
        ...


class ToolWorkflowClient(Protocol):
    """Agent 只能通过全栈工具模块执行白名单业务动作。"""

    async def execute_required(
        self,
        command: AgentWorkflowCommand,
        *,
        agent_run_id: uuid.UUID,
        required_tools: list[RequiredToolName],
    ) -> AgentToolBatchResult:
        """按可信上下文执行所需工具并返回可追踪结果。"""
        ...


class WorkflowState(TypedDict, total=False):
    """LangGraph 节点间显式传递的类型化状态。"""

    command: AgentWorkflowCommand
    session: AsyncSession
    agent_run_id: uuid.UUID
    state_path: Annotated[list[str], operator.add]
    node_timings_ms: Annotated[list[tuple[str, int]], operator.add]
    inference: IntentInferenceResult
    retrieval: RagRetrievalResult
    hits: list[KnowledgeRetrievalHit]
    required_tools: list[RequiredToolName]
    tool_executions: Annotated[list[ExecutedAgentTool], operator.add]
    unresolved_tools: list[RequiredToolName]
    draft: FaqAnswerModelOutput
    review: GroundingReviewOutput
    tool_draft: ToolAnswerModelOutput
    tool_review: ToolGroundingReviewOutput
    authoritative_claims: BusinessClaimInventory
    safety_passed: bool
    tool_safety_passed: bool
    automatic_delivery_allowed: bool
    trusted_reply: str
    transfer_performed: bool
    model_refusal: bool
    grounding_confidence: float
    final_confidence: float
    action: AgentAction
    terminal_state: WorkflowTerminalState
    input_tokens: int
    output_tokens: int
    provider: str
    model: str
    detected_language: CustomerLanguage
    reply_language: SupportedLanguage
    customer_translation: TranslationBundleResult
    translation_error_code: str
    safety_reason_codes: list[str]
    decision_reason: AgentDecisionReason


class AgentWorkflowExecutionError(Exception):
    """对调用方只暴露稳定错误码和可追踪运行 ID。"""

    def __init__(self, agent_run_id: uuid.UUID, error_code: str) -> None:
        self.agent_run_id = agent_run_id
        self.error_code = error_code
        super().__init__(f"Agent 工作流失败，agent_run_id={agent_run_id}，error_code={error_code}")


class AgentWorkflowService:
    """编排意图、RAG 和受控工具；业务副作用只能由工具端口执行。"""

    def __init__(
        self,
        *,
        classifier: IntentInferenceClient,
        rag_service: RagClient,
        generator: StructuredGenerator,
        run_recorder: AgentWorkflowRunRecorder,
        tool_service: ToolWorkflowClient | None = None,
        translation_service: TranslationService | None = None,
        reply_safety_policy: ReplySafetyPolicy | None = None,
        auto_reply_threshold: float,
        human_review_threshold: float,
    ) -> None:
        if not 0 <= human_review_threshold < auto_reply_threshold <= 1:
            raise ValueError("Agent 置信度阈值必须满足 0 <= 人工复核 < 自动回复 <= 1")
        self.classifier = classifier
        self.rag_service = rag_service
        self.generator = generator
        self.run_recorder = run_recorder
        self.tool_service = tool_service
        self.translation_service = translation_service
        self.reply_safety_policy = reply_safety_policy or ReplySafetyPolicy()
        self.auto_reply_threshold = auto_reply_threshold
        self.human_review_threshold = human_review_threshold
        self._graph = self._build_graph()

    async def run(self, session: AsyncSession, command: AgentWorkflowCommand) -> AgentWorkflowResult:
        """执行一次完整 FAQ 工作流，并在任何外部调用前创建运行记录。"""
        run_id = await self.run_recorder.start(
            AgentRunStart(
                store_id=command.store_id,
                conversation_id=command.conversation_id,
                trigger_message_id=command.trigger_message_id,
                provider_name=self.classifier.provider_name,
                model_name=self.classifier.model_name,
                prompt_version=WORKFLOW_PROMPT_VERSION,
                input_summary=build_input_summary(command),
                trace_id=command.trace_id,
            )
        )
        started_at = time.perf_counter()
        initial_state = cast(
            WorkflowState,
            {
                "command": command,
                "session": session,
                "agent_run_id": run_id,
                "state_path": ["RECEIVED"],
                "node_timings_ms": [],
                "required_tools": [],
                "tool_executions": [],
                "unresolved_tools": [],
                "hits": [],
                "safety_passed": False,
                "tool_safety_passed": False,
                "automatic_delivery_allowed": False,
                "transfer_performed": False,
                "model_refusal": False,
                "grounding_confidence": 0.0,
                "final_confidence": 0.0,
                "input_tokens": 0,
                "output_tokens": 0,
                "provider": self.classifier.provider_name,
                "model": self.classifier.model_name,
                "safety_reason_codes": [],
                "authoritative_claims": BusinessClaimInventory(complete=True, claims=[]),
            },
        )
        try:
            state = cast(WorkflowState, await self._graph.ainvoke(initial_state))
            result = self._build_result(state, max(0, int((time.perf_counter() - started_at) * 1000)))
            await self.run_recorder.complete_workflow(
                run_id,
                AgentWorkflowRunCompletion(
                    provider_name=result.provider,
                    model_name=result.model,
                    prompt_version=WORKFLOW_PROMPT_VERSION,
                    intent=result.intent,
                    classification_state=result.classification_state,
                    intent_confidence=result.intent_confidence,
                    retrieval_score=result.retrieval_score,
                    final_confidence=result.final_confidence,
                    action=result.action,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    latency_ms=result.latency_ms,
                    state_path=state["state_path"],
                    citation_ids=[citation.chunk_id for citation in result.citations],
                    required_tools=list(result.required_tools),
                    prompt_versions=result.prompt_versions,
                    embedding_provider=result.embedding_provider,
                    embedding_model=result.embedding_model,
                    reranker_provider=result.reranker_provider,
                    reranker_model=result.reranker_model,
                    reranker_revision=result.reranker_revision,
                    retrieval_candidate_count=result.retrieval_candidate_count,
                    tool_call_summaries=[
                        f"{item.tool_call_id}:{item.tool_name}:{item.status}:{item.error_code or 'none'}"
                        for item in result.tool_calls
                    ],
                    detected_language=result.detected_language,
                    reply_language=result.reply_language,
                    translation_prompt_version=(
                        result.customer_translation.prompt_version if result.customer_translation else None
                    ),
                    translation_error_code=state.get("translation_error_code"),
                    safety_reason_codes=result.safety_reason_codes,
                    decision_reason=state["decision_reason"],
                    node_timings_ms=state["node_timings_ms"],
                    business_claim_summaries=[
                        (
                            f"{claim.subject_type.value}:{claim.action.value}:"
                            f"{claim.evidence_type.value}:{claim.evidence_id or 'none'}"
                        )
                        for claim in state.get(
                            "authoritative_claims",
                            BusinessClaimInventory(complete=True, claims=[]),
                        ).claims
                    ],
                ),
            )
            logger.info(
                "agent_workflow_completed",
                extra={
                    "trace_id": command.trace_id,
                    "agent_run_id": str(run_id),
                    "intent": result.intent.value if result.intent else None,
                    "terminal_state": result.terminal_state.value,
                    "action": result.action.value,
                    "retrieval_count": len(result.citations),
                    "final_confidence": result.final_confidence,
                    "latency_ms": result.latency_ms,
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "detected_language": result.detected_language.value,
                    "reply_language": result.reply_language,
                    "safety_reason_codes": result.safety_reason_codes,
                },
            )
            return result
        except asyncio.CancelledError:
            await self._record_failure(run_id, "AGENT_CANCELLED", started_at)
            raise
        except (LLMProviderError, EmbeddingProviderError, RerankingProviderError) as error:
            error_code = error.code.value
            await self._record_failure(
                run_id,
                error_code,
                started_at,
                failure_stage=error.failure_stage if isinstance(error, LLMProviderError) else None,
                output_failure_kind=error.output_failure_kind if isinstance(error, LLMProviderError) else None,
                output_schema_issues=error.output_schema_issues if isinstance(error, LLMProviderError) else (),
            )
            raise AgentWorkflowExecutionError(run_id, error_code) from error
        except AgentWorkflowExecutionError:
            raise
        except Exception as error:
            await self._record_failure(run_id, "AGENT_WORKFLOW_ERROR", started_at)
            logger.error(
                "agent_workflow_failed",
                extra={
                    "trace_id": command.trace_id,
                    "agent_run_id": str(run_id),
                    "error_type": type(error).__name__,
                },
            )
            raise AgentWorkflowExecutionError(run_id, "AGENT_WORKFLOW_ERROR") from error

    def _build_graph(self) -> Any:
        """构建无循环工作流，硬性限制节点次数和模型消费。"""
        builder = StateGraph(WorkflowState)
        builder.add_node("context_loaded", self._context_loaded)
        builder.add_node("intent_classified", self._intent_classified)
        builder.add_node("tool_required", self._tool_required)
        builder.add_node("tool_executed", self._tool_executed)
        builder.add_node("tool_response_drafted", self._tool_response_drafted)
        builder.add_node("tool_safety_checked", self._tool_safety_checked)
        builder.add_node("knowledge_retrieved", self._knowledge_retrieved)
        builder.add_node("response_drafted", self._timed_node("faq_draft", self._response_drafted))
        builder.add_node("safety_checked", self._timed_node("safety_review", self._safety_checked))
        builder.add_node("confidence_evaluated", self._confidence_evaluated)
        builder.add_node("reply_translated", self._timed_node("translation", self._reply_translated))
        builder.add_node("handoff_executed", self._handoff_executed)
        builder.add_node("auto_reply_ready", self._auto_reply_ready)
        builder.add_node("human_review", self._human_review)
        builder.add_node("transferred", self._transferred)
        builder.add_edge(START, "context_loaded")
        builder.add_edge("context_loaded", "intent_classified")
        builder.add_conditional_edges("intent_classified", self._route_after_intent)
        builder.add_edge("tool_required", "tool_executed")
        builder.add_conditional_edges("tool_executed", self._route_after_tool_execution)
        builder.add_conditional_edges("tool_response_drafted", self._route_after_tool_draft)
        builder.add_edge("tool_safety_checked", "confidence_evaluated")
        builder.add_conditional_edges("knowledge_retrieved", self._route_after_retrieval)
        builder.add_conditional_edges("response_drafted", self._route_after_draft)
        builder.add_edge("safety_checked", "confidence_evaluated")
        builder.add_edge("confidence_evaluated", "reply_translated")
        builder.add_conditional_edges("reply_translated", self._route_terminal)
        builder.add_edge("handoff_executed", "transferred")
        builder.add_edge("auto_reply_ready", END)
        builder.add_edge("human_review", END)
        builder.add_edge("transferred", END)
        return builder.compile()

    @staticmethod
    def _timed_node(
        name: str,
        node: Callable[[WorkflowState], Awaitable[WorkflowState]],
    ) -> Any:
        """仅累计固定节点的单调耗时；运行摘要写入端再执行白名单过滤。"""

        async def run_timed(state: WorkflowState) -> WorkflowState:
            started_at = time.perf_counter_ns()
            update = await node(state)
            elapsed_ms = max(0, (time.perf_counter_ns() - started_at) // 1_000_000)
            return {**update, "node_timings_ms": [(name, elapsed_ms)]}

        return run_timed

    async def _context_loaded(self, state: WorkflowState) -> WorkflowState:
        """命令已由 Pydantic 完成长度和历史预算校验。"""
        command = state["command"]
        detected_language = detect_customer_language(command.message)
        reply_language = resolve_reply_language(
            command.reply_profile,
            detected_language,
            command.language,
        )
        return {
            "detected_language": detected_language,
            "reply_language": reply_language,
            "state_path": ["CONTEXT_LOADED"],
        }

    async def _intent_classified(self, state: WorkflowState) -> WorkflowState:
        """分类与当前店铺只读检索重叠；仅 FAQ 路径消费检索结果。"""
        command = state["command"]
        retrieval_task: asyncio.Task[tuple[RagRetrievalResult, int]] | None = None
        # 命中任何确定性工具规则的提问保持原工具路径，不做推测性 FAQ 查询。
        if not any(detect_required_tools(command.message, intent) for intent in IntentName):

            async def retrieve_timed() -> tuple[RagRetrievalResult, int]:
                started_at = time.perf_counter_ns()
                result = await self.rag_service.retrieve(state["session"], command.store_id, command.message)
                return result, max(0, (time.perf_counter_ns() - started_at) // 1_000_000)

            retrieval_task = asyncio.create_task(retrieve_timed())
        try:
            classification_started_at = time.perf_counter_ns()
            try:
                inference = await self.classifier.infer(command, agent_run_id=state["agent_run_id"])
            except LLMProviderError as error:
                if error.code != LLMErrorCode.LLM_REFUSAL:
                    error.failure_stage = LLMFailureStage.CLASSIFICATION
                    raise
                inference = IntentInferenceResult(
                    output=IntentModelOutput(
                        intent=None,
                        confidence=0,
                        classification_state=ClassificationState.MODEL_REFUSAL,
                    ),
                    provider=self.classifier.provider_name,
                    model=self.classifier.model_name,
                    prompt_version="intent-classifier-v1.0.1",
                    input_tokens=0,
                    output_tokens=0,
                    latency_ms=0,
                )
            classification_ms = max(0, (time.perf_counter_ns() - classification_started_at) // 1_000_000)
            update: WorkflowState = {
                "inference": inference,
                "provider": inference.provider,
                "model": inference.model,
                "input_tokens": state["input_tokens"] + inference.input_tokens,
                "output_tokens": state["output_tokens"] + inference.output_tokens,
                "node_timings_ms": [("classification", classification_ms)],
                "state_path": ["INTENT_CLASSIFIED"],
            }
            output = inference.output
            if (
                retrieval_task is not None
                and output.classification_state == ClassificationState.CLASSIFIED
                and output.confidence >= self.human_review_threshold
                and output.intent is not None
                and not detect_required_tools(command.message, output.intent)
            ):
                retrieval, retrieval_ms = await retrieval_task
                update["retrieval"] = retrieval
                update["node_timings_ms"] = [("classification", classification_ms), ("retrieval", retrieval_ms)]
            return update
        finally:
            if retrieval_task is not None:
                if not retrieval_task.done():
                    retrieval_task.cancel()
                await asyncio.gather(retrieval_task, return_exceptions=True)

    def _route_after_intent(self, state: WorkflowState) -> str:
        """拒判和低置信度直接决策；实时业务需求进入工具门禁。"""
        output = state["inference"].output
        if (
            output.classification_state != ClassificationState.CLASSIFIED
            or output.confidence < self.human_review_threshold
        ):
            return "confidence_evaluated"
        assert output.intent is not None
        if detect_required_tools(state["command"].message, output.intent):
            return "tool_required"
        return "knowledge_retrieved"

    async def _tool_required(self, state: WorkflowState) -> WorkflowState:
        """由确定性规则声明白名单工具，模型无权发明工具名称。"""
        intent = state["inference"].output.intent
        assert intent is not None
        return {
            "required_tools": detect_required_tools(state["command"].message, intent),
            "state_path": ["TOOL_REQUIRED"],
        }

    async def _tool_executed(self, state: WorkflowState) -> WorkflowState:
        """通过全栈工具端口执行；缺少可信上下文时明确保留为未解析。"""
        required_tools = state.get("required_tools", [])
        if self.tool_service is None:
            return {
                "unresolved_tools": required_tools,
                "state_path": ["TOOL_EXECUTED"],
            }
        batch = await self.tool_service.execute_required(
            state["command"],
            agent_run_id=state["agent_run_id"],
            required_tools=required_tools,
        )
        return {
            "tool_executions": batch.results,
            "unresolved_tools": batch.unresolved_tools,
            "state_path": ["TOOL_EXECUTED"],
        }

    def _route_after_tool_execution(self, state: WorkflowState) -> str:
        """只有全部非接管工具成功时才允许解释工具结果。"""
        executions = state.get("tool_executions", [])
        if state.get("unresolved_tools"):
            return "confidence_evaluated"
        if not executions:
            return "confidence_evaluated"
        if any(item.tool_name == "transfer_to_human" for item in executions):
            return "confidence_evaluated"
        if any(item.result.status != "succeeded" for item in executions):
            return "confidence_evaluated"
        return "tool_response_drafted"

    async def _tool_response_drafted(self, state: WorkflowState) -> WorkflowState:
        """仅依据已成功工具结果生成解释，不得声称失败动作已完成。"""
        command = state["command"]
        request = StructuredRequest(
            system_prompt=TOOL_ANSWER_SYSTEM_PROMPT,
            user_prompt=build_tool_answer_prompt(command, state["tool_executions"], state["reply_language"]),
            trace_id=command.trace_id,
            max_output_tokens=1024,
            business_prompt_id=BusinessPromptId.TOOL_ANSWER,
        )
        try:
            generated = await self.generator.generate(request, ToolAnswerModelOutput)
        except LLMProviderError as error:
            if error.code != LLMErrorCode.LLM_REFUSAL:
                error.failure_stage = LLMFailureStage.TOOL_DRAFT
                raise
            return {"model_refusal": True, "state_path": ["TOOL_RESPONSE_DRAFTED"]}
        return {
            "tool_draft": generated.parsed_output,
            "provider": generated.provider,
            "model": generated.model,
            "input_tokens": state["input_tokens"] + generated.input_tokens,
            "output_tokens": state["output_tokens"] + generated.output_tokens,
            "state_path": ["TOOL_RESPONSE_DRAFTED"],
        }

    def _route_after_tool_draft(self, state: WorkflowState) -> str:
        """拒绝或无草稿时直接失败关闭。"""
        return "tool_safety_checked" if state.get("tool_draft") else "confidence_evaluated"

    async def _tool_safety_checked(self, state: WorkflowState) -> WorkflowState:
        """先用代码校验工具引用，再由独立模型复核事实和完成声明。"""
        draft = state["tool_draft"]
        successful_ids = {
            item.result.tool_call_id for item in state.get("tool_executions", []) if item.result.status == "succeeded"
        }
        cited_ids = set(draft.tool_call_ids)
        if not cited_ids or not cited_ids.issubset(successful_ids):
            return {
                "tool_safety_passed": False,
                "grounding_confidence": 0.0,
                "safety_reason_codes": ["INVALID_TOOL_REFERENCE"],
                "state_path": ["TOOL_SAFETY_CHECKED"],
            }
        successful_tool_evidence = build_trusted_tool_evidence(state.get("tool_executions", []))
        authoritative_claims = build_authoritative_tool_claims(state.get("tool_executions", []))
        bound_model_claims = bind_redacted_tool_claims(draft.business_claims, authoritative_claims)
        successful_tools = {item.tool_name for item in successful_tool_evidence.values()}
        mocked_tool_call_ids = {
            item.result.tool_call_id
            for item in state.get("tool_executions", [])
            if item.result.status == "succeeded" and item.result.mocked
        }
        trusted_reply = render_trusted_tool_reply(
            state.get("tool_executions", []),
            state["reply_language"],
            draft.answer,
        )
        policy_claims = authoritative_claims if authoritative_claims.claims else bound_model_claims
        deterministic_safety = self.reply_safety_policy.evaluate(
            draft.answer,
            evidence_kind=ReplyEvidenceKind.TOOL,
            successful_tools=successful_tools,
            has_mock_result=any(item.result.mocked for item in state.get("tool_executions", [])),
            claim_inventory=policy_claims,
            successful_tool_evidence=successful_tool_evidence,
            mocked_tool_call_ids=mocked_tool_call_ids,
            expected_store_id=state["command"].store_id,
            content_origin=(
                ReplyContentOrigin.TRUSTED_TOOL_TEMPLATE
                if trusted_reply is not None and authoritative_claims.claims
                else ReplyContentOrigin.MODEL_GENERATED
            ),
        )
        reason_codes = list(deterministic_safety.reason_codes)
        if authoritative_claims.claims and bound_model_claims.claims:
            # 模型声明不再授予权限，但仍作为纵深检查捕获跨订单、错工具和
            # 错主体。唯一允许的对象占位符已在上方按可信证据精确绑定。
            advisory_safety = self.reply_safety_policy.evaluate(
                draft.answer,
                evidence_kind=ReplyEvidenceKind.TOOL,
                successful_tools=successful_tools,
                has_mock_result=any(item.result.mocked for item in state.get("tool_executions", [])),
                claim_inventory=bound_model_claims,
                successful_tool_evidence=successful_tool_evidence,
                mocked_tool_call_ids=mocked_tool_call_ids,
                expected_store_id=state["command"].store_id,
                content_origin=ReplyContentOrigin.MODEL_GENERATED,
            )
            reason_codes.extend(advisory_safety.reason_codes)
        if draft.answer_language != state["reply_language"]:
            reason_codes.append("OUTPUT_LANGUAGE_MISMATCH")
        if reason_codes:
            return {
                "tool_safety_passed": False,
                "grounding_confidence": 0.0,
                "automatic_delivery_allowed": False,
                "safety_reason_codes": list(dict.fromkeys(reason_codes)),
                "authoritative_claims": authoritative_claims,
                "state_path": ["TOOL_SAFETY_CHECKED"],
            }
        command = state["command"]
        request = StructuredRequest(
            system_prompt=TOOL_GROUNDING_REVIEW_SYSTEM_PROMPT,
            user_prompt=build_tool_grounding_review_prompt(command, state["tool_executions"], draft),
            trace_id=command.trace_id,
            max_output_tokens=256,
            business_prompt_id=BusinessPromptId.TOOL_GROUNDING_REVIEW,
        )
        try:
            generated = await self.generator.generate(request, ToolGroundingReviewOutput)
        except LLMProviderError as error:
            if error.code != LLMErrorCode.LLM_REFUSAL:
                error.failure_stage = LLMFailureStage.TOOL_SAFETY_REVIEW
                raise
            return {
                "model_refusal": True,
                "tool_safety_passed": False,
                "grounding_confidence": 0.0,
                "automatic_delivery_allowed": False,
                "safety_reason_codes": ["MODEL_REFUSAL"],
                "authoritative_claims": authoritative_claims,
                "state_path": ["TOOL_SAFETY_CHECKED"],
            }
        review = generated.parsed_output
        safety_passed = (
            review.is_safe
            and review.is_grounded
            and review.completion_claim_valid
            and review.business_claims_consistent
            and not draft.needs_human
        )
        return {
            "tool_review": review,
            "tool_safety_passed": safety_passed,
            "automatic_delivery_allowed": safety_passed and deterministic_safety.automatic_delivery_allowed,
            "trusted_reply": trusted_reply or "",
            "grounding_confidence": min(draft.grounding_confidence, review.confidence) if safety_passed else 0.0,
            "safety_reason_codes": [] if safety_passed else review.reason_codes,
            "authoritative_claims": authoritative_claims,
            "provider": generated.provider,
            "model": generated.model,
            "input_tokens": state["input_tokens"] + generated.input_tokens,
            "output_tokens": state["output_tokens"] + generated.output_tokens,
            "state_path": ["TOOL_SAFETY_CHECKED"],
        }

    async def _knowledge_retrieved(self, state: WorkflowState) -> WorkflowState:
        """查询当前 store_id 的发布 FAQ，并累计 Embedding Token。"""
        command = state["command"]
        retrieval = state.get("retrieval")
        timings: list[tuple[str, int]] = []
        if retrieval is None:
            started_at = time.perf_counter_ns()
            retrieval = await self.rag_service.retrieve(state["session"], command.store_id, command.message)
            timings = [("retrieval", max(0, (time.perf_counter_ns() - started_at) // 1_000_000))]
        update: WorkflowState = {
            "retrieval": retrieval,
            "hits": retrieval.hits,
            "input_tokens": state["input_tokens"] + retrieval.embedding_input_tokens,
            "state_path": ["KNOWLEDGE_RETRIEVED"],
        }
        if timings:
            update["node_timings_ms"] = timings
        return update

    def _route_after_retrieval(self, state: WorkflowState) -> str:
        """无知识时禁止调用答案模型，直接进入保守决策。"""
        return "response_drafted" if state.get("hits") else "confidence_evaluated"

    async def _response_drafted(self, state: WorkflowState) -> WorkflowState:
        """仅依据本次 Top-K 片段生成带引用草稿。"""
        command = state["command"]
        request = StructuredRequest(
            system_prompt=FAQ_ANSWER_SYSTEM_PROMPT,
            user_prompt=build_faq_answer_prompt(command, state["hits"], state["reply_language"]),
            trace_id=command.trace_id,
            max_output_tokens=1024,
            business_prompt_id=BusinessPromptId.FAQ_ANSWER,
        )
        try:
            generated = await self.generator.generate(request, FaqAnswerModelOutput)
        except LLMProviderError as error:
            if error.code != LLMErrorCode.LLM_REFUSAL:
                error.failure_stage = LLMFailureStage.FAQ_DRAFT
                raise
            return {"model_refusal": True, "state_path": ["RESPONSE_DRAFTED"]}
        return {
            "draft": generated.parsed_output,
            "provider": generated.provider,
            "model": generated.model,
            "input_tokens": state["input_tokens"] + generated.input_tokens,
            "output_tokens": state["output_tokens"] + generated.output_tokens,
            "state_path": ["RESPONSE_DRAFTED"],
        }

    def _route_after_draft(self, state: WorkflowState) -> str:
        """模型拒绝没有草稿，不能继续复核或尝试绕过。"""
        return "safety_checked" if state.get("draft") else "confidence_evaluated"

    async def _safety_checked(self, state: WorkflowState) -> WorkflowState:
        """先由代码校验引用集合，再调用独立模型复核依据和安全性。"""
        draft = state["draft"]
        allowed_ids = {hit.chunk_id for hit in state["hits"]}
        cited_ids = set(draft.citation_chunk_ids)
        if not cited_ids or not cited_ids.issubset(allowed_ids):
            return {
                "safety_passed": False,
                "grounding_confidence": 0.0,
                "safety_reason_codes": ["INVALID_FAQ_REFERENCE"],
                "state_path": ["SAFETY_CHECKED"],
            }
        trusted_reply = render_trusted_faq_reply(state["hits"], draft.citation_chunk_ids, draft.answer)
        deterministic_safety = self.reply_safety_policy.evaluate(
            draft.answer,
            evidence_kind=ReplyEvidenceKind.FAQ,
            claim_inventory=draft.business_claims,
            faq_evidence_ids=allowed_ids,
            expected_store_id=state["command"].store_id,
            knowledge_safety_metadata=[hit.safety_metadata for hit in state["hits"] if hit.chunk_id in cited_ids],
            content_origin=(
                ReplyContentOrigin.TRUSTED_FAQ_TEMPLATE
                if trusted_reply is not None
                else ReplyContentOrigin.MODEL_GENERATED
            ),
        )
        reason_codes = list(deterministic_safety.reason_codes)
        if draft.answer_language != state["reply_language"]:
            reason_codes.append("OUTPUT_LANGUAGE_MISMATCH")
        if reason_codes:
            return {
                "safety_passed": False,
                "grounding_confidence": 0.0,
                "automatic_delivery_allowed": False,
                "safety_reason_codes": list(dict.fromkeys(reason_codes)),
                "state_path": ["SAFETY_CHECKED"],
            }
        command = state["command"]
        request = StructuredRequest(
            system_prompt=GROUNDING_REVIEW_SYSTEM_PROMPT,
            user_prompt=build_grounding_review_prompt(command, state["hits"], draft),
            trace_id=command.trace_id,
            max_output_tokens=256,
            business_prompt_id=BusinessPromptId.FAQ_GROUNDING_REVIEW,
        )
        try:
            generated = await self.generator.generate(request, GroundingReviewOutput)
        except LLMProviderError as error:
            if error.code != LLMErrorCode.LLM_REFUSAL:
                error.failure_stage = LLMFailureStage.SAFETY_REVIEW
                raise
            return {
                "model_refusal": True,
                "safety_passed": False,
                "grounding_confidence": 0.0,
                "automatic_delivery_allowed": False,
                "safety_reason_codes": ["MODEL_REFUSAL"],
                "state_path": ["SAFETY_CHECKED"],
            }
        review = generated.parsed_output
        safety_passed = (
            review.is_safe and review.is_grounded and review.business_claims_consistent and not draft.needs_human
        )
        return {
            "review": review,
            "safety_passed": safety_passed,
            "automatic_delivery_allowed": safety_passed and deterministic_safety.automatic_delivery_allowed,
            "trusted_reply": trusted_reply or "",
            "grounding_confidence": min(draft.grounding_confidence, review.confidence) if safety_passed else 0.0,
            "safety_reason_codes": [] if safety_passed else review.reason_codes,
            "provider": generated.provider,
            "model": generated.model,
            "input_tokens": state["input_tokens"] + generated.input_tokens,
            "output_tokens": state["output_tokens"] + generated.output_tokens,
            "state_path": ["SAFETY_CHECKED"],
        }

    async def _confidence_evaluated(self, state: WorkflowState) -> WorkflowState:
        """用代码聚合三项置信度，模型不能自行决定最终动作。"""
        output = state["inference"].output
        retrieval = state.get("retrieval")
        retrieval_score = retrieval.top_score if retrieval else 0.0
        grounding_confidence = state.get("grounding_confidence", 0.0)
        required_tools = state.get("required_tools", [])
        executions = state.get("tool_executions", [])
        uses_tools = bool(required_tools)

        if uses_tools:
            succeeded_names = {item.tool_name for item in executions if item.result.status == "succeeded"}
            execution_failed = any(item.result.status != "succeeded" for item in executions)
            transfer_requested = "transfer_to_human" in required_tools
            is_forced_transfer = (
                output.classification_state != ClassificationState.CLASSIFIED
                or output.confidence < self.human_review_threshold
                or bool(state.get("unresolved_tools"))
                or not set(required_tools).issubset(succeeded_names)
                or execution_failed
                or transfer_requested
                or state.get("model_refusal", False)
                or not state.get("tool_safety_passed", False)
            )
            final_confidence = 0.0 if is_forced_transfer else min(output.confidence, 1.0, grounding_confidence)
        else:
            is_forced_transfer = (
                output.classification_state != ClassificationState.CLASSIFIED
                or output.confidence < self.human_review_threshold
                or not state.get("hits")
                or state.get("model_refusal", False)
                or not state.get("safety_passed", False)
            )
            final_confidence = (
                0.0 if is_forced_transfer else min(output.confidence, retrieval_score, grounding_confidence)
            )
        if is_forced_transfer or final_confidence < self.human_review_threshold:
            action = AgentAction.TRANSFER_HUMAN
        elif final_confidence < self.auto_reply_threshold:
            action = AgentAction.HUMAN_REVIEW
        else:
            action = AgentAction.AUTO_REPLY
        if action == AgentAction.AUTO_REPLY and any(item.result.mocked for item in executions):
            action = AgentAction.HUMAN_REVIEW
        if (
            action == AgentAction.TRANSFER_HUMAN
            and any(item.result.status == "succeeded" and item.result.mocked for item in executions)
            and set(state.get("safety_reason_codes", [])) == {"MOCK_COMPLETION_CLAIM"}
            and output.classification_state == ClassificationState.CLASSIFIED
            and output.confidence >= self.human_review_threshold
            and not state.get("unresolved_tools")
            and not state.get("model_refusal", False)
            and all(item.result.status == "succeeded" for item in executions)
            and "transfer_to_human" not in required_tools
        ):
            # Mock 写动作被确定性安全门禁判为不可对客，并不代表会话本身必须
            # 立即转接。只有 MOCK_COMPLETION_CLAIM 这一项原因且工具均成功时，
            # 保留人工复核终态；草稿仍因 tool_safety_passed=False 不会对客暴露。
            action = AgentAction.HUMAN_REVIEW
        if action == AgentAction.AUTO_REPLY and not state.get("automatic_delivery_allowed", False):
            # 语言模型草稿只能供人工复核；自动就绪必须来自当次可信数据的固定文本。
            action = AgentAction.HUMAN_REVIEW
        decision_reason: AgentDecisionReason = "none"
        if action == AgentAction.TRANSFER_HUMAN:
            if uses_tools:
                decision_reason = "tool_path"
            elif output.classification_state != ClassificationState.CLASSIFIED:
                decision_reason = "classification_unresolved"
            elif output.confidence < self.human_review_threshold:
                decision_reason = "intent_confidence_low"
            elif not state.get("hits"):
                decision_reason = "faq_knowledge_missing"
            elif state.get("model_refusal", False):
                decision_reason = "model_refusal"
            else:
                draft = state.get("draft")
                review = state.get("review")
                if draft is not None and draft.needs_human:
                    decision_reason = "faq_draft_needs_human"
                elif review is not None and not review.is_safe:
                    decision_reason = "faq_review_unsafe"
                elif review is not None and not review.is_grounded:
                    decision_reason = "faq_review_ungrounded"
                elif review is not None and not review.business_claims_consistent:
                    decision_reason = "faq_review_claims_inconsistent"
                elif state.get("safety_reason_codes"):
                    decision_reason = "faq_safety_rejected"
                elif review is None:
                    decision_reason = "faq_review_missing"
                elif review.confidence < self.human_review_threshold:
                    decision_reason = "faq_review_confidence_low"
                elif draft is not None and draft.grounding_confidence < self.human_review_threshold:
                    decision_reason = "faq_draft_confidence_low"
                elif retrieval_score < self.human_review_threshold:
                    decision_reason = "faq_retrieval_confidence_low"
                else:
                    decision_reason = "unknown"
        return {
            "final_confidence": final_confidence,
            "action": action,
            "decision_reason": decision_reason,
            "state_path": ["CONFIDENCE_EVALUATED"],
        }

    async def _reply_translated(self, state: WorkflowState) -> WorkflowState:
        """按客服工作语言翻译客户消息和安全草稿。

        翻译虽然是辅助字段，但仍属于本次模型运行；供应商超时、拒绝或
        结构错误必须让工作流失败，避免运行记录伪装成成功。
        """
        if self.translation_service is None:
            return {"state_path": ["REPLY_TRANSLATED"]}
        command = state["command"]
        draft_reply = self._safe_draft_reply(state)
        try:
            translation = await self.translation_service.translate_bundle(
                trigger_message_id=command.trigger_message_id,
                message=command.message,
                draft_reply=draft_reply,
                target_language=command.reply_profile.operator_language,
                trace_id=command.trace_id,
            )
        except LLMProviderError as error:
            error.failure_stage = LLMFailureStage.TRANSLATION
            raise
        if translation is None:
            return {"state_path": ["REPLY_TRANSLATED"]}
        return {
            "customer_translation": translation,
            "provider": translation.provider,
            "model": translation.model,
            "input_tokens": state["input_tokens"] + translation.input_tokens,
            "output_tokens": state["output_tokens"] + translation.output_tokens,
            "state_path": ["REPLY_TRANSLATED"],
        }

    @staticmethod
    def _safe_draft_reply(state: WorkflowState) -> str | None:
        """只允许已经通过对应安全门禁的草稿进入翻译节点。"""
        action = state["action"]
        if action not in {AgentAction.AUTO_REPLY, AgentAction.HUMAN_REVIEW}:
            return None
        if action == AgentAction.AUTO_REPLY:
            return state.get("trusted_reply") or None
        if state.get("safety_passed") and state.get("draft") is not None:
            return state["draft"].answer
        if state.get("tool_safety_passed") and state.get("tool_draft") is not None:
            return state["tool_draft"].answer
        return None

    def _route_terminal(self, state: WorkflowState) -> str:
        """根据代码动作选择唯一终态节点。"""
        action = state["action"]
        if action == AgentAction.AUTO_REPLY:
            return "auto_reply_ready"
        if action == AgentAction.HUMAN_REVIEW:
            return "human_review"
        return "handoff_executed"

    async def _handoff_executed(self, state: WorkflowState) -> WorkflowState:
        """必要时调用转人工工具；失败仍保留接管建议且不得伪装成功。"""
        executions = state.get("tool_executions", [])
        existing_transfer = next(
            (item for item in executions if item.tool_name == "transfer_to_human"),
            None,
        )
        if existing_transfer is not None:
            return {
                "transfer_performed": existing_transfer.result.status == "succeeded",
                "state_path": ["HANDOFF_EXECUTED"],
            }

        command = state["command"]
        context = command.tool_context
        if self.tool_service is None or context is None or "transfer_to_human" not in context.available_tools:
            return {"transfer_performed": False, "state_path": ["HANDOFF_EXECUTED"]}

        required_tools = list(dict.fromkeys([*state.get("required_tools", []), "transfer_to_human"]))
        batch = await self.tool_service.execute_required(
            command,
            agent_run_id=state["agent_run_id"],
            required_tools=["transfer_to_human"],
        )
        transfer = next(
            (item for item in batch.results if item.tool_name == "transfer_to_human"),
            None,
        )
        return {
            "required_tools": required_tools,
            "tool_executions": batch.results,
            "unresolved_tools": list(dict.fromkeys([*state.get("unresolved_tools", []), *batch.unresolved_tools])),
            "transfer_performed": transfer is not None and transfer.result.status == "succeeded",
            "state_path": ["HANDOFF_EXECUTED"],
        }

    async def _auto_reply_ready(self, state: WorkflowState) -> WorkflowState:
        """仅表示满足自动回复条件，不调用平台或创建消息。"""
        return {"terminal_state": WorkflowTerminalState.AUTO_REPLY_READY, "state_path": ["AUTO_REPLY_READY"]}

    async def _human_review(self, state: WorkflowState) -> WorkflowState:
        """中置信度草稿交由人工复核。"""
        return {"terminal_state": WorkflowTerminalState.HUMAN_REVIEW, "state_path": ["HUMAN_REVIEW"]}

    async def _transferred(self, state: WorkflowState) -> WorkflowState:
        """返回转人工终态，并区分是否已完成业务接管写入。"""
        return {"terminal_state": WorkflowTerminalState.TRANSFERRED, "state_path": ["TRANSFERRED"]}

    def _build_result(self, state: WorkflowState, latency_ms: int) -> AgentWorkflowResult:
        """把内部状态收敛为经 Pydantic 校验的稳定交接契约。"""
        inference = state["inference"]
        output = inference.output
        retrieval = state.get("retrieval")
        draft = state.get("draft")
        tool_draft = state.get("tool_draft")
        action = state["action"]
        referenced_ids = set(draft.citation_chunk_ids) if draft else set()
        citations = [
            AgentCitation(
                document_id=hit.document_id,
                chunk_id=hit.chunk_id,
                category_id=hit.category_id,
                document_version=hit.document_version,
                chunk_index=hit.chunk_index,
                score=hit.score,
                source_label=hit.source_label,
            )
            for hit in state.get("hits", [])
            if hit.chunk_id in referenced_ids
        ]
        can_expose_faq_draft = action in {AgentAction.AUTO_REPLY, AgentAction.HUMAN_REVIEW} and state.get(
            "safety_passed", False
        )
        can_expose_tool_draft = action in {AgentAction.AUTO_REPLY, AgentAction.HUMAN_REVIEW} and state.get(
            "tool_safety_passed", False
        )
        tool_calls = [
            AgentToolCallView(
                tool_call_id=item.result.tool_call_id,
                tool_name=item.tool_name,
                status=item.result.status,
                error_code=item.result.error_code,
                mocked=item.result.mocked,
                replayed=item.result.replayed,
            )
            for item in state.get("tool_executions", [])
        ]
        draft_reply: str | None = None
        if action == AgentAction.AUTO_REPLY:
            draft_reply = state.get("trusted_reply") or None
        elif draft is not None and can_expose_faq_draft:
            draft_reply = draft.answer
        elif tool_draft is not None and can_expose_tool_draft:
            draft_reply = tool_draft.answer
        return AgentWorkflowResult(
            agent_run_id=state["agent_run_id"],
            terminal_state=state["terminal_state"],
            intent=output.intent,
            classification_state=output.classification_state,
            citations=citations,
            draft_reply=draft_reply,
            required_tools=state.get("required_tools", []),
            tool_calls=tool_calls,
            intent_confidence=output.confidence,
            retrieval_score=retrieval.top_score if retrieval else 0.0,
            grounding_confidence=state.get("grounding_confidence", 0.0),
            final_confidence=state["final_confidence"],
            action=action,
            requires_human=action != AgentAction.AUTO_REPLY,
            transfer_performed=state.get("transfer_performed", False),
            send_performed=False,
            detected_language=state["detected_language"],
            reply_language=state["reply_language"],
            customer_translation=state.get("customer_translation"),
            safety_reason_codes=state.get("safety_reason_codes", []),
            provider=state["provider"],
            model=state["model"],
            embedding_provider=retrieval.embedding_provider if retrieval else None,
            embedding_model=retrieval.embedding_model if retrieval else None,
            reranker_provider=retrieval.reranker_provider if retrieval else None,
            reranker_model=retrieval.reranker_model if retrieval else None,
            reranker_revision=retrieval.reranker_revision if retrieval else None,
            retrieval_candidate_count=retrieval.candidate_count if retrieval else 0,
            prompt_versions={
                "workflow": WORKFLOW_PROMPT_VERSION,
                "intent": inference.prompt_version,
                "answer": FAQ_ANSWER_PROMPT_VERSION,
                "review": GROUNDING_REVIEW_PROMPT_VERSION,
                "tool_answer": TOOL_ANSWER_PROMPT_VERSION,
                "tool_review": TOOL_GROUNDING_REVIEW_PROMPT_VERSION,
                "translation": TRANSLATION_PROMPT_VERSION,
            },
            input_tokens=state["input_tokens"],
            output_tokens=state["output_tokens"],
            latency_ms=latency_ms,
            trace_id=state["command"].trace_id,
        )

    async def _record_failure(
        self,
        run_id: uuid.UUID,
        error_code: str,
        started_at: float,
        *,
        failure_stage: LLMFailureStage | None = None,
        output_failure_kind: LLMOutputFailureKind | None = None,
        output_schema_issues: tuple[LLMOutputSchemaIssue, ...] = (),
    ) -> None:
        """在独立提交中保存失败终态，外部异常不会抹去运行证据。"""
        timeout_codes = {
            LLMErrorCode.LLM_TIMEOUT.value,
            EmbeddingErrorCode.EMBEDDING_TIMEOUT.value,
            RerankingErrorCode.RERANK_TIMEOUT.value,
        }
        status = AgentRunStatus.TIMEOUT if error_code in timeout_codes else AgentRunStatus.FAILED
        await self.run_recorder.fail(
            run_id,
            status,
            AgentAction.FAILED,
            error_code,
            self.classifier.provider_name,
            self.classifier.model_name,
            max(0, int((time.perf_counter() - started_at) * 1000)),
            failure_stage=failure_stage,
            output_failure_kind=output_failure_kind,
            output_schema_issues=output_schema_issues,
        )
