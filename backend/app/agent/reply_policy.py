"""定义店铺级回复风格和中英文识别的确定性规则。"""

import re
from collections.abc import Mapping
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SupportedLanguage = Literal["zh-CN", "en"]
ReplyLanguage = Literal["auto", "zh-CN", "en"]

CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
LATIN_PATTERN = re.compile(r"[A-Za-z]")


class CustomerLanguage(StrEnum):
    """客户消息的确定性语言标签。"""

    ZH_CN = "zh-CN"
    EN = "en"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class ReplyTone(StrEnum):
    """允许店铺选择的有限回复语气，禁止把自由 Prompt 当作配置。"""

    FRIENDLY = "friendly"
    PROFESSIONAL = "professional"
    CONCISE = "concise"
    EMPATHETIC = "empathetic"


class AgentReplyProfile(BaseModel):
    """可信业务层传给 Agent 的店铺级回复配置。

    配置只允许固定枚举和简短品牌名，避免运营字段演变成可注入任意系统
    指令的 Prompt 通道。当前配置可以存放在 ``agent_configs.knowledge_scope``
    的 ``reply_profile`` 子对象中，不需要修改数据库结构。
    """

    model_config = ConfigDict(extra="forbid")

    tone: ReplyTone = ReplyTone.FRIENDLY
    reply_language: ReplyLanguage = "auto"
    operator_language: SupportedLanguage = "zh-CN"
    brand_name: str | None = Field(default=None, min_length=1, max_length=80)

    @field_validator("brand_name")
    @classmethod
    def validate_brand_name(cls, value: str | None) -> str | None:
        """拒绝控制符和换行，品牌名只能作为展示数据进入 Prompt。"""
        if value is None:
            return None
        normalized = value.strip()
        if not normalized or any(ord(character) < 32 for character in normalized):
            raise ValueError("品牌名称不能包含控制字符")
        return normalized


def detect_customer_language(text: str) -> CustomerLanguage:
    """使用字符集信号识别中文、英文、混合和未知消息。

    该识别器不调用模型，因此可以在进入 Prompt 前稳定执行。只要中文和
    拉丁字母同时出现就保留 ``mixed``，避免把中英混输静默归到某一语言。
    """
    has_cjk = CJK_PATTERN.search(text) is not None
    has_latin = LATIN_PATTERN.search(text) is not None
    if has_cjk and has_latin:
        return CustomerLanguage.MIXED
    if has_cjk:
        return CustomerLanguage.ZH_CN
    if has_latin:
        return CustomerLanguage.EN
    return CustomerLanguage.UNKNOWN


def resolve_reply_language(
    profile: AgentReplyProfile,
    detected_language: CustomerLanguage,
    declared_language: str | None = None,
) -> SupportedLanguage:
    """计算回答语言；显式店铺配置优先，自动模式优先跟随客户。"""
    if profile.reply_language != "auto":
        return profile.reply_language
    if detected_language in {CustomerLanguage.ZH_CN, CustomerLanguage.EN}:
        return detected_language.value  # type: ignore[return-value]
    if declared_language in {"zh-CN", "en"}:
        return declared_language  # type: ignore[return-value]
    # 混合或无文字消息无法可靠决定语言时，使用客服工作语言便于人工复核。
    return profile.operator_language


def resolve_store_reply_profile(configuration: Mapping[str, object]) -> AgentReplyProfile:
    """从店铺配置 JSON 中提取回复配置，缺失时返回安全默认值。

    ``configuration`` 由全栈服务从已经完成店铺隔离的 AgentConfig 读取。
    存在但结构非法时 Pydantic 会失败关闭，不会静默接纳任意字段。
    """
    raw_profile = configuration.get("reply_profile")
    if raw_profile is None:
        return AgentReplyProfile()
    if not isinstance(raw_profile, Mapping):
        raise ValueError("reply_profile 必须是对象")
    return AgentReplyProfile.model_validate(dict(raw_profile))
