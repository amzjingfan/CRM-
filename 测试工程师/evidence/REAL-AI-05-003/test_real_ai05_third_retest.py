"""REAL-AI-05 第三次独立复测证据。

本探针只验证一次性真实模型评测与常驻服务的配置隔离，不调用外部模型、
不读取真实业务数据，也不修改产品代码、数据库或平台状态。
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.shared.config.settings import TIKTOK_OAUTH_FIXED_REDIRECT_URI, Settings

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
PRODUCT_ROOT = WORKSPACE_ROOT / "CRM智能聊天系统"
ROOT_ENV_PATH = PRODUCT_ROOT / ".env"
COMPOSE_PATH = PRODUCT_ROOT / "docker-compose.yml"
LONG_LIVED_SERVICES = (
    "backend",
    "worker",
    "jobs",
    "agent-worker",
    "retrieval-model-service",
)


def _active_env_values(variable_name: str) -> list[str]:
    """读取指定根环境变量的有效赋值，不回显任何密钥或其他配置。"""
    prefix = f"{variable_name}="
    return [
        line.split("=", 1)[1].strip()
        for line in ROOT_ENV_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith(prefix) and not line.lstrip().startswith("#")
    ]


def _compose_service_block(compose_text: str, service_name: str) -> str:
    """提取一个顶层 Compose 服务块，避免同文注释或其他服务造成伪命中。"""
    lines = compose_text.splitlines()
    start = lines.index(f"  {service_name}:")
    block = [lines[start]]
    for line in lines[start + 1 :]:
        if line.startswith("  ") and not line.startswith("    ") and line.endswith(":"):
            break
        block.append(line)
    return "\n".join(block)


def _approved_live_eval_settings(**overrides: object) -> Settings:
    """构造只用于隔离 integration 进程的合成评测配置。"""
    values: dict[str, object] = {
        "APP_ENV": "integration",
        "TIKTOK_OAUTH_REDIRECT_URI": TIKTOK_OAUTH_FIXED_REDIRECT_URI,
        "LLM_ENABLED": True,
        "LLM_LIVE_EVAL": True,
        "LLM_PRIMARY_PROVIDER": "deepseek",
        "LLM_PRIMARY_MODEL": "deepseek-v4-flash",
        "DEEPSEEK_API_KEY": "synthetic-test-key-not-for-network",
        "LLM_INPUT_COST_PER_MILLION_USD": "0.44",
        "LLM_OUTPUT_COST_PER_MILLION_USD": "1.32",
        "LLM_PRICING_VERSION": "deepseek-v4-2026-08-16-peak-cache-miss",
        "LLM_PRICING_CURRENCY": "USD",
        "LLM_PRICING_BASIS": "conservative_peak_cache_miss",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_root_environment_keeps_one_time_live_evaluation_disabled() -> None:
    """根环境只能保存关闭值，避免普通服务和 Alembic 被一次性授权污染。"""
    assert _active_env_values("LLM_LIVE_EVAL") == ["false"]


@pytest.mark.parametrize("service_name", LONG_LIVED_SERVICES)
def test_every_long_lived_service_forces_live_evaluation_off(service_name: str) -> None:
    """每个常驻 Python 服务都必须独立覆盖真实评测开关。"""
    block = _compose_service_block(COMPOSE_PATH.read_text(encoding="utf-8"), service_name)
    active_lines = [
        line.strip()
        for line in block.splitlines()
        if line.strip().startswith("LLM_LIVE_EVAL:") and not line.lstrip().startswith("#")
    ]
    assert active_lines == ['LLM_LIVE_EVAL: "false"']


def test_current_root_environment_can_construct_settings_without_live_pricing() -> None:
    """普通开发配置不应再因缺少一次性评测价格元组而启动失败。"""
    settings = Settings(_env_file=ROOT_ENV_PATH)
    assert settings.llm_live_eval is False


def test_incomplete_live_evaluation_configuration_still_fails_closed() -> None:
    """修复配置污染不能放宽真实评测的完整计价门禁。"""
    with pytest.raises(ValidationError, match="正数 Token 单价"):
        Settings(
            _env_file=None,
            APP_ENV="integration",
            TIKTOK_OAUTH_REDIRECT_URI=TIKTOK_OAUTH_FIXED_REDIRECT_URI,
            LLM_ENABLED=True,
            LLM_LIVE_EVAL=True,
            LLM_PRIMARY_PROVIDER="deepseek",
            LLM_PRIMARY_MODEL="deepseek-v4-flash",
            DEEPSEEK_API_KEY="synthetic-test-key-not-for-network",
        )


def test_approved_live_evaluation_remains_available_only_to_isolated_process() -> None:
    """完整显式配置仍可供获批 integration 评测进程使用。"""
    settings = _approved_live_eval_settings()
    assert settings.app_env == "integration"
    assert settings.llm_live_eval is True
    assert settings.llm_primary_model == "deepseek-v4-flash"


def test_production_cannot_enable_offline_live_evaluation() -> None:
    """即使费率完整，生产常驻进程也不得开启离线真实模型评测。"""
    with pytest.raises(ValidationError, match="生产环境禁止"):
        _approved_live_eval_settings(APP_ENV="production")
