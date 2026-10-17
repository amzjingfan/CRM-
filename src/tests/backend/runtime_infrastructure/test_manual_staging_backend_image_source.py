"""手动 G5 新部署只接受构建输入未变的祖先后端镜像。"""

import shutil
import subprocess

import pytest
from _support import SOURCE_ROOT

SCRIPT = SOURCE_ROOT / "scripts" / "Assert-StagingManualBackendImageSource.ps1"
POWERSHELL = shutil.which("pwsh")
IMAGE_REVISION = "a" * 40
CURRENT_MAIN = "b" * 40


def check_revision(
    *,
    mode: str = "DeployG5",
    compare_status: str = "ahead",
    backend_changed: bool = False,
    dockerfile_changed: bool = False,
    dockerfile_missing: bool = False,
    truncated: bool = False,
    image_revision: str = IMAGE_REVISION,
) -> subprocess.CompletedProcess[str]:
    assert POWERSHELL is not None
    backend_image = "1" * 40
    backend_main = ("2" if backend_changed else "1") * 40
    dockerfile_image = "3" * 40
    dockerfile_main = ("4" if dockerfile_changed else "3") * 40
    old_tree = (
        "@{ truncated=$false; tree=@("
        f"@{{path='src/backend';type='tree';sha='{backend_image}'}},"
        f"@{{path='src/docker/Dockerfile.backend';type='blob';sha='{dockerfile_image}'}}"
        ") }"
    )
    current_entries = [f"@{{path='src/backend';type='tree';sha='{backend_main}'}}"]
    if not dockerfile_missing:
        current_entries.append(f"@{{path='src/docker/Dockerfile.backend';type='blob';sha='{dockerfile_main}'}}")
    current_tree = f"@{{ truncated=${str(truncated).lower()}; tree=@(" + ",".join(current_entries) + ") }"
    escaped_script = str(SCRIPT).replace("'", "''")
    command = (
        "function Invoke-RestMethod { param($Uri, $Headers) "
        f"if ($Uri -like '*/compare/*') {{ return @{{status='{compare_status}';behind_by=0;ahead_by=1}} }} "
        f"if ($Uri -like '*{IMAGE_REVISION}?recursive=1') {{ return {old_tree} }} "
        f"if ($Uri -like '*{CURRENT_MAIN}?recursive=1') {{ return {current_tree} }} "
        "throw 'Unexpected API call' }; "
        f"& '{escaped_script}' -Mode {mode} "
        f"-SourceSha {CURRENT_MAIN} -ImageRevisionSha {image_revision} -Token 'fixture'"
    )
    return subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=15,
    )


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
def test_ancestor_image_with_identical_backend_build_inputs_is_allowed() -> None:
    assert check_revision().returncode == 0


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
def test_reconcile_accepts_ancestor_image_with_identical_backend_build_inputs() -> None:
    assert check_revision(mode="ReconcileFixture").returncode == 0


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
@pytest.mark.parametrize(
    "changes",
    [
        {"compare_status": "diverged"},
        {"backend_changed": True},
        {"dockerfile_changed": True},
        {"dockerfile_missing": True},
        {"truncated": True},
    ],
)
def test_reconcile_rejects_unverified_or_changed_backend_image(changes: dict[str, object]) -> None:
    assert check_revision(mode="ReconcileFixture", **changes).returncode != 0  # type: ignore[arg-type]


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
def test_matching_recovery_image_needs_no_github_comparison() -> None:
    assert check_revision(mode="RestoreReadAndTranslation", image_revision=CURRENT_MAIN).returncode == 0


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
@pytest.mark.parametrize(
    "changes",
    [
        {"compare_status": "diverged"},
        {"backend_changed": True},
        {"dockerfile_changed": True},
        {"dockerfile_missing": True},
        {"truncated": True},
        {"mode": "RestoreReadAndTranslation"},
    ],
)
def test_revision_drift_fails_closed_when_not_an_identical_build(changes: dict[str, object]) -> None:
    assert check_revision(**changes).returncode != 0  # type: ignore[arg-type]
