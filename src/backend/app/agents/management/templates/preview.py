"""预览是服务端生成的不可变应用快照，不产生店铺配置副作用。"""

import uuid
from typing import cast

from pydantic import JsonValue, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.management.config_models import AgentConfig
from app.agents.management.models import AgentConfigVersion
from app.agents.management.service import config_snapshot, running_snapshot, version_snapshot
from app.agents.management.templates.diff import FIELD_KEYS, config_fields
from app.agents.management.templates.knowledge import knowledge_dependencies, resolve_mappings
from app.agents.management.templates.models import (
    AgentTemplate,
    AgentTemplateBatch,
    AgentTemplateBatchItem,
    AgentTemplateVersion,
)
from app.agents.management.templates.schemas import (
    ApplicationIssue,
    ApplicationItemRequest,
    ApplicationItemView,
    ApplicationPreviewRequest,
    ApplicationPreviewView,
    TemplateConfig,
)
from app.agents.management.templates.service import can_manage_templates, config_hash
from app.agents.management.templates.state import fields_config, resolve_fields, snapshot_hash
from app.agents.prompts.compiler import compile_prompt
from app.agents.providers.factory import validate_tool_model
from app.agents.tools.access import tool_catalog
from app.agents.tools.metadata import TOOL_METADATA
from app.audit.models import AuditLog
from app.auth.store_access import allowed_store_ids
from app.shared.config.settings import get_settings
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import Store


async def authorize_store(session: AsyncSession, user: User, store_id: uuid.UUID) -> Store:
    active = await session.scalar(select(User.status).where(User.id == user.id))
    store = await session.scalar(
        select(Store).where(Store.id == store_id, Store.status == "active", Store.deleted_at.is_(None))
    )
    if active != "active" or store is None or store_id not in await allowed_store_ids(session, user, "agent.manage"):
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "资源不存在或无权管理", 404)
    return store


def catalog_hash() -> str:
    settings = get_settings()
    return snapshot_hash(
        {
            "models": [
                (settings.llm_primary_provider, settings.llm_primary_model),
                (settings.llm_fallback_provider, settings.llm_fallback_model),
            ],
            "tools": {
                name: {
                    "permission": meta.permission,
                    "scopes": meta.scopes,
                    "any_scopes": meta.any_scopes,
                    "arguments": meta.arguments.model_json_schema(),
                }
                for name, meta in TOOL_METADATA.items()
            },
        }
    )


def actual_fields(config: AgentConfig) -> dict[str, JsonValue]:
    state = config.template_state_json or {}
    states = cast(dict[str, dict[str, JsonValue]], state.get("fields", {}))
    slot_state = states.get("knowledge_slots", {})
    fields = cast(
        dict[str, JsonValue],
        {
            "agent_type": cast(JsonValue, config.knowledge_scope.get("agent_type", "service")),
            "description": config.description,
            "model": {"provider": config.draft_model_provider, "name": config.draft_model_name},
            "tool_names": sorted(set(config.enabled_tools)),
            "knowledge_slots": slot_state.get("accepted_value", slot_state.get("baseline_value", [])),
        },
    )
    for key in FIELD_KEYS:
        if key.startswith("prompt_sections."):
            fields[key] = config.draft_prompt_sections.get(key.removeprefix("prompt_sections."), "")
    return fields


async def template_version(
    session: AsyncSession, template_id: uuid.UUID, version: int
) -> tuple[AgentTemplate, AgentTemplateVersion, TemplateConfig]:
    template = await session.scalar(
        select(AgentTemplate).where(AgentTemplate.id == template_id).execution_options(populate_existing=True)
    )
    if template is None or template.archived_at is not None or template.published_version is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "模板不存在或不可应用", 404)
    row = await session.scalar(
        select(AgentTemplateVersion).where(
            AgentTemplateVersion.template_id == template_id, AgentTemplateVersion.version == version
        )
    )
    if row is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "模板版本不存在", 404)
    try:
        config = TemplateConfig.model_validate(row.config_json)
    except ValidationError as error:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "模板版本配置已失效", 409) from error
    if config_hash(config) != row.content_sha256:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "模板版本校验失败", 409)
    return template, row, config


async def _preview_item(
    session: AsyncSession,
    user: User,
    batch: AgentTemplateBatch,
    version: AgentTemplateVersion,
    template: TemplateConfig,
    payload: ApplicationItemRequest,
    store: Store,
) -> tuple[AgentTemplateBatchItem, ApplicationItemView]:
    issues: list[ApplicationIssue] = []
    linked = await session.scalar(
        select(AgentConfig).where(
            AgentConfig.store_id == store.id,
            AgentConfig.template_id == batch.template_id,
            AgentConfig.deleted_at.is_(None),
        )
    )
    config = None
    published = None
    if payload.action == "create":
        if linked is not None:
            issues.append(ApplicationIssue(code="already_linked", message="本店已关联该模板，请选择更新"))
    else:
        config = await session.scalar(
            select(AgentConfig).where(
                AgentConfig.id == payload.agent_id, AgentConfig.store_id == store.id, AgentConfig.deleted_at.is_(None)
            )
        )
        if config is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Agent 不存在", 404)
        if config.draft_revision != payload.expected_revision:
            issues.append(ApplicationIssue(code="revision_changed", message="Agent 草稿已变化，请刷新"))
        if payload.action == "adopt" and config.template_id is not None:
            issues.append(ApplicationIssue(code="already_linked", message="Agent 已关联模板"))
        if payload.action == "update" and config.template_id != batch.template_id:
            issues.append(ApplicationIssue(code="template_mismatch", message="Agent 未关联此模板"))
        if linked is not None and linked.id != config.id:
            issues.append(ApplicationIssue(code="already_linked", message="本店已有其他 Agent 关联此模板"))
        if config.published_version is not None:
            published = await session.scalar(
                select(AgentConfigVersion).where(
                    AgentConfigVersion.agent_config_id == config.id,
                    AgentConfigVersion.store_id == store.id,
                    AgentConfigVersion.version == config.published_version,
                )
            )
            if published is None:
                raise AppError(ErrorCode.RESOURCE_CONFLICT, "Agent 发布快照缺失", 409)
    name = config.name if config else payload.name or template.default_agent_name
    code = config.code if config else payload.code or template.suggested_code
    collision = await session.scalar(
        select(AgentConfig.id).where(
            AgentConfig.store_id == store.id, AgentConfig.code == code, AgentConfig.deleted_at.is_(None)
        )
    )
    if collision is not None and (config is None or collision != config.id):
        issues.append(ApplicationIssue(code="code_conflict", message="本店 Agent 编码已存在", field="code"))
    actual = actual_fields(config) if config else config_fields(template)
    previous = config.template_state_json if config else None
    try:
        fields, state, choices, diffs, field_issues = resolve_fields(
            template, actual, previous, batch.template_version, payload.fields, payload.action
        )
        issues.extend(field_issues)
        accepted = fields_config(fields, name=name, code=code)
    except ValidationError as error:
        # 非法最终目标不得冻结为有效快照；旧工具仍可在明确选择替换后修复。
        raise AppError(ErrorCode.VALIDATION_ERROR, "最终配置字段无效", 422) from error
    except ValueError as error:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, str(error), 409) from error
    slots = [slot.model_dump(mode="json") for slot in accepted.knowledge_slots]
    scope = config.knowledge_scope if config else {}
    current_files = cast(list[str], scope.get("file_ids", []))
    requested = {key: [str(fid) for fid in values] for key, values in payload.knowledge_mappings.items()}
    files, mappings, extras = resolve_mappings(
        slots, previous, current_files, requested, [str(fid) for fid in payload.unbind_removed_file_ids]
    )
    if len(files) > 100:
        raise AppError(ErrorCode.VALIDATION_ERROR, "Agent 最多绑定 100 个知识文件", 422)
    binding_requested = bool(payload.knowledge_mappings or payload.unbind_removed_file_ids) or set(files) != set(
        current_files
    )
    if binding_requested and store.id not in await allowed_store_ids(session, user, "knowledge.view"):
        raise AppError(ErrorCode.PERMISSION_DENIED, "没有本店知识绑定权限", 403)
    dependencies, knowledge_issues = await knowledge_dependencies(session, store.id, files, publish=payload.publish)
    issues.extend(knowledge_issues)
    if payload.publish:
        for slot in slots:
            if slot["required"] and not mappings[str(slot["key"])]:
                issues.append(
                    ApplicationIssue(code="required_slot_missing", message="必需知识槽尚未映射", field=str(slot["key"]))
                )
    state["knowledge_mappings"], state["extra_file_ids"] = mappings, extras
    if payload.action in {"create", "adopt"} or "knowledge_slots" in choices:
        cast(dict[str, dict[str, object]], state["fields"])["knowledge_slots"]["accepted_value"] = slots
    full_target = cast(
        dict[str, JsonValue],
        {
            "name": name,
            "code": code,
            "description": accepted.description,
            "agent_type": accepted.agent_type,
            "model_provider": accepted.model_provider,
            "model_name": accepted.model_name,
            "prompt_sections": accepted.prompt_sections,
            "enabled_tools": sorted(set(accepted.tool_names)),
            "knowledge_file_ids": files,
            "reply_profile": scope.get("reply_profile"),
        },
    )
    draft_snapshot = config_snapshot(config) if config else None
    published_snapshot = version_snapshot(published) if published else None
    comparable_draft = running_snapshot(draft_snapshot) if draft_snapshot else {}
    has_draft = config is not None and (published_snapshot is None or comparable_draft != published_snapshot)
    if payload.publish and has_draft and not payload.include_existing_draft:
        issues.append(
            ApplicationIssue(
                code="existing_draft_confirmation_required", message="请确认完整目标包含当前全部未发布草稿"
            )
        )
    if payload.publish:
        try:
            validate_tool_model(get_settings(), accepted.model_provider, accepted.model_name)
            compile_prompt(accepted.prompt_sections)
        except (ValueError, AppError):
            issues.append(
                ApplicationIssue(code="publication_configuration_invalid", message="发布需要有效模型和完整七段提示词")
            )
    # 缺少平台授权是现有可配置工具的警告，不提升为发布阻断。
    catalog = await tool_catalog(session, user, store.id)
    warnings = [
        ApplicationIssue(code="tool_unavailable", message=tool.reason, field=tool.name)
        for tool in catalog.tools
        if tool.name in accepted.tool_names and tool.availability == "unavailable"
    ]
    flags = {
        "publish": payload.publish,
        "enable_after_publish": payload.enable_after_publish,
        "include_existing_draft": payload.include_existing_draft,
    }
    item = AgentTemplateBatchItem(
        id=uuid.uuid4(),
        batch_id=batch.id,
        store_id=store.id,
        agent_config_id=config.id if config else None,
        expected_revision=config.draft_revision if config else None,
        expected_published_version=config.published_version if config else None,
        expected_status=config.status if config else None,
        field_choices_json={
            key: decision.model_dump(mode="json", exclude_unset=True) for key, decision in choices.items()
        },
        knowledge_mapping_json=cast(dict[str, object], mappings),
    )
    view = ApplicationItemView(
        id=item.id,
        store_id=store.id,
        store_name=store.name,
        agent_id=config.id if config else None,
        action=payload.action,
        valid=not issues,
        issues=issues,
        warnings=warnings,
        diffs=diffs,
        published_snapshot=published_snapshot,
        full_target=full_target,
        knowledge_slots=accepted.knowledge_slots,
        mappings=mappings,
        has_existing_draft=has_draft,
        field_choices=choices,
        flags=flags,
        request=payload,
    )
    item.target_config_json = {
        "store_id": str(item.store_id),
        "agent_id": str(item.agent_config_id) if item.agent_config_id else None,
        "expected_revision": item.expected_revision,
        "expected_published_version": item.expected_published_version,
        "expected_status": item.expected_status,
        "config": full_target,
        "template_state": state,
        "template_hash": version.content_sha256,
        "catalog_hash": catalog_hash(),
        "dependencies": dependencies,
        "binding_requested": binding_requested,
        "action": payload.action,
        "valid": not issues,
        "publish": payload.publish,
        "enable_after_publish": payload.enable_after_publish,
        "include_existing_draft": payload.include_existing_draft,
        "original_config": draft_snapshot,
        "published_snapshot": published_snapshot,
        "view": view.model_dump(mode="json"),
    }
    item.target_config_hash = snapshot_hash(item.target_config_json)
    return item, view


def _invalid_item(
    batch: AgentTemplateBatch, payload: ApplicationItemRequest, store: Store, error: AppError
) -> tuple[AgentTemplateBatchItem, ApplicationItemView]:
    code, message = {
        403: ("binding_permission_denied", "没有本店知识绑定权限"),
        404: ("target_unavailable", "Agent 或知识文件不存在或不可用"),
        409: ("item_changed", "本店配置或关联已变化，请重新预览"),
        422: ("invalid_target", "本店最终配置或知识映射无效"),
    }[error.status_code]
    flags = {
        "publish": payload.publish,
        "enable_after_publish": payload.enable_after_publish,
        "include_existing_draft": payload.include_existing_draft,
    }
    item = AgentTemplateBatchItem(
        id=uuid.uuid4(),
        batch_id=batch.id,
        store_id=store.id,
        agent_config_id=None,
        expected_revision=payload.expected_revision,
        field_choices_json={},
        knowledge_mapping_json={},
    )
    view = ApplicationItemView(
        id=item.id,
        store_id=store.id,
        store_name=store.name,
        agent_id=None,
        action=payload.action,
        valid=False,
        issues=[ApplicationIssue(code=code, message=message)],
        warnings=[],
        diffs=[],
        published_snapshot=None,
        full_target={},
        knowledge_slots=[],
        mappings={},
        has_existing_draft=False,
        field_choices=payload.fields or {},
        flags=flags,
        request=payload,
    )
    # 无法定位的请求 ID 仅存作重配资料，绝不写入可执行 FK 或完整目标。
    item.target_config_json = {
        "valid": False,
        "request": payload.model_dump(mode="json"),
        "view": view.model_dump(mode="json"),
    }
    item.target_config_hash = snapshot_hash(item.target_config_json)
    return item, view


async def create_application_preview(
    session: AsyncSession, user: User, template_id: uuid.UUID, payload: ApplicationPreviewRequest
) -> ApplicationPreviewView:
    _, version, config = await template_version(session, template_id, payload.template_version)
    # 先核对请求店铺，父批次信息也不能成为跨店存在性探针。
    stores = {
        requested.store_id: await authorize_store(session, user, requested.store_id) for requested in payload.items
    }
    if payload.parent_batch_id is not None:
        parent = await session.get(AgentTemplateBatch, payload.parent_batch_id)
        if (
            parent is None
            or parent.template_id != template_id
            or (parent.created_by != user.id and not await can_manage_templates(session, user))
        ):
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "父批次不存在", 404)
        succeeded = set(
            (
                await session.scalars(
                    select(AgentTemplateBatchItem.store_id).where(
                        AgentTemplateBatchItem.batch_id == parent.id, AgentTemplateBatchItem.status == "succeeded"
                    )
                )
            ).all()
        )
        parent_stores = set(
            (
                await session.scalars(
                    select(AgentTemplateBatchItem.store_id).where(AgentTemplateBatchItem.batch_id == parent.id)
                )
            ).all()
        )
        if any(item.store_id not in parent_stores or item.store_id in succeeded for item in payload.items):
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "父批次仅可重新预览未成功店铺", 409)
    batch = AgentTemplateBatch(
        id=uuid.uuid4(),
        template_id=template_id,
        template_version=payload.template_version,
        created_by=user.id,
        parent_batch_id=payload.parent_batch_id,
        status="preview",
        mode="publish"
        if all(i.publish for i in payload.items)
        else "mixed"
        if any(i.publish for i in payload.items)
        else "save_draft",
    )
    views, items = [], []
    for requested in payload.items:
        try:
            item, view = await _preview_item(
                session, user, batch, version, config, requested, stores[requested.store_id]
            )
        except AppError as error:
            if error.status_code not in {403, 404, 409, 422}:
                raise
            item, view = _invalid_item(batch, requested, stores[requested.store_id], error)
        items.append(item)
        views.append(view)
    batch.preview_json = {
        "schema_version": 1,
        "template_id": str(template_id),
        "template_version": payload.template_version,
        "items": [{"id": str(item.id), "target_config_hash": item.target_config_hash} for item in items],
    }
    batch.preview_hash = snapshot_hash(batch.preview_json)
    session.add(batch)
    await session.flush()
    session.add_all(items)
    session.add(
        AuditLog(
            actor_type="user",
            actor_id=user.id,
            action="agent.template.preview",
            resource_type="agent_template_batch",
            resource_id=batch.id,
            after_data={"preview_hash": batch.preview_hash, "item_count": len(items)},
            result="succeeded",
        )
    )
    await session.commit()
    return ApplicationPreviewView(
        preview_id=batch.id,
        preview_hash=batch.preview_hash,
        template_id=template_id,
        template_version=payload.template_version,
        items=views,
    )
