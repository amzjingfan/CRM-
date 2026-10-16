"""从固定时间窗的容器日志只提取白名单异常类型计数。"""

import json
import sys
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

WINDOW_START = datetime(2026, 10, 16, 6, 45, 5, tzinfo=UTC)
WINDOW_END = datetime(2026, 10, 16, 6, 45, 20, tzinfo=UTC)
ALLOWED_TYPES = frozenset(
    {
        "OperationalError",
        "ProgrammingError",
        "IntegrityError",
        "DatabaseError",
        "InterfaceError",
        "MissingGreenlet",
        "InvalidRequestError",
        "StatementError",
        "UndefinedTableError",
        "UndefinedColumnError",
        "ConnectionDoesNotExistError",
        "TimeoutError",
        "ValidationError",
        "ValueError",
        "TypeError",
        "KeyError",
        "AttributeError",
        "RuntimeError",
    }
)


def classify_lines(lines: Iterable[str]) -> dict[str, Any]:
    """忽略非结构化、非目标事件和越界时间；绝不返回原始日志字段。"""
    counts: Counter[str] = Counter()
    for line in lines:
        try:
            record = json.loads(line)
            if not isinstance(record, dict) or record.get("event") != "internal_error":
                continue
            timestamp = datetime.fromisoformat(record["timestamp"])
            if timestamp.tzinfo is None or not WINDOW_START <= timestamp.astimezone(UTC) <= WINDOW_END:
                continue
        except (KeyError, TypeError, ValueError):
            continue
        raw_type = record.get("exception_type")
        counts[raw_type if isinstance(raw_type, str) and raw_type in ALLOWED_TYPES else "other"] += 1
    return {
        "mode": "diagnose_auth_logs",
        "matched_events": sum(counts.values()),
        "exception_types": dict(sorted(counts.items())),
        "provider_calls": 0,
    }


def main() -> None:
    try:
        report = classify_lines(sys.stdin)
    except Exception:
        report = {"mode": "diagnose_auth_logs", "matched_events": 0, "exception_types": {}, "provider_calls": 0}
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
