---
record_id: TR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R07
record_type: test
revision: R07
status: PARTIAL
task_id: MVP-AGENT-STAGING-DEPLOY-001
tested_sha: 01f138657e3bdb03376e2ee49cfeb6d4e0224411
created_at: '2026-10-29T19:05:46+08:00'
updated_at: '2026-10-29T19:05:46+08:00'
supersedes: docs/reports/tests/TR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R06.md
implementation_record: docs/records/implementation/IR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R07.md
requirement_ids:
- MVP-AGENT-STAGING-DEPLOY-001
acceptance_ids:
- AC-01
- AC-02
- AC-03
---

# 测试范围与结论

本地PASS，任务仍PARTIAL（本subject尚未公开部署验收）。Windows、Python3.11、独立PG/pgvector/tmpfs、迁移041；测试临时输出src/tests/.artifacts/agent-rag-staging-20261029。

# 本次命令与结果

- test_specialist_question_boundary：RED6fail/1pass→GREEN7pass；有效改写、拒绝改写回退且无泄漏、原文拒绝零调用、无原文仍拒绝、相同文本单校验、其他业务/运行异常不吞。焦点62pass。
- backend cwd `.venv/Scripts/python.exe -m pytest -q -rs -o cache_dir=<绝对src/tests/.artifacts路径>`：2542pass/3Windows POSIX条件skip/2依赖warning，231.21秒；独立PG迁移head。
- Ruff check通过/format413，mypy app/scripts255，uv lock --check通过；前端lint0error/8既有warning、typecheck、52契约、生产build通过。
- 生产Next隔离本机端口，UI_CACHE_EXPECT_PRODUCTION=1、npm run test:ui：最终142pass/0skip，52.48秒；首轮及修改路径错误导致的过早重跑均141pass/1旧文案等待超时，原日志保留。仅更新两处已被新说明替代的断言，不删交互、不放宽阈值。
- 新subject的动态协议16和共享确定性安全237另运行（低敏JSON）；不代表真实模型准确率。

# 现场/候选证据与边界

839实际手动部署12容器/三公网200、041/人工模式；纯RAG browser 15.824秒、1次search_knowledge retrieved、2个v1块引用，正文含问题未提供的Indigo Lighthouse及三项材料，审计正确succeeded/result_status=retrieved。

联合原始失败2.409秒，子Agent零tokens/零工具。隔离只读诊断复现worker93的AppError VALIDATION_ERROR；候选补修在独立进程加载，不改运行服务/env。v4候选四工具成功但最终漏答名称，保留不当作完整成功。正常页面发布v5补充逐项回应后，候选四工具均成功（订单列表、详情、物流、RAG），1包裹8轨迹、3文件v1块引用、回答2690字符含唯一文档名称，send_performed=false。超过2000的完整稿应在工作台展开并先精简后送审，不能截断。

直接受权业务工具复核1包裹8轨迹成功；一次早期诊断调用物流两次失败，未取得精确上游原因，不能据此说平台无轨迹。诊断辅助脚本错误读取AgentDebugView.status，发生在产品调用完成后，不计产品通过证据。

# 未执行项和复测条件

本源码尚待精确镜像发布后的Codex浏览器联合问答、负例与工作台草稿/展开验收。仅成功后统一清理已知合成消息、其专属记忆和文件，保留真实数据、运行与审计。没有真实平台发送；production未放行。
