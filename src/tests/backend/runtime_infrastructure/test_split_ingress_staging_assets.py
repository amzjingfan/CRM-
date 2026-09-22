"""双服务器 staging 入口资产的失败关闭契约测试。"""

import configparser
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

import pytest
from _support import SOURCE_ROOT

ROOTLESS_OVERLAY = SOURCE_ROOT / "compose" / "docker-compose.rootless-staging.yml"
ROOTLESS_TUNNEL_NGINX = SOURCE_ROOT / "deploy" / "nginx" / "nginx-tunnel.conf"
ROOTLESS_DIR = SOURCE_ROOT / "deploy" / "staging" / "rootless"
TUNNEL_UNIT = ROOTLESS_DIR / "systemd" / "user" / "crm-staging-tunnel.service"
TUNNEL_INSTALLER = ROOTLESS_DIR / "install-reverse-tunnel.sh"
PROCESS_WAITER = ROOTLESS_DIR / "wait-for-reviewed-process.sh"
PUBLIC_ACCOUNT_INSTALLER = ROOTLESS_DIR / "install-public-tunnel-account.sh"
PUBLIC_EGRESS_ACCOUNT_INSTALLER = ROOTLESS_DIR / "install-public-egress-account.sh"
PUBLIC_NGINX_DIR = ROOTLESS_DIR / "public-nginx"
PUBLIC_HTTP_VHOST = PUBLIC_NGINX_DIR / "staging.overselfx.com-http.conf"
PUBLIC_HTTPS_VHOST = PUBLIC_NGINX_DIR / "staging.overselfx.com.conf"
SPLIT_INGRESS_VERIFIER = ROOTLESS_DIR / "verify-split-ingress.sh"


def test_rootless_overlay_exposes_only_split_ingress_http_port() -> None:
    """错误端口或 TLS 发布会再次把 CRM 与 GitLab/宿主机证书耦合。"""
    source = ROOTLESS_OVERLAY.read_text(encoding="utf-8")

    assert '"127.0.0.1:18081:80"' in source
    assert "10080" not in source
    assert "10443" not in source
    assert "nginx-tunnel.conf" in source


def test_inner_proxy_preserves_https_origin_without_terminating_tls() -> None:
    """内层代理重复终止 TLS 或相信客户端协议头会破坏单一信任边界。"""
    source = ROOTLESS_TUNNEL_NGINX.read_text(encoding="utf-8")

    assert "listen 80 default_server" in source
    assert "listen 443" not in source
    assert "ssl_certificate" not in source
    assert "proxy_set_header X-Forwarded-Proto https" in source
    assert "proxy_buffering off" in source
    assert "proxy_request_buffering off" in source
    assert '"uri":"$uri"' in source
    assert "$request_uri" not in source

    webhook_location = source.split("location ^~ /v1/webhooks/", 1)[1].split("location /v1/", 1)[0]
    assert "error_log /dev/null;" in webhook_location
    assert "proxy_pass http://backend:8000;" in webhook_location
    assert "proxy_set_header X-Forwarded-Proto https;" in webhook_location


def test_reverse_tunnel_is_loopback_only_and_targets_crm_port() -> None:
    """隧道必须避开 GitLab 端口，并在创建监听失败时立即退出。"""
    unit = configparser.ConfigParser(interpolation=None, strict=False)
    unit.read_string(TUNNEL_UNIT.read_text(encoding="utf-8"))
    command = unit["Service"]["ExecStart"]

    assert "/usr/bin/ssh -NT" in command
    assert "-R 127.0.0.1:18080:127.0.0.1:18081" in command
    assert "ExitOnForwardFailure=yes" in command
    assert "StrictHostKeyChecking=yes" in command
    assert "IdentitiesOnly=yes" in command
    assert "StrictHostKeyChecking=no" not in command
    assert "crm-tunnel@38.55.145.52" in command
    assert unit["Service"]["Restart"] == "always"
    assert unit["Service"]["RestartSec"] == "5"


def test_tunnel_installers_preserve_account_and_key_boundaries() -> None:
    """安装器必须拒绝弱权限、身份漂移和可复用为交互登录的密钥。"""
    business = TUNNEL_INSTALLER.read_text(encoding="utf-8")
    public = PUBLIC_ACCOUNT_INSTALLER.read_text(encoding="utf-8")

    for required in (
        "set -Eeuo pipefail",
        "EXPECTED_UID=1004",
        "SECRET_DIR=/home/crmdeploy/secrets/tunnel",
        'PRIVATE_KEY="$SECRET_DIR/id_ed25519"',
        'KNOWN_HOSTS="$SECRET_DIR/known_hosts"',
        "ssh-keygen -F",
        "SHA256:PPupiUWQYpCvIzPtolycQELbt5o49rqp1Hu1RHHE3XU",
        "systemd-analyze --user verify",
        'systemctl --user enable "$UNIT_NAME"',
        'systemctl --user restart "$UNIT_NAME"',
        '"systemd:$UNIT_NAME" /proc 20 1',
    ):
        assert required in business
    assert 'systemctl --user enable --now "$UNIT_NAME"' not in business
    assert business.index("export XDG_RUNTIME_DIR=/run/user/1004") < business.index(
        'systemd-analyze --user verify "$UNIT_SOURCE"'
    )
    assert business.index("export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1004/bus") < business.index(
        'systemd-analyze --user verify "$UNIT_SOURCE"'
    )
    assert business.index("systemctl --user daemon-reload") < business.index('systemctl --user restart "$UNIT_NAME"')
    assert "StrictHostKeyChecking=no" not in business

    for required in (
        "set -Eeuo pipefail",
        "crm-tunnel",
        "/home/crm-tunnel",
        'command="/usr/bin/false"',
        "restrict,port-forwarding",
        'permitlisten="127.0.0.1:18080"',
        "ssh-ed25519",
        "passwd --lock",
        "Existing authorized_keys differs from the reviewed tunnel key",
    ):
        assert required in public
    assert "sudo" not in public
    assert "docker" not in public
    assert "GatewayPorts yes" not in public


def test_public_egress_installer_is_idempotent_and_fail_closed() -> None:
    """公网固定出口账号只能开放三个 HTTPS 目的地，未知既有状态必须停止安装。"""
    installer = PUBLIC_EGRESS_ACCOUNT_INSTALLER.read_text(encoding="utf-8")

    for required in (
        "crm-egress",
        "/home/crm-egress",
        "AllowTcpForwarding local",
        "PermitOpen auth.tiktok-shops.com:443 open-api.tiktokglobalshop.com:443 checkip.amazonaws.com:443",
        "PermitListen none",
        "GatewayPorts no",
        "ForceCommand /usr/bin/false",
        "restrict,port-forwarding",
        'permitopen="auth.tiktok-shops.com:443"',
        'permitopen="open-api.tiktokglobalshop.com:443"',
        'permitopen="checkip.amazonaws.com:443"',
        "sshd -t",
        "systemctl reload ssh",
    ):
        assert required in installer
    assert "systemctl restart ssh" not in installer
    assert "crm-tunnel" not in installer

    inspection_complete = installer.index("existing_state_validated=true")
    creation_branch = installer[installer.index("if [[ $account_exists == false ]]") :]
    assert 'passwd --lock "$ACCOUNT"' not in installer[:inspection_complete]
    assert creation_branch.index("useradd --create-home") < creation_branch.index('passwd --lock "$ACCOUNT"')
    assert creation_branch.index('passwd --lock "$ACCOUNT"') < creation_branch.index("\nfi\n")

    for rejected_state in (
        "exactly one non-empty line",
        "Only an Ed25519 public key",
        "Existing authorized_keys differs",
        "must not be a symlink",
        "must not belong to sudo or extra groups",
        "Duplicate or unknown SSH Match configuration",
    ):
        assert rejected_state in installer
    assert installer.count("rollback_new_artifacts") == 3
    for guarded_failure in (
        'sshd -t || fail "SSH server rejected the egress account policy"',
        'systemctl reload ssh || fail "Cannot reload SSH server safely"',
    ):
        assert guarded_failure in installer


def test_public_egress_installer_inspects_existing_state_before_any_write() -> None:
    """既有账号的密钥或 Match 漂移必须在创建目录、临时文件或覆盖策略前失败。"""
    installer = PUBLIC_EGRESS_ACCOUNT_INSTALLER.read_text(encoding="utf-8")

    inspection_complete = installer.index("existing_state_validated=true")
    for write_operation in (
        "useradd --create-home",
        'install -d -o "$account_uid"',
        'mktemp "$ssh_dir/authorized_keys.',
        'mv -- "$temporary_keys" "$AUTHORIZED_KEYS"',
        'mv -- "$temporary_policy" "$SSHD_POLICY"',
    ):
        assert inspection_complete < installer.index(write_operation)

    for required_existing_check in (
        '[[ -d "$ssh_dir"',
        '[[ -f "$AUTHORIZED_KEYS"',
        'cmp -s -- <(render_authorized_key) "$AUTHORIZED_KEYS"',
        '[[ -f "$SSHD_POLICY"',
        'cmp -s -- <(render_sshd_policy) "$SSHD_POLICY"',
    ):
        assert required_existing_check in installer[:inspection_complete]


def test_public_egress_installer_backs_up_sshd_before_policy_write() -> None:
    """新增 Match drop-in 前必须保留精确 SSHD 备份，并在校验失败时恢复。"""
    installer = PUBLIC_EGRESS_ACCOUNT_INSTALLER.read_text(encoding="utf-8")

    for required in (
        "SSHD_BACKUP_ROOT=/var/backups/crm-staging/sshd",
        'tar --create --absolute-names --numeric-owner --file "$sshd_backup"',
        'tar --extract --absolute-names --numeric-owner --file "$sshd_backup"',
        "restore_sshd_backup",
    ):
        assert required in installer
    assert installer.index('tar --create --absolute-names --numeric-owner --file "$sshd_backup"') < installer.index(
        'mv -- "$temporary_policy" "$SSHD_POLICY"'
    )


def test_public_egress_installer_rejects_backup_path_drift_before_account_write() -> None:
    """备份路径的链接、所有者或权限漂移必须在创建账号前失败，新增目录必须可回滚。"""
    installer = PUBLIC_EGRESS_ACCOUNT_INSTALLER.read_text(encoding="utf-8")
    inspection_complete = installer.index("existing_state_validated=true")

    for required_preflight in (
        "for trusted_backup_parent in /var /var/backups; do",
        '[[ -d "$trusted_backup_parent" && ! -L "$trusted_backup_parent" ]]',
        '[[ $(stat -c %u "$trusted_backup_parent") == 0 ]]',
        "(( (8#$trusted_backup_mode & 0022) == 0 ))",
        '[[ ! -e "$SSHD_BACKUP_ROOT" && ! -L "$SSHD_BACKUP_ROOT" ]]',
    ):
        assert required_preflight in installer[:inspection_complete]
    assert inspection_complete < installer.index('install -d -o root -g root -m 0700 "$SSHD_BACKUP_ROOT"')
    for rollback_flag in ("backup_parent_created", "backup_root_created"):
        assert f"{rollback_flag}=false" in installer
        assert f"if [[ ${rollback_flag} == true ]]" in installer


@pytest.mark.parametrize(
    ("match_line", "expected_match"),
    [
        ("Match User crm-egress", True),
        ("Match User crm-*", True),
        ("Match Group operators User crm-egress", True),
        ("Match Group crm-egress", True),
        ("Match Group crm-*", True),
        ("Match Group operators", False),
        ("Match User crm-tunnel", False),
        ("Match User *,!crm-egress", False),
        ("Match User crm-*,!crm-tunnel", True),
    ],
)
def test_public_egress_installer_detects_matching_openssh_user_patterns(
    tmp_path: Path,
    match_line: str,
    expected_match: bool,
) -> None:
    """重复 Match 检查必须理解 OpenSSH 通配与否定列表，不能只比对字面用户名。"""
    config = tmp_path / "sshd-pattern.conf"
    config.write_bytes(f"{match_line}\n    PasswordAuthentication no\n".encode())
    if os.name == "nt":
        git = shutil.which("git")
        assert git is not None, "Git for Windows is required for SSHD pattern behavior tests"
        bash_path = Path(git).resolve().parent.parent / "bin" / "bash.exe"
        assert bash_path.is_file(), f"Git Bash is required: {bash_path}"
        bash = str(bash_path)
        config_arg = f"/{config.drive[0].lower()}/{config.as_posix()[3:]}"
    else:
        bash = shutil.which("bash")
        assert bash is not None, "bash is required for SSHD pattern behavior tests"
        config_arg = config.as_posix()
    installer = PUBLIC_EGRESS_ACCOUNT_INSTALLER.read_text(encoding="utf-8")
    function_prelude = installer.split("trap cleanup EXIT", 1)[0]

    result = subprocess.run(
        [bash, "-c", f'{function_prelude}\ncontains_account_match "$1"', "--", config_arg],
        capture_output=True,
        check=False,
        text=True,
        timeout=5,
    )

    assert (result.returncode == 0) is expected_match, result.stderr


def test_public_egress_installer_requires_the_dedicated_primary_group() -> None:
    """既有账号必须保留同名专用主组，避免组级 Match 语义与预检假设不一致。"""
    installer = PUBLIC_EGRESS_ACCOUNT_INSTALLER.read_text(encoding="utf-8")
    inspection_complete = installer.index("existing_state_validated=true")

    assert '[[ $primary_group == "$ACCOUNT" ]]' in installer[:inspection_complete]


def test_public_egress_installer_retains_backup_when_restore_fails(tmp_path: Path) -> None:
    """恢复解包失败时保留唯一备份，但仍清除本次创建的密钥和账号。"""
    backup = tmp_path / "sshd-before.tar"
    backup.write_bytes(b"reviewed-backup")
    policy = tmp_path / "91-crm-egress.conf"
    policy.write_bytes(b"candidate-policy")
    authorized_keys = tmp_path / "authorized_keys"
    authorized_keys.write_bytes(b"candidate-key")
    account_marker = tmp_path / "crm-egress-account"
    account_marker.write_bytes(b"candidate-account")
    if os.name == "nt":
        git = shutil.which("git")
        assert git is not None, "Git for Windows is required for rollback behavior tests"
        bash_path = Path(git).resolve().parent.parent / "bin" / "bash.exe"
        assert bash_path.is_file(), f"Git Bash is required: {bash_path}"
        bash = str(bash_path)
        backup_arg = f"/{backup.drive[0].lower()}/{backup.as_posix()[3:]}"
        policy_arg = f"/{policy.drive[0].lower()}/{policy.as_posix()[3:]}"
        keys_arg = f"/{authorized_keys.drive[0].lower()}/{authorized_keys.as_posix()[3:]}"
        account_arg = f"/{account_marker.drive[0].lower()}/{account_marker.as_posix()[3:]}"
    else:
        bash = shutil.which("bash")
        assert bash is not None, "bash is required for rollback behavior tests"
        backup_arg = backup.as_posix()
        policy_arg = policy.as_posix()
        keys_arg = authorized_keys.as_posix()
        account_arg = account_marker.as_posix()
    installer = PUBLIC_EGRESS_ACCOUNT_INSTALLER.read_text(encoding="utf-8")
    function_prelude = installer.split("trap cleanup EXIT", 1)[0]
    exercise = """
sshd_backup=$1
SSHD_POLICY=$2
AUTHORIZED_KEYS=$3
account_marker=$4
policy_created=true
keys_created=true
account_created=true
tar() { return 23; }
userdel() { rm -f -- "$account_marker"; }
set +e
rollback_new_artifacts
status=$?
[[ $status -ne 0 && -f $sshd_backup && ! -e $AUTHORIZED_KEYS && ! -e $account_marker ]]
"""

    result = subprocess.run(
        [bash, "-c", f"{function_prelude}\n{exercise}", "--", backup_arg, policy_arg, keys_arg, account_arg],
        capture_output=True,
        check=False,
        text=True,
        timeout=5,
    )

    assert result.returncode == 0, result.stderr
    assert backup.is_file()
    assert not authorized_keys.exists()
    assert not account_marker.exists()


@pytest.mark.parametrize("failure_target", ["authorized_keys", "account", "backup", "backup_directory"])
def test_public_egress_installer_reports_incomplete_rollback(tmp_path: Path, failure_target: str) -> None:
    """密钥、账号或备份任一清理失败都必须保留状态并报告回滚失败。"""
    artifact = tmp_path / failure_target
    artifact.write_bytes(b"candidate-artifact")
    if os.name == "nt":
        git = shutil.which("git")
        assert git is not None, "Git for Windows is required for rollback behavior tests"
        bash_path = Path(git).resolve().parent.parent / "bin" / "bash.exe"
        assert bash_path.is_file(), f"Git Bash is required: {bash_path}"
        bash = str(bash_path)
        artifact_arg = f"/{artifact.drive[0].lower()}/{artifact.as_posix()[3:]}"
    else:
        bash = shutil.which("bash")
        assert bash is not None, "bash is required for rollback behavior tests"
        artifact_arg = artifact.as_posix()
    installer = PUBLIC_EGRESS_ACCOUNT_INSTALLER.read_text(encoding="utf-8")
    function_prelude = installer.split("trap cleanup EXIT", 1)[0]
    setup_by_target = {
        "authorized_keys": "AUTHORIZED_KEYS=$1\nkeys_created=true\nrm() { return 31; }",
        "account": "account_marker=$1\naccount_created=true\nuserdel() { return 32; }",
        "backup": "sshd_backup=$1\nrm() { return 33; }",
        "backup_directory": "SSHD_BACKUP_ROOT=$1\nbackup_root_created=true\nrmdir() { return 34; }",
    }
    state_assertion = {
        "authorized_keys": "[[ $keys_created == true ]]",
        "account": "[[ $account_created == true ]]",
        "backup": "[[ -n $sshd_backup ]]",
        "backup_directory": "[[ $backup_root_created == true ]]",
    }
    exercise = f"""
{setup_by_target[failure_target]}
set +e
rollback_new_artifacts
status=$?
[[ $status -ne 0 && -f $1 ]] && {state_assertion[failure_target]}
"""

    result = subprocess.run(
        [bash, "-c", f"{function_prelude}\n{exercise}", "--", artifact_arg],
        capture_output=True,
        check=False,
        text=True,
        timeout=5,
    )

    assert result.returncode == 0, result.stderr
    assert artifact.is_file()


def _ssh_cmdline(*overrides: str) -> bytes:
    argv = [
        "/usr/bin/ssh",
        "-NT",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "ExitOnForwardFailure=yes",
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        "ServerAliveInterval=30",
        "-o",
        "ServerAliveCountMax=3",
        "-o",
        "UserKnownHostsFile=/home/crmdeploy/secrets/tunnel/known_hosts",
        "-i",
        "/home/crmdeploy/secrets/tunnel/id_ed25519",
        "-R",
        "127.0.0.1:18080:127.0.0.1:18081",
        "crm-tunnel@38.55.145.52",
    ]
    argv[: len(overrides)] = overrides
    return b"\0".join(item.encode() for item in argv) + b"\0"


def test_process_waiter_reloads_pid_until_reviewed_tunnel_command(tmp_path: Path) -> None:
    """服务自动重启换 PID 后必须重新取 MainPID，不得永久盯住旧进程。"""
    assert PROCESS_WAITER.is_file(), f"missing process waiter: {PROCESS_WAITER}"
    if os.name == "nt":
        pytest.skip("process waiter behavior requires a POSIX bash runtime")
    bash = shutil.which("bash")
    assert bash is not None, "bash is required for process waiter behavior tests"

    proc_root = tmp_path / "proc"
    old_process = proc_root / "1001"
    new_process = proc_root / "1002"
    old_process.mkdir(parents=True)
    new_process.mkdir()
    (old_process / "cmdline").write_bytes(_ssh_cmdline("/usr/bin/ssh", "-NT", "-o", "BatchMode=no"))
    (new_process / "cmdline").write_bytes(_ssh_cmdline())
    pid_file = tmp_path / "main-pid"
    pid_file.write_text("1001\n", encoding="ascii")

    def publish_reviewed_command() -> None:
        time.sleep(0.12)
        pid_file.write_text("1002\n", encoding="ascii")

    started = time.monotonic()
    publisher = threading.Thread(target=publish_reviewed_command)
    publisher.start()
    result = subprocess.run(
        [
            bash,
            str(PROCESS_WAITER),
            f"file:{pid_file}",
            str(proc_root),
            "30",
            "0.02",
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=5,
    )
    publisher.join(timeout=1)

    assert result.returncode == 0, result.stderr
    assert time.monotonic() - started >= 0.1


@pytest.mark.parametrize(
    "cmdline",
    [
        _ssh_cmdline("/bin/not-ssh", "/usr/bin/ssh -NT"),
        _ssh_cmdline(
            "/usr/bin/ssh",
            "-NT",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "ExitOnForwardFailure=yes",
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            "ServerAliveInterval=30",
            "-o",
            "ServerAliveCountMax=3",
            "-o",
            "UserKnownHostsFile=/home/crmdeploy/secrets/tunnel/known_hosts",
            "-i",
            "/home/crmdeploy/secrets/tunnel/id_ed25519",
            "-R",
            "127.0.0.1:18080:127.0.0.1:180810",
        ),
    ],
)
def test_process_waiter_rejects_argv_substring_lookalikes(tmp_path: Path, cmdline: bytes) -> None:
    """只允许逐个 argv 完全匹配，禁止可执行文件或端口子串伪装。"""
    source = PROCESS_WAITER.read_text(encoding="utf-8")
    assert "mapfile -d '' -t running_argv" in source
    assert "expected_argv" in source

    if os.name == "nt":
        pytest.skip("process waiter behavior requires a POSIX bash runtime")
    bash = shutil.which("bash")
    assert bash is not None, "bash is required for process waiter behavior tests"

    proc_root = tmp_path / "proc"
    process = proc_root / "2001"
    process.mkdir(parents=True)
    (process / "cmdline").write_bytes(cmdline)
    pid_file = tmp_path / "main-pid"
    pid_file.write_text("2001\n", encoding="ascii")

    result = subprocess.run(
        [bash, str(PROCESS_WAITER), f"file:{pid_file}", str(proc_root), "1", "0"],
        capture_output=True,
        check=False,
        text=True,
        timeout=5,
    )

    assert result.returncode != 0


def test_public_http_vhost_is_acme_only_and_fail_closed_before_tls() -> None:
    """证书切换前，除 ACME 文件外的请求必须保持 503。"""
    source = PUBLIC_HTTP_VHOST.read_text(encoding="utf-8")

    assert "listen 80" in source
    assert "server_name staging.overselfx.com;" in source
    assert "location ^~ /.well-known/acme-challenge/" in source
    assert "/www/wwwroot/staging.overselfx.com" in source
    assert "return 503" in source
    assert "proxy_pass" not in source
    assert "ssl_certificate" not in source


def test_public_vhost_never_targets_gitlab_or_private_host() -> None:
    """正式公网入口只能把通过 TLS 的请求交给本机回环隧道。"""
    source = PUBLIC_HTTPS_VHOST.read_text(encoding="utf-8")

    assert "server_name staging.overselfx.com;" in source
    assert "ssl_protocols TLSv1.2 TLSv1.3;" in source
    assert "/www/server/panel/vhost/cert/staging.overselfx.com/fullchain.pem" in source
    assert "/www/server/panel/vhost/cert/staging.overselfx.com/privkey.pem" in source
    assert "proxy_pass http://127.0.0.1:18080" in source
    assert "proxy_set_header Host staging.overselfx.com" in source
    assert "proxy_set_header X-Forwarded-Proto https" in source
    assert "proxy_buffering off" in source
    assert "proxy_request_buffering off" in source
    assert "$request_uri" not in source
    assert "192.168.110.210" not in source
    assert ":10080" not in source


def test_public_vhost_replaces_inner_security_headers_once() -> None:
    """客户端只能看到公网 TLS 边界定义的一组安全头，不得与内层值重复或冲突。"""
    source = PUBLIC_HTTPS_VHOST.read_text(encoding="utf-8")
    https_server_preamble = source.rsplit("server {", 1)[1].split("location =", 1)[0]

    for header in (
        "Strict-Transport-Security",
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
    ):
        assert f"proxy_hide_header {header};" in https_server_preamble


def test_split_ingress_verifier_checks_public_and_loopback_boundaries() -> None:
    """全链路验证必须拒绝错误 DNS、证书、监听、GitLab 响应和不安全 TLS。"""
    source = SPLIT_INGRESS_VERIFIER.read_text(encoding="utf-8")

    for required in (
        "set -Eeuo pipefail",
        "1.1.1.1",
        "8.8.8.8",
        "openssl x509 -checkhost",
        "127.0.0.1:18080",
        "127.0.0.1:18081",
        "/healthz",
        "/v1/health",
        "/v1/health/ready",
        "/users/sign_in",
    ):
        assert required in source
    assert "x-gitlab-" in source.lower()
    assert "curl -k" not in source
    assert "--insecure" not in source
    assert "privkey.pem" not in source
