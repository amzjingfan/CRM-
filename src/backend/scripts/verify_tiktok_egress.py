"""从应用使用的 SOCKS5H 路径验证 TikTok 公网出口。"""

from __future__ import annotations

import ipaddress
import json
import os
import sys

import httpx

CHECK_IP_URL = "https://checkip.amazonaws.com"
FIXED_PROXY_URL = "socks5h://tiktok-egress:1080"
SCHEMA_VERSION = 1


def parse_observed_egress(configured_ip: str, payload: str) -> str:
    """只接受 checkip 返回的一个 IP，并要求与部署配置完全一致。"""
    candidate = payload
    if candidate.endswith("\r\n"):
        candidate = candidate[:-2]
    elif candidate.endswith("\n"):
        candidate = candidate[:-1]

    configured = ipaddress.ip_address(configured_ip)
    observed = ipaddress.ip_address(candidate)
    if observed != configured:
        raise ValueError(f"Observed egress {observed} does not match configured IP")
    return str(observed)


def main() -> int:
    """验证固定代理出口；任何配置、网络或内容异常都失败关闭。"""
    try:
        configured_ip = os.environ.get("TIKTOK_EGRESS_IP")
        proxy_url = os.environ.get("TIKTOK_EGRESS_PROXY_URL")
        if not configured_ip or not proxy_url:
            raise ValueError("Required TikTok egress configuration is missing")
        if proxy_url != FIXED_PROXY_URL:
            raise ValueError("TikTok egress proxy does not match the fixed service address")

        with httpx.Client(proxy=proxy_url, trust_env=False, timeout=10) as client:
            response = client.get(CHECK_IP_URL)
            response.raise_for_status()
        observed_ip = parse_observed_egress(configured_ip, response.text)
    except (ValueError, httpx.HTTPError):
        print("TikTok egress verification failed", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "status": "ok",
                "observed_ip": observed_ip,
                "configured_ip": str(ipaddress.ip_address(configured_ip)),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
