"""对已按店铺权限筛选的客服作可复核的确定性派单。"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

RECENT_REPLY_WINDOW = timedelta(hours=72)


@dataclass(frozen=True)
class AssignmentCandidate:
    """候选者的实时负载与接待状态，不包含买家或消息正文。"""

    user_id: uuid.UUID
    pending_count: int
    online: bool
    last_assigned_at: datetime | None


@dataclass(frozen=True)
class AssignmentDecision:
    user_id: uuid.UUID
    reason: Literal["recent_responder", "least_pending"]


def choose_candidate(
    candidates: list[AssignmentCandidate],
    *,
    now: datetime,
    recent_responder_id: uuid.UUID | None = None,
    recent_reply_at: datetime | None = None,
) -> AssignmentDecision | None:
    """先排除不可接待者，再按近期服务和待处理负载排序。"""
    eligible = [item for item in candidates if item.online]
    if not eligible:
        return None
    if (
        recent_responder_id is not None
        and recent_reply_at is not None
        and recent_reply_at.tzinfo is not None
        and timedelta(0) <= now - recent_reply_at <= RECENT_REPLY_WINDOW
        and any(item.user_id == recent_responder_id for item in eligible)
    ):
        return AssignmentDecision(recent_responder_id, "recent_responder")
    selected = min(
        eligible,
        key=lambda item: (
            item.pending_count,
            item.last_assigned_at or datetime.min.replace(tzinfo=UTC),
            item.user_id,
        ),
    )
    return AssignmentDecision(selected.user_id, "least_pending")
