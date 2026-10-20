---
record_id: TR-MVP-WORKSPACE-SEARCH-TRANSLATION-DEPLOY-001-20261020-R02
record_type: test
revision: R02
status: PASS
task_id: MVP-WORKSPACE-SEARCH-TRANSLATION-DEPLOY-001
tested_sha: a48f7447dfb905dcea5b30028544c1b0c04e1014
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-SEARCH-TRANSLATION-DEPLOY-001-20261020-R01.md
requirement_ids: [MVP-WORKSPACE-SEARCH-TRANSLATION-DEPLOY-001]
acceptance_ids: [AC-03]
environment: Signed-in Codex in-app browser against staging; deployed backend/frontend from a48f7447; existing DeepSeek provider
created_at: 2026-10-20T10:42:02Z
updated_at: 2026-10-20T10:42:02Z
supersedes: TR-MVP-WORKSPACE-SEARCH-TRANSLATION-DEPLOY-001-20261020-R01
---

# 测试范围、环境与 TEST_LAYOUT

R01 已证明搜索修复、不可变镜像和 staging 手动部署通过，但明确没有执行真实 DeepSeek 翻译。本轮仅补充已登录工作台的真实草稿翻译现场烟测。沿用 R01 的源码、运行环境和其余门禁结果；没有代码或配置变更。原型参考 `workspace-prototype.html?variant=A` 的第 3 项统一搜索与第 5 项多语言人工回复。

# 命令和逐项结果

- 在已登录 staging 工作台的已授权 TikTok 会话中，输入**合成**中文草稿“你好，请问需要什么帮助？”，选择英语后点“预览译文”；页面返回“Hello, how may I help you?”，同时显示原始草稿。这证明一次真实 DeepSeek 草稿翻译调用成功返回，并非合成 API 拦截。
- 点击“审阅并发送”后，审阅弹窗的目标语言为英语、准确待发送内容与上述译文一致，且另有独立“确认并发送”动作。本轮仅点击“返回修改”，没有点击最终发送。
- 清空草稿后译文预览消失，发送按钮禁用；目标语言已恢复“不翻译 · 原文”。搜索保持先前买家单项命中 1 个会话的状态。
- 从权威 `origin/main=efa891dafbbfabfa0c00e9f5a19681ce48712e04` 对比已部署源码 `a48f7447dfb905dcea5b30028544c1b0c04e1014`，`src/` 无差异。已有 [R01](TR-MVP-WORKSPACE-SEARCH-TRANSLATION-DEPLOY-001-20261020-R01.md) 的数据库搜索、浏览器合成发送和部署验证仍适用。

# REQ/AC 或门禁与证据映射

AC-03：真实授权会话、真实 DeepSeek 英语译文、原文/译文同屏、准确内容人工审阅、最终发送独立确认和清空后预览失效均由本次浏览器页面状态直接观察。多语言下拉框列出英语、印尼语、西班牙语、葡萄牙语、法语和泰语；统一服务和合成浏览器测试覆盖目标语言契约与将预览译文作为发送正文的路径，详见源码任务 [R01 TR](TR-MVP-WORKSPACE-SEARCH-TRANSLATION-001-20261020-R01.md)。

# 缺陷、未执行项与残余风险

只对英语做了一次真实 Provider 烟测，未逐种评估译文质量。没有向 TikTok 买家发送本轮译文，也未扩大既有单店真实发送范围；发送链路的既有真实互发证据与合成译文发送契约是独立证据，不能表述为本轮真实译文外发。未部署 production；G8 No-Go 不变。本轮没有保存客户正文、会话标识或凭据。

# 结论和复测条件

**PASS，仅限 staging 的真实草稿翻译预览与人工审阅烟测。** R01 关于“未执行真实 DeepSeek 翻译”的陈述只描述 R01 当时状态；本轮已补足一次英语真实调用，但仍不能声称六语质量评估或真实译文外发通过。
