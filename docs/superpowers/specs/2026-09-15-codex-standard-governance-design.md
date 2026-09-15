# Codex STANDARD 单人持续开发治理设计

状态：已确认，待实施
日期：2026-09-15
目标分支：`docs/codex-standard-governance`
治理档位：`STANDARD`

## 1. 目标

把用户提供提示词的第六至十二章完整转化为本仓库可长期执行的 Codex 协作规则，使一位开发者能在 Codex 桌面版中持续完成需求、实现、验证、恢复和发布准备，同时保持当前 TikTok 人工辅助 v0.1 的产品与安全边界。

本次只修改规则、文档入口和治理目录，不修改前后端源码、数据库迁移、运行配置、Prompt、评测数据或发布资产，不推送远端，也不执行生产、付费或外部写操作。

## 2. 当前基线

- 仓库是单仓库模块化单体，产品工程位于 Git 根目录。
- 项目阶段为 `ACTIVE`，不是 `BOOTSTRAP`；已有产品、架构、接口、AI、部署、测试与发布门禁文档。
- 根 `AGENTS.md` 是唯一自动加载的项目级规则，当前没有嵌套规则文件。
- 当前分支基线为 `main@e0592c29c2e9d4153ffbbbf43da9a7aa05c29207`，工作区洁净；本地 `main` 相对 `origin/main` 领先 132 个提交。
- `docs/open-work.md` 只保存未完成事项，没有任务 ID、状态、分支、依赖和证据映射。
- 后端模块测试位于 `backend/tests/`，跨数据库集成测试位于 `tests/integration/`，前端测试位于 `frontend/tests/`；实际布局为 `hybrid`。
- 最近的仓库压缩已取消岗位目录、外部 Skill 副本和重复报告链；本次不得恢复这些结构。

## 3. 设计原则

1. 根 `AGENTS.md` 只保存每次任务都必须生效的短规则和权威入口；详细格式放在 `docs/governance.md`，避免自动加载上下文膨胀。
2. 当前事实只保留一个权威位置。产品范围仍由 `docs/product.md` 管理，系统设计仍由 `docs/architecture.md` 管理，不重复创建 `PRD.md` 或 `SYSTEM.md`。
3. `docs/tasks/TASKS.md` 取代 `docs/open-work.md`，成为任务状态唯一事实源；其他文档只能引用或汇总，不维护第二套状态。
4. `docs/memory/PROJECT-STATE.md` 是恢复工作所需的精简状态摘要，不复制任务表、测试报告或发布门禁正文。
5. 实施、测试和审查记录按风险与任务类型创建；纯文字、索引或低风险规则修正可直接由任务和提交说明承载。
6. 不预建没有真实内容的记录、审查或清理目录。首次产生对应事实时再创建目录、源记录和索引。
7. 所有自动化、GitHub、Codex 任务和远端写入都遵循“查重—执行—复核—记录恢复点”，工具不可用时明确降级，不虚报成功。

## 4. 目标文件结构

```text
AGENTS.md                              每次任务自动生效的仓库规则与文档路由
docs/
├─ README.md                           当前文档地图与事实优先级
├─ governance.md                       第六至十二章的完整长期治理契约
├─ product.md                          现有产品范围与验收事实
├─ architecture.md                     现有系统架构事实
├─ tasks/
│  └─ TASKS.md                         唯一任务状态源
├─ memory/
│  └─ PROJECT-STATE.md                 跨会话恢复摘要
└─ quality/
   └─ TEST-STRATEGY.md                 测试层级、门禁和追踪策略
tests/
└─ README.md                           实际测试发现规则、命令和数据约束
.github/pull_request_template.md       PR 中的任务、验证、证据和风险检查
.gitignore                             本地隔离区与治理临时输出保护
```

后续按真实需要创建以下目录，不在本次生成空占位：

```text
docs/decisions/
docs/records/implementation/
docs/reports/tests/
docs/reports/reviews/
docs/operations/cleanup/
docs/memory/sessions/
.maintenance/quarantine/
```

## 5. 第六章：架构、Git 与 worktree

`AGENTS.md` 保存不可跳过的简版规则，`docs/governance.md` 保存完整规则：

- 默认单仓库、模块化单体、一个主要部署单元和最少运行服务；无需求证据时不新增微服务、事件总线、Kubernetes、共享包、插件系统或复杂权限平台。
- 只有难逆转、影响公共契约、数据、权限、安全或长期成本的决定才创建 ADR；普通可逆实现选择写入任务或提交即可。
- 每次任务记录并核对 `REPOSITORY_ID`、`PRIMARY_BRANCH`、`AUTHORIZED_WORK_ROOT` 和 `BASE_SHA`；worktree 必须属于同一 Git common dir。
- 不在 `main` 做日常修改；使用 `feature/*`、`fix/*`、`docs/*`、`hotfix/*` 或 `spike/*` 短期分支，并优先放入 `.worktrees/`。
- 保留未知文件、未提交修改、现有历史、标签和远端；禁止强制推送、历史重写和 `git reset --hard` 覆盖共享状态。
- Git 远端变更、推送、PR、合并、标签和发布属于独立步骤。先读取远端与分支状态，确认精确目标，再执行并复核。

## 6. 第七章：轻量任务管理与 Codex 任务

`docs/tasks/TASKS.md` 使用以下状态：

```text
BACKLOG → READY → DOING → VERIFYING → DONE
DOING/VERIFYING → BLOCKED
未完成状态 → CANCELLED
```

任务表至少包含：`ID`、可验证结果、需求/验收或门禁、状态、分支、依赖、实施记录、测试记录、审查记录和最终 subject SHA。进入 `READY` 前必须具备范围、验收、依赖和验证方法；`DONE` 必须绑定真实提交与足够证据，不接受 `WORKTREE`。

单人默认在当前 Codex 任务中完成普通短任务。只有跨里程碑、需要独立分支或会话交接的 `READY` 任务才创建新的可见 Codex 任务；创建前读取现有任务并按项目简称与任务 ID 查重。子智能体只用于路径和依赖真正独立的并行工作，不代替 `TASKS.md`，也不恢复岗位目录。

Codex UI 操作失败或工具不支持时记录 `UI_UNAVAILABLE`，给出目标标题和人工步骤，继续不依赖该 UI 操作的仓库工作。归档或删除可见任务仍需明确授权。

## 7. 第八章：开发循环与质量

开发循环固定为：选择最高优先级 `READY` → 复核范围、依赖、授权根与 Git → `DOING` → 最小完整实现 → 验证并修复 → 同步文档和证据 → `VERIFYING` → `DONE`。

质量规则包括：

- 优先交付可运行的纵向切片；可逆细节自行决定，产品或架构边界变化才暂停请求决定。
- 新依赖必须证明必要性，并检查维护状态、许可证、体积与安全影响。
- 数据库变化使用可回滚迁移；认证、租户和敏感数据变化补充负向与越权测试。
- AI 变化记录 Provider/模型、Prompt/配置、评测样例、阈值、成本与降级。
- 按风险运行 format、lint、typecheck、unit、integration、build、健康检查、核心流程、权限、迁移、AI eval、secret/dependency scan；不适用或未执行项必须说明。
- 不得通过删除测试、降低阈值、绕过安全门禁或修改验收标准制造通过。
- “完成、通过、部署、通知、推送、合并”只在取得真实工具或命令证据后表述。

## 8. 第九章：测试布局、记录与索引

本项目固定 `TEST_LAYOUT=hybrid`：

- `backend/tests/`：后端模块、契约、安全与确定性测试。
- `tests/integration/`：真实 PostgreSQL/pgvector 的跨模块集成测试。
- `frontend/tests/`：前端契约、组合、安全与业务行为测试。
- `backend/evals/`：版本化 AI/RAG 评测数据与受控结果。
- `release/evidence/`：发布基线需要长期保留的低敏机器证据，不作为普通测试输出目录。

`docs/quality/TEST-STRATEGY.md` 记录测试层级、适用环境、门禁、数据规则和需求追踪；`tests/README.md` 记录真实发现规则、命令、fixture/helper 规则及临时输出位置。不存在真实测试的层级标为 `N/A` 并写明启用条件，不创建空目录。

改变源码、测试源码、依赖、配置、迁移、Prompt、模型、数据基线或运行行为的任务，在 `DONE` 前建立最终 IR 与 TR；认证、授权、租户、敏感数据、迁移、公共契约、生产基础设施、高风险依赖和关键 AI 变化默认还需 RR。纯文档与索引修正没有新的实施或测试事实时不强制新增记录。

记录使用提示词规定的 frontmatter、命名、状态和修订规则，并区分：

- `CANDIDATE_SUBJECT_SHA`：最后一个影响交付内容的真实提交；IR/TR/RR 绑定该 SHA。
- `EVIDENCE_HEAD_SHA`：只包含后续证据与状态更新的实际 HEAD；在门禁现场读取，不写入会造成自指的仓库内容。

IR/TR/RR 是事实源，INDEX 是可重建派生视图。首次产生某类记录时创建该目录和索引；索引输入相同时正文必须相同。发现缺项、重复 ID、链接或 SHA 不一致时标记 `INDEX_STALE`，从全部源记录重建；不能通过只改索引掩盖源记录错误。

## 9. 第十章：记忆、恢复与 UI 降级

`docs/memory/PROJECT-STATE.md` 只保存恢复所需的最新摘要：项目阶段、治理档位、仓库身份、主/当前分支、subject SHA、固定 `EVIDENCE_HEAD_SHA=READ_AT_GATE`、产品与架构入口、里程碑、活动任务、最新记录、索引状态、目录卫生、阻塞、决定、风险、部署状态和最多三个下一动作。

任务、基线、重要提交、验证、记录、索引、目录盘点、清理、会话切换或发布状态变化时更新。只有跨会话确实需要额外交接时才创建精简 session memory；禁止写入真实 thread ID、本机绝对路径、密钥或个人数据。

Git、文件、Codex UI 和 GitHub 不是原子事务。每一步必须查重、执行、复核并记录恢复点；任一步失败时保留已完成事实，明确下一步，不假装整体成功。

## 10. 第十一章：目录与文件清理

启动、里程碑交付前、生产发布前和用户要求时进行只读卫生盘点。没有候选时只在 `PROJECT-STATE.md` 记录 `Workspace hygiene: CLEAN`，不创建空清理任务或目录。

实际隔离或删除必须建立独立 `MAINT-CLEANUP-*` 任务和 `CLEANUP-*` 批次，记录精确路径、Git 状态、大小、SHA-256、引用、关联任务/worktree、可重建性、影响、恢复方法、验证和保留期。清理不得夹带在功能任务中。

- 未知文件、用户文件、需求来源、生产数据、备份、密钥、迁移和活动 worktree 内容不自动隔离或删除。
- 隔离只在用户确认的持久 checkout/worktree 中进行，唯一副本不得放入临时或可能被 Codex 自动清理的位置。
- 被跟踪文件的移动或删除必须形成可审阅 diff；不得用 `.gitignore` 隐藏。
- 隔离后重跑引用扫描及适用质量门禁；失败优先按 manifest 恢复。
- 默认保留期采用提示词规定的 7/14/30 天分级；unknown、数据、备份、密钥和迁移不自动删除。
- 没有已批准且版本化的精确清理策略时，永久删除必须针对具体批次和精确路径再次取得授权。

`.maintenance/` 加入 `.gitignore`，并明确排除在构建、测试、索引、AI/RAG 摄取、打包和部署路径之外。

## 11. 第十二章：变更、发布与批准

产品目标/用户、当期范围、权限/租户/敏感数据、公共 API/数据模型、生产部署、核心 AI 或持续成本发生重大变化时，暂停受影响任务，展示差异、影响、备选和推荐，取得一次决定并更新基线。

产品与技术基线批准后，范围内普通实现、测试、低风险依赖、文档、短期分支和提交可持续推进，不重复请求批准。以下操作仍需单独批准：

- 重大产品或架构变化；
- 删除或覆盖未知文件；
- 破坏性 Git 与共享历史改写；
- 生产数据和不可逆迁移；
- 付费资源、权限扩大和生产密钥；
- 对外消息、公开发布和生产发布；
- 接受失败测试或降低既定验收标准。

生产发布前必须绑定候选 SHA，完成适用验证、配置与密钥检查、迁移、备份、回滚、监控和残余风险说明，并取得明确发布批准；发布后执行冒烟并记录真实结果。GitHub 推送、创建 PR、合并或打标签不自动等于生产放行。

## 12. 文件变更

1. 修改 `AGENTS.md`：加入 STANDARD 模式、授权/资料边界、文档路由，以及第六至十二章每次任务必须执行的摘要。
2. 新增 `docs/governance.md`：保存本设计第 5～11 节的可执行长期规则、表格格式、记录格式和清理格式。
3. 移动并重写 `docs/open-work.md` 为 `docs/tasks/TASKS.md`：保留当前 P0/P1 事实，建立唯一状态表，不虚构已经完成或 READY 的任务。
4. 新增 `docs/memory/PROJECT-STATE.md`：记录当前 ACTIVE/ STANDARD 基线和恢复入口。
5. 新增 `docs/quality/TEST-STRATEGY.md` 与 `tests/README.md`：登记 hybrid 布局、实际命令和门禁。
6. 修改 `docs/README.md`：更新事实优先级、入口和维护规则。
7. 修改 `.github/pull_request_template.md`：加入任务 ID、subject/evidence SHA、按风险 IR/TR/RR、未执行项和清理声明。
8. 修改 `.gitignore`：忽略 `.maintenance/`，避免本地隔离副本、manifest 草稿和清理输出进入提交。
9. 不修改源码、运行配置、数据库、Prompt、评测集、`release/` 或历史 superpowers 设计/计划。

## 13. 验证与验收

实施完成后至少执行：

1. `git status --short --branch` 与 `git diff --check`。
2. 检查 `docs/open-work.md` 不再受跟踪，`docs/tasks/TASKS.md` 成为唯一任务状态入口。
3. 检查 `AGENTS.md`、`docs/README.md` 与 PR 模板中的全部仓库相对路径存在。
4. 检查第六至十二章各规则在 `AGENTS.md` 或 `docs/governance.md` 中有明确落点。
5. 检查 Markdown 不含本机绝对路径、真实凭证、Token、生产数据、虚构 SHA 或虚构通过结论。
6. 检查根 `AGENTS.md` 保持简洁并低于 Codex 默认项目指令上限。
7. 检查产品范围、安全开关、发布门禁和当前未完成事实未被改变。
8. 因不修改运行行为，不运行后端、前端、数据库或真实平台回归，并在交付说明中明确未运行原因。

## 14. 风险与回滚

- **状态重复：** 通过删除 `docs/open-work.md` 并只让 `TASKS.md` 保存状态解决。
- **规则过长：** 根 `AGENTS.md` 只保留摘要，完整格式放入按需读取的 `docs/governance.md`。
- **旧压缩设计冲突：** 不恢复岗位目录、外部 Skill 和空报告；IR/TR/RR 只在真实行为变更时按风险产生。
- **错误宣称项目已完成：** 新任务默认从 `BACKLOG` 建立，已有测试与门禁结论保持原文含义。
- **远端风险：** 本次不修改 `origin`、不推送、不创建 PR、不合并；后续单独读取 GitHub 状态并取得相应授权。
- **需要撤销：** 所有变更位于独立短期分支，可通过普通提交或后续 `git revert` 恢复，不重写历史。
