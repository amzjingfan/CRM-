#!/usr/bin/env bash
set -Eeuo pipefail
[[ $(id -u) -eq 0 ]] || { echo "bootstrap-host.sh must run as root" >&2; exit 1; }
[[ $(. /etc/os-release; printf '%s' "$ID") == ubuntu ]] || { echo "Ubuntu is required" >&2; exit 1; }
[[ $(getent passwd crmdeploy | cut -d: -f6) == /home/crmdeploy ]] || { echo "Unexpected crmdeploy home" >&2; exit 1; }
root_free_kb=$(df --output=avail / | tail -1 | tr -d ' ')
(( root_free_kb >= 1572864 )) || { echo "Root filesystem requires at least 1.5 GiB free" >&2; exit 1; }

# 固定已确认的主机和账户身份，避免把部署资源放到其他账户或文件系统。
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
umask 027
fail() { echo "ERROR: $*" >&2; exit 1; }
[[ $(. /etc/os-release; printf '%s' "$VERSION_ID") == 26.04 ]] || fail "Ubuntu 26.04 is required"
[[ $(uname -m) == x86_64 ]] || fail "x86_64 is required"
[[ $(id -u crmdeploy) == 1004 && $(id -g crmdeploy) == 1004 ]] || fail "Expected crmdeploy UID/GID 1004"
[[ $(realpath -e /home/crmdeploy) == /home/crmdeploy ]] || fail "Home must not be a symlink"
[[ -x /usr/bin/dockerd-rootless-setuptool.sh ]] || fail "Rootless setup tool is missing"
[[ -S /var/run/docker.sock ]] || fail "System Docker socket is missing"
for mapping in /etc/subuid /etc/subgid; do
    awk -F: '$1 == "crmdeploy" && $3 >= 65536 {found=1} END {exit !found}' "$mapping" ||
        fail "crmdeploy requires an existing range of at least 65536 in $mapping"
done
case " $(id -nG crmdeploy) " in
    *" docker "*|*" sudo "*) fail "crmdeploy must not belong to privileged groups" ;;
esac

# 只锁本项目操作，绝不停止公司容器；同一脚本并发执行时立即拒绝。
exec 9>/run/lock/crm-staging-bootstrap.lock
flock -n 9 || fail "Another CRM bootstrap is running"
evidence_root=/home/crmdeploy/evidence
[[ ! -L "$evidence_root" ]] || fail "Evidence directory must not be a symlink"
# 父目录留给后续非 root 部署任务写证据；本次主机快照子目录由 root 拥有。
install -d -o 1004 -g 1004 -m 0750 "$evidence_root"
for directory in "$evidence_root/host-baseline-before" "$evidence_root/host-baseline-after"; do
    [[ ! -L "$directory" ]] || fail "Evidence directory must not be a symlink: $directory"
    install -d -o root -g 1004 -m 0750 "$directory"
done
before_dir=$(mktemp -d "$evidence_root/host-baseline-before/run-XXXXXXXX")
after_dir="$evidence_root/host-baseline-after/${before_dir##*/}"
install -d -o root -g 1004 -m 0750 "$after_dir"
chown root:1004 "$before_dir"
chmod 0750 "$before_dir"

# 显式使用系统 socket，清空客户端上下文，防止操作者的 DOCKER_HOST 改变取证对象。
system_docker() {
    env -i PATH="$PATH" HOME=/root /usr/bin/docker --host unix:///var/run/docker.sock "$@"
}

snapshot() {
    local destination=$1 container_id
    system_docker ps --no-trunc --format '{{json .}}' >"$destination/docker-ps.jsonl" || return 1
    df -B1 / /home >"$destination/filesystems.txt" || return 1
    system_docker ps --all --quiet --no-trunc >"$destination/container-ids.txt" || return 1
    : >"$destination/containers.unsorted"
    while IFS= read -r container_id; do
        [[ -n "$container_id" ]] || continue
        # 限定低敏字段，不保存容器完整 inspect（可能包含公司环境变量/密钥）。
        system_docker inspect --format '{{.Id}}|{{.Name}}|{{.Image}}|{{.State.StartedAt}}|{{.State.Running}}' \
            "$container_id" >>"$destination/containers.unsorted" || return 1
    done <"$destination/container-ids.txt"
    LC_ALL=C sort "$destination/containers.unsorted" >"$destination/containers.txt" || return 1
}

baseline_ready=false
finish() {
    local exit_code=$?
    trap - EXIT
    set +e
    # apt、用户服务或 Rootless 校验失败也必须保留事后快照；取证失败同样不得报成功。
    if ! snapshot "$after_dir"; then
        echo "ERROR: Cannot capture final system Docker snapshot" >&2
        exit_code=1
    elif [[ "$baseline_ready" == true ]]; then
        if ! diff -u "$before_dir/containers.txt" "$after_dir/containers.txt" >"$after_dir/containers.diff"; then
            echo "ERROR: System Docker containers changed; investigate evidence before continuing" >&2
            exit_code=1
        fi
    else
        exit_code=1
    fi
    printf '%s\n' "$exit_code" >"$after_dir/exit-code.txt"
    echo "Evidence: $before_dir and $after_dir"
    exit "$exit_code"
}
trap finish EXIT
snapshot "$before_dir"
baseline_ready=true

# uidmap 是唯一显式安装包；needrestart 仅列出建议，避免自动重启任何现有服务。
NEEDRESTART_MODE=l apt-get update
NEEDRESTART_MODE=l apt-get install --no-install-recommends -y uidmap
loginctl enable-linger crmdeploy
systemctl start user@1004.service

# 清空继承环境，Rootless 的用户配置、缓存和镜像均使用 /home/crmdeploy 下的默认位置。
as_deploy() {
    runuser -u crmdeploy -- env -i PATH="$PATH" HOME=/home/crmdeploy \
        USER=crmdeploy LOGNAME=crmdeploy XDG_RUNTIME_DIR=/run/user/1004 \
        DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1004/bus "$@"
}
as_deploy /usr/bin/dockerd-rootless-setuptool.sh install --force
as_deploy systemctl --user enable --now docker.service
[[ -S /run/user/1004/docker.sock ]] || fail "Rootless Docker socket is missing"
as_deploy /usr/bin/docker --host unix:///run/user/1004/docker.sock info \
    --format '{{json .SecurityOptions}}' >"$after_dir/rootless-security-options.json"
grep -q '"name=rootless"' "$after_dir/rootless-security-options.json" || fail "Daemon is not Rootless"
docker_root=$(as_deploy /usr/bin/docker --host unix:///run/user/1004/docker.sock info --format '{{.DockerRootDir}}')
resolved_root=$(realpath -e "$docker_root")
[[ "$resolved_root" == /home/crmdeploy/* ]] || fail "Rootless storage must remain under /home/crmdeploy"
printf '%s\n' "$resolved_root" >"$after_dir/rootless-storage.txt"
echo "Rootless checks passed; final system-container comparison follows"
