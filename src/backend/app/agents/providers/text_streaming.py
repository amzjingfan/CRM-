"""模型原生流的内部增量协议；工具参数不能直接作为可发送正文。"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class ModelStreamDelta:
    kind: Literal["text", "tool_arguments"]
    text: str = ""
    tool_index: int | None = None
    tool_id: str | None = None
    tool_name: str | None = None
    arguments_delta: str = ""


ModelDeltaCallback = Callable[[ModelStreamDelta], Awaitable[None]]
