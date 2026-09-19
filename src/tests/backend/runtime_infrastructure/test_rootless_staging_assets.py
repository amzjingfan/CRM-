"""Rootless 主机资产静态契约；真实 Bash/端口/失败注入由 Ubuntu Task 8 验证。"""

import configparser
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from _support import REPOSITORY_ROOT, SOURCE_ROOT

ROOTLESS_DIR = SOURCE_ROOT / "deploy" / "staging" / "rootless"
SYSTEMD_DIR = ROOTLESS_DIR / "systemd"


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


@pytest.mark.parametrize(
    "relative_path",
    [
        "install-entry-proxy.sh",
        "systemd/crm-staging-http.service",
        "systemd/crm-staging-http.socket",
        "systemd/crm-staging-https.service",
        "systemd/crm-staging-https.socket",
    ],
)
def test_legacy_same_host_entry_proxy_assets_are_not_active(relative_path: str) -> None:
    """旧同机 80/443 转发资产不能与 split-ingress 形成第二条可执行入口。"""
    assert not (ROOTLESS_DIR / relative_path).exists()


@pytest.mark.parametrize("extension", ["service", "socket"])
def test_systemd_units_have_lf_checkout_contract(extension: str) -> None:
    """固定 Git 检出换行，避免 Windows 资产与 Linux 已安装单元 cmp 不一致。"""
    attributes = (REPOSITORY_ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert f"*.{extension} text eol=lf" in attributes.splitlines()
    for unit in SYSTEMD_DIR.glob(f"*.{extension}"):
        assert b"\r" not in unit.read_bytes()


def test_evidence_parent_remains_writable_by_deployment_user() -> None:
    """主机取证不能夺走后续 crmdeploy 部署任务创建证据目录的权限。"""
    source = (ROOTLESS_DIR / "bootstrap-host.sh").read_text(encoding="utf-8")
    assert 'install -d -o 1004 -g 1004 -m 0750 "$evidence_root"' in source


@pytest.mark.parametrize(
    "name",
    ["bootstrap-host.sh", "install-public-tunnel-account.sh", "install-reverse-tunnel.sh", "verify-split-ingress.sh"],
)
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
