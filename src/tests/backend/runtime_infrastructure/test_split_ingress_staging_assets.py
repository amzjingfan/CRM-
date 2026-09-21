"""双服务器 staging 入口资产的失败关闭契约测试。"""

import configparser
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

import pytest
from _support import SOURCE_ROOT

ROOTLESS_OVERLAY = SOURCE_ROOT / "compose" / "docker-compose.rootless-staging.yml"
ROOTLESS_TUNNEL_NGINX = SOURCE_ROOT / "deploy" / "nginx" / "nginx-tunnel.conf"
ROOTLESS_DIR = SOURCE_ROOT / "deploy" / "staging" / "rootless"
TUNNEL_UNIT = ROOTLESS_DIR / "systemd" / "user" / "crm-staging-tunnel.service"
TUNNEL_INSTALLER = ROOTLESS_DIR / "install-reverse-tunnel.sh"
PROCESS_WAITER = ROOTLESS_DIR / "wait-for-reviewed-process.sh"
PUBLIC_ACCOUNT_INSTALLER = ROOTLESS_DIR / "install-public-tunnel-account.sh"
PUBLIC_NGINX_DIR = ROOTLESS_DIR / "public-nginx"
PUBLIC_HTTP_VHOST = PUBLIC_NGINX_DIR / "staging.overselfx.com-http.conf"
PUBLIC_HTTPS_VHOST = PUBLIC_NGINX_DIR / "staging.overselfx.com.conf"
SPLIT_INGRESS_VERIFIER = ROOTLESS_DIR / "verify-split-ingress.sh"


def test_rootless_overlay_exposes_only_split_ingress_http_port() -> None:
    """错误端口或 TLS 发布会再次把 CRM 与 GitLab/宿主机证书耦合。"""
    source = ROOTLESS_OVERLAY.read_text(encoding="utf-8")

    assert '"127.0.0.1:18081:80"' in source
    assert "10080" not in source
    assert "10443" not in source
    assert "nginx-tunnel.conf" in source


def test_inner_proxy_preserves_https_origin_without_terminating_tls() -> None:
    """内层代理重复终止 TLS 或相信客户端协议头会破坏单一信任边界。"""
    source = ROOTLESS_TUNNEL_NGINX.read_text(encoding="utf-8")

    assert "listen 80 default_server" in source
    assert "listen 443" not in source
    assert "ssl_certificate" not in source
    assert "proxy_set_header X-Forwarded-Proto https" in source
    assert "proxy_buffering off" in source
    assert "proxy_request_buffering off" in source
    assert '"uri":"$uri"' in source
    assert "$request_uri" not in source

    webhook_location = source.split("location ^~ /v1/webhooks/", 1)[1].split("location /v1/", 1)[0]
    assert "error_log /dev/null;" in webhook_location
    assert "proxy_pass http://backend:8000;" in webhook_location
    assert "proxy_set_header X-Forwarded-Proto https;" in webhook_location


def test_reverse_tunnel_is_loopback_only_and_targets_crm_port() -> None:
    """隧道必须避开 GitLab 端口，并在创建监听失败时立即退出。"""
    unit = configparser.ConfigParser(interpolation=None, strict=False)
    unit.read_string(TUNNEL_UNIT.read_text(encoding="utf-8"))
    command = unit["Service"]["ExecStart"]

    assert "/usr/bin/ssh -NT" in command
    assert "-R 127.0.0.1:18080:127.0.0.1:18081" in command
    assert "ExitOnForwardFailure=yes" in command
    assert "StrictHostKeyChecking=yes" in command
    assert "IdentitiesOnly=yes" in command
    assert "StrictHostKeyChecking=no" not in command
    assert "crm-tunnel@38.55.145.52" in command
    assert unit["Service"]["Restart"] == "always"
    assert unit["Service"]["RestartSec"] == "5"


def test_tunnel_installers_preserve_account_and_key_boundaries() -> None:
    """安装器必须拒绝弱权限、身份漂移和可复用为交互登录的密钥。"""
    business = TUNNEL_INSTALLER.read_text(encoding="utf-8")
    public = PUBLIC_ACCOUNT_INSTALLER.read_text(encoding="utf-8")

    for required in (
        "set -Eeuo pipefail",
        "EXPECTED_UID=1004",
        "SECRET_DIR=/home/crmdeploy/secrets/tunnel",
        'PRIVATE_KEY="$SECRET_DIR/id_ed25519"',
        'KNOWN_HOSTS="$SECRET_DIR/known_hosts"',
        "ssh-keygen -F",
        "SHA256:PPupiUWQYpCvIzPtolycQELbt5o49rqp1Hu1RHHE3XU",
        "systemd-analyze --user verify",
        'systemctl --user enable "$UNIT_NAME"',
        'systemctl --user restart "$UNIT_NAME"',
        '"systemd:$UNIT_NAME" /proc 20 1',
    ):
        assert required in business
    assert 'systemctl --user enable --now "$UNIT_NAME"' not in business
    assert business.index("export XDG_RUNTIME_DIR=/run/user/1004") < business.index(
        'systemd-analyze --user verify "$UNIT_SOURCE"'
    )
    assert business.index("export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1004/bus") < business.index(
        'systemd-analyze --user verify "$UNIT_SOURCE"'
    )
    assert business.index("systemctl --user daemon-reload") < business.index('systemctl --user restart "$UNIT_NAME"')
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
        "Existing authorized_keys differs from the reviewed tunnel key",
    ):
        assert required in public
    assert "sudo" not in public
    assert "docker" not in public
    assert "GatewayPorts yes" not in public


def _ssh_cmdline(*overrides: str) -> bytes:
    argv = [
        "/usr/bin/ssh",
        "-NT",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "ExitOnForwardFailure=yes",
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        "ServerAliveInterval=30",
        "-o",
        "ServerAliveCountMax=3",
        "-o",
        "UserKnownHostsFile=/home/crmdeploy/secrets/tunnel/known_hosts",
        "-i",
        "/home/crmdeploy/secrets/tunnel/id_ed25519",
        "-R",
        "127.0.0.1:18080:127.0.0.1:18081",
        "crm-tunnel@38.55.145.52",
    ]
    argv[: len(overrides)] = overrides
    return b"\0".join(item.encode() for item in argv) + b"\0"


def test_process_waiter_reloads_pid_until_reviewed_tunnel_command(tmp_path: Path) -> None:
    """服务自动重启换 PID 后必须重新取 MainPID，不得永久盯住旧进程。"""
    assert PROCESS_WAITER.is_file(), f"missing process waiter: {PROCESS_WAITER}"
    if os.name == "nt":
        pytest.skip("process waiter behavior requires a POSIX bash runtime")
    bash = shutil.which("bash")
    assert bash is not None, "bash is required for process waiter behavior tests"

    proc_root = tmp_path / "proc"
    old_process = proc_root / "1001"
    new_process = proc_root / "1002"
    old_process.mkdir(parents=True)
    new_process.mkdir()
    (old_process / "cmdline").write_bytes(_ssh_cmdline("/usr/bin/ssh", "-NT", "-o", "BatchMode=no"))
    (new_process / "cmdline").write_bytes(_ssh_cmdline())
    pid_file = tmp_path / "main-pid"
    pid_file.write_text("1001\n", encoding="ascii")

    def publish_reviewed_command() -> None:
        time.sleep(0.12)
        pid_file.write_text("1002\n", encoding="ascii")

    started = time.monotonic()
    publisher = threading.Thread(target=publish_reviewed_command)
    publisher.start()
    result = subprocess.run(
        [
            bash,
            str(PROCESS_WAITER),
            f"file:{pid_file}",
            str(proc_root),
            "30",
            "0.02",
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=5,
    )
    publisher.join(timeout=1)

    assert result.returncode == 0, result.stderr
    assert time.monotonic() - started >= 0.1


@pytest.mark.parametrize(
    "cmdline",
    [
        _ssh_cmdline("/bin/not-ssh", "/usr/bin/ssh -NT"),
        _ssh_cmdline(
            "/usr/bin/ssh",
            "-NT",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "ExitOnForwardFailure=yes",
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            "ServerAliveInterval=30",
            "-o",
            "ServerAliveCountMax=3",
            "-o",
            "UserKnownHostsFile=/home/crmdeploy/secrets/tunnel/known_hosts",
            "-i",
            "/home/crmdeploy/secrets/tunnel/id_ed25519",
            "-R",
            "127.0.0.1:18080:127.0.0.1:180810",
        ),
    ],
)
def test_process_waiter_rejects_argv_substring_lookalikes(tmp_path: Path, cmdline: bytes) -> None:
    """只允许逐个 argv 完全匹配，禁止可执行文件或端口子串伪装。"""
    source = PROCESS_WAITER.read_text(encoding="utf-8")
    assert "mapfile -d '' -t running_argv" in source
    assert "expected_argv" in source

    if os.name == "nt":
        pytest.skip("process waiter behavior requires a POSIX bash runtime")
    bash = shutil.which("bash")
    assert bash is not None, "bash is required for process waiter behavior tests"

    proc_root = tmp_path / "proc"
    process = proc_root / "2001"
    process.mkdir(parents=True)
    (process / "cmdline").write_bytes(cmdline)
    pid_file = tmp_path / "main-pid"
    pid_file.write_text("2001\n", encoding="ascii")

    result = subprocess.run(
        [bash, str(PROCESS_WAITER), f"file:{pid_file}", str(proc_root), "1", "0"],
        capture_output=True,
        check=False,
        text=True,
        timeout=5,
    )

    assert result.returncode != 0


def test_public_http_vhost_is_acme_only_and_fail_closed_before_tls() -> None:
    """证书切换前，除 ACME 文件外的请求必须保持 503。"""
    source = PUBLIC_HTTP_VHOST.read_text(encoding="utf-8")

    assert "listen 80" in source
    assert "server_name staging.overselfx.com;" in source
    assert "location ^~ /.well-known/acme-challenge/" in source
    assert "/www/wwwroot/staging.overselfx.com" in source
    assert "return 503" in source
    assert "proxy_pass" not in source
    assert "ssl_certificate" not in source


def test_public_vhost_never_targets_gitlab_or_private_host() -> None:
    """正式公网入口只能把通过 TLS 的请求交给本机回环隧道。"""
    source = PUBLIC_HTTPS_VHOST.read_text(encoding="utf-8")

    assert "server_name staging.overselfx.com;" in source
    assert "ssl_protocols TLSv1.2 TLSv1.3;" in source
    assert "/www/server/panel/vhost/cert/staging.overselfx.com/fullchain.pem" in source
    assert "/www/server/panel/vhost/cert/staging.overselfx.com/privkey.pem" in source
    assert "proxy_pass http://127.0.0.1:18080" in source
    assert "proxy_set_header Host staging.overselfx.com" in source
    assert "proxy_set_header X-Forwarded-Proto https" in source
    assert "proxy_buffering off" in source
    assert "proxy_request_buffering off" in source
    assert "$request_uri" not in source
    assert "192.168.110.210" not in source
    assert ":10080" not in source


def test_public_vhost_replaces_inner_security_headers_once() -> None:
    """客户端只能看到公网 TLS 边界定义的一组安全头，不得与内层值重复或冲突。"""
    source = PUBLIC_HTTPS_VHOST.read_text(encoding="utf-8")
    https_server_preamble = source.rsplit("server {", 1)[1].split("location =", 1)[0]

    for header in (
        "Strict-Transport-Security",
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
    ):
        assert f"proxy_hide_header {header};" in https_server_preamble


def test_split_ingress_verifier_checks_public_and_loopback_boundaries() -> None:
    """全链路验证必须拒绝错误 DNS、证书、监听、GitLab 响应和不安全 TLS。"""
    source = SPLIT_INGRESS_VERIFIER.read_text(encoding="utf-8")

    for required in (
        "set -Eeuo pipefail",
        "1.1.1.1",
        "8.8.8.8",
        "openssl x509 -checkhost",
        "127.0.0.1:18080",
        "127.0.0.1:18081",
        "/healthz",
        "/v1/health",
        "/v1/health/ready",
        "/users/sign_in",
    ):
        assert required in source
    assert "x-gitlab-" in source.lower()
    assert "curl -k" not in source
    assert "--insecure" not in source
    assert "privkey.pem" not in source
