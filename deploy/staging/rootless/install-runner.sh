#!/usr/bin/env bash
set -Eeuo pipefail
# bash -a 或继承的 SHELLOPTS 会自动导出后续赋值；读取注册凭证前必须关闭。
set +a
# 拒绝外部 bash -x 调用；在读取任何注册凭证之前结束，避免调试输出泄密。
[[ $- != *x* ]] || exit 1
umask 077
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
fail() { echo "ERROR: $*" >&2; exit 1; }
[[ $(id -un) == crmdeploy && $(id -u) == 1004 && $(id -g) == 1004 ]] || fail "Run as crmdeploy UID/GID 1004"
[[ $(getent passwd crmdeploy | cut -d: -f6) == /home/crmdeploy ]] || fail "Unexpected account home"
[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || fail "Linux x64 is required"
[[ ${HOME:-} == /home/crmdeploy ]] || fail "Unexpected HOME"
[[ $(realpath -e /home/crmdeploy) == /home/crmdeploy ]] || fail "Home must not be a symlink"
export XDG_RUNTIME_DIR=/run/user/1004
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1004/bus
[[ -S /run/user/1004/docker.sock ]] || fail "Rootless Docker socket is missing"

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
manifest="$script_dir/toolchain-manifest.json"
unit_source="$script_dir/systemd/user/crm-staging-runner.service"
cache_dir=/home/crmdeploy/.cache/crm-toolchain
runner_dir=/home/crmdeploy/runner
powershell_dir=/home/crmdeploy/tools/powershell
unit_dir=/home/crmdeploy/.config/systemd/user
unit_target="$unit_dir/crm-staging-runner.service"

# 检查路径的每一级，拒绝链接和其他账户目录，避免缓存或服务文件落到预期目录外。
check_directory() {
    local directory=$1 current=/home/crmdeploy component
    [[ "$directory" == /home/crmdeploy/* ]] || fail "Unexpected installation path"
    local relative=${directory#/home/crmdeploy/}
    local -a components
    IFS=/ read -r -a components <<<"$relative"
    for component in "${components[@]}"; do
        current="$current/$component"
        [[ ! -L "$current" ]] || fail "Installation path contains a symlink"
        if [[ -e "$current" ]]; then
            [[ -d "$current" && $(stat -c %u "$current") == 1004 ]] || fail "Unexpected path ownership or type"
        else
            mkdir -- "$current"
        fi
    done
}
check_directory "$cache_dir"
check_directory "$unit_dir"
check_directory /home/crmdeploy/tools
[[ ! -L "$cache_dir/install.lock" ]] || fail "Lock must not be a symlink"
exec 9>"$cache_dir/install.lock"
flock -n 9 || fail "Another runner installer is running"
[[ -f "$unit_source" && ! -L "$unit_source" ]] || fail "Runner unit template is missing or linked"
[[ ! -L "$unit_target" ]] || fail "Runner unit must not be a symlink"
if [[ -e "$unit_target" ]]; then
    [[ -f "$unit_target" && $(stat -c %u "$unit_target") == 1004 ]] || fail "Unexpected runner unit ownership"
    cmp -s "$unit_source" "$unit_target" || fail "Existing runner unit differs; review before replacement"
fi
[[ ! -e "$unit_dir/crm-staging-runner.service.d" ]] || fail "Unexpected runner service drop-ins"

# 去掉调用者可能留下的 export 属性，保证随后读取的 Token 不会传给子进程环境。
unset runner_token
runner_token=
cleanup() {
    # 注册失败、用户中断和正常结束均移除进程中的短期凭证，不输出原始异常参数。
    unset runner_token
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# 仅解释 JSON 数据，不 source/eval 清单。官方 URL 必须与名称、版本和平台精确对应。
metadata=$(python3 - "$manifest" <<'PY'
import json
import re
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    manifest = json.load(source)
if manifest.get("schema_version") != 1 or manifest.get("platform") != "linux-x64":
    sys.exit("Unsupported toolchain manifest")
for name, repository, prefix in (
    ("runner", "actions/runner", "actions-runner-linux-x64"),
    ("powershell", "PowerShell/PowerShell", "powershell"),
):
    entry = manifest[name]
    version, digest = entry["version"], entry["sha256"]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        sys.exit("Invalid toolchain version or checksum")
    filename = f"{prefix}-{version}" + ("-linux-x64" if name == "powershell" else "") + ".tar.gz"
    url = f"https://github.com/{repository}/releases/download/v{version}/{filename}"
    if entry["url"] != url:
        sys.exit("Unexpected toolchain release URL")
    print(f"{name}\t{url}\t{digest}")
PY
) || fail "Toolchain manifest validation failed"

while IFS=$'\t' read -r name url digest; do
    destination="$runner_dir"
    [[ "$name" != powershell ]] || destination="$powershell_dir"
    [[ ! -L "$destination" ]] || fail "Tool destination must not be a symlink"
    if [[ -e "$destination" ]]; then
        check_directory "$destination"
        [[ -f "$destination/.crm-toolchain-sha256" && ! -L "$destination/.crm-toolchain-sha256" ]] || fail "Unmanaged tool directory"
        [[ $(<"$destination/.crm-toolchain-sha256") == "$digest" ]] || fail "Installed tool baseline differs"
        # 已安装 Runner 允许 GitHub 的认证自动更新；重复执行不得用旧归档覆盖运行中版本。
        continue
    fi
    archive=$(mktemp "$cache_dir/$name-XXXXXXXX.tar.gz")
    curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
        --connect-timeout 30 --max-time 900 --output "$archive" "$url"
    printf '%s  %s\n' "$digest" "$archive" | sha256sum -c - || fail "Archive checksum mismatch"
    extracted=$(mktemp -d "$cache_dir/$name-extract-XXXXXXXX")
    # 仅解压已校验的官方归档；失败保留私有缓存供排查，不提升半成品为可运行目录。
    tar -xzf "$archive" --no-same-owner -C "$extracted"
    printf '%s\n' "$digest" >"$extracted/.crm-toolchain-sha256"
    mv -T -- "$extracted" "$destination"
done <<<"$metadata"
[[ -f "$powershell_dir/pwsh" && ! -L "$powershell_dir/pwsh" ]] || fail "PowerShell executable is missing or linked"
chmod u+x "$powershell_dir/pwsh"
[[ -x "$runner_dir/run.sh" && -x "$runner_dir/config.sh" ]] || fail "Runner archive is incomplete"
cd "$runner_dir"
if [[ -e .runner || -L .runner ]]; then
    [[ -f .runner && ! -L .runner ]] || fail "Runner settings must be a regular file"
    # 同名本地 Runner 已注册时不再调用 config.sh（官方工具拒绝重复注册）；仅恢复服务。
    python3 - <<'PY' || fail "Existing runner identity differs"
import json
import sys

with open(".runner", encoding="utf-8-sig") as source:
    settings = json.load(source)
expected = {
    "gitHubUrl": "https://github.com/CP11-gh/CRM",
    "agentName": "crm-staging-192-168-110-210",
    "workFolder": "/home/crmdeploy/runner/_work",
}
sys.exit(0 if all(settings.get(key) == value for key, value in expected.items()) else 1)
PY
else
    # Token 仅在所需的 config.sh argv 中出现；禁止显示输入，也不保存或导出到环境。
    IFS= read -r -s runner_token || fail "Runner registration token is required on stdin"
    [[ "$runner_token" =~ ^[A-Za-z0-9_]+$ ]] || fail "Invalid runner registration token"
    if ! ./config.sh --unattended --url https://github.com/CP11-gh/CRM --token "$runner_token" \
        --name crm-staging-192-168-110-210 --labels crm-staging \
        --work /home/crmdeploy/runner/_work --replace >/dev/null 2>&1; then
        unset runner_token
        fail "Runner registration failed; obtain a fresh one-hour registration token"
    fi
    unset runner_token
fi
install -m 0600 "$unit_source" "$unit_target"
systemctl --user daemon-reload
systemctl --user enable --now crm-staging-runner.service
echo "CRM staging runner user service is enabled"
