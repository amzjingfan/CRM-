# Phase 4 REAL-AI-04 回复、翻译和营销草稿第二次独立综合测试报告

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-AI-04` |
| 模块编号 | M04 |
| 模块名称 | REAL-AI-04 回复、翻译和营销草稿 |
| 被测主责 Agent | AIAgent开发工程师Agent |
| 测试执行 Agent | 测试工程师Agent |
| 测试类型 | 综合测试、修复验证、接口与集成测试、安全测试、并发测试、数据库测试、回归测试、部署检查、代码审查 |
| 测试日期 | 2026-09-02 |
| 本轮结论 | **不通过** |

## 2. 测试依据

- `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md`
- `架构师/PLAN-001-REAL-真实平台与AI生产环境接入实施计划-v1.0.md`
- `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`
- `共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`
- `共享记忆文档/智能客服平台 — 管理端接口文档.md`
- `共享记忆文档/MVP范围与验收标准.md`
- `共享记忆文档/代码编写手册.md`
- `共享记忆文档/实施记录/Phase4-P4-00-AIAgent开发工程师Agent-REAL-AI-04综合测试缺陷修复-027.md`
- `测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-REAL-AI-04回复翻译营销草稿-综合测试-001.md`
- `测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-REAL-AI-03缺陷关闭-综合测试-010.md`

## 3. 测试目标、范围与非范围

本轮重点复测上一轮两个 P1，并审查修复新增的营销草稿审核闭环：

- SSE 在结果交给传输层前发生断开、取消或失败时，是否补记稳定交付失败终态，同时保留计算已完成的低敏摘要。
- 安全 AI 营销候选是否持久化为 `waiting_review + pending`，且不调用发券、平台消息或其他写工具。
- 草稿查询与审核是否执行权限校验、店铺隔离、审计和零发送约束。
- `Idempotency-Key` 是否真正进入审核业务语义，同键同请求是否重放，同键不同请求是否冲突。
- 并发批准与拒绝是否原子串行化，是否只允许一个审核终态。
- 迁移、依赖安全、BGE 运行时、全量后端和前端是否回归。

本轮不调用真实 DeepSeek，不执行真实 TikTok 写操作，不评测真实模型语言质量，不执行公开回复、生产翻译、AI 营销发送、50 客户端 SSE 压测或五日稳定性观察。测试工程师未修改产品代码、开发测试、依赖锁文件、实施计划和历史报告。

## 4. 基线冻结与独立方法

### 4.1 当前基线

- 当前目录不是 Git 仓库，无法声明提交级不可变基线。
- 对 `backend/app`、`backend/migrations`、`backend/tests`、`frontend/app`、`frontend/lib`、`frontend/tests` 及后端/前端依赖清单共 232 个文件按相对路径排序，分别计算 SHA-256，再将相对路径和小写文件哈希以 LF 拼接后计算聚合 SHA-256：

```text
6135d92a24c2c854fdfd79867d9b01ec3947b236c100d67f4171a98efc160b3a
```

- 该哈希用于标识本次可验证文件快照，不等价于不可变提交。

### 4.2 独立证据

测试工程师新增只读测试证据：

```text
测试工程师/evidence/REAL-AI-04-002/test_real_ai04_independent_retest.py
```

独立探针覆盖：

1. SSE 在 `result` 事件前断开。
2. 工作流结果产生后、输出前取消。
3. 安全营销候选进入待审核且零工具副作用。
4. 跨店铺审核统一返回资源不存在。
5. 相同审核请求重试是否重放。
6. 并发批准和拒绝是否只允许一个终态。
7. 隔离 PostgreSQL 中真实双事务并发审核。

探针使用合成数据，不包含真实客户、店铺、订单、Token、模型密钥或完整消息。

## 5. 测试环境

| 组件 | 版本或状态 |
| --- | --- |
| PowerShell | 7.6.4 |
| Python | 3.11.15 |
| uv | 0.12.3 |
| Docker | 29.7.2 |
| Docker Compose | 5.3.1，使用 `docker-compose` 独立命令 |
| Node.js | 24.19.0 |
| npm | 11.17.0 |
| 前端框架 | Next.js 15.5.23 |
| 隔离数据库 | `pgvector/pgvector:pg16`，测试服务宿主端口 5433，完成后已删除 |
| Alembic head | `022_ai_marketing_review` |
| 运行服务 | backend/frontend/postgres/redis/minio 健康，worker/jobs 运行 |
| 真实 DeepSeek | 未调用；本轮只验收确定性工程和失败关闭边界 |

## 6. 执行结果汇总

| 验证项 | 预期 | 实际 | 结果 |
| --- | --- | --- | --- |
| REAL-AI-04 开发回归 | 无失败 | 5 passed | 通过 |
| 独立修复与安全探针 | 全部满足契约 | 4 passed、2 failed；PostgreSQL 专项另复现并发缺陷 | **失败** |
| SSE 结果前断开 | 交付不得保留成功终态 | 写入 `SSE_DELIVERY_INTERRUPTED`，无 `result` | 通过 |
| SSE 取消 | 使用稳定取消错误码 | 写入 `SSE_DELIVERY_CANCELLED`，无 `result` | 通过 |
| 安全营销候选 | 待审核、零发送 | `waiting_review + pending`，工具调用为 0 | 通过 |
| 店铺隔离 | 跨店铺统一 404 | 返回资源不存在 | 通过 |
| 审核同请求重试 | 同键同请求重放原结果 | 首次成功，第二次返回 409；服务层未接收幂等键 | **失败** |
| 审核并发终态 | 只允许一个成功 | 批准和拒绝两个事务均成功 | **失败** |
| 隔离 PostgreSQL 全量 | 无失败、无数据库跳过 | 1199 passed、2 warnings | 通过 |
| 迁移往返 | `021 → 022 → 021 → 022` | 通过，恢复 head | 通过 |
| Ruff check/format | 无错误和格式差异 | 通过；223 个产品文件，独立探针也通过 | 通过 |
| mypy | 无错误 | 162 个源文件通过 | 通过 |
| compileall | 无语法错误 | 通过 | 通过 |
| 前端 lint/typecheck | 无错误 | 均通过 | 通过 |
| 前端测试 | 无失败 | 32 passed | 通过 |
| 前端生产构建 | 构建成功 | 14 个静态路由生成成功 | 通过 |
| Python 锁定依赖审计 | 无已知漏洞 | 124 个包无已知漏洞或不利状态 | 通过 |
| BGE CPU 运行时 | 真实本地资产可推理 | Transformers 5.10.4、Torch 2.13.0+cpu、1024 维向量、Rerank 有限分数 | 通过 |
| Compose 与健康检查 | 配置有效、服务可用 | 配置通过；`/v1/health` HTTP 200 | 通过 |

两项全量警告来自 Starlette TestClient/httpx 与 Argon2 版本属性弃用提示，不影响本轮功能结论。GPU/FP16 探针本轮未由测试工程师重复执行；027 号实施记录中的开发者证据予以保留，但不作为本轮异主体独立结论。

## 7. 上一轮缺陷复测

### DEF-REAL-AI04-001：SSE 在结果交付前断开仍保留成功运行

状态：**Closed**。

复测结果：

- 路由在传输层尚未取得 `result` 时识别断开和取消。
- `mark_suggestion_delivery_interrupted()` 仅对原 `succeeded` 运行补记失败，使用稳定错误码。
- 运行摘要保留 `computation_status=succeeded;delivery_status=interrupted`，没有把模型计算事实伪装成失败或把交付失败伪装成成功。
- 独立断开和取消探针均通过。

关闭边界：本结论只覆盖结果交给 ASGI 传输层之前的失败。当前设计不推断网络层最终送达，也不等价于端到端客户端 ACK。

### DEF-REAL-AI04-002：安全营销候选无法进入人工审核闭环

状态：**Closed**。

复测结果：

- 确定性安全和独立复核通过的候选返回 `is_safe=true`，但继续固定 `requires_human=true`、`send_performed=false`。
- Worker 持久化草稿正文、AgentRun 关联和审核状态，并停在 `waiting_review + pending`。
- 查询和审核按店铺隔离，跨店铺访问返回 404。
- 批准或拒绝只更新审核记录和审计日志，不调用平台工具。
- 前端明确提示批准不代表发送。
- `022_ai_marketing_review` 迁移和往返通过。

关闭边界：审核原子性和幂等性是本轮新增发现，分别登记为 `DEF-REAL-AI04-003/004`，不重新打开旧缺陷编号。

### 继承门禁：Transformers 已知漏洞

状态：**Closed（本轮依赖范围）**。

- 锁定版本已从 5.5.4 升级到 5.10.4。
- `uv audit --locked` 返回 124 个包无已知漏洞和不利状态。
- 测试工程师使用本地只读 BGE 资产完成 CPU Embedding 和 Rerank 探针，向量维度为 1024，分数为有限值。
- 本轮没有下载模型或向外发送数据。

## 8. 新增缺陷

### DEF-REAL-AI04-003：审核接口声明幂等但未实现结果重放

| 项目 | 内容 |
| --- | --- |
| 优先级 | **P2** |
| 状态 | **Open** |
| 类型 | 接口契约、幂等、重试一致性 |
| 影响范围 | `POST /v1/marketing/events/{event_id}/review`、前端审核重试、审计一致性 |
| 是否阻断 | 单独不阻断草稿生成，但阻断审核接口按既定写操作契约验收 |
| 建议负责 Agent | AIAgent开发工程师Agent、全栈开发工程师Agent |

复现步骤：

1. 对同一待审核事件以相同操作者、相同审核决定、相同评论和相同 `Idempotency-Key` 发起批准。
2. 首次请求成功后，模拟网络响应丢失并重放相同请求。
3. 观察第二次结果和审计记录。

实际结果：

- 路由只通过依赖检查请求头存在，没有把幂等键传给 Service。
- Service 方法没有幂等键、请求哈希或结果重放参数。
- 首次请求把事件改为 `approved`；第二次在状态检查处返回 `409 RESOURCE_CONFLICT`。
- 前端 `reviewMarketingDraft()` 不接收调用方稳定键，通用客户端为每次写请求生成新 UUID；401 刷新后的重试也会重新构造请求头。

预期结果：

- 同键同规范化请求应重放第一次终态和响应，不重复写审计。
- 同键不同请求应返回 409。
- 幂等键必须进入服务层和持久化约束，不能只检查请求头存在。

代码证据：

- `backend/app/marketing/router.py:201-214`：依赖验证头存在，但调用 Service 时未传入键。
- `backend/app/marketing/service.py:124-168`：无幂等参数和重放记录。
- `frontend/lib/api.ts:62-83`：通用写请求生成随机键，刷新后重新执行 `rawRequest()`。
- `frontend/lib/api.ts:121`：审核方法不接收稳定幂等键。

### DEF-REAL-AI04-004：并发批准和拒绝可同时成功

| 项目 | 内容 |
| --- | --- |
| 优先级 | **P1** |
| 状态 | **Open** |
| 类型 | 并发一致性、人工审核、安全状态机 |
| 影响范围 | AI 营销人工审核、最终审核状态、审计可信度 |
| 是否阻断 | 是，阻断 REAL-AI-04 端到端验收和生产营销草稿审核放行 |
| 建议负责 Agent | AIAgent开发工程师Agent、全栈开发工程师Agent；架构师Agent确认审核终态规则 |

复现步骤：

1. 创建一个 `waiting_review + pending` 的合成营销事件。
2. 开启两个独立数据库事务，一个批准、一个拒绝。
3. 使用同步屏障确保两事务都在任一提交前读到 `pending`。
4. 同时继续提交并统计成功结果。

实际结果：

- 两个事务都通过状态检查并成功返回。
- Repository 使用普通 `SELECT`，没有 `FOR UPDATE`。
- Service 执行“读取状态 → 内存改值 → 添加审计 → commit”，没有条件更新、版本号或唯一终态约束。
- 最终事件状态取决于最后提交者，并存在产生相互矛盾审核轨迹的执行路径。

隔离 PostgreSQL 独立复现结果：

```text
expected successful=1, conflict=1
actual   successful=2, conflict=0
```

预期结果：批准和拒绝只能有一个成为最终决定；另一事务应返回稳定 409，或在同键同请求时重放原结果。数据库状态和审计必须共同保持唯一终态语义。

建议修复：

- 使用 `SELECT ... FOR UPDATE` 串行化同一事件审核，或使用带旧状态条件的原子 `UPDATE ... WHERE status='waiting_review' AND ai_review_status='pending' RETURNING ...`。
- 将幂等键、规范化请求哈希和审核结果持久化，并建立必要唯一约束。
- 审计记录应和状态变更处于同一事务；未获得状态转换权的事务不得写成功审计。
- 增加真实 PostgreSQL 双事务回归，不得只使用内存 Stub。

代码证据：

- `backend/app/marketing/repository.py:24-31`：普通查询，无行锁。
- `backend/app/marketing/service.py:131-166`：非原子状态检查和提交。

## 9. 功能、安全与数据审查

### 9.1 回复、翻译与 SSE

- 现有回复和翻译继续保持 `send_performed=false`，未发现 AI 绕过受控工具直接写平台。
- SSE 断开/取消修复只修改运行追踪，不扩大公开回复权限。
- 翻译脱敏、触发消息关联、原文哈希、同语言跳过模型和失败关闭由全量回归继续覆盖。
- 真实 DeepSeek 翻译准确率和生产时延仍无本轮证据。

### 9.2 AI 营销草稿

- 安全候选现在可以进入待审核，不安全候选继续隐藏正文。
- `is_safe=true` 仅表示候选内容通过当前确定性门禁，不等于允许发送。
- `approved` 只表示人工审核结论，不调用发券、消息或平台适配器。
- 审核评论仅保存 SHA-256 摘要，未发现原文进入审计日志。
- 店铺隔离通过，但审核终态的幂等和并发完整性未通过。

### 9.3 既有安全缺陷状态

- `DEF-P4-AI-008` 按最新权威报告保持 Closed，本轮未发现危险客户实例事实自动发送回归。
- `DEF-P4-AI-009` 已被 REAL-AI-03 第十次开放集复测改为 **P2/Reopened**；本轮全量固定测试通过不能覆盖该开放集失败，也不能将其关闭。

## 10. 自动化、数据库与运行态证据

### 10.1 后端与依赖

| 命令或场景 | 结果 |
| --- | --- |
| `uv lock --check` | 通过；解析 125 个包 |
| `uv run ruff check app migrations scripts tests` | All checks passed |
| `uv run ruff format --check app migrations scripts tests` | 223 files already formatted |
| `uv run mypy app scripts` | 通过；162 个源文件 |
| `uv run python -m compileall -q app scripts` | 通过 |
| 隔离 PostgreSQL `uv run pytest` | 1199 passed、2 warnings |
| `uv audit --locked` | 通过；124 个包无已知漏洞或不利状态 |
| 独立证据 Ruff check/format | 通过 |

### 10.2 数据库

| 场景 | 结果 |
| --- | --- |
| 空库 `001 → 022` | 通过 |
| `022 → 021 → 022` | 通过，恢复 `022_ai_marketing_review (head)` |
| 隔离 PostgreSQL 全量 | 1199 passed、0 skipped |
| PostgreSQL 双事务审核 | 两个相反审核均成功，失败 |
| 测试服务清理 | `postgres-test` 已停止并删除，无隔离数据残留 |

并发专项的一次确定性运行返回两个成功；为追加诊断字段进行重复执行时出现事务等待，测试工程师手动终止该次诊断并删除隔离服务。首次数据库复现、独立内存屏障和源代码三类证据一致，足以确认缺少并发串行化；手动终止的诊断运行不计为通过证据。

### 10.3 前端、运行态与模型资产

| 验证项 | 结果 |
| --- | --- |
| `npm run lint` | 通过 |
| `npm run typecheck` | 通过 |
| `npm run test` | 32 passed |
| `npm run build` | Next.js 15.5.23 构建通过，14 个静态路由 |
| `docker-compose config --quiet` | 通过 |
| `docker-compose ps` | 原有七个服务正常，测试数据库无残留 |
| `GET /v1/health` | HTTP 200，`status=ok`，版本 0.1.0 |
| BGE CPU 探针 | 1024 维 Embedding、Rerank 分数有限，未下载模型 |

本轮没有调用真实模型、真实店铺或外部写接口，没有产生可恢复或不可恢复的真实业务数据。

## 11. 尚未完成的生产门禁

除本报告两个新增 Open 缺陷外，以下门禁仍未完成：

- `DEF-P4-AI-009` 开放集误拦截修复和独立复测。
- 真实 DeepSeek 回复、翻译、营销草稿和结构化声明质量评测。
- 真实模型数据出境、脱敏、限流、余额不足和生产错误降级验收。
- 50 个授权客户端 SSE 首分块、P99、错误率、断线和取消测试。
- 连续五日稳定性和 99.5% 可用性。
- 真实 TikTok 店铺联调、真实人工消息发送和联合回滚。
- Git 提交或其他不可变发布候选冻结。

公开 AI 回复、生产翻译、AI 营销发送、自动回复和 AI 触发的平台写操作必须继续关闭。

## 12. 最终结论

**REAL-AI-04 第二次独立综合测试不通过。**

- `DEF-REAL-AI04-001` 已关闭：SSE 在结果交给传输层前断开或取消会补记稳定交付失败终态。
- `DEF-REAL-AI04-002` 已关闭：安全营销候选可持久化、查询和人工审核，保持店铺隔离、审计和零发送。
- 上一轮 Transformers 已知漏洞门禁已关闭：锁定依赖审计和 BGE CPU 兼容探针通过。
- 新增 `DEF-REAL-AI04-003`（P2/Open）：审核接口只检查幂等头存在，没有实现同键结果重放。
- 新增 `DEF-REAL-AI04-004`（P1/Open）：并发批准和拒绝可同时成功，审核终态和审计不具备原子一致性。
- 1199 项隔离 PostgreSQL 全量、32 项前端、迁移、静态质量、生产构建、Compose 和健康检查通过，但不能覆盖新的 P1。
- `DEF-P4-AI-009` 仍为 P2/Reopened；真实模型、公开 SSE 和稳定性门禁仍未验收。

在 `DEF-REAL-AI04-004` 关闭、`DEF-REAL-AI04-003` 完成契约修复，并由测试工程师执行第三次独立复测前，REAL-AI-04 不得验收，AI 营销草稿审核不得用于生产放行依据。

## 13. 清理与交接

- 测试工程师仅新增本报告、独立证据和测试报告索引条目，未修改产品代码或开发测试。
- 隔离 `postgres-test` 服务已停止并删除；临时测试数据不可恢复，原有项目服务未受影响。
- `DEF-REAL-AI04-003/004` 交由 AIAgent开发工程师Agent与全栈开发工程师Agent修复；架构师Agent确认“同一事件唯一人工终态”和幂等重放规则。
- 修复后必须执行真实 PostgreSQL 双事务测试、同键同请求重放、同键不同请求冲突、审计唯一性、店铺隔离和全量回归。
- 正式测试结论以本报告为当前 REAL-AI-04 权威结论，001 号报告保留历史追溯。
