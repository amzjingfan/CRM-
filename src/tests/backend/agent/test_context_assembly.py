"""关键事实逐字保留，普通历史与证据服从总上下文预算。"""

import pytest


def test_context_keeps_literal_money_time_and_drops_low_relevance_evidence() -> None:
    from app.agents.runtime.context import (
        ContextEvidence,
        LiteralFact,
        ModelLimits,
        build_context,
    )

    facts = (
        LiteralFact(key="amount", value="USD 12.34", source_ref="tool:order:1"),
        LiteralFact(key="deadline", value="2026-10-31 12:00 UTC", source_ref="file:v2:chunk1"),
    )
    context = build_context(
        literal_facts=facts,
        evidence=(
            ContextEvidence(source_ref="file:v2:chunk1", text="退货申请需经平台审核。", relevance=0.9),
            ContextEvidence(source_ref="file:v2:chunk2", text="无关商品说明。" * 400, relevance=0.1),
        ),
        recent_history=("买家询问订单",),
        session_summary="此前讨论过物流",
        limits=ModelLimits(context_window_tokens=300, output_reserve_tokens=50, safety_margin_tokens=50),
        base_prompt_tokens=50,
    )
    assert context.literal_facts == facts
    assert "USD 12.34" in context.rendered
    assert "2026-10-31 12:00 UTC" in context.rendered
    assert "退货申请需经平台审核" in context.rendered
    assert "无关商品说明" not in context.rendered
    assert context.used_tokens <= 150


def test_critical_fact_over_budget_never_truncates_original() -> None:
    from app.agents.runtime.context import ContextBudgetExceeded, LiteralFact, ModelLimits, build_context

    with pytest.raises(ContextBudgetExceeded) as error:
        build_context(
            literal_facts=(LiteralFact(key="policy", value="政策原文" * 1000, source_ref="file:v2:1"),),
            evidence=(),
            recent_history=(),
            session_summary="",
            limits=ModelLimits(context_window_tokens=100, output_reserve_tokens=30, safety_margin_tokens=20),
            base_prompt_tokens=20,
        )
    assert error.value.reason_code == "critical_facts_over_budget"
