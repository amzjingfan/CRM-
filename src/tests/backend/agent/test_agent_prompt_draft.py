"""Agent 草稿模型与七段配置可保存，但发布前仍要校验。"""

from app.agents.management.schemas import AgentConfigCreate, AgentConfigUpdate

SECTIONS = {
    "identity": "身份",
    "service_scope": "范围",
    "tool_rules": "工具",
    "escalation": "升级",
    "language_format": "语言",
    "compliance": "合规",
    "clarification": "澄清",
}


def test_draft_api_accepts_configured_model_and_seven_sections() -> None:
    update = AgentConfigUpdate(
        model_provider="deepseek",
        model_name="deepseek-v4-flash",
        prompt_sections=SECTIONS,
        expected_revision=1,
    )
    assert update.prompt_sections == SECTIONS
    assert update.model_name == "deepseek-v4-flash"


def test_tool_selection_is_not_limited_to_seven_entries_by_schema() -> None:
    payload = AgentConfigCreate.model_validate(
        {
            "store_id": "11111111-1111-1111-1111-111111111111",
            "name": "店铺 Agent",
            "code": "store-agent",
            "enabled_tools": ["query_order"] * 8,
        }
    )
    assert len(payload.enabled_tools) == 8
