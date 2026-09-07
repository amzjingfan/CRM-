# CRM 智能聊天系统总体架构设计 v1.5 增量说明

状态：已确认

## 1. 版本关系

本文件继承 `ARCH-001-SYS-系统总体架构设计-v1.4.md` 的全部未变更内容，新增工作区根单仓库、GitHub Flow 和发布基线架构，并同步 2026-09-07 可追溯的数据库、真实平台、AI、性能与生产门禁状态。v1.4 保留为历史版本，不删除、不覆盖。

生产安全边界继续以 `ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md` 和 `ADR-005-AI-知识语义类型与发布审批边界-v1.0.md` 为准。本版本不改变公开 API、数据模型、Prompt 或运行开关。

## 2. 交付与版本控制架构

### 2.1 单仓库边界

```text
工作区根 Git 仓库
├─ CRM智能聊天系统/       产品代码、迁移、测试、部署配置
├─ 架构师/                架构与生产放行门禁
├─ AI agent 开发工程师/   AI 方案、Prompt 与评测设计
├─ 全栈开发工程师/        全栈方案和交接文档
├─ 测试工程师/            正式测试报告与低敏证据
├─ 共享记忆文档/          需求、接口、索引和实施记录
├─ 开发工具/              Skill、脚本和模板
└─ release/baselines/     机器可读发布基线
```

工作区根目录是唯一 Git 仓库。产品代码目录仍是正式运行实现的唯一归属，但所有架构、测试和项目事实与代码共享同一提交历史，从而保证任一发布标签都能同时还原代码、迁移、验收依据和正式报告。

### 2.2 GitHub Flow

```text
main
  └─ feature/* | fix/* | docs/* | hotfix/*
       → 小步提交
       → Pull Request
       → CI + 审阅 + 文档/实施记录同步
       → squash merge
       → 删除短期分支
```

`main` 是唯一长期分支。有 GitHub 远程后禁止直接 push，要求 Pull Request、后端/前端 CI 和人工审阅。基线建立后，短期分支优先放在 `.worktrees/` 隔离工作区。

本次首次导入存在两个受控例外：仓库创建前的设计/计划直接形成 bootstrap 提交；预先存在但尚未跟踪的项目文件无法出现在 Git worktree，因此首次基线分支在主检出目录实施。基线进入 `main` 后，这两个例外终止。

## 3. 版本化资产与排除边界

### 3.1 必须跟踪

- 产品源代码、迁移、锁文件、Dockerfile、Compose 和脱敏配置示例。
- 架构、接口、任务、共享记忆、实施记录、正式测试报告和低敏评测证据。
- 模型名称、Revision、许可证和资产 SHA-256 清单。
- GitHub Actions、PR 模板、GitHub Flow 规范和发布基线清单。

### 3.2 禁止跟踪

- `.env`、私钥、Token、凭证池、真实生产配置和客户隐私。
- BGE、Reranker 或其他模型权重。
- `.venv`、`node_modules`、包缓存、构建缓存、日志和测试临时目录。
- `.worktrees/` 中的隔离检出副本。

根 `.gitignore` 是仓库级规则，产品目录现有 `.gitignore` 作为纵深保护。任何发布暂存前必须验证敏感路径被忽略，并检查候选大文件。

## 4. 发布基线架构

本次应用版本保持 `0.1.0`，预发布工程标签为 `v0.1.0-mvp.20260907`。标签指向最终 `main` squash 提交，提交通过以下命令解析，避免清单文件写入自身提交 SHA 形成循环：

```powershell
git rev-list -n 1 v0.1.0-mvp.20260907
```

机器可读清单位于 `release/baselines/v0.1.0-mvp.20260907.json`，固定：

- Alembic head、迁移文件及 SHA-256。
- `.env.example`、依赖锁、包清单、Dockerfile 和 Compose 构建输入 SHA-256。
- 评测数据集、清单、结果、模型、Prompt、DLP 策略、运行 ID 和 SHA-256。
- 应用镜像本地 `image_id`、仓库 `repo_digest` 和构建状态。
- 尚未关闭的生产门禁及权威证据路径。

本地 Docker image ID、镜像仓库 RepoDigest 和 Dockerfile SHA-256 是三类不同证据。未推送到内容寻址镜像仓库时，`repo_digest` 必须为 `null`；不能用其他摘要冒充。

## 5. 当前数据库与配置基线

- 当前权威 Alembic head 为 `023_marketing_review_idempotency`，替代 v1.4 记录的 `018_ai_observability`。
- `019_tiktok_channel_unique` 强制一个内部店铺只能绑定一个 TikTok 渠道。
- `020_knowledge_safety` 增加知识语义分类和发布审批。
- `021_message_unknown` 增加平台写入未知终态和人工对账边界。
- `022_ai_marketing_review` 增加 AI 交付与营销审核状态。
- `023_marketing_review_idempotency` 加固营销审核幂等与并发终态。
- 应用版本为 `0.1.0`；实际配置值只允许从仓库外环境或密钥系统注入，基线只散列 `.env.example`。

生产能力继续通过独立开关逐级扩大。公开 AI 回复、AI 翻译、AI 营销、自动回复和真实平台高风险写入不能因 Git 标签或工程测试通过而自动开启。

## 6. 当前工程与质量状态

| 范围 | 当前权威状态 | 主要证据 |
| --- | --- | --- |
| Phase 1～3 核心工程 | Phase 2 已通过；Phase 3 在契约级 Mock 范围通过 | `共享记忆文档/测试报告索引.md` |
| REAL-FS-01 基础设施 | 不通过；`DEF-REAL-FS01-005` P1 和 `006` P2 Open | REAL-FS-01 005 号证据恢复报告 |
| REAL-FS-02 OAuth | 当前工程范围有条件通过；真实店铺未执行 | OAuth 003 号报告 |
| REAL-FS-03 只读/Webhook | 当前确定性工程范围有条件通过；真实投递未执行 | 只读/Webhook 003 号报告 |
| REAL-FS-04 人工消息 | 当前确定性工程范围有条件通过；真实消息未执行 | 人工消息 002 号报告 |
| REAL-FS-05 SSE 运行面 | 当前确定性工程范围有条件通过；`DEF-REAL-FS05-005` P3 Open | SSE 003 号报告 |
| REAL-AI-04 回复/翻译/营销契约 | 确定性工程与无网络 Provider 契约有条件通过；相关缺陷 Closed | REAL-AI-04 006 号报告 |
| REAL-AI-05 真实模型固定评测 | 当前固定聚合门禁有条件通过；32/36、88.89%，生产翻译未证明 | REAL-AI-05 005 号报告 |

REAL-AI-05 的固定聚合结果满足准确率、危险逃逸、合法误拦截、Provider 失败和成本配置门禁，但翻译分层为 `0/2`，只能证明本次冻结评测的聚合门禁，不能证明生产翻译质量。

## 7. 当前生产门禁

```text
Git/配置/镜像基线（G0）
        ↓
TikTok OAuth/只读/Webhook（G1/G2）
        ↓
人工普通消息真实灰度（G3）
        ↓
DeepSeek 安全、回复、翻译、营销质量（G4）
        ↓
50 授权客户端真实 SSE + 五日 99.5%（G5/G6）
        ↓
高风险工具灰度（G7）
        ↓
最终生产签署（G8）
```

当前 G0 已建立根 Git、source/config 与后端本地镜像基线；后端本地镜像为 `crm-backend@sha256:a07b580c40b7ba6bd32f82b5231df17a38c25d471cb9af9049b28bce135c47bf`。前端本次构建因 Docker Hub OAuth 超时及容器内 `npm ci` 网络停滞未形成新镜像，且仍有 3 个 High；关键日志事件仍可能折叠，应用与外部镜像的受控仓库 RepoDigest、真实密钥轮换、备份恢复和回滚演练尚未形成完整证据。G1～G4 只具备部分确定性工程或冻结评测证据；G5/G6 未执行。因此 G7、G8 保持阻塞，生产仍未放行。

## 8. CI 与测试边界

Pull Request CI 固定执行：

- Python 3.11、uv 0.12.3、锁文件检查、Ruff、mypy 和默认 pytest。
- Node.js 20、`npm ci`、ESLint、TypeScript、前端测试和 Next.js 生产构建。

CI 不替代隔离 PostgreSQL、真实模型、真实 TikTok、镜像安全、50 并发、五日稳定性或备份恢复测试。正式结论必须继续存放在 `测试工程师/`，共享目录只维护索引。

## 9. 后续执行顺序

1. 完成本次根仓库导入、机器可读基线、验证、合并和带注释标签。
2. 独立修复并复测 `DEF-REAL-FS01-005/006`，不得把破坏性 Next.js Major 升级混入基线任务。
3. 在隔离 integration/staging 环境完成真实 TikTok OAuth、只读、Webhook 和人工消息单店铺灰度。
4. 补充生产翻译独立评测、真实 DeepSeek 50 授权客户端 SLA 和五日 99.5% 稳定性证据。
5. 完成镜像仓库 RepoDigest、密钥轮换、备份恢复、回滚和最终架构/产品签署后，另建正式生产 SemVer 标签。
