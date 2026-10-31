"""受信任管理入口调用的 Agent 版本发布事务。"""

import copy
import hmac
import secrets
import uuid
from dataclasses import dataclass
from typing import cast

from pydantic import JsonValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.core.reply_policy import AgentReplyProfile
from app.agents.management.config_models import AgentConfig
from app.agents.management.models import AgentConfigVersion
from app.agents.management.templates.diff import FIELD_KEYS
from app.agents.management.templates.knowledge import resolve_mappings
from app.agents.management.templates.state import snapshot_hash
from app.agents.prompts.compiler import compile_prompt
from app.agents.prompts.review import PROMPT_CONFIGURATION_REVIEW_VERSION, review_configured_prompt
from app.agents.providers.factory import validate_tool_model
from app.audit.models import AuditLog
from app.shared.config.settings import Settings, get_settings
from app.shared.exceptions.errors import AppError, ErrorCode

_PREPARATION_KEY = secrets.token_bytes(32)


@dataclass(frozen=True, slots=True)
class PreparedPublication:
    """进程内可信复核凭证，只能用于被准确复核的配置快照。"""

    config_hash: str
    provider: str
    model: str
    prompt_hash: str
    input_tokens: int
    output_tokens: int
    _seal: str


def config_snapshot(config: AgentConfig) -> dict[str, JsonValue]:
    scope = config.knowledge_scope if isinstance(config.knowledge_scope, dict) else {}
    return cast(
        dict[str, JsonValue],
        {
            "name": config.name,
            "code": config.code,
            "description": config.description,
            "agent_type": scope.get("agent_type", "service"),
            "model_provider": config.draft_model_provider,
            "model_name": config.draft_model_name,
            "prompt_sections": dict(config.draft_prompt_sections),
            "enabled_tools": sorted(set(config.enabled_tools or [])),
            "knowledge_file_ids": sorted(set(cast(list[str], scope.get("file_ids", [])))),
            "reply_profile": copy.deepcopy(scope.get("reply_profile")),
        },
    )


def version_snapshot(version: AgentConfigVersion) -> dict[str, JsonValue]:
    return cast(
        dict[str, JsonValue],
        {
            "name": version.name,
            "code": version.code,
            "description": version.description,
            "agent_type": version.agent_type,
            "model_provider": version.model_provider,
            "model_name": version.model_name,
            "prompt_sections": dict(version.prompt_sections),
            "enabled_tools": sorted(set(version.tool_names)),
            "knowledge_file_ids": sorted(set(version.file_ids)),
            "reply_profile": copy.deepcopy(version.reply_profile),
        },
    )


def running_snapshot(snapshot: dict[str, JsonValue]) -> dict[str, JsonValue]:
    result = dict(snapshot)
    result["prompt_sections"] = {
        key: value.strip() for key, value in cast(dict[str, str], result["prompt_sections"]).items()
    }
    return result


def template_source(config: AgentConfig) -> dict[str, object] | None:
    if config.template_id is None:
        return None
    state = copy.deepcopy(config.template_state_json or {})
    actual = config_snapshot(config)
    raw_mappings = cast(dict[str, list[str]], state.get("knowledge_mappings", {}))
    slots: list[dict[str, object]] = [{"key": key} for key in raw_mappings]
    # 发布来源只投影当前真实绑定；副本校正不能重写草稿或复活历史引用。
    _, mappings, extras = resolve_mappings(slots, state, cast(list[str], actual["knowledge_file_ids"]), {}, [])
    state["knowledge_mappings"], state["extra_file_ids"] = mappings, extras
    fields = cast(dict[str, dict[str, object]], state.get("fields", {}))
    for key in FIELD_KEYS:
        if key not in fields:
            continue
        if key == "model":
            value: object = {"provider": actual["model_provider"], "name": actual["model_name"]}
        elif key == "tool_names":
            value = actual["enabled_tools"]
        elif key == "knowledge_slots":
            value = fields[key].get("accepted_value", fields[key].get("baseline_value"))
        elif key.startswith("prompt_sections."):
            value = config.draft_prompt_sections.get(key.removeprefix("prompt_sections."), "")
        else:
            value = actual[key]
        fields[key]["actual_value"] = copy.deepcopy(value)
        fields[key]["local_override"] = bool(fields[key].get("local_override")) or value != fields[key].get(
            "baseline_value"
        )
    return {"template_id": str(config.template_id), **state}


def _publication_signature(values: tuple[object, ...]) -> str:
    return hmac.new(_PREPARATION_KEY, snapshot_hash(values).encode(), "sha256").hexdigest()


async def prepare_publication(snapshot: dict[str, JsonValue], settings: Settings) -> PreparedPublication:
    provider, model = snapshot["model_provider"], snapshot["model_name"]
    try:
        validate_tool_model(settings, cast(str | None, provider), cast(str | None, model))
    except ValueError as error:
        raise AppError(ErrorCode.VALIDATION_ERROR, "模型不在当前项目原生工具配置中", 422) from error
    if not isinstance(provider, str) or not isinstance(model, str):
        raise AppError(ErrorCode.VALIDATION_ERROR, "尚未配置模型", 422)
    compiled = compile_prompt(cast(dict[str, str], snapshot["prompt_sections"]))
    if snapshot.get("reply_profile") is not None:
        AgentReplyProfile.model_validate(snapshot["reply_profile"])
    review_input, review_output = await review_configured_prompt(
        sections=compiled.sections, settings=settings, provider_name=provider, model_name=model
    )
    values = (snapshot_hash(snapshot), provider, model, compiled.content_sha256, review_input, review_output)
    return PreparedPublication(*values, _publication_signature(values))


def write_publication(
    session: AsyncSession, config: AgentConfig, publisher_id: uuid.UUID | None, prepared: PreparedPublication
) -> AgentConfigVersion:
    """调用者已持配置锁及授权；本函数不提交事务。"""
    values = (
        prepared.config_hash,
        prepared.provider,
        prepared.model,
        prepared.prompt_hash,
        prepared.input_tokens,
        prepared.output_tokens,
    )
    snapshot = config_snapshot(config)
    if not hmac.compare_digest(prepared._seal, _publication_signature(values)) or prepared.config_hash != snapshot_hash(
        snapshot
    ):
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "配置与模型复核快照不一致", 409)
    next_version = (config.published_version or 0) + 1
    version = AgentConfigVersion(
        store_id=config.store_id,
        agent_config_id=config.id,
        version=next_version,
        name=config.name,
        code=config.code,
        description=config.description,
        agent_type=str(config.knowledge_scope.get("agent_type", "service")),
        model_provider=prepared.provider,
        model_name=prepared.model,
        prompt_sections=dict(compile_prompt(config.draft_prompt_sections).sections),
        prompt_hash=prepared.prompt_hash,
        tool_names=list(config.enabled_tools),
        file_ids=cast(list[str], snapshot["knowledge_file_ids"]),
        ready_for_v2=True,
        published_by=publisher_id,
        template_source_json=template_source(config),
        reply_profile=copy.deepcopy(cast(dict[str, object] | None, snapshot["reply_profile"])),
    )
    session.add(version)
    config.__dict__["_published_template_source_json"] = version.template_source_json
    session.add(
        AuditLog(
            store_id=config.store_id,
            actor_type="user" if publisher_id else "system",
            actor_id=publisher_id,
            action="agent.config.publish",
            resource_type="agent_config",
            resource_id=config.id,
            after_data={
                "version": next_version,
                "prompt_hash": prepared.prompt_hash,
                "privacy_review_version": PROMPT_CONFIGURATION_REVIEW_VERSION,
                "privacy_review_input_tokens": prepared.input_tokens,
                "privacy_review_output_tokens": prepared.output_tokens,
            },
            result="succeeded",
        )
    )
    config.published_version = next_version
    config.draft_revision += 1
    return version


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
        .execution_options(populate_existing=True)
    )
    if config is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Agent 配置不存在", 404)
    if config.draft_revision != expected_revision:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "Agent 配置已更新，请刷新后重试", 409)
    prepared = await prepare_publication(config_snapshot(config), get_settings())
    version = write_publication(session, config, publisher_id, prepared)
    await session.commit()
    await session.refresh(version)
    return version
