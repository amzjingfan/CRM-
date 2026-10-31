"""四个新模板的配置清单可通过现有模板 API 发布，订单物流原模板保持独立。"""

import json
from pathlib import Path

from app.agents.management.templates.schemas import TemplateConfig
from app.agents.prompts.compiler import compile_prompt
from app.agents.prompts.sections import SECTION_TITLES

MANIFEST = Path(__file__).resolve().parents[2] / "ai" / "datasets" / "five_agent_templates.json"


def test_four_new_template_configs_are_publishable_and_have_distinct_purposes() -> None:
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert {entry["code"] for entry in entries} == {
        "presales_products_v1",
        "aftersales_products_v1",
        "logistics_update_v1",
        "reply_fallback_v1",
    }
    types = {entry["code"]: TemplateConfig.model_validate(entry["config"]).agent_type for entry in entries}
    assert types["logistics_update_v1"] == "logistics_event"
    assert types["reply_fallback_v1"] == "fallback"
    for entry in entries:
        config = TemplateConfig.model_validate(entry["config"])
        assert set(config.prompt_sections) == {key for key, _ in SECTION_TITLES}
        assert len(config.tool_names) == len(set(config.tool_names))
        assert config.model_provider == "deepseek"
        compile_prompt(config.prompt_sections)


def test_templates_use_only_bound_knowledge_and_no_platform_send_tool() -> None:
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for entry in entries:
        config = TemplateConfig.model_validate(entry["config"])
        assert "send_platform_message" not in config.tool_names
        assert all(slot.key and not slot.required for slot in config.knowledge_slots)
    fallback = next(entry["config"] for entry in entries if entry["code"] == "reply_fallback_v1")
    assert fallback["knowledge_slots"] == []
    assert "search_knowledge" not in fallback["tool_names"]
