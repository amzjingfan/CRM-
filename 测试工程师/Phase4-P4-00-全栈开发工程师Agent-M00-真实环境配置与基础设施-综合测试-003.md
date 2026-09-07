# Phase 4 REAL-FS-01 真实环境配置与基础设施第三次综合测试报告

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
| 上一轮报告 | `测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-真实环境配置与基础设施-综合测试-002.md` |
| 修复实施记录 | `共享记忆文档/实施记录/Phase4-P4-00-全栈开发工程师Agent-真实环境基础设施二次测试缺陷修复-005.md` |
| 被测计划 | `全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` 的 `REAL-FS-01` |
| 测试类型 | 综合测试、修复验证、回归测试、配置测试、安全测试、数据库测试、部署测试、恢复演练检查 |
| 执行日期 | 2026-08-25 |
| 测试结论 | **不通过；`DEF-REAL-FS01-002` 已关闭，但 `DEF-REAL-FS01-001` 仍为 P1/Open，不得进入真实 OAuth 或 DeepSeek 生产联调** |

最终结论：002 号报告要求的多词消息、带业务前缀的消息/地址、`MINIO_ACCESS_KEY`、`TIKTOK_CREDENTIAL_ENCRYPTION_KEY` 和最终 `JsonFormatter` 固定样本均已修复；生产 Compose 的五类服务最小密钥矩阵、检索服务开发 `.env` 隔离和高风险开关失败关闭也已通过，`DEF-REAL-FS01-002` 可以关闭。

但独立变形测试发现，常见的未加引号冒号格式仍会绕过统一日志出口：`X-API-Key: <value>` 和 `TIKTOK_APP_SECRET: <value>` 的无价值哨兵在 `redact_log_text` 及最终 `JsonFormatter` 中均可检索到。该问题仍属于原 `DEF-REAL-FS01-001` 的“日志不得出现 API Key/平台密钥”影响范围，因此该 P1 仅为部分修复并保持 Open，REAL-FS-01 继续不通过。

工程回归无退化：专项 21 项、默认后端 495 项、隔离 PostgreSQL 503 项、001→018 与 018→017→018 迁移、前端 22 项测试及 14 个页面生产构建、锁定依赖审计、Nginx 动态 OAuth 日志、健康检查、恢复脚本和敏感凭据源码扫描均完成。

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

- 复测 002 号报告中仍 Open 的 `DEF-REAL-FS01-001/002`。
- 使用未出现在开发固定测试中的日志语法变体，验证统一日志出口，而不是只执行开发新增用例。
- 动态合并普通与 AI 生产 Profile，仅比较环境变量键、哨兵映射结果和开关状态，不输出环境变量值。
- 回归已关闭的 CORS、Nginx OAuth query、实施记录路径、后端、数据库、迁移、前端、依赖和恢复门禁。

### 2.3 未执行和结论边界

- 未提供真实 TLS 证书和目标主机，未执行公网 TLS 证书链与 SSE 穿透测试。
- 未在目标云环境核验固定出口 IP，也未配置 TikTok IP 白名单。
- 未读取、打印或使用仓库 `.env` 的真实值；所有动态配置和日志测试只使用无价值哨兵。
- 未执行真实 PostgreSQL/MinIO 数据恢复，只验证脚本语法、`WhatIf` 和错误目标拒绝。
- OAuth、真实 TikTok API/Webhook/平台写操作、DeepSeek Provider、真实模型 SSE 和五日稳定性属于 REAL-FS-02～06，不在本报告功能验收范围。

## 3. 测试环境

| 项目 | 实际环境 |
| --- | --- |
| 操作系统 | Windows，PowerShell 7.6.4，Asia/Shanghai |
| Python | 3.11.15，uv 0.12.3，锁文件解析 125 个包 |
| 前端 | Node.js 24.19.0、npm 11.17.0；生产 Compose 默认 Node 20.19.4 镜像 |
| Docker | Docker Engine 29.7.2、Docker Compose 5.3.1 |
| 数据库 | 隔离 PostgreSQL 16 + pgvector；迁移 head 为 `018_ai_observability` |
| 代码状态 | 当前目录不是 Git 仓库；按 2026-08-25 二次修复后的工作区执行，测试工程师未修改产品代码 |

## 4. 缺陷复测结论

| 缺陷 | 原优先级 | 独立复测结果 | 状态 |
| --- | --- | --- | --- |
| `DEF-REAL-FS01-001`：应用与 Nginx 日志泄漏 | P1 | 002 报告全部固定反例、Settings repr、DSN、OAuth query 和 Nginx 301/502 均通过；新增冒号格式 `X-API-Key`、`TIKTOK_APP_SECRET` 在帮助函数和最终 Formatter 中仍泄漏 | **部分修复，Open** |
| `DEF-REAL-FS01-002`：生产密钥注入和环境隔离 | P1 | 五类服务矩阵通过；检索服务无业务系统禁止键，Worker 无 DeepSeek Key，Agent Worker 无 TikTok 凭据，所有生产服务不再整体继承开发 `.env` | **关闭** |
| `DEF-REAL-FS01-003`：CORS 校验过宽 | P2 | 7 类凭据、路径、query、fragment、通配符、HTTP 和非法端口变体均被拒绝 | **保持关闭** |
| `DEF-REAL-FS01-004`：实施记录失效路径 | P3 | 本轮权威计划和最新修复记录引用路径均存在，未发现回归 | **保持关闭** |

本轮没有创建新缺陷编号。冒号格式失败是原 `DEF-REAL-FS01-001` 已定义的凭证日志泄漏在新语法下的复现，不应以新编号掩盖原缺陷仍未根治。

## 5. 测试场景与结果

### 5.1 REAL-FS-01 专项与独立日志变体

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| 开发新增专项测试 | `tests/test_real_runtime_config.py`：21 passed | 通过 |
| 002 报告多词 `message=` | 多个单词全部脱敏 | 通过 |
| 业务前缀消息/地址 | `buyer_last_message`、`delivery_address`、`customer_message`、`shipping_address` 均脱敏 | 通过 |
| Python 字典表示 | 单引号消息和地址值均脱敏 | 通过 |
| 实际配置密钥名 | 大小写 `MINIO_ACCESS_KEY`、`TIKTOK_CREDENTIAL_ENCRYPTION_KEY` 均脱敏 | 通过 |
| 带引号多词值 | 值完整脱敏，后续低敏字段仍保留 | 通过 |
| 冒号格式 API Key | `X-API-Key: <sentinel>` 在 `redact_log_text` 中仍存在 | **失败，DEF-REAL-FS01-001** |
| 冒号格式平台密钥 | `TIKTOK_APP_SECRET: <sentinel>` 在 `redact_log_text` 中仍存在 | **失败，DEF-REAL-FS01-001** |
| 最终 JSON Formatter | 上述两个冒号格式哨兵仍可检索 | **失败，DEF-REAL-FS01-001** |

失败原因：当前敏感字段正则只处理带引号的 JSON `key: value` 和文本 `key=value`，未覆盖 HTTP Header、诊断文本和部分第三方异常常用的未加引号 `key: value` 格式。

### 5.2 Compose 环境隔离和最小权限

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| 普通生产 Profile | 8 个服务，配置解析通过 | 通过 |
| AI 生产 Profile | 10 个服务，配置解析通过 | 通过 |
| 必填配置缺失 | `DATABASE_URL` 置空时以非零状态安全失败 | 通过 |
| Worker 最小权限 | 有公共和 TikTok 平台域，无 `DEEPSEEK_API_KEY` | 通过 |
| Agent Worker 最小权限 | 有公共和 DeepSeek 模型域，无 5 个 TikTok 凭据键 | 通过 |
| 检索模型服务隔离 | 仅有本地模型配置和自身 Token；数据库、Redis、MinIO、JWT、TikTok、DeepSeek 禁止键为 0 | 通过 |
| 所需配置存在性 | 五类服务的职责内必需键无缺失 | 通过 |
| 高风险开关 | backend、worker、jobs、agent-worker 共 40/40 项为 `false` | 通过 |

动态检查将 Compose 输出保存在进程内，仅输出服务数量、违规键名和开关布尔结果；没有打印任何配置值。

### 5.3 CORS、Nginx 与健康检查

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| CORS 独立无效样本 | 7/7 被生产配置拒绝 | 通过 |
| Nginx HTTP OAuth callback | 301；日志无 code/state 哨兵 | 通过 |
| Nginx 上游失败 OAuth callback | 502；日志无 code/state 哨兵 | 通过 |
| `/v1/health` | HTTP 200，仅返回 `status/version` | 通过 |
| `/v1/health/ready` 依赖不可用 | HTTP 503，只有统一响应与四个组件的 `ok/disabled/error` 状态，不含底层异常或连接信息 | 通过 |

### 5.4 后端、数据库、迁移与前端回归

| 测试项 | 实际结果 | 状态 |
| --- | --- | --- |
| `uv lock --check` | 125 个包解析成功 | 通过 |
| Ruff | All checks passed | 通过 |
| Ruff format | 181 files already formatted | 通过 |
| mypy | 150 个源文件无问题 | 通过 |
| 后端默认回归 | 495 passed、8 skipped、2 个既有警告 | 通过 |
| 隔离 PostgreSQL 全量回归 | 503 passed、0 skipped、2 个既有警告 | 通过 |
| 空库迁移 | 001→018 | 通过 |
| 最新迁移回滚恢复 | 018→017→018，最终 `018_ai_observability (head)` | 通过 |
| 前端 lint/typecheck | 无错误 | 通过 |
| 前端自动化 | 22 passed | 通过 |
| 前端生产构建 | 14 个静态页面构建成功 | 通过 |
| 锁定依赖审计 | 124 个包无已知漏洞或不良状态 | 通过 |
| 高风险凭据源码模式扫描 | 277 个文件，0 命中 | 通过 |

保留两个既有非阻断警告：Starlette TestClient/httpx 弃用提示、passlib 读取 argon2 版本弃用提示。默认跳过的 8 项 PostgreSQL 用例已在隔离数据库回归中覆盖。

### 5.5 恢复门禁与清理

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| 四个备份/恢复脚本 AST | 0 个语法错误 | 通过 |
| PostgreSQL 恢复 `WhatIf` | 完成且未执行恢复 | 通过 |
| MinIO 恢复 `WhatIf` | 完成且未执行恢复 | 通过 |
| 错误 PostgreSQL 目标确认 | 被拒绝 | 通过 |
| 临时容器清理 | `crm-real-fs01-retest3-nginx` 和 `crm-postgres-test-1` 均不存在 | 通过 |
| 测试缓存清理 | 本轮 5 个 pytest/uv 临时目录均已删除 | 通过 |

## 6. 未关闭缺陷

### DEF-REAL-FS01-001：统一日志出口仍泄漏未加引号冒号格式凭证

| 项目 | 内容 |
| --- | --- |
| 优先级 | P1 |
| 类型 | 安全、日志脱敏、生产凭证保护 |
| 影响范围 | 应用统一日志出口、第三方库日志、HTTP Header/诊断文本、TikTok 与 DeepSeek 凭证注入门禁 |
| 是否阻断 | 是；阻断 REAL-FS-01、REAL-FS-02 和 REAL-FS-05 真实凭证联调 |
| 建议负责 Agent | 全栈开发工程师Agent |

复现步骤：

1. 使用无价值哨兵构造 `X-API-Key: <sentinel>` 或 `TIKTOK_APP_SECRET: <sentinel>` 文本。
2. 调用 `redact_log_text`，检查输出是否仍包含哨兵。
3. 将同一文本放入 `logging.LogRecord` 并经 `JsonFormatter().format(record)` 输出。
4. 检查最终 JSON 日志是否仍包含哨兵。

实际结果：两类哨兵在帮助函数和最终 Formatter 中均未被替换。

预期结果：统一日志出口应对同一敏感字段集合同时覆盖 JSON、`key=value` 和常见未加引号 `key: value` 表示；API Key、平台密钥和客户隐私不得因分隔符变化进入日志。

最小修复建议：复用现有 `SENSITIVE_FIELD_NAME` 和安全值边界，增加未加引号冒号键值规则，并把本报告两个独立变体加入最终 Formatter 回归测试。无需引入新的日志依赖或第二套脱敏器。

## 7. 文档状态观察

`OBS-REAL-FS01-001` 仍未处理：`ARCH-001-SYS-v1.4`、`ADR-004-REAL` 和生产放行检查表仍把 `DEF-P4-AI-008/009` 描述为未关闭或 G4 失败，而当前权威 M04 014 号报告已确认 `DEF-P4-AI-001～012` 全部 Closed。该观察归架构师 Agent，不影响本报告对 `DEF-REAL-FS01-001` 的 P1 判定，也不代表真实模型生产质量已经通过。

## 8. 验收建议

- REAL-FS-01 继续判定为不通过。
- `DEF-REAL-FS01-002` 关闭；`DEF-REAL-FS01-003/004` 保持关闭。
- `DEF-REAL-FS01-001` 关闭前，不注入真实 TikTok/DeepSeek 凭证，不进入 REAL-FS-02 OAuth 或 REAL-FS-05 DeepSeek 生产联调。
- 下一轮只需先修复并独立复测冒号格式日志出口，再执行专项、Compose 最小权限、Nginx OAuth 动态日志和完整工程回归；无需重复修改已通过的 Compose 密钥矩阵。
- 即使该 P1 关闭，真实 TLS、固定出口 IP、不可变发布基线、凭证轮换和真实备份恢复仍属于后续生产门禁，不等于最终生产放行。

## 9. 执行证据摘要

主要命令：

```text
uv run pytest tests/test_real_runtime_config.py -q
独立日志语法变体脚本（只输出失败标签）
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

清理说明：测试只使用隔离 PostgreSQL、一次性 Nginx 容器和无价值哨兵；精确命名的临时容器及本轮缓存均已删除。测试工程师仅新增本报告并更新测试报告索引，未修改产品代码。
