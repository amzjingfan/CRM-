"""Agent 运营管理业务规则。"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.reply_policy import resolve_store_reply_profile
from app.agent.workflow_prompt import (
    FAQ_ANSWER_PROMPT_VERSION,
    GROUNDING_REVIEW_PROMPT_VERSION,
    TOOL_ANSWER_PROMPT_VERSION,
    TOOL_GROUNDING_REVIEW_PROMPT_VERSION,
    WORKFLOW_PROMPT_VERSION,
)
from app.agent_management.models import AgentConfig
from app.agent_management.repository import find_config, list_configs, list_run_logs
from app.agent_management.schemas import (
    AgentConfigCreate,
    AgentConfigUpdate,
    AgentConfigView,
    AgentRunLogPage,
    AgentRunLogView,
    AgentRuntimeView,
    ToolCallLogView,
)
from app.audit.models import AuditLog
from app.auth.store_access import allowed_store_ids, ensure_store_access
from app.shared.config.settings import get_settings
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError, ErrorCode


def runtime_view() -> AgentRuntimeView:
    settings = get_settings()
    return AgentRuntimeView(
        available=settings.llm_enabled and settings.embedding_enabled,
        llm_provider=settings.llm_primary_provider,
        llm_model=settings.llm_primary_model,
        embedding_provider=settings.embedding_provider,
        embedding_model=settings.embedding_model,
        reranker_model="BAAI/bge-reranker-large",
        prompt_versions={
            "workflow": WORKFLOW_PROMPT_VERSION,
            "answer": FAQ_ANSWER_PROMPT_VERSION,
            "review": GROUNDING_REVIEW_PROMPT_VERSION,
            "tool_answer": TOOL_ANSWER_PROMPT_VERSION,
            "tool_review": TOOL_GROUNDING_REVIEW_PROMPT_VERSION,
        },
        auto_reply_threshold=settings.agent_auto_reply_threshold,
        human_review_threshold=settings.agent_human_review_threshold,
    )


def config_view(config: AgentConfig) -> AgentConfigView:
    return AgentConfigView(
        id=config.id,
        store_id=config.store_id,
        name=config.name,
        code=config.code,
        description=config.description,
        status=config.status,  # type: ignore[arg-type]
        enabled_tools=list(config.enabled_tools),
        knowledge_scope=dict(config.knowledge_scope),
        reply_profile=resolve_store_reply_profile(config.knowledge_scope),
        runtime=runtime_view(),
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


async def get_configs(session: AsyncSession, user: User) -> list[AgentConfigView]:
    rows = await list_configs(session, await allowed_store_ids(session, user))
    return [config_view(item) for item in rows]


async def get_config(session: AsyncSession, user: User, config_id: uuid.UUID) -> AgentConfig:
    item = await find_config(session, config_id, await allowed_store_ids(session, user))
    if item is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Agent 配置不存在", 404)
    return item


async def create_config(
    session: AsyncSession,
    user: User,
    payload: AgentConfigCreate,
) -> AgentConfigView:
    await ensure_store_access(session, user, payload.store_id)
    config = AgentConfig(
        store_id=payload.store_id,
        name=payload.name,
        code=payload.code,
        description=payload.description,
        enabled_tools=list(dict.fromkeys(payload.enabled_tools)),
        knowledge_scope={
            "mode": payload.knowledge_scope,
            **(
                {"reply_profile": payload.reply_profile.model_dump(mode="json")}
                if payload.reply_profile is not None
                else {}
            ),
        },
        created_by=user.id,
    )
    session.add(config)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "Agent 配置编码已存在", 409) from exc
    session.add(
        AuditLog(
            store_id=config.store_id,
            actor_type="user",
            actor_id=user.id,
            action="agent.config.create",
            resource_type="agent_config",
            resource_id=config.id,
            after_data={"code": config.code, "status": config.status},
            result="succeeded",
        )
    )
    await session.commit()
    await session.refresh(config)
    return config_view(config)


async def update_config(
    session: AsyncSession,
    user: User,
    config_id: uuid.UUID,
    payload: AgentConfigUpdate,
) -> AgentConfigView:
    config = await get_config(session, user, config_id)
    before = {
        "name": config.name,
        "enabled_tools": list(config.enabled_tools),
        "reply_profile": resolve_store_reply_profile(config.knowledge_scope).model_dump(mode="json"),
    }
    changes = payload.model_dump(exclude_unset=True)
    if "enabled_tools" in changes:
        changes["enabled_tools"] = list(dict.fromkeys(changes["enabled_tools"]))
    scope = dict(config.knowledge_scope)
    if "knowledge_scope" in changes:
        scope["mode"] = changes.pop("knowledge_scope")
    if "reply_profile" in changes:
        reply_profile = changes.pop("reply_profile")
        if reply_profile is None:
            scope.pop("reply_profile", None)
        else:
            scope["reply_profile"] = reply_profile
    config.knowledge_scope = scope
    for field, value in changes.items():
        setattr(config, field, value)
    session.add(
        AuditLog(
            store_id=config.store_id,
            actor_type="user",
            actor_id=user.id,
            action="agent.config.update",
            resource_type="agent_config",
            resource_id=config.id,
            before_data=before,
            after_data={
                "name": config.name,
                "enabled_tools": list(config.enabled_tools),
                "reply_profile": resolve_store_reply_profile(config.knowledge_scope).model_dump(mode="json"),
            },
            result="succeeded",
        )
    )
    await session.commit()
    await session.refresh(config)
    return config_view(config)


async def set_config_status(
    session: AsyncSession,
    user: User,
    config_id: uuid.UUID,
    status: str,
) -> AgentConfigView:
    config = await get_config(session, user, config_id)
    before = config.status
    config.status = status
    session.add(
        AuditLog(
            store_id=config.store_id,
            actor_type="user",
            actor_id=user.id,
            action=f"agent.config.{status}",
            resource_type="agent_config",
            resource_id=config.id,
            before_data={"status": before},
            after_data={"status": status},
            result="succeeded",
        )
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "该店铺已有启用的 Agent 配置", 409) from exc
    await session.refresh(config)
    return config_view(config)


async def delete_config(session: AsyncSession, user: User, config_id: uuid.UUID) -> None:
    config = await get_config(session, user, config_id)
    if config.status == "enabled":
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "请先停用 Agent 配置", 409)
    config.deleted_at = datetime.now(UTC)
    session.add(
        AuditLog(
            store_id=config.store_id,
            actor_type="user",
            actor_id=user.id,
            action="agent.config.delete",
            resource_type="agent_config",
            resource_id=config.id,
            before_data={"code": config.code},
            result="succeeded",
        )
    )
    await session.commit()


async def get_logs(
    session: AsyncSession,
    user: User,
    config_id: uuid.UUID,
    page: int,
    page_size: int,
    start: datetime | None,
    end: datetime | None,
) -> AgentRunLogPage:
    config = await get_config(session, user, config_id)
    rows, total = await list_run_logs(session, config, page, page_size, start, end)
    items = [
        AgentRunLogView(
            id=run.id,
            conversation_id=run.conversation_id,
            status=run.status,
            action=run.action,
            intent=run.intent,
            intent_confidence=float(run.intent_confidence) if run.intent_confidence is not None else None,
            retrieval_score=float(run.retrieval_score) if run.retrieval_score is not None else None,
            final_confidence=float(run.final_confidence) if run.final_confidence is not None else None,
            model_provider=run.model_provider,
            model_name=run.model_name,
            prompt_version=run.prompt_version,
            latency_ms=run.latency_ms,
            input_tokens=run.input_tokens,
            output_tokens=run.output_tokens,
            error_code=run.error_code,
            trace_id=run.trace_id,
            legacy_unassigned=run.agent_config_id is None,
            tool_calls=[
                ToolCallLogView(
                    id=call.id,
                    tool_name=call.tool_name,
                    status=call.status,
                    error_code=call.error_code,
                    latency_ms=call.latency_ms,
                    mocked=call.mocked,
                )
                for call in calls
            ],
            created_at=run.created_at,
        )
        for run, calls in rows
    ]
    return AgentRunLogPage(items=items, page=page, page_size=page_size, total=total)
