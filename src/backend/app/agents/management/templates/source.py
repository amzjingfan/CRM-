"""草稿来源按实际字段投影，运行来源只读历史快照。"""

import uuid
from typing import cast

from pydantic import JsonValue, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.management.config_models import AgentConfig
from app.agents.management.config_service import config_view, get_config
from app.agents.management.models import AgentConfigVersion
from app.agents.management.schemas import AgentConfigView
from app.agents.management.service import template_source as project_template_source
from app.agents.management.templates.diff import FIELD_KEYS, config_fields
from app.agents.management.templates.models import AgentTemplate, AgentTemplateVersion
from app.agents.management.templates.preview import actual_fields
from app.agents.management.templates.schemas import TemplateConfig
from app.agents.management.templates.selection_schemas import (
    AgentTemplateSourceView,
    DraftTemplateSource,
    PublishedTemplateSource,
    TemplateFieldSource,
)
from app.agents.management.templates.service import config_hash, field_needs_review
from app.audit.models import AuditLog
from app.auth.store_access import allowed_store_ids_for_permission
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import Store


async def _authorized_config(
    session: AsyncSession, user: User, agent_id: uuid.UUID, permission: str, *, lock: bool = False
) -> AgentConfig:
    statement = (
        select(AgentConfig)
        .join(Store, Store.id == AgentConfig.store_id)
        .where(
            AgentConfig.id == agent_id,
            AgentConfig.deleted_at.is_(None),
            AgentConfig.store_id.in_(await allowed_store_ids_for_permission(session, user, permission)),
            Store.status == "active",
            Store.deleted_at.is_(None),
        )
        .execution_options(populate_existing=True)
    )
    if lock:
        statement = statement.with_for_update(of=AgentConfig)
    config = await session.scalar(statement)
    if config is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "资源不存在或无权访问", 404)
    # 等锁期间用户/店铺可被停用或撤权；新SQL不能沿用认证对象缓存，也不新增行锁。
    current_store = await session.scalar(
        select(Store.id).where(
            Store.id == config.store_id,
            Store.status == "active",
            Store.deleted_at.is_(None),
            select(User.id).where(User.id == user.id, User.status == "active").exists(),
        )
    )
    if current_store is None or config.store_id not in await allowed_store_ids_for_permission(
        session, user, permission
    ):
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "资源不存在或无权访问", 404)
    return config


async def template_source(session: AsyncSession, user: User, agent_id: uuid.UUID) -> AgentTemplateSourceView:
    config = await _authorized_config(session, user, agent_id, "agent.view")
    published = None
    if config.published_version is not None:
        version = await session.scalar(
            select(AgentConfigVersion).where(
                AgentConfigVersion.agent_config_id == config.id,
                AgentConfigVersion.store_id == config.store_id,
                AgentConfigVersion.version == config.published_version,
            )
        )
        if version is None:
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "Agent 发布快照缺失", 409)
        published = PublishedTemplateSource(
            version=version.version,
            template_source_json=cast(dict[str, JsonValue] | None, version.template_source_json),
        )
    draft = None
    if config.template_id is not None:
        template = await session.get(AgentTemplate, config.template_id)
        if template is None or template.published_version is None:
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "关联模板已发布来源缺失", 409)
        rows = (
            await session.scalars(
                select(AgentTemplateVersion).where(
                    AgentTemplateVersion.template_id == template.id,
                    AgentTemplateVersion.version <= template.published_version,
                )
            )
        ).all()
        history = {}
        for row in rows:
            try:
                value = TemplateConfig.model_validate(row.config_json)
            except ValidationError:
                continue
            if config_hash(value) == row.content_sha256:
                history[row.version] = config_fields(value)
        target = history.get(template.published_version)
        if target is None:
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "模板已发布版本无效", 409)
        actual = actual_fields(config)
        state = config.template_state_json or {}
        states = state.get("fields") if state.get("schema_version") == 1 else None
        projected = project_template_source(config) or {}
        projected_fields = cast(dict[str, dict[str, object]], projected.get("fields", {}))
        fields = []
        for key in FIELD_KEYS:
            field = states.get(key) if isinstance(states, dict) else None
            aligned = actual[key] == target[key]
            field_state = field if isinstance(field, dict) else {}
            valid = "baseline_value" in field_state
            fields.append(
                TemplateFieldSource(
                    field=key,
                    aligned=aligned,
                    local_override=bool(projected_fields.get(key, {}).get("local_override")),
                    applied_template_version=field_state.get("applied_template_version") if valid else None,
                    last_reviewed_template_version=field_state.get("last_reviewed_template_version") if valid else None,
                    pending_review=field_needs_review(field, key, target[key], template.published_version, history),
                )
            )
        draft = DraftTemplateSource(
            template_id=template.id,
            name=template.name,
            archived=template.archived_at is not None,
            target_template_version=template.published_version,
            draft_revision=config.draft_revision,
            fields=fields,
            aligned_count=sum(f.aligned for f in fields),
            local_override_count=sum(f.local_override for f in fields),
            pending_review_count=sum(f.pending_review for f in fields),
        )
    return AgentTemplateSourceView(agent_id=config.id, store_id=config.store_id, draft=draft, published=published)


async def detach_template(
    session: AsyncSession, user: User, agent_id: uuid.UUID, expected_revision: int
) -> AgentConfigView:
    config = await _authorized_config(session, user, agent_id, "agent.manage", lock=True)
    if config.draft_revision != expected_revision:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "Agent 配置已更新，请刷新后重试", 409)
    if config.template_id is not None:
        old_template = config.template_id
        config.template_id, config.template_state_json = None, None
        config.draft_revision += 1
        session.add(
            AuditLog(
                store_id=config.store_id,
                actor_type="user",
                actor_id=user.id,
                action="agent.template.detach",
                resource_type="agent_config",
                resource_id=config.id,
                before_data={"template_id": str(old_template), "draft_revision": expected_revision},
                after_data={"template_id": None, "draft_revision": config.draft_revision},
                result="succeeded",
            )
        )
        await session.commit()
        await session.refresh(config)
    return config_view(await get_config(session, user, agent_id, permission_code="agent.manage"))
