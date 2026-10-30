"""逐字段模板基线独立推进；本店实际配置是覆盖状态的事实来源。"""

import copy
import hashlib
import json
from collections.abc import Mapping
from typing import Literal, cast

from pydantic import JsonValue

from app.agents.management.templates.diff import FIELD_KEYS, config_fields, three_way_diff
from app.agents.management.templates.schemas import ApplicationIssue, FieldDecision, FieldDiff, TemplateConfig


def snapshot_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def fields_config(fields: Mapping[str, JsonValue], *, name: str, code: str) -> TemplateConfig:
    model = fields["model"]
    # 模型必须以完整 pair 校验，不能把半个手工选择悄悄补成 null。
    if not isinstance(model, dict) or set(model) != {"provider", "name"}:
        from pydantic import ValidationError

        raise ValidationError.from_exception_data(
            "TemplateConfig", [{"type": "missing", "loc": ("model",), "input": model}]
        )
    return TemplateConfig.model_validate(
        {
            "default_agent_name": name,
            "suggested_code": code,
            "agent_type": fields["agent_type"],
            "description": fields["description"],
            "model_provider": model["provider"],
            "model_name": model["name"],
            "tool_names": fields["tool_names"],
            "knowledge_slots": fields["knowledge_slots"],
            "prompt_sections": {
                key.removeprefix("prompt_sections."): fields[key]
                for key in FIELD_KEYS
                if key.startswith("prompt_sections.")
            },
        }
    )


def resolve_fields(
    template: TemplateConfig,
    actual: Mapping[str, JsonValue],
    previous: dict[str, object] | None,
    version: int,
    decisions: dict[str, FieldDecision] | None,
    action: Literal["create", "adopt", "update"],
) -> tuple[dict[str, JsonValue], dict[str, object], dict[str, FieldDecision], list[FieldDiff], list[ApplicationIssue]]:
    target = config_fields(template)
    state = copy.deepcopy(previous) if previous else {"schema_version": 1, "fields": {}}
    raw_fields = state.get("fields")
    if state.get("schema_version") != 1 or not isinstance(raw_fields, dict):
        raise ValueError("模板字段基线无效，请重新关联")
    states = cast(dict[str, dict[str, JsonValue]], raw_fields)
    if action in {"create", "adopt"}:
        states.update(
            {
                key: {
                    "baseline_value": copy.deepcopy(value),
                    "applied_template_version": version,
                    "last_reviewed_template_version": version,
                    "local_override": action == "adopt" and actual[key] != value,
                }
                for key, value in target.items()
            }
        )
    if set(states) != set(FIELD_KEYS) or any("baseline_value" not in states[k] for k in FIELD_KEYS):
        raise ValueError("模板字段基线不完整，请重新关联")
    baseline = {key: states[key]["baseline_value"] for key in FIELD_KEYS}
    diffs = three_way_diff(baseline, actual, target)
    choices = dict(decisions or {})
    issues = []
    if decisions is None and action == "update":
        for diff in diffs:
            if diff.status in {"template_changed", "converged"}:
                choices[diff.field] = FieldDecision(choice="template")
            elif diff.status == "local_changed":
                choices[diff.field] = FieldDecision(choice="local")
            elif diff.status == "conflict":
                issues.append(ApplicationIssue(code="field_conflict", message="字段存在未解决冲突", field=diff.field))
    result = copy.deepcopy(target if action == "create" else dict(actual))
    for key, decision in choices.items():
        old = states[key]
        if decision.choice == "template":
            result[key] = copy.deepcopy(target[key])
            states[key] = {
                "baseline_value": copy.deepcopy(target[key]),
                "applied_template_version": version,
                "last_reviewed_template_version": version,
                "local_override": False,
            }
        else:
            result[key] = copy.deepcopy(decision.value if decision.choice == "manual" else actual[key])
            states[key] = {
                **old,
                "last_reviewed_template_version": version,
                "local_override": decision.choice == "manual" or result[key] != target[key],
            }
    fields_config(result, name=template.default_agent_name, code=template.suggested_code)
    return result, state, choices, diffs, issues
