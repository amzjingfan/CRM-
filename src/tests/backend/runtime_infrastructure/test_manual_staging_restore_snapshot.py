"""G5 恢复必须匹配窗口开启前捕获的运行状态。"""

import json
import shutil
import subprocess

import pytest
from _support import SOURCE_ROOT

SCRIPT = SOURCE_ROOT / "scripts" / "Assert-StagingG5RestoreSnapshot.ps1"
POWERSHELL = shutil.which("pwsh")
IMAGES = {
    "candidate_backend": "ghcr.io/cp11-gh/crm-backend@sha256:" + "a" * 64,
    "candidate_frontend": "ghcr.io/cp11-gh/crm-frontend@sha256:" + "b" * 64,
    "candidate_retrieval": "ghcr.io/cp11-gh/crm-retrieval-model-service@sha256:" + "c" * 64,
    "previous_backend": "ghcr.io/cp11-gh/crm-backend@sha256:" + "d" * 64,
    "previous_frontend": "ghcr.io/cp11-gh/crm-frontend@sha256:" + "e" * 64,
    "previous_retrieval": "ghcr.io/cp11-gh/crm-retrieval-model-service@sha256:" + "f" * 64,
}


def invoke(snapshot, *, restore_mode="RestoreManualSend", images=None):
    assert POWERSHELL is not None
    chosen = IMAGES | (images or {})
    return subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(SCRIPT),
            "-Mode",
            "VerifyRestore",
            "-RestoreMode",
            restore_mode,
            "-SnapshotFile",
            str(snapshot),
            "-CandidateBackendImage",
            chosen["candidate_backend"],
            "-FrontendImage",
            chosen["candidate_frontend"],
            "-RetrievalModelImage",
            chosen["candidate_retrieval"],
            "-PreviousBackendImage",
            chosen["previous_backend"],
            "-PreviousFrontendImage",
            chosen["previous_frontend"],
            "-PreviousRetrievalModelImage",
            chosen["previous_retrieval"],
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=15,
    )


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
def test_restore_matches_only_captured_images_conversation_and_translation(tmp_path) -> None:
    snapshot = tmp_path / "restore-snapshot.json"
    snapshot.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "images": IMAGES,
                "manual_send_enabled": True,
                "webhook_read_enabled": True,
                "allowed_conversation_id": "123456789",
                "workspace_translation_enabled": True,
            }
        ),
        encoding="utf-8",
    )
    matching = invoke(snapshot)
    assert matching.returncode == 0, matching.stderr
    assert matching.stdout.strip() == "true"

    wrong_mode = invoke(snapshot, restore_mode="RestoreDefault")
    assert wrong_mode.returncode != 0
    assert "pre-window snapshot" in (wrong_mode.stdout + wrong_mode.stderr).lower()

    wrong_digest = invoke(snapshot, images={"previous_frontend": IMAGES["candidate_frontend"]})
    assert wrong_digest.returncode != 0
    assert "pre-window snapshot" in (wrong_digest.stdout + wrong_digest.stderr).lower()

    state = json.loads(snapshot.read_text(encoding="utf-8"))
    state["workspace_translation_enabled"] = False
    snapshot.write_text(json.dumps(state), encoding="utf-8")
    assert invoke(snapshot).stdout.strip() == "false"

    snapshot.write_text(
        snapshot.read_text(encoding="utf-8").replace('"manual_send_enabled": true', '"manual_send_enabled": false'),
        encoding="utf-8",
    )
    disabled_send = invoke(snapshot)
    assert disabled_send.returncode != 0


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
def test_other_restore_modes_cannot_override_pre_window_manual_send(tmp_path) -> None:
    snapshot = tmp_path / "restore-snapshot.json"
    state = {
        "schema_version": 1,
        "images": IMAGES,
        "manual_send_enabled": False,
        "webhook_read_enabled": True,
        "allowed_conversation_id": "",
        "workspace_translation_enabled": True,
    }
    snapshot.write_text(json.dumps(state), encoding="utf-8")
    assert invoke(snapshot, restore_mode="RestoreReadAndTranslation").stdout.strip() == "true"
    assert invoke(snapshot, restore_mode="RestoreDefault").returncode != 0
    state["webhook_read_enabled"] = False
    state["workspace_translation_enabled"] = False
    snapshot.write_text(json.dumps(state), encoding="utf-8")
    assert invoke(snapshot, restore_mode="RestoreDefault").stdout.strip() == "false"
    assert invoke(snapshot, restore_mode="RestoreManualSend").returncode != 0


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
def test_restore_rejects_missing_or_invalid_snapshot(tmp_path) -> None:
    snapshot = tmp_path / "restore-snapshot.json"
    assert invoke(snapshot).returncode != 0
    snapshot.write_text("{}", encoding="utf-8")
    assert invoke(snapshot).returncode != 0


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
def test_capture_reads_running_images_and_scoped_mode_before_window(tmp_path) -> None:
    snapshot = tmp_path / "restore-snapshot.json"
    harness = tmp_path / "capture.ps1"
    harness.write_text(
        """
param([string]$SnapshotFile, [string]$RunningBackendImage, [switch]$ChangeAfterCapture, [switch]$UnsupportedMode)
if ($UnsupportedMode) { $manualSend = 'false'; $conversation = ''; $translation = 'false' }
else { $manualSend = 'true'; $conversation = '123456789'; $translation = 'true' }
function docker {
    $global:LASTEXITCODE = 0
    if ($args[0] -ceq 'ps') {
        $service = [string](@($args | Where-Object { $_ -like 'label=com.docker.compose.service=*' })[0])
        switch ($service) {
            'label=com.docker.compose.service=backend' { return 'aaaaaaaaaaaa' }
            'label=com.docker.compose.service=frontend' { return 'bbbbbbbbbbbb' }
            'label=com.docker.compose.service=retrieval-model-service' { return 'cccccccccccc' }
        }
        throw 'unexpected service'
    }
    if ($args[0] -ceq 'inspect') {
        switch ($args[-1]) {
            'aaaaaaaaaaaa' {
                return (@{ Image = $RunningBackendImage; Env = @(
                    "REAL_TIKTOK_MESSAGE_WRITE_ENABLED=$manualSend",
                    "TIKTOK_MESSAGE_WRITE_ALLOWED_CONVERSATION_ID=$conversation",
                    "WORKSPACE_MESSAGE_TRANSLATION_ENABLED=$translation",
                    'LLM_ENABLED=false', 'SSE_LOAD_TEST_ENABLED=false',
                    'REAL_TIKTOK_READ_ENABLED=true',
                    'REAL_TIKTOK_WEBHOOK_ENABLED=true',
                    'REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED=false',
                    'ALLOW_MOCK_PLATFORM_ADAPTERS=false',
                    'LLM_LIVE_EVAL=false',
                    'AI_TRANSLATION_ENABLED=false',
                    'AI_MARKETING_ENABLED=false',
                    'AUTO_REPLY_ENABLED=false',
                    'CHAT_QUERY_LIMIT=10'
                ) } | ConvertTo-Json -Compress)
            }
            'bbbbbbbbbbbb' { return (@{ Image = 'PREVIOUS_FRONTEND'; Env = @() } | ConvertTo-Json -Compress) }
            'cccccccccccc' { return (@{ Image = 'PREVIOUS_RETRIEVAL'; Env = @() } | ConvertTo-Json -Compress) }
        }
    }
    throw 'unexpected docker call'
}
function chmod { $global:LASTEXITCODE = 0 }
& 'SNAPSHOT_SCRIPT' -Mode Capture -SnapshotFile $SnapshotFile `
    -CandidateBackendImage 'CANDIDATE_BACKEND' -FrontendImage 'CANDIDATE_FRONTEND' `
    -RetrievalModelImage 'CANDIDATE_RETRIEVAL' -PreviousBackendImage 'PREVIOUS_BACKEND' `
    -PreviousFrontendImage 'PREVIOUS_FRONTEND' -PreviousRetrievalModelImage 'PREVIOUS_RETRIEVAL'
if ($LASTEXITCODE -ne 0) { throw 'capture failed' }
if ($ChangeAfterCapture) { $RunningBackendImage = 'CANDIDATE_BACKEND' }
& 'SNAPSHOT_SCRIPT' -Mode VerifyUnchanged -SnapshotFile $SnapshotFile `
    -CandidateBackendImage 'CANDIDATE_BACKEND' -FrontendImage 'CANDIDATE_FRONTEND' `
    -RetrievalModelImage 'CANDIDATE_RETRIEVAL' -PreviousBackendImage 'PREVIOUS_BACKEND' `
    -PreviousFrontendImage 'PREVIOUS_FRONTEND' -PreviousRetrievalModelImage 'PREVIOUS_RETRIEVAL'
""".replace("SNAPSHOT_SCRIPT", str(SCRIPT).replace("'", "''"))
        .replace("CANDIDATE_BACKEND", IMAGES["candidate_backend"])
        .replace("CANDIDATE_FRONTEND", IMAGES["candidate_frontend"])
        .replace("CANDIDATE_RETRIEVAL", IMAGES["candidate_retrieval"])
        .replace("PREVIOUS_BACKEND", IMAGES["previous_backend"])
        .replace("PREVIOUS_FRONTEND", IMAGES["previous_frontend"])
        .replace("PREVIOUS_RETRIEVAL", IMAGES["previous_retrieval"]),
        encoding="utf-8",
    )

    captured = subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-File", str(harness), str(snapshot), IMAGES["previous_backend"]],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=15,
    )
    assert captured.returncode == 0, captured.stderr
    assert "pre_window_runtime_unchanged" in captured.stdout
    assert json.loads(snapshot.read_text(encoding="utf-8"))["workspace_translation_enabled"] is True
    assert json.loads(snapshot.read_text(encoding="utf-8"))["webhook_read_enabled"] is True
    assert invoke(snapshot).stdout.strip() == "true"

    changed_after_capture = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(harness),
            str(tmp_path / "changed.json"),
            IMAGES["previous_backend"],
            "-ChangeAfterCapture",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=15,
    )
    assert changed_after_capture.returncode != 0
    assert "pre-window" in (changed_after_capture.stdout + changed_after_capture.stderr).lower()

    unsupported = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(harness),
            str(tmp_path / "unsupported.json"),
            IMAGES["previous_backend"],
            "-UnsupportedMode",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=15,
    )
    assert unsupported.returncode != 0
    assert not (tmp_path / "unsupported.json").exists()

    wrong_runtime = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(harness),
            str(tmp_path / "wrong.json"),
            IMAGES["candidate_backend"],
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=15,
    )
    assert wrong_runtime.returncode != 0
    assert not (tmp_path / "wrong.json").exists()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
def test_restore_rejects_non_g5_runtime_before_switch(tmp_path) -> None:
    snapshot = tmp_path / "restore-snapshot.json"
    snapshot.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "images": IMAGES,
                "manual_send_enabled": True,
                "webhook_read_enabled": True,
                "allowed_conversation_id": "123456789",
                "workspace_translation_enabled": True,
            }
        ),
        encoding="utf-8",
    )
    harness = tmp_path / "g5-current.ps1"
    harness.write_text(
        """
param([string]$SnapshotFile, [string]$RunningBackendImage, [string]$RunningLimit, [switch]$Stopped)
$previousMode = $RunningBackendImage -ceq 'PREVIOUS_BACKEND' -and $RunningLimit -ceq '10'
$llm = if ($previousMode) { 'false' } else { 'true' }
$sse = if ($previousMode) { 'false' } else { 'true' }
$embedding = if ($previousMode) { 'false' } else { 'true' }
$read = if ($previousMode) { 'true' } else { 'false' }
$write = if ($previousMode) { 'true' } else { 'false' }
$translation = if ($previousMode) { 'true' } else { 'false' }
$conversation = if ($previousMode) { '123456789' } else { '' }
$conversationEnv = if ($previousMode) { @("TIKTOK_MESSAGE_WRITE_ALLOWED_CONVERSATION_ID=$conversation") } else { @() }
function docker {
    $global:LASTEXITCODE = 0
    if ($args[0] -ceq 'ps') {
        if ($Stopped -and '-a' -cnotin $args -and '--all' -cnotin $args) { return @() }
        $service = [string](@($args | Where-Object { $_ -like 'label=com.docker.compose.service=*' })[0])
        switch ($service) {
            'label=com.docker.compose.service=backend' { return 'aaaaaaaaaaaa' }
            'label=com.docker.compose.service=frontend' { return 'bbbbbbbbbbbb' }
            'label=com.docker.compose.service=retrieval-model-service' { return 'cccccccccccc' }
        }
    }
    if ($args[0] -ceq 'inspect') {
        switch ($args[-1]) {
            'aaaaaaaaaaaa' { return (@{ Image = $RunningBackendImage; Env = @(
                'APP_ENV=staging', "LLM_ENABLED=$llm", "SSE_LOAD_TEST_ENABLED=$sse",
                "EMBEDDING_ENABLED=$embedding", "CHAT_QUERY_LIMIT=$RunningLimit",
                "REAL_TIKTOK_READ_ENABLED=$read", "REAL_TIKTOK_WEBHOOK_ENABLED=$read",
                "REAL_TIKTOK_MESSAGE_WRITE_ENABLED=$write",
                'REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED=false',
                "WORKSPACE_MESSAGE_TRANSLATION_ENABLED=$translation",
                'ALLOW_MOCK_PLATFORM_ADAPTERS=false', 'LLM_LIVE_EVAL=false',
                'AI_TRANSLATION_ENABLED=false', 'AI_MARKETING_ENABLED=false',
                'AUTO_REPLY_ENABLED=false'
            ) + $conversationEnv } | ConvertTo-Json -Compress) }
            'bbbbbbbbbbbb' { return (@{ Image = 'CANDIDATE_FRONTEND'; Env = @() } | ConvertTo-Json -Compress) }
            'cccccccccccc' { return (@{ Image = 'CANDIDATE_RETRIEVAL'; Env = @() } | ConvertTo-Json -Compress) }
        }
    }
    throw 'unexpected docker call'
}
& 'SNAPSHOT_SCRIPT' -Mode VerifyRecoverableCurrent -SnapshotFile $SnapshotFile `
    -CandidateBackendImage 'CANDIDATE_BACKEND' -FrontendImage 'CANDIDATE_FRONTEND' `
    -RetrievalModelImage 'CANDIDATE_RETRIEVAL' -PreviousBackendImage 'PREVIOUS_BACKEND' `
    -PreviousFrontendImage 'PREVIOUS_FRONTEND' -PreviousRetrievalModelImage 'PREVIOUS_RETRIEVAL'
""".replace("SNAPSHOT_SCRIPT", str(SCRIPT).replace("'", "''"))
        .replace("CANDIDATE_BACKEND", IMAGES["candidate_backend"])
        .replace("CANDIDATE_FRONTEND", IMAGES["candidate_frontend"])
        .replace("CANDIDATE_RETRIEVAL", IMAGES["candidate_retrieval"])
        .replace("PREVIOUS_BACKEND", IMAGES["previous_backend"])
        .replace("PREVIOUS_FRONTEND", IMAGES["previous_frontend"])
        .replace("PREVIOUS_RETRIEVAL", IMAGES["previous_retrieval"]),
        encoding="utf-8",
    )

    def check(image: str, limit: str, *, stopped: bool = False):
        return subprocess.run(
            [
                POWERSHELL,
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(harness),
                str(snapshot),
                image,
                limit,
                *(["-Stopped"] if stopped else []),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=15,
        )

    assert check(IMAGES["candidate_backend"], "60").returncode == 0
    assert check(IMAGES["candidate_backend"], "60", stopped=True).returncode == 0
    assert check(IMAGES["previous_backend"], "10").returncode == 0
    assert check(IMAGES["previous_backend"], "60").returncode != 0
    assert check(IMAGES["candidate_backend"], "10").returncode != 0
