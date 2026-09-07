# Phase 4 REAL-FS-01 真实环境配置与基础设施修复后综合测试报告

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
| 原始缺陷报告 | `测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-真实环境配置与基础设施-综合测试-001.md` |
| 修复实施记录 | `共享记忆文档/实施记录/Phase4-P4-00-全栈开发工程师Agent-真实环境基础设施测试缺陷修复-004.md` |
| 被测计划 | `全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` 的 `REAL-FS-01` |
| 测试类型 | 综合测试、修复验证、回归测试、配置测试、安全测试、数据库测试、部署测试、恢复演练检查 |
| 执行日期 | 2026-08-25 |
| 测试结论 | **不通过；两个 P1 仅部分修复，仍不得进入真实 OAuth 或 DeepSeek 生产联调** |

最终结论：`DEF-REAL-FS01-003` 和 `DEF-REAL-FS01-004` 已关闭；`DEF-REAL-FS01-001`、`DEF-REAL-FS01-002` 的原始固定样本和部分主路径已经修复，但独立变形与最小权限测试仍发现客户消息/地址及实际密钥字段可绕过日志脱敏，生产 AI Profile 的检索模型服务仍继承开发 `.env` 中的 DeepSeek Key，且 Agent/集成 Worker 获得超出职责所需的跨域凭据。因此两个 P1 均为“部分修复、Open”，REAL-FS-01 不满足日志无凭证、环境隔离和最小权限要求。

工程回归未退化：专项 18 项、默认后端 492 项、隔离 PostgreSQL 500 项、001→018 与 018→017→018 迁移、前端 22 项测试及 14 个页面生产构建、依赖审计、Nginx 动态 OAuth 日志、健康检查和恢复脚本门禁均完成。

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

- 独立复测 `DEF-REAL-FS01-001～004`，不以开发新增固定测试代替变形验证。
- 检查应用日志、Settings 调试表示、Nginx 301/502、OAuth query 和连接串脱敏。
- 检查生产 Compose 主机/CI 显式注入、开发 `.env` 隔离、服务最小权限和高风险开关。
- 检查 CORS Origin 的凭据、路径、query、fragment、通配符和端口边界。
- 回归后端、数据库、迁移、前端、健康检查、依赖和恢复脚本。

### 2.3 未执行和结论边界

- 未提供真实域名证书和目标主机，未执行真实 TLS 证书链、公网访问和 SSE 穿透。
- 未在目标云环境核验固定出口 IP，未配置 TikTok IP 白名单。
- 未取得或使用真实 TikTok、DeepSeek 凭证；测试只使用无价值哨兵，报告不记录仓库 `.env` 内容。
- 未执行真实 PostgreSQL/MinIO 数据恢复，仅验证脚本语法、`WhatIf` 和目标确认门禁。
- OAuth、真实 TikTok API/Webhook/平台写操作、DeepSeek Provider 和真实模型 SSE 属于 REAL-FS-02～05，不在本报告功能验收范围。

## 3. 测试环境

| 项目 | 实际环境 |
| --- | --- |
| 操作系统 | Windows，PowerShell 7.6.4，Asia/Shanghai |
| Python | 3.11.15，uv 0.12.3，锁文件解析 125 个包 |
| 前端 | Node.js 24.19.0、npm 11.17.0；生产 Compose 默认 Node 20.19.4 镜像 |
| Docker | Docker Engine 29.7.2、Docker Compose 5.3.1 |
| 数据库 | PostgreSQL 16 + pgvector；迁移 head 为 `018_ai_observability` |
| 代码状态 | 当前目录不是 Git 仓库；按 2026-08-25 修复后工作区执行，未修改产品代码 |

## 4. 缺陷复测结论

| 缺陷 | 原优先级 | 独立复测结果 | 状态 |
| --- | --- | --- | --- |
| `DEF-REAL-FS01-001`：应用与 Nginx 日志泄漏 | P1 | 原 `app_secret/client_secret/message` 单词样本、Settings repr、DSN、OAuth query 和 Nginx 301/502 已通过；但多词未引号 `message`、`customer_message`、`shipping_address`、`MINIO_ACCESS_KEY`、`TIKTOK_CREDENTIAL_ENCRYPTION_KEY` 仍泄漏 | **部分修复，Open** |
| `DEF-REAL-FS01-002`：生产密钥注入和环境隔离 | P1 | backend/worker/jobs/agent-worker 显式映射和高风险开关关闭通过；但 `retrieval-model-service` 仍继承开发 `.env` 并获得 DeepSeek Key，Agent Worker 同时获得 5 个 TikTok 凭据，集成 Worker 获得 DeepSeek Key | **部分修复，Open** |
| `DEF-REAL-FS01-003`：CORS 校验过宽 | P2 | 凭据、路径、query、fragment、通配符、HTTP 和非法端口均被拒绝；多个 HTTPS Origin 和可选端口被接受 | **关闭** |
| `DEF-REAL-FS01-004`：实施记录失效路径 | P3 | 两个旧路径已移除，当前记录引用的 PRD 和接口文档均存在 | **关闭** |

本轮没有创建新缺陷编号；新失败样本均属于原 `DEF-REAL-FS01-001/002` 的既定影响范围。

## 5. 测试场景与结果

### 5.1 REAL-FS-01 专项和日志安全

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| 开发新增专项测试 | `tests/test_real_runtime_config.py` 18 passed | 通过 |
| 原密钥名样本 | `app_secret`、`client_secret`、`tiktok_app_secret` 已脱敏 | 通过 |
| OAuth query | 大小写 `code/state` 已脱敏 | 通过 |
| DSN 密码 | PostgreSQL/Redis URL 密码不进入输出 | 通过 |
| Settings repr | JWT、数据库 URL、Redis URL、MinIO、Shopee、Amazon 密钥哨兵均隐藏 | 通过 |
| 普通 `message=` 单词值 | 单词值被脱敏 | 通过 |
| 未引号多词 `message=` | 仅第一个词被替换，后续两个哨兵仍存在 | **失败，DEF-REAL-FS01-001** |
| 前缀业务字段 | JSON `customer_message`、`shipping_address` 正文仍存在 | **失败，DEF-REAL-FS01-001** |
| 实际配置密钥名 | `minio_access_key`、`tiktok_credential_encryption_key` 值仍存在 | **失败，DEF-REAL-FS01-001** |
| JsonFormatter 出口 | 上述失败样本经最终 JSON Formatter 后仍可检索到哨兵 | **失败，DEF-REAL-FS01-001** |

失败根因：当前可选字段前缀只作用于 `api_key/secret/password/credential` 这一组，不作用于 `message/address`；`access_key` 和 `credential_encryption_key` 不是已覆盖后缀；未引号 key-value 值在第一个空白处结束匹配。

### 5.2 CORS 与生产配置

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| 生产禁用 Mock | Mock 开关为 true 时启动校验拒绝 | 通过 |
| 生产 Cookie、弱密钥和开发数据库凭据 | 非安全值被拒绝 | 通过 |
| 公网基址和出口 IP | 非 HTTPS、无主机、缺失或非法 IP 被拒绝 | 通过 |
| CORS 凭据 | `https://user:password@host` 被拒绝 | 通过 |
| CORS path/query/fragment | 全部被拒绝 | 通过 |
| CORS 通配符、HTTP、非法端口 | 全部被拒绝 | 通过 |
| 合法多来源与端口 | 两个明确 HTTPS Origin 正确解析 | 通过 |
| Compose 必填配置 | 将必填变量置空后配置解析以非零状态安全失败 | 通过 |

### 5.3 Compose 显式注入、环境隔离和最小权限

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| 普通 Profile 服务数 | 8 个服务 | 通过 |
| 普通 Profile 显式映射 | backend/worker/jobs 共 33/33 个契约值采用主机/CI 哨兵 | 通过 |
| 普通 Profile 开关关闭 | 3 个应用服务共 30/30 个高风险开关为 false | 通过 |
| AI Profile 服务数 | 10 个服务 | 通过 |
| AI Profile 显式映射 | backend/worker/jobs/agent-worker 共 44/44 个契约值采用主机/CI 哨兵 | 通过 |
| AI Profile 开关关闭 | 4 个应用服务共 40/40 个高风险开关为 false | 通过 |
| 四个应用服务 env_file reset | backend/worker/jobs/agent-worker 不再整体继承基础 `.env` | 通过 |
| 检索模型服务环境隔离 | `retrieval-model-service` 仍保留基础 `env_file: .env`；在未向当前进程注入 DeepSeek Key 时，合并结果仍出现 `DEEPSEEK_API_KEY` 键 | **失败，DEF-REAL-FS01-002** |
| Agent 最小权限 | `agent-worker` 获得 TikTok App Key/Secret、OAuth URI、Webhook Secret、凭证加密 Key 共 5 项 | **失败，DEF-REAL-FS01-002** |
| 集成 Worker 最小权限 | `worker` 获得其职责不需要的 DeepSeek API Key | **失败，DEF-REAL-FS01-002** |

上述检查只比较键名、存在性和哨兵是否匹配，没有输出任何环境变量真实值。问题违反 ADR 中“Agent 不持有平台凭证”和各环境/服务密钥隔离边界，并扩大任一容器被利用后的凭据暴露面。

### 5.4 Nginx 与运行态

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| Nginx 配置语法 | 一次性 `nginx:1.27.5-alpine` 容器正常启动 | 通过 |
| HTTP OAuth callback | 301；访问日志只含规范化 URI，不含 code/state | 通过 |
| 上游失败 OAuth callback | 502；访问/错误日志均不含 code/state | 通过 |
| SSE 代理 | buffering/cache 关闭，读取超时 120 秒 | 通过（静态与语法） |
| `/v1/health` | HTTP 200，`code=0`，只含 status/version | 通过 |
| `/v1/health/ready` | HTTP 200，`status=ready`，只含组件级状态 | 通过 |

Nginx 子项已经满足本轮日志复测要求；`DEF-REAL-FS01-001` 保持 Open 的原因仅是应用统一日志出口仍存在上述变形泄漏。

### 5.5 工程质量、数据库与前端回归

| 测试项 | 实际结果 | 状态 |
| --- | --- | --- |
| `uv lock --check` | 125 个包解析成功 | 通过 |
| Ruff | All checks passed | 通过 |
| Ruff format | 181 files already formatted | 通过 |
| mypy | 150 个源文件无问题 | 通过 |
| 后端默认回归 | 492 passed、8 skipped、2 个既有警告 | 通过 |
| 隔离 PostgreSQL 全量回归 | 500 passed、0 skipped、2 个既有警告 | 通过 |
| 空库迁移 | 001→018 | 通过 |
| 最新迁移回滚恢复 | 018→017→018，最终 `018_ai_observability (head)` | 通过 |
| 前端 lint/typecheck | 无错误 | 通过 |
| 前端自动化 | 22 passed | 通过 |
| 前端生产构建 | 14 个静态页面构建成功 | 通过 |
| 锁定依赖审计 | 124 个包无已知漏洞或不良状态 | 通过 |
| 常见高风险凭据模式扫描 | 277 个源码/配置/文档文件，0 命中 | 通过 |

保留两个既有非阻断警告：Starlette TestClient/httpx 弃用提示、passlib 读取 argon2 版本弃用提示。默认跳过的 8 项 PostgreSQL 用例已经在隔离数据库回归中覆盖。

### 5.6 恢复与清理

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| 四个备份/恢复脚本 AST | 0 个语法错误 | 通过 |
| PostgreSQL 恢复 `WhatIf` | 完成且未执行恢复 | 通过 |
| MinIO 恢复 `WhatIf` | 完成且未执行恢复 | 通过 |
| 错误 PostgreSQL 目标确认 | 被拒绝 | 通过 |
| 临时容器清理 | Nginx 和 PostgreSQL 测试容器均已删除 | 通过 |
| 测试缓存清理 | 本轮 5 个项目内 pytest/uv 临时目录均已删除 | 通过 |

## 6. 未关闭缺陷的复现与建议

### 6.1 DEF-REAL-FS01-001：日志脱敏仍可被常见字段变体绕过

复现步骤：

1. 使用无价值哨兵调用 `redact_log_text` 或 `JsonFormatter`。
2. 分别输入未引号多词 `message=`、JSON `customer_message`、JSON `shipping_address`、`minio_access_key` 和 `tiktok_credential_encryption_key`。
3. 检查最终 JSON 日志中是否仍包含第二个/第三个词、客户正文、地址和密钥哨兵。

实际结果：五类样本均存在未脱敏内容。原固定样本、Settings repr 和 Nginx 路径已通过，因此状态为部分修复。

预期结果：统一日志出口应覆盖实际配置字段名和带业务前缀的消息/地址字段；包含空格的客户正文不能只隐藏首词。

建议修复：

- 使用明确的敏感键集合加后缀规则，覆盖 `*_message`、`*_address`、`*_access_key`、`*_credential_encryption_key`。
- 对 key-value 文本规定可靠边界；无法确定值边界时，不记录原文本或从命中敏感键处截断到明确分隔符。
- 增加本报告五类变形样本及最终 `JsonFormatter` 测试，不只测试帮助函数。

### 6.2 DEF-REAL-FS01-002：生产密钥仍跨服务扩散并残留开发 `.env` 注入

复现步骤：

1. 使用安全哨兵和 `--profile ai` 合并基础、生产 Compose。
2. 不向当前进程设置 DeepSeek Key，只检查 `retrieval-model-service.environment` 的键名。
3. 检查 `agent-worker` 是否拥有 TikTok 凭据键，检查 `worker` 是否拥有 DeepSeek Key。

实际结果：检索模型服务因基础 `env_file: .env` 获得 DeepSeek Key；Agent Worker 获得 5 个 TikTok 凭据；集成 Worker 获得 DeepSeek Key。显式主机/CI映射本身已经工作，高风险开关保持关闭。

预期结果：生产所有服务均不得整体继承开发 `.env`；每个容器只接收职责必需的密钥。Agent Worker 不持有 TikTok 凭据，检索模型服务不持有 TikTok/DeepSeek/JWT/数据库/MinIO 密钥。

建议修复：

- 对 `retrieval-model-service` 同样执行生产 `env_file: !reset []`，只显式注入检索模型 Token 和模型运行配置。
- 拆分公共非敏感运行环境、平台集成密钥和模型密钥三个 Compose anchor，不向所有进程展开同一全集。
- 明确 backend、integration worker、jobs、agent worker、retrieval model service 的最小密钥矩阵，并增加键存在性测试。

## 7. 文档状态观察

`OBS-REAL-FS01-001` 仍未处理：`ADR-004`、`ARCH-001-SYS-v1.4` 和生产放行检查表仍将 `DEF-P4-AI-008/009` 描述为未关闭，而当前权威 M04 014 号报告已确认 `DEF-P4-AI-001～012` 全部 Closed。该观察归架构师/共享记忆文档 Agent，不改变本轮两个 P1 的产品结论。

## 8. 验收建议

- REAL-FS-01 继续判定为不通过。
- `DEF-REAL-FS01-001/002` 关闭前，不注入真实 TikTok/DeepSeek 凭据，不进入 REAL-FS-02 OAuth 或 REAL-FS-05 DeepSeek 生产联调。
- `DEF-REAL-FS01-003/004` 可以关闭，不要求重复修改。
- 下一轮至少复测本报告全部日志变形样本、五类服务最小密钥矩阵、AI Profile 开发 `.env` 隔离、Nginx OAuth 动态日志和完整工程回归。
- 真实 TLS、固定出口 IP、凭据轮换和真实备份恢复仍为后续生产门禁；即使本轮两个 P1 关闭，也不等于生产放行。

## 9. 执行证据摘要

主要命令：

```text
pytest tests/test_real_runtime_config.py -q
uv lock --check
ruff check app scripts tests
ruff format --check app scripts tests
mypy app scripts
pytest -q -rs --basetemp=<project-local-temp>
scripts/run-postgres-integration-tests.ps1
alembic upgrade head / downgrade 017_phase4_metrics / upgrade head
uv audit --locked
npm run lint
npm run typecheck
npm run test
npm run build
docker-compose -f docker-compose.yml -f docker-compose.prod.yml config --format json
docker-compose --profile ai -f docker-compose.yml -f docker-compose.prod.yml config --format json
nginx:1.27.5-alpine 动态 301/502 OAuth 日志测试
restore-postgres.ps1 -WhatIf
restore-minio.ps1 -WhatIf
```

清理说明：所有测试仅使用隔离数据库和无价值哨兵；临时容器及本轮缓存均已精确删除。测试工程师只新增本报告并更新测试报告索引，未修改产品代码。
