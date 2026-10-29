"""动态模型请求使用剩余总预算，SDK 超时仍保留已完成工具进度。"""

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from langchain_core.tools import tool
from openai import APITimeoutError

from app.agents.core.errors import LLMErrorCode, LLMProviderError
from app.agents.providers import factory
from app.agents.providers.tool_calling import DeepSeekToolCallingProvider, OpenAIToolCallingProvider
from app.agents.tools.loop import ToolEvent, run_tool_loop
from app.shared.config.settings import Settings


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_name", ["deepseek", "openai", "anthropic"])
@pytest.mark.parametrize("remaining", [35.0, 1.5, 0.0, -1.0, None])
async def test_native_client_uses_remaining_deadline_without_changing_default_or_retry_budget(
    monkeypatch, provider_name, remaining
) -> None:
    settings = Settings(
        _env_file=None,
        LLM_PRIMARY_PROVIDER=provider_name,
        LLM_PRIMARY_MODEL="configured-model",
        LLM_TIMEOUT_SECONDS=15,
        DEEPSEEK_API_KEY="synthetic-key",
        OPENAI_API_KEY="synthetic-key",
        ANTHROPIC_API_KEY="synthetic-key",
    )
    client = SimpleNamespace(close=AsyncMock())
    sdk = Mock(return_value=client)
    monkeypatch.setattr(factory, "AsyncOpenAI", sdk)
    monkeypatch.setattr(factory, "AsyncAnthropic", sdk)
    monkeypatch.setattr(factory, "monotonic", lambda: 100.0, raising=False)
    kwargs = {} if remaining is None else {"deadline": 100.0 + remaining}

    if remaining is not None and remaining <= 0:
        with pytest.raises(TimeoutError):
            async with factory.tool_provider(settings, provider_name, "configured-model", **kwargs):
                pytest.fail("expired model budget cannot yield a provider")
        sdk.assert_not_called()
        return

    async with factory.tool_provider(settings, provider_name, "configured-model", **kwargs):
        sdk.assert_called_once()
        assert sdk.call_args.kwargs["timeout"] == (15.0 if remaining is None else remaining)
        assert sdk.call_args.kwargs["max_retries"] == 0
    client.close.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_class", [DeepSeekToolCallingProvider, OpenAIToolCallingProvider])
async def test_native_sdk_timeout_has_stable_code_and_no_invented_usage(provider_class) -> None:
    create = AsyncMock(side_effect=APITimeoutError(request=httpx.Request("POST", "https://synthetic.invalid")))
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    with pytest.raises(LLMProviderError) as caught:
        await provider_class(model_name="configured-model", client=client).complete(
            messages=(), tools=(), max_output_tokens=2048
        )
    assert caught.value.code == LLMErrorCode.LLM_TIMEOUT
    assert (caught.value.input_tokens, caught.value.output_tokens) == (0, 0)
    create.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_class", [DeepSeekToolCallingProvider, OpenAIToolCallingProvider])
async def test_native_timeout_keeps_completed_tool_event_and_only_known_usage(provider_class) -> None:
    @tool
    async def read_order() -> dict:
        """读取合成订单状态。"""
        return {"status": "succeeded", "facts": {"status": "shipped"}}

    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="tool_calls",
                message=SimpleNamespace(
                    content=None,
                    tool_calls=[
                        SimpleNamespace(
                            id="order-1", type="function", function=SimpleNamespace(name="read_order", arguments="{}")
                        )
                    ],
                ),
            )
        ],
        usage=SimpleNamespace(prompt_tokens=11, completion_tokens=4),
    )
    create = AsyncMock(
        side_effect=[response, APITimeoutError(request=httpx.Request("POST", "https://synthetic.invalid"))]
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    result = await run_tool_loop(
        provider=provider_class(model_name="configured-model", client=client),
        messages=(),
        tools=(read_order,),
        deadline=time.monotonic() + 5,
        max_output_tokens=2048,
    )

    assert result.answer is None
    assert result.reason_code == "llm_timeout"
    assert result.events == (ToolEvent("order-1", "read_order", "succeeded"),)
    assert result.observations[0].facts == {"status": "shipped"}
    assert (result.input_tokens, result.output_tokens) == (11, 4)
    assert create.await_count == 2
