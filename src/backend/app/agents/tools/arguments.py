"""模型可填业务参数；租户、会话和客户标识只来自服务端。"""

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from app.tools.contracts import StrictToolArguments


class EmptyArguments(StrictToolArguments):
    pass


class OrderSearchArguments(StrictToolArguments):
    query: str = Field(default="", max_length=100, description="订单号、物流号、商品名称或 SKU 关键词")
    field: Literal["order", "tracking", "product", "spu", "sku", "sellerSku"] = "order"
    status: Literal["all", "unpaid", "ship", "transit", "done", "cancel"] = "all"
    created_after: datetime | None = Field(default=None, description="带时区的下单时间下界，包含")
    created_before: datetime | None = Field(default=None, description="带时区的下单时间上界，不包含")
    page: int = Field(default=1, ge=1, le=10000)

    @model_validator(mode="after")
    def validate_window(self) -> "OrderSearchArguments":
        for value in (self.created_after, self.created_before):
            if value is not None and value.tzinfo is None:
                raise ValueError("时间筛选必须带时区")
        if self.created_after and self.created_before and self.created_after >= self.created_before:
            raise ValueError("时间范围无效")
        return self


class OrderSelectionArguments(StrictToolArguments):
    order_ref: str | None = Field(
        default=None,
        pattern=r"^o[1-9][0-9]*$",
        max_length=20,
        description="search_customer_orders 本次运行返回的候选引用；多订单时必须选择",
    )


class LogisticsArguments(OrderSelectionArguments):
    enhanced: bool = Field(default=False, description="仅受支持的跨境店使用增强多包裹轨迹")
    event_offset: int = Field(
        default=0, ge=0, le=1000000, description="轨迹续读位置，使用返回的next_event_offset；已读完时可设为event_count"
    )
    package_offset: int = Field(
        default=0,
        ge=0,
        le=1000000,
        description="包裹续读位置，使用返回的next_package_offset；已读完时可设为package_count",
    )


class AftersalesArguments(OrderSelectionArguments):
    return_ref: str | None = Field(
        default=None,
        pattern=r"^r[1-9][0-9]*$",
        max_length=20,
        description="本次查询返回的售后申请引用，查询具体处理记录时使用",
    )
    include_records: bool = Field(default=False, description="查询处理历史；多条申请时先选择 return_ref")
    page: int = Field(default=1, ge=1, le=10000, description="所选申请的商品明细与处理记录页码")
    page_size: int = Field(default=5, ge=1, le=10)
    page_ref: str | None = Field(
        default=None,
        pattern=r"^a[1-9][0-9]*$",
        max_length=20,
        description="本工具上一页返回的 next_page_ref，不接受平台 token",
    )


class ProductSearchArguments(StrictToolArguments):
    query: str = Field(default="", max_length=100)
    field: Literal["name", "sku", "sellerSku"] = "name"
    page_ref: str | None = Field(default=None, pattern=r"^p[1-9][0-9]*$", max_length=20)


class ProductSelectionArguments(StrictToolArguments):
    product_ref: str = Field(
        pattern=r"^p[1-9][0-9]*$", max_length=20, description="search_products 本次运行返回的商品候选引用"
    )
    page: int = Field(default=1, ge=1, le=10000, description="规格、参数和描述的页码；继续读取直到 next_page 为空")
    page_size: int = Field(default=10, ge=1, le=20)


class CouponSearchArguments(StrictToolArguments):
    query: str = Field(default="", max_length=100)
    field: Literal["name", "code"] = "name"
    page_ref: str | None = Field(default=None, pattern=r"^c[1-9][0-9]*$", max_length=20)


class ConversationHistoryArguments(StrictToolArguments):
    offset: int = Field(default=0, ge=0, le=100000, description="从本轮冻结的会话历史倒序分页")
    limit: int = Field(default=10, ge=1, le=20)


class CollaborationArguments(StrictToolArguments):
    content: str = Field(
        min_length=1,
        max_length=2000,
        description="AI 建议，包含问题摘要、已查事实、引用和待解决事项；不能声称已发送或已转交",
    )


class KnowledgeArguments(StrictToolArguments):
    query: str = Field(min_length=1, max_length=4000)
