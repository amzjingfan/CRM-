---
record_id: IR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R02
record_type: implementation
revision: R02
status: FINAL
task_id: MVP-WORKSPACE-TRACKING-TIMELINE-001
base_sha: 43f7a3c84b825effd127d0267a25187649a99bf1
final_sha: 39244eb15b6c11db9b7463656304de1a92153c9d
requirement_ids: [MVP-WORKSPACE-TRACKING-TIMELINE-001]
acceptance_ids: [AC-03, AC-04, AC-05]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R02.md
review_record: docs/reports/reviews/RR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R02.md
created_at: 2026-10-22T03:09:10Z
updated_at: 2026-10-22T03:09:10Z
supersedes: docs/records/implementation/IR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R01.md
---

# 实施目标与范围

根据用户的图 2，将逐节点翻译改为顶部一键翻译全部包裹节点；补上单号复制和“发送物流卡片”草稿入口。后者只填入现有编辑栏，坐席仍需审阅与确认，点击弹窗按钮不调用发送接口。

# 实际变更及原因

- 新增 `tracking-timeline-translation` POST：服务端重新核对订单与会话买家，从官方通用轨迹或跨境增强缓存读取全部节点，不接受客户端提交物流正文。全量长度与 DLP 检查后，复用已注册的 `customer-translation-v1.0.1`，最多三个并发翻译最多 40 条节点。任一节点失败时前端保留所有原文，不展示部分译文；审计只记录条数和模型用量。
- 弹窗顶部提供“翻译全部/重新翻译”和“查看原文/查看译文”，全部包裹节点在原位置替换；响应必须与当前节点描述、时间、单号逐项一致。包裹切换、增强轨迹替换或详情刷新后旧响应不能误用。
- 当前包裹单号可复制；“发送物流卡片”把当前包裹原文、物流单号、物流商与全部节点预填到现有草稿通道，超过 2000 字符时提示坐席自行选取，不截断事实或自动发送。
- 同步产品、API 和 AI 当前文档；无迁移、配置、新依赖或新的平台写入。

# 验证交接与限制

源码 subject 为 `39244eb15b6c11db9b7463656304de1a92153c9d`。本地回归、浏览器和生产构建结果见 R02 TR，安全审查见 R02 RR。真实 DeepSeek 一键翻译、staging 合入后运行摘要和用户登录态核对仍待执行；当前不声称 staging 已更新。超过 40 条节点的整批翻译会明确报错，原文与复制功能保留。production 仍为 No-Go。
