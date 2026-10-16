"""固定时间窗内的认证 500 异常只输出低敏类型。"""

import json

from scripts.classify_staging_auth_logs import classify_lines


def test_classifies_only_internal_error_in_fixed_window_without_raw_log() -> None:
    lines = [
        json.dumps(
            {
                "timestamp": "2026-10-16T06:45:11.000000+00:00",
                "event": "internal_error",
                "exception_type": "ProgrammingError",
                "message": "private-response-marker",
                "trace_id": "00000000-0000-4000-8000-000000000001",
            }
        ),
        json.dumps(
            {
                "timestamp": "2026-10-16T06:45:12+00:00",
                "event": "internal_error",
                "exception_type": "UnexpectedSecretClass",
            }
        ),
        json.dumps(
            {"timestamp": "2026-10-16T06:44:00+00:00", "event": "internal_error", "exception_type": "ValueError"}
        ),
        json.dumps(
            {"timestamp": "2026-10-16T06:45:12+00:00", "event": "http_server_access", "exception_type": "ValueError"}
        ),
        "not-json-private-response-marker",
    ]
    report = classify_lines(lines)
    assert report == {
        "mode": "diagnose_auth_logs",
        "matched_events": 2,
        "exception_types": {"ProgrammingError": 1, "other": 1},
        "provider_calls": 0,
    }
    assert "private-response-marker" not in json.dumps(report)
    assert "UnexpectedSecretClass" not in json.dumps(report)


def test_empty_window_reports_zero_without_guessing() -> None:
    assert classify_lines([]) == {
        "mode": "diagnose_auth_logs",
        "matched_events": 0,
        "exception_types": {},
        "provider_calls": 0,
    }
