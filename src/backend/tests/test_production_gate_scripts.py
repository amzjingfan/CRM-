"""staging 生产门禁和回滚脚本的失败关闭契约测试。"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml


def repository_root(start: Path) -> Path:
    """从普通 checkout 或 linked worktree 中定位 Git 仓库根。"""
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    raise AssertionError("Git repository root was not found")


REPOSITORY_ROOT = repository_root(Path(__file__).resolve())
SOURCE_ROOT = REPOSITORY_ROOT / "src"
PREFLIGHT_SCRIPT = SOURCE_ROOT / "scripts" / "Test-StagingProductionGates.ps1"
ROLLBACK_SCRIPT = SOURCE_ROOT / "scripts" / "Invoke-StagingRollbackDrill.ps1"
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")

BACKEND_IMAGE = "ghcr.io/cp11-gh/crm-backend@sha256:" + "a" * 64
FRONTEND_IMAGE = "ghcr.io/cp11-gh/crm-frontend@sha256:" + "b" * 64
PREVIOUS_BACKEND_IMAGE = "ghcr.io/cp11-gh/crm-backend@sha256:" + "c" * 64
PREVIOUS_FRONTEND_IMAGE = "ghcr.io/cp11-gh/crm-frontend@sha256:" + "d" * 64
RETRIEVAL_MODEL_IMAGE = "ghcr.io/cp11-gh/crm-retrieval-model-service@sha256:" + "e" * 64
PREVIOUS_RETRIEVAL_MODEL_IMAGE = "ghcr.io/cp11-gh/crm-retrieval-model-service@sha256:" + "f" * 64
SECRET_SENTINEL = "must-not-appear-in-command-output-or-evidence"
ROOTLESS_DOCKER_HOST = "unix:///run/user/1004/docker.sock"
REQUIRED_MODEL_FILES = (
    "bge-m3/config.json",
    "bge-m3/pytorch_model.bin",
    "bge-m3/tokenizer.json",
    "bge-reranker-large/config.json",
    "bge-reranker-large/model.safetensors",
    "bge-reranker-large/tokenizer.json",
)
ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
POWERSHELL_GUTTER_PATTERN = re.compile(r"\r?\n\s*\|\s*")
WHITESPACE_PATTERN = re.compile(r"\s+")


def test_staging_workflow_passes_runner_socket_and_keeps_minimum_permissions() -> None:
    """工作流必须把调用者 UID 交给脚本的 1004 门禁，且 GHCR 不依赖长期 PAT。"""
    workflow = yaml.safe_load((REPOSITORY_ROOT / ".github/workflows/staging-gates.yml").read_text("utf-8"))
    assert workflow["permissions"] == {"contents": "read", "packages": "read"}
    steps = workflow["jobs"]["staging"]["steps"]
    login = next(step for step in steps if step.get("uses", "").startswith("docker/login-action@"))
    assert login["with"]["password"] == "${{ secrets.GITHUB_TOKEN }}"
    gate = next(step["run"] for step in steps if step["name"] == "Run the selected staging gate")
    assert "$runnerUid = (& id -u).Trim()" in gate
    assert "$LASTEXITCODE -ne 0" in gate
    assert "$runnerUid -notmatch '^[1-9][0-9]*$'" in gate
    assert '$dockerHost = "unix:///run/user/$runnerUid/docker.sock"' in gate
    assert '$common["DockerHost"] = $dockerHost' in gate
    assert gate.index("$runnerUid =") < gate.index("$common =") < gate.index("switch ($env:OPERATION)")


@pytest.mark.parametrize(
    "base_url,accepted",
    [
        ("https://staging.hophorsefit.com", True),
        ("", False),
        ("https://www.hophorsefit.com", False),
        ("https://staging.hophorsefit.com/", False),
        ("https://staging.hophorsefit.com.evil.invalid", False),
        ("https://staging.hophorsefit.com/v1", False),
        ("https://STAGING.hophorsefit.com", False),
    ],
)
def test_workflow_rejects_nonexact_base_url_before_mutation(tmp_path: Path, base_url: str, accepted: bool) -> None:
    """执行真实工作流预检片段，防止生产地址、前缀匹配或路径误配置被放行。"""
    workflow = yaml.safe_load((REPOSITORY_ROOT / ".github/workflows/staging-gates.yml").read_text("utf-8"))
    steps = workflow["jobs"]["staging"]["steps"]
    guards = [step for step in steps if step["name"] == "Validate staging target"]
    assert len(guards) == 1, "exact staging URL guard must precede credential or deployment steps"
    guard = guards[0]
    login_index = next(index for index, step in enumerate(steps) if "GHCR" in step["name"])
    assert steps.index(guard) < login_index
    script = tmp_path / "workflow-target-guard.ps1"
    script.write_text(guard["run"], encoding="utf-8")
    environment = os.environ.copy()
    environment["CRM_STAGING_BASE_URL"] = base_url
    result = run_powershell(script, environment=environment)
    assert (result.returncode == 0) is accepted


def run_powershell(
    script: Path,
    *arguments: str,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """使用当前平台可用的 PowerShell 执行脚本并捕获低敏输出。"""
    assert POWERSHELL is not None, "PowerShell is required for production gate tests"
    assert script.exists(), f"missing production gate script: {script}"
    return subprocess.run(
        [POWERSHELL, "-NoLogo", "-NoProfile", "-File", str(script), *arguments],
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
        text=True,
        timeout=30,
        env=environment,
    )


def run_powershell_with_context_probe(
    script: Path,
    tmp_path: Path,
    *arguments: str,
    environment: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    """在同一 PowerShell 进程中调用脚本并输出恢复后的 Docker context。"""
    assert POWERSHELL is not None, "PowerShell is required for production gate tests"
    wrapper_script = tmp_path / "run-gate-with-context-probe.ps1"
    wrapper_script.write_text(
        """$targetScript = $args[0]
$targetArguments = @()
if ($args.Count -gt 1) {
    $targetArguments = $args[1..($args.Count - 1)]
}
$exitCode = 0
try {
    & $targetScript @targetArguments
}
catch {
    Write-Error $_
    $exitCode = 1
}
if ($LASTEXITCODE -ne 0) {
    $exitCode = $LASTEXITCODE
}
Write-Output "__DOCKER_CONTEXT_AFTER=$([Environment]::GetEnvironmentVariable('DOCKER_CONTEXT', 'Process'))"
exit $exitCode
""",
        encoding="utf-8",
    )
    return subprocess.run(
        [POWERSHELL, "-NoLogo", "-NoProfile", "-File", str(wrapper_script), str(script), *arguments],
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
        text=True,
        timeout=30,
        env=environment,
    )


def normalized_process_output(result: subprocess.CompletedProcess[str]) -> str:
    """归一化 PowerShell 7 在非 Windows 平台渲染的样式码和换行栏。"""
    output = ANSI_ESCAPE_PATTERN.sub("", result.stdout + result.stderr)
    output = POWERSHELL_GUTTER_PATTERN.sub(" ", output)
    return WHITESPACE_PATTERN.sub(" ", output).strip().lower()


def test_normalized_process_output_removes_ansi_and_line_gutters() -> None:
    """Ubuntu PowerShell 的样式码和自动换行栏不得拆断门禁错误语义。"""
    result = subprocess.CompletedProcess(
        args=["pwsh"],
        returncode=1,
        stdout="",
        stderr="\x1b[31;1mreparse\x1b[0m\n | \x1b[31;1mpoint.\x1b[0m",
    )

    assert normalized_process_output(result) == "reparse point."


@pytest.fixture
def staging_env_file(tmp_path: Path) -> Path:
    """创建只含测试值的仓库外环境文件样本，不使用开发机真实配置。"""
    model_asset_dir = tmp_path / "model-assets"
    (model_asset_dir / "bge-m3").mkdir(parents=True)
    (model_asset_dir / "bge-reranker-large").mkdir()
    for relative_path in REQUIRED_MODEL_FILES:
        (model_asset_dir / relative_path).write_bytes(f"test:{relative_path}".encode())
    env_file = tmp_path / "crm-staging.env"
    env_file.write_text(
        "\n".join(
            [
                "DATABASE_URL=postgresql+asyncpg://crm:test@postgres:5432/crm",
                "REDIS_URL=redis://redis:6379/0",
                "MINIO_ENDPOINT=minio:9000",
                "MINIO_ACCESS_KEY=test-access",
                f"MINIO_SECRET_KEY={SECRET_SENTINEL}",
                "JWT_SECRET_KEY=test-jwt-key-with-at-least-32-characters",
                "CORS_ORIGINS=https://staging.hophorsefit.com",
                "PUBLIC_BASE_URL=https://staging.hophorsefit.com",
                "PUBLIC_API_BASE_URL=https://staging.hophorsefit.com/v1",
                "TIKTOK_EGRESS_IP=203.0.113.10",
                "TIKTOK_OAUTH_REDIRECT_URI=https://staging.hophorsefit.com/v1/integrations/tiktok/oauth/callback",
                "POSTGRES_DB=crm",
                "POSTGRES_USER=crm",
                "POSTGRES_PASSWORD=test-postgres-password",
                "TLS_CERT_DIR=/secure/test-certs",
                f"RETRIEVAL_MODEL_ASSET_DIR={model_asset_dir}",
                f"RETRIEVAL_MODEL_SERVICE_IMAGE={RETRIEVAL_MODEL_IMAGE}",
                "POSTGRES_IMAGE=pgvector/pgvector:0.8.0-pg16@sha256:" + "1" * 64,
                "REDIS_IMAGE=redis:7.4.2-alpine@sha256:" + "2" * 64,
                "MINIO_IMAGE=minio/minio:RELEASE.2025-04-22T22-12-26Z@sha256:" + "3" * 64,
                "NGINX_IMAGE=nginx:1.27.5-alpine@sha256:" + "4" * 64,
                "REAL_TIKTOK_READ_ENABLED=false",
                "REAL_TIKTOK_WEBHOOK_ENABLED=false",
                "REAL_TIKTOK_MESSAGE_WRITE_ENABLED=false",
                "REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED=false",
                "LLM_ENABLED=false",
                "LLM_LIVE_EVAL=false",
                "AI_TRANSLATION_ENABLED=false",
                "AI_MARKETING_ENABLED=false",
                "AUTO_REPLY_ENABLED=false",
                "ALLOW_MOCK_PLATFORM_ADAPTERS=false",
            ]
        ),
        encoding="utf-8",
    )
    return env_file


def replace_environment_value(env_file: Path, name: str, value: str | None) -> None:
    """替换或删除测试环境变量，不读取开发机真实配置。"""
    lines = env_file.read_text(encoding="utf-8").splitlines()
    replacement = f"{name}={value}" if value is not None else None
    updated = [replacement if line.startswith(f"{name}=") else line for line in lines]
    if replacement is None:
        updated = [line for line in updated if line is not None]
    env_file.write_text("\n".join(updated), encoding="utf-8")


def validation_image_arguments(script: Path) -> tuple[str, ...]:
    """返回预检或回滚脚本共用的不可变镜像参数。"""
    if script == PREFLIGHT_SCRIPT:
        return (
            "-BackendImage",
            BACKEND_IMAGE,
            "-FrontendImage",
            FRONTEND_IMAGE,
            "-RetrievalModelImage",
            RETRIEVAL_MODEL_IMAGE,
        )
    return (
        "-CandidateBackendImage",
        BACKEND_IMAGE,
        "-CandidateFrontendImage",
        FRONTEND_IMAGE,
        "-CandidateRetrievalModelImage",
        RETRIEVAL_MODEL_IMAGE,
        "-PreviousBackendImage",
        PREVIOUS_BACKEND_IMAGE,
        "-PreviousFrontendImage",
        PREVIOUS_FRONTEND_IMAGE,
        "-PreviousRetrievalModelImage",
        PREVIOUS_RETRIEVAL_MODEL_IMAGE,
    )


def write_fake_compose_runtime(tmp_path: Path, model_asset_dir: Path) -> tuple[dict[str, str], Path]:
    """创建受控 Compose 替身，记录命令且让健康等待失败关闭。"""
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    command_log = tmp_path / "fake-compose-commands.jsonl"
    config_path = tmp_path / "fake-compose-config.json"
    application_environment = {
        "APP_ENV": "staging",
        "ALLOW_MOCK_PLATFORM_ADAPTERS": "false",
        "REAL_TIKTOK_READ_ENABLED": "false",
        "REAL_TIKTOK_WEBHOOK_ENABLED": "false",
        "REAL_TIKTOK_MESSAGE_WRITE_ENABLED": "false",
        "REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED": "false",
        "LLM_ENABLED": "false",
        "LLM_LIVE_EVAL": "false",
        "AI_TRANSLATION_ENABLED": "false",
        "AI_MARKETING_ENABLED": "false",
        "AUTO_REPLY_ENABLED": "false",
    }
    services = {
        "postgres": {"image": "pgvector/pgvector:0.8.0-pg16@sha256:" + "1" * 64},
        "redis": {"image": "redis:7.4.2-alpine@sha256:" + "2" * 64},
        "minio": {"image": "minio/minio:RELEASE.2025-04-22T22-12-26Z@sha256:" + "3" * 64},
        "backend": {"image": BACKEND_IMAGE, "environment": application_environment.copy()},
        "worker": {"image": BACKEND_IMAGE, "environment": application_environment.copy()},
        "jobs": {"image": BACKEND_IMAGE, "environment": application_environment.copy()},
        "agent-worker": {"image": BACKEND_IMAGE, "environment": application_environment.copy()},
        "retrieval-model-service": {
            "image": RETRIEVAL_MODEL_IMAGE,
            "volumes": [
                {
                    "type": "bind",
                    "source": str(model_asset_dir.absolute()),
                    "target": "/models",
                    "read_only": True,
                }
            ],
            "environment": {"RETRIEVAL_MODEL_VERIFY_HASHES": "true"},
        },
        "frontend": {"image": FRONTEND_IMAGE},
        "proxy": {
            "image": "nginx:1.27.5-alpine@sha256:" + "4" * 64,
            "ports": [
                {"host_ip": "127.0.0.1", "published": "10080", "target": "80"},
                {"host_ip": "127.0.0.1", "published": "10443", "target": "443"},
            ],
        },
    }
    config_path.write_text(json.dumps({"services": services}), encoding="utf-8")
    fake_runtime = tmp_path / "fake_docker.py"
    fake_runtime.write_text(
        """import json
import os
import sys
from pathlib import Path

arguments = sys.argv[1:]
with Path(os.environ["FAKE_DOCKER_LOG"]).open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(arguments) + "\\n")
with Path(os.environ["FAKE_DOCKER_CONTEXT_LOG"]).open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(os.environ.get("DOCKER_CONTEXT")) + "\\n")
if "config" in arguments:
    print(Path(os.environ["FAKE_DOCKER_CONFIG"]).read_text(encoding="utf-8"))
    sys.exit(int(os.environ.get("FAKE_DOCKER_CONFIG_EXIT_CODE", "0")))
if "up" in arguments and "--wait" in arguments:
    sys.exit(42)
sys.exit(0)
""",
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment["FAKE_DOCKER_PYTHON"] = sys.executable
    environment["FAKE_DOCKER_SCRIPT"] = str(fake_runtime)
    if os.name == "nt":
        wrapper = '@echo off\r\n"%FAKE_DOCKER_PYTHON%" "%FAKE_DOCKER_SCRIPT%" %*\r\n'
        (fake_bin / "docker.cmd").write_text(wrapper, encoding="utf-8")
    else:
        wrapper_path = fake_bin / "docker"
        wrapper_path.write_text(
            '#!/bin/sh\nexec "$FAKE_DOCKER_PYTHON" "$FAKE_DOCKER_SCRIPT" "$@"\n',
            encoding="utf-8",
        )
        wrapper_path.chmod(0o755)
    environment["PATH"] = str(fake_bin) + os.pathsep + environment.get("PATH", "")
    environment["FAKE_DOCKER_LOG"] = str(command_log)
    environment["FAKE_DOCKER_CONTEXT_LOG"] = str(tmp_path / "fake-docker-context.jsonl")
    environment["FAKE_DOCKER_CONFIG"] = str(config_path)
    return environment, command_log


def create_directory_link(link_path: Path, target_path: Path) -> None:
    """创建目录符号链接；Windows 无权限时使用无需管理员权限的 Junction。"""
    try:
        link_path.symlink_to(target_path, target_is_directory=True)
        return
    except (NotImplementedError, OSError):
        if os.name != "nt":
            pytest.skip("directory symlinks are unavailable on this runner")
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link_path), str(target_path)],
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        pytest.skip("directory junctions are unavailable on this Windows runner")


def assert_compose_invocations_use_fixed_staging_target(command_log: Path) -> None:
    """校验真正交给 CLI 的每个操作参数，捕获项目名、profile 或任一覆盖层丢失。"""
    commands = [json.loads(line) for line in command_log.read_text(encoding="utf-8").splitlines()]
    # CLI 探测 compose version 不接收项目配置；其余 config/pull/up 均必须隔离。
    operations = [arguments for arguments in commands if arguments[:2] != ["compose", "version"]]
    assert operations, "gate must reach a real Compose operation"
    for arguments in operations:
        assert arguments[0] == "compose"
        assert arguments.count("--project-name") == 1
        assert arguments[arguments.index("--project-name") + 1] == "crm-staging"
        assert arguments.count("--profile") == 1
        assert arguments[arguments.index("--profile") + 1] == "ai"
        compose_files = [Path(arguments[index + 1]) for index, value in enumerate(arguments) if value == "-f"]
        assert compose_files == [
            SOURCE_ROOT / "compose" / "docker-compose.yml",
            SOURCE_ROOT / "compose" / "docker-compose.prod.yml",
            SOURCE_ROOT / "compose" / "docker-compose.rootless-staging.yml",
        ]


def create_file_link(link_path: Path, target_path: Path) -> None:
    """创建文件符号链接；不支持时跳过该平台专用分支。"""
    try:
        link_path.symlink_to(target_path)
    except (NotImplementedError, OSError):
        pytest.skip("file symlinks are unavailable on this runner")


def test_preflight_rejects_production_environment(tmp_path: Path) -> None:
    """本任务的运维脚本不得被误用于 production。"""
    result = run_powershell(
        PREFLIGHT_SCRIPT,
        "-Environment",
        "production",
        "-EnvFile",
        str(tmp_path / "missing.env"),
        "-BackendImage",
        BACKEND_IMAGE,
        "-FrontendImage",
        FRONTEND_IMAGE,
        "-RetrievalModelImage",
        RETRIEVAL_MODEL_IMAGE,
        "-BaseUrl",
        "https://production.example.com",
        "-EvidenceFile",
        str(tmp_path / "evidence.json"),
        "-ConfirmTarget",
        "production",
        "-DockerHost",
        ROOTLESS_DOCKER_HOST,
        "-ValidateOnly",
    )

    assert result.returncode != 0
    assert "staging" in (result.stdout + result.stderr).lower()


@pytest.mark.parametrize("script", [PREFLIGHT_SCRIPT, ROLLBACK_SCRIPT])
@pytest.mark.parametrize(
    "docker_host",
    ["tcp://127.0.0.1:2375", "unix:///var/run/docker.sock", "unix:///run/user/1005/docker.sock", ""],
)
def test_gate_scripts_reject_non_rootless_docker_hosts(
    script: Path,
    docker_host: str,
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """门禁只允许 crmdeploy 的固定 Rootless Docker socket。"""
    result = run_powershell(
        script,
        "-Environment",
        "staging",
        "-EnvFile",
        str(staging_env_file),
        *validation_image_arguments(script),
        "-BaseUrl",
        "https://staging.hophorsefit.com",
        "-EvidenceFile",
        str(tmp_path / "evidence.json"),
        "-ConfirmTarget",
        "staging",
        "-DockerHost",
        docker_host,
        "-ValidateOnly",
    )

    assert result.returncode != 0
    assert "rootless docker host" in normalized_process_output(result)


@pytest.mark.parametrize("script", [PREFLIGHT_SCRIPT, ROLLBACK_SCRIPT])
def test_gate_scripts_fix_project_and_rootless_overlay_before_compose_operations(script: Path) -> None:
    """config、pull、up 必须共享固定项目名和 Rootless staging 覆盖层。"""
    source = script.read_text(encoding="utf-8-sig")

    assert "--project-name" in source
    assert "crm-staging" in source
    assert "docker-compose.rootless-staging.yml" in source
    compose_path = source[source.index("$rootlessOverlay") :]
    for operation in ("Get-ProductionComposeConfig", '"pull"', '"up"'):
        assert compose_path.index("docker-compose.rootless-staging.yml") < compose_path.index(operation)


@pytest.mark.parametrize("script", [PREFLIGHT_SCRIPT, ROLLBACK_SCRIPT])
@pytest.mark.parametrize(
    ("path", "expect_success"),
    [("validate_only", True), ("whatif", True), ("config_failure", False)],
)
def test_gate_scripts_clear_and_restore_inherited_docker_context(
    script: Path,
    path: str,
    expect_success: bool,
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """Docker context 必须在所有门禁路径中对 CLI 清空，且在调用进程中恢复。"""
    model_asset_dir = Path(
        next(
            line.split("=", 1)[1]
            for line in staging_env_file.read_text(encoding="utf-8").splitlines()
            if line.startswith("RETRIEVAL_MODEL_ASSET_DIR=")
        )
    )
    environment, command_log = write_fake_compose_runtime(tmp_path, model_asset_dir)
    inherited_context = "inherited-system-docker-context"
    environment["DOCKER_CONTEXT"] = inherited_context
    mode_arguments: tuple[str, ...] = ("-ValidateOnly",)
    if path == "whatif":
        mode_arguments = ("-Deploy", "-WhatIf") if script == PREFLIGHT_SCRIPT else ("-Execute", "-WhatIf")
    elif path == "config_failure":
        environment["FAKE_DOCKER_CONFIG_EXIT_CODE"] = "41"

    result = run_powershell_with_context_probe(
        script,
        tmp_path,
        "-Environment",
        "staging",
        "-EnvFile",
        str(staging_env_file),
        *validation_image_arguments(script),
        "-BaseUrl",
        "https://staging.hophorsefit.com",
        "-EvidenceFile",
        str(tmp_path / "evidence.json"),
        "-ConfirmTarget",
        "staging",
        "-DockerHost",
        ROOTLESS_DOCKER_HOST,
        *mode_arguments,
        environment=environment,
    )

    assert (result.returncode == 0) is expect_success, result.stdout + result.stderr
    assert f"__DOCKER_CONTEXT_AFTER={inherited_context}" in result.stdout
    context_values = [
        json.loads(line) for line in (tmp_path / "fake-docker-context.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert context_values
    assert context_values == [""] * len(context_values)
    assert_compose_invocations_use_fixed_staging_target(command_log)


def test_preflight_rejects_floating_application_image(
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """候选部署必须拒绝 latest 或普通版本标签。"""
    result = run_powershell(
        PREFLIGHT_SCRIPT,
        "-Environment",
        "staging",
        "-EnvFile",
        str(staging_env_file),
        "-BackendImage",
        "ghcr.io/cp11-gh/crm-backend:latest",
        "-FrontendImage",
        FRONTEND_IMAGE,
        "-RetrievalModelImage",
        RETRIEVAL_MODEL_IMAGE,
        "-BaseUrl",
        "https://staging.example.com",
        "-EvidenceFile",
        str(tmp_path / "evidence.json"),
        "-ConfirmTarget",
        "staging",
        "-DockerHost",
        ROOTLESS_DOCKER_HOST,
        "-ValidateOnly",
    )

    assert result.returncode != 0
    assert "digest" in (result.stdout + result.stderr).lower()


def test_preflight_rejects_credential_bearing_image_reference(
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """镜像引用不得借任意前缀把凭据或控制内容写入低敏证据。"""
    marker = "credential-must-not-be-recorded"
    malicious_image = f"https://user:{marker}@ghcr.io/cp11-gh/crm-backend@sha256:" + "a" * 64
    evidence_file = tmp_path / "evidence.json"
    result = run_powershell(
        PREFLIGHT_SCRIPT,
        "-Environment",
        "staging",
        "-EnvFile",
        str(staging_env_file),
        "-BackendImage",
        malicious_image,
        "-FrontendImage",
        FRONTEND_IMAGE,
        "-RetrievalModelImage",
        RETRIEVAL_MODEL_IMAGE,
        "-BaseUrl",
        "https://staging.example.com",
        "-EvidenceFile",
        str(evidence_file),
        "-ConfirmTarget",
        "staging",
        "-DockerHost",
        ROOTLESS_DOCKER_HOST,
        "-ValidateOnly",
    )

    assert result.returncode != 0
    assert marker not in (result.stdout + result.stderr)
    assert not evidence_file.exists()


def test_validate_only_writes_redacted_preflight_evidence(
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """静态预检证据只能包含变量名和摘要，不能回显环境值。"""
    evidence_file = tmp_path / "preflight-evidence.json"
    model_asset_dir = Path(
        next(
            line.split("=", 1)[1]
            for line in staging_env_file.read_text(encoding="utf-8").splitlines()
            if line.startswith("RETRIEVAL_MODEL_ASSET_DIR=")
        )
    )
    environment, _ = write_fake_compose_runtime(tmp_path, model_asset_dir)
    result = run_powershell(
        PREFLIGHT_SCRIPT,
        "-Environment",
        "staging",
        "-EnvFile",
        str(staging_env_file),
        "-BackendImage",
        BACKEND_IMAGE,
        "-FrontendImage",
        FRONTEND_IMAGE,
        "-RetrievalModelImage",
        RETRIEVAL_MODEL_IMAGE,
        "-BaseUrl",
        "https://staging.example.com",
        "-EvidenceFile",
        str(evidence_file),
        "-ConfirmTarget",
        "staging",
        "-DockerHost",
        ROOTLESS_DOCKER_HOST,
        "-ValidateOnly",
        environment=environment,
    )

    combined_output = result.stdout + result.stderr
    assert result.returncode == 0, combined_output
    assert SECRET_SENTINEL not in combined_output
    assert SECRET_SENTINEL not in evidence_file.read_text(encoding="utf-8")
    evidence = json.loads(evidence_file.read_text(encoding="utf-8-sig"))
    assert evidence["status"] == "validated"
    assert evidence["production_release"] is False
    assert evidence["external_model_assets_validated"] is True
    assert evidence["compose_project"] == "crm-staging"
    assert evidence["docker_transport"] == "rootless_unix_socket"
    assert len(evidence["rootless_overlay_sha256"]) == 64
    assert ROOTLESS_DOCKER_HOST not in evidence_file.read_text(encoding="utf-8-sig")


@pytest.mark.parametrize(
    ("configure", "expected_error"),
    [
        (
            lambda config: config["services"]["backend"]["environment"].update({"LLM_ENABLED": "true"}),
            "capability",
        ),
        (
            lambda config: config["services"]["proxy"]["ports"].append(
                {"host_ip": "0.0.0.0", "published": "10081", "target": "80"}
            ),
            "loopback ports",
        ),
    ],
)
def test_preflight_rejects_merged_compose_capability_or_port_regressions(
    configure: object,
    expected_error: str,
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """Rootless overlay 后的合并配置不得重新开启能力或暴露额外端口。"""
    model_asset_dir = Path(
        next(
            line.split("=", 1)[1]
            for line in staging_env_file.read_text(encoding="utf-8").splitlines()
            if line.startswith("RETRIEVAL_MODEL_ASSET_DIR=")
        )
    )
    environment, _ = write_fake_compose_runtime(tmp_path, model_asset_dir)
    config_path = tmp_path / "fake-compose-config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    configure(config)
    config_path.write_text(json.dumps(config), encoding="utf-8")

    result = run_powershell(
        PREFLIGHT_SCRIPT,
        "-Environment",
        "staging",
        "-EnvFile",
        str(staging_env_file),
        "-BackendImage",
        BACKEND_IMAGE,
        "-FrontendImage",
        FRONTEND_IMAGE,
        "-RetrievalModelImage",
        RETRIEVAL_MODEL_IMAGE,
        "-BaseUrl",
        "https://staging.hophorsefit.com",
        "-EvidenceFile",
        str(tmp_path / "evidence.json"),
        "-ConfirmTarget",
        "staging",
        "-DockerHost",
        ROOTLESS_DOCKER_HOST,
        "-ValidateOnly",
        environment=environment,
    )

    assert result.returncode != 0
    assert expected_error in normalized_process_output(result)


def test_preflight_rejects_missing_external_model_asset_directory(
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """staging 环境必须显式提供服务器仓库外模型目录。"""
    replace_environment_value(staging_env_file, "RETRIEVAL_MODEL_ASSET_DIR", None)

    result = run_powershell(
        PREFLIGHT_SCRIPT,
        "-Environment",
        "staging",
        "-EnvFile",
        str(staging_env_file),
        "-BackendImage",
        BACKEND_IMAGE,
        "-FrontendImage",
        FRONTEND_IMAGE,
        "-RetrievalModelImage",
        RETRIEVAL_MODEL_IMAGE,
        "-BaseUrl",
        "https://staging.example.com",
        "-EvidenceFile",
        str(tmp_path / "evidence.json"),
        "-ConfirmTarget",
        "staging",
        "-DockerHost",
        ROOTLESS_DOCKER_HOST,
        "-ValidateOnly",
    )

    assert result.returncode != 0
    assert "RETRIEVAL_MODEL_ASSET_DIR" in (result.stdout + result.stderr)


def test_preflight_rejects_relative_model_asset_directory(
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """模型目录必须是服务器绝对路径，不能随 checkout 位置漂移。"""
    replace_environment_value(staging_env_file, "RETRIEVAL_MODEL_ASSET_DIR", "./deploy/models")

    result = run_powershell(
        PREFLIGHT_SCRIPT,
        "-Environment",
        "staging",
        "-EnvFile",
        str(staging_env_file),
        "-BackendImage",
        BACKEND_IMAGE,
        "-FrontendImage",
        FRONTEND_IMAGE,
        "-RetrievalModelImage",
        RETRIEVAL_MODEL_IMAGE,
        "-BaseUrl",
        "https://staging.example.com",
        "-EvidenceFile",
        str(tmp_path / "evidence.json"),
        "-ConfirmTarget",
        "staging",
        "-DockerHost",
        ROOTLESS_DOCKER_HOST,
        "-ValidateOnly",
    )

    assert result.returncode != 0
    assert "absolute" in (result.stdout + result.stderr).lower()


def test_preflight_rejects_model_asset_directory_inside_checkout(
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """生产权重不得回退到 Git checkout 内的开发模型目录。"""
    replace_environment_value(
        staging_env_file,
        "RETRIEVAL_MODEL_ASSET_DIR",
        str(SOURCE_ROOT / "deploy" / "models"),
    )

    result = run_powershell(
        PREFLIGHT_SCRIPT,
        "-Environment",
        "staging",
        "-EnvFile",
        str(staging_env_file),
        "-BackendImage",
        BACKEND_IMAGE,
        "-FrontendImage",
        FRONTEND_IMAGE,
        "-RetrievalModelImage",
        RETRIEVAL_MODEL_IMAGE,
        "-BaseUrl",
        "https://staging.example.com",
        "-EvidenceFile",
        str(tmp_path / "evidence.json"),
        "-ConfirmTarget",
        "staging",
        "-DockerHost",
        ROOTLESS_DOCKER_HOST,
        "-ValidateOnly",
    )

    assert result.returncode != 0
    assert "outside" in (result.stdout + result.stderr).lower()


@pytest.mark.parametrize("script", [PREFLIGHT_SCRIPT, ROLLBACK_SCRIPT])
def test_gate_scripts_reject_model_assets_anywhere_inside_git_checkout(
    script: Path,
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """嵌套产品目录不能让工作树根目录内的权重绕过仓库外门禁。"""
    replace_environment_value(staging_env_file, "RETRIEVAL_MODEL_ASSET_DIR", str(REPOSITORY_ROOT))
    evidence_file = tmp_path / f"{script.stem}-git-root-evidence.json"
    result = run_powershell(
        script,
        "-Environment",
        "staging",
        "-EnvFile",
        str(staging_env_file),
        *validation_image_arguments(script),
        "-BaseUrl",
        "https://staging.example.com",
        "-EvidenceFile",
        str(evidence_file),
        "-ConfirmTarget",
        "staging",
        "-DockerHost",
        ROOTLESS_DOCKER_HOST,
        "-ValidateOnly",
    )

    assert result.returncode != 0
    assert "outside" in (result.stdout + result.stderr).lower()
    assert not evidence_file.exists()


@pytest.mark.parametrize("script", [PREFLIGHT_SCRIPT, ROLLBACK_SCRIPT])
def test_gate_scripts_reject_external_link_pointing_into_git_checkout(
    script: Path,
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """仓库外符号链接或 Junction 不得把仓库内资产伪装成外部目录。"""
    with tempfile.TemporaryDirectory(prefix=".model-link-target-", dir=SOURCE_ROOT / "backend") as directory:
        internal_target = Path(directory)
        for relative_path in REQUIRED_MODEL_FILES:
            asset_path = internal_target / relative_path
            asset_path.parent.mkdir(parents=True, exist_ok=True)
            asset_path.write_bytes(f"test:{relative_path}".encode())
        link_path = tmp_path / "linked-model-assets"
        create_directory_link(link_path, internal_target)
        try:
            replace_environment_value(staging_env_file, "RETRIEVAL_MODEL_ASSET_DIR", str(link_path))
            environment, _ = write_fake_compose_runtime(tmp_path, link_path)
            evidence_file = tmp_path / f"{script.stem}-linked-assets.json"
            result = run_powershell(
                script,
                "-Environment",
                "staging",
                "-EnvFile",
                str(staging_env_file),
                *validation_image_arguments(script),
                "-BaseUrl",
                "https://staging.example.com",
                "-EvidenceFile",
                str(evidence_file),
                "-ConfirmTarget",
                "staging",
                "-DockerHost",
                ROOTLESS_DOCKER_HOST,
                "-ValidateOnly",
                environment=environment,
            )
        finally:
            if link_path.exists() or link_path.is_symlink():
                if os.name == "nt":
                    os.rmdir(link_path)
                else:
                    link_path.unlink()

    assert result.returncode != 0
    assert "reparse point" in normalized_process_output(result)
    assert not evidence_file.exists()


@pytest.mark.parametrize("script", [PREFLIGHT_SCRIPT, ROLLBACK_SCRIPT])
def test_gate_scripts_reject_linked_model_runtime_file(
    script: Path,
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """正常外部目录中的六个必需文件也不能是符号链接。"""
    model_asset_dir = Path(
        next(
            line.split("=", 1)[1]
            for line in staging_env_file.read_text(encoding="utf-8").splitlines()
            if line.startswith("RETRIEVAL_MODEL_ASSET_DIR=")
        )
    )
    linked_asset = model_asset_dir / "bge-m3" / "config.json"
    linked_asset.unlink()
    link_target = tmp_path / "linked-config-target.json"
    link_target.write_bytes(b"test:linked-config")
    create_file_link(linked_asset, link_target)
    environment, _ = write_fake_compose_runtime(tmp_path, model_asset_dir)
    evidence_file = tmp_path / f"{script.stem}-linked-file.json"
    result = run_powershell(
        script,
        "-Environment",
        "staging",
        "-EnvFile",
        str(staging_env_file),
        *validation_image_arguments(script),
        "-BaseUrl",
        "https://staging.example.com",
        "-EvidenceFile",
        str(evidence_file),
        "-ConfirmTarget",
        "staging",
        "-DockerHost",
        ROOTLESS_DOCKER_HOST,
        "-ValidateOnly",
        environment=environment,
    )

    assert result.returncode != 0
    assert "reparse point" in normalized_process_output(result)
    assert not evidence_file.exists()


@pytest.mark.parametrize("script", [PREFLIGHT_SCRIPT, ROLLBACK_SCRIPT])
@pytest.mark.parametrize("relative_path", REQUIRED_MODEL_FILES)
def test_gate_scripts_require_every_model_runtime_file(
    script: Path,
    relative_path: str,
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """两个门禁脚本必须与推理引擎保持相同的六文件启动契约。"""
    model_asset_dir = Path(
        next(
            line.split("=", 1)[1]
            for line in staging_env_file.read_text(encoding="utf-8").splitlines()
            if line.startswith("RETRIEVAL_MODEL_ASSET_DIR=")
        )
    )
    (model_asset_dir / relative_path).unlink()
    environment, _ = write_fake_compose_runtime(tmp_path, model_asset_dir)
    evidence_file = tmp_path / f"{script.stem}-{relative_path.replace('/', '-')}.json"
    result = run_powershell(
        script,
        "-Environment",
        "staging",
        "-EnvFile",
        str(staging_env_file),
        *validation_image_arguments(script),
        "-BaseUrl",
        "https://staging.example.com",
        "-EvidenceFile",
        str(evidence_file),
        "-ConfirmTarget",
        "staging",
        "-DockerHost",
        ROOTLESS_DOCKER_HOST,
        "-ValidateOnly",
        environment=environment,
    )

    assert result.returncode != 0, result.stdout + result.stderr
    assert "required model asset file" in (result.stdout + result.stderr).lower()
    assert not evidence_file.exists()


def test_preflight_rejects_external_model_directory_without_required_weights(
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """外部目录缺少任一固定权重时必须在 Compose 启动前失败。"""
    empty_model_dir = tmp_path / "empty-model-assets"
    empty_model_dir.mkdir()
    replace_environment_value(staging_env_file, "RETRIEVAL_MODEL_ASSET_DIR", str(empty_model_dir))

    result = run_powershell(
        PREFLIGHT_SCRIPT,
        "-Environment",
        "staging",
        "-EnvFile",
        str(staging_env_file),
        "-BackendImage",
        BACKEND_IMAGE,
        "-FrontendImage",
        FRONTEND_IMAGE,
        "-RetrievalModelImage",
        RETRIEVAL_MODEL_IMAGE,
        "-BaseUrl",
        "https://staging.example.com",
        "-EvidenceFile",
        str(tmp_path / "evidence.json"),
        "-ConfirmTarget",
        "staging",
        "-DockerHost",
        ROOTLESS_DOCKER_HOST,
        "-ValidateOnly",
    )

    assert result.returncode != 0
    assert "required model asset file" in (result.stdout + result.stderr).lower()


def test_preflight_rejects_floating_external_image(
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """仓库外环境文件不得把已固定的基础设施镜像降级为浮动标签。"""
    source = staging_env_file.read_text(encoding="utf-8")
    staging_env_file.write_text(
        source.replace(
            "NGINX_IMAGE=nginx:1.27.5-alpine@sha256:" + "4" * 64,
            "NGINX_IMAGE=nginx:latest",
        ),
        encoding="utf-8",
    )
    result = run_powershell(
        PREFLIGHT_SCRIPT,
        "-Environment",
        "staging",
        "-EnvFile",
        str(staging_env_file),
        "-BackendImage",
        BACKEND_IMAGE,
        "-FrontendImage",
        FRONTEND_IMAGE,
        "-RetrievalModelImage",
        RETRIEVAL_MODEL_IMAGE,
        "-BaseUrl",
        "https://staging.example.com",
        "-EvidenceFile",
        str(tmp_path / "evidence.json"),
        "-ConfirmTarget",
        "staging",
        "-DockerHost",
        ROOTLESS_DOCKER_HOST,
        "-ValidateOnly",
    )

    assert result.returncode != 0
    assert "digest" in (result.stdout + result.stderr).lower()


def test_preflight_live_path_forces_capabilities_off_before_deploy() -> None:
    """即使 runner 已有同名变量，候选部署也必须主动覆盖为 false。"""
    source = PREFLIGHT_SCRIPT.read_text(encoding="utf-8-sig")
    live_path = source[source.index("$savedEnvironment") :]

    assert "Set-DisabledCapabilities" in live_path
    assert live_path.index("Set-DisabledCapabilities") < live_path.index("$env:BACKEND_IMAGE = $BackendImage")


def test_preflight_deploys_the_validated_retrieval_model_image() -> None:
    """候选部署必须实际拉取并启动刚通过摘要校验的检索模型镜像。"""
    source = PREFLIGHT_SCRIPT.read_text(encoding="utf-8-sig")
    deploy_path = source[source.index('if (-not $PSCmdlet.ShouldProcess("staging"') :]

    assert deploy_path.count('"retrieval-model-service"') >= 2


def test_rollback_plan_disables_capabilities_before_switching_images(
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """回滚计划必须先紧急关闭真实能力，再切换历史镜像摘要。"""
    evidence_file = tmp_path / "rollback-evidence.json"
    model_asset_dir = Path(
        next(
            line.split("=", 1)[1]
            for line in staging_env_file.read_text(encoding="utf-8").splitlines()
            if line.startswith("RETRIEVAL_MODEL_ASSET_DIR=")
        )
    )
    environment, _ = write_fake_compose_runtime(tmp_path, model_asset_dir)
    result = run_powershell(
        ROLLBACK_SCRIPT,
        "-Environment",
        "staging",
        "-EnvFile",
        str(staging_env_file),
        "-CandidateBackendImage",
        BACKEND_IMAGE,
        "-CandidateFrontendImage",
        FRONTEND_IMAGE,
        "-CandidateRetrievalModelImage",
        RETRIEVAL_MODEL_IMAGE,
        "-PreviousBackendImage",
        PREVIOUS_BACKEND_IMAGE,
        "-PreviousFrontendImage",
        PREVIOUS_FRONTEND_IMAGE,
        "-PreviousRetrievalModelImage",
        PREVIOUS_RETRIEVAL_MODEL_IMAGE,
        "-BaseUrl",
        "https://staging.example.com",
        "-EvidenceFile",
        str(evidence_file),
        "-ConfirmTarget",
        "staging",
        "-DockerHost",
        ROOTLESS_DOCKER_HOST,
        "-ValidateOnly",
        environment=environment,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert SECRET_SENTINEL not in (result.stdout + result.stderr)
    evidence = json.loads(evidence_file.read_text(encoding="utf-8-sig"))
    assert evidence["planned_steps"] == [
        "disable_real_capabilities",
        "deploy_previous_image_digests",
        "verify_health",
    ]
    assert evidence["production_release"] is False


def test_rollback_rejects_floating_external_image(
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """回滚也必须在任何 Compose 调用前拒绝浮动外部镜像。"""
    source = staging_env_file.read_text(encoding="utf-8")
    staging_env_file.write_text(
        source.replace(
            "REDIS_IMAGE=redis:7.4.2-alpine@sha256:" + "2" * 64,
            "REDIS_IMAGE=redis:latest",
        ),
        encoding="utf-8",
    )
    result = run_powershell(
        ROLLBACK_SCRIPT,
        "-Environment",
        "staging",
        "-EnvFile",
        str(staging_env_file),
        "-CandidateBackendImage",
        BACKEND_IMAGE,
        "-CandidateFrontendImage",
        FRONTEND_IMAGE,
        "-CandidateRetrievalModelImage",
        RETRIEVAL_MODEL_IMAGE,
        "-PreviousBackendImage",
        PREVIOUS_BACKEND_IMAGE,
        "-PreviousFrontendImage",
        PREVIOUS_FRONTEND_IMAGE,
        "-PreviousRetrievalModelImage",
        PREVIOUS_RETRIEVAL_MODEL_IMAGE,
        "-BaseUrl",
        "https://staging.example.com",
        "-EvidenceFile",
        str(tmp_path / "rollback-evidence.json"),
        "-ConfirmTarget",
        "staging",
        "-DockerHost",
        ROOTLESS_DOCKER_HOST,
        "-ValidateOnly",
    )

    assert result.returncode != 0
    assert "digest" in (result.stdout + result.stderr).lower()


@pytest.mark.parametrize(
    ("script", "mode", "image_arguments"),
    [
        (
            PREFLIGHT_SCRIPT,
            "-Deploy",
            (
                "-BackendImage",
                BACKEND_IMAGE,
                "-FrontendImage",
                FRONTEND_IMAGE,
                "-RetrievalModelImage",
                RETRIEVAL_MODEL_IMAGE,
            ),
        ),
        (
            ROLLBACK_SCRIPT,
            "-Execute",
            (
                "-CandidateBackendImage",
                BACKEND_IMAGE,
                "-CandidateFrontendImage",
                FRONTEND_IMAGE,
                "-CandidateRetrievalModelImage",
                RETRIEVAL_MODEL_IMAGE,
                "-PreviousBackendImage",
                PREVIOUS_BACKEND_IMAGE,
                "-PreviousFrontendImage",
                PREVIOUS_FRONTEND_IMAGE,
                "-PreviousRetrievalModelImage",
                PREVIOUS_RETRIEVAL_MODEL_IMAGE,
            ),
        ),
    ],
)
def test_whatif_never_records_passed_evidence(
    script: Path,
    mode: str,
    image_arguments: tuple[str, ...],
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """WhatIf 未执行部署或回滚时只能记录 not_executed。"""
    evidence_file = tmp_path / f"{script.stem}-whatif.json"
    model_asset_dir = Path(
        next(
            line.split("=", 1)[1]
            for line in staging_env_file.read_text(encoding="utf-8").splitlines()
            if line.startswith("RETRIEVAL_MODEL_ASSET_DIR=")
        )
    )
    environment, _ = write_fake_compose_runtime(tmp_path, model_asset_dir)
    result = run_powershell(
        script,
        "-Environment",
        "staging",
        "-EnvFile",
        str(staging_env_file),
        *image_arguments,
        "-BaseUrl",
        "https://127.0.0.1:1",
        "-EvidenceFile",
        str(evidence_file),
        "-ConfirmTarget",
        "staging",
        "-DockerHost",
        ROOTLESS_DOCKER_HOST,
        mode,
        "-WhatIf",
        environment=environment,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    combined_output = result.stdout + result.stderr
    assert "not executed" in combined_output.lower()
    if evidence_file.exists():
        evidence = json.loads(evidence_file.read_text(encoding="utf-8-sig"))
        assert evidence["status"] == "not_executed"
        assert evidence["production_release"] is False


@pytest.mark.parametrize(
    ("script", "mode"),
    [(PREFLIGHT_SCRIPT, "-Deploy"), (ROLLBACK_SCRIPT, "-Execute")],
)
def test_live_gate_waits_for_compose_health_before_writing_passed_evidence(
    script: Path,
    mode: str,
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """Compose 健康等待失败时，部署和回滚都必须失败关闭且不能写 passed。"""
    model_asset_dir = Path(
        next(
            line.split("=", 1)[1]
            for line in staging_env_file.read_text(encoding="utf-8").splitlines()
            if line.startswith("RETRIEVAL_MODEL_ASSET_DIR=")
        )
    )
    environment, command_log = write_fake_compose_runtime(tmp_path, model_asset_dir)
    evidence_file = tmp_path / f"{script.stem}-unhealthy.json"
    result = run_powershell(
        script,
        "-Environment",
        "staging",
        "-EnvFile",
        str(staging_env_file),
        *validation_image_arguments(script),
        "-BaseUrl",
        "https://127.0.0.1:1",
        "-EvidenceFile",
        str(evidence_file),
        "-ConfirmTarget",
        "staging",
        "-DockerHost",
        ROOTLESS_DOCKER_HOST,
        mode,
        "-Confirm:$false",
        environment=environment,
    )

    assert command_log.exists(), result.stdout + result.stderr
    assert_compose_invocations_use_fixed_staging_target(command_log)
    commands = [json.loads(line) for line in command_log.read_text(encoding="utf-8").splitlines()]
    up_commands = [arguments for arguments in commands if "up" in arguments]
    assert result.returncode != 0
    assert up_commands
    assert all("--wait" in arguments for arguments in up_commands)
    assert all("--wait-timeout" in arguments for arguments in up_commands)
    assert all("600" in arguments for arguments in up_commands)
    if evidence_file.exists():
        assert json.loads(evidence_file.read_text(encoding="utf-8-sig"))["status"] != "passed"
