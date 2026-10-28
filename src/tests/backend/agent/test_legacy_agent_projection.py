"""旧配置切换到动态 Agent 时只使用安全七段提示词，不回落 FAQ。"""

import uuid
from types import SimpleNamespace

from app.agents.management import repository
from app.agents.prompts.compiler import verify_published_prompt


def test_legacy_published_config_gets_safe_function_calling_projection(monkeypatch) -> None:
    store_id = uuid.uuid4()
    config = SimpleNamespace(
        id=uuid.uuid4(),
        store_id=store_id,
        name="物流专员",
        code="shipping",
        description="只读订单与物流",
        enabled_tools=["query_order", "query_logistics"],
        knowledge_scope={"agent_type": "service", "file_ids": []},
        draft_model_provider=None,
        draft_model_name=None,
    )
    legacy = SimpleNamespace(
        version=1,
        name=config.name,
        code=config.code,
        description=config.description,
        agent_type="service",
        model_provider=None,
        model_name=None,
        prompt_sections={},
        prompt_hash=None,
        tool_names=config.enabled_tools,
        file_ids=[],
        ready_for_v2=False,
    )
    monkeypatch.setattr(
        repository,
        "get_settings",
        lambda: SimpleNamespace(llm_primary_provider="deepseek", llm_primary_model="deepseek-chat"),
    )

    projected = repository._project(config, legacy)

    assert projected.ready_for_v2
    assert projected.config_version == 1
    assert projected.model_provider == "deepseek"
    assert projected.model_name == "deepseek-chat"
    assert projected.tool_names == ("query_order", "query_logistics")
    assert projected.file_ids == ()
    assert projected.prompt_hash
    assert "FAQ" not in verify_published_prompt(projected.prompt_sections, projected.prompt_hash).text


def test_explicit_published_version_is_not_overwritten_by_compatibility(monkeypatch) -> None:
    config = SimpleNamespace(
        id=uuid.uuid4(),
        store_id=uuid.uuid4(),
        name="draft changed",
        code="draft",
        description=None,
        enabled_tools=[],
        knowledge_scope={"file_ids": []},
    )
    version = SimpleNamespace(
        version=2,
        name="published",
        code="published",
        description="published scope",
        agent_type="service",
        model_provider="openai",
        model_name="configured-model",
        prompt_sections={"identity": "published"},
        prompt_hash="hash",
        tool_names=["query_order"],
        file_ids=[],
        ready_for_v2=True,
    )
    monkeypatch.setattr(repository, "get_settings", lambda: None)

    projected = repository._project(config, version)

    assert projected.name == "published"
    assert projected.model_name == "configured-model"
    assert projected.prompt_hash == "hash"
