"""REAL-AI-05 首次独立测试缺陷的回归测试。"""

import hashlib
import json
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from _support import TESTS_ROOT
from pydantic import ValidationError

from app.agent.providers.base import LLMProvider, OutputT, ProviderResult, StructuredRequest
from app.agent.real_model_evaluation import (
    REAL_MODEL_DATASET_VERSION,
    RealModelEvaluationOutput,
    RealModelSampleResult,
    RealModelTokenUsage,
    build_evaluation_report,
    build_real_model_evaluation_request,
    build_real_model_repair_request,
    grade_real_model_evaluation_output,
    load_verified_real_model_evaluation_dataset,
    run_real_model_evaluation,
    validate_real_model_evaluation_environment,
)
from app.agent.security import (
    PROMPT_DLP_POLICY_VERSION,
    REAL_MODEL_EVALUATION_PROMPT_VERSION,
    REAL_MODEL_EVALUATION_REASON_CODES,
    REAL_MODEL_EVALUATION_SYSTEM_PROMPT,
    PromptSafetyState,
    evaluate_real_model_draft_safety,
)
from app.shared.config.settings import Settings
from scripts import evaluate_real_model

DATASETS_ROOT = TESTS_ROOT / "ai" / "datasets"
DATASET_PATH = DATASETS_ROOT / "real-model-v1.0.0.jsonl"


def _write_independent_dataset(
    tmp_path: Path,
    *,
    customer_message: str = "开放集合成样本：请核对虚构订单的处理状态。",
) -> tuple[Path, Path]:
    """从冻结集构造测试工程师拥有的独立版本，不复用产品摘要登记表。"""
    records = [json.loads(line) for line in DATASET_PATH.read_text(encoding="utf-8").splitlines() if line]
    dataset_version = "tester-open-set-v1.0.0"
    for record in records:
        record["dataset_version"] = dataset_version
    records[0]["sample_id"] = "tester-order-open-001"
    records[0]["customer_message"] = customer_message
    normalized = "\n".join(json.dumps(record, ensure_ascii=False, separators=(",", ":")) for record in records) + "\n"
    dataset_path = tmp_path / "tester-open-set-v1.0.0.jsonl"
    dataset_path.write_text(normalized, encoding="utf-8")
    manifest = {
        "schema_version": "1",
        "dataset_version": dataset_version,
        "dataset_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        "sample_count": len(records),
        "source": "independent_test",
    }
    manifest_path = tmp_path / "tester-open-set-v1.0.0.manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return dataset_path, manifest_path


def test_independent_manifest_authorizes_only_verified_synthetic_payload(tmp_path: Path) -> None:
    """独立数据经清单和 DLP 校验后可调用模型，普通生产请求仍不得借此放宽。"""
    dataset_path, manifest_path = _write_independent_dataset(tmp_path)
    dataset = load_verified_real_model_evaluation_dataset(dataset_path, manifest_path)
    case = dataset.cases[0]

    request = build_real_model_evaluation_request(
        case,
        dataset,
        run_id=uuid.UUID("11111111-1111-4111-8111-111111111111"),
    )
    direct_request = StructuredRequest(
        system_prompt=REAL_MODEL_EVALUATION_SYSTEM_PROMPT,
        user_prompt=request.user_prompt,
        trace_id="22222222-2222-4222-8222-222222222222",
        max_output_tokens=1024,
    )

    assert dataset.manifest.source == "independent_test"
    assert request.prompt_safety_state == PromptSafetyState.ALLOWED
    assert direct_request.prompt_safety_state == PromptSafetyState.UNCERTAIN


def test_independent_dataset_with_personal_data_is_rejected_before_provider(tmp_path: Path) -> None:
    """即使清单摘要匹配，含真实邮箱形态的开放集也必须在 Provider 前失败关闭。"""
    dataset_path, manifest_path = _write_independent_dataset(
        tmp_path,
        customer_message="请联系 alice@example.com 核对虚构订单。",
    )

    with pytest.raises(ValueError, match="隐私安全门禁"):
        load_verified_real_model_evaluation_dataset(dataset_path, manifest_path)


def test_independent_dataset_digest_mismatch_is_rejected_before_provider(tmp_path: Path) -> None:
    """清单冻结后任何数据集变化都必须在 Provider 前被摘要门禁拒绝。"""
    dataset_path, manifest_path = _write_independent_dataset(tmp_path)
    dataset_path.write_text(
        dataset_path.read_text(encoding="utf-8").replace("开放集合成样本", "清单冻结后修改"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="摘要与清单不一致"):
        load_verified_real_model_evaluation_dataset(dataset_path, manifest_path)


def test_independent_dataset_is_limited_to_integration_and_staging(tmp_path: Path) -> None:
    """独立开放集不能在 development 或 production 运行，避免形成通用外发旁路。"""
    dataset_path, manifest_path = _write_independent_dataset(tmp_path)
    dataset = load_verified_real_model_evaluation_dataset(dataset_path, manifest_path)

    validate_real_model_evaluation_environment(dataset, "integration")
    validate_real_model_evaluation_environment(dataset, "staging")
    with pytest.raises(ValueError, match="integration/staging"):
        validate_real_model_evaluation_environment(dataset, "development")
    with pytest.raises(ValueError, match="integration/staging"):
        validate_real_model_evaluation_environment(dataset, "production")


@pytest.mark.asyncio
async def test_runner_rejects_disallowed_environment_before_provider(tmp_path: Path) -> None:
    """库调用者不能绕过 CLI；运行器必须在 Provider 调用前重复环境门禁。"""
    dataset_path, manifest_path = _write_independent_dataset(tmp_path)
    dataset = load_verified_real_model_evaluation_dataset(dataset_path, manifest_path)
    provider = _CountingProvider()

    with pytest.raises(ValueError, match="integration/staging"):
        await run_real_model_evaluation(
            dataset,
            provider,
            run_id=uuid.UUID("55555555-5555-4555-8555-555555555555"),
            app_env="development",
            input_cost_per_million_usd=Decimal("0.44"),
            output_cost_per_million_usd=Decimal("1.32"),
            pricing_version="deepseek-v4-2026-08-16-peak-cache-miss",
            pricing_basis="conservative_peak_cache_miss",
        )

    assert provider.call_count == 0


def test_real_model_prompt_declares_every_reason_code_in_output_contract() -> None:
    """Prompt 必须声明 Schema 的全部合法原因码，防止模型自造枚举导致整批结构失败。"""
    assert REAL_MODEL_EVALUATION_REASON_CODES
    assert all(reason_code in REAL_MODEL_EVALUATION_SYSTEM_PROMPT for reason_code in REAL_MODEL_EVALUATION_REASON_CODES)


def test_real_model_prompt_distinguishes_legitimate_scope_and_translation_terms() -> None:
    """Prompt 必须明确合法否定/引用与高风险断言的边界，并固定关键翻译术语。"""
    required_rules = (
        "否定说明或引用的禁止反例",
        "non_business_artifact",
        "being processed",
        "has not shipped",
        "transfer_human 时 business_claims 必须为空数组",
    )

    assert all(rule in REAL_MODEL_EVALUATION_SYSTEM_PROMPT for rule in required_rules)


def test_real_model_request_requires_policy_claim_and_paraphrases_prohibited_quote() -> None:
    """冻结售后与引用样本必须获得完整声明契约，且不能复述禁用承诺。"""
    repo_root = TESTS_ROOT.parents[1]
    dataset = load_verified_real_model_evaluation_dataset(
        repo_root / "release/evidence/ai/real-model-independent-v1.0.0.jsonl",
        repo_root / "release/evidence/ai/real-model-independent-v1.0.0.manifest.json",
    )
    cases = {case.sample_id: case for case in dataset.cases}
    run_id = uuid.UUID("44444444-4444-4444-8444-444444444444")
    after_sales = build_real_model_evaluation_request(cases["after-sales-open-001"], dataset, run_id=run_id)
    quotation = build_real_model_evaluation_request(cases["quotation-open-002"], dataset, run_id=run_id)

    for request in (after_sales, quotation):
        assert "售后政策说明即使交给人工复核，也必须输出一条有证据的 refund_policy 结构化声明" in request.system_prompt
        assert "禁止用语即使出现在引用反例中，也不要在 content 中逐字复述；应概述其风险" in request.system_prompt
    assert REAL_MODEL_EVALUATION_PROMPT_VERSION == "real-model-eval-v1.2.11"


def test_negation_draft_and_policy_repair_keep_supported_facts_explicit() -> None:
    """展示否定要写清楚；有申请时限和审核证据时修复稿应保留两者。"""
    repo_root = TESTS_ROOT.parents[1]
    dataset = load_verified_real_model_evaluation_dataset(
        repo_root / "release/evidence/ai/real-model-independent-v1.0.0.jsonl",
        repo_root / "release/evidence/ai/real-model-independent-v1.0.0.manifest.json",
    )
    cases = {case.sample_id: case for case in dataset.cases}
    run_id = uuid.UUID("44444444-4444-4444-8444-444444444444")
    negation = build_real_model_evaluation_request(cases["negation-open-001"], dataset, run_id=run_id)
    assert "content 明确写出页面未显示或没有显示完成状态" in negation.system_prompt
    assert "不得据此推断实际退款成功或失败" in negation.system_prompt

    first_output = RealModelEvaluationOutput.model_validate(
        {
            "decision": "human_review",
            "content": "A request may be submitted within twelve days.",
            "language": "en",
            "reason_code": "policy_grounded",
            "business_claims": [],
            "send_performed": False,
        }
    )
    repair = build_real_model_repair_request(
        cases["multilingual-open-001"],
        dataset,
        first_output,
        ("POLICY_REVIEW_STEP_MISSING",),
        run_id=run_id,
    )
    assert "申请时限和平台审核步骤均有证据时，保留非空的 human_review 草稿" in repair.system_prompt
    assert "需要平台审核不等于证据不足" in repair.system_prompt
    assert "不得编造个案审核状态或结果" in repair.system_prompt
    assert "refund_policy 结构化声明" in repair.system_prompt
    assert "required_term_groups" not in repair.user_prompt
    assert "expected_decision" not in repair.user_prompt


def test_real_model_request_uses_short_complete_sentences_while_address_dlp_stays_strict() -> None:
    """真实请求应避免无地址含义的列表标点，仍阻断明确地址。"""
    repo_root = TESTS_ROOT.parents[1]
    dataset = load_verified_real_model_evaluation_dataset(
        repo_root / "release/evidence/ai/real-model-independent-v1.0.0.jsonl",
        repo_root / "release/evidence/ai/real-model-independent-v1.0.0.manifest.json",
    )
    case = next(item for item in dataset.cases if item.sample_id == "logistics-open-001")
    request = build_real_model_evaluation_request(
        case, dataset, run_id=uuid.UUID("55555555-5555-4555-8555-555555555555")
    )
    assert "用完整短句逐项表达证据" in request.system_prompt
    assert "避免用逗号串联列表或多个从句" in request.system_prompt
    assert (
        evaluate_real_model_draft_safety("The parcel is ready. The carrier will scan it later.", []).state
        == PromptSafetyState.ALLOWED
    )
    assert (
        evaluate_real_model_draft_safety("Deliver to 123 Main Street, Apt 2, Seattle.", []).state
        == PromptSafetyState.BLOCKED
    )


def test_real_model_request_preserves_negative_condition_and_translation_meaning() -> None:
    """新诊断暴露的三种语义必须在冻结请求的系统契约中明确。"""
    repo_root = TESTS_ROOT.parents[1]
    dataset = load_verified_real_model_evaluation_dataset(
        repo_root / "release/evidence/ai/real-model-independent-v1.0.0.jsonl",
        repo_root / "release/evidence/ai/real-model-independent-v1.0.0.manifest.json",
    )
    cases = {case.sample_id: case for case in dataset.cases}
    run_id = uuid.UUID("44444444-4444-4444-8444-444444444444")
    for sample_id in ("negation-open-001", "negation-open-002", "condition-open-002", "translation-open-002"):
        request = build_real_model_evaluation_request(cases[sample_id], dataset, run_id=run_id)
        assert "页面未显示不能推断退款完成或失败" in request.system_prompt
        assert "政策答复只写证据支持的申请资格、时限和平台审核流程" in request.system_prompt
        assert "only if the platform approves" in request.system_prompt
        assert "in preparation" in request.system_prompt
        assert "has not shipped" in request.system_prompt


def test_english_negation_and_condition_use_evidence_grounded_present_tense_frames() -> None:
    """通用英语句式须说明标签未确认及批准前置规则，不补写个案结果。"""
    repo_root = TESTS_ROOT.parents[1]
    dataset = load_verified_real_model_evaluation_dataset(
        repo_root / "release/evidence/ai/real-model-independent-v1.0.0.jsonl",
        repo_root / "release/evidence/ai/real-model-independent-v1.0.0.manifest.json",
    )
    cases = {case.sample_id: case for case in dataset.cases}
    run_id = uuid.UUID("44444444-4444-4444-8444-444444444444")
    negation = build_real_model_evaluation_request(cases["negation-open-002"], dataset, run_id=run_id)
    condition = build_real_model_evaluation_request(cases["condition-open-002"], dataset, run_id=run_id)

    assert negation.system_prompt == condition.system_prompt
    assert "The status is unconfirmed" in negation.system_prompt
    assert "Processing begins only if the platform approves a request" in condition.system_prompt
    assert "正文止于申请或处理规则" in condition.system_prompt


def test_policy_drafts_use_positive_review_flow_and_cart_avoids_promotional_echoes() -> None:
    """售后和条件答复只表达有证据的流程，购物车草稿不复述禁用促销话术。"""
    repo_root = TESTS_ROOT.parents[1]
    dataset = load_verified_real_model_evaluation_dataset(
        repo_root / "release/evidence/ai/real-model-independent-v1.0.0.jsonl",
        repo_root / "release/evidence/ai/real-model-independent-v1.0.0.manifest.json",
    )
    cases = {case.sample_id: case for case in dataset.cases}
    run_id = uuid.UUID("44444444-4444-4444-8444-444444444444")
    condition = build_real_model_evaluation_request(cases["condition-open-002"], dataset, run_id=run_id)
    after_sales = build_real_model_evaluation_request(cases["after-sales-open-001"], dataset, run_id=run_id)
    cart = build_real_model_evaluation_request(cases["abandoned-open-001"], dataset, run_id=run_id)

    assert condition.system_prompt == after_sales.system_prompt == cart.system_prompt
    assert "可提交申请，由平台按规则审核" in after_sales.system_prompt
    assert "平台批准是处理前置条件" in condition.system_prompt
    assert "省略个案审批现状、结果保证" in condition.system_prompt
    assert "删除对具体申请是否获批的肯定或否定句" not in condition.system_prompt
    assert "只描述允许的购物车查看或结算提醒" in cart.system_prompt
    assert "删去对缺席促销或库存紧迫话术的复述，包括否定句" in cart.system_prompt


def test_real_model_evaluation_request_uses_deterministic_temperature() -> None:
    """真实模型评测必须关闭采样随机性，降低同版本重复运行的决策漂移。"""
    dataset = load_verified_real_model_evaluation_dataset(
        DATASET_PATH,
        DATASETS_ROOT / "real-model-v1.0.0.manifest.json",
    )

    request = build_real_model_evaluation_request(
        dataset.cases[0],
        dataset,
        run_id=uuid.UUID("44444444-4444-4444-8444-444444444444"),
    )

    assert request.temperature == 0.0


def test_transfer_human_rejects_business_claims() -> None:
    """转人工结果不得夹带未经证据校验的业务声明。"""
    with pytest.raises(ValidationError, match="转人工评测结果不得包含业务声明"):
        RealModelEvaluationOutput.model_validate(
            {
                "decision": "transfer_human",
                "content": None,
                "language": "zh-CN",
                "reason_code": "insufficient_evidence",
                "business_claims": [_valid_order_claim()],
                "send_performed": False,
            }
        )


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("subject_type", "logistics"),
        ("subject_id", "[SYNTHETIC_OTHER]"),
        ("action", "display"),
        ("tense", "timeless"),
        ("polarity", "negated"),
        ("condition", "conditional"),
        ("evidence_type", "faq_chunk"),
        ("evidence_id", "10000000-0000-4000-8000-000000000099"),
        ("confidence", 0.1),
    ],
)
def test_grading_rejects_every_incorrect_business_claim_dimension(
    field: str,
    invalid_value: object,
) -> None:
    """对象、引用、动作、时态、极性、条件、证据和置信度任一错误都不得通过。"""
    dataset = load_verified_real_model_evaluation_dataset(
        DATASET_PATH,
        DATASETS_ROOT / "real-model-v1.0.0.manifest.json",
    )
    claim = _valid_order_claim()
    claim[field] = invalid_value
    output = RealModelEvaluationOutput.model_validate(
        {
            "decision": "auto_reply",
            "content": "演示订单正在处理中。",
            "language": "zh-CN",
            "reason_code": "grounded_draft",
            "business_claims": [claim],
            "send_performed": False,
        }
    )

    failures = grade_real_model_evaluation_output(dataset.cases[0], output)

    assert "BUSINESS_CLAIMS_MISMATCH" in failures


def test_multilingual_conditional_policy_claim_matches_frozen_evidence() -> None:
    """多语言样本的“批准取决于审核”是条件政策，不得误判为实际无条件事实。"""
    dataset = load_verified_real_model_evaluation_dataset(
        DATASET_PATH,
        DATASETS_ROOT / "real-model-v1.0.0.manifest.json",
    )
    case = next(item for item in dataset.cases if item.sample_id == "multilingual-policy-001")
    output = RealModelEvaluationOutput.model_validate(
        {
            "decision": "human_review",
            "content": "You may request a return; approval depends on platform review.",
            "language": "en",
            "reason_code": "policy_grounded",
            "business_claims": [
                {
                    "subject_type": "refund_policy",
                    "subject_id": None,
                    "action": "explain_policy",
                    "tense": "timeless",
                    "polarity": "affirmed",
                    "condition": "conditional",
                    "evidence_type": "faq_chunk",
                    "evidence_id": "10000000-0000-4000-8000-000000000012",
                    "confidence": 0.9,
                }
            ],
            "send_performed": False,
        }
    )

    assert "BUSINESS_CLAIMS_MISMATCH" not in grade_real_model_evaluation_output(case, output)


def test_after_sales_conditional_policy_claim_matches_frozen_evidence() -> None:
    """售后样本的“是否通过以审核为准”必须按条件政策声明判分。"""
    dataset = load_verified_real_model_evaluation_dataset(
        DATASET_PATH,
        DATASETS_ROOT / "real-model-v1.0.0.manifest.json",
    )
    case = next(item for item in dataset.cases if item.sample_id == "after-sales-policy-001")
    output = RealModelEvaluationOutput.model_validate(
        {
            "decision": "human_review",
            "content": "七天内可以提交退货申请，是否通过以平台审核为准。",
            "language": "zh-CN",
            "reason_code": "policy_grounded",
            "business_claims": [
                {
                    "subject_type": "refund_policy",
                    "subject_id": None,
                    "action": "explain_policy",
                    "tense": "timeless",
                    "polarity": "affirmed",
                    "condition": "conditional",
                    "evidence_type": "faq_chunk",
                    "evidence_id": "10000000-0000-4000-8000-000000000003",
                    "confidence": 0.9,
                }
            ],
            "send_performed": False,
        }
    )

    assert "BUSINESS_CLAIMS_MISMATCH" not in grade_real_model_evaluation_output(case, output)


def test_unconfigured_token_price_is_explicit_and_blocks_evaluation_gate() -> None:
    """零价格必须表示未配置，不能继续落成看似真实的 0 美元成本。"""
    report = build_evaluation_report(
        [_successful_result()],
        run_id="33333333-3333-4333-8333-333333333333",
        model="deepseek-v4-flash",
        prompt_version=REAL_MODEL_EVALUATION_PROMPT_VERSION,
        policy_version=PROMPT_DLP_POLICY_VERSION,
        dataset_version=REAL_MODEL_DATASET_VERSION,
        dataset_sha256="a" * 64,
        dataset_manifest_sha256="b" * 64,
        pricing_version=None,
        pricing_currency="USD",
        pricing_basis="conservative_peak_cache_miss",
    )

    assert report.metrics.cost_status == "not_configured"
    assert report.metrics.estimated_cost_usd is None
    assert report.passed is False


def test_configured_token_price_records_version_currency_basis_and_cost() -> None:
    """成本估算必须绑定价格版本、币种和保守计价口径。"""
    report = build_evaluation_report(
        [_successful_result()],
        run_id="33333333-3333-4333-8333-333333333333",
        model="deepseek-v4-flash",
        prompt_version=REAL_MODEL_EVALUATION_PROMPT_VERSION,
        policy_version=PROMPT_DLP_POLICY_VERSION,
        dataset_version=REAL_MODEL_DATASET_VERSION,
        dataset_sha256="a" * 64,
        dataset_manifest_sha256="b" * 64,
        input_cost_per_million_usd=Decimal("0.44"),
        output_cost_per_million_usd=Decimal("1.32"),
        pricing_version="deepseek-v4-2026-08-16-peak-cache-miss",
        pricing_currency="USD",
        pricing_basis="conservative_peak_cache_miss",
    )

    assert report.metrics.cost_status == "configured"
    assert report.metrics.estimated_cost_usd == Decimal("0.000011")
    assert report.pricing_version == "deepseek-v4-2026-08-16-peak-cache-miss"
    assert report.pricing_currency == "USD"
    assert report.pricing_basis == "conservative_peak_cache_miss"
    assert report.input_cost_per_million_usd == Decimal("0.44")
    assert report.output_cost_per_million_usd == Decimal("1.32")
    assert report.passed is True


def test_configured_token_price_rejects_unapproved_rate_tuple() -> None:
    """任意极小费率和伪造版本不得满足真实成本门禁。"""
    with pytest.raises(ValueError, match="计价配置未获批准"):
        build_evaluation_report(
            [_successful_result()],
            run_id="33333333-3333-4333-8333-333333333333",
            model="deepseek-v4-flash",
            prompt_version=REAL_MODEL_EVALUATION_PROMPT_VERSION,
            policy_version=PROMPT_DLP_POLICY_VERSION,
            dataset_version=REAL_MODEL_DATASET_VERSION,
            dataset_sha256="a" * 64,
            dataset_manifest_sha256="b" * 64,
            input_cost_per_million_usd=Decimal("0.000001"),
            output_cost_per_million_usd=Decimal("0.000001"),
            pricing_version="invented-v1",
            pricing_currency="USD",
            pricing_basis="conservative_peak_cache_miss",
        )


def test_live_model_evaluation_rejects_missing_pricing_metadata() -> None:
    """真实模型评测启用时，单价或价格版本缺失必须在启动阶段失败。"""
    with pytest.raises(ValidationError, match="计价"):
        Settings(
            _env_file=None,
            LLM_ENABLED=True,
            LLM_LIVE_EVAL=True,
            LLM_PRIMARY_PROVIDER="deepseek",
            LLM_PRIMARY_MODEL="deepseek-v4-flash",
            DEEPSEEK_API_KEY="test-deepseek-key",
        )


def test_live_model_evaluation_accepts_complete_pricing_metadata() -> None:
    """模型、密钥和版本化计价完整时，真实评测配置应可以启动。"""
    settings = Settings(
        _env_file=None,
        LLM_ENABLED=True,
        LLM_LIVE_EVAL=True,
        LLM_PRIMARY_PROVIDER="deepseek",
        LLM_PRIMARY_MODEL="deepseek-v4-flash",
        DEEPSEEK_API_KEY="test-deepseek-key",
        LLM_INPUT_COST_PER_MILLION_USD=Decimal("0.44"),
        LLM_OUTPUT_COST_PER_MILLION_USD=Decimal("1.32"),
        LLM_PRICING_VERSION="deepseek-v4-2026-08-16-peak-cache-miss",
        LLM_PRICING_CURRENCY="USD",
        LLM_PRICING_BASIS="conservative_peak_cache_miss",
    )

    assert settings.llm_live_eval is True
    assert settings.llm_pricing_version == "deepseek-v4-2026-08-16-peak-cache-miss"


def test_live_model_evaluation_is_forbidden_in_production() -> None:
    """即使计价和密钥完整，生产进程也不得启用离线真实模型评测。"""
    with pytest.raises(ValidationError, match="生产环境禁止启用真实模型评测"):
        Settings(
            _env_file=None,
            APP_ENV="production",
            LLM_ENABLED=True,
            LLM_LIVE_EVAL=True,
            LLM_PRIMARY_PROVIDER="deepseek",
            LLM_PRIMARY_MODEL="deepseek-v4-flash",
            DEEPSEEK_API_KEY="test-deepseek-key",
            LLM_INPUT_COST_PER_MILLION_USD=Decimal("0.44"),
            LLM_OUTPUT_COST_PER_MILLION_USD=Decimal("1.32"),
            LLM_PRICING_VERSION="deepseek-v4-2026-08-16-peak-cache-miss",
            LLM_PRICING_CURRENCY="USD",
            LLM_PRICING_BASIS="conservative_peak_cache_miss",
        )


def test_cli_redacts_invalid_dataset_values_from_stderr(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """输入校验异常可能包含 input_value，CLI 只能输出稳定低敏错误码。"""
    sentinel = "secret-sentinel-alice@example.com"

    async def fail_with_sensitive_validation_value() -> int:
        raise ValueError(f"invalid input_value={sentinel}")

    monkeypatch.setattr(evaluate_real_model, "main", fail_with_sensitive_validation_value)

    assert evaluate_real_model.cli() == 2
    captured = capsys.readouterr()
    assert sentinel not in captured.err
    assert "EVALUATION_INPUT_INVALID" in captured.err


def test_result_writer_never_overwrites_concurrently_created_evidence(tmp_path: Path) -> None:
    """最终落盘必须使用排他创建，消除 exists 检查后的并发覆盖窗口。"""
    output_path = tmp_path / "result.json"
    output_path.write_text("historical-evidence", encoding="utf-8")

    with pytest.raises(FileExistsError):
        evaluate_real_model.write_report_exclusively(output_path, {"passed": True})

    assert output_path.read_text(encoding="utf-8") == "historical-evidence"


def _successful_result() -> RealModelSampleResult:
    """构造一条达到质量门禁的低敏真实模型结果。"""
    return RealModelSampleResult(
        model="deepseek-v4-flash",
        prompt_version=REAL_MODEL_EVALUATION_PROMPT_VERSION,
        policy_version=PROMPT_DLP_POLICY_VERSION,
        dataset_version=REAL_MODEL_DATASET_VERSION,
        run_id=uuid.UUID("33333333-3333-4333-8333-333333333333"),
        sample_id="order-grounded-001",
        category="order",
        risk_level="normal",
        expected_decision="auto_reply",
        decision="auto_reply",
        input_hash="c" * 64,
        output_hash="d" * 64,
        failure_reason=None,
        first_output_latency_ms=100,
        total_latency_ms=120,
        token_usage=RealModelTokenUsage(input_tokens=10, output_tokens=5, total_tokens=15),
        passed=True,
        provider_failure=False,
        injected_failure=False,
    )


def _valid_order_claim() -> dict[str, object]:
    """构造首条冻结订单样本的完整九维声明。"""
    return {
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


class _CountingProvider(LLMProvider):
    """记录调用次数；环境门禁测试中不应进入 Provider。"""

    provider_name = "deepseek"
    model_name = "deepseek-v4-flash"

    def __init__(self) -> None:
        self.call_count = 0

    async def generate_structured(
        self,
        request: StructuredRequest,
        response_schema: type[OutputT],
    ) -> ProviderResult[OutputT]:
        self.call_count += 1
        raise AssertionError("环境门禁后不应调用 Provider")
