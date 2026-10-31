"""按店铺读取全部已启用 Agent；缺少 V2 发布版本也显式返回。"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.core.reply_policy import AgentReplyProfile
from app.agents.management.config_models import AgentConfig
from app.agents.management.models import AgentConfigVersion
from app.agents.prompts.compiler import compile_prompt
from app.agents.prompts.sections import legacy_safe_sections
from app.shared.config.settings import get_settings


@dataclass(frozen=True, slots=True)
class PublishedAgent:
    id: uuid.UUID
    store_id: uuid.UUID
    config_version: int | None
    name: str
    code: str
    description: str | None
    agent_type: str
    model_provider: str | None
    model_name: str | None
    prompt_sections: Mapping[str, str]
    prompt_hash: str | None
    tool_names: tuple[str, ...]
    file_ids: tuple[str, ...]
    ready_for_v2: bool
    reply_profile: AgentReplyProfile | None = None


def _project(config: AgentConfig, version: AgentConfigVersion | None) -> PublishedAgent:
    scope = config.knowledge_scope
    raw_file_ids = scope.get("file_ids", [])
    file_ids = tuple(str(item) for item in raw_file_ids) if isinstance(raw_file_ids, list) else ()
    legacy = (
        version is not None
        and version.version == 1
        and not version.ready_for_v2
        and not version.prompt_sections
        and version.model_provider is None
        and version.model_name is None
    )
    compatibility_prompt = compile_prompt(legacy_safe_sections()) if legacy else None
    settings = get_settings() if legacy else None
    legacy_model = settings.llm_primary_model if settings is not None else None
    return PublishedAgent(
        id=config.id,
        store_id=config.store_id,
        config_version=version.version if version is not None else None,
        name=version.name if version is not None else config.name,
        code=version.code if version is not None else config.code,
        description=version.description if version is not None else config.description,
        agent_type=version.agent_type if version is not None else str(scope.get("agent_type", "service")),
        model_provider=(
            settings.llm_primary_provider if settings is not None else version.model_provider if version else None
        ),
        model_name=legacy_model if legacy else version.model_name if version is not None else None,
        prompt_sections=(
            compatibility_prompt.sections
            if compatibility_prompt is not None
            else MappingProxyType(dict(version.prompt_sections))
            if version is not None
            else MappingProxyType({})
        ),
        prompt_hash=(
            compatibility_prompt.content_sha256
            if compatibility_prompt is not None
            else version.prompt_hash
            if version
            else None
        ),
        tool_names=tuple(version.tool_names) if version is not None else tuple(config.enabled_tools),
        file_ids=tuple(version.file_ids) if version is not None else file_ids,
        ready_for_v2=(bool(legacy_model) if legacy else bool(version.ready_for_v2) if version else False),
        reply_profile=(
            AgentReplyProfile.model_validate(version.reply_profile)
            if version is not None and getattr(version, "reply_profile", None) is not None
            else None
        ),
    )


async def get_published_agent(
    session: AsyncSession, *, store_id: uuid.UUID, config_id: uuid.UUID
) -> PublishedAgent | None:
    """调试时可读取停用 Agent 的已发布版本，不会让它进入店铺路由。"""
    row = (
        await session.execute(
            select(AgentConfig, AgentConfigVersion)
            .outerjoin(
                AgentConfigVersion,
                and_(
                    AgentConfigVersion.agent_config_id == AgentConfig.id,
                    AgentConfigVersion.store_id == AgentConfig.store_id,
                    AgentConfigVersion.version == AgentConfig.published_version,
                ),
            )
            .where(
                AgentConfig.id == config_id,
                AgentConfig.store_id == store_id,
                AgentConfig.deleted_at.is_(None),
            )
        )
    ).first()
    return _project(*row) if row is not None else None


async def list_enabled_agents(session: AsyncSession, store_id: uuid.UUID) -> list[PublishedAgent]:
    """不按 Agent 类型或数量预筛；未发布配置留在候选集中供运行层失败关闭。"""
    statement = (
        select(AgentConfig, AgentConfigVersion)
        .outerjoin(
            AgentConfigVersion,
            and_(
                AgentConfigVersion.agent_config_id == AgentConfig.id,
                AgentConfigVersion.store_id == AgentConfig.store_id,
                AgentConfigVersion.version == AgentConfig.published_version,
            ),
        )
        .where(
            AgentConfig.store_id == store_id,
            AgentConfig.status == "enabled",
            AgentConfig.deleted_at.is_(None),
        )
        .order_by(AgentConfig.created_at, AgentConfig.id)
    )
    rows = (await session.execute(statement)).all()
    return [_project(config, version) for config, version in rows]
