#!/usr/bin/env bash
set -Eeuo pipefail
[[ $- != *x* ]] || exit 1
umask 077
export PATH=/usr/sbin:/usr/bin:/sbin:/bin

fail() { echo "ERROR: $*" >&2; exit 1; }

DOMAIN=staging.overselfx.com
EXPECTED_IP=38.55.145.52

check_loopback_listener() {
    local port=$1 expected=$2 listeners listener_count
    listeners=$(ss -H -ltn "sport = :$port") || fail "Cannot inspect loopback listener"
    listener_count=$(awk -v expected="$expected" '
        $4 != expected { exit 2 }
        { count++ }
        END { if (count != 1) exit 3; print count }
    ' <<<"$listeners") || fail "Unexpected loopback listener"
    [[ $listener_count == 1 ]] || fail "Unexpected loopback listener"
}

[[ $# -eq 1 ]] || fail "Usage: verify-split-ingress.sh public|business"
role=$1
case "$role" in
    business)
        for command in ss awk; do
            command -v "$command" >/dev/null || fail "Required command is missing: $command"
        done
        check_loopback_listener 18081 127.0.0.1:18081
        echo "Business-host loopback listener is valid"
        exit 0
        ;;
    public) ;;
    *) fail "Role must be public or business" ;;
esac

for command in curl dig openssl ss awk grep sort mktemp; do
    command -v "$command" >/dev/null || fail "Required command is missing: $command"
done

for resolver in 1.1.1.1 8.8.8.8; do
    answers=$(dig +time=3 +tries=1 +short A "$DOMAIN" "@$resolver") || fail "DNS lookup failed"
    unique_answers=$(printf '%s\n' "$answers" | awk 'NF' | sort -u)
    [[ $unique_answers == "$EXPECTED_IP" ]] || fail "DNS A record differs from the approved gateway"
done

check_loopback_listener 18080 127.0.0.1:18080

certificate_file=$(mktemp)
headers_file=$(mktemp)
payload_file=$(mktemp)
cleanup() { rm -f -- "$certificate_file" "$headers_file" "$payload_file"; }
trap cleanup EXIT

openssl s_client -connect "$DOMAIN:443" -servername "$DOMAIN" -verify_return_error </dev/null 2>/dev/null |
    openssl x509 -outform PEM >"$certificate_file" || fail "Cannot verify public certificate chain"
openssl x509 -checkhost "$DOMAIN" -in "$certificate_file" -noout >/dev/null || fail "Certificate SAN mismatch"
openssl x509 -in "$certificate_file" -noout -checkend 604800 >/dev/null || fail "Certificate expires within seven days"

http_code=$(curl --silent --show-error --output "$payload_file" --dump-header "$headers_file" --write-out '%{http_code}' \
    --max-redirs 0 --connect-timeout 5 --max-time 15 "http://$DOMAIN/") || fail "HTTP redirect check failed"
[[ $http_code == 301 ]] || fail "HTTP does not redirect to HTTPS"
grep -Eiq '^location:[[:space:]]*https://staging\.overselfx\.com/[[:space:]]*$' "$headers_file" ||
    fail "Unexpected HTTP redirect target"

for path in / /healthz /v1/health /v1/health/ready; do
    http_code=$(curl --fail --silent --show-error --output "$payload_file" --dump-header "$headers_file" \
        --write-out '%{http_code}' --proto '=https' --tlsv1.2 --connect-timeout 5 --max-time 20 \
        "https://$DOMAIN$path") || fail "HTTPS endpoint check failed"
    [[ $http_code == 200 ]] || fail "HTTPS endpoint returned a non-success status"
    if grep -Eiq '^(x-gitlab-|location:.*?/users/sign_in)' "$headers_file" ||
        grep -Fq '/users/sign_in' "$payload_file"; then
        fail "GitLab response detected at the CRM staging entry"
    fi
done

echo "Split-ingress DNS, TLS, listeners, redirect and HTTPS checks passed"
