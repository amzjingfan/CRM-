# Phase2 平台接入、会话与客服工作台综合测试报告

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| 测试阶段 | Phase2 |
| 任务编号 | P2-00 阶段汇总 |
| 模块编号 | M02 |
| 模块名称 | 平台接入、会话与工作台 |
| 被测主责 Agent | 全栈开发工程师 Agent |
| 测试执行 Agent | 测试工程师 Agent |
| 协作 Agent | 架构师 Agent |
| 被测实施记录 | `共享记忆文档/实施记录/Phase2-P2-00-全栈开发工程师Agent-平台接入会话与客服工作台阶段汇总-001.md` |
| 测试日期 | 2026-08-20 |
| 测试结论 | 有条件通过；代码和后端运行态门禁通过，浏览器页面实测与前端 Compose 启动受环境限制未完成 |

## 2. 测试范围

本次覆盖：

- 三个平台契约级 Mock 适配器、TikTok HMAC、Shopee/Amazon Mock 验签。
- Webhook 载荷校验、首次接收、重复投递幂等、Worker 处理和事件状态。
- Phase 2 数据库迁移、pgvector、店铺/渠道/客户/会话/消息/订单/Webhook/审计表。
- HttpOnly Cookie、CSRF、浏览器认证、RBAC、工作台会话列表、消息详情和人工发送。
- 后端质量门禁、前端 lint/typecheck/test/build、Compose 配置和已运行基础设施。

明确不纳入本次通过判定：真实 TikTok/Shopee/Amazon 联调、真实平台凭证、AI Agent、Prompt、RAG、SSE AI 回复和生产部署。

## 3. 测试环境

| 项目 | 实际环境 |
| --- | --- |
| 后端 | Python 3.11 虚拟环境，FastAPI 模块化单体 |
| 数据库 | Docker `pgvector/pgvector:pg16` |
| Redis | Docker `redis:7-alpine` |
| MinIO | Docker `minio/minio:latest` |
| 前端 | Next.js 15.5.23，Node/npm 本地依赖已安装 |
| 运行目录 | `CRM智能聊天系统/` |

## 4. 执行结果汇总

| 类别 | 验证项 | 结果 | 状态 |
| --- | --- | --- | --- |
| 后端 | `ruff check app migrations scripts tests` | All checks passed | 通过 |
| 后端 | `mypy app scripts` | 100 source files，无错误 | 通过 |
| 后端 | `pytest -q` | 46 passed，2 warnings，0 failed | 通过 |
| 后端 | `python -m compileall -q app migrations scripts` | 完成，无编译错误 | 通过 |
| 前端 | `npm run lint` | 成功 | 通过 |
| 前端 | `npm run typecheck` | 成功 | 通过 |
| 前端 | `npm run test` | 7 passed，0 failed | 通过 |
| 前端 | `npm run build` | Next.js 生产构建成功，生成 `/workspace` 等页面 | 通过 |
| 基础设施 | `docker-compose config --quiet` | 成功 | 通过 |
| 基础设施 | `docker-compose ps` | PostgreSQL、Redis、MinIO、backend、worker、jobs 均运行；frontend 未运行 | 条件通过 |
| 健康检查 | `GET /v1/health` | HTTP 200，`code=0`，`status=ok` | 通过 |
| 迁移 | 临时数据库 `upgrade head → downgrade base → upgrade head` | 001～013 全部成功，临时库已清理 | 通过 |

## 5. 关键功能测试

### 5.1 认证与安全

| 用例 | 预期 | 实际 | 状态 |
| --- | --- | --- | --- |
| 浏览器登录 | 设置 Cookie，返回成功响应 | `POST /v1/auth/browser/login` 返回 `code=0`；Cookie 包含 `crm_access_token`、`crm_csrf_token` | 通过 |
| `/auth/me` | 返回当前用户、角色、权限 | 返回测试管理员及 17 项权限 | 通过 |
| Cookie 安全属性 | Access Token 不可被脚本读取，CSRF 单独提交 | 认证测试通过；Cookie 名称和安全用途符合设计 | 通过 |
| 写操作缺少 CSRF | 拒绝请求 | `POST /v1/settings/stores` 返回 HTTP 403 | 通过 |
| 密码/Token 泄露 | 不应出现在测试输出和业务响应 | 本次输出和报告未记录密码、Token、密钥或完整消息 | 通过 |

### 5.2 Webhook 与平台接入

| 用例 | 预期 | 实际 | 状态 |
| --- | --- | --- | --- |
| Shopee Mock 合法签名首次投递 | 快速接收、`duplicate=false` | `accepted=true`、`duplicate=false` | 通过 |
| 同一事件重复投递 | 不重复落库，返回重复标记 | `accepted=true`、`duplicate=true`，数据库事件数为 1 | 通过 |
| 非法签名 | 拒绝且不进入业务处理 | HTTP 401 | 通过 |
| Worker 处理 | 事件最终成功并保留处理状态 | 数据库查询为 `succeeded`、`retry_count=0`、已设置 `processed_at` | 通过 |
| 统一事件类型 | 非法事件不能进入业务层 | Pydantic 判别联合测试通过 | 通过 |
| TikTok HMAC | 按原始 Body 验签 | 后端平台适配器测试通过 | 通过 |
| 请求体限制 | 大于 1 MiB 拒绝 | 代码和现有适配器测试覆盖；未在本次运行态发送超大载荷 | 未执行 |

### 5.3 会话与客服工作台 API

| 用例 | 预期 | 实际 | 状态 |
| --- | --- | --- | --- |
| 演示数据 | 可创建三平台契约级渠道 | `seed_phase2_demo.py` 幂等完成；数据库有 1 个店铺、3 个渠道 | 通过 |
| 会话列表 | 分页、筛选和稳定排序 | `GET /v1/workspace/sessions?filter=all&page=1&page_size=20` 返回成功，共 2 个测试会话 | 通过 |
| 消息详情 | 返回会话消息，不隐式修改未读 | 消息分页接口返回 `code=0` | 通过 |
| 人工发送 | 先处理后发送，真实记录 Mock 状态 | 带 `Idempotency-Key` 发送成功，返回 `status=sent` | 通过 |
| 发送失败 | 不伪装成功 | 单元测试覆盖失败结果和状态路径 | 通过 |
| 店铺隔离 | 非授权店铺按资源不存在处理 | 访问边界单元测试与 Repository 约束通过；未构造第二个受限用户做完整黑盒跨店铺回归 | 条件通过 |

## 6. 缺陷与环境限制

### ENV-001：前端 Compose 服务无法构建

- 级别：环境阻塞，非产品代码缺陷。
- 现象：`docker-compose up -d frontend` 在拉取 `node:20-alpine` 时无法连接 Docker Hub 授权服务。
- 影响：未能验证前端容器启动和容器内页面访问；本地 `npm run build` 已通过。
- 建议：在可访问 Docker Hub 的环境重新执行前端 Compose 启动和浏览器回归。

### ENV-002：浏览器页面级验证未完成

- 级别：环境阻塞，非产品代码缺陷。
- 现象：浏览器访问 `http://127.0.0.1:3000/login` 时本地开发服务未保持监听；随后前端 Compose 构建又受 ENV-001 阻塞。
- 影响：未取得登录页、工作台三栏布局、375/768/1024/1440 响应式、键盘导航和控制台零错误的浏览器证据。
- 建议：启动 frontend 服务后补充浏览器测试，不应以本报告替代该项。

### WARN-001：现有依赖警告

- FastAPI/Starlette TestClient 提示未来建议安装 `httpx2`。
- passlib/argon2 提示读取 `argon2.__version__` 的弃用警告。
- 当前不影响测试结果，但建议后续依赖升级时处理。

## 7. 交付验收判断

Phase 2 后端代码、数据库迁移、契约 Mock 接入、Webhook 幂等与 Worker、认证安全和工作台 API 已达到本次可验证范围的质量门禁。由于前端容器构建和浏览器页面实测受外部网络/本地服务环境限制，本报告结论为“有条件通过”，不建议标记为完整发布验收通过。

补齐 frontend Compose 启动、浏览器页面和响应式交互证据后，可进行 Phase 2 最终复核。

## 8. 交接给开发与架构 Agent

- 保持契约级 Mock 适配器标识，不对外宣称真实平台联调完成。
- 保留 Webhook 原始事件摘要、重复投递结果和 Worker 处理状态，以便测试工程师复核。
- 继续禁止浏览器 localStorage 保存 JWT；所有浏览器写操作保留 Origin/CSRF 校验。
- 补测浏览器 UI 后，如发现页面问题另行生成递增序号报告，不覆盖本报告。
