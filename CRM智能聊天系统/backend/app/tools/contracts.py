"""全栈业务工具公开契约，供 HTTP、任务和 AI Agent 统一调用。"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ToolName = Literal[
    "query_order",
    "query_logistics",
    "query_customer_profile",
    "update_shipping_address",
    "send_coupon",
    "transfer_to_human",
    "send_platform_message",
]
WriteToolName = Literal[
    "update_shipping_address",
    "send_coupon",
    "transfer_to_human",
    "send_platform_message",
]
ToolStatus = Literal["succeeded", "failed", "timeout", "unknown"]

WRITE_TOOL_NAMES: frozenset[str] = frozenset(
    {"update_shipping_address", "send_coupon", "transfer_to_human", "send_platform_message"}
)


class StrictToolArguments(BaseModel):
    """工具参数一律拒绝额外字段，防止模型把未授权数据传入执行层。"""

    model_config = ConfigDict(extra="forbid")


class QueryOrderArguments(StrictToolArguments):
    """查询订单所需的可信订单标识。"""

    order_id: str = Field(min_length=1, max_length=200)


class QueryLogisticsArguments(QueryOrderArguments):
    """查询物流所需的可信订单标识。"""


class QueryCustomerProfileArguments(StrictToolArguments):
    """查询客户画像所需的店铺内客户标识。"""

    customer_id: uuid.UUID


class UpdateShippingAddressArguments(StrictToolArguments):
    """地址修改参数；仅允许可信业务层批准后进入工具执行器。"""

    order_id: str = Field(min_length=1, max_length=200)
    recipient_name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=50)
    address_line1: str = Field(min_length=1, max_length=300)
    address_line2: str | None = Field(default=None, max_length=300)
    city: str = Field(min_length=1, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    postal_code: str = Field(min_length=1, max_length=30)
    country_code: str = Field(pattern=r"^[A-Z]{2}$")


class SendCouponArguments(StrictToolArguments):
    """优惠券发放参数；优惠码和目标客户不能由模型自由生成。"""

    customer_id: uuid.UUID
    coupon_code: str = Field(pattern=r"^[A-Za-z0-9_-]+$", min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    expires_at: datetime | None = None


class TransferToHumanArguments(StrictToolArguments):
    """转人工参数；会话 ID 始终来自可信上下文。"""

    conversation_id: uuid.UUID
    reason: str = Field(min_length=1, max_length=500)
    assign_to: uuid.UUID | None = None


class SendPlatformMessageArguments(StrictToolArguments):
    """平台发送参数；只能由批准发送的内部流程调用。"""

    conversation_id: uuid.UUID
    content: str = Field(min_length=1, max_length=4000)


class StrictToolOutput(BaseModel):
    """工具输出同样拒绝额外字段，避免污染数据进入 Agent 上下文。"""

    model_config = ConfigDict(extra="forbid")


class OrderToolData(StrictToolOutput):
    """订单查询返回的最小标准化事实。"""

    order_id: uuid.UUID
    external_order_id: str = Field(min_length=1, max_length=200)
    status: str = Field(min_length=1, max_length=30)
    payment_status: str | None = Field(default=None, max_length=30)
    fulfillment_status: str | None = Field(default=None, max_length=30)
    currency: str = Field(min_length=1, max_length=10)
    total_amount: str = Field(min_length=1, max_length=50)
    ordered_at: datetime | None = None


class LogisticsToolData(StrictToolOutput):
    """物流查询返回的最小标准化事实。"""

    order_id: uuid.UUID
    external_order_id: str = Field(min_length=1, max_length=200)
    tracking_number: str | None = Field(default=None, max_length=200)
    tracking_status: str | None = Field(default=None, max_length=100)
    shipped_at: datetime | None = None
    delivered_at: datetime | None = None


class CustomerProfileToolData(StrictToolOutput):
    """客户画像查询返回的非联系方式字段。"""

    customer_id: uuid.UUID
    tags: list[str] = Field(default_factory=list, max_length=100)
    order_count: int = Field(ge=0)
    total_spend: str = Field(min_length=1, max_length=50)


READ_REPLAY_CONTRACT_VERSION: Literal[1] = 1


class OrderReadReplayData(StrictToolOutput):
    """订单查询首次成功结果的低敏恢复快照（v1）。"""

    order_id: uuid.UUID
    status: str = Field(min_length=1, max_length=30)


class LogisticsReadReplayData(StrictToolOutput):
    """物流查询首次成功结果的低敏恢复快照（v1）。"""

    order_id: uuid.UUID
    tracking_status: str | None = Field(max_length=100)


class CustomerProfileReadReplayData(StrictToolOutput):
    """客户画像查询首次成功结果的低敏恢复快照（v1）。"""

    customer_id: uuid.UUID
    order_count: int = Field(ge=0)


class ShippingAddressToolData(StrictToolOutput):
    """地址变更请求的安全结果。"""

    order_id: uuid.UUID
    status: Literal["pending_confirmation"]
    mocked: Literal[True]


class CouponToolData(StrictToolOutput):
    """优惠券发放结果；当前阶段固定为 Mock。"""

    issuance_id: uuid.UUID
    coupon_code: str = Field(min_length=1, max_length=100)
    status: str = Field(min_length=1, max_length=30)
    mocked: Literal[True]


class TransferToolData(StrictToolOutput):
    """人工接管写入结果。"""

    transfer_id: uuid.UUID
    status: Literal["transferred"]


class PlatformMessageToolData(StrictToolOutput):
    """已批准平台消息发送的持久化结果。"""

    message_id: uuid.UUID
    status: str = Field(min_length=1, max_length=20)
    mocked: bool


TOOL_ARGUMENT_SCHEMAS: dict[str, type[StrictToolArguments]] = {
    "query_order": QueryOrderArguments,
    "query_logistics": QueryLogisticsArguments,
    "query_customer_profile": QueryCustomerProfileArguments,
    "update_shipping_address": UpdateShippingAddressArguments,
    "send_coupon": SendCouponArguments,
    "transfer_to_human": TransferToHumanArguments,
    "send_platform_message": SendPlatformMessageArguments,
}

TOOL_OUTPUT_SCHEMAS: dict[str, type[StrictToolOutput]] = {
    "query_order": OrderToolData,
    "query_logistics": LogisticsToolData,
    "query_customer_profile": CustomerProfileToolData,
    "update_shipping_address": ShippingAddressToolData,
    "send_coupon": CouponToolData,
    "transfer_to_human": TransferToolData,
    "send_platform_message": PlatformMessageToolData,
}

READ_TOOL_REPLAY_OUTPUT_SCHEMAS: dict[str, type[StrictToolOutput]] = {
    "query_order": OrderReadReplayData,
    "query_logistics": LogisticsReadReplayData,
    "query_customer_profile": CustomerProfileReadReplayData,
}


def validate_tool_arguments(tool_name: str, arguments: dict[str, object]) -> dict[str, object]:
    """按工具名称执行强类型校验并返回标准 JSON 参数。

    模型输出、客户消息和跨模块调用都属于不可信输入。工具名称不在白名单、
    字段缺失、额外字段或格式错误时必须在产生业务副作用前失败。
    """
    schema = TOOL_ARGUMENT_SCHEMAS.get(tool_name)
    if schema is None:
        raise ValueError("工具不在允许的白名单中")
    return schema.model_validate(arguments).model_dump(mode="json")


def validate_tool_output(tool_name: str, data: dict[str, object]) -> dict[str, object]:
    """校验成功工具结果并转换为 JSON 安全结构。"""
    schema = TOOL_OUTPUT_SCHEMAS.get(tool_name)
    if schema is None:
        raise ValueError("工具不在允许的白名单中")
    return schema.model_validate(data).model_dump(mode="json")


def validate_read_tool_replay_output(tool_name: str, data: dict[str, object]) -> dict[str, object]:
    """按 v1 低敏契约校验只读工具重放快照。"""
    schema = READ_TOOL_REPLAY_OUTPUT_SCHEMAS.get(tool_name)
    if schema is None:
        raise ValueError("工具没有只读重放契约")
    return schema.model_validate(data).model_dump(mode="json")


class ToolDefinition(BaseModel):
    """工具注册信息；执行器只允许调用此白名单和固定契约。"""

    name: ToolName
    input_schema: str
    output_schema: str
    permission: str
    timeout_ms: int = Field(gt=0, le=60_000)
    idempotency_required: bool
    success_conditions: tuple[str, ...] = Field(min_length=1)
    error_codes: tuple[str, ...] = Field(min_length=1)
    audit_action: str

    @property
    def required_permission(self) -> str:
        """兼容既有全栈调用方使用的权限字段名称。"""
        return self.permission

    @property
    def timeout_seconds(self) -> float:
        """把毫秒契约转换为 asyncio 使用的秒数。"""
        return self.timeout_ms / 1000


class ToolExecutionContext(BaseModel):
    """由可信后端生成的身份和店铺上下文，模型不得自行构造权限。"""

    store_id: uuid.UUID
    actor_type: Literal["user", "agent", "job"]
    actor_id: uuid.UUID | None = None
    permissions: set[str] = Field(default_factory=set)
    agent_run_id: uuid.UUID | None = None
    trace_id: str | None = None
    # 只由人工 HTTP Service 在完成二次确认后设置。Agent/Job 即使能构造
    # 工具参数，也不能把普通消息升级为真实平台写操作。
    human_confirmed: bool = False


class ToolInvocation(BaseModel):
    """受控工具调用命令。"""

    tool_name: ToolName
    idempotency_key: str = Field(min_length=1, max_length=200)
    arguments: dict[str, object]
    context: ToolExecutionContext


class ToolResult(BaseModel):
    """不暴露内部异常和敏感输入的工具结果。"""

    tool_call_id: uuid.UUID
    status: ToolStatus
    data: dict[str, object] | None = None
    error_code: str | None = None
    mocked: bool = False
    replayed: bool = False
    replay_contract_version: Literal[1] | None = None


TOOL_DEFINITIONS: dict[str, ToolDefinition] = {
    item.name: item
    for item in [
        ToolDefinition(
            name="query_order",
            input_schema="QueryOrderArguments",
            output_schema="OrderToolData",
            permission="orders.view",
            timeout_ms=5_000,
            idempotency_required=False,
            success_conditions=("订单属于当前店铺", "返回标准化订单摘要"),
            error_codes=(
                "TOOL_RESOURCE_NOT_FOUND",
                "TOOL_PERMISSION_DENIED",
                "TOOL_TIMEOUT",
                "TOOL_OUTPUT_INVALID",
            ),
            audit_action="order.query",
        ),
        ToolDefinition(
            name="query_logistics",
            input_schema="QueryLogisticsArguments",
            output_schema="LogisticsToolData",
            permission="orders.view",
            timeout_ms=5_000,
            idempotency_required=False,
            success_conditions=("订单属于当前店铺", "返回标准化物流摘要"),
            error_codes=(
                "TOOL_RESOURCE_NOT_FOUND",
                "TOOL_PERMISSION_DENIED",
                "TOOL_TIMEOUT",
                "TOOL_OUTPUT_INVALID",
            ),
            audit_action="logistics.query",
        ),
        ToolDefinition(
            name="query_customer_profile",
            input_schema="QueryCustomerProfileArguments",
            output_schema="CustomerProfileToolData",
            permission="workspace.view",
            timeout_ms=5_000,
            idempotency_required=False,
            success_conditions=("客户属于当前店铺", "仅返回最小画像字段"),
            error_codes=(
                "TOOL_RESOURCE_NOT_FOUND",
                "TOOL_PERMISSION_DENIED",
                "TOOL_TIMEOUT",
                "TOOL_OUTPUT_INVALID",
            ),
            audit_action="customer.query",
        ),
        ToolDefinition(
            name="update_shipping_address",
            input_schema="UpdateShippingAddressArguments",
            output_schema="ShippingAddressToolData",
            permission="orders.address.update",
            timeout_ms=10_000,
            idempotency_required=True,
            success_conditions=("请求已进入待平台确认状态", "Mock 状态明确可见"),
            error_codes=(
                "TOOL_RESOURCE_NOT_FOUND",
                "TOOL_PERMISSION_DENIED",
                "TOOL_IDEMPOTENCY_CONFLICT",
                "TOOL_TIMEOUT",
                "TOOL_OUTPUT_INVALID",
            ),
            audit_action="order.address.update",
        ),
        ToolDefinition(
            name="send_coupon",
            input_schema="SendCouponArguments",
            output_schema="CouponToolData",
            permission="coupons.issue",
            timeout_ms=10_000,
            idempotency_required=True,
            success_conditions=("优惠券记录已创建", "Mock 状态明确可见"),
            error_codes=(
                "TOOL_RESOURCE_NOT_FOUND",
                "TOOL_PERMISSION_DENIED",
                "TOOL_IDEMPOTENCY_CONFLICT",
                "TOOL_TIMEOUT",
                "TOOL_OUTPUT_INVALID",
            ),
            audit_action="coupon.issue",
        ),
        ToolDefinition(
            name="transfer_to_human",
            input_schema="TransferToHumanArguments",
            output_schema="TransferToolData",
            permission="workspace.transfer",
            timeout_ms=5_000,
            idempotency_required=True,
            success_conditions=("会话状态为 transferred", "审计记录已创建"),
            error_codes=(
                "TOOL_RESOURCE_NOT_FOUND",
                "TOOL_PERMISSION_DENIED",
                "TOOL_IDEMPOTENCY_CONFLICT",
                "TOOL_TIMEOUT",
                "TOOL_OUTPUT_INVALID",
            ),
            audit_action="conversation.transfer",
        ),
        ToolDefinition(
            name="send_platform_message",
            input_schema="SendPlatformMessageArguments",
            output_schema="PlatformMessageToolData",
            permission="workspace.reply",
            timeout_ms=15_000,
            idempotency_required=True,
            success_conditions=("消息状态为 sent", "平台结果和审计状态已保存"),
            error_codes=(
                "TOOL_RESOURCE_NOT_FOUND",
                "TOOL_PERMISSION_DENIED",
                "TOOL_HUMAN_CONFIRMATION_REQUIRED",
                "TOOL_IDEMPOTENCY_CONFLICT",
                "TOOL_RECONCILIATION_REQUIRED",
                "TOOL_RESULT_UNKNOWN",
                "TOOL_TIMEOUT",
            ),
            audit_action="message.send",
        ),
    ]
}
