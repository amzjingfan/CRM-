# Phase 4 SSE、看板、部署与稳定性综合测试报告

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；关联 P2-09、P4-01～P4-11 |
| 模块编号 | M00（阶段跨模块汇总；覆盖 M02、M04、M05、M06） |
| 模块名称 | SSE、看板、Agent 运营、系统设置与部署稳定性 |
| 被测主责 Agent | 全栈开发工程师Agent |
| 被测协作 Agent | 架构师Agent、AIAgent开发工程师Agent |
| 测试执行 Agent | 测试工程师Agent |
| 关联实施记录 | `共享记忆文档/实施记录/Phase4-P4-00-全栈开发工程师Agent-SSE看板部署与稳定性阶段汇总-001.md` |
| 测试类型 | 综合测试、回归测试、数据库测试、接口测试、安全测试、页面交互测试、兼容性测试、部署测试 |
| 执行日期 | 2026-08-22 |
| 测试结论 | **不通过** |

最终结论：**Phase 4 工程主链路和自动化回归通过，但存在 1 个 P1、2 个 P2 未关闭缺陷，且真实模型 SSE 50 并发与五天稳定性门禁尚未形成有效证据，不建议当前版本完成 Phase 4 正式验收。**

## 2. 测试依据、范围与边界

### 2.1 测试依据

- `共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`。
- `共享记忆文档/智能客服平台 — 管理端接口文档.md`，重点为 11.6 Phase 4 接口增量。
- `共享记忆文档/开发任务拆解（按人天分配）.md` Phase 4。
- `共享记忆文档/MVP范围与验收标准.md`。
- `全栈开发工程师/PLAN-001-全栈工程实施计划-v1.0.md` Phase 4。
- `架构师/ARCH-001-SYS-系统总体架构设计-v1.3.md`、`架构师/ARCH-003-DATA-数据库与向量库初版设计-v1.1.md`。
- 项目全部适用的 `AGENTS.md`、`共享记忆文档/代码编写手册.md` 和 `测试工程师/测试报告命名规范.md`。

### 2.2 覆盖范围

- 迁移 016～017、空库升级、逐级回滚和数据库约束回归。
- `/suggest`、POST SSE、认证、CSRF、限流和失败关闭。
- 看板、Agent 运营、团队、店铺和渠道 API/页面。
- 自动回复默认关闭、Mock 平台真实写能力阻断和 Agent Worker 启动状态。
- 前端主题、多语言、375/768/1024/1440 响应式、触控尺寸、可访问结构和控制台。
- 生产 Compose、非 root 镜像、健康检查、JSON 日志以及备份恢复安全门禁。

### 2.3 非目标和未执行门禁

- 不验证 TikTok Shop、Shopee、Amazon 真实平台写操作；当前仍按契约级 Mock 验收。
- 不修改 AI Agent 的 Prompt、模型路由、RAG、阈值和工作流节点。
- 本轮未取得授权真实模型会话，未执行真实模型 SSE 首分块和 P99 测试。
- 五天连续稳定性和 99.5% 可用性需要持续环境观测，单次测试会话不生成虚假通过结论。
- 已有 BGE 模型服务 50 并发结论只覆盖内部检索模型服务，不等同于本次公开 SSE 接口性能。

## 3. 测试环境与代码基线

| 项目 | 实际环境 |
| --- | --- |
| 操作系统 | Windows，Asia/Shanghai |
| Python | 3.11，项目 `uv.lock` 与 `.uv-cache` |
| 前端 | Next.js 15.5.23、React 19、TypeScript |
| 数据库 | PostgreSQL 16 + pgvector；开发库 head 为 `017_phase4_metrics` |
| 基础服务 | backend、frontend、postgres、redis、minio 健康；worker、jobs、agent-worker 运行中 |
| AI/平台状态 | 自动回复关闭；Agent Worker 启动但不认领任务；三平台 `real_writes=false` |
| 浏览器 | Codex 内置 Chromium，使用真实 DOM、计算样式、截图和控制台检查 |
| 响应式视口 | 375×900、768×900、1024×900、1440×900 |
| 代码快照 | 221 个相关文件组合 SHA-256：`e435792015112ebfb3f223a8e35aebf8ee4d7dd1a655a707e4199ff0c3344125` |

当前目录不是 Git 仓库；组合摘要只用于标识本次工作区快照，不具备提交不可变性。

## 4. 测试场景与结果

### 4.1 工程质量与回归

| 测试项 | 命令/方法 | 实际结果 | 状态 |
| --- | --- | --- | --- |
| 锁文件一致性 | `uv --cache-dir .uv-cache lock --check` | 解析 125 个包 | 通过 |
| Ruff | `uv ... run ruff check .` | All checks passed | 通过 |
| Ruff 格式 | `uv ... run ruff format --check .` | 188 个文件已格式化 | 通过 |
| mypy | `uv ... run mypy app scripts` | 141 个源文件无问题 | 通过 |
| 后端默认回归 | `uv ... run pytest -q -rs` | 116 passed、4 skipped、2 warnings | 通过；跳过项已在隔离库覆盖 |
| 隔离数据库全量回归 | `scripts/run-postgres-integration-tests.ps1` | 120 passed、0 skipped、2 warnings | 通过 |
| 依赖审计 | `uv audit --locked` | 124 个包无已知漏洞或不利状态 | 通过 |
| 前端 lint/typecheck | `npm run lint`、`npm run typecheck` | 无错误 | 通过 |
| 前端组件测试 | `npm run test` | 19 passed | 通过 |
| 前端生产构建 | `npm run build` | 14 个静态页面生成成功 | 通过 |

保留两项非阻断依赖警告：Starlette TestClient/httpx 兼容性弃用提示、passlib 读取 argon2 版本的弃用提示。

### 4.2 数据库与迁移

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| 空库完整升级 | tmpfs 隔离库完成 001→017 | 通过 |
| Phase 4 逐级回滚 | 017→015 成功 | 通过 |
| 分级恢复 | 015→016→017 成功，最终为 head | 通过 |
| 完整数据库测试 | 120 项全部通过 | 通过 |
| 测试库清理 | `postgres-test` 精确停止并删除，未触碰开发卷 | 通过 |
| 开发库版本 | `017_phase4_metrics (head)` | 通过 |

### 4.3 API、SSE 与安全

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| `/v1/health` | HTTP 200，`status=ok` | 通过 |
| `/v1/health/ready` | HTTP 200，`status=ready` | 通过 |
| 未认证看板访问 | HTTP 401 | 通过 |
| 浏览器 Cookie 登录 | HTTP 200 | 通过 |
| SSE 缺少 CSRF | HTTP 403 | 通过 |
| SSE 不存在会话 | HTTP 200；事件为 `accepted,status,status,error,done` | 通过，失败关闭 |
| SSE 中文 UTF-8/顺序契约 | 自动化测试通过 | 通过 |
| 建议频率限制 | 同一测试用户在窗口内后续请求返回 429 | 通过 |
| Phase 4 运行验收 | store、agent、dashboard、team、SSE error contract 全部 True | 通过 |
| AI 运营字段越权 | Schema 拒绝提交模型字段 | 通过 |
| Mock 自动发送边界 | 三适配器 `real_writes=false`；自动回复默认关闭 | 通过 |

浏览器点击“生成”后，在 AI 依赖不可用/当前会话无法完成建议时显示“连接已结束，可重试”，未填充回复框、未自动发送，控制台无 error/warning。

### 4.4 看板、Agent 与系统设置页面

| 页面/能力 | 结果 | 状态 |
| --- | --- | --- |
| 数据看板 | 四指标、趋势 SVG、渠道分布、预警、热门咨询、更新时间可见 | 通过 |
| 趋势替代数据表 | 点击后生成 1 个表格、8 行（表头 + 7 日） | 通过 |
| Agent 运营页 | 运营配置入口存在；模型/Prompt/阈值未作为可写字段暴露 | 通过 |
| 店铺/渠道/团队页 | 路由、列表、创建/角色/禁用入口存在；渠道明确标记 Mock | 通过 |
| 明暗主题 | `light` 与 `dark` 切换生效，背景色同步变化 | 通过 |
| 四档响应式 | 五个 Phase 4 页面均满足 `scrollWidth == clientWidth` | 通过 |
| 英文模式 | 页面只部分翻译，仍混入大量中文 | **失败，DEF-P4-002** |
| 移动端触控尺寸 | 多个 Phase 4 控件高度为 40px | **失败，DEF-P4-003** |
| 浏览器控制台 | 最终 warning/error 列表为空 | 通过 |

四档响应式实测页面：`/dashboard`、`/agents`、`/settings/stores`、`/settings/channels`、`/settings/team`。375px 实际页面内容宽度为 360px，均未出现整体横向溢出。

### 4.5 部署与稳定性工程能力

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| 基础 Compose 配置 | `docker compose config --quiet` | 通过 |
| 生产 Compose 配置 | 使用测试占位公开 API URL 校验 | 通过 |
| 生产挂载与命令 | 后端/前端无源码挂载；后端无 reload；前端 `node server.js` | 通过 |
| 基础设施端口 | 生产覆盖不发布 PostgreSQL、Redis、MinIO 端口 | 通过 |
| restart policy | backend/frontend 为 `unless-stopped` | 通过 |
| 非 root | 后端 UID 999；生产前端镜像 UID 100 | 通过 |
| JSON 日志 | backend/jobs/agent-worker 为单行 JSON | 通过 |
| Agent Worker | 启动门禁通过；自动回复关闭时不认领任务 | 通过 |
| 恢复安全门禁 | PostgreSQL/MinIO `-WhatIf` 生效，错误目标确认被拒绝 | 通过 |
| 50 并发 SSE 脚本 | 单 Token 脚本与最大单用户并发 20 的配置约束冲突 | **失败，DEF-P4-001** |
| 五天稳定性 | 未执行 | 未通过生产门禁 |

日志证据示例仅包含低敏运行字段：`jobs_worker_started`、`agent_worker_ready` 和“自动回复开关关闭，Worker 不认领任务”。

## 5. 缺陷明细

### DEF-P4-001：50 并发 SSE 脚本无法在服务端合法配置下完成默认目标

| 项目 | 内容 |
| --- | --- |
| 优先级 | **P1** |
| 类型 | 性能测试工具、验收阻断 |
| 影响范围 | `backend/scripts/load_test_sse.py`、SSE 50 并发验收 |
| 建议负责 Agent | 全栈开发工程师Agent |
| 状态 | 未修复 |

复现步骤：

1. 查看脚本：默认 `--concurrency=50`，所有请求共用同一个 `CRM_ACCESS_TOKEN`。
2. 查看服务配置：`CHAT_USER_CONCURRENCY` 默认 2，Schema 上限为 20。
3. 尝试构造 `chat_user_concurrency=50`，Pydantic 返回校验失败；实测输出为 `rejected-50-user-concurrency`。
4. 因脚本不支持多用户 Token 池，即使把配置调到合法上限 20，默认 50 个请求也至少有 30 个会被 429 拒绝。

预期结果：50 并发工具应能在不绕过生产限流契约的前提下模拟 50 个授权并发客户端，例如支持多用户凭据池，并分别报告成功、429、首分块和总耗时；或者将测试目标明确改为“单用户并发限流验证”，另提供系统级 50 并发脚本。

实际结果：当前脚本不能形成公开 SSE 50 成功并发证据，阻断 Phase 4 P4-10 对该接口的性能验收。

### DEF-P4-002：英文模式未覆盖 Phase 4 页面业务文案

| 项目 | 内容 |
| --- | --- |
| 优先级 | **P2** |
| 类型 | 多语言、页面一致性 |
| 影响范围 | 数据看板、Agent 运营、团队设置、工作台 AI 建议 |
| 建议负责 Agent | 全栈开发工程师Agent |
| 状态 | 未修复 |

复现步骤：

1. 登录后点击“切换语言”，确认 `<html lang="en">`。
2. 打开 `/dashboard`：核心卡片部分为英文，但“会话趋势”“渠道分布”“实时预警”“热门咨询”“数据更新时间”等仍为中文。
3. 打开 `/agents`：页面标题为英文，但新建配置表单“店铺、编码、名称、说明、白名单工具、保存运营配置”仍为中文。
4. 打开 `/settings/team` 和 `/workspace`：团队正文、表单及 AI 建议区域仍大量使用中文。

预期结果：Phase 4 新增页面和交互文案在英文模式下使用统一词典，不出现中英混排。

实际结果：仅导航、部分标题和部分指标完成翻译，违反本阶段中英文验收要求。

### DEF-P4-003：移动端 Phase 4 交互控件未达到 44px 触控高度

| 项目 | 内容 |
| --- | --- |
| 优先级 | **P2** |
| 类型 | 移动端可访问性、页面交互 |
| 影响范围 | `/settings/team`，同类表单控件需一并回归 |
| 建议负责 Agent | 全栈开发工程师Agent |
| 状态 | 未修复 |

复现步骤：

1. 将视口设置为 375×900，打开 `/settings/team`。
2. 读取可见交互控件的计算尺寸。
3. 店铺/渠道/团队标签、角色下拉、姓名/邮箱/密码输入、角色和店铺范围下拉高度均为 40px。

预期结果：按 Phase 4 计划，移动端触控区域至少 44px。

实际结果：多处控件为 40px，键盘可达但触控尺寸不达标。

## 6. 观察项与环境风险

### OBS-P4-001：无 BOM 中文 PowerShell 脚本在 Windows PowerShell 5 下解析失败

- `powershell.exe -File scripts/run-postgres-integration-tests.ps1` 将 UTF-8 中文误解为本地代码页并产生语法错误。
- PowerShell 7 直接执行同一脚本后，隔离库迁移和 120 项测试全部通过。
- 该问题未影响当前 PowerShell 7 环境，但 README 使用笼统 `powershell` 代码块，建议明确最低版本或调整脚本编码兼容性。
- 优先级建议：P3，不阻断当前 Phase 4 核心功能。

### 生产门禁

- 真实平台写操作仍是 P0 外部接入风险，但不作为本次 Mock 范围内产品缺陷。
- 真实模型 SSE 50 并发、首分块和 P99 尚无本轮证据。
- 五天连续稳定性和 99.5% 可用性尚无正式报告。
- Docker Hub 固定 Node 标签可用性取决于发布环境镜像预热；本轮使用本地已构建生产镜像验证 UID。

## 7. 回归结果与验收建议

- Phase 1～3、AI Agent 和 BGE 既有自动化随本轮全量后端/数据库/前端测试执行，未发现回归失败。
- 迁移 001→017、017→015→016→017、健康检查、Cookie/CSRF、SSE 错误契约、看板/Agent/团队核心 API、生产 Compose 和非 root 镜像通过。
- Phase 4 当前仍有 `DEF-P4-001`（P1）、`DEF-P4-002`（P2）、`DEF-P4-003`（P2）未关闭。
- 真实模型 SSE 性能和五天稳定性仍属于正式生产门禁。

**验收建议：不接受当前 Phase 4 正式验收。先修复 DEF-P4-001～003并执行独立复测；其后使用可表达 50 个授权客户端的压测方案完成真实模型 SSE 性能测试，并继续执行五天稳定性观测。**

## 8. 证据与清理说明

- 自动化证据：116 项默认后端测试、120 项完整数据库测试、19 项前端测试及 14 路由生产构建。
- API 证据：登录 200、未认证 401、缺少 CSRF 403、SSE 事件 `accepted,status,status,error,done`、频控 429。
- 浏览器证据：真实 DOM、计算样式、截图、四档视口和控制台；最终控制台 warning/error 为 0。
- 部署证据：基础/生产 Compose 校验、生产前端 UID 100、后端 UID 999、JSON Worker 日志和恢复 `-WhatIf`。
- 本轮创建的两个临时测试账号已精确删除；隔离 PostgreSQL tmpfs 容器已删除；浏览器语言和主题已恢复为中文/亮色。
- 测试工程师未修改任何产品代码。
