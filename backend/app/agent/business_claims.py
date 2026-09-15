"""定义 AI 回复中的规范化业务声明及确定性证据校验。

自然语言只负责展示，授权判断只依赖本模块中的有限业务语义和本次运行的
可信证据 ID。这样新增同义词不会改变退款、资金移动和平台写操作的权限
边界；旧文本扫描仅作为遗漏声明时的纵深防御。
"""

import uuid
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.tools.contracts import ToolName


class BusinessClaimSubjectType(StrEnum):
    """声明主体的稳定业务类型，不接受模型临时创造类型。"""

    REFUND_POLICY = "refund_policy"
    REFUND_REQUEST = "refund_request"
    REFUND_DECISION = "refund_decision"
    REFUND_FUNDS = "refund_funds"
    ORDER = "order"
    LOGISTICS = "logistics"
    CUSTOMER_PROFILE = "customer_profile"
    SHIPPING_ADDRESS = "shipping_address"
    COUPON = "coupon"
    PROMISE_TIME = "promise_time"
    PLATFORM_MESSAGE = "platform_message"
    NON_BUSINESS_ARTIFACT = "non_business_artifact"
    OTHER = "other"


class BusinessClaimAction(StrEnum):
    """把开放语言动作映射到可审计的有限业务动作。"""

    EXPLAIN_POLICY = "explain_policy"
    SUBMIT_REQUEST = "submit_request"
    APPROVE = "approve"
    REJECT = "reject"
    EXECUTE = "execute"
    TRANSFER_FUNDS = "transfer_funds"
    RECEIVE_FUNDS = "receive_funds"
    REPORT_STATUS = "report_status"
    QUERY = "query"
    UPDATE = "update"
    SEND = "send"
    PROMISE = "promise"
    DISPLAY = "display"
    OTHER = "other"


class BusinessClaimTense(StrEnum):
    """声明对应的时间属性。"""

    PAST = "past"
    PRESENT = "present"
    FUTURE = "future"
    TIMELESS = "timeless"


class BusinessClaimPolarity(StrEnum):
    """区分肯定事实、直接否定和不确定判断。"""

    AFFIRMED = "affirmed"
    NEGATED = "negated"
    UNCERTAIN = "uncertain"


class BusinessClaimCondition(StrEnum):
    """区分当前事实与条件、假设、引用和示例。"""

    ACTUAL = "actual"
    CONDITIONAL = "conditional"
    HYPOTHETICAL = "hypothetical"
    QUOTED = "quoted"
    EXAMPLE = "example"


class BusinessClaimEvidenceType(StrEnum):
    """业务声明允许绑定的可信来源类型。"""

    NONE = "none"
    FAQ_CHUNK = "faq_chunk"
    TOOL_CALL = "tool_call"
    TRIGGER_CONTEXT = "trigger_context"


class BusinessClaim(BaseModel):
    """单条规范化业务声明；不保存自然语言原文或敏感工具结果。"""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    subject_type: BusinessClaimSubjectType
    subject_id: str | None = Field(default=None, min_length=1, max_length=200)
    action: BusinessClaimAction
    tense: BusinessClaimTense
    polarity: BusinessClaimPolarity
    condition: BusinessClaimCondition
    evidence_type: BusinessClaimEvidenceType
    evidence_id: uuid.UUID | None
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_evidence_reference(self) -> "BusinessClaim":
        """校验主体动作组合和证据引用，拒绝模型临时重定义语义。"""
        allowed_actions = _ALLOWED_ACTIONS_BY_SUBJECT[self.subject_type]
        if self.action not in allowed_actions:
            raise ValueError("业务声明的 subject_type 与 action 不匹配")
        requires_id = self.evidence_type in {
            BusinessClaimEvidenceType.FAQ_CHUNK,
            BusinessClaimEvidenceType.TOOL_CALL,
        }
        if requires_id and self.evidence_id is None:
            raise ValueError("FAQ 或工具业务声明必须提供 evidence_id")
        if not requires_id and self.evidence_id is not None:
            raise ValueError("无具体证据的业务声明不得提供 evidence_id")
        if self.subject_type in _SUBJECTS_REQUIRING_ID and self.subject_id is None:
            raise ValueError("客户实例业务声明必须提供脱敏或可信 subject_id")
        return self


class BusinessClaimInventory(BaseModel):
    """模型对候选回复中全部业务声明的完整清单。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    complete: Literal[True]
    claims: list[BusinessClaim] = Field(max_length=12)

    @model_validator(mode="after")
    def validate_claim_scope_consistency(self) -> "BusinessClaimInventory":
        """拒绝同一主体动作给出重复或互相冲突的命题。

        证据 ID 和时态不能把同一业务命题拆成互不相干的记录。模型若用
        不同引用或时态同时输出“已完成”和“未完成”，下游仍无法确定哪一条
        对应正文，因此在结构化边界直接失败关闭。
        """
        seen_claims: set[tuple[object, ...]] = set()
        for claim in self.claims:
            claim_key = (
                claim.subject_type,
                claim.subject_id,
                claim.action,
            )
            if claim_key in seen_claims:
                raise ValueError("同一主体和动作不能包含重复或互相冲突的业务命题")
            seen_claims.add(claim_key)
        return self


class TrustedToolEvidence(BaseModel):
    """由工具执行结果构造的可信资源证据，模型无权创建或修改。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_name: ToolName
    store_id: uuid.UUID
    subject_ids: frozenset[str] = Field(min_length=1, max_length=4)
    mocked: bool = False


_TOOL_EVIDENCE_BY_CLAIM: dict[
    tuple[BusinessClaimSubjectType, BusinessClaimAction],
    frozenset[str],
] = {
    (BusinessClaimSubjectType.ORDER, BusinessClaimAction.REPORT_STATUS): frozenset({"query_order"}),
    (BusinessClaimSubjectType.LOGISTICS, BusinessClaimAction.REPORT_STATUS): frozenset({"query_logistics"}),
    (BusinessClaimSubjectType.CUSTOMER_PROFILE, BusinessClaimAction.REPORT_STATUS): frozenset(
        {"query_customer_profile"}
    ),
    (BusinessClaimSubjectType.SHIPPING_ADDRESS, BusinessClaimAction.SUBMIT_REQUEST): frozenset(
        {"update_shipping_address"}
    ),
    (BusinessClaimSubjectType.SHIPPING_ADDRESS, BusinessClaimAction.UPDATE): frozenset({"update_shipping_address"}),
    (BusinessClaimSubjectType.COUPON, BusinessClaimAction.SEND): frozenset({"send_coupon"}),
    (BusinessClaimSubjectType.PLATFORM_MESSAGE, BusinessClaimAction.SEND): frozenset({"send_platform_message"}),
}

_ALLOWED_ACTIONS_BY_SUBJECT: dict[BusinessClaimSubjectType, frozenset[BusinessClaimAction]] = {
    BusinessClaimSubjectType.REFUND_POLICY: frozenset({BusinessClaimAction.EXPLAIN_POLICY}),
    BusinessClaimSubjectType.REFUND_REQUEST: frozenset(
        {BusinessClaimAction.SUBMIT_REQUEST, BusinessClaimAction.REPORT_STATUS}
    ),
    BusinessClaimSubjectType.REFUND_DECISION: frozenset(
        {BusinessClaimAction.APPROVE, BusinessClaimAction.REJECT, BusinessClaimAction.REPORT_STATUS}
    ),
    BusinessClaimSubjectType.REFUND_FUNDS: frozenset(
        {
            BusinessClaimAction.EXECUTE,
            BusinessClaimAction.TRANSFER_FUNDS,
            BusinessClaimAction.RECEIVE_FUNDS,
            BusinessClaimAction.REPORT_STATUS,
        }
    ),
    BusinessClaimSubjectType.ORDER: frozenset({BusinessClaimAction.QUERY, BusinessClaimAction.REPORT_STATUS}),
    BusinessClaimSubjectType.LOGISTICS: frozenset({BusinessClaimAction.QUERY, BusinessClaimAction.REPORT_STATUS}),
    BusinessClaimSubjectType.CUSTOMER_PROFILE: frozenset(
        {BusinessClaimAction.QUERY, BusinessClaimAction.REPORT_STATUS}
    ),
    BusinessClaimSubjectType.SHIPPING_ADDRESS: frozenset(
        {BusinessClaimAction.QUERY, BusinessClaimAction.SUBMIT_REQUEST, BusinessClaimAction.UPDATE}
    ),
    BusinessClaimSubjectType.COUPON: frozenset(
        {BusinessClaimAction.QUERY, BusinessClaimAction.SEND, BusinessClaimAction.DISPLAY}
    ),
    BusinessClaimSubjectType.PROMISE_TIME: frozenset({BusinessClaimAction.PROMISE}),
    BusinessClaimSubjectType.PLATFORM_MESSAGE: frozenset({BusinessClaimAction.SEND}),
    BusinessClaimSubjectType.NON_BUSINESS_ARTIFACT: frozenset(
        {BusinessClaimAction.DISPLAY, BusinessClaimAction.UPDATE, BusinessClaimAction.OTHER}
    ),
    BusinessClaimSubjectType.OTHER: frozenset({BusinessClaimAction.OTHER}),
}

_SUBJECTS_REQUIRING_ID = {
    BusinessClaimSubjectType.REFUND_REQUEST,
    BusinessClaimSubjectType.REFUND_DECISION,
    BusinessClaimSubjectType.REFUND_FUNDS,
    BusinessClaimSubjectType.ORDER,
    BusinessClaimSubjectType.LOGISTICS,
    BusinessClaimSubjectType.CUSTOMER_PROFILE,
    BusinessClaimSubjectType.SHIPPING_ADDRESS,
    BusinessClaimSubjectType.COUPON,
    BusinessClaimSubjectType.PROMISE_TIME,
    BusinessClaimSubjectType.PLATFORM_MESSAGE,
}

_HIGH_RISK_INSTANCE_SUBJECTS = _SUBJECTS_REQUIRING_ID

_ALLOWED_TENSES_BY_ACTION: dict[BusinessClaimAction, frozenset[BusinessClaimTense]] = {
    BusinessClaimAction.EXPLAIN_POLICY: frozenset({BusinessClaimTense.TIMELESS}),
    BusinessClaimAction.REPORT_STATUS: frozenset({BusinessClaimTense.PRESENT}),
    BusinessClaimAction.SUBMIT_REQUEST: frozenset({BusinessClaimTense.PAST, BusinessClaimTense.PRESENT}),
    BusinessClaimAction.APPROVE: frozenset({BusinessClaimTense.PAST, BusinessClaimTense.PRESENT}),
    BusinessClaimAction.REJECT: frozenset({BusinessClaimTense.PAST, BusinessClaimTense.PRESENT}),
    BusinessClaimAction.EXECUTE: frozenset({BusinessClaimTense.PAST, BusinessClaimTense.PRESENT}),
    BusinessClaimAction.TRANSFER_FUNDS: frozenset({BusinessClaimTense.PAST, BusinessClaimTense.PRESENT}),
    BusinessClaimAction.RECEIVE_FUNDS: frozenset({BusinessClaimTense.PAST, BusinessClaimTense.PRESENT}),
    BusinessClaimAction.UPDATE: frozenset({BusinessClaimTense.PAST, BusinessClaimTense.PRESENT}),
    BusinessClaimAction.SEND: frozenset({BusinessClaimTense.PAST, BusinessClaimTense.PRESENT}),
    BusinessClaimAction.QUERY: frozenset({BusinessClaimTense.PRESENT}),
    BusinessClaimAction.DISPLAY: frozenset({BusinessClaimTense.PRESENT}),
    BusinessClaimAction.PROMISE: frozenset({BusinessClaimTense.FUTURE}),
}

_REFUND_OUTCOME_SUBJECTS = {
    BusinessClaimSubjectType.REFUND_REQUEST,
    BusinessClaimSubjectType.REFUND_DECISION,
    BusinessClaimSubjectType.REFUND_FUNDS,
}


class BusinessClaimPolicy:
    """只根据规范动作和可信证据绑定判断业务声明是否可用。"""

    def evaluate(
        self,
        inventory: BusinessClaimInventory,
        *,
        evidence_kind: str,
        faq_evidence_ids: AbstractSet[uuid.UUID],
        successful_tool_evidence: Mapping[uuid.UUID, TrustedToolEvidence],
        mocked_tool_call_ids: AbstractSet[uuid.UUID],
        expected_store_id: uuid.UUID | None = None,
    ) -> list[str]:
        """返回稳定原因码；正文中的动词同义词不会参与授权判断。"""
        reason_codes: list[str] = []
        for claim in inventory.claims:
            evidence_error = self._evidence_error(
                claim,
                evidence_kind=evidence_kind,
                faq_evidence_ids=faq_evidence_ids,
                successful_tool_evidence=successful_tool_evidence,
                expected_store_id=expected_store_id,
            )
            if evidence_error:
                reason_codes.append(evidence_error)
                continue
            if claim.subject_type in _HIGH_RISK_INSTANCE_SUBJECTS and not self._is_asserted_actual_claim(claim):
                # 现有 DTO 只有极性和条件标签，没有独立的否定/条件作用域树。
                # 对客户实例事实，任何非“肯定且当前成立”的组合都无法证明正文
                # 的作用域，必须转人工，不能因为它看似是否定句就跳过证据检查。
                reason_codes.append("AMBIGUOUS_BUSINESS_CLAIM_SCOPE")
                continue
            if claim.subject_type in _REFUND_OUTCOME_SUBJECTS:
                # 当前白名单工具没有退款申请、审批、打款或到账事实端口。
                # FAQ 只能解释政策，不能证明当前客户实例的退款动作。
                reason_codes.append("UNAUTHORIZED_COMMITMENT")
                continue
            allowed_tenses = _ALLOWED_TENSES_BY_ACTION.get(claim.action)
            if allowed_tenses is not None and claim.tense not in allowed_tenses:
                reason_codes.append("BUSINESS_CLAIM_TENSE_MISMATCH")
                continue
            if not self._is_asserted_actual_claim(claim):
                continue
            if claim.subject_type == BusinessClaimSubjectType.PROMISE_TIME:
                # 当前工具层没有“承诺时效”证据端口；订单/物流查询只能证明
                # 当前状态，不能证明未来到达时间，因此该能力上线前一律失败关闭。
                reason_codes.append("UNAUTHORIZED_COMMITMENT")
                continue
            allowed_tools = _TOOL_EVIDENCE_BY_CLAIM.get((claim.subject_type, claim.action))
            if allowed_tools is None:
                if claim.subject_type in _HIGH_RISK_INSTANCE_SUBJECTS:
                    # 所有客户实例事实必须存在明确的可信工具映射；有效 FAQ
                    # 引用、无证据声明或未登记工具都不能证明实例动作。
                    reason_codes.append("INVALID_BUSINESS_CLAIM_EVIDENCE")
                continue
            evidence = successful_tool_evidence.get(claim.evidence_id) if claim.evidence_id is not None else None
            if (
                evidence is None
                or evidence.tool_name not in allowed_tools
                or claim.subject_id is None
                or claim.subject_id not in evidence.subject_ids
            ):
                reason_codes.append("INVALID_BUSINESS_CLAIM_EVIDENCE")
                continue
            if (claim.evidence_id in mocked_tool_call_ids or evidence.mocked) and claim.action in {
                BusinessClaimAction.SUBMIT_REQUEST,
                BusinessClaimAction.SEND,
                BusinessClaimAction.UPDATE,
            }:
                reason_codes.append("MOCK_COMPLETION_CLAIM")
        return list(dict.fromkeys(reason_codes))

    @staticmethod
    def _is_asserted_actual_claim(claim: BusinessClaim) -> bool:
        """否定、存疑、条件、假设、引述和示例不是当前完成事实。"""
        return claim.polarity == BusinessClaimPolarity.AFFIRMED and claim.condition == BusinessClaimCondition.ACTUAL

    @staticmethod
    def _evidence_error(
        claim: BusinessClaim,
        *,
        evidence_kind: str,
        faq_evidence_ids: AbstractSet[uuid.UUID],
        successful_tool_evidence: Mapping[uuid.UUID, TrustedToolEvidence],
        expected_store_id: uuid.UUID | None,
    ) -> str | None:
        """校验声明来源属于本次运行，拒绝跨运行或伪造引用。"""
        if claim.evidence_type == BusinessClaimEvidenceType.FAQ_CHUNK:
            if evidence_kind != "faq" or claim.evidence_id not in faq_evidence_ids:
                return "INVALID_BUSINESS_CLAIM_EVIDENCE"
        elif claim.evidence_type == BusinessClaimEvidenceType.TOOL_CALL:
            evidence = successful_tool_evidence.get(claim.evidence_id) if claim.evidence_id is not None else None
            if (
                evidence_kind != "tool"
                or evidence is None
                or (expected_store_id is not None and evidence.store_id != expected_store_id)
            ):
                return "INVALID_BUSINESS_CLAIM_EVIDENCE"
            allowed_tools = _TOOL_EVIDENCE_BY_CLAIM.get((claim.subject_type, claim.action))
            if (
                allowed_tools is None
                or evidence.tool_name not in allowed_tools
                or claim.subject_id is None
                or claim.subject_id not in evidence.subject_ids
            ):
                return "INVALID_BUSINESS_CLAIM_EVIDENCE"
        elif (
            claim.subject_type == BusinessClaimSubjectType.REFUND_POLICY
            and claim.action == BusinessClaimAction.EXPLAIN_POLICY
            and claim.polarity == BusinessClaimPolarity.AFFIRMED
        ):
            return "INVALID_BUSINESS_CLAIM_EVIDENCE"
        return None
