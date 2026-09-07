# DeepSeek SSE 测试缺陷修复实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 REAL-FS-05 |
| 模块编号 | M02 |
| 主责 Agent | 全栈开发工程师Agent |
| 协作 Agent | 架构师Agent、AIAgent开发工程师Agent、测试工程师Agent |
| 实施状态 | 已完成 |
| 开始日期 | 2026-09-04 |
| 完成日期 | 2026-09-04 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 的 AI 首输出与系统可用性目标。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 的 11.6、11.18。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`。
- 任务依据：`全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` 的 REAL-FS-05。
- 缺陷依据：`测试工程师/Phase4-P4-00-全栈开发工程师Agent-M02-DeepSeek配置与SSE生产运行面-综合测试-001.md`。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 修复 `DEF-REAL-FS05-001～003` 的根因。
- 保持现有 `/v1/chat/query`、AI 安全草稿和生产开关边界不变。
- 为测试工程师提供可重复的确定性复测入口。

### 3.2 实施范围

- 生产 LLM 密钥非空校验与 ready 一致性。
- Redis SSE 并发租约生命周期、原子容量判断和精确释放。
- 单机 50 客户端压测限流 Profile、前置校验、样本完整性和退出状态。
- 对应测试、环境模板、部署说明、接口文档和计划状态。

### 3.3 非目标

- 不修改 DeepSeek Provider、Prompt、RAG、安全语义判定或模型质量算法。
- 不执行真实 DeepSeek 付费调用、50 个真实授权客户端或五日稳定性测试。
- 不开放公开回复、翻译、营销、自动回复或 AI 触发的平台写操作。
- 不处理既有 `DEF-REAL-FS01-005` 的 Next.js 16 破坏性升级。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解和验收标准。
- [x] 已读取代码编写手册和适用 `ponytail` Skill。
- [x] 已确认 Phase、任务编号、模块编号和主责 Agent。
- [x] 已确认 AI 模块边界、生产开关和独立复测要求。

## 5. 实施方案

### 5.1 方案说明

配置层新增统一的 `has_non_blank_secret` 判断，生产启动和 ready 对 DeepSeek、OpenAI、Anthropic 使用同一规则。SSE 并发控制不再使用固定 TTL 的整数计数器，而是为每次请求生成唯一 Redis 租约令牌；Lua 原子清理过期租约、判断容量并加入，释放只删除当前令牌。租约时长由流超时加 60 秒清理余量推导。

单机压测不修改日常默认限流。新增独立 Compose 叠加，将 integration/staging 测试窗口的单 IP 限额设为 60；应用启动门禁拒绝在 development/production 启用该 Profile。压测脚本要求声明实际服务端 IP 限额，全部样本完成且出现首个安全 `delta` 才返回成功退出码。

### 5.2 依赖关系

- 前置依赖：现有 Redis 7、DeepSeek Provider、`/v1/chat/query` 和 Cookie/CSRF 鉴权。
- 后续依赖：测试工程师独立复测 `DEF-REAL-FS05-001～003`；目标环境执行真实模型性能与五日稳定性测试。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 空白密钥被误判为配置完成 | ready 假阳性，首请求才失败 | 启动和 ready 复用去空白后的非空 Secret 校验 |
| 老请求释放新请求槽位 | 并发上限失效、成本增加 | 每个请求唯一租约，按令牌精确释放 |
| 不同实例租约时长不同 | 新短租约缩短旧长租约键 TTL | Lua 根据有序集合最晚到期时间设置键 TTL |
| 压测 Profile 被误用于生产 | 生产 IP 限流被长期放宽 | `SSE_LOAD_TEST_ENABLED` 仅允许 integration/staging |
| 429 或无首分块被误报为性能通过 | 形成无效放行证据 | 全样本完成且都有首个安全 `delta` 才成功退出 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `backend/app/shared/config/settings.py` | 修改 | 统一非空密钥校验、派生 SSE 租约时长、压测环境门禁 | 全栈开发工程师Agent |
| `backend/app/shared/health.py` | 修改 | ready 复用统一密钥规则 | 全栈开发工程师Agent |
| `backend/app/shared/database/redis.py` | 修改 | 唯一 SSE 租约和原子 Lua 容量控制 | 全栈开发工程师Agent |
| `backend/app/chat/router.py` | 修改 | 传入派生租约时长并按令牌释放 | 全栈开发工程师Agent |
| `backend/scripts/load_test_sse.py` | 修改 | 单 IP 容量预检、完整样本门禁和非零失败退出 | 全栈开发工程师Agent |
| `backend/tests/test_real_fs05_sse_runtime.py` | 修改 | 空白密钥、租约、压测环境与 Compose 回归 | 全栈开发工程师Agent |
| `backend/tests/test_sse_load_test.py` | 修改 | 单 IP 容量和性能样本完整性测试 | 全栈开发工程师Agent |
| `backend/tests/test_real_ai04_regressions.py` | 修改 | 适配唯一租约契约 | 全栈开发工程师Agent |
| `docker-compose.sse-load-test.yml` | 新增 | integration/staging 单机 50 客户端专用环境与限流叠加 | 全栈开发工程师Agent |
| `.env.example` | 修改 | 增加默认关闭的压测门禁变量 | 全栈开发工程师Agent |
| `README.md`、`deploy/production/README.md` | 修改 | 压测启停、预检、失败判定和恢复说明 | 全栈开发工程师Agent |
| `共享记忆文档/智能客服平台 — 管理端接口文档.md` | 修改 | 同步租约与压测契约 | 全栈开发工程师Agent |
| `全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` | 修改 | 同步缺陷修复状态 | 全栈开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：`POST /v1/chat/query` 请求和 SSE 事件结构不变。
- 数据库：不适用；无迁移和表结构变化。
- Redis：并发键升级为 `chat:concurrency:v2:{user_id}` 有序集合，历史计数器键依赖原 TTL 自然失效。
- 配置：新增 `SSE_LOAD_TEST_ENABLED=false`；仅专用 Compose 叠加设置为 true。
- AI：不适用；未修改模型、Prompt、RAG、工具或安全策略。

### 6.3 关键实现说明

- 密钥检查只在内存中读取 `SecretStr` 并判断 `strip()` 后是否非空，不记录或返回密钥。
- Redis 以服务端 `TIME` 计算租约到期时间，避免应用节点时钟偏差。
- Lua 使用最晚租约到期分值设置键 TTL，滚动配置变化不会让短租约提前删除长租约。
- 压测声明值不是关闭限流；请求仍经过认证、权限、CSRF、用户和 IP 限流，只为受控测试窗口提供足够样本容量。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| 空白密钥与 ready 专项 | REAL-FS-05、health、runtime 配置测试 | 空字符串/空格/换行失败关闭 | 90 passed | 通过 |
| 租约与 AI04 回归 | REAL-FS-05 + REAL-AI-04 聚焦测试 | 唯一租约且旧流程无退化 | 28 passed | 通过 |
| 最终 FS05 聚焦 | FS05 + SSE load 测试 | 三缺陷固定测试全部通过 | 42 passed | 通过 |
| 实际 Redis Lua | 真实 Redis 首次申请、超限、释放、再次申请 | `True True True` | 与预期一致 | 通过 |
| 默认后端全量 | `pytest -q -rs` | 无失败 | 1249 passed，12 skipped | 通过 |
| 隔离 PostgreSQL 全量 | `scripts/run-postgres-integration-tests.ps1` | 空库升级且无跳过 | 1261 passed，0 skipped；001→023 | 通过 |
| Python 编译 | `python -m compileall -q app scripts migrations` | 无语法错误 | 正常退出 | 通过 |
| Ruff | `ruff check app tests scripts migrations` | 无告警 | All checks passed | 通过 |
| 格式 | `ruff format --check app tests scripts migrations` | 无漂移 | 226 files already formatted | 通过 |
| mypy | `mypy app scripts` | 类型通过 | 162 个源文件通过 | 通过 |
| 前端 | `npm run lint`、`typecheck`、`test`、`build` | 全部通过 | 32 passed，14 个静态页面构建成功 | 通过 |
| Compose 合并 | production topology + ai + DeepSeek + load-test | backend=integration/60，后台 AI 关闭 | 合成配置解析成功；jobs/agent-worker LLM 关闭 | 通过 |
| Python 锁与审计 | `uv lock --check`、`uv audit --locked` | 锁一致且无已知漏洞 | 125 包解析；124 包无已知漏洞 | 通过 |
| 前端依赖审计 | `npm audit --audit-level=high` | 无 High | 3 High；沿用 DEF-REAL-FS01-005 | 失败 |
| 真实模型性能/稳定性 | 50 授权客户端、连续五日 | 达到 ADR 门禁 | 未执行，需目标环境和成本授权 | 未执行 |

## 8. 实施结果

- 完成项：三个 P1 的开发修复、固定测试、实际 Redis 探针、隔离数据库回归和文档同步。
- 未完成项：测试工程师独立复测、真实 DeepSeek 50 客户端性能、连续五日稳定性。
- 与原方案差异：新增显式 `SSE_LOAD_TEST_ENABLED`，防止专用限流叠加被误用于 development/production。
- 当前状态：开发修复已完成；原测试报告中的缺陷仍保持 Open，等待测试工程师独立复测。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| DEF-REAL-FS01-005 | Next.js 15 依赖链仍有 3 个 High，自动修复要求破坏性升级 Next.js 16 | P1 | 全栈开发工程师Agent、架构师Agent、测试工程师Agent | REAL-FS-01 独立依赖升级任务 |
| R-FS05-004 | 真实 DeepSeek 50 客户端和五日 99.5% 稳定性尚未执行 | P1 | 测试工程师Agent、架构师Agent | REAL-FS-05 生产验收 |

## 10. 交接事项

- 交接给：测试工程师Agent、架构师Agent。
- 后续任务：独立复测 `DEF-REAL-FS05-001～003`；通过后再安排真实模型性能和五日稳定性测试。
- 必须注意：专用压测叠加只能用于 integration/staging；压测后必须移除；正式缺陷状态不得由开发实施记录自行关闭。

## 11. 文档同步

- [x] 已同步接口变化。
- [x] 已同步架构决策（未改变 ADR，仅细化现有运行契约）。
- [x] 已同步任务状态。
- [x] 已通知测试工程师需要覆盖的范围。
- [x] 测试报告索引将在测试工程师正式复测后更新。
