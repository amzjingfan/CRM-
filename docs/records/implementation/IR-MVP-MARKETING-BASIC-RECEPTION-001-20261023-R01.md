---
record_id: IR-MVP-MARKETING-BASIC-RECEPTION-001-20261023-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-MARKETING-BASIC-RECEPTION-001
base_sha: bc542e7b34d7eac3ac97db0bb97b43ef74772cdb
final_sha: 439c50c926240e34e85d543629dab9cd03bdaea4
requirement_ids: [MVP-MARKETING-BASIC-RECEPTION-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
test_record: docs/reports/tests/TR-MVP-MARKETING-BASIC-RECEPTION-001-20261023-R01.md
review_record: docs/reports/reviews/RR-MVP-MARKETING-BASIC-RECEPTION-001-20261023-R01.md
created_at: 2026-10-23T02:47:35Z
updated_at: 2026-10-23T03:16:13Z
supersedes: null
---

# 实施目标与范围

按用户九张参考图，在“智能营销 → 基础接待”提供快捷回复、超时自动回复、进店欢迎语三个侧边栏入口及配置页面，并在工作台消息发送栏提供文字快捷回复。用户明确限定超时和欢迎语本次只保存页面与配置，不自动向 TikTok 买家发送。

# 实际变更及原因

- 新建独立 `reception` 后端模块和迁移 `028_basic_reception_config`，管理个人/团队快捷回复分组、文本回复和超时/欢迎策略配置。列表支持店铺、范围、分组、搜索及分页；回复保存快捷键、最多三个标签、站点及文本消息段；策略保存店铺范围、有效期、顺序、超时分钟和配置开关。
- 智能营销侧边栏保留原营销流程，并列出基础接待的三个子页面。快捷回复页面支持分组与回复增删改、搜索和预览；策略页面支持筛选、新增、编辑、复制、排序、删除和配置开关，醒目说明自动发送未启用。
- 工作台发送栏加入表情、收藏、快捷回复及图片/视频入口。图片/视频仅说明本期不可用；选择快捷回复可填入可编辑草稿，或进入现有准确内容的人工审阅弹窗，最终发送仍由坐席确认。输入 `/快捷键` 可选用当前回复。
- 独立审查发现未知快捷键回车、旧分页响应覆盖新搜索、策略“下移”、超过首个 API 分页的分组及站点标签等交互边界；已据此修正并增加浏览器回归。最终代码审查另发现编辑回复时重复快捷键可能触发数据库提前刷新而返回 500、`/快捷键` 未查团队范围；修正为修改前检查冲突返回 409，查找个人优先、团队其次，并补回归。rebase 后主线 TikTok OAuth job 的旧测试夹具未提供目标店铺角色，调整夹具使用真实店铺权限而未放宽产品校验。

# 关键决定与偏差

“已配置”及配置开关不代表平台正在自动发送。未接入营销 Worker、未创建自动触发任务、未新增媒体发送能力。站点为话术展示字段；现有会话缺少可靠站点字段，工作台不按站点筛选。多消息段在工作台合并为一个受现有 2000 字符上限约束的文本草稿。

# 数据、配置、接口和迁移影响

新增 `/v1/marketing/reception/{groups,replies,policies}` 的列表、新建、修改、删除接口；写入经 Cookie CSRF、`Idempotency-Key` 和低敏审计。个人内容按创建者隔离，团队与策略按目标店铺和既有权限隔离；跨店铺对象不暴露。策略响应始终声明 `delivery_enabled=false`。迁移 028 创建独立配置表及关联表，可在隔离 PostgreSQL 中升降级验证；不新增运行服务或真实平台凭证。

# 验证交接

源码候选、命令及本地结果见所链 TR，风险审查见 RR。最终 subject SHA 为 `439c50c926240e34e85d543629dab9cd03bdaea4`；该 SHA 的完整 PostgreSQL 2294 passed/3 skipped、生产浏览器 81/81、前端契约 48/48 和适用静态/构建门禁通过。任务仍为 `VERIFYING`，等待合并后 staging 的独立手动门禁。

# 限制、风险与回滚

本记录不代表 staging 或真实平台验收。若进行 staging 部署，应走已批准的直接手动路径，先核对不可变镜像、备份和迁移，再检查健康及真实登录态只读页面；production 仍保持 No-Go。回滚应用前应核对迁移 028 所存配置，不能在有需保留的新增数据时盲目降级。未向买家发送测试消息。
