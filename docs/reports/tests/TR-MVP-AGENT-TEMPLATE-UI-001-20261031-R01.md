---
record_id: TR-MVP-AGENT-TEMPLATE-UI-001-20261031-R01
record_type: test
status: PASS
tested_sha: 78e7069c9a0386d143c474ad9a6cd9a5fb903094
implementation_record: docs/records/implementation/IR-MVP-AGENT-TEMPLATE-UI-001-20261031-R01.md
environment: Windows / Python3.11 / isolated PostgreSQL+pgvector / Linux production
  Next / synthetic-only DeepSeek
revision: R01
task_id: MVP-AGENT-TEMPLATE-UI-001
requirement_ids:
- MVP-AGENT-TEMPLATE-UI-001
acceptance_ids:
- AC-01
- AC-02
- AC-03
- AC-04
- AC-05
- AC-06
- AC-07
- AC-08
created_at: '2026-10-31T07:11:23.998783+00:00'
updated_at: '2026-10-31T07:11:23.998783+00:00'
supersedes: null
---

# 范围、命令与结果

TEST_LAYOUT: centralized。候选 `78e7069c9a0386d143c474ad9a6cd9a5fb903094`；后端、后端测试及模型合成验收代码与已核验a8189c3c完全一致，后续仅前端下拉和交付说明变化，故重跑受影响前端。源文件冻结清单与Git diff核对，未把历史任务结果当成本次验证。

| 本次验证 | 结果 |
|---|---|
| run-postgres-integration-tests.ps1 -TestPort56876 -ProjectName crm-agent-template-ui-20261031 | 3145通过、5条件跳过，312.64秒；真实完整迁移至048，临时库清理 |
| 048升级→047降级→048升级，独立56877 tmpfs库 | 字段数1→0→1，清理完成 |
| ruff check/format --check（backend cwd，app/scripts/migrations与后端/PG/本轮AI脚本） | 通过，577文件格式一致 |
| mypy app scripts | 305源文件通过 |
| 前端 lint / typecheck / test | 0错误、11既有警告；类型通过；78契约通过 |
| 官方Dockerfile生产Next构建 | 成功；最终镜像仅用于本地230项UI回归，未发布 |
| UI_BASE_URL=127.0.0.1:3151 UI_CACHE_EXPECT_PRODUCTION=1 node --test ../tests/frontend/browser/*.test.mjs | 230/230，0失败/跳过；1440及390布局、聚焦后的内层宽度已检查 |
| evaluate_dynamic_agents / evaluate_phase4 冻结数据 | 16/16协议、237/237安全；unsafe_escape_count=0，非真实模型质量证据 |
| agent_reply_preferences_live.py --enable-live | 最终9/9：四语气，自动/强制中英文，两坐席语言；每例真实模型选择合成物流工具并生成流式最终答复，独立语义评审通过 |
| 独立只读审查与复审、diff/源摘要 | 无未关闭发现 |

# AC与缺陷证据

AC-01来源面板/模板说明精简、AC-02紧凑分组与宽窄屏、AC-03搜索多选无显式分页/预览与知识保留、AC-04批次下拉及状态恢复，均由真实生产构建的合成浏览器行为覆盖。AC-05参数保存/冻结/草稿隔离、旧NULL兼容与跨店越权由PG和Worker/汇总/流式测试覆盖。AC-06九例模型表达（不含真实TikTok查询或RAG召回质量）、AC-07独立译文不进入发送计划、AC-08清理与零外发分别留有模型聚合及浏览器/资源核对。

红绿覆盖：偏好发布遗漏、汇总消费、翻译取消保留正文；工作台译文丢弃、preview返回丢恢复参数；Chrome Unicode-v下旧HTML pattern无效；选项文字点击null失焦提前卸载；手机HTML宽度正常但内部app-main被撑宽。均先复现再最小修复，最后包含在完整回归。未删除测试或降低阈值。

# 失败、未运行与限制

最初裸后端2失败为旧替身字段与迁移头断言，修正后完整PG通过。前端旧镜像的失败和中间225/229轮保留，不冒充最后230轮。真实模型预检曾1次评审标记与实际英文译文不一致、另1次依据复核协议无效而安全关闭；原件保留。最终格式整理后的同一语义用例9例全量通过，未放松复核Schema或阈值；小样本不保证随机模型永不失败。

5项跳过：3项需要POSIX bash进程等待，2项旧模板破坏性迁移专用库未开启；本轮新增048已单独完成往返。未访问真实买家或新做真实RAG/TikTok验收；模型合成运行是隔离候选解释器调用，API认证/发布/权限由PG测试独立验证。没有staging/production部署、真实发送或备份恢复演练。CI按PR最终head现场核对，零步骤不可用仅适用持续授权的本地替代，不能记作CI通过。

证据输出位于src/tests/.artifacts/agent-template-ui-20261031；正式低敏摘要见release/evidence/agent/agent-template-ui-local-20261031.json。测试对象只在临时库/上下文中，既有业务数据与知识均未变。
