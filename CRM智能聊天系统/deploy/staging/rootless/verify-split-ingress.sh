#!/usr/bin/env bash
set -Eeuo pipefail
# 拒绝调用者开启 trace，避免 CSRF Cookie 在命令跟踪中泄露。
[[ $- != *x* ]] || exit 1
umask 077
export PATH=/usr/sbin:/usr/bin:/sbin:/bin

fail() { echo "ERROR: $*" >&2; exit 1; }

DOMAIN=staging.overselfx.com
EXPECTED_IP=38.55.145.52
TUNNEL_LISTENER=127.0.0.1:18080
[[ $# -eq 2 ]] || fail "Usage: verify-split-ingress.sh COOKIE_JAR SESSION_UUID"
cookie_jar=$1
session_id=$2
[[ $session_id =~ ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89aAbB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$ ]] ||
    fail "SESSION_UUID is invalid"
[[ -f "$cookie_jar" && ! -L "$cookie_jar" && -s "$cookie_jar" ]] ||
    fail "Cookie jar must be a non-empty regular file"
cookie_mode=$(stat -c %a "$cookie_jar") || fail "Cannot inspect cookie jar permissions"
[[ $cookie_mode == 600 ]] || fail "Cookie jar must use mode 0600"
[[ $(stat -c %u "$cookie_jar") == $(id -u) ]] || fail "Unexpected cookie jar owner"

for command in curl dig openssl ss awk grep sort stat id; do
    command -v "$command" >/dev/null || fail "Required command is missing: $command"
done

# 三个独立公共递归解析器必须给出相同的固定入口地址。
for resolver in 1.1.1.1 8.8.8.8 9.9.9.9; do
    answers=$(dig +time=3 +tries=1 +short A "$DOMAIN" "@$resolver") ||
        fail "DNS lookup failed"
    unique_answers=$(printf '%s\n' "$answers" | awk 'NF' | sort -u)
    [[ $unique_answers == "$EXPECTED_IP" ]] || fail "DNS A record differs from the approved gateway"
done

# 本脚本必须在公网服务器运行；远程转发端口只能出现在 IPv4 回环地址。
listeners=$(ss -H -ltn 'sport = :18080') || fail "Cannot inspect tunnel listener"
listener_count=$(awk -v expected="$TUNNEL_LISTENER" '
    $4 != expected { exit 2 }
    { count++ }
    END { if (count != 1) exit 3; print count }
' <<<"$listeners") || fail "Unexpected tunnel listener"
[[ $listener_count == 1 ]] || fail "Unexpected tunnel listener"

certificate_file=$(mktemp)
headers_file=$(mktemp)
payload_file=$(mktemp)
csrf_token=
cleanup() {
    unset csrf_token
    rm -f -- "$certificate_file" "$headers_file" "$payload_file"
}
trap cleanup EXIT

openssl s_client -connect "$DOMAIN:443" -servername "$DOMAIN" </dev/null 2>/dev/null |
    openssl x509 -outform PEM >"$certificate_file" || fail "Cannot retrieve public certificate"
openssl x509 -checkhost "$DOMAIN" -in "$certificate_file" -noout >/dev/null || fail "Certificate SAN mismatch"
openssl x509 -in "$certificate_file" -noout -checkend 604800 >/dev/null || fail "Certificate expires within seven days"

http_code=$(curl --silent --show-error --output /dev/null --dump-header "$headers_file" --write-out '%{http_code}' \
    --max-redirs 0 --connect-timeout 5 --max-time 15 "http://$DOMAIN/healthz") || fail "HTTP redirect check failed"
[[ $http_code == 301 ]] || fail "HTTP does not redirect to HTTPS"
grep -Eiq '^location:[[:space:]]*https://staging\.overselfx\.com/healthz[[:space:]]*$' "$headers_file" ||
    fail "Unexpected HTTP redirect target"
for path in /healthz /v1/health /v1/health/ready; do
    curl --fail --silent --show-error --output /dev/null --proto '=https' --tlsv1.2 \
        --connect-timeout 5 --max-time 15 "https://$DOMAIN$path" || fail "HTTPS health check failed"
done

csrf_token=$(awk '$6 == "crm_csrf_token" { value=$7 } END { print value }' "$cookie_jar")
[[ $csrf_token =~ ^[A-Za-z0-9._~-]+$ ]] || fail "Valid CSRF cookie is missing"
printf '{"session_id":"%s"}\n' "$session_id" >"$payload_file"

# CSRF 值经 curl 标准输入传入，不出现在进程参数或输出；响应正文直接丢弃。
set +e
http_code=$(curl --silent --show-error --output /dev/null --dump-header "$headers_file" \
    --write-out '%{http_code}' --proto '=https' --tlsv1.2 --connect-timeout 5 --max-time 15 \
    --request POST --cookie "$cookie_jar" --header 'Content-Type: application/json' \
    --data-binary "@$payload_file" --config <(printf 'header = "X-CSRF-Token: %s"\n' "$csrf_token") \
    "https://$DOMAIN/v1/chat/query")
curl_exit=$?
set -e
(( curl_exit == 0 || curl_exit == 28 )) || fail "SSE request failed"
[[ $http_code == 200 ]] || fail "SSE endpoint did not return HTTP 200"
grep -Eiq '^content-type:[[:space:]]*text/event-stream([[:space:]]*;|[[:space:]]*$)' "$headers_file" ||
    fail "SSE response has the wrong content type"

echo "Split-ingress DNS, TLS, loopback tunnel, health, redirect and SSE checks passed"
