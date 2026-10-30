"""模板应用字段状态、知识来源和输入契约。"""

import copy
import uuid

import pytest
from pydantic import ValidationError

from app.agents.management.templates.diff import config_fields
from app.agents.management.templates.knowledge import resolve_mappings
from app.agents.management.templates.schemas import (
    ApplicationItemRequest,
    ApplicationPreviewRequest,
    ApplicationPreviewView,
    FieldDecision,
    TemplateConfig,
)
from app.agents.management.templates.state import resolve_fields


def config(**changes):
    return TemplateConfig(default_agent_name="客服", suggested_code="service", **changes)


def test_decisions_reject_extra_missing_manual_unknown_fields_and_model_half():
    with pytest.raises(ValidationError):
        FieldDecision(choice="manual")
    with pytest.raises(ValidationError):
        FieldDecision(choice="local", template_state_json={})
    with pytest.raises(ValidationError):
        ApplicationItemRequest(store_id=uuid.uuid4(), action="update", fields={"model_provider": {"choice": "local"}})


def test_unselected_fields_never_advance_but_explicit_local_reviews():
    original = config(description="A")
    _, state, _, _, _ = resolve_fields(original, config_fields(original), None, 1, None, "create")
    before = copy.deepcopy(state)
    target = config(description="C", agent_type="operations")
    values, state, choices, diffs, issues = resolve_fields(target, config_fields(original), state, 2, {}, "update")
    assert state == before
    assert choices == {}
    assert values["description"] == "A"
    assert next(d for d in diffs if d.field == "description").status == "template_changed"
    assert not issues
    _, state, _, _, _ = resolve_fields(
        target, values, state, 2, {"description": FieldDecision(choice="local")}, "update"
    )
    assert state["fields"]["description"] == {
        **before["fields"]["description"],
        "local_override": True,
        "last_reviewed_template_version": 2,
    }
    assert state["fields"]["agent_type"] == before["fields"]["agent_type"]


def test_conflict_is_displayable_and_manual_resolves_atomically_paired_model():
    a = config(model_provider="deepseek", model_name="A")
    _, state, _, _, _ = resolve_fields(a, config_fields(a), None, 1, None, "create")
    b = config(model_provider="openai", model_name="B")
    c = config(model_provider="deepseek", model_name="C")
    _, _, _, _, issues = resolve_fields(c, config_fields(b), state, 2, None, "update")
    assert issues[0].code == "field_conflict"
    values, updated, _, _, issues = resolve_fields(
        c,
        config_fields(b),
        state,
        2,
        {"model": FieldDecision(choice="manual", value={"provider": "openai", "name": "D"})},
        "update",
    )
    assert values["model"] == {"provider": "openai", "name": "D"}
    assert updated["fields"]["model"]["baseline_value"] == config_fields(a)["model"]
    assert updated["fields"]["model"]["applied_template_version"] == 1
    assert updated["fields"]["model"]["last_reviewed_template_version"] == 2
    assert not issues


def test_adoption_keeps_local_and_converged_advances_metadata():
    c = config(description="template")
    b = config(description="local")
    values, state, _, _, _ = resolve_fields(c, config_fields(b), None, 1, None, "adopt")
    assert values["description"] == "local"
    assert state["fields"]["description"]["local_override"] is True
    values["description"] = "new"
    _, state, choices, _, _ = resolve_fields(config(description="new"), values, state, 2, None, "update")
    assert choices["description"].choice == "template"
    assert state["fields"]["description"]["baseline_value"] == "new"


def test_knowledge_sources_preserve_manual_unbinds_multiple_slots_and_removed_extras():
    f, g, manual = [str(uuid.uuid4()) for _ in range(3)]
    slots = [
        {"key": "a", "name": "A", "purpose": "A", "required": False},
        {"key": "b", "name": "B", "purpose": "B", "required": False},
    ]
    state = {"knowledge_mappings": {"a": [f, g], "b": [f]}, "extra_file_ids": [manual]}
    files, mappings, extras = resolve_mappings(slots, state, [f, manual], {}, [])
    assert files == sorted([f, manual])
    assert mappings == {"a": [f], "b": [f]}
    assert extras == [manual]
    files, mappings, extras = resolve_mappings(slots[1:], state, [f, g, manual], {}, [g, f])
    assert files == sorted([f, manual])
    assert mappings == {"b": [f]}
    assert extras == [manual]
    files, _, extras = resolve_mappings([], state, [f, g, manual], {}, [])
    assert files == extras == sorted([f, g, manual])


def test_create_overrides_validate_final_complete_model_and_reject_retired_tools_only_at_target():
    c = config()
    values = config_fields(c)
    values["tool_names"] = ["retired"]
    resolved, _, _, _, _ = resolve_fields(c, values, None, 1, {"tool_names": FieldDecision(choice="template")}, "adopt")
    assert resolved["tool_names"] == []
    with pytest.raises(ValidationError):
        resolve_fields(
            c,
            config_fields(c),
            None,
            1,
            {"model": FieldDecision(choice="manual", value={"provider": "deepseek"})},
            "create",
        )


def test_same_file_keeps_independent_extra_source_after_slot_unbind():
    file_id = str(uuid.uuid4())
    slot = {"key": "policy", "name": "政策", "purpose": "依据", "required": False}
    state = {"knowledge_mappings": {"policy": [file_id]}, "extra_file_ids": [file_id]}
    files, mappings, extras = resolve_mappings([slot], state, [file_id], {}, [])
    assert files == extras == [file_id]
    assert mappings == {"policy": [file_id]}
    files, _, extras = resolve_mappings([], state, [file_id], {}, [file_id])
    assert files == extras == [file_id]
    assert resolve_mappings([slot], state, [], {}, [])[0] == []


def test_store_selection_has_no_arbitrary_hundred_store_limit():
    payload = ApplicationPreviewRequest.model_validate(
        {"template_version": 1, "items": [{"store_id": str(uuid.uuid4()), "action": "create"} for _ in range(101)]}
    )
    assert len(payload.items) == 101


@pytest.mark.parametrize("choice", ["template", "local"])
def test_complete_preview_json_roundtrip_omits_nonmanual_value_and_preserves_manual_null(choice):
    store_id = uuid.uuid4()
    request = ApplicationItemRequest.model_validate(
        {
            "store_id": str(store_id),
            "action": "create",
            "fields": {"agent_type": {"choice": choice}, "description": {"choice": "manual", "value": None}},
        }
    )
    view = ApplicationPreviewView.model_validate(
        {
            "preview_id": uuid.uuid4(),
            "preview_hash": "a" * 64,
            "template_id": uuid.uuid4(),
            "template_version": 1,
            "items": [
                {
                    "id": uuid.uuid4(),
                    "store_id": store_id,
                    "store_name": "测试店",
                    "agent_id": None,
                    "action": "create",
                    "valid": True,
                    "issues": [],
                    "warnings": [],
                    "diffs": [],
                    "published_snapshot": None,
                    "full_target": {"description": None},
                    "knowledge_slots": [],
                    "mappings": {},
                    "has_existing_draft": False,
                    "field_choices": request.fields,
                    "flags": {"publish": False},
                    "request": request,
                }
            ],
        }
    )
    encoded = view.model_dump(mode="json")
    assert encoded["items"][0]["field_choices"]["agent_type"] == {"choice": choice}
    assert encoded["items"][0]["field_choices"]["description"] == {"choice": "manual", "value": None}
    assert encoded["items"][0]["request"]["fields"]["agent_type"] == {"choice": choice}
    assert ApplicationPreviewView.model_validate_json(view.model_dump_json()) == view
    with pytest.raises(ValidationError):
        FieldDecision.model_validate({"choice": choice, "value": "untrusted value"})
