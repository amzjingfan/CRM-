# GitHub Flow 与发布基线治理实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | PhaseX |
| 任务编号 | PX-00；正式项目管理任务编号待补充 |
| 模块编号 | 跨模块治理 |
| 主责 Agent | 架构师Agent |
| 协作 Agent | 无 |
| 实施状态 | 部分完成 |
| 开始日期 | 2026-09-07 |
| 完成日期 | 未完成 |
| 代码位置 | 不涉及产品代码；治理文件位于工作区根目录及各文档责任目录 |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md`；本次未改变 API。
- 架构依据：`架构师/ARCH-001-SYS-系统总体架构设计-v1.4.md`、`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`。
- 任务依据：用户批准的“根仓库 GitHub Flow 管理与 MVP 发布基线冻结”任务；正式 PX 编号待项目管理补充。
- 验收依据：`共享记忆文档/MVP范围与验收标准.md`、`架构师/验收-001-CROSS-真实环境生产放行检查表-v1.0.md`。
- 代码规范：`共享记忆文档/代码编写手册.md`；本次没有修改产品代码。
- 设计与计划：`docs/superpowers/specs/2026-09-07-github-flow-release-baseline-design.md`、`docs/superpowers/plans/2026-09-07-github-flow-release-baseline.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 以工作区根目录建立唯一 Git 仓库，并为后续开发固定 GitHub Flow。
- 将代码、架构、正式测试报告、共享文档和开发工具纳入同一提交历史。
- 冻结应用版本、迁移 023、构建配置、评测数据与可取得的镜像摘要。
- 同步 README、架构 v1.5、生产放行检查表和两个项目索引，并恢复缺失记录。

### 3.2 实施范围

- 根 Git 治理文件、GitHub Actions、PR 模板和工作流说明。
- 工作区既有正式文件的首次安全导入。
- 机器可读基线清单、架构与验收文档、缺失证据恢复和索引修订。
- 后端/前端静态检查、默认测试、前端宿主机构建和应用镜像构建尝试。

### 3.3 非目标

- 不修复既有产品缺陷，不升级 Next.js Major，不修改 API、数据库结构、Prompt 或功能开关。
- 不提交 `.env`、真实凭证、客户数据、模型权重、虚拟环境、依赖目录、缓存或测试临时目录。
- 未提供 GitHub 仓库地址前，不擅自创建远程、推送或配置分支保护。
- 本次工程预发布基线不等同生产放行。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解和验收标准。
- [x] 已读取代码编写手册和适用 Skill。
- [x] 已确认 Phase、任务边界、模块边界和主责 Agent。
- [x] 已确认依赖、风险和验收方式。

## 5. 实施方案

### 5.1 方案说明

根目录作为唯一仓库，`main` 作为唯一长期分支，日常变更使用 `feature/*`、`fix/*`、`docs/*` 或 `hotfix/*` 短期分支，经 PR、CI 和审阅后 squash merge。首次导入在 `docs/release-baseline-20260907` 分支完成；由于既有项目文件在仓库初始化时尚未跟踪，无法进入新 worktree，本次受控地在主检出目录实施，后续任务改用 `.worktrees/`。

基线清单以带注释标签 `v0.1.0-mvp.20260907` 作为最终提交绑定，避免在被提交的清单内写入自身 commit SHA 造成循环。清单同时固定迁移、构建输入、评测资产和本次实际取得的镜像证据；无法取得的摘要明确写为 `null` 并记录原因。

### 5.2 依赖关系

- 前置依赖：Git 2.55、Python 3.11、uv 0.12.3、Node/npm、Docker Desktop，以及现有项目锁文件和正式测试证据。
- 后续依赖：所有新功能分支、Pull Request、CI、发布标签、生产镜像推送和 G0～G8 放行任务。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 首次导入混入秘密或大文件 | 泄密、仓库膨胀 | 先审计 824 个候选文件，再暂存；补充 `.pytest*/`、`.test-artifacts/` 规则后复核禁入项和大文件均为 0 |
| 清单摘要与实际文件漂移 | 基线不可复现 | 对 23 个冻结文件逐一重算 SHA-256 并与 JSON 比对 |
| 镜像构建受外网影响 | 摘要不完整 | 后端成功即记录真实摘要；前端失败保持 blocked，不复用历史镜像冒充本次产物 |
| Git 远程未知 | 无法推送和配置保护 | 只完成本地治理；等待用户提供远程后另行执行 |
| 工程基线被误解为生产放行 | 提前开启真实能力 | README、架构、清单和验收表均保留 `production_release=false` 与阻断项 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `.gitignore`、`.gitattributes`、`.github/`、`AGENTS.md` | 新增/修改 | 建立根仓库排除、行尾、CI、PR 和 GitHub Flow 强制规则 | 架构师Agent |
| `共享记忆文档/Git与GitHub Flow开发规范.md` | 新增 | 固定分支、提交、PR、squash、回滚、标签和远程配置流程 | 架构师Agent |
| `release/baselines/v0.1.0-mvp.20260907.json` | 新增 | 固定版本、迁移、配置、评测、镜像证据和未关闭门禁 | 架构师Agent |
| `CRM智能聊天系统/README.md` | 修改 | 同步根仓库、GitHub Flow、迁移 023 和基线入口 | 架构师Agent |
| `架构师/ARCH-001-SYS-系统总体架构设计-v1.5.md` | 新增/修改 | 增量同步单仓库、基线架构和当前门禁状态 | 架构师Agent |
| `架构师/验收-001-CROSS-真实环境生产放行检查表-v1.1.md` | 新增/修改 | 同步 G0～G8 状态和后端镜像证据 | 架构师Agent |
| `测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-真实环境配置与基础设施-综合测试-005.md` | 新增 | 按现存索引和可验证证据恢复缺失报告，明确不是伪造历史原件 | 架构师Agent |
| `共享记忆文档/实施记录/PhaseX-PX-00-全栈开发工程师Agent-环境变量注释完善-001.md` | 新增 | 恢复索引所指向的缺失实施记录 | 架构师Agent |
| `共享记忆文档/测试报告索引.md`、`共享记忆文档/实施记录索引.md` | 修改 | 修复断链并登记本次治理记录 | 架构师Agent |
| 工作区 7 个一级责任目录 | 纳入版本控制 | 737 个正式文件首次导入同一提交历史 | 架构师Agent |

### 6.2 接口、数据和配置变更

- API：不适用；无接口变化。
- 数据库：无新迁移；基线确认 head 为 `023_marketing_review_idempotency`，down revision 为 `022_ai_marketing_review`。
- 配置项：新增仓库治理和 CI 配置；只散列 `.env.example`，未读取或记录真实 `.env` 值。
- AI：无 Prompt、模型调用或 RAG 行为变化；固定 REAL-AI-05 模型、Prompt、DLP、运行 ID、数据集和结果摘要。

### 6.3 关键实现说明

- 初始化提交：`49a1c4d`、`d00fe71`、`3ac86a5`；治理提交：`5911d30`、`501478a`、`e28df7c`、`3442e23`；首次全项目安全导入：`62c65df`。
- 后端本次镜像构建成功：`crm-backend@sha256:a07b580c40b7ba6bd32f82b5231df17a38c25d471cb9af9049b28bce135c47bf`，基础镜像为 `ghcr.io/astral-sh/uv@sha256:4f5d923c9dcea037f57bda425dd209f3ec643da2f0b74227f68d09dab0b3bb36`。
- 前端固定基础镜像首次因 Docker Hub OAuth 超时失败；使用本地 `node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293` 后，分别使用 npm 官方源和项目镜像源重试，两次都停滞于容器内 `npm ci` 超过两分钟并终止，未产生本次前端镜像。
- 历史 `crm-frontend:phase4-prod` 只在清单中标记为参考，不作为当前源码的冻结产物。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| Git 候选安全审计 | `git ls-files --others --exclude-standard` + 路径/大小规则 | 禁入和大文件为 0 | 最终 737 个、7.11 MiB；禁入 0、大文件 0、未处理 0 | 通过 |
| Git 忽略验证 | `git check-ignore`、ignored 文件枚举 | 临时与秘密文件不入库 | 102 个 `.pytest-*` 和 2 个 `.test-artifacts` 文件被排除 | 通过 |
| 基线 JSON 与 SHA-256 | `ConvertFrom-Json` + `Get-FileHash` | JSON 有效且摘要一致 | 23 个冻结文件全部匹配，迁移元数据一致 | 通过 |
| Python 锁文件 | `uv lock --check` | 锁文件有效 | 125 个包解析通过 | 通过 |
| Ruff | `uv run ruff check .`、`uv run ruff format --check .` | 无静态与格式错误 | 全部通过，235 个文件已格式化 | 通过 |
| mypy | `uv run mypy app scripts` | 无类型错误 | 166 个源文件无问题 | 通过 |
| 后端默认测试 | `uv run pytest --basetemp=.../.pytest-release-baseline-20260907` | 默认测试通过 | 1321 passed、12 skipped、2 warnings，6.53s | 通过 |
| pytest 环境异常复核 | 默认 `uv run pytest` 后改用项目内 basetemp | 区分测试失败与环境失败 | 默认运行在系统 Temp 清理 `pytest-current` 时 WinError 5；项目内 basetemp 后退出码 0 | 通过 |
| 前端测试 | `npm run test` | 测试通过 | 32 passed、0 failed | 通过 |
| 前端宿主机构建 | `npm run build` | 生产构建成功 | Next.js 15.5.23 编译成功，14 个页面生成 | 通过 |
| backend 镜像 | `docker build -f Dockerfile.backend ...` | 生成可摘要镜像 | 构建成功并取得 `sha256:a07b...` | 通过 |
| frontend 镜像 | `docker build -f Dockerfile.frontend.prod ...` | 生成可摘要镜像 | 外部网络/OAuth 和 npm 安装停滞，未产生镜像 | 失败 |
| 前端依赖审计 | `npm audit --registry=https://registry.npmjs.org --audit-level=high --json` | 无 High | 3 个 High，修复建议涉及 Next.js 16 Major | 失败 |

## 8. 实施结果

- 完成项：根仓库、GitHub Flow、CI/PR、全项目安全导入、迁移/配置/评测 SHA-256、后端镜像摘要、README/架构/清单/两个索引同步、两份缺失证据恢复、默认质量门禁验证。
- 未完成项：前端本次镜像、应用与外部镜像的受控仓库 RepoDigest、GitHub remote/PR/分支保护、最终分支整合与带注释标签。
- 与原方案差异：首次导入未使用 worktree，原因是 737 个既有文件在初始化时未跟踪；前端镜像因外部网络无法完成。
- 当前状态：本地 source/config/evaluation/backend-image 工程基线已形成，但完整镜像闭环和远程 GitHub Flow 尚未形成，因此记录为“部分完成”，生产保持不放行。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| RB-GIT-001 | 未提供 GitHub 远程，无法配置 PR、required checks 和 main 保护 | P1 | 架构师Agent | 下一次仓库接入任务 |
| RB-IMG-001 | 前端新镜像未构建，外部镜像未固定受控仓库 RepoDigest | P1 | 全栈开发工程师Agent | REAL-FS-01/G0 |
| DEF-REAL-FS01-005 | 前端依赖仍有 3 个 High，自动建议为 Next.js 16 Major | P1 | 全栈开发工程师Agent | REAL-FS-01 独立修复分支 |
| DEF-REAL-FS01-006 | 关键日志事件语义折叠 | P2 | 全栈开发工程师Agent | REAL-FS-01 独立修复分支 |
| RB-PROD-001 | 真实店铺、真实 SSE、五日稳定性、密钥轮换、备份恢复和回滚未完成 | P1 | 架构师Agent | G1～G8 |

## 10. 交接事项

- 交接给：架构师Agent、全栈开发工程师Agent、测试工程师Agent。
- 后续任务：先完成当前分支集成选择；取得 GitHub URL 后配置 remote/PR/分支保护；随后独立修复 G0 P1/P2，并完成前端与外部镜像摘要闭环。
- 必须注意：`v0.1.0-mvp.20260907` 只能表示工程预发布基线；不得据此开启真实平台写入、自动回复、AI 翻译或 AI 营销。

## 11. 文档同步

- [x] 已确认无接口变化。
- [x] 已同步架构决策。
- [x] 已同步任务状态。
- [ ] 待测试工程师对本次 Git/基线治理范围形成独立正式结论。
- [x] 已更新现有测试报告索引并恢复其缺失权威报告。
