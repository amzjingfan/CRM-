"""定义店铺级回复风格和中英文识别的确定性规则。"""

import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

if TYPE_CHECKING:
    from app.agents.management.repository import PublishedAgent

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
    的 ``reply_profile`` 子对象中；运行时只读取不可变发布快照。
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

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


REPLY_POLICY_VERSION = "published-reply-preferences-v1.1.1"

ASSISTANT_VOICE_POLICY = (
    "你是人工客服团队的智能客服助手，以客服团队的服务口吻面向买家，不能冒充某位人工客服。"
    "避免第一人称单数（我、I、me），用客观表述说明买家问题、已核实情况和下一步。"
    "无法直接处理时，说明需要人工客服核实跟进，不能让买家自行联系人工客服或另找客服。"
    "涉及取消、退款或异常时仍只陈述已核实事实，不能把拟跟进说成操作完成；"
    "只有实际接管或备注工具成功时才可说已转交、已安排；未执行时只说明待人工核实，不能暗示已经进入客服处理队列。"
    "事实中未提供的状态保持未知，不得将缺失信息推断为未发生；退货、取消、退款是不同状态，不能相互推断。"
    "不要照抄固定话术；由模型根据本轮问题、实际工具结果和买家语种自然组织简洁回答。"
)


def compile_reply_policy(profile: AgentReplyProfile | None) -> str:
    """有限表达偏好统一编译；不改变七段哈希、工具权限或证据要求。"""
    if profile is None:
        return f"[{REPLY_POLICY_VERSION}] {ASSISTANT_VOICE_POLICY}客户正文跟随本轮买家的真实文字语种。"
    tone = {
        ReplyTone.FRIENDLY: "亲切自然、有礼貌，避免过度热情和无关寒暄",
        ReplyTone.PROFESSIONAL: "专业准确、措辞稳健，避免口语化和额外承诺",
        ReplyTone.CONCISE: "简洁直答、删去重复和寒暄，保留必要事实与编号",
        ReplyTone.EMPATHETIC: "理解买家处境，适度表达理解后说明已核实事实，不能承诺未核实结果",
    }[profile.tone]
    language = (
        "auto：由模型依据本轮买家原始问题判断语种；历史、工具原文和路由任务不能覆盖它"
        if profile.reply_language == "auto"
        else f"{profile.reply_language}：买家正文统一使用{'中文' if profile.reply_language == 'zh-CN' else '英文'}"
    )
    return (
        f"[{REPLY_POLICY_VERSION}] {ASSISTANT_VOICE_POLICY}"
        "已发布回复偏好优先决定表达，覆盖七段中的冲突语气或语言要求。"
        f"语气={profile.tone.value}：{tone}。客户回复语言={language}。"
        "只影响表达，不改变事实、隐私、安全或权限。坐席工作语言不影响买家正文；"
        "不要在买家正文添加坐席译文、解释或内部审阅说明。"
    )


@dataclass(frozen=True, slots=True)
class PublishedReplyPreferences:
    profile: AgentReplyProfile | None
    operator_language: SupportedLanguage | None
    source: str


def resolve_published_reply_profile(
    agents: tuple["PublishedAgent", ...], *, primary_agent_id: uuid.UUID | None = None
) -> PublishedReplyPreferences:
    """仅实际参与者可决定表达；无明确主配置时冲突统一跟随本轮问题。"""
    primary = next((item for item in agents if item.id == primary_agent_id), None)
    if primary is not None:
        profile = primary.reply_profile
        return PublishedReplyPreferences(profile, profile.operator_language if profile else None, "explicit_primary")
    profiles = [item.reply_profile for item in agents]
    if not profiles or all(item is None for item in profiles):
        return PublishedReplyPreferences(None, None, "legacy")
    first = profiles[0]
    if all(item == first for item in profiles) and first is not None:
        return PublishedReplyPreferences(first, first.operator_language, "unanimous")
    # 旧发布无偏好时也不能借其他 Agent 的显式语种冒充全店共识。
    operators = {item.operator_language for item in profiles if item is not None}
    operator = next(iter(operators)) if len(operators) == 1 and all(item is not None for item in profiles) else None
    return PublishedReplyPreferences(AgentReplyProfile(), operator, "conflict_follow_question")
