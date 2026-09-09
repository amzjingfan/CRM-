#!/usr/bin/env bash
set -Eeuo pipefail
[[ $(id -u) -eq 0 ]] || { echo "install-entry-proxy.sh must run as root" >&2; exit 1; }
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
export LC_ALL=C
umask 027
fail() { echo "ERROR: $*" >&2; exit 1; }
[[ $(. /etc/os-release; printf '%s' "$ID:$VERSION_ID") == ubuntu:26.04 ]] || fail "Ubuntu 26.04 is required"
[[ $(id -u crmdeploy) == 1004 && $(id -g crmdeploy) == 1004 ]] || fail "Expected crmdeploy UID/GID 1004"
[[ $(getent passwd crmdeploy | cut -d: -f6) == /home/crmdeploy ]] || fail "Unexpected crmdeploy home"
[[ -x /usr/lib/systemd/systemd-socket-proxyd ]] || fail "systemd socket proxy binary is missing"
exec 9>/run/lock/crm-staging-entry-proxy.lock
flock -n 9 || fail "Another CRM entry-proxy install is running"
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/systemd" && pwd -P)
units=(crm-staging-http.socket crm-staging-http.service crm-staging-https.socket crm-staging-https.service)
created_units=()
declare -A was_active was_enabled

# 已有同名单元必须与仓库资产逐字相同且无 override；名称相同不能证明归属。
for unit in "${units[@]}"; do
    [[ -f "$source_dir/$unit" && ! -L "$source_dir/$unit" ]] || fail "Invalid source unit: $unit"
    destination="/etc/systemd/system/$unit"
    [[ ! -L "$destination" ]] || fail "Refusing symlink or masked unit: $unit"
    fragment=$(systemctl show "$unit" --property=FragmentPath --value)
    [[ -z "$fragment" || "$fragment" == "$destination" ]] || fail "Foreign unit path: $unit"
    [[ -z $(systemctl show "$unit" --property=DropInPaths --value) ]] || fail "Unit has overrides: $unit"
    [[ $(systemctl show "$unit" --property=NeedDaemonReload --value) != yes ]] || fail "Unloaded changes: $unit"
    if [[ -e "$destination" ]]; then
        [[ -f "$destination" ]] && cmp -s "$source_dir/$unit" "$destination" || fail "Unit content differs: $unit"
        [[ $(stat -c '%u:%g:%a' "$destination") == 0:0:644 ]] || fail "Unexpected unit ownership/mode: $unit"
    fi
    was_active[$unit]=false
    was_enabled[$unit]=false
    if systemctl is-active --quiet "$unit"; then was_active[$unit]=true; fi
    if systemctl is-enabled --quiet "$unit"; then was_enabled[$unit]=true; fi
done

check_port() {
    local port=$1 prefix=$2 listeners socket_rows process_ids process_id proxy_pid
    listeners=$(ss -H -lntp "sport = :$port") || fail "Cannot inspect port $port"
    [[ -n "$listeners" ]] || return 0
    systemctl is-active --quiet "$prefix.socket" || fail "Port $port is occupied by a foreign listener"
    [[ $(systemctl show "$prefix.socket" --property=SubState --value) == listening ]] ||
        fail "Expected socket is not listening on port $port"
    # 所有同端口的 systemd socket 都必须属于精确单元，不能仅因为监听 PID 是 1 就放行。
    socket_rows=$(systemctl list-sockets --all --no-legend --no-pager) || fail "Cannot inspect socket ownership"
    printf '%s\n' "$socket_rows" | awk -v port="$port" -v expected="$prefix.socket" '
        $1 ~ (":" port "$") {found=1; if ($2 != expected) foreign=1}
        END {exit (!found || foreign)}' || fail "Foreign or unverifiable systemd socket on port $port"
    proxy_pid=$(systemctl show "$prefix.service" --property=MainPID --value)
    while IFS= read -r listener; do
        process_ids=$(printf '%s\n' "$listener" | grep -oE 'pid=[0-9]+' || true)
        [[ -n "$process_ids" ]] || fail "Port $port process ownership is unavailable"
        while IFS= read -r process_id; do
            [[ "$process_id" == pid=1 || ( "$proxy_pid" != 0 && "$process_id" == "pid=$proxy_pid" ) ]] ||
                fail "Foreign process on port $port"
        done <<<"$process_ids"
    done <<<"$listeners"
}
check_port 80 crm-staging-http
check_port 443 crm-staging-https

evidence_root=/home/crmdeploy/evidence
[[ $(realpath -e /home/crmdeploy) == /home/crmdeploy ]] || fail "Home must not be a symlink"
[[ ! -L "$evidence_root" ]] || fail "Evidence directory must not be a symlink"
install -d -o 1004 -g 1004 -m 0750 "$evidence_root"
evidence_dir=$(mktemp -d "$evidence_root/entry-proxy-XXXXXXXX")
chown root:1004 "$evidence_dir"
chmod 0750 "$evidence_dir"

rollback() {
    local unit
    # 只撤销本次新启动/启用的精确项目单元；原本运行的 socket/service 完整保留。
    for unit in "${units[@]}"; do
        if [[ ${was_active[$unit]} == false ]]; then
            systemctl stop "$unit" || echo "ERROR: Rollback stop failed: $unit" >&2
        fi
        if [[ "$unit" == *.socket && ${was_enabled[$unit]} == false ]]; then
            systemctl disable "$unit" || echo "ERROR: Rollback disable failed: $unit" >&2
        fi
    done
    for unit in "${created_units[@]}"; do
        rm -f -- "/etc/systemd/system/$unit" || echo "ERROR: Rollback removal failed: $unit" >&2
    done
    systemctl daemon-reload || echo "ERROR: Rollback daemon-reload failed" >&2
}

finish() {
    local exit_code=$?
    trap - EXIT
    set +e
    if (( exit_code != 0 )); then rollback; fi
    # service 在尚未收到连接时为 inactive 属于正常状态；status 原始退出码单独记录。
    systemctl status --no-pager "${units[@]}" >"$evidence_dir/systemctl-status.txt" 2>&1
    printf '%s\n' "$?" >"$evidence_dir/status-command-exit-code.txt"
    ss -lntp >"$evidence_dir/ss-lntp.txt" 2>&1 || exit_code=1
    printf '%s\n' "$exit_code" >"$evidence_dir/exit-code.txt"
    echo "Evidence: $evidence_dir"
    exit "$exit_code"
}
trap finish EXIT
for unit in "${units[@]}"; do
    if [[ ! -e "/etc/systemd/system/$unit" ]]; then
        created_units+=("$unit")
        install -o root -g root -m 0644 "$source_dir/$unit" "/etc/systemd/system/$unit"
    fi
done
systemctl daemon-reload
systemctl enable --now crm-staging-http.socket crm-staging-https.socket
systemctl is-active --quiet crm-staging-http.socket
systemctl is-active --quiet crm-staging-https.socket
# 激活后重检归属，端口在预检之后被其他进程抢占时失败并回滚本次新增资产。
check_port 80 crm-staging-http
check_port 443 crm-staging-https
echo "CRM entry sockets are active; proxy services remain socket-activated"
