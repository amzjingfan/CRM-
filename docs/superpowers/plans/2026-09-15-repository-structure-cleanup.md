# Repository Structure Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将六个角色型一级目录的 424 个跟踪文件压缩为不超过十五份当前文档和一组最小机器证据，并在修复全部活动引用后删除这些目录。

**Architecture:** 以 `CRM智能聊天系统/` 作为唯一产品工程，以根 `docs/` 保存面向用途的当前事实，以 `release/evidence/` 保存发布清单必须读取的低敏机器证据。先记录结构基线，再分主题生成压缩文档，随后迁移证据、修复路径、删除旧目录，最后执行与变更范围相称的必要验证。

**Tech Stack:** Markdown、JSON/JSONL、Python 3.11、pytest、PowerShell、Git/GitHub Flow。

**Spec:** `docs/superpowers/specs/2026-09-15-repository-structure-cleanup-design.md`

## Global Constraints

- 删除 `全栈开发工程师/`、`AI agent 开发工程师/`、`共享记忆文档/`、`开发工具/`、`架构师/`、`测试工程师/` 六个一级目录。
- 不允许把旧文件原样换目录保存；压缩文档必须去重、合并并可独立阅读。
- 长期维护的压缩文档最多十五份；机器证据和既有 `docs/superpowers/` 文件不计入该数量。
- Git 历史和发布标签保存历史全文；不得重写历史、修改已有标签或强制推送。
- 不改变产品运行行为、公开 API、数据库迁移、配置默认值、权限或生产安全边界。
- TikTok 人工辅助 v0.1 仍是限定发布范围；三平台完整 MVP、自动回复、自动营销和高风险写入不得被描述为已放行。
- `.env`、模型权重、缓存和无关 worktree 不属于本次清理范围；禁止使用 `git clean -fdX`。
- 机器证据迁移后必须同步路径与 SHA-256；模型清单和发布基线必须继续可解析、可验证。
- 实施发生在 `docs/repository-structure-cleanup` 隔离分支，基线为 `origin/main@960e62a`。

---

## File Structure

### 新建的长期文档

- `docs/README.md`：唯一文档入口、事实优先级和维护规则。
- `docs/product.md`：产品目标、完整 MVP、TikTok v0.1 范围和验收口径。
- `docs/api.md`：当前有效的管理端接口与明确标记的规划接口。
- `docs/architecture.md`：完整当前架构、数据流、模块边界和数据结构。
- `docs/ai.md`：模型、RAG、结构化声明、工具与失败关闭契约。
- `docs/development.md`：编码、测试、Git、提交和安全规范。
- `docs/deployment.md`：模型资产、TikTok、DeepSeek、staging 和回滚边界。
- `docs/release-gates.md`：G0～G8 当前门禁、状态和证据入口。
- `docs/test-status.md`：最新测试结论和未关闭缺陷矩阵。
- `docs/open-work.md`：仅包含尚未完成且仍有业务价值的工作。
- `docs/history.md`：项目关键里程碑与被压缩历史的 Git 追溯方法。

### 新建或调整的机器资产

- `CRM智能聊天系统/backend/scripts/bge_production_gate.py`：角色无关的 BGE 生产门禁脚本；从旧脚本提炼并复用现有 RAG 评测逻辑。
- `release/evidence/retrieval/bge-quality-threshold-052-20260821.json`：最终 BGE 质量门禁证据。
- `release/evidence/retrieval/bge-capacity-gpu-gate-20260821.json`：最终 GPU 容量门禁证据。
- `release/evidence/retrieval/bge-gpu-runtime-20260821.json`：GPU、冷启动和显存证据。
- `release/evidence/ai/real-model-independent-v1.0.0.jsonl`：发布基线固定的独立评测集。
- `release/evidence/ai/real-model-independent-v1.0.0.manifest.json`：评测集 manifest。

### 修改的活动入口

- `AGENTS.md`
- `CRM智能聊天系统/AGENTS.md`
- `.github/CODEOWNERS`
- `.github/pull_request_template.md`
- `CRM智能聊天系统/README.md`
- `CRM智能聊天系统/deploy/models/README.md`
- `CRM智能聊天系统/deploy/models/model-manifest.json`
- `CRM智能聊天系统/deploy/staging/rootless/README.md`
- `CRM智能聊天系统/deploy/production/README.md`
- `release/baselines/v0.1.0-mvp.20260907.json`

### 删除的目录

- `全栈开发工程师/`
- `AI agent 开发工程师/`
- `共享记忆文档/`
- `开发工具/`
- `架构师/`
- `测试工程师/`

---

### Task 1: 记录清理基线

**Files:**
- Read: `docs/superpowers/specs/2026-09-15-repository-structure-cleanup-design.md`
- Read: `release/baselines/v0.1.0-mvp.20260907.json`
- Read: `CRM智能聊天系统/deploy/models/model-manifest.json`

**Interfaces:**
- Consumes: Git 跟踪文件列表、模型清单和发布基线 JSON。
- Produces: 删除前文件数、行数、旧路径引用和机器证据摘要，供最终结果对照。

- [ ] **Step 1: 记录六个目录的跟踪文件数和文本行数**

```powershell
$targets=@('全栈开发工程师','AI agent 开发工程师','共享记忆文档','开发工具','架构师','测试工程师')
foreach($target in $targets){
  $files=Get-ChildItem -LiteralPath $target -Recurse -File -Force
  $lines=0
  foreach($file in $files){ try { $lines+=(Get-Content -LiteralPath $file.FullName | Measure-Object -Line).Lines } catch {} }
  [PSCustomObject]@{Target=$target;Tracked=(git ls-files -- $target | Measure-Object).Count;Files=$files.Count;Lines=$lines}
}
```

Expected: 六个目录全部存在，总跟踪文件约 424，总文本行约 7.06 万。

- [ ] **Step 2: 记录冻结评测集摘要**

```powershell
(Get-FileHash -Algorithm SHA256 '测试工程师/evidence/REAL-AI-05-002/real-model-independent-v1.0.0.jsonl').Hash.ToLower()
(Get-FileHash -Algorithm SHA256 '测试工程师/evidence/REAL-AI-05-002/real-model-independent-v1.0.0.manifest.json').Hash.ToLower()
```

Expected: 分别为 `7f7c7084ac37e9aef5c9b1a947a9f44250cd89e290f5ae18990ec558e5c6df94` 和 `232f52a3fa5f5c33622f25a87456128aa9c553a5c00da682bbce2cb8cb3d6905`。

---

### Task 2: 压缩产品、接口和开发规范

**Files:**
- Create: `docs/README.md`
- Create: `docs/product.md`
- Create: `docs/api.md`
- Create: `docs/development.md`
- Read: `共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`
- Read: `共享记忆文档/MVP范围与验收标准.md`
- Read: `共享记忆文档/开发任务拆解（按人天分配）.md`
- Read: `共享记忆文档/智能客服平台 — 管理端接口文档.md`
- Read: `共享记忆文档/代码编写手册.md`
- Read: `共享记忆文档/Git与GitHub Flow开发规范.md`

**Interfaces:**
- Consumes: 当前 PRD、接口增量、代码规范和 Git 规范。
- Produces: 后续架构、测试、部署和根 AGENTS 可链接的稳定文档入口。

- [ ] **Step 1: 创建文档导航**

`docs/README.md` 固定包含：事实优先级、十一份文档用途、代码/配置/ADR/测试结论冲突时的判定顺序，以及“历史全文使用 Git 标签或提交读取”的说明。事实优先级写为：运行代码与迁移 → 已接受安全 ADR 的压缩结论 → 发布基线 → 最新正式测试状态 → 产品规划。

- [ ] **Step 2: 编写独立的产品当前版**

`docs/product.md` 固定包含以下章节：背景与目标、完整 MVP、TikTok 人工辅助 v0.1、明确非目标、核心用户流程、量化验收标准、后续路线。保留三平台完整 MVP；将自动回复、主动营销、Shopee/Amazon 真实接入标为后续工作，不复制旧 48 项人天表。

- [ ] **Step 3: 编写独立的当前接口文档**

`docs/api.md` 以管理端接口文档第 11 节实际增量为主，固定覆盖认证、看板、工作台、知识库、营销、Agent 运营、团队、TikTok OAuth、Webhook 和通用错误码。早期 `/marketing/flows`、PUT 更新和无确认发送等草案不得写成已实现接口；规划接口集中到“规划但未放行”一节。

- [ ] **Step 4: 编写统一开发规范**

`docs/development.md` 合并代码编写手册和 GitHub Flow，保留 Python/TypeScript 类型、中文业务注释、安全、测试、分支、提交和 PR 门禁。删除目录归属、角色负责人、逐任务实施记录和“先读取共享记忆目录”要求，改为从 `docs/README.md` 选择任务相关文档。

- [ ] **Step 5: 验证压缩文档没有增量链依赖**

```powershell
$files=@('docs/README.md','docs/product.md','docs/api.md','docs/development.md')
Select-String -Path $files -Pattern '继承.*v[0-9]|共享记忆文档/|参见已删除' -Encoding utf8
```

Expected: 无匹配。

- [ ] **Step 6: 提交产品文档压缩**

```powershell
git add -- docs/README.md docs/product.md docs/api.md docs/development.md
git commit -m 'docs: compress product and development guidance'
```

---

### Task 3: 压缩架构、AI 与部署边界

**Files:**
- Create: `docs/architecture.md`
- Create: `docs/ai.md`
- Create: `docs/deployment.md`
- Read: `架构师/ARCH-001-SYS-系统总体架构设计-v1.0.md`
- Read: `架构师/ARCH-001-SYS-系统总体架构设计-v1.1.md`
- Read: `架构师/ARCH-001-SYS-系统总体架构设计-v1.2.md`
- Read: `架构师/ARCH-001-SYS-系统总体架构设计-v1.3.md`
- Read: `架构师/ARCH-001-SYS-系统总体架构设计-v1.4.md`
- Read: `架构师/ARCH-001-SYS-系统总体架构设计-v1.5.md`
- Read: `架构师/ARCH-003-DATA-数据库与向量库初版设计-v1.0.md`
- Read: `架构师/ARCH-003-DATA-数据库与向量库初版设计-v1.1.md`
- Read: `架构师/ADR-001-AI-模型适配与意图识别模块编号确认为M04-v1.0.md`
- Read: `架构师/ADR-002-AI-采用本地BGE检索模型-v1.0.md`
- Read: `架构师/ADR-003-AI-BGE检索阈值与RTX4060容量基线-v1.0.md`
- Read: `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`
- Read: `架构师/ADR-005-AI-知识语义类型与发布审批边界-v1.0.md`
- Read: `架构师/ADR-006-CROSS-TikTok人工辅助首版发布范围-v1.0.md`
- Read: `架构师/ADR-007-INFRA-Rootless-Staging部署边界-v1.0.md`
- Read: `AI agent 开发工程师/AI-001-MODEL-模型适配与意图评测规范-v1.0.md`
- Read: `AI agent 开发工程师/AI-002-RAG-FAQ检索与Agent工作流规范-v1.0.md`
- Read: `AI agent 开发工程师/AI-002-RAG-FAQ检索与Agent工作流规范-v1.1.md`
- Read: `AI agent 开发工程师/AI-002-RAG-FAQ检索与Agent工作流规范-v1.2.md`
- Read: `AI agent 开发工程师/AI-002-RAG-FAQ检索与Agent工作流规范-v1.3.md`
- Read: `AI agent 开发工程师/AI-002-RAG-FAQ检索与Agent工作流规范-v1.4.md`
- Read: `AI agent 开发工程师/AI-003-MODEL-BGE本地模型下载与校验指南-v1.0.md`
- Read: `AI agent 开发工程师/AI-004-TOOL-业务工具与安全接管规范-v1.0.md`
- Read: `AI agent 开发工程师/AI-005-REPLY-回复翻译营销与评测规范-v1.0.md`
- Read: `AI agent 开发工程师/AI-005-REPLY-回复翻译营销与评测规范-v1.1.md`
- Read: `AI agent 开发工程师/AI-005-REPLY-回复翻译营销与评测规范-v1.2.md`
- Read: `AI agent 开发工程师/AI-005-REPLY-回复翻译营销与评测规范-v1.3.md`
- Read: `AI agent 开发工程师/AI-005-REPLY-回复翻译营销与评测规范-v1.4.md`
- Read: `AI agent 开发工程师/AI-005-REPLY-回复翻译营销与评测规范-v1.5.md`
- Read: `AI agent 开发工程师/AI-006-SAFETY-知识语义类型与发布审批架构评审请求-v1.0.md`

**Interfaces:**
- Consumes: 已确认架构、ADR、AI 规范、产品配置和数据库迁移。
- Produces: 产品 README、部署说明、发布门禁和测试状态引用的当前技术边界。

- [ ] **Step 1: 生成完整当前架构**

`docs/architecture.md` 固定包含：单仓库边界、Next.js/FastAPI/PostgreSQL/Redis/MinIO 组件、API/Worker/Agent/模型服务数据流、店铺隔离、工具执行边界、当前迁移 `023_marketing_review_idempotency`、BGE-M3 1024 维混合检索、真实平台适配和失败关闭。每节必须可独立理解，不出现版本继承语句。

- [ ] **Step 2: 生成完整当前 AI 契约**

`docs/ai.md` 固定包含：模型 Provider、Prompt/DLP 版本、RAG Top-20→Top-5 与 `0.52` 阈值、知识语义/逐版本审批、可信业务声明、工具白名单、人工复核/转人工终态、翻译营销边界、观测指标。明确 DeepSeek 不是业务事实来源，Agent 不直接访问平台 SDK 或业务数据库，公开自动回复继续关闭。

- [ ] **Step 3: 生成部署当前版**

`docs/deployment.md` 固定包含：环境分层、Compose 叠加关系、Rootless staging、split-ingress、TikTok 回调域名、模型固定 Revision/哈希权威来源、配置默认关闭项、真实消息 `unknown` 对账、备份/回滚入口。staging 当前域名使用 `staging.overselfx.com`，旧 staging 域名不得作为有效配置出现。

- [ ] **Step 4: 交叉核对高风险边界**

```powershell
Select-String -Path docs/architecture.md,docs/ai.md,docs/deployment.md -Pattern 'AUTO_REPLY_ENABLED=false|REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED=false|0\.52|023_marketing_review_idempotency|staging\.overselfx\.com' -Encoding utf8
```

Expected: 五类当前事实均至少出现一次；自动回复和高风险写入只以关闭或未放行语义出现。

- [ ] **Step 5: 提交架构压缩**

```powershell
git add -- docs/architecture.md docs/ai.md docs/deployment.md
git commit -m 'docs: consolidate architecture and AI boundaries'
```

---

### Task 4: 压缩门禁、测试、待办和历史

**Files:**
- Create: `docs/release-gates.md`
- Create: `docs/test-status.md`
- Create: `docs/open-work.md`
- Create: `docs/history.md`
- Read: `架构师/验收-001-CROSS-真实环境生产放行检查表-v1.1.md`
- Read: `共享记忆文档/测试报告索引.md`
- Read: `共享记忆文档/实施记录索引.md`
- Read: `全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md`
- Read: `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md`
- Read: `架构师/PLAN-001-REAL-真实平台与AI生产环境接入实施计划-v1.0.md`

**Interfaces:**
- Consumes: 当前生产检查表、正式报告索引、计划和发布基线。
- Produces: 当前发布判断、最新测试结论、未完成事项和历史追溯入口。

- [ ] **Step 1: 编写生产门禁矩阵**

`docs/release-gates.md` 使用 G0～G8 表格，每行包含范围、当前状态、阻断条件、证据路径和下一动作。沿用 v1.1 当前状态，并吸收 `origin/main@960e62a` 的 split-ingress 更新；不得把基础设施已就绪写成应用真实部署通过。

- [ ] **Step 2: 编写测试状态矩阵**

`docs/test-status.md` 按 M00/M01/M02/M03/M04 和 REAL-FS/REAL-AI 主题汇总。BGE 质量记录 Recall@20=100%、Rerank Recall@5=100%、拒判率=100%、阈值=0.52；GPU 容量记录 50 并发零失败、Embedding P99=375.22ms、Reranker P99=1966.59ms、显存峰值 3697MB。真实 TikTok、真实 DeepSeek SSE、五日稳定性按检查表如实标记未完成或阻塞。

- [ ] **Step 3: 只保留未完成工作**

`docs/open-work.md` 固定按优先级列出：真实密钥轮换、真实店铺 OAuth/只读/Webhook/人工消息、真实 DeepSeek 质量、50 客户端 SSE、五日稳定性、备份恢复、生产回滚、生产最终签署。已经完成的 Mock、确定性测试和工程实现只作为前置条件概述，不复制任务步骤。

- [ ] **Step 4: 编写压缩历史**

`docs/history.md` 按日期记录 Phase 1～4、BGE 切换、TikTok/DeepSeek 安全边界、GitHub Flow、v0.1 基线、Rootless staging 和 split-ingress。每项只写结果、关键编号、提交/标签和遗留风险；开头说明旧实施记录和报告全文可通过 Git 标签 `v0.1.0-mvp.20260907` 及其之前提交读取。

- [ ] **Step 5: 检查测试结论与门禁没有夸大**

```powershell
Select-String -Path docs/release-gates.md,docs/test-status.md,docs/open-work.md -Pattern '生产已放行|完整 MVP 已完成|自动回复已开放|Shopee.*真实接入已完成|Amazon.*真实接入已完成' -Encoding utf8
```

Expected: 无匹配。

- [ ] **Step 6: 提交状态压缩**

```powershell
git add -- docs/release-gates.md docs/test-status.md docs/open-work.md docs/history.md
git commit -m 'docs: compress gates tests and project history'
```

---

### Task 5: 归并机器证据和 BGE 门禁脚本

**Files:**
- Create: `release/evidence/retrieval/bge-quality-threshold-052-20260821.json`
- Create: `release/evidence/retrieval/bge-capacity-gpu-gate-20260821.json`
- Create: `release/evidence/retrieval/bge-gpu-runtime-20260821.json`
- Create: `release/evidence/ai/real-model-independent-v1.0.0.jsonl`
- Create: `release/evidence/ai/real-model-independent-v1.0.0.manifest.json`
- Create: `CRM智能聊天系统/backend/scripts/bge_production_gate.py`
- Modify: `CRM智能聊天系统/deploy/models/model-manifest.json`
- Modify: `release/baselines/v0.1.0-mvp.20260907.json`

**Interfaces:**
- Consumes: 冻结证据原字节、旧 BGE 门禁脚本和现有 `scripts/evaluate_rag.py`。
- Produces: 角色无关的发布证据路径、保持原 SHA-256 的评测集、可重复执行的质量/容量门禁。

- [ ] **Step 1: 复制最小机器证据白名单**

仅复制以下五个冻结文件到目标路径，不复制其他 `测试工程师/evidence/` 内容：

```powershell
New-Item -ItemType Directory -Force -Path release/evidence/retrieval,release/evidence/ai
Copy-Item -LiteralPath '测试工程师/evidence/bge-quality-threshold-052-20260821.json' -Destination 'release/evidence/retrieval/bge-quality-threshold-052-20260821.json'
Copy-Item -LiteralPath '测试工程师/evidence/bge-capacity-gpu-gate-20260821.json' -Destination 'release/evidence/retrieval/bge-capacity-gpu-gate-20260821.json'
Copy-Item -LiteralPath '测试工程师/evidence/bge-gpu-runtime-20260821.json' -Destination 'release/evidence/retrieval/bge-gpu-runtime-20260821.json'
Copy-Item -LiteralPath '测试工程师/evidence/REAL-AI-05-002/real-model-independent-v1.0.0.jsonl' -Destination 'release/evidence/ai/real-model-independent-v1.0.0.jsonl'
Copy-Item -LiteralPath '测试工程师/evidence/REAL-AI-05-002/real-model-independent-v1.0.0.manifest.json' -Destination 'release/evidence/ai/real-model-independent-v1.0.0.manifest.json'
```

- [ ] **Step 2: 验证冻结评测集字节未改变**

```powershell
(Get-FileHash -Algorithm SHA256 'release/evidence/ai/real-model-independent-v1.0.0.jsonl').Hash.ToLower()
(Get-FileHash -Algorithm SHA256 'release/evidence/ai/real-model-independent-v1.0.0.manifest.json').Hash.ToLower()
```

Expected: 分别为 `7f7c7084ac37e9aef5c9b1a947a9f44250cd89e290f5ae18990ec558e5c6df94` 和 `232f52a3fa5f5c33622f25a87456128aa9c553a5c00da682bbce2cb8cb3d6905`。

- [ ] **Step 3: 提炼 BGE 门禁脚本**

将旧 `测试工程师/scripts/bge_production_gate.py` 的 HTTP 容量测试、显存采样和 JSON 输出迁入 `backend/scripts/bge_production_gate.py`；质量样本模型、`cosine_similarity` 和 `load_cases` 从同目录 `evaluate_rag.py` 导入，删除重复定义。保留 CLI：`--mode quality|capacity|all`、`--base-url`、`--dataset`、`--output`、`--configured-threshold`、`--sample-gpu`，并保持失败门禁以非零退出。

- [ ] **Step 4: 更新模型清单和发布基线路径**

`model-manifest.json` 保持字段名不变，值改为：

```json
"quality_gate_report": "release/evidence/retrieval/bge-quality-threshold-052-20260821.json",
"capacity_gate_report": "release/evidence/retrieval/bge-capacity-gpu-gate-20260821.json"
```

发布基线改为：

```json
"dataset_path": "release/evidence/ai/real-model-independent-v1.0.0.jsonl",
"dataset_manifest_path": "release/evidence/ai/real-model-independent-v1.0.0.manifest.json"
```

摘要字段保持原值，因为冻结文件字节不变。

- [ ] **Step 5: 运行证据和脚本测试**

```powershell
Set-Location 'CRM智能聊天系统/backend'
uv run ruff check scripts/bge_production_gate.py
uv run mypy scripts/bge_production_gate.py
uv run pytest tests/test_retrieval_model_asset_hashes.py -v
```

Expected: Ruff、mypy 和两个证据测试通过；目录删除测试仍可失败。

- [ ] **Step 6: 提交机器证据归并**

```powershell
git add -- release/evidence 'CRM智能聊天系统/backend/scripts/bge_production_gate.py' 'CRM智能聊天系统/deploy/models/model-manifest.json' 'release/baselines/v0.1.0-mvp.20260907.json'
git commit -m 'build: consolidate release evidence'
```

---

### Task 6: 更新项目规则和活动引用

**Files:**
- Modify: `AGENTS.md`
- Modify: `CRM智能聊天系统/AGENTS.md`
- Modify: `.github/CODEOWNERS`
- Modify: `.github/pull_request_template.md`
- Modify: `CRM智能聊天系统/README.md`
- Modify: `CRM智能聊天系统/deploy/models/README.md`
- Modify: `CRM智能聊天系统/deploy/staging/rootless/README.md`
- Modify: `CRM智能聊天系统/deploy/production/README.md`
- Modify: applicable files under `docs/superpowers/plans/` and `docs/superpowers/specs/`

**Interfaces:**
- Consumes: 新 `docs/README.md`、发布证据路径和当前产品入口。
- Produces: 删除旧目录后仍然闭合的协作、部署、发布和审阅流程。

- [ ] **Step 1: 将根 AGENTS 改为唯一项目规范**

根 `AGENTS.md` 只保留：实施前从 `docs/README.md` 选择相关当前文档、代码前阅读 `docs/development.md`、产品代码归属、安全边界、测试、文档同步和 GitHub Flow。删除六类角色身份、目录职责、角色交接和逐任务实施记录要求。

- [ ] **Step 2: 精简产品 AGENTS**

产品 `AGENTS.md` 只描述 `CRM智能聊天系统/` 内的工程约束，引用根 AGENTS、`docs/development.md`、`docs/api.md`、`docs/architecture.md` 和 `docs/ai.md`；不得要求读取角色目录或项目 Skill 副本。

- [ ] **Step 3: 更新 GitHub 所有权和 PR 模板**

CODEOWNERS 将旧三条角色目录规则替换为 `/docs/ @CP11-gh`，保留 `/release/` 和敏感产品路径。PR 模板把“架构、共享文档或实施记录”改为“文档或发布证据”，把两条旧文档同步复选框改为：

```markdown
- [ ] 当前文档、发布门禁或机器证据已按变更风险同步
- [ ] 不适用的测试和文档项已说明原因
```

- [ ] **Step 4: 更新产品和部署入口**

产品 README 的 Git 规范、ADR、测试报告和 BGE 指南链接改到新文档/证据；模型 README 以 `docs/deployment.md` 为下载校验指南；staging/production README 分别链接 `docs/deployment.md` 和 `docs/release-gates.md`，不再以架构师或测试工程师路径作为权威入口。

- [ ] **Step 5: 清理仍作为当前依据的 superpowers 文档引用**

保留设计历史正文，但将其中用于执行命令、文件创建或当前权威入口的旧路径改为新路径；纯历史叙述可以保留旧目录名称。结构测试已排除 `docs/superpowers/`，因此这一步必须人工审查差异，不能依靠测试豁免跳过。

- [ ] **Step 6: 扫描活动引用**

```powershell
git -c core.quotepath=false grep -n -I -E '共享记忆文档/|测试工程师/|架构师/|开发工具/|全栈开发工程师/|AI agent 开发工程师/' -- AGENTS.md .github 'CRM智能聊天系统' release docs ':!docs/superpowers/**' ':!docs/history.md'
```

Expected: 无输出。

- [ ] **Step 7: 提交规则和引用修复**

```powershell
git add -- AGENTS.md .github 'CRM智能聊天系统/AGENTS.md' 'CRM智能聊天系统/README.md' 'CRM智能聊天系统/deploy' docs/superpowers
git commit -m 'docs: remove role-based repository references'
```

---

### Task 7: 删除六个子智能体目录

**Files:**
- Delete: `全栈开发工程师/`
- Delete: `AI agent 开发工程师/`
- Delete: `共享记忆文档/`
- Delete: `开发工具/`
- Delete: `架构师/`
- Delete: `测试工程师/`

**Interfaces:**
- Consumes: Tasks 2～6 已提交的压缩文档、机器证据和新路径引用。
- Produces: 不再包含角色型一级目录的仓库工作树。

- [ ] **Step 1: 最后确认删除目标是六个明确目录**

```powershell
$expected=@('全栈开发工程师','AI agent 开发工程师','共享记忆文档','开发工具','架构师','测试工程师')
$resolved=$expected | ForEach-Object { (Resolve-Path -LiteralPath $_).Path }
$root=(Resolve-Path -LiteralPath '.').Path
$resolved | ForEach-Object { if(-not $_.StartsWith($root + [IO.Path]::DirectorySeparatorChar)){ throw "删除目标越出工作区: $_" } }
$resolved
```

Expected: 只输出当前隔离 worktree 下的六个绝对路径。

- [ ] **Step 2: 使用 Git 删除六个跟踪目录**

```powershell
git rm -r -- '全栈开发工程师' 'AI agent 开发工程师' '共享记忆文档' '开发工具' '架构师' '测试工程师'
```

- [ ] **Step 3: 运行结构与证据检查**

```powershell
Get-ChildItem -LiteralPath docs -File | Measure-Object
git -c core.quotepath=false grep -n -I -E '共享记忆文档/|测试工程师/|架构师/|开发工具/|全栈开发工程师/|AI agent 开发工程师/' -- AGENTS.md .github 'CRM智能聊天系统' release docs ':!docs/superpowers/**' ':!docs/history.md'
```

Expected: 根 `docs/` 长期文档不超过十五份；旧路径活动引用扫描无输出。

- [ ] **Step 4: 审查删除规模和新建规模**

```powershell
git diff --stat origin/main...HEAD
git status --short
Get-ChildItem -LiteralPath '../../docs' -File | Measure-Object
```

Expected: 六个目录全部标记删除；根 `docs/` 长期文档数量不超过十五；没有未计划的产品代码变更。

- [ ] **Step 5: 提交目录删除**

```powershell
git commit -m 'chore: remove role-based project directories'
```

---

### Task 8: 必要验证与一次性迁移说明

**Files:**
- Modify when verification exposes a defect: `AGENTS.md`
- Modify when verification exposes a defect: `.github/CODEOWNERS`
- Modify when verification exposes a defect: `.github/pull_request_template.md`
- Modify when verification exposes a defect: `docs/README.md`
- Modify when verification exposes a defect: `docs/product.md`
- Modify when verification exposes a defect: `docs/api.md`
- Modify when verification exposes a defect: `docs/architecture.md`
- Modify when verification exposes a defect: `docs/ai.md`
- Modify when verification exposes a defect: `docs/development.md`
- Modify when verification exposes a defect: `docs/deployment.md`
- Modify when verification exposes a defect: `docs/release-gates.md`
- Modify when verification exposes a defect: `docs/test-status.md`
- Modify when verification exposes a defect: `docs/open-work.md`
- Modify when verification exposes a defect: `docs/history.md`
- Modify when verification exposes a defect: `release/baselines/v0.1.0-mvp.20260907.json`
- Modify when verification exposes a defect: `CRM智能聊天系统/deploy/models/model-manifest.json`
- Modify when verification exposes a defect: `CRM智能聊天系统/backend/scripts/bge_production_gate.py`
- Do not create: any file under the six deleted directories

**Interfaces:**
- Consumes: 完整结构清理结果。
- Produces: 可审阅的验证证据和干净分支，不再生成角色实施记录。

- [ ] **Step 1: 验证 Git 和文档结构**

```powershell
git status --short --branch
git diff --check origin/main...HEAD
git -c core.quotepath=false ls-files | Select-String -Pattern '^(全栈开发工程师|AI agent 开发工程师|共享记忆文档|开发工具|架构师|测试工程师)/'
```

Expected: diff check 无错误；旧目录没有跟踪文件。

- [ ] **Step 2: 验证 JSON 和冻结摘要**

```powershell
Get-Content -LiteralPath 'release/baselines/v0.1.0-mvp.20260907.json' -Raw | ConvertFrom-Json | Out-Null
Get-Content -LiteralPath 'CRM智能聊天系统/deploy/models/model-manifest.json' -Raw | ConvertFrom-Json | Out-Null
Set-Location 'CRM智能聊天系统/backend'
uv run pytest tests/test_retrieval_model_asset_hashes.py -v
```

Expected: JSON 解析成功，结构和模型清单测试通过。

- [ ] **Step 3: 运行受影响文件的静态检查**

```powershell
Set-Location 'CRM智能聊天系统/backend'
uv lock --check
uv run ruff check scripts/bge_production_gate.py
uv run ruff format --check scripts/bge_production_gate.py
uv run mypy scripts/bge_production_gate.py
```

Expected: 锁文件有效，两个受影响的 Python 文件通过 Ruff 和 mypy。

- [ ] **Step 4: 明确不重复执行无关产品回归**

本次不修改前端、业务后端、数据库迁移、运行配置或依赖，因此不执行完整后端 pytest、前端 `npm ci`、lint、typecheck、测试或生产构建。最终交付明确记录这些检查未执行及原因，不把历史结果描述为本分支验证结果。

- [ ] **Step 5: 运行敏感信息和旧路径最终扫描**

```powershell
Set-Location '../..'
git -c core.quotepath=false grep -n -I -E '(sk-[A-Za-z0-9_-]{16,}|Bearer [A-Za-z0-9._-]{16,}|BEGIN (RSA |EC )?PRIVATE KEY)' -- .
git -c core.quotepath=false grep -n -I -E '共享记忆文档/|测试工程师/|架构师/|开发工具/|全栈开发工程师/|AI agent 开发工程师/' -- AGENTS.md .github 'CRM智能聊天系统' release docs ':!docs/superpowers/**' ':!docs/history.md'
```

Expected: 两次扫描均无输出。

- [ ] **Step 6: 记录最终规模和验证结果**

在最终提交说明和 PR 描述中记录：删除文件数、新增长期文档数、保留机器证据数、净行数变化、实际测试结果和未执行的真实平台门禁。不要创建旧规则要求的角色实施记录。

- [ ] **Step 7: 提交验证中产生的修正**

只有验证确实产生文件修正时执行：

```powershell
git add -- AGENTS.md .github docs release 'CRM智能聊天系统'
git commit -m 'docs: finalize repository cleanup validation'
```

- [ ] **Step 8: 最终分支检查**

```powershell
git status --short --branch
git log --oneline --decorate origin/main..HEAD
```

Expected: 工作树干净，提交按结构契约、文档压缩、证据归并、引用修复、目录删除和验证修正分层排列。
