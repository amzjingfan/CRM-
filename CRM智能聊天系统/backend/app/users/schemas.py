"""团队管理 API 类型。"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator


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


class TeamMemberCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    temporary_password: str = Field(min_length=12, max_length=128)
    assignments: list[TeamRoleAssignment] = Field(min_length=1, max_length=100)


class TeamMemberUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    assignments: list[TeamRoleAssignment] | None = Field(default=None, min_length=1, max_length=100)


class TeamMemberView(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    status: Literal["active", "disabled"]
    assignments: list[TeamRoleAssignment]
    last_login_at: datetime | None
    created_at: datetime
