"""REAL-AI-05 可审计的 LLM 计价登记表。

计价只用于评测成本估算，不替代供应商账单。把模型、价格版本、币种、
口径和费率作为一个不可拆分元组验证，避免任意正数伪装成已批准配置。
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ApprovedLLMPricing:
    """一项经过架构配置确认的模型计价元组。"""

    provider: str
    model: str
    version: str
    currency: str
    basis: str
    input_per_million: Decimal
    output_per_million: Decimal


DEEPSEEK_V4_FLASH_PEAK_CACHE_MISS = ApprovedLLMPricing(
    provider="deepseek",
    model="deepseek-v4-flash",
    version="deepseek-v4-2026-08-16-peak-cache-miss",
    currency="USD",
    basis="conservative_peak_cache_miss",
    input_per_million=Decimal("0.44"),
    output_per_million=Decimal("1.32"),
)

APPROVED_LLM_PRICING = (DEEPSEEK_V4_FLASH_PEAK_CACHE_MISS,)


def validate_approved_llm_pricing(
    *,
    provider: str,
    model: str,
    version: str,
    currency: str,
    basis: str,
    input_per_million: Decimal,
    output_per_million: Decimal,
) -> ApprovedLLMPricing:
    """返回完全匹配的登记项；未知、非有限或部分匹配均失败关闭。"""
    if not input_per_million.is_finite() or not output_per_million.is_finite():
        raise ValueError("LLM 计价配置未获批准")
    candidate = (
        provider.strip().lower(),
        model.strip(),
        version.strip(),
        currency.strip().upper(),
        basis.strip(),
        input_per_million,
        output_per_million,
    )
    for pricing in APPROVED_LLM_PRICING:
        approved = (
            pricing.provider,
            pricing.model,
            pricing.version,
            pricing.currency,
            pricing.basis,
            pricing.input_per_million,
            pricing.output_per_million,
        )
        if candidate == approved:
            return pricing
    raise ValueError("LLM 计价配置未获批准")
