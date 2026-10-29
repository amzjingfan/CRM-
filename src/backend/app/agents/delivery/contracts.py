"""完整复核消息的有序交付边界；生成中草稿不能提交为发送计划。"""

import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from app.workspace.schemas import MessageView


class TextPart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["text"]
    content: str = Field(min_length=1, max_length=2000)


class CardPart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["logistics_card"]
    order_id: str = Field(min_length=1, max_length=200, pattern=r"^[0-9]+$")
    package_id: str | None = Field(default=None, min_length=1, max_length=200, pattern=r"^[0-9]+$")


ReplyPart = Annotated[TextPart | CardPart, Field(discriminator="kind")]


class ReplyBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trigger_message_id: uuid.UUID | None = None
    parts: list[ReplyPart] = Field(min_length=1)
    preview_only: StrictBool = True
    confirmed: StrictBool = False

    @model_validator(mode="after")
    def valid_plan(self) -> "ReplyBatchRequest":
        if not self.preview_only and not self.confirmed:
            raise ValueError("发送前必须显式人工确认")
        seen_card = False
        size = 0
        for part in self.parts:
            if isinstance(part, TextPart):
                units = len(part.content.encode("utf-16-le")) // 2
                if seen_card or not part.content.strip() or units > 2000:
                    raise ValueError("文字需完整且不超过2000字符，并放在卡片之前")
                size += units
            else:
                seen_card = True
                size += len(part.order_id) + len(part.package_id or "") + 32
        if size > 16000:
            raise ValueError("交付计划超出上下文预算")
        return self


class ReplyPartResult(BaseModel):
    index: int
    kind: Literal["text", "logistics_card"]
    status: Literal["pending", "sent", "previewed", "failed", "unknown"]
    message_id: uuid.UUID | None = None
    error_code: str | None = None


class ReplyBatchView(BaseModel):
    id: uuid.UUID
    preview_only: bool
    status: Literal["previewed", "completed", "partial", "failed", "unknown"]
    parts: list[ReplyPartResult]
    messages: list[MessageView]
