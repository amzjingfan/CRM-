# CRM 智能聊天系统

面向跨境电商客服的 TikTok Shop 工作台。项目采用单仓库模块化单体：FastAPI 提供业务与平台接口，Next.js 提供管理端，PostgreSQL/pgvector、Redis、MinIO 和本地 BGE 模型服务支持会话、知识检索与 AI 建议。

当前交付以 TikTok 店铺为范围。系统提供店铺授权、消息接入、客服会话、订单与物流只读核对、人工审阅发送、知识库、Agent 配置及部门接待协作。自动化能力受环境、店铺授权、策略开关和安全门禁约束；代码中有入口不代表已在所有环境开放。

## 当前状态

- 原仓库 main 是已合并代码的基线；各工作树中的未提交改动和未合并分支不自动计入发布版本。
- staging 已开展 TikTok 多店人工接待及受控 Agent/自动化验收。实际启用范围、现场限制和最新证据以[发布门禁](docs/operations/RELEASE-GATES.md)及[部署说明](docs/operations/DEPLOYMENT.md)为准。
- production 仍为 No-Go。Shopee 和 Amazon 的真实接入、高风险平台写入以及未经批准的自动营销不属于当前放行范围。

完整产品边界见[产品范围](docs/product/PRODUCT.md)；实施任务状态见[任务表](docs/tasks/TASKS.md)。历史设计与测试记录不能代替当前环境的发布证据。

## 项目结构

| 路径 | 内容 |
|---|---|
| src/backend/ | FastAPI 模块化单体、平台适配器、Agent、后台任务与数据库迁移 |
| src/frontend/ | Next.js 客服工作台、知识库、Agent、营销和系统设置 |
| src/compose/、src/deploy/ | 本地及受控环境的服务编排、部署资产 |
| src/tests/ | 后端、前端、PostgreSQL 集成测试及普通 AI 评测资产 |
| docs/ | 产品、架构、工程、质量、治理与发布状态的当前文档 |
| release/ | 版本基线和经脱敏的发布证据 |

文档入口见[docs/README.md](docs/README.md)。架构与权限边界见[系统架构](docs/architecture/SYSTEM.md)、[接口](docs/architecture/API.md)和[AI](docs/architecture/AI.md)。

## 本地启动

需要 PowerShell 5.1 或更新版本及可用的 Docker Compose。首次启动先从示例配置创建仅供本机使用的环境文件，填入开发环境所需配置：

    Copy-Item src/config/.env.example src/config/.env
    ./src/scripts/start-local.ps1

启动脚本使用 src/compose/docker-compose.yml 构建并运行本地服务。管理端默认地址为 http://localhost:3000；后端健康检查为 http://localhost:8000/v1/health。需要真实 TikTok、模型或部署环境时，遵循[部署说明](docs/operations/DEPLOYMENT.md)的独立配置与授权流程，不把本地示例配置用于生产。

## 验证入口

后端在 src/backend/ 执行：

    uv sync --frozen --all-groups
    uv run ruff check . ../tests/backend ../tests/integration/postgres
    uv run ruff format --check . ../tests/backend ../tests/integration/postgres
    uv run mypy app scripts
    uv run pytest

前端在 src/frontend/ 执行：

    npm ci
    npm run lint
    npm run typecheck
    npm run test
    npm run build

PostgreSQL/pgvector 隔离集成测试、浏览器测试和 AI 评测的运行条件见[测试入口](src/tests/README.md)与[测试策略](docs/quality/TEST-STRATEGY.md)。本地通过不等于真实 TikTok 或 production 放行。

## 安全与协作

- 店铺访问由服务端授权；人工发送须复核收件人和准确内容，发送结果不确定时先对账，禁止盲目重试。
- 不提交 src/config/.env、真实密钥或 Token、客户数据、模型权重、依赖目录、缓存及测试临时输出。
- 从真实 main 创建短期分支，完成适用验证和审查后按项目规则合并。详见[开发规范](docs/engineering/DEVELOPMENT.md)与[治理规则](docs/governance/GOVERNANCE.md)。
