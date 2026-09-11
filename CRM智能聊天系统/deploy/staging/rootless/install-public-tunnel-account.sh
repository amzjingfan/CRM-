#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
export PATH=/usr/sbin:/usr/bin:/sbin:/bin

fail() { echo "ERROR: $*" >&2; exit 1; }

ACCOUNT=crm-tunnel
ACCOUNT_HOME=/home/crm-tunnel
AUTHORIZED_KEYS="$ACCOUNT_HOME/.ssh/authorized_keys"

[[ $(id -u) -eq 0 ]] || fail "Run as root"
[[ $# -eq 1 ]] || fail "Usage: install-public-tunnel-account.sh PUBLIC_KEY_FILE"
public_key_file=$1
[[ -f "$public_key_file" && ! -L "$public_key_file" && -s "$public_key_file" ]] ||
    fail "Public key must be a non-empty regular file"
[[ $(awk 'NF { count++ } END { print count + 0 }' "$public_key_file") -eq 1 ]] ||
    fail "Public key file must contain exactly one non-empty line"
read -r key_type key_blob _ <"$public_key_file"
[[ $key_type == ssh-ed25519 && $key_blob =~ ^[A-Za-z0-9+/]+={0,2}$ ]] ||
    fail "Only one OpenSSH Ed25519 public key is accepted"
ssh-keygen -lf "$public_key_file" >/dev/null || fail "Public key validation failed"

if getent passwd "$ACCOUNT" >/dev/null; then
    [[ $(getent passwd "$ACCOUNT" | cut -d: -f6) == "$ACCOUNT_HOME" ]] || fail "Unexpected tunnel account home"
else
    useradd --create-home --home-dir "$ACCOUNT_HOME" --shell /usr/sbin/nologin "$ACCOUNT"
fi
usermod --shell /usr/sbin/nologin "$ACCOUNT"
passwd --lock "$ACCOUNT" >/dev/null
account_uid=$(id -u "$ACCOUNT")
account_gid=$(id -g "$ACCOUNT")
primary_group=$(id -gn "$ACCOUNT")
[[ $(id -nG "$ACCOUNT") == "$primary_group" ]] ||
    fail "Unexpected tunnel account group memberships"
[[ -d "$ACCOUNT_HOME" && ! -L "$ACCOUNT_HOME" ]] || fail "Tunnel account home is missing or linked"
[[ $(stat -c %u "$ACCOUNT_HOME") == "$account_uid" ]] || fail "Unexpected tunnel home owner"
home_mode=$(stat -c %a "$ACCOUNT_HOME") || fail "Cannot inspect tunnel home permissions"
(( (8#$home_mode & 0022) == 0 )) || fail "Tunnel home must not be group/other writable"

ssh_dir="$ACCOUNT_HOME/.ssh"
[[ ! -L "$ssh_dir" && ! -L "$AUTHORIZED_KEYS" ]] || fail "Tunnel SSH paths must not be links"
if [[ -e "$ssh_dir" ]]; then
    [[ -d "$ssh_dir" ]] || fail "Tunnel SSH directory is not a directory"
    [[ $(stat -c %u "$ssh_dir") == "$account_uid" ]] || fail "Unexpected tunnel SSH directory owner"
    ssh_dir_mode=$(stat -c %a "$ssh_dir") || fail "Cannot inspect tunnel SSH directory permissions"
    (( (8#$ssh_dir_mode & 0022) == 0 )) || fail "Tunnel SSH directory must not be group/other writable"
fi
install -d -o "$account_uid" -g "$account_gid" -m 0700 "$ssh_dir"
temporary_keys=$(mktemp "$ssh_dir/authorized_keys.XXXXXXXX")
cleanup() { rm -f -- "$temporary_keys"; }
trap cleanup EXIT
printf 'command="/usr/bin/false",restrict,port-forwarding,permitlisten="127.0.0.1:18080" ssh-ed25519 %s crm-staging-reverse-tunnel\n' \
    "$key_blob" >"$temporary_keys"
chown "$account_uid:$account_gid" "$temporary_keys"
chmod 0600 "$temporary_keys"
mv -f -- "$temporary_keys" "$AUTHORIZED_KEYS"
trap - EXIT

sshd_effective=$(sshd -T) || fail "Cannot read effective SSH server configuration"
grep -Eq '^allowtcpforwarding (yes|remote)$' <<<"$sshd_effective" || fail "Remote forwarding is disabled"
grep -q '^gatewayports no$' <<<"$sshd_effective" || fail "GatewayPorts must remain disabled"
echo "Restricted CRM staging tunnel account is installed"
