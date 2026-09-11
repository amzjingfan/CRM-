"""双服务器 staging 入口资产契约测试。"""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ROOTLESS_OVERLAY = PROJECT_ROOT / "docker-compose.rootless-staging.yml"
ROOTLESS_TUNNEL_NGINX = PROJECT_ROOT / "deploy" / "nginx" / "nginx-tunnel.conf"


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
