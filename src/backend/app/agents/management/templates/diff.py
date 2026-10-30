"""不读取环境、不写入配置的三方字段比较。"""

from collections.abc import Mapping

from pydantic import JsonValue

from app.agents.management.templates.schemas import DiffChoice, DiffStatus, FieldDiff, TemplateConfig
from app.agents.prompts.sections import SECTION_TITLES

FIELD_KEYS = (
    "agent_type",
    "description",
    "model",
    "tool_names",
    "knowledge_slots",
    *(f"prompt_sections.{key}" for key, _ in SECTION_TITLES),
)


def config_fields(config: TemplateConfig) -> dict[str, JsonValue]:
    """名称和编码只用于创建；模型原子比较，工具及槽按集合语义比较。"""
    slots: list[JsonValue] = [
        slot.model_dump(mode="json") for slot in sorted(config.knowledge_slots, key=lambda s: s.key)
    ]
    tools: list[JsonValue] = [name for name in sorted(set(config.tool_names))]
    fields: dict[str, JsonValue] = {
        "agent_type": config.agent_type,
        "description": config.description,
        "model": {"provider": config.model_provider, "name": config.model_name},
        "tool_names": tools,
        "knowledge_slots": slots,
    }
    for key, _ in SECTION_TITLES:
        fields[f"prompt_sections.{key}"] = config.prompt_sections.get(key, "")
    return fields


def three_way_diff(
    baseline: Mapping[str, JsonValue], local: Mapping[str, JsonValue], target: Mapping[str, JsonValue]
) -> list[FieldDiff]:
    """比较 config_fields 格式的完整十二字段映射，允许每字段来自不同版本。"""
    # 缺失基线不能视为显式空值，否则会把未知状态误判为可以覆盖。
    expected = set(FIELD_KEYS)
    if any(set(fields) != expected for fields in (baseline, local, target)):
        raise ValueError("三方差异必须包含且仅包含十二个通用配置字段")
    result = []
    for field in FIELD_KEYS:
        base_value, local_value, target_value = baseline[field], local[field], target[field]
        status: DiffStatus
        choice: DiffChoice
        if base_value == local_value == target_value:
            status, choice = "unchanged", "skip"
        elif local_value == target_value:
            status, choice = "converged", "skip"
        elif local_value == base_value:
            status, choice = "template_changed", "template"
        elif target_value == base_value:
            status, choice = "local_changed", "local"
        else:
            status, choice = "conflict", "resolve"
        result.append(
            FieldDiff(
                field=field,
                baseline=base_value,
                local=local_value,
                target=target_value,
                status=status,
                default_choice=choice,
            )
        )
    return result
