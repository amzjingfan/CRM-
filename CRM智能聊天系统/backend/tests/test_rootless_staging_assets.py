"""Rootless 主机资产静态契约；真实 Bash/端口/失败注入由 Ubuntu Task 8 验证。"""

import configparser
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ROOTLESS_DIR = PROJECT_ROOT / "deploy" / "staging" / "rootless"
SYSTEMD_DIR = ROOTLESS_DIR / "systemd"


def _bash_executable() -> str | None:
    """返回可执行受控脚本的 Bash。"""
    bash = shutil.which("bash")
    if os.name == "nt":
        # Windows 的系统 bash 通常是 WSL 启动器；优先使用 Git for Windows。
        git = shutil.which("git")
        git_bash = Path(git).resolve().parents[1] / "bin" / "bash.exe" if git else None
        bash = str(git_bash) if git_bash and git_bash.is_file() else None
    return bash


def _extract_bash_function(source: str, function_name: str) -> str:
    """提取不含嵌套函数的 Bash 函数，供受控行为测试执行真实实现。"""
    start = source.index(f"{function_name}() {{")
    end = source.index("\n}\n", start) + len("\n}\n")
    return source[start:end]


def _to_bash_path(path: Path) -> str:
    """Windows 下把盘符路径转换为 Git Bash 可用的 POSIX 路径。"""
    posix_path = path.as_posix()
    if os.name != "nt":
        return posix_path
    drive = path.drive.removesuffix(":").lower()
    return f"/{drive}{posix_path[2:]}"


def test_bootstrap_never_reconfigures_system_docker() -> None:
    """捕获误改系统引擎、扩大账户权限或安装范围的回归。"""
    source = (ROOTLESS_DIR / "bootstrap-host.sh").read_text(encoding="utf-8")
    forbidden = (
        "daemon.json",
        "data-root",
        "systemctl restart docker",
        "usermod",
        "adduser",
        "apt-get upgrade",
        "apt-get dist-upgrade",
    )
    assert all(token not in source for token in forbidden)
    assert "apt-get install --no-install-recommends -y uidmap" in source
    assert "dockerd-rootless-setuptool.sh install --force" in source
    assert "loginctl enable-linger crmdeploy" in source
    assert "NEEDRESTART_MODE=l" in source


def test_bootstrap_pins_identity_and_rootless_storage() -> None:
    """账户不符、空间不足、Rootless 标志或路径不符必须有显式门禁。"""
    source = (ROOTLESS_DIR / "bootstrap-host.sh").read_text(encoding="utf-8")
    for required in (
        "set -Eeuo pipefail",
        "id -u crmdeploy",
        "id -g crmdeploy",
        "1004",
        "/home/crmdeploy",
        "1572864",
        "VERSION_ID",
        "26.04",
        "x86_64",
        "SecurityOptions",
        "name=rootless",
        "DockerRootDir",
        "realpath -e",
        "unix:///run/user/1004/docker.sock",
        "env -i",
        "[[ -S /run/user/1004/docker.sock ]]",
    ):
        assert required in source


def test_bootstrap_compares_full_system_snapshot_even_on_failure() -> None:
    """失败分支不得跳过公司容器快照，ID/名称/镜像/启动时间均纳入比较。"""
    source = (ROOTLESS_DIR / "bootstrap-host.sh").read_text(encoding="utf-8")
    for required in (
        "unix:///var/run/docker.sock",
        "ps --no-trunc --format '{{json .}}'",
        "df -B1 / /home",
        "host-baseline-before",
        "host-baseline-after",
        "{{.Id}}",
        "{{.Name}}",
        "{{.Image}}",
        "{{.State.StartedAt}}",
        "{{.State.Running}}",
        "LC_ALL=C sort",
        "trap finish EXIT",
        "diff -u",
        'exit "$exit_code"',
    ):
        assert required in source
    assert source.index("trap finish EXIT") < source.index("apt-get update")


@pytest.mark.parametrize("protocol,port,target", [("http", "80", "10080"), ("https", "443", "10443")])
def test_entry_proxy_targets_only_loopback(protocol: str, port: str, target: str) -> None:
    """用解析后的 unit 契约捕获低端口、转发目的地和沙箱保护回归。"""
    socket = configparser.ConfigParser(interpolation=None)
    socket.read_string((SYSTEMD_DIR / f"crm-staging-{protocol}.socket").read_text(encoding="utf-8"))
    assert socket["Socket"]["ListenStream"] == port
    assert socket["Socket"]["Accept"] == "no"
    assert socket["Socket"]["Service"] == f"crm-staging-{protocol}.service"
    assert socket["Install"]["WantedBy"] == "sockets.target"
    service = configparser.ConfigParser(interpolation=None)
    service.read_string((SYSTEMD_DIR / f"crm-staging-{protocol}.service").read_text(encoding="utf-8"))
    assert service["Service"]["ExecStart"] == f"/usr/lib/systemd/systemd-socket-proxyd 127.0.0.1:{target}"
    for key in ("PrivateTmp", "NoNewPrivileges", "ProtectHome"):
        assert service["Service"][key] == "yes"
    assert service["Service"]["ProtectSystem"] == "strict"
    assert "Install" not in service


def test_installer_rejects_foreign_listeners_and_modified_units_before_writes() -> None:
    """占用端口不能仅凭 PID 1 放行；同时校验 unit 路径、内容及归属。"""
    source = (ROOTLESS_DIR / "install-entry-proxy.sh").read_text(encoding="utf-8")
    for required in (
        "ss -H -lntp",
        "list-sockets",
        "FragmentPath",
        "DropInPaths",
        "NeedDaemonReload",
        "MainPID",
        "cmp -s",
        "check_port 80 crm-staging-http",
        "check_port 443 crm-staging-https",
        "systemctl daemon-reload",
        "systemctl enable --now crm-staging-http.socket crm-staging-https.socket",
        "systemctl status",
        "ss -lntp",
        "entry-proxy",
        "rollback",
        "flock",
    ):
        assert required in source
    assert source.index("check_port 443 crm-staging-https") < source.index("install -o root -g root -m 0644")
    assert "enable --now crm-staging-http.service" not in source
    assert "systemctl restart docker" not in source


def test_installer_rechecks_port_ownership_after_socket_activation() -> None:
    """捕获只做预检、启动之后未核对真实监听者的缺口。"""
    source = (ROOTLESS_DIR / "install-entry-proxy.sh").read_text(encoding="utf-8")
    activated = source.split("systemctl enable --now crm-staging-http.socket crm-staging-https.socket", 1)[1]
    assert "check_port 80 crm-staging-http" in activated
    assert "check_port 443 crm-staging-https" in activated


@pytest.mark.parametrize(
    "substate,accepted",
    [("listening", True), ("running", True), ("dead", False), ("failed", False), ("start-pre", False), ("", False)],
)
def test_installer_substate_contract_accepts_only_listening_or_running(substate: str, accepted: bool) -> None:
    """静态解析实际 case 白名单；Bash 执行和首个连接后的幂等验证仍归 Task 8。"""
    source = (ROOTLESS_DIR / "install-entry-proxy.sh").read_text(encoding="utf-8")
    state_branch = re.search(
        r'case \$\(systemctl show "\$prefix\.socket" --property=SubState --value\) in\s+'
        r"([a-z|]+)\) ;;\s+\*\) fail [^\n]+ ;;\s+esac",
        source,
    )
    assert state_branch is not None, "SubState must use an explicit allowlist and a failing default branch"
    allowed_states = state_branch.group(1).split("|")
    assert set(allowed_states) == {"listening", "running"}
    assert (substate in allowed_states) is accepted


@pytest.mark.parametrize("extension", ["service", "socket"])
def test_systemd_units_have_lf_checkout_contract(extension: str) -> None:
    """固定 Git 检出换行，避免 Windows 资产与 Linux 已安装单元 cmp 不一致。"""
    attributes = (PROJECT_ROOT.parent / ".gitattributes").read_text(encoding="utf-8")
    assert f"*.{extension} text eol=lf" in attributes.splitlines()
    for unit in SYSTEMD_DIR.glob(f"*.{extension}"):
        assert b"\r" not in unit.read_bytes()


@pytest.mark.parametrize("name", ["bootstrap-host.sh", "install-entry-proxy.sh"])
def test_evidence_parent_remains_writable_by_deployment_user(name: str) -> None:
    """主机取证不能夺走后续 crmdeploy 部署任务创建证据目录的权限。"""
    source = (ROOTLESS_DIR / name).read_text(encoding="utf-8")
    assert 'install -d -o 1004 -g 1004 -m 0750 "$evidence_root"' in source


@pytest.mark.parametrize("name", ["bootstrap-host.sh", "install-entry-proxy.sh"])
def test_shell_assets_use_lf_and_no_utf8_bom(name: str) -> None:
    """Windows 检出后脚本仍需可作为 Linux Bash 资产交付。"""
    content = (ROOTLESS_DIR / name).read_bytes()
    assert content.startswith(b"#!/usr/bin/env bash\n")
    assert b"\r" not in content


def test_runner_manifest_pins_verified_official_archives() -> None:
    """供应链版本、平台或摘要漂移必须重新审核，不能静默下载 latest。"""
    path = ROOTLESS_DIR / "toolchain-manifest.json"
    assert path.is_file(), "checksum-pinned toolchain manifest is missing"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest == {
        "schema_version": 1,
        "platform": "linux-x64",
        "runner": {
            "version": "2.336.0",
            "url": "https://github.com/actions/runner/releases/download/v2.336.0/"
            "actions-runner-linux-x64-2.336.0.tar.gz",
            "sha256": "04cf0be1aff4c3ec3554466c39124ca250e3effd8873bb7e8d68535aa9505d5d",
        },
        "powershell": {
            "version": "7.6.5",
            "url": "https://github.com/PowerShell/PowerShell/releases/download/v7.6.5/"
            "powershell-7.6.5-linux-x64.tar.gz",
            "sha256": "b34ab3b19acac1d3d4d0d3cfdb02acf62f457b0b6a962ff008132033f7566844",
        },
    }


def test_runner_installer_guards_identity_credentials_and_extraction_order() -> None:
    """静态契约覆盖安装入口；真实 Bash、断点恢复和注册留给 Ubuntu 门禁。"""
    path = ROOTLESS_DIR / "install-runner.sh"
    assert path.is_file(), "runner installer is missing"
    source = path.read_text(encoding="utf-8")
    for required in (
        "set -Eeuo pipefail",
        "umask 077",
        "id -un",
        "crmdeploy",
        "id -u",
        "1004",
        "realpath -e",
        "/home/crmdeploy/.cache/crm-toolchain",
        "/home/crmdeploy/runner",
        "/home/crmdeploy/tools/powershell",
        "toolchain-manifest.json",
        "sealed-$filename",
        '[[ -e "$sealed_archive" || -L "$sealed_archive" ]]',
        '[[ -f "$sealed_archive" && ! -L "$sealed_archive" ]]',
        '$(stat -c %u "$sealed_archive") == 1004',
        "read -r -s runner_token",
        "trap cleanup EXIT",
        "unset runner_token",
        "sha256sum -c",
        'cd "$runner_dir"',
        './config.sh --unattended --url https://github.com/CP11-gh/CRM --token "$runner_token"',
        "--name crm-staging-192-168-110-210 --labels crm-staging",
        "--work /home/crmdeploy/runner/_work --replace",
        "systemctl --user daemon-reload",
        "systemctl --user enable --now crm-staging-runner.service",
        "flock",
    ):
        assert required in source
    assert "set -x" not in source
    assert "export runner_token" not in source
    assert source.index("sha256sum -c") < source.index("tar -xzf")
    config_tail = source.split("./config.sh --unattended", 1)[1]
    assert config_tail.index("unset runner_token") < config_tail.index("systemctl --user daemon-reload")
    assert b"\r" not in path.read_bytes()


def test_runner_installer_secures_home_and_every_existing_directory_component() -> None:
    """Home 与遍历到的既有目录都必须拒绝错误属主、链接和组/其他写权限。"""
    source = (ROOTLESS_DIR / "install-runner.sh").read_text(encoding="utf-8")
    for required in (
        "check_existing_directory() {",
        '[[ -d "$directory" && ! -L "$directory" ]]',
        '$(stat -c %u "$directory") == 1004',
        "8#$directory_mode & 0022",
        "check_existing_directory /home/crmdeploy",
        'check_existing_directory "$current"',
    ):
        assert required in source
    assert source.index("check_existing_directory /home/crmdeploy") < source.index('check_directory "$cache_dir"')


def test_runner_user_service_uses_home_tools_and_rootless_socket() -> None:
    """Runner 不得借系统级 User 配置或默认 Docker socket 越过用户隔离。"""
    path = SYSTEMD_DIR / "user" / "crm-staging-runner.service"
    assert path.is_file(), "runner user unit is missing"
    unit = configparser.ConfigParser(interpolation=None)
    unit.read_string(path.read_text(encoding="utf-8"))
    service = unit["Service"]
    assert "User" not in service
    assert service["ExecStart"] == "/home/crmdeploy/runner/run.sh"
    assert service["WorkingDirectory"] == "/home/crmdeploy/runner"
    assert "DOCKER_HOST=unix:///run/user/1004/docker.sock" in service["Environment"]
    assert "PATH=/home/crmdeploy/tools/powershell:" in service["Environment"]
    assert unit["Install"]["WantedBy"] == "default.target"


def test_runner_token_cannot_inherit_export_attribute() -> None:
    """Bash 已导出的同名变量在赋值后仍会导出，读凭证前必须先 unset。"""
    source = (ROOTLESS_DIR / "install-runner.sh").read_text(encoding="utf-8")
    before_assignment = source.split("runner_token=", 1)[0]
    assert "unset runner_token" in before_assignment


@pytest.mark.parametrize("allexport_source", ["argument", "environment"])
def test_runner_token_stays_out_of_child_environment_with_allexport(allexport_source: str) -> None:
    """执行实际凭证初始化/读取片段，捕获 bash -a 与 SHELLOPTS 自动导出泄漏。"""
    bash = shutil.which("bash")
    if os.name == "nt":
        # Windows 的系统 bash 通常只是 WSL 启动器；使用已有 Git for Windows 的真实 Bash。
        git = shutil.which("git")
        git_bash = Path(git).resolve().parents[1] / "bin" / "bash.exe" if git else None
        bash = str(git_bash) if git_bash and git_bash.is_file() else None
    if bash is None:
        pytest.skip("Bash is required to verify runner token process-environment isolation")

    source = (ROOTLESS_DIR / "install-runner.sh").read_text(encoding="utf-8")
    preamble = source.split("[[ $(id -un)", 1)[0]
    credential_setup = source.split("unset runner_token\n", 1)[1].split("# 仅解释 JSON", 1)[0]
    token_read = next(line.strip() for line in source.splitlines() if "IFS= read -r -s runner_token" in line)
    # 只执行生产初始化和 read，随后真实启动子 Bash 检查环境；不执行下载、注册或 systemd。
    probe = (
        preamble
        + "unset runner_token\n"
        + credential_setup
        + token_read
        + "\n/usr/bin/bash --noprofile --norc -c '[[ ! ${runner_token+x} ]]'\n"
    )
    environment = os.environ.copy()
    environment.pop("BASH_ENV", None)
    environment.pop("SHELLOPTS", None)
    environment["runner_token"] = "FAKE_INHERITED_TOKEN"
    arguments = [bash, "--noprofile", "--norc"]
    if allexport_source == "argument":
        arguments.append("-a")
    else:
        environment["SHELLOPTS"] = "allexport"
    result = subprocess.run(
        [*arguments, "-c", probe],
        input="FAKE_REVIEW_TOKEN\n",
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, "registration token was exported into the child process environment"
    assert result.stdout == ""


def test_runner_rerun_preserves_managed_install_and_checks_registered_identity() -> None:
    """重复安装不覆盖自动更新后的 Runner，也不接管其他仓库已注册的身份。"""
    source = (ROOTLESS_DIR / "install-runner.sh").read_text(encoding="utf-8")
    for required in (
        ".crm-toolchain-sha256",
        'cmp -s "$unit_source" "$unit_target"',
        "[[ -e .runner || -L .runner ]]",
        '"gitHubUrl": "https://github.com/CP11-gh/CRM"',
        '"agentName": "crm-staging-192-168-110-210"',
        '"workFolder": "/home/crmdeploy/runner/_work"',
    ):
        assert required in source


def test_runner_readme_promotes_merged_assets_before_versioned_installer_invocation() -> None:
    """运行手册必须先验签并原子提升合并后资产，再调用同一 HEAD 的安装器。"""
    source = (ROOTLESS_DIR / "README.md").read_text(encoding="utf-8")
    required = (
        "git status --porcelain=v1",
        "git branch --show-current",
        "git rev-parse HEAD",
        "^[0-9a-f]{40}$",
        "install-runner.sh",
        "toolchain-manifest.json",
        "systemd/user/crm-staging-runner.service",
        ".incoming-bootstrap-$bootstrapRevision-$transferId",
        "rootless-staging-bootstrap-$bootstrapRevision",
        "Get-FileHash",
        "$remoteSrcGuard = 'check_secure_directory /home/crmdeploy/src'",
        "stat -c %u",
        "$runnerInstallerSha256",
        "$toolchainManifestSha256",
        "$runnerUnitSha256",
        "sha256sum -c -",
        "bash -n",
        "normalize_transferred_file '$remoteTransferDir/install-runner.sh' 0700",
        "normalize_transferred_file '$remoteTransferDir/toolchain-manifest.json' 0600",
        "normalize_transferred_file '$remoteTransferDir/systemd/user/crm-staging-runner.service' 0600",
        "mv -T",
    )
    for marker in required:
        assert marker in source

    promotion = source.index("mv -T", source.index(".incoming-bootstrap-"))
    versioned_installer = source.index("rootless-staging-bootstrap-$runnerBootstrapRevision/install-runner.sh")
    invocation = source.index("$runnerToken | ssh")
    assert promotion < versioned_installer < invocation
    assert "/rootless-staging-bootstrap/install-runner.sh" not in source[invocation:]
    assert "$invokeVerifiedRunner" in source[invocation:]


def test_runner_readme_normalizes_windows_scp_modes_before_strict_file_checks() -> None:
    """唯一私有 incoming 目录内应先拒绝链接/错属主，再精确收紧 Windows SCP 文件模式。"""
    source = (ROOTLESS_DIR / "README.md").read_text(encoding="utf-8")
    transfer_section = source[source.index("$remoteDirectoryGuard =") : source.index("$manifest =")]

    guard = "$remoteTransferredFileGuard = 'normalize_transferred_file()"
    assert guard in transfer_section
    guard_start = transfer_section.index(guard)
    guard_end = transfer_section.index("';", guard_start)
    guard_body = transfer_section[guard_start:guard_end]
    for required in (
        'test -f "$path"',
        'test ! -L "$path"',
        'test "$(stat -c %u "$path")" = 1004',
        'chmod "$target_mode" -- "$path"',
        'check_secure_file "$path"',
    ):
        assert required in guard_body

    verify_start = transfer_section.index('$verifyBootstrap = "')
    verify_end = transfer_section.index('"\nssh -i', verify_start)
    verify_body = transfer_section[verify_start:verify_end]
    directory_check = verify_body.index("check_secure_directory '$remoteTransferDir'")
    installer_normalize = verify_body.index("normalize_transferred_file '$remoteTransferDir/install-runner.sh' 0700")
    manifest_normalize = verify_body.index(
        "normalize_transferred_file '$remoteTransferDir/toolchain-manifest.json' 0600"
    )
    unit_normalize = verify_body.index(
        "normalize_transferred_file '$remoteTransferDir/systemd/user/crm-staging-runner.service' 0600"
    )
    first_digest_check = verify_body.index("sha256sum -c -")
    promotion = verify_body.index("mv -T")

    assert directory_check < installer_normalize < manifest_normalize < unit_normalize
    assert unit_normalize < first_digest_check < promotion
    assert "chmod *" not in verify_body


def test_runner_readme_normalizes_archive_scp_mode_before_digest_and_promotion() -> None:
    """工具归档也必须在私有 incoming 内先验类型/属主，再收紧模式并验签提升。"""
    source = (ROOTLESS_DIR / "README.md").read_text(encoding="utf-8")
    transfer_section = source[source.index("$remoteDirectoryGuard =") : source.index("传输后先以")]

    guard = "$remoteTransferredFileGuard = 'normalize_transferred_file()"
    assert guard in transfer_section
    verify_start = transfer_section.index('$verifyAndPromote = "')
    verify_end = transfer_section.index('"\n  ssh -i', verify_start)
    verify_body = transfer_section[verify_start:verify_end]

    directory_check = verify_body.index("check_secure_directory '$remoteCacheTransferDir'")
    archive_normalize = verify_body.index("normalize_transferred_file '$remoteIncoming' 0600")
    first_digest_check = verify_body.index("sha256sum -c -")
    promotion = verify_body.index("mv -T")
    sealed_strict_check = verify_body.index("check_secure_file '$remoteSealed'")

    assert directory_check < archive_normalize < first_digest_check < promotion < sealed_strict_check
    assert "chmod 0600 '$remoteIncoming'" not in verify_body
    assert "chmod *" not in verify_body


def test_runner_readme_rechecks_remote_path_security_at_every_ssh_boundary() -> None:
    """各跨 SSH 边界都必须重新校验父路径、临时目录和提升后目录。"""
    source = (ROOTLESS_DIR / "README.md").read_text(encoding="utf-8")
    for required in (
        "$remoteDirectoryGuard = 'set -euo pipefail;",
        "$remoteFileGuard =",
        "8#$mode & 0022",
        '$prepareBootstrap = "$remoteDirectoryGuard $remoteHomeGuard;',
        (
            '$verifyBootstrap = "$remoteDirectoryGuard $remoteFileGuard '
            "$remoteTransferredFileGuard $remoteHomeGuard; $remoteSrcGuard;"
        ),
        '$prepareToolchainCache = "$remoteDirectoryGuard $remoteHomeGuard;',
        '$prepareRemote = "$remoteDirectoryGuard $remoteHomeGuard; $remoteDotCacheGuard; $remoteCacheGuard;',
        (
            '$verifyAndPromote = "$remoteDirectoryGuard $remoteFileGuard '
            "$remoteTransferredFileGuard $remoteHomeGuard; $remoteDotCacheGuard; $remoteCacheGuard;"
        ),
        "check_secure_directory '$remoteTransferDir'",
        "check_secure_directory '$remoteBootstrap'",
        "check_secure_directory '$remoteCacheTransferDir'",
        "check_secure_file '$remoteSealed'",
    ):
        assert required in source


def test_runner_readme_rehashes_and_revalidates_versioned_assets_before_token_request() -> None:
    """申请短期 Token 前必须从当前 HEAD 重算本地摘要并最终复验远端版本目录。"""
    source = (ROOTLESS_DIR / "README.md").read_text(encoding="utf-8")
    token_section = source[source.index("$runnerBranch =") :]
    for required in (
        "$runnerBootstrapRevision = ([string](git rev-parse HEAD)).Trim()",
        "$runnerBootstrapFiles = [ordered]@{",
        "Get-FileHash",
        "$runnerInstallerSha256",
        "$toolchainManifestSha256",
        "$runnerUnitSha256",
        "$verifyRunnerBootstrap =",
        "check_secure_directory '$runnerBootstrap'",
        "check_secure_file '$runnerInstaller'",
        "sha256sum -c -",
        "bash -n '$runnerInstaller'",
        "ssh -i $env:CRM_STAGING_SSH_KEY crmdeploy@192.168.110.210 $verifyRunnerBootstrap",
    ):
        assert required in token_section

    remote_verify = token_section.index("$verifyRunnerBootstrap =")
    remote_verify_call = token_section.index("ssh -i", remote_verify)
    token_request = token_section.index("actions/runners/registration-token")
    assert remote_verify < remote_verify_call < token_request


def test_runner_token_bearing_ssh_revalidates_assets_in_the_same_remote_process() -> None:
    """携带 Token 的 SSH 必须在同一远端进程复验资产后才读取 stdin。"""
    source = (ROOTLESS_DIR / "README.md").read_text(encoding="utf-8")
    token_section = source[source.index("$runnerBranch =") :]
    invoke_line = next(
        (line.strip() for line in token_section.splitlines() if line.startswith("$invokeVerifiedRunner =")), ""
    )
    token_ssh_line = next(line.strip() for line in token_section.splitlines() if "$runnerToken | ssh" in line)

    assert invoke_line, "Token invocation does not define a same-process verified command"
    assert "$verifyRunnerBootstrap;" in invoke_line
    assert "tr -d '\\r'" in invoke_line
    assert "| bash '$runnerInstaller'" in invoke_line
    assert "$invokeVerifiedRunner" in token_ssh_line
    assert "bash -o pipefail -c" not in token_ssh_line

    verification_definition = token_section.index("$verifyRunnerBootstrap =")
    verified_invocation_definition = token_section.index("$invokeVerifiedRunner =")
    token_request = token_section.index("actions/runners/registration-token")
    token_ssh = token_section.index("$runnerToken | ssh")
    assert verification_definition < verified_invocation_definition < token_request < token_ssh


def test_runner_readme_chmods_only_the_two_manifest_archives() -> None:
    """缓存复核不得用通配符改变同目录中的未知归档。"""
    source = (ROOTLESS_DIR / "README.md").read_text(encoding="utf-8")
    assert 'chmod 0600 "$cache"/sealed-*.tar.gz' not in source
    assert 'chmod 0600 "$cache/sealed-actions-runner-linux-x64-2.336.0.tar.gz"' in source
    assert 'chmod 0600 "$cache/sealed-powershell-7.6.5-linux-x64.tar.gz"' in source


def _run_verified_archive_selection(
    tmp_path: Path,
    *,
    cache_kind: str,
    expected_digest: str,
    owner_uid: str = "1004",
    cache_mode: str = "700",
    archive_mode: str = "600",
) -> tuple[subprocess.CompletedProcess[str], Path, Path, Path]:
    """在受控 Bash 环境中执行安装器的密封归档选择函数。

    测试仅覆盖外部网络边界和 UID 观测；归档类型、符号链接与 SHA-256
    仍由真实 Bash 和 sha256sum 判定。
    """
    bash = _bash_executable()
    if bash is None:
        pytest.skip("Bash is required to verify trusted runner archive selection")

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    filename = "actions-runner-linux-x64-2.336.0.tar.gz"
    sealed_archive = cache_dir / f"sealed-{filename}"
    trusted_content = b"trusted-toolchain-archive\n"
    if cache_kind == "file":
        sealed_archive.write_bytes(trusted_content)
    elif cache_kind == "directory":
        sealed_archive.mkdir()
    elif cache_kind == "symlink":
        target = cache_dir / "symlink-target.tar.gz"
        target.write_bytes(trusted_content)
        try:
            sealed_archive.symlink_to(target)
        except OSError as error:
            pytest.skip(f"Current platform cannot create a file symlink: {error}")
    elif cache_kind != "missing":
        raise AssertionError(f"Unsupported test cache kind: {cache_kind}")

    network_log = tmp_path / "network.log"
    extraction_log = tmp_path / "extraction.log"
    installer_source = (ROOTLESS_DIR / "install-runner.sh").read_text(encoding="utf-8")
    archive_function = _extract_bash_function(installer_source, "prepare_verified_archive")
    url = "https://github.com/actions/runner/releases/download/v2.336.0/actions-runner-linux-x64-2.336.0.tar.gz"
    probe = (
        "set -Eeuo pipefail\n"
        "fail() { printf 'ERROR: %s\\n' \"$*\" >&2; exit 71; }\n"
        "stat() {\n"
        "  case $2 in\n"
        "    %u) printf '%s\\n' \"${FAKE_ARCHIVE_OWNER:?}\" ;;\n"
        "    %a)\n"
        '      if [[ $3 == "$cache_dir" ]]; then\n'
        "        printf '%s\\n' \"${FAKE_CACHE_MODE:?}\"\n"
        "      else\n"
        "        printf '%s\\n' \"${FAKE_ARCHIVE_MODE:?}\"\n"
        "      fi\n"
        "      ;;\n"
        "    *) return 64 ;;\n"
        "  esac\n"
        "}\n"
        "curl() {\n"
        "  local output= url=${!#}\n"
        "  while (($#)); do\n"
        "    if [[ $1 == --output ]]; then output=$2; shift 2; else shift; fi\n"
        "  done\n"
        '  printf \'%s\\n\' "$url" >>"${FAKE_NETWORK_LOG:?}"\n'
        "  printf 'trusted-toolchain-archive\\n' >\"$output\"\n"
        "}\n"
        f"cache_dir='{_to_bash_path(cache_dir)}'\n"
        f"{archive_function}\n"
        f"prepare_verified_archive runner '{filename}' '{url}' '{expected_digest}'\n"
        "printf 'entered-extraction\\n' >>\"${FAKE_EXTRACTION_LOG:?}\"\n"
        'printf \'selected:%s\\n\' "$(basename -- "$archive")"\n'
    )
    environment = os.environ.copy()
    environment["FAKE_ARCHIVE_OWNER"] = owner_uid
    environment["FAKE_CACHE_MODE"] = cache_mode
    environment["FAKE_ARCHIVE_MODE"] = archive_mode
    environment["FAKE_NETWORK_LOG"] = _to_bash_path(network_log)
    environment["FAKE_EXTRACTION_LOG"] = _to_bash_path(extraction_log)
    result = subprocess.run(
        [bash, "--noprofile", "--norc", "-c", probe],
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    return result, sealed_archive, network_log, extraction_log


def _run_existing_directory_check(
    tmp_path: Path,
    *,
    path_kind: str,
    owner_uid: str = "1004",
    directory_mode: str = "700",
) -> subprocess.CompletedProcess[str]:
    """受控执行既有目录安全检查，不依赖 Windows 实际 UID。"""
    bash = _bash_executable()
    if bash is None:
        pytest.skip("Bash is required to verify existing directory security")

    candidate = tmp_path / "candidate"
    if path_kind == "directory":
        candidate.mkdir()
    elif path_kind == "file":
        candidate.write_text("not-a-directory\n", encoding="utf-8")
    elif path_kind == "symlink":
        target = tmp_path / "target"
        target.mkdir()
        try:
            candidate.symlink_to(target, target_is_directory=True)
        except OSError as error:
            pytest.skip(f"Current platform cannot create a directory symlink: {error}")
    else:
        raise AssertionError(f"Unsupported path kind: {path_kind}")

    installer_source = (ROOTLESS_DIR / "install-runner.sh").read_text(encoding="utf-8")
    directory_function = _extract_bash_function(installer_source, "check_existing_directory")
    probe = (
        "set -Eeuo pipefail\n"
        "fail() { printf 'ERROR: %s\\n' \"$*\" >&2; exit 71; }\n"
        "stat() {\n"
        "  case $2 in\n"
        "    %u) printf '%s\\n' \"${FAKE_DIRECTORY_OWNER:?}\" ;;\n"
        "    %a) printf '%s\\n' \"${FAKE_DIRECTORY_MODE:?}\" ;;\n"
        "    *) return 64 ;;\n"
        "  esac\n"
        "}\n"
        f"{directory_function}\n"
        f"check_existing_directory '{_to_bash_path(candidate)}'\n"
    )
    environment = os.environ.copy()
    environment["FAKE_DIRECTORY_OWNER"] = owner_uid
    environment["FAKE_DIRECTORY_MODE"] = directory_mode
    return subprocess.run(
        [bash, "--noprofile", "--norc", "-c", probe],
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def test_existing_secure_directory_is_accepted(tmp_path: Path) -> None:
    """UID 1004 且无组/其他写权限的真实目录允许继续。"""
    result = _run_existing_directory_check(tmp_path, path_kind="directory")
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("path_kind", "owner_uid", "directory_mode"),
    [
        ("directory", "2000", "700"),
        ("directory", "1004", "720"),
        ("directory", "1004", "707"),
        ("file", "1004", "700"),
        ("symlink", "1004", "700"),
    ],
)
def test_insecure_existing_directory_is_rejected(
    tmp_path: Path,
    path_kind: str,
    owner_uid: str,
    directory_mode: str,
) -> None:
    """错误属主、可写 mode、非目录或链接都必须失败关闭。"""
    result = _run_existing_directory_check(
        tmp_path,
        path_kind=path_kind,
        owner_uid=owner_uid,
        directory_mode=directory_mode,
    )
    assert result.returncode != 0


def test_valid_sealed_runner_archive_is_selected_without_network(tmp_path: Path) -> None:
    """合法密封归档必须零网络返回原路径。"""
    digest = hashlib.sha256(b"trusted-toolchain-archive\n").hexdigest()
    result, sealed_archive, network_log, extraction_log = _run_verified_archive_selection(
        tmp_path,
        cache_kind="file",
        expected_digest=digest,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[-1] == f"selected:{sealed_archive.name}"
    assert not network_log.exists()
    assert extraction_log.read_text(encoding="utf-8") == "entered-extraction\n"


@pytest.mark.parametrize(
    ("cache_kind", "owner_uid", "digest"),
    [
        ("file", "1004", "0" * 64),
        ("file", "2000", hashlib.sha256(b"trusted-toolchain-archive\n").hexdigest()),
        ("directory", "1004", hashlib.sha256(b"trusted-toolchain-archive\n").hexdigest()),
        ("symlink", "1004", hashlib.sha256(b"trusted-toolchain-archive\n").hexdigest()),
    ],
)
def test_invalid_existing_sealed_archive_fails_closed_without_network(
    tmp_path: Path,
    cache_kind: str,
    owner_uid: str,
    digest: str,
) -> None:
    """密封路径存在但不可信时，禁止通过官方下载绕过失败。"""
    result, _, network_log, extraction_log = _run_verified_archive_selection(
        tmp_path,
        cache_kind=cache_kind,
        expected_digest=digest,
        owner_uid=owner_uid,
    )
    assert result.returncode != 0
    assert not network_log.exists()
    assert not extraction_log.exists()


@pytest.mark.parametrize(
    ("cache_mode", "archive_mode"),
    [("720", "600"), ("707", "600"), ("700", "620"), ("700", "602")],
)
def test_group_or_other_writable_cache_paths_fail_closed_without_network(
    tmp_path: Path,
    cache_mode: str,
    archive_mode: str,
) -> None:
    """缓存目录或密封文件可被组/其他用户写入时必须零网络硬停。"""
    digest = hashlib.sha256(b"trusted-toolchain-archive\n").hexdigest()
    result, _, network_log, extraction_log = _run_verified_archive_selection(
        tmp_path,
        cache_kind="file",
        expected_digest=digest,
        cache_mode=cache_mode,
        archive_mode=archive_mode,
    )
    assert result.returncode != 0
    assert not network_log.exists()
    assert not extraction_log.exists()


def test_missing_sealed_archive_downloads_only_the_manifest_official_url(tmp_path: Path) -> None:
    """只有密封归档不存在时才可从清单官方 URL 下载。"""
    digest = hashlib.sha256(b"trusted-toolchain-archive\n").hexdigest()
    result, sealed_archive, network_log, extraction_log = _run_verified_archive_selection(
        tmp_path,
        cache_kind="missing",
        expected_digest=digest,
    )
    assert result.returncode == 0, result.stderr
    assert not sealed_archive.exists()
    assert network_log.read_text(encoding="utf-8").splitlines() == [
        "https://github.com/actions/runner/releases/download/v2.336.0/actions-runner-linux-x64-2.336.0.tar.gz"
    ]
    assert extraction_log.read_text(encoding="utf-8") == "entered-extraction\n"


def test_official_download_checksum_mismatch_stops_before_extraction(tmp_path: Path) -> None:
    """官方下载摘要不符必须只请求一次官方 URL，且不得进入解压阶段。"""
    result, _, network_log, extraction_log = _run_verified_archive_selection(
        tmp_path,
        cache_kind="missing",
        expected_digest="0" * 64,
    )
    assert result.returncode != 0
    assert network_log.read_text(encoding="utf-8").splitlines() == [
        "https://github.com/actions/runner/releases/download/v2.336.0/actions-runner-linux-x64-2.336.0.tar.gz"
    ]
    assert not extraction_log.exists()
