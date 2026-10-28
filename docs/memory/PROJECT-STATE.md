# 项目状态与恢复入口

2026-10-28，STANDARD。当前任务 MVP-AGENT-TOOL-SUITE-001 进入 VERIFYING，唯一状态源见 docs/tasks/TASKS.md。BASE_SHA=9d6a9182ec7e9e29712e670654b757f8c767ef5d；分支 feature/agent-tool-suite-20261028，目标 origin/main；最终subject=01975ab2471adfe2a704116367c34d27415a3240。根 checkout 未共享历史与未知私有文件保留。

已接通十二项业务工具、六类统一目录、三种操作标签及原四项人工确认提议；原生 @tool/function calling 自动选择配置工具，后端目录驱动 UI，订单/商品/售后使用本轮不透明候选引用。商品/优惠按店铺授权，无需买家会话；其他业务对象及内部写入绑定当前会话。040新增内部协作记录、幂等和审计，不发送平台消息或转交会话；知识仅显式绑定获批文件，保留撤权检查。此前动态多Agent源码PR #582与状态PR #583已合并；编排继续采用 asyncio，未恢复旧 FAQ。

最终本地验收：subject `01975ab2471adfe2a704116367c34d27415a3240`，应用树与84702完整后端2375 passed/3平台条件跳过的受测树相同，当前候选入口增量38 passed/3平台跳过；生产浏览器121、前端契约48、Ruff/格式/mypy252源文件、040往返、16动态/237安全评测和依赖审计通过；两轴审查已闭环。IR/TR/RR为MVP-AGENT-TOOL-SUITE-001-20261028-R03，三索引CANDIDATE_VIEW。EVIDENCE_HEAD_SHA=READ_AT_GATE；任务仍VERIFYING，PR https://github.com/CP11-gh/CRM/pull/589 已创建；源码和证据已推送，部署未批准。用户本轮贴出的AGENTS指令要求人工审阅，现等待用户对本PR的人审决定；既有GitHub零步骤本地替代授权继续适用。合并复核后才能DONE。

主线另新增性能R04日志证据release/evidence/staging/crm-staging-server-timing-20261028.json，已保留；该改动仅入口低敏耗时日志，不是Agent部署。

本阶段未部署，用户要求完成本地验证后等统一批准。性能任务MVP-STAGING-LATENCY-001仍在VERIFYING；独立release e64ef52c仅将性能修复部署staging，动态Agent未部署。性能入口连接复用R03证据见release/evidence/staging/crm-staging-nginx-keepalive-20261028.json；入口回环改善但公网未证实改善，AC-01/AC-06仍待该任务复测。本阶段未访问真实模型、TikTok数据或密钥，真实站点联合链路与性能仍待获批后验收；production G8 No-Go。欢迎语/超时回复工具未纳入本阶段。

Workspace hygiene: ATTENTION。根未知需求/私有文件和其他活动工作树保留；本次 Next 开发服务生成了未跟踪的前端AGENTS文件，未提交或删除；临时日志/截图在 src/tests/.artifacts，未作为发布证据。公开官方文档UI读取失败记为 UI_UNAVAILABLE，端点参考来自本机官方OAS与可读取docv2搜索结果。

下一动作：①取得本轮AGENTS要求的PR人工审阅决定；②按精确head门禁合并并核对索引/关闭任务；③等待用户批准统一部署。
