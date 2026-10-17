"""手动 G5 部署锁当前 main，恢复锁已审核的历史提交。"""

import shutil
import subprocess

import pytest
from _support import SOURCE_ROOT

SCRIPT = SOURCE_ROOT / "scripts" / "Assert-StagingManualSourcePolicy.ps1"
POWERSHELL = shutil.which("pwsh")
SOURCE = "a" * 40
NEXT_MAIN = "b" * 40


def check(mode: str, *, current_main: str = SOURCE, resolved_commit: str = SOURCE) -> subprocess.CompletedProcess[str]:
    assert POWERSHELL is not None
    return subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(SCRIPT),
            "-Mode",
            mode,
            "-SourceSha",
            SOURCE,
            "-ResolvedCommitSha",
            resolved_commit,
            "-CurrentMainSha",
            current_main,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=15,
    )


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
@pytest.mark.parametrize("mode", ["CheckOnly", "DeployG5", "VectorizeG5"])
def test_new_deployment_requires_current_main(mode: str) -> None:
    assert check(mode).returncode == 0
    assert check(mode, current_main=NEXT_MAIN).returncode != 0


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
@pytest.mark.parametrize(
    "mode",
    [
        "RestoreDefault",
        "RestoreReadAndTranslation",
        "RollbackPrevious",
        "ContentCheck",
        "ContentPrepare",
        "RenewCredentials",
    ],
)
def test_recovery_accepts_reviewed_commit_after_main_moves(mode: str) -> None:
    assert check(mode, current_main=NEXT_MAIN).returncode == 0
    assert check(mode, current_main=NEXT_MAIN, resolved_commit=NEXT_MAIN).returncode != 0


def test_gate_calls_shared_policy_and_checks_recovery_image_revision() -> None:
    gate = (SOURCE_ROOT / "scripts" / "Invoke-StagingManualG5.ps1").read_text("utf-8")
    assert "Assert-StagingManualSourcePolicy.ps1" in gate
    assert gate.count("Assert-StagingManualBackendImageSource.ps1") == 2
    assert "-ImageRevisionSha ([string]$candidate.Config.Labels.'org.opencontainers.image.revision')" in gate
