"""原生模型调用前统一检查消息、工具 Schema 和输出保留预算。"""

import json
from typing import Protocol, cast

import tiktoken
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool

from app.agents.orchestration.router import RouteModelPort
from app.agents.providers.text_streaming import ModelDeltaCallback
from app.agents.providers.tool_calling import ToolTurn
from app.agents.runtime.context import ContextBudgetExceeded, ModelLimits

_TOKENIZER = tiktoken.get_encoding("cl100k_base")


class _StreamingPort(Protocol):
    async def complete_streaming(
        self,
        *,
        messages: tuple[dict[str, object], ...],
        tools: tuple[BaseTool, ...],
        max_output_tokens: int,
        on_delta: ModelDeltaCallback,
    ) -> ToolTurn: ...


class BudgetedToolProvider:
    """只检查请求，不截断工具结果或逐字事实；超预算时不触达 SDK。"""

    def __init__(self, inner: RouteModelPort, limits: ModelLimits) -> None:
        self.inner = inner
        self.limits = limits

    async def complete(
        self,
        *,
        messages: tuple[dict[str, object], ...],
        tools: tuple[BaseTool, ...],
        max_output_tokens: int,
    ) -> ToolTurn:
        self._check_budget(messages, tools, max_output_tokens)
        return await self.inner.complete(messages=messages, tools=tools, max_output_tokens=max_output_tokens)

    async def complete_streaming(
        self,
        *,
        messages: tuple[dict[str, object], ...],
        tools: tuple[BaseTool, ...],
        max_output_tokens: int,
        on_delta: ModelDeltaCallback,
    ) -> ToolTurn:
        self._check_budget(messages, tools, max_output_tokens)
        if callable(getattr(self.inner, "complete_streaming", None)):
            return await cast(_StreamingPort, self.inner).complete_streaming(
                messages=messages, tools=tools, max_output_tokens=max_output_tokens, on_delta=on_delta
            )
        # 旧测试端口可继续运行；完整结果不能伪装成原生增量。
        return await self.inner.complete(messages=messages, tools=tools, max_output_tokens=max_output_tokens)

    def _check_budget(
        self, messages: tuple[dict[str, object], ...], tools: tuple[BaseTool, ...], max_output_tokens: int
    ) -> None:
        envelope = json.dumps(
            {"messages": messages, "tools": [convert_to_openai_tool(item) for item in tools]},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        required = len(_TOKENIZER.encode(envelope)) + max_output_tokens + self.limits.safety_margin_tokens
        if max_output_tokens <= 0 or required > self.limits.context_window_tokens:
            raise ContextBudgetExceeded("model_request_over_budget")
