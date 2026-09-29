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
from _support import REPOSITORY_ROOT, SOURCE_ROOT

PREFLIGHT_SCRIPT = SOURCE_ROOT / "scripts" / "Test-StagingProductionGates.ps1"
ROLLBACK_SCRIPT = SOURCE_ROOT / "scripts" / "Invoke-StagingRollbackDrill.ps1"
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")

BACKEND_IMAGE = "ghcr.io/cp11-gh/crm-backend@sha256:" + "a" * 64
FRONTEND_IMAGE = "ghcr.io/cp11-gh/crm-frontend@sha256:" + "b" * 64
PREVIOUS_BACKEND_IMAGE = "ghcr.io/cp11-gh/crm-backend@sha256:" + "c" * 64
PREVIOUS_FRONTEND_IMAGE = "ghcr.io/cp11-gh/crm-frontend@sha256:" + "d" * 64
RETRIEVAL_MODEL_IMAGE = "ghcr.io/cp11-gh/crm-retrieval-model-service@sha256:" + "e" * 64
UNREVIEWED_RETRIEVAL_MODEL_IMAGE = "ghcr.io/cp11-gh/crm-retrieval-model-service@sha256:" + "9" * 64
PREVIOUS_RETRIEVAL_MODEL_IMAGE = "ghcr.io/cp11-gh/crm-retrieval-model-service@sha256:" + "f" * 64
SECRET_SENTINEL = "must-not-appear-in-command-output-or-evidence"
ROOTLESS_DOCKER_HOST = "unix:///run/user/1004/docker.sock"
TIKTOK_EGRESS_IP = "38.55.145.52"
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
    assert workflow["jobs"]["staging"]["timeout-minutes"] == 120
    steps = workflow["jobs"]["staging"]["steps"]
    assert not any(step.get("uses", "").startswith("docker/login-action@") for step in steps)
    login = next(step for step in steps if step["name"] == "Log in to GHCR for immutable image pulls")
    assert login["shell"] == "pwsh"
    assert login["env"] == {
        "DOCKER_CONFIG": "${{ runner.temp }}/crm-staging-docker-config",
        "GHCR_TOKEN": "${{ secrets.GITHUB_TOKEN }}",
        "GHCR_USERNAME": "${{ github.actor }}",
    }
    assert "docker login ghcr.io" in login["run"]
    assert "--password-stdin" in login["run"]
    assert "$env:GHCR_TOKEN |" in login["run"]
    gate_step = next(step for step in steps if step["name"] == "Run the selected staging gate")
    assert gate_step["env"]["DOCKER_CONFIG"] == "${{ runner.temp }}/crm-staging-docker-config"
    gate = gate_step["run"]
    assert "$runnerUid = (& id -u).Trim()" in gate
    assert "$LASTEXITCODE -ne 0" in gate
    assert "$runnerUid -notmatch '^[1-9][0-9]*$'" in gate
    assert '$dockerHost = "unix:///run/user/$runnerUid/docker.sock"' in gate
    assert '$common["DockerHost"] = $dockerHost' in gate
    assert gate.index("$runnerUid =") < gate.index("$common =") < gate.index("switch ($env:OPERATION)")
    logout = next(step for step in steps if step["name"] == "Log out from GHCR")
    assert logout["if"] == (
        "${{ always() && (steps.verify_dispatch_commit.outcome == 'success' || "
        "steps.verify_prefetch_source.outcome == 'success') }}"
    )
    assert logout["env"]["DOCKER_CONFIG"] == "${{ runner.temp }}/crm-staging-docker-config"
    assert "docker logout ghcr.io" in logout["run"]


@pytest.mark.parametrize(
    "base_url,accepted",
    [
        ("https://staging.overselfx.com", True),
        ("", False),
        ("https://www.overselfx.com", False),
        ("https://staging.overselfx.com/", False),
        ("https://staging.overselfx.com.evil.invalid", False),
        ("https://staging.overselfx.com/v1", False),
        ("https://STAGING.overselfx.com", False),
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
    egress_secret_dir = tmp_path / "tiktok-egress-secrets"
    egress_secret_dir.mkdir()
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
                "CORS_ORIGINS=https://staging.overselfx.com",
                "PUBLIC_BASE_URL=https://staging.overselfx.com",
                "PUBLIC_API_BASE_URL=https://staging.overselfx.com/v1",
                f"TIKTOK_EGRESS_IP={TIKTOK_EGRESS_IP}",
                f"TIKTOK_EGRESS_SECRET_DIR={egress_secret_dir}",
                "TIKTOK_OAUTH_REDIRECT_URI=https://staging.overselfx.com/v1/integrations/tiktok/oauth/callback",
                "POSTGRES_DB=crm",
                "POSTGRES_USER=crm",
                "POSTGRES_PASSWORD=test-postgres-password",
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
    tiktok_application_environment = {
        **application_environment,
        "TIKTOK_EGRESS_PROXY_URL": "socks5h://tiktok-egress:1080",
    }
    egress_secret_dir = tmp_path / "tiktok-egress-secrets"
    tiktok_service_contract = {
        "networks": {"default": None, "tiktok-egress": None},
        "depends_on": {"tiktok-egress": {"condition": "service_healthy"}},
    }
    services = {
        "postgres": {"image": "pgvector/pgvector:0.8.0-pg16@sha256:" + "1" * 64},
        "redis": {"image": "redis:7.4.2-alpine@sha256:" + "2" * 64},
        "minio": {"image": "minio/minio:RELEASE.2025-04-22T22-12-26Z@sha256:" + "3" * 64},
        "tiktok-egress": {
            "image": BACKEND_IMAGE,
            "user": "0:0",
            "read_only": True,
            "cap_drop": ["ALL"],
            "security_opt": ["no-new-privileges:true"],
            "volumes": [
                {
                    "type": "bind",
                    "source": str(egress_secret_dir.absolute()),
                    "target": "/run/secrets/tiktok-egress",
                    "read_only": True,
                }
            ],
            "networks": {"tiktok-egress": None},
        },
        "backend": {
            "image": BACKEND_IMAGE,
            "environment": tiktok_application_environment.copy(),
            **tiktok_service_contract,
        },
        "worker": {
            "image": BACKEND_IMAGE,
            "environment": tiktok_application_environment.copy(),
            **tiktok_service_contract,
        },
        "jobs": {
            "image": BACKEND_IMAGE,
            "environment": tiktok_application_environment.copy(),
            **tiktok_service_contract,
        },
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
            "ports": [{"host_ip": "127.0.0.1", "published": "18081", "target": "80"}],
            "volumes": [
                {
                    "type": "bind",
                    "source": str(SOURCE_ROOT / "deploy" / "nginx" / "nginx-tunnel.conf"),
                    "target": "/etc/nginx/nginx.conf",
                    "read_only": True,
                }
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
with Path(os.environ["FAKE_DOCKER_ENV_LOG"]).open("a", encoding="utf-8") as handle:
    handle.write(json.dumps({
        "arguments": arguments,
        "BACKEND_IMAGE": os.environ.get("BACKEND_IMAGE"),
        "TIKTOK_EGRESS_IMAGE": os.environ.get("TIKTOK_EGRESS_IMAGE"),
        "REAL_TIKTOK_READ_ENABLED": os.environ.get("REAL_TIKTOK_READ_ENABLED"),
        "REAL_TIKTOK_WEBHOOK_ENABLED": os.environ.get("REAL_TIKTOK_WEBHOOK_ENABLED"),
        "REAL_TIKTOK_MESSAGE_WRITE_ENABLED": os.environ.get("REAL_TIKTOK_MESSAGE_WRITE_ENABLED"),
        "REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED": os.environ.get("REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED"),
    }) + "\\n")
if "config" in arguments:
    if os.environ.get("TLS_CERT_DIR") != "/__crm_staging_tls_not_used__":
        print("staging compose must inject the non-mounted TLS interpolation sentinel", file=sys.stderr)
        sys.exit(43)
    print(Path(os.environ["FAKE_DOCKER_CONFIG"]).read_text(encoding="utf-8"))
    sys.exit(int(os.environ.get("FAKE_DOCKER_CONFIG_EXIT_CODE", "0")))
if "ps" in arguments and "-q" in arguments:
    if (
        os.environ.get("FAKE_DOCKER_PAUSED_RETRIEVAL") == "1"
        and "--status" in arguments
        and arguments[arguments.index("--status") + 1] == "running"
        and arguments[-1] == "retrieval-model-service"
    ):
        sys.exit(0)
    print("candidate-" + arguments[-1])
    sys.exit(0)
if arguments[:2] == ["inspect", "--format"]:
    service = arguments[-1].removeprefix("candidate-")
    references = {
        "backend": "ghcr.io/cp11-gh/crm-backend@sha256:" + "a" * 64,
        "frontend": "ghcr.io/cp11-gh/crm-frontend@sha256:" + "b" * 64,
        "retrieval-model-service": os.environ.get(
            "FAKE_DOCKER_LIVE_RETRIEVAL_IMAGE",
            "ghcr.io/cp11-gh/crm-retrieval-model-service@sha256:" + "e" * 64,
        ),
    }
    print(references[service])
    sys.exit(0)
if arguments[-6:] == ["run", "--rm", "--no-deps", "backend", "python", "scripts/verify_tiktok_egress.py"]:
    exit_code = int(os.environ.get("FAKE_DOCKER_VERIFY_EXIT_CODE", "0"))
    if exit_code:
        print("TikTok egress verification failed", file=sys.stderr)
        sys.exit(exit_code)
    print(json.dumps({
        "schema_version": 1,
        "status": "ok",
        "configured_ip": "38.55.145.52",
        "observed_ip": "38.55.145.52",
    }))
    sys.exit(0)
if "up" in arguments and "--wait" in arguments:
    configured_failure = os.environ.get("FAKE_DOCKER_FAIL_UP_NUMBER")
    if configured_failure is None:
        sys.exit(42)
    commands = [
        json.loads(line)
        for line in Path(os.environ["FAKE_DOCKER_LOG"]).read_text(encoding="utf-8").splitlines()
    ]
    up_number = sum("up" in command and "--wait" in command for command in commands)
    if up_number == int(configured_failure):
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
    environment["FAKE_DOCKER_ENV_LOG"] = str(tmp_path / "fake-docker-environment.jsonl")
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
    # 容器镜像只允许通过只读 inspect 核对；Compose 的 config/ps/pull/up 均必须隔离。
    direct_operations = [arguments for arguments in commands if arguments[0] != "compose"]
    assert all(arguments[:2] == ["inspect", "--format"] for arguments in direct_operations)
    operations = [
        arguments for arguments in commands if arguments[0] == "compose" and arguments[:2] != ["compose", "version"]
    ]
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
            SOURCE_ROOT / "compose" / "docker-compose.tiktok-egress.yml",
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
        "https://staging.overselfx.com",
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
    """config、pull、up 必须共享固定项目名和完整 staging 覆盖层顺序。"""
    source = script.read_text(encoding="utf-8-sig")

    assert "--project-name" in source
    assert "crm-staging" in source
    assert "docker-compose.tiktok-egress.yml" in source
    assert "docker-compose.rootless-staging.yml" in source
    compose_path = source[source.index("$egressOverlay") :]
    assert compose_path.index("docker-compose.tiktok-egress.yml") < compose_path.index(
        "docker-compose.rootless-staging.yml"
    )
    pull_operation = "Invoke-ComposePullsWithRetry" if script == PREFLIGHT_SCRIPT else '"pull"'
    for operation in ("Get-ProductionComposeConfig", pull_operation, '"up"'):
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
        "https://staging.overselfx.com",
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
    assert len(evidence["tiktok_egress_overlay_sha256"]) == 64
    assert ROOTLESS_DOCKER_HOST not in evidence_file.read_text(encoding="utf-8-sig")


def test_validate_only_rejects_unreviewed_retrieval_model_env_image(
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """环境文件不得用旧摘要覆盖工作流已经审阅的检索模型摘要。"""
    replace_environment_value(
        staging_env_file,
        "RETRIEVAL_MODEL_SERVICE_IMAGE",
        UNREVIEWED_RETRIEVAL_MODEL_IMAGE,
    )
    model_asset_dir = Path(
        next(
            line.split("=", 1)[1]
            for line in staging_env_file.read_text(encoding="utf-8").splitlines()
            if line.startswith("RETRIEVAL_MODEL_ASSET_DIR=")
        )
    )
    environment, _ = write_fake_compose_runtime(tmp_path, model_asset_dir)
    config_path = Path(environment["FAKE_DOCKER_CONFIG"])
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["services"]["retrieval-model-service"]["image"] = UNREVIEWED_RETRIEVAL_MODEL_IMAGE
    config_path.write_text(json.dumps(config), encoding="utf-8")
    evidence_file = tmp_path / "mismatched-retrieval-evidence.json"

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

    assert result.returncode != 0
    assert "must equal the reviewed retrievalmodelimage input." in normalized_process_output(result)
    assert not evidence_file.exists()


@pytest.mark.parametrize("script", [PREFLIGHT_SCRIPT, ROLLBACK_SCRIPT])
@pytest.mark.parametrize(
    ("configure", "expected_error"),
    [
        (
            lambda config: config["services"]["backend"]["environment"].update({"LLM_ENABLED": "true"}),
            "capability",
        ),
        (
            lambda config: config["services"]["proxy"]["ports"].append(
                {"host_ip": "127.0.0.1", "published": "18082", "target": "80"}
            ),
            "loopback http port",
        ),
        (
            lambda config: config["services"]["proxy"]["ports"][0].update({"host_ip": "0.0.0.0"}),
            "loopback http port",
        ),
        (
            lambda config: config["services"]["proxy"]["ports"][0].update({"published": "10080"}),
            "loopback http port",
        ),
        (
            lambda config: config["services"]["proxy"]["ports"][0].update({"published": "10443", "target": "443"}),
            "loopback http port",
        ),
        (
            lambda config: config["services"]["proxy"]["volumes"][0].update({"read_only": False}),
            "read-only tunnel nginx configuration",
        ),
        (
            lambda config: config["services"]["proxy"]["volumes"].append(
                {
                    "type": "bind",
                    "source": "/secure/test-certs",
                    "target": "/etc/nginx/certs",
                    "read_only": True,
                }
            ),
            "read-only tunnel nginx configuration",
        ),
        (
            lambda config: (
                config["services"]["tiktok-egress"]
                .setdefault("ports", [])
                .append({"host_ip": "127.0.0.1", "published": "1080", "target": "1080"})
            ),
            "egress helper must not publish ports",
        ),
        (
            lambda config: config["services"]["tiktok-egress"].update({"read_only": False}),
            "egress helper must use a read-only root filesystem",
        ),
        (
            lambda config: config["services"]["tiktok-egress"].update({"user": "999:999"}),
            "egress helper must run as container root under rootless docker",
        ),
        (
            lambda config: config["services"]["tiktok-egress"].update({"image": PREVIOUS_BACKEND_IMAGE}),
            "unexpected image for service: tiktok-egress",
        ),
        (
            lambda config: config["services"]["tiktok-egress"]["volumes"][0].update(
                {"source": str(SOURCE_ROOT / "tests")}
            ),
            "egress helper must mount only the reviewed secret directory",
        ),
        (
            lambda config: config["services"]["tiktok-egress"].update({"networks": {"default": None}}),
            "egress helper must join only the dedicated network",
        ),
        (
            lambda config: config["services"]["tiktok-egress"].update({"cap_drop": []}),
            "egress helper must drop all capabilities",
        ),
        (
            lambda config: config["services"]["tiktok-egress"].update({"security_opt": []}),
            "egress helper must set no-new-privileges",
        ),
    ],
)
def test_gate_scripts_reject_merged_compose_capability_port_or_mount_regressions(
    script: Path,
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
        script,
        "-Environment",
        "staging",
        "-EnvFile",
        str(staging_env_file),
        *validation_image_arguments(script),
        "-BaseUrl",
        "https://staging.overselfx.com",
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
    assert live_path.index("Invoke-TikTokEgressVerification") < live_path.index("Test-HealthEndpoint")
    passed_evidence = live_path[live_path.index('Write-Evidence -Status "passed"') :]
    assert "-EgressVerification $egressVerification" in passed_evidence


@pytest.mark.parametrize("script", [PREFLIGHT_SCRIPT, ROLLBACK_SCRIPT])
@pytest.mark.parametrize("value_kind", ["missing", "relative", "inside_checkout"])
def test_gate_scripts_reject_unsafe_egress_secret_directory(
    script: Path,
    value_kind: str,
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """SSH 私钥目录必须真实存在于 checkout 外部，且不能依赖相对工作目录。"""
    if value_kind == "missing":
        value = str(tmp_path / "missing-egress-secrets")
    elif value_kind == "relative":
        value = "./tiktok-egress-secrets"
    else:
        value = str(SOURCE_ROOT / "tests")
    replace_environment_value(staging_env_file, "TIKTOK_EGRESS_SECRET_DIR", value)

    result = run_powershell(
        script,
        "-Environment",
        "staging",
        "-EnvFile",
        str(staging_env_file),
        *validation_image_arguments(script),
        "-BaseUrl",
        "https://staging.overselfx.com",
        "-EvidenceFile",
        str(tmp_path / "unsafe-egress-secret-evidence.json"),
        "-ConfirmTarget",
        "staging",
        "-DockerHost",
        ROOTLESS_DOCKER_HOST,
        "-ValidateOnly",
    )

    assert result.returncode != 0
    assert not (tmp_path / "unsafe-egress-secret-evidence.json").exists()


@pytest.mark.parametrize("script", [PREFLIGHT_SCRIPT, ROLLBACK_SCRIPT])
def test_gate_scripts_reject_linked_egress_secret_directory(
    script: Path,
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """仓库外链接不得把 checkout 内目录伪装成 SSH 密钥目录。"""
    link_path = tmp_path / "linked-egress-secrets"
    create_directory_link(link_path, SOURCE_ROOT / "tests")
    try:
        replace_environment_value(staging_env_file, "TIKTOK_EGRESS_SECRET_DIR", str(link_path))
        result = run_powershell(
            script,
            "-Environment",
            "staging",
            "-EnvFile",
            str(staging_env_file),
            *validation_image_arguments(script),
            "-BaseUrl",
            "https://staging.overselfx.com",
            "-EvidenceFile",
            str(tmp_path / "linked-egress-secret-evidence.json"),
            "-ConfirmTarget",
            "staging",
            "-DockerHost",
            ROOTLESS_DOCKER_HOST,
            "-ValidateOnly",
        )
    finally:
        if link_path.exists() or link_path.is_symlink():
            if os.name == "nt":
                os.rmdir(link_path)
            else:
                link_path.unlink()

    assert result.returncode != 0
    assert "reparse point" in normalized_process_output(result)
    assert not (tmp_path / "linked-egress-secret-evidence.json").exists()


def test_preflight_deploys_the_validated_retrieval_model_image() -> None:
    """候选部署必须实际拉取并启动刚通过摘要校验的检索模型镜像。"""
    source = PREFLIGHT_SCRIPT.read_text(encoding="utf-8-sig")
    deploy_path = source[source.index('if (-not $PSCmdlet.ShouldProcess("staging"') :]

    assert deploy_path.count('"retrieval-model-service"') >= 2


def test_preflight_migrates_and_checks_database_head_before_starting_application(
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """首次部署必须先启动依赖并把数据库迁移到镜像声明的全部 head，再启动应用。"""
    model_asset_dir = Path(
        next(
            line.split("=", 1)[1]
            for line in staging_env_file.read_text(encoding="utf-8").splitlines()
            if line.startswith("RETRIEVAL_MODEL_ASSET_DIR=")
        )
    )
    environment, command_log = write_fake_compose_runtime(tmp_path, model_asset_dir)
    environment["FAKE_DOCKER_FAIL_UP_NUMBER"] = "3"
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
        "https://127.0.0.1:1",
        "-EvidenceFile",
        str(tmp_path / "migration-order.json"),
        "-ConfirmTarget",
        "staging",
        "-DockerHost",
        ROOTLESS_DOCKER_HOST,
        "-Deploy",
        "-Confirm:$false",
        environment=environment,
    )

    assert result.returncode != 0
    commands = [json.loads(line) for line in command_log.read_text(encoding="utf-8").splitlines()]
    dependency_up = next(
        index
        for index, command in enumerate(commands)
        if "up" in command and {"postgres", "redis", "minio"}.issubset(command) and "backend" not in command
    )
    upgrade = next(
        index
        for index, command in enumerate(commands)
        if command[-7:] == ["run", "--rm", "--no-deps", "backend", "alembic", "upgrade", "head"]
    )
    check_heads = next(
        index
        for index, command in enumerate(commands)
        if command[-7:] == ["run", "--rm", "--no-deps", "backend", "alembic", "current", "--check-heads"]
    )
    application_up = next(index for index, command in enumerate(commands) if "up" in command and "backend" in command)
    assert dependency_up < upgrade < check_heads < application_up


def test_preflight_verifies_egress_before_migrations_and_applications(
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """helper 健康后先验证出口，再允许迁移和候选应用启动。"""
    model_asset_dir = Path(
        next(
            line.split("=", 1)[1]
            for line in staging_env_file.read_text(encoding="utf-8").splitlines()
            if line.startswith("RETRIEVAL_MODEL_ASSET_DIR=")
        )
    )
    environment, command_log = write_fake_compose_runtime(tmp_path, model_asset_dir)
    environment["FAKE_DOCKER_FAIL_UP_NUMBER"] = "999"
    evidence_file = tmp_path / "egress-order-evidence.json"
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
        "https://127.0.0.1:1",
        "-EvidenceFile",
        str(evidence_file),
        "-ConfirmTarget",
        "staging",
        "-DockerHost",
        ROOTLESS_DOCKER_HOST,
        "-Deploy",
        "-Confirm:$false",
        environment=environment,
    )

    commands = [json.loads(line) for line in command_log.read_text(encoding="utf-8").splitlines()]
    helper_up = next(index for index, command in enumerate(commands) if "up" in command and "tiktok-egress" in command)
    application_up = next(index for index, command in enumerate(commands) if "up" in command and "backend" in command)
    verifier_run = next(
        index
        for index, command in enumerate(commands)
        if command[-6:]
        == [
            "run",
            "--rm",
            "--no-deps",
            "backend",
            "python",
            "scripts/verify_tiktok_egress.py",
        ]
    )
    migration_upgrade = next(
        index
        for index, command in enumerate(commands)
        if command[-7:] == ["run", "--rm", "--no-deps", "backend", "alembic", "upgrade", "head"]
    )
    migration_check = next(
        index
        for index, command in enumerate(commands)
        if command[-7:] == ["run", "--rm", "--no-deps", "backend", "alembic", "current", "--check-heads"]
    )
    assert result.returncode != 0
    assert helper_up < verifier_run < migration_upgrade < migration_check < application_up
    pull_commands = [command for command in commands if "pull" in command]
    assert [command[-2:] for command in pull_commands] == [
        ["pull", "tiktok-egress"],
        ["pull", "frontend"],
        ["pull", "retrieval-model-service"],
    ]
    if evidence_file.exists():
        assert json.loads(evidence_file.read_text(encoding="utf-8-sig"))["status"] != "passed"


def test_preflight_verifier_failure_never_records_passed_evidence(
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """代理路径验证失败必须在公网健康检查和 passed 证据前停止。"""
    model_asset_dir = Path(
        next(
            line.split("=", 1)[1]
            for line in staging_env_file.read_text(encoding="utf-8").splitlines()
            if line.startswith("RETRIEVAL_MODEL_ASSET_DIR=")
        )
    )
    environment, command_log = write_fake_compose_runtime(tmp_path, model_asset_dir)
    environment["FAKE_DOCKER_FAIL_UP_NUMBER"] = "999"
    environment["FAKE_DOCKER_VERIFY_EXIT_CODE"] = "44"
    evidence_file = tmp_path / "egress-mismatch-evidence.json"
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
        "https://127.0.0.1:1",
        "-EvidenceFile",
        str(evidence_file),
        "-ConfirmTarget",
        "staging",
        "-DockerHost",
        ROOTLESS_DOCKER_HOST,
        "-Deploy",
        "-Confirm:$false",
        environment=environment,
    )

    commands = [json.loads(line) for line in command_log.read_text(encoding="utf-8").splitlines()]
    assert result.returncode != 0
    assert any(command[-1:] == ["scripts/verify_tiktok_egress.py"] for command in commands)
    assert not any("alembic" in command for command in commands)
    assert not any("up" in command and "backend" in command for command in commands)
    if evidence_file.exists():
        assert json.loads(evidence_file.read_text(encoding="utf-8-sig"))["status"] != "passed"


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
    assert len(evidence["rootless_overlay_sha256"]) == 64
    assert len(evidence["tiktok_egress_overlay_sha256"]) == 64


def test_rollback_keeps_candidate_egress_image_while_switching_applications(
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """历史后端可能不含 OpenSSH；回滚期间 helper 必须始终固定候选后端摘要。"""
    model_asset_dir = Path(
        next(
            line.split("=", 1)[1]
            for line in staging_env_file.read_text(encoding="utf-8").splitlines()
            if line.startswith("RETRIEVAL_MODEL_ASSET_DIR=")
        )
    )
    environment, _ = write_fake_compose_runtime(tmp_path, model_asset_dir)
    environment["FAKE_DOCKER_FAIL_UP_NUMBER"] = "999"
    result = run_powershell(
        ROLLBACK_SCRIPT,
        "-Environment",
        "staging",
        "-EnvFile",
        str(staging_env_file),
        *validation_image_arguments(ROLLBACK_SCRIPT),
        "-BaseUrl",
        "https://127.0.0.1:1",
        "-EvidenceFile",
        str(tmp_path / "rollback-live-evidence.json"),
        "-ConfirmTarget",
        "staging",
        "-DockerHost",
        ROOTLESS_DOCKER_HOST,
        "-Execute",
        "-Confirm:$false",
        environment=environment,
    )

    records = [
        json.loads(line)
        for line in (tmp_path / "fake-docker-environment.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    compose_operations = [record for record in records if record["arguments"][:2] != ["compose", "version"]]
    previous_image_operations = [
        record for record in compose_operations if record["BACKEND_IMAGE"] == PREVIOUS_BACKEND_IMAGE
    ]
    assert result.returncode != 0
    assert previous_image_operations
    assert all(record["TIKTOK_EGRESS_IMAGE"] == BACKEND_IMAGE for record in compose_operations)
    assert all(record["TIKTOK_EGRESS_IMAGE"] == BACKEND_IMAGE for record in previous_image_operations)
    for record in compose_operations:
        for capability in (
            "REAL_TIKTOK_READ_ENABLED",
            "REAL_TIKTOK_WEBHOOK_ENABLED",
            "REAL_TIKTOK_MESSAGE_WRITE_ENABLED",
            "REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED",
        ):
            assert record[capability] == "false"


def test_rollback_rejects_non_candidate_live_retrieval_before_mutation(
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """当前检索镜像仍是旧摘要时，不得把镜像更换报告为候选回滚。"""
    model_asset_dir = Path(
        next(
            line.split("=", 1)[1]
            for line in staging_env_file.read_text(encoding="utf-8").splitlines()
            if line.startswith("RETRIEVAL_MODEL_ASSET_DIR=")
        )
    )
    environment, command_log = write_fake_compose_runtime(tmp_path, model_asset_dir)
    environment["FAKE_DOCKER_LIVE_RETRIEVAL_IMAGE"] = UNREVIEWED_RETRIEVAL_MODEL_IMAGE
    evidence_file = tmp_path / "rollback-wrong-live-image.json"
    result = run_powershell(
        ROLLBACK_SCRIPT,
        "-Environment",
        "staging",
        "-EnvFile",
        str(staging_env_file),
        *validation_image_arguments(ROLLBACK_SCRIPT),
        "-BaseUrl",
        "https://127.0.0.1:1",
        "-EvidenceFile",
        str(evidence_file),
        "-ConfirmTarget",
        "staging",
        "-DockerHost",
        ROOTLESS_DOCKER_HOST,
        "-Execute",
        "-Confirm:$false",
        environment=environment,
    )

    commands = [json.loads(line) for line in command_log.read_text(encoding="utf-8").splitlines()]
    assert result.returncode != 0
    assert "retrieval-model-service" in normalized_process_output(result)
    assert not any("pull" in command or "up" in command for command in commands)
    assert not evidence_file.exists()


def test_rollback_rejects_paused_candidate_retrieval_before_mutation(
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """镜像摘要虽正确，检索容器未运行时也不得开始切换。"""
    model_asset_dir = Path(
        next(
            line.split("=", 1)[1]
            for line in staging_env_file.read_text(encoding="utf-8").splitlines()
            if line.startswith("RETRIEVAL_MODEL_ASSET_DIR=")
        )
    )
    environment, command_log = write_fake_compose_runtime(tmp_path, model_asset_dir)
    environment["FAKE_DOCKER_PAUSED_RETRIEVAL"] = "1"
    evidence_file = tmp_path / "rollback-paused-live-image.json"
    result = run_powershell(
        ROLLBACK_SCRIPT,
        "-Environment",
        "staging",
        "-EnvFile",
        str(staging_env_file),
        *validation_image_arguments(ROLLBACK_SCRIPT),
        "-BaseUrl",
        "https://127.0.0.1:1",
        "-EvidenceFile",
        str(evidence_file),
        "-ConfirmTarget",
        "staging",
        "-DockerHost",
        ROOTLESS_DOCKER_HOST,
        "-Execute",
        "-Confirm:$false",
        environment=environment,
    )

    commands = [json.loads(line) for line in command_log.read_text(encoding="utf-8").splitlines()]
    assert result.returncode != 0
    assert "retrieval-model-service" in normalized_process_output(result)
    assert not any("pull" in command or "up" in command for command in commands)
    assert not evidence_file.exists()


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


@pytest.mark.parametrize(
    ("script", "mode"),
    [(PREFLIGHT_SCRIPT, "-Deploy"), (ROLLBACK_SCRIPT, "-Execute")],
)
def test_live_gate_refreshes_proxy_after_backend_recreation(
    script: Path,
    mode: str,
    staging_env_file: Path,
    tmp_path: Path,
) -> None:
    """backend 地址变化后必须重启内层 Nginx，并等 proxy 健康再检查公网。"""
    model_asset_dir = Path(
        next(
            line.split("=", 1)[1]
            for line in staging_env_file.read_text(encoding="utf-8").splitlines()
            if line.startswith("RETRIEVAL_MODEL_ASSET_DIR=")
        )
    )
    environment, command_log = write_fake_compose_runtime(tmp_path, model_asset_dir)
    environment["FAKE_DOCKER_FAIL_UP_NUMBER"] = "999"
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
        str(tmp_path / "proxy-refresh.json"),
        "-ConfirmTarget",
        "staging",
        "-DockerHost",
        ROOTLESS_DOCKER_HOST,
        mode,
        "-Confirm:$false",
        environment=environment,
    )

    assert result.returncode != 0  # 本测试不提供公网服务。
    assert command_log.exists(), result.stdout + result.stderr
    commands = [json.loads(line) for line in command_log.read_text(encoding="utf-8").splitlines()]
    application_up = max(index for index, command in enumerate(commands) if "up" in command and "backend" in command)
    proxy_restart = next(index for index, command in enumerate(commands) if command[-2:] == ["restart", "proxy"])
    proxy_wait = next(
        index
        for index, command in enumerate(commands)
        if command[-7:] == ["up", "-d", "--no-build", "--wait", "--wait-timeout", "600", "proxy"]
    )
    assert application_up < proxy_restart < proxy_wait
