# GitHub Flow 与发布基线治理实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | PhaseX |
| 任务编号 | PX-00；正式项目管理任务编号待补充 |
| 模块编号 | 跨模块治理 |
| 主责 Agent | 架构师Agent |
| 协作 Agent | 无 |
| 实施状态 | 已完成（工程预发布基线治理） |
| 开始日期 | 2026-09-07 |
| 完成日期 | 2026-09-07 |
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
- 不在 Pull Request 审阅、CI 和合并完成前创建发布标签，也不把远程接入等同于生产放行。
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
| 清单摘要与实际文件漂移 | 基线不可复现 | 对 25 个冻结文件逐一重算 SHA-256 并与 JSON 比对 |
| 镜像构建受外网影响 | 摘要不完整 | 后端成功即记录真实摘要；前端失败保持 blocked，不复用历史镜像冒充本次产物 |
| 远程写入凭证泄漏 | 仓库可能被未授权修改 | 使用仅绑定 `CP11-gh/CRM` 的可写 Deploy Key；私钥只保存在本地 `.git/deploy-keys/`，不纳入版本控制 |
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
| `CRM智能聊天系统/backend/tests/test_tiktok_oauth.py` | 修改 | 为 OAuth 回放/发起用户异常用例显式注入假配置，消除对开发机 `.env` 的隐式依赖 | 架构师Agent |
| 工作区 7 个一级责任目录 | 纳入版本控制 | 737 个正式文件首次导入同一提交历史 | 架构师Agent |

### 6.2 接口、数据和配置变更

- API：不适用；无接口变化。
- 数据库：无新迁移；基线确认 head 为 `023_marketing_review_idempotency`，down revision 为 `022_ai_marketing_review`。
- 配置项：新增仓库治理和 CI 配置；只散列 `.env.example`，未读取或记录真实 `.env` 值。
- AI：无 Prompt、模型调用或 RAG 行为变化；固定 REAL-AI-05 模型、Prompt、DLP、运行 ID、数据集和结果摘要。

### 6.3 关键实现说明

- 初始化提交：`49a1c4d`、`d00fe71`、`3ac86a5`；治理提交：`5911d30`、`501478a`、`e28df7c`、`3442e23`；首次全项目安全导入：`62c65df`。
- 已配置 `origin=ssh://git@ssh.github.com:443/CP11-gh/CRM.git`，推送 `main` 与 `docs/release-baseline-20260907`。PR #1 在最终审阅修复提交进入前被合并为 `3c24aee`，随后由 PR #2 回退为 `051d398`；包含全部审阅修复的 [Pull Request #3](https://github.com/CP11-gh/CRM/pull/3) 已通过独立人工复核和两项 GitHub Actions 门禁，并 squash merge 为 `190adf4`。
- 仓库级可写 Deploy Key 编号为 `162515972`，公钥指纹为 `SHA256:D2TRU58ouqzIdYsRJ2N2gjqRG6st8dGKrjyC984OEQ4`；私钥位于本地 `.git/deploy-keys/CP11-gh-CRM-20260907`，未被跟踪。
- 后端本次镜像使用固定基础镜像重新构建成功，本地 image ID 为 `sha256:def6eec93b6277bdc1a6bfc1db6117ee4b6e5d1cc0f0ba077368be8cc8ac6b83`；尚未推送受控仓库，因此 RepoDigest 保持 `null`。基础镜像固定为 `ghcr.io/astral-sh/uv:python3.11-bookworm-slim@sha256:4f5d923c9dcea037f57bda425dd209f3ec643da2f0b74227f68d09dab0b3bb36`。
- 前端固定基础镜像首次因 Docker Hub OAuth 超时失败；使用本地 `node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293` 后，分别使用 npm 官方源和项目镜像源重试，两次都停滞于容器内 `npm ci` 超过两分钟并终止，未产生本次前端镜像。
- 历史 `crm-frontend:phase4-prod` 只在清单中标记为参考，不作为当前源码的冻结产物。
- 合并前独立审阅识别出镜像证据语义、TypeScript 构建缓存、CODEOWNERS 缺失和 MCP 浮动版本四项 Important；当前分支已按实际证据修正、删除缓存、补齐所有权规则并将 `chrome-devtools-mcp` 固定为 `1.8.0`。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| Git 候选安全审计 | `git ls-files --others --exclude-standard` + 路径/大小规则 | 禁入和大文件为 0 | 最终 737 个、7.11 MiB；禁入 0、大文件 0、未处理 0 | 通过 |
| Git 忽略验证 | `git check-ignore`、ignored 文件枚举 | 临时与秘密文件不入库 | 102 个 `.pytest-*` 和 2 个 `.test-artifacts` 文件被排除 | 通过 |
| 基线 JSON 与 SHA-256 | `ConvertFrom-Json` + `Get-FileHash` | JSON 有效且摘要一致 | 25 个冻结文件全部匹配，迁移元数据一致 | 通过 |
| Python 锁文件 | `uv lock --check` | 锁文件有效 | 125 个包解析通过 | 通过 |
| Ruff | `uv run ruff check .`、`uv run ruff format --check .` | 无静态与格式错误 | 全部通过，235 个文件已格式化 | 通过 |
| mypy | `uv run mypy app scripts` | 无类型错误 | 166 个源文件无问题 | 通过 |
| 后端默认测试 | `uv run pytest --basetemp=.../.pytest-release-baseline-20260907` | 默认测试通过 | 1321 passed、12 skipped、2 warnings，6.53s | 通过 |
| pytest 环境异常复核 | 默认 `uv run pytest` 后改用项目内 basetemp | 区分测试失败与环境失败 | 默认运行在系统 Temp 清理 `pytest-current` 时 WinError 5；项目内 basetemp 后退出码 0 | 通过 |
| 前端测试 | `npm run test` | 测试通过 | 32 passed、0 failed | 通过 |
| 前端宿主机构建 | `npm run build` | 生产构建成功 | Next.js 15.5.23 编译成功，14 个页面生成 | 通过 |
| backend 镜像 | `docker build -f Dockerfile.backend ...` | 使用固定基础镜像生成可摘要镜像 | 构建成功并取得本地 image ID `sha256:def6...`；版本烟测输出 `crm-chat-system\|0.1.0` | 通过 |
| frontend 镜像 | `docker build -f Dockerfile.frontend.prod ...` | 生成可摘要镜像 | 外部网络/OAuth 和 npm 安装停滞，未产生镜像 | 失败 |
| 前端依赖审计 | `npm audit --registry=https://registry.npmjs.org --audit-level=high --json` | 无 High | 3 个 High，修复建议涉及 Next.js 16 Major | 失败 |
| GitHub 远程、PR 与 squash merge | SSH 推送、GitHub REST API | 远程分支、审阅和整合链路可用 | PR #1 的提前整合由 PR #2 回退；最终 PR #3 已人工审阅并 squash merge 为 `190adf4` | 通过 |
| GitHub Actions 首轮与最终复跑 | PR #1、PR #3 的 `CI` workflow | 后端、前端门禁通过 | 首轮定位 OAuth 单测依赖本机 `.env`；PR #3 最终提交 `7af04d4` 的 `Backend quality gates`、`Frontend quality gates` 均为 `success` | 通过 |
| 合并后回归验证 | 在 `main@190adf4` 运行后端与前端测试 | 合并树与审阅树一致，测试无回归 | Git tree 均为 `d006cbb0290d3aae9153c277d4387466611abc8b`；后端 1321 passed、12 skipped，前端 32 passed、0 failed | 通过 |
| main 分支保护 | GitHub Branch Protection API | 禁止直推并要求 PR/CI | 当前私有仓库套餐返回 403，需升级 GitHub 套餐或改为公开仓库 | 阻塞 |

## 8. 实施结果

- 完成项：根仓库、GitHub Flow、CI/PR、全项目安全导入、迁移/配置/评测 SHA-256、后端本地镜像证据、README/架构/清单/两个索引同步、两份缺失证据恢复、默认质量门禁验证、独立人工审阅、PR #3 squash merge，以及合并后回归验证。
- 最终版本绑定：本记录所在 `main` 提交以带注释标签 `v0.1.0-mvp.20260907` 标记；标签只表示工程预发布基线，`production_release=false`。
- 未完成项：前端本次镜像、应用与外部镜像的受控仓库 RepoDigest、受套餐限制的 main 分支保护与 required checks，以及 G1～G8 真实环境与回滚验证；这些事项不属于本次工程预发布基线治理的完成条件，继续阻断生产放行。
- 与原方案差异：首次导入未使用 worktree，原因是 737 个既有文件在初始化时未跟踪；前端镜像因外部网络无法完成。
- 当前状态：source/config/evaluation/backend-image 工程基线已形成，最终审阅树已通过 PR #3 进入 `main`，工程预发布基线治理完成；完整镜像闭环、分支保护和真实环境门禁仍未完成，生产保持不放行。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| RB-GIT-001 | 当前 GitHub 套餐不支持私有仓库分支保护，无法在服务端强制 PR 和 required checks | P1 | 架构师Agent | 升级套餐或评估转为公开仓库后配置 |
| RB-IMG-001 | 后端只有本地 image ID，前端新镜像未构建，应用与外部镜像均未固定受控仓库 RepoDigest | P1 | 全栈开发工程师Agent | REAL-FS-01/G0 |
| DEF-REAL-FS01-005 | 前端依赖仍有 3 个 High，自动建议为 Next.js 16 Major | P1 | 全栈开发工程师Agent | REAL-FS-01 独立修复分支 |
| DEF-REAL-FS01-006 | 关键日志事件语义折叠 | P2 | 全栈开发工程师Agent | REAL-FS-01 独立修复分支 |
| RB-PROD-001 | 真实店铺、真实 SSE、五日稳定性、密钥轮换、备份恢复和回滚未完成 | P1 | 架构师Agent | G1～G8 |

## 10. 交接事项

- 交接给：架构师Agent、全栈开发工程师Agent、测试工程师Agent。
- 后续任务：在本记录进入 `main` 后创建并核验带注释标签 `v0.1.0-mvp.20260907`；随后从最新 `main` 新建独立短期分支，处理 3 个 High 前端依赖风险、前端与外部镜像 RepoDigest、真实环境及回滚验证。分支保护需先升级 GitHub 套餐或评估转为公开仓库。
- 必须注意：`v0.1.0-mvp.20260907` 只能表示工程预发布基线；不得据此开启真实平台写入、自动回复、AI 翻译或 AI 营销。

## 11. 文档同步

- [x] 已确认无接口变化。
- [x] 已同步架构决策。
- [x] 已同步任务状态。
- [ ] 待测试工程师对本次 Git/基线治理范围形成独立正式结论。
- [x] 已更新现有测试报告索引并恢复其缺失权威报告。
