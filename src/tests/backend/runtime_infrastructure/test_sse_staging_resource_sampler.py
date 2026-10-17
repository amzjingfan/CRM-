"""G5 手动压测的只读资源与网络队列采样契约。"""

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


def sampler():  # type: ignore[no-untyped-def]
    return importlib.import_module("scripts.sample_sse_staging_resources")


def test_docker_stats_are_reduced_to_fixed_numeric_fields() -> None:
    raw = "\n".join(
        json.dumps(
            {
                "Name": name,
                "CPUPerc": cpu,
                "MemUsage": memory,
                "PIDs": pids,
                "SecretField": "never-report-this",
            }
        )
        for name, cpu, memory, pids in (
            ("crm-staging-backend-1", "12.5%", "120MiB / 2GiB", "7"),
            ("crm-staging-worker-1", "1.2%", "10MiB / 2GiB", "2"),
            ("crm-staging-agent-worker-1", "0.1%", "3MiB / 2GiB", "1"),
        )
    )

    result = sampler().parse_docker_stats(raw)

    assert result["backend"] == {"cpu_percent": 12.5, "memory_bytes": 125829120, "pids": 7}
    assert set(result) == {"backend", "worker", "agent_worker"}
    assert "never-report-this" not in json.dumps(result)


def test_docker_stats_reject_malformed_memory_without_raw_value() -> None:
    raw = json.dumps({"Name": "crm-staging-backend-1", "CPUPerc": "1%", "MemUsage": 7, "PIDs": "1"})

    with pytest.raises(ValueError, match="^invalid_sample$"):
        sampler().parse_docker_stats(raw)


def test_tcp_sampler_counts_only_backend_port_connections_and_accept_queue() -> None:
    raw = """sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt uid timeout inode
0: 00000000:1F40 00000000:0000 0A 00000000:00000002 00:00000000 00000000 0 0 1
1: 0100007F:1F40 0200007F:ABCD 01 00000003:00000004 00:00000000 00000000 0 0 2
2: 0100007F:01BB 0200007F:ABCD 01 0000000A:0000000B 00:00000000 00000000 0 0 3
"""

    result = sampler().parse_backend_tcp(raw)

    assert result == {
        "accept_queue_pending": 2,
        "established_connections": 1,
        "send_queue_bytes": 3,
        "receive_queue_bytes": 4,
    }


def test_sampler_fails_closed_without_backend_listener() -> None:
    with pytest.raises(ValueError, match="backend_listener_missing"):
        sampler().parse_backend_tcp("sl local_address rem_address st tx_queue rx_queue\n")


def test_report_uses_peak_numbers_and_never_includes_raw_errors() -> None:
    module = sampler()
    snapshots = [
        {
            "containers": {
                "backend": {"cpu_percent": 10.0, "memory_bytes": 100, "pids": 5},
                "worker": {"cpu_percent": 1.0, "memory_bytes": 20, "pids": 2},
                "agent_worker": {"cpu_percent": 0.0, "memory_bytes": 10, "pids": 1},
            },
            "backend_tcp": {
                "accept_queue_pending": 1,
                "established_connections": 4,
                "send_queue_bytes": 0,
                "receive_queue_bytes": 2,
            },
        },
        {
            "containers": {
                "backend": {"cpu_percent": 20.0, "memory_bytes": 90, "pids": 6},
                "worker": {"cpu_percent": 0.0, "memory_bytes": 30, "pids": 2},
                "agent_worker": {"cpu_percent": 0.0, "memory_bytes": 10, "pids": 1},
            },
            "backend_tcp": {
                "accept_queue_pending": 0,
                "established_connections": 5,
                "send_queue_bytes": 1,
                "receive_queue_bytes": 0,
            },
        },
    ]

    result = module.summarize_samples(snapshots)

    assert result["sample_count"] == 2
    assert result["containers"]["backend"] == {"cpu_percent_peak": 20.0, "memory_bytes_peak": 100, "pids_peak": 6}
    assert result["backend_tcp"]["accept_queue_pending_peak"] == 1
    assert result["backend_tcp"]["established_connections_peak"] == 5
    assert result["application_queue"] == "not_applicable_sync_workflow"
    assert "secret" not in json.dumps(result).lower()


def test_empty_sampling_window_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = sampler()
    image = "ghcr.io/cp11-gh/crm-backend@sha256:" + "a" * 64
    reports: list[dict[str, object]] = []
    times = iter((100.0, 101.0))
    monkeypatch.setattr(module, "_assert_target", lambda *_: None)
    monkeypatch.setattr(module, "_docker", lambda *_: f"{image}|true")
    monkeypatch.setattr(module, "_write_report", lambda _path, report: reports.append(report))
    monkeypatch.setattr(module.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sample_sse_staging_resources",
            "--backend-image",
            image,
            "--output",
            str(tmp_path / "resources.json"),
            "--duration-seconds",
            "1",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        module.main()

    assert exc_info.value.code == 1
    assert reports[0]["status"] == "failed"
    assert reports[0]["failure_category"] == "invalid_sample"


def test_sampling_stops_after_current_sample_when_window_ends(monkeypatch: pytest.MonkeyPatch) -> None:
    module = sampler()
    monkeypatch.setattr(module.time, "monotonic", lambda: 100.0)

    class Stop:
        stopped = False

        def is_set(self) -> bool:
            return self.stopped

        def wait(self, _seconds: float) -> bool:
            self.stopped = True
            return True

    samples = module.collect_samples(120, 1, Stop(), lambda: {"fixed": 1})

    assert samples == [{"fixed": 1}]


def test_docker_failure_exposes_only_fixed_category(monkeypatch: pytest.MonkeyPatch) -> None:
    module = sampler()
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *_, **__: subprocess.CompletedProcess([], 1, "", "secret-token=never-report-this"),
    )

    with pytest.raises(ValueError, match="^docker_unavailable$") as exc_info:
        module._docker("stats")

    assert "never-report-this" not in str(exc_info.value)
