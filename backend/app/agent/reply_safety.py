"""对所有 AI 草稿执行供应商无关的确定性安全门禁。"""

import re
import uuid
from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from enum import StrEnum

from pydantic import BaseModel, Field

from app.agent.business_claims import (
    BusinessClaimAction,
    BusinessClaimCondition,
    BusinessClaimInventory,
    BusinessClaimPolarity,
    BusinessClaimPolicy,
    BusinessClaimSubjectType,
    TrustedToolEvidence,
)
from app.agent.refund_safety import RefundFactPolicy
from app.agent.security import ALPHANUMERIC_ID_PATTERN, EMAIL_PATTERN, PHONE_PATTERN
from app.knowledge_base.schemas import (
    KnowledgePublicationApproval,
    KnowledgeSafetyMetadata,
    KnowledgeStatementType,
)

_LEGACY_KNOWLEDGE_METADATA_NOT_PROVIDED = object()


class ReplyEvidenceKind(StrEnum):
    """区分草稿可以依赖的事实来源。"""

    FAQ = "faq"
    TOOL = "tool"
    MARKETING = "marketing"


class ReplyContentOrigin(StrEnum):
    """记录回复文本来源；来源可信不等于已取得业务自动交付审批。"""

    UNSTRUCTURED = "unstructured"
    MODEL_GENERATED = "model_generated"
    TRUSTED_FAQ_TEMPLATE = "trusted_faq_template"
    TRUSTED_TOOL_TEMPLATE = "trusted_tool_template"


class ReplySafetyResult(BaseModel):
    """低敏安全检查结果；内容安全不等于具备自动发送授权。"""

    is_safe: bool
    automatic_delivery_allowed: bool = False
    reason_codes: list[str] = Field(default_factory=list, max_length=8)


GENERAL_UNAUTHORIZED_COMMITMENT_PATTERNS = (
    re.compile(
        r"(?<!不)(?<!不会)(?<!不能)(?<!无法)(?:保证|承诺|一定|必定|肯定)"
        r".{0,12}(?:退款|赔偿|补偿|优惠券|到账|送达)"
    ),
    re.compile(r"(?:guarantee|promise|definitely).{0,24}(?:refund|compensat|coupon|arriv|deliver)", re.IGNORECASE),
    re.compile(r"(?:退款|赔偿|补偿)\s*(?:人民币|RMB|CNY|USD|\$|¥)?\s*\d+(?:\.\d+)?", re.IGNORECASE),
)
REFUND_FACT_POLICY = RefundFactPolicy()
BUSINESS_CLAIM_POLICY = BusinessClaimPolicy()
ORDER_STATUS_PATTERNS = (
    re.compile(r"(?:您的|你的)?订单(?:已经|已|正在|目前).{0,20}(?:发货|运输|派送|签收|送达|取消)"),
    re.compile(r"(?:您的|你的)?订单.{0,20}(?:明天|今天|肯定|一定|预计).{0,12}(?:到达|送达|派送)"),
    re.compile(
        r"(?:your\s+)?order\s+(?:has|is|was).{0,24}(?:shipped|transit|delivered|cancelled|arrive)", re.IGNORECASE
    ),
    re.compile(r"(?:物流|包裹|快递)(?:显示|信息为|状态为)?.{0,20}(?:已|已经|正在)(?:离开|到达|运输|派送|签收|送达)"),
    re.compile(
        r"(?:tracking|shipment|parcel|package).{0,24}(?:has|is|was).{0,20}"
        r"(?:left|arrived|transit|delivered|shipped)",
        re.IGNORECASE,
    ),
)
ADDRESS_COMPLETION_PATTERNS = (
    re.compile(r"(?:已经|已|为您).{0,12}(?:修改|更新|变更).{0,10}(?:收货)?地址"),
    re.compile(r"(?:收货)?地址.{0,10}(?:已经|已)(?:修改|更新|变更)"),
    re.compile(
        r"(?:we|i)\s+(?:have|has).{0,16}(?:changed|updated).{0,16}(?:shipping\s+)?address",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:shipping\s+)?address.{0,20}(?:has been|was).{0,12}(?:changed|updated)",
        re.IGNORECASE,
    ),
)
MOCK_COMPLETION_PATTERNS = (
    re.compile(r"(?:优惠券|消息|地址).{0,16}(?:已经|已)(?:真实)?(?:发放|发送|修改|更新|完成)"),
    re.compile(r"(?:已经|已|为您).{0,16}(?:发放|发送|修改|更新).{0,12}(?:优惠券|消息|地址)"),
    re.compile(
        r"(?:coupon|message|address).{0,24}(?:has been|was|successfully)\s+(?:issued|sent|updated)", re.IGNORECASE
    ),
    re.compile(
        r"(?:we|i)\s+(?:have|has).{0,16}(?:issued|sent|changed|updated).{0,16}"
        r"(?:coupon|message|address)",
        re.IGNORECASE,
    ),
)


class ReplySafetyPolicy:
    """用代码拦截敏感数据和高风险业务承诺。

    模型安全复核仍会保留，但它不能替代这层确定性门禁。工具事实只有在
    对应白名单查询成功后才可用于订单状态；Mock 写结果永远不能被描述成
    真实平台动作已经完成。
    """

    def evaluate(
        self,
        answer: str,
        *,
        evidence_kind: ReplyEvidenceKind,
        successful_tools: AbstractSet[str] | None = None,
        has_mock_result: bool = False,
        claim_inventory: BusinessClaimInventory | None = None,
        faq_evidence_ids: AbstractSet[uuid.UUID] | None = None,
        successful_tool_evidence: Mapping[uuid.UUID, TrustedToolEvidence] | None = None,
        mocked_tool_call_ids: AbstractSet[uuid.UUID] | None = None,
        content_origin: ReplyContentOrigin = ReplyContentOrigin.UNSTRUCTURED,
        expected_store_id: uuid.UUID | None = None,
        knowledge_safety_metadata: Sequence[KnowledgeSafetyMetadata] | None | object = (
            _LEGACY_KNOWLEDGE_METADATA_NOT_PROVIDED
        ),
    ) -> ReplySafetyResult:
        """返回稳定原因码，并单独给出自动发送授权。

        模型生成文本和旧兼容入口即使没有命中已知风险，也只能供人工复核。
        只有代码从当次真实查询工具结果确定性渲染的文本才可能获得自动
        发送授权。FAQ 当前没有类型化事实范围和发布审批，逐字一致只能证明
        文本来源，不能证明它有权陈述客户实例状态。
        """
        tool_evidence = {
            evidence_id: (
                evidence if isinstance(evidence, TrustedToolEvidence) else TrustedToolEvidence.model_validate(evidence)
            )
            for evidence_id, evidence in (successful_tool_evidence or {}).items()
        }
        tools = set(successful_tools or set()) | {item.tool_name for item in tool_evidence.values()}
        reason_codes: list[str] = []
        if knowledge_safety_metadata is not _LEGACY_KNOWLEDGE_METADATA_NOT_PROVIDED:
            reason_codes.extend(
                self._evaluate_knowledge_safety(
                    knowledge_safety_metadata,
                    tool_evidence=tool_evidence,
                    expected_store_id=expected_store_id,
                )
            )
        if self._contains_sensitive_identifier(answer):
            reason_codes.append("SENSITIVE_DATA_EXPOSURE")
        if claim_inventory is not None:
            reason_codes.extend(
                BUSINESS_CLAIM_POLICY.evaluate(
                    claim_inventory,
                    evidence_kind=evidence_kind.value,
                    faq_evidence_ids=faq_evidence_ids or set(),
                    successful_tool_evidence=tool_evidence,
                    mocked_tool_call_ids=mocked_tool_call_ids or set(),
                    expected_store_id=expected_store_id,
                )
            )
        has_general_commitment = any(pattern.search(answer) for pattern in GENERAL_UNAUTHORIZED_COMMITMENT_PATTERNS)
        has_unsupported_refund_text = REFUND_FACT_POLICY.contains_unsupported_fact(answer)
        # 结构化元数据已经证明全部引用均为当前店铺、当前审批版本的政策、
        # 技术资产或非断言命题时，旧自然语言词法规则只保留观测价值，不能
        # 再覆盖类型化审批结论。客户实例、缺失审批、跨店铺和版本漂移不会
        # 进入该分支，仍由结构化知识门禁和业务声明策略失败关闭。
        approved_non_customer_knowledge = self._is_approved_non_customer_knowledge(
            knowledge_safety_metadata,
            expected_store_id=expected_store_id,
        )
        legacy_claim_rules_block = not approved_non_customer_knowledge
        # 模型自由文本本来就没有自动交付资格。旧退款扫描对它继续失败关闭
        # 只会把合法技术对象误杀并隐藏，无法解决未收录表达；此时由结构化
        # 高风险声明承担硬阻断，漏报或错分则保守留给人工复核。
        legacy_refund_blocks = content_origin != ReplyContentOrigin.MODEL_GENERATED and legacy_claim_rules_block
        if (legacy_claim_rules_block and has_general_commitment) or (
            legacy_refund_blocks and claim_inventory is None and has_unsupported_refund_text
        ):
            reason_codes.append("UNAUTHORIZED_COMMITMENT")
        elif (
            legacy_refund_blocks
            and has_unsupported_refund_text
            and claim_inventory is not None
            and not self._declares_refund_outcome(claim_inventory)
        ):
            # 结构化清单漏掉正文中的已知高风险模式时失败关闭。这里仅检测
            # 声明完整性，不再根据自然语言词表授予任何业务权限。
            reason_codes.append("BUSINESS_CLAIM_INVENTORY_MISMATCH")
        has_order_claim = any(pattern.search(answer) for pattern in ORDER_STATUS_PATTERNS)
        has_order_evidence = bool(tools & {"query_order", "query_logistics"})
        if (
            legacy_claim_rules_block
            and has_order_claim
            and (evidence_kind != ReplyEvidenceKind.TOOL or not has_order_evidence)
        ):
            reason_codes.append("FABRICATED_ORDER_STATUS")
        has_address_claim = any(pattern.search(answer) for pattern in ADDRESS_COMPLETION_PATTERNS)
        has_address_evidence = "update_shipping_address" in tools
        if (
            legacy_claim_rules_block
            and has_address_claim
            and (evidence_kind != ReplyEvidenceKind.TOOL or not has_address_evidence)
        ):
            reason_codes.append("UNAUTHORIZED_COMMITMENT")
        if has_mock_result and (claim_inventory is None or not claim_inventory.claims):
            # Mock 执行结果若无法形成强类型声明，说明重放摘要或替代端口已经
            # 丢失动作语义。此时不能依赖自然语言词表猜测是否“真实完成”，
            # 必须直接失败关闭并保留统一原因码。
            reason_codes.append("MOCK_COMPLETION_CLAIM")
        elif has_mock_result and any(pattern.search(answer) for pattern in MOCK_COMPLETION_PATTERNS):
            reason_codes.append("MOCK_COMPLETION_CLAIM")
        trusted_origin = content_origin == ReplyContentOrigin.TRUSTED_TOOL_TEMPLATE
        if trusted_origin and (claim_inventory is None or not claim_inventory.claims):
            # “可信模板”只是来源标签，不是事实授权。确定性工具回复必须同时
            # 携带由服务端生成的对象级声明；缺少或空清单时一律失败关闭。
            reason_codes.append("BUSINESS_CLAIM_INVENTORY_MISSING")
        unique_reason_codes = list(dict.fromkeys(reason_codes))
        return ReplySafetyResult(
            is_safe=not unique_reason_codes,
            automatic_delivery_allowed=trusted_origin and not unique_reason_codes,
            reason_codes=unique_reason_codes,
        )

    @staticmethod
    def _is_approved_non_customer_knowledge(
        metadata_items: Sequence[KnowledgeSafetyMetadata] | None | object,
        *,
        expected_store_id: uuid.UUID | None,
    ) -> bool:
        """仅当全部引用都属于当前店铺、当前版本且经人工审批时停用旧词表裁决。"""
        if not isinstance(metadata_items, Sequence) or not metadata_items or expected_store_id is None:
            return False
        allowed_types = {
            KnowledgeStatementType.POLICY,
            KnowledgeStatementType.TECHNICAL_ARTIFACT,
            KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
        }
        return all(
            isinstance(metadata, KnowledgeSafetyMetadata)
            and metadata.store_id == expected_store_id
            and metadata.document_version == metadata.approved_document_version
            and metadata.publication_approval != KnowledgePublicationApproval.DRAFT
            and metadata.statement_type in allowed_types
            for metadata in metadata_items
        )

    @staticmethod
    def _evaluate_knowledge_safety(
        metadata_items: Sequence[KnowledgeSafetyMetadata] | None | object,
        *,
        tool_evidence: Mapping[uuid.UUID, TrustedToolEvidence],
        expected_store_id: uuid.UUID | None,
    ) -> list[str]:
        """执行知识审批矩阵；任何缺失、越权或版本漂移都失败关闭。"""
        if not isinstance(metadata_items, Sequence) or not metadata_items:
            return ["KNOWLEDGE_SAFETY_METADATA_MISSING"]
        reasons: list[str] = []
        for metadata in metadata_items:
            if not isinstance(metadata, KnowledgeSafetyMetadata):
                reasons.append("KNOWLEDGE_SAFETY_METADATA_INVALID")
                continue
            if expected_store_id is None or metadata.store_id != expected_store_id:
                reasons.append("KNOWLEDGE_SAFETY_STORE_MISMATCH")
            if metadata.document_version != metadata.approved_document_version:
                reasons.append("KNOWLEDGE_SAFETY_VERSION_MISMATCH")
            if (
                metadata.publication_approval == KnowledgePublicationApproval.DRAFT
                or metadata.statement_type == KnowledgeStatementType.UNKNOWN
            ):
                reasons.append("KNOWLEDGE_SAFETY_METADATA_UNAPPROVED")
            if metadata.statement_type == KnowledgeStatementType.CUSTOMER_INSTANCE_FACT:
                has_same_store_real_tool = any(
                    evidence.store_id == expected_store_id
                    and not evidence.mocked
                    and evidence.tool_name in {"query_order", "query_logistics", "query_customer_profile"}
                    for evidence in tool_evidence.values()
                )
                if not has_same_store_real_tool:
                    reasons.append("KNOWLEDGE_CUSTOMER_FACT_REQUIRES_TOOL")
        return reasons

    @staticmethod
    def _declares_refund_outcome(inventory: BusinessClaimInventory) -> bool:
        """判断清单是否显式声明了当前肯定的退款审批或资金结果。"""
        return any(
            claim.subject_type
            in {
                BusinessClaimSubjectType.REFUND_REQUEST,
                BusinessClaimSubjectType.REFUND_DECISION,
                BusinessClaimSubjectType.REFUND_FUNDS,
            }
            and claim.action
            in {
                BusinessClaimAction.SUBMIT_REQUEST,
                BusinessClaimAction.APPROVE,
                BusinessClaimAction.REJECT,
                BusinessClaimAction.EXECUTE,
                BusinessClaimAction.TRANSFER_FUNDS,
                BusinessClaimAction.RECEIVE_FUNDS,
                BusinessClaimAction.REPORT_STATUS,
            }
            and claim.polarity == BusinessClaimPolarity.AFFIRMED
            and claim.condition == BusinessClaimCondition.ACTUAL
            for claim in inventory.claims
        )

    @staticmethod
    def _contains_sensitive_identifier(answer: str) -> bool:
        """占位符可安全展示，原始邮箱、电话和长标识必须阻断。"""
        without_placeholders = answer.replace("[EMAIL]", "").replace("[SENSITIVE_ID]", "")
        return bool(
            EMAIL_PATTERN.search(without_placeholders)
            or PHONE_PATTERN.search(without_placeholders)
            or ALPHANUMERIC_ID_PATTERN.search(without_placeholders)
        )
