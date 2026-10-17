"""在 G5 手动压测期间只读采样 Rootless 容器资源和 backend TCP 队列。"""

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from math import isfinite
from pathlib import Path
from threading import Event
from typing import Any

CONTAINERS = {
    "backend": "crm-staging-backend-1",
    "worker": "crm-staging-worker-1",
    "agent_worker": "crm-staging-agent-worker-1",
}
DOCKER_HOST = "unix:///run/user/1004/docker.sock"
OUTPUT_PATTERN = re.compile(r"/home/crmdeploy/\.cache/crm-g5-manual/[a-z0-9-]+/resources\.json")
IMAGE_PATTERN = re.compile(r"ghcr\.io/cp11-gh/crm-backend@sha256:[0-9a-f]{64}")
MEMORY_UNITS = {"B": 1, "kB": 1000, "MB": 1000**2, "GB": 1000**3, "KiB": 1024, "MiB": 1024**2, "GiB": 1024**3}


def _memory_bytes(value: str) -> int:
    match = re.fullmatch(r"(\d+(?:\.\d+)?)(B|kB|MB|GB|KiB|MiB|GiB)", value)
    if match is None:
        raise ValueError("invalid_sample")
    return round(float(match.group(1)) * MEMORY_UNITS[match.group(2)])


def parse_docker_stats(raw: str) -> dict[str, dict[str, float | int]]:
    """只接受固定三个容器，并把 Docker 的自由格式输出缩减为数值白名单。"""

    result: dict[str, dict[str, float | int]] = {}
    names = {name: role for role, name in CONTAINERS.items()}
    try:
        for line in raw.splitlines():
            row = json.loads(line)
            role = names[row["Name"]]
            cpu_text = row["CPUPerc"]
            if not isinstance(cpu_text, str) or not cpu_text.endswith("%"):
                raise ValueError("invalid_sample")
            cpu = float(cpu_text[:-1])
            if not isfinite(cpu) or cpu < 0 or role in result:
                raise ValueError("invalid_sample")
            memory = _memory_bytes(row["MemUsage"].split(" / ", maxsplit=1)[0])
            pids = int(row["PIDs"])
            if pids < 0:
                raise ValueError("invalid_sample")
            result[role] = {"cpu_percent": cpu, "memory_bytes": memory, "pids": pids}
    except (AttributeError, KeyError, TypeError, ValueError, json.JSONDecodeError, OverflowError) as exc:
        raise ValueError("invalid_sample") from exc
    if set(result) != set(CONTAINERS):
        raise ValueError("invalid_sample")
    return result


def parse_backend_tcp(raw: str) -> dict[str, int]:
    """读取 backend:8000 的内核监听待接收队列及已建立连接。"""

    accept_queue = 0
    connections = 0
    send_queue = 0
    receive_queue = 0
    listener_found = False
    try:
        for line in raw.splitlines():
            fields = line.split()
            if not fields or fields[0] == "sl":
                continue
            if len(fields) < 5:
                raise ValueError("invalid_sample")
            if int(fields[1].rsplit(":", maxsplit=1)[1], 16) != 8000:
                continue
            send_hex, receive_hex = fields[4].split(":")
            send_bytes, receive_bytes = int(send_hex, 16), int(receive_hex, 16)
            if fields[3] == "0A":
                listener_found = True
                accept_queue += receive_bytes
            elif fields[3] == "01":
                connections += 1
                send_queue += send_bytes
                receive_queue += receive_bytes
    except (IndexError, ValueError) as exc:
        raise ValueError("invalid_sample") from exc
    if not listener_found:
        raise ValueError("backend_listener_missing")
    return {
        "accept_queue_pending": accept_queue,
        "established_connections": connections,
        "send_queue_bytes": send_queue,
        "receive_queue_bytes": receive_queue,
    }


def summarize_samples(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    if not snapshots:
        raise ValueError("invalid_sample")
    return {
        "sample_count": len(snapshots),
        "containers": {
            role: {
                f"{metric}_peak": max(snapshot["containers"][role][metric] for snapshot in snapshots)
                for metric in ("cpu_percent", "memory_bytes", "pids")
            }
            for role in CONTAINERS
        },
        "backend_tcp": {
            f"{metric}_peak": max(snapshot["backend_tcp"][metric] for snapshot in snapshots)
            for metric in (
                "accept_queue_pending",
                "established_connections",
                "send_queue_bytes",
                "receive_queue_bytes",
            )
        },
        "application_queue": "not_applicable_sync_workflow",
    }


def _docker(*arguments: str) -> str:
    try:
        completed = subprocess.run(["docker", *arguments], capture_output=True, text=True, check=False, timeout=15)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("docker_unavailable") from exc
    if completed.returncode != 0:
        raise ValueError("docker_unavailable")
    return completed.stdout.strip()


def _sample_once() -> dict[str, Any]:
    stats = _docker("stats", "--no-stream", "--format", "{{json .}}", *CONTAINERS.values())
    tcp = _docker("exec", CONTAINERS["backend"], "cat", "/proc/net/tcp", "/proc/net/tcp6")
    return {"containers": parse_docker_stats(stats), "backend_tcp": parse_backend_tcp(tcp)}


def collect_samples(
    duration_seconds: int, interval_seconds: int, stop: Event, sample: Callable[[], dict[str, Any]]
) -> list[dict[str, Any]]:
    deadline = time.monotonic() + duration_seconds
    snapshots: list[dict[str, Any]] = []
    while not stop.is_set() and time.monotonic() < deadline:
        snapshots.append(sample())
        stop.wait(min(interval_seconds, max(0.0, deadline - time.monotonic())))
    return snapshots


def _assert_target(output: Path, backend_image: str) -> None:
    if sys.platform != "linux" or os.geteuid() != 1004 or os.environ.get("DOCKER_HOST") != DOCKER_HOST:
        raise ValueError("target_invalid")
    if IMAGE_PATTERN.fullmatch(backend_image) is None or OUTPUT_PATTERN.fullmatch(str(output)) is None:
        raise ValueError("target_invalid")
    parent = output.parent
    if (
        parent.is_symlink()
        or not parent.is_dir()
        or parent.stat().st_uid != 1004
        or parent.stat().st_mode & 0o777 != 0o700
    ):
        raise ValueError("target_invalid")
    if output.exists() or output.is_symlink():
        raise ValueError("target_invalid")


def _write_report(output: Path, report: dict[str, Any]) -> None:
    try:
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=True, separators=(",", ":"))
            stream.write("\n")
    except OSError as exc:
        raise SystemExit("resource_evidence_unavailable") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only G5 staging resource sampler")
    parser.add_argument("--backend-image", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--duration-seconds", type=int, default=120, choices=range(1, 301))
    parser.add_argument("--interval-seconds", type=int, default=1, choices=range(1, 11))
    args = parser.parse_args()
    try:
        _assert_target(args.output, args.backend_image)
    except (OSError, ValueError) as exc:
        raise SystemExit("resource_target_invalid") from exc

    snapshots: list[dict[str, Any]] = []
    stop = Event()
    started_at = datetime.now(UTC).isoformat()
    failure: str | None = None
    prior_sigterm = signal.signal(signal.SIGTERM, lambda *_: stop.set())
    try:
        running = _docker("inspect", "--format", "{{.Config.Image}}|{{.State.Running}}", CONTAINERS["backend"])
        if running != f"{args.backend_image}|true":
            raise ValueError("runtime_image_mismatch")
        snapshots = collect_samples(args.duration_seconds, args.interval_seconds, stop, _sample_once)
    except ValueError as exc:
        failure = (
            str(exc)
            if str(exc)
            in {"docker_unavailable", "invalid_sample", "backend_listener_missing", "runtime_image_mismatch"}
            else "invalid_sample"
        )
    finally:
        signal.signal(signal.SIGTERM, prior_sigterm)
    if not snapshots and failure is None:
        failure = "invalid_sample"
    report = {
        "mode": "g5_resource_sampling",
        "status": "failed" if failure else "passed",
        "started_at": started_at,
        "ended_at": datetime.now(UTC).isoformat(),
        "backend_image": args.backend_image,
        "requested_duration_seconds": args.duration_seconds,
        "interval_seconds": args.interval_seconds,
        "stopped_early": stop.is_set(),
        "failure_category": failure,
        "metrics": summarize_samples(snapshots) if snapshots and not failure else None,
    }
    _write_report(args.output, report)
    print(json.dumps(report, ensure_ascii=True, separators=(",", ":")))
    if failure:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
