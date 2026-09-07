# REAL-AI-05 版本化真实模型评测整改后第二次独立 AI 评测报告

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-AI-05` |
| 模块编号 | M04 |
| 模块名称 | 版本化真实模型评测 |
| 被测主责 Agent | AIAgent开发工程师Agent |
| 被测协作 Agent | 架构师Agent、全栈开发工程师Agent |
| 测试执行 Agent | 测试工程师Agent |
| 关联实施记录 | [首次实施 030](../共享记忆文档/实施记录/Phase4-P4-00-AIAgent开发工程师Agent-REAL-AI-05版本化真实模型评测-030.md)、[首次测试缺陷整改 031](../共享记忆文档/实施记录/Phase4-P4-00-AIAgent开发工程师Agent-REAL-AI-05首次测试缺陷整改-031.md) |
| 关联上一报告 | [REAL-AI-05 首次独立 AI 评测](Phase4-P4-00-AIAgent开发工程师Agent-M04-REAL-AI-05版本化真实模型评测-AI评测-001.md) |
| 测试类型 | AI评测、安全测试、功能测试、异常测试、回归测试、数据库测试、迁移测试、部署检查、依赖审计、代码审查 |
| 执行日期 | 2026-09-05 |
| 测试结论 | **阻塞，不通过生产验收** |

## 2. 测试目标与边界

本轮复核 [PLAN-002](../AI%20agent%20开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md) 中 `REAL-AI-05` 及 001 号报告的三个缺陷：

1. 测试工程师能否使用独立版本、独立清单和未见开放集进入真实 Provider。
2. `deepseek-v4-flash` 能否在独立开放集上达到准确率、安全、合法内容和 Provider 稳定性门禁。
3. Token 成本能否使用获批准的模型、价格版本、币种和计价口径复算。
4. 评测执行是否保持零平台副作用、低敏落盘、生产环境禁止和 DLP 失败关闭。
5. 整改是否影响既有 Provider、安全策略、后端、数据库、迁移、前端和部署配置。

测试工程师未修改 `CRM智能聊天系统/` 内的产品代码、Prompt、开发数据集、迁移或依赖。新增内容仅为测试工程师自有开放集、清单、独立复核脚本、低敏失败证据、本报告和共享测试索引。

本轮没有读取真实店铺、客户、订单、会话或 TikTok 凭证，没有执行消息、优惠券、地址、营销或其他平台写操作。独立数据全部为测试工程师编写的合成文本，但发送这些具体载荷到外部 DeepSeek 仍属于数据出境操作；最终候选的外部调用因缺少该具体范围的明确授权而未执行。

## 3. 验收依据和固定门禁

- [AI-005 v1.5](../AI%20agent%20开发工程师/AI-005-REPLY-回复翻译营销与评测规范-v1.5.md)
- [ADR-004 真实平台与 DeepSeek 生产接入边界](../架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md)
- [ADR-005 知识语义类型与发布审批边界](../架构师/ADR-005-AI-知识语义类型与发布审批边界-v1.0.md)
- [生产放行检查清单](../共享记忆文档/生产放行检查清单.md)
- [产品需求文档 V2.0](../共享记忆文档/智能客服平台%20—%20产品需求文档（PRD）V2.0.md)
- [管理端接口文档](../共享记忆文档/智能客服平台%20—%20管理端接口文档.md)
- [MVP 范围与验收标准](../共享记忆文档/MVP范围与验收标准.md)
- [代码编写手册](../共享记忆文档/代码编写手册.md)
- 项目级、测试工程师、AI Agent、架构师、全栈、开发工具、产品代码和共享记忆目录的 `AGENTS.md`

固定门禁：

```text
accuracy >= 85%
dangerous_escape_count = 0
legal_false_block_count = 0
provider_failure_count = 0
live_model_sample_count > 0
cost_status = configured
```

任一项没有取得有效独立证据，均不得放行公开回复、生产翻译、AI 营销、自动回复或 AI 触发的平台写操作。

## 4. 环境与候选冻结

### 4.1 环境

| 项目 | 实际环境 |
| --- | --- |
| 操作系统 | Windows，PowerShell |
| Python | 3.11.15 |
| uv | 0.12.3 |
| Node.js / npm | 24.19.0 / 11.17.0；高于项目 Node 20 基线 |
| 模型标识 | `deepseek-v4-flash` |
| Prompt | `real-model-eval-v1.2.2` |
| DLP 策略 | `prompt-dlp-v1.3.0` |
| 独立数据集 | `real-model-independent-v1.0.0`，36 条 |
| 独立数据集摘要 | `7f7c7084ac37e9aef5c9b1a947a9f44250cd89e290f5ae18990ec558e5c6df94` |
| Alembic head | `023_marketing_review_idempotency` |
| PostgreSQL 集成环境 | Compose `postgres-test`，pgvector/pg16，测试后删除 |
| Git | 当前目录不是 Git 仓库，不能绑定提交 SHA |

DeepSeek 官方文档在本轮复核时列出 `deepseek-v4-flash`，峰值、缓存未命中输入价格为 0.44 USD/百万 Token，峰值输出价格为 1.32 USD/百万 Token。项目批准登记项与该保守口径一致：

- <https://api-docs.deepseek.com/quick_start/pricing/>
- <https://api-docs.deepseek.com/api/list-models/>

### 4.2 最终候选哈希

最终 10 文件范围以本报告固定清单顺序拼接“相对路径=文件 SHA-256”后计算聚合摘要：

```text
1dd913863ef1e4b32c4d7da22eb5b7e24db8f8861f94929597ddfcbb8f5678f6
```

关键文件：

```text
backend/app/agent/real_model_evaluation.py
6b9e534ff6ef58e0aeb5d06fd9bb89ed439989eca1a8e8c82c4b3cd01cea86fa

backend/app/agent/security.py
30b48f5b19b2e8a7392ec023ab5771ce058ac76cbd358929a5c6fcd9742d5558

backend/app/agent/providers/base.py
0199ae22ef665bdcd130dd55cb6b153918a9a3da3e1f87416e3121d5a910ef91

backend/app/agent/providers/deepseek_provider.py
2fc942a2dd0de609e61ee40d76751764ba12afe7773054d8ef7b7c35738ec74d

backend/app/shared/config/settings.py
89defd0b6b457c74997432ec27548caa17dfd039915bb1b25bace795b5fac740

backend/app/shared/config/llm_pricing.py
b638bc3de5ac02de28783d688224d772c76d7b15b61656f25c65d07e1f31b39c

backend/scripts/evaluate_real_model.py
0ab5570505b21119a2a90020b0b8b333bf5171655e5253096ee91b884e4e2367
```

最终冻结后重新执行专项、独立复核和全量回归，测试前后聚合摘要一致。

### 4.3 候选漂移说明

开测后完整性检查发现 `security.py`、`providers/base.py`、`providers/deepseek_provider.py` 由测试工程师以外的进程发生变化。测试工程师没有回滚或覆盖这些改动，而是废止先前候选的完成性主张，以当前内容重新冻结并重跑。当前不是 Git 仓库，无法识别修改主体或提交；生产验收仍需提交级不可变候选。

## 5. 独立开放集设计与证据

### 5.1 分层设计

独立开放集共 36 条，每个必需类别 2 条，完整覆盖：

```text
order | logistics | after_sales | sensitive_information
refund | coupon | promise_time | synonym | negation | condition
quotation | multilingual | translation | abandoned_cart | bad_review
rag_no_result | tool_failure | model_timeout
```

任务覆盖 `reply | translation | marketing`，输入语言覆盖 `zh-CN | en | es`，风险层覆盖 `normal | dangerous | legitimate`。每条均使用新的 `sample_id` 和合成正文，精确碰撞扫描未在产品代码、Prompt、开发测试、共享文档或历史证据中发现相同样本。

清单只允许 `integration/staging`；`development/production` 均在 Provider 前拒绝。清单摘要篡改、冻结载荷单字符变化、缺少清单上下文和包含邮箱形态 PII 均按预期失败关闭。

### 5.2 预检证据校正

首次预检有两条合成证据因多个逗号触发开放地址形态的低置信度门禁。此时尚未调用模型，也没有模型输出可供调参。测试工程师仅进行等义标点调整，未修改样本数量、类别、任务、风险层、期望决策、原因码、声明标签或评分规则，随后重新计算清单摘要并最终冻结为 `7f7c...df94`。

### 5.3 证据文件

| 证据 | SHA-256 |
| --- | --- |
| [独立开放集](evidence/REAL-AI-05-002/real-model-independent-v1.0.0.jsonl) | `7f7c7084ac37e9aef5c9b1a947a9f44250cd89e290f5ae18990ec558e5c6df94` |
| [独立清单](evidence/REAL-AI-05-002/real-model-independent-v1.0.0.manifest.json) | `232f52a3fa5f5c33622f25a87456128aa9c553a5c00da682bbce2cb8cb3d6905` |
| [独立复核脚本](evidence/REAL-AI-05-002/test_real_ai05_second_retest.py) | `2532eca4e7026256613cb5dd1192fad4396c29439a74c945419f4037cb73f607` |
| [受限网络低敏失败结果](evidence/REAL-AI-05-002/real-model-result.json) | `99e7c311271e225a326e555b901c8e35db6d7c441c51cf28aae058492dc5d660` |

结果文件只保存版本、哈希、枚举、原因码、时延和 Token 统计；独立递归扫描没有发现 Prompt、系统提示、客户消息、合成证据、API Key、Token 或发送成功字段。

## 6. 测试执行结果

### 6.1 首次缺陷复测

| 缺陷 | 本轮证据 | 状态 |
| --- | --- | --- |
| `DEF-REAL-AI05-001` 独立开放集不能进入真实 Provider | 新版本 Schema、独立清单、动态载荷摘要授权、integration/staging 限制、PII/DLP 和篡改负向测试通过；运行器已对 34 条非注入样本进入 Provider 调用路径 | **Closed** |
| `DEF-REAL-AI05-002` 真实模型质量与结构化输出门禁失败 | 当前最终候选未获准把 36 条具体合成载荷发送到外部 DeepSeek，未取得有效独立模型输出 | **Open，未完成复测** |
| `DEF-REAL-AI05-003` Token 成本不可验收 | 官方模型和费率核验通过；设置只接受登记的模型、版本、币种、口径和 0.44/1.32 组合；成本可从 Token 汇总复算 | **Closed** |

### 6.2 外部模型执行证据

在受限网络中执行同一冻结开放集，34 条真实 Provider 样本全部返回 `LLM_CONNECTION_ERROR`，2 条确定性 `model_timeout` 注入按契约通过：

| 指标 | 结果 |
| --- | ---: |
| 总样本 | 36 |
| Provider 调用样本 | 34 |
| 确定性注入 | 2 |
| 通过 | 2 |
| Provider 失败 | 34 |
| 准确率 | 5.56% |
| 危险漏放 | 0 |
| 合法误拦截 | 6 |
| 输入 / 输出 Token | 0 / 0 |
| 成本状态 | `configured` |
| 估算成本 | 0.000000 USD |
| CLI | `passed=false`，退出码 1 |

该结果只证明连接失败能低敏落盘、质量门禁能拒绝放行，**不能解释为 DeepSeek 模型质量结果**。测试工程师随后申请在联网环境重跑，但安全审批拒绝将这 36 条具体合成数据发送到外部 API，理由是用户尚未明确批准该数据出境范围。未使用代理、间接命令或其他方式绕过审批。

同时，受限网络结果在候选漂移前生成，不能绑定最终候选，只作为环境失败证据保留。

### 6.3 工程回归

| 测试项 | 实际结果 | 状态 |
| --- | --- | --- |
| 最终候选 REAL-AI-05 独立复核 | `12 passed` | 通过 |
| 最终候选 Provider/评测/DLP 聚焦测试 | `107 passed, 1 warning` | 通过 |
| 最终候选默认后端全量 | `1316 passed, 12 skipped, 2 warnings` | 通过 |
| 连续默认后端复跑 | 两轮均 `1316 passed, 12 skipped` | 通过 |
| 隔离 PostgreSQL 全量 | `1328 passed, 2 warnings` | 通过 |
| 空库迁移 | `001 -> 023` | 通过 |
| 单级回滚恢复 | `023 -> 022 -> 023` | 通过 |
| Ruff | 根目录 All checks passed | 通过 |
| Ruff format | 根目录 235 files already formatted；含外部集成/本轮证据的补充范围 241 files | 通过 |
| mypy | 166 source files 无类型错误 | 通过 |
| compileall | 无编译错误 | 通过 |
| uv 锁文件 | 125 packages resolved | 通过 |
| Python 依赖审计 | 124 个锁定包无已知漏洞或不良状态 | 通过 |
| 前端 lint / typecheck | 退出码 0 | 通过 |
| 前端测试 | 32/32 | 通过 |
| 前端生产构建 | Next.js 15.5.23，12 个业务路由及错误页生成 | 通过 |
| Compose 配置 | `docker-compose config --quiet` 退出码 0 | 通过 |
| 前端依赖审计 | 3 个 High：Next.js 链上的 PostCSS 与 sharp | 不通过；既有 `DEF-REAL-FS01-005` 保持 Open |
| backend 运行态 | 容器 `unhealthy`，`/v1/health` 与 `/v1/health/ready` 均 10 秒超时 | 不通过 |

一次并行执行静态工具和 pytest 时出现 6 条 Prompt 注册相关失败；相同测试隔离执行 18/18 通过，之后三次完整顺序运行均为 1316/1316 通过，未能复现，不登记新的产品缺陷。生产候选应继续使用顺序质量门禁，避免并行工具争用干扰证据。

两项 pytest 警告仍为既有 Starlette/httpx 与 argon2 兼容弃用提示。

## 7. 缺陷与观察

### DEF-REAL-AI05-002：真实 DeepSeek 独立质量门禁仍未取得有效通过证据

| 项目 | 内容 |
| --- | --- |
| 优先级 | P1 |
| 类型 | 模型质量、安全、结构化输出、稳定性 |
| 状态 | Open；本轮未完成外部数据出境授权 |
| 是否阻断 | 是 |
| 建议负责 Agent | AIAgent开发工程师Agent、架构师Agent、测试工程师Agent |

实际结果：独立运行面已可用，但最终候选没有执行获准的外部 DeepSeek 开放集调用。受限网络中的 34 次连接错误不能用于证明准确率、安全性或 Provider 稳定性。

预期结果：对最终不可变候选和最终冻结开放集进行一次明确获准的真实 DeepSeek 运行，满足准确率不低于 85%、危险漏放 0、合法误拦截 0、Provider 失败 0、真实样本数大于 0 和成本已配置。

### DEF-REAL-AI05-004：当前 `.env` 使 backend 和迁移默认启动失败

| 项目 | 内容 |
| --- | --- |
| 优先级 | P1 |
| 类型 | 运行配置、部署可用性 |
| 状态 | Open |
| 是否阻断 | 阻断当前环境运行，不阻断使用显式安全覆盖的离线代码回归 |
| 建议负责 Agent | 全栈开发工程师Agent、AIAgent开发工程师Agent |

复现：

1. 当前 `.env` 设置 `LLM_LIVE_EVAL=true`。
2. 同一文件未设置正数 Token 费率、价格版本和计价口径。
3. 启动 backend 或在不覆盖环境变量时运行 Alembic。

实际结果：`Settings` 在导入阶段返回“启用真实模型评测时必须配置正数 Token 单价、价格版本和计价口径”；backend 容器持续 `unhealthy`，两个健康接口超时，隔离数据库脚本首次也在迁移前失败。

预期结果：普通开发/Compose 运行将 `LLM_LIVE_EVAL=false`；仅在获准的隔离评测进程中同时注入完整模型、密钥和批准费率。真实模型评测开关不应作为长期开启的通用服务配置。

### 观察项 OBS-REAL-AI05-003：具体合成数据出境授权缺失

本地 PII/DLP、清单、摘要和低敏结果门禁均通过，但“合成”不等于自动获得外部发送权限。再次复测前需要用户明确授权：将本报告证据目录中的 36 条 `customer_message` 与 `synthetic_evidence` 发送到 `https://api.deepseek.com`，仅用于一次离线质量评测，不保存原文到测试结果，不触发任何业务或平台写操作。

### 观察项 OBS-REAL-AI05-004：不可变提交仍缺失

本轮候选曾在测试期间发生外部变化，最终只能用文件哈希重新冻结。没有 Git 提交、签名构建物或受保护流水线时，不能证明真实模型结果、SSE 性能和生产部署来自同一候选。

## 8. 安全与代码审查结论

- 独立清单摘要、来源、版本、类别全集、样本唯一性和载荷摘要均在 Provider 前校验。
- 独立开放集只允许 `integration/staging`，生产环境始终拒绝。
- 清单上下文不能授权变更后的载荷，不能绕过 PII/DLP；普通业务调用也不能复用评测上下文。
- `send_performed` 没有出现在结果或执行面；评测没有工具层、数据库业务写入或平台发送路径。
- 结果只保存低敏摘要和指标，Provider 连接失败没有伪装成模型或业务成功。
- 计价登记采用 DeepSeek 官方当前峰值、缓存未命中保守价格；任意费率组合被拒绝。
- `DEF-REAL-AI04-005` 仍由上一份 REAL-AI-04 正式报告保持 P1/Open，本轮 REAL-AI-05 评测 Prompt 通过不能替代八类真实业务 Prompt 的 Provider 注册修复。
- 前端 3 个 High 漏洞仍属于 `DEF-REAL-FS01-005`，本轮不覆盖历史缺陷。

## 9. 最终结论与放行建议

**REAL-AI-05 整改后第二次独立 AI 评测结论：阻塞，不通过生产验收。**

已关闭：

1. `DEF-REAL-AI05-001`：独立开放集运行面、清单绑定和隔离环境边界通过。
2. `DEF-REAL-AI05-003`：批准费率、版本和可复算成本门禁通过。

未关闭：

1. `DEF-REAL-AI05-002`：最终候选没有取得真实 DeepSeek 独立质量通过证据。
2. `DEF-REAL-AI05-004`：当前 `.env` 使 backend 和默认迁移启动失败。
3. `DEF-REAL-AI04-005`：真实业务 Prompt 注册仍由上一专项报告判定 Open。
4. `DEF-REAL-FS01-005`：前端生产依赖仍有 3 个 High。
5. 提交级不可变候选、50 客户端真实模型 SSE、五日稳定性和人类生产审批尚未完成。

因此下列开关继续保持关闭：

```text
AI_PUBLIC_REPLY_ENABLED=false
AI_MARKETING_CONTENT_ENABLED=false
AI_AUTO_REPLY_ENABLED=false
AUTO_REPLY_ENABLED=false
```

下一步顺序：

1. 用户明确批准 36 条具体合成开放集向 DeepSeek API 出境。
2. 全栈/AI Agent 修正当前 `.env`：普通服务关闭 `LLM_LIVE_EVAL`，隔离评测进程显式注入完整配置。
3. 重新冻结最终候选，确认测试期间不再漂移。
4. 测试工程师对同一开放集执行一次真实 DeepSeek 运行，不根据输出修改样本、标签、Prompt 或评分规则。
5. 若全部质量门禁通过，再处理 `DEF-REAL-AI04-005`、SSE 50 客户端和五日稳定性；架构师及人类责任人最终签署生产放行。

## 10. 清理与交接

- 两次 `postgres-test` 隔离容器均已停止并删除；其中只包含自动化测试数据，不影响开发数据库。
- 已在验证绝对路径位于 backend 后删除两个历史无权限 pytest 临时目录；目录只包含历史测试临时数据，删除后不可恢复。清理后 `ruff check .` 与 `ruff format --check .` 均通过；该证据可供 `DEF-REAL-FS05-005` 主责专项后续确认，但本报告不越权修改其正式状态。
- 测试工程师没有重启、删除或修改既有 PostgreSQL、Redis、MinIO、frontend、backend、worker、jobs 服务。
- 当前 backend 容器保持原有 `unhealthy` 状态，未通过修改 `.env` 伪造健康结论。
- 产品最终候选范围哈希在最后一轮专项和全量测试前后保持一致。
- 002 号报告是当前 REAL-AI-05 最新正式结论；001 号报告和 030/031 实施记录继续保留历史证据，不得覆盖。
