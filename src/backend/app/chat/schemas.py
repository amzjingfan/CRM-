"""AI 建议和 SSE 公开类型。"""

import uuid
from typing import Literal

from pydantic import BaseModel, Field


class SuggestionRequest(BaseModel):
    trigger_message_id: uuid.UUID | None = None


class ChatQueryRequest(SuggestionRequest):
    session_id: uuid.UUID
    reply_mode: Literal["single", "review_plan"] = "single"


class SuggestionCitation(BaseModel):
    document_id: uuid.UUID
    chunk_id: uuid.UUID
    score: float
    source_label: str


class SuggestionTranslation(BaseModel):
    """公开翻译辅助信息，不暴露 Provider、模型、Token 或原始模型响应。"""

    trigger_message_id: uuid.UUID
    source_text_sha256: str
    source_language: Literal["zh-CN", "en", "mixed", "unknown"]
    target_language: Literal["zh-CN", "en"]
    message_translation: str
    draft_translation: str | None
    prompt_version: str


class SuggestionView(BaseModel):
    agent_run_id: uuid.UUID
    content: str | None
    reply_parts: list[str] = Field(default_factory=list)
    logistics_order_numbers: list[str] = Field(default_factory=list)
    trigger_message_id: uuid.UUID | None = None
    reason_codes: list[str] = Field(default_factory=list)
    intent: str | None
    confidence: float
    action: str
    terminal_state: str
    requires_human: bool
    transfer_performed: bool
    send_performed: Literal[False] = False
    citations: list[SuggestionCitation]
    translation: SuggestionTranslation | None = None
    translation_error_code: str | None = None
    trace_id: str
    demo_mode: bool = False
    demo_scenario: str | None = None
