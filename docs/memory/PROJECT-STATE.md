# 项目状态与恢复入口

2026-10-28，治理STANDARD，TikTok人工辅助v0.1；仓库CP11-gh/CRM，目标origin/main。十二工具任务的唯一状态源为docs/tasks/TASKS.md；产品源码PR #589经用户人工审阅批准后已合并，合并提交6d29190195f356b5fe004692746ebe3b13c8e58c。仅状态文档收尾使用docs/agent-tool-suite-close-20261028，恢复时以权威主线和任务表为准；产品候选未部署。

CANDIDATE_SUBJECT_SHA=eab7e2c207308fde34be1ca50f25d32be1670cfa，EVIDENCE_HEAD_SHA=READ_AT_GATE。最新性能IR/RR为MVP-STAGING-LATENCY-001-20261029-R10、TR为R11；工具IR/TR/RR为MVP-AGENT-TOOL-SUITE-001-20261028-R03。门店授权聚合源码经[PR #599](https://github.com/CP11-gh/CRM/pull/599)合入主线 `0eda03197efe81c271ae3de180507e9d222d3f2b`，R08索引经PR #600成为CURRENT；R09发布证据经[PR #601](https://github.com/CP11-gh/CRM/pull/601)合入主线 `b0c3efcf05ab1633972c419675755cc96dd2226f`，R09三索引经PR #602从权威主线源记录核对为CURRENT；TR R10补测经[PR #603](https://github.com/CP11-gh/CRM/pull/603)合入主线 `0896fb757a1acce92ae8ca1b636402208a17efae`，三索引已从权威主线源记录核对为CURRENT。

浏览器并发认证刷新 eab7e2c2 的 51 契约、129 生产浏览器、类型、构建及双轴审查已通过；迟到订单只读 POST 复用已刷新 Cookie，写请求仍保留刷新和原幂等键。源码经 PR #605 合入 main f8c3be74；三索引从权威主线源记录重建为 CURRENT；staging 仍运行性能专用 release 18cea7f2，本次前端修复尚待独立部署，主线动态 Agent 不纳入。全站现场回显未完成。

十二业务工具、六类目录、三种操作标签和原四项人工确认提议已在本地验收。后端/前端/测试与完整受测84702ae0同树，完整后端2375 passed/3 POSIX跳过；生产浏览器121、前端契约48、Ruff/格式/mypy252源文件、040往返、16动态协议/237安全样本和依赖审计通过。最终01975ab2仅导入既有入口低敏日志字段，受影响入口38 passed/3平台跳过；未冒充在该提交重跑全量。两轴技术审查闭环。PR #589精确head的CI两作业均终止于runner=0/steps=0，CI未运行，按用户持续批准采用本地替代；用户另已明确批准本PR合并及仅任务/索引/恢复摘要文档收尾。

原生@tool/function calling选择发布的完整工具集；订单不默认最新，店铺/买家/会话在服务端核验；商品/优惠可仅按店铺授权。知识仅绑定获批文件，没有旧FAQ回退；内部备注和接管请求真实保存、幂等审计，不转交或发送。历史工具记忆区分scope并去除临时引用，只作需重查线索。040正式协作数据及迁移定义不可在回滚时随意删除。

部署状态：本轮动态Agent重写和工具扩展尚未部署，等待用户统一批准。性能任务MVP-STAGING-LATENCY-001仍由任务表和性能R09证据维护；PR #593已合入main（73ef0852），工作台并行刷新release 9d6ccc20已单独发布；基础接待并行请求PR #595已合入main（b84cbb6d），对应专用release 97ac71ef单独手动发布。数据看板渐进回显源码PR #597已合入main（f440fb64），该PR两项CI均runner空/0步骤失败、不计通过；独立release f9bfc109已仅更新前端并通过本地门禁、私有备份、ValidateOnly/Deploy、12容器与已登录默认店铺看板只读核对；跨店现场工具超时，公网单次仍秒级，不声称整体加速。PR #595两项CI均为runner空/0步骤失败，不计通过，以本地验证记录为准。后端和Agent未变，私有备份及ValidateOnly/Deploy通过，12容器和已登录三页面只读核对通过。分段探测显示业务机回环远快于入口隧道和公网，WAN重传及偶发504仍在；用户明确将网络异常期间公网p50/p95改为诊断记录，不作为应用改动绝对阈值，整体提速尚未证实。production G8 No-Go。真实模型语义、TikTok字段及联合链路、现场时延未在本轮验收。欢迎语/超时回复仍只有原基础接待配置，未新增触发或发送工具。

门店页R09：本地源与专用release的生产浏览器分别128/128、124/124，后端授权安全17/17，前端契约48/48；主线源全量后端2325 passed/55 skipped，Ruff/格式/mypy通过。PR #599两项GitHub CI均在runner启动前0步骤失败，不计通过，本地等价门禁已记录。首次临时GHCR登录组合命令被自动策略拒绝，分步隔离登录后发布成功并注销。性能专用release `18cea7f2` 已从原运行基线单独部署：前后端精确摘要、私有备份、ValidateOnly/Deploy、12容器、034迁移头和三个公网健康200通过；已登录门店页出现一条授权行，刷新浏览器工具60秒超时，故现场刷新时延未验收。Agent现有调试开关、单店人工发送及全部安全开关保持，主线新动态Agent代码未部署。低敏证据见release/evidence/staging/crm-staging-stores-progressive-20261029.json；WAN/隧道仍抖动，整体提速未证实。R10只读补测：已登录刷新后仍显示一条授权店铺且按钮可用；同时间窗口内层代理三条成功请求为22/18/16毫秒，但浏览器工具壁钟耗时不能证明用户可见回显速度，见release/evidence/staging/crm-staging-store-refresh-readonly-20261029.json。

Workspace hygiene: ATTENTION。根checkout未共享历史、未知需求/私有文件和其他活动工作树保留；前端工具生成的未跟踪AGENTS文件保持原状。临时日志、截图和收尾差异在src/tests/.artifacts，不提交或删除未知内容。官方公开文档UI不可用记UI_UNAVAILABLE，既有端点依据OAS和官方docv2。

下一动作：①仅将已合入的认证修复摘取到性能专用 staging release；随后补已登录门店刷新与全站冷/热、跨店、故障/限流真实回显对照，保留公网p50/p95诊断记录；②入口/隧道WAN异常待网络条件改善后复测；③Agent主线新版本仅在用户另行批准后部署。
