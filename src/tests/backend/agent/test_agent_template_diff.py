"""模板边界和三方合并建议不依赖数据库或运行环境。"""

import copy

import pytest
from pydantic import ValidationError

from app.agents.management.templates.diff import config_fields, three_way_diff
from app.agents.management.templates.schemas import FieldDiff, TemplateConfig


def config(**changes: object) -> TemplateConfig:
    return TemplateConfig.model_validate({"default_agent_name": "客服", "suggested_code": "service", **changes})


def diff(baseline: TemplateConfig, local: TemplateConfig, target: TemplateConfig) -> list[FieldDiff]:
    return three_way_diff(config_fields(baseline), config_fields(local), config_fields(target))


@pytest.mark.parametrize(
    ("baseline", "local", "target", "status", "choice"),
    [
        ("a", "a", "a", "unchanged", "skip"),
        ("a", "a", "b", "template_changed", "template"),
        ("a", "b", "a", "local_changed", "local"),
        ("a", "b", "b", "converged", "skip"),
        ("a", "b", "c", "conflict", "resolve"),
    ],
)
def test_three_way_states_keep_local_edits(baseline: str, local: str, target: str, status: str, choice: str) -> None:
    result = diff(config(description=baseline), config(description=local), config(description=target))
    field = next(item for item in result if item.field == "description")
    assert (field.baseline, field.local, field.target) == (baseline, local, target)
    assert (field.status, field.default_choice) == (status, choice)


def test_model_provider_and_name_are_one_atomic_conflict() -> None:
    result = diff(
        config(model_provider="deepseek", model_name="old"),
        config(model_provider="openai", model_name="old"),
        config(model_provider="deepseek", model_name="new"),
    )
    model = next(item for item in result if item.field == "model")
    assert model.local == {"provider": "openai", "name": "old"}
    assert model.target == {"provider": "deepseek", "name": "new"}
    assert model.status == "conflict"
    assert not any(item.field in {"model_provider", "model_name"} for item in result)


def test_set_like_tools_and_slots_ignore_order_without_mutating_input() -> None:
    a = {"key": "policy", "name": "政策", "purpose": "售后", "required": True}
    b = {"key": "faq", "name": "问答", "purpose": "常见问题", "required": False}
    baseline = config(tool_names=["query_order", "query_logistics"], knowledge_slots=[a, b])
    local = config(tool_names=["query_logistics", "query_order", "query_order"], knowledge_slots=[b, a])
    before = copy.deepcopy(local.model_dump())
    assert all(item.status == "unchanged" for item in diff(baseline, local, baseline))
    assert local.model_dump() == before


def test_only_portable_fields_enter_comparison_and_each_prompt_is_independent() -> None:
    baseline = config(prompt_sections={"identity": "旧身份"})
    target = config(default_agent_name="另一个名字", suggested_code="other", prompt_sections={"identity": "新身份"})
    fields = config_fields(baseline)
    assert set(fields) == {
        "agent_type",
        "description",
        "model",
        "tool_names",
        "knowledge_slots",
        "prompt_sections.identity",
        "prompt_sections.service_scope",
        "prompt_sections.tool_rules",
        "prompt_sections.escalation",
        "prompt_sections.language_format",
        "prompt_sections.compliance",
        "prompt_sections.clarification",
    }
    assert fields["prompt_sections.clarification"] == ""
    changed = [item.field for item in diff(baseline, baseline, target) if item.status != "unchanged"]
    assert changed == ["prompt_sections.identity"]


@pytest.mark.parametrize("side", ["baseline", "local", "target"])
def test_missing_baseline_or_comparison_fields_are_rejected(side: str) -> None:
    values = {name: config_fields(config()) for name in ("baseline", "local", "target")}
    del values[side]["description"]
    with pytest.raises(ValueError):
        three_way_diff(values["baseline"], values["local"], values["target"])


def test_same_incomplete_or_unknown_field_sets_are_rejected() -> None:
    fields = config_fields(config())
    del fields["description"]
    with pytest.raises(ValueError):
        three_way_diff(fields, fields, fields)
    fields["description"] = None
    fields["reply_profile"] = {}
    with pytest.raises(ValueError):
        three_way_diff(fields, fields, fields)


def test_incomplete_draft_allows_empty_model_and_partial_prompt() -> None:
    draft = config(prompt_sections={"identity": ""}, model_provider="deepseek")
    assert draft.model_name is None
    assert draft.prompt_sections == {"identity": ""}


@pytest.mark.parametrize(
    "changes",
    [
        {"prompt_sections": {"unknown": "bad"}},
        {"prompt_sections": {"identity": "a" * 4001}},
        {"tool_names": ["unknown_tool"]},
        {
            "knowledge_slots": [
                {"key": "faq", "name": "FAQ", "purpose": "解答", "required": False},
                {"key": "faq", "name": "重复", "purpose": "解答", "required": True},
            ]
        },
        {"knowledge_slots": [{"key": "faq", "name": "FAQ", "purpose": "解答", "required": "false"}]},
        {"knowledge_slots": [{"key": "faq", "name": "FAQ", "purpose": "解答", "required": False, "file_id": "secret"}]},
        {"file_ids": ["actual-file"]},
        {"reply_profile": {}},
        {"default_agent_name": 1},
    ],
)
def test_nonportable_or_invalid_draft_is_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        config(**changes)
