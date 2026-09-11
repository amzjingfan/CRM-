#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
export PATH=/usr/sbin:/usr/bin:/sbin:/bin

fail() { echo "ERROR: $*" >&2; exit 1; }

EXPECTED_USER=crmdeploy
EXPECTED_UID=1004
EXPECTED_HOME=/home/crmdeploy
SECRET_DIR=/home/crmdeploy/secrets/tunnel
PRIVATE_KEY=/home/crmdeploy/secrets/tunnel/id_ed25519
KNOWN_HOSTS=/home/crmdeploy/secrets/tunnel/known_hosts
UNIT_NAME=crm-staging-tunnel.service

[[ $(id -un) == "$EXPECTED_USER" && $(id -u) == "$EXPECTED_UID" ]] ||
    fail "Run as crmdeploy UID 1004"
[[ ${HOME:-} == "$EXPECTED_HOME" ]] || fail "Unexpected HOME"
[[ $(getent passwd "$EXPECTED_USER" | cut -d: -f6) == "$EXPECTED_HOME" ]] ||
    fail "Unexpected account home"
[[ $(realpath -e "$EXPECTED_HOME") == "$EXPECTED_HOME" ]] ||
    fail "Home must not be a symlink"

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

# 验证私钥格式和固定网关的已知主机记录；不自动接受或替换远端主机身份。
ssh-keygen -y -f "$PRIVATE_KEY" >/dev/null || fail "Invalid tunnel private key"
ssh-keygen -F 38.55.145.52 -f "$KNOWN_HOSTS" >/dev/null ||
    fail "Pinned public gateway host key is missing"
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
systemctl --user enable --now crm-staging-tunnel.service
systemctl --user is-enabled --quiet crm-staging-tunnel.service || fail "Tunnel service is not enabled"
systemctl --user is-active --quiet crm-staging-tunnel.service || fail "Tunnel service is not active"
echo "CRM staging reverse tunnel is enabled"
