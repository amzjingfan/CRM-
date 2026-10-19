"""G6 冻结原始采集和本期 48 小时验收的计数与低敏探针契约。"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from scripts import observe_staging_g6 as observer

START = datetime(2026, 10, 20, 0, 0, tzinfo=UTC)
END = START + timedelta(hours=72)


def rows(failed: set[int] | None = None) -> list[dict[str, object]]:
    return [{"slot": slot, "ok": slot not in (failed or set())} for slot in range(4320)]


def test_complete_window_accepts_at_most_21_failed_minutes() -> None:
    result = observer.evaluate(rows(set(range(21))), START, END, END)
    assert result["result"] == "pass"
    assert result["available_slots"] == 4299
    assert result["failed_slots"] == 21
    assert result["missing_slots"] == 0

    assert observer.evaluate(rows(set(range(22))), START, END, END)["result"] == "fail"


def test_missing_duplicate_and_unfinished_window_cannot_pass() -> None:
    one_gap = observer.evaluate(rows()[:-1], START, END, END)
    assert one_gap["missing_slots"] == 1
    assert one_gap["available_slots"] == 4319
    assert observer.evaluate(rows()[:-22], START, END, END)["result"] == "fail"
    assert observer.evaluate(rows() + [{"slot": 0, "ok": True}], START, END, END)["result"] == "invalid"
    assert observer.evaluate(rows(), START, END, END - timedelta(seconds=1))["result"] == "in_progress"


def test_48_hour_acceptance_uses_first_2880_slots_and_995_percent() -> None:
    end = START + timedelta(hours=48)
    source = rows(set(range(14)))
    accepted = observer.acceptance_rows(source, observer.ACCEPTANCE_MINUTES)
    result = observer.evaluate(accepted, START, end, end)
    assert result["result"] == "pass"
    assert result["expected_slots"] == 2880
    assert result["minimum_available_slots"] == 2866
    assert result["available_slots"] == 2866
    assert result["failed_slots"] == 14
    assert observer.evaluate(accepted, START, end, end - timedelta(seconds=1))["result"] == "in_progress"

    fifteen_down = observer.acceptance_rows(rows(set(range(15))), observer.ACCEPTANCE_MINUTES)
    assert observer.evaluate(fifteen_down, START, end, end)["result"] == "fail"
    assert observer.evaluate(accepted[:-15], START, end, end)["result"] == "fail"


def test_48_hour_acceptance_preserves_invalid_rows_inside_or_outside_source_envelope() -> None:
    end = START + timedelta(hours=48)
    original = rows()
    original.extend(({"slot": 4, "ok": True}, {"slot": 5000, "ok": True}))
    accepted = observer.acceptance_rows(original, observer.ACCEPTANCE_MINUTES)
    assert len(accepted) == 2882
    assert observer.evaluate(accepted, START, end, end)["result"] == "invalid"


def test_probe_reduces_commands_to_fixed_statuses_without_raw_values(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run(*command: str) -> tuple[int, str]:
        calls.append(command)
        if command[0] == "curl":
            return 0, "200 0"
        if "inspect" in command:
            return 0, "a" * 64 + "|running|healthy|2026-10-19T00:00:00Z|0|sha256:" + "b" * 64
        if any("verify_tiktok_egress.py" in part for part in command):
            return 0, json.dumps({"status": "ok", "configured_ip": "38.55.145.52", "observed_ip": "38.55.145.52"})
        raise AssertionError(command)

    monkeypatch.setattr(observer, "run_command", fake_run)
    result = observer.probe_once(1)

    assert result["ok"] is True
    assert result["public_http"] == [200, 200, 200]
    assert result["egress_ip_ok"] is True
    assert "https://staging.overselfx.com/v1/health/ready" in " ".join(" ".join(x) for x in calls)
    assert "secret" not in json.dumps(result).lower()


def test_failed_egress_never_reports_available_or_raw_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*command: str) -> tuple[int, str]:
        if command[0] == "curl":
            return 0, "200 0"
        if "inspect" in command:
            return 0, "a" * 64 + "|running|healthy|2026-10-19T00:00:00Z|0|sha256:" + "b" * 64
        return 1, "secret=must-not-leak"

    monkeypatch.setattr(observer, "run_command", fake_run)
    result = observer.probe_once(1)
    assert result["ok"] is False
    assert result["egress_ip_ok"] is False
    assert "must-not-leak" not in json.dumps(result)


def test_resource_sample_has_fixed_numeric_fields_and_sync_queue_label(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*command: str) -> tuple[int, str]:
        if "stats" in command:
            return 0, "\n".join(
                json.dumps(
                    {"Name": name, "CPUPerc": "1.0%", "MemUsage": "2MiB / 4GiB", "PIDs": "2", "Secret": "hidden"}
                )
                for name in observer.RESOURCE_CONTAINERS
            )
        return 0, (
            "sl local_address rem_address st tx_queue rx_queue\n"
            "0: 00000000:1F40 00000000:0000 0A 00000000:00000002\n"
            "1: 0100007F:1F40 0200007F:ABCD 01 00000003:00000004\n"
        )

    monkeypatch.setattr(observer, "run_command", fake_run)
    result = observer._resources()
    assert result is not None
    assert result["backend_tcp"]["accept_queue_pending"] == 2
    assert result["application_queue"] == "not_applicable_sync_workflow"
    assert "hidden" not in json.dumps(result)


def test_collector_appends_private_sample_and_alert_without_duplicate_on_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    times = iter((START + timedelta(seconds=1), START + timedelta(seconds=1), END, END))
    monkeypatch.setattr(observer, "utc_now", lambda: next(times, END))
    monkeypatch.setattr(
        observer,
        "probe_once",
        lambda slot: {"slot": slot, "sampled_at_utc": START.isoformat(), "ok": False, "resource_sample_ok": False},
    )
    observer._collect(tmp_path, START, "a" * 40)
    observer._collect(tmp_path, START, "a" * 40)
    samples = (tmp_path / "samples.jsonl").read_text(encoding="utf-8").splitlines()
    alerts = (tmp_path / "alerts.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(samples) == 1
    assert len(alerts) == 1
    assert json.loads(alerts[0])["event"] == "G6_ALERT"


def test_probe_finishing_after_its_minute_is_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    times = iter((START + timedelta(seconds=1), START + timedelta(seconds=1), END))
    monkeypatch.setattr(observer, "utc_now", lambda: next(times, END))
    monkeypatch.setattr(
        observer,
        "probe_once",
        lambda slot: {
            "slot": slot,
            "sampled_at_utc": (START + timedelta(seconds=61)).isoformat(),
            "ok": True,
            "resource_sample_ok": False,
        },
    )
    observer._collect(tmp_path, START, "a" * 40)
    sample = json.loads((tmp_path / "samples.jsonl").read_text(encoding="utf-8"))
    assert sample["ok"] is False
    assert sample["late_sample"] is True


def test_runtime_image_drift_marks_later_slot_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    times = iter((START + timedelta(seconds=1), START + timedelta(seconds=1), START + timedelta(seconds=61), END))
    monkeypatch.setattr(observer, "utc_now", lambda: next(times, END))

    def fake_probe(slot: int) -> dict[str, object]:
        digest = "a" * 64 if slot == 0 else "b" * 64
        return {
            "slot": slot,
            "sampled_at_utc": (START + timedelta(minutes=slot, seconds=2)).isoformat(),
            "ok": True,
            "helper": {"image_sha256": "c" * 64},
            "backend": {"image_sha256": digest},
            "resource_sample_ok": True,
        }

    monkeypatch.setattr(observer, "probe_once", fake_probe)
    observer._collect(tmp_path, START, "a" * 40)
    samples = [json.loads(line) for line in (tmp_path / "samples.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [item["ok"] for item in samples] == [True, False]
    assert samples[1]["image_drift"] is True
