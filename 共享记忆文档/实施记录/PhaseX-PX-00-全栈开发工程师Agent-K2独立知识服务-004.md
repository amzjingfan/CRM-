# K2 独立知识服务实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | PhaseX |
| 任务编号 | PX-00；专项任务 K2，正式项目管理编号待补充 |
| 模块编号 | M04 |
| 主责 Agent | 全栈开发工程师Agent |
| 协作 Agent | 架构师Agent（提供已签署的 KB-G0/K1 架构与治理基线）；本次无其他 Agent 实际协作 |
| 实施状态 | 已完成（K2 工程实现）；正式独立 QA 与生产放行待执行 |
| 开始日期 | 2026-09-15 |
| 完成日期 | 2026-09-15 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/产品需求文档.md` 中 M04 知识库与 RAG 边界，以及用户确认的“公司内部多个系统共用、项目内部资料不入库、先打通 TK-US”范围。
- 接口依据：`架构师/API-001-KB-内部证据检索与兼容契约-v1.0.md`。
- 架构依据：`架构师/ADR-001-KB-独立知识服务与空间授权边界-v1.0.md`、`架构师/SEC-001-KB-身份权限与数据安全基线-v1.0.md`、`架构师/DEP-001-KB-独立部署可用性与灾备基线-v1.0.md`、`架构师/DATA-001-KB-公司级知识来源与覆盖治理-v1.0.md`、`架构师/验收-001-KB-KBG0联合架构评审结论-v1.0.md`。
- 任务依据：`共享记忆文档/开发任务拆解（按人天分配）.md` 中 Phase X / K2。
- 验收依据：K2 实施计划的 Completion Gate；G0 结论明确 K2 完成不等于 K3 内容、K4 同步、K5 多系统或生产放行完成。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 交付可独立启动、独立迁移、独立授权且可供多个内部系统复用的公司级知识证据服务底座。
- 在 K3 活跃索引不存在时稳定失败关闭，不伪造知识证据。

### 3.2 实施范围

- 独立 FastAPI 应用、健康/就绪端点和 `POST /internal/v1/evidence:search`。
- 独立 `company_knowledge` 数据库、11 张权威表、4 个 Alembic 版本和 migration/runtime 分权角色。
- 应用 ES256/EdDSA JWT、店铺委托 JWT、JTI 撤销、精确范围授权和强制低敏审计。
- Compose 叠加栈、`company-knowledge` MinIO 桶和最小读写策略。
- 自动化测试、静态检查、真实本地容器迁移/健康/权限/审计联调。

### 3.3 非目标

- 不采集或导入 K1 内容，不生成切片、Embedding、向量或混合检索索引。
- 不调用 TikTok Shop，不同步店铺数据，不修改 CRM FAQ/RAG 链路，不切换任何消费系统。
- 不把项目 PRD、代码、接口、测试、实施记录、运维材料或内部聊天纳入知识语料。
- 不执行正式独立 QA、真实预发/生产部署、备份恢复、性能或两个真实消费系统验收。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解和验收标准。
- [x] 涉及代码时已读取代码编写手册和适用 Skill。
- [x] 已确认 Phase、任务编号、模块编号和主责 Agent。
- [x] 已确认依赖、风险和验收方式。

## 5. 实施方案

### 5.1 方案说明

K2 采用独立 FastAPI 进程和独立 SQLAlchemy metadata/Alembic 历史；可与 CRM 共用 PostgreSQL 集群和 MinIO 实例，但数据库、数据库角色、桶、对象存储账号和权限策略相互隔离。调用方先用短期应用 Token 建立服务身份，访问 `shop_private` 时再携带更短期的店铺委托 Token；两类 Token 使用分离公钥集，应用 key 绑定唯一应用。最终授权由服务端应用范围、店铺 grant 与受委托主体 grant 判定，而非信任请求正文或 Token 自报权限。

证据接口把身份/权限 HTTP 错误与 `ok / no_evidence / conflict / unavailable` 业务四态分离。K2 的默认 searcher 固定返回 `unavailable / INDEX_GENERATION_UNAVAILABLE`，待 K3 以可替换端口接入活跃索引。可替换 searcher 返回后仍由 API 出口强制核对应用、平台、市场、语言、读者、空间、店铺、时效、用途策略、代际和追踪标识，任一不符返回 `CONTENT_METADATA_INVALID`。所有决策先写强制低敏审计，审计不可用时请求失败关闭；响应 `trace_id` 与审计记录可直接关联。

### 5.2 依赖关系

- 前置依赖：KB-G0-01～07 已接受；K1 三类内容、来源权利和 TK-US 授权证据已完成签署；本地 PostgreSQL/MinIO/Docker Desktop 可用。
- 后续依赖：K3 内容与索引管道、K4 TK 来源同步、K5 多系统消费与灰度验收。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 调用方伪造店铺或扩大范围 | 跨应用/跨店铺数据泄漏 | 非对称短期 Token、服务端精确 grant、店铺委托和 JTI 撤销取交集 |
| 无索引时返回错误答案 | 误导客服或触发错误动作 | K2 默认 `unavailable`，不回退 CRM FAQ，不允许自动发送 |
| 审计含敏感正文 | 扩大数据暴露面 | 仅存低敏代号、哈希、决策、计数、耗时和 trace；结构测试禁止 query/Token/正文列 |
| PostgreSQL 旧卷恢复慢导致假失败 | Compose 启动不稳定 | 仅在 K2 叠加栈增加 120 秒启动宽限和重试，不改数据卷 |
| 运行身份拥有 DDL | 服务被攻陷后可改权威结构 | migration/runtime 独立角色；实测 runtime DDL 被拒绝 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/backend/app/knowledge_service/` | 新增 | 配置、入口、认证、授权、模型、仓储、四态 API、错误和审计实现 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/knowledge_alembic.ini`、`backend/knowledge_migrations/` | 新增 | 独立 Alembic 环境；001 基线、002 可回填治理元数据、003 审计 trace、004 安全边界迁移 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_knowledge_service_*.py` | 新增 | 配置、健康、模型、迁移、认证、授权、API、OpenAPI、部署测试 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/pyproject.toml`、`backend/uv.lock` | 修改 | 显式加入 `cryptography` 非对称验签依赖并锁定版本 | 全栈开发工程师Agent |
| `CRM智能聊天系统/docker-compose.knowledge.yml` | 新增 | 知识库初始化、迁移、MinIO 初始化和知识服务叠加栈 | 全栈开发工程师Agent |
| `CRM智能聊天系统/deploy/postgres/bootstrap-company-knowledge.sql` | 新增 | 独立数据库及 migration/runtime 最小权限角色 | 全栈开发工程师Agent |
| `CRM智能聊天系统/deploy/minio/company-knowledge-policy.json` | 新增 | 专用桶最小读写策略 | 全栈开发工程师Agent |
| `CRM智能聊天系统/.env.example`、`deploy/postgres/README.md`、`deploy/minio/README.md` | 修改 | K2 配置模板与部署说明 | 全栈开发工程师Agent |
| `架构师/API-001-KB-内部证据检索与兼容契约-v1.0.md`、`架构师/DATA-001-KB-公司级知识来源与覆盖治理-v1.0.md` | 修改 | 同步实际接口、身份头、错误边界、K2 状态和治理表落地情况 | 全栈开发工程师Agent |
| `共享记忆文档/智能客服平台 — 管理端接口文档.md`、`开发任务拆解（按人天分配）.md` | 修改 | 增加 K2 消费契约和 K2～K5 状态 | 全栈开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：新增 `/internal/health/live`、`/internal/health/ready` 和 `POST /internal/v1/evidence:search`；应用 Token 使用 `Authorization`，店铺委托使用 `X-Shop-Delegation`。
- 数据库：新增 11 张 `kb_*` 表（含委托主体权威）；应用范围精确到平台、市场、语言、读者和空间；治理元数据对齐 DATA-001-KB；审计增加 `trace_id` 和分离的应用/委托 JTI 哈希。
- 配置项：新增 `KNOWLEDGE_*` 独立配置命名空间和分离的 `KNOWLEDGE_APPLICATION_VERIFICATION_KEYS_JSON` / `KNOWLEDGE_DELEGATION_VERIFICATION_KEYS_JSON`；部署入口校验真实 PEM、应用 key 绑定、公用受众、专用数据库/runtime 用户和非示例对象存储凭证。Compose 不再把 CRM `.env` 整体注入容器。未记录任何真实密钥。
- AI：K2 不运行本地或外部模型；只定义 K3 searcher 端口和失败关闭行为。

### 6.3 关键实现说明

- 应用 Token 最长 5 分钟、委托 Token 最长 2 分钟；强制 `typ`、`kid`、issuer、audience、token_type、时间和 JTI claims，只接受 ES256/EdDSA；两套 key domain 不能交叉签名。
- `company_shared` 禁止 `shop_ref`；`shop_private` 必须同时满足应用 Token、委托 Token、服务端精确范围和有效店铺 grant。
- 401 表示身份无效/撤销，403 表示已认证但应用停用或超范围，503 表示授权权威、就绪依赖或强制审计不可用。
- 强制审计不保存查询、Token、知识正文、客户数据或真实店铺 ID；`shop_ref` 只保存 SHA-256，`jti` 只保存哈希。
- 本地 Compose 使用专用数据库与对象存储账号；运行角色只读权威表且只能追加审计，不能更新授权、删除审计或创建表。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| K2 自动化测试 | `uv run --offline pytest tests/test_knowledge_service_*.py -q` | 全部通过 | 60 passed；1 条第三方 TestClient 弃用警告 | 通过 |
| 后端全量回归 | `uv run --offline pytest -q --basetemp <随机隔离目录>` | 全仓测试通过且避开 Windows 共享临时目录权限问题 | 1621 passed，16 skipped；仅第三方弃用/测试算法警告 | 通过 |
| CRM 健康/安全回归 | `uv run --offline pytest tests/test_health.py tests/test_security.py -q` | 既有边界无回归 | 7 passed；2 条第三方弃用警告 | 通过 |
| Ruff | `uv run --offline ruff check app/knowledge_service knowledge_migrations tests/test_knowledge_service_*.py` | 无问题 | All checks passed | 通过 |
| Mypy | `uv run --offline mypy app/knowledge_service` | 无类型错误 | 12 个源文件无问题 | 通过 |
| Alembic 离线 SQL | `uv run --offline alembic -c knowledge_alembic.ini upgrade head --sql` | 独立生成 001～004 且无 CRM 表 | 成功生成至 `004_kb_security` | 通过 |
| 带数据真实迁移 | 随机新建隔离库，插入 001 种子后执行 `001→head→001→head`，最后仅删除该临时库 | 升降级成功且来源、审批、审计数据保真 | 两轮成功；回退后 `seed-reviewer/未审` 保留，最终版本 `004_kb_security` | 通过 |
| Compose 解析 | `docker-compose -f docker-compose.yml -f docker-compose.knowledge.yml config --quiet` | 配置有效 | 退出码 0 | 通过 |
| 最终镜像构建 | `docker-compose -f docker-compose.yml -f docker-compose.knowledge.yml build knowledge-service` | 最新依赖与代码可生成镜像 | 成功构建本地 `crm-backend:local`，镜像 ID `73c248655ab4` | 通过 |
| 容器与就绪 | 启动叠加栈并请求 `GET /internal/health/ready` | 服务、独立库和对象存储依赖就绪 | `status=ok`、`database=company_knowledge`；服务及依赖健康 | 通过 |
| 真实负向鉴权与审计关联 | 无 Token 请求 `req-k2-security-final-2` 后查询审计 | HTTP 401 且响应/audit trace 一致 | HTTP 401；trace `361e6cb7-dd18-42e2-afb3-be7f220e6008` 在审计中对应 `rejected` | 通过 |
| 数据库最小权限 | 查询 PostgreSQL 权限目录并以 runtime 角色追加审计 | 权威表只读、审计只插入 | `applications SELECT=true/UPDATE=false`，`audit INSERT=true/DELETE=false`；实际 INSERT 成功 | 通过 |
| MinIO 初始化 | 检查初始化容器日志 | 专用桶/用户/策略创建并绑定 | `company-knowledge`、`knowledge-local`、`company-knowledge-rw` 创建/绑定成功 | 通过 |
| 正式独立 QA | 测试工程师在独立环境执行 K2 安全、迁移、故障和性能测试 | 形成权威测试报告 | 本次未执行；开发验证不能替代独立 QA | 未执行 |

## 8. 实施结果

- 完成项：独立进程、数据库/迁移、对象存储、非对称身份、服务端精确授权、四态证据契约、强制低敏审计、失败关闭、自动化与本地容器验证。
- 未完成项：K3 内容与索引、K4 TK 同步、K5 两个真实内部系统接入、独立 QA、真实 staging/production 门禁。
- 与原方案差异：治理元数据、审计追踪和安全收紧拆分为 002/003/004 增量迁移；代码审查后新增分域验签、委托主体权威、响应出口围栏、带数据可逆迁移与逐表最小权限；Compose 针对既有 PostgreSQL 持久卷恢复增加 K2 专属启动宽限；未越权生成测试工程师正式报告。
- 当前状态：K2 工程实现已完成且开发侧门禁通过；在正式独立 QA 前不标记为项目验收或生产可用。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-001 | 尚无活跃内容/向量索引，服务按设计只返回 unavailable | P1 | AIAgent开发工程师Agent、全栈开发工程师Agent | PhaseX / K3 |
| R-002 | 尚未执行真实 TK 来源变更同步、撤销和冲突治理 | P1 | 全栈开发工程师Agent、数据负责人 | PhaseX / K4 |
| R-003 | 尚未由两个真实内部消费系统证明隔离、回退和兼容 | P1 | 全栈开发工程师Agent、测试工程师Agent | PhaseX / K5 |
| R-004 | 未执行独立 QA、性能、故障注入、备份恢复和真实环境门禁 | P1 | 测试工程师Agent、运维负责人 | PhaseX / K2 QA、K5 |
| R-005 | 生产应用身份、验签公钥、精确 grant 与密钥轮换尚未配置 | P1 | 架构师Agent、全栈开发工程师Agent | PhaseX / K5、生产门禁 |

## 10. 交接事项

- 交接给：测试工程师Agent、AIAgent开发工程师Agent、全栈开发工程师Agent。
- 后续任务：测试工程师先按 API-001-KB、SEC-001-KB、DEP-001-KB 和本记录执行独立 K2 复测；通过后推进 K3 内容管道与混合检索，再推进 K4/K5。
- 必须注意：不要向 K2 导入项目内部资料；不要把 `unavailable` 当成错误答案回退入口；不要在没有真实应用身份、精确 grant 和独立验收时声称“公司多个系统已经共用”。

## 11. 文档同步

- [x] 已同步接口变化。
- [x] 已同步架构决策。
- [x] 已同步任务状态。
- [x] 已通知测试工程师需要覆盖的范围（本记录即交接依据）。
- [x] 测试报告索引将在正式测试完成后更新，本次未生成竞争性测试结论。
