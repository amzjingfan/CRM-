---
record_id: IR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R05
record_type: implementation
status: FINAL
revision: R05
task_id: MVP-AGENT-STAGING-DEPLOY-001
created_at: '2026-10-29T17:11:09+08:00'
updated_at: '2026-10-29T17:11:09+08:00'
base_sha: e3fcbd1a7df18ab5d5df7b64e45b65e02c93773e
final_sha: ff4d5e262bed31f07d9ec04a7c021c1a2b7fa9ba
requirement_ids:
- MVP-AGENT-STAGING-DEPLOY-001
acceptance_ids:
- AC-01
- AC-02
- AC-03
test_record: docs/reports/tests/TR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R05.md
review_record: docs/reports/reviews/RR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R05.md
supersedes: docs/records/implementation/IR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R04.md
---

# 实施目标与范围

统一修复 Agent 订单/详情/物流回答与工作台编辑体验。用户最终要求先完成本地开发测试，部署等待另行批准；本批不切换 staging、不发布 v4 配置、不推送镜像、不发送平台消息。

# 实际变更及原因

从授权工具的固定类型投影保留订单号、运单号及商品/SKU编号；不把运行候选引用保存为跨轮资源。原始买家问题与路由子问题分开，汇总遵从实际参与 Agent 的输出段；Markdown 解析为纯文本并保护业务编号字面值。

隐私先逐字过滤，再仅用已清理正文重组并独立核验；表达偏离由模型 output_rewrite_required 判断，不用正则检测语言。明确 unsupported 可在原总时限内仅从核实证据生成新稿，旧拒稿不进入新上下文；无效协议/引用/片段立即失败关闭，内外共享已复核正文防止重复投票。逐轮已知用量在取消/失败时保留，迟到模型结果不展示。

七段编译只做结构/长度/hash，发布时使用所选项目模型通过原生 @tool 语义复核，不按字段词或地址类别数判断。新增正则草案已移除，core/security.py 与基线相同；其他共享输入门禁不附带放宽。行锁刷新 ORM 缓存，旧 revision 返回409且不调用模型。

精确 UUID 的调试与普通建议 POST 外层容纳 Agent 预算。工作台修正滚动容器定位；新增完整草稿/译文大窗口，关闭保留草稿，Enter只换行；长稿不截断，超过原2000限制先编辑后送审发送。

# 数据、配置、接口与验证交接

无数据库迁移或发送权限扩大。新增直接 Markdown 解析依赖（原锁文件已有相同版本），三个模型协议版本见机器证据。新评测统计防止把超时/协议失败误当预期拒绝通过。最终应用树与 fa180 完全一致；完整回归及新统计8项、模型证据详见TR。

# 恢复与发布边界

待用户明确批准后，按集成主线重建精确发布镜像、协调单点切换、重新备份并执行受审门禁；发布后再用Codex浏览器验收和正常发布v4。已授权合成触发及仅由其派生的记忆保留至最终现场验收，不重建买家、不动真实消息。production G8仍No-Go。
