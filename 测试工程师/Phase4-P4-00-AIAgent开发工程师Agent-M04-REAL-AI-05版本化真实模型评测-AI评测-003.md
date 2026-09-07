# REAL-AI-05 版本化真实模型评测整改后第三次独立 AI 评测报告

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
| 关联实施记录 | [REAL-AI-05 二次测试配置隔离整改 033](../共享记忆文档/实施记录/Phase4-P4-00-AIAgent开发工程师Agent-REAL-AI-05二次测试配置隔离整改-033.md) |
| 关联上一报告 | [REAL-AI-05 第二次独立 AI 评测](Phase4-P4-00-AIAgent开发工程师Agent-M04-REAL-AI-05版本化真实模型评测-AI评测-002.md) |
| 测试类型 | AI评测、安全测试、配置测试、异常测试、回归测试、数据库测试、迁移测试、部署检查、依赖审计、代码审查 |
| 执行日期 | 2026-09-05 |
| 测试结论 | **阻塞，不通过生产验收；`DEF-REAL-AI05-004` Closed，`DEF-REAL-AI05-002` 保持 Open** |

## 2. 测试目标与边界

本轮在 AIAgent开发工程师Agent完成 002 号报告问题整改后，独立验证：

1. 项目根环境是否恢复 `LLM_LIVE_EVAL=false`，普通服务和 Alembic 是否不再要求一次性真实评测计价元组。
2. backend、worker、jobs、agent-worker 和 retrieval-model-service 是否都在 Compose 中显式关闭真实评测开关。
3. 获准的 `integration/staging` 隔离进程是否仍可使用完整、已登记的价格配置开启评测，生产环境是否继续失败关闭。
4. 既有独立开放集清单、载荷摘要、PII/DLP、低敏结果和成本复算边界是否保持有效。
5. 整改是否影响 Provider、安全规则、后端、数据库、迁移、前端、运行健康和依赖安全。
6. 最终候选是否已经取得真实 DeepSeek 独立质量通过证据。

测试工程师没有修改 [产品代码目录](../CRM智能聊天系统/)、Prompt、开发数据集、迁移、依赖锁文件或生产开关。新增内容仅为测试工程师自有独立配置探针、本报告和共享测试索引。

本轮没有读取真实店铺、客户、订单、会话或 TikTok 凭证，没有执行工具、消息、发券、地址、营销或其他平台写操作。没有把上一报告的 36 条合成开放集发送到 DeepSeek，因为尚未获得绑定具体数据集摘要、目标供应商和用途的一次性外部数据出境授权。

## 3. 验收依据与固定门禁

- [PLAN-002 REAL-AI-05](../AI%20agent%20开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md)
- [AI-005 v1.5](../AI%20agent%20开发工程师/AI-005-REPLY-回复翻译营销与评测规范-v1.5.md)
- [ADR-004 真实平台与 DeepSeek 生产接入边界](../架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md)
- [ADR-005 知识语义类型与发布审批边界](../架构师/ADR-005-AI-知识语义类型与发布审批边界-v1.0.md)
- [产品需求文档 V2.0](../共享记忆文档/智能客服平台%20—%20产品需求文档（PRD）V2.0.md)
- [管理端接口文档](../共享记忆文档/智能客服平台%20—%20管理端接口文档.md)
- [MVP 范围与验收标准](../共享记忆文档/MVP范围与验收标准.md)
- [代码编写手册](../共享记忆文档/代码编写手册.md)
- 项目级、测试工程师、AI Agent、架构师、全栈、开发工具、产品代码和共享记忆目录的 `AGENTS.md`

真实模型质量固定门禁：

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

### 4.1 测试环境

| 项目 | 实际环境 |
| --- | --- |
| 操作系统 | Windows，PowerShell |
| Python | 3.11.15 |
| uv | 0.12.3 |
| Node.js / npm | 24.19.0 / 11.17.0；高于项目 Node 20 基线 |
| Docker Compose | 5.3.1 |
| 模型标识 | `deepseek-v4-flash` |
| Prompt | `real-model-eval-v1.2.2` |
| DLP 策略 | `prompt-dlp-v1.3.0` |
| 独立开放集 | `real-model-independent-v1.0.0`，36 条，沿用 002 号报告冻结版本 |
| Alembic head | `023_marketing_review_idempotency` |
| 开发数据库版本 | `022_ai_marketing_review` |
| PostgreSQL 集成环境 | 一次性 `postgres-test`，pgvector/pg16，测试后删除 |
| Git | 当前目录不是 Git 仓库，不能绑定提交 SHA |

DeepSeek 官方文档在 2026-09-05 复核时仍列出 `deepseek-v4-flash`。当前项目使用的保守计价口径与官方峰值、缓存未命中输入 0.44 USD/百万 Token和输出 1.32 USD/百万 Token一致：

- [DeepSeek Models & Pricing](https://api-docs.deepseek.com/quick_start/pricing/)
- [DeepSeek Lists Models](https://api-docs.deepseek.com/api/list-models)

### 4.2 最终候选哈希

当前没有 Git 提交。测试工程师以 11 个 REAL-AI-05 相关受测文件为固定顺序，按“相对路径=文件 SHA-256”拼接后计算聚合摘要。测试前后摘要一致：

```text
c65dd3cea0eab52ea1478001622befe9016e0573f3cb8ac0db405bfd1f646517
```

关键文件 SHA-256：

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
```

其余整改关键文件：

```text
backend/tests/test_real_runtime_config.py
ca5025ede82c98ecf86ff82fdcde77d1d1d029087cf3b7f06abf0edaf2b17fb7

docker-compose.yml
eb6985cdeee750c6f9ab21d466da0992868a804aed32656920443627d50fae8f

.env.example
b64d4a83e093f65eadd1981f8cb8a0206412520f71046f7886281c6399a8081a

README.md
971e051bb9df6937ef2d9900d5a910ee7deee5d3add258c1f91f6e7658105e97
```

根 `.env` 可能包含服务端密钥，因此不写入报告、不输出完整内容，也不计算可公开摘要。本轮只校验有效的 `LLM_LIVE_EVAL` 赋值精确为单个 `false`。

## 5. 独立测试设计与证据

新增独立探针：

```text
测试工程师/evidence/REAL-AI-05-003/test_real_ai05_third_retest.py
SHA-256: f66dc7054d0ea4bcb9097f1a2d7a78e7c6c29d535724d086e9424e02004ea039
```

该探针不调用外部网络，覆盖：

- 根 `.env` 只有一个有效 `LLM_LIVE_EVAL=false`。
- 五个常驻 Python 服务分别精确覆盖 `LLM_LIVE_EVAL: "false"`。
- 当前根环境可正常构造 `Settings`，不要求一次性计价元组。
- 开启真实评测但缺少费率时仍失败关闭。
- `integration` 隔离进程使用完整已登记费率时可创建配置。
- `production` 即使费率完整也拒绝开启离线真实模型评测。

首轮探针结果为 8 通过、2 失败。失败原因是测试探针遗漏 `integration` 环境强制要求的架构固定 TikTok OAuth 回调地址，先触发了无关配置门禁。测试工程师只在证据脚本的合成配置中补入固定回调地址，未修改产品代码、预期标签或真实评测规则；重跑结果为 `10 passed`。该首轮失败不登记为产品缺陷。

002 号报告的独立开放集、清单、低敏失败结果和 12 项复核脚本保持原样。当前候选的 Provider、评测执行器、安全规则和价格登记文件摘要与 002 号报告一致，没有证据表明开发侧在看到开放集后调整这些受测逻辑。

## 6. 测试执行结果

### 6.1 缺陷复测

| 缺陷 | 本轮证据 | 状态 |
| --- | --- | --- |
| `DEF-REAL-AI05-001` 独立开放集不能进入真实 Provider | 002 号冻结证据复核 `12/12`；清单、摘要、环境、PII/DLP 和低敏结果边界保持通过 | **Closed，保持关闭** |
| `DEF-REAL-AI05-002` 真实模型质量与结构化输出门禁失败 | 未获得针对具体开放集向 DeepSeek 外发的一次性授权；本轮真实模型样本数为 0 | **Open，阻断生产验收** |
| `DEF-REAL-AI05-003` Token 成本不可验收 | 价格登记与 DeepSeek 官方当前保守峰值口径一致；复算与错误费率拒绝测试保持通过 | **Closed，保持关闭** |
| `DEF-REAL-AI05-004` 根环境污染常驻服务和迁移 | 独立探针 10/10；五服务 Compose 解析均为 false；三个运行容器均为 false；健康和 Alembic 可达 | **Closed** |

### 6.2 工程与运行回归

| 测试项 | 实际结果 | 状态 |
| --- | --- | --- |
| 第三次独立配置探针 | `10 passed` | 通过 |
| 002 号冻结证据复核 | `12 passed` | 通过 |
| Provider、评测、DLP 和配置聚焦测试 | `177 passed, 1 warning` | 通过 |
| 默认后端全量 | `1321 passed, 12 skipped, 2 warnings` | 通过 |
| 隔离 PostgreSQL 全量 | `1333 passed, 2 warnings` | 通过 |
| 空库迁移 | `001 -> 023` | 通过 |
| 单级回滚恢复 | `023 -> 022 -> 023` | 通过 |
| Ruff | `ruff check .` 通过 | 通过 |
| Ruff format | 235 个文件格式正确 | 通过 |
| mypy | 166 个源文件无类型错误 | 通过 |
| compileall | 退出码 0 | 通过 |
| uv 锁文件 | 125 packages resolved | 通过 |
| Python 依赖审计 | 124 个锁定包无已知漏洞或不良状态 | 通过 |
| 前端 lint / typecheck | 退出码 0 | 通过 |
| 前端测试 | 32/32 | 通过 |
| 前端生产构建 | Next.js 15.5.23，12 个业务路由及错误页生成 | 通过 |
| Compose 配置 | `docker-compose config` 通过 | 通过 |
| 五服务 Compose 解析值 | backend、worker、jobs、agent-worker、retrieval-model-service 均为 `false` | 通过 |
| 运行容器环境 | backend、worker、jobs 均为 `LLM_LIVE_EVAL=false` | 通过 |
| `/v1/health` | `status=ok` | 通过 |
| `/v1/health/ready` | database、redis、object_storage 为 ok，llm_provider 为 ok | 通过 |
| 前端依赖审计 | 3 个 High：Next.js 依赖链中的 PostCSS 和 sharp | 不通过；既有 `DEF-REAL-FS01-005` 保持 Open |
| 真实独立 DeepSeek 评测 | 未执行，真实模型样本数为 0 | 阻塞 |

两个 pytest 警告为既有 Starlette/httpx 和 argon2 兼容弃用提示。npm 首次使用本机配置镜像时因镜像不实现审计 API 失败；指定官方 npm registry 后得到 3 个 High 的有效结果。

当前开发数据库仍为 `022_ai_marketing_review`，落后代码 head `023_marketing_review_idempotency`。隔离空库升级、回滚和恢复已通过，但测试工程师没有越权升级现有开发数据库。

## 7. 缺陷与观察

### DEF-REAL-AI05-002：真实 DeepSeek 独立质量门禁仍无有效通过证据

| 项目 | 内容 |
| --- | --- |
| 优先级 | P1 |
| 类型 | 模型质量、安全、结构化输出、稳定性 |
| 状态 | Open |
| 是否阻断 | 是 |
| 建议负责 Agent | AIAgent开发工程师Agent、架构师Agent、测试工程师Agent、人类数据责任人 |

实际结果：当前候选没有执行获准的外部 DeepSeek 开放集调用。本轮 `live_model_sample_count=0`，不能证明准确率、危险漏放、合法误拦截或 Provider 稳定性达到生产门禁。

预期结果：对固定候选和冻结开放集完成一次明确获准的真实 DeepSeek 运行，满足准确率不低于 85%、危险漏放 0、合法误拦截 0、Provider 失败 0、真实样本数大于 0 和成本已配置。

复测前授权必须明确以下范围：

```text
数据集：测试工程师/evidence/REAL-AI-05-002/real-model-independent-v1.0.0.jsonl
数据集 SHA-256：7f7c7084ac37e9aef5c9b1a947a9f44250cd89e290f5ae18990ec558e5c6df94
外发内容：36 条合成 customer_message 与 synthetic_evidence
目标供应商：https://api.deepseek.com
用途：一次 REAL-AI-05 离线质量评测
结果留存：只保存低敏哈希、枚举、原因码、时延、Token 和成本，不保存模型正文
副作用：禁止工具、数据库业务写入和任何平台发送
```

### 观察项 OBS-REAL-AI05-005：开发数据库落后代码 head

运行服务已恢复健康，但开发数据库仍为 022，代码 head 为 023。该差异不影响本轮隔离数据库证据，也不属于 AIAgent开发工程师Agent可自行升级的范围；应由全栈或数据库主责确认迁移窗口。

### 观察项 OBS-REAL-AI05-006：不可变发布候选仍缺失

当前目录不是 Git 仓库。本轮文件哈希在测试前后稳定，但哈希清单不能替代提交、签名构建物和受保护流水线。真实模型结果、SSE 性能和最终生产部署必须绑定同一不可变候选。

本轮没有新增 REAL-AI-05 产品缺陷。

## 8. 安全与代码审查结论

- 根环境和五个常驻服务对一次性真实评测采用双层关闭，避免评测授权扩大到普通 API、Worker、Jobs 和本地检索服务。
- 独立评测仍只允许 `integration/staging`，生产环境在配置阶段拒绝。
- 缺少费率、模型、价格版本或口径时继续失败关闭；任意自定义费率不能绕过登记项。
- 既有开放集清单、载荷摘要、PII/DLP 和低敏结果边界没有退化。
- 运行健康接口没有返回 API Key、模型凭证或客户数据。
- 本轮没有外部模型调用、业务工具调用、平台发送或业务数据库写入。
- `DEF-REAL-AI04-005` 已由 REAL-AI-04 006 号报告关闭，本轮不再列为 REAL-AI-05 当前阻断。
- 前端 3 个 High 漏洞仍属于 `DEF-REAL-FS01-005`，本报告不越权关闭。

## 9. 最终结论与放行建议

**REAL-AI-05 整改后第三次独立 AI 评测结论：阻塞，不通过生产验收。**

本轮确认：

1. `DEF-REAL-AI05-004` 已关闭。根环境、五服务 Compose 配置、运行容器、健康接口和 Alembic 可达性均恢复。
2. `DEF-REAL-AI05-001/003` 保持关闭。
3. `DEF-REAL-AI05-002` 保持 P1/Open。真实模型样本数仍为 0，不能把代码回归、无网络契约或历史连接失败结果解释为模型质量通过。
4. 未发现新的 REAL-AI-05 产品缺陷。

因此下列生产能力继续保持关闭：

```text
AI_PUBLIC_REPLY_ENABLED=false
AI_MARKETING_CONTENT_ENABLED=false
AI_AUTO_REPLY_ENABLED=false
AUTO_REPLY_ENABLED=false
```

后续固定顺序：

1. 人类数据责任人明确批准上文指定的 36 条合成开放集向 DeepSeek 外发。
2. 在 `integration/staging` 隔离进程中临时注入完整 Key 和已登记计价配置，不修改根 `.env`。
3. 重新校验候选聚合摘要和数据集摘要，不根据输出修改 Prompt、样本、标签或评分规则。
4. 执行一次真实 DeepSeek 开放集评测并保存低敏结果。
5. 若全部 REAL-AI-05 质量门禁通过，再进入真实模型 SSE 50 授权客户端、五日稳定性和人类生产审批。

## 10. 清理与交接

- 两次 `postgres-test` 临时容器均已停止并删除，仅包含自动化测试数据，不影响开发数据库。
- 测试工程师没有停止、重启、删除或修改现有 backend、frontend、postgres、redis、minio、worker 和 jobs 服务。
- 已核对绝对路径位于产品目录后，删除本轮创建的 `.uv-cache-test`、`.docker-config-test` 和三个残留的 `.pytest-real-ai05-003-*` 临时目录。目录只包含工具缓存或测试临时数据，删除后不可恢复；没有触碰产品代码、业务数据或历史测试证据。
- 产品候选聚合摘要在最后一轮测试后与开测前一致。
- 本报告是当前 REAL-AI-05 最新正式结论；001、002 号报告和 030、031、033 实施记录继续保留历史证据，不得覆盖。
