"""数据看板公开响应类型。"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

DashboardPeriod = Literal["today", "7d", "30d"]


class DashboardMetrics(BaseModel):
    total_sessions: int
    transfer_rate: float = Field(ge=0, le=100)
    avg_response_time: float | None
    recovered_gmv: Decimal
    currency: str
    period: DashboardPeriod
    updated_at: datetime | None
    intent_accuracy: float | None = Field(default=None, ge=0, le=100)
    intent_labeled_count: int = Field(default=0, ge=0)
    rag_hit_rate: float = Field(default=0, ge=0, le=100)
    tool_success_rate: float = Field(default=0, ge=0, le=100)
    p95_first_output_latency_ms: int | None = Field(default=None, ge=0)
    total_input_tokens: int = Field(default=0, ge=0)
    total_output_tokens: int = Field(default=0, ge=0)
    estimated_cost_usd: Decimal = Field(default=Decimal("0"), ge=0)
    cost_configured: bool = False


class TrendPoint(BaseModel):
    date: date
    sessions: int


class DashboardTrend(BaseModel):
    items: list[TrendPoint]


class ChannelItem(BaseModel):
    platform: str
    count: int
    percentage: float = Field(ge=0, le=100)


class DashboardChannels(BaseModel):
    items: list[ChannelItem]


class RefundAlert(BaseModel):
    total: int


class ReviewAlert(BaseModel):
    total: int
    golden_window: bool


class AbandonedCartAlert(BaseModel):
    total: int
    potential_gmv: Decimal


class DashboardAlerts(BaseModel):
    refund_requests: RefundAlert
    bad_reviews: ReviewAlert
    abandoned_carts: AbandonedCartAlert


class TopQueryItem(BaseModel):
    rank: int
    intent: str
    count: int
