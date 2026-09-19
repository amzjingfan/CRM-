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
read -r key_type key_blob key_comment key_extra <"$public_key_file"
[[ $key_type == ssh-ed25519 && $key_blob =~ ^[A-Za-z0-9+/]+={0,2}$ && -z ${key_extra:-} ]] ||
    fail "Only one OpenSSH Ed25519 public key without authorization options is accepted"
ssh-keygen -lf "$public_key_file" >/dev/null || fail "Public key validation failed"
validated_public_key="$key_type $key_blob crm-staging-reverse-tunnel"

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

# restrict 默认关闭转发，随后只重新启用受 permitlisten 约束的远程 TCP 转发。
temporary_keys=$(mktemp "$ssh_dir/authorized_keys.XXXXXXXX")
temporary_policy=
cleanup() {
    rm -f -- "$temporary_keys"
    [[ -z $temporary_policy ]] || rm -f -- "$temporary_policy"
}
trap cleanup EXIT
printf 'command="/usr/bin/false",restrict,port-forwarding,permitlisten="127.0.0.1:18080" %s\n' \
    "$validated_public_key" >"$temporary_keys"
chown "$account_uid:$account_gid" "$temporary_keys"
chmod 0600 "$temporary_keys"
if [[ -e "$AUTHORIZED_KEYS" ]]; then
    [[ -f "$AUTHORIZED_KEYS" && ! -L "$AUTHORIZED_KEYS" ]] || fail "Existing authorized_keys is not a regular file"
    [[ $(stat -c %u "$AUTHORIZED_KEYS") == "$account_uid" ]] || fail "Unexpected authorized_keys owner"
    [[ $(stat -c %a "$AUTHORIZED_KEYS") == 600 ]] || fail "authorized_keys must use mode 0600"
    cmp -s -- "$temporary_keys" "$AUTHORIZED_KEYS" ||
        fail "Existing authorized_keys differs from the reviewed tunnel key"
    rm -f -- "$temporary_keys"
else
    mv -- "$temporary_keys" "$AUTHORIZED_KEYS"
fi

# 账号级 Match 只约束 crm-tunnel，不改变 sshd 的全局 GatewayPorts 策略。
SSHD_POLICY_DIR=/etc/ssh/sshd_config.d
SSHD_POLICY="$SSHD_POLICY_DIR/90-crm-tunnel.conf"
[[ -d "$SSHD_POLICY_DIR" && ! -L "$SSHD_POLICY_DIR" ]] || fail "SSH policy directory is missing or linked"
[[ $(stat -c %u "$SSHD_POLICY_DIR") == 0 ]] || fail "Unexpected SSH policy directory owner"
policy_dir_mode=$(stat -c %a "$SSHD_POLICY_DIR") || fail "Cannot inspect SSH policy directory permissions"
(( (8#$policy_dir_mode & 0022) == 0 )) || fail "SSH policy directory must not be group/other writable"

temporary_policy=$(mktemp "$SSHD_POLICY_DIR/.90-crm-tunnel.conf.XXXXXXXX")
cat >"$temporary_policy" <<'EOF'
Match User crm-tunnel
    AuthenticationMethods publickey
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    AllowTcpForwarding remote
    AllowStreamLocalForwarding no
    GatewayPorts no
    PermitListen 127.0.0.1:18080
    PermitOpen none
    AllowAgentForwarding no
    X11Forwarding no
    PermitTTY no
    PermitTunnel no
    PermitUserRC no
    MaxSessions 0
    ForceCommand /usr/bin/false
Match all
EOF
chown root:root "$temporary_policy"
chmod 0600 "$temporary_policy"

policy_created=false
if [[ -e "$SSHD_POLICY" || -L "$SSHD_POLICY" ]]; then
    [[ -f "$SSHD_POLICY" && ! -L "$SSHD_POLICY" ]] || fail "Existing tunnel SSH policy is not a regular file"
    [[ $(stat -c %u "$SSHD_POLICY") == 0 ]] || fail "Unexpected tunnel SSH policy owner"
    [[ $(stat -c %a "$SSHD_POLICY") == 600 ]] || fail "Tunnel SSH policy must use mode 0600"
    cmp -s -- "$temporary_policy" "$SSHD_POLICY" || fail "Existing tunnel SSH policy differs from the reviewed policy"
    rm -f -- "$temporary_policy"
else
    mv -- "$temporary_policy" "$SSHD_POLICY"
    policy_created=true
fi
temporary_policy=

rollback_new_policy() {
    if [[ $policy_created == true ]]; then
        rm -f -- "$SSHD_POLICY"
        sshd -t >/dev/null 2>&1 && systemctl reload ssh >/dev/null 2>&1 || true
    fi
}
sshd -t || { rollback_new_policy; fail "SSH server rejected the tunnel account policy"; }
sshd_effective=$(sshd -T -C "user=$ACCOUNT,host=localhost,addr=127.0.0.1,laddr=127.0.0.1,lport=22") || {
    rollback_new_policy
    fail "Cannot read account-scoped SSH server configuration"
}
for expected_policy in \
    "authenticationmethods publickey" \
    "passwordauthentication no" \
    "kbdinteractiveauthentication no" \
    "allowtcpforwarding remote" \
    "allowstreamlocalforwarding no" \
    "gatewayports no" \
    "permitlisten 127.0.0.1:18080" \
    "permitopen none" \
    "allowagentforwarding no" \
    "x11forwarding no" \
    "permittty no" \
    "permittunnel no" \
    "permituserrc no" \
    "maxsessions 0" \
    "forcecommand /usr/bin/false"; do
    grep -Fxq "$expected_policy" <<<"$sshd_effective" || {
        rollback_new_policy
        fail "Unexpected account-scoped SSH forwarding policy"
    }
done
systemctl reload ssh || { rollback_new_policy; fail "Cannot reload SSH server safely"; }
trap - EXIT
echo "Restricted CRM staging tunnel account is installed"
