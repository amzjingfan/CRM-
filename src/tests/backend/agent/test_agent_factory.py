"""共享模型连接池与逐请求文件检索端口。"""

import uuid
from types import SimpleNamespace
from typing import cast

import pytest
from fastapi import Request
from pytest import MonkeyPatch
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.core import factory
from app.agents.rag.factory import build_bound_file_rag
from app.chat import router as chat_router
from app.chat.schemas import SuggestionRequest, SuggestionView
from app.shared.config.settings import Settings
from app.shared.database.base import User


@pytest.mark.asyncio
async def test_g5_shared_runtime_reuses_transports_but_not_request_state() -> None:
    """并发请求共用 HTTP 连接池，绑定文件检索端口仍逐请求创建。"""
    settings = SimpleNamespace(
        llm_enabled=True,
        embedding_enabled=True,
        llm_primary_provider="deepseek",
        llm_primary_model="deepseek-chat",
        llm_fallback_provider="anthropic",
        llm_fallback_model=None,
        deepseek_api_key=SimpleNamespace(get_secret_value=lambda: "test-key"),
        deepseek_base_url="https://example.invalid",
        deepseek_thinking_enabled=False,
        llm_timeout_seconds=15.0,
        retrieval_model_service_url="http://127.0.0.1:8010",
        retrieval_model_service_token=SimpleNamespace(get_secret_value=lambda: "test-token"),
        embedding_provider="local_bge",
        embedding_model="BAAI/bge-m3",
        embedding_dimensions=1024,
        embedding_timeout_seconds=10.0,
        embedding_max_attempts=1,
        embedding_batch_size=16,
        reranker_max_attempts=1,
        llm_max_attempts=2,
        llm_max_output_tokens=256,
        rag_dense_top_k=20,
        rag_lexical_top_k=20,
        rag_candidate_top_k=20,
        rag_top_k=5,
        rag_rrf_k=60,
        rag_min_score=0.52,
        rag_min_lexical_score=0.0,
        rag_max_context_tokens=800,
        ai_translation_enabled=False,
        agent_auto_reply_threshold=0.8,
        agent_human_review_threshold=0.6,
    )
    runtime = factory.build_shared_agent_runtime(cast(Settings, settings))
    assert runtime is not None
    first = build_bound_file_rag(cast(Settings, settings), runtime)
    second = build_bound_file_rag(cast(Settings, settings), runtime)

    assert first.embedding_service is second.embedding_service
    assert first.reranking_service is second.reranking_service
    assert first.search_port is not second.search_port

    provider_client = runtime.primary_provider._client
    retrieval_client = runtime.retrieval_client._client
    await runtime.aclose()
    assert provider_client.is_closed
    assert retrieval_client.is_closed
    settings.llm_fallback_model = "claude-test"
    assert factory.build_shared_agent_runtime(cast(Settings, settings)) is None


@pytest.mark.asyncio
async def test_suggestion_route_passes_process_runtime_to_request_workflow(monkeypatch: MonkeyPatch) -> None:
    """普通建议入口传递进程级运行时，避免请求层重新建连接。"""
    runtime = object()
    received: list[object] = []

    async def allow_limits(*_args: object) -> None:
        return None

    async def suggest(*_args: object) -> SuggestionView:
        received.append(_args[-1])
        return SuggestionView(
            agent_run_id=uuid.uuid4(),
            content="安全草稿",
            intent="faq",
            confidence=0.9,
            action="human_review",
            terminal_state="completed",
            requires_human=True,
            transfer_performed=False,
            citations=[],
            trace_id="trace",
        )

    monkeypatch.setattr(chat_router, "_enforce_chat_limits", allow_limits)
    monkeypatch.setattr(chat_router, "suggest_for_user", suggest)
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(agent_runtime=runtime)), state=SimpleNamespace()
    )
    await chat_router.suggest(
        uuid.uuid4(),
        SuggestionRequest(),
        cast(Request, request),
        cast(AsyncSession, object()),
        cast(User, object()),
    )
    assert received == [runtime]
