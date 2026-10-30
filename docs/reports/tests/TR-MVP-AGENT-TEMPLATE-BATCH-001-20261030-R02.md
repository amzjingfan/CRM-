---
record_id: TR-MVP-AGENT-TEMPLATE-BATCH-001-20261030-R02
revision: R02
record_type: test
status: PASS
task_id: MVP-AGENT-TEMPLATE-BATCH-001
tested_sha: a8ef79964e9596a5f29d1974c0003d9131013221
implementation_record: docs/records/implementation/IR-MVP-AGENT-TEMPLATE-BATCH-001-20261030-R02.md
requirement_ids: [MVP-AGENT-TEMPLATE-BATCH-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05, AC-06, AC-07, AC-08, AC-09, AC-10]
environment: Windows; isolated PostgreSQL/pgvector; Next.js standalone production; Chrome
created_at: 2026-10-30T14:14:12.762481+00:00
updated_at: 2026-10-30T14:14:12.762481+00:00
supersedes: TR-MVP-AGENT-TEMPLATE-BATCH-001-20261030-R01
---

# 本次最终候选与命令结果

TEST_LAYOUT: centralized；输出在忽略的src/tests/.artifacts/agent-template-batch-20261030/candidate-a8ef7996-*。只使用本任务既有full_test/migration_test隔离库，无staging数据库。后端临时业务服务未重启；新前端用正常工具自动启动，验证完成后已核对拥有者并停止，3146/18496/18497无监听。

| 检查 | 本次实际命令和结果 |
|---|---|
| 完整后端/PG | src/backend下python -m pytest -c pyproject.toml；2970通过/5条件跳过/2旧warning，289.63s；3为Windows条件，2为另跑的迁移opt-in |
| 专库迁移 | test_agent_template_models.py -k 'roundtrip or populated_template'，显式迁移专库及AGENT_TEMPLATE_MIGRATION_ROUNDTRIP=1；2通过/2未选，6.79s |
| 静态/锁 | Ruff通过，566文件格式通过，mypy302源文件通过，uv lock --check通过 |
| 确定性评测 | scripts.evaluate_dynamic_agents的16样本与scripts.evaluate_phase4的237样本passed=true；非真实模型质量 |
| 前端 | npm run test 74通过；lint 0错误/8旧warning；typecheck、production build exit0 |
| 生产浏览器 | UI_BASE_URL=loopback3146及UI_CACHE_EXPECT_PRODUCTION=1，npm run test:ui；209通过/0失败/0跳过，67.16s |
| 构建绑定 | build wTldBkwGAxrziapfB45QR；HTML200，13个引用JS/CSS逐项哈希与本地构建相同 |

首次契约测试误带构建用NEXT_PUBLIC_API_BASE_URL=/v1，出现固定默认URL断言失败；在契约进程清除构建专用环境后74通过，仅生产构建恢复该环境。保留失败日志，不修改产品或断言。

# 复用证据与AC-01～10

最终Agent实现、迁移、Agent前端业务路径与831逐树相同。真实两店V1/V2/V3、关页6ms后仍running继而独立完成、重开attempt1、本店覆盖11/1/0、不可变历史及55自有行清理的证据和完整AC入口见[TR R01](TR-MVP-AGENT-TEMPLATE-BATCH-001-20261030-R01.md)，明确复用且未重跑V4。新完整2970及209仍覆盖全部AC的组件/PG/浏览器用例，并保留共享管理员接待修复的新断言。

四个依赖清单与同轮31165审计逐blob相同，复用其官方npm450依赖/漏洞0及pip-audit无已知漏洞结果，原审计限制仍有效；未宣称新环境全面审计。

# 未运行与风险

本轮不运行真实模型、TikTok、真实外发、staging/production、48小时稳定性、生产备份或合成备份恢复。合成fixture已清理，不重建。GitHub精确head结果在PR逐项核验，零步骤失败只能标CI未运行，按已持续批准本地替代；部署仍需独立批准。
