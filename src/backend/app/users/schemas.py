"""团队管理 API 类型。"""

import uuid
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class TeamRoleAssignment(BaseModel):
    role: Literal["admin", "supervisor", "agent"]
    store_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def validate_scope(self) -> "TeamRoleAssignment":
        if self.role == "admin" and self.store_id is not None:
            raise ValueError("admin 必须是系统级角色")
        if self.role != "admin" and self.store_id is None:
            raise ValueError("supervisor 和 agent 必须指定店铺")
        return self


class TeamRoleView(BaseModel):
    role: str
    store_id: uuid.UUID | None


class TeamMemberCreate(BaseModel):
    login_name: str | None = Field(default=None, pattern=r"^[A-Za-z][A-Za-z0-9_-]{5,15}$")
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, pattern=r"^\+?[0-9][0-9 -]{5,19}$")
    timezone: str = Field(default="Asia/Shanghai", max_length=64)
    max_concurrent_sessions: int = Field(default=50, ge=1, le=1000)
    temporary_password: str = Field(min_length=12, max_length=128)
    assignments: list[TeamRoleAssignment] = Field(min_length=1, max_length=100)
    department_id: uuid.UUID | None = None

    @field_validator("login_name")
    @classmethod
    def normalize_login_name(cls, value: str | None) -> str | None:
        return value.lower() if value is not None else None

    @model_validator(mode="after")
    def require_login_identity(self) -> "TeamMemberCreate":
        if self.login_name is None and self.email is None:
            raise ValueError("登录账号或邮箱至少填写一项")
        return self

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("工作时区无效") from exc
        return value


class TeamMemberUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, pattern=r"^\+?[0-9][0-9 -]{5,19}$")
    timezone: str | None = Field(default=None, max_length=64)
    max_concurrent_sessions: int | None = Field(default=None, ge=1, le=1000)
    assignments: list[TeamRoleAssignment] | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        return TeamMemberCreate.validate_timezone(value) if value is not None else None


class TeamMemberView(BaseModel):
    id: uuid.UUID
    login_name: str | None
    name: str
    email: str | None
    phone: str | None
    timezone: str
    max_concurrent_sessions: int
    status: Literal["active", "disabled"]
    assignments: list[TeamRoleView]
    department_ids: list[uuid.UUID] = Field(default_factory=list)
    last_login_at: datetime | None
    created_at: datetime


class TeamMemberPasswordChange(BaseModel):
    password: str = Field(min_length=12, max_length=128)
