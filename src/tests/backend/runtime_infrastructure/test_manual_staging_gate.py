"""G5 手动 staging 入口在接触凭据或 Docker 前必须失败关闭。"""

import json
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
    *,
    source_sha: str = "e" * 40,
    backend: str = BACKEND,
    mode: str = "DeployG5",
    archive_sha: str | None = None,
    confirm_content: str | None = None,
    runtime_source_sha: str | None = None,
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
        arguments.extend(
            [
                "-ArchivePath",
                "/home/crmdeploy/src/g5-source.tar",
                "-ArchiveSha256",
                archive_sha,
            ]
        )
    if confirm_content is not None:
        arguments.extend(["-ConfirmContent", confirm_content])
    if runtime_source_sha is not None:
        arguments.extend(["-RuntimeBackendSourceSha", runtime_source_sha])
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
    for mode in (
        "CheckOnly",
        "DeployG5",
        "RestoreDefault",
        "RestoreReadAndTranslation",
        "RollbackPrevious",
    ):
        assert f"'{mode}'" in source
    assert "Test-StagingProductionGates.ps1" in source
    assert "Prepare-StagingRollbackImages.ps1" in source
    assert "Set-StagingDockerPullMode.ps1" in source
    assert "Invoke-StagingRollbackDrill.ps1" in source
    assert "status --porcelain --untracked-files=all" in source
    assert "--password-stdin" in source
    assert "common.EnableG5SSELoadTest = $true" in source


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
def test_accepts_restore_of_existing_read_and_translation_mode() -> None:
    result = invoke(mode="RestoreReadAndTranslation")
    assert result.returncode != 0
    assert "staging linux host" in (result.stdout + result.stderr).lower()


def test_read_and_translation_restore_uses_both_existing_gate_switches() -> None:
    source = SCRIPT.read_text("utf-8")
    assert "if ($Mode -ceq 'RestoreReadAndTranslation')" in source
    assert "$common.EnableTikTokWebhookRead = $true" in source
    assert "$common.EnableWorkspaceTranslation = $true" in source


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
@pytest.mark.parametrize(
    ("mode", "confirmation"),
    [
        ("ContentCheck", None),
        ("ContentPrepare", "prepare-50-isolated-g5-messages"),
        ("RenewCredentials", "renew-50-existing-g5-tokens"),
    ],
)
def test_content_modes_reach_host_gate_only_with_exact_confirmation(mode: str, confirmation: str | None) -> None:
    result = invoke(mode=mode, confirm_content=confirmation)
    assert result.returncode != 0
    assert "staging linux host" in (result.stdout + result.stderr).lower()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
@pytest.mark.parametrize("mode", ["ContentPrepare", "RenewCredentials"])
def test_content_writes_reject_missing_confirmation_before_host_access(
    mode: str,
) -> None:
    result = invoke(mode=mode)
    assert result.returncode != 0
    assert "content confirmation" in (result.stdout + result.stderr).lower()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
def test_content_prepare_rejects_confirmation_for_credential_renewal() -> None:
    result = invoke(mode="ContentPrepare", confirm_content="renew-50-existing-g5-tokens")
    assert result.returncode != 0
    assert "content confirmation" in (result.stdout + result.stderr).lower()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
def test_one_faq_vectorization_requires_exact_confirmation_and_image_revision() -> None:
    missing_confirmation = invoke(mode="VectorizeG5", runtime_source_sha="f" * 40)
    assert missing_confirmation.returncode != 0
    assert "content confirmation" in (missing_confirmation.stdout + missing_confirmation.stderr).lower()

    missing_revision = invoke(mode="VectorizeG5", confirm_content="vectorize-one-isolated-g5-faq")
    assert missing_revision.returncode != 0
    assert "runtime backend source sha" in (missing_revision.stdout + missing_revision.stderr).lower()

    valid = invoke(
        mode="VectorizeG5",
        confirm_content="vectorize-one-isolated-g5-faq",
        runtime_source_sha="f" * 40,
    )
    assert valid.returncode != 0
    assert "staging linux host" in (valid.stdout + valid.stderr).lower()


def test_manual_content_runner_uses_reviewed_workdir_and_private_mounts() -> None:
    source = (SOURCE_ROOT / "scripts" / "Invoke-StagingManualG5Content.ps1").read_text("utf-8")
    assert "'--workdir', '/opt/crm-g5-source'" in source
    assert "type=bind,source=$source,target=/opt/crm-g5-source,readonly" in source
    assert "PYTHONPATH=/opt/crm-g5-source:/app" in source
    assert "target=/opt/crm-g5-vectorize.py,readonly" not in source
    assert "'--read-only'" in source
    assert "'--pull=never'" in source
    assert "g5-38852775454-2.json" in source
    assert "g5-38852775454-3.json" in source
    assert "EXPECTED_RUNTIME_JWT_SHA256" in source
    assert "DATABASE_URL" in source


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
def test_direct_content_runner_rejects_write_without_confirmation() -> None:
    script = SOURCE_ROOT / "scripts" / "Invoke-StagingManualG5Content.ps1"
    result = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(script),
            "-Mode",
            "ContentPrepare",
            "-SourceSha",
            "e" * 40,
            "-BackendImage",
            BACKEND,
            "-ReviewRoot",
            "/home/crmdeploy/src/crm-reviewed-source-g5-test",
            "-EnvironmentFile",
            "/home/crmdeploy/config/crm-staging.env",
            "-DockerHost",
            "unix:///run/user/1004/docker.sock",
            "-EvidenceFile",
            "/home/crmdeploy/.cache/crm-g5-manual/g5-test/content.json",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=15,
    )
    assert result.returncode != 0
    assert "content confirmation" in (result.stdout + result.stderr).lower()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
def test_direct_vector_runner_rejects_write_without_confirmation() -> None:
    script = SOURCE_ROOT / "scripts" / "Invoke-StagingManualG5Content.ps1"
    result = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(script),
            "-Mode",
            "VectorizeG5",
            "-SourceSha",
            "e" * 40,
            "-RuntimeBackendSourceSha",
            "f" * 40,
            "-BackendImage",
            BACKEND,
            "-ReviewRoot",
            "/home/crmdeploy/src/crm-reviewed-source-g5-test",
            "-EnvironmentFile",
            "/home/crmdeploy/config/crm-staging.env",
            "-DockerHost",
            "unix:///run/user/1004/docker.sock",
            "-EvidenceFile",
            "/home/crmdeploy/.cache/crm-g5-manual/g5-test/content.json",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=15,
    )
    assert result.returncode != 0
    assert "content confirmation" in (result.stdout + result.stderr).lower()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
def test_private_file_policy_allows_read_only_reconciliation_after_renewal() -> None:
    policy = SOURCE_ROOT / "scripts" / "Assert-StagingG5PrivateFileSet.ps1"

    def check(mode: str, names: list[str]) -> int:
        return subprocess.run(
            [
                POWERSHELL,
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(policy),
                "-Mode",
                mode,
                "-NamesJson",
                json.dumps(names),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=15,
        ).returncode

    original = ["g5-38852775454-1.json", "g5-38852775454-2.json"]
    renewed = [*original, "g5-38852775454-3.json"]
    assert check("ContentCheck", original) == 0
    assert check("ContentCheck", renewed) == 0
    assert check("VectorizeG5", original) == 0
    assert check("VectorizeG5", renewed) != 0
    assert check("RenewCredentials", renewed) != 0
    assert check("ContentPrepare", renewed) != 0
    assert check("ContentCheck", [*renewed, "unexpected.json"]) != 0
    assert check("ContentCheck", ["g5-38852775454-1.json,g5-38852775454-2.json"]) != 0
