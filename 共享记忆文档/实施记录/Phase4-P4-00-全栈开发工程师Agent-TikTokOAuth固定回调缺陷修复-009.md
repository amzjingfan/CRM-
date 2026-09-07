# TikTok OAuth 固定回调缺陷修复实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 REAL-FS-02 |
| 模块编号 | M00 |
| 主责 Agent | 全栈开发工程师Agent |
| 协作 Agent | 架构师Agent、测试工程师Agent |
| 实施状态 | 开发修复已完成；待第三次独立复测 |
| 开始日期 | 2026-08-26 |
| 完成日期 | 2026-08-26 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 任务依据：`全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` 的 REAL-FS-02。
- 测试依据：`测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-TikTokOAuth授权与凭证生命周期-综合测试-002.md`。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 第 11.7 节。
- 代码规范：项目及角色 `AGENTS.md`、`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 修复 `DEF-REAL-FS02-006`：真实环境错误 OAuth Redirect URI 未失败关闭。
- 让应用实际 callback 路由、生产固定地址、启动校验和 OAuth 业务入口共享同一契约。
- 在创建 Redis `state` 或交换 Token 前拒绝 HTTP、错误主机、错误路径、query 和 fragment。

### 3.2 实施范围

- TikTok OAuth 回调常量、Settings 启动校验和 OAuth Service 运行校验。
- FastAPI callback 路由与固定地址的一致性约束。
- 生产 Compose 必填配置、环境模板、部署文档、接口文档和回归测试。

### 3.3 非目标

- 不把 Redirect URI 作为 TikTok 卖家授权 URL 的未定义参数发送；平台实际跳转仍由 Partner Center 配置。
- 不实施 REAL-FS-03 的真实只读 Adapter、Webhook 或任何真实写操作。
- 不读取或注入真实 TikTok 凭证，不执行真实店铺授权。
- 不修改 AI Agent、Prompt、RAG、模型或公开回复边界。

## 4. 实施前确认

- [x] 已读取全部适用 `AGENTS.md`、共享记忆清单和代码编写手册。
- [x] 已读取 REAL-FS-02 计划、ADR、接口契约、002 号测试报告和上一轮实施记录。
- [x] 已复现 `unsafe_oauth_redirect_runtime_accepted=true`。
- [x] 已确认 002 号报告中的 `DEF-REAL-FS02-001～005` 已关闭，本次只处理新增 006。
- [x] 已确认当前迁移 head 保持 `019_tiktok_channel_unique`，本次无需数据库迁移。

## 5. 根因与方案

### 5.1 根因

`validate_oauth_runtime()` 原先只检查 `TIKTOK_OAUTH_REDIRECT_URI` 非空。HTTPS 校验位于真实 TikTok Adapter 前置条件中，而当前四个 `REAL_TIKTOK_*` 开关必须保持关闭，因此 OAuth 端点已经可用时不会触发该分支。FastAPI callback 路径另以字符串声明，配置与实际路由没有共同来源。

该问题不是应用直接开放重定向：TikTok 的实际回调由 Partner Center 管理。风险是应用无法发现目标环境的错误或恶意配置漂移，并可能让发布人员误以为声明值已经参与执行链路。

### 5.2 修复方案

- 在配置模块定义 callback 路由、公开路径和架构固定 Redirect URI 三个关联常量。
- FastAPI callback 装饰器直接使用共享路由常量。
- integration、staging、production 在 Settings 构造时必须使用固定 HTTPS 地址。
- OAuth start 和 callback 通过 `validate_oauth_runtime()` 再次校验 HTTPS、固定路径及真实环境完全匹配。
- 生产 Compose 将 Redirect URI 改为必填；部署文档明确仍需人工核对 Partner Center 实际配置。
- API 只返回稳定低敏错误，不回显错误 URI。

## 6. 实际变更

| 文件路径 | 变更说明 |
| --- | --- |
| `backend/app/shared/config/settings.py` | 新增固定回调契约及真实环境启动校验 |
| `backend/app/integrations/oauth_router.py` | callback 路由复用共享常量 |
| `backend/app/integrations/oauth_service.py` | start/callback 前执行低敏失败关闭 |
| `backend/tests/test_real_runtime_config.py` | 覆盖三类真实环境和五类错误 URI、固定地址及 Compose 必填 |
| `backend/tests/test_tiktok_oauth.py` | 覆盖运行校验、start 前失败和路由一致性 |
| `docker-compose.prod.yml`、`.env.example` | 固定回调改为生产必填并补充约束说明 |
| `README.md`、`deploy/production/README.md` | 同步当前测试状态和 Partner Center 外部门禁 |
| `共享记忆文档/智能客服平台 — 管理端接口文档.md` | 同步 OAuth 回调配置契约 |
| `全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` | 同步 002 号报告和 006 开发修复状态 |

接口路径、数据库结构和迁移版本均未变化。所有真实平台、模型、公开回复、营销和自动回复开关继续保持关闭。

## 7. 验证记录

| 验证项 | 实际结果 | 状态 |
| --- | --- | --- |
| 缺陷复现 | 修复前生产 Settings 与 OAuth 运行校验输出 `unsafe_oauth_redirect_runtime_accepted=true` | 已复现 |
| OAuth/配置专项 | 76 passed | 通过 |
| 后端默认回归 | 603 passed、10 skipped、2 个既有弃用警告 | 通过 |
| PostgreSQL 隔离全量 | 空库升级 001→019；613 passed、0 skipped、2 个既有弃用警告 | 通过 |
| Ruff 检查与格式 | 全部产品/测试目录通过 | 通过 |
| mypy | 155 个源文件无类型错误 | 通过 |
| 前端 | lint、typecheck、24 项测试、14 个静态页面生产构建通过 | 通过 |
| 生产 Compose | 无真实凭证哨兵配置合并成功，输出 8 个服务 | 通过 |
| 锁文件 | `uv lock --check --offline` 解析 125 个包 | 通过 |
| 依赖审计 | 124 个包无已知漏洞或不良状态 | 通过 |
| 真实 TikTok 店铺 | 未注入真实凭证，未执行 | 未执行 |

## 8. 实施结果与遗留风险

- `DEF-REAL-FS02-006` 的工程根因已修复，但缺陷状态仍以 002 号正式报告的 P2/Open 为准，必须由测试工程师第三次独立复测关闭。
- 测试工程师应至少复测 HTTP、错误主机、错误路径、query、fragment、固定正确地址、生产 Settings、OAuth start 失败关闭、现有专项和迁移回归。
- 真实店铺 OAuth、Scope、Get Authorized Shops、Token 刷新、过期识别和平台侧撤销仍未执行。
- 发布时必须在 TikTok Partner Center 人工核对 Redirect URL；应用只能校验本地声明，不能读取平台后台配置。
- REAL-FS-03 和所有真实写操作继续禁止放行。

## 9. 交接事项

- 交接给：测试工程师Agent、架构师Agent。
- 下一步：生成第三次独立综合测试报告，不覆盖 001/002 历史报告。
- 第三次复测通过后，才可申请使用用户真实店铺进行受控 OAuth 联调；真实联调仍不得自动开放只读、Webhook 或写操作开关。

## 10. 文档同步

- [x] 已同步接口配置契约。
- [x] 已同步部署门禁和 Partner Center 人工核对要求。
- [x] 已同步全栈实施计划状态。
- [x] 已新增实施记录并更新实施记录索引。
- [x] 未修改 002 号测试报告及测试报告索引的权威结论。
