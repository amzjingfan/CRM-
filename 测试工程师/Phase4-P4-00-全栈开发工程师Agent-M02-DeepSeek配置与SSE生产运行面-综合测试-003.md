# Phase 4 REAL-FS-05 DeepSeek 配置与 SSE 生产运行面第三次独立综合测试报告

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
| 关联实施记录 | `共享记忆文档/实施记录/Phase4-P4-00-全栈开发工程师Agent-DeepSeekSSE性能门禁修复-018.md` |
| 前序报告 | `测试工程师/Phase4-P4-00-全栈开发工程师Agent-M02-DeepSeek配置与SSE生产运行面-综合测试-002.md` |
| 测试类型 | 综合测试、修复验证、性能门禁测试、边界测试、接口测试、安全测试、回归测试、数据库测试、部署配置测试、依赖审计 |
| 执行日期 | 2026-09-04 |
| 测试结论 | **有条件通过当前确定性工程范围** |

## 2. 结论摘要

本轮独立复测确认，002 号报告新增的 `DEF-REAL-FS05-004` 已完成根因修复。SSE 压测脚本现在同时要求样本完整、请求成功、存在 `accepted` 和首个安全 `delta`，并固定执行首个安全输出 P99 `<3000ms`、总耗时 P99 `<5000ms` 的严格比较。CLI 只允许收紧阈值，不能放宽架构上限。

独立构造 50 个完整样本后得到：2999/4999ms 以退出码 0 通过；首输出恰好 3000ms 或总耗时恰好 5000ms 均失败；单个尾部慢样本、NaN、负值和缺失指标均失败；尝试通过 API 或 CLI 放宽到 3001/5001ms 均被拒绝。JSON 证据包含实际阈值、`strictly_less_than` 比较语义和最终门禁状态，失败时进程以非零状态退出。因此 `DEF-REAL-FS05-004` 改为 Closed。

本轮 121 项聚焦测试、1259 项默认后端测试、1271 项隔离 PostgreSQL 测试、32 项前端测试、空库 001→023 迁移、Python 编译、Ruff 代码检查、mypy、Python 锁文件与依赖审计、前端生产构建、Compose 合并、运行态健康检查均通过。`DEF-REAL-FS05-001～003` 未发现回归，继续保持 Closed。

测试同时发现两个历史 PostgreSQL pytest 临时目录位于后端工作目录且当前用户无读取权限，导致计划规定的 `uv run ruff format --check .` 在 Ruff 0.16.3 中崩溃；对实际源码、脚本、迁移和测试目录执行格式检查时 233 个文件全部通过。该问题不影响 REAL-FS-05 运行逻辑，但破坏标准质量命令的可重复执行，新增 `DEF-REAL-FS05-005`（P3/Open，非阻断）。

因此：

- `DEF-REAL-FS05-001～004`：Closed。
- `DEF-REAL-FS05-005`：P3/Open，非阻断。
- REAL-FS-05 当前确定性工程范围有条件通过。
- 真实 DeepSeek 50 个授权客户端性能、连续五日稳定性和 99.5% 可用性仍未执行，不能据此签署生产放行。
- 既有 `DEF-REAL-FS01-005` 的前端 3 个 High 仍未关闭。
- 公开 AI 回复、生产翻译/营销、自动回复和 AI 触发的平台写操作继续关闭。

## 3. 测试依据、目标与边界

### 3.1 测试依据

- 项目级及各一级目录 `AGENTS.md`。
- `共享记忆文档/代码编写手册.md`。
- 最新 PRD、管理端接口文档、任务拆解、MVP 验收标准和项目团队职责。
- `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`。
- `全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` 的 REAL-FS-05。
- 002 号权威测试报告和 018 号全栈修复实施记录。

### 3.2 本轮目标

1. 独立复测 `DEF-REAL-FS05-004`，确认慢样本不再被错误包装为合格性能证据。
2. 验证严格小于边界、P99 尾部样本、非有限值、缺失值和可配置阈值的失败关闭行为。
3. 验证 CLI 退出码、JSON 证据、README、接口文档和架构阈值保持一致。
4. 重跑 REAL-FS-05 聚焦测试、默认后端、隔离 PostgreSQL、前端、Compose、健康检查和依赖审计。
5. 确认 `DEF-REAL-FS05-001～003` 无回归，并识别新的交付或生产风险。

### 3.3 明确未执行

- 未主动调用真实 DeepSeek 付费接口。
- 未使用真实客户消息、订单、地址、Cookie、Token 或店铺数据。
- 未执行真实模型 50 个授权客户端并发。
- 未执行连续五日稳定性和 99.5% 可用性观察。
- 未开启公开 AI、AI 营销、自动回复或 AI 触发的平台写操作。
- 本轮修复未涉及前端页面，未重复浏览器人工冒烟；002 号页面证据保留，本轮以 32 项前端测试和生产构建验证无回归。

## 4. 测试环境

| 项目 | 实际环境 |
| --- | --- |
| 操作系统 | Windows / PowerShell |
| Python | 3.11.15 |
| pytest | 9.1.1 |
| Ruff | 0.16.3 |
| Node.js | 24.19.0 |
| npm | 11.17.0 |
| Docker Engine | 29.7.2 |
| Docker Compose | 5.3.1 |
| 数据库 | 独立临时 PostgreSQL 容器，空库执行 001→023；结束后移除 |
| 当前运行态 | backend、frontend、postgres、redis、minio 健康；worker、jobs 运行中 |

项目基线仍为 Node.js 20 LTS，本机为 Node.js 24.19.0。当前前端检查全部通过，但 Node 20 兼容性仍应由 CI 或不可变生产镜像确认。

## 5. 原缺陷复测结果

| 缺陷 | 本轮证据 | 状态 |
| --- | --- | --- |
| `DEF-REAL-FS05-001` 空白 DeepSeek Key 健康误报 | Settings、ready 和 REAL-FS-05 聚焦回归继续通过；未发现空白密钥路径退化 | **Closed，保持** |
| `DEF-REAL-FS05-002` 租约 TTL 短于最长流时长 | 唯一租约、派生 TTL、精确释放和路由清理回归继续通过 | **Closed，保持** |
| `DEF-REAL-FS05-003` 默认 IP 限流导致 50 客户端压测失效 | integration/staging 专用 Profile、50/60 容量契约和联网前容量预检继续通过 | **Closed，保持** |
| `DEF-REAL-FS05-004` 压测脚本未执行首输出和 P99 SLA | 低于阈值通过；等于/高于阈值、尾部慢样本、非有限指标、缺失指标及阈值放宽均失败关闭；失败退出码为非零 | **Closed** |

## 6. 测试结果汇总

| 测试项 | 结果 | 证据/说明 |
| --- | --- | --- |
| REAL-FS-05 聚焦回归 | 通过 | 121 passed，1 个第三方弃用警告 |
| 默认后端全量 | 通过 | 1259 passed，12 skipped，2 warnings；跳过项由隔离 PostgreSQL 补测 |
| 隔离 PostgreSQL 全量 | 通过 | 1271 passed，0 skipped；空库 001→023 |
| Python 编译 | 通过 | `app`、`scripts`、`migrations` 正常编译 |
| Ruff 代码检查 | 通过 | All checks passed |
| Ruff 源码格式 | 通过 | 对 `app scripts tests migrations ../tests/integration` 检查，233 files already formatted |
| Ruff 仓库根格式命令 | 不通过（新增非阻断缺陷） | `uv run ruff format --check .` 因两个历史无权限 pytest 目录触发 Ruff panic，退出 1 |
| mypy | 通过 | 162 个源文件无类型错误 |
| Python 锁文件 | 通过 | 125 packages 解析成功 |
| Python 依赖审计 | 通过 | 124 packages 无已知漏洞或不利状态 |
| 前端 lint | 通过 | 退出码 0 |
| 前端类型检查 | 通过 | 退出码 0 |
| 前端测试 | 通过 | 32 passed |
| 前端生产构建 | 通过 | Next.js 15.5.23；14 个静态页面生成成功 |
| production + ai + DeepSeek Compose | 通过 | 合并后 10 个服务，未展开或记录真实密钥 |
| production + ai + DeepSeek + load-test Compose | 通过 | 合并后 10 个服务，专用压测叠加可解析 |
| 当前健康检查 | 通过但有限 | `/v1/health` 为 ok，`/v1/health/ready` 为 ready |
| 流前未认证请求 | 通过 | `/v1/chat/query` 返回 HTTP 403 JSON，未以 SSE 200 掩盖失败 |
| npm 官方依赖审计 | 不通过（既有缺陷） | 3 个 High，沿用 `DEF-REAL-FS01-005` |
| 压测完整性门禁 | 通过 | 缺样本、失败样本、缺首个安全 delta 或非有限指标均失败 |
| 压测 SLA 阈值门禁 | 通过 | 首输出 P99 `<3000ms`、总耗时 P99 `<5000ms`，严格小于 |
| 真实模型 50 客户端性能 | 未执行 | 需 50 组授权凭证、真实 Provider、成本预算和隔离窗口 |
| 五日稳定性 | 未执行 | 需独立目标环境连续观测 |

## 7. 关键独立验证

### 7.1 严格 SLA 边界

使用 50 个成功且完整的低敏合成样本验证：

```text
first_delta_p99=2999ms, total_p99=4999ms -> passed=true, exit=0
first_delta_p99=3000ms, total_p99=4999ms -> passed=false, exit=1
first_delta_p99=2999ms, total_p99=5000ms -> passed=false
single slow tail in 50 samples -> passed=false
```

结果确认使用严格 `<`，不会把等于阈值包装成通过。

### 7.2 非有限值和不完整样本

以下输入均被失败关闭：

- P99 样本含 NaN。
- 延迟为负值。
- 样本数量不足。
- `ok=false`。
- 缺少 `accepted_ms`。
- 缺少 `first_delta_ms`。

### 7.3 阈值不能被调用方放宽

程序接口拒绝大于架构上限的阈值；CLI 验证结果如下：

```text
--first-delta-p99-limit-ms 3001 -> exit=2
--total-p99-limit-ms 5001       -> exit=2
--first-delta-p99-limit-ms nan  -> exit=2
--total-p99-limit-ms 0          -> exit=2
```

CLI 可以使用 3000/5000 的架构上限，也可以使用更严格的正数阈值。输出证据包含 `first_delta_p99_limit_ms`、`total_p99_limit_ms`、`sla_comparison=strictly_less_than` 和 `performance_gate_passed`。

### 7.4 协议、部署和运行态

- README、接口文档、计划和代码均使用首个安全输出 P99 `<3000ms`、总耗时 P99 `<5000ms`。
- production、AI、DeepSeek SSE 和专用压测 Compose 叠加均能完成配置解析。
- 当前 Docker Compose 中 backend、frontend、PostgreSQL、Redis、MinIO 均为 healthy，worker 和 jobs 正常运行。
- `/v1/health` 返回 200/ok，`/v1/health/ready` 返回 200/ready。
- 未认证 `/v1/chat/query` 在流建立前返回 403 JSON。
- ready 只代表当前配置和本地依赖检查通过，不代表真实 DeepSeek 余额、网络、响应质量或 SLA 达标。

## 8. 新增缺陷

### DEF-REAL-FS05-005：历史无权限测试目录导致规定的仓库根 Ruff 格式命令崩溃

| 项目 | 内容 |
| --- | --- |
| 优先级 | P3 |
| 状态 | Open |
| 类型 | 交付环境、质量门禁可重复性 |
| 影响范围 | 后端标准检查命令、CI/本地交接 |
| 是否阻断 | 否 |
| 建议负责 Agent | 全栈开发工程师Agent、测试工程师Agent |

#### 复现步骤

1. 进入 `CRM智能聊天系统/backend`。
2. 执行 `uv --cache-dir ../.uv-cache run ruff format --check .`。
3. 观察 Ruff 0.16.3 输出 `Expected a ruff source file` panic 并以退出码 1 结束。
4. 分目录检查发现以下两个 2026-08-24 遗留目录无法被当前用户读取：
   - `backend/developCRM智能聊天系统.tmppytest-phase4-010-postgres-escalated`
   - `backend/developCRM智能聊天系统.tmppytest-phase4-010-postgres-final`
5. 改为只检查 `app scripts tests migrations ../tests/integration`，233 个文件全部通过。

#### 实际结果

标准命令无法正常完成；Ruff 仓库根扫描因无权限历史测试目录崩溃。源码范围格式检查通过。

#### 预期结果

- PostgreSQL/pytest 临时目录应创建在项目规定的临时证据目录或仓库外，并在测试结束后清理。
- 修复目录所有权/访问权限，或在确认目录不属于正式源码后将其加入 Ruff 排除规则。
- `uv run ruff format --check .` 应稳定返回格式检查结果，不得因测试残留崩溃。

#### 风险说明

该问题不影响 SSE、DeepSeek 配置或运行时行为，也未发现源码格式错误，因此不阻断 `DEF-REAL-FS05-004` 关闭；但会使交接人员无法按计划原样执行质量命令，应在下一轮工程清理中修复。

## 9. 既有风险和观察

### 9.1 `DEF-REAL-FS01-005` 仍为 Open

使用 npm 官方 registry 复核仍得到 3 个 High，涉及 Next.js 依赖链中的 PostCSS 和 sharp/libvips。自动修复要求升级至 Next.js 16.3.4，属于破坏性升级。本轮不重复创建缺陷，也不由测试工程师修改依赖。

### 9.2 确定性门禁不等于真实模型性能

本轮验证的是压测工具能够正确拒绝不合格证据。所有性能边界样本均为低敏合成数据，未发生真实 DeepSeek 调用，不能证明真实模型首输出、总耗时、限流、余额或质量达标。

### 9.3 生产放行仍需独立证据

真实 DeepSeek 50 个不同授权客户端并发、连续五日稳定性、99.5% 可用性、真实数据脱敏边界和生产告警/回滚仍需在授权隔离环境中完成。上述证据缺失时，生产 AI 开关必须保持关闭。

## 10. 回归与生产验证建议

### 10.1 P3 工程清理

1. 确认两个历史目录不含需保留的测试证据。
2. 由具备权限的负责 Agent 安全清理或修正目录权限，不得盲目递归删除未知路径。
3. 调整 PostgreSQL 集成脚本的临时目录策略，避免再次在后端源码根生成无权限目录。
4. 重跑 `uv run ruff check .` 和 `uv run ruff format --check .`。

### 10.2 真实性能与稳定性

1. 准备 50 组不同授权用户的 Cookie 凭证，凭证只存放在仓库外并在测试后安全删除。
2. 由授权人确认真实 DeepSeek 调用成本预算、隔离窗口和监控负责人。
3. 使用真实 Provider 执行 50 客户端并发，要求所有流完整并满足首输出 P99 `<3000ms`、总耗时 P99 `<5000ms`。
4. 连续运行五日，形成不低于 99.5% 可用性的正式证据。
5. 单独生成性能与稳定性报告，并由架构师签署最终生产放行记录。

## 11. 执行命令和结果

| 命令或检查 | 结果 |
| --- | --- |
| `pytest` REAL-FS-05、SSE load、health、runtime config | 121 passed |
| `pytest -q` | 1259 passed，12 skipped |
| `scripts/run-postgres-integration-tests.ps1` | 1271 passed，0 skipped；001→023 |
| `python -m compileall -q app scripts migrations` | 通过 |
| `ruff check .` | 代码检查通过；扫描时对历史无权限目录给出访问警告 |
| `ruff format --check app scripts tests migrations ../tests/integration` | 233 files already formatted |
| `uv run ruff format --check .` | 退出 1；新增 `DEF-REAL-FS05-005` |
| `mypy app scripts` | 162 个源文件通过 |
| `uv lock --check` | 通过，125 packages |
| `uv audit --locked` | 通过，124 packages 无已知漏洞 |
| `npm run lint` | 通过 |
| `npm run typecheck` | 通过 |
| `npm run test` | 32 passed |
| `npm run build` | 通过，14 个静态页面 |
| production + ai + DeepSeek Compose 配置 | 通过，10 个服务 |
| production + ai + DeepSeek + load-test Compose 配置 | 通过，10 个服务 |
| `/v1/health`、`/v1/health/ready` | 通过 |
| 未认证 `/v1/chat/query` | 403 JSON，通过 |
| `npm audit --audit-level=high` | 3 High；既有 `DEF-REAL-FS01-005` |
| 50 个完整边界样本与 CLI 阈值探针 | 通过；不达标时退出 1，非法阈值退出 2 |

## 12. 清理和数据安全

- 隔离 PostgreSQL 容器在测试结束后已停止并移除。
- 未调用真实 DeepSeek，不产生模型调用费用。
- 未修改后端、前端、迁移、测试代码或生产配置。
- 未输出 `.env`、真实 DeepSeek Key、Token、Cookie、会话 ID、消息正文或客户隐私。
- Compose 验证只使用合成占位配置；报告只保存低敏计数、状态和复现条件。
- 两个历史无权限目录未被测试工程师删除或修改，等待负责 Agent 确认所有权和安全处置方式。

## 13. 最终判定

**REAL-FS-05：有条件通过当前确定性工程范围。**

`DEF-REAL-FS05-001～004` 已通过独立复测并全部 Closed；新增 `DEF-REAL-FS05-005`（P3/Open）只影响标准格式命令的可重复执行，不阻断 SSE 性能门禁修复验收。现有确定性代码、数据库、前端、部署配置和依赖回归未发现 REAL-FS-05 阻断缺陷。

该结论不等于真实生产放行。既有 `DEF-REAL-FS01-005` 仍未关闭，真实模型 50 个授权客户端性能、连续五日稳定性和 99.5% 可用性仍未执行。在全部生产门禁完成并由架构师签署前，公开 AI 回复、生产翻译/营销、自动回复和 AI 触发的平台写操作继续关闭。
