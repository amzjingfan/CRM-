# TikTok OAuth 首次测试缺陷修复实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 REAL-FS-02 |
| 模块编号 | M00 |
| 主责 Agent | 全栈开发工程师Agent |
| 协作 Agent | 架构师Agent、测试工程师Agent |
| 实施状态 | 已完成 |
| 开始日期 | 2026-08-26 |
| 完成日期 | 2026-08-26 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 的真实渠道接入与多店铺隔离。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 第 11.7 节。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`。
- 任务依据：`全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` 的 REAL-FS-02。
- 测试依据：`测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-TikTokOAuth授权与凭证生命周期-综合测试-001.md`。
- 代码规范：`共享记忆文档/代码编写手册.md`。
- 官方契约：TikTok Shop Authorization、Refresh Token 和 Get Authorized Shops 文档。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 修复 `DEF-REAL-FS02-001～005` 的工程根因。
- 让 TikTok 渠道只能经 OAuth 创建，并在数据库层保证单店铺单 TikTok 渠道。
- 让 Token 刷新验证授权主体、授权店铺和 Scope 连续性，并具备可运行、并发安全的提前刷新入口。

### 3.2 实施范围

- 通用渠道 Schema/Service 的 TikTok 服务端拒绝。
- TikTok Token 刷新校验和 Jobs Worker 周期任务。
- `channel_accounts` TikTok 部分唯一索引及 019 可逆迁移。
- OAuth `return_to` 精确白名单。
- 后端、数据库、前端、Compose、文档和自动化回归。

### 3.3 非目标

- 不实施 REAL-FS-03 的真实只读 Adapter 或 Webhook。
- 不执行真实店铺 OAuth、真实 Token 刷新或平台后台撤销。
- 不开放平台写操作、公开 AI 回复、AI 营销或自动回复。
- 不修改 AI Agent、Prompt、RAG、模型和安全策略。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解和验收标准。
- [x] 已读取代码编写手册和 Ponytail Skill。
- [x] 已确认 Phase、任务编号、模块编号和主责 Agent。
- [x] 已确认依赖、风险和验收方式。

## 5. 实施方案

### 5.1 方案说明

沿用现有 FastAPI 模块化单体、SQLAlchemy、Jobs Worker 和 PostgreSQL，不新增调度框架。通用渠道入口在 Pydantic Schema 和 Service 两层拒绝 TikTok；OAuth callback 继续作为唯一授权写入口。Token 刷新重新校验卖家身份、Scope、`open_id` 哈希和 Get Authorized Shops 返回的唯一外部店铺，验证全部通过后才覆盖密文。

Jobs Worker 使用可配置周期扫描即将过期的渠道，Repository 通过 `FOR UPDATE SKIP LOCKED` 每次原子认领一条记录；刷新提交后释放行锁，因此多 Worker 不会同时刷新同一渠道。数据库迁移 019 使用 `store_id` 且 `platform='tiktok'` 的部分唯一索引兜底 callback 并发竞态。

### 5.2 依赖关系

- 前置依赖：REAL-FS-01、REAL-FS-02 初版、PostgreSQL、Jobs Worker、TikTok OAuth 客户端和服务端密钥配置。
- 后续依赖：REAL-FS-02 测试工程师独立复测；通过后才可申请真实店铺受控联调和 REAL-FS-03。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 历史数据已有重复 TikTok 渠道 | 唯一索引无法安全建立 | 019 迁移失败关闭并输出数据治理提示，不自动删除授权和审计证据 |
| 刷新返回其他卖家或店铺 | 凭证错绑到错误租户 | 对比 `open_id` 哈希并重新读取唯一授权店铺，不一致时保留旧密文并标记 `expired` |
| 多 Jobs Worker 重复刷新 | Token 轮换竞态、旧 Refresh Token 覆盖新值 | PostgreSQL 行锁和 `SKIP LOCKED` 原子认领 |
| 开发环境没有 TikTok OAuth 配置 | Worker 周期报错或误访问公网 | 配置不完整时刷新周期直接跳过 |
| 工程修复被误写为测试关闭 | 后续 Agent 错误放行真实平台 | 实施记录只标记开发完成，测试报告中的 Open 状态保持不变 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `backend/app/stores/schemas.py` | 修改 | 通用渠道请求只接受 Shopee/Amazon | 全栈开发工程师Agent |
| `backend/app/stores/service.py` | 修改 | Service 层再次拒绝 TikTok OAuth 绕过 | 全栈开发工程师Agent |
| `backend/app/stores/models.py` | 修改 | 声明 TikTok 单店铺部分唯一索引 | 全栈开发工程师Agent |
| `backend/app/stores/repository.py` | 修改 | 增加即将过期渠道的 `SKIP LOCKED` 认领 | 全栈开发工程师Agent |
| `backend/app/integrations/oauth_service.py` | 修改 | 严格回跳、刷新主体/店铺校验及刷新周期 | 全栈开发工程师Agent |
| `backend/app/jobs/worker.py` | 修改 | 接入 TikTok Token 周期刷新 | 全栈开发工程师Agent |
| `backend/app/shared/config/settings.py` | 修改 | 增加刷新周期、提前量和批量配置 | 全栈开发工程师Agent |
| `backend/migrations/versions/019_enforce_single_tiktok_channel_per_store.py` | 新增 | 可逆 TikTok 单店铺唯一迁移 | 全栈开发工程师Agent |
| `backend/tests/test_tiktok_oauth.py` | 修改 | 补充五项缺陷的服务级回归 | 全栈开发工程师Agent |
| `tests/integration/test_tiktok_oauth_postgres.py` | 新增 | 验证唯一索引和多 Worker 行锁认领 | 全栈开发工程师Agent |
| `.env.example`、`docker-compose.prod.yml` | 修改 | 同步刷新配置与生产注入 | 全栈开发工程师Agent |
| `README.md`、`deploy/production/README.md` | 修改 | 更新迁移 head、刷新和安全边界 | 全栈开发工程师Agent |
| `共享记忆文档/智能客服平台 — 管理端接口文档.md` | 修改 | 同步内部刷新和服务端限制 | 全栈开发工程师Agent |
| `全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` | 修改 | 同步首次测试和修复状态 | 全栈开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：OAuth 路径不变；通用 `POST /v1/settings/channels` 的 `platform` 请求值收窄为 `shopee | amazon`。
- 数据库：新增 head `019_tiktok_channel_unique`，建立 `uq_channel_accounts_store_tiktok` 部分唯一索引；升级和回滚均已验证。
- 配置项：新增 `TIKTOK_TOKEN_REFRESH_POLL_SECONDS=300`、`TIKTOK_TOKEN_REFRESH_LEAD_SECONDS=86400`、`TIKTOK_TOKEN_REFRESH_BATCH_SIZE=20`。
- AI：不适用；未修改任何 AI 代码或配置边界。

### 6.3 关键实现说明

- `return_to` 只接受精确字符串 `/settings/channels`，拒绝 query、fragment、外部 URL 和其他站内路径。
- 刷新校验失败不会覆盖 Access/Refresh Token 密文；渠道改为 `expired`，`oauth_status` 改为 `reauthorization_required` 并写低敏审计。
- 刷新成功会同步当前授权店铺摘要、过期时间、Scope、平台请求 ID 和最后同步时间。
- 019 只限制 TikTok，不改变 Shopee/Amazon 的现有数据模型。
- 所有真实平台与自动化开关继续关闭。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| 锁文件 | `uv lock --check` | 锁文件可复现 | 125 个包解析成功 | 通过 |
| 后端专项 | `uv run pytest tests/test_tiktok_oauth.py tests/test_real_runtime_config.py -q` | 五项缺陷回归通过 | 43 passed | 通过 |
| 后端默认回归 | `uv run pytest -q` | 既有模块无退化 | 551 passed、10 skipped、2 个既有弃用警告 | 通过 |
| PostgreSQL 全量 | `scripts/run-postgres-integration-tests.ps1` | 001→019 和数据库场景通过 | 561 passed、0 skipped、2 个既有弃用警告 | 通过 |
| 并发刷新 | 两个独立数据库会话认领同一渠道 | 仅一个会话获得渠道 | 第二个会话返回空 | 通过 |
| 唯一约束 | 同店铺插入两个 TikTok 渠道 | 第二条被数据库拒绝 | `IntegrityError` | 通过 |
| 迁移可逆 | `alembic downgrade 018_ai_observability` 后 `upgrade head` | 019 可回滚并恢复 | 最终 `019_tiktok_channel_unique (head)` | 通过 |
| 静态检查 | Ruff、format、`mypy app scripts` | 全部通过 | 210 文件格式正确，155 个源文件无类型错误 | 通过 |
| 前端回归 | lint、typecheck、test、build | 无退化 | 24 passed，14 个静态页面构建成功 | 通过 |
| 生产 Compose | 仅输出 `config --services` | 安全解析 | 8 个服务解析成功 | 通过 |
| 依赖审计 | `uv audit --locked` | 无已知漏洞 | 124 个包无已知漏洞或不良状态 | 通过 |
| 真实 TikTok OAuth/刷新 | 真实凭证受控联调 | 证明真实平台行为 | 未执行：未注入真实凭证 | 未执行 |

开发过程中新增 PostgreSQL 测试曾两次因测试清理/父子插入顺序错误失败；修正测试夹具后从空库执行 001→019 和全部 561 项测试通过。两次失败均未修改产品数据，隔离 `postgres-test` 使用 tmpfs 并已删除。

## 8. 实施结果

- 完成项：`DEF-REAL-FS02-001～005` 的开发修复、019 迁移、刷新调度、配置、测试和文档同步。
- 未完成项：测试工程师独立复测；真实店铺 OAuth、真实 Token 刷新和平台侧撤销。
- 与原方案差异：初版认为无需迁移；独立测试证明应用层查询存在并发竞态，因此新增 019 部分唯一索引。
- 当前状态：开发修复已完成，但权威 001 号测试报告仍为不通过，缺陷正式关闭前不得放行 REAL-FS-03。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-REAL-FS02-004 | `DEF-REAL-FS02-001～005` 尚未由测试工程师独立复测关闭 | P1 | 测试工程师Agent | REAL-FS-02 第二次综合测试 |
| R-REAL-FS02-005 | 真实店铺 OAuth、Scope、Token 刷新和平台侧撤销尚未执行 | P1 | 全栈开发工程师Agent、测试工程师Agent | REAL-FS-02 真实环境联调 |
| R-REAL-FS02-006 | 平台后台撤销和密钥轮换仍需运维演练 | P2 | 全栈开发工程师Agent、架构师Agent | REAL-FS-06 |

## 10. 交接事项

- 交接给：测试工程师Agent、架构师Agent。
- 后续任务：测试工程师对 001 号报告执行第二次独立综合复测；正式关闭后才申请真实店铺联调。
- 必须注意：复测必须使用迁移 head 019，覆盖 TikTok 通用 POST 拒绝、`open_id`/授权店铺变化、两个数据库会话并发认领、019 升降级和严格 `return_to`。所有真实能力开关继续保持关闭。

## 11. 文档同步

- [x] 已同步接口变化。
- [x] 已同步架构既有单店铺单 TikTok 边界的数据库实现。
- [x] 已同步任务状态。
- [x] 已通知测试工程师需要覆盖的范围。
- [x] 测试报告索引保持权威 001 号“不通过”结论，待测试工程师复测后更新。
