---
record_id: TR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R08
record_type: test
revision: R08
status: PARTIAL
task_id: MVP-AGENT-STAGING-DEPLOY-001
tested_sha: daf879b8bbf7ce293ea773690f8ef1ebc27bcc44
created_at: '2026-10-29T20:01:34+08:00'
updated_at: '2026-10-29T20:01:34+08:00'
supersedes: docs/reports/tests/TR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R07.md
implementation_record: docs/records/implementation/IR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R08.md
requirement_ids:
- MVP-AGENT-STAGING-DEPLOY-001
acceptance_ids:
- AC-01
- AC-02
- AC-03
- AC-04
---

# 测试范围与结论

本地及真实候选预检PASS；任务总体PARTIAL，本subject尚未公开部署和最终双语验收。Windows/Python3.11，独立PG/pgvector/tmpfs、迁移041；临时输出src/tests/.artifacts/agent-rag-staging-20261029。

# 本次命令与结果

- test_native_model_deadline和execution_chain：RED24failed/3passed→GREEN27passed；覆盖三SDK剩余预算、临期短预算、过期零创建、默认15秒/零重试、同deadline传递、SDK超时稳定分类及此前工具/已知11+4tokens保留。焦点86passed，含取消、总deadline、配置发布、RAG和路由回退。
- 完整隔离PG迁移后 backend cwd `.venv/Scripts/python.exe -m pytest -q -rs -o cache_dir=<绝对src/tests/.artifacts路径>`：2561passed/3Windows POSIX条件skip/2依赖warning，216.09秒。
- Ruff check及format414files、mypy app/scripts255、uv lock --check通过。动态协议16和共享确定性安全237在本source运行，不能代替真实模型语义指标。
- 前端产品/测试树与0fb完全相同，复用R07同树52契约、142生产浏览器、lint/typecheck/build；本次没有再声称新跑前端全套。新前后端发布镜像仍需精确集成源构建和核对。

# 真实候选四入口预检

以已授权买家、项目DeepSeek和同一已审批绑定文件，独立进程校验运行基线hash后只加载3个候选模块，不改运行服务文件/环境。正常页面发布配置v6；输入分别来自debug当前问题或实际合成Message正文，不把路由语言当原始语言。

| 入口 | 秒 | 字符 | 引用数 | 结果 |
|---|---:|---:|---:|---|
| 英文debug |22.664|3036|3|四工具、英文、唯一文档名称|
| 中文debug |18.794|1445|2|四工具、中文、唯一文档名称|
| 英文formal |24.897|2206|3|四工具、英文、唯一文档名称|
| 中文formal |35.926|1257|2|四工具、中文、唯一文档名称|

四类均review_ready、真实订单/运单号在正文、无Markdown、send_performed=false。3个不同引用chunk通过数据库join核对预期文件v1；正式SuggestionCitation公开DTO不含version字段，不把API中null统计称作返回了v1。中文formal第一次物流THIRD_PARTY_ERROR后模型再次查询成功，原事件保留。英文formal超过2000字符，最终UI必须验证完整保留且精简前不能送审发送。

# 失败、未执行与残余风险

0fb中文debug24.002秒失败和独立诊断确认APITimeoutError；工具四项成功不等于回答成功。0fb英文工作台26.030秒生成中文，亦不计双语通过。四类候选预检不能冒充已发布服务或浏览器验收。下一步在最终服务上正常Codex浏览器中英调试、中英工作台、无依据负例和完整编辑验收；全部成功后清理已知合成夹具并定稿。
