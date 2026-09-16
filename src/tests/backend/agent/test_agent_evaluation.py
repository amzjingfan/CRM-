"""验证意图评测指标计算，防止用不平衡数据掩盖分类退化。"""

import json
import logging
import uuid
from collections import Counter

from _support import TESTS_ROOT

from app.agent.evaluation import EvaluationCase, EvaluationPrediction, calculate_metrics
from app.agent.schemas import ClassificationState, IntentName
from app.shared.logging.setup import JsonFormatter
from scripts.evaluate_intents import build_evaluation_trace_id, load_cases
from scripts.evaluate_rag import load_cases as load_rag_cases


def test_versioned_eval_datasets_live_under_central_test_root() -> None:
    datasets = TESTS_ROOT / "ai" / "datasets"
    assert (datasets / "intent-classifier-v1.0.0.jsonl").is_file()
    assert (datasets / "faq-rag-v1.0.0.jsonl").is_file()
    assert not (TESTS_ROOT.parent / "backend" / "evals").exists()


def test_evaluation_reports_accuracy_per_class_and_abstention_rate() -> None:
    """评测应同时报告五类准确度和边界问题拒判率。"""
    cases = [
        EvaluationCase(case_id="l-1", message="物流", expected_intent=IntentName.LOGISTICS_QUERY),
        EvaluationCase(case_id="r-1", message="退货", expected_intent=IntentName.RETURN_POLICY),
        EvaluationCase(
            case_id="u-1",
            message="未知",
            expected_intent=None,
            expected_state=ClassificationState.UNKNOWN,
        ),
    ]
    predictions = [
        EvaluationPrediction("l-1", IntentName.LOGISTICS_QUERY, ClassificationState.CLASSIFIED, 0.9, 10, 7, 20),
        EvaluationPrediction("r-1", IntentName.GENERAL, ClassificationState.CLASSIFIED, 0.7, 10, 7, 20),
        EvaluationPrediction("u-1", None, ClassificationState.UNKNOWN, 0.2, 10, 7, 20),
    ]

    metrics = calculate_metrics(cases, predictions)

    assert metrics.classified_accuracy == 0.5
    assert metrics.abstention_accuracy == 1.0
    assert metrics.per_intent[IntentName.LOGISTICS_QUERY].recall == 1.0
    assert metrics.per_intent[IntentName.RETURN_POLICY].recall == 0.0
    assert metrics.total_input_tokens == 30
    assert metrics.total_output_tokens == 21


def test_versioned_dataset_has_balanced_100_classified_and_30_abstention_cases() -> None:
    """评测集规模和类别分布必须保持计划约定，防止门禁被静默稀释。"""
    cases = load_cases(TESTS_ROOT / "ai" / "datasets" / "intent-classifier-v1.0.0.jsonl")
    classified = [case for case in cases if case.expected_intent is not None]
    abstention = [case for case in cases if case.expected_intent is None]

    assert len(classified) == 100
    assert len(abstention) == 30
    assert Counter(case.expected_intent for case in classified) == Counter({intent: 20 for intent in IntentName})
    assert Counter(case.expected_state for case in abstention) == Counter(
        {
            ClassificationState.UNKNOWN: 10,
            ClassificationState.MIXED: 10,
            ClassificationState.INSUFFICIENT_CONTEXT: 10,
        }
    )


def test_live_evaluation_trace_id_is_stable_canonical_uuid_without_case_text() -> None:
    """真实评测使用 UUID Trace ID，并通过独立 case_id 字段关联样本语义。"""
    trace_id = build_evaluation_trace_id("synthetic-address-case-001")

    assert str(uuid.UUID(trace_id)) == trace_id
    assert trace_id == build_evaluation_trace_id("synthetic-address-case-001")
    assert "synthetic-address-case-001" not in trace_id

    record = logging.LogRecord("test", logging.INFO, __file__, 1, "deepseek_call_succeeded", (), None)
    record.event = "deepseek_call_succeeded"
    record.trace_id = trace_id
    payload = json.loads(JsonFormatter().format(record))

    assert payload["trace_id"] == trace_id


def test_provider_failure_is_counted_as_error_instead_of_successful_abstention() -> None:
    """供应商失败不得被包装成正确拒判，并且必须在报告中单独计数。"""
    cases = [
        EvaluationCase(
            case_id="unknown-1",
            message="未知问题",
            expected_intent=None,
            expected_state=ClassificationState.UNKNOWN,
        )
    ]
    predictions = [
        EvaluationPrediction(
            "unknown-1",
            None,
            ClassificationState.UNKNOWN,
            0.0,
            0,
            0,
            120,
            error_code="LLM_OUTPUT_INVALID",
        )
    ]

    metrics = calculate_metrics(cases, predictions)

    assert metrics.abstention_accuracy == 0.0
    assert metrics.provider_failure_count == 1
    assert metrics.provider_error_counts == {"LLM_OUTPUT_INVALID": 1}
    assert metrics.confusion_matrix["abstain"]["error"] == 1
    assert metrics.incorrect_cases == [
        {"case_id": "unknown-1", "expected": "unknown", "actual": "error:LLM_OUTPUT_INVALID"}
    ]


def test_versioned_rag_dataset_has_50_grounded_and_20_rejection_cases() -> None:
    """RAG 数据集规模必须保持门禁约定，并且所有 case_id 唯一。"""
    cases = load_rag_cases(TESTS_ROOT / "ai" / "datasets" / "faq-rag-v1.0.0.jsonl")
    grounded = [case for case in cases if case.expected_document_key]
    rejected = [case for case in cases if not case.expected_document_key]

    assert len(grounded) == 50
    assert len(rejected) == 20
    assert len({case.case_id for case in cases}) == 70
