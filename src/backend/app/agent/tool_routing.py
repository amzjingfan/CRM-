"""以确定性规则把客户需求映射到 Phase 3 白名单工具。"""

import re

from app.agent.schemas import IntentName, RequiredToolName

ORDER_IDENTIFIER = re.compile(r"\b(?=[A-Z0-9-]{8,}\b)(?=[A-Z0-9-]*\d)[A-Z0-9-]+\b", re.IGNORECASE)
LOGISTICS_REALTIME = re.compile(
    r"(我的.*包裹|订单.*(?:到哪|哪里|位置|物流)|包裹.*(?:到哪|哪里|位置)|"
    r"where\s+is\s+my\s+(?:order|package)|track\s+my|tracking\s+(?:status|number))",
    re.IGNORECASE,
)
ORDER_STATUS = re.compile(r"(订单状态|我的订单|order\s+status|my\s+order)", re.IGNORECASE)
ADDRESS_UPDATE = re.compile(r"(改.*地址|修改.*地址|change\s+(?:my\s+)?(?:shipping\s+)?address)", re.IGNORECASE)
COUPON_REQUEST = re.compile(
    r"(发.*优惠券|补发.*优惠券|给.*优惠券|优惠券|coupon|voucher)",
    re.IGNORECASE,
)
CUSTOMER_PROFILE = re.compile(
    r"(会员(?:信息|等级|标签)|客户标签|我的标签|我的订单数|消费记录|member\s+(?:profile|tier)|customer\s+profile)",
    re.IGNORECASE,
)
HUMAN_HANDOFF = re.compile(
    r"(人工客服|转人工|找真人|投诉|取消订单|申请退款|human\s+agent|live\s+agent|cancel\s+order|refund)",
    re.IGNORECASE,
)


def detect_required_tools(message: str, intent: IntentName) -> list[RequiredToolName]:
    """只输出静态白名单名称，参数、权限和批准由后续执行层决定。"""
    if HUMAN_HANDOFF.search(message):
        return ["transfer_to_human"]
    if ADDRESS_UPDATE.search(message):
        return ["update_shipping_address"]
    if COUPON_REQUEST.search(message):
        return ["send_coupon"]
    if CUSTOMER_PROFILE.search(message):
        return ["query_customer_profile"]
    has_identifier = ORDER_IDENTIFIER.search(message) is not None
    if intent == IntentName.LOGISTICS_QUERY and (has_identifier or LOGISTICS_REALTIME.search(message)):
        return ["query_logistics"]
    if ORDER_STATUS.search(message):
        return ["query_order"]
    if intent in {IntentName.RETURN_POLICY, IntentName.GENERAL, IntentName.PRICE_INQUIRY} and (
        has_identifier or ORDER_STATUS.search(message)
    ):
        return ["query_order"]
    return []
