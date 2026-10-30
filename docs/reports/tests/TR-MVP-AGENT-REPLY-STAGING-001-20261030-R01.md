---
revision: R01
task_id: MVP-AGENT-REPLY-STAGING-001
created_at: '2026-10-30T01:38:11.618174+00:00'
updated_at: '2026-10-30T01:38:11.618174+00:00'
supersedes: null
record_id: TR-MVP-AGENT-REPLY-STAGING-001-20261030-R01
record_type: test
status: PASS
tested_sha: fe4cf4b8a7977d43cebdc711e38b302b7afe7d06
implementation_record: docs/records/implementation/IR-MVP-AGENT-REPLY-STAGING-001-20261030-R01.md
requirement_ids:
- MVP-AGENT-REPLY-STAGING-001
acceptance_ids:
- AC-01
- AC-02
- AC-03
- AC-04
- AC-05
environment: isolated Windows PGvector + rootless staging; zero real send
---

# 范围、环境与集中测试布局

TEST_LAYOUT=centralized；Windows/Python3.11、Next16.4.2/Chrome；合成PGvector隔离库56874，临时输出均src/tests/.artifacts。staging使用既有rootless crmdeploy，不触碰系统Docker/production。真实数据只读，使用已获授权的既有买家与配置模型；不创建买家/订单，不发平台消息。外部API实际执行允许既有授权缓存，不把mocked=false解释为每次都重新访问平台。

# 命令及实际结果

- 冻结release d111：`python -m pytest -c pyproject.toml -q`（DATABASE_URL/TEST_DATABASE_URL指向隔离库，绝对cache_dir）2712通过、3平台skip；前端npm lint/typecheck/test/build通过，55契约、158生产浏览器通过，最终测试替身改completed后相关14项再次通过。lint0error/8既有warning；Ruff437文件、mypy277、锁文件、动态16/安全237通过。
- 集成subject fe4cf4b8：同命令本地044库2731通过、3平台skip、2既有弃用warning；Ruff450文件/mypy284通过；前端合并后lint/typecheck/55契约/build及生产浏览器161/161通过。前端树自c1b05c68未变，后续仅测试时钟变更。
- 回归先红后绿：两个不同分段被拒后分别重答整题，原代码返回两份相同完整答案；修复后整组重建为一条。移除UI的两项断言在旧生产构建均失败，修改后通过；保留确认框不发送、冻结编辑、失败卡片重试、未知禁止重发等行为测试。
- 合并后首次全量2730通过/3skip/1失败：既有20ms测试偶发先把工具判超时，未覆盖目标阶段。改用仅loop模块的逻辑时钟，在工具成功后推进至截止时间，保留工具成功事件与10/5用量断言，8相关测试通过，再全量2731通过。未改生产阈值、未降验收门槛。
- 前后端源码导出/OCI blob SHA256、linux/amd64、revision、RepoDigest均核验；每次切换前私有PG/MinIO/env/运行元数据备份，pg_restore目录及gzip可读性通过，未做实际整库恢复演练。ValidateOnly/Deploy健康门禁通过，最终043_logistics_updates、12服务健康/运行，自动回复/营销/高风险/物流通知双开关均false。

# 本轮真实工具、RAG与浏览器

初始12个服务级单问/组合/负例中，11个产生回答，一次中文范围外问题invalid_route_arguments无正文；物流领域缺政策负例补测正确说明无真实赔付依据。EN/ZH订单列表、订单详情、最新物流、文档检索单问与物流+知识组合均成功；所有真实工具mocked=false。文件v2已审批/ready、1个1024维BGE-M3块，记录中的文档引用均核对到绑定v2。无FAQ回退。

Codex浏览器真实操作中，最初scope外合成保养问题不匹配物流Agent；改为物流核查指南并保留失败。旧分段版本出现重复答案，修复5940d4c5后中英文正式工作台成功，中文可分两段；最终d111前端再次分别生成中文及英文完整短答复，卡片排文字之后，预演按钮/通知预演区消失。正式整组确认框显示准确文字→卡片顺序，随后返回修改，未点击确认发送。真实未复核草稿先于最终结果在UI可见；服务级首稿4.3～10.6秒、最终6.1～16.8秒，仅为本轮样本，不是稳定性SLA。

保留旧输出全轨迹、路由invalid_agent_id/invalid_route_arguments、evidence_review_invalid和一次实际query_logistics失败记录；人工重试后获得上述通过结果，不声称一次成功率100%。工具计数和最终trace摘要见低敏机器证据。合成指南只验证知识命中，不代表真实店铺政策。

# 零发送、清理与残余风险

最终原26条消息哈希未变、外发仍26。恢复性清理16条精确合成入站消息及专属测试记忆，文件软删/解绑v13，分类、模型、工具、其他六段提示词保留。刷新浏览器后输入框0/2000，测试稿不残留。自动通知真实外发及买家端分段交付未执行；没有声称TikTok支持原生逐token追加。本轮仅测试合成Markdown文件，不等于全格式解析/OCR复验。旧R10确有中英工具+文件RAG现场通过，独立于本轮证据。

GitHub CI按最终证据HEAD现场核对：只在全部失败作业runner0/steps0、没有执行失败时使用持续批准的本地替代；CI记录为未运行，具体run/job与合并见PR647及机器证据。production保持No-Go。
