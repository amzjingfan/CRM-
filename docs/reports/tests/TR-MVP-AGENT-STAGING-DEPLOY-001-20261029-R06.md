---
record_id: TR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R06
record_type: test
revision: R06
status: PARTIAL
task_id: MVP-AGENT-STAGING-DEPLOY-001
tested_sha: 3bfd55ee91d654ad69c63b73907285c3a0a4c4d3
created_at: 2026-10-29T18:14:51+08:00
updated_at: 2026-10-29T18:14:51+08:00
supersedes: docs/reports/tests/TR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R05.md
implementation_record: docs/records/implementation/IR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R06.md
requirement_ids: [MVP-AGENT-STAGING-DEPLOY-001]
acceptance_ids: [AC-01, AC-02, AC-03]
---

# 测试范围、环境与TEST_LAYOUT

本地门禁PASS；任务总体PARTIAL，部署及公开浏览器联合验收待执行。Windows/Python3.12，独立Compose postgres-test/tmpfs、唯一项目/回环端口，Alembic041。项目内临时输出仅src/tests/.artifacts/agent-rag-staging-20261029，安全资产测试默认仓库外tmp。

# 命令和逐项结果

- 新test_dynamic_rag_evidence.py：实现前RED4failed/9passed，实现后13passed；真实run_specialist→工具JSON→引用/grounding，持久化SQL insert参数，不镜像实现。
- 包含worker、execution、native tools、绑定RAG、timeout、failureprogress的焦点55passed。
- 隔离PG迁移后从src/backend执行 `.venv/Scripts/python.exe -m pytest -q -rs -o cache_dir=<src/tests/.artifacts绝对路径>`：2535passed、3Windows条件skip、2依赖deprecationwarning，223.51秒；未降低断言/阈值。
- Ruff app/scripts/backendtests check通过，format412files；mypy app/scripts255sourcefiles；uv lock --check通过。
- 前端 npm run lint/typecheck/test/build：0errors、8既有warnings、52契约通过，生产构建完成。本轮UI仅知识说明文案，未重复旧105浏览器全套，实际发布后另做Codex浏览器验收；旧R05不能冒充本轮结果。
- 动态协议16/16、共享确定性安全237/237，通过但不代表真实模型路由准确率。
- git diff --check通过；未知src/frontend/AGENTS.md保持未跟踪。

# 缺陷、未执行项与残余风险

首次扩展全量误把basetemp设在仓库内：2381pass/99fail/58skip，触发发布/SSE安全资产契约及根tests布局，不记通过；99原失败保留。Agent独跑1340pass/1时序失败（deadline），文件立即复核9/9通过，最终完整PG该例通过；未改该代码或放宽时间断言。相对cache路径错误生成10文件，按独立批次可恢复隔离后改绝对cache+默认外部tmp重跑2535/3。

当前合成Markdown上传正常：3块、ready，已通过正常审批/绑定草稿，但未调用真实模型检索、未发布新配置；这些现场环节仍待部署完成。没有平台发送。

# REQ/AC映射和结论

AC-01源码/本地门禁完成，精确发布和备份待做；AC-02 RAG预算、审计与失败关闭回归完成，公开模型联合回答待验收；AC-03知识库说明准确，实际UI/工作台最终验收待做。当前任务不能DONE。
