"""模型可见工具目录与可信执行边界。"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.tools.contracts import ToolResult


@pytest.mark.asyncio
async def test_all_configured_tools_use_langchain_tool_metadata_but_only_read_executes() -> None:
    from app.agents.tools.catalog import AgentToolContext, build_agent_tools, invoke_selected_tool

    executor = SimpleNamespace(
        execute=AsyncMock(
            return_value=ToolResult(tool_call_id=uuid.uuid4(), status="succeeded", data={"status": "shipped"})
        )
    )
    context = AgentToolContext(
        store_id=uuid.uuid4(),
        agent_run_id=uuid.uuid4(),
        order_id="trusted-order",
        customer_id=uuid.uuid4(),
        permissions=frozenset({"orders.view"}),
        trace_id="trace",
    )
    names = (
        "query_logistics",
        "send_platform_message",
        "query_order",
        "query_customer_profile",
        "update_shipping_address",
        "send_coupon",
        "transfer_to_human",
    )
    tools = build_agent_tools(names, context=context, executor=executor)
    assert tuple(tool.name for tool in tools) == names
    assert all(tool.description for tool in tools)
    assert tools[0].args_schema is not None
    assert "order_id" not in tools[0].args_schema.model_json_schema().get("properties", {})

    read = await invoke_selected_tool(tools[0], {})
    assert "succeeded" in str(read)
    invocation = executor.execute.await_args.args[0]
    assert invocation.arguments == {"order_id": "trusted-order"}
    assert invocation.context.store_id == context.store_id

    proposal = await invoke_selected_tool(tools[1], {})
    assert "human_confirmation_required" in str(proposal)
    assert executor.execute.await_count == 1


@pytest.mark.asyncio
async def test_model_cannot_supply_order_or_customer_id_and_missing_context_fails_closed() -> None:
    from app.agents.tools.catalog import AgentToolContext, build_agent_tools, invoke_selected_tool

    executor = SimpleNamespace(execute=AsyncMock())
    context = AgentToolContext(
        store_id=uuid.uuid4(),
        agent_run_id=uuid.uuid4(),
        order_id=None,
        customer_id=None,
        permissions=frozenset({"orders.view"}),
        trace_id="trace",
    )
    tool = build_agent_tools(("query_order",), context=context, executor=executor)[0]
    assert "context_unavailable" in str(await invoke_selected_tool(tool, {}))
    executor.execute.assert_not_awaited()
    with pytest.raises(ValidationError):
        await invoke_selected_tool(tool, {"order_id": "other-shop-order"})


@pytest.mark.asyncio
async def test_tool_result_omits_resource_ids_and_blocks_sensitive_free_text() -> None:
    from app.agents.tools.catalog import AgentToolContext, build_agent_tools, invoke_selected_tool

    executor = SimpleNamespace(
        execute=AsyncMock(
            return_value=ToolResult(
                tool_call_id=uuid.uuid4(),
                status="succeeded",
                data={
                    "order_id": str(uuid.uuid4()),
                    "external_order_id": "external-123",
                    "tracking_status": "in_transit",
                    "latest_tracking_description": "Ship to 123 Main Street, New York, NY 10001",
                },
            )
        )
    )
    context = AgentToolContext(
        store_id=uuid.uuid4(),
        agent_run_id=uuid.uuid4(),
        order_id="trusted",
        customer_id=None,
        permissions=frozenset({"orders.view"}),
        trace_id="trace",
    )
    selected = build_agent_tools(("query_logistics",), context=context, executor=executor)[0]
    result = await invoke_selected_tool(selected, {})
    assert "in_transit" in str(result)
    assert "external-123" not in str(result)
    assert "Main Street" not in str(result)


@pytest.mark.asyncio
async def test_bound_knowledge_is_a_function_tool_with_explicit_query() -> None:
    from app.agents.tools.catalog import AgentToolContext, build_agent_tools, invoke_selected_tool

    context = AgentToolContext(
        store_id=uuid.uuid4(),
        agent_run_id=uuid.uuid4(),
        order_id=None,
        customer_id=None,
        permissions=frozenset(),
        trace_id="trace",
    )
    search = AsyncMock(return_value={"hits": [{"chunk_id": "safe-chunk", "content": "需人工审核"}]})
    catalog = build_agent_tools(
        (), context=context, executor=SimpleNamespace(execute=AsyncMock()), knowledge_search=search
    )
    assert [item.name for item in catalog] == ["search_knowledge"]
    assert "query" in catalog[0].args_schema.model_json_schema()["properties"]
    result = await invoke_selected_tool(catalog[0], {"query": "退货政策"})
    assert "需人工审核" in str(result)
    search.assert_awaited_once_with("退货政策")
