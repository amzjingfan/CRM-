"""工具名称、分类、能力标签与授权条件的唯一目录。"""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from app.agents.tools.arguments import (
    AftersalesArguments,
    CollaborationArguments,
    ConversationHistoryArguments,
    CouponSearchArguments,
    EmptyArguments,
    KnowledgeArguments,
    LogisticsArguments,
    OrderSearchArguments,
    OrderSelectionArguments,
    ProductSearchArguments,
    ProductSelectionArguments,
)
from app.agents.tools.logistics_updates.contracts import NotificationArguments

Operation = Literal["read", "internal_write", "confirmation", "notification"]


class ToolGroup(BaseModel):
    key: str
    title: str
    description: str


GROUPS = (
    ToolGroup(key="orders", title="订单与物流", description="找到正确订单，核实交易与配送进度"),
    ToolGroup(key="products", title="商品与优惠", description="查询商品规格、可售状态和优惠条件"),
    ToolGroup(key="aftersales", title="售后服务", description="核实退货、退款与换货申请"),
    ToolGroup(key="customers", title="客户与会话", description="了解当前买家及本次会话上下文"),
    ToolGroup(key="knowledge", title="知识检索", description="从绑定文件中查找有来源的依据"),
    ToolGroup(key="collaboration", title="人工协作", description="保留内部建议，帮助坐席接手"),
)


@dataclass(frozen=True)
class ToolMetadata:
    name: str
    title: str
    description: str
    category: str
    operation: Operation
    permission: str
    arguments: type[BaseModel]
    scopes: tuple[str, ...] = ()
    any_scopes: tuple[str, ...] = ()
    requires_context: bool = True


_TOOLS = (
    ToolMetadata(
        "notify_logistics_update",
        "物流更新通知",
        "仅为服务端绑定的新物流节点生成一条买家语言通知；复核和策略授权后交付，默认审阅预览。普通问答不能主动发送。",
        "orders",
        "notification",
        "workspace.reply",
        NotificationArguments,
        ("seller.order.info", "seller.customer_service", "seller.logistics"),
    ),
    ToolMetadata(
        "search_customer_orders",
        "买家订单查询",
        "按状态、商品、订单号和时间查询当前买家订单，返回候选引用与分页。多订单时先选单。",
        "orders",
        "read",
        "orders.view",
        OrderSearchArguments,
        ("seller.order.info", "seller.customer_service"),
    ),
    ToolMetadata(
        "query_order",
        "订单详情",
        "核实已选择订单的金额、支付、履约时间、商品及规格；多订单无选择时返回候选，不能默认最新。",
        "orders",
        "read",
        "orders.view",
        OrderSelectionArguments,
        ("seller.order.info", "seller.customer_service"),
    ),
    ToolMetadata(
        "query_logistics",
        "物流进度",
        "默认只读所选订单的最新物流节点及时间，客户正文先给最新状态再附随后卡片；完整历史仅内部核查时显式请求并分页，增强轨迹按店铺能力提供。",
        "orders",
        "read",
        "orders.view",
        LogisticsArguments,
        ("seller.order.info", "seller.customer_service", "seller.logistics"),
    ),
    ToolMetadata(
        "search_products",
        "商品搜索",
        "按名称、SKU 或商家 SKU 搜索当前店铺商品，返回可供进一步查询的候选引用。",
        "products",
        "read",
        "workspace.view",
        ProductSearchArguments,
        ("seller.product.basic",),
        requires_context=False,
    ),
    ToolMetadata(
        "query_product",
        "商品详情",
        "使用本轮商品候选引用读取参数、品牌、描述、规格、价格、可售状态及平台提供的库存；长内容需继续分页。",
        "products",
        "read",
        "workspace.view",
        ProductSelectionArguments,
        ("seller.product.basic",),
        requires_context=False,
    ),
    ToolMetadata(
        "query_available_coupons",
        "优惠券查询",
        "只读查询店铺优惠券状态、优惠内容和有效期；查询不等于买家满足领取条件或已经发券。",
        "products",
        "read",
        "workspace.view",
        CouponSearchArguments,
        any_scopes=("seller.customer_service", "seller.promotion.info"),
        requires_context=False,
    ),
    ToolMetadata(
        "query_aftersales",
        "售后查询",
        "查询已选择订单的退货、退款、换货申请、金额、期限和退回物流；include_records读取所选申请的处理历史，缺授权不等于无售后。",
        "aftersales",
        "read",
        "orders.view",
        AftersalesArguments,
        ("seller.order.info", "seller.customer_service", "seller.return_refund.basic"),
    ),
    ToolMetadata(
        "query_customer_profile",
        "客户画像",
        "读取当前会话买家的 CRM 已同步标签、订单数、消费摘要与阶段；不代表平台完整历史，不提供地址电话。",
        "customers",
        "read",
        "workspace.view",
        EmptyArguments,
    ),
    ToolMetadata(
        "query_conversation_messages",
        "会话历史",
        "按需读取当前会话在本次运行冻结之前的历史消息；不能跨用户、跨会话读取。",
        "customers",
        "read",
        "workspace.view",
        ConversationHistoryArguments,
    ),
    ToolMetadata(
        "search_knowledge",
        "知识检索",
        "检索当前 Agent 显式绑定且仍获内部审批的知识文件，返回原文片段、版本和引用。"
        "查询使用完整问题语义；无命中可改写查询再检索，不代表文件不存在或未审批。",
        "knowledge",
        "read",
        "knowledge.view",
        KnowledgeArguments,
        requires_context=False,
    ),
    ToolMetadata(
        "create_handoff_request",
        "创建接管请求",
        "保存当前会话的 AI 接管建议、已查事实与未解决事项；不会完成实际会话转交。",
        "collaboration",
        "internal_write",
        "workspace.reply",
        CollaborationArguments,
    ),
    ToolMetadata(
        "add_internal_note",
        "添加内部备注",
        "在当前会话保存明确标为 AI 建议的内部备注，供坐席查阅；不会发送给买家。",
        "collaboration",
        "internal_write",
        "workspace.reply",
        CollaborationArguments,
    ),
    ToolMetadata(
        "update_shipping_address",
        "修改收货地址",
        "提出修改地址的人工确认请求；Agent 不执行地址变更。",
        "orders",
        "confirmation",
        "orders.address.update",
        EmptyArguments,
    ),
    ToolMetadata(
        "send_coupon",
        "发放优惠券",
        "提出发券的人工确认请求；Agent 不发放优惠券。",
        "products",
        "confirmation",
        "coupons.issue",
        EmptyArguments,
    ),
    ToolMetadata(
        "transfer_to_human",
        "实际转交会话",
        "提出会话转交的人工确认请求；Agent 不修改会话分配状态。",
        "collaboration",
        "confirmation",
        "workspace.transfer",
        EmptyArguments,
    ),
    ToolMetadata(
        "send_platform_message",
        "发送平台消息",
        "提出平台发送的人工确认请求；Agent 不发送任何真实消息。",
        "collaboration",
        "confirmation",
        "workspace.reply",
        EmptyArguments,
    ),
)
TOOL_METADATA = {item.name: item for item in _TOOLS}


class ToolMetadataView(BaseModel):
    name: str
    title: str
    description: str
    category: str
    operation: Operation
    requires_context: bool
    availability: Literal["available", "unavailable", "requires_context", "requires_knowledge", "confirmation"]
    reason: str
    missing_scopes: list[str] = Field(default_factory=list)


class ToolCatalogView(BaseModel):
    groups: list[ToolGroup]
    tools: list[ToolMetadataView]


def catalog_view(*, permissions: set[str], scopes: set[str], platform_available: bool = True) -> ToolCatalogView:
    """仅返回条件摘要，不泄露渠道或凭证；运行前仍需重新授权。"""
    views = []
    for item in _TOOLS:
        missing = [scope for scope in item.scopes if scope not in scopes]
        if item.any_scopes and not scopes.intersection(item.any_scopes):
            missing.append(" 或 ".join(item.any_scopes))
        availability: Literal["available", "unavailable", "requires_context", "requires_knowledge", "confirmation"]
        if item.permission not in permissions:
            availability, reason = "unavailable", f"缺少操作权限：{item.permission}"
        elif item.operation == "confirmation":
            availability, reason = "confirmation", "仅生成待人工确认的提议"
        elif (item.scopes or item.any_scopes) and not platform_available:
            availability, reason = "unavailable", "TikTok 只读开关或店铺授权尚不可用"
        elif missing:
            availability, reason = "unavailable", "缺少平台授权：" + "、".join(missing)
        elif item.name == "search_knowledge":
            availability, reason = "requires_knowledge", "仅检索已绑定且获批的文件"
        elif item.requires_context:
            availability, reason = "requires_context", "运行时需关联当前店铺的授权会话"
        else:
            availability, reason = "available", "可用"
        views.append(
            ToolMetadataView(
                name=item.name,
                title=item.title,
                description=item.description,
                category=item.category,
                operation=item.operation,
                requires_context=item.requires_context,
                availability=availability,
                reason=reason,
                missing_scopes=missing,
            )
        )
    return ToolCatalogView(groups=list(GROUPS), tools=views)
