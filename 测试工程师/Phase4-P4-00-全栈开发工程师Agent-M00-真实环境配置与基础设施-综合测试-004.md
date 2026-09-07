# Phase 4 REAL-FS-01 真实环境配置与基础设施第四次综合测试报告

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-FS-01` |
| 模块编号 | M00（真实环境基础设施跨模块基线） |
| 模块名称 | 真实环境配置与基础设施 |
| 被测主责 Agent | 全栈开发工程师Agent |
| 被测协作 Agent | 架构师Agent、AIAgent开发工程师Agent |
| 测试执行 Agent | 测试工程师Agent |
| 上一轮报告 | `测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-真实环境配置与基础设施-综合测试-003.md` |
| 关联实施记录 | `共享记忆文档/实施记录/Phase4-P4-00-全栈开发工程师Agent-真实环境基础设施第三次测试缺陷修复-006.md` |
| 被测计划 | `全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` 的 `REAL-FS-01` |
| 测试类型 | 综合测试、修复验证、回归测试、配置测试、安全测试、数据库测试、部署测试、恢复演练检查 |
| 执行日期 | 2026-08-25 |
| 测试结论 | **有条件通过 REAL-FS-01 当前工程范围；`DEF-REAL-FS01-001～004` 全部关闭，无新增 P0/P1/P2** |

最终结论：003 号报告发现的未加引号冒号格式凭证泄漏已完成根因修复。开发专项 23 项通过；测试工程师新增 10 类未固化敏感变体在 `redact_log_text`、最终 `JsonFormatter` 和真实根 Logger 出口均无泄漏，6 类普通状态字段也没有被误脱敏。因此 `DEF-REAL-FS01-001` 关闭，既有 `DEF-REAL-FS01-002/003/004` 保持关闭。

工程回归无退化：默认后端 497 项、隔离 PostgreSQL 505 项、001→018 与 018→017→018 迁移、前端 22 项测试及 14 个页面生产构建、普通/AI 生产 Profile、Nginx 动态 OAuth 日志、健康检查、依赖审计、恢复脚本和源码凭据扫描全部通过。

本报告仅验收 REAL-FS-01 已交付的工程配置和安全基线。真实 TLS 证书链、目标主机固定出口 IP、不可变发布基线、真实密钥注入与轮换、真实备份恢复仍未在目标环境验证，因此本结论不等于生产放行，也不允许打开真实平台、模型、营销或自动回复开关。

## 2. 测试依据、范围与边界

### 2.1 测试依据

- `共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`。
- `共享记忆文档/智能客服平台 — 管理端接口文档.md`。
- `共享记忆文档/开发任务拆解（按人天分配）.md`。
- `共享记忆文档/MVP范围与验收标准.md`。
- `共享记忆文档/代码编写手册.md`。
- `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`。
- `架构师/ARCH-001-SYS-系统总体架构设计-v1.4.md`。
- `架构师/验收-001-CROSS-真实环境生产放行检查表-v1.0.md`。
- `全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md`。
- 项目全部适用的 `AGENTS.md`、实施记录规范和测试报告命名规范。

### 2.2 本轮重点

- 独立复测 `DEF-REAL-FS01-001` 的冒号格式日志凭证泄漏。
- 增加大小写、空白、制表符、多词、折行、点号前缀、Cookie Token、Basic/Bearer 等未固化变体。
- 增加普通状态字段负向控制，验证修复不会把所有冒号文本无差别抹除。
- 通过真实 Logger 配置验证第三方 Logger 向统一 JSON 出口传播后的最终结果。
- 回归 Compose 密钥矩阵、开发 `.env` 隔离、CORS、Nginx、健康检查、数据库、迁移、前端、依赖与恢复门禁。

### 2.3 未执行和结论边界

- 未提供真实 TLS 证书和目标部署主机，未执行公网证书链、安全组和 SSE 穿透验证。
- 未在目标云环境核验固定出口 IP，也未配置 TikTok IP 白名单。
- 未读取、打印或使用仓库 `.env` 的真实值；动态配置和日志测试只使用无价值哨兵。
- 未执行真实 PostgreSQL/MinIO 数据恢复，只验证脚本语法、`WhatIf` 和错误目标拒绝。
- 未执行 TikTok OAuth、真实 API/Webhook、平台写操作、DeepSeek 真实调用、50 授权客户端 SSE 和五日稳定性；这些属于 REAL-FS-02～06 和生产 G0～G8 门禁。

## 3. 测试环境

| 项目 | 实际环境 |
| --- | --- |
| 操作系统 | Windows，PowerShell 7.6.4，Asia/Shanghai |
| Python | 3.11.15，uv 0.12.3，锁文件解析 125 个包 |
| 前端 | Node.js 24.19.0、npm 11.17.0；生产 Compose 默认 Node 20.19.4 镜像 |
| Docker | Docker Engine 29.7.2、Docker Compose 5.3.1 |
| 数据库 | 隔离 PostgreSQL 16 + pgvector；迁移 head 为 `018_ai_observability` |
| 代码状态 | 当前目录不是 Git 仓库；按 2026-08-25 第三次缺陷修复后的工作区执行，测试工程师未修改产品代码 |

## 4. 缺陷复测结论

| 缺陷 | 原优先级 | 本轮独立复测结果 | 状态 |
| --- | --- | --- | --- |
| `DEF-REAL-FS01-001`：应用与 Nginx 日志泄漏 | P1 | 冒号格式固定反例、10 类独立敏感变体、6 类负向控制、真实 Logger、OAuth query、Nginx 301/502 均通过 | **关闭** |
| `DEF-REAL-FS01-002`：生产密钥注入和环境隔离 | P1 | 普通/AI Profile、五类服务矩阵、检索服务隔离和 40 个高风险开关无回归 | **保持关闭** |
| `DEF-REAL-FS01-003`：CORS 校验过宽 | P2 | 7 类非法 Origin 全部被拒绝 | **保持关闭** |
| `DEF-REAL-FS01-004`：实施记录失效路径 | P3 | 计划、修复记录和报告引用路径存在 | **保持关闭** |

本轮未发现新的 P0/P1/P2/P3 产品缺陷。

## 5. 测试场景与结果

### 5.1 日志安全专项

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| 开发专项测试 | `tests/test_real_runtime_config.py`：23 passed | 通过 |
| 003 报告冒号固定反例 | `X-API-Key`、`TIKTOK_APP_SECRET` 在帮助函数和 Formatter 中均脱敏 | 通过 |
| 大小写和空白 | 小写 Header、冒号两侧空格和制表符均脱敏 | 通过 |
| 多词与折行值 | 多词平台密钥和折行 Access Key 均不泄漏 | 通过 |
| 鉴权 Header | `Authorization: Basic`、`Proxy-Authorization: Bearer` 均脱敏 | 通过 |
| 业务前缀字段 | `customer_last_message`、`shipping-address` 均脱敏 | 通过 |
| 点号前缀 Header | `headers.X-API-Key` 仍能识别并脱敏 | 通过 |
| Cookie Token | `crm_access_token=...` 不进入输出 | 通过 |
| 最终 Formatter | 10/10 独立敏感变体均无哨兵 | 通过 |
| 普通字段负向控制 | `status`、`port`、`timestamp`、普通 Secret 单词、`content_type`、`address_count` 共 6/6 保持原值 | 通过 |
| 真实 Logger 出口 | 第三方 Logger 输出单行 JSON，哨兵消失，低敏 event/trace 保留 | 通过 |

修复只扩展已有敏感字段规则的文本分隔符，没有引入第二套脱敏器或新的依赖，符合统一出口和最小变更原则。

### 5.2 Compose、配置和服务最小权限

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| 普通生产 Profile | 8 个服务，配置解析通过 | 通过 |
| AI 生产 Profile | 10 个服务，配置解析通过 | 通过 |
| 必填配置缺失 | `DATABASE_URL` 置空时配置以非零状态安全失败 | 通过 |
| Worker 最小权限 | 无 `DEEPSEEK_API_KEY` | 通过 |
| Agent Worker 最小权限 | 无 TikTok App/OAuth/Webhook/加密凭据 | 通过 |
| 检索模型服务隔离 | 数据库、Redis、MinIO、JWT、TikTok、DeepSeek 禁止键为 0 | 通过 |
| 职责内必需键 | 五类服务无缺失 | 通过 |
| 高风险开关 | 四个应用服务共 40/40 项为 `false` | 通过 |

Compose 输出仅在进程内解析，测试证据只记录服务数量、违规键名和布尔状态，没有打印配置值。

### 5.3 CORS、Nginx 和健康检查

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| CORS 非法来源 | 凭据、路径、query、fragment、通配符、HTTP、非法端口共 7/7 被拒绝 | 通过 |
| Nginx HTTP OAuth callback | 301，日志无 code/state 哨兵 | 通过 |
| Nginx 上游失败 OAuth callback | 502，日志无 code/state 哨兵 | 通过 |
| `/v1/health` | HTTP 200，仅含 `status/version` | 通过 |
| `/v1/health/ready` 依赖不可用 | HTTP 503，只返回统一结构和四个组件状态，不含连接信息或异常正文 | 通过 |

### 5.4 后端、数据库、迁移和前端回归

| 测试项 | 实际结果 | 状态 |
| --- | --- | --- |
| `uv lock --check` | 125 个包解析成功 | 通过 |
| Ruff | All checks passed | 通过 |
| Ruff format | 181 files already formatted | 通过 |
| mypy | 150 个源文件无问题 | 通过 |
| 后端默认回归 | 497 passed、8 skipped、2 个既有警告 | 通过 |
| 隔离 PostgreSQL 全量回归 | 505 passed、0 skipped、2 个既有警告 | 通过 |
| 空库迁移 | 001→018 | 通过 |
| 最新迁移回滚恢复 | 018→017→018，最终 `018_ai_observability (head)` | 通过 |
| 前端 lint/typecheck | 无错误 | 通过 |
| 前端自动化 | 22 passed | 通过 |
| 前端生产构建 | 14 个静态页面构建成功 | 通过 |
| 锁定依赖审计 | 124 个包无已知漏洞或不良状态 | 通过 |
| 高风险凭据源码模式扫描 | 277 个文件，0 命中 | 通过 |

两个既有非阻断警告未变化：Starlette TestClient/httpx 弃用提示、passlib 读取 argon2 版本弃用提示。默认跳过的 8 项 PostgreSQL 用例已在隔离数据库回归中覆盖。

### 5.5 恢复门禁与清理

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| 四个备份/恢复脚本 AST | 0 个语法错误 | 通过 |
| PostgreSQL 恢复 `WhatIf` | 完成且未执行恢复 | 通过 |
| MinIO 恢复 `WhatIf` | 完成且未执行恢复 | 通过 |
| 错误 PostgreSQL 目标确认 | 被拒绝 | 通过 |
| 临时容器 | `crm-real-fs01-retest4-nginx`、`crm-postgres-test-1` 均已删除 | 通过 |
| 测试缓存 | 本轮 5 个 pytest/uv 临时目录均已删除 | 通过 |

## 6. 缺陷与观察

### 6.1 产品缺陷

本轮无未关闭产品缺陷；`DEF-REAL-FS01-001～004` 全部 Closed。

### 6.2 OBS-REAL-FS01-001：架构文档状态仍滞后

| 项目 | 内容 |
| --- | --- |
| 优先级 | P3 |
| 类型 | 文档一致性、生产门禁状态 |
| 是否阻断 REAL-FS-01 工程验收 | 否 |
| 建议负责 Agent | 架构师Agent、共享记忆文档Agent |

`ARCH-001-SYS-v1.4`、`ADR-004-REAL` 和生产放行检查表仍把 `DEF-P4-AI-008/009` 描述为 Open 或 G4 失败；当前权威 M04 014 号报告已确认 `DEF-P4-AI-001～012` 全部 Closed。应同步为“确定性工程缺陷已关闭，真实模型质量门禁仍未执行”，避免把工程缺陷状态与生产模型验收状态混为一谈。

该观察不影响 REAL-FS-01 当前工程验收，但最终生产放行前必须修正。

## 7. 验收结论与后续门禁

- REAL-FS-01 当前工程范围有条件通过。
- `DEF-REAL-FS01-001～004` 全部关闭，本轮无新增 P0/P1/P2。
- 可以进入 REAL-FS-02/05 的代码实施和不使用真实凭证的受控联调准备。
- 实际注入真实 TikTok/DeepSeek 凭证和执行真实店铺 OAuth 前，必须完成目标环境 TLS、固定出口 IP、仓库外密钥注入、不可变归档/版本哈希和凭证轮换方案检查。
- 所有 `REAL_TIKTOK_*`、`LLM_ENABLED`、`LLM_LIVE_EVAL`、`AI_TRANSLATION_ENABLED`、`AI_MARKETING_ENABLED` 和 `AUTO_REPLY_ENABLED` 继续保持 `false`，后续按架构放行顺序逐项开启。
- 本报告不放行真实平台写操作、公开 AI 回复、AI 营销、50 授权客户端 SSE、五日稳定性或生产发布。

## 8. 执行证据摘要

主要命令：

```text
uv run pytest tests/test_real_runtime_config.py -q
独立日志敏感变体、负向控制和真实 Logger 出口脚本
uv lock --check
uv run ruff check app scripts tests
uv run ruff format --check app scripts tests
uv run mypy app scripts
uv run pytest -q -rs --basetemp=<project-local-temp>
scripts/run-postgres-integration-tests.ps1
alembic upgrade head / downgrade 017_phase4_metrics / upgrade head
uv audit --locked
npm run lint
npm run typecheck
npm run test
npm run build
docker-compose -f docker-compose.yml -f docker-compose.prod.yml config --format json
docker-compose --profile ai -f docker-compose.yml -f docker-compose.ai.yml -f docker-compose.prod.yml config --format json
nginx:1.27.5-alpine 动态 301/502 OAuth 日志测试
restore-postgres.ps1 -WhatIf
restore-minio.ps1 -WhatIf
```

清理说明：本轮只使用隔离 PostgreSQL、一次性 Nginx 容器和无价值哨兵；临时容器与项目内测试缓存均已精确清理。测试工程师仅新增本报告并更新测试报告索引，未修改产品代码。
