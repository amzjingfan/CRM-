"""共享模板草稿与不可变版本；发布不修改任何店铺 Agent。"""

import hashlib
import json
import uuid
from datetime import UTC, datetime

from pydantic import JsonValue, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.management.config_models import AgentConfig
from app.agents.management.config_service import runtime_view
from app.agents.management.models import AgentConfigVersion
from app.agents.management.templates.diff import config_fields
from app.agents.management.templates.lifecycle_schemas import (
    TemplateCatalogTool,
    TemplateCatalogView,
    TemplateCreate,
    TemplateFromAgent,
    TemplateListView,
    TemplatePromptSection,
    TemplateUpdate,
    TemplateVersionView,
    TemplateView,
)
from app.agents.management.templates.models import AgentTemplate, AgentTemplateVersion
from app.agents.management.templates.schemas import TemplateConfig
from app.agents.prompts.compiler import compile_prompt
from app.agents.prompts.review import review_configured_prompt
from app.agents.prompts.sections import SECTION_TITLES
from app.agents.providers.factory import NATIVE_TOOL_PROVIDERS, validate_tool_model
from app.agents.tools.metadata import GROUPS, TOOL_METADATA
from app.audit.models import AuditLog
from app.auth.store_access import allowed_store_ids
from app.shared.config.settings import get_settings
from app.shared.database.base import Role, User, user_roles
from app.shared.exceptions.errors import AppError, ErrorCode


def config_hash(config: TemplateConfig) -> str:
    return hashlib.sha256(
        json.dumps(config.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


async def can_manage_templates(session: AsyncSession, user: User) -> bool:
    """共享模板只认同一数据库授权行的系统管理员，不信前端角色并集。"""
    return (
        await session.scalar(
            select(user_roles.c.id)
            .join(Role, Role.id == user_roles.c.role_id)
            .join(User, User.id == user_roles.c.user_id)
            .where(
                User.id == user.id,
                User.status == "active",
                user_roles.c.store_id.is_(None),
                Role.code == "admin",
            )
            .limit(1)
        )
        is not None
    )


async def require_template_manager(session: AsyncSession, user: User) -> None:
    if not await can_manage_templates(session, user):
        raise AppError(ErrorCode.PERMISSION_DENIED, "只有系统级管理员可以维护共享模板", 403)


async def _template(session: AsyncSession, template_id: uuid.UUID, *, lock: bool = False) -> AgentTemplate:
    statement = select(AgentTemplate).where(AgentTemplate.id == template_id).execution_options(populate_existing=True)
    if lock:
        statement = statement.with_for_update()
    row = await session.scalar(statement)
    if row is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "模板不存在", 404)
    return row


def _revision(row: AgentTemplate, expected_revision: int) -> None:
    if row.draft_revision != expected_revision:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "模板已更新，请刷新后重试", 409)


async def _readable(session: AsyncSession, user: User, template_id: uuid.UUID) -> tuple[AgentTemplate, bool]:
    manager = await can_manage_templates(session, user)
    row = await _template(session, template_id)
    if not manager and (row.published_version is None or row.archived_at is not None):
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "模板不存在", 404)
    return row, manager


def field_needs_review(
    field: object, key: str, value: JsonValue, version: int, history: dict[int, dict[str, JsonValue]]
) -> bool:
    """保留本店覆盖的明确审阅不反复提示，只看已审阅版本的字段是否变化。"""
    if not isinstance(field, dict) or "baseline_value" not in field:
        return True
    reviewed = field.get("last_reviewed_template_version")
    if (
        not isinstance(reviewed, int)
        or isinstance(reviewed, bool)
        or not 1 <= reviewed <= version
        or not isinstance(field.get("local_override"), bool)
    ):
        return True
    reviewed_fields = history.get(reviewed)
    return reviewed_fields is None or reviewed_fields[key] != value


def _needs_review(
    config: AgentConfig, target: TemplateConfig, version: int, history: dict[int, dict[str, JsonValue]]
) -> bool:
    state = config.template_state_json
    if not isinstance(state, dict) or state.get("schema_version") != 1:
        return True
    fields = state.get("fields")
    if not isinstance(fields, dict):
        return True
    for key, value in config_fields(target).items():
        field = fields.get(key)
        if field_needs_review(field, key, value, version, history):
            return True
    return False


async def template_view(session: AsyncSession, user: User, row: AgentTemplate, manager: bool) -> TemplateView:
    versions = (
        await session.scalars(select(AgentTemplateVersion).where(AgentTemplateVersion.template_id == row.id))
    ).all()
    configs: dict[int, TemplateConfig] = {}
    for item in versions:
        try:
            config = TemplateConfig.model_validate(item.config_json)
        except ValidationError:
            continue
        if config_hash(config) == item.content_sha256:
            configs[item.version] = config
    if row.published_version is not None and row.published_version not in configs:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "模板已发布版本无效，请联系管理员核查", 409)
    history = {number: config_fields(config) for number, config in configs.items()}
    published = configs.get(row.published_version) if row.published_version is not None else None
    statement = select(AgentConfig).where(AgentConfig.template_id == row.id, AgentConfig.deleted_at.is_(None))
    if not manager:
        statement = statement.where(AgentConfig.store_id.in_(await allowed_store_ids(session, user, "agent.view")))
    linked = (await session.scalars(statement)).all()
    return TemplateView(
        id=row.id,
        code=row.code,
        name=row.name,
        description=row.description,
        draft_revision=row.draft_revision if manager else None,
        published_version=row.published_version,
        archived_at=row.archived_at,
        config=TemplateConfig.model_validate(row.draft_config_json) if manager else published,
        published_config=published,
        can_manage=manager,
        linked_store_count=len({item.store_id for item in linked}),
        update_count=sum(_needs_review(item, published, row.published_version, history) for item in linked)
        if published is not None and row.published_version is not None
        else 0,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def list_templates(session: AsyncSession, user: User, *, include_archived: bool = False) -> TemplateListView:
    manager = await can_manage_templates(session, user)
    statement = select(AgentTemplate).order_by(AgentTemplate.created_at, AgentTemplate.id)
    if not manager:
        statement = statement.where(AgentTemplate.published_version.is_not(None), AgentTemplate.archived_at.is_(None))
    elif not include_archived:
        statement = statement.where(AgentTemplate.archived_at.is_(None))
    rows = (await session.scalars(statement)).all()
    return TemplateListView(
        items=[await template_view(session, user, row, manager) for row in rows], can_manage=manager
    )


async def get_template(session: AsyncSession, user: User, template_id: uuid.UUID) -> TemplateView:
    row, manager = await _readable(session, user, template_id)
    return await template_view(session, user, row, manager)


def _audit(session: AsyncSession, user_id: uuid.UUID, row: AgentTemplate, action: str) -> None:
    session.add(
        AuditLog(
            actor_type="user",
            actor_id=user_id,
            action=f"agent.template.{action}",
            resource_type="agent_template",
            resource_id=row.id,
            result="succeeded",
            after_data={
                "revision": row.draft_revision,
                "version": row.published_version,
                "config_hash": config_hash(TemplateConfig.model_validate(row.draft_config_json)),
            },
        )
    )


async def create_template(session: AsyncSession, user: User, payload: TemplateCreate) -> TemplateView:
    await require_template_manager(session, user)
    row = AgentTemplate(
        code=payload.code,
        name=payload.name,
        description=payload.description,
        draft_config_json=payload.config.model_dump(mode="json"),
        created_by=user.id,
        updated_by=user.id,
    )
    session.add(row)
    try:
        await session.flush()
    except IntegrityError as error:
        await session.rollback()
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "模板编码已存在", 409) from error
    _audit(session, user.id, row, "create")
    await session.commit()
    await session.refresh(row)
    return await template_view(session, user, row, True)


async def update_template(
    session: AsyncSession, user: User, template_id: uuid.UUID, payload: TemplateUpdate
) -> TemplateView:
    await require_template_manager(session, user)
    row = await _template(session, template_id, lock=True)
    await require_template_manager(session, user)
    _revision(row, payload.expected_revision)
    if row.archived_at is not None:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "请先恢复已归档模板", 409)
    if "name" in payload.model_fields_set:
        assert payload.name is not None
        row.name = payload.name
    if "description" in payload.model_fields_set:
        row.description = payload.description
    if payload.config is not None:
        row.draft_config_json = payload.config.model_dump(mode="json")
    row.draft_revision += 1
    row.updated_by = user.id
    _audit(session, user.id, row, "update")
    await session.commit()
    await session.refresh(row)
    return await template_view(session, user, row, True)


async def publish_template(
    session: AsyncSession, user: User, template_id: uuid.UUID, expected_revision: int
) -> TemplateView:
    await require_template_manager(session, user)
    user_id = user.id
    row = await _template(session, template_id)
    _revision(row, expected_revision)
    if row.archived_at is not None:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "已归档模板不能发布", 409)
    frozen = TemplateConfig.model_validate(row.draft_config_json)
    frozen_hash = config_hash(frozen)
    # 模型复核在事务外；保留值快照，释放读事务后不再访问过期 ORM 属性。
    await session.rollback()
    settings = get_settings()
    try:
        validate_tool_model(settings, frozen.model_provider, frozen.model_name)
    except ValueError as error:
        raise AppError(ErrorCode.VALIDATION_ERROR, "模型不在当前项目原生工具配置中", 422) from error
    compiled = compile_prompt(frozen.prompt_sections)
    assert frozen.model_provider is not None and frozen.model_name is not None
    await review_configured_prompt(
        sections=compiled.sections, settings=settings, provider_name=frozen.model_provider, model_name=frozen.model_name
    )
    # 复核期间可能被撤权、编辑或归档，最终写入必须重新核验。
    actor = await session.get(User, user_id)
    if actor is None or actor.status != "active":
        raise AppError(ErrorCode.PERMISSION_DENIED, "当前用户不可维护模板", 403)
    await require_template_manager(session, actor)
    row = await _template(session, template_id, lock=True)
    await require_template_manager(session, actor)
    _revision(row, expected_revision)
    if row.archived_at is not None or config_hash(TemplateConfig.model_validate(row.draft_config_json)) != frozen_hash:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "模板已变化，请重新发布", 409)
    next_version = (row.published_version or 0) + 1
    session.add(
        AgentTemplateVersion(
            template_id=row.id,
            version=next_version,
            config_json=frozen.model_dump(mode="json"),
            content_sha256=frozen_hash,
            published_by=user_id,
        )
    )
    row.published_version = next_version
    row.draft_revision += 1
    row.updated_by = user_id
    _audit(session, user_id, row, "publish")
    await session.commit()
    await session.refresh(row)
    return await template_view(session, actor, row, True)


async def set_template_archived(
    session: AsyncSession, user: User, template_id: uuid.UUID, expected_revision: int, *, archived: bool
) -> TemplateView:
    await require_template_manager(session, user)
    row = await _template(session, template_id, lock=True)
    await require_template_manager(session, user)
    _revision(row, expected_revision)
    row.archived_at = datetime.now(UTC) if archived else None
    row.draft_revision += 1
    row.updated_by = user.id
    _audit(session, user.id, row, "archive" if archived else "restore")
    await session.commit()
    await session.refresh(row)
    return await template_view(session, user, row, True)


async def list_template_versions(
    session: AsyncSession, user: User, template_id: uuid.UUID
) -> list[TemplateVersionView]:
    await _readable(session, user, template_id)
    versions = (
        await session.scalars(
            select(AgentTemplateVersion)
            .where(AgentTemplateVersion.template_id == template_id)
            .order_by(AgentTemplateVersion.version.desc())
        )
    ).all()
    return [
        TemplateVersionView(
            version=row.version,
            config=TemplateConfig.model_validate(row.config_json),
            content_sha256=row.content_sha256,
            published_at=row.published_at,
        )
        for row in versions
    ]


async def template_from_agent(session: AsyncSession, user: User, payload: TemplateFromAgent) -> TemplateView:
    await require_template_manager(session, user)
    allowed = await allowed_store_ids(session, user, "agent.view")
    source = await session.scalar(
        select(AgentConfig)
        .where(
            AgentConfig.id == payload.source_agent_id,
            AgentConfig.store_id.in_(allowed),
            AgentConfig.deleted_at.is_(None),
        )
        .with_for_update()
    )
    if source is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "源Agent不存在", 404)
    # 等待源锁期间用户或源店可能失效，必须从当前授权行及有效店铺重新核验。
    await require_template_manager(session, user)
    if source.store_id not in await allowed_store_ids(session, user, "agent.view"):
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "源Agent不存在", 404)
    if payload.source_version is not None:
        version = await session.scalar(
            select(AgentConfigVersion).where(
                AgentConfigVersion.agent_config_id == source.id,
                AgentConfigVersion.store_id == source.store_id,
                AgentConfigVersion.version == payload.source_version,
            )
        )
        if version is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "源Agent版本不存在", 404)
        values: dict[str, object] = {
            "default_agent_name": version.name,
            "suggested_code": version.code,
            "agent_type": version.agent_type,
            "description": version.description,
            "model_provider": version.model_provider,
            "model_name": version.model_name,
            "prompt_sections": version.prompt_sections,
            "tool_names": version.tool_names,
        }
    else:
        if source.draft_revision != payload.source_draft_revision:
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "源Agent草稿已更新", 409)
        values = {
            "default_agent_name": source.name,
            "suggested_code": source.code,
            "agent_type": source.knowledge_scope.get("agent_type", "service"),
            "description": source.description,
            "model_provider": source.draft_model_provider,
            "model_name": source.draft_model_name,
            "prompt_sections": source.draft_prompt_sections,
            "tool_names": source.enabled_tools,
        }
    # 显式投影通用字段；文件ID、回复策略、记忆与审批永不进入模板。
    config = TemplateConfig.model_validate(
        {**values, "knowledge_slots": [slot.model_dump() for slot in payload.knowledge_slots]}
    )
    return await create_template(
        session,
        user,
        TemplateCreate(code=payload.code, name=payload.name, description=payload.description, config=config),
    )


def template_catalog() -> TemplateCatalogView:
    """纯配置目录不推断任何店铺的工具可用性或业务授权。"""
    return TemplateCatalogView(
        model_options=[
            option for option in runtime_view().model_options if option["provider"] in NATIVE_TOOL_PROVIDERS
        ],
        prompt_sections=[TemplatePromptSection(key=key, title=title) for key, title in SECTION_TITLES],
        groups=list(GROUPS),
        tools=[
            TemplateCatalogTool(
                name=item.name,
                title=item.title,
                description=item.description,
                category=item.category,
                operation=item.operation,
                requires_context=item.requires_context,
            )
            for item in TOOL_METADATA.values()
        ],
    )
