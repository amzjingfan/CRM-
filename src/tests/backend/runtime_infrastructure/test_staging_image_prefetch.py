"""Staging image prefetch must not switch services or accept unsafe image references."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from _support import REPOSITORY_ROOT, SOURCE_ROOT

SCRIPT = SOURCE_ROOT / "scripts" / "Prepare-StagingRollbackImages.ps1"
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")
IMAGES = (
    "ghcr.io/cp11-gh/crm-backend@sha256:" + "a" * 64,
    "ghcr.io/cp11-gh/crm-frontend@sha256:" + "b" * 64,
    "ghcr.io/cp11-gh/crm-retrieval-model-service@sha256:" + "c" * 64,
    "ghcr.io/cp11-gh/crm-backend@sha256:" + "d" * 64,
    "ghcr.io/cp11-gh/crm-frontend@sha256:" + "e" * 64,
    "ghcr.io/cp11-gh/crm-retrieval-model-service@sha256:" + "f" * 64,
)


def fake_docker(tmp_path: Path) -> tuple[dict[str, str], Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "docker.jsonl"
    runtime = bin_dir / "fake_docker.py"
    runtime.write_text(
        """import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with Path(os.environ['FAKE_DOCKER_LOG']).open('a', encoding='utf-8') as output:
    payload = {'args': args, 'host': os.environ.get('DOCKER_HOST')}
    payload['context'] = os.environ.get('DOCKER_CONTEXT')
    output.write(json.dumps(payload) + '\\n')
if args[:1] == ['pull']:
    if args[1] == os.environ.get('FAKE_DOCKER_FAIL_IMAGE'):
        sys.exit(42)
    sys.exit(0)
if args[:2] == ['image', 'inspect']:
    print(json.dumps([args[-1]]))
    sys.exit(0)
sys.exit(99)
""",
        encoding="utf-8",
    )
    if os.name == "nt":
        (bin_dir / "docker.cmd").write_text(
            '@echo off\r\n"%FAKE_DOCKER_PYTHON%" "%FAKE_DOCKER_SCRIPT%" %*\r\n',
            encoding="utf-8",
        )
    else:
        wrapper = bin_dir / "docker"
        wrapper.write_text('#!/bin/sh\nexec "$FAKE_DOCKER_PYTHON" "$FAKE_DOCKER_SCRIPT" "$@"\n')
        wrapper.chmod(0o755)
    environment = os.environ.copy()
    environment.update(
        {
            "PATH": str(bin_dir) + os.pathsep + environment.get("PATH", ""),
            "FAKE_DOCKER_PYTHON": sys.executable,
            "FAKE_DOCKER_SCRIPT": str(runtime),
            "FAKE_DOCKER_LOG": str(log),
            "DOCKER_CONTEXT": "unsafe-system-context",
        }
    )
    return environment, log


def invoke(tmp_path: Path, environment: dict[str, str], *overrides: str) -> subprocess.CompletedProcess[str]:
    assert POWERSHELL is not None
    args = [
        POWERSHELL,
        "-NoLogo",
        "-NoProfile",
        "-File",
        str(SCRIPT),
        "-Environment",
        "staging",
        "-ConfirmTarget",
        "staging",
        "-DockerHost",
        "unix:///run/user/1004/docker.sock",
        "-EvidenceFile",
        str(tmp_path / "evidence.json"),
    ]
    for name, image in zip(
        (
            "CandidateBackendImage",
            "CandidateFrontendImage",
            "CandidateRetrievalModelImage",
            "PreviousBackendImage",
            "PreviousFrontendImage",
            "PreviousRetrievalModelImage",
        ),
        IMAGES,
        strict=True,
    ):
        args += [f"-{name}", image]
    for name, value in zip(overrides[::2], overrides[1::2], strict=True):
        args[args.index(name) + 1] = value
    return subprocess.run(
        args, capture_output=True, text=True, encoding="utf-8", errors="replace", env=environment, timeout=30
    )


def test_prefetch_pulls_exact_six_digests_without_service_mutation(tmp_path: Path) -> None:
    """A wrong operation branch or floating reference must not touch staging services."""
    environment, log = fake_docker(tmp_path)
    result = invoke(tmp_path, environment)
    assert result.returncode == 0, result.stdout + result.stderr
    commands = [json.loads(line) for line in log.read_text("utf-8").splitlines()]
    assert [command["args"] for command in commands if command["args"][0] == "pull"] == [
        ["pull", image] for image in IMAGES
    ]
    assert all(command["args"][0] in {"pull", "image"} for command in commands)
    assert all(command["host"] == "unix:///run/user/1004/docker.sock" for command in commands)
    assert all(command["context"] in (None, "") for command in commands)
    evidence = json.loads((tmp_path / "evidence.json").read_text("utf-8"))
    assert evidence["status"] == "passed"
    assert evidence["image_count"] == 6
    assert evidence["production_release"] is False


@pytest.mark.parametrize(
    "override",
    [
        ("-ConfirmTarget", "production"),
        ("-DockerHost", "unix:///var/run/docker.sock"),
        ("-PreviousBackendImage", "ghcr.io/cp11-gh/crm-backend:latest"),
    ],
)
def test_prefetch_rejects_wrong_target_or_floating_image_before_pull(tmp_path: Path, override: tuple[str, str]) -> None:
    environment, log = fake_docker(tmp_path)
    result = invoke(tmp_path, environment, *override)
    assert result.returncode != 0
    assert not log.exists()
    assert not (tmp_path / "evidence.json").exists()


def test_prefetch_pull_failure_never_reports_pass(tmp_path: Path) -> None:
    environment, log = fake_docker(tmp_path)
    environment["FAKE_DOCKER_FAIL_IMAGE"] = IMAGES[2]
    result = invoke(tmp_path, environment)
    assert result.returncode != 0
    commands = [json.loads(line)["args"] for line in log.read_text("utf-8").splitlines()]
    assert [args for args in commands if args[0] == "pull"] == [["pull", image] for image in IMAGES[:3]]
    assert not (tmp_path / "evidence.json").exists()


def test_prefetch_rejects_existing_evidence_before_pull(tmp_path: Path) -> None:
    """A failed rerun must not leave a previous passed artifact at the same path."""
    environment, log = fake_docker(tmp_path)
    evidence = tmp_path / "evidence.json"
    evidence.write_text('{"status":"passed"}', encoding="utf-8")
    result = invoke(tmp_path, environment)
    assert result.returncode != 0
    assert not log.exists()
    assert evidence.read_text("utf-8") == '{"status":"passed"}'


def test_staging_workflow_exposes_prefetch_without_expanding_token_permissions() -> None:
    workflow = yaml.safe_load((REPOSITORY_ROOT / ".github/workflows/staging-gates.yml").read_text("utf-8"))
    assert "prefetch" in workflow[True]["workflow_dispatch"]["inputs"]["operation"]["options"]
    assert workflow["permissions"] == {"contents": "read", "packages": "read"}
    steps = workflow["jobs"]["staging"]["steps"]
    prefetch = next(step for step in steps if step["name"] == "Prefetch immutable rollback images")
    assert prefetch["if"] == "${{ inputs.operation == 'prefetch' }}"
    assert "CRM_STAGING_ENV_FILE" not in prefetch["env"]
    assert "Prepare-StagingRollbackImages.ps1" in prefetch["run"]
    assert "$env:GITHUB_RUN_ID-$env:GITHUB_RUN_ATTEMPT.json" in prefetch["run"]
    gate = next(step for step in steps if step["name"] == "Run the selected staging gate")
    assert gate["if"] == "${{ inputs.operation != 'prefetch' }}"
    upload = next(step for step in steps if step["name"] == "Upload low-sensitive prefetch evidence")
    assert upload["if"] == "${{ success() && inputs.operation == 'prefetch' }}"
    assert upload["with"]["path"] == (
        "${{ runner.temp }}/crm-staging-prefetch-evidence-${{ github.run_id }}-${{ github.run_attempt }}.json"
    )
