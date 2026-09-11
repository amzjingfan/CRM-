# 双服务器 Rootless Docker staging 运行手册

日期：2026-09-11。架构依据为 `架构师/ADR-008-INFRA-双服务器Staging入口分离-v1.0.md`。本文是当前唯一活动入口手册；未执行命令不是成功证据。

## 1. 范围与当前状态

| 层级 | 当前状态 | 完成条件 |
| --- | --- | --- |
| Rootless 主机与 runner | 已有现场基础 | 实施前重新只读复核，系统公司容器五字段不变 |
| 仓库双机入口资产 | 实施中 | PR、CI、人工审阅、squash merge 和新 main 镜像完成 |
| DNS/TLS/隧道/应用 G0 | 未执行 | 本手册真实命令与低敏证据全部通过 |
| TikTok G1～G6 | 未执行 | OAuth/读取、Webhook、人工消息、AI/RAG、性能、五日稳定性 |
| production | 未批准 | staging 通过后另行讨论运行方案并完成 G8 |

只验收 TikTok OAuth、读取、Webhook、人工发送、AI 建议、RAG、工作台、知识库和看板。Shopee/Amazon 概念和 UI 保留但不做真实接入；自动回复、营销和高风险写入不在本轮范围。

## 2. 固定参数与保护边界

```text
PUBLIC_GATEWAY=38.55.145.52
BUSINESS_SERVER=192.168.110.210
PUBLIC_DOMAIN=staging.overselfx.com
PUBLIC_TUNNEL_LISTENER=127.0.0.1:18080
ROOTLESS_PROXY_LISTENER=127.0.0.1:10080
DOCKER_HOST=unix:///run/user/1004/docker.sock
COMPOSE_PROJECT_NAME=crm-staging
CRM_STAGING_ENV_FILE=/home/crmdeploy/config/crm-staging.env
```

`38.55.145.52` 只承担公网 Nginx/TLS 和受限隧道账号；`192.168.110.210` 只承担 Rootless CRM。禁止停止、重启、迁移、修复或接管业务服务器的系统 Docker 与公司容器。活动 staging TLS 私钥不得复制到业务服务器。

部署环境文件位于仓库外且为 `0600`。初始值至少保持：

```text
APP_ENV=staging
PUBLIC_BASE_URL=https://staging.overselfx.com
PUBLIC_API_BASE_URL=https://staging.overselfx.com/v1
CORS_ORIGINS=https://staging.overselfx.com
TIKTOK_OAUTH_REDIRECT_URI=https://staging.overselfx.com/v1/integrations/tiktok/oauth/callback
TLS_CERT_DIR=/home/crmdeploy/config/unused-tls
RETRIEVAL_MODEL_ASSET_DIR=/home/crmdeploy/assets/models
ALLOW_MOCK_PLATFORM_ADAPTERS=false
REAL_TIKTOK_READ_ENABLED=false
REAL_TIKTOK_WEBHOOK_ENABLED=false
REAL_TIKTOK_MESSAGE_WRITE_ENABLED=false
REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED=false
LLM_ENABLED=false
LLM_LIVE_EVAL=false
AI_TRANSLATION_ENABLED=false
AI_MARKETING_ENABLED=false
AUTO_REPLY_ENABLED=false
```

`TLS_CERT_DIR` 只是基础 production Compose 的插值兼容值；Rootless overlay 必须覆盖并消除证书挂载，业务服务器不得在该路径放活动证书。数据库、MinIO、JWT 和检索 Token 由安全渠道生成，不输出正文。模型六文件必须位于 `/home/crmdeploy/assets/models` 并匹配 `deploy/models/model-manifest.json`。

## 3. 两台服务器预检

先在本地干净、已 squash merge 的 `main` 记录完整 SHA；所有传输文件都按该提交逐项核对 SHA-256。

公网服务器以 root 只读检查：

```bash
set -euo pipefail
cat /etc/os-release | sed -n 's/^PRETTY_NAME=//p'
df -B1 / /home
free -b
ss -lntp
/www/server/nginx/sbin/nginx -t
find /www/server/panel/vhost/nginx -maxdepth 1 -type f -name '*.conf' -printf '%f\n' | sort
sshd -T | grep -E '^(allowtcpforwarding|gatewayports) '
```

业务服务器以 root 记录系统容器低敏基线，只保留 ID、名称、镜像、StartedAt、Running 和端口摘要；不要保存完整 inspect 或环境。复核 `/home` 容量、UID 1004、Rootless socket/data-root/security options、runner 状态和 10080 未被其他进程占用。任何公司容器差异立即停止并交由公司运维判断。

## 4. 转移已合并资产

从本地根仓库复制 `CRM智能聊天系统/deploy/staging/rootless/`、`deploy/nginx/nginx-tunnel.conf`、三层 Compose、门禁脚本和已合并源码到业务服务器的版本目录；公网服务器只接收两个 vhost、验证脚本和公网账号安装器。目标必须是新的、非符号链接目录，传输后逐文件比较本地/远端 SHA-256。

脚本语法和 unit 在使用前验证：

```bash
bash -n install-reverse-tunnel.sh install-public-tunnel-account.sh verify-split-ingress.sh
systemd-analyze --user verify systemd/user/crm-staging-tunnel.service
```

## 5. 专用 runner 安全维护（既有 Task 9）

安装器固定官方归档 URL/SHA-256，先校验再解压到 `/home/crmdeploy`，不安装 OS 包。PowerShell 基线 7.6.5、Runner 基线 2.336.0；已登记同名 runner 可保留 GitHub 的认证自动更新。原生依赖缺失、摘要不符、非本安装器目录或身份不符均停止，不运行 runner 的系统依赖自动安装脚本。

若目标主机无法稳定访问 GitHub Release，允许从本地通过受保护的 SSH/SCP 传入“密封归档”。这不是第三方镜像站：本地下载必须使用 `toolchain-manifest.json` 的原始官方 URL，传输前后均必须按同一清单 SHA-256 校验。远端文件名固定为 `/home/crmdeploy/.cache/crm-toolchain/sealed-<manifest filename>`；安装器若发现该路径存在但类型、符号链接、UID 1004 属主或摘要任一不符，立即失败且不退回网络。

在本地干净 `main` checkout 根目录执行下列 PowerShell。本地临时目录不得放入 Git，不得写入 Token 或私钥；上传完成并复核后再按团队保留策略处理本地副本。

```powershell
$rootlessAssets = Resolve-Path -LiteralPath './CRM智能聊天系统/deploy/staging/rootless'
$currentBranch = ([string](git branch --show-current)).Trim()
if ($LASTEXITCODE -ne 0 -or $currentBranch -ne 'main') { throw 'Runner assets must come from main' }
$worktreeChanges = @(git status --porcelain=v1)
if ($LASTEXITCODE -ne 0 -or $worktreeChanges.Count -ne 0) { throw 'Runner assets require a clean main checkout' }
$bootstrapRevision = ([string](git rev-parse HEAD)).Trim()
if ($LASTEXITCODE -ne 0 -or $bootstrapRevision -notmatch '^[0-9a-f]{40}$') { throw 'Cannot resolve a full merged HEAD' }
$bootstrapFiles = [ordered]@{
  'install-runner.sh' = Join-Path $rootlessAssets 'install-runner.sh'
  'toolchain-manifest.json' = Join-Path $rootlessAssets 'toolchain-manifest.json'
  'systemd/user/crm-staging-runner.service' = Join-Path $rootlessAssets 'systemd/user/crm-staging-runner.service'
}
$bootstrapDigests = @{}
foreach ($relativePath in $bootstrapFiles.Keys) {
  $digest = (Get-FileHash -LiteralPath $bootstrapFiles[$relativePath] -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($digest -notmatch '^[0-9a-f]{64}$') { throw "Cannot hash merged asset $relativePath" }
  $bootstrapDigests[$relativePath] = $digest
}

# 每次 SSH 都自包含相同的目录/文件门禁；不把前一次检查结果当作后一次调用的可信状态。
$remoteDirectoryGuard = 'set -euo pipefail; check_secure_directory() { local path=$1 mode; test -d "$path"; test ! -L "$path"; test "$(stat -c %u "$path")" = 1004; mode=$(stat -c %a "$path"); test "$((8#$mode & 0022))" = 0; };'
$remoteFileGuard = 'check_secure_file() { local path=$1 mode; test -f "$path"; test ! -L "$path"; test "$(stat -c %u "$path")" = 1004; mode=$(stat -c %a "$path"); test "$((8#$mode & 0022))" = 0; };'
$remoteTransferredFileGuard = 'normalize_transferred_file() { local path=$1 target_mode=$2; test -f "$path"; test ! -L "$path"; test "$(stat -c %u "$path")" = 1004; chmod "$target_mode" -- "$path"; check_secure_file "$path"; };'
$remoteHomeGuard = 'check_secure_directory /home/crmdeploy'
$remoteSrcGuard = 'check_secure_directory /home/crmdeploy/src'
$remoteDotCacheGuard = 'check_secure_directory /home/crmdeploy/.cache'
$remoteCacheGuard = 'check_secure_directory /home/crmdeploy/.cache/crm-toolchain'

# 合并资产先进入唯一目录，逐文件验签后原子提升；既有目标版本不允许被覆盖。
$transferId = [guid]::NewGuid().ToString('N')
$remoteTransferDir = "/home/crmdeploy/src/.incoming-bootstrap-$bootstrapRevision-$transferId"
$remoteBootstrap = "/home/crmdeploy/src/rootless-staging-bootstrap-$bootstrapRevision"
$prepareBootstrap = "$remoteDirectoryGuard $remoteHomeGuard; if [[ -e /home/crmdeploy/src || -L /home/crmdeploy/src ]]; then $remoteSrcGuard; else mkdir -m 0700 -- /home/crmdeploy/src; fi; $remoteSrcGuard; test ! -e '$remoteBootstrap'; test ! -L '$remoteBootstrap'; mkdir -m 0700 -- '$remoteTransferDir'; mkdir -m 0700 -- '$remoteTransferDir/systemd' '$remoteTransferDir/systemd/user'; check_secure_directory '$remoteTransferDir'; check_secure_directory '$remoteTransferDir/systemd'; check_secure_directory '$remoteTransferDir/systemd/user'"
ssh -i $env:CRM_STAGING_SSH_KEY crmdeploy@192.168.110.210 $prepareBootstrap
if ($LASTEXITCODE -ne 0) { throw 'Cannot prepare unique merged-asset directory' }
scp -i $env:CRM_STAGING_SSH_KEY $bootstrapFiles['install-runner.sh'] "crmdeploy@192.168.110.210:$remoteTransferDir/install-runner.sh"
if ($LASTEXITCODE -ne 0) { throw 'Cannot transfer merged install-runner.sh' }
scp -i $env:CRM_STAGING_SSH_KEY $bootstrapFiles['toolchain-manifest.json'] "crmdeploy@192.168.110.210:$remoteTransferDir/toolchain-manifest.json"
if ($LASTEXITCODE -ne 0) { throw 'Cannot transfer merged toolchain manifest' }
scp -i $env:CRM_STAGING_SSH_KEY $bootstrapFiles['systemd/user/crm-staging-runner.service'] "crmdeploy@192.168.110.210:$remoteTransferDir/systemd/user/crm-staging-runner.service"
if ($LASTEXITCODE -ne 0) { throw 'Cannot transfer merged runner unit' }
$runnerInstallerSha256 = $bootstrapDigests['install-runner.sh']
$toolchainManifestSha256 = $bootstrapDigests['toolchain-manifest.json']
$runnerUnitSha256 = $bootstrapDigests['systemd/user/crm-staging-runner.service']
$verifyBootstrap = "$remoteDirectoryGuard $remoteFileGuard $remoteTransferredFileGuard $remoteHomeGuard; $remoteSrcGuard; check_secure_directory '$remoteTransferDir'; check_secure_directory '$remoteTransferDir/systemd'; check_secure_directory '$remoteTransferDir/systemd/user'; normalize_transferred_file '$remoteTransferDir/install-runner.sh' 0700; normalize_transferred_file '$remoteTransferDir/toolchain-manifest.json' 0600; normalize_transferred_file '$remoteTransferDir/systemd/user/crm-staging-runner.service' 0600; printf '%s  %s\n' '$runnerInstallerSha256' '$remoteTransferDir/install-runner.sh' | sha256sum -c -; printf '%s  %s\n' '$toolchainManifestSha256' '$remoteTransferDir/toolchain-manifest.json' | sha256sum -c -; printf '%s  %s\n' '$runnerUnitSha256' '$remoteTransferDir/systemd/user/crm-staging-runner.service' | sha256sum -c -; bash -n '$remoteTransferDir/install-runner.sh'; test ! -e '$remoteBootstrap'; test ! -L '$remoteBootstrap'; mv -T -- '$remoteTransferDir' '$remoteBootstrap'; check_secure_directory '$remoteBootstrap'; check_secure_directory '$remoteBootstrap/systemd'; check_secure_directory '$remoteBootstrap/systemd/user'; check_secure_file '$remoteBootstrap/install-runner.sh'; check_secure_file '$remoteBootstrap/toolchain-manifest.json'; check_secure_file '$remoteBootstrap/systemd/user/crm-staging-runner.service'; printf '%s  %s\n' '$runnerInstallerSha256' '$remoteBootstrap/install-runner.sh' | sha256sum -c -; printf '%s  %s\n' '$toolchainManifestSha256' '$remoteBootstrap/toolchain-manifest.json' | sha256sum -c -; printf '%s  %s\n' '$runnerUnitSha256' '$remoteBootstrap/systemd/user/crm-staging-runner.service' | sha256sum -c -; bash -n '$remoteBootstrap/install-runner.sh'"
ssh -i $env:CRM_STAGING_SSH_KEY crmdeploy@192.168.110.210 $verifyBootstrap
if ($LASTEXITCODE -ne 0) { throw 'Merged runner assets failed remote verification or atomic promotion' }

$manifest = Get-Content -LiteralPath (Join-Path $rootlessAssets 'toolchain-manifest.json') -Raw | ConvertFrom-Json
$offlineCache = Join-Path ([IO.Path]::GetTempPath()) ('crm-runner-cache-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $offlineCache | Out-Null

$prepareToolchainCache = "$remoteDirectoryGuard $remoteHomeGuard; if [[ -e /home/crmdeploy/.cache || -L /home/crmdeploy/.cache ]]; then $remoteDotCacheGuard; else mkdir -m 0700 -- /home/crmdeploy/.cache; fi; $remoteDotCacheGuard; if [[ -e /home/crmdeploy/.cache/crm-toolchain || -L /home/crmdeploy/.cache/crm-toolchain ]]; then $remoteCacheGuard; else mkdir -m 0700 -- /home/crmdeploy/.cache/crm-toolchain; fi; $remoteCacheGuard"
ssh -i $env:CRM_STAGING_SSH_KEY crmdeploy@192.168.110.210 $prepareToolchainCache
if ($LASTEXITCODE -ne 0) { throw 'Cannot prepare remote toolchain cache' }

foreach ($toolName in @('runner', 'powershell')) {
  $entry = $manifest.$toolName
  $uri = [Uri]$entry.url
  if ($uri.Scheme -ne 'https' -or $uri.Host -ne 'github.com') { throw "Unexpected toolchain URL for $toolName" }
  $filename = [IO.Path]::GetFileName($uri.AbsolutePath)
  $expectedSha256 = ([string]$entry.sha256).ToLowerInvariant()
  if ($filename -notmatch '^[A-Za-z0-9._-]+$' -or $expectedSha256 -notmatch '^[0-9a-f]{64}$') { throw "Unsafe manifest metadata for $toolName" }
  $localArchive = Join-Path $offlineCache ('sealed-' + $filename)
  curl.exe --fail --location --proto '=https' --proto-redir '=https' --retry 5 --retry-all-errors --continue-at - --output $localArchive $entry.url
  if ($LASTEXITCODE -ne 0) { throw "Official download failed for $toolName" }
  $actualSha256 = (Get-FileHash -LiteralPath $localArchive -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actualSha256 -ne $expectedSha256) { throw "Local SHA-256 mismatch for $toolName" }

  # 先在新建的唯一目录中上传，避免 SCP 跟随既有 sealed 链接或把中断半包暴露为正式缓存。
  $transferId = [guid]::NewGuid().ToString('N')
  $remoteCacheTransferDir = "/home/crmdeploy/.cache/crm-toolchain/.incoming-$transferId"
  $remoteIncoming = "$remoteCacheTransferDir/archive"
  $remoteSealed = "/home/crmdeploy/.cache/crm-toolchain/sealed-$filename"
  $prepareRemote = "$remoteDirectoryGuard $remoteHomeGuard; $remoteDotCacheGuard; $remoteCacheGuard; mkdir -m 0700 -- '$remoteCacheTransferDir'; check_secure_directory '$remoteCacheTransferDir'; test ! -e '$remoteIncoming'; test ! -L '$remoteIncoming'; test ! -e '$remoteSealed'; test ! -L '$remoteSealed'"
  ssh -i $env:CRM_STAGING_SSH_KEY crmdeploy@192.168.110.210 $prepareRemote
  if ($LASTEXITCODE -ne 0) { throw "Remote sealed path already exists or incoming path is unsafe for $toolName" }
  scp -i $env:CRM_STAGING_SSH_KEY $localArchive "crmdeploy@192.168.110.210:$remoteIncoming"
  if ($LASTEXITCODE -ne 0) { throw "Archive transfer failed for $toolName" }
  $verifyAndPromote = "$remoteDirectoryGuard $remoteFileGuard $remoteTransferredFileGuard $remoteHomeGuard; $remoteDotCacheGuard; $remoteCacheGuard; check_secure_directory '$remoteCacheTransferDir'; normalize_transferred_file '$remoteIncoming' 0600; test ! -e '$remoteSealed'; test ! -L '$remoteSealed'; printf '%s  %s\n' '$expectedSha256' '$remoteIncoming' | sha256sum -c -; mv -T -- '$remoteIncoming' '$remoteSealed'; rmdir -- '$remoteCacheTransferDir'; $remoteHomeGuard; $remoteDotCacheGuard; $remoteCacheGuard; check_secure_file '$remoteSealed'; printf '%s  %s\n' '$expectedSha256' '$remoteSealed' | sha256sum -c -"
  ssh -i $env:CRM_STAGING_SSH_KEY crmdeploy@192.168.110.210 $verifyAndPromote
  if ($LASTEXITCODE -ne 0) { throw "Remote verification or atomic promotion failed for $toolName; inspect the unique incoming directory" }
}
```

传输后先以 `crmdeploy` 身份重新校验类型、链接、属主和摘要，再申请 Runner 注册 Token。下列摘要必须与当前合并后清单逐字一致；版本升级时不得沿用本示例值。

```bash
set -euo pipefail
cache=/home/crmdeploy/.cache/crm-toolchain
test -f "$cache/sealed-actions-runner-linux-x64-2.336.0.tar.gz"
test ! -L "$cache/sealed-actions-runner-linux-x64-2.336.0.tar.gz"
test "$(stat -c %u "$cache/sealed-actions-runner-linux-x64-2.336.0.tar.gz")" = 1004
test -f "$cache/sealed-powershell-7.6.5-linux-x64.tar.gz"
test ! -L "$cache/sealed-powershell-7.6.5-linux-x64.tar.gz"
test "$(stat -c %u "$cache/sealed-powershell-7.6.5-linux-x64.tar.gz")" = 1004
chmod 0600 "$cache/sealed-actions-runner-linux-x64-2.336.0.tar.gz"
chmod 0600 "$cache/sealed-powershell-7.6.5-linux-x64.tar.gz"
printf '%s  %s\n' '04cf0be1aff4c3ec3554466c39124ca250e3effd8873bb7e8d68535aa9505d5d' "$cache/sealed-actions-runner-linux-x64-2.336.0.tar.gz" | sha256sum -c -
printf '%s  %s\n' 'b34ab3b19acac1d3d4d0d3cfdb02acf62f457b0b6a962ff008132033f7566844' "$cache/sealed-powershell-7.6.5-linux-x64.tar.gz" | sha256sum -c -
```

本地 PowerShell 先确认仓库 runner 管理权限，再将一小时注册 Token 仅经 stdin 传递。Windows 原生管道产生 CRLF，远端 `tr` 删除 CR、保留 LF。Token-bearing SSH 直接执行由完整远端复验和安装器管道组成的 `$invokeVerifiedRunner`，不再嵌套 `bash -c` 引号；同一进程的 `set -euo pipefail` 会在任一复验失败时阻止读取 Token 和启动安装器。Token 不拼入 SSH 命令参数、不写临时文件或环境，也不输出；不要启用命令转录/调试或打印变量：

```powershell
$runnerBranch = ([string](git branch --show-current)).Trim()
if ($LASTEXITCODE -ne 0 -or $runnerBranch -ne 'main') { throw 'Runner registration requires main' }
$runnerWorktreeChanges = @(git status --porcelain=v1)
if ($LASTEXITCODE -ne 0 -or $runnerWorktreeChanges.Count -ne 0) { throw 'Runner registration requires a clean main checkout' }
$runnerBootstrapRevision = ([string](git rev-parse HEAD)).Trim()
if ($LASTEXITCODE -ne 0 -or $runnerBootstrapRevision -notmatch '^[0-9a-f]{40}$') { throw 'Cannot re-resolve merged runner HEAD' }
$runnerRootlessAssets = Resolve-Path -LiteralPath './CRM智能聊天系统/deploy/staging/rootless'
$runnerBootstrapFiles = [ordered]@{
  'install-runner.sh' = Join-Path $runnerRootlessAssets 'install-runner.sh'
  'toolchain-manifest.json' = Join-Path $runnerRootlessAssets 'toolchain-manifest.json'
  'systemd/user/crm-staging-runner.service' = Join-Path $runnerRootlessAssets 'systemd/user/crm-staging-runner.service'
}
$runnerBootstrapDigests = @{}
foreach ($relativePath in $runnerBootstrapFiles.Keys) {
  $digest = (Get-FileHash -LiteralPath $runnerBootstrapFiles[$relativePath] -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($digest -notmatch '^[0-9a-f]{64}$') { throw "Cannot re-hash merged asset $relativePath" }
  $runnerBootstrapDigests[$relativePath] = $digest
}
$runnerInstallerSha256 = $runnerBootstrapDigests['install-runner.sh']
$toolchainManifestSha256 = $runnerBootstrapDigests['toolchain-manifest.json']
$runnerUnitSha256 = $runnerBootstrapDigests['systemd/user/crm-staging-runner.service']
$runnerBootstrap = "/home/crmdeploy/src/rootless-staging-bootstrap-$runnerBootstrapRevision"
$runnerInstaller = "/home/crmdeploy/src/rootless-staging-bootstrap-$runnerBootstrapRevision/install-runner.sh"
$runnerManifest = "$runnerBootstrap/toolchain-manifest.json"
$runnerUnit = "$runnerBootstrap/systemd/user/crm-staging-runner.service"
$remoteDirectoryGuard = 'set -euo pipefail; check_secure_directory() { local path=$1 mode; test -d "$path"; test ! -L "$path"; test "$(stat -c %u "$path")" = 1004; mode=$(stat -c %a "$path"); test "$((8#$mode & 0022))" = 0; };'
$remoteFileGuard = 'check_secure_file() { local path=$1 mode; test -f "$path"; test ! -L "$path"; test "$(stat -c %u "$path")" = 1004; mode=$(stat -c %a "$path"); test "$((8#$mode & 0022))" = 0; };'
$remoteHomeGuard = 'check_secure_directory /home/crmdeploy'
$remoteSrcGuard = 'check_secure_directory /home/crmdeploy/src'
$verifyRunnerBootstrap = "$remoteDirectoryGuard $remoteFileGuard $remoteHomeGuard; $remoteSrcGuard; check_secure_directory '$runnerBootstrap'; check_secure_directory '$runnerBootstrap/systemd'; check_secure_directory '$runnerBootstrap/systemd/user'; check_secure_file '$runnerInstaller'; check_secure_file '$runnerManifest'; check_secure_file '$runnerUnit'; printf '%s  %s\n' '$runnerInstallerSha256' '$runnerInstaller' | sha256sum -c -; printf '%s  %s\n' '$toolchainManifestSha256' '$runnerManifest' | sha256sum -c -; printf '%s  %s\n' '$runnerUnitSha256' '$runnerUnit' | sha256sum -c -; bash -n '$runnerInstaller'"
$invokeVerifiedRunner = "$verifyRunnerBootstrap; tr -d '\r' | bash '$runnerInstaller'"
ssh -i $env:CRM_STAGING_SSH_KEY crmdeploy@192.168.110.210 $verifyRunnerBootstrap
if ($LASTEXITCODE -ne 0) { throw 'Versioned runner assets failed final verification; no Token requested' }
gh api repos/CP11-gh/CRM/actions/runners --jq '.total_count'
if ($LASTEXITCODE -ne 0) { throw 'Repository administrator action required' }
$runnerToken = $null
try {
  $runnerToken = gh api -X POST repos/CP11-gh/CRM/actions/runners/registration-token --jq '.token'
  if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($runnerToken)) { throw 'No registration token returned' }
  $runnerToken | ssh -i $env:CRM_STAGING_SSH_KEY crmdeploy@192.168.110.210 $invokeVerifiedRunner
  if ($LASTEXITCODE -ne 0) { throw 'Runner install failed' }
} finally { $runnerToken = $null }
gh api repos/CP11-gh/CRM/actions/runners --jq '.runners[] | select(.name=="crm-staging-192-168-110-210") | {name,status,busy,labels:[.labels[].name]}'
```

以 `crmdeploy` 验证，不输出其认证文件：

```bash
/home/crmdeploy/tools/powershell/pwsh --version
/home/crmdeploy/runner/bin/Runner.Listener --version
XDG_RUNTIME_DIR=/run/user/1004 systemctl --user is-active crm-staging-runner.service
```

GitHub `staging` Environment 限制 main，Secret `CRM_STAGING_ENV_FILE` 仅保存上述绝对路径，Variable `CRM_STAGING_BASE_URL` 保存精确域名。runner 标签必须有 `self-hosted,linux,x64,crm-staging`，用户实际 UID 必须为 1004。工作流通过短期 `GITHUB_TOKEN`、`contents: read/packages: read` 登录 GHCR；私有包应授予本仓库 Actions 读取权，不在环境文件保存 PAT。

## 6. 安装受限账号并建立隧道

### 6.1 生成独立身份并固定主机指纹

在公网服务器记录真实 Ed25519 主机公钥指纹：

```bash
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

在业务服务器以 `crmdeploy` 创建独立目录和密钥；不得复用登录服务器的运维私钥：

```bash
install -d -m 0700 /home/crmdeploy/secrets/tunnel
ssh-keygen -t ed25519 -a 64 -N '' -C crm-staging-reverse-tunnel -f /home/crmdeploy/secrets/tunnel/id_ed25519
chmod 0600 /home/crmdeploy/secrets/tunnel/id_ed25519
ssh-keyscan -T 10 -t ed25519 38.55.145.52 > /home/crmdeploy/secrets/tunnel/known_hosts.pending
ssh-keygen -lf /home/crmdeploy/secrets/tunnel/known_hosts.pending
```

人工比较两端指纹完全一致后，才把 `known_hosts.pending` 原子提升为 `known_hosts` 并设为 `0600`。指纹不一致立即停止，不能关闭主机校验。

### 6.2 公网服务器安装账号

只把 `id_ed25519.pub` 传到公网服务器受限临时路径，然后以 root 运行已合并安装器：

```bash
bash install-public-tunnel-account.sh /root/crm-staging-tunnel.pub
getent passwd crm-tunnel
sshd -T | grep -E '^(allowtcpforwarding|gatewayports) '
```

核对账号 home 为 `/home/crm-tunnel`、shell 为 `/usr/sbin/nologin`、密码锁定，授权项只允许 `127.0.0.1:18080`。随后删除传输的公钥临时副本；公钥非秘密，但不应成为漂移配置源。

### 6.3 业务服务器启动用户服务

以 `crmdeploy` 运行：

```bash
bash install-reverse-tunnel.sh
systemctl --user is-enabled crm-staging-tunnel.service
systemctl --user is-active crm-staging-tunnel.service
```

公网服务器必须只看到回环监听：

```bash
ss -H -ltn 'sport = :18080'
```

结果必须包含 `127.0.0.1:18080`，且不得包含 `0.0.0.0`、`[::]` 或公网网卡地址。此时业务端 10080 尚未启动也允许隧道存在，HTTP 健康会失败关闭。

## 7. 公网 HTTP、DNS 与 TLS

### 7.1 安装 HTTP 引导 vhost

先保存现有同名文件和其他站点低敏响应摘要。创建 ACME webroot，安装 `public-nginx/staging.overselfx.com-http.conf`。只有语法通过才 reload；失败时恢复备份并再次语法检查。

```bash
install -d -m 0755 /www/wwwroot/staging.overselfx.com/.well-known/acme-challenge
install -m 0644 staging.overselfx.com-http.conf /www/server/panel/vhost/nginx/staging.overselfx.com.conf
/www/server/nginx/sbin/nginx -t
/www/server/nginx/sbin/nginx -s reload
printf '%s\n' crm-staging-acme-probe > /www/wwwroot/staging.overselfx.com/.well-known/acme-challenge/probe
curl --fail --resolve staging.overselfx.com:80:38.55.145.52 http://staging.overselfx.com/.well-known/acme-challenge/probe | grep -Fx crm-staging-acme-probe
rm -- /www/wwwroot/staging.overselfx.com/.well-known/acme-challenge/probe
```

探针不含凭据，验证后立即删除。除 ACME 和 `/healthz` 外，HTTP 引导 vhost 必须返回 503。

### 7.2 切换 DNS

域名管理后台把唯一 A 记录改为 `38.55.145.52`，移除冲突 A/AAAA。至少用三个公共解析器确认：

```bash
dig +short A staging.overselfx.com @1.1.1.1
dig +short A staging.overselfx.com @8.8.8.8
dig +short A staging.overselfx.com @9.9.9.9
```

三者未全部返回 `38.55.145.52` 时不得签发证书或写“DNS 已通过”。

### 7.3 签发无邮箱公信证书

先确认 `certbot` 已由服务器管理员批准并安装；不得为本任务擅自更换宝塔或其他站点的 ACME 机制：

```bash
certbot certonly --webroot -w /www/wwwroot/staging.overselfx.com -d staging.overselfx.com --agree-tos --register-unsafely-without-email --non-interactive
openssl x509 -checkhost staging.overselfx.com -in /etc/letsencrypt/live/staging.overselfx.com/fullchain.pem -noout
openssl x509 -checkend 2592000 -in /etc/letsencrypt/live/staging.overselfx.com/fullchain.pem -noout
```

只输出公开证书信息，不输出私钥。证书路径、续期方式或 Nginx 读取权限不满足时停止。

### 7.4 切换正式 vhost

原子安装 `public-nginx/staging.overselfx.com.conf`，`nginx -t` 通过后 reload。验证 HTTP 301、TLSv1.2/1.3、证书 SAN，以及所有其他 vhost 的前后摘要不变。正式上游只能是 `127.0.0.1:18080`。

## 8. Validate 与失败关闭部署

候选的 backend、frontend、retrieval 必须来自本次合并后完整 main SHA，并用三条 `repository@sha256:<64-hex>` 输入。以 `crmdeploy` 在干净 main checkout 根执行：

```powershell
$common = @{
  Environment = 'staging'
  ConfirmTarget = 'staging'
  DockerHost = 'unix:///run/user/1004/docker.sock'
  EnvFile = '/home/crmdeploy/config/crm-staging.env'
  BaseUrl = 'https://staging.overselfx.com'
}
$candidate = @{
  BackendImage = Read-Host 'Reviewed backend repository@sha256'
  FrontendImage = Read-Host 'Reviewed frontend repository@sha256'
  RetrievalModelImage = Read-Host 'Reviewed retrieval repository@sha256'
}
& './CRM智能聊天系统/scripts/Test-StagingProductionGates.ps1' @common @candidate -EvidenceFile '/home/crmdeploy/evidence/validate.json' -ValidateOnly
```

validate 只证明输入、模型目录和合并 Compose 契约；不拉镜像、不证明容器或公网可用。确认 Rootless 有受控短期 GHCR 登录后执行：

```powershell
& './CRM智能聊天系统/scripts/Test-StagingProductionGates.ps1' @common @candidate -EvidenceFile '/home/crmdeploy/evidence/deploy.json' -Deploy -Confirm
```

脚本使用 `--no-build --wait --wait-timeout 600`。任一服务失败就保持真实失败，不能切系统 Docker、打开 Mock 或跳过摘要。部署后迁移 head 必须为 `023_marketing_review_idempotency`。

## 9. G0 验证

### 9.1 公网链路

准备一个 `0600`、仓库外的已登录 Cookie jar 和一个授权会话 UUID，在公网服务器运行：

```bash
bash verify-split-ingress.sh /root/protected-crm-cookie.jar AUTHORIZED_SESSION_UUID
```

脚本检查三个 DNS 解析器、证书 SAN/有效期、回环 18080、HTTP 301、`/healthz`、`/v1/health`、`/v1/health/ready` 和 SSE `text/event-stream`，不保存响应正文。用完安全删除 Cookie jar。

### 9.2 Rootless 与恢复

- 所有 CRM 容器 healthy，Rootless data-root 位于 `/home/crmdeploy`，系统 Docker 没有 CRM 资源。
- 六个模型文件启动 SHA-256 校验通过，四个应用服务的十项能力开关全部为 false。
- 重启 Rootless 应用、断开并恢复隧道后，健康端点自动恢复；隧道中断期间公网必须 502，不得绕过到其他地址。
- PostgreSQL 和 MinIO 备份必须在隔离目标完成恢复，核对迁移、对象数量/摘要和审计。
- 上一版三个镜像必须证明兼容当前 callback、迁移 023 和配置，才能执行 `Invoke-StagingRollbackDrill.ps1 -Execute`；回滚后还要切回候选。
- 重新计算公司系统容器和公网其他 vhost 的低敏摘要，必须与预检一致。

任一项未执行都不能写“G0 通过”。

## 10. 停止与撤除

紧急关闭入口时，先在业务服务器以 `crmdeploy` 停止隧道：

```bash
systemctl --user stop crm-staging-tunnel.service
```

这会移除公网 `127.0.0.1:18080`，公网 Nginx 失败关闭。应用可按需要继续保留供本机调查。恢复前先确认 unit、私钥权限和主机指纹，再启动服务。

旧 `crm-staging-http.socket`、`crm-staging-https.socket` 及对应 service 是 ADR-007 的历史入口，必须保持 disabled，不得运行 `install-entry-proxy.sh`。删除旧 unit、Rootless 数据、镜像、卷、备份、runner 或账号需要单独明确批准；不得操作公司系统 Docker。

## 11. G1～G6 与证据

G0 独立通过后，按 G1 OAuth/读取 → G2 Webhook → G3 单操作员人工消息 → G4 AI/RAG → G5 50 个独立授权客户端 SSE → G6 连续五个真实日历日、99.5% 可用性推进。每级使用独立受审阅配置，失败即回到前一安全能力集。

所有低敏证据至少记录：完整 main SHA、三条应用 RepoDigest、外部镜像摘要、overlay/config/model manifest SHA-256、迁移、UTC 时间、主机角色、健康、恢复/回滚和工作流 run ID。私钥、Token、Cookie、环境正文、客户消息、模型权重和完整容器 inspect 不进入 Git、日志或 Actions 制品。
