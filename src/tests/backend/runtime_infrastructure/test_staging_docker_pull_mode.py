"""Rootless staging pull tuning must be reversible and scoped to the runner."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from _support import SOURCE_ROOT

SCRIPT = SOURCE_ROOT / "scripts" / "Set-StagingDockerPullMode.ps1"
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")


@pytest.mark.parametrize("original", [b'{"debug":true,"max-concurrent-downloads":3}\n', b"", None])
@pytest.mark.parametrize("prefetch_fails", [False, True])
def test_staging_pull_mode_restores_original_config_bytes(
    tmp_path: Path, original: bytes | None, prefetch_fails: bool
) -> None:
    assert POWERSHELL is not None
    config = tmp_path / "new-config" / "daemon.json" if original is None else tmp_path / "daemon.json"
    if original:
        config.write_bytes(original)
    backup = config.parent / "daemon.backup"
    harness = tmp_path / "harness.ps1"
    harness.write_text(
        """$ErrorActionPreference = 'Stop'
function id { $global:LASTEXITCODE = 0; '1004' }
function systemctl {
    $global:LASTEXITCODE = 0
    if ($args[0] -eq '--user' -and $args[1] -eq 'is-active') { 'active'; return }
    if ($args[0] -eq '--user' -and $args[1] -eq 'show') {
        if ($args -contains 'ExecReload') { '/bin/kill -s HUP'; return }
        '1234'; return
    }
    if ($args[0] -eq '--user' -and $args[1] -eq 'reload') { return }
    throw 'unexpected systemctl call'
}
function docker { $global:LASTEXITCODE = 0; 'runner-daemon' }
& $args[0] -Mode Enter -DockerHost 'unix:///run/user/1004/docker.sock' -ConfigPath $args[1] -BackupPath $args[2]
if ($LASTEXITCODE -ne 0) { throw 'enter failed' }
$active = Get-Content -LiteralPath $args[1] -Raw | ConvertFrom-Json
if ($active.'max-concurrent-downloads' -ne 1) { throw 'concurrency was not lowered' }
if (-not (Test-Path -LiteralPath $args[2])) { throw 'backup missing while active' }
try {
    if ($args[3] -eq 'fail') { throw 'simulated prefetch failure' }
}
finally {
    & $args[0] -Mode Restore -DockerHost 'unix:///run/user/1004/docker.sock' -ConfigPath $args[1] -BackupPath $args[2]
}
if (Test-Path -LiteralPath $args[2]) { throw 'backup retained after restore' }
""",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            POWERSHELL,
            "-NoLogo",
            "-NoProfile",
            "-File",
            str(harness),
            str(SCRIPT),
            str(config),
            str(backup),
            "fail" if prefetch_fails else "pass",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    assert (result.returncode != 0) == prefetch_fails, result.stdout + result.stderr
    if original:
        assert config.read_bytes() == original
    else:
        assert not config.exists()
    if original is None:
        assert not config.parent.exists()
    assert not backup.exists()


def test_staging_pull_mode_rejects_wrong_docker_socket_before_config_change(
    tmp_path: Path,
) -> None:
    assert POWERSHELL is not None
    config = tmp_path / "daemon.json"
    config.write_text(json.dumps({"max-concurrent-downloads": 3}), encoding="utf-8")
    original = config.read_bytes()
    backup = tmp_path / "daemon.backup"
    result = subprocess.run(
        [
            POWERSHELL,
            "-NoLogo",
            "-NoProfile",
            "-File",
            str(SCRIPT),
            "-Mode",
            "Enter",
            "-DockerHost",
            "unix:///var/run/docker.sock",
            "-ConfigPath",
            str(config),
            "-BackupPath",
            str(backup),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    assert result.returncode != 0
    assert config.read_bytes() == original
    assert not backup.exists()
