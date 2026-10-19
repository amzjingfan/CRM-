"""在 staging 主机只读采集 G6 连续运行证据；不保存响应正文或凭据。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DOCKER_HOST = "unix:///run/user/1004/docker.sock"
PUBLIC_URLS = (
    "https://staging.overselfx.com/healthz",
    "https://staging.overselfx.com/v1/health",
    "https://staging.overselfx.com/v1/health/ready",
)
EGRESS_IP = "38.55.145.52"
HELPER = "crm-staging-tiktok-egress-1"
BACKEND = "crm-staging-backend-1"
RESOURCE_CONTAINERS = (
    BACKEND,
    "crm-staging-worker-1",
    "crm-staging-agent-worker-1",
    "crm-staging-retrieval-model-service-1",
    "crm-staging-postgres-1",
)
# 已启动的原始采集器冻结为 72 小时；本期 G6 验收在相同原件的前 48 小时截取。
MINUTES = 4320
ACCEPTANCE_MINUTES = 2880
ROOT = Path("/home/crmdeploy/.cache/crm-g6")
RUN_ID = re.compile(r"g6-[0-9]{8}-[a-z0-9]{6}\Z")
INSPECT = re.compile(
    r"([0-9a-f]{64})\|(running|exited)\|(healthy|unhealthy|starting)\|([^|]+)\|([0-9]+)\|sha256:([0-9a-f]{64})\Z"
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def run_command(*command: str) -> tuple[int, str]:
    """命令异常仅返回固定失败类；不向证据传递原始 stderr。"""
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=25, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""
    return completed.returncode, completed.stdout[:65536]


def _inspect(name: str) -> dict[str, Any] | None:
    code, raw = run_command(
        "docker",
        "inspect",
        name,
        "--format",
        "{{.Id}}|{{.State.Status}}|{{.State.Health.Status}}|{{.State.StartedAt}}|{{.RestartCount}}|{{.Image}}",
    )
    match = INSPECT.fullmatch(raw.strip()) if code == 0 else None
    if match is None:
        return None
    return {
        "id": match[1],
        "running": match[2] == "running",
        "healthy": match[3] == "healthy",
        "started_at": match[4],
        "restart_count": int(match[5]),
        "image_sha256": match[6],
    }


def _resources() -> dict[str, Any] | None:
    code, raw = run_command("docker", "stats", "--no-stream", "--format", "{{json .}}", *RESOURCE_CONTAINERS)
    if code != 0:
        return None
    samples: dict[str, dict[str, float | int]] = {}
    units = {"B": 1, "KiB": 1024, "MiB": 1024**2, "GiB": 1024**3, "TiB": 1024**4}
    try:
        for line in raw.splitlines():
            item = json.loads(line)
            name = item["Name"]
            if name not in RESOURCE_CONTAINERS or name in samples:
                return None
            cpu = float(item["CPUPerc"].removesuffix("%"))
            memory_match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)([KMGT]?i?B)", item["MemUsage"].split(" / ")[0])
            if memory_match is None or not (0 <= cpu < 100000):
                return None
            pids = int(item["PIDs"])
            if pids < 0:
                return None
            samples[name] = {
                "cpu_percent": cpu,
                "memory_bytes": round(float(memory_match[1]) * units[memory_match[2]]),
                "pids": pids,
            }
        if set(samples) != set(RESOURCE_CONTAINERS):
            return None
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, OverflowError):
        return None

    code, raw = run_command("docker", "exec", BACKEND, "cat", "/proc/net/tcp", "/proc/net/tcp6")
    if code != 0:
        return None
    accept_queue = connections = send_queue = receive_queue = 0
    listener = False
    try:
        for line in raw.splitlines():
            fields = line.split()
            if not fields or fields[0] == "sl":
                continue
            if int(fields[1].rsplit(":", 1)[1], 16) != 8000:
                continue
            send_hex, receive_hex = fields[4].split(":")
            if fields[3] == "0A":
                listener = True
                accept_queue += int(receive_hex, 16)
            elif fields[3] == "01":
                connections += 1
                send_queue += int(send_hex, 16)
                receive_queue += int(receive_hex, 16)
    except (IndexError, ValueError):
        return None
    if not listener:
        return None
    return {
        "containers": samples,
        "backend_tcp": {
            "accept_queue_pending": accept_queue,
            "established_connections": connections,
            "send_queue_bytes": send_queue,
            "receive_queue_bytes": receive_queue,
        },
        "application_queue": "not_applicable_sync_workflow",
    }


def probe_once(slot: int) -> dict[str, Any]:
    """任一公网、容器或真实代理出口失败，当前分钟按不可用计。"""
    codes: list[int] = []
    for url in PUBLIC_URLS:
        code, raw = run_command(
            "curl",
            "--silent",
            "--show-error",
            "--noproxy",
            "*",
            "--output",
            "/dev/null",
            "--max-time",
            "8",
            "--write-out",
            "%{http_code} %{ssl_verify_result}",
            url,
        )
        codes.append(200 if code == 0 and raw.strip() == "200 0" else 0)
    helper = _inspect(HELPER)
    backend = _inspect(BACKEND)
    code, raw = run_command("docker", "exec", BACKEND, "python", "scripts/verify_tiktok_egress.py")
    try:
        egress = json.loads(raw) if code == 0 else {}
    except (ValueError, TypeError):
        egress = {}
    egress_ok = (
        egress.get("status") == "ok"
        and egress.get("observed_ip") == EGRESS_IP
        and egress.get("configured_ip") == EGRESS_IP
    )
    resource = _resources() if slot % 5 == 0 else None
    resource_ok = resource is not None if slot % 5 == 0 else True
    return {
        "slot": slot,
        "sampled_at_utc": utc_now().isoformat(),
        "public_http": codes,
        "helper": helper,
        "backend": backend,
        "egress_ip_ok": egress_ok,
        "resource": resource,
        "resource_sample_ok": resource_ok,
        "ok": all(value == 200 for value in codes)
        and helper is not None
        and helper["running"]
        and helper["healthy"]
        and backend is not None
        and backend["running"]
        and backend["healthy"]
        and egress_ok
        and resource_ok,
    }


def evaluate(rows: list[dict[str, object]], start: datetime, end: datetime, now: datetime) -> dict[str, Any]:
    """冻结窗口按分钟计；缺口不可用，重复或越界原件无效。"""
    minutes = int((end - start).total_seconds() // 60)
    if minutes not in (ACCEPTANCE_MINUTES, MINUTES) or end - start != timedelta(minutes=minutes):
        raise ValueError("invalid_window")
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("invalid_window")
    seen: set[int] = set()
    available = 0
    invalid = False
    for row in rows:
        slot = row.get("slot")
        ok = row.get("ok")
        if type(slot) is not int or not 0 <= slot < minutes or type(ok) is not bool or slot in seen:
            invalid = True
            continue
        seen.add(slot)
        available += int(ok)
    missing = minutes - len(seen)
    failed = len(seen) - available
    minimum_available = (minutes * 995 + 999) // 1000
    result = (
        "invalid" if invalid else "in_progress" if now < end else "pass" if available >= minimum_available else "fail"
    )
    return {
        "result": result,
        "window_start_utc": start.isoformat(),
        "window_end_utc": end.isoformat(),
        "expected_slots": minutes,
        "minimum_available_slots": minimum_available,
        "observed_slots": len(seen),
        "available_slots": available,
        "failed_slots": failed,
        "missing_slots": missing,
        "availability_percent": round(100 * available / minutes, 6),
        "resource_samples": sum(
            1 for row in rows if row.get("resource_sample_ok") is True and row.get("resource") is not None
        ),
    }


def acceptance_rows(rows: list[dict[str, object]], minutes: int) -> list[dict[str, object]]:
    """只排除采集原件中验收窗口结束后的合法槽，保留窗口内异常供判无效。"""
    accepted = []
    for row in rows:
        slot = row.get("slot")
        if type(slot) is not int or not minutes <= int(slot) < MINUTES:
            accepted.append(row)
    return accepted


def _append(path: Path, record: dict[str, Any]) -> None:
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        output.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        output.flush()
        os.fsync(output.fileno())


def _run_dir(run_id: str) -> Path:
    if RUN_ID.fullmatch(run_id) is None:
        raise ValueError("invalid_run_id")
    if ROOT.parent.is_symlink() or ROOT.is_symlink():
        raise ValueError("symlink_forbidden")
    if not ROOT.parent.is_dir() or ROOT.parent.stat().st_uid != 1004 or ROOT.parent.stat().st_mode & 0o077:
        raise ValueError("private_parent_required")
    ROOT.mkdir(mode=0o700, exist_ok=True)
    if ROOT.stat().st_uid != 1004 or ROOT.stat().st_mode & 0o077:
        raise ValueError("private_root_required")
    directory = ROOT / run_id
    if directory.is_symlink():
        raise ValueError("symlink_forbidden")
    directory.mkdir(mode=0o700, exist_ok=True)
    if directory.stat().st_uid != 1004 or directory.stat().st_mode & 0o077:
        raise ValueError("private_run_dir_required")
    return directory


def _read_rows(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    if path.is_symlink():
        raise ValueError("symlink_forbidden")
    with path.open(encoding="utf-8") as source:
        return [json.loads(line) for line in source]


def _collect(directory: Path, start: datetime, source_sha: str) -> None:
    metadata_path = directory / "meta.json"
    metadata = {
        "schema_version": 1,
        "run_id": directory.name,
        "source_sha": source_sha,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "start_utc": start.isoformat(),
        "end_utc": (start + timedelta(minutes=MINUTES)).isoformat(),
    }
    if metadata_path.exists():
        if metadata_path.is_symlink() or json.loads(metadata_path.read_text(encoding="utf-8")) != metadata:
            raise ValueError("metadata_mismatch")
    else:
        if start < utc_now() - timedelta(seconds=10):
            raise ValueError("backdated_start_forbidden")
        fd = os.open(metadata_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(metadata, output, sort_keys=True)
            output.flush()
            os.fsync(output.fileno())
    samples_path = directory / "samples.jsonl"
    prior = _read_rows(samples_path)
    seen = {row["slot"] for row in prior}
    previous_ok = prior[-1]["ok"] if prior else True
    end = start + timedelta(minutes=MINUTES)
    baseline_path = directory / "runtime-baseline.json"
    if baseline_path.is_symlink():
        raise ValueError("symlink_forbidden")
    baseline = json.loads(baseline_path.read_text(encoding="utf-8")) if baseline_path.exists() else None
    while (now := utc_now()) < end:
        if now < start:
            time.sleep(min(5, (start - now).total_seconds()))
            continue
        slot = int((now - start).total_seconds() // 60)
        if slot in seen:
            next_slot = start + timedelta(minutes=slot + 1)
            time.sleep(min(5, max(0.1, (next_slot - now).total_seconds())))
            continue
        sample = probe_once(slot)
        try:
            sampled_at = datetime.fromisoformat(sample["sampled_at_utc"])
            on_time = start + timedelta(minutes=slot) <= sampled_at < start + timedelta(minutes=slot + 1)
        except (KeyError, TypeError, ValueError):
            on_time = False
        if not on_time:
            sample["ok"] = False
            sample["late_sample"] = True
        helper = sample.get("helper")
        backend = sample.get("backend")
        identity = (
            {"helper_image_sha256": helper["image_sha256"], "backend_image_sha256": backend["image_sha256"]}
            if isinstance(helper, dict) and isinstance(backend, dict)
            else None
        )
        if sample["ok"] and identity is not None and baseline is None:
            baseline = identity
            _append(baseline_path, baseline)
        elif baseline is not None and identity != baseline:
            sample["ok"] = False
            sample["image_drift"] = True
        _append(samples_path, sample)
        seen.add(slot)
        if sample["ok"] != previous_ok:
            event = {
                "event": "G6_ALERT" if not sample["ok"] else "G6_RECOVERED",
                "slot": slot,
                "at_utc": sample["sampled_at_utc"],
            }
            _append(directory / "alerts.jsonl", event)
            print(json.dumps(event, sort_keys=True), flush=True)
        previous_ok = sample["ok"]
    print(json.dumps(evaluate(_read_rows(samples_path), start, end, utc_now()), sort_keys=True), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only staging G6 observer")
    parser.add_argument("mode", choices=("preflight", "collect", "report"))
    parser.add_argument("--run-id")
    parser.add_argument("--start-utc")
    parser.add_argument("--source-sha")
    parser.add_argument("--acceptance-minutes", type=int, choices=(ACCEPTANCE_MINUTES, MINUTES))
    args = parser.parse_args()
    if (
        os.name != "posix"
        or getattr(os, "getuid", lambda: -1)() != 1004
        or os.environ.get("DOCKER_HOST") != DOCKER_HOST
    ):
        raise ValueError("staging_rootless_only")
    if args.mode == "preflight":
        result = probe_once(0)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["ok"] else 1
    if not args.run_id:
        raise ValueError("run_id_required")
    directory = _run_dir(args.run_id)
    if args.mode == "collect":
        if args.acceptance_minutes is not None:
            raise ValueError("acceptance_override_report_only")
        if not args.start_utc or not args.source_sha or re.fullmatch(r"[0-9a-f]{40}", args.source_sha) is None:
            raise ValueError("source_identity_required")
        start = datetime.fromisoformat(args.start_utc.replace("Z", "+00:00"))
        if start.tzinfo != UTC or start.second or start.microsecond:
            raise ValueError("start_must_be_utc_minute")
        _collect(directory, start, args.source_sha)
        return 0
    meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
    start = datetime.fromisoformat(meta["start_utc"])
    collection_end = datetime.fromisoformat(meta["end_utc"])
    minutes = args.acceptance_minutes or ACCEPTANCE_MINUTES
    end = start + timedelta(minutes=minutes)
    if end > collection_end:
        raise ValueError("acceptance_exceeds_collection_window")
    result = evaluate(acceptance_rows(_read_rows(directory / "samples.jsonl"), minutes), start, end, utc_now())
    result["collection_window_end_utc"] = collection_end.isoformat()
    result["collector_script_sha256"] = meta["script_sha256"]
    result["source_sha"] = meta["source_sha"]
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
