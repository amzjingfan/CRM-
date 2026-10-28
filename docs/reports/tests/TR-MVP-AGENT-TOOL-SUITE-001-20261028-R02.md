---
record_id: TR-MVP-AGENT-TOOL-SUITE-001-20261028-R02
record_type: test
revision: R02
status: PASS
task_id: MVP-AGENT-TOOL-SUITE-001
tested_sha: 84702ae0e59edc54fd6ba1ea8755c1cf79c1f4be
implementation_record: docs/records/implementation/IR-MVP-AGENT-TOOL-SUITE-001-20261028-R02.md
requirement_ids: [MVP-AGENT-TOOL-SUITE-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: Windows, Python3.11.15, Node24.19.0, Next16.4.2, isolated PostgreSQL-pgvector
created_at: 2026-10-28T19:34:13+08:00
updated_at: 2026-10-28T19:41:40+08:00
supersedes: docs/reports/tests/TR-MVP-AGENT-TOOL-SUITE-001-20261028-R01.md
---

# 最终集成候选验证

TEST_LAYOUT=centralized。本次最终集成候选完整后端2375 passed / 3 POSIX平台条件跳过、2既有warning，228.12秒；生产浏览器121 passed、0失败。前端与迁移未受上游Nginx变动影响：最终前端树b096d22f111b5d825a97684bcaba3d4f912f82c6、前端测试树db460113d89258aa4e1523eb21604e9850ee9531、迁移树becb98244bac2d854034fdae8983306b13c48729与4ef/6f一致；本次已通过的生产构建、lint/typecheck/48契约和040往返结果沿用R01。最终候选已重跑生产浏览器121/121、Ruff465/类型252、16动态协议/237安全评测和锁文件校验。

# 需求映射、闭环与限制

AC-01～05映射、失败记录、TDD与两轴闭环细节见R01 TR。R01确实测试6f；本记录复测合并上游后的候选，不改写历史结果。真实模型语义准确率、官方店铺字段、联合调用、Linux平台跳过项及现场性能未验；无平台发送、部署、密钥读取或production放行。

集成时先前bc4全量2374通过/3跳过、1旧入口断言失败。正式配置已在上游改为命名upstream；本次只将测试改为核验唯一命名upstream、唯一127.0.0.1:18080后端和全部proxy_pass目标，原TLS/私网/头部负向检查保留。最终84702完整复测全绿，没有回退上游连接复用或放宽安全检查。锁定依赖审计无已知漏洞，最终diff有限强密钥模式0命中。
