"""G5 手动 staging 入口在接触凭据或 Docker 前必须失败关闭。"""

import shutil
import subprocess

import pytest
from _support import SOURCE_ROOT

SCRIPT = SOURCE_ROOT / "scripts" / "Invoke-StagingManualG5.ps1"
POWERSHELL = shutil.which("pwsh")
BACKEND = "ghcr.io/cp11-gh/crm-backend@sha256:" + "a" * 64
FRONTEND = "ghcr.io/cp11-gh/crm-frontend@sha256:" + "b" * 64
RETRIEVAL = "ghcr.io/cp11-gh/crm-retrieval-model-service@sha256:" + "c" * 64
PREVIOUS_BACKEND = "ghcr.io/cp11-gh/crm-backend@sha256:" + "d" * 64


def invoke(
    *, source_sha: str = "e" * 40, backend: str = BACKEND, mode: str = "DeployG5", archive_sha: str | None = None
) -> subprocess.CompletedProcess[str]:
    assert POWERSHELL is not None
    arguments = [
        POWERSHELL,
        "-NoProfile",
        "-NonInteractive",
        "-File",
        str(SCRIPT),
        "-Mode",
        mode,
        "-SourceSha",
        source_sha,
        "-CandidateBackendImage",
        backend,
        "-FrontendImage",
        FRONTEND,
        "-RetrievalModelImage",
        RETRIEVAL,
        "-PreviousBackendImage",
        PREVIOUS_BACKEND,
        "-PreviousFrontendImage",
        FRONTEND,
        "-PreviousRetrievalModelImage",
        RETRIEVAL,
        "-ConfirmTarget",
        "staging",
        "-EvidenceDirectory",
        "/home/crmdeploy/evidence/g5-test",
    ]
    if archive_sha is not None:
        arguments.extend(["-ArchivePath", "/home/crmdeploy/src/g5-source.tar", "-ArchiveSha256", archive_sha])
    return subprocess.run(
        arguments,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=15,
    )


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
def test_rejects_unpinned_backend_before_host_access() -> None:
    result = invoke(backend="ghcr.io/cp11-gh/crm-backend:latest")
    assert result.returncode != 0
    assert "immutable" in (result.stdout + result.stderr).lower()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
def test_rejects_invalid_source_sha_before_host_access() -> None:
    result = invoke(source_sha="main")
    assert result.returncode != 0
    assert "source sha" in (result.stdout + result.stderr).lower()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
def test_refuses_to_run_outside_staging_linux_host() -> None:
    result = invoke(mode="CheckOnly")
    assert result.returncode != 0
    assert "staging linux host" in (result.stdout + result.stderr).lower()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
def test_rejects_invalid_reviewed_archive_hash_before_host_access() -> None:
    result = invoke(archive_sha="not-a-hash")
    assert result.returncode != 0
    assert "archive sha" in (result.stdout + result.stderr).lower()


def test_manual_entry_keeps_rollback_and_default_restore_explicit() -> None:
    source = SCRIPT.read_text("utf-8")
    assert "ValidateSet('CheckOnly', 'DeployG5', 'RestoreDefault', 'RollbackPrevious')" in source
    assert "Test-StagingProductionGates.ps1" in source
    assert "Prepare-StagingRollbackImages.ps1" in source
    assert "Set-StagingDockerPullMode.ps1" in source
    assert "Invoke-StagingRollbackDrill.ps1" in source
    assert "status --porcelain --untracked-files=all" in source
    assert "--password-stdin" in source
    assert "common.EnableG5SSELoadTest = $true" in source
