"""单客服部按店铺派单的管理与本人在线接口。"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class ReceptionAgentInput(BaseModel):
    user_id: uuid.UUID
    auto_enabled: bool = False
    capacity: int = Field(default=20, ge=1, le=1000)


class ReceptionStoreInput(BaseModel):
    enabled: bool = False
    agents: list[ReceptionAgentInput] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def unique_agents(self) -> "ReceptionStoreInput":
        if len({agent.user_id for agent in self.agents}) != len(self.agents):
            raise ValueError("接待客服不可重复")
        return self


class ReceptionAgentView(BaseModel):
    user_id: uuid.UUID
    name: str
    active: bool
    auto_enabled: bool
    accepting: bool
    capacity: int
    pending_count: int
    online: bool
    last_heartbeat_at: datetime | None


class ReceptionStoreView(BaseModel):
    store_id: uuid.UUID
    department_id: uuid.UUID
    enabled: bool
    queue_count: int
    queue_reasons: dict[str, int] = Field(default_factory=dict)
    takeover_count: int = 0
    takeover_conversation_ids: list[uuid.UUID] = Field(default_factory=list)
    agents: list[ReceptionAgentView]


class ReceptionHeartbeatInput(BaseModel):
    store_id: uuid.UUID
    accepting: bool = True


class ReceptionHeartbeatView(BaseModel):
    store_id: uuid.UUID
    accepting: bool
    last_heartbeat_at: datetime


class OwnReceptionStoreView(BaseModel):
    store_id: uuid.UUID
    accepting: bool
    online: bool
