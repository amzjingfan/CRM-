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
cache = Path(os.environ['FAKE_DOCKER_CACHE'])
with Path(os.environ['FAKE_DOCKER_LOG']).open('a', encoding='utf-8') as output:
    payload = {'args': args, 'host': os.environ.get('DOCKER_HOST')}
    payload['context'] = os.environ.get('DOCKER_CONTEXT')
    output.write(json.dumps(payload) + '\\n')
if args[:1] == ['pull']:
    if args[1] == os.environ.get('FAKE_DOCKER_FAIL_IMAGE'):
        sys.exit(42)
    if args[1] == os.environ.get('FAKE_DOCKER_FAIL_ONCE_IMAGE'):
        pulls = [json.loads(line)['args'] for line in Path(os.environ['FAKE_DOCKER_LOG']).read_text().splitlines()]
        if sum(command == args for command in pulls) == 1:
            sys.exit(42)
    with cache.open('a', encoding='utf-8') as output:
        output.write(args[1] + '\\n')
    sys.exit(0)
if args[:2] == ['image', 'inspect']:
    if not cache.exists() or args[-1] not in cache.read_text(encoding='utf-8').splitlines():
        print('No such image', file=sys.stderr)
        sys.exit(1)
    if args[-1] == os.environ.get('FAKE_DOCKER_WRONG_DIGEST_IMAGE'):
        print(json.dumps(['ghcr.io/cp11-gh/other@sha256:' + '0' * 64]))
        sys.exit(0)
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
            "FAKE_DOCKER_CACHE": str(tmp_path / "cached-images.txt"),
            "DOCKER_CONTEXT": "unsafe-system-context",
        }
    )
    return environment, log


def invoke(
    tmp_path: Path,
    environment: dict[str, str],
    *overrides: str,
    resumable_script: Path | None = None,
) -> subprocess.CompletedProcess[str]:
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
    if resumable_script is not None:
        args += ["-ResumableOciScript", str(resumable_script)]
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        timeout=30,
        check=False,
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


def test_prefetch_reuses_unchanged_backend_and_retrieval_digests(tmp_path: Path) -> None:
    """A frontend-only update verifies six roles but downloads only two distinct images."""
    environment, log = fake_docker(tmp_path)
    result = invoke(
        tmp_path,
        environment,
        "-PreviousBackendImage",
        IMAGES[0],
        "-PreviousRetrievalModelImage",
        IMAGES[2],
    )
    assert result.returncode == 0, result.stdout + result.stderr
    commands = [json.loads(line)["args"] for line in log.read_text("utf-8").splitlines()]
    assert [args for args in commands if args[0] == "pull"] == [
        ["pull", IMAGES[0]],
        ["pull", IMAGES[1]],
        ["pull", IMAGES[2]],
        ["pull", IMAGES[4]],
    ]
    evidence = json.loads((tmp_path / "evidence.json").read_text("utf-8"))
    assert evidence["image_count"] == 6
    assert evidence["image_references"] == [*IMAGES[:3], IMAGES[0], IMAGES[4], IMAGES[2]]


def test_prefetch_rejects_identical_candidate_and_previous_sets(tmp_path: Path) -> None:
    environment, log = fake_docker(tmp_path)
    result = invoke(
        tmp_path,
        environment,
        "-PreviousBackendImage",
        IMAGES[0],
        "-PreviousFrontendImage",
        IMAGES[1],
        "-PreviousRetrievalModelImage",
        IMAGES[2],
    )
    assert result.returncode != 0
    assert not log.exists()
    assert not (tmp_path / "evidence.json").exists()


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
    assert [args for args in commands if args[0] == "pull"] == [
        ["pull", IMAGES[0]],
        ["pull", IMAGES[1]],
        *([["pull", IMAGES[2]]] * 3),
    ]
    assert not (tmp_path / "evidence.json").exists()


def test_prefetch_resumes_verified_images_after_a_failed_pull(tmp_path: Path) -> None:
    """一次中断后只重新拉取未核对的摘要，最终仍需六项全部核对。"""
    environment, log = fake_docker(tmp_path)
    environment["FAKE_DOCKER_FAIL_IMAGE"] = IMAGES[2]
    first = invoke(tmp_path, environment)
    assert first.returncode != 0
    assert not (tmp_path / "evidence.json").exists()

    environment.pop("FAKE_DOCKER_FAIL_IMAGE")
    second = invoke(tmp_path, environment)
    assert second.returncode == 0, second.stdout + second.stderr
    commands = [json.loads(line)["args"] for line in log.read_text("utf-8").splitlines()]
    assert [args for args in commands if args[0] == "pull"] == [
        ["pull", IMAGES[0]],
        ["pull", IMAGES[1]],
        *([["pull", IMAGES[2]]] * 3),
        *[["pull", image] for image in IMAGES[2:]],
    ]
    assert IMAGES[2] in first.stdout
    assert IMAGES[2] in second.stdout
    evidence = json.loads((tmp_path / "evidence.json").read_text("utf-8"))
    assert evidence["image_count"] == 6
    assert evidence["image_references"] == list(IMAGES)


def test_prefetch_retries_one_transient_pull_failure_and_still_verifies_digest(tmp_path: Path) -> None:
    environment, log = fake_docker(tmp_path)
    environment["FAKE_DOCKER_FAIL_ONCE_IMAGE"] = IMAGES[2]
    result = invoke(tmp_path, environment)
    assert result.returncode == 0, result.stdout + result.stderr
    commands = [json.loads(line)["args"] for line in log.read_text("utf-8").splitlines()]
    assert [args for args in commands if args[0] == "pull"] == [
        *[["pull", image] for image in IMAGES[:3]],
        ["pull", IMAGES[2]],
        *[["pull", image] for image in IMAGES[3:]],
    ]
    assert json.loads((tmp_path / "evidence.json").read_text("utf-8"))["image_count"] == 6


def test_prefetch_rejects_wrong_local_repo_digest_after_pull(tmp_path: Path) -> None:
    environment, log = fake_docker(tmp_path)
    environment["FAKE_DOCKER_WRONG_DIGEST_IMAGE"] = IMAGES[1]
    result = invoke(tmp_path, environment)
    assert result.returncode != 0
    commands = [json.loads(line)["args"] for line in log.read_text("utf-8").splitlines()]
    assert [args for args in commands if args[0] == "pull"] == [["pull", image] for image in IMAGES[:2]]
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


def test_all_missing_images_use_checked_resumable_import(tmp_path: Path) -> None:
    environment, log = fake_docker(tmp_path)
    bin_dir = tmp_path / "bin"
    oci_script = tmp_path / "verified-oci-source.py"
    oci_script.write_text("# Exact source fetched by workflow\n", encoding="utf-8")
    fake_oci = bin_dir / "fake_oci.py"
    fake_oci.write_text(
        """import json, os, sys
from pathlib import Path
args = sys.argv[1:]
image = args[args.index('--image') + 1]
with Path(os.environ['FAKE_OCI_LOG']).open('a', encoding='utf-8') as output:
    output.write(json.dumps(args) + '\\n')
if image == os.environ.get('FAKE_OCI_FAIL_IMAGE'):
    sys.exit(42)
with Path(os.environ['FAKE_DOCKER_CACHE']).open('a', encoding='utf-8') as output:
    output.write(image + '\\n')
""",
        encoding="utf-8",
    )
    if os.name == "nt":
        (bin_dir / "python3.cmd").write_text(
            '@echo off\r\n"%FAKE_DOCKER_PYTHON%" "%FAKE_OCI_SCRIPT%" %*\r\n',
            encoding="utf-8",
        )
    else:
        wrapper = bin_dir / "python3"
        wrapper.write_text('#!/bin/sh\nexec "$FAKE_DOCKER_PYTHON" "$FAKE_OCI_SCRIPT" "$@"\n')
        wrapper.chmod(0o755)
    oci_log = tmp_path / "oci.jsonl"
    environment.update(
        {
            "FAKE_OCI_SCRIPT": str(fake_oci),
            "FAKE_OCI_LOG": str(oci_log),
            "DOCKER_CONFIG": str(tmp_path),
        }
    )
    environment["FAKE_OCI_FAIL_IMAGE"] = IMAGES[0]
    failed = invoke(tmp_path, environment, resumable_script=oci_script)
    assert failed.returncode != 0
    assert not (tmp_path / "evidence.json").exists()
    environment.pop("FAKE_OCI_FAIL_IMAGE")
    result = invoke(tmp_path, environment, resumable_script=oci_script)
    assert result.returncode == 0, result.stdout + result.stderr
    commands = [json.loads(line)["args"] for line in log.read_text("utf-8").splitlines()]
    assert [args for args in commands if args[0] == "pull"] == []
    calls = [json.loads(line) for line in oci_log.read_text("utf-8").splitlines()]
    assert [args[args.index("--image") + 1] for args in calls] == [IMAGES[0], *IMAGES]
    assert json.loads((tmp_path / "evidence.json").read_text("utf-8"))["image_count"] == 6


def test_staging_workflow_exposes_prefetch_without_expanding_token_permissions() -> None:
    workflow = yaml.safe_load((REPOSITORY_ROOT / ".github/workflows/staging-gates.yml").read_text("utf-8"))
    assert "prefetch" in workflow[True]["workflow_dispatch"]["inputs"]["operation"]["options"]
    assert workflow["permissions"] == {"contents": "read", "packages": "read"}
    steps = workflow["jobs"]["staging"]["steps"]
    prefetch = next(step for step in steps if step["name"] == "Prefetch immutable rollback images")
    assert prefetch["if"] == "${{ inputs.operation == 'prefetch' }}"
    assert "CRM_STAGING_ENV_FILE" not in prefetch["env"]
    assert "& $env:PREFETCH_SCRIPT" in prefetch["run"]
    assert "$env:GITHUB_RUN_ID-$env:GITHUB_RUN_ATTEMPT.json" in prefetch["run"]
    gate = next(step for step in steps if step["name"] == "Run the selected staging gate")
    assert gate["if"] == "${{ inputs.operation != 'prefetch' }}"
    upload = next(step for step in steps if step["name"] == "Upload low-sensitive prefetch evidence")
    assert upload["if"] == "${{ success() && inputs.operation == 'prefetch' }}"
    assert upload["with"]["path"] == (
        "${{ runner.temp }}/crm-staging-prefetch-evidence-${{ github.run_id }}-${{ github.run_attempt }}.json"
    )


def test_staging_workflow_verifies_reviewed_source_before_docker_access() -> None:
    """Runner Git 路径不可用时，其他 staging 门禁仍须验证精确提交的源码包。"""
    workflow = yaml.safe_load((REPOSITORY_ROOT / ".github/workflows/staging-gates.yml").read_text("utf-8"))
    source_job = workflow["jobs"]["prepare_source"]
    assert source_job["if"] == "${{ inputs.operation != 'prefetch' }}"
    assert source_job["permissions"] == {"contents": "read"}
    source_steps = source_job["steps"]
    checkout = next(step for step in source_steps if step["name"] == "Check out reviewed main")
    assert checkout["with"]["ref"] == "${{ github.sha }}"
    pack = next(step for step in source_steps if step["name"] == "Pack exact staging source")
    assert '"$(git rev-parse HEAD)" != "$GITHUB_SHA"' in pack["run"]
    assert "git archive" in pack["run"]
    assert "source_sha256" in source_job["outputs"]
    steps = workflow["jobs"]["staging"]["steps"]
    download = next(step for step in steps if step["name"] == "Download reviewed staging source")
    verify = next(step for step in steps if step["name"] == "Verify reviewed staging source")
    assert verify["if"] == "${{ inputs.operation != 'prefetch' }}"
    assert steps.index(verify) == steps.index(download) + 1
    assert steps.index(verify) < next(
        i for i, step in enumerate(steps) if step["name"] == "Log in to GHCR for immutable image pulls"
    )
    assert '$env:GITHUB_REF -cne "refs/heads/main"' in verify["run"]
    assert "$actualDigest -cne $env:SOURCE_SHA256" in verify["run"]
    assert "tar -xf" in verify["run"]
    assert verify["id"] == "verify_dispatch_commit"
    gate = next(step for step in steps if step["name"] == "Run the selected staging gate")
    assert gate["working-directory"] == "${{ steps.verify_dispatch_commit.outputs.source_root }}"
    api_source = next(step for step in steps if step["name"] == "Verify exact prefetch source through GitHub API")
    assert api_source["if"] == "${{ inputs.operation == 'prefetch' }}"
    assert api_source["id"] == "verify_prefetch_source"
    login = next(step for step in steps if step["name"] == "Log in to GHCR for immutable image pulls")
    assert steps.index(api_source) < steps.index(login)
    assert "?ref=$env:GITHUB_SHA" in api_source["run"]
    assert '"blob $($scriptBytes.Length)`0"' in api_source["run"]
    assert "$actualBlobSha -cne $source.sha" in api_source["run"]
    assert "Set-StagingDockerPullMode.ps1" in api_source["run"]
    assert "prefetch_ghcr_oci.py" in api_source["run"]
    prefetch = next(step for step in steps if step["name"] == "Prefetch immutable rollback images")
    assert "steps.verify_prefetch_source.outputs.script_path" in prefetch["env"]["PREFETCH_SCRIPT"]
    assert "steps.verify_prefetch_source.outputs.mode_script_path" in prefetch["env"]["PULL_MODE_SCRIPT"]
    assert "steps.verify_prefetch_source.outputs.oci_script_path" in prefetch["env"]["OCI_PREFETCH_SCRIPT"]
    assert "-ResumableOciScript $env:OCI_PREFETCH_SCRIPT" in prefetch["run"]
    assert prefetch["run"].index("& python3 -c") < prefetch["run"].index("-Mode Enter")
    assert "-Mode Enter" in prefetch["run"]
    assert "-Mode Restore" in prefetch["run"]
    assert "& $env:PREFETCH_SCRIPT" in prefetch["run"]
    recovery = next(step for step in steps if step["name"] == "Recover Rootless Docker pull configuration")
    assert "always()" in recovery["if"]
    assert "-Mode Restore" in recovery["run"]
    logout = next(step for step in steps if step["name"] == "Log out from GHCR")
    assert logout["if"] == (
        "${{ always() && (steps.verify_dispatch_commit.outcome == 'success' || "
        "steps.verify_prefetch_source.outcome == 'success') }}"
    )


def test_live_staging_proxy_mount_survives_runner_temp_cleanup() -> None:
    """部署和回滚的相对 Nginx bind 来源必须位于持久目录。"""
    workflow = yaml.safe_load((REPOSITORY_ROOT / ".github/workflows/staging-gates.yml").read_text("utf-8"))
    steps = workflow["jobs"]["staging"]["steps"]
    verify = next(step for step in steps if step["name"] == "Verify reviewed staging source")
    gate = next(step for step in steps if step["name"] == "Run the selected staging gate")

    assert verify["env"]["OPERATION"] == "${{ inputs.operation }}"
    assert "/home/crmdeploy/src/crm-reviewed-source-" in verify["run"]
    assert '"deploy", "rollback"' in verify["run"]
    assert "source_root=$sourceRoot" in verify["run"]
    assert gate["working-directory"] == "${{ steps.verify_dispatch_commit.outputs.source_root }}"
