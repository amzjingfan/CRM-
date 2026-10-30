"""Agent 运营管理业务规则。"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Literal, cast

from sqlalchemy import select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.core.reply_policy import resolve_store_reply_profile
from app.agents.management.config_models import AgentConfig
from app.agents.management.config_repository import find_config, list_configs, list_run_logs
from app.agents.management.models import AgentConfigVersion
from app.agents.management.repository import get_published_agent
from app.agents.management.schemas import (
    AgentConfigCreate,
    AgentConfigUpdate,
    AgentConfigView,
    AgentRunLogPage,
    AgentRunLogView,
    AgentRuntimeView,
    ToolCallLogView,
)
from app.agents.prompts.compiler import PLATFORM_POLICY_VERSION
from app.agents.safety.grounding import GROUNDING_PROMPT_VERSION
from app.audit.models import AuditLog
from app.auth.store_access import allowed_store_ids
from app.knowledge_base.document_models import KnowledgeFile
from app.shared.config.settings import get_settings
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError, ErrorCode


def runtime_view() -> AgentRuntimeView:
    settings = get_settings()
    return AgentRuntimeView(
        available=(
            (settings.agent_v2_debug_enabled and settings.agent_debug_enabled)
            or (settings.agent_v2_formal_enabled and settings.llm_enabled)
        )
        and bool(settings.llm_primary_model),
        llm_provider=settings.llm_primary_provider,
        llm_model=settings.llm_primary_model,
        available_models=list(
            dict.fromkeys(model for model in (settings.llm_primary_model, settings.llm_fallback_model) if model)
        ),
        model_options=[
            {"provider": provider, "model_name": model}
            for provider, model in (
                (settings.llm_primary_provider, settings.llm_primary_model),
                (settings.llm_fallback_provider, settings.llm_fallback_model),
            )
            if provider and model
        ],
        embedding_provider=settings.embedding_provider,
        embedding_model=settings.embedding_model,
        reranker_model="BAAI/bge-reranker-large",
        prompt_versions={
            "platform_policy": PLATFORM_POLICY_VERSION,
            "dynamic_router": "v2",
            "evidence_review": GROUNDING_PROMPT_VERSION,
        },
        auto_reply_threshold=settings.agent_auto_reply_threshold,
        human_review_threshold=settings.agent_human_review_threshold,
    )


def config_view(config: AgentConfig) -> AgentConfigView:
    scope = dict(config.knowledge_scope)
    if scope.get("mode") == "store_ready_faq":
        scope["mode"] = "bound_files_only"
    return AgentConfigView(
        id=config.id,
        store_id=config.store_id,
        name=config.name,
        code=config.code,
        description=config.description,
        agent_type=config.knowledge_scope.get("agent_type", "service"),  # type: ignore[arg-type]
        status=config.status,  # type: ignore[arg-type]
        draft_revision=getattr(config, "draft_revision", 1),
        published_version=getattr(config, "published_version", None),
        template_id=getattr(config, "template_id", None),
        template_state_json=getattr(config, "template_state_json", None),
        published_template_source_json=getattr(config, "_published_template_source_json", None),
        model_provider=getattr(config, "draft_model_provider", None),
        model_name=getattr(config, "draft_model_name", None),
        prompt_sections=dict(getattr(config, "draft_prompt_sections", {})),
        enabled_tools=list(config.enabled_tools),
        knowledge_file_ids=[
            uuid.UUID(str(item)) for item in cast(list[object], config.knowledge_scope.get("file_ids", []))
        ],
        knowledge_scope=scope,
        reply_profile=resolve_store_reply_profile(config.knowledge_scope),
        runtime=runtime_view(),
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


async def get_configs(session: AsyncSession, user: User) -> list[AgentConfigView]:
    rows = await list_configs(session, await allowed_store_ids(session, user, "agent.view"))
    await _load_published_sources(session, rows)
    return [config_view(item) for item in rows]


async def _load_published_sources(session: AsyncSession, configs: Sequence[AgentConfig]) -> None:
    keys = [
        (config.id, config.store_id, config.published_version)
        for config in configs
        if config.published_version is not None
    ]
    sources = {}
    if keys:
        rows = (
            await session.execute(
                select(
                    AgentConfigVersion.agent_config_id,
                    AgentConfigVersion.store_id,
                    AgentConfigVersion.version,
                    AgentConfigVersion.template_source_json,
                ).where(
                    tuple_(
                        AgentConfigVersion.agent_config_id, AgentConfigVersion.store_id, AgentConfigVersion.version
                    ).in_(keys)
                )
            )
        ).all()
        sources = {(row.agent_config_id, row.store_id, row.version): row.template_source_json for row in rows}
    # 草稿关联与运行来源独立；解除关联也不能抹掉仍在运行的旧版本来源。
    for config in configs:
        config.__dict__["_published_template_source_json"] = sources.get(
            (config.id, config.store_id, config.published_version)
        )


async def get_config(
    session: AsyncSession,
    user: User,
    config_id: uuid.UUID,
    *,
    permission_code: Literal["agent.view", "agent.manage"] = "agent.view",
) -> AgentConfig:
    # 部门会话范围不是 Agent 授权；写入调用者必须明确要求目标店的管理权限。
    item = await find_config(session, config_id, await allowed_store_ids(session, user, permission_code))
    if item is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Agent 配置不存在", 404)
    await _load_published_sources(session, [item])
    return item


async def validate_knowledge_file_ids(
    session: AsyncSession, store_id: uuid.UUID, file_ids: list[uuid.UUID]
) -> list[uuid.UUID]:
    """文件绑定只接受当前店铺仍可用的导入文件，不能用客户端 ID 扩大范围。"""
    unique_ids = list(dict.fromkeys(file_ids))
    if not unique_ids:
        return []
    found = (
        await session.scalars(
            select(KnowledgeFile.id).where(
                KnowledgeFile.id.in_(unique_ids),
                KnowledgeFile.store_id == store_id,
                KnowledgeFile.archived_at.is_(None),
                KnowledgeFile.deleted_at.is_(None),
            )
        )
    ).all()
    if set(found) != set(unique_ids):
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "所选知识文件不存在或不可绑定", 404)
    return unique_ids


def require_knowledge_view_for_binding(user: User, file_ids: list[uuid.UUID]) -> None:
    """Agent 配置权限不能提升为知识文件读取或绑定权限。"""
    if not file_ids:
        return
    if "admin" in {role.code for role in user.roles}:
        return
    if "knowledge.view" not in {permission.code for role in user.roles for permission in role.permissions}:
        raise AppError(ErrorCode.PERMISSION_DENIED, "没有绑定知识文件的权限", 403)


async def create_config(
    session: AsyncSession,
    user: User,
    payload: AgentConfigCreate,
) -> AgentConfigView:
    if payload.store_id not in await allowed_store_ids(session, user, "agent.manage"):
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "资源不存在", 404)
    require_knowledge_view_for_binding(user, payload.knowledge_file_ids)
    file_ids = await validate_knowledge_file_ids(session, payload.store_id, payload.knowledge_file_ids)
    config = AgentConfig(
        store_id=payload.store_id,
        name=payload.name,
        code=payload.code,
        description=payload.description,
        enabled_tools=list(dict.fromkeys(payload.enabled_tools)),
        draft_model_provider=payload.model_provider,
        draft_model_name=payload.model_name,
        draft_prompt_sections=dict(payload.prompt_sections),
        knowledge_scope={
            "mode": payload.knowledge_scope,
            "agent_type": payload.agent_type,
            "file_ids": [str(item) for item in file_ids],
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
    config = await get_config(session, user, config_id, permission_code="agent.manage")
    # 授权读取后重新加锁并刷新 revision，避免两个旧草稿同时通过 Python 比较。
    await session.refresh(config, with_for_update=True)
    if getattr(config, "deleted_at", None) is not None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Agent 不存在", 404)
    before = {
        "name": config.name,
        "enabled_tools": list(config.enabled_tools),
        "agent_type": config.knowledge_scope.get("agent_type", "service"),
        "file_ids": config.knowledge_scope.get("file_ids", []),
        "reply_profile": resolve_store_reply_profile(config.knowledge_scope).model_dump(mode="json"),
    }
    changes = payload.model_dump(exclude_unset=True)
    expected_revision = changes.pop("expected_revision", None)
    if expected_revision is not None and expected_revision != getattr(config, "draft_revision", 1):
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "Agent 配置已更新，请刷新后重试", 409)
    if "enabled_tools" in changes:
        changes["enabled_tools"] = list(dict.fromkeys(changes["enabled_tools"]))
    if "model_provider" in changes:
        config.draft_model_provider = changes.pop("model_provider")
    if "model_name" in changes:
        config.draft_model_name = changes.pop("model_name")
    if "prompt_sections" in changes:
        prompt_sections = changes.pop("prompt_sections")
        config.draft_prompt_sections = dict(prompt_sections or {})
    previous_scope = dict(config.knowledge_scope)
    scope = dict(previous_scope)
    if scope.get("mode") == "store_ready_faq":
        scope["mode"] = "bound_files_only"
    if "knowledge_scope" in changes:
        scope["mode"] = changes.pop("knowledge_scope")
    if "reply_profile" in changes:
        reply_profile = changes.pop("reply_profile")
        if reply_profile is None:
            scope.pop("reply_profile", None)
        else:
            scope["reply_profile"] = reply_profile
    if "agent_type" in changes:
        agent_type = changes.pop("agent_type")
        if agent_type is None:
            raise AppError(ErrorCode.VALIDATION_ERROR, "Agent 类型不能为空", 422)
        scope["agent_type"] = agent_type
    if "knowledge_file_ids" in changes:
        requested_ids = changes.pop("knowledge_file_ids")
        existing_ids = scope.get("file_ids", [])
        if not isinstance(existing_ids, list):
            raise AppError(ErrorCode.VALIDATION_ERROR, "Agent 知识文件配置无效", 422)
        if {str(item) for item in requested_ids or []} != {str(item) for item in existing_ids}:
            require_knowledge_view_for_binding(user, requested_ids or [])
        file_ids = await validate_knowledge_file_ids(session, config.store_id, requested_ids or [])
        scope["file_ids"] = [str(item) for item in file_ids]
    config.knowledge_scope = scope
    for field, value in changes.items():
        setattr(config, field, value)
    if (
        changes
        or scope != previous_scope
        or any(field in payload.model_fields_set for field in ("model_provider", "model_name", "prompt_sections"))
    ):
        config.draft_revision = getattr(config, "draft_revision", 1) + 1
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
                "agent_type": scope.get("agent_type", "service"),
                "file_ids": scope.get("file_ids", []),
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
    config = await get_config(session, user, config_id, permission_code="agent.manage")
    if status == "enabled":
        version = await get_published_agent(session, store_id=config.store_id, config_id=config.id)
        if version is None or not version.ready_for_v2:
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "请先发布完整的 Agent 配置", 409)
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
    config = await get_config(session, user, config_id, permission_code="agent.manage")
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
            parent_run_id=run.parent_run_id,
            config_version=run.config_version,
            phase=run.phase,
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
