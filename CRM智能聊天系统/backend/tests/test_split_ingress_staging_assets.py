"""双服务器 staging 入口资产契约测试。"""

import configparser
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ROOTLESS_OVERLAY = PROJECT_ROOT / "docker-compose.rootless-staging.yml"
ROOTLESS_TUNNEL_NGINX = PROJECT_ROOT / "deploy" / "nginx" / "nginx-tunnel.conf"
ROOTLESS_DIR = PROJECT_ROOT / "deploy" / "staging" / "rootless"
TUNNEL_USER_UNIT = ROOTLESS_DIR / "systemd" / "user" / "crm-staging-tunnel.service"
TUNNEL_INSTALLER = ROOTLESS_DIR / "install-reverse-tunnel.sh"
PUBLIC_ACCOUNT_INSTALLER = ROOTLESS_DIR / "install-public-tunnel-account.sh"


def test_rootless_overlay_exposes_only_tunnel_http_port() -> None:
    """Rootless 入口只能通过业务服务器回环 HTTP 端口交给 SSH 隧道。"""
    source = ROOTLESS_OVERLAY.read_text(encoding="utf-8")

    assert '"127.0.0.1:10080:80"' in source
    assert "10443" not in source
    assert "nginx-tunnel.conf" in source


def test_inner_proxy_preserves_https_origin_without_terminating_tls() -> None:
    """内层代理不得重复终止 TLS，并必须保持外部 HTTPS 安全语义。"""
    source = ROOTLESS_TUNNEL_NGINX.read_text(encoding="utf-8")

    assert "listen 80 default_server" in source
    assert "listen 443" not in source
    assert "ssl_certificate" not in source
    assert "proxy_set_header X-Forwarded-Proto https" in source
    assert "proxy_buffering off" in source
    assert "proxy_request_buffering off" in source
    assert "error_log /dev/null" in source
    assert '"uri":"$uri"' in source
    assert "$request_uri" not in source


def test_reverse_tunnel_unit_is_loopback_only_and_fail_closed() -> None:
    """隧道断线必须自动恢复，且远端监听不能暴露到公网网卡。"""
    unit = configparser.ConfigParser(interpolation=None, strict=False)
    unit.read_string(TUNNEL_USER_UNIT.read_text(encoding="utf-8"))
    command = unit["Service"]["ExecStart"]

    assert "/usr/bin/ssh -NT" in command
    assert "ExitOnForwardFailure=yes" in command
    assert "StrictHostKeyChecking=yes" in command
    assert "IdentitiesOnly=yes" in command
    assert "127.0.0.1:18080:127.0.0.1:10080" in command
    assert "crm-tunnel@38.55.145.52" in command
    assert unit["Service"]["Restart"] == "always"
    assert unit["Service"]["RestartSec"] == "5"


def test_tunnel_installers_preserve_identity_and_key_boundaries() -> None:
    """安装器必须拒绝弱权限、错误身份和可复用为 shell 的授权密钥。"""
    business = TUNNEL_INSTALLER.read_text(encoding="utf-8")
    public = PUBLIC_ACCOUNT_INSTALLER.read_text(encoding="utf-8")

    for required in (
        "set -Eeuo pipefail",
        "EXPECTED_UID=1004",
        "/home/crmdeploy/secrets/tunnel/id_ed25519",
        "/home/crmdeploy/secrets/tunnel/known_hosts",
        "ssh-keygen -F",
        "systemd-analyze --user verify",
        "systemctl --user enable --now crm-staging-tunnel.service",
    ):
        assert required in business
    assert "StrictHostKeyChecking=no" not in business

    for required in (
        "set -Eeuo pipefail",
        "crm-tunnel",
        "/home/crm-tunnel",
        'command="/usr/bin/false"',
        "restrict,port-forwarding",
        'permitlisten="127.0.0.1:18080"',
        "ssh-ed25519",
        "passwd --lock",
    ):
        assert required in public
    assert "sudo" not in public
    assert "docker" not in public
