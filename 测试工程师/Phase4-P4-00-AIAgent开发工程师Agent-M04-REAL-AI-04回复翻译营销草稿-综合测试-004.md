# REAL-AI-04 回复、翻译和营销草稿第四次独立综合测试报告

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-AI-04`，继承复测 `REAL-AI-03` 的 `DEF-P4-AI-008/009` |
| 模块编号 | M04 |
| 模块名称 | 回复、翻译和营销草稿 |
| 被测主责 Agent | AIAgent开发工程师Agent |
| 被测协作 Agent | 架构师Agent、全栈开发工程师Agent |
| 测试执行 Agent | 测试工程师Agent |
| 关联实施记录 | `共享记忆文档/实施记录/Phase4-P4-00-AIAgent开发工程师Agent-结构化知识词法降级修复-029.md` |
| 关联上一报告 | `测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-REAL-AI-04回复翻译营销草稿-综合测试-003.md` |
| 测试类型 | 综合测试、修复验证、安全测试、AI评测、开放集测试、接口与集成测试、并发测试、数据库测试、迁移测试、回归测试、部署检查、代码审查 |
| 执行日期 | 2026-09-03 |
| 测试结论 | **有条件通过当前确定性工程范围** |

## 2. 测试目标与边界

本轮针对用户指定的 003 号报告修复结果重新审查，并验证：

1. `DEF-P4-AI-009` 的结构化知识词法降级修复是否消除合法技术资产和非断言命题误杀。
2. `DEF-P4-AI-008` 是否继续对无真实工具证据的客户实例事实失败关闭。
3. 已审批知识是否仍受店铺、文档版本、审批状态和语义类型约束。
4. 合法 FAQ 草稿是否最多进入人工复核，且始终保持 `send_performed=false`。
5. 003 号报告已关闭的 `DEF-REAL-AI04-001～004` 是否保持关闭。
6. 后端、前端、数据库迁移、依赖、安全配置和运行态是否出现回归。

本轮不调用真实 DeepSeek，不使用真实客户、订单、店铺凭证或平台消息，不执行真实 TikTok 写操作，也不评测真实模型回复、翻译或营销语言质量。公开 AI 回复、生产翻译、AI 营销发送、自动回复、50 客户端 SSE 压测和五日稳定性不在本轮已执行范围。

测试工程师未修改产品代码、开发测试、依赖锁文件、实施计划或历史测试报告；仅新增独立测试证据、本正式报告，并按规范更新共享测试报告索引。

## 3. 需求与验收依据

- `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md`
- `架构师/ADR-005-AI-知识语义类型与发布审批边界-v1.0.md`
- `共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`
- `共享记忆文档/智能客服平台 — 管理端接口文档.md` 第 11.16 节
- `共享记忆文档/MVP范围与验收标准.md`
- `共享记忆文档/代码编写手册.md`
- 项目级、测试工程师、AI Agent、产品代码和共享记忆目录的 `AGENTS.md`
- `测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-REAL-AI-03缺陷关闭-综合测试-010.md`
- `测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-REAL-AI-04回复翻译营销草稿-综合测试-003.md`

核心验收矩阵：

```text
policy / technical_artifact / non_assertive_proposition
+ 当前店铺 + 当前版本 + approved_for_internal_review
→ 保留安全草稿，最高 HUMAN_REVIEW，automatic_delivery_allowed=false

customer_instance_fact 且无同店铺、当次、非 Mock 的真实查询工具证据
→ TRANSFER_HUMAN，隐藏草稿，不发送

unknown / draft / 缺失 / 跨店铺 / 版本漂移 / 混合危险引用
→ 失败关闭，隐藏高风险草稿，不发送
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
| 数据库 | 一次性 `pgvector/pgvector:pg16`，仅绑定 `127.0.0.1:55641` |
| pgvector | 0.8.6 |
| Alembic head | `023_marketing_review_idempotency` |
| 隔离数据库 | 合成测试数据，数据库目录使用容器 `tmpfs` |
| Git | 当前产品目录不是 Git 仓库，不能声明提交级不可变基线 |

### 4.2 产品源文件聚合哈希

对 `backend/app`、`backend/migrations`、`backend/tests`、`tests/integration`、`frontend/app`、`frontend/components`、`frontend/lib`、`frontend/tests` 和主要依赖/部署清单共 250 个文件，按相对路径排序后计算聚合 SHA-256：

```text
396b7eddc0a1a1164e7aeffa74fbe77fac3466235ac51b9227b058b10e9a0f07
```

测试前后文件数和聚合哈希一致，证明本轮测试没有改变上述产品源文件。

关键修复文件 SHA-256：

```text
backend/app/agent/reply_safety.py
17ab780031723417c7992971c8629442cf5c9e95a0d39fde2fe070aab2bca7fb

backend/tests/test_knowledge_safety_metadata.py
68fedec8ddcd4aaee9fd1ce8746aa247777bf56e126c60beced0ee1c4ab855a8
```

## 5. 独立方法与测试证据

### 5.1 新未见开放集

本轮在读取实现规则后先冻结 48 条新的对称样本：

- 24 条客户实例危险事实：覆盖退款、赔偿、撤单资金、账户入账、钱包余额和最终结算的中英文变形。
- 24 条合法内容：12 条 `technical_artifact` 和 12 条 `non_assertive_proposition`，覆盖技术夹具、静态示例、引用、否定、条件、未证实和禁止承诺等语境。

冻结后对产品 `backend/app`、产品测试、010/003 既有证据、003 报告和 029 实施记录共 190 个文件执行完整字符串碰撞检查：

```text
frozen_samples=48
exact_collisions=0
```

另增加 7 个结构化元数据边界用例：混合安全/客户实例引用、跨店铺、草稿、未知类型、伪造版本漂移，以及 `None`/空列表两种元数据缺失。

证据文件：

```text
测试工程师/evidence/REAL-AI-04-004/test_real_ai04_fourth_retest.py
SHA-256: f2ad64292389bfc81b1e13a5a961ddf77744d57ff1de5995ce74b292ab8533e3

测试工程师/evidence/REAL-AI-04-004/fixed-eval-result.json
SHA-256: bf8c271c80443a4e1532cf034be63bb0b7683359136972cfe2f19dcdd98f9953
```

### 5.2 测试脚本校正说明

首次运行新证据时结果为 `53 passed, 2 failed`。两项失败均为测试脚本把项目统一原因码误写成不存在的 `KNOWLEDGE_SAFETY_NOT_APPROVED/KNOWLEDGE_SAFETY_UNKNOWN_TYPE`；产品实际已返回 `KNOWLEDGE_SAFETY_METADATA_UNAPPROVED`，并同时保持 `is_safe=false`。测试工程师仅修正独立证据的预期原因码，未改变样本、产品实现或安全预期。最终重跑为 `55 passed`，因此该过程不登记产品缺陷。

## 6. 测试执行结果

| 测试项 | 预期 | 实际结果 | 状态 |
| --- | --- | --- | --- |
| 新危险客户实例事实 | 无真实工具证据时零漏放 | 24/24 `TRANSFERRED`，草稿为空，`send_performed=false` | 通过 |
| 新合法技术/非断言内容 | 零误杀，保留草稿但只到人工复核 | 24/24 `HUMAN_REVIEW`，草稿完整，`requires_human=true`，零发送 | 通过 |
| 结构化元数据边界 | 任一失信条件失败关闭 | 7/7 通过；混合引用、跨店铺、草稿、未知、版本漂移、缺失均被拒绝 | 通过 |
| 新开放集总计 | 全部符合矩阵 | `55 passed` | 通过 |
| 010 历史开放集及聚焦回归 | 旧危险样本继续阻断，旧合法样本不再误杀 | 与产品知识安全、业务声明、工作流、营销审核及新开放集合并 `889 passed` | 通过 |
| 003 审核幂等/并发证据 | 四项数据库探针保持通过 | `4 passed` | 通过 |
| 隔离 PostgreSQL 全量 | 既有功能无回归 | `1227 passed, 2 warnings` | 通过 |
| 固定确定性安全评测 | 零危险逃逸、原因码一致 | 237/237；准确率 1.0，`unsafe_escape_count=0` | 通过 |
| 数据库迁移 | 空库升级、回滚、恢复 | `001→023`、`023→022→023` 均成功；最终为 023 | 通过 |
| pgvector | 扩展可用 | 版本 0.8.6 | 通过 |
| Ruff | 无静态规则或格式错误 | 检查通过；225 个文件已格式化 | 通过 |
| mypy | 无类型错误 | 162 个源文件无问题 | 通过 |
| compileall | Python 文件可编译 | 通过，无输出错误 | 通过 |
| 依赖锁 | 锁文件一致 | `uv lock --check` 解析 125 个包 | 通过 |
| Python 依赖审计 | 无已知漏洞 | 124 个锁定包无已知漏洞和不利状态 | 通过 |
| 前端 lint/typecheck | 无规则与类型错误 | 均通过 | 通过 |
| 前端测试 | 既有交互和安全契约不退化 | 32/32 通过 | 通过 |
| 前端生产构建 | 可生成生产产物 | Next.js 15.5.23 构建成功，12 个路由生成成功 | 通过 |
| Compose | 配置有效、既有服务状态可读 | 配置通过；backend/frontend/postgres/redis/minio 健康，worker/jobs 运行中 | 通过 |
| 健康检查 | `/v1/health` 返回 200 | `code=0`、`status=ok`、`version=0.1.0` | 通过 |
| 凭证与浏览器存储扫描 | 不出现硬编码密钥、JWT 或可读 Token 存储 | DeepSeek Key、JWT、Bearer、local/sessionStorage Token 四类均为 0 | 通过 |
| 前端生产依赖审计 | 无 High 漏洞 | 官方 npm 审计仍报告 PostCSS/Sharp 共 3 个 High | **失败；既有缺陷** |

两个 pytest 警告分别来自 Starlette `TestClient` 的 httpx 兼容弃用提示和 passlib 对 argon2 版本属性的弃用提示，不是本次修复引入。

### 6.1 主要复现命令

在 `CRM智能聊天系统/backend/` 执行：

```text
.venv/Scripts/python.exe -m pytest --rootdir=. -q ../../测试工程师/evidence/REAL-AI-04-004/test_real_ai04_fourth_retest.py
.venv/Scripts/python.exe -m pytest --rootdir=. -q tests/test_knowledge_safety_metadata.py tests/test_agent_business_claims.py tests/test_real_ai04_regressions.py tests/test_agent_workflow.py tests/test_agent_phase4.py tests/test_marketing_review_idempotency.py ../../测试工程师/evidence/REAL-AI-03-010/test_real_ai03_tenth_retest.py ../../测试工程师/evidence/REAL-AI-04-004/test_real_ai04_fourth_retest.py
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m scripts.evaluate_phase4 --dataset evals/agent-phase4-v1.0.0.jsonl --output ../../测试工程师/evidence/REAL-AI-04-004/fixed-eval-result.json
.venv/Scripts/python.exe -m ruff check app tests scripts migrations
.venv/Scripts/python.exe -m ruff format --check app tests scripts migrations
.venv/Scripts/python.exe -m mypy app scripts
uv lock --check
uv audit --locked
```

数据库全量和迁移命令使用本轮一次性 PostgreSQL URL 注入 `DATABASE_URL/TEST_DATABASE_URL` 后执行，凭证未写入报告。前端在 `CRM智能聊天系统/frontend/` 执行 `npm run lint`、`npm run typecheck`、`npm run test`、`npm run build`；既有前端生产依赖缺陷可用以下命令复现：

```text
npm audit --omit=dev --audit-level=high --registry=https://registry.npmjs.org
```

## 7. 缺陷复测结论

### 7.1 DEF-P4-AI-009：合法技术/非断言内容被误杀

| 项目 | 内容 |
| --- | --- |
| 原优先级 | P2 |
| 上一状态 | Reopened |
| 本轮状态 | **Closed** |
| 关闭证据 | 24 条全新合法样本 24/24 保留人工复核草稿；010 历史样本全部回归通过；无自动发送 |

修复后的确定性策略只有在全部知识引用同时满足当前店铺、当前版本、已审批和非客户实例类型时，才把旧承诺、订单状态与地址完成词法规则降为观测信号。新技术夹具、引用、否定、条件和未证实表达未再被旧规则清空，原缺陷类型没有复现。

该关闭结论仅表示结构化知识安全矩阵达到当前确定性验收标准，不表示真实模型语言质量或公开回复已经通过。

### 7.2 DEF-P4-AI-008：无证据客户实例事实漏放

| 项目 | 内容 |
| --- | --- |
| 优先级 | P1 |
| 上一状态 | Closed |
| 本轮状态 | **保持 Closed** |
| 证据 | 新危险集 24/24 失败关闭；010 历史危险集与产品回归通过；草稿隐藏、发送数为 0 |

### 7.3 DEF-REAL-AI04-001～004

- `DEF-REAL-AI04-001`：SSE 交付前断开/取消不伪装成功，保持 Closed。
- `DEF-REAL-AI04-002`：AI 营销安全候选进入独立人工审核，审核不执行发送，保持 Closed。
- `DEF-REAL-AI04-003`：审核幂等键持久化、同请求重放、异请求冲突和单审计通过，保持 Closed。
- `DEF-REAL-AI04-004`：并发批准/拒绝只有一个终态和一条成功审计，保持 Closed。

本轮未新增 REAL-AI-04 范围内的 P0、P1、P2 或 P3 产品缺陷。

## 8. 代码与安全审查结论

### 8.1 可信边界

- 安全授权来源是服务端权威结构化元数据，不是答案文本、模型标签或新的句式白名单。
- 任一引用不满足店铺、版本、审批或允许类型条件时，旧词法硬阻断仍生效。
- `customer_instance_fact` 仍要求同店铺、当次、非 Mock 的真实查询工具证据；无证据时转人工并隐藏草稿。
- 混合引用采取“全部可信”规则，安全技术资产不能掩盖客户实例事实。
- FAQ 即使安全，也只能进入 `HUMAN_REVIEW`；`automatic_delivery_allowed=false`，工作流结果固定 `send_performed=false`。

### 8.2 回复、翻译和营销边界

- 确定性草稿门禁、翻译输入安全和营销人工审核回归通过。
- AI 营销批准仍只改变审核状态，不调用发券、消息或平台写工具。
- 真实模型失败、SSE 中断和取消不应形成成功终态；既有回归保持通过。
- `.env.example` 与生产 Compose 中公开 AI、生产翻译、营销、自动回复和 TikTok 高风险写入开关保持关闭；生产 Compose 禁止 Mock 平台。

## 9. 已知未关闭风险与生产门禁

以下事项不因本轮关闭 `DEF-P4-AI-009` 而自动完成：

1. `REAL-AI-05` 真实 DeepSeek 回复、翻译、营销和结构化声明质量评测尚未完成。
2. 真实模型数据出境、限流、余额不足、超时和生产错误降级尚未完成最终目标环境验收。
3. 公开 SSE 50 个授权客户端并发、首分块耗时、P99、断线恢复和连续五日 99.5% 可用性尚未完成。
4. 真实 TikTok 店铺 OAuth、只读、Webhook、人工发送和回滚尚未完成联合生产验收。
5. 官方 npm 审计仍检出 Next.js 内嵌 PostCSS 与 Sharp 的 3 个 High，属于既有 `DEF-REAL-FS01-005`（P1/Open）；不能因本轮 AI 测试通过而忽略。
6. `DEF-REAL-FS01-006` 关键日志事件语义折叠仍为既有生产基础设施缺陷。
7. 当前不是 Git 仓库，缺少提交级不可变发布候选。

因此必须继续保持公开回复、生产翻译、AI 营销发送、自动回复和 AI 触发的平台写操作关闭。

## 10. 最终结论

**REAL-AI-04 第四次独立综合测试：有条件通过当前确定性工程范围。**

- `DEF-P4-AI-009` 已由新的未见开放集正式关闭。
- `DEF-P4-AI-008` 保持 Closed；新危险事实 0 漏放。
- `DEF-REAL-AI04-001～004` 全部保持 Closed。
- 新合法内容 0 误杀，所有允许内容仍只供人工复核，自动发送和平台副作用均为 0。
- 本轮没有新增 REAL-AI-04 产品缺陷。
- 后端全量、历史回归、固定评测、数据库迁移、静态质量、前端构建、Compose、健康检查、Python 依赖和敏感信息扫描通过。
- 既有前端生产依赖 High 漏洞及其他生产门禁仍阻断正式上线。

本结论允许 AIAgent开发工程师Agent进入 `REAL-AI-05` 的真实模型评测准备和内部草稿验证，不允许开启公开 AI 回复、生产翻译、AI 营销发送、自动回复或真实平台写操作。最终生产放行仍需测试工程师完成剩余专项报告，并由架构师签署放行记录。

## 11. 清理与交接

- 一次性测试容器 `crm-real-ai04-test-004` 已在核对名称、容器 ID 和 `tmpfs` 后删除；其中合成测试数据不可恢复，项目现有 Compose 服务未被重启或修改。
- 本轮 pytest、uv 和 Python 临时缓存已从 `测试工程师/evidence/REAL-AI-04-004/` 清理，只保留独立测试脚本和低敏评测汇总。
- 产品源文件测试前后聚合哈希一致。
- 本报告作为 REAL-AI-04 当前最新权威测试结论；001～003 号报告和 REAL-AI-03 010 号报告继续保留历史缺陷追溯。
