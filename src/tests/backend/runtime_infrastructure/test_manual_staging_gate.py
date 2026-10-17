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
    pre_window_evidence_directory: str | None = None,
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
    if pre_window_evidence_directory is not None:
        arguments.extend(["-PreWindowEvidenceDirectory", pre_window_evidence_directory])
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
    result = invoke(
        mode="RestoreReadAndTranslation",
        pre_window_evidence_directory="/home/crmdeploy/.cache/crm-g5-manual/prior-g5-window",
    )
    assert result.returncode != 0
    assert "staging linux host" in (result.stdout + result.stderr).lower()


def test_read_and_translation_restore_uses_both_existing_gate_switches() -> None:
    source = SCRIPT.read_text("utf-8")
    assert "if ($Mode -ceq 'RestoreReadAndTranslation')" in source
    assert "$common.EnableTikTokWebhookRead = $true" in source
    assert "$common.EnableWorkspaceTranslation = $true" in source


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
def test_manual_send_restore_takes_conversation_only_from_private_snapshot() -> None:
    valid = invoke(
        mode="RestoreManualSend", pre_window_evidence_directory="/home/crmdeploy/.cache/crm-g5-manual/prior-g5-window"
    )
    assert valid.returncode != 0
    assert "staging linux host" in (valid.stdout + valid.stderr).lower()

    source = SCRIPT.read_text("utf-8")
    assert "[string]$AllowedTikTokConversationId," not in source
    assert "Get-Content -LiteralPath $snapshotFile -Raw | ConvertFrom-Json" in source


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
@pytest.mark.parametrize("restore_mode", ["RestoreDefault", "RestoreReadAndTranslation", "RestoreManualSend"])
def test_each_restore_requires_a_private_pre_window_snapshot_path(restore_mode: str) -> None:
    missing = invoke(mode=restore_mode)
    assert "pre-window evidence" in (missing.stdout + missing.stderr).lower()

    invalid = invoke(
        mode=restore_mode,
        pre_window_evidence_directory="/tmp/restore.json",
    )
    assert "pre-window evidence" in (invalid.stdout + invalid.stderr).lower()

    unrelated = invoke(
        mode="DeployG5",
        pre_window_evidence_directory="/home/crmdeploy/.cache/crm-g5-manual/prior-g5-window",
    )
    assert "pre-window evidence" in (unrelated.stdout + unrelated.stderr).lower()


def test_manual_send_restore_targets_previous_digests_and_scoped_gate() -> None:
    source = SCRIPT.read_text("utf-8")
    assert "'RestoreManualSend'" in source
    assert "Mode -ceq 'RestoreManualSend'" in source
    assert (
        "Mode -cin @('RollbackPrevious', 'RestoreDefault', 'RestoreReadAndTranslation', 'RestoreManualSend')" in source
    )
    assert "{ $PreviousBackendImage } else { $CandidateBackendImage }" in source
    assert "{ $PreviousFrontendImage } else { $FrontendImage }" in source
    assert "{ $PreviousRetrievalModelImage } else { $RetrievalModelImage }" in source
    assert "$common.EnableTikTokWebhookRead = $true" in source
    assert "$common.EnableTikTokManualSend = $true" in source
    assert "$common.AllowedTikTokConversationId = $restoredConversation" in source
    assert "$common.EnableWorkspaceTranslation = $true" in source
    assert "Assert-StagingG5RestoreSnapshot.ps1" in source
    assert source.count("-Mode VerifyUnchanged") == 2
    assert "$deployCommon.PreWindowSnapshotFile = $snapshotFile" in source


def test_g5_deploy_rechecks_pre_window_state_inside_shared_deployment_lock() -> None:
    source = (SOURCE_ROOT / "scripts" / "Test-StagingProductionGates.ps1").read_text("utf-8")
    lock = source.index("'crm-staging-deploy.lock'")
    recheck = source.index("-Mode VerifyUnchanged @snapshotArgs")
    pull = source.index("Invoke-ComposePullsWithRetry -Command $compose")
    assert lock < recheck < pull


def test_g5_restore_rechecks_window_state_inside_shared_deployment_lock() -> None:
    source = (SOURCE_ROOT / "scripts" / "Test-StagingProductionGates.ps1").read_text("utf-8")
    lock = source.index("'crm-staging-deploy.lock'")
    recheck = source.index("-Mode VerifyRecoverableCurrent @snapshotArgs")
    pull = source.index("Invoke-ComposePullsWithRetry -Command $compose", lock)
    assert lock < recheck < pull


def test_emergency_rollback_uses_shared_deployment_lock() -> None:
    source = (SOURCE_ROOT / "scripts" / "Invoke-StagingRollbackDrill.ps1").read_text("utf-8")
    lock = source.index("'crm-staging-deploy.lock'")
    recheck = source.index("Assert-LiveCandidateImages -Command $compose -ComposeArguments $composeArguments")
    mutate = source.index(
        'Invoke-Compose -Command $compose -Arguments ($composeArguments + @("pull", "tiktok-egress"))'
    )
    assert lock < recheck < mutate
    assert "[System.IO.FileShare]::None" in source
    assert "$deploymentLock.Dispose()" in source


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
@pytest.mark.parametrize(
    ("mode", "confirmation"),
    [
        ("ContentCheck", None),
        ("ContentPrepare", "prepare-50-isolated-g5-messages"),
        ("ReconcileFixture", "replace-50-isolated-g5-return-questions"),
        ("ReconcileFaqV3", "replace-one-isolated-g5-faq-answer-v3"),
        ("RenewCredentials", "renew-50-existing-g5-tokens"),
    ],
)
def test_content_modes_reach_host_gate_only_with_exact_confirmation(mode: str, confirmation: str | None) -> None:
    runtime_source_sha = "f" * 40 if mode == "ReconcileFixture" else None
    result = invoke(mode=mode, confirm_content=confirmation, runtime_source_sha=runtime_source_sha)
    assert result.returncode != 0
    assert "staging linux host" in (result.stdout + result.stderr).lower()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
@pytest.mark.parametrize("mode", ["ContentPrepare", "ReconcileFixture", "ReconcileFaqV3", "RenewCredentials"])
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
def test_replacement_rejects_other_write_confirmation() -> None:
    result = invoke(mode="ReconcileFixture", confirm_content="prepare-50-isolated-g5-messages")
    assert result.returncode != 0
    assert "content confirmation" in (result.stdout + result.stderr).lower()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
def test_replacement_requires_runtime_image_revision_before_host_access() -> None:
    missing = invoke(mode="ReconcileFixture", confirm_content="replace-50-isolated-g5-return-questions")
    assert missing.returncode != 0
    assert "runtime backend source sha" in (missing.stdout + missing.stderr).lower()

    provided = invoke(
        mode="ReconcileFixture",
        confirm_content="replace-50-isolated-g5-return-questions",
        runtime_source_sha="f" * 40,
    )
    assert provided.returncode != 0
    assert "staging linux host" in (provided.stdout + provided.stderr).lower()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
def test_replacement_accepts_only_original_four_file_inventory() -> None:
    policy = SOURCE_ROOT / "scripts" / "Assert-StagingG5PrivateFileSet.ps1"

    def check(names: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                POWERSHELL,
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(policy),
                "-Mode",
                "ReconcileFixture",
                "-NamesJson",
                json.dumps(names),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=15,
        )

    exact = [f"g5-38852775454-{index}.json" for index in range(1, 5)]
    assert check(exact).returncode == 0
    assert check(exact[:-1]).returncode != 0
    assert check([*exact, "unexpected.json"]).returncode != 0


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
def test_third_faq_reconciliation_requires_exact_five_file_inventory() -> None:
    policy = SOURCE_ROOT / "scripts" / "Assert-StagingG5PrivateFileSet.ps1"

    def check(names: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                POWERSHELL,
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(policy),
                "-Mode",
                "ReconcileFaqV3",
                "-NamesJson",
                json.dumps(names),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=15,
        )

    exact = [f"g5-38852775454-{index}.json" for index in range(1, 6)]
    assert check(exact).returncode == 0
    assert check(exact[:-1]).returncode != 0
    assert check([*exact, "unexpected.json"]).returncode != 0


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
    assert "Assert-StagingG5PrivateFileSet.ps1" in source
    assert '"/opt/crm-g5-credentials/$credentialName"' in source
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
    fourth = [*renewed, "g5-38852775454-4.json"]
    fifth = [*fourth, "g5-38852775454-5.json"]
    assert check("ContentCheck", original) == 0
    assert check("ContentCheck", renewed) == 0
    assert check("ContentCheck", fourth) == 0
    assert check("ContentCheck", fifth) == 0
    assert check("RenewCredentials", fourth) == 0
    assert check("VectorizeG5", original) == 0
    assert check("VectorizeG5", renewed) != 0
    assert check("ContentPrepare", renewed) != 0
    assert check("ContentCheck", [*renewed, "unexpected.json"]) != 0
    assert check("ContentCheck", [*renewed, "g5-38852775454-5.json"]) != 0
    assert check("RenewCredentials", [*renewed, "g5-38852775454-5.json"]) != 0
    assert check("ContentCheck", [*renewed, "g5-38852775454-04.json"]) != 0
    assert check("ContentCheck", ["g5-38852775454-1.json,g5-38852775454-2.json"]) != 0


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
def test_private_file_policy_selects_latest_for_read_and_next_for_renewal() -> None:
    policy = SOURCE_ROOT / "scripts" / "Assert-StagingG5PrivateFileSet.ps1"
    original = ["g5-38852775454-1.json", "g5-38852775454-2.json"]
    generations = [*original, "g5-38852775454-3.json", "g5-38852775454-4.json"]
    ten_generations = [f"g5-38852775454-{index}.json" for index in range(1, 11)]
    for mode, names, expected in (
        ("ContentCheck", original, "g5-38852775454-3.json"),
        ("ContentCheck", generations, "g5-38852775454-4.json"),
        ("RenewCredentials", generations, "g5-38852775454-5.json"),
        ("ContentCheck", ten_generations, "g5-38852775454-10.json"),
        ("RenewCredentials", ten_generations, "g5-38852775454-11.json"),
    ):
        result = subprocess.run(
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
        )
        assert result.returncode == 0
        assert result.stdout.strip() == expected
