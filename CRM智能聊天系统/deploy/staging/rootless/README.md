# Rootless Docker staging 运行手册

日期：2026-09-09。状态：仓库工程已交付，真实主机执行待验证。架构依据为 `架构师/ADR-007-INFRA-Rootless-Staging部署边界-v1.0.md`；工程及后续现场证据统一登记到 `测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-Rootless-Staging运行面-综合测试-007.md`。本文中的命令是后续执行步骤，不是执行成功记录。

## 1. 范围与四个独立门禁

| 门禁 | 必须取得的证据 | 当前状态 |
| --- | --- | --- |
| 基础运行面就绪 | UID、Rootless socket/security options、/home 存储、用户服务、公司容器前后不变 | 未执行 |
| 失败关闭部署通过 | 不可变镜像、外部模型/TLS、全部能力关闭、HTTPS 健康、备份恢复与兼容版本回滚 | 未执行 |
| G1～G6 真实门禁通过 | OAuth/读取、Webhook、人工发送、AI/RAG、真实 SSE、连续五日稳定性独立证据 | 未执行 |
| production 放行 | 生产运行方案另行评审，并完成适用 G0～G6 与 G8 签署 | 未批准 |

四者互不推导：前一个通过不代表下一个通过。当前只实现 TikTok 人工辅助首版；产品与 UI 保留三平台，Shopee/Amazon 真实接入、高风险写入、自动回复和营销不在本次范围。

服务器为 `192.168.110.210`（公网 `183.158.225.78`），用户固定为 `crmdeploy`、UID/GID `1004`、home `/home/crmdeploy`。系统 Docker 和公司容器不属于项目操作范围，禁止停止、重启、改配置、迁移、修复或接管。前后容器 ID/名称/镜像 ID/StartedAt/Running 任一变化就是硬停点；调查证据并交由公司运维判断，不能自动修复公司负载。

唯一公网入口为四个 CRM systemd 单元提供的 80/443 TCP 转发，目标为 Rootless proxy 的 `127.0.0.1:10080/10443`。Docker API 不监听 TCP。Rootless 数据预期为 `/home/crmdeploy/.local/share/docker`，实际路径与 security options 以 Task 8 的 `docker info` 证据为准。

## 2. 固定参数和前置材料

```text
DOCKER_HOST=unix:///run/user/1004/docker.sock
COMPOSE_PROJECT_NAME=crm-staging
CRM_STAGING_ENV_FILE=/home/crmdeploy/config/crm-staging.env
CRM_STAGING_BASE_URL=https://staging.hophorsefit.com
```

仓库外配置由主机管理员安全写入，权限 `0600`，不要复制开发 `.env.example` 后直接运行。公网值必须是：

```text
APP_ENV=staging
PUBLIC_BASE_URL=https://staging.hophorsefit.com
PUBLIC_API_BASE_URL=https://staging.hophorsefit.com/v1
CORS_ORIGINS=https://staging.hophorsefit.com
TIKTOK_OAUTH_REDIRECT_URI=https://staging.hophorsefit.com/v1/integrations/tiktok/oauth/callback
TLS_CERT_DIR=/home/crmdeploy/secrets/tls/staging.hophorsefit.com
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

数据库、MinIO、JWT、检索服务 Token 等由安全渠道生成/注入；TikTok 与 DeepSeek 凭据在各自真实门禁窗口前留空。模型六个普通文件必须在 checkout 外：`bge-m3/{config.json,pytorch_model.bin,tokenizer.json}`、`bge-reranker-large/{config.json,model.safetensors,tokenizer.json}`，拒绝路径链上的符号链接。`deploy/models/model-manifest.json` 当前只登记两份权重的 SHA-256；启动时验证这两份权重。四个辅助 JSON 文件的逐文件摘要来源仍需 Task 10 补齐，不能声称已完成六文件哈希验证。

`BACKEND_IMAGE`、`FRONTEND_IMAGE`、`RETRIEVAL_MODEL_SERVICE_IMAGE` 必须来自本分支合并后完整 main SHA 的发布制品，均为 `repository@sha256:<64-hex>`；不得使用标签替代摘要或在主机 build。`release/images/mvp-production-gates.json` 的 `f7c0f9f9` 是历史已发布版本，不包含本次 staging 回调改动，不能当成本次候选。四个外部运行镜像的摘要继续取该清单 `external_images`。候选发布、配置同步和真实拉取均待执行。

DNS A 记录 `staging.hophorsefit.com → 183.158.225.78`、上游 NAT/80/443、公信 TLS、模型和真实配置目前均待外部提供/验证。TLS 由域名管理员通过公司 CA/ACME 流程签发，仓库不处理 DNS/CA 凭据。证书目录与两份文件采用 `root:crmdeploy`，目录 `0750`、文件 `0640`；`crmdeploy` 可读、不可改私钥。验证 SAN、有效期、证书链与私钥匹配，只输出公开证书信息。缺任一材料时停在 validate 前，不生成“部署通过”。

## 3. 转移资产与主机预检（Task 8）

只转移已审阅并合并的资产。以下 PowerShell 在本地干净 main checkout 根执行；`CRM_STAGING_SSH_KEY` 指向已设定最小 ACL 的 SSH 私钥文件，不能将私钥复制进仓库。首次 SSH 必须经管理员核对主机指纹，不能关闭主机密钥校验。

```powershell
if (!(Test-Path -LiteralPath $env:CRM_STAGING_SSH_KEY -PathType Leaf)) { throw 'Missing protected SSH key path' }
git status --short --branch
git rev-parse HEAD
ssh -i $env:CRM_STAGING_SSH_KEY root@192.168.110.210 'test ! -e /home/crmdeploy/src/rootless-staging-bootstrap && install -d -o crmdeploy -g crmdeploy -m 0750 /home/crmdeploy/src/rootless-staging-bootstrap'
if ($LASTEXITCODE -ne 0) { throw 'Transfer target exists or cannot be created; inspect before overwriting' }
scp -r -i $env:CRM_STAGING_SSH_KEY './CRM智能聊天系统/deploy/staging/rootless/.' 'root@192.168.110.210:/home/crmdeploy/src/rootless-staging-bootstrap/'
if ($LASTEXITCODE -ne 0) { throw 'Asset transfer failed' }
```

在服务器 root shell 执行以下检查。确认源文件与合并提交逐文件 SHA-256 一致，并确认目标目录无链接后才调整该精确目录的归属。已存在目录时不覆盖；先核对版本。

```bash
set -euo pipefail
test "$(realpath -e /home/crmdeploy/src/rootless-staging-bootstrap)" = /home/crmdeploy/src/rootless-staging-bootstrap
test -z "$(find /home/crmdeploy/src/rootless-staging-bootstrap -type l -print -quit)"
chown -R crmdeploy:crmdeploy /home/crmdeploy/src/rootless-staging-bootstrap
bash -n /home/crmdeploy/src/rootless-staging-bootstrap/bootstrap-host.sh
bash -n /home/crmdeploy/src/rootless-staging-bootstrap/install-entry-proxy.sh
bash -n /home/crmdeploy/src/rootless-staging-bootstrap/install-runner.sh
systemd-analyze verify /home/crmdeploy/src/rootless-staging-bootstrap/systemd/crm-staging-http.socket /home/crmdeploy/src/rootless-staging-bootstrap/systemd/crm-staging-http.service /home/crmdeploy/src/rootless-staging-bootstrap/systemd/crm-staging-https.socket /home/crmdeploy/src/rootless-staging-bootstrap/systemd/crm-staging-https.service
id crmdeploy
getent passwd crmdeploy
df -B1 / /home
ss -lntp
env -i PATH=/usr/bin:/bin HOME=/root /usr/bin/docker --host unix:///var/run/docker.sock info --format '{{.DockerRootDir}}'
```

预检要求 Ubuntu 26.04 x86_64、systemd 259、根盘至少 1.5 GiB 可用、UID/GID/home 精确匹配、既有 subuid/subgid 各至少 65536、用户不在 docker/sudo 组。检查已有用户 Docker 配置和 user unit；未知自定义配置必须先停止推进，不启动它验证后再补救。核对系统容器与既有基线，80/443 必须空闲或经安装器确认属于同版本 CRM socket。不要打印完整 Docker inspect 或环境文件。

执行 bootstrap：

```bash
bash /home/crmdeploy/src/rootless-staging-bootstrap/bootstrap-host.sh
runuser -u crmdeploy -- env -i PATH=/usr/bin:/bin HOME=/home/crmdeploy XDG_RUNTIME_DIR=/run/user/1004 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1004/bus /usr/bin/docker --host unix:///run/user/1004/docker.sock info --format '{{json .SecurityOptions}} {{.DockerRootDir}}'
runuser -u crmdeploy -- env -i PATH=/usr/bin:/bin HOME=/home/crmdeploy XDG_RUNTIME_DIR=/run/user/1004 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1004/bus systemctl --user is-active docker.service
runuser -u crmdeploy -- env -i PATH=/usr/bin:/bin HOME=/home/crmdeploy XDG_RUNTIME_DIR=/run/user/1004 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1004/bus systemctl --user is-enabled docker.service
```

bootstrap 只显式安装 `uidmap`，`NEEDRESTART_MODE=l`；启用 linger 和用户 Docker。成功/失败都会在 `/home/crmdeploy/evidence/host-baseline-before/run-*` 与同名 `host-baseline-after/run-*` 保留容器快照与比较，退出码必须为 0 且差异为空。失败保留安装状态供调查，不自动卸包或删数据。实际 Linux 幂等、错误路径及 socket 激活测试仍待执行，禁止通过真实重启公司容器制造失败注入。

## 4. 专用 runner（Task 9）

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

## 5. validate、入口、deploy 与健康（Tasks 10～11）

优先在 GitHub Actions 的 `Staging production gates` 手工运行：选 main、输入 `operation=validate`、`confirm_target=staging` 与已审阅候选的三个完整摘要。工作流拉取已审阅 main、精确校验基础 URL、按 UID 推导 DockerHost。两个脚本均清除继承 `DOCKER_CONTEXT`，显式设置 Rootless `DOCKER_HOST` 并在所有路径退出时恢复。

直接 validate 的等价命令如下，在服务器 `crmdeploy` 的 PowerShell 7 中执行；先 `Set-Location` 到经审阅的 Git checkout 根。三个输入是公开摘要，不能填 Token：

```powershell
$candidateBackend = Read-Host 'Reviewed candidate backend repository@sha256'
$candidateFrontend = Read-Host 'Reviewed candidate frontend repository@sha256'
$candidateRetrieval = Read-Host 'Reviewed candidate retrieval repository@sha256'
$common = @{
  Environment = 'staging'
  ConfirmTarget = 'staging'
  DockerHost = 'unix:///run/user/1004/docker.sock'
  EnvFile = '/home/crmdeploy/config/crm-staging.env'
  BaseUrl = 'https://staging.hophorsefit.com'
}
$candidate = @{
  BackendImage = $candidateBackend
  FrontendImage = $candidateFrontend
  RetrievalModelImage = $candidateRetrieval
}
& './CRM智能聊天系统/scripts/Test-StagingProductionGates.ps1' @common @candidate -EvidenceFile '/home/crmdeploy/evidence/validate.json' -ValidateOnly
```

validate 检查输入/模型目录和合并 Compose，不拉取镜像、不探测公信证书、不证明容器可启动。其 `validated` JSON 不能用作部署通过。Compose 固定项目名 `crm-staging`、profile `ai`、基础/prod/rootless 三层；外部配置必须与候选 retrieval 摘要一致。不得打印展开的 `docker compose config`、完整容器环境或连接串。

在首次 deploy 前安装入口 socket，以供 deploy 后的公网健康探针使用；socket 可以在后端高端口尚未启动时监听，这不证明转发成功。root 执行：

```bash
bash /home/crmdeploy/src/rootless-staging-bootstrap/install-entry-proxy.sh
systemctl is-active crm-staging-http.socket crm-staging-https.socket
ss -lntp 'sport = :80 or sport = :443'
```

安装器拒绝外来端口占用、同名不同内容 unit、drop-in、symlink/mask 和未 reload 配置。失败只撤销本次新增入口变化。未收到连接时 service inactive 是正常情况；连接后 socket 可以为 `running`。Task 11 必须建立连接后再运行同一安装器验证幂等。

DNS/TLS、模型、配置、候选与入口全部确认后，使用工作流 `operation=deploy`（其 GHCR 登录自动清理）；直接运行仅限已有受控短期 registry 认证的窗口：

```powershell
& './CRM智能聊天系统/scripts/Test-StagingProductionGates.ps1' @common @candidate -EvidenceFile '/home/crmdeploy/evidence/deploy.json' -Deploy -Confirm
```

脚本 `up` 使用 `--no-build --wait --wait-timeout 600`，模型启动哈希计算可能耗时。任一容器或健康失败立即停止，不重试开能力。用外部网络检查 DNS、TLS 与以下入口；不要用 `-k` 忽略证书问题：

```powershell
Resolve-DnsName staging.hophorsefit.com -Type A
Test-NetConnection staging.hophorsefit.com -Port 80
Test-NetConnection staging.hophorsefit.com -Port 443
curl.exe --fail --proto '=https' https://staging.hophorsefit.com/
curl.exe --fail --proto '=https' https://staging.hophorsefit.com/healthz
curl.exe --fail --proto '=https' https://staging.hophorsefit.com/v1/health
curl.exe --fail --proto '=https' https://staging.hophorsefit.com/v1/health/ready
```

以上响应不能包含连接串、路径、凭据和原始异常。容器能力检查只提取已列出的十项布尔开关，四个应用服务必须全部 false。`llm_provider=disabled` 属于初次部署预期；ready 不调用真实 DeepSeek。合并后的 Git SHA、镜像摘要、时间、迁移 `023_marketing_review_idempotency`、配置版本/受控摘要需要另行记录，现有门禁 JSON 不会自动提供完整发布基线。

## 6. 备份、恢复与镜像回滚

先记录系统公司容器保护快照。备份在 `crmdeploy` 的 PowerShell 中执行，使用完整 Compose 环境以防老脚本选中默认项目。进入产品目录，备份目录必须仓库外、受访问控制并由运维加密保管：

```powershell
Set-Location './CRM智能聊天系统'
$env:DOCKER_HOST = 'unix:///run/user/1004/docker.sock'
Remove-Item Env:DOCKER_CONTEXT -ErrorAction SilentlyContinue
$env:COMPOSE_PROJECT_NAME = 'crm-staging'
$env:COMPOSE_PROFILES = 'ai'
$env:COMPOSE_ENV_FILES = '/home/crmdeploy/config/crm-staging.env'
$env:COMPOSE_FILE = 'docker-compose.yml:docker-compose.prod.yml:docker-compose.rootless-staging.yml'
$backupRun = Get-Date -Format 'yyyyMMdd-HHmmss'
& './scripts/backup-postgres.ps1' -OutputFile "/home/crmdeploy/backups/$backupRun/postgres.sql"
& './scripts/backup-minio.ps1' -OutputDirectory "/home/crmdeploy/backups/$backupRun/minio"
```

旧 `restore-*` 会写入选定数据库/MinIO，不能直接对当前 staging 执行。Task 11 必须先建立隔离恢复目标、明确目标名称和备份路径，再依 `deploy/postgres/README.md` 执行受确认的恢复，核对迁移、对象数量/摘要和审计。隔离恢复目标与命令尚待现场确定，当前恢复门禁未执行；不要把备份脚本退出 0 当作恢复通过。删除恢复目标或任何数据需要单独明确批准。

镜像回滚前必须证明上一版三个摘要与候选分别不同，且兼容 staging 回调、迁移 023 和配置。历史清单 `f7c0f9f9` 的 OAuth 仅接受 www，不能直接沿用 staging 回调做成功回滚；在兼容性方案经过架构确认前，停止真实回滚。不得为了演练将 staging 回调切到 production 域名。

兼容前置项齐全后，从 checkout 根、沿用第 5 节 `$common/$candidate*`，进行只验证再执行：

```powershell
$rollback = @{
  CandidateBackendImage = $candidateBackend
  CandidateFrontendImage = $candidateFrontend
  CandidateRetrievalModelImage = $candidateRetrieval
  PreviousBackendImage = (Read-Host 'Approved compatible previous backend repository@sha256')
  PreviousFrontendImage = (Read-Host 'Approved compatible previous frontend repository@sha256')
  PreviousRetrievalModelImage = (Read-Host 'Approved compatible previous retrieval repository@sha256')
}
& './CRM智能聊天系统/scripts/Invoke-StagingRollbackDrill.ps1' @common @rollback -EvidenceFile '/home/crmdeploy/evidence/rollback-plan.json' -ValidateOnly
# 只有兼容性核验和恢复准备完成后执行下一行；也可工作流 operation=rollback。
& './CRM智能聊天系统/scripts/Invoke-StagingRollbackDrill.ps1' @common @rollback -EvidenceFile '/home/crmdeploy/evidence/rollback.json' -Execute -Confirm
```

执行顺序为关闭能力、切上一版、验证三个健康端点；结束停在上一版，需单独以 `deploy` 切回候选。脚本不自动降级数据库、不删除业务记录。运行后重新比较公司容器 ID/StartedAt 等五字段，并确认系统 Docker 未新增 CRM 数据、根盘仍至少 1.5 GiB。

## 7. 停止与撤除边界

入口紧急停止只针对下面四个单元；先停 socket，避免 service 被再次激活：

```bash
systemctl stop crm-staging-http.socket crm-staging-https.socket
systemctl stop crm-staging-http.service crm-staging-https.service
systemctl disable crm-staging-http.socket crm-staging-https.socket
```

确需撤除入口时，root 先逐一验证内容/归属/无 drop-in，再删除四个精确文件（服务为 socket 激活，没有单独 enable）：

```bash
set -euo pipefail
for unit in crm-staging-http.socket crm-staging-http.service crm-staging-https.socket crm-staging-https.service; do
  test ! -L "/etc/systemd/system/$unit"
  test "$(stat -c '%u:%g:%a' "/etc/systemd/system/$unit")" = 0:0:644
  test -z "$(systemctl show "$unit" --property=DropInPaths --value)"
  cmp -s "/home/crmdeploy/src/rootless-staging-bootstrap/systemd/$unit" "/etc/systemd/system/$unit"
done
systemctl stop crm-staging-http.socket crm-staging-https.socket
systemctl stop crm-staging-http.service crm-staging-https.service
systemctl disable crm-staging-http.socket crm-staging-https.socket
rm -- /etc/systemd/system/crm-staging-http.socket /etc/systemd/system/crm-staging-http.service /etc/systemd/system/crm-staging-https.socket /etc/systemd/system/crm-staging-https.service
systemctl daemon-reload
```

不匹配就停止并人工核对。上述仅删除可从已合并仓库恢复的入口单元；不删除镜像、卷、备份、注册信息或 `/home/crmdeploy` 内容。停止 runner 可由 `crmdeploy` 执行 `systemctl --user stop crm-staging-runner.service`；完整注销 runner、停用/卸载 Rootless 和数据清理不属于自动回滚，需要另外明确批准。

## 8. 证据与下一阶段

脚本只记录低敏部署/回滚 JSON；Actions 成功制品保留 30 天，失败可能无上传制品，必须保留原失败退出码并安全收集局部证据，不能补造 passed 文件。主机原始快照留在受限目录，进入 Git 前进一步脱敏；不上传配置正文、私钥、模型或客户数据。每次执行记录来源完整 SHA、候选/上一版摘要、overlay SHA-256、配置版本/摘要、迁移、主机 OS 与 Rootless 信息、容器比较、健康结果、恢复/回滚结果、UTC 时间和 workflow run ID。

Task 12 只在 007 报告中补入真实证据并更新索引，不创建第二份竞争结论。G1 OAuth/读取 → G2 Webhook → G3 单操作员人工消息 → G4 AI/RAG → G5 50 授权客户端 SSE → G6 五个真实日历日/99.5%，须按放行检查表逐项取得真实测试授权和独立证据。rootless overlay 和现有门禁脚本固定关闭全部能力，不能用于直接开启后续真实门禁；能力开启方案必须另经审阅。production 最终运行方式留待 staging 适用门禁通过后商讨。
