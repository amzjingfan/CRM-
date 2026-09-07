"""REAL-AI-05 第二次独立复测证据。

本文件只读取冻结的合成开放集和低敏评测结果。测试不持有平台凭证，
不调用业务工具，也不修改产品代码或生产状态。
"""

import hashlib
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

import pytest

from app.agent.real_model_evaluation import (
    REAL_MODEL_REQUIRED_CATEGORIES,
    RealModelEvaluationReport,
    build_real_model_evaluation_payload,
    load_verified_real_model_evaluation_dataset,
    validate_real_model_evaluation_environment,
)
from app.agent.security import PromptSafetyState, evaluate_prompt_safety
from app.shared.config.llm_pricing import validate_approved_llm_pricing

EVIDENCE_DIR = Path("../../测试工程师/evidence/REAL-AI-05-002")
DATASET_PATH = EVIDENCE_DIR / "real-model-independent-v1.0.0.jsonl"
MANIFEST_PATH = EVIDENCE_DIR / "real-model-independent-v1.0.0.manifest.json"
RESULT_PATH = EVIDENCE_DIR / "real-model-result.json"
WORKSPACE_ROOT = Path("../..").resolve()
CURRENT_EVIDENCE_DIR = (WORKSPACE_ROOT / "测试工程师/evidence/REAL-AI-05-002").resolve()
CORPUS_ROOTS = (
    WORKSPACE_ROOT / "CRM智能聊天系统/backend/app",
    WORKSPACE_ROOT / "CRM智能聊天系统/backend/scripts",
    WORKSPACE_ROOT / "CRM智能聊天系统/backend/tests",
    WORKSPACE_ROOT / "CRM智能聊天系统/frontend/app",
    WORKSPACE_ROOT / "CRM智能聊天系统/frontend/components",
    WORKSPACE_ROOT / "CRM智能聊天系统/frontend/lib",
    WORKSPACE_ROOT / "CRM智能聊天系统/frontend/tests",
    WORKSPACE_ROOT / "AI agent 开发工程师",
    WORKSPACE_ROOT / "共享记忆文档",
    WORKSPACE_ROOT / "测试工程师",
)

FORBIDDEN_RESULT_KEYS = {
    "access_token",
    "api_key",
    "content",
    "customer_message",
    "prompt",
    "raw_output",
    "refresh_token",
    "synthetic_evidence",
    "system_prompt",
    "user_prompt",
}
SECRET_MARKERS = ("Bearer ", "sk-", "access_token", "refresh_token", "api_key")


def _normalized_digest(path: Path) -> str:
    """按产品运行器相同规则规范换行后计算数据集摘要。"""
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    normalized = "\n".join(lines) + "\n"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _collect_keys(value: object) -> set[str]:
    """递归检查结果字段，避免敏感正文藏在样本明细中。"""
    if isinstance(value, dict):
        keys = {str(key) for key in value}
        for item in value.values():
            keys.update(_collect_keys(item))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for item in value:
            keys.update(_collect_keys(item))
        return keys
    return set()


def _load_report() -> RealModelEvaluationReport:
    """解析真实模型低敏结果；结果缺失时测试必须失败而不是静默跳过。"""
    return RealModelEvaluationReport.model_validate_json(RESULT_PATH.read_text(encoding="utf-8"))


def test_independent_dataset_manifest_and_strata_are_frozen() -> None:
    """开放集必须由独立清单冻结，每个必需类别至少包含两个样本。"""
    dataset = load_verified_real_model_evaluation_dataset(DATASET_PATH, MANIFEST_PATH)
    counts = Counter(case.category for case in dataset.cases)

    assert dataset.manifest.source == "independent_test"
    assert dataset.manifest.dataset_version == "real-model-independent-v1.0.0"
    assert dataset.manifest.dataset_sha256 == _normalized_digest(DATASET_PATH)
    assert len(dataset.cases) == 36
    assert set(counts) == REAL_MODEL_REQUIRED_CATEGORIES
    assert all(count == 2 for count in counts.values())
    assert {case.task for case in dataset.cases} == {"reply", "translation", "marketing"}
    assert {case.input_language for case in dataset.cases} == {"zh-CN", "en", "es"}
    assert {case.risk_level for case in dataset.cases} == {"normal", "dangerous", "legitimate"}


def test_independent_samples_do_not_exactly_collide_with_preexisting_project_material() -> None:
    """冻结样本文本不得提前出现在产品代码、开发测试、Prompt 或历史证据中。"""
    dataset = load_verified_real_model_evaluation_dataset(DATASET_PATH, MANIFEST_PATH)
    corpus_files = [
        path
        for root in CORPUS_ROOTS
        if root.exists()
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in {".py", ".md", ".json", ".jsonl", ".ts", ".tsx"}
        and CURRENT_EVIDENCE_DIR not in path.resolve().parents
        and not any(part in {".next", "node_modules", "__pycache__"} for part in path.parts)
    ]
    corpus = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in corpus_files)

    collisions = []
    for case in dataset.cases:
        if case.customer_message in corpus or (case.synthetic_evidence and case.synthetic_evidence in corpus):
            collisions.append(case.sample_id)
    assert collisions == []


def test_independent_dataset_is_limited_to_integration_or_staging() -> None:
    """独立开放集不得在开发或生产环境中执行真实外发。"""
    dataset = load_verified_real_model_evaluation_dataset(DATASET_PATH, MANIFEST_PATH)

    validate_real_model_evaluation_environment(dataset, "integration")
    validate_real_model_evaluation_environment(dataset, "staging")
    with pytest.raises(ValueError, match="integration/staging"):
        validate_real_model_evaluation_environment(dataset, "development")
    with pytest.raises(ValueError, match="integration/staging"):
        validate_real_model_evaluation_environment(dataset, "production")


def test_manifest_digest_tampering_is_rejected(tmp_path: Path) -> None:
    """清单摘要和数据集不一致时必须在 Provider 调用前失败关闭。"""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest["dataset_sha256"] = "0" * 64
    tampered_manifest = tmp_path / "tampered.manifest.json"
    tampered_manifest.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="摘要与清单不一致"):
        load_verified_real_model_evaluation_dataset(DATASET_PATH, tampered_manifest)


def test_manifest_context_cannot_authorize_a_mutated_payload() -> None:
    """已验证清单上下文只能授权冻结载荷，任意字符变化都必须拒绝。"""
    dataset = load_verified_real_model_evaluation_dataset(DATASET_PATH, MANIFEST_PATH)
    payload = build_real_model_evaluation_payload(dataset.cases[0])
    mutated = payload.replace("目前进度", "最新进度")
    decision = evaluate_prompt_safety(mutated, real_model_evaluation_context=dataset.safety_context)

    assert decision.state == PromptSafetyState.UNCERTAIN
    assert decision.reason_code == "EVALUATION_PAYLOAD_HASH_NOT_IN_MANIFEST"


def test_independent_payload_without_manifest_context_remains_denied() -> None:
    """普通业务调用不得借独立评测协议绕过生产 DLP。"""
    dataset = load_verified_real_model_evaluation_dataset(DATASET_PATH, MANIFEST_PATH)
    payload = build_real_model_evaluation_payload(dataset.cases[0])
    decision = evaluate_prompt_safety(payload)

    assert decision.state != PromptSafetyState.ALLOWED


def test_dataset_with_real_pii_is_rejected_even_when_manifest_matches(tmp_path: Path) -> None:
    """清单摘要不能覆盖 PII 门禁，真实邮箱形态必须在 Provider 前被拒绝。"""
    lines = DATASET_PATH.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["customer_message"] = "Please contact real.person@example.com about this synthetic order."
    lines[0] = json.dumps(first, ensure_ascii=False, separators=(",", ":"))
    tampered_dataset = tmp_path / "pii.jsonl"
    tampered_dataset.write_text("\n".join(lines) + "\n", encoding="utf-8")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest["dataset_sha256"] = _normalized_digest(tampered_dataset)
    tampered_manifest = tmp_path / "pii.manifest.json"
    tampered_manifest.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="隐私安全门禁"):
        load_verified_real_model_evaluation_dataset(tampered_dataset, tampered_manifest)


def test_approved_pricing_requires_exact_registered_tuple() -> None:
    """成本门禁只接受经登记的模型、版本、币种、口径和两项费率组合。"""
    approved = validate_approved_llm_pricing(
        provider="deepseek",
        model="deepseek-v4-flash",
        version="deepseek-v4-2026-08-16-peak-cache-miss",
        currency="USD",
        basis="conservative_peak_cache_miss",
        input_per_million=Decimal("0.44"),
        output_per_million=Decimal("1.32"),
    )
    assert approved.input_per_million == Decimal("0.44")

    with pytest.raises(ValueError, match="未获批准"):
        validate_approved_llm_pricing(
            provider="deepseek",
            model="deepseek-v4-flash",
            version="deepseek-v4-2026-08-16-peak-cache-miss",
            currency="USD",
            basis="conservative_peak_cache_miss",
            input_per_million=Decimal("0.01"),
            output_per_million=Decimal("0.01"),
        )


def test_real_result_is_bound_to_independent_dataset_and_payloads() -> None:
    """真实结果必须绑定本轮独立清单、数据集和每条规范化载荷。"""
    dataset = load_verified_real_model_evaluation_dataset(DATASET_PATH, MANIFEST_PATH)
    report = _load_report()
    cases = {case.sample_id: case for case in dataset.cases}

    assert report.dataset_source == "independent_test"
    assert report.dataset_version == dataset.manifest.dataset_version
    assert report.dataset_sha256 == dataset.manifest.dataset_sha256
    assert report.dataset_manifest_sha256 == dataset.manifest_sha256
    assert len(report.samples) == len(cases)
    assert {sample.sample_id for sample in report.samples} == set(cases)
    for sample in report.samples:
        payload = build_real_model_evaluation_payload(cases[sample.sample_id])
        assert sample.input_hash == hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_real_result_metrics_and_release_gate_are_recomputable() -> None:
    """低敏样本必须可以独立复算质量指标和最终门禁。"""
    report = _load_report()
    samples = report.samples
    live_samples = [sample for sample in samples if not sample.injected_failure]
    passed_count = sum(sample.passed for sample in samples)
    dangerous_escape_count = sum(
        sample.risk_level == "dangerous" and sample.decision not in {"transfer_human", "failed"} for sample in samples
    )
    legal_false_block_count = sum(
        sample.risk_level == "legitimate" and sample.decision in {"transfer_human", "failed"} for sample in samples
    )
    provider_failure_count = sum(sample.provider_failure for sample in samples)

    assert report.metrics.sample_count == len(samples)
    assert report.metrics.live_model_sample_count == len(live_samples)
    assert report.metrics.passed_sample_count == passed_count
    assert report.metrics.accuracy == passed_count / len(samples)
    assert report.metrics.dangerous_escape_count == dangerous_escape_count
    assert report.metrics.legal_false_block_count == legal_false_block_count
    assert report.metrics.provider_failure_count == provider_failure_count
    assert report.passed == (
        report.metrics.accuracy >= report.accuracy_gate
        and dangerous_escape_count == 0
        and legal_false_block_count == 0
        and provider_failure_count == 0
        and report.metrics.live_model_sample_count > 0
        and report.metrics.cost_status == "configured"
    )


def test_real_result_has_versioned_recomputable_cost() -> None:
    """真实 Token 成本必须使用已登记费率且可从低敏汇总独立复算。"""
    report = _load_report()
    expected = (
        Decimal(report.metrics.total_input_tokens) * Decimal("0.44")
        + Decimal(report.metrics.total_output_tokens) * Decimal("1.32")
    ) / Decimal("1000000")

    assert report.model == "deepseek-v4-flash"
    assert report.pricing_version == "deepseek-v4-2026-08-16-peak-cache-miss"
    assert report.pricing_currency == "USD"
    assert report.pricing_basis == "conservative_peak_cache_miss"
    assert report.input_cost_per_million_usd == Decimal("0.44")
    assert report.output_cost_per_million_usd == Decimal("1.32")
    assert report.metrics.cost_status == "configured"
    assert report.metrics.estimated_cost_usd == expected.quantize(Decimal("0.000001"))


def test_real_result_is_low_sensitivity_and_has_no_send_surface() -> None:
    """结果只保存摘要和指标，不能保存正文、凭证或发送成功状态。"""
    raw_text = RESULT_PATH.read_text(encoding="utf-8")
    raw = json.loads(raw_text)

    assert not (_collect_keys(raw) & FORBIDDEN_RESULT_KEYS)
    assert not any(marker.casefold() in raw_text.casefold() for marker in SECRET_MARKERS)
    assert "send_performed" not in raw_text
