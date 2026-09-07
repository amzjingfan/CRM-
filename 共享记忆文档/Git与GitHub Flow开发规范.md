# CRM 智能聊天系统 Git 与 GitHub Flow 开发规范

状态：已确认

版本：v1.0

日期：2026-09-07

## 1. 仓库边界

唯一 Git 仓库根目录为工作区根目录：

```text
E:\develop\CRM智能聊天系统
```

产品代码、架构文档、测试报告、共享记忆文档和开发工具必须在同一提交历史中保持可追溯。正式产品代码仍只允许放在 `CRM智能聊天系统/`。

`.env`、真实密钥、Token、凭证池、模型权重、虚拟环境、`node_modules`、缓存、构建目录、日志和测试临时目录禁止提交。允许提交脱敏的 `.env.example`、模型资产清单及不含敏感正文的测试证据。

## 2. GitHub Flow 原则

- 唯一长期分支是 `main`，它必须始终保持可构建、可测试。
- 每个任务从最新 `main` 创建一个短期分支，一个分支只解决一个目标。
- 所有共享变更通过 Pull Request 合并，默认使用 squash merge。
- CI、人工审阅、文档同步和安全检查通过后才能合并。
- 合并后删除短期分支；发布节点使用带注释标签固定。
- 禁止日常直接提交 `main`、强制推送共享分支或用 `git reset --hard` 覆盖工作。

分支命名：

| 类型 | 格式 | 示例 |
| --- | --- | --- |
| 功能 | `feature/{任务编号}-{主题}` | `feature/P4-07-metric-etl` |
| 修复 | `fix/{缺陷编号}-{主题}` | `fix/DEF-REAL-FS01-005-npm-audit` |
| 文档 | `docs/{任务编号或主题}-{主题}` | `docs/P4-00-release-checklist` |
| 紧急修复 | `hotfix/{缺陷编号}-{主题}` | `hotfix/SEC-001-token-leak` |

主题使用短横线分隔的英文小写词。分支名不得包含密钥、客户、店铺、订单或其他敏感标识。

## 3. 首次本机配置

先确认提交身份。不要把密码或访问令牌写入 Git 配置：

```powershell
git config --global --get user.name
git config --global --get user.email
```

只有输出为空时，才设置自己的真实姓名和工作邮箱：

```powershell
git config --global user.name "你的姓名"
git config --global user.email "你的工作邮箱"
```

本项目当前没有预设 GitHub 远程地址。仓库管理员提供地址后，在仓库根目录执行一次：

```powershell
$RepositoryUrl = "仓库管理员提供的 GitHub HTTPS 或 SSH 地址"
git remote add origin $RepositoryUrl
git remote -v
git push -u origin main
Remove-Variable RepositoryUrl
```

如果 `origin` 已存在，先执行 `git remote -v` 核对，不要直接覆盖。

## 4. 每个任务的标准流程

### 4.1 更新主分支

```powershell
git switch main
git status --short --branch
git pull --ff-only
```

工作区有未提交修改时先确认归属，不得暂存、移动或删除他人的修改。

### 4.2 创建分支和隔离 worktree

基线完成后优先使用 `.worktrees/`：

```powershell
$BranchName = "feature/P4-07-metric-etl"
$WorktreePath = ".worktrees/p4-07-metric-etl"
git worktree add $WorktreePath -b $BranchName main
Set-Location $WorktreePath
git status --short --branch
```

`.worktrees/` 已由根 `.gitignore` 排除。不要把 worktree 放入其他可跟踪目录。

### 4.3 小步修改和验证

```powershell
git status --short
git diff --check
git diff
```

只暂存当前任务文件，禁止无审查使用全量暂存：

```powershell
git add -- path/to/file1 path/to/file2
git diff --cached --check
git diff --cached
```

提交使用 Conventional Commits：

```powershell
git commit -m "feat: implement metric ETL"
```

常用类型为 `feat`、`fix`、`docs`、`test`、`build`、`ci`、`chore`。提交正文应记录任务编号、实际验证和遗留风险。

### 4.4 推送和 Pull Request

```powershell
git push -u origin feature/P4-07-metric-etl
```

在 GitHub 创建面向 `main` 的 Pull Request，完整填写仓库 PR 模板。至少确认：

- 需求和非目标清晰。
- 变更范围单一、没有无关格式化。
- 后端/前端相关质量检查已实际执行。
- 没有密钥、大文件、依赖或缓存误提交。
- README、接口、架构、测试索引和实施记录按影响范围同步。
- 迁移、配置、发布开关和回滚方式已说明。

CI 和审阅通过后使用 squash merge。禁止在 CI 失败时绕过门禁。

### 4.5 合并后清理

在主检出目录执行：

```powershell
git switch main
git pull --ff-only
git worktree remove .worktrees/p4-07-metric-etl
git worktree prune
git branch -d feature/P4-07-metric-etl
```

如果 `git worktree remove` 提示仍有未提交文件，立即停止，先核对并保存这些文件；禁止擅自使用 `--force`。

## 5. 冲突与回滚

共享提交的安全回滚使用新提交，不改写历史：

```powershell
git revert <需要回滚的提交SHA>
git push origin main
```

Pull Request 分支需要同步主分支时，优先把最新 `main` 合并或按团队约定 rebase；已经被他人基于其开发的共享分支不得擅自 rebase 或强制推送。

发现密钥误提交时，不只是删除文件：必须立即停用并轮换凭证、通知项目负责人，再由仓库管理员制定历史清理方案。

## 6. 发布标签和基线

本次工程基线标签固定为 `v0.1.0-mvp.20260907`。带注释标签的通用命令为：

```powershell
git tag -a v0.1.0-mvp.20260907 -m "MVP engineering baseline 2026-09-07; production not released"
git show --no-patch v0.1.0-mvp.20260907
```

配置 GitHub 远程后单独推送标签：

```powershell
git push origin v0.1.0-mvp.20260907
```

标签冻结的是可追溯工程状态，不自动表示生产放行。机器可读证据位于 `release/baselines/v0.1.0-mvp.20260907.json`；生产发布仍须满足架构师生产放行检查表的全部门禁。

## 7. 分支保护建议

GitHub 仓库创建后，由管理员为 `main` 配置：

- 禁止直接 push 和 force push。
- 要求 Pull Request 才能合并。
- 要求后端、前端 CI 检查通过。
- 要求至少一名审阅者批准并解决全部对话。
- 合并后自动删除短期分支。

这些设置由 GitHub 服务端执行；本地规范和 CI 文件不能替代服务器端分支保护。
