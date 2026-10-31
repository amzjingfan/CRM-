---
record_id: TR-MVP-AGENT-DEBUG-STREAM-XBM-001-20261031-R02
revision: R02
record_type: test
status: PASS
tested_sha: ecc94a7b2e7293553c307fa3f6393755962196e8
implementation_record: docs/records/implementation/IR-MVP-AGENT-DEBUG-STREAM-XBM-001-20261031-R02.md
requirement_ids: [MVP-AGENT-DEBUG-STREAM-XBM-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05, AC-06, AC-07]
environment: staging rootless; merged main OCI linux/amd64; actual DeepSeek and local BGE-M3/pgvector; authenticated Codex browser and authorized temporary API identity
task_id: MVP-AGENT-DEBUG-STREAM-XBM-001
created_at: 2026-10-31T03:36:15.944047+00:00
updated_at: 2026-10-31T03:36:15.944047+00:00
supersedes: docs/reports/tests/TR-MVP-AGENT-DEBUG-STREAM-XBM-001-20261031-R01.md
---

本轮交付说明及证据 subject 为 `ecc94a7b2e7293553c307fa3f6393755962196e8`；实际运行/测试镜像 revision 为 `8bf9873c4ebaa1eeda882acad24acfbb1ff7a0b8`，本任务后端、Agent页面/API及部署协议源码一致。后续主线的工作台物流卡片改动未在本轮镜像中部署，本TR不把其记为现场验收。文档检查针对前者，现场调用针对后者，不声称重新部署文档提交。

# 本地与发布身份

本地候选63b69216完整结果见R01：3018通过/5条件跳过、生产浏览器214/214、78契约、静态/类型/构建及16/237评测。运行镜像来自已合并主线8bf9873c，src输入逐项无差异，不把历史失败当最终通过。CODE subject与发布revision分别保留。

备份校验、旧/新ValidateOnly、Deploy、047、12运行服务、固定出口均通过；三健康及/login、/marketing、/knowledge、/settings/stores、/agents无query的8路径200，页面no-store与指纹JS immutable通过。完整镜像与SHA在[低敏机器证据](../../../release/evidence/staging/crm-staging-agent-debug-stream-xbm-20261031.json)。临时输出根为src/tests/.artifacts/agent-debug-stream-xbm-20261031/，不提交买家正文或截图。

# 现场行为与AC映射

| 验收 | 本轮真实结果 |
|---|---|
| AC-01/02 中文工具+RAG | trace51e257a8；订单列表、详情、物流和知识同轮成功；中文正文及指南引用；提交后输入为空。下一草稿保留由生产浏览器行为测试覆盖 |
| AC-05 英文工具+RAG | trace0ba60e43；同四工具、英文正文、指南引用、review_ready；由已登录Codex浏览器观察 |
| AC-04/05 店铺路由 | tracee9639b68；从本店启用目录选择XBM订单物流Agent；三工具+引用回答。模型复用列表事实时无需冗余调用query_order |
| AC-02 公网原生SSE | trace92e2ac22；accepted→126条draft→result→done；首草稿13877ms、末草稿14918ms、终态21574ms，5个不同交付批次；文本长度增长，均unverified=true/sendable=false，无人工切字 |
| AC-03 真实中途断连 | trace25ca8cdc；首草稿后关闭公网响应，运行持久化failed/DYNAMIC_RUN_CANCELLED；工具诊断保留。真实ASGI重复取消、Redis租约释放、切店迟到隔离另由R01测试锁定 |
| AC-04 模板等价 | 模板v1与XBM v3的模型、七段提示词、工具、类型、用途逐字段等同US v13，模板关联保留；US草稿r29及运行v13不变 |
| AC-07 清理与保留 | 自有指南软删除，有效文件0、发布绑定0；模板和XBM Agent启用且保留，XBM发布v3。31条工具审计全部mocked=false；本任务Agent运行关联消息0 |
| AC-05/07 清理后回归 | traceb20f8f9e；v3调用订单列表+物流成功、中文简答，无知识工具/无引用；未回退FAQ |

# 已发现问题及过程失败

旧版中文跟随历史英文、仅编号查询no_hits已统一修复并用原问题复放。浏览器操作约21秒，无法稳定捕捉短暂草稿，因此经本轮明确授权，正式公网API使用同一管理员现存登录会话、10分钟凭证及Cookie/CSRF，凭证不落盘；进程退出且当前时间超过有效期。浏览器继续用于中英文和配置/清理核对。

首个SSE探针将query_order误写成每次必调，虽实际有列表/物流/知识和review_ready，断言失败；依据用户“模型自主选择工具”的既定要求，修正探针为语义所需能力，未修改产品或质量阈值。其运行d64039c6保留为探针失败过程；最终公网及取消探针独立通过。首个探针曾因登录会话无created_at属性在签发前失败，改用真实expires_at排序；不新增登录或权限。

# 未执行与结论

AC-01至07满足本轮范围。未执行真实买家消息发送、production、POSIX等待用例、显式破坏性模板迁移往返和备份恢复演练；不把这些项记为通过。并非所有UI极短状态都被现场截图捕获，实际分片以公网协议证据和本地浏览器行为测试共同确认。知识全文和原版本为可恢复性保留，已退出有效检索。测试后仅剩持久模板与Agent及审计，不留合成文件有效绑定。
