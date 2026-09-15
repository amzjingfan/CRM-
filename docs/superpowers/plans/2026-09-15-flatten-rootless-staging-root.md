# 首版 Rootless Staging 根目录扁平化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `77d9f8f` 的产品工程提升到 `E:\develop\CRM智能聊天系统` 根目录，同时保留现有 Git 历史、用途型文档和首版 Rootless Staging 部署能力。

**Architecture:** 外层仓库继续作为唯一 Git 仓库，在迁移分支上通过普通向前提交删除嵌套跟踪路径并增加等价的根级路径。产品文件来自 `77d9f8f:CRM智能聊天系统/`，根级 CI、发布清单和当前文档单独适配新路径；不移动 `.git`、不重写历史、不触碰远程。

**Tech Stack:** Git、PowerShell 7、FastAPI/Python、Next.js/TypeScript、Docker Compose、GitHub Actions

**Spec:** `docs/superpowers/specs/2026-09-15-flatten-rootless-staging-root-design.md`

## Global Constraints

- 源产品基线固定为提交 `77d9f8f78844f08e5840e505af53ef87e9484c0b`。
- 仓库根固定为 `E:\develop\CRM智能聊天系统`，不得移动或复制 `.git`。
- 迁移使用普通提交，不使用 `git reset --hard`、强制推送或历史重写。
- `AGENTS.md`、`docs/`、`release/` 保持用途型结构，不恢复岗位或子智能体一级目录。
- 不读取、打印、提交或覆盖 `CRM智能聊天系统/.env`；不清理内层未跟踪的 IDE、缓存和临时文件。
- 不修改 `origin`，不执行 fetch、pull 或 push。
- 只运行 Git、路径和配置静态检查，不运行大规模后端、前端或容器测试。

---

## File Structure

- `backend/`：由 `77d9f8f:CRM智能聊天系统/backend/` 提升，包含应用、迁移、脚本和测试。
- `frontend/`：由 `77d9f8f:CRM智能聊天系统/frontend/` 提升。
- `deploy/`：由 `77d9f8f:CRM智能聊天系统/deploy/` 提升，保留首版 Rootless Staging。
- `scripts/`、`tests/`：由同一基线提升。
- 根级 Dockerfile、Compose、`.env.example`、`.mcp.json`、`README.md`：由产品基线提升。
- `.gitignore`、`.gitattributes`、`AGENTS.md`：保留当前根级治理文件，只补充迁移后确有需要的规则。
- `.github/`：使用 `77d9f8f` 的 Rootless Staging 工作流语义并改为根级路径。
- `docs/`：保留当前用途型文档入口，删除后续 K2/Split-ingress 状态并记录扁平化迁移。
- `release/`：保留低敏评测证据；基线和镜像清单恢复为 `77d9f8f` 语义并改为根级路径。

### Task 1: 提升 `77d9f8f` 产品快照到仓库根

**Files:**
- Delete tracked tree: `CRM智能聊天系统/`
- Create/replace: `backend/`
- Create/replace: `frontend/`
- Create/replace: `deploy/`
- Create/replace: `scripts/`
- Create/replace: `tests/`
- Create/replace: `.env.example`
- Create/replace: `.mcp.json`
- Create/replace: `README.md`
- Create/replace: `Dockerfile.backend`
- Create/replace: `Dockerfile.frontend`
- Create/replace: `Dockerfile.frontend.prod`
- Create/replace: `Dockerfile.model-service`
- Create/replace: `docker-compose.yml`
- Create/replace: `docker-compose.ai.yml`
- Create/replace: `docker-compose.deepseek-sse.yml`
- Create/replace: `docker-compose.gpu.yml`
- Create/replace: `docker-compose.prod.yml`
- Create/replace: `docker-compose.rootless-staging.yml`
- Create/replace: `docker-compose.sse-load-test.yml`
- Create/replace: `docker-compose.tiktok-manual.yml`

**Interfaces:**
- Consumes: Git tree `77d9f8f:CRM智能聊天系统/`.
- Produces: 根级产品树；后续任务可直接使用 `backend/`、`frontend/`、`deploy/` 和根级 Compose 路径。

- [ ] **Step 1: 再次确认分支、工作区和源提交**

Run:

```powershell
git status --short --branch
git rev-parse HEAD
git rev-parse 77d9f8f
```

Expected: 当前分支为 `feature/flatten-rootless-staging-root`；除本计划文件外无意外修改；源 SHA 为 `77d9f8f78844f08e5840e505af53ef87e9484c0b`。

- [ ] **Step 2: 将基线产品树导出到仓库内临时目录**

Run:

```powershell
$migrationTemp = Join-Path (Get-Location).Path '.tmp\flatten-rootless-staging-77d9f8f'
$resolvedRoot = (Resolve-Path -LiteralPath '.').Path
if (-not $migrationTemp.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) { throw '临时目录越出仓库根' }
New-Item -ItemType Directory -Force -Path $migrationTemp | Out-Null
git archive --format=tar --output="$migrationTemp\baseline.tar" 77d9f8f -- 'CRM智能聊天系统'
tar.exe -xf "$migrationTemp\baseline.tar" -C $migrationTemp
Get-ChildItem -Force -LiteralPath "$migrationTemp\CRM智能聊天系统"
```

Expected: 临时目录出现 `backend`、`frontend`、`deploy`、`scripts`、`tests` 及基线根文件；归档不含 `.env`、缓存或模型权重。

- [ ] **Step 3: 删除嵌套目录中的受版本控制文件**

Run:

```powershell
git rm -r -- 'CRM智能聊天系统'
```

Expected: Git 暂存嵌套产品树删除；被根 `.gitignore` 忽略的 `.env`、IDE 配置和缓存仍留在原目录且未被读取。

- [ ] **Step 4: 复制基线产品文件到根目录，保留当前治理文件**

Run:

```powershell
$sourceRoot = Join-Path $migrationTemp 'CRM智能聊天系统'
$excludedNames = @('.gitignore', 'AGENTS.md')
Get-ChildItem -Force -LiteralPath $sourceRoot |
  Where-Object { $_.Name -notin $excludedNames } |
  ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $resolvedRoot -Recurse -Force }
git add --all -- . ':(exclude)docs' ':(exclude).github' ':(exclude)release'
git status --short
```

Expected: Git 将大部分变化识别为从 `CRM智能聊天系统/...` 到根级路径的 rename；`AGENTS.md` 和根 `.gitignore` 未被旧版本覆盖。

- [ ] **Step 5: 验证根级产品快照内容**

Run:

```powershell
$sourceFiles = git ls-tree -r --name-only 77d9f8f -- 'CRM智能聊天系统'
$expected = $sourceFiles | ForEach-Object { $_ -replace '^CRM智能聊天系统/', '' } | Where-Object { $_ -notin @('.gitignore', 'AGENTS.md') }
$missing = $expected | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) }
if ($missing) { $missing; throw '根级产品文件缺失' }
git diff --cached --check
```

Expected: `$missing` 为空，`git diff --cached --check` 无输出。

- [ ] **Step 6: 提交产品树提升**

Run:

```powershell
git commit -m "chore: flatten rootless staging product tree"
```

Expected: 生成一个仅包含产品树提升的本地提交。

### Task 2: 将 CI 和发布清单适配到根级路径

**Files:**
- Modify: `.github/CODEOWNERS`
- Modify: `.github/pull_request_template.md`
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/publish-images.yml`
- Modify: `.github/workflows/staging-gates.yml`
- Modify: `release/baselines/v0.1.0-mvp.20260907.json`
- Modify: `release/images/mvp-production-gates.json`
- Preserve: `release/evidence/ai/*`
- Preserve: `release/evidence/retrieval/*`
- Delete: `release/knowledge-content/`

**Interfaces:**
- Consumes: Task 1 的根级产品路径。
- Produces: 不依赖 `CRM智能聊天系统/` 前缀的 CI、Staging 门禁和发布清单。

- [ ] **Step 1: 恢复首版 Rootless Staging 的根级工作流和机器清单**

Run:

```powershell
git restore --source=77d9f8f --worktree --staged -- '.github' 'release/baselines/v0.1.0-mvp.20260907.json' 'release/images/mvp-production-gates.json'
git rm -r --ignore-unmatch -- 'release/knowledge-content'
```

Expected: `.github/workflows/staging-gates.yml` 回到首版 Rootless Staging 语义，K2 知识内容清单进入删除状态。

- [ ] **Step 2: 批量移除仓库内嵌套前缀**

Run:

```powershell
$pathFiles = @(
  '.github/CODEOWNERS',
  '.github/workflows/ci.yml',
  '.github/workflows/publish-images.yml',
  '.github/workflows/staging-gates.yml',
  'release/baselines/v0.1.0-mvp.20260907.json',
  'release/images/mvp-production-gates.json'
)
foreach ($pathFile in $pathFiles) {
  $content = [System.IO.File]::ReadAllText((Join-Path $resolvedRoot $pathFile))
  $content = $content.Replace('CRM智能聊天系统/', '')
  [System.IO.File]::WriteAllText((Join-Path $resolvedRoot $pathFile), $content, [System.Text.UTF8Encoding]::new($false))
}
```

Expected: CI 的 working directory 变为 `backend`/`frontend`，Docker context 和脚本入口均从仓库根解析，发布清单路径不带嵌套前缀。

- [ ] **Step 3: 清理 CODEOWNERS 中已删除的岗位目录规则**

Edit `.github/CODEOWNERS` so it contains only current root paths and repository owner `@CP11-gh`; remove entries for `AI agent 开发工程师/`、`全栈开发工程师/`、`共享记忆文档/`、`开发工具/`、`架构师/`、`测试工程师/`。

- [ ] **Step 4: 静态验证 CI 和发布 JSON**

Run:

```powershell
$legacyRefs = Get-ChildItem -File -Recurse -LiteralPath '.github','release' |
  Select-String -SimpleMatch 'CRM智能聊天系统/'
if ($legacyRefs) { $legacyRefs; throw 'CI 或发布清单仍含旧前缀' }
Get-Content -Raw 'release/baselines/v0.1.0-mvp.20260907.json' | ConvertFrom-Json | Out-Null
Get-Content -Raw 'release/images/mvp-production-gates.json' | ConvertFrom-Json | Out-Null
git diff --check
```

Expected: 无旧前缀，两个 JSON 可解析，差异检查无输出。

- [ ] **Step 5: 提交 CI 和发布路径迁移**

Run:

```powershell
git add -- '.github' 'release'
git commit -m "ci: adapt rootless staging to repository root"
```

Expected: 生成 Rootless Staging CI/发布清单适配提交。

### Task 3: 将当前用途型文档回写到首版 Rootless Staging 事实

**Files:**
- Modify: `docs/README.md`
- Modify: `docs/deployment.md`
- Modify: `docs/release-gates.md`
- Modify: `docs/history.md`
- Modify as required by factual scan: `docs/product.md`
- Modify as required by factual scan: `docs/api.md`
- Modify as required by factual scan: `docs/architecture.md`
- Modify as required by factual scan: `docs/ai.md`
- Modify as required by factual scan: `docs/open-work.md`
- Modify as required by factual scan: `docs/test-status.md`
- Delete: `docs/knowledge-service.md`
- Delete: `docs/superpowers/plans/2026-09-11-split-ingress-rootless-staging.md`
- Delete: `docs/superpowers/plans/2026-09-14-cross-border-knowledge-service-roadmap.md`
- Delete: `docs/superpowers/plans/2026-09-14-k1-source-governance.md`
- Delete: `docs/superpowers/plans/2026-09-15-k2-independent-knowledge-service.md`
- Delete: `docs/superpowers/specs/2026-09-11-split-ingress-rootless-staging-design.md`
- Preserve: `docs/superpowers/specs/2026-09-15-flatten-rootless-staging-root-design.md`
- Preserve: `docs/superpowers/plans/2026-09-15-flatten-rootless-staging-root.md`

**Interfaces:**
- Consumes: `77d9f8f` Rootless Staging 代码、Task 2 根级路径。
- Produces: 与实际根级代码一致的用途型当前文档。

- [ ] **Step 1: 删除明确晚于目标基线的专题文档**

Run:

```powershell
$obsoleteDocs = @(
  'docs/knowledge-service.md',
  'docs/superpowers/plans/2026-09-11-split-ingress-rootless-staging.md',
  'docs/superpowers/plans/2026-09-14-cross-border-knowledge-service-roadmap.md',
  'docs/superpowers/plans/2026-09-14-k1-source-governance.md',
  'docs/superpowers/plans/2026-09-15-k2-independent-knowledge-service.md',
  'docs/superpowers/specs/2026-09-11-split-ingress-rootless-staging-design.md'
)
git rm --ignore-unmatch -- $obsoleteDocs
```

Expected: 仅删除 Split-ingress、K1/K2 独立知识服务的后续文档，不删除本次迁移设计和计划。

- [ ] **Step 2: 更新文档入口和部署事实**

Edit `docs/README.md`:

- 将“产品代码位于 `CRM智能聊天系统/`”改为“产品代码位于仓库根目录”。
- 删除 `knowledge-service.md` 文档地图项。

Edit `docs/deployment.md`:

- 删除 Split-ingress 公网服务器、反向 SSH 隧道和独立知识服务叠加描述。
- 明确首版 Rootless Staging 在业务主机使用 Rootless Docker，应用监听回环 `10080/10443`，由同机 systemd socket/service 转发 `80/443`。
- 将模型清单路径改为 `deploy/models/model-manifest.json`。
- 保持真实平台、AI、高风险写入、备份与回滚仍未放行。

- [ ] **Step 3: 更新门禁和历史**

Edit `docs/release-gates.md`:

- G0 只描述首版 Rootless Staging 资产已具备、真实部署/恢复/回滚仍待验证。
- 删除 Split-ingress 连通判定。
- G4 删除独立知识服务 K3 流量切换表述，保留 `77d9f8f` 已存在的 DeepSeek/RAG/DLP/知识审批边界。

Edit `docs/history.md`:

- 将 staging 历史截点固定到 `77d9f8f` 的首版 Rootless Staging。
- 保留 2026-09-15 文档压缩与本次仓库根扁平化记录，用于解释为什么岗位目录没有恢复。
- 明确 Split-ingress 和 K2 仅存在于后续历史，不属于当前工作树。

- [ ] **Step 4: 扫描并修正其余当前文档**

Run:

```powershell
$docRefs = Get-ChildItem -File -Recurse -LiteralPath 'docs' |
  Select-String -Pattern 'CRM智能聊天系统/|split-ingress|Split-ingress|knowledge-service|K2 independent|docker-compose\.knowledge'
$docRefs
```

For each result outside the preserved migration design/plan, apply these exact rules:

- `CRM智能聊天系统/<path>` → `<path>`；
- Split-ingress/current tunnel claims → remove from current-state sections or mark as later historical work not present in the working tree；
- independent knowledge service/K2/K3 runtime claims → remove from current-state sections；
- do not alter source SHA `77d9f8f` or historical filenames quoted solely for Git traceability。

- [ ] **Step 5: 验证文档事实和格式**

Run:

```powershell
$unexpected = Get-ChildItem -File -Recurse -LiteralPath 'docs' |
  Where-Object { $_.FullName -notlike '*2026-09-15-flatten-rootless-staging-root*' } |
  Select-String -Pattern 'CRM智能聊天系统/|当前.*split-ingress|当前.*独立知识服务'
if ($unexpected) { $unexpected; throw '当前文档仍含迁移后失效事实' }
git diff --check
```

Expected: 当前事实不再引用嵌套产品路径或把后续能力描述为当前能力，差异检查无输出。

- [ ] **Step 6: 提交文档状态回退**

Run:

```powershell
git add -- 'docs'
git commit -m "docs: restore initial rootless staging state"
```

Expected: 生成用途型文档与首版 Staging 状态同步提交。

### Task 4: 全仓路径、安全和历史验收

**Files:**
- Modify if required by verification: `.gitignore`
- Modify if required by verification: `.gitattributes`
- Modify if required by verification: `README.md`
- Modify if required by verification: `deploy/staging/rootless/README.md`
- Modify if required by verification: `scripts/Test-StagingProductionGates.ps1`
- Modify if required by verification: `scripts/Invoke-StagingRollbackDrill.ps1`

**Interfaces:**
- Consumes: Tasks 1～3 的完整迁移结果。
- Produces: 可提交合并且不触碰远程的本地迁移分支。

- [ ] **Step 1: 扫描所有受跟踪文本中的旧路径**

Run:

```powershell
$trackedFiles = git ls-files
$legacyRefs = foreach ($trackedFile in $trackedFiles) {
  if (Test-Path -LiteralPath $trackedFile -PathType Leaf) {
    Select-String -LiteralPath $trackedFile -SimpleMatch 'CRM智能聊天系统/' -ErrorAction SilentlyContinue
  }
}
$legacyRefs
```

Expected: 只允许迁移设计/计划中用于解释旧路径的引用；运行代码、CI、部署说明和发布清单不得命中。

- [ ] **Step 2: 修正运行面仍存在的旧前缀**

For every match in `README.md`、`.github/`、`deploy/`、`scripts/`、Compose 或发布 JSON，将仓库内路径前缀 `CRM智能聊天系统/` 移除。保留 `deploy/cloudflared/config.example.yml` 中与真实本机绝对位置相关的示例时，必须改成不绑定开发机盘符的占位路径 `/home/crmdeploy/.cloudflared/YOUR_TUNNEL_UUID.json`。

- [ ] **Step 3: 验证目标树与后续能力排除**

Run:

```powershell
git ls-files -- 'CRM智能聊天系统/**'
git ls-files -- 'backend/app/knowledge_service/**' 'backend/knowledge_migrations/**' 'docker-compose.knowledge.yml' 'deploy/staging/rootless/*tunnel*'
git ls-files -- 'deploy/staging/rootless/bootstrap-host.sh' 'deploy/staging/rootless/install-entry-proxy.sh' 'docker-compose.rootless-staging.yml' '.github/workflows/staging-gates.yml'
```

Expected: 第一条和第二条无输出；第三条列出四个首版 Rootless Staging 关键资产。

- [ ] **Step 4: 验证敏感文件和本地残留未进入 Git**

Run:

```powershell
git ls-files | Select-String -Pattern '(^|/)\.env$|\.pem$|\.key$|node_modules|\.venv|\.pytest_cache|\.ruff_cache|\.uv-cache'
git check-ignore -v 'CRM智能聊天系统/.env'
```

Expected: 第一条无输出；第二条确认内层 `.env` 被根 `.gitignore` 忽略。

- [ ] **Step 5: 验证 Git 历史、远程和工作区**

Run:

```powershell
git merge-base --is-ancestor 77d9f8f HEAD
git merge-base --is-ancestor 8235443 HEAD
git remote -v
git diff --check
git status --short --branch
```

Expected: 两次 ancestry 检查退出码均为 0；`origin` 仍为 `ssh://git@ssh.github.com:443/CP11-gh/CRM.git`；无格式错误；状态只包含本任务尚未提交的修正。

- [ ] **Step 6: 提交最终路径修正**

Run:

```powershell
git add --all
git diff --cached --check
git commit -m "chore: finalize rootless staging root migration"
```

Expected: 最终迁移提交成功，未推送远程。

- [ ] **Step 7: 生成最终验收摘要**

Run:

```powershell
git status --short --branch
git log --oneline --decorate -5
git diff --stat 8235443..HEAD
git ls-files | Measure-Object
```

Expected: 工作区无受跟踪修改；日志包含设计、产品提升、CI/发布适配、文档同步和最终修正提交；统计可用于交付说明。
