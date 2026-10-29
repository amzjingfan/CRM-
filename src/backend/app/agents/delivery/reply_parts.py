"""模型提交有序完整答复；部分JSON只成为坐席可见的未复核草稿。"""

from collections.abc import Awaitable, Callable

from langchain_core.tools import tool
from langchain_core.utils.json import parse_partial_json
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.agents.providers.text_streaming import ModelStreamDelta
from app.agents.providers.tool_calling import ToolTurn
from app.agents.runtime.output import plain_text_answer, platform_character_count

DraftPartSink = Callable[[int, str], Awaitable[None]]


class ReplyPartsOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    texts: list[str] = Field(
        min_length=1, description="按答复顺序排列的完整纯文本，每条聚焦当前买家所问的一个或相近事项"
    )

    @model_validator(mode="after")
    def bounded_texts(self) -> "ReplyPartsOutput":
        if (
            any(not text.strip() for text in self.texts)
            or sum(platform_character_count(text) for text in self.texts) > 16_000
        ):
            raise ValueError("答复段不能为空且总内容必须在运行预算内")
        return self


@tool("submit_reply_parts", args_schema=ReplyPartsOutput)
async def submit_reply_parts(texts: list[str]) -> dict[str, object]:
    """提交给当前买家消息的有序答复。简单问题只一条，多个独立问题分条；不混答其他消息，不输出工具/审核说明。每条完整、简洁、跟随买家语言。物流正文仅最新状态和时间，完整轨迹由物流卡片展示。此函数不发送消息。"""
    return {"texts": texts}


def parts_from_turn(turn: ToolTurn) -> tuple[str, ...]:
    if len(turn.calls) != 1 or turn.calls[0].name != submit_reply_parts.name:
        raise ValueError("invalid_reply_parts_submission")
    return tuple(ReplyPartsOutput.model_validate(turn.calls[0].arguments).texts)


class ReplyDraftCollector:
    """按tool index累积JSON，仅把白名单字段的文本快照送给审阅栏。"""

    def __init__(self, sink: DraftPartSink, *, literal_values: tuple[str, ...] = ()) -> None:
        self.sink = sink
        self.literal_values = literal_values
        self.arguments: dict[int, str] = {}
        self.names: dict[int, str] = {}
        self.last_parts: dict[int, str] = {}
        self.reply_tool_index: int | None = None

    async def __call__(self, delta: ModelStreamDelta) -> None:
        if delta.kind != "tool_arguments" or delta.tool_index is None:
            return
        index = delta.tool_index
        if delta.tool_name is not None:
            self.names[index] = delta.tool_name
        self.arguments[index] = self.arguments.get(index, "") + delta.arguments_delta
        if sum(len(value) for value in self.arguments.values()) > 64_000:
            raise ValueError("reply_draft_over_budget")
        if self.names.get(index) != submit_reply_parts.name:
            return
        if self.reply_tool_index is None:
            self.reply_tool_index = index
        if self.reply_tool_index != index:
            return
        try:
            partial = parse_partial_json(self.arguments[index])
        except ValueError:
            return
        if not isinstance(partial, dict) or not isinstance(partial.get("texts"), list):
            return
        for part_index, value in enumerate(partial["texts"]):
            if not isinstance(value, str):
                continue
            # JSON流可能停在emoji的一半；只等完整码点显示，不把孤立代理项发成非法UTF-8。
            display = value.encode("utf-16-le", errors="surrogatepass").decode("utf-16-le", errors="ignore")
            text = plain_text_answer(display, literal_values=self.literal_values)
            if text and self.last_parts.get(part_index) != text:
                self.last_parts[part_index] = text
                await self.sink(part_index, text)
