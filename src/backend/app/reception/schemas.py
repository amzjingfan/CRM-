"""基础接待的文本配置边界模型。"""

import uuid
from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Scope = Literal["personal", "team"]
PolicyKind = Literal["timeout", "welcome"]
ValidityMode = Literal["long_term", "date_range", "fixed_hours"]


def _nonblank(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("文本不能为空")
    return value


class GroupCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_id: uuid.UUID
    scope: Scope
    name: str = Field(min_length=1, max_length=100)
    enabled: bool = True
    sort_order: int = Field(default=0, ge=0, le=100_000)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _nonblank(value)


class GroupUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    enabled: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=100_000)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        return _nonblank(value) if value is not None else None


class GroupView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    store_id: uuid.UUID
    scope: Scope
    owner_user_id: uuid.UUID | None
    name: str
    enabled: bool = True
    reply_count: int = 0
    sort_order: int


class ReplyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_id: uuid.UUID
    scope: Scope
    group_id: uuid.UUID
    shortcut: str = Field(pattern=r"^[A-Za-z0-9]{1,8}$")
    tags: list[str] = Field(default_factory=list, max_length=3)
    site_code: str | None = Field(default=None, min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    messages: list[str] = Field(min_length=1, max_length=5)
    sort_order: int = Field(default=0, ge=0, le=100_000)

    @field_validator("shortcut")
    @classmethod
    def normalize_shortcut(cls, value: str) -> str:
        return value.lower()

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, values: list[str]) -> list[str]:
        tags = [_nonblank(value) for value in values]
        if any(len(value) > 30 for value in tags) or len(set(tags)) != len(tags):
            raise ValueError("标签过长或重复")
        return tags

    @field_validator("messages")
    @classmethod
    def validate_messages(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values) or len("\n".join(values)) > 2000:
            raise ValueError("消息段不能为空且合并后最多 2000 字符")
        return values


class ReplyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_id: uuid.UUID | None = None
    shortcut: str | None = Field(default=None, pattern=r"^[A-Za-z0-9]{1,8}$")
    tags: list[str] | None = Field(default=None, max_length=3)
    site_code: str | None = Field(default=None, min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    messages: list[str] | None = Field(default=None, min_length=1, max_length=5)
    sort_order: int | None = Field(default=None, ge=0, le=100_000)

    @field_validator("shortcut")
    @classmethod
    def normalize_shortcut(cls, value: str | None) -> str | None:
        return value.lower() if value is not None else None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, values: list[str] | None) -> list[str] | None:
        return ReplyCreate.validate_tags(values) if values is not None else None

    @field_validator("messages")
    @classmethod
    def validate_messages(cls, values: list[str] | None) -> list[str] | None:
        return ReplyCreate.validate_messages(values) if values is not None else None


class ReplyView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    store_id: uuid.UUID
    scope: Scope
    owner_user_id: uuid.UUID | None
    group_id: uuid.UUID
    shortcut: str
    tags: list[str]
    site_code: str | None
    messages: list[str]
    sort_order: int


class PolicySchedule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: ValidityMode
    start_date: date | None = None
    end_date: date | None = None
    daily_start_time: time | None = None
    daily_end_time: time | None = None

    @model_validator(mode="after")
    def validate_schedule(self) -> "PolicySchedule":
        if self.mode == "long_term":
            if any(
                value is not None
                for value in (self.start_date, self.end_date, self.daily_start_time, self.daily_end_time)
            ):
                raise ValueError("长期策略不能设置起止日期或每日时段")
            return self
        if self.start_date is None or self.end_date is None or self.start_date > self.end_date:
            raise ValueError("有效期必须包含正确的起止日期")
        if any(
            value is not None and value.tzinfo is not None for value in (self.daily_start_time, self.daily_end_time)
        ):
            raise ValueError("每日时间必须是站点本地时间，不得附带时区")
        if self.mode == "date_range":
            if self.daily_start_time is not None or self.daily_end_time is not None:
                raise ValueError("起止策略不能设置每日时段")
        elif (
            self.daily_start_time is None or self.daily_end_time is None or self.daily_start_time >= self.daily_end_time
        ):
            raise ValueError("固定时段必须包含同一天内正确的起止时间")
        return self


class PolicyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: PolicyKind
    name: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=2000)
    timeout_minutes: int | None = Field(default=None, ge=1, le=43_200)
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    schedule: PolicySchedule | None = None
    enabled: bool = False
    sort_order: int = Field(default=0, ge=0, le=100_000)
    store_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)

    @field_validator("name", "content")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _nonblank(value)

    @model_validator(mode="after")
    def validate_policy(self) -> "PolicyCreate":
        if self.kind == "timeout" and self.timeout_minutes is None:
            raise ValueError("超时策略必须填写分钟数")
        if self.kind == "welcome" and self.timeout_minutes is not None:
            raise ValueError("欢迎语不能设置超时分钟数")
        if self.valid_from and self.valid_to and self.valid_from >= self.valid_to:
            raise ValueError("结束时间必须晚于开始时间")
        if self.schedule is not None and (self.valid_from is not None or self.valid_to is not None):
            raise ValueError("新有效期不能与旧时间字段同时设置")
        if any(value is not None and value.tzinfo is None for value in (self.valid_from, self.valid_to)):
            raise ValueError("有效期时间必须带时区")
        if len(set(self.store_ids)) != len(self.store_ids):
            raise ValueError("店铺不能重复")
        return self


class PolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, min_length=1, max_length=2000)
    timeout_minutes: int | None = Field(default=None, ge=1, le=43_200)
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    schedule: PolicySchedule | None = None
    enabled: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=100_000)
    store_ids: list[uuid.UUID] | None = Field(default=None, min_length=1, max_length=100)


class PolicyView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: PolicyKind
    name: str
    content: str
    timeout_minutes: int | None
    valid_from: datetime | None
    valid_to: datetime | None
    schedule: PolicySchedule | None = None
    enabled: bool
    sort_order: int
    store_ids: list[uuid.UUID]
    delivery_enabled: Literal[False] = False


class GroupPage(BaseModel):
    items: list[GroupView]
    total: int
    page: int
    page_size: int


class ReplyPage(BaseModel):
    items: list[ReplyView]
    total: int
    page: int
    page_size: int


class PolicyPage(BaseModel):
    items: list[PolicyView]
    total: int
    page: int
    page_size: int
