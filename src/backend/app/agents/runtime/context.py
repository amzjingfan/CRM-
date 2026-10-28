"""总上下文预算与逐字关键事实分离。"""

import json
import re
from dataclasses import dataclass

import tiktoken

from app.agents.safety.input import prepare_untrusted_text
from app.shared.exceptions.errors import AppError

_TOKENIZER = tiktoken.get_encoding("cl100k_base")


@dataclass(frozen=True, slots=True)
class ModelLimits:
    context_window_tokens: int
    output_reserve_tokens: int
    safety_margin_tokens: int

    @property
    def input_limit(self) -> int:
        available = self.context_window_tokens - self.output_reserve_tokens - self.safety_margin_tokens
        if available <= 0:
            raise ValueError("模型上下文预算无效")
        return available


@dataclass(frozen=True, slots=True)
class LiteralFact:
    key: str
    value: str
    source_ref: str


@dataclass(frozen=True, slots=True)
class ContextEvidence:
    source_ref: str
    text: str
    relevance: float


class ContextBudgetExceeded(Exception):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


@dataclass(frozen=True, slots=True)
class ContextPackage:
    literal_facts: tuple[LiteralFact, ...]
    evidence: tuple[ContextEvidence, ...]
    recent_history: tuple[str, ...]
    session_summary: str
    rendered: str
    used_tokens: int
    dropped_evidence_count: int


_AMOUNT_PATTERN = re.compile(r"^[A-Z]{3} [0-9]{1,12}(?:\.[0-9]{1,2})?$")
_TIME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?::\d{2})? (?:UTC|[+-]\d{2}:\d{2})$")


def _validate_literal_fact(fact: LiteralFact) -> None:
    if not fact.key or not fact.source_ref or not fact.value:
        raise ValueError("关键事实必须附有原值与来源")
    # 金额和 UTC 时间是经业务 Schema 验证的结构化值；通用自由文本 DLP 会把
    # 其数字误认作个人标识。保持原值，但仅允许严格格式和可信字段名。
    if fact.key == "amount" and _AMOUNT_PATTERN.fullmatch(fact.value):
        return
    if fact.key == "deadline" and _TIME_PATTERN.fullmatch(fact.value):
        return
    try:
        sanitized = prepare_untrusted_text(fact.value, source="tool_result")
    except AppError as error:
        raise ContextBudgetExceeded("critical_fact_sensitive") from error
    if sanitized.text != fact.value:
        raise ContextBudgetExceeded("critical_fact_sensitive")


def _render(
    facts: tuple[LiteralFact, ...],
    evidence: list[ContextEvidence],
    history: list[str],
    summary: str,
) -> str:
    return json.dumps(
        {
            "literal_facts": [{"key": fact.key, "value": fact.value, "source_ref": fact.source_ref} for fact in facts],
            "evidence": [{"source_ref": item.source_ref, "text": item.text} for item in evidence],
            "recent_history": history,
            "session_summary": summary,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def count_tokens(text: str) -> int:
    return len(_TOKENIZER.encode(text))


def build_context(
    *,
    literal_facts: tuple[LiteralFact, ...],
    evidence: tuple[ContextEvidence, ...],
    recent_history: tuple[str, ...],
    session_summary: str,
    limits: ModelLimits,
    base_prompt_tokens: int,
) -> ContextPackage:
    """事实不截断；先选高相关证据和近期历史，最后装可压缩摘要。"""
    available = limits.input_limit - base_prompt_tokens
    if available <= 0:
        raise ContextBudgetExceeded("base_prompt_over_budget")
    for fact in literal_facts:
        _validate_literal_fact(fact)
    chosen_evidence: list[ContextEvidence] = []
    chosen_history: list[str] = []
    chosen_summary = ""
    rendered = _render(literal_facts, chosen_evidence, chosen_history, chosen_summary)
    if count_tokens(rendered) > available:
        raise ContextBudgetExceeded("critical_facts_over_budget")

    for candidate in sorted(evidence, key=lambda item: (-item.relevance, item.source_ref)):
        try:
            safe_text = prepare_untrusted_text(candidate.text, source="knowledge_chunk").text
        except AppError:
            continue
        projected = ContextEvidence(candidate.source_ref, safe_text, candidate.relevance)
        trial = _render(literal_facts, [*chosen_evidence, projected], chosen_history, chosen_summary)
        if count_tokens(trial) <= available:
            chosen_evidence.append(projected)
            rendered = trial

    for item in reversed(recent_history):
        try:
            safe_history = prepare_untrusted_text(item, source="user_message").text
        except AppError:
            continue
        trial_history = [safe_history, *chosen_history]
        trial = _render(literal_facts, chosen_evidence, trial_history, chosen_summary)
        if count_tokens(trial) <= available:
            chosen_history = trial_history
            rendered = trial

    if session_summary.strip():
        try:
            safe_summary = prepare_untrusted_text(session_summary, source="session_summary").text
            trial = _render(literal_facts, chosen_evidence, chosen_history, safe_summary)
            if count_tokens(trial) <= available:
                chosen_summary = safe_summary
                rendered = trial
        except AppError:
            pass
    return ContextPackage(
        literal_facts=literal_facts,
        evidence=tuple(chosen_evidence),
        recent_history=tuple(chosen_history),
        session_summary=chosen_summary,
        rendered=rendered,
        used_tokens=count_tokens(rendered),
        dropped_evidence_count=len(evidence) - len(chosen_evidence),
    )
