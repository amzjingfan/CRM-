---
record_id: TR-MVP-AGENT-TOOL-SUITE-001-20261028-R03
record_type: test
revision: R03
status: PASS
task_id: MVP-AGENT-TOOL-SUITE-001
tested_sha: 01975ab2471adfe2a704116367c34d27415a3240
implementation_record: docs/records/implementation/IR-MVP-AGENT-TOOL-SUITE-001-20261028-R03.md
requirement_ids: [MVP-AGENT-TOOL-SUITE-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: Windows, Python3.11.15, isolated PostgreSQL-pgvector, unchanged application tree
created_at: 2026-10-28T19:52:02+08:00
updated_at: 2026-10-28T19:52:02+08:00
supersedes: docs/reports/tests/TR-MVP-AGENT-TOOL-SUITE-001-20261028-R02.md
---

# 验证范围与真实来源

TEST_LAYOUT=centralized。本候选仅集成已入主线的入口日志字段和证据；未在01975ab2重跑完整2375项，不能冒充新全量结果。产品和测试树与84702ae0完全一致；最终产品全量结果为R02 TR记录的2375 passed/3 POSIX跳过/2既有warning，228.12秒；121生产浏览器、48契约、构建、类型、格式、16动态协议/237安全评测、040往返与依赖审计的本次证据按相同源码树复用。

本候选从src/backend新运行：PYTHONPATH=.;../tests/backend python -m pytest ../tests/backend/runtime_infrastructure/test_split_ingress_staging_assets.py -q --tb=short，38 passed / 3 POSIX条件跳过，1.21秒；覆盖TLS、只转发回环隧道、SSE、隐私日志、缓存和入口资产边界。该上游新增日志字段的现场验证由独立性能R04记录承载，不能转称本工具已部署。

# AC映射及限制

AC-01～04的工具/配置/内部写入/知识与权限功能同R02，当前应用/测试身份比较无差异；AC-05由本次完整应用证据、明确的源码树身份和本候选受影响入口回归共同满足。真实模型语义、TikTok站点字段、现场联合链路和性能仍未验，无外发或部署。原R01/R02所有限制继续适用。
