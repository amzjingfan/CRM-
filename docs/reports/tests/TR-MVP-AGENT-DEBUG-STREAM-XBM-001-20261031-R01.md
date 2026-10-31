---
record_id: TR-MVP-AGENT-DEBUG-STREAM-XBM-001-20261031-R01
revision: R01
record_type: test
status: PASS
tested_sha: 63b69216ccaa82a48a6bf18786d4f8876f7fec73
implementation_record: docs/records/implementation/IR-MVP-AGENT-DEBUG-STREAM-XBM-001-20261031-R01.md
requirement_ids: [MVP-AGENT-DEBUG-STREAM-XBM-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-06]
environment: Windows; Python 3.11 frozen dependencies; Docker linux/amd64 production Next; isolated PostgreSQL/pgvector on IPv4 loopback
task_id: MVP-AGENT-DEBUG-STREAM-XBM-001
created_at: 2026-10-31T02:50:53.526328+00:00
updated_at: 2026-10-31T02:50:53.526328+00:00
supersedes: null
---

# 命令和结果

TEST_LAYOUT: centralized。最终subject 63b69216，依赖复用已冻结可信环境，不修改全局配置。临时输出均在 src/tests/.artifacts/agent-debug-stream-xbm-20261031/。

| 验证 | 本次结果 |
|---|---|
| run-postgres-integration-tests.ps1 -TestPort 56875 -ProjectName crm-agent-debug-stream-xbm-20261031 | 3018通过、5条件跳过，319.19秒；真实迁移到047并完整pytest，无排除文件 |
| ruff check app ../tests/backend ../tests/integration/postgres / ruff format --check 同范围 | 通过；487文件格式一致 |
| mypy app scripts / uv lock --check | 304源文件通过；锁检查通过 |
| npm run lint / typecheck / test | 0错误、11既有警告；类型通过；78契约通过 |
| 官方Dockerfile前后端 linux/amd64生产构建 | 均成功；前端镜像dce14679…的生产服务用于本轮UI验证 |
| UI_BASE_URL=http://127.0.0.1:3148 UI_CACHE_EXPECT_PRODUCTION=1 node --test ../tests/frontend/browser/*.test.mjs | 214通过、0跳过、82.33秒；覆盖6项调试流、模板、工作台、缓存及其他模块 |
| scripts.evaluate_dynamic_agents / scripts.evaluate_phase4 | 16/16协议边界、237/237安全；unsafe_escape_count=0；均非真实模型质量评测 |
| git diff --check；独立审查 | 通过；此前P1/P2全部关闭 |

完整PG日志 postgres-integrated-final.log；生产浏览器 ui-integrated-final.log；构建 frontend-integrated-build.log/backend-candidate-build.log；评测 dynamic-eval-integrated.json/safety-eval-integrated.json。

# 缺陷复现及闭合

原提交函数保留已发送输入的行为测试先红，真实ASGI2.0断连清理未完成先红；修复后通过。最初PG运行因旧专库硬编码拒绝setup，随后短生命周期因localhost连接回退停在queued；记录失败原件，严格隔离目标+明确IPv4后原断言通过，未延长时限。现场中文回答英文、编号脱敏后查询失义均有真实失败记录；新增语种传播与no_hits说明测试通过，尚待新运行版现场复验。

# 覆盖与未执行

AC-01/02/03/06本地候选通过：即时提交/保留下一输入、真实生成早片机制/终态替换、清空切店断连/取消审计释放，以及主线整合。3条跳过需要POSIX bash进程等待，2条迁移往返需独立破坏性测试开关，本次未运行；047常规升级已运行。新候选公网SSE、XBM中英文最终联合回答和清理属于后续现场TR，不用mock结果代替。旧版本英文现场 trace da473773-b7f5-4f11-8279-93c7dc5d6e0a 已有三业务工具+知识检索/指南引用，中文失败 adda3bfb-ad0f-4206-ac56-711c6ee909a0。未在仓库记录买家、订单或模型原文，未外发消息。

CI run41161400056两个作业124419525358/124419525621均终止failure、runner空、0steps，测试未运行；按持续批准本地替代，不能记CI通过。最终证据提交后须重新核对当前head的作业。
