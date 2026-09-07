# AI Agent Phase 1 修复后独立复测报告

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase1 |
| 任务编号 | P2-01；关联 P2-02 |
| 模块编号 | M04 |
| 模块名称 | 模型适配与意图识别 |
| 被测主责 Agent | AIAgent开发工程师Agent |
| 被测协作 Agent | 架构师Agent、测试工程师Agent |
| 测试执行 Agent | 测试工程师 Agent |
| 关联实施记录 | `共享记忆文档/实施记录/Phase1-P2-01-AIAgent开发工程师Agent-DeepSeek真实评测稳定性修复-003.md` |
| 关联上一轮报告 | `测试工程师/Phase1-P2-01-AIAgent开发工程师Agent-M04-模型适配与意图识别-AI评测-004.md` |
| 测试类型 | AI评测、回归测试、安全测试、集成测试 |
| 执行日期 | 2026-08-20 |
| 测试结论 | 通过；建议验收 Phase 1 AI Agent 模型适配与意图识别交付 |

## 2. 测试范围与验收标准

本次针对 DEF-AI-003 修复进行独立复测，范围包括：

- DeepSeek 真实模型调用、结构化输出、截断/空输出恢复和评测不中止策略。
- 五类意图识别：物流、退换货、尺码、价格、通用问题。
- 未知、混合、上下文不足等边界样本的保守拒判。
- Provider 错误统计、Token、耗时和敏感信息保护。
- AI Agent 代码回归、依赖、Compose、健康检查和数据库当前迁移状态。

验收门槛：

- 五类意图准确率不低于 85%。
- 边界样本正确拒判率不低于 90%。
- 真实评测必须完整生成聚合报告。
- Provider 最终失败数必须为 0。
- 不得泄露 API Key、Prompt、客户原文和完整模型输出。

## 3. 测试环境

| 项目 | 实际环境 |
| --- | --- |
| 操作系统 | Windows PowerShell |
| Python | 3.11.15 项目基线 |
| 运行环境 | `CRM智能聊天系统/backend/.venv` |
| LLM 实时评测 | `LLM_LIVE_EVAL=true` |
| 主 Provider | DeepSeek |
| 主模型 | `deepseek-v4-flash` |
| 思考模式 | `DEEPSEEK_THINKING_ENABLED=false` |
| 数据集 | `backend/evals/intent-classifier-v1.0.0.jsonl`，130 条 |
| 凭证处理 | 仅验证密钥存在性，未输出或写入报告 |

## 4. 独立真实模型评测

执行命令：

```text
python -m scripts.evaluate_intents --dataset backend/evals/intent-classifier-v1.0.0.jsonl --output <临时聚合报告路径>
```

实际结果：

| 指标 | 实际结果 | 门槛 | 状态 |
| --- | ---: | ---: | --- |
| 五类意图准确率 | 86.00% | ≥85% | 通过 |
| 边界正确拒判率 | 93.33% | ≥90% | 通过 |
| Provider 最终失败数 | 0 | 0 | 通过 |
| 输入 Token | 71,735 | 记录即可 | 通过 |
| 输出 Token | 2,401 | 记录即可 | 通过 |
| 平均端到端耗时 | 1,153.6 ms | 记录即可 | 通过 |
| 评测报告生成 | 完整生成 | 必须完成 | 通过 |

各意图 F1：

| 意图 | Precision | Recall | F1 | Support |
| --- | ---: | ---: | ---: | ---: |
| logistics_query | 1.000 | 0.950 | 0.974 | 20 |
| return_policy | 1.000 | 0.950 | 0.974 | 20 |
| size_guide | 1.000 | 0.950 | 0.974 | 20 |
| price_inquiry | 0.938 | 0.750 | 0.833 | 20 |
| general | 0.875 | 0.700 | 0.778 | 20 |

评测期间出现 2 次 `deepseek_output_invalid`/`llm_call_failed` 日志，但均被应用层恢复；最终 `provider_failure_count=0`，未发生评测中止，未将失败样本误算为正确拒判。该行为符合修复实施记录中的重试和错误统计策略。

## 5. 回归测试结果

| 验证项 | 命令或方法 | 实际结果 | 状态 |
| --- | --- | --- | --- |
| Ruff | `ruff check app migrations scripts tests` | All checks passed | 通过 |
| 格式 | `ruff format --check app migrations scripts tests` | 130 files already formatted | 通过 |
| mypy | `mypy app scripts` | 100 个源文件无类型错误 | 通过 |
| Python 编译 | `python -m compileall -q app migrations scripts tests` | 通过 | 通过 |
| 自动化测试 | `pytest -q` | 46 passed，2 个第三方弃用警告 | 通过 |
| 锁文件 | `uv lock --check` | Resolved 66 packages | 通过 |
| 依赖审计 | `uv audit --locked` | 65 个包无已知漏洞或不良状态 | 通过 |
| Compose | `docker-compose config --quiet` | 退出码 0 | 通过 |
| 当前迁移版本 | 查询 `alembic_version` | `013_marketing` | 通过 |
| 服务健康检查 | `GET http://localhost:8000/v1/health` | HTTP 200，返回 `code=0` | 通过 |

## 6. DEF-AI-003 修复验证

上一轮缺陷：真实 DeepSeek 评测因空输出或 Token 截断中止，未生成完整质量指标。

本轮复现结果：

1. 真实 DeepSeek 调用成功。
2. 130 条样本全部处理完成。
3. 聚合报告完整生成。
4. Provider 最终失败数为 0。
5. 准确率和拒判率均达到门槛。

结论：DEF-AI-003 已通过独立复测，状态更新为“已修复并验证”。

## 7. 未执行项与环境限制

本轮未对当前开发数据库直接执行 `alembic downgrade`：当前数据库已处于 `013_marketing`，回滚到 008 可能删除后续阶段表及数据，安全保护拒绝了该破坏性操作。此前已有迁移链升级、回滚和重新升级证据；本轮仅验证当前版本、Compose 配置和健康检查，不将该项重复声明为本轮执行通过。

## 8. 安全检查

- API Key 未进入命令输出、测试报告或评测聚合报告。
- 评测聚合报告未保存客户原文、Prompt 或完整模型响应。
- 仅记录 Provider、模型、统计指标和合成 Case ID/标签。
- 真实模型评测通过显式 `LLM_LIVE_EVAL=true` 启用；默认自动化测试未访问公网。

## 9. 缺陷与风险

| 编号 | 问题或风险 | 优先级 | 状态 | 负责 Agent |
| --- | --- | --- | --- | --- |
| DEF-AI-003 | DeepSeek 真实评测曾因空输出/截断中止 | P0 | 已修复并通过独立复测 | AIAgent开发工程师Agent |
| R-AI-005 | 本次准确率为 86%，仅高于 85% 门槛 1 个百分点，模型随机性可能造成波动 | P1 | 保留风险 | AIAgent开发工程师Agent |
| R-DB-005 | 本轮未在现有开发数据库执行破坏性回滚 | P2 | 环境限制，已有历史证据 | 全栈开发工程师Agent |

## 10. 回归结论与验收建议

Phase 1 AI Agent 模型适配层与意图识别本轮独立复测通过。DEF-AI-003 已解决，真实评测完成且达到既定质量门禁，建议架构师将 P2-01/P2-02 标记为“测试通过，可验收”。

后续仍建议在扩大评测集和多轮模型稳定性测试中持续关注 `price_inquiry` 与 `general` 的召回率，以及准确率接近门槛带来的波动风险。

