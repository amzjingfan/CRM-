"""十二项工具目录、参数边界与分类的行为契约。"""

import pytest
from pydantic import ValidationError


def test_catalog_covers_business_tools_logistics_notification_and_four_confirmation_proposals() -> None:
    from app.agents.tools.metadata import TOOL_METADATA, ToolCatalogView, catalog_view

    result = catalog_view(permissions={item.permission for item in TOOL_METADATA.values()}, scopes=set())
    assert isinstance(result, ToolCatalogView)
    assert [group.title for group in result.groups] == [
        "订单与物流",
        "商品与优惠",
        "售后服务",
        "客户与会话",
        "知识检索",
        "人工协作",
    ]
    assert len(result.tools) == 17
    assert sum(item.operation == "read" for item in result.tools) == 10
    assert sum(item.operation == "internal_write" for item in result.tools) == 2
    assert sum(item.operation == "confirmation" for item in result.tools) == 4
    assert sum(item.operation == "notification" for item in result.tools) == 1
    assert result.tools[0].missing_scopes


def test_config_accepts_all_catalog_names_but_rejects_unknown_names() -> None:
    from app.agents.management.schemas import AgentConfigUpdate
    from app.agents.tools.metadata import TOOL_METADATA

    assert len(AgentConfigUpdate(enabled_tools=list(TOOL_METADATA)).enabled_tools) == 17
    with pytest.raises(ValidationError):
        AgentConfigUpdate(enabled_tools=["arbitrary_http"])


def test_selection_uses_candidate_refs_not_trusted_identifiers() -> None:
    from app.agents.tools.arguments import OrderSelectionArguments, ProductSelectionArguments

    assert OrderSelectionArguments(order_ref="o1").order_ref == "o1"
    with pytest.raises(ValidationError):
        OrderSelectionArguments(order_id="other-store")
    with pytest.raises(ValidationError):
        OrderSelectionArguments(order_ref="1234567890123456789")
    with pytest.raises(ValidationError):
        OrderSelectionArguments(order_number="5764296284738123456")
    with pytest.raises(ValidationError):
        ProductSelectionArguments(product_ref="1729382256910270465")
    with pytest.raises(ValidationError):
        ProductSelectionArguments(product_ref="p1", product_number="1729382256910270465")


@pytest.mark.asyncio
async def test_complete_configured_catalog_uses_function_call_schemas_without_trusted_ids() -> None:
    import uuid
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from app.agents.tools.catalog import AgentToolContext, build_agent_tools, invoke_selected_tool
    from app.agents.tools.metadata import TOOL_METADATA

    business = SimpleNamespace(invoke=AsyncMock(return_value={"status": "succeeded", "facts": {"count": 0}}))
    shared = SimpleNamespace(execute=AsyncMock())
    search = AsyncMock(return_value={"status": "succeeded", "hits": []})
    context = AgentToolContext(uuid.uuid4(), uuid.uuid4(), None, uuid.uuid4(), frozenset(), "test")
    tools = build_agent_tools(
        tuple(TOOL_METADATA), context=context, executor=shared, business_executor=business, knowledge_search=search
    )
    assert len(tools) == 17 and len({item.name for item in tools}) == 17
    for item in tools:
        fields = item.args_schema.model_json_schema().get("properties", {})
        assert not {"store_id", "customer_id", "conversation_id", "order_id", "product_id"}.intersection(fields)
    selected = next(item for item in tools if item.name == "search_products")
    assert (await invoke_selected_tool(selected, {"query": "band"}))["status"] == "succeeded"
    assert business.invoke.await_args.args[0] == "search_products"
    proposal = next(item for item in tools if item.name == "send_platform_message")
    assert (await invoke_selected_tool(proposal, {}))["status"] == "human_confirmation_required"
    shared.execute.assert_not_awaited()


def test_structured_facts_from_distinct_queries_and_pages_are_all_preserved() -> None:
    import uuid

    from app.agents.orchestration.aggregator import _conflicting_facts
    from app.agents.orchestration.coordinator import SpecialistResult
    from app.agents.runtime.worker import _verified_facts
    from app.agents.tools.loop import ToolObservation

    first = ToolObservation(
        "page-one", "query_logistics", "succeeded", {"events": [{"description": "Arrived"}]}, "a" * 16
    )
    second = ToolObservation(
        "page-two", "query_logistics", "succeeded", {"events": [{"description": "Departed"}]}, "b" * 16
    )
    facts = _verified_facts((first, second))
    assert len(facts) == 2 and "Arrived" in str(facts) and "Departed" in str(facts)
    assert not _conflicting_facts(
        (
            SpecialistResult(uuid.uuid4(), "one", verified_facts=_verified_facts((first,))),
            SpecialistResult(uuid.uuid4(), "two", verified_facts=_verified_facts((second,))),
        )
    )
