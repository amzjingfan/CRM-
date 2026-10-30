"""派单排序只使用登录在线和跨店负载事实。"""

import uuid
from datetime import UTC, datetime, timedelta

from app.reception_assignment.rules import AssignmentCandidate, choose_candidate

NOW = datetime(2026, 10, 29, 8, 0, tzinfo=UTC)


def candidate(
    user_id: uuid.UUID,
    *,
    pending: int = 0,
    online: bool = True,
    last_assigned_at: datetime | None = None,
) -> AssignmentCandidate:
    return AssignmentCandidate(user_id, pending, online, last_assigned_at)


def test_recent_human_responder_wins_only_within_72_hours_and_if_eligible() -> None:
    recent, less_busy = uuid.uuid4(), uuid.uuid4()
    choices = [candidate(recent, pending=4), candidate(less_busy, pending=0)]

    selected = choose_candidate(choices, now=NOW, recent_responder_id=recent, recent_reply_at=NOW - timedelta(hours=3))
    assert selected is not None and (selected.user_id, selected.reason) == (recent, "recent_responder")

    expired = choose_candidate(choices, now=NOW, recent_responder_id=recent, recent_reply_at=NOW - timedelta(hours=73))
    assert expired is not None and (expired.user_id, expired.reason) == (less_busy, "least_pending")

    offline = choose_candidate(
        [candidate(recent, online=False), candidate(less_busy)],
        now=NOW,
        recent_responder_id=recent,
        recent_reply_at=NOW - timedelta(hours=3),
    )
    assert offline is not None and offline.user_id == less_busy


def test_least_pending_breaks_ties_by_oldest_assignment_then_user_id() -> None:
    older, newer = uuid.uuid4(), uuid.uuid4()
    choices = [
        candidate(newer, pending=1, last_assigned_at=NOW - timedelta(minutes=1)),
        candidate(older, pending=1, last_assigned_at=NOW - timedelta(hours=1)),
    ]
    selected = choose_candidate(choices, now=NOW)
    assert selected is not None and selected.user_id == older

    stable = choose_candidate([candidate(newer), candidate(older)], now=NOW)
    assert stable is not None and stable.user_id == min(older, newer)


def test_only_logged_out_agents_are_excluded_and_no_hidden_capacity_limit() -> None:
    offline, busy = uuid.uuid4(), uuid.uuid4()
    assert choose_candidate([candidate(offline, online=False)], now=NOW) is None
    assert choose_candidate([candidate(offline, online=False), candidate(busy, pending=500)], now=NOW).user_id == busy
