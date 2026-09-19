"""双服务器 staging 入口资产的失败关闭契约测试。"""

import configparser

from _support import SOURCE_ROOT

ROOTLESS_OVERLAY = SOURCE_ROOT / "compose" / "docker-compose.rootless-staging.yml"
ROOTLESS_TUNNEL_NGINX = SOURCE_ROOT / "deploy" / "nginx" / "nginx-tunnel.conf"
ROOTLESS_DIR = SOURCE_ROOT / "deploy" / "staging" / "rootless"
TUNNEL_UNIT = ROOTLESS_DIR / "systemd" / "user" / "crm-staging-tunnel.service"
TUNNEL_INSTALLER = ROOTLESS_DIR / "install-reverse-tunnel.sh"
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
        'systemctl --user show "$UNIT_NAME" --property=MainPID --value',
        "/proc/$main_pid/cmdline",
    ):
        assert required in business
    assert 'systemctl --user enable --now "$UNIT_NAME"' not in business
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
