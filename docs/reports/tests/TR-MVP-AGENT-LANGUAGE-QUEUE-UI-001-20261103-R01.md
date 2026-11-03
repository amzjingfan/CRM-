---
record_id: TR-MVP-AGENT-LANGUAGE-QUEUE-UI-001-20261103-R01
record_type: test
revision: R01
status: PASS

task_id: MVP-AGENT-LANGUAGE-QUEUE-UI-001
tested_sha: 70293cc68d803670345826cf2892d0ff209d0869
implementation_record: docs/records/implementation/IR-MVP-AGENT-LANGUAGE-QUEUE-UI-001-20261103-R01.md
requirement_ids: [AGENT_REPLY_LIVENESS_AND_ASSISTANT_VOICE]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05, AC-06, AC-07, AC-08]
environment: Windows PowerShell; Python 3.11; isolated PostgreSQL/pgvector; native Next standalone; staging manual immutable images
created_at: 2026-11-03T10:14:54.034992+00:00
updated_at: 2026-11-03T10:14:54.034992+00:00
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

TEST_LAYOUT: centralized。所有测试源码和临时输出位于src/tests；正式记录和低敏发布证据独立保留。最终后端源70293cc6，前端及模型提示词af2f4252与最终候选对应内容相同；前端树及浏览器测试自bc0之后无变化。

# 命令和逐项结果

- 修复前卡片/计时器隔离回归：纠正测试替身后在旧源码真实观测10项失败；错误替身的早期输出保留，不当作缺陷RED。
- UI/API发送超时、等待状态和未读回归：旧生产镜像及旧API分别失败；新生产前端对应行为通过。实际隔离PG自动投递捕获保持未读4。
- 物流事务新增4项：旧实现3失败/1通过；新物流整组39通过。成功提交与失败回滚均允许第二位买家阶段的独立Webhook更新第一笔订单；店铺/会话配置GET在业务行锁存在时可读。
- 最终70293cc6：从src/backend运行 `uv run --frozen pytest -q -rs`，隔离库同时设置DATABASE_URL、TEST_DATABASE_URL、AGENT_TEMPLATE_RUNTIME_TEST_DATABASE_URL，结果3711 passed、5 skipped、2依赖弃用警告，404.92秒。5跳过为3个Windows缺POSIX进程等待用例、2个未启用专门迁移演练用例；不作为通过。实际库已在线升级051。
- `uv run --frozen ruff check . ../tests/backend ../tests/integration/postgres`、format --check、mypy app scripts（321文件）、uv lock --check均通过，620文件格式满足。
- 前端npm lint无错误、12既有警告；typecheck、86项契约和生产构建通过。原生本地Next下运行 `node --test src/tests/frontend/browser/reply-review.test.mjs src/tests/frontend/browser/workspace-experience.test.mjs`：90 passed、0 failed。测试拦截合成API，不是真实平台UI。
- 前后端固定源码归档构建成功，实际CI #728及#729前后端作业都执行并SUCCESS；未使用零步骤例外或Actions部署。独立源码审查APPROVE。
- 五模板最终v3：`agent_template_voice_live.py --enable-live --templates ... --policy ... --output ...`，同一冻结数据和标准10/10。只使用合成事实、生成及独立模型评分，没有业务工具/RAG/平台发送；执行者逐条阅读回答，确认语言、无我/I、无自行联系客服、接管表述与提供事实一致。
- 保留失败：v1自动评分10/10，但执行者阅读发现售后英文推断未提供的取消/退款状态，判定该条不合格；v2评分9/10，订单英文暗示未执行的接管。之后统一策略1.1.1及候选模板明确未知字段与待人工语义；v3数据/标准未改。文件名中的历史human-adjudication不代表用户人工审阅。
- 首轮af2精确手动发布后，真实只读检查曾504；定位jobs持锁并重启恢复。最终702后端与af2前端手动发布，051、关键运行服务及4条公网路径200；只读PG blocked_transactions=0、idle_write_transactions=0。
- 五模板正式认证PATCH/publish并回读v2、7段，模型/工具/知识槽未改变；后续检查只读幂等复核，没有重复发布。实际共享policy编译正文与被测hash一致。
- 正式API回读：US auto；XBM off，最新任务cancelled/AUTOMATION_POLICY_CHANGED、auto-preview为null，无前序Agent阻塞。两店欢迎24小时咨询段、60分钟超时与物流external保持。当前受影响会话未读本来0，GET前后0仅证明本次读取不改值；非零保留由隔离回归证明。
- 自建3148/3149前端均停止；临时PG/tmpfs容器已删除。staging本轮没有创建合成买家/订单/消息/Agent/文件，没有测试外发，临时同管理员身份仅内存，进程结束；五模板v2为用户要求的正式配置，保留。

# REQ/AC 或门禁与证据映射

AC-01非文字与语言、AC-02计时器隔离、AC-03终态UI、AC-04助手表达、AC-05未读、AC-06人工发送边界、AC-07五模板中英、AC-08逐买家事务/无锁GET分别映射受影响单元、隔离PG、前端契约/浏览器、模型表达与线上只读证据。完整摘要及模板Prompt hash见[机器证据](../../../release/evidence/staging/crm-staging-agent-language-queue-20261103.json)。

# 缺陷、未执行项与残余风险

未新向真实买家试发或重放旧取消/unknown，不能证明本次真人端送达；没有重新运行真实工具/RAG全链路。现场浏览器标签绑定超时为UI_UNAVAILABLE，本地行为测试不能冒充线上视觉验收。两次源PR实际CI通过；纯文档收尾按文档门禁校验。模型可能仍存在随机表达偏差，继续经现有依据与安全复核。旧发送的历史具体锁持有者未追溯证明，新增jobs持锁根因由本次现场PG证据确认，不能倒推所有旧失败。

# 结论和复测条件

本次代码、模板更新、隔离回归和手动发布验收PASS；XBM关闭状态不视为修复失败，也未擅自恢复开启。新自然业务或用户授权试发可另证实际送达，production G8保持No-Go。
