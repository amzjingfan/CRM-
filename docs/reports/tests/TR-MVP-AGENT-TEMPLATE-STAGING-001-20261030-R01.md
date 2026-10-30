---
record_id: TR-MVP-AGENT-TEMPLATE-STAGING-001-20261030-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-AGENT-TEMPLATE-STAGING-001
created_at: 2026-10-30T16:56:13.795981+00:00
updated_at: 2026-10-30T16:56:13.795981+00:00
supersedes: null
tested_sha: dcf5621e4c725faead3f6f67d01d6770bca5a88a
implementation_record: docs/records/implementation/IR-MVP-AGENT-TEMPLATE-STAGING-001-20261030-R01.md
requirement_ids: [MVP-AGENT-TEMPLATE-STAGING-001]
acceptance_ids: [AC-CANDIDATE, AC-NO-SEND]
environment: Windows; Next.js standalone production; Chrome; authorized staging
---

# 最终候选本次验证

TEST_LAYOUT: centralized。临时输出统一在忽略的 src/tests/.artifacts/agent-template-staging-20261030。最终代码 SHA 为 dcf5621e4c725faead3f6f67d01d6770bca5a88a，独立审查与下列重跑均绑定它。

| 命令/检查 | 结果 |
|---|---|
| npm run lint | 0 error，8 既有 warning |
| npm run typecheck | exit 0 |
| npm run test | 77 passed，0 failed/skip |
| npm run build | exit 0，standalone 本地启动通过 |
| UI_BASE_URL=loopback3146，UI_CACHE_EXPECT_PRODUCTION=1，npm run test:ui | 210 passed，0 failed/skip，63.92s |
| 新缺陷 red/green | 状态三条旧实现失败；跨店已映射文件旧实现1!=0；审查追加预览前断言旧生产构建1!=0；最终以上全部通过 |
| 独立审查 | 本地映射优先边界修复后0阻断项 |

此前开发模式208通过/1生产专用skip，只作为过程记录；最终生产210全通过替代它。后端、迁移、配置与 d67078db 未改，本次 UI 修复不重跑无关后端/PG/AI eval，不把历史2970描述为本次结果。

# 首轮真实现场矩阵

真实登录 Codex 浏览器创建一份模板和两店各一份合成文档，真实解析/清洗/分块/BGE-M3/pgvector 索引均 ready。模板 v1 创建两店草稿，v2 冲突先阻止确认，选择保留US本店描述/采用新格式后两店更新成功。只延迟自有停用测试Agent行的写锁110秒，观察处理中并离页；释放后任务完成，重新打开四个新建/更新项目各attempt=1，旧运行版本保留。未暂停全局处理器。

US 中文和英文各一次真实模型调用 search_customer_orders、query_logistics、search_knowledge，均有可见正文、相应语言、当前物流和本店文件引用。XBM 独立知识问题调用 search_knowledge，输出本店三项缺件资料且只引用XBM文件。数据库9项断言核实本店覆盖、格式同步、旧版本、两模板版本、文件隔离及零自动发送。所有测试Agent保持停用，不改变正式路由。

# 限制

本修订不代表最终统一修复已部署，也不代表测试数据清理完成；原文件仍保留以供复测。首次现场分属 fbacb372 和测试期间切入的 d67078db，不能冒称均在最终候选上运行。未执行平台发送、公开自动回复、production、48小时稳定性或备份恢复演练。最终发布和精确清理单独补录。
