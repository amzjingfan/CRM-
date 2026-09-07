# REAL-AI-04 回复、翻译和营销草稿第六次独立综合测试报告

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-AI-04`，复测 `DEF-REAL-AI04-005` |
| 模块编号 | M04 |
| 模块名称 | 回复、翻译和营销草稿 |
| 被测主责 Agent | AIAgent开发工程师Agent |
| 被测协作 Agent | 架构师Agent、全栈开发工程师Agent |
| 测试执行 Agent | 测试工程师Agent |
| 关联实施记录 | `共享记忆文档/实施记录/Phase4-P4-00-AIAgent开发工程师Agent-REAL-AI-04业务Prompt注册缺陷修复-032.md` |
| 关联上一报告 | `测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-REAL-AI-04回复翻译营销草稿-综合测试-005.md` |
| 测试类型 | 综合测试、Provider 契约测试、安全测试、异常测试、AI 评测、回归测试、数据库测试、迁移测试、部署检查、依赖审计、代码审查 |
| 执行日期 | 2026-09-05 |
| 测试结论 | **当前确定性工程与无网络 Provider 契约范围有条件通过；`DEF-REAL-AI04-005` Closed** |

## 2. 测试目标与边界

本轮在 AIAgent开发工程师Agent完成 005 号报告问题整改后，独立验证：

1. 意图分类、FAQ 回复、FAQ 复核、工具回复、工具复核、翻译、营销生成和营销复核八类业务 Prompt 是否都进入版本化注册表。
2. 注册项是否同时绑定系统 Prompt 摘要、输入前缀、顶层字段集合和最终响应 Schema。
3. 八类合法业务信封是否真实到达 `DeepSeekProvider` 的 SDK 调用边界并完成结构化输出解析。
4. 未登记直传、系统 Prompt 篡改、场景错配、Schema 错配、前缀/字段漂移、JSON 重复键、未脱敏敏感数据和评测上下文混用是否继续在 SDK 前失败关闭。
5. 实际翻译和营销业务服务是否已经打通；营销候选是否仍固定人工审核、`send_performed=false`。
6. `DEF-P4-AI-008/009`、`DEF-REAL-AI04-001～004`、后端、数据库、迁移、固定评测和前端是否出现回归。

本轮只使用虚构低敏数据和无网络 SDK 记录客户端，不调用真实 DeepSeek，不使用真实客户、订单、店铺或 TikTok 凭证，不执行数据库业务写入、业务工具或平台消息发送。真实模型回复质量、翻译质量、营销文案质量、公开 SSE 50 客户端性能和五日稳定性属于 REAL-AI-05 与联合生产门禁，不由本报告代替。

测试工程师未修改产品代码、开发测试、依赖锁文件、实施计划、`.env` 或历史测试报告；仅新增测试工程师自有探针、固定评测摘要、本正式报告，并更新共享测试报告索引。

## 3. 需求与验收依据

- `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md`
- `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`
- `架构师/ADR-005-AI-知识语义类型与发布审批边界-v1.0.md`
- `共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`
- `共享记忆文档/智能客服平台 — 管理端接口文档.md`
- `共享记忆文档/MVP范围与验收标准.md`
- `共享记忆文档/代码编写手册.md`
- 项目级、测试工程师、AI Agent、产品代码和共享记忆目录的 `AGENTS.md`
- `测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-REAL-AI-04回复翻译营销草稿-综合测试-005.md`

关键验收链路：

```text
可信业务服务选择固定业务场景
→ 系统 Prompt 摘要与场景 ID 精确匹配
→ 输入前缀、顶层字段和 DLP 校验
→ 响应 Schema 与场景绑定
→ DeepSeek SDK
→ Pydantic 结构校验与业务安全门禁
→ 仅返回草稿或候选，不直接发送平台消息
```

## 4. 测试环境与基线冻结

### 4.1 环境

| 项目 | 实际环境 |
| --- | --- |
| 操作系统 | Windows，PowerShell |
| Python | 3.11.15 |
| uv | 0.12.3 |
| Node.js / npm | 24.19.0 / 11.17.0；本地 Node 高于项目 Node 20 基线 |
| 前端 | Next.js 15.5.23 |
| Docker / Compose | Docker 29.7.2；独立 `docker-compose` 5.3.1 |
| 数据库 | 一次性 `pgvector/pgvector:pg16` 测试服务，`tmpfs` 数据卷，端口 5433 |
| Alembic head | `023_marketing_review_idempotency` |
| Git | 当前产品目录不是 Git 仓库，不能声明提交级不可变基线 |

### 4.2 产品源文件聚合哈希

对 `backend/app`、`backend/migrations`、`backend/scripts`、`backend/tests`、`tests/integration`、前端主要代码与测试目录，以及主要依赖和部署清单共 273 个文件，按相对路径和文件 SHA-256 生成聚合摘要：

```text
7965772284448e1005dde675fe294542f587dfdc3a92eecef6ca20cdf627ca0e
```

由于当前目录不是 Git 仓库，该摘要只表示本轮测试快照，不等同于提交级不可变发布候选。

关键文件 SHA-256：

```text
backend/app/agent/prompt_registry.py
f150182098d92b706352bedf79d0fc2e5b7e49514630f144b0b522bd6e8573b8

backend/app/agent/security.py
30b48f5b19b2e8a7392ec023ab5771ce058ac76cbd358929a5c6fcd9742d5558

backend/app/agent/providers/base.py
0199ae22ef665bdcd130dd55cb6b153918a9a3da3e1f87416e3121d5a910ef91

backend/app/agent/translation.py
6d0ce2293c1c1552ca789012801e0930e9646d110f6c2ad1fcbe7dda53eb43ef

backend/app/agent/marketing_generation.py
42b356db63efe80f902f6b15434c5b99abe27b512a80d7c765fff70412442cf8
```

## 5. 独立测试方法与证据

### 5.1 新增独立探针

```text
测试工程师/evidence/REAL-AI-04-006/test_real_ai04_prompt_registry_retest.py
SHA-256: 896bd8bdd64a1d4b4c5ffe1dff88f90047ccbc6375a4406e8d7d3ee5efe71598
```

探针不复用产品测试函数。七个测试函数名在 `backend/tests` 中精确重名数均为 0，参数化后共执行 29 项：

- 8 项合法业务信封使用产品真实 `DeepSeekProvider`，每项必须完成一次无网络 SDK 调用和对应 Pydantic Schema 解析。
- 8 项注册摘要、响应 Schema 和顶层字段集合一致性校验。
- 9 项非法信封 SDK 前拒绝：缺少场景、系统 Prompt 篡改、错场景、错 Schema、错前缀、缺字段、多字段、嵌套重复键、未脱敏邮箱。
- 1 项 REAL-AI-05 评测上下文与生产业务场景冲突拒绝。
- 1 项真实 `TranslationService` 调用链，验证返回原文 SHA-256 关联而非额外复制原文。
- 1 项真实 `MarketingCopyService` 生成与独立复核双调用，验证人工审核和零发送边界。
- 1 项测试替身无平台、数据库和工具写入接口约束。

结果：

```text
29 passed in 1.05s
```

005 号历史证据原样保留，不把其中“实际业务服务应被拒绝”的旧断言作为当前质量门禁。新探针重新覆盖了其仍应成立的安全边界：调用方若不提供业务场景 ID，直接传入产品系统 Prompt 仍返回 `LLM_REFUSAL`，且 SDK 调用数为 0。

### 5.2 代码调用点审查

产品代码共找到 8 个显式业务场景调用点，场景完整无缺失：

```text
service.py: INTENT_CLASSIFIER
workflow.py: FAQ_ANSWER / FAQ_GROUNDING_REVIEW
workflow.py: TOOL_ANSWER / TOOL_GROUNDING_REVIEW
translation.py: TRANSLATION
marketing_generation.py: MARKETING_COPY / MARKETING_REVIEW
```

`DeepSeekProvider`、`OpenAIProvider` 和 `AnthropicProvider` 均在最终调用前把响应 Schema 名交给统一信封校验。Agent 仍不直接拥有平台发送或数据库写操作能力。

### 5.3 固定安全评测

```text
测试工程师/evidence/REAL-AI-04-006/fixed-eval-result.json
SHA-256: bf8c271c80443a4e1532cf034be63bb0b7683359136972cfe2f19dcdd98f9953

sample_count=237
safety_accuracy=1.0
reason_code_accuracy=1.0
unsafe_escape_count=0
failed_case_ids=[]
passed=true
live_model_evaluation=false
```

## 6. 测试执行结果

| 测试项 | 结果 | 状态 |
| --- | --- | --- |
| 八类业务 Prompt 注册 | 8/8 摘要、版本、字段和响应 Schema 绑定一致 | 通过 |
| 八类业务信封 Provider 正向路径 | 8/8 到达无网络 DeepSeek SDK 替身并解析成功；共 8 次调用 | 通过 |
| 未登记直传保护 | 不带场景 ID 的产品系统 Prompt 在 SDK 前返回 `LLM_REFUSAL` | 通过 |
| 篡改与错配保护 | 系统 Prompt 篡改、错场景、错 Schema、错前缀均 SDK 零调用 | 通过 |
| 输入结构与 DLP | 缺失/额外字段、嵌套重复键、未脱敏邮箱均 SDK 零调用 | 通过 |
| 评测上下文隔离 | REAL-AI-05 评测白名单不能和业务场景叠加 | 通过 |
| 翻译实际服务链路 | 1 次 Provider 调用；输出目标语言一致；使用原文 SHA-256 关联 | 通过 |
| 营销实际服务链路 | 生成和复核各 1 次；安全候选保留；强制人工审核；`send_performed=false` | 通过 |
| 聚焦回归 | `849 passed, 3 skipped in 6.20s` | 通过 |
| 默认后端全量 | `1316 passed, 12 skipped, 2 warnings in 8.09s` | 通过 |
| 隔离 PostgreSQL 全量 | `1328 passed, 2 warnings in 9.47s` | 通过 |
| 数据库迁移 | 空库 `001→023`；`023→022→023`；最终为 023 | 通过 |
| 固定安全评测 | 237/237，准确率 1.0，原因码准确率 1.0，零危险逃逸 | 通过 |
| Ruff | 规则检查通过；234 个 Python 文件格式检查通过 | 通过 |
| mypy | `Success: no issues found in 166 source files`；本机耗时约 110 秒 | 通过 |
| compileall | `app`、迁移、脚本和开发测试可编译 | 通过 |
| 依赖锁 | `uv lock --check`，解析 125 个包 | 通过 |
| Python 依赖审计 | 124 个锁定包无已知漏洞和不利状态 | 通过 |
| 前端 lint/typecheck | 均通过 | 通过 |
| 前端测试 | 32/32 通过 | 通过 |
| 前端生产构建 | Next.js 15.5.23 构建成功，14 个静态页面步骤完成 | 通过 |
| Compose 配置 | `docker-compose config --quiet` 返回 0 | 通过 |
| 当前运行态健康 | backend 容器仍为 `unhealthy`；`/v1/health` 10 秒超时 | **环境失败，既有** |
| Python/AI 低敏扫描 | 12 个修复相关文件中密钥样式、凭证赋值和危险开关命中均为 0 | 通过 |
| 前端生产依赖审计 | PostCSS/Sharp 共 3 个 High；修复建议升级 Next 16 | **失败，既有 `DEF-REAL-FS01-005`** |

两个 pytest 警告仍来自 Starlette `TestClient`/httpx 兼容弃用提示和 passlib 读取 argon2 版本属性的弃用提示，不是本轮新增缺陷。

## 7. 缺陷复测结论

### 7.1 DEF-REAL-AI04-005：Closed

| 项目 | 复测结论 |
| --- | --- |
| 原优先级 | P1 |
| 原影响 | REAL-AI-04 真实 Provider 草稿、翻译、营销和后续公开 AI 链路阻断 |
| 当前状态 | **Closed** |
| 关闭证据 | 8 类注册一致性、8 类 DeepSeek 最终边界正向调用、9 类失败关闭、翻译和营销实际服务调用 |

修复符合预期：

- 新增集中业务 Prompt 注册表，八类场景均有稳定 ID、版本、用途、正文 SHA-256、输入前缀、顶层字段集合和响应 Schema。
- `StructuredRequest` 显式携带 `business_prompt_id`，三个 Provider 在 SDK 前统一校验响应 Schema。
- FAQ 和工具动态回复配置已移入业务 JSON，系统 Prompt 保持固定正文。
- 未登记和被篡改的系统 Prompt 继续默认拒绝，没有通过关闭门禁或复用评测上下文放宽权限。
- 翻译和营销真实业务服务已从“SDK 前统一拒绝”变为“通过注册边界进入 SDK”；营销仍没有平台发送能力。

因此 `DEF-REAL-AI04-005` 正式关闭。

### 7.2 既有 REAL-AI-04 与安全缺陷

- `DEF-P4-AI-008/009`：237 条固定评测零危险逃逸，知识安全和工作流回归通过，保持 Closed。
- `DEF-REAL-AI04-001`：SSE 结果交付前断开或取消不伪装成功，保持 Closed。
- `DEF-REAL-AI04-002`：安全营销候选进入人工审核且不发送，保持 Closed。
- `DEF-REAL-AI04-003`：审核幂等重放和冲突规则保持通过，保持 Closed。
- `DEF-REAL-AI04-004`：并发相反决定只有一个终态，保持 Closed。

本轮未发现新的 REAL-AI-04 P0/P1/P2 产品缺陷。

## 8. 观察与环境状态

### OBS-REAL-AI04-006-01：系统 Prompt 安全文档字符串存在历史措辞

`backend/app/agent/security.py` 的 `evaluate_system_prompt_safety()` 文档字符串仍写有“业务 Prompt 后续必须……建立版本化注册表”，而注册表本轮已经落地。该措辞不影响运行、安全或验收，不登记为产品缺陷；建议 AIAgent开发工程师下次维护时改为“业务 Prompt 必须通过版本化注册表”，避免维护者误读当前状态。

### ENV-REAL-AI04-006-01：测试期间 `.env` 发生外部变更

本轮初始读取到 `LLM_LIVE_EVAL=true` 且价格治理字段未配置，迁移命令因 Settings 失败关闭；测试工程师仅在确定性命令中使用进程级 `LLM_LIVE_EVAL=false`。测试期间 `.env` 于 2026-09-05 11:21 被外部更新为：

```text
APP_ENV=development
LLM_ENABLED=true
LLM_LIVE_EVAL=false
AI_TRANSLATION_ENABLED=true
AI_MARKETING_ENABLED=false
AUTO_REPLY_ENABLED=false
```

测试工程师没有编辑 `.env`。当前直接创建 `Settings` 已成功，文件级价格治理阻断已解除；但该环境变化发生在基线测试期间，且当前目录没有 Git，后续生产候选仍需重新冻结。

### ENV-REAL-AI04-006-02：现有 backend 容器仍不健康

当前 backend 容器已运行 3 天并保持 `unhealthy`，`http://localhost:8000/v1/health` 在 10 秒内无响应；PostgreSQL、Redis、MinIO 和前端为 healthy，worker/jobs 运行。当前 `.env` 已关闭真实评测，但既有容器没有重新创建，仍可能持有旧环境。本轮不重启用户长期服务，不将其归为业务 Prompt 修复缺陷；全栈工程师应在下次运行态验收中按受控方式重建 backend 并复核健康。

## 9. 仍未关闭的生产门禁

1. REAL-AI-05 的独立真实 DeepSeek 最终模型质量结论仍未完成，本报告不关闭或替代其缺陷状态。
2. 真实 DeepSeek 回复、翻译和营销语言质量、成本与开放集评测尚未由本报告执行。
3. 真实模型 50 个授权客户端 SSE、首输出/P99、断线恢复和五日 99.5% 稳定性尚未完成。
4. 当前 backend 容器不健康，需在受控重建后重新验证健康、配置和运行日志。
5. 前端生产依赖仍有 3 个 High，既有 `DEF-REAL-FS01-005` 未关闭；测试工程师未执行破坏性 `npm audit fix --force`。
6. 真实 TikTok OAuth、Scope、Webhook、人工消息发送、未知结果对账和回滚仍需联合生产验收。
7. 当前不是 Git 仓库，缺少提交级不可变发布候选。

在以上生产门禁全部关闭前，公开 AI 回复、AI 营销自动发送、自动回复和 AI 触发平台写操作继续关闭。`DEF-REAL-AI04-005` 的关闭只表示业务 Prompt 注册和无网络 Provider 契约恢复，不等同于生产放行。

## 10. 最终结论

**REAL-AI-04 第六次独立综合测试：当前确定性工程与无网络 Provider 契约范围有条件通过。**

- `DEF-REAL-AI04-005` 已关闭：八类业务 Prompt 均完成版本化精确注册，8/8 合法信封可到达 DeepSeek SDK 边界并解析结构化响应。
- 失败关闭没有退化：9 类篡改、错配、结构漂移和敏感输入均 SDK 零调用；无场景直传继续拒绝；评测上下文不能授权业务信封。
- 翻译服务已可调用 Provider；营销生成和独立复核已可调用 Provider，但结果仍固定人工审核且 `send_performed=false`。
- 29 项独立探针、849 项聚焦、1316 项默认后端、1328 项隔离 PostgreSQL、237 条固定评测、迁移、Ruff、mypy、Python 依赖、32 项前端测试和生产构建通过。
- `DEF-P4-AI-008/009` 与 `DEF-REAL-AI04-001～004` 保持 Closed；本轮无新增 REAL-AI-04 P0/P1/P2 产品缺陷。
- 当前 backend 容器不健康、前端 3 个 High、真实模型质量/性能/稳定性和真实平台门禁仍未完成，因此不得据本报告开启生产 AI 或真实平台自动写操作。

## 11. 清理与交接

- 一次性 PostgreSQL 测试服务已停止并删除，测试数据使用 `tmpfs`，没有触碰开发数据库。
- 本轮 pytest、mypy 和 uv 临时缓存均已从 `测试工程师/evidence/REAL-AI-04-006/` 清理，仅保留独立探针和低敏固定评测摘要。
- 没有重启、替换或修改用户现有 Compose 服务，backend 的不健康状态原样保留并登记。
- 本报告成为 REAL-AI-04 当前最新权威测试结论；001～005 号报告继续保留历史缺陷追溯。
