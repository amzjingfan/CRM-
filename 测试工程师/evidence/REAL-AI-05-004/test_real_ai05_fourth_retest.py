"""REAL-AI-05 第四次独立复测证据。

本探针验证 003 号报告后的候选文件、冻结开放集和活文档门禁没有漂移。
它不调用 DeepSeek、不读取密钥或真实业务数据，也不修改产品代码和业务状态。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
PRODUCT_ROOT = WORKSPACE_ROOT / "CRM智能聊天系统"
PLAN_PATH = (
    WORKSPACE_ROOT
    / "AI agent 开发工程师"
    / "PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md"
)
REMEDIATION_PATH = (
    WORKSPACE_ROOT
    / "共享记忆文档"
    / "实施记录"
    / "Phase4-P4-00-AIAgent开发工程师Agent-REAL-AI-05第三次独立测试结论同步与门禁校准-034.md"
)
DATASET_PATH = (
    WORKSPACE_ROOT
    / "测试工程师"
    / "evidence"
    / "REAL-AI-05-002"
    / "real-model-independent-v1.0.0.jsonl"
)
MANIFEST_PATH = DATASET_PATH.with_suffix(".manifest.json")

# 这些摘要来自 003 号权威报告。逐文件比较比未声明规范化算法的聚合摘要更可复现。
EXPECTED_CANDIDATE_HASHES = {
    "backend/app/agent/real_model_evaluation.py": "6b9e534ff6ef58e0aeb5d06fd9bb89ed439989eca1a8e8c82c4b3cd01cea86fa",
    "backend/app/agent/security.py": "30b48f5b19b2e8a7392ec023ab5771ce058ac76cbd358929a5c6fcd9742d5558",
    "backend/app/agent/providers/base.py": "0199ae22ef665bdcd130dd55cb6b153918a9a3da3e1f87416e3121d5a910ef91",
    "backend/app/agent/providers/deepseek_provider.py": "2fc942a2dd0de609e61ee40d76751764ba12afe7773054d8ef7b7c35738ec74d",
    "backend/app/shared/config/settings.py": "89defd0b6b457c74997432ec27548caa17dfd039915bb1b25bace795b5fac740",
    "backend/app/shared/config/llm_pricing.py": "b638bc3de5ac02de28783d688224d772c76d7b15b61656f25c65d07e1f31b39c",
    "backend/scripts/evaluate_real_model.py": "0ab5570505b21119a2a90020b0b8b333bf5171655e5253096ee91b884e4e2367",
    "backend/tests/test_real_runtime_config.py": "ca5025ede82c98ecf86ff82fdcde77d1d1d029087cf3b7f06abf0edaf2b17fb7",
    "docker-compose.yml": "eb6985cdeee750c6f9ab21d466da0992868a804aed32656920443627d50fae8f",
    ".env.example": "b64d4a83e093f65eadd1981f8cb8a0206412520f71046f7886281c6399a8081a",
    "README.md": "971e051bb9df6937ef2d9900d5a910ee7deee5d3add258c1f91f6e7658105e97",
}
EXPECTED_DATASET_SHA256 = (
    "7f7c7084ac37e9aef5c9b1a947a9f44250cd89e290f5ae18990ec558e5c6df94"
)
CANONICAL_AI_SWITCHES = (
    "LLM_ENABLED",
    "LLM_LIVE_EVAL",
    "AI_TRANSLATION_ENABLED",
    "AI_MARKETING_ENABLED",
    "AUTO_REPLY_ENABLED",
)


def _sha256(path: Path) -> str:
    """计算文件原始字节摘要，避免换行规范化掩盖候选变化。"""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_candidate_files_match_report_003() -> None:
    """003 号报告覆盖的 11 个候选文件必须逐一保持不变。"""
    actual = {
        relative_path: _sha256(PRODUCT_ROOT / relative_path)
        for relative_path in EXPECTED_CANDIDATE_HASHES
    }
    assert actual == EXPECTED_CANDIDATE_HASHES


def test_independent_dataset_and_manifest_remain_frozen() -> None:
    """开放集正文、版本、样本数和独立来源必须仍与已冻结证据一致。"""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert _sha256(DATASET_PATH) == EXPECTED_DATASET_SHA256
    assert manifest == {
        "schema_version": "1",
        "dataset_version": "real-model-independent-v1.0.0",
        "dataset_sha256": EXPECTED_DATASET_SHA256,
        "sample_count": 36,
        "source": "independent_test",
    }


def test_live_documents_keep_real_model_gate_open_and_switch_names_canonical() -> None:
    """整改文档必须保持 002 为开放阻断，并只使用架构确认的正式开关。"""
    plan = PLAN_PATH.read_text(encoding="utf-8")
    remediation = REMEDIATION_PATH.read_text(encoding="utf-8")
    for switch_name in CANONICAL_AI_SWITCHES:
        assert switch_name in plan
        assert switch_name in remediation
    assert "`DEF-REAL-AI05-002` 仍为 P1/Open" in plan
    assert "`DEF-REAL-AI05-002` 仍缺少" in remediation
    assert "本轮未调用真实 DeepSeek" in remediation
    assert "实施状态 | 部分完成" in remediation


def test_root_and_long_lived_services_keep_live_evaluation_disabled() -> None:
    """一次性评测未获准前，根环境和五个常驻服务必须显式关闭真实评测。"""
    root_env = (PRODUCT_ROOT / ".env").read_text(encoding="utf-8")
    active_root_values = [
        line.split("=", 1)[1].strip()
        for line in root_env.splitlines()
        if line.strip().startswith("LLM_LIVE_EVAL=")
        and not line.lstrip().startswith("#")
    ]
    assert active_root_values == ["false"]

    compose = (PRODUCT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert compose.count('LLM_LIVE_EVAL: "false"') == 5
