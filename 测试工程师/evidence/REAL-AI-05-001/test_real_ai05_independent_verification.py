"""REAL-AI-05 测试工程师独立、低敏验证证据。

本文件只读取产品评测数据和开发侧低敏结果，不修改产品代码、不调用平台工具，
也不输出 Prompt、样本文本、模型正文或密钥。新增独立载荷只用于确认当前 DLP
是否允许测试工程师执行未进入开发集的开放集评测。
"""

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agent.real_model_evaluation import (
    REAL_MODEL_DATASET_SHA256,
    REAL_MODEL_REQUIRED_CATEGORIES,
    RealModelEvaluationCase,
    RealModelEvaluationOutput,
    RealModelEvaluationReport,
    build_real_model_evaluation_payload,
    load_real_model_evaluation_cases,
)
from app.agent.security import PromptSafetyState, evaluate_prompt_safety

DATASET_PATH = Path("evals/real-model-v1.0.0.jsonl")
DEVELOPER_RESULT_PATH = Path("evals/results/real-model-v1.0.0-deepseek-20260904-003.json")
TESTER_RESULT_PATH = Path("../../测试工程师/evidence/REAL-AI-05-001/real-model-result.json")
RESULT_PATHS = (DEVELOPER_RESULT_PATH, TESTER_RESULT_PATH)
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


def _normalized_dataset_digest(path: Path) -> str:
    """按产品定义统一换行，独立复算冻结数据集摘要。"""
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    normalized = "\n".join(lines) + "\n"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _collect_keys(value: object) -> set[str]:
    """递归收集低敏结果字段名，避免只检查顶层而漏过样本明细。"""
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


def test_frozen_dataset_digest_categories_and_ids_are_consistent() -> None:
    """数据集摘要、18 个必需类别和样本唯一性必须同时成立。"""
    cases = load_real_model_evaluation_cases(DATASET_PATH)

    assert _normalized_dataset_digest(DATASET_PATH) == REAL_MODEL_DATASET_SHA256
    assert len(cases) == 18
    assert {case.category for case in cases} == REAL_MODEL_REQUIRED_CATEGORIES
    assert len({case.sample_id for case in cases}) == len(cases)


@pytest.mark.parametrize("result_path", RESULT_PATHS)
def test_real_result_is_schema_valid_and_bound_to_dataset_payloads(result_path: Path) -> None:
    """开发侧和测试侧结果必须可解析，且每个输入哈希绑定冻结载荷。"""
    report = RealModelEvaluationReport.model_validate_json(result_path.read_text(encoding="utf-8"))
    cases = {case.sample_id: case for case in load_real_model_evaluation_cases(DATASET_PATH)}

    assert report.dataset_sha256 == REAL_MODEL_DATASET_SHA256
    assert len(report.samples) == len(cases)
    assert {sample.sample_id for sample in report.samples} == set(cases)
    for sample in report.samples:
        payload = build_real_model_evaluation_payload(cases[sample.sample_id])
        assert sample.input_hash == hashlib.sha256(payload.encode("utf-8")).hexdigest()


@pytest.mark.parametrize("result_path", RESULT_PATHS)
def test_real_result_contains_no_forbidden_raw_fields(result_path: Path) -> None:
    """低敏结果不得成为 Prompt、样本文本、模型正文或凭证的第二份存储。"""
    raw = json.loads(result_path.read_text(encoding="utf-8"))

    assert not (_collect_keys(raw) & FORBIDDEN_RESULT_KEYS)


def test_model_cannot_claim_send_side_effect() -> None:
    """评测输出中的发送状态必须固定为 false。"""
    with pytest.raises(ValidationError):
        RealModelEvaluationOutput.model_validate(
            {
                "decision": "human_review",
                "content": "合成测试草稿",
                "language": "zh-CN",
                "reason_code": "policy_grounded",
                "business_claims": [],
                "send_performed": True,
            }
        )


def test_independent_dataset_version_is_rejected_by_product_schema() -> None:
    """记录当前实现无法加载测试工程师独立版本数据集的事实。"""
    base_case = load_real_model_evaluation_cases(DATASET_PATH)[0].model_dump(mode="json")
    base_case["dataset_version"] = "tester-open-set-v1.0.0"
    base_case["sample_id"] = "tester-order-open-001"
    base_case["customer_message"] = "合成开放样本：请核对另一个虚构订单的处理状态。"

    with pytest.raises(ValidationError) as error:
        RealModelEvaluationCase.model_validate(base_case)

    assert any(item["type"] == "literal_error" for item in error.value.errors())


def test_independent_payload_is_not_allowed_to_reach_provider() -> None:
    """即使冒用开发数据集版本，未登记开放样本也必须在 Provider 前失败关闭。"""
    base_case = load_real_model_evaluation_cases(DATASET_PATH)[0].model_dump(mode="json")
    base_case["sample_id"] = "tester-order-open-002"
    base_case["customer_message"] = "合成开放样本：订单尚未确认，请避免声明已经完成。"
    independent_case = RealModelEvaluationCase.model_validate(base_case)
    payload = build_real_model_evaluation_payload(independent_case)
    decision = evaluate_prompt_safety(payload)

    assert decision.state != PromptSafetyState.ALLOWED
    assert decision.reason_code == "UNTRUSTED_STRUCTURED_DATA_REQUIRES_DLP"


def test_current_real_model_result_fails_all_release_gates() -> None:
    """真实结果存在危险漏放、合法误拦截和 Provider 失败时必须拒绝放行。"""
    report = RealModelEvaluationReport.model_validate_json(DEVELOPER_RESULT_PATH.read_text(encoding="utf-8"))

    assert report.passed is False
    assert report.metrics.accuracy < report.accuracy_gate
    assert report.metrics.dangerous_escape_count > 0
    assert report.metrics.legal_false_block_count > 0
    assert report.metrics.provider_failure_count > 0


def test_tester_real_model_result_fails_release_gate() -> None:
    """测试工程师本轮真实运行只要准确率或 Provider 稳定性失败就不得放行。"""
    report = RealModelEvaluationReport.model_validate_json(TESTER_RESULT_PATH.read_text(encoding="utf-8"))

    assert report.passed is False
    assert report.metrics.accuracy < report.accuracy_gate
    assert report.metrics.provider_failure_count > 0
