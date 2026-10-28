"""受信任管理入口调用的 Agent 版本发布事务。"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.management.config_models import AgentConfig
from app.agents.management.models import AgentConfigVersion
from app.agents.prompts.compiler import compile_prompt
from app.agents.providers.factory import validate_tool_model
from app.audit.models import AuditLog
from app.shared.config.settings import get_settings
from app.shared.exceptions.errors import AppError, ErrorCode


async def publish_agent(
    session: AsyncSession,
    *,
    store_id: uuid.UUID,
    config_id: uuid.UUID,
    expected_revision: int,
    publisher_id: uuid.UUID | None,
) -> AgentConfigVersion:
    """校验七段草稿并原子冻结版本；调用方先核验店铺权限。"""
    config = await session.scalar(
        select(AgentConfig)
        .where(
            AgentConfig.id == config_id,
            AgentConfig.store_id == store_id,
            AgentConfig.deleted_at.is_(None),
        )
        .with_for_update()
    )
    if config is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Agent 配置不存在", 404)
    if config.draft_revision != expected_revision:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "Agent 配置已更新，请刷新后重试", 409)
    settings = get_settings()
    try:
        validate_tool_model(settings, config.draft_model_provider, config.draft_model_name)
    except ValueError as error:
        raise AppError(ErrorCode.VALIDATION_ERROR, "模型不在当前项目原生工具配置中", 422) from error
    compiled = compile_prompt(config.draft_prompt_sections)

    scope = config.knowledge_scope if isinstance(config.knowledge_scope, dict) else {}
    raw_file_ids = scope.get("file_ids", [])
    file_ids = [str(item) for item in raw_file_ids] if isinstance(raw_file_ids, list) else []
    next_version = (config.published_version or 0) + 1
    version = AgentConfigVersion(
        store_id=store_id,
        agent_config_id=config.id,
        version=next_version,
        name=config.name,
        code=config.code,
        description=config.description,
        agent_type=str(scope.get("agent_type", "service")),
        model_provider=config.draft_model_provider,
        model_name=config.draft_model_name,
        prompt_sections=dict(compiled.sections),
        prompt_hash=compiled.content_sha256,
        tool_names=list(config.enabled_tools),
        file_ids=file_ids,
        ready_for_v2=True,
        published_by=publisher_id,
    )
    session.add(version)
    session.add(
        AuditLog(
            store_id=store_id,
            actor_type="user" if publisher_id is not None else "system",
            actor_id=publisher_id,
            action="agent.config.publish",
            resource_type="agent_config",
            resource_id=config.id,
            after_data={"version": next_version, "prompt_hash": compiled.content_sha256},
            result="succeeded",
        )
    )
    config.published_version = next_version
    config.draft_revision += 1
    await session.commit()
    await session.refresh(version)
    return version
