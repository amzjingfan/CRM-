"""REAL-AI-05 版本化真实模型评测契约测试。"""

import json
import uuid
from decimal import Decimal
from pathlib import Path

import pytest

from app.agent.phase4_evaluation import AgentMetricAction
from app.agent.providers.base import LLMProvider, OutputT, ProviderResult, StructuredRequest
from app.agent.real_model_evaluation import (
    REAL_MODEL_DATASET_VERSION,
    REAL_MODEL_REQUIRED_CATEGORIES,
    RealModelEvaluationOutput,
    RealModelSampleResult,
    build_evaluation_report,
    build_real_model_evaluation_payload,
    load_real_model_evaluation_cases,
    load_verified_real_model_evaluation_dataset,
    run_real_model_evaluation,
)
from app.agent.security import PromptSafetyState, evaluate_prompt_safety

DATASET_PATH = Path("evals/real-model-v1.0.0.jsonl")
MANIFEST_PATH = Path("evals/real-model-v1.0.0.manifest.json")


def test_versioned_real_model_dataset_covers_required_categories() -> None:
    """版本化数据集必须覆盖计划规定的全部回复、翻译和营销风险类别。"""
    cases = load_real_model_evaluation_cases(DATASET_PATH)

    assert {case.category for case in cases} == REAL_MODEL_REQUIRED_CATEGORIES
    assert {case.dataset_version for case in cases} == {REAL_MODEL_DATASET_VERSION}
    assert len({case.sample_id for case in cases}) == len(cases)


def test_registered_evaluation_payload_is_allowed_but_mutation_fails_closed() -> None:
    """只有冻结数据集的逐字载荷可以越过外部 Provider 的最终 DLP 边界。"""
    cases = load_real_model_evaluation_cases(DATASET_PATH)
    payload = build_real_model_evaluation_payload(cases[0])

    assert all(
        evaluate_prompt_safety(build_real_model_evaluation_payload(case)).state == PromptSafetyState.ALLOWED
        for case in cases
    )

    mutated = json.loads(payload)
    mutated["customer_message"] = "未登记的客户自由文本"
    decision = evaluate_prompt_safety(json.dumps(mutated, ensure_ascii=False, separators=(",", ":")))

    assert decision.state != PromptSafetyState.ALLOWED


def test_evaluation_output_never_allows_side_effects() -> None:
    """评测输出只能形成草稿或转人工，模型不能声明已经执行平台发送。"""
    with pytest.raises(ValueError):
        RealModelEvaluationOutput.model_validate(
            {
                "decision": "auto_reply",
                "content": "测试草稿",
                "language": "zh-CN",
                "reason_code": "grounded_draft",
                "business_claims": [],
                "send_performed": True,
            }
        )


def test_report_contains_required_low_sensitivity_fields_and_security_counts() -> None:
    """聚合报告必须可追溯版本，同时统计危险漏放和合法误拦截。"""
    results = [
        _sample_result("danger-1", risk_level="dangerous", expected="transfer_human", actual="auto_reply"),
        _sample_result("legal-1", risk_level="legitimate", expected="human_review", actual="transfer_human"),
        _sample_result("normal-1", risk_level="normal", expected="auto_reply", actual="auto_reply", passed=True),
    ]

    report = build_evaluation_report(
        results,
        run_id="11111111-1111-4111-8111-111111111111",
        model="deepseek-test",
        prompt_version="real-model-eval-v1.0.1",
        policy_version="prompt-dlp-v1.3.0",
        dataset_version=REAL_MODEL_DATASET_VERSION,
    )

    assert report.metrics.dangerous_escape_count == 1
    assert report.metrics.legal_false_block_count == 1
    assert report.metrics.accuracy == pytest.approx(1 / 3)
    assert report.metrics.p95_first_output_latency_ms == 300
    assert report.metrics.p99_total_latency_ms == 400
    serialized = report.model_dump(mode="json")
    assert set(serialized["samples"][0]) >= {
        "model",
        "prompt_version",
        "policy_version",
        "dataset_version",
        "run_id",
        "sample_id",
        "input_hash",
        "output_hash",
        "decision",
        "failure_reason",
        "first_output_latency_ms",
        "total_latency_ms",
        "token_usage",
    }
    assert "customer_message" not in json.dumps(serialized, ensure_ascii=False)


@pytest.mark.asyncio
async def test_real_model_runner_grades_structured_claim_literals() -> None:
    """Literal 类型的声明值必须可参与判分，不能因错误假设为 Enum 中断整轮评测。"""
    dataset = load_verified_real_model_evaluation_dataset(DATASET_PATH, MANIFEST_PATH)
    report = await run_real_model_evaluation(
        dataset,
        _GroundedOrderProvider(),
        run_id=uuid.UUID("22222222-2222-4222-8222-222222222222"),
        app_env="development",
        input_cost_per_million_usd=Decimal("0.44"),
        output_cost_per_million_usd=Decimal("1.32"),
        pricing_version="deepseek-v4-2026-08-16-peak-cache-miss",
        pricing_basis="conservative_peak_cache_miss",
    )

    assert report.samples[0].passed is True
    assert report.samples[0].failure_reason is None


class _GroundedOrderProvider(LLMProvider):
    """返回一个合法订单声明的低成本 Provider 替身。"""

    provider_name = "test"
    model_name = "deepseek-v4-flash"

    async def generate_structured(
        self,
        request: StructuredRequest,
        response_schema: type[OutputT],
    ) -> ProviderResult[OutputT]:
        """返回与首条冻结样本一致的结构化结果。"""
        output = response_schema.model_validate(
            {
                "decision": "auto_reply",
                "content": "演示订单正在处理中。",
                "language": "zh-CN",
                "reason_code": "grounded_draft",
                "business_claims": [
                    {
                        "subject_type": "order",
                        "subject_id": "[SYNTHETIC_ORDER]",
                        "action": "report_status",
                        "tense": "present",
                        "polarity": "affirmed",
                        "condition": "actual",
                        "evidence_type": "tool_call",
                        "evidence_id": "10000000-0000-4000-8000-000000000001",
                        "confidence": 0.9,
                    }
                ],
                "send_performed": False,
            }
        )
        return ProviderResult(
            provider=self.provider_name,
            model=self.model_name,
            parsed_output=output,
            input_tokens=10,
            output_tokens=5,
            latency_ms=100,
            provider_request_id=None,
        )


def _sample_result(
    sample_id: str,
    *,
    risk_level: str,
    expected: AgentMetricAction,
    actual: AgentMetricAction,
    passed: bool = False,
) -> RealModelSampleResult:
    """构造不含正文的低敏指标样本。"""
    return RealModelSampleResult.model_validate(
        {
            "model": "deepseek-test",
            "prompt_version": "real-model-eval-v1.0.1",
            "policy_version": "prompt-dlp-v1.3.0",
            "dataset_version": REAL_MODEL_DATASET_VERSION,
            "run_id": "11111111-1111-4111-8111-111111111111",
            "sample_id": sample_id,
            "category": "refund",
            "risk_level": risk_level,
            "expected_decision": expected,
            "decision": actual,
            "input_hash": "a" * 64,
            "output_hash": "b" * 64,
            "failure_reason": None if passed else "DECISION_MISMATCH",
            "first_output_latency_ms": 300,
            "total_latency_ms": 400,
            "token_usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            "passed": passed,
            "provider_failure": False,
            "injected_failure": False,
        }
    )
