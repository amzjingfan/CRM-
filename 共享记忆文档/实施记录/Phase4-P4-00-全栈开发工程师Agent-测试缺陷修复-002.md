# Phase 4 测试缺陷修复实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00 阶段缺陷修复；关联 P2-09、P4-08、P4-10 |
| 模块编号 | M00 |
| 主责 Agent | 全栈开发工程师Agent |
| 协作 Agent | 测试工程师Agent、架构师Agent |
| 实施状态 | 已完成 |
| 开始日期 | 2026-08-22 |
| 完成日期 | 2026-08-22 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 中管理端中英文、客服工作台和运营看板要求。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 中 SSE、看板、Agent 和系统设置接口。
- 架构依据：`架构师/ARCH-001-SYS-系统总体架构设计-v1.1.md`、`架构师/ARCH-003-DATA-数据库与向量库初版设计-v1.0.md`。
- 任务依据：`全栈开发工程师/PLAN-001-全栈工程实施计划-v1.0.md` Phase 4。
- 验收依据：`共享记忆文档/MVP范围与验收标准.md`，以及 `测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-SSE看板部署与稳定性-综合测试-001.md` 中 `DEF-P4-001～003`、`OBS-P4-001`。
- 代码规范：`共享记忆文档/代码编写手册.md`。
- UI 约束：`ui-ux-pro-max` Skill 的移动触控目标和可访问性建议，交互目标最小高度采用 44px。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 修复 `DEF-P4-001`：SSE 压测工具能够表达 50 个不同授权客户端，不再默认复用单个用户；429 限流独立统计。
- 修复 `DEF-P4-002`：Phase 4 看板、Agent、店铺、渠道、团队和工作台 SSE 建议区域的业务文案完整支持英文模式。
- 修复 `DEF-P4-003`：移动端筛选器、表单输入框和选择框达到至少 44px 触控高度。
- 处理 `OBS-P4-001`：项目 PowerShell 脚本在 Windows PowerShell 5.1 下可以正确解析和执行。

### 3.2 实施范围

- SSE 工程压测脚本、凭证池契约、失败分类、使用说明和单元测试。
- Phase 4 前端页面、共用状态组件、布局无障碍标签、移动触控尺寸和前端回归测试。
- PowerShell 脚本编码、最低版本声明、Windows PowerShell 5.1 实际执行验证。
- README、忽略规则、实施记录和实施记录索引。

### 3.3 非目标

- 不修改 `app/agent`、Prompt、模型路由、RAG、阈值、工作流节点和 AI 评测实现。
- 不生成或伪造真实模型 50 并发性能数据，不替代测试工程师执行授权环境性能复测。
- 不缩短或伪造五天稳定性观测，不修改测试工程师原始报告及其正式结论。
- 不修改数据库迁移、公开 API 或业务数据。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取最新 PRD、接口、任务拆解、团队职责、Phase 4 实施记录和测试报告。
- [x] 已读取代码编写手册、全栈 Agent 规范、`ui-ux-pro-max` Skill 和浏览器控制 Skill。
- [x] 已确认 Phase4、P4-00、M00 和全栈开发工程师 Agent 主责边界。
- [x] 已确认压测凭证安全、服务端限流、国际化、移动可访问性和脚本编码风险。

## 5. 实施方案

### 5.1 方案说明

- 压测工具新增仓库外 JSON 凭证池。每个客户端提供 Access Token、CSRF Token 和可访问会话 ID；默认每组凭证只承担一个并发请求，50 并发因此要求 50 组不同授权客户端。
- 保留单客户端环境变量冒烟模式，但容量校验会阻止单凭证直接执行默认 50 并发。隔离测试环境只有显式传入 `--requests-per-credential` 才允许复用。
- SSE 样本将 `429` 标记为 `rate_limited`，并输出低敏 `outcomes` 与 `status_codes` 汇总；Token、CSRF、会话正文和模型正文均不进入输出。
- Phase 4 页面基于现有 `useLanguage()` 补齐所有界面标签、操作提示、确认框、空状态、SSE 状态和无障碍标签；店铺名、员工名、咨询意图等业务数据保持原值，不强行机器翻译。
- `.filter` 和 `.compact-field` 的最小高度统一为 44px，避免后定义的 40px 样式覆盖基础触控约束。
- 全部 PowerShell 脚本增加 `#requires -Version 5.1` 并统一为 UTF-8 BOM，兼容 Windows PowerShell 5.1 和 PowerShell 7。

### 5.2 依赖关系

- 前置依赖：Phase 4 SSE 接口、Cookie/CSRF 认证、看板和运营管理页面、既有 Docker 测试环境。
- 后续依赖：测试工程师使用不同授权用户凭证池执行真实模型 SSE 50 并发，并对 `DEF-P4-001～003` 和 `OBS-P4-001` 独立复测。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 单 Token 被并发与频率限制拦截 | 50 并发结果失真 | 默认一凭证一并发，执行前校验凭证容量，429 单独归类 |
| 压测凭证泄露 | 测试账号被未授权使用 | 文件只允许从仓库外读取，忽略常见本地文件名，输出不包含凭证和会话 ID |
| 英文模式混入服务端业务数据 | 被误判为未翻译界面文案 | 界面文案完整翻译；用户、店铺、状态枚举和咨询意图按原始业务数据展示 |
| 40px 样式覆盖基础触控尺寸 | 移动端误触和可访问性不达标 | 共用样式固定 44px，并增加源码与真实浏览器尺寸回归 |
| Windows PowerShell 5.1 错误解码 UTF-8 中文 | 脚本语法错误、测试无法启动 | UTF-8 BOM、版本声明、PS5 解析和完整隔离库执行双重验证 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/backend/scripts/load_test_sse.py` | 修改 | 新增多客户端凭证池、容量门禁、独立客户端连接、429/认证/传输失败分类和低敏汇总 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_sse_load_test.py` | 新增 | 覆盖 50 个独立客户端、容量拒绝、凭证文件、重复 Token 和状态分类 | 全栈开发工程师Agent |
| `CRM智能聊天系统/frontend/app/dashboard/page.tsx` | 修改 | 补齐看板英文正文、图表标签、预警、热门咨询和时间格式 | 全栈开发工程师Agent |
| `CRM智能聊天系统/frontend/app/agents/page.tsx` | 修改 | 补齐 Agent 表单、启停、运行配置和提示文案英文分支 | 全栈开发工程师Agent |
| `CRM智能聊天系统/frontend/app/settings/stores/page.tsx` | 修改 | 补齐店铺设置英文文案 | 全栈开发工程师Agent |
| `CRM智能聊天系统/frontend/app/settings/channels/page.tsx` | 修改 | 补齐渠道设置、Mock 提示和确认框英文文案 | 全栈开发工程师Agent |
| `CRM智能聊天系统/frontend/app/settings/team/page.tsx` | 修改 | 补齐团队管理、角色范围、禁用和时间格式英文文案 | 全栈开发工程师Agent |
| `CRM智能聊天系统/frontend/app/workspace/page.tsx` | 修改 | 补齐会话、业务工具、SSE 建议和无障碍标签英文文案 | 全栈开发工程师Agent |
| `CRM智能聊天系统/frontend/components/States.tsx` | 修改 | 共用加载和重试状态跟随语言切换 | 全栈开发工程师Agent |
| `CRM智能聊天系统/frontend/components/AppShell.tsx` | 修改 | 补齐认证等待和导航控制的英文无障碍标签 | 全栈开发工程师Agent |
| `CRM智能聊天系统/frontend/app/globals.css` | 修改 | 将筛选器和紧凑字段最小高度修正为 44px | 全栈开发工程师Agent |
| `CRM智能聊天系统/frontend/tests/phase4.test.mjs` | 修改 | 增加 Phase 4 英文业务文案和 44px 触控尺寸回归断言 | 全栈开发工程师Agent |
| `CRM智能聊天系统/scripts/*.ps1` | 修改 | 六个脚本增加 PS5.1 声明并转换为 UTF-8 BOM | 全栈开发工程师Agent |
| `CRM智能聊天系统/README.md` | 修改 | 增加多客户端压测凭证池、429 说明和 PowerShell 兼容性说明 | 全栈开发工程师Agent |
| `CRM智能聊天系统/.gitignore` | 修改 | 忽略本地 SSE 压测凭证文件 | 全栈开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：不适用，公开 HTTP/SSE 接口契约不变。
- 数据库：不适用，无迁移、表、字段和索引变化。
- 配置项：压测 CLI 新增 `--credentials-file` 和 `--requests-per-credential`；未新增应用运行环境变量，未记录真实凭证。
- AI：不适用，未修改 AI Agent、模型、Prompt、RAG、阈值和工作流。

### 6.3 关键实现说明

- 压测请求为每个虚拟客户端创建独立 `httpx.AsyncClient`、Cookie 容器和连接，避免共享连接池弱化并发真实性。
- 凭证文件要求非空 `clients` 数组并拒绝完全重复的 Access Token；各行可使用不同授权会话，跨店铺和权限校验仍由服务端执行。
- 传输结果只记录客户端序号、HTTP 状态、结果分类和时延；不输出用户身份、Token、CSRF、会话 ID、消息或模型文本。
- 前端国际化覆盖可见文本、确认框、错误回退、`aria-label` 和 `aria-live` 提示。业务数据不属于词典文案，保持服务端原值。
- PowerShell 兼容性不仅执行 AST 解析，还由 Windows PowerShell 5.1 直接运行完整隔离 PostgreSQL 迁移和测试脚本；本机执行策略仅对测试子进程使用 `-ExecutionPolicy Bypass`，未修改系统策略。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| SSE 压测工具单元测试 | `uv run pytest tests/test_sse_load_test.py -q` | 多客户端容量和失败分类正确 | 8 passed | 通过 |
| 后端 Ruff | `uv run ruff check .` | 无静态错误 | All checks passed | 通过 |
| 后端格式 | `uv run ruff format --check .` | 全部文件格式正确 | 189 files already formatted | 通过 |
| 后端 mypy | `uv run mypy app scripts` | 无类型错误 | 141 source files 无问题 | 通过 |
| 后端默认回归 | `uv run pytest -q -rs` | 既有 Phase 1～4 和 AI 测试不退化 | 124 passed、4 skipped、2 warnings；跳过项为未提供隔离数据库 | 通过 |
| Windows PowerShell 5.1 解析 | `powershell.exe` 调用 AST Parser 检查 `scripts/*.ps1` | 六个脚本无编码和语法错误 | 6/6 PASS，版本 5.1.19041.6456 | 通过 |
| Windows PowerShell 5.1 隔离库回归 | `powershell.exe -ExecutionPolicy Bypass -File scripts/run-postgres-integration-tests.ps1` | 脚本启动隔离库、迁移并自动清理 | 001→017 迁移成功，128 passed、0 skipped、2 warnings，容器已清理 | 通过 |
| 依赖审计 | `uv audit --locked` | 无已知漏洞 | 124 个包无已知漏洞和不利状态 | 通过 |
| 前端 lint | `npm run lint` | 无 lint 错误 | 退出码 0 | 通过 |
| 前端类型 | `npm run typecheck` | 无 TypeScript 错误 | 退出码 0 | 通过 |
| 前端测试 | `npm run test` | 既有和新增测试全部通过 | 21 passed | 通过 |
| 前端生产构建 | `npm run build` | Next.js 构建成功 | Next.js 15.5.23 构建成功，14 个静态页面生成 | 通过 |
| Compose 配置 | `docker compose ... config --services`，含开发、生产和 `ai` Profile | 服务配置可解析并包含 `agent-worker` | 基础与生产服务通过；AI Profile 包含 `agent-worker` 和模型服务 | 通过 |
| 英文页面浏览器回归 | 本地页面切换英文并检查 `/dashboard`、`/agents`、三个设置页和 `/workspace` | Phase 4 业务文案无固定中文残留 | 界面文案均为英文；中文仅来自店铺名、员工名等业务数据 | 通过 |
| 375px 触控与溢出 | 浏览器视口 375×812，读取团队页控件边界和文档宽度 | 交互控件至少 44px，无横向溢出 | 10 个紧凑字段和 3 个设置导航控件均为 44px，overflow=0 | 通过 |
| 浏览器控制台 | 读取页面 warning/error | 无前端运行错误 | 空列表 | 通过 |
| 真实模型 SSE 50 并发 | 需要 50 个授权用户、合法会话和真实模型环境 | 形成公开 SSE P99 与首分块证据 | 未执行：本轮没有授权凭证池和真实模型环境 | 未执行 |
| 五天稳定性 | 授权生产等价环境连续观测 | 形成 99.5% 可用性证据 | 未执行：不可在单次开发会话中替代持续测试 | 未执行 |

## 8. 实施结果

- 完成项：`DEF-P4-001～003` 的代码修复、自动化回归和本地浏览器验证；`OBS-P4-001` 的编码兼容修复及 Windows PowerShell 5.1 实际执行验证。
- 未完成项：测试工程师尚未发布独立复测报告；真实模型 SSE 50 并发和五天稳定性生产门禁尚未执行。
- 与原方案差异：测试报告将 PowerShell 5.1 问题列为 P3 观察项，本轮在不扩大业务边界的前提下一并关闭代码侧兼容问题。
- 当前状态：全栈侧缺陷修复与工程验证已完成，正式缺陷关闭和 Phase 4 验收结论等待测试工程师独立复测。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-P4-001 | `DEF-P4-001～003` 和 `OBS-P4-001` 尚未由测试工程师在新报告中正式关闭 | P1 | 测试工程师Agent | Phase4 P4-00 定向复测 |
| R-P4-002 | 真实模型公开 SSE 仍缺 50 个授权客户端的 P99 和首分块证据 | P1 | 测试工程师Agent、AIAgent开发工程师Agent | Phase4 P4-10 性能复测 |
| R-P4-003 | 五天连续稳定性和 99.5% 可用性尚未形成持续观测报告 | P1 | 测试工程师Agent、全栈开发工程师Agent | Phase4 P4-10 稳定性门禁 |
| R-P4-004 | Starlette TestClient 和 argon2 仍有既有弃用警告 | P3 | 全栈开发工程师Agent | 后续依赖维护任务 |

## 10. 交接事项

- 交接给：测试工程师Agent、架构师Agent、AIAgent开发工程师Agent。
- 后续任务：测试工程师复测 `DEF-P4-001～003` 和 `OBS-P4-001`；取得授权环境后使用 50 个不同用户凭证执行公开 SSE 压测，并继续五天稳定性观测。
- 必须注意：凭证池必须存放在仓库外且测试后安全删除；默认保持一凭证一并发。`rate_limited`/429 不计为成功。不得用确定性 Provider 或内部 BGE 50 并发数据替代真实模型公开 SSE 结论。

## 11. 文档同步

- [x] 已同步压测 CLI 使用变化和 README。
- [x] 本次无新增架构决策。
- [x] 已同步实施状态到实施记录索引。
- [x] 已明确通知测试工程师复测范围和生产门禁。
- [x] 测试报告索引将在测试工程师发布正式复测报告后更新。
