#!/usr/bin/env bash
set -Eeuo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin

fail() { echo "ERROR: $*" >&2; exit 1; }

[[ $# -eq 4 ]] || fail "Usage: $0 PID_SOURCE PROC_ROOT ATTEMPTS INTERVAL_SECONDS"
pid_source=$1
proc_root=$2
attempts=$3
interval_seconds=$4

[[ $attempts =~ ^[1-9][0-9]*$ && $attempts -le 120 ]] || fail "Invalid attempt count"
[[ $interval_seconds =~ ^(0|[1-9][0-9]*)(\.[0-9]+)?$ ]] || fail "Invalid wait interval"
[[ $proc_root == /* && -d "$proc_root" && ! -L "$proc_root" ]] || fail "Invalid proc root"

expected_argv=(
    /usr/bin/ssh
    -NT
    -o BatchMode=yes
    -o ConnectTimeout=10
    -o ExitOnForwardFailure=yes
    -o IdentitiesOnly=yes
    -o StrictHostKeyChecking=yes
    -o ServerAliveInterval=30
    -o ServerAliveCountMax=3
    -o UserKnownHostsFile=/home/crmdeploy/secrets/tunnel/known_hosts
    -i /home/crmdeploy/secrets/tunnel/id_ed25519
    -R 127.0.0.1:18080:127.0.0.1:18081
    crm-tunnel@38.55.145.52
)

read_main_pid() {
    local main_pid pid_file
    case "$pid_source" in
        systemd:crm-staging-tunnel.service)
            [[ $proc_root == /proc ]] || return 1
            /usr/bin/systemctl --user show crm-staging-tunnel.service --property=MainPID --value
            ;;
        file:*)
            pid_file=${pid_source#file:}
            [[ $pid_file == /* && -f "$pid_file" && ! -L "$pid_file" && -r "$pid_file" ]] || return 1
            IFS= read -r main_pid <"$pid_file"
            printf '%s\n' "$main_pid"
            ;;
        *)
            return 1
            ;;
    esac
}

for ((attempt = 1; attempt <= attempts; attempt++)); do
    if main_pid=$(read_main_pid 2>/dev/null) && [[ $main_pid =~ ^[1-9][0-9]*$ ]]; then
        cmdline_file="$proc_root/$main_pid/cmdline"
        running_argv=()
        if [[ -r "$cmdline_file" ]] &&
            mapfile -d '' -t running_argv <"$cmdline_file" 2>/dev/null; then
            reviewed=true
            [[ ${#running_argv[@]} -eq ${#expected_argv[@]} ]] || reviewed=false
            for index in "${!expected_argv[@]}"; do
                if [[ ${running_argv[$index]:-} != "${expected_argv[$index]}" ]]; then
                    reviewed=false
                    break
                fi
            done
            if [[ $reviewed == true ]]; then
                exit 0
            fi
        fi
    fi
    if (( attempt < attempts )); then
        sleep "$interval_seconds"
    fi
done

fail "Reviewed process command did not become ready"
