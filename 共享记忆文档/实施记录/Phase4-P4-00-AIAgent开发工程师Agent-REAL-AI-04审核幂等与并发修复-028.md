# REAL-AI-04 审核幂等与并发修复实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-AI-04` |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 全栈开发工程师Agent、架构师Agent、测试工程师Agent |
| 实施状态 | 已完成 |
| 开始日期 | 2026-09-03 |
| 完成日期 | 2026-09-03 |
| 代码位置 | `CRM智能聊天系统/` |

> “已完成”仅表示 `DEF-REAL-AI04-003/004` 的开发修复和工程验证完成。两项缺陷仍以 002 号正式测试报告的 Open 状态为准，必须由测试工程师第三次独立复测后才能关闭；生产 AI、公开回复和营销发送继续关闭。

## 2. 需求与依据

- 缺陷依据：`测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-REAL-AI-04回复翻译营销草稿-综合测试-002.md` 中 `DEF-REAL-AI04-003/004`。
- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 中 AI 营销草稿、人工复核和安全发送边界。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 中统一写操作幂等、营销事件和权限规则。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`、`AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md`。
- 任务依据：REAL-AI-04 回复、翻译和营销草稿。
- 验收依据：`共享记忆文档/MVP范围与验收标准.md` 中人工复核、失败关闭、幂等和可审计要求。
- 代码规范：`共享记忆文档/代码编写手册.md`、项目各级 `AGENTS.md` 及 Agent/Python/PostgreSQL/TDD/安全/Ponytail Skill。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 同一审核幂等键和同一规范化请求重放首次终态，不重复写审计。
- 同一幂等键对应不同请求时稳定返回 `409 RESOURCE_CONFLICT`。
- 并发批准和拒绝只能有一个数据库终态和一条成功审计。
- 浏览器 401 刷新重试复用原始幂等键。

### 3.2 实施范围

- 营销事件审核字段、唯一约束和可逆迁移。
- Marketing Repository 原子条件更新、Service 幂等重放与低敏审计。
- 审核路由和前端 API 幂等键透传、自动刷新重试稳定性。
- 单元、前端源契约和隔离 PostgreSQL 双事务集成测试。

### 3.3 非目标

- 不修改 AI 草稿生成、Prompt、DeepSeek Provider 或安全决策算法。
- 不执行真实平台消息、发券、地址修改或营销发送。
- 不开启公开 AI 回复、自动回复或生产翻译。
- 不替代测试工程师修改 002 号报告或自行关闭正式缺陷。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解、验收标准和 002 号测试报告。
- [x] 已读取代码编写手册、各级 `AGENTS.md` 和适用 Skill。
- [x] 已确认 Phase、任务编号、模块编号和主责 Agent。
- [x] 已确认真实平台写操作、公开 AI 回复和营销发送继续保持关闭。

## 5. 实施方案

### 5.1 方案说明

审核事件新增持久化的幂等键和规范化请求 SHA-256，并由 `(store_id, ai_review_idempotency_key)` 唯一约束防止同店铺重复占用。Repository 使用带前置状态条件的单条 `UPDATE ... RETURNING` 抢占 `waiting_review + pending` 事件；PostgreSQL 在并发写锁释放后重新校验条件，因此最多一个事务能够取得终态。

Service 在抢占失败后读取当前事件：同键同哈希返回已有结果且不再写审计，同键不同哈希返回 409，其他已终结竞争也返回 409。事件终态和 `audit_logs` 在同一事务提交；唯一约束竞争通过 `IntegrityError` 回滚并转成稳定冲突，避免半提交。审计只保存幂等键摘要、请求摘要和评论摘要，不保存审核评论原文。

前端在一次写请求开始时构造稳定请求配置，原请求和一次 401 刷新重试共用同一 `Idempotency-Key`；审核 API 也允许调用方显式传入同一键处理网络结果丢失后的安全重放。

### 5.2 依赖关系

- 前置依赖：迁移 `022_ai_marketing_review`、营销事件审核 API、店铺 RBAC、PostgreSQL。
- 后续依赖：测试工程师第三次独立复测、REAL-AI-05 真实模型评测、后续独立营销发送工具和生产门禁。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 同键结果丢失后重复审核 | 返回冲突或重复审计 | 持久化键和请求哈希；同键同请求直接重放 |
| 同键被用于另一请求或事件 | 错误复用历史结果 | 哈希比对和店铺级唯一约束，冲突返回 409 |
| 并发批准与拒绝都成功 | 审核终态及审计不可信 | 单条条件更新原子抢占，状态和审计同事务 |
| 401 自动重试更换键 | 服务端无法识别同一次操作 | 请求入口生成一次稳定配置并复用 |
| 审核信息泄漏 | 审计包含敏感业务内容 | 仅保存键、请求和评论 SHA-256 摘要 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/backend/app/marketing/models.py` | 修改 | 增加审核幂等键、请求哈希、成对检查和店铺级唯一约束 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/marketing/repository.py` | 修改 | 增加带状态前置条件的原子审核抢占 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/marketing/service.py` | 修改 | 实现请求哈希、同键重放、冲突处理和同事务低敏审计 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/marketing/router.py` | 修改 | 把校验后的 `Idempotency-Key` 显式传给 Service | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/migrations/versions/023_marketing_review_idempotency.py` | 新增 | 可逆增加审核幂等字段、检查约束和唯一约束 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_marketing_review_idempotency.py` | 新增 | 覆盖同键重放、不同请求冲突和审计唯一性 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_real_ai04_regressions.py` | 修改 | 适配原子 Repository 契约并保留原 REAL-AI-04 回归 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/tests/integration/test_marketing_review_postgres.py` | 新增 | 隔离 PostgreSQL 双连接并发终态和持久化重放测试 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/frontend/lib/api.ts` | 修改 | 生成并复用稳定幂等键，审核方法显式接收键 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/frontend/app/marketing/page.tsx` | 修改 | 每次人工审核动作创建一个幂等键并传给 API | AIAgent开发工程师Agent |
| `CRM智能聊天系统/frontend/tests/phase3.test.mjs` | 修改 | 增加审核显式键和 401 重试复用契约检查 | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：`POST /v1/marketing/events/{event_id}/review` 路径与响应结构不变；`Idempotency-Key` 从仅校验升级为服务层和数据库持久化语义。
- 数据库：新增迁移 `023_marketing_review_idempotency`；`marketing_events` 增加 `ai_review_idempotency_key`、`ai_review_request_hash`、成对检查约束和 `(store_id, ai_review_idempotency_key)` 唯一约束。
- 配置项：不新增环境变量或生产开关。
- AI：不修改模型、Prompt、RAG、安全阈值或草稿内容；审核批准仍不发送。

### 6.3 关键实现说明

- 写竞争不依赖进程内锁，多个 Worker/进程仍由 PostgreSQL 统一保证唯一终态。
- 同键重放不会新增 `audit_logs`；同键不同请求和其他竞争终态均使用公开冲突错误。
- 内部可信调用未传键时按请求哈希派生稳定内部键；公开 HTTP 路由仍强制要求真实幂等头。
- 状态更新和审计记录共同提交，任何唯一约束异常都会回滚整个事务。
- 批准结果仍固定 `send_performed=false`，未增加平台副作用。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| TDD 红测 | 新增幂等单元测试后先运行 | 修复前稳定失败 | 缺少 `claim_event_review`，2 项按预期失败 | 通过 |
| 聚焦单元回归 | REAL-AI-04 及审核幂等测试 | 新旧行为均通过 | 新增 2 项通过；原 REAL-AI-04 5 项通过 | 通过 |
| 迁移往返 | 空库升级至 023，`023 → 022 → 023` | 可升级、可回滚、恢复 head | 全部通过，当前 `023_marketing_review_idempotency` | 通过 |
| PostgreSQL 幂等重放 | 两个独立会话顺序重放 | 同键同请求重放、异请求 409、审计 1 条 | 通过 | 通过 |
| PostgreSQL 并发终态 | 两个独立事务并发批准/拒绝 | 成功 1、冲突 1、终态 1、审计 1 | 通过 | 通过 |
| 后端全量回归 | 隔离 PostgreSQL 执行 `pytest` | 无失败 | `1203 passed, 2 warnings` | 通过 |
| Python 代码检查 | `ruff check`、显式源码目录 `ruff format --check` | 无错误 | 检查通过，232 个文件格式通过 | 通过 |
| Python 类型检查 | `mypy app scripts` | 无类型错误 | 本机连续运行超过 5 分钟无输出，人工终止；未获得结论 | 未执行 |
| 依赖锁与审计 | `uv lock --check`、`uv audit --locked` | 锁一致且无已知漏洞 | 125 包解析；124 包无已知漏洞和不利状态 | 通过 |
| 前端质量 | `npm run lint/typecheck/test/build` | 全部通过 | lint/typecheck 通过，32 项测试通过，14 个静态路由构建成功 | 通过 |
| Compose 配置 | `docker-compose config --quiet` | 配置合法 | 退出码 0 | 通过 |
| 正式独立复测 | 测试工程师第三次报告 | 关闭 003/004 | 未执行，开发 Agent 无权关闭正式缺陷 | 未执行 |

补充：对整个后端目录执行 `ruff format --check .` 时，Ruff 被历史不可访问 pytest 临时目录触发内部 panic；改为显式扫描正式源码、脚本、迁移和测试目录后通过。该工具环境问题不影响产品代码验证，但应清理历史测试临时目录后再恢复点号扫描。

## 8. 实施结果

- 完成项：审核持久化幂等、结果重放、异请求冲突、原子唯一终态、同事务审计、401 重试稳定键、迁移和自动化测试。
- 未完成项：测试工程师第三次独立复测；本机 mypy 全量运行结论；真实 DeepSeek 质量、公开回复、营销发送和稳定性门禁。
- 与原方案差异：采用单条条件更新而非长事务 `SELECT FOR UPDATE`，缩短锁持有时间并直接表达唯一终态前置条件；未新增独立幂等表。
- 当前状态：开发修复和工程验证完成，`DEF-REAL-AI04-003/004` 仍为 Open，REAL-AI-04 和生产营销草稿审核仍不得放行。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-001 | `DEF-REAL-AI04-003/004` 尚未由测试工程师独立复测 | P1 | 测试工程师Agent | Phase4 / REAL-AI-04 第三次复测 |
| R-002 | 本机 mypy 多次超过 5 分钟无输出，未取得全量类型检查结论 | P2 | AIAgent开发工程师Agent、环境维护者 | Phase4 / REAL-AI-04 复测前环境检查 |
| R-003 | `DEF-P4-AI-009` 按 002 号报告仍为 Reopened | P2 | AIAgent开发工程师Agent、测试工程师Agent | Phase4 / REAL-AI-03 |
| R-004 | 真实模型、公开 SSE、营销发送和五日稳定性尚未验收 | P1 | 架构师Agent、全栈开发工程师Agent、AIAgent开发工程师Agent、测试工程师Agent | Phase4 生产门禁 |
| R-005 | 当前项目不是 Git 仓库，不能提供提交级不可变基线 | P2 | 架构师Agent、项目负责人 | 版本治理 |

## 10. 交接事项

- 交接给：测试工程师Agent、全栈开发工程师Agent、架构师Agent。
- 后续任务：测试工程师使用新的隔离 PostgreSQL 执行同键同请求重放、同键异请求冲突、双事务批准/拒绝、审计唯一性、店铺隔离和全量回归；全栈工程师复核前端网络重试边界；架构师维持生产门禁。
- 必须注意：不得修改 002 号历史报告；`approved` 仍只表示草稿审核通过，不表示平台已发送。第三次独立复测关闭缺陷前，不得把本次开发验证作为生产放行结论。

## 11. 文档同步

- [x] 已同步接口幂等语义和数据库迁移。
- [x] 未新增相互竞争的架构决策。
- [x] 已同步任务状态为开发修复完成、待第三次独立复测。
- [x] 已通知测试工程师需要覆盖的范围。
- [x] 测试报告索引将在正式测试完成后由测试工程师更新。
