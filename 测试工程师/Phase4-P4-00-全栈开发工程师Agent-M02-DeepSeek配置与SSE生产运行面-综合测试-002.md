# Phase 4 REAL-FS-05 DeepSeek 配置与 SSE 生产运行面修复后独立综合测试报告

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 REAL-FS-05 |
| 模块编号 | M02 |
| 模块名称 | DeepSeek 配置与 SSE 生产运行面 |
| 被测主责 Agent | 全栈开发工程师Agent |
| 被测协作 Agent | 架构师Agent、AIAgent开发工程师Agent |
| 测试执行 Agent | 测试工程师 Agent |
| 关联实施记录 | `共享记忆文档/实施记录/Phase4-P4-00-全栈开发工程师Agent-DeepSeekSSE测试缺陷修复-017.md` |
| 前序报告 | `测试工程师/Phase4-P4-00-全栈开发工程师Agent-M02-DeepSeek配置与SSE生产运行面-综合测试-001.md` |
| 测试类型 | 综合测试、修复验证、配置测试、接口测试、安全测试、并发控制测试、回归测试、数据库测试、部署配置测试、页面冒烟测试 |
| 执行日期 | 2026-09-04 |
| 测试结论 | **不通过** |

## 2. 结论摘要

本轮对 001 号报告中的 `DEF-REAL-FS05-001～003` 完成独立复测：空白 DeepSeek Key 已在真实环境启动和 ready 检查中统一失败关闭；Redis 并发控制已改为唯一租约令牌并由流超时加 60 秒派生租期；单机 50 客户端专用 Profile、IP 容量预检、完整样本和首个安全 `delta` 门禁均已落地。三个原 P1 均可改为 Closed。

专项自动化 111 项、默认后端 1249 项、隔离 PostgreSQL 1261 项、前端 32 项、空库迁移 001→023、静态质量、生产构建、Compose 合并、真实 Redis 探针、健康检查和页面冒烟均通过。

但是，独立负向测试发现压测脚本只校验“50 个样本完整且存在首个安全 `delta`”，没有把架构门禁中的“首输出小于 3 秒、P99 小于 5 秒”纳入成功判定。构造 50 个首输出 P99=10000ms、总耗时 P99=20000ms 的完整慢样本后，脚本仍输出 `performance_gate_passed=true` 并以退出码 0 结束。该问题会把明显不达标的性能结果包装成可放行结果，新增 `DEF-REAL-FS05-004`（P1/Open）。

因此：

- `DEF-REAL-FS05-001～003`：Closed。
- `DEF-REAL-FS05-004`：P1/Open，阻断 REAL-FS-05 工程验收。
- REAL-FS-05 总体仍为不通过。
- 真实 DeepSeek 50 个授权客户端性能、连续五日稳定性和 99.5% 可用性仍未执行。
- 公开 AI 回复、生产翻译/营销、自动回复和 AI 触发的平台写操作继续关闭。

## 3. 测试依据、目标与边界

### 3.1 测试依据

- 项目级及各一级目录 `AGENTS.md`。
- `共享记忆文档/代码编写手册.md`。
- 最新 PRD、管理端接口文档、任务拆解、MVP 验收标准和项目团队职责。
- `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`。
- `全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` 的 REAL-FS-05。
- 001 号权威测试报告和 017 号全栈修复实施记录。

### 3.2 本轮目标

1. 独立复测三个原 P1 的根因，而非只重跑开发新增测试。
2. 验证 Settings、ready、Redis Lua、路由租约、压测 Profile 和压测脚本的一致性。
3. 验证修复对 SSE、AI 安全草稿、数据库、前端和部署配置无回归。
4. 审查修复后的压测工具是否能够形成有效的生产性能放行证据。

### 3.3 明确未执行

- 未主动调用真实 DeepSeek 付费接口。
- 未使用真实客户消息、订单、地址或店铺数据。
- 未执行真实模型 50 个授权客户端并发。
- 未执行连续五日稳定性和 99.5% 可用性观察。
- 未开启公开 AI、AI 营销、自动回复或 AI 触发的平台写操作。

## 4. 测试环境

| 项目 | 实际环境 |
| --- | --- |
| 操作系统 | Windows / PowerShell |
| Python | 3.11.15 |
| pytest | 9.1.1 |
| Node.js | 24.19.0 |
| npm | 11.17.0 |
| Docker Engine | 29.7.2 |
| Docker Compose | 5.3.1 |
| 数据库 | 独立临时 PostgreSQL 容器，空库执行 001→023 |
| Redis 独立探针 | 本地 Redis 7 的隔离 DB 与随机键，完成后清理 |
| 页面验证 | Codex 内置浏览器访问本地 `http://localhost:3000/workspace` |

项目基线仍为 Node.js 20 LTS，本机为 Node.js 24.19.0。当前前端检查全部通过，但 Node 20 兼容性仍应由 CI 或不可变生产镜像确认。

## 5. 原缺陷复测结果

| 缺陷 | 复测结果 | 状态 |
| --- | --- | --- |
| `DEF-REAL-FS05-001` 空白 DeepSeek Key 健康误报 | 空字符串、普通空格、制表符/换行和不换行空格均被真实环境 Settings 拒绝；ready 返回 false；生产启动和健康检查复用 `has_non_blank_secret` | **Closed** |
| `DEF-REAL-FS05-002` 租约 TTL 短于最长流时长 | 6/180/600 秒流超时分别派生 66/240/660 秒租约；真实 Redis 验证容量、TTL、伪令牌释放和持有者精确释放均通过 | **Closed** |
| `DEF-REAL-FS05-003` 默认 IP 限流导致 50 客户端压测失效 | 专用 Profile 默认将窗口限额设为 60；只允许 integration/staging；脚本声明低于并发数时联网前失败；真实 Redis 同 IP 50/50 接受、60/60 接受、第 61 次拒绝 | **Closed** |

## 6. 测试结果汇总

| 测试项 | 结果 | 证据/说明 |
| --- | --- | --- |
| REAL-FS-05 聚焦回归 | 通过 | 111 passed，1 个第三方弃用警告 |
| 默认后端全量 | 通过 | 1249 passed，12 skipped，2 warnings；跳过项由隔离 PostgreSQL 补测 |
| 隔离 PostgreSQL 全量 | 通过 | 1261 passed，0 skipped；空库 001→023 |
| Python 编译 | 通过 | `compileall` 正常退出 |
| Ruff | 通过 | All checks passed |
| Ruff 格式 | 通过 | 226 files already formatted |
| mypy | 通过 | 162 个源文件无类型错误 |
| Python 锁文件 | 通过 | 125 packages 解析成功 |
| Python 依赖审计 | 通过 | 124 packages 无已知漏洞或不利状态 |
| 前端 lint | 通过 | 退出码 0 |
| 前端类型检查 | 通过 | 退出码 0 |
| 前端测试 | 通过 | 32 passed |
| 前端生产构建 | 通过 | Next.js 15.5.23；14 个静态页面生成成功 |
| 文档化 Compose 组合 | 通过 | 10 个服务；backend 为 integration、限额 60、仅 backend 启用 LLM；jobs/agent-worker 的 LLM 和自动回复关闭 |
| 当前健康检查 | 通过但有限 | `/v1/health` 和 `/v1/health/ready` 成功；组件 database/redis/object_storage 为 ok，retrieval disabled，llm_provider ok |
| 流前未认证请求 | 通过 | HTTP 403 + `application/json`，未以 SSE 200 掩盖失败 |
| 页面冒烟 | 通过 | 工作台和 AI 建议区正常，建议不自动发送；控制台无 error/warning |
| npm 官方依赖审计 | 不通过（既有缺陷） | 3 个 High，沿用 `DEF-REAL-FS01-005` |
| 压测完整性门禁 | 通过 | 缺样本、失败样本或缺首个安全 delta 时返回失败 |
| 压测 SLA 阈值门禁 | **失败** | 首输出 10s、总 P99 20s 仍标记通过并退出 0 |
| 真实模型 50 客户端性能 | 未执行 | 需授权凭证池、成本预算和修复后的门禁工具 |
| 五日稳定性 | 未执行 | 需独立目标环境连续观测 |

## 7. 关键独立验证

### 7.1 空白密钥失败关闭

对空字符串、普通空格、制表符加换行、不换行空格分别执行启动和 ready 探针：

```text
Settings accepted: false, false, false, false
ready configured: false, false, false, false
```

结果符合预期，且未在命令输出、日志或报告中展开任何真实密钥。

### 7.2 真实 Redis 唯一租约

使用随机用户和隔离 Redis DB 验证：

```text
首次申请成功 = true
TTL 覆盖 660 秒 = true
容量满时第二次申请被拒绝 = true
伪造/旧令牌不能释放持有者槽位 = true
持有者精确释放后可以重新申请 = true
```

探针结束后随机并发键和限流键均已清理。

### 7.3 单 IP 50 客户端容量

使用 61 个随机用户和同一随机测试 IP、窗口限额 60 验证：

```text
前 50 次接受 = 50
前 60 次接受 = 60
第 61 次拒绝 = true
```

说明原 `DEF-REAL-FS05-003` 的运行根因已被专用限流 Profile 覆盖。

### 7.4 页面和协议边界

- 已登录管理员可打开工作台。
- AI 建议区显示“不会自动发送或执行写工具”。
- 无建议时“使用”按钮禁用。
- 未主动点击“生成”，避免在没有本轮成本授权时调用真实 DeepSeek。
- 浏览器控制台 error/warning 数量为 0。
- 未认证 `/v1/chat/query` 在流建立前返回 JSON 403。

## 8. 新增缺陷

### DEF-REAL-FS05-004：压测脚本未执行首输出和 P99 SLA，超阈值慢样本仍以成功退出

| 项目 | 内容 |
| --- | --- |
| 优先级 | P1 |
| 状态 | Open |
| 类型 | 性能门禁有效性、错误放行 |
| 影响范围 | REAL-FS-05、P4-10、真实模型 SSE 放行、五日性能证据 |
| 是否阻断 | 是 |
| 建议负责 Agent | 全栈开发工程师Agent、架构师Agent |

#### 复现步骤

1. 构造 50 个状态为成功、包含 `accepted`、`delta` 和 `done.reason=completed` 的完整样本。
2. 将每个样本的首个安全 `delta` 设置为 10000ms，总耗时设置为 20000ms。
3. 运行 `performance_gate_passed(samples, 50)`。
4. 使用相同样本替换 `run_one` 后执行压测脚本 `main()`，检查输出和退出码。

#### 实际结果

```text
succeeded = 50
first_delta_p99_ms = 10000.0
total_p99_ms = 20000.0
performance_gate_passed = true
process exit_code = 0
```

`backend/scripts/load_test_sse.py:219-223` 只检查样本数量、请求成功、accepted 和 first_delta 是否存在。脚本虽计算并输出首输出 P99 和总耗时 P99，但没有把任何 SLA 阈值放入 `performance_gate_passed` 或退出码。

#### 影响

- 明显不满足 ADR“首输出小于 3 秒、50 客户端 P99 小于 5 秒”的结果仍会显示性能门禁通过。
- 自动化流水线只检查退出码时可能错误放行生产 AI。
- 连续五日保存的证据可能全部完整但性能不合格，汇总时无法依赖 `performance_gate_passed` 字段。

#### 预期结果

- 在测试前由架构师冻结指标语义，至少明确首输出和总耗时使用最大值还是 P99。
- 压测脚本增加明确的阈值参数或固定契约，例如首输出门禁 3000ms、总耗时 P99 门禁 5000ms。
- `performance_gate_passed` 同时要求样本完整、成功数量达标、首输出指标达标和 P99 指标达标。
- 任一阈值不达标时输出 `performance_gate_passed=false` 并以非零退出码结束。
- 增加恰好等于阈值、略低于阈值、略高于阈值、单一尾部慢请求和 50 样本 P99 的边界测试。

## 9. 既有风险和观察

### 9.1 `DEF-REAL-FS01-005` 仍为 Open

使用 npm 官方 registry 复核仍得到 3 个 High，涉及 Next.js 依赖链中的 PostCSS 和 sharp/libvips。自动修复要求升级至 Next.js 16.3.4，属于破坏性升级。本轮不重复创建缺陷，也不由测试工程师修改依赖。

### 9.2 ready 不代表真实模型可用

本地 `/v1/health/ready` 返回 `llm_provider=ok` 只表示当前配置完整，不会调用收费接口，也不能证明余额、供应商网络、真实响应质量或延迟达标。

### 9.3 确定性全量回归不能替代生产性能与稳定性

1249/1261 项后端回归和 32 项前端测试未覆盖真实 DeepSeek 网络、真实供应商限流、50 个授权用户及五日连续运行，不能用于签署最终生产放行。

## 10. 回归建议

### 10.1 `DEF-REAL-FS05-004` 修复后

1. 使用 50 个完整但分别低于、等于和高于 SLA 的合成样本验证进程退出码。
2. 验证一个尾部慢请求对 P99 计算和最终门禁的影响。
3. 验证 CLI、JSON 证据和 README 对阈值单位、默认值和指标语义一致。
4. 重跑 111 项 REAL-FS-05 聚焦测试、默认后端和隔离 PostgreSQL 全量回归。
5. 重跑前端、Compose、健康和依赖安全检查。

### 10.2 生产性能与稳定性

1. 修复 P1 后再准备 50 组不同授权用户凭证，凭证必须存放在仓库外。
2. 由授权人确认真实 DeepSeek 调用成本预算和测试窗口。
3. 使用真实 Provider 获取 50 个成功样本，验证首输出和 P99 的正式阈值。
4. 连续运行五日，形成不低于 99.5% 可用性的正式证据。
5. 单独生成性能/稳定性测试报告，由架构师完成最终放行记录。

## 11. 执行命令和结果

| 命令或检查 | 结果 |
| --- | --- |
| `pytest` REAL-FS-05、SSE load、health、runtime config | 111 passed |
| `pytest -q -rs` | 1249 passed，12 skipped |
| `scripts/run-postgres-integration-tests.ps1` | 1261 passed，0 skipped；001→023 |
| `python -m compileall -q app scripts migrations` | 通过 |
| `ruff check app tests scripts migrations` | 通过 |
| `ruff format --check app tests scripts migrations` | 226 files already formatted |
| `mypy app scripts` | 162 个源文件通过 |
| `uv lock --check` | 通过 |
| `uv audit --locked` | 124 packages 无已知漏洞 |
| `npm run lint` | 通过 |
| `npm run typecheck` | 通过 |
| `npm run test` | 32 passed |
| `npm run build` | 通过，14 个静态页面 |
| README 中 production + ai + DeepSeek + load-test Compose 组合 | 通过；10 个服务，integration/60，后台 AI 关闭 |
| 真实 Redis 唯一租约探针 | 通过 |
| 真实 Redis 同 IP 50/60 容量探针 | 通过 |
| `/v1/health`、`/v1/health/ready` | 通过 |
| 未认证 `/v1/chat/query` | 403 JSON，通过 |
| 本地工作台浏览器冒烟 | 通过，控制台无 error/warning |
| `npm audit --registry=https://registry.npmjs.org` | 3 High；既有缺陷 |
| 50 个完整慢样本性能门禁探针 | **退出码 0、错误判定通过** |

## 12. 清理和数据安全

- 隔离 PostgreSQL 容器在测试结束后已停止并移除。
- Redis 探针使用随机用户、随机测试 IP 和隔离 DB，相关键已清理。
- 未修改后端、前端、迁移、测试代码或生产配置。
- 未输出 `.env`、真实 DeepSeek Key、Token、Cookie、消息正文或客户隐私。
- 本报告只保存低敏计数、状态和复现条件。

## 13. 最终判定

**REAL-FS-05：不通过。**

`DEF-REAL-FS05-001～003` 已通过独立复测并关闭；新增 `DEF-REAL-FS05-004`（P1/Open），压测脚本能够把明显超出首输出和 P99 SLA 的结果判为成功。既有 `DEF-REAL-FS01-005` 仍未关闭，真实模型 50 客户端性能和五日稳定性尚未执行。在新增 P1 关闭并完成真实生产门禁前，公开 AI 回复、生产翻译/营销、自动回复和 AI 触发的平台写操作继续关闭。
