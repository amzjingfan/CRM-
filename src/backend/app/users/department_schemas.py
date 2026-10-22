"""部门管理 API 类型。"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    store_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("部门名称不能为空")
        return value

    @field_validator("store_ids")
    @classmethod
    def unique_stores(cls, values: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(values) != len(set(values)):
            raise ValueError("负责店铺不可重复")
        return values


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    store_ids: list[uuid.UUID] | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str | None) -> str | None:
        return DepartmentCreate.valid_name(value) if value is not None else None

    @field_validator("store_ids")
    @classmethod
    def unique_stores(cls, values: list[uuid.UUID] | None) -> list[uuid.UUID] | None:
        if values is not None and len(values) != len(set(values)):
            raise ValueError("负责店铺不可重复")
        return values


class DepartmentView(BaseModel):
    id: uuid.UUID
    name: str
    store_ids: list[uuid.UUID]
    created_at: datetime


class DepartmentMemberAdd(BaseModel):
    user_id: uuid.UUID
