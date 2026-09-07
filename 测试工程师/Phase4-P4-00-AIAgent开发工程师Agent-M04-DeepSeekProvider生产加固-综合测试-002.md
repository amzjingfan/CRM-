# Phase 4 REAL-AI-01 M04 DeepSeek Provider 生产加固修复后综合复测报告

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-AI-01` |
| 模块编号 | M04 |
| 模块名称 | DeepSeek Provider 生产加固 |
| 被测主责 Agent | AIAgent开发工程师Agent |
| 被测协作 Agent | 架构师Agent、全栈开发工程师Agent |
| 测试执行 Agent | 测试工程师Agent |
| 关联实施记录 | `共享记忆文档/实施记录/Phase4-P4-00-AIAgent开发工程师Agent-DeepSeekProvider测试缺陷修复-002.md` |
| 原测试报告 | `测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-DeepSeekProvider生产加固-综合测试-001.md` |
| 历史回归依据 | `测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-回复翻译营销与评测闭环-综合测试-002.md` 及后续至 014 号报告 |
| 测试类型 | 综合测试、修复验证、真实模型冒烟、回归测试、数据库测试、安全测试、代码审查 |
| 执行日期 | 2026-08-26 |
| 测试结论 | **不通过 REAL-AI-01 独立验收；工程回归通过，但 `DEF-REAL-AI01-001/002` 均仅部分修复，继续保持 P1/Open** |

用户指定的“回复翻译营销与评测闭环-综合测试-002”属于历史 M04 回归依据；本轮 REAL-AI-01 的直接缺陷基线为 DeepSeek Provider 001 号报告及最新修复实施记录。本报告不改写历史报告，只验证当前代码是否关闭两个 P1。

## 2. 测试依据、目标与边界

### 2.1 测试依据

- 项目根目录、AI Agent、代码目录、全栈、共享记忆、开发工具、架构师和测试工程师目录中的全部适用 `AGENTS.md`。
- `共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`、`MVP范围与验收标准.md`、管理端接口文档、任务拆解、团队职责和代码编写手册。
- `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` 中 `REAL-AI-01`。
- `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`、`ARCH-001-SYS-系统总体架构设计-v1.4.md`。
- DeepSeek Provider 001 号正式报告中的 `DEF-REAL-AI01-001/002` 复现和回归要求。
- 最新修复实施记录要求覆盖的中英文地址、楼栋/房间/邮编、历史消息、工具拆分地址、Trace ID、供应商请求 ID、生产 Formatter 和真实最小请求。
- `security-and-hardening`、`independent-verification` 和 `ponytail` Skill；安全边界不因最小实现原则而降级。

### 2.2 复测目标

1. 验证完整地址不能经当前消息、历史、工具结果或 `StructuredRequest` 最终边界进入外部 Provider。
2. 验证客户端 Trace ID 和供应商请求 ID 不能夹带客户正文、地址、密钥样式、Unicode、控制字符或超长值进入生产 JSON 日志。
3. 验证 JSON Output、Schema 校验、空响应、截断、异常分类、有限重试、取消和 `stream=false` 契约无退化。
4. 验证固定 Phase 4 安全评测、全部后端测试、真实 PostgreSQL、迁移、静态质量和依赖安全无回归。
5. 在不含客户数据的前提下重新尝试一次真实 DeepSeek 正式 Prompt 最小请求。

### 2.3 非目标

- 不修改产品代码、开发测试、Prompt、固定评测集或依赖锁。
- 不执行真实 TikTok 写操作、公开 AI 回复、自动回复、翻译或营销发送。
- 不把单次真实请求等同于 REAL-AI-05 的版本化质量评测。
- 不执行真实 SSE 50 个授权客户端性能、P99 或五日稳定性测试。
- 不验证前端页面；REAL-AI-01 没有前端交付。

## 3. 被测快照与独立性

当前产品目录不是 Git 仓库，无法冻结不可变提交。对 12 个 Provider、安全、日志、入口、开发测试和锁文件计算组合 SHA-256：

```text
b9db7100afe05989f3d8b1529c3bd629a372cdbcfab6078879414228d16153db
```

关键文件摘要：

| 文件 | SHA-256 |
| --- | --- |
| `backend/app/agent/security.py` | `03E7F20D5014DDB89A2AF5267C175D618EA70207A3B8AE59FCB48260CBE47540` |
| `backend/app/agent/providers/base.py` | `EC8C3B9E0E148596300EB021C3BB3EDDCF75F9853BEC99EE597418BF58F25B2E` |
| `backend/app/agent/providers/deepseek_provider.py` | `33C3A5BD6FC9EFAC972C2F49E5F00C56D57A0731E35BB5F1FF3F876580816083` |
| `backend/app/agent/workflow_prompt.py` | `4B060EC349C6566F947818C12AE1E16AEE8910718D85CB32D86C35312F3D4A20` |
| `backend/app/shared/logging/setup.py` | `5D0CC828679BCCE0B7293EFE282C9004C8B24BD2957A62A6EF46ADE81E16F6AC` |
| `backend/app/main.py` | `A3994C8862B5130846432983D90D26ABA69F33A86E0FC035F0BFC62D74FB72C3` |
| `backend/uv.lock` | `3AD5B450855EC7684EA0DD2C2361B5A2E663A5A51050C3DCBA96FB79C69B6172` |

独立性说明：本轮由测试工程师基于当前工作区重新执行，不复用开发者测试结果；独立样本未写入开发测试或固定评测集。由于执行环境仍属于同一 Codex 模型家族且无 Git 不可变提交，本报告属于“独立测试过程和新样本”，不宣称达到异组织、异模型、签名制品级独立验证。

## 4. 测试环境

| 项目 | 实际环境 |
| --- | --- |
| 操作系统 | Windows 10.0.19045，Asia/Shanghai |
| PowerShell | 7.6.4 |
| Python | 3.11.15 |
| uv | 0.12.3 |
| Docker / Compose | 29.7.2 / 5.3.1 |
| PostgreSQL / pgvector | 独立 `pgvector/pgvector:pg16` 容器、端口 55434、tmpfs |
| Alembic head | `019_tiktok_channel_unique` |
| DeepSeek | `deepseek-v4-flash`；Key 只确认已配置，不读取、不输出 |
| Provider 超时 / 总尝试 | 15 秒 / 3 次应用层总预算 |
| 高风险开关 | `AUTO_REPLY_ENABLED=false`、`AI_TRANSLATION_ENABLED=false`、`AI_MARKETING_ENABLED=false` |

## 5. 原缺陷修复验证

| 原缺陷 | 开发固定样本 | 独立变形样本 | 状态 |
| --- | --- | --- | --- |
| `DEF-REAL-AI01-001` 完整地址进入 Provider | 标准中文道路地址、标准英文门牌在前地址、带标签地址及既有结构化字段通过 | 天干门牌、无道路后缀公寓地址、PO Box、门牌在街道名后、拆分字段别名仍泄漏 | **部分修复，P1/Open** |
| `DEF-REAL-AI01-002` 日志标识夹带正文 | 空格正文、Unicode、控制字符、超长值被拒绝；HTTP 非 UUID Trace ID 被替换 | 连字符客户正文、连字符地址和 `sk-` 样式值可经 `provider_request_id` 原样进入 Formatter | **部分修复，P1/Open** |

## 6. 测试场景与结果

### 6.1 工程质量、Provider 和完整回归

| 测试项 | 实际结果 | 状态 |
| --- | --- | --- |
| `uv lock --check` | 125 个包解析成功 | 通过 |
| Ruff | All checks passed | 通过 |
| Ruff 格式 | 210 files already formatted | 通过 |
| mypy | 155 个源文件无问题 | 通过 |
| compileall | 无错误 | 通过 |
| 地址、工具、Provider、日志、健康聚焦测试 | 97 passed、1 warning | 通过开发固定集 |
| 默认后端全量 | 563 passed、10 skipped、2 warnings | 通过；数据库用例随后补跑 |
| 独立 PostgreSQL 全量 | **573 passed、0 skipped、2 warnings** | 通过 |
| 锁定依赖审计 | 124 个包无已知漏洞和不良项目状态 | 通过 |

两个 warning 为既有 Starlette TestClient/httpx 和 argon2 版本元数据弃用提示，不影响本轮安全结论。

### 6.2 数据库与迁移

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| 空库升级 | `001_enable_pgvector → 019_tiktok_channel_unique` | 通过 |
| 当前版本 | `019_tiktok_channel_unique (head)` | 通过 |
| 回滚当前版本 | `019 → 018` | 通过 |
| 恢复到 head | `018 → 019` | 通过 |
| 数据库完整回归 | 573 passed、0 skipped | 通过 |

### 6.3 Provider 输出、异常和运行门禁

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| JSON Output 与 Pydantic 二次校验 | 有效结构通过；非法 JSON、空响应、Schema 失配失败关闭 | 通过 |
| 截断与非正常终止 | `length/tool_calls/未知原因` 不进入工作流；内容过滤拒绝 | 通过 |
| 429、408、超时、连接和 5xx | 映射为稳定可重试错误 | 通过 Mock 契约 |
| 400/422、401/402/403 | 映射为稳定不可重试错误 | 通过 Mock 契约 |
| 取消 | `CancelledError` 原样传播 | 通过 |
| 原生流式输出 | 请求保持 `stream=false` | 通过 |
| 固定确定性安全评测 | 234 条，安全准确率和原因码准确率 100%，危险漏放 0，`live_model_evaluation=false` | 通过固定集 |
| 真实 DeepSeek 最小请求 | 合成物流问题在 15 秒超时，Provider 映射为 `LLM_TIMEOUT/retriable=true` | 失败关闭通过；成功链路本轮未重新确认 |
| 高风险开关 | 自动回复、翻译和营销均为 false | 通过当前门禁 |

001 号报告曾在同日成功完成真实最小请求。本轮重试结果只能证明当前超时分类和失败关闭，不能把历史成功当成本轮成功，也不能形成真实模型质量或可用性通过结论。

### 6.4 独立地址变形测试

所有样本均为测试工程师构造的虚拟数据；脚本只输出命中布尔值，不保存完整 Provider 请求。

| 样本 | 预期 | 实际 | 状态 |
| --- | --- | --- | --- |
| `北京市朝阳区建国路甲88号A座1201室` | 整体或足以复原地址的部分被屏蔽 | `StructuredRequest.user_prompt` 保留完整地址 | 失败 |
| `北京市海淀区东升园公寓12号楼3单元501室` | 整体被屏蔽 | 完整保留 | 失败 |
| `PO Box 123, Seattle, WA 98101` | PO Box、城市和邮编均不能保留 | 三部分均保留 | 失败 |
| `Baker Street 221B, London NW1 6XE` | 街道、门牌、城市和邮编不能组合保留 | UK 邮编被替换，但街道门牌和城市保留 | 失败 |
| 标准 `350 Fifth Avenue, Apt 12B...` | 屏蔽 | 被替换为地址标记 | 通过控制样本 |
| `祖冲之路1555弄18号2楼` | 屏蔽 | 被替换为地址标记 | 通过控制样本 |

结构化工具结果使用以下常见拆分字段：

```text
district
street_name
house_number
building
room
postal_code
```

实际仅 `postal_code` 被替换，其他五个字段均保留，可在模型端重新拼合。当前正式工具输出 Schema 通常不返回地址正文，降低了现有主路径暴露面；但 `_sanitize_value` 被设计为外部 Provider 前的最终通用防线，且修复实施记录明确承诺“分段工具地址不可重新拼接”，因此不能据此关闭原 P1。

### 6.5 独立日志元数据变形测试

| `provider_request_id` 输入 | 实际结果 | 状态 |
| --- | --- | --- |
| 标准 UUID | 原样保留 | 通过正向控制 |
| Unicode 正文 | `[INVALID_LOG_METADATA]` | 通过 |
| 控制字符 | `[INVALID_LOG_METADATA]` | 通过 |
| 101 字符超长值 | `[INVALID_LOG_METADATA]` | 通过 |
| `private-customer-message` | 原样保留 | 失败 |
| `350-Fifth-Avenue-Apt-12B` | 原样保留 | 失败 |
| `sk-1234567890abcdef` | 原样保留 | 失败 |

HTTP 中间件已将客户端 `X-Trace-Id` 收紧为标准 UUID，该子路径验证通过。但最终 Formatter 仍使用一个通用“有限 ASCII、100 字符”正则判断所有字符串元数据；字符集和长度合法不等于内容低敏。`DeepSeekProvider` 会把响应 ID 或错误请求 ID写入 `provider_request_id`，该外部值仍可把上述内容带入生产日志。

## 7. 缺陷详情

### DEF-REAL-AI01-001：完整地址脱敏仍可被常见地址形态绕过

| 项目 | 内容 |
| --- | --- |
| 优先级 | **P1** |
| 状态 | **部分修复 / Open** |
| 类型 | 数据出境、客户隐私、Provider 最终边界 |
| 代码位置 | `backend/app/agent/security.py`、`backend/app/agent/providers/base.py`、`backend/app/agent/workflow_prompt.py` |
| 是否阻断 | **是，阻断 REAL-AI-01 和生产 AI 放行** |
| 建议负责 Agent | AIAgent开发工程师Agent；架构师Agent评审数据最小化边界 |

复现步骤：

1. 使用上述天干门牌、无道路后缀公寓、PO Box 或街道名在前的英文地址构造 `StructuredRequest.user_prompt`。
2. 读取构造完成后的 `user_prompt`，无需调用真实模型。
3. 对工具结果调用 `_sanitize_value`，字段使用 `district/street_name/house_number/building/room/postal_code`。
4. 检查地址组成部分是否仍可复原。

实际结果：四类文本地址均保留足以复原的地址；拆分字段仅邮编被屏蔽。

预期结果：ADR-004 明确禁止完整地址进入 DeepSeek。最终 Provider 边界必须对不能可靠最小化的地址失败关闭；通用工具序列化不能依靠不完整字段名黑名单证明安全。

建议修复：

- 把当前地址正则定位为纵深防御，不作为唯一出境证明。
- 对客户消息中的寄送、搬家、地址修改等高风险上下文执行整段最小化或拒绝外发，覆盖 `甲/乙` 门牌、`弄/号楼/单元/室`、PO Box 和门牌顺序变体。
- 工具结果优先使用当前强类型输出 Schema 的字段级允许列表，只序列化模型确实需要的物流/状态字段；不要把任意字典先接收再用地址字段黑名单过滤。
- 在 `StructuredRequest` 最终边界增加独立失败条件，并把本报告样本加入回归，但不要只对四条样本打补丁。

### DEF-REAL-AI01-002：日志元数据通用 ASCII 正则仍允许正文和密钥样式值

| 项目 | 内容 |
| --- | --- |
| 优先级 | **P1** |
| 状态 | **部分修复 / Open** |
| 类型 | 日志隐私、凭证保护、外部输入验证 |
| 代码位置 | `backend/app/shared/logging/setup.py`、`backend/app/agent/providers/deepseek_provider.py` |
| 是否阻断 | **是，阻断 REAL-AI-01 和生产日志放行** |
| 建议负责 Agent | AIAgent开发工程师Agent、全栈开发工程师Agent |

复现步骤：

1. 创建包含安全 `event` 的 `LogRecord`。
2. 将连字符客户正文、地址或 `sk-` 样式值写入 `provider_request_id`。
3. 使用生产 `JsonFormatter` 格式化。
4. 检查输出 JSON。

实际结果：三类值均满足当前 ASCII/长度正则并原样进入日志。

预期结果：外部供应商 ID 和请求 Header 都是不可信输入。最终日志出口不能仅凭字符集和长度推断低敏，密钥样式或客户正文不得借标识字段进入日志。

建议修复：

- 按字段定义契约：Formatter 中 `trace_id` 只接受 UUID；内部启动、校验等场景使用事件字段，不借 Trace ID 表达语义。
- `provider_request_id` 建议只记录稳定不可逆摘要和长度，保留关联能力但不保存供应商原始字符串。
- Provider、模型、Prompt 版本和错误码分别按可信配置/枚举校验，不复用一个通用字符串允许正则。
- 把本报告三条独立负向样本加入最终 Formatter 和真实 Provider 失败日志回归。

## 8. 回归、风险与验收状态

| 范围 | 结论 |
| --- | --- |
| Provider JSON、错误、重试、取消、`stream=false` | 通过，无退化 |
| 历史 M04 确定性安全 | 234 条固定评测通过；历史 002 报告相关回归无自动化退化 |
| 后端与数据库 | 573 项隔离 PostgreSQL 全量通过；迁移可逆 |
| `DEF-REAL-AI01-001` | 部分修复，P1/Open |
| `DEF-REAL-AI01-002` | 部分修复，P1/Open |
| 真实 DeepSeek | 本轮最小请求超时；错误分类通过，成功链路未重新确认 |
| 公开 AI / 翻译 / 营销 | 开关保持关闭，未放行 |

遗留生产门禁：

- 修复并独立关闭上述两个 P1。
- 完成 REAL-AI-05 真实回复、翻译、营销和结构化业务声明评测。
- 完成真实 SSE 50 个授权客户端首输出、P99、取消、断线恢复和五日稳定性。
- 完成真实日志采集端查询、保留和密钥轮换证据。
- 建立 Git 或签名制品级不可变发布基线。

## 9. 最终结论

**最终结论：不通过 REAL-AI-01 独立验收。**

开发修复对固定路径有效：标准中英文地址、Unicode/控制字符/超长日志值和客户端非 UUID Trace ID 已被阻断；Provider 工程、573 项完整数据库回归、234 条固定安全评测、迁移和依赖安全均通过。

但独立变形测试证明两个原 P1 的根因仍存在。常见地址格式仍能穿过 `StructuredRequest` 最终边界，工具地址别名可被重新拼合；日志 Formatter 仍会接受连字符正文、地址和密钥样式值。两项均命中 ADR-004 的明确停止条件，不能按“仅剩边缘风险”降级。

在测试工程师后续独立复测关闭两项缺陷前，必须继续保持：

```text
AUTO_REPLY_ENABLED=false
AI_TRANSLATION_ENABLED=false
AI_MARKETING_ENABLED=false
```

本报告不否定 001 号报告已经通过的 Provider 工程主体和历史真实最小请求，只拒绝关闭当前两个生产数据安全缺陷。

## 10. 测试清理

- 本轮 PostgreSQL 使用精确名称 `crm-real-ai01-002-postgres`、独立端口 55434 和 tmpfs；测试后已停止并删除，临时数据库不可恢复。
- 已清理本轮两个 pytest 临时目录和一份固定评测临时结果。
- 未触碰持久化开发 PostgreSQL、Redis、MinIO 或其他正在运行的容器。
- 未修改产品代码、开发测试、Prompt、固定评测集、迁移或锁文件。
- 本轮只新增本正式测试报告并更新 `共享记忆文档/测试报告索引.md`。
