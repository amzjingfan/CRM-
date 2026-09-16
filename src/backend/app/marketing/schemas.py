"""主动营销管理接口类型。"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class CampaignCreate(BaseModel):
    """创建店铺级营销活动。"""

    store_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    trigger_type: Literal["cart_abandoned", "bad_review"]
    action_type: Literal["send_message", "send_coupon", "send_coupon_and_message"]
    content_mode: Literal["template", "ai"]
    template_content: str | None = Field(default=None, max_length=4000)
    coupon_code: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]+$", max_length=100)
    trigger_delay_minutes: int = Field(default=30, ge=5, le=43_200)
    cooldown_hours: int = Field(default=24, ge=1, le=720)
    max_contacts_30d: int = Field(default=3, ge=1, le=30)

    @model_validator(mode="after")
    def validate_action_inputs(self) -> "CampaignCreate":
        """模板和优惠券动作必须具备确定输入，AI 模式只进入等待状态。"""
        if self.content_mode == "template" and "message" in self.action_type and not self.template_content:
            raise ValueError("模板消息不能为空")
        if "coupon" in self.action_type and not self.coupon_code:
            raise ValueError("优惠券动作必须填写 coupon_code")
        return self


class CampaignUpdate(BaseModel):
    """营销活动可编辑配置。"""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    action_type: Literal["send_message", "send_coupon", "send_coupon_and_message"] | None = None
    content_mode: Literal["template", "ai"] | None = None
    template_content: str | None = Field(default=None, max_length=4000)
    coupon_code: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]+$", max_length=100)
    trigger_delay_minutes: int | None = Field(default=None, ge=5, le=43_200)
    cooldown_hours: int | None = Field(default=None, ge=1, le=720)
    max_contacts_30d: int | None = Field(default=None, ge=1, le=30)


class CampaignView(BaseModel):
    """营销活动展示结构。"""

    id: uuid.UUID
    store_id: uuid.UUID
    name: str
    trigger_type: str
    action_type: str
    content_mode: str
    template_content: str | None
    coupon_code: str | None
    trigger_delay_minutes: int
    cooldown_hours: int
    max_contacts_30d: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CampaignPage(BaseModel):
    """营销活动分页。"""

    items: list[CampaignView]
    page: int
    page_size: int
    total: int


class MarketingEventView(BaseModel):
    """营销执行与转化记录。"""

    id: uuid.UUID
    store_id: uuid.UUID
    campaign_id: uuid.UUID
    customer_id: uuid.UUID | None
    source_type: str
    source_id: uuid.UUID
    status: str
    attempt_count: int
    error_code: str | None
    ai_draft_content: str | None
    ai_draft_agent_run_id: uuid.UUID | None
    ai_review_status: str | None
    ai_reviewed_by: uuid.UUID | None
    ai_reviewed_at: datetime | None
    triggered_at: datetime
    completed_at: datetime | None
    converted_at: datetime | None

    model_config = {"from_attributes": True}


class MarketingEventPage(BaseModel):
    """营销事件分页。"""

    items: list[MarketingEventView]
    page: int
    page_size: int
    total: int


class MarketingDraftReview(BaseModel):
    """人工审核 AI 营销草稿；本契约不包含发送动作。"""

    decision: Literal["approve", "reject"]
    comment: str | None = Field(default=None, max_length=500)
