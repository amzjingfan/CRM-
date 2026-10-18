"""定义 Agent 运行记录写入契约，隔离分类编排和 SQLAlchemy。"""

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal, Protocol, get_args

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.errors import (
    LLMFailureStage,
    LLMOutputFailureKind,
    LLMOutputSchemaErrorType,
    LLMOutputSchemaIssue,
    LLMOutputSchemaPath,
)
from app.agent.models import AgentRun
from app.agent.reply_policy import CustomerLanguage, SupportedLanguage
from app.agent.schemas import (
    AgentAction,
    AgentRunStatus,
    ClassificationState,
    IntentClassificationResult,
    IntentName,
)

AgentDecisionReason = Literal[
    "none",
    "classification_unresolved",
    "intent_confidence_low",
    "faq_knowledge_missing",
    "model_refusal",
    "faq_draft_needs_human",
    "faq_safety_rejected",
    "faq_review_unsafe",
    "faq_review_ungrounded",
    "faq_review_claims_inconsistent",
    "faq_review_missing",
    "faq_review_confidence_low",
    "faq_draft_confidence_low",
    "faq_retrieval_confidence_low",
    "tool_path",
    "unknown",
]
_SAFE_DECISION_REASONS = frozenset(get_args(AgentDecisionReason))


@dataclass(frozen=True, slots=True)
class AgentRunStart:
    """创建 Agent 运行记录所需的安全字段。"""

    store_id: uuid.UUID
    conversation_id: uuid.UUID
    trigger_message_id: uuid.UUID | None
    provider_name: str
    model_name: str
    prompt_version: str
    input_summary: str
    trace_id: str
    agent_config_id: uuid.UUID | None = None


class AgentRunRecorder(Protocol):
    """Agent 运行记录端口；实现只能写入 Agent 自有数据。"""

    async def start(self, values: AgentRunStart) -> uuid.UUID:
        """在外部调用前持久化 running 记录。"""
        ...

    async def succeed(self, run_id: uuid.UUID, result: IntentClassificationResult) -> None:
        """将运行记录更新为成功终态。"""
        ...

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
        output_failure_kind: LLMOutputFailureKind | None = None,
        output_schema_issues: tuple[LLMOutputSchemaIssue, ...] = (),
    ) -> None:
        """在独立事务中保存失败或超时终态。"""
        ...


@dataclass(frozen=True, slots=True)
class AgentWorkflowRunCompletion:
    """完整 FAQ 工作流写入 agent_runs 的安全终态。"""

    provider_name: str
    model_name: str
    prompt_version: str
    intent: IntentName | None
    classification_state: ClassificationState
    intent_confidence: float
    retrieval_score: float
    final_confidence: float
    action: AgentAction
    input_tokens: int
    output_tokens: int
    latency_ms: int
    state_path: list[str]
    citation_ids: list[uuid.UUID]
    required_tools: list[str]
    prompt_versions: dict[str, str]
    embedding_provider: str | None = None
    embedding_model: str | None = None
    reranker_provider: str | None = None
    reranker_model: str | None = None
    reranker_revision: str | None = None
    retrieval_candidate_count: int = 0
    tool_call_summaries: list[str] = field(default_factory=list)
    detected_language: CustomerLanguage = CustomerLanguage.UNKNOWN
    reply_language: SupportedLanguage = "zh-CN"
    translation_prompt_version: str | None = None
    translation_error_code: str | None = None
    safety_reason_codes: list[str] = field(default_factory=list)
    business_claim_summaries: list[str] = field(default_factory=list)
    decision_reason: AgentDecisionReason = "none"
    node_timings_ms: list[tuple[str, int]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class MarketingAgentRunCompletion:
    """营销文案生成的低敏终态，不保存评价正文或生成内容。"""

    event_id: uuid.UUID
    provider_name: str
    model_name: str
    prompt_version: str
    is_safe: bool
    requires_human: bool
    safety_reason_codes: list[str]
    input_tokens: int
    output_tokens: int
    latency_ms: int


class AgentWorkflowRunRecorder(Protocol):
    """完整工作流运行记录端口，与 Phase 1 分类记录保持兼容但相互独立。"""

    async def start(self, values: AgentRunStart) -> uuid.UUID:
        """在首次外部调用前提交 running 记录。"""
        ...

    async def complete_workflow(self, run_id: uuid.UUID, result: AgentWorkflowRunCompletion) -> None:
        """保存检索、置信度、节点路径和最终动作。"""
        ...

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
        output_failure_kind: LLMOutputFailureKind | None = None,
        output_schema_issues: tuple[LLMOutputSchemaIssue, ...] = (),
    ) -> None:
        """保存失败或超时终态。"""
        ...


class NullAgentRunRecorder:
    """评测专用记录器，明确不向业务数据库写入评测运行。"""

    async def start(self, values: AgentRunStart) -> uuid.UUID:
        """返回仅用于串联单次评测的随机运行 ID。"""
        return uuid.uuid4()

    async def succeed(self, run_id: uuid.UUID, result: IntentClassificationResult) -> None:
        """评测不持久化成功运行。"""

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
        output_failure_kind: LLMOutputFailureKind | None = None,
        output_schema_issues: tuple[LLMOutputSchemaIssue, ...] = (),
    ) -> None:
        """评测不持久化失败运行。"""

    async def complete_workflow(self, run_id: uuid.UUID, result: AgentWorkflowRunCompletion) -> None:
        """离线工作流评测不写业务数据库。"""


class SqlAlchemyAgentRunRecorder:
    """使用独立提交保存 Agent 运行，不触碰任何业务实体。"""

    def __init__(self, session: AsyncSession) -> None:
        """绑定当前请求或任务的异步数据库会话。"""
        self.session = session

    async def start(self, values: AgentRunStart) -> uuid.UUID:
        """在模型调用前提交 running 记录，防止超时抹去执行证据。"""
        run = AgentRun(
            id=uuid.uuid4(),
            agent_config_id=values.agent_config_id,
            store_id=values.store_id,
            conversation_id=values.conversation_id,
            trigger_message_id=values.trigger_message_id,
            model_provider=values.provider_name,
            model_name=values.model_name,
            prompt_version=values.prompt_version,
            action=AgentAction.HUMAN_REVIEW.value,
            status=AgentRunStatus.RUNNING.value,
            input_summary=values.input_summary,
            trace_id=values.trace_id,
        )
        self.session.add(run)
        await self.session.commit()
        return run.id

    async def complete_marketing(self, run_id: uuid.UUID, result: MarketingAgentRunCompletion) -> None:
        """保存营销 AI 终态，并用事件 ID 连接后续低敏工具调用链。"""
        run = await self._require_run(run_id)
        run.model_provider = result.provider_name
        run.model_name = result.model_name
        run.prompt_version = result.prompt_version
        run.action = (
            AgentAction.AUTO_REPLY.value
            if result.is_safe and not result.requires_human
            else AgentAction.HUMAN_REVIEW.value
        )
        run.status = AgentRunStatus.SUCCEEDED.value if result.is_safe else AgentRunStatus.FAILED.value
        run.error_code = None if result.is_safe else "AI_MARKETING_REVIEW_REQUIRED"
        run.input_tokens = result.input_tokens
        run.output_tokens = result.output_tokens
        run.latency_ms = result.latency_ms
        reasons = ",".join(result.safety_reason_codes) or "none"
        run.output_summary = (
            f"run_type=marketing;event_id={result.event_id};prompt={result.prompt_version};"
            f"is_safe={str(result.is_safe).lower()};requires_human={str(result.requires_human).lower()};"
            f"safety_reasons={reasons}"
        )
        await self.session.commit()

    async def succeed(self, run_id: uuid.UUID, result: IntentClassificationResult) -> None:
        """保存分类终态、Token 和耗时，不保存模型原始文本。"""
        run = await self._require_run(run_id)
        run.model_provider = result.provider
        run.model_name = result.model
        run.prompt_version = result.prompt_version
        run.intent = result.intent.value if result.intent else None
        run.intent_confidence = Decimal(str(result.confidence)).quantize(Decimal("0.0001"))
        run.action = result.action.value
        run.status = AgentRunStatus.SUCCEEDED.value
        run.output_summary = (
            f"classification_state={result.classification_state.value};"
            f"intent={result.intent.value if result.intent else 'none'}"
        )
        run.error_code = None
        run.latency_ms = result.latency_ms
        run.input_tokens = result.input_tokens
        run.output_tokens = result.output_tokens
        await self.session.commit()

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
        output_failure_kind: LLMOutputFailureKind | None = None,
        output_schema_issues: tuple[LLMOutputSchemaIssue, ...] = (),
    ) -> None:
        """保存模型失败终态，供重试任务和运维按稳定错误码定位。"""
        run = await self._require_run(run_id)
        run.model_provider = provider_name
        run.model_name = model_name
        run.status = status.value
        run.action = action.value
        run.error_code = error_code
        # 仅保存固定枚举；供应商原文、异常和未经校验的动态字段都不得入库。
        summary = f"error_code={error_code}"
        if error_code == "LLM_OUTPUT_INVALID":
            if isinstance(failure_stage, LLMFailureStage):
                summary += f";failure_stage={failure_stage.value}"
            if isinstance(output_failure_kind, str) and output_failure_kind in {
                "unfinished",
                "empty",
                "invalid_structure",
                "invalid_json",
                "invalid_schema",
            }:
                summary += f";output_failure_kind={output_failure_kind}"
                if output_failure_kind == "invalid_schema":
                    allowed_paths = set(get_args(LLMOutputSchemaPath))
                    allowed_types = set(get_args(LLMOutputSchemaErrorType))
                    safe_issues: list[str] = []
                    for issue in output_schema_issues:
                        if not isinstance(issue, tuple) or len(issue) != 2:
                            continue
                        path, error_type = issue
                        if (
                            isinstance(path, str)
                            and isinstance(error_type, str)
                            and path in allowed_paths
                            and error_type in allowed_types
                        ):
                            item = f"{path}:{error_type}"
                            if item not in safe_issues:
                                safe_issues.append(item)
                        if len(safe_issues) == 8:
                            break
                    if safe_issues:
                        summary += f";output_schema_issues={','.join(safe_issues)}"
        run.output_summary = summary
        run.latency_ms = latency_ms
        await self.session.commit()

    async def complete_workflow(self, run_id: uuid.UUID, result: AgentWorkflowRunCompletion) -> None:
        """保存完整工作流终态，但不保存消息、知识正文或模型原始输出。"""
        run = await self._require_run(run_id)
        run.model_provider = result.provider_name
        run.model_name = result.model_name
        run.prompt_version = result.prompt_version
        run.intent = result.intent.value if result.intent else None
        run.intent_confidence = Decimal(str(result.intent_confidence)).quantize(Decimal("0.0001"))
        run.retrieval_score = Decimal(str(result.retrieval_score)).quantize(Decimal("0.0001"))
        run.final_confidence = Decimal(str(result.final_confidence)).quantize(Decimal("0.0001"))
        run.action = result.action.value
        run.status = AgentRunStatus.SUCCEEDED.value
        run.error_code = None
        run.input_tokens = result.input_tokens
        run.output_tokens = result.output_tokens
        run.latency_ms = result.latency_ms
        citations = ",".join(str(citation_id) for citation_id in result.citation_ids) or "none"
        required_tools = ",".join(result.required_tools) or "none"
        tool_calls = ",".join(result.tool_call_summaries) or "none"
        prompt_versions = ",".join(f"{key}:{value}" for key, value in sorted(result.prompt_versions.items()))
        retrieval_models = (
            f"embedding={result.embedding_provider or 'none'}/{result.embedding_model or 'none'};"
            f"reranker={result.reranker_provider or 'none'}/{result.reranker_model or 'none'};"
            f"reranker_revision={result.reranker_revision or 'none'};"
            f"candidate_count={result.retrieval_candidate_count}"
        )
        safety_reasons = ",".join(result.safety_reason_codes) or "none"
        decision_reason = (
            result.decision_reason
            if isinstance(result.decision_reason, str) and result.decision_reason in _SAFE_DECISION_REASONS
            else "unknown"
        )
        business_claims = ",".join(result.business_claim_summaries) or "none"
        translation = (
            f"detected_language={result.detected_language.value};reply_language={result.reply_language};"
            f"translation_prompt={result.translation_prompt_version or 'none'};"
            f"translation_error={result.translation_error_code or 'none'}"
        )
        allowed_nodes = {
            "classification",
            "retrieval",
            "faq_draft",
            "safety_review",
            "translation",
            "retrieval_embedding_wait",
            "retrieval_search",
            "retrieval_search_acquire",
            "retrieval_search_query",
        }
        safe_timings: list[str] = []
        seen_nodes: set[str] = set()
        for item in result.node_timings_ms:
            if not isinstance(item, tuple) or len(item) != 2:
                continue
            name, elapsed_ms = item
            if (
                isinstance(name, str)
                and name in allowed_nodes
                and name not in seen_nodes
                and type(elapsed_ms) is int
                and elapsed_ms >= 0
            ):
                safe_timings.append(f"{name}:{elapsed_ms}")
                seen_nodes.add(name)
        run.output_summary = (
            f"classification_state={result.classification_state.value};"
            f"states={'>'.join(result.state_path)};citations={citations};"
            f"required_tools={required_tools};tool_calls={tool_calls};"
            f"business_claims={business_claims};prompts={prompt_versions};"
            f"safety_reasons={safety_reasons};"
            f"decision_reason={decision_reason};"
            f"{translation};{retrieval_models};node_timings_ms={','.join(safe_timings) or 'none'}"
        )
        await self.session.commit()

    async def _require_run(self, run_id: uuid.UUID) -> AgentRun:
        """加载 Agent 自有运行记录，不允许静默忽略链路损坏。"""
        run = await self.session.get(AgentRun, run_id)
        if run is None:
            raise RuntimeError("Agent 运行记录不存在")
        return run
