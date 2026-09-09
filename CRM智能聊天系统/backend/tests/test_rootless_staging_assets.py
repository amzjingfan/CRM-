"""Rootless 主机资产静态契约；真实 Bash/端口/失败注入由 Ubuntu Task 8 验证。"""

import configparser
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ROOTLESS_DIR = PROJECT_ROOT / "deploy" / "staging" / "rootless"
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
