# 首版 Rootless Staging 根目录扁平化设计

## 1. 背景与决定

当前 Git 根目录为 `E:\develop\CRM智能聊天系统`，产品工程位于同名子目录
`CRM智能聊天系统/`。本次决定保留外层目录作为唯一 Git 根，将产品工程提升到仓库根，
并把产品代码恢复为源提交 `77d9f8f`（首版 Rootless Staging）的状态。

迁移采用向前提交，不移动 `.git`，不使用 `git reset --hard`，也不改写或删除现有提交历史。
因此 `77d9f8f`、迁移前的本地 `main`（`8235443`）以及此前汇总到 `main` 的分支历史仍可追溯。

## 2. 目标状态

迁移后仓库根直接包含：

- `backend/`、`frontend/`、`deploy/`、`scripts/`、`tests/`；
- Dockerfile、Compose 文件、`.env.example`、`.mcp.json` 和产品 `README.md`；
- 根级 `.github/`、`docs/`、`release/`、`.gitattributes`、`.gitignore` 和 `AGENTS.md`。

Git 不再跟踪 `CRM智能聊天系统/` 嵌套产品目录。此前已删除的岗位或子智能体一级目录不恢复。

## 3. 基线与历史策略

- 产品源码、测试和部署资产以 `77d9f8f:CRM智能聊天系统/` 为权威快照。
- Rootless Staging 工作流和发布清单以 `77d9f8f` 的根级 `.github/`、`docs/`、`release/`
  为历史依据，但迁移后必须改成根目录路径。
- 当前用途型文档结构保留，内容回写到首版 Rootless Staging 的事实，不恢复旧岗位文档体系。
- 迁移在 `feature/flatten-rootless-staging-root` 分支形成新的向前提交；源 SHA 写入迁移说明。

## 4. 路径迁移规则

| 迁移前 | 迁移后 | 处理方式 |
| --- | --- | --- |
| `CRM智能聊天系统/backend/` | `backend/` | 使用 `77d9f8f` 快照替换 |
| `CRM智能聊天系统/frontend/` | `frontend/` | 使用 `77d9f8f` 快照替换 |
| `CRM智能聊天系统/deploy/` | `deploy/` | 保留首版 Rootless Staging 资产 |
| `CRM智能聊天系统/scripts/` | `scripts/` | 使用首版门禁与回滚脚本 |
| `CRM智能聊天系统/tests/` | `tests/` | 使用 `77d9f8f` 快照替换 |
| `CRM智能聊天系统/*` 根文件 | 仓库根 | 与根级文件逐项合并 |
| `.github/` | `.github/` | 恢复首版工作流并移除嵌套路径前缀 |
| `docs/`、`release/` | 原位置 | 同步 Staging 事实并修正路径 |

路径修正覆盖 CI 的 `working-directory`、缓存路径、Docker build context、PowerShell 脚本入口、
CODEOWNERS、部署说明和发布清单。绝对服务器路径只有在确实依赖仓库层级时才修改。

## 5. 本地数据和安全边界

- 不读取、提交或输出 `CRM智能聊天系统/.env` 的内容。
- `.env`、IDE 配置、缓存和测试临时目录不属于代码迁移；本次不主动删除这些未跟踪文件。
- 不迁移模型权重、凭证、Token、日志、构建产物、虚拟环境或依赖目录。
- 迁移前后的受版本控制内容均可由 Git 历史恢复；不删除外层 `.worktrees/`。

## 6. 远程仓库策略

本次不修改现有 `origin`，也不推送。目录迁移完成后，待用户提供新的 GitHub 地址，再单独执行：

1. 记录旧远程地址；
2. 更新或替换 `origin`；
3. 验证 fetch/push URL；
4. 经明确授权后推送分支或 `main`。

## 7. 验收标准

本次执行最小充分验证：

1. 当前分支不是 `main`，工作区变更仅属于本次迁移。
2. Git 跟踪的产品代码位于仓库根，不再位于 `CRM智能聊天系统/`。
3. 根级产品文件与 `77d9f8f:CRM智能聊天系统/` 的内容一致，允许的差异仅为路径适配和当前文档。
4. `.github`、部署脚本、文档和发布清单中不再使用已废弃的仓库内嵌套前缀。
5. 首版 Rootless Staging 资产存在，Split-ingress 和 K2 后续代码不进入目标产品快照。
6. `.env` 和其他敏感或本地文件未进入 Git。
7. 运行 Git 状态、历史、文件清单和关键配置静态检查；不运行大规模测试。

## 8. 风险与恢复

- **路径遗漏：** 使用版本库全文检索检查旧前缀，并人工核对 CI、Compose 和部署入口。
- **同名根文件冲突：** `AGENTS.md` 使用当前项目规范；`.gitignore` 和 `.gitattributes` 合并产品及仓库规则；
  其他产品根文件按 `77d9f8f` 恢复。
- **旧文档与新结构矛盾：** 当前用途型文档优先，不恢复岗位目录；历史细节通过源提交追溯。
- **误覆盖本地配置：** 不读取或迁移 `.env`，不清理内层未跟踪文件。
- **需要撤销：** 迁移为普通提交，可通过新分支、提交父节点或后续 `git revert` 恢复，不需要强制重置。
