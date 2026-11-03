---
record_id: TR-MVP-AGENT-AUTOMATION-WINDOW-001-20261103-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-AGENT-AUTOMATION-WINDOW-001
base_sha: 7fe0788ff9c97ec0e5ed6ffc80f2946c4f89cfed
tested_sha: fc5d0c70e3d508b9ba78949a5d609f28ee234559
requirement_ids: [USER-AUTOMATION-SEND-FIX]
acceptance_ids: [AC-01, AC-02, AC-03]
created_at: 2026-11-03T03:06:06.853923+00:00
updated_at: 2026-11-03T03:06:06.853923+00:00
supersedes: null
implementation_record: docs/records/implementation/IR-MVP-AGENT-AUTOMATION-WINDOW-001-20261103-R01.md
review_record: docs/reports/reviews/RR-MVP-AGENT-AUTOMATION-WINDOW-001-20261103-R01.md
environment: Windows isolated PostgreSQL/pgvector050 and approved staging two stores
---

# 本次真实验证

针对固定subject执行，不引用旧结果代替本次验证。依赖沿用可信本地环境；隔离postgres-test迁移到050，平台写入使用合成捕获，未连接真实发送接口。

| 验证 | 命令/范围 | 结果 |
|---|---|---|
| 缺陷RED | pytest指定详情缺字段及窗口授权参数例 | 5 failed，正例因缺省false被拒绝 |
| 最终全后端 | uv run pytest -c pyproject.toml -q --tb=short，DATABASE_URL/TEST_DATABASE_URL/AGENT_TEMPLATE_RUNTIME_TEST_DATABASE_URL指向本机隔离库 | 3678 passed /5 skipped /2依赖弃用warnings，416.24秒 |
| 格式/静态 | ruff check . ../tests/backend ../tests/integration/postgres；ruff format --check 同范围 | 全部通过，615格式文件 |
| 类型/依赖锁 | mypy app scripts；uv lock --check | 321源文件通过；锁通过 |
| 官方HTTP契约+持久投递 | 详情无窗口、列表第二页true/false/缺字段，Agent/welcome/timeout/logistics_discovery共12组合；捕获末端适配器和账本 | 显式true才投递/发现，关闭/未知零投递；welcome/timeout SYSTEM、Agent ROBOT |
| 安全回归 | 身份不符、目标未找到、重复目标/游标、错误类型、整体超时及原撤权/幂等/有序性 | 全量包含并通过 |
| 实际GitHubCI | run41566451806，后端14步骤/前端11步骤实际完成 | 均success，无需本地替代例外 |
| 构建/部署 | 固定Git archive上下文构建；私有GHCR推送+直接镜像传输；ValidateOnly/Deploy customer profile | 不可变后端ac640ba7…2efc，四进程及egress一致；050、三健康200；前端/检索保持 |
| 正式认证现场只读 | 当前管理员有效登录派生内存JWT，正式API回读四项策略；真实TikTok详情/列表及订单读取 | 两店grant/identity/window全true；XBM样本1订单、US样本0；无外发 |
| 清理 | fixture自有行删除、隔离tmpfs容器停止；staging只读0测试行 | 自有测试店铺/策略均0，未删除真实数据 |

# 范围与限制

PASS仅覆盖本缺陷与批准的零试发验收；当前历史取消记录仍保留，尚无新自然业务的成功发送回执，不能声称买家已收到。物流首次建基线，按60分钟轮询，未强制事件或历史补发。五项条件跳过按现有套件保持，未删除测试/降低阈值；不将跳过说成通过。UI/Prompt/真实模型/RAG输出没有改变，本次未重新跑完整浏览器或付费模型矩阵；现有CI前端仍实际验证。一次探索性/health为404，正确/healthz、/v1/health、/v1/health/ready均200。私有备份复制初次被权限阻止后改用root Docker cp，未切换前完成备份；没有放宽权限。

[低敏原件与日志摘要](../../../release/evidence/staging/crm-staging-automation-window-20261103.json)包含source/merge SHA、镜像、配置、只读结果、清理与每份原始日志SHA256。秘密、订单标识和客户正文未提交。
