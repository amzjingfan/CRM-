# REAL-AI-04 回复、翻译和营销草稿第五次独立综合测试报告

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-AI-04`，并审查 `REAL-AI-05` 首次测试缺陷整改对本任务的影响 |
| 模块编号 | M04 |
| 模块名称 | 回复、翻译和营销草稿 |
| 被测主责 Agent | AIAgent开发工程师Agent |
| 被测协作 Agent | 架构师Agent、全栈开发工程师Agent |
| 测试执行 Agent | 测试工程师Agent |
| 关联实施记录 | `共享记忆文档/实施记录/Phase4-P4-00-AIAgent开发工程师Agent-REAL-AI-04回复翻译营销草稿-026.md`、`共享记忆文档/实施记录/Phase4-P4-00-AIAgent开发工程师Agent-REAL-AI-05首次测试缺陷整改-031.md` |
| 关联上一报告 | `测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-REAL-AI-04回复翻译营销草稿-综合测试-004.md` |
| 测试类型 | 综合测试、接口与集成测试、安全测试、AI 评测、异常测试、回归测试、数据库测试、迁移测试、部署检查、代码审查 |
| 执行日期 | 2026-09-05 |
| 测试结论 | **不通过** |

## 2. 测试目标与边界

本轮在 AIAgent开发工程师Agent完成 REAL-AI-05 首次测试缺陷整改后，重新审查 REAL-AI-04 的回复、翻译和营销草稿生产调用链，重点验证：

1. FAQ 回复、工具结果回复、意图识别、翻译、营销生成和营销复核使用的真实系统 Prompt 能否通过外部 Provider 最终安全边界。
2. REAL-AI-05 新增的系统 Prompt 注册机制是否只允许评测信封，还是已经覆盖 REAL-AI-04 的业务信封。
3. 翻译与营销服务能否在启用真实 Provider 时到达 SDK 调用，同时继续满足脱敏、失败关闭和零平台副作用要求。
4. `DEF-P4-AI-008/009` 与 `DEF-REAL-AI04-001～004` 是否保持关闭。
5. 后端、隔离 PostgreSQL、迁移、固定评测、前端和依赖是否出现回归。

本轮未使用真实客户、订单、店铺或 TikTok 凭证，未执行平台写操作。由于新的独立探针证实业务请求在本地 Provider 边界即被拒绝，测试工程师未继续产生无意义的真实 DeepSeek 计费请求；探针使用无网络记录客户端确认 SDK 调用数为 0。真实模型语言质量、公开 SSE 50 客户端性能和五日稳定性不在本轮完成范围。

测试工程师未修改产品代码、开发测试、依赖锁文件、实施计划或历史测试报告；仅新增独立测试证据、本正式报告，并按规范更新共享测试报告索引。

## 3. 需求与验收依据

- `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md`
- `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`
- `架构师/ADR-005-AI-知识语义类型与发布审批边界-v1.0.md`
- `共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`
- `共享记忆文档/智能客服平台 — 管理端接口文档.md`
- `共享记忆文档/MVP范围与验收标准.md`
- `共享记忆文档/代码编写手册.md`
- 项目级、测试工程师、AI Agent、产品代码和共享记忆目录的 `AGENTS.md`
- `测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-REAL-AI-04回复翻译营销草稿-综合测试-004.md`
- `测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-REAL-AI-05版本化真实模型评测-AI评测-001.md`

REAL-AI-04 的关键验收边界：

```text
受控业务输入
→ 回复 / 翻译 / 营销结构化请求
→ Provider 最终脱敏与系统 Prompt 信任校验
→ DeepSeek SDK
→ 结构化输出校验与安全门禁
→ 仅生成草稿或候选，不直接发送平台消息
```

系统 Prompt 采用失败关闭是正确原则，但项目自身的固定业务 Prompt 必须通过版本化、精确匹配的可信注册表授权；不能把所有业务 Prompt 永久当作未知输入拒绝，也不能为修复功能而放宽任意系统 Prompt 的默认拒绝策略。

## 4. 测试环境与基线冻结

### 4.1 环境

| 项目 | 实际环境 |
| --- | --- |
| 操作系统 | Windows，PowerShell |
| Python | 3.11.15 |
| uv | 0.12.3 |
| Node.js / npm | 24.19.0 / 11.17.0；本地 Node 高于项目 Node 20 基线 |
| 前端 | Next.js 15.5.23 |
| 数据库 | 项目脚本创建的一次性 `pgvector/pgvector:pg16`，使用容器 `tmpfs` |
| Alembic head | `023_marketing_review_idempotency` |
| Git | 当前产品目录不是 Git 仓库，不能声明提交级不可变基线 |

### 4.2 产品源文件聚合哈希

对 `backend/app`、`backend/migrations`、`backend/tests`、`tests/integration`、`frontend/app`、`frontend/components`、`frontend/lib`、`frontend/tests` 和主要依赖/部署清单共 252 个文件，按相对路径排序后计算聚合 SHA-256：

```text
1d8fd4872d089f960a6d86187262b5252b445387a6075f9c9f916824509d4617
```

本轮仅记录结论快照；由于当前目录不是 Git 仓库，不能将该哈希等同于提交级不可变发布候选。

关键文件 SHA-256：

```text
backend/app/agent/security.py
3906b6be6d5840a4962d401f0bb5d81d6514e8a75ee3c08ad4595f92f46a9433

backend/app/agent/providers/base.py
f6004716d884c9a2f1914d8283d2de12417fd51115d6d07089d68f261500def2

backend/app/agent/translation.py
fcd5832bdddcfb4cd20e7281a4f2e4be648b538297bcc476dbeb2329ba668967

backend/app/agent/marketing_generation.py
64d6675abdb8accb88f2a2faf35ddda082aca8231cbb429aa8354381d54dc73f
```

## 5. 独立方法与证据

### 5.1 Provider 最终边界探针

新增独立证据：

```text
测试工程师/evidence/REAL-AI-04-005/test_real_ai04_provider_boundary.py
SHA-256: 6457c279e88954b04de4e12ae0ce114f2253cf888debb6588986f6b1f29c0fe5
```

探针使用产品真实 `DeepSeekProvider`、`StructuredGenerationService`、`TranslationService` 和 `MarketingCopyService`，仅把底层 HTTP 客户端替换为记录调用次数的无网络客户端。这样可以同时验证真实产品边界，并保证不泄漏数据、不产生模型费用。

覆盖八类产品固定系统 Prompt：

1. 意图分类。
2. FAQ 回复生成。
3. FAQ Grounding 复核。
4. 工具结果回复生成。
5. 工具 Grounding 复核。
6. 翻译。
7. 营销文案生成。
8. 营销文案独立复核。

对照组使用 REAL-AI-05 的 `REAL_MODEL_EVALUATION_SYSTEM_PROMPT`。最终结果：

```text
13 passed in 13.14s
```

这 13 项“通过”表示探针成功、稳定地证明了当前行为，并不表示业务功能通过：八类 REAL-AI-04 Prompt 均返回 `UNTRUSTED_SYSTEM_PROMPT_REQUIRES_REGISTRY`；对照的 REAL-AI-05 评测 Prompt 被允许；翻译和营销服务均返回 `LLM_REFUSAL`，底层客户端调用数为 0。

### 5.2 回归与固定评测

在当前 `.env` 上直接收集测试时，Settings 因 `LLM_LIVE_EVAL=true` 但价格和价格版本未配置而失败关闭。测试工程师没有修改 `.env`，仅对不执行真实模型的回归命令设置进程级 `LLM_LIVE_EVAL=false`，以区分环境配置漂移与确定性产品回归。

聚焦回归覆盖 REAL-AI-04、Agent 工作流、Phase4、知识安全、营销审核、REAL-AI-05 及既有测试证据：

```text
798 passed, 3 skipped in 6.77s
```

默认后端全量：

```text
1292 passed, 12 skipped, 2 warnings in 36.78s
```

隔离 PostgreSQL 全量：

```text
1304 passed, 2 warnings in 8.61s
```

固定确定性安全评测：

```text
sample_count=237
safety_accuracy=1.0
reason_code_accuracy=1.0
unsafe_escape_count=0
failed_count=0
passed=true
live_model_evaluation=false
```

评测汇总：

```text
测试工程师/evidence/REAL-AI-04-005/fixed-eval-result.json
SHA-256: bf8c271c80443a4e1532cf034be63bb0b7683359136972cfe2f19dcdd98f9953
```

## 6. 测试执行结果

| 测试项 | 预期 | 实际结果 | 状态 |
| --- | --- | --- | --- |
| REAL-AI-04 系统 Prompt 注册 | 固定、版本化业务 Prompt 可通过；任意 Prompt 默认拒绝 | 八类业务 Prompt 全部为 `UNCERTAIN`，原因码 `UNTRUSTED_SYSTEM_PROMPT_REQUIRES_REGISTRY` | **失败** |
| 评测 Prompt 对照 | REAL-AI-05 专用信封可按注册表通过 | 评测 Prompt 被允许 | 通过 |
| 翻译真实 Provider 边界 | 脱敏后进入 SDK，结构化校验，失败不发送 | 在 SDK 前返回 `LLM_REFUSAL`；客户端 0 调用 | **失败** |
| 营销真实 Provider 边界 | 生成与复核可进入 SDK，仍只产生待审草稿 | 在 SDK 前返回 `LLM_REFUSAL`；客户端 0 调用 | **失败** |
| 评测上下文滥用 | 评测信封不能授权业务信封 | 使用评测上下文仍不能放行翻译信封 | 通过 |
| 平台副作用 | 测试不得发送真实消息或执行工具 | 无网络客户端、无工具写接口、零平台发送 | 通过 |
| 既有 REAL-AI-04 回归 | 001～004 和业务安全门禁不退化 | 聚焦集合 `798 passed, 3 skipped` | 通过 |
| 默认后端全量 | 既有功能无回归 | `1292 passed, 12 skipped, 2 warnings` | 通过 |
| 隔离 PostgreSQL 全量 | 数据库路径无回归 | `1304 passed, 2 warnings` | 通过 |
| 数据库迁移 | 空库升级、回滚、恢复 | `001→023`、`023→022→023` 成功，最终为 023 | 通过 |
| 固定确定性评测 | 零危险逃逸、原因码一致 | 237/237，准确率 1.0，零逃逸 | 通过 |
| Ruff | 无静态规则或格式错误 | 检查通过；231 个 Python 文件格式通过 | 通过 |
| mypy | 无类型错误 | 165 个源文件无问题 | 通过 |
| compileall | Python 文件可编译 | 通过 | 通过 |
| 依赖锁 | 锁文件一致 | `uv lock --check` 解析 125 个包 | 通过 |
| Python 依赖审计 | 无已知漏洞 | 124 个锁定包无已知漏洞和不利状态 | 通过 |
| 前端 lint/typecheck | 无规则与类型错误 | 均通过 | 通过 |
| 前端测试 | 既有交互和安全契约不退化 | 32/32 通过 | 通过 |
| 前端生产构建 | 可生成生产产物 | Next.js 15.5.23 构建成功，14 个页面条目生成 | 通过 |
| Compose 配置 | 配置可解析 | `docker compose config --quiet` 通过 | 通过 |
| 当前运行态健康 | `/v1/health` 返回 200，backend healthy | 健康请求 20 秒超时；backend 已连续 884 次健康检查失败并处于 `unhealthy` | **环境失败** |
| 低敏扫描 | 不出现硬编码凭证和评测明文结果 | 60 个相关文件中密钥模式 0、禁止结果字段 0 | 通过 |
| 前端生产依赖审计 | 无 High 漏洞 | PostCSS/Sharp 共 3 个 High；自动修复要求升级 Next 16 | **失败；既有缺陷** |

两个 pytest 警告来自 Starlette `TestClient`/httpx 兼容弃用提示和 passlib 读取 argon2 版本属性的弃用提示，不是本轮新增缺陷。

### 6.1 主要复现命令

在 `CRM智能聊天系统/backend/` 执行：

```text
$env:LLM_LIVE_EVAL='false'; .venv/Scripts/python.exe -m pytest --rootdir=. -q ../../测试工程师/evidence/REAL-AI-04-005/test_real_ai04_provider_boundary.py
$env:LLM_LIVE_EVAL='false'; .venv/Scripts/python.exe -m pytest --rootdir=. -q tests/test_real_ai04_regressions.py tests/test_agent_phase4.py tests/test_agent_workflow.py tests/test_knowledge_safety_metadata.py tests/test_marketing_review_idempotency.py tests/test_real_model_evaluation.py tests/test_real_model_evaluation_remediation.py ../../测试工程师/evidence/REAL-AI-04-003 ../../测试工程师/evidence/REAL-AI-04-004
$env:LLM_LIVE_EVAL='false'; .venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m scripts.evaluate_phase4 --dataset evals/agent-phase4-v1.0.0.jsonl --output ../../测试工程师/evidence/REAL-AI-04-005/fixed-eval-result.json
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
.venv/Scripts/python.exe -m mypy app scripts
uv lock --check
uv audit --locked
```

隔离数据库使用项目 `scripts/run-postgres-integration-tests.ps1` 创建临时 PostgreSQL 16 + pgvector 环境并自动清理；迁移另行验证 `001→023` 和 `023→022→023`。前端执行 `npm run lint`、`npm run typecheck`、`npm run test`、`npm run build` 和：

```text
npm audit --omit=dev --audit-level=high --registry=https://registry.npmjs.org
```

## 7. 缺陷与观察

### DEF-REAL-AI04-005：真实 Provider 最终边界未注册 REAL-AI-04 业务系统 Prompt

| 项目 | 内容 |
| --- | --- |
| 优先级 | **P1** |
| 类型 | 功能、集成、安全边界配置 |
| 状态 | **Open** |
| 是否阻断 | **是；阻断 REAL-AI-04 真实 Provider 草稿、生产翻译、营销草稿及后续公开 AI** |
| 建议负责 Agent | AIAgent开发工程师Agent |

复现步骤：

1. 使用产品真实 `DeepSeekProvider` 和 `StructuredGenerationService` 构造翻译、营销生成或 FAQ/工具回复请求。
2. 系统 Prompt 使用产品模块中定义的固定常量，例如 `TRANSLATION_SYSTEM_PROMPT` 或 `MARKETING_COPY_SYSTEM_PROMPT`。
3. 请求进入 `StructuredGenerationRequest` 的最终安全校验。
4. 观察 `evaluate_system_prompt_safety()` 的注册表仅识别 Provider 契约、合成演示和 REAL-AI-05 评测三个 Prompt。

实际结果：

- REAL-AI-04 八类业务 Prompt 均返回 `UNTRUSTED_SYSTEM_PROMPT_REQUIRES_REGISTRY`。
- 翻译和营销公开服务返回 `LLM_REFUSAL`。
- 请求在 SDK 前失败，网络客户端调用数为 0。
- REAL-AI-05 专用评测 Prompt 可以通过，形成“评测链路可调用、真实业务链路不可调用”的集成断层。

预期结果：

- 项目固定业务 Prompt 应使用显式名称、版本、用途和内容摘要注册，并由调用场景精确选择。
- 任意调用方传入的未知系统 Prompt 仍必须默认拒绝。
- 注册业务 Prompt 后必须增加真实 Provider 边界测试，分别覆盖回复、翻译、营销生成与营销复核。
- 不得通过关闭最终安全校验、允许任意字符串或复用评测上下文来修复。

代码证据：

- `backend/app/agent/security.py:756`：系统 Prompt 最终安全判定。
- `backend/app/agent/security.py:762`、`:768`、`:774`：仅有三个精确允许分支。
- `backend/app/agent/security.py:790`：其余 Prompt 统一返回未注册。
- `backend/app/agent/providers/base.py:48`：请求构造时执行该判定。
- `backend/app/agent/translation.py:84`、`backend/app/agent/marketing_generation.py:135`、`:167`：实际业务 Prompt 进入 Provider。

### ENV-REAL-AI04-005-01：本地真实评测配置漂移导致 Settings 失败关闭

| 项目 | 内容 |
| --- | --- |
| 类型 | 环境配置、运行门禁 |
| 状态 | Open |
| 是否阻断 | 阻断当前本地环境的真实评测和新进程启动；不作为产品代码缺陷 |
| 建议负责 Agent | AIAgent开发工程师Agent、全栈开发工程师Agent、环境运维人员 |

当前 `.env` 的低敏状态为：

```text
APP_ENV=development
LLM_ENABLED=true
LLM_LIVE_EVAL=true
LLM_INPUT_PRICE_PER_MILLION=<unset>
LLM_OUTPUT_PRICE_PER_MILLION=<unset>
LLM_PRICING_VERSION=<unset>
LLM_PRICING_BASIS=<unset>
AI_TRANSLATION_ENABLED=true
AI_MARKETING_ENABLED=false
AUTO_REPLY_ENABLED=false
```

整改后的 Settings 会正确拒绝缺少价格治理信息的真实评测配置。这是安全的失败关闭，但当前环境因此不能直接启动或收集测试。应由环境主责人员填入架构师批准的价格快照和版本，或在非真实评测环境显式关闭 `LLM_LIVE_EVAL`；测试工程师未代填商业价格，也未修改用户 `.env`。

### ENV-REAL-AI04-005-02：当前 backend 容器不健康

当前项目 Compose 中 PostgreSQL、Redis、MinIO 和前端为 healthy，worker/jobs 运行，但 backend 容器为 `unhealthy`。`/v1/health` 请求 20 秒超时，容器健康日志连续 884 次显示 3 秒读取超时。本轮没有重启或替换用户现有长期运行容器，因此登记为运行环境问题；在进入下一轮联调前必须由全栈工程师定位并恢复健康。

## 8. 既有缺陷复测结论

### 8.1 DEF-P4-AI-008/009

- `DEF-P4-AI-008`：237 条固定评测零危险逃逸，业务安全和工作流回归通过，保持 **Closed**。
- `DEF-P4-AI-009`：既有知识安全、开放集和工作流回归通过，保持 **Closed**。

这两项关闭表示确定性声明和安全矩阵没有回归，不表示真实业务 Provider 链路已通过。

### 8.2 DEF-REAL-AI04-001～004

- `DEF-REAL-AI04-001`：SSE 结果交付前断开/取消不伪装成功，保持 Closed。
- `DEF-REAL-AI04-002`：安全营销候选进入人工审核且不发送，保持 Closed。
- `DEF-REAL-AI04-003`：审核幂等重放和冲突规则保持通过，保持 Closed。
- `DEF-REAL-AI04-004`：并发相反决定只有一个终态，保持 Closed。

### 8.3 REAL-AI-05 首次报告问题的影响

本轮不代替 REAL-AI-05 缺陷专项复测，也不关闭其 001 号报告中的缺陷。可以确认的是：整改新增的评测 Prompt 注册已经生效，但该注册没有覆盖 REAL-AI-04 的生产业务 Prompt，直接暴露 `DEF-REAL-AI04-005`。REAL-AI-05 是否通过，仍须由测试工程师按其任务范围另行生成复测报告。

## 9. 代码与安全审查结论

- Provider 对未知系统 Prompt 失败关闭，安全默认值正确，没有发现因本缺陷造成的数据泄漏或平台副作用。
- 当前问题不能通过放宽默认拒绝规则解决；应建立版本化业务 Prompt 注册表和调用场景绑定。
- 业务 Prompt 注册必须与 Prompt 版本、结构化 Schema、脱敏策略和输出用途共同审计，防止评测信封被业务路径滥用。
- 翻译和营销服务在当前真实 Provider 配置下不可用；现有 Stub/确定性测试不能作为真实 Provider 集成成功的证据。
- `.env.example` 和生产开关仍应保持公开回复、营销和自动回复关闭，直到本缺陷及其专项复测完成。
- 低敏扫描未发现硬编码 DeepSeek Key、Token 或评测明文结果进入相关代码/证据。

## 10. 其他未关闭生产风险

1. 官方 npm 审计仍检出 Next.js 间接依赖 PostCSS 与 Sharp 共 3 个 High，属于既有 `DEF-REAL-FS01-005`；自动修复建议升级 Next 16，需由全栈和架构师评估兼容性，测试工程师未执行 `--force`。
2. 当前 backend 容器不健康，运行态健康门禁失败。
3. 当前 `.env` 的真实评测价格治理字段不完整，新进程会正确失败关闭。
4. REAL-AI-05 真实模型质量、成本和开放集问题需单独复测，本报告不作关闭结论。
5. 真实 DeepSeek 50 客户端 SSE 性能、首包、P99 和五日稳定性尚未完成最终放行。
6. 真实 TikTok 店铺 OAuth、Webhook、人工消息和回滚仍需联合生产验收。
7. 当前不是 Git 仓库，缺少提交级不可变发布候选。

## 11. 最终结论

**REAL-AI-04 第五次独立综合测试：不通过。**

- 新增 `DEF-REAL-AI04-005`（P1/Open）：REAL-AI-04 八类真实业务系统 Prompt 均未进入 Provider 可信注册表，回复、翻译和营销请求在 DeepSeek SDK 前统一失败。
- REAL-AI-05 评测 Prompt 可以通过，证明当前修复只打通了评测专用链路，不能代表真实业务链路可用。
- `DEF-P4-AI-008/009` 与 `DEF-REAL-AI04-001～004` 保持 Closed；确定性安全、幂等、并发和零发送边界没有回归。
- 1292 项默认后端、1304 项隔离 PostgreSQL、237 条固定评测、迁移、静态质量、Python 依赖、32 项前端测试和生产构建通过。
- 当前 backend 容器不健康，前端生产依赖仍有 3 个 High，本地真实评测配置也未完成价格治理字段。

在 `DEF-REAL-AI04-005` 由测试工程师独立复测关闭前，不得开启生产翻译、AI 营销内容、公开 AI 回复、自动回复或 AI 触发的平台写操作。建议修复后至少执行八类业务 Prompt 的真实 Provider 最终边界测试、翻译/营销服务调用测试、未知 Prompt 负向测试、全量回归和一次受控真实 DeepSeek 合成请求。

## 12. 清理与交接

- 项目脚本创建的一次性 PostgreSQL 测试服务已自动删除，合成数据库使用 `tmpfs`，没有影响用户现有 PostgreSQL 数据。
- 本轮没有重启或修改用户现有 Compose 服务；backend 的不健康状态原样保留并登记。
- 测试工程师临时 pytest、mypy 和 uv 缓存将在报告复核后清理，仅保留 `测试工程师/evidence/REAL-AI-04-005/` 下的独立探针和低敏评测汇总。
- 本报告作为 REAL-AI-04 当前最新权威测试结论；001～004 号报告保留历史缺陷追溯。
