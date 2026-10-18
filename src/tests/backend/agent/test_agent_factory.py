"""锁定实际运行工厂的 FAQ 关键路径选择。"""

from types import SimpleNamespace
from typing import cast

from pytest import MonkeyPatch
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import factory
from app.agent.workflow_prompt import FAQ_ANSWER_SYSTEM_PROMPT
from app.shared.config.settings import Settings


def test_runtime_factory_uses_parallel_store_scoped_faq_retrieval(monkeypatch: MonkeyPatch) -> None:
    """现场 Agent 应使用已有的分类/检索重叠路径，而非等待检索后再组合分类。"""
    provider = SimpleNamespace(provider_name="fake", model_name="fake")
    monkeypatch.setattr(factory, "build_provider_pair", lambda _: (provider, None))
    monkeypatch.setattr(factory, "build_embedding_service", lambda _: object())
    monkeypatch.setattr(factory, "build_reranking_service", lambda _: object())
    settings = SimpleNamespace(
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

    workflow = factory.build_agent_workflow(cast(AsyncSession, object()), cast(Settings, settings))

    assert workflow.combined_faq_enabled is False


def test_parallel_faq_draft_keeps_content_judgment_separate_from_employee_review() -> None:
    """恢复单节点 FAQ 草稿时，不应把员工必审直接写成内容级拒绝。"""
    assert "FAQ 草稿一律需要人工复核" not in FAQ_ANSWER_SYSTEM_PROMPT
    assert "needs_human 只表示内容是否需要额外人工判断" in FAQ_ANSWER_SYSTEM_PROMPT
    assert "所有草稿仍须员工审核并确认发送" in FAQ_ANSWER_SYSTEM_PROMPT
    assert "独立安全复核" in FAQ_ANSWER_SYSTEM_PROMPT
