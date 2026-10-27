"""把可信 FAQ 或工具结果渲染为可自动交付的固定回复。"""

import re
import unicodedata
import uuid
from collections.abc import Iterable

from pydantic import ValidationError

from app.agent.business_claims import (
    BusinessClaim,
    BusinessClaimAction,
    BusinessClaimCondition,
    BusinessClaimEvidenceType,
    BusinessClaimInventory,
    BusinessClaimPolarity,
    BusinessClaimSubjectType,
    BusinessClaimTense,
    TrustedToolEvidence,
)
from app.agent.reply_policy import SupportedLanguage
from app.agent.tool_execution import ExecutedAgentTool
from app.knowledge_base.schemas import KnowledgeRetrievalHit
from app.tools.contracts import (
    READ_REPLAY_CONTRACT_VERSION,
    validate_read_tool_replay_output,
    validate_tool_output,
)

_ANSWER_MARKER = re.compile(r"(?:^|\n)\s*(?:答案|answer)\s*[:：]\s*", re.IGNORECASE)
_WHITESPACE = re.compile(r"\s+")

_LOGISTICS_TEMPLATES: dict[str, dict[SupportedLanguage, str]] = {
    "pending": {"zh-CN": "订单物流信息正在准备中。", "en": "The shipment information is being prepared."},
    "shipped": {
        "zh-CN": "订单已经发货，请继续留意物流更新。",
        "en": "The order has shipped. Please watch for tracking updates.",
    },
    "in_transit": {
        "zh-CN": "订单正在运输中，请继续留意物流更新。",
        "en": "The order is in transit. Please watch for tracking updates.",
    },
    "delivered": {
        "zh-CN": "物流状态显示订单已经送达。",
        "en": "The shipment status shows that the order was delivered.",
    },
}
_ORDER_TEMPLATES: dict[str, dict[SupportedLanguage, str]] = {
    "pending": {"zh-CN": "订单当前处于待处理状态。", "en": "The order is currently pending."},
    "paid": {"zh-CN": "订单当前已支付。", "en": "The order is currently paid."},
    "shipped": {"zh-CN": "订单当前已发货。", "en": "The order is currently shipped."},
    "delivered": {"zh-CN": "订单当前已送达。", "en": "The order is currently delivered."},
    "completed": {"zh-CN": "订单当前已完成。", "en": "The order is currently completed."},
    "cancelled": {"zh-CN": "订单当前已取消。", "en": "The order is currently cancelled."},
}


def render_trusted_faq_reply(
    hits: list[KnowledgeRetrievalHit],
    citation_ids: list[uuid.UUID],
    model_answer: str,
) -> str | None:
    """仅当模型答案与单条已发布 FAQ 的答案原文一致时返回可信文本。

    自动回复不接受模型改写。多引用、无法提取答案或任何文字差异都降级为
    人工复核，从根源上阻止模型把 FAQ 政策扩写成客户退款或资金事实。
    """
    if len(citation_ids) != 1:
        return None
    hit = next((item for item in hits if item.chunk_id == citation_ids[0]), None)
    if hit is None:
        return None
    if hit.source_type != "faq":
        return None
    answer = extract_trusted_faq_answer(hit)
    if answer is None or _normalize_text(answer) != _normalize_text(model_answer):
        return None
    return answer


def render_trusted_tool_reply(
    executions: list[ExecutedAgentTool],
    language: SupportedLanguage,
    model_answer: str,
) -> str | None:
    """仅允许查询工具的有限状态通过固定模板形成自动回复。"""
    template = build_trusted_tool_template(executions, language)
    if template is None or _normalize_text(template) != _normalize_text(model_answer):
        return None
    return template


def extract_trusted_faq_answer(hit: KnowledgeRetrievalHit) -> str | None:
    """从已发布 FAQ 命中提取可逐字复制的答案模板。"""
    if hit.source_type != "faq":
        return None
    return _extract_faq_answer(hit.content)


def build_trusted_tool_template(
    executions: list[ExecutedAgentTool],
    language: SupportedLanguage,
) -> str | None:
    """从单个真实查询结果生成固定客服文本，未知状态不生成模板。"""
    successful = [item for item in executions if item.result.status == "succeeded" and not item.result.mocked]
    if len(successful) != 1:
        return None
    execution = successful[0]
    data = _validated_tool_data(execution)
    if data is None:
        return None
    if execution.tool_name == "query_logistics":
        status = data.get("tracking_status")
        return _template_for_status(_LOGISTICS_TEMPLATES, status, language)
    if execution.tool_name == "query_order":
        status = data.get("status")
        return _template_for_status(_ORDER_TEMPLATES, status, language)
    return None


def build_debug_tool_fallback_reply(executions: list[ExecutedAgentTool], language: SupportedLanguage) -> str | None:
    """调试时只用已校验的单次只读结果生成不含对象标识的固定提示。"""
    successful = [item for item in executions if item.result.status == "succeeded" and not item.result.mocked]
    if len(successful) != 1 or _validated_tool_data(successful[0]) is None:
        return None
    tool_name = successful[0].tool_name
    if tool_name not in {"query_order", "query_logistics", "query_customer_profile"}:
        return None
    template = build_trusted_tool_template(executions, language)
    if template is None:
        fallback = {
            "query_order": {
                "zh-CN": "当前订单状态需要坐席核对。",
                "en": "An agent needs to verify the current order status.",
            },
            "query_logistics": {
                "zh-CN": "当前没有可核验的配送状态。请坐席核对。",
                "en": "No verified delivery status is available. An agent should check it.",
            },
            "query_customer_profile": {
                "zh-CN": "已读取当前会话的客户资料。请坐席核对。",
                "en": "The customer profile was read. An agent should review it.",
            },
        }[tool_name][language]
    else:
        fallback = template
    prefix = "【系统固定提示·非模型原文】" if language == "zh-CN" else "[System fact prompt. Not model text] "
    return prefix + fallback


def build_trusted_tool_evidence(
    executions: Iterable[ExecutedAgentTool],
) -> dict[uuid.UUID, TrustedToolEvidence]:
    """从已校验工具输出提取对象 ID，并保留执行时固定的店铺来源。

    当前工作流的店铺只应由安全策略作为 ``expected_store_id`` 参与比较，
    不能在此处给工具结果重新贴标。旧替身若没有携带执行来源则失败关闭，
    不生成可用于自动交付的可信证据。
    """
    evidence: dict[uuid.UUID, TrustedToolEvidence] = {}
    for execution in executions:
        result = execution.result
        if result.status != "succeeded" or execution.source_store_id is None:
            continue
        data = _validated_tool_data(execution)
        if data is None:
            continue
        subject_ids = _tool_subject_ids(execution, data)
        if not subject_ids:
            continue
        evidence[result.tool_call_id] = TrustedToolEvidence(
            tool_name=execution.tool_name,
            store_id=execution.source_store_id,
            subject_ids=frozenset(subject_ids),
            mocked=result.mocked or bool(data.get("mocked", False)),
        )
    return evidence


def build_authoritative_tool_claims(
    executions: Iterable[ExecutedAgentTool],
) -> BusinessClaimInventory:
    """由执行层为已验证工具结果生成对象级声明。

    真实对象 ID 只在服务端可信边界内使用，不发送给模型。订单与物流只
    接受有限已知状态；画像、地址请求、优惠券和平台消息只按强类型工具
    输出生成声明。Mock 写结果也形成声明，但随后由安全策略明确阻断为
    真实完成事实，不能因为不生成声明而绕过审计。
    """
    claims: list[BusinessClaim] = []
    for execution in executions:
        result = execution.result
        if result.status != "succeeded":
            continue
        data = _validated_tool_data(execution)
        if data is None:
            continue
        subject_id = _primary_subject_id(execution, data)
        if subject_id is None:
            continue
        if execution.tool_name == "query_logistics":
            if result.mocked:
                continue
            status = data.get("tracking_status")
            if not isinstance(status, str) or status.casefold() not in _LOGISTICS_TEMPLATES:
                continue
            subject_type = BusinessClaimSubjectType.LOGISTICS
            action = BusinessClaimAction.REPORT_STATUS
        elif execution.tool_name == "query_order":
            if result.mocked:
                continue
            status = data.get("status")
            if not isinstance(status, str) or status.casefold() not in _ORDER_TEMPLATES:
                continue
            subject_type = BusinessClaimSubjectType.ORDER
            action = BusinessClaimAction.REPORT_STATUS
        elif execution.tool_name == "query_customer_profile":
            if result.mocked:
                continue
            subject_type = BusinessClaimSubjectType.CUSTOMER_PROFILE
            action = BusinessClaimAction.REPORT_STATUS
        elif execution.tool_name == "update_shipping_address":
            if data.get("status") != "pending_confirmation":
                continue
            subject_type = BusinessClaimSubjectType.SHIPPING_ADDRESS
            action = BusinessClaimAction.SUBMIT_REQUEST
        elif execution.tool_name == "send_coupon":
            if data.get("status") != "issued":
                continue
            subject_type = BusinessClaimSubjectType.COUPON
            action = BusinessClaimAction.SEND
        elif execution.tool_name == "send_platform_message":
            if data.get("status") != "sent":
                continue
            subject_type = BusinessClaimSubjectType.PLATFORM_MESSAGE
            action = BusinessClaimAction.SEND
        else:
            continue
        claims.append(
            BusinessClaim(
                subject_type=subject_type,
                subject_id=subject_id,
                action=action,
                tense=BusinessClaimTense.PRESENT,
                polarity=BusinessClaimPolarity.AFFIRMED,
                condition=BusinessClaimCondition.ACTUAL,
                evidence_type=BusinessClaimEvidenceType.TOOL_CALL,
                evidence_id=result.tool_call_id,
                confidence=1.0,
            )
        )
    return BusinessClaimInventory(complete=True, claims=claims)


def bind_redacted_tool_claims(
    model_claims: BusinessClaimInventory,
    authoritative_claims: BusinessClaimInventory,
) -> BusinessClaimInventory:
    """把模型可见的脱敏占位符绑定到执行层已验证的真实主体。

    该转换只接受证据 ID、主体类型和动作都与代码声明完全一致的占位符。
    模型提供的其他真实值或错误类型不会被修正，仍由安全策略拒绝，因而
    不会削弱跨订单、跨工具和跨对象校验。
    """
    subjects_by_key = {
        (claim.evidence_id, claim.subject_type, claim.action): claim.subject_id
        for claim in authoritative_claims.claims
        if claim.subject_id is not None
    }
    bound_claims: list[BusinessClaim] = []
    for claim in model_claims.claims:
        if claim.subject_id != "[SENSITIVE_ID]":
            bound_claims.append(claim)
            continue
        subject_id = subjects_by_key.get((claim.evidence_id, claim.subject_type, claim.action))
        bound_claims.append(claim.model_copy(update={"subject_id": subject_id or claim.subject_id}))
    return BusinessClaimInventory(complete=True, claims=bound_claims)


def _extract_faq_answer(content: str) -> str | None:
    """提取 FAQ 规范内容中的答案部分；无标记内容整体视为答案。"""
    matches = list(_ANSWER_MARKER.finditer(content))
    answer = content[matches[-1].end() :] if matches else content
    normalized = _normalize_text(answer)
    return normalized if 0 < len(normalized) <= 2000 else None


def _normalize_text(value: str) -> str:
    """只统一 Unicode 与空白，不做同义改写或模糊匹配。"""
    return _WHITESPACE.sub(" ", unicodedata.normalize("NFC", value)).strip()


def _template_for_status(
    templates: dict[str, dict[SupportedLanguage, str]],
    status: object,
    language: SupportedLanguage,
) -> str | None:
    """只渲染代码已收录的标准状态，未知平台值转人工。"""
    if not isinstance(status, str):
        return None
    localized = templates.get(status.casefold())
    return localized.get(language) if localized else None


def _tool_subject_ids(execution: ExecutedAgentTool, data: dict[str, object]) -> set[str]:
    """按工具契约提取可被声明引用的业务对象 ID。"""
    keys_by_tool = {
        "query_order": ("order_id", "external_order_id"),
        "query_logistics": ("order_id", "external_order_id"),
        "query_customer_profile": ("customer_id",),
        "update_shipping_address": ("order_id",),
        "send_coupon": ("issuance_id",),
        "transfer_to_human": ("transfer_id",),
        "send_platform_message": ("message_id",),
    }
    return {str(data[key]) for key in keys_by_tool[execution.tool_name] if data.get(key) is not None}


def _primary_subject_id(execution: ExecutedAgentTool, data: dict[str, object]) -> str | None:
    """按工具契约选择唯一主对象供代码声明使用。"""
    primary_keys = {
        "query_order": ("order_id", "external_order_id"),
        "query_logistics": ("order_id", "external_order_id"),
        "query_customer_profile": ("customer_id",),
        "update_shipping_address": ("order_id",),
        "send_coupon": ("issuance_id",),
        "send_platform_message": ("message_id",),
    }
    for key in primary_keys.get(execution.tool_name, ()):
        value = data.get(key)
        if value is not None:
            return str(value)
    return None


def _validated_tool_data(execution: ExecutedAgentTool) -> dict[str, object] | None:
    """在权威渲染边界再次执行输出 Schema，拒绝替代端口绕过执行器校验。"""
    data = execution.result.data
    if data is None:
        return None
    try:
        if execution.result.replayed and execution.result.replay_contract_version == READ_REPLAY_CONTRACT_VERSION:
            return validate_read_tool_replay_output(execution.tool_name, data)
        return validate_tool_output(execution.tool_name, data)
    except (ValidationError, ValueError):
        return None
