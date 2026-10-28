"""模型窗口按配置选择，工具续传和汇总每次都检查完整请求预算。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agents.providers.tool_calling import ToolTurn
from app.agents.runtime.context import ContextBudgetExceeded, ModelLimits
from app.shared.config.settings import Settings


def test_router_reserves_catalog_capacity_before_adding_long_history() -> None:
    from app.agents.runtime.context import count_tokens
    from app.agents.runtime.execution import build_routing_context

    limits = ModelLimits(8192, 1024, 1024)
    context, catalog_budget = build_routing_context(
        "那这个订单呢",
        tuple("此前在问包裹状态。" * 100 for _ in range(50)),
        "客户此前在问包裹",
        limits,
    )
    assert count_tokens(context) + catalog_budget + 1024 + count_tokens("那这个订单呢") <= limits.input_limit
    assert catalog_budget > 0


def test_selected_model_uses_its_configured_context_window() -> None:
    from app.agents.providers.factory import model_limits

    settings = Settings(
        _env_file=None,
        LLM_PRIMARY_PROVIDER="deepseek",
        LLM_PRIMARY_MODEL="primary",
        LLM_FALLBACK_PROVIDER="openai",
        LLM_FALLBACK_MODEL="fallback",
        LLM_PRIMARY_CONTEXT_WINDOW_TOKENS=16384,
        LLM_FALLBACK_CONTEXT_WINDOW_TOKENS=32768,
    )
    assert model_limits(settings, "deepseek", "primary").context_window_tokens == 16384
    assert model_limits(settings, "openai", "fallback").context_window_tokens == 32768


@pytest.mark.asyncio
async def test_budget_rechecks_full_tool_history_before_any_provider_call() -> None:
    from app.agents.providers.budget import BudgetedToolProvider

    inner = SimpleNamespace(complete=AsyncMock(return_value=ToolTurn("ok", (), {}, 1, 1)))
    provider = BudgetedToolProvider(inner, ModelLimits(160, 32, 32))
    await provider.complete(messages=({"role": "user", "content": "订单状态"},), tools=(), max_output_tokens=32)
    with pytest.raises(ContextBudgetExceeded, match="model_request_over_budget"):
        await provider.complete(
            messages=(
                {"role": "user", "content": "订单状态"},
                {"role": "tool", "tool_call_id": "call-1", "content": "物流轨迹" * 200},
            ),
            tools=(),
            max_output_tokens=32,
        )
    assert inner.complete.await_count == 1
