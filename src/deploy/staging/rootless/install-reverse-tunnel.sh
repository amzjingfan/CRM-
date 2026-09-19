#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
export PATH=/usr/sbin:/usr/bin:/sbin:/bin

fail() { echo "ERROR: $*" >&2; exit 1; }

EXPECTED_USER=crmdeploy
EXPECTED_UID=1004
EXPECTED_HOME=/home/crmdeploy
PUBLIC_GATEWAY=38.55.145.52
EXPECTED_HOST_FINGERPRINT=SHA256:PPupiUWQYpCvIzPtolycQELbt5o49rqp1Hu1RHHE3XU
SECRET_DIR=/home/crmdeploy/secrets/tunnel
PRIVATE_KEY="$SECRET_DIR/id_ed25519"
KNOWN_HOSTS="$SECRET_DIR/known_hosts"
UNIT_NAME=crm-staging-tunnel.service

[[ $(id -un) == "$EXPECTED_USER" && $(id -u) == "$EXPECTED_UID" ]] ||
    fail "Run as crmdeploy UID 1004"
[[ ${HOME:-} == "$EXPECTED_HOME" ]] || fail "Unexpected HOME"
[[ $(getent passwd "$EXPECTED_USER" | cut -d: -f6) == "$EXPECTED_HOME" ]] ||
    fail "Unexpected account home"
[[ $(realpath -e "$EXPECTED_HOME") == "$EXPECTED_HOME" ]] || fail "Home must not be a symlink"

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
UNIT_SOURCE="$script_dir/systemd/user/$UNIT_NAME"
UNIT_DIR="$EXPECTED_HOME/.config/systemd/user"
UNIT_TARGET="$UNIT_DIR/$UNIT_NAME"

check_owned_directory() {
    local directory=$1 mode
    [[ -d "$directory" && ! -L "$directory" ]] || fail "Required directory is missing or linked"
    [[ $(stat -c %u "$directory") == "$EXPECTED_UID" ]] || fail "Unexpected directory owner"
    mode=$(stat -c %a "$directory") || fail "Cannot inspect directory permissions"
    (( (8#$mode & 0022) == 0 )) || fail "Directory must not be group/other writable"
}

check_secret_file() {
    local secret_file=$1 mode
    [[ -f "$secret_file" && ! -L "$secret_file" ]] || fail "Required secret file is missing or linked"
    [[ $(stat -c %u "$secret_file") == "$EXPECTED_UID" ]] || fail "Unexpected secret owner"
    mode=$(stat -c %a "$secret_file") || fail "Cannot inspect secret permissions"
    [[ $mode == 600 ]] || fail "Secret files must use mode 0600"
}

check_owned_directory "$EXPECTED_HOME"
check_owned_directory "$SECRET_DIR"
[[ $(stat -c %a "$SECRET_DIR") == 700 ]] || fail "Tunnel secret directory must use mode 0700"
check_secret_file "$PRIVATE_KEY"
check_secret_file "$KNOWN_HOSTS"
[[ -s "$PRIVATE_KEY" && -s "$KNOWN_HOSTS" ]] || fail "Tunnel identity files must not be empty"

# 验证私钥格式和固定网关 Ed25519 指纹，不自动接受或替换远端主机身份。
ssh-keygen -y -f "$PRIVATE_KEY" >/dev/null || fail "Invalid tunnel private key"
mapfile -t pinned_keys < <(
    ssh-keygen -F "$PUBLIC_GATEWAY" -f "$KNOWN_HOSTS" 2>/dev/null |
        awk '$1 !~ /^#/ && $2 == "ssh-ed25519" { print }'
)
[[ ${#pinned_keys[@]} -eq 1 ]] || fail "Pinned public gateway Ed25519 host key is missing or ambiguous"
actual_fingerprint=$(printf '%s\n' "${pinned_keys[0]}" | ssh-keygen -lf - -E sha256 | awk 'NR == 1 { print $2 }')
[[ $actual_fingerprint == "$EXPECTED_HOST_FINGERPRINT" ]] || fail "Pinned public gateway host fingerprint differs"

[[ -f "$UNIT_SOURCE" && ! -L "$UNIT_SOURCE" ]] || fail "Tunnel unit template is missing or linked"
systemd-analyze --user verify "$UNIT_SOURCE" || fail "Tunnel unit validation failed"

mkdir -p -- "$UNIT_DIR"
check_owned_directory "$EXPECTED_HOME/.config"
check_owned_directory "$EXPECTED_HOME/.config/systemd"
check_owned_directory "$UNIT_DIR"
[[ ! -L "$UNIT_TARGET" ]] || fail "Tunnel unit target must not be a symlink"
install -m 0600 "$UNIT_SOURCE" "$UNIT_TARGET"

export XDG_RUNTIME_DIR=/run/user/1004
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1004/bus
systemctl --user daemon-reload
systemctl --user enable "$UNIT_NAME"
# enable --now 不会重启已活动的旧 unit；必须显式 restart 才能从 GitLab 目标切到 CRM。
systemctl --user restart "$UNIT_NAME"
systemctl --user is-enabled --quiet "$UNIT_NAME" || fail "Tunnel service is not enabled"
systemctl --user is-active --quiet "$UNIT_NAME" || fail "Tunnel service is not active"
main_pid=$(systemctl --user show "$UNIT_NAME" --property=MainPID --value)
[[ $main_pid =~ ^[1-9][0-9]*$ && -r "/proc/$main_pid/cmdline" ]] || fail "Tunnel service has no readable running process"
running_command=$(tr '\0' ' ' <"/proc/$main_pid/cmdline")
[[ $running_command == *"/usr/bin/ssh -NT"* ]] || fail "Tunnel service is not running the reviewed SSH client"
[[ $running_command == *"-R 127.0.0.1:18080:127.0.0.1:18081"* ]] || fail "Running tunnel still targets an unreviewed port"
echo "CRM staging reverse tunnel is enabled and restarted"
