# 文档职责域分类设计

**日期：** 2026-09-16  
**治理档位：** `STANDARD`  
**变更类型：** 纯文档目录重组  
**状态：** 待用户书面规格确认

## 背景与目标

`docs/` 当前同时在根目录放置产品、架构、工程、运维、治理和历史文档，另有任务、质量、记忆及 Superpowers 过程文档子目录。随着 Codex 桌面版持续参与开发，根目录职责不够清晰，容易增加文档选择和链接维护成本。

本次变更只调整当前文档的目录与名称，并同步有效引用。它不修改项目源码、运行配置、产品范围、接口结论、测试结论或发布结论。

## 设计原则

1. 按稳定职责域分类，而不是按临时阶段、岗位或里程碑分类。
2. `docs/README.md` 保持为唯一文档入口，并说明每个分类的职责和事实优先级。
3. 每份当前事实文档只有一个正式位置，不创建兼容副本或分类级 `README.md`。
4. `docs/tasks/TASKS.md` 继续作为任务状态唯一事实源；`docs/memory/PROJECT-STATE.md` 继续作为跨会话恢复摘要。
5. `docs/superpowers/specs/` 与 `docs/superpowers/plans/` 保持原位，兼容现有 Skill 的默认输出位置。
6. 历史规格和计划保留其形成时的路径描述，不批量改写历史证据。

## 目标目录

```text
docs/
├─ README.md
├─ product/
│  └─ PRODUCT.md
├─ architecture/
│  ├─ SYSTEM.md
│  ├─ API.md
│  └─ AI.md
├─ engineering/
│  └─ DEVELOPMENT.md
├─ quality/
│  ├─ TEST-STRATEGY.md
│  └─ TEST-STATUS.md
├─ operations/
│  ├─ DEPLOYMENT.md
│  └─ RELEASE-GATES.md
├─ governance/
│  └─ GOVERNANCE.md
├─ tasks/
│  └─ TASKS.md
├─ memory/
│  └─ PROJECT-STATE.md
├─ history/
│  └─ PROJECT-HISTORY.md
└─ superpowers/
   ├─ specs/
   └─ plans/
```

## 路径映射

| 当前路径 | 目标路径 | 职责 |
| --- | --- | --- |
| `docs/product.md` | `docs/product/PRODUCT.md` | 产品范围、用户、能力边界和验收口径 |
| `docs/architecture.md` | `docs/architecture/SYSTEM.md` | 系统边界、模块、数据流和架构约束 |
| `docs/api.md` | `docs/architecture/API.md` | 接口约定和端点事实 |
| `docs/ai.md` | `docs/architecture/AI.md` | AI 流程、模型和评测边界 |
| `docs/development.md` | `docs/engineering/DEVELOPMENT.md` | 开发规范、分层、命令和实现约束 |
| `docs/test-status.md` | `docs/quality/TEST-STATUS.md` | 当前测试状态与最近证据 |
| `docs/deployment.md` | `docs/operations/DEPLOYMENT.md` | 部署拓扑、步骤和运行约束 |
| `docs/release-gates.md` | `docs/operations/RELEASE-GATES.md` | 发布门禁和放行条件 |
| `docs/governance.md` | `docs/governance/GOVERNANCE.md` | 决策、证据、记录和批准规则 |
| `docs/history.md` | `docs/history/PROJECT-HISTORY.md` | 历史事实和阶段记录 |

以下路径保持不变：`docs/README.md`、`docs/tasks/TASKS.md`、`docs/memory/PROJECT-STATE.md`、`docs/quality/TEST-STRATEGY.md` 和 `docs/superpowers/**`。

## 引用更新边界

更新所有当前有效入口和说明中的旧路径，包括：

- 根目录 `AGENTS.md` 与 `README.md`；
- `docs/README.md` 和全部当前事实文档；
- `docs/tasks/TASKS.md`、`docs/memory/PROJECT-STATE.md`、`docs/quality/TEST-STRATEGY.md`；
- `tests/README.md`、部署说明和模型说明等仍被维护的文档；
- 其他代码或配置中真实依赖这些路径的引用。

`docs/superpowers/specs/**` 与 `docs/superpowers/plans/**` 中已经形成的旧路径保留，避免改变历史计划和证据的语义。本设计规格及后续实施计划也属于历史过程文档。

## 执行与恢复

变更在 `codex/docs-classify-documentation` 短期分支和独立 worktree 中执行。文件移动使用 Git 可识别的重命名，引用更新作为可审阅差异提交。

若验证失败，先修复引用或目录映射；若决定放弃整个未共享变更，可删除该短期 worktree 和分支。不得用破坏性 Git 覆盖主工作区。

## 验收标准

1. 目标目录与路径映射全部成立，旧的十个当前文档路径不再存在。
2. `docs/README.md` 能从一个入口准确路由到所有当前事实文档，并说明分类职责。
3. 除历史 `docs/superpowers/**` 外，活动文件中不再引用旧路径。
4. 活动 Markdown 相对链接均能解析到存在的仓库文件或有效锚点范围内的目标文件。
5. `AGENTS.md` 中的项目规则指向新路径，且核心治理语义保持不变。
6. Git 差异不包含项目源码、运行配置、密钥、生成物或无关内容。
7. `git diff --check` 通过；目录、旧路径、链接和敏感信息检查通过。

## 验证策略

这是静态文档变更，不运行无关产品测试。验证包括：

- Git 状态、差异范围和重命名检查；
- 目标文件存在性与旧文件不存在性检查；
- 排除历史过程文档后的旧路径全文扫描；
- 活动 Markdown 本地链接解析检查；
- `git diff --check`；
- 常见密钥和敏感信息模式扫描。

## 非目标

- 不重写文档中的产品、架构、接口、部署、测试或发布结论。
- 不修改应用源码、测试源码、依赖、CI、容器或生产配置。
- 不新增文档站点生成器、重定向层、兼容副本或索引自动化。
- 不推送远端、不创建或合并 Pull Request、不发布版本。
