"""staging G4 工作流必须精确验证新低敏报告和调用上限。"""

import re
from pathlib import Path

from app.agent.real_model_evaluation import RealModelEvaluationMetrics, RealModelEvaluationReport, RealModelSampleResult

ROOT = Path(__file__).resolve().parents[4]
WORKFLOW = ROOT / ".github/workflows/evaluate-staging-deepseek.yml"


def _allowed_keys(source: str, variable: str) -> set[str]:
    match = re.search(rf"\${variable} = @\(([^\n]+)\)", source)
    assert match is not None, f"missing {variable} allowlist"
    return set(re.findall(r"'([^']+)'", match.group(1)))


def test_live_artifact_allowlists_match_pydantic_models() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    assert _allowed_keys(source, "allowedReportKeys") == set(RealModelEvaluationReport.model_fields)
    assert _allowed_keys(source, "allowedSampleKeys") == set(RealModelSampleResult.model_fields)
    assert _allowed_keys(source, "allowedMetricsKeys") == set(RealModelEvaluationMetrics.model_fields)
    assert "content" not in _allowed_keys(source, "allowedSampleKeys")
    assert "prompt" not in _allowed_keys(source, "allowedSampleKeys")


def test_live_gate_requires_new_flow_and_bounded_provider_calls() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "$report.evaluation_flow_version -cne 'policy-repair-dlp-regeneration-v1'" in source
    assert "$report.metrics.provider_call_count -gt 68" in source
    assert "$report.metrics.repair_attempt_count -gt 34" in source
    assert "$report.metrics.regeneration_attempt_count -gt 34" in source
    assert "($report.metrics.repair_attempt_count + $report.metrics.regeneration_attempt_count) -gt 34" in source
    assert "($sample.repair_attempted -and $sample.regeneration_attempted)" in source
    assert "$report.samples.Count -ne 36" in source
    assert "$report.metrics.live_model_sample_count -ne 34" in source
    assert "$report.metrics.injected_failure_sample_count -ne 2" in source
    assert "provider_calls = 0" in source


def test_live_artifact_accepts_only_fixed_location_shape_codes() -> None:
    reasons = _allowed_keys(WORKFLOW.read_text(encoding="utf-8"), "allowedPolicyReasons")
    assert {
        "DRAFT_DLP_UNCERTAIN_BUSINESS_LOCATION",
        "DRAFT_DLP_UNCERTAIN_LOCATION_TERMS",
        "DRAFT_DLP_UNCERTAIN_LOCATION_SCRIPT",
        "DRAFT_DLP_UNCERTAIN_LOCATION_SEPARATORS",
        "DRAFT_DLP_UNCERTAIN_LOCATION_NUMBERS",
    } <= reasons
    assert not any("CONTENT" in reason or "TEXT" in reason for reason in reasons)


def test_live_artifact_accepts_only_fixed_schema_diagnostics() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    assert {"invalid_json", "invalid_schema"} <= _allowed_keys(source, "allowedOutputFailureKinds")
    assert {"business_claims[].confidence", "business_claims[].evidence_id", "unknown"} <= _allowed_keys(
        source, "allowedOutputSchemaPaths"
    )
    assert {"missing", "extra_forbidden", "less_than_equal"} <= _allowed_keys(source, "allowedOutputSchemaErrorTypes")
    assert "@($sample.provider_output_schema_issues).Count -gt 8" in source
