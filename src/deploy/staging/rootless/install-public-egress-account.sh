#!/usr/bin/env bash
set -Eeuo pipefail
[[ $- != *x* ]] || exit 1
umask 077
export PATH=/usr/sbin:/usr/bin:/sbin:/bin

ACCOUNT=crm-egress
ACCOUNT_HOME=/home/crm-egress
AUTHORIZED_KEYS="$ACCOUNT_HOME/.ssh/authorized_keys"
SSHD_CONFIG=/etc/ssh/sshd_config
SSHD_POLICY_DIR=/etc/ssh/sshd_config.d
SSHD_POLICY="$SSHD_POLICY_DIR/91-crm-egress.conf"
SSHD_BACKUP_PARENT=/var/backups/crm-staging
SSHD_BACKUP_ROOT=/var/backups/crm-staging/sshd

account_created=false
keys_created=false
policy_created=false
backup_parent_created=false
backup_root_created=false
temporary_keys=
temporary_policy=
sshd_backup=

cleanup() {
    [[ -z $temporary_keys ]] || rm -f -- "$temporary_keys"
    [[ -z $temporary_policy ]] || rm -f -- "$temporary_policy"
}

restore_sshd_backup() {
    [[ -n $sshd_backup && -f $sshd_backup ]] || return 0
    if ! rm -f -- "$SSHD_POLICY"; then
        echo "ERROR: Cannot remove candidate SSHD policy; retained backup: $sshd_backup" >&2
        return 1
    fi
    if ! tar --extract --absolute-names --numeric-owner --file "$sshd_backup"; then
        echo "ERROR: SSHD backup restore failed; retained backup: $sshd_backup" >&2
        return 1
    fi
    if ! rm -f -- "$sshd_backup"; then
        echo "ERROR: SSHD was restored but the retained backup could not be removed: $sshd_backup" >&2
        return 1
    fi
    sshd_backup=
}

rollback_new_artifacts() {
    local restore_failed=false
    local identity_cleanup_failed=false

    if [[ $policy_created == true ]]; then
        if restore_sshd_backup; then
            policy_created=false
        else
            restore_failed=true
        fi
    fi
    if [[ $keys_created == true ]]; then
        if rm -f -- "$AUTHORIZED_KEYS"; then
            keys_created=false
        else
            identity_cleanup_failed=true
        fi
    fi
    if [[ $account_created == true ]]; then
        if userdel --remove "$ACCOUNT" >/dev/null 2>&1; then
            account_created=false
        else
            identity_cleanup_failed=true
        fi
    fi
    if [[ $restore_failed == true ]]; then
        return 1
    fi
    if [[ -n $sshd_backup ]]; then
        if rm -f -- "$sshd_backup"; then
            sshd_backup=
        else
            return 1
        fi
    fi
    if [[ $backup_root_created == true ]]; then
        if rmdir -- "$SSHD_BACKUP_ROOT" 2>/dev/null; then
            backup_root_created=false
        else
            return 1
        fi
    fi
    if [[ $backup_parent_created == true ]]; then
        if rmdir -- "$SSHD_BACKUP_PARENT" 2>/dev/null; then
            backup_parent_created=false
        else
            return 1
        fi
    fi
    [[ $identity_cleanup_failed == false ]]
}

on_error() {
    status=$?
    trap - ERR
    if ! rollback_new_artifacts; then
        echo "ERROR: Automatic rollback failed; do not remove the retained SSHD backup" >&2
    fi
    exit "$status"
}

fail() {
    echo "ERROR: $*" >&2
    if ! rollback_new_artifacts; then
        echo "ERROR: Automatic rollback failed; do not remove the retained SSHD backup" >&2
    fi
    exit 1
}

render_authorized_key() {
    printf '%s %s\n' \
        'restrict,port-forwarding,permitopen="auth.tiktok-shops.com:443",permitopen="open-api.tiktokglobalshop.com:443",permitopen="checkip.amazonaws.com:443"' \
        "$validated_public_key"
}

render_sshd_policy() {
    cat <<'EOF'
Match User crm-egress
    AuthenticationMethods publickey
    PubkeyAuthentication yes
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    AllowTcpForwarding local
    AllowStreamLocalForwarding no
    GatewayPorts no
    PermitListen none
    PermitOpen auth.tiktok-shops.com:443 open-api.tiktokglobalshop.com:443 checkip.amazonaws.com:443
    AllowAgentForwarding no
    X11Forwarding no
    PermitTTY no
    PermitTunnel no
    PermitUserRC no
    MaxSessions 0
    ForceCommand /usr/bin/false
Match all
EOF
}

pattern_list_matches_account() {
    local pattern_list=$1
    local candidate_pattern
    local matched_positive=false
    local saw_positive=false
    local candidate_patterns=()

    # Quoted/escaped forms are valid SSHD syntax but are intentionally rejected as
    # unknown here rather than risking an incomplete pre-write drift check.
    [[ $pattern_list != *\"* && $pattern_list != *\\* ]] || return 0
    IFS=',' read -r -a candidate_patterns <<<"$pattern_list"
    for candidate_pattern in "${candidate_patterns[@]}"; do
        [[ -n $candidate_pattern ]] || return 0
        if [[ $candidate_pattern == !* ]]; then
            candidate_pattern=${candidate_pattern#!}
            [[ -n $candidate_pattern ]] || return 0
            if [[ $ACCOUNT == $candidate_pattern ]]; then
                return 1
            fi
        else
            saw_positive=true
            if [[ $ACCOUNT == $candidate_pattern ]]; then
                matched_positive=true
            fi
        fi
    done
    [[ $saw_positive == true && $matched_positive == true ]]
}

contains_account_match() {
    local config_file=$1
    local raw_line line keyword_index criterion pattern_list
    local fields=()

    while IFS= read -r raw_line || [[ -n $raw_line ]]; do
        line=${raw_line%%#*}
        read -r -a fields <<<"$line"
        [[ ${#fields[@]} -gt 0 && ${fields[0],,} == match ]] || continue
        for ((keyword_index = 1; keyword_index < ${#fields[@]}; keyword_index++)); do
            criterion=${fields[$keyword_index],,}
            [[ $criterion == user || $criterion == group ]] || continue
            ((keyword_index++))
            [[ $keyword_index -lt ${#fields[@]} ]] || return 0
            pattern_list=${fields[$keyword_index]}
            if pattern_list_matches_account "$pattern_list"; then
                return 0
            fi
        done
    done <"$config_file"
    return 1
}

trap cleanup EXIT
trap on_error ERR
[[ $(id -u) -eq 0 ]] || fail "Run as root"
[[ $# -eq 1 ]] || fail "Usage: install-public-egress-account.sh PUBLIC_KEY_FILE"
public_key_file=$1
[[ -f "$public_key_file" && ! -L "$public_key_file" && -s "$public_key_file" ]] ||
    fail "Public key must be a non-empty regular file and must not be a symlink"
[[ $(awk 'NF { count++ } END { print count + 0 }' "$public_key_file") -eq 1 ]] ||
    fail "Public key file must contain exactly one non-empty line"
read -r key_type key_blob _ <"$public_key_file"
[[ $key_type == ssh-ed25519 && $key_blob =~ ^[A-Za-z0-9+/]+={0,2}$ ]] ||
    fail "Only an Ed25519 public key without authorization options is accepted"
ssh-keygen -lf "$public_key_file" >/dev/null || fail "Public key validation failed"
validated_public_key="$key_type $key_blob crm-tiktok-fixed-egress"

[[ -f "$SSHD_CONFIG" && ! -L "$SSHD_CONFIG" ]] || fail "Main SSHD config must not be a symlink"
[[ -d "$SSHD_POLICY_DIR" && ! -L "$SSHD_POLICY_DIR" ]] || fail "SSHD policy directory must not be a symlink"
[[ $(stat -c %u "$SSHD_POLICY_DIR") == 0 ]] || fail "Unexpected SSHD policy directory owner"
policy_dir_mode=$(stat -c %a "$SSHD_POLICY_DIR") || fail "Cannot inspect SSHD policy directory"
(( (8#$policy_dir_mode & 0022) == 0 )) || fail "SSHD policy directory must not be group/other writable"
[[ ! -L "$SSHD_POLICY" ]] || fail "Egress SSHD policy must not be a symlink"

for trusted_backup_parent in /var /var/backups; do
    [[ -d "$trusted_backup_parent" && ! -L "$trusted_backup_parent" ]] ||
        fail "Trusted backup parent must be a real directory"
    [[ $(stat -c %u "$trusted_backup_parent") == 0 ]] || fail "Unexpected backup parent owner"
    trusted_backup_mode=$(stat -c %a "$trusted_backup_parent") || fail "Cannot inspect backup parent"
    (( (8#$trusted_backup_mode & 0022) == 0 )) || fail "Backup parent must not be group/other writable"
done
backup_parent_exists=false
if [[ -e "$SSHD_BACKUP_PARENT" || -L "$SSHD_BACKUP_PARENT" ]]; then
    [[ -d "$SSHD_BACKUP_PARENT" && ! -L "$SSHD_BACKUP_PARENT" ]] ||
        fail "SSHD backup parent must be a real directory"
    [[ $(stat -c %u "$SSHD_BACKUP_PARENT") == 0 ]] || fail "Unexpected SSHD backup parent owner"
    backup_parent_mode=$(stat -c %a "$SSHD_BACKUP_PARENT") || fail "Cannot inspect SSHD backup parent"
    (( (8#$backup_parent_mode & 0022) == 0 )) || fail "SSHD backup parent must not be group/other writable"
    backup_parent_exists=true
else
    [[ ! -e "$SSHD_BACKUP_PARENT" && ! -L "$SSHD_BACKUP_PARENT" ]] || fail "Unknown SSHD backup parent"
fi
backup_root_exists=false
if [[ -e "$SSHD_BACKUP_ROOT" || -L "$SSHD_BACKUP_ROOT" ]]; then
    [[ -d "$SSHD_BACKUP_ROOT" && ! -L "$SSHD_BACKUP_ROOT" ]] ||
        fail "SSHD backup root must be a real directory"
    [[ $(stat -c %u "$SSHD_BACKUP_ROOT") == 0 ]] || fail "Unexpected SSHD backup root owner"
    backup_root_mode=$(stat -c %a "$SSHD_BACKUP_ROOT") || fail "Cannot inspect SSHD backup root"
    (( (8#$backup_root_mode & 0022) == 0 )) || fail "SSHD backup root must not be group/other writable"
    backup_root_exists=true
else
    [[ ! -e "$SSHD_BACKUP_ROOT" && ! -L "$SSHD_BACKUP_ROOT" ]] || fail "Unknown SSHD backup root"
fi

account_exists=false
if account_record=$(getent passwd "$ACCOUNT"); then
    account_exists=true
    [[ $(cut -d: -f6 <<<"$account_record") == "$ACCOUNT_HOME" ]] || fail "Unexpected egress account home"
    [[ $(cut -d: -f7 <<<"$account_record") == /usr/sbin/nologin ]] || fail "Unexpected egress account shell"
    [[ $(passwd -S "$ACCOUNT" | awk '{ print $2 }') == L ]] || fail "Egress account is not locked"
    account_uid=$(id -u "$ACCOUNT")
    account_gid=$(id -g "$ACCOUNT")
    primary_group=$(id -gn "$ACCOUNT")
    [[ $primary_group == "$ACCOUNT" ]] || fail "Unexpected egress primary group"
    [[ $(id -nG "$ACCOUNT") == "$primary_group" ]] ||
        fail "Egress account must not belong to sudo or extra groups"

    [[ -d "$ACCOUNT_HOME" && ! -L "$ACCOUNT_HOME" ]] || fail "Egress home must not be a symlink"
    [[ $(stat -c %u "$ACCOUNT_HOME") == "$account_uid" ]] || fail "Unexpected egress home owner"
    [[ $(stat -c %a "$ACCOUNT_HOME") == 700 ]] || fail "Egress home must use mode 0700"

    ssh_dir="$ACCOUNT_HOME/.ssh"
    [[ -d "$ssh_dir" && ! -L "$ssh_dir" ]] || fail "Existing egress SSH directory is missing or invalid"
    [[ $(stat -c %u "$ssh_dir") == "$account_uid" ]] || fail "Unexpected egress SSH directory"
    [[ $(stat -c %a "$ssh_dir") == 700 ]] || fail "Egress SSH directory must use mode 0700"
    [[ -f "$AUTHORIZED_KEYS" && ! -L "$AUTHORIZED_KEYS" ]] ||
        fail "Existing authorized_keys must be a regular file and must not be a symlink"
    [[ $(stat -c %u "$AUTHORIZED_KEYS") == "$account_uid" ]] || fail "Unexpected authorized_keys owner"
    [[ $(stat -c %a "$AUTHORIZED_KEYS") == 600 ]] || fail "authorized_keys must use mode 0600"
    cmp -s -- <(render_authorized_key) "$AUTHORIZED_KEYS" ||
        fail "Existing authorized_keys differs from the reviewed egress key"

    [[ -f "$SSHD_POLICY" && ! -L "$SSHD_POLICY" ]] || fail "Existing egress SSHD policy is not regular"
    [[ $(stat -c %u "$SSHD_POLICY") == 0 ]] || fail "Unexpected egress SSHD policy owner"
    [[ $(stat -c %a "$SSHD_POLICY") == 600 ]] || fail "Egress SSHD policy must use mode 0600"
    cmp -s -- <(render_sshd_policy) "$SSHD_POLICY" ||
        fail "Existing egress SSHD policy differs from the reviewed policy"
else
    [[ ! -e "$ACCOUNT_HOME" && ! -L "$ACCOUNT_HOME" ]] || fail "Unknown pre-existing egress home"
    [[ ! -e "$SSHD_POLICY" ]] || fail "Unknown pre-existing egress SSHD policy"
fi

shopt -s nullglob
sshd_configs=("$SSHD_CONFIG" "$SSHD_POLICY_DIR"/*.conf)
shopt -u nullglob
for config_file in "${sshd_configs[@]}"; do
    [[ "$config_file" == "$SSHD_POLICY" ]] && continue
    [[ -f "$config_file" && ! -L "$config_file" ]] || fail "SSHD config path must not be a symlink"
    if contains_account_match "$config_file"; then
        fail "Duplicate or unknown SSH Match configuration for crm-egress"
    fi
done
/usr/sbin/sshd -t || fail "Existing SSH server configuration is invalid"
existing_state_validated=true

if [[ $account_exists == false ]]; then
    useradd --create-home --home-dir "$ACCOUNT_HOME" --shell /usr/sbin/nologin --user-group "$ACCOUNT"
    account_created=true
    passwd --lock "$ACCOUNT" >/dev/null
    [[ $(passwd -S "$ACCOUNT" | awk '{ print $2 }') == L ]] || fail "Egress account is not locked"
    account_uid=$(id -u "$ACCOUNT")
    account_gid=$(id -g "$ACCOUNT")
    chmod 0700 "$ACCOUNT_HOME"

    ssh_dir="$ACCOUNT_HOME/.ssh"
    install -d -o "$account_uid" -g "$account_gid" -m 0700 "$ssh_dir"
    temporary_keys=$(mktemp "$ssh_dir/authorized_keys.XXXXXXXX")
    render_authorized_key >"$temporary_keys"
    chown "$account_uid:$account_gid" "$temporary_keys"
    chmod 0600 "$temporary_keys"
    mv -- "$temporary_keys" "$AUTHORIZED_KEYS"
    temporary_keys=
    keys_created=true

    if [[ $backup_parent_exists == false ]]; then
        install -d -o root -g root -m 0700 "$SSHD_BACKUP_PARENT"
        backup_parent_created=true
    fi
    if [[ $backup_root_exists == false ]]; then
        install -d -o root -g root -m 0700 "$SSHD_BACKUP_ROOT"
        backup_root_created=true
    fi
    sshd_backup=$(mktemp "$SSHD_BACKUP_ROOT/crm-egress-before-XXXXXXXX.tar")
    tar --create --absolute-names --numeric-owner --file "$sshd_backup" "$SSHD_CONFIG" "$SSHD_POLICY_DIR"
    chmod 0600 "$sshd_backup"

    temporary_policy=$(mktemp "$SSHD_POLICY_DIR/.91-crm-egress.conf.XXXXXXXX")
    render_sshd_policy >"$temporary_policy"
    chown root:root "$temporary_policy"
    chmod 0600 "$temporary_policy"
    mv -- "$temporary_policy" "$SSHD_POLICY"
    temporary_policy=
    policy_created=true
fi

/usr/sbin/sshd -t || fail "SSH server rejected the egress account policy"
sshd_effective=$(/usr/sbin/sshd -T -C "user=$ACCOUNT,host=localhost,addr=192.168.1.173") ||
    fail "Cannot read account-scoped SSH server configuration"
for expected_policy in \
    "authenticationmethods publickey" \
    "pubkeyauthentication yes" \
    "passwordauthentication no" \
    "kbdinteractiveauthentication no" \
    "allowtcpforwarding local" \
    "allowstreamlocalforwarding no" \
    "gatewayports no" \
    "permitlisten none" \
    "permitopen auth.tiktok-shops.com:443 open-api.tiktokglobalshop.com:443 checkip.amazonaws.com:443" \
    "allowagentforwarding no" \
    "x11forwarding no" \
    "permittty no" \
    "permittunnel no" \
    "permituserrc no" \
    "maxsessions 0" \
    "forcecommand /usr/bin/false"; do
    grep -Fxq "$expected_policy" <<<"$sshd_effective" || {
        fail "Unexpected account-scoped SSH forwarding policy"
    }
done
/usr/bin/systemctl reload ssh || fail "Cannot reload SSH server safely"
trap - ERR
trap - EXIT
echo "Restricted CRM TikTok egress account is installed"
