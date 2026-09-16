# 意图分类真实模型评测报告

- 结果：未通过
- 主模型：`deepseek-v4-flash`
- 备用模型：`deepseek-v4-pro`
- 五类准确率：94.00%（门槛 85%）
- 边界正确拒判率：80.00%（门槛 90%）
- 输入 Token：45426
- 输出 Token：2377
- 平均端到端耗时：1162.9 ms
- Provider 失败数：1
- Provider 错误分布：`{"LLM_OUTPUT_INVALID": 1}`

## 各意图指标

| 意图 | Precision | Recall | F1 | Support |
| :--- | ---: | ---: | ---: | ---: |
| logistics_query | 0.909 | 1.000 | 0.952 | 20 |
| return_policy | 1.000 | 1.000 | 1.000 | 20 |
| size_guide | 1.000 | 1.000 | 1.000 | 20 |
| price_inquiry | 1.000 | 0.800 | 0.889 | 20 |
| general | 0.783 | 0.900 | 0.837 | 20 |

## 混淆矩阵

```json
{
  "logistics_query": {
    "logistics_query": 20,
    "return_policy": 0,
    "size_guide": 0,
    "price_inquiry": 0,
    "general": 0,
    "abstain": 0,
    "error": 0
  },
  "return_policy": {
    "logistics_query": 0,
    "return_policy": 20,
    "size_guide": 0,
    "price_inquiry": 0,
    "general": 0,
    "abstain": 0,
    "error": 0
  },
  "size_guide": {
    "logistics_query": 0,
    "return_policy": 0,
    "size_guide": 20,
    "price_inquiry": 0,
    "general": 0,
    "abstain": 0,
    "error": 0
  },
  "price_inquiry": {
    "logistics_query": 0,
    "return_policy": 0,
    "size_guide": 0,
    "price_inquiry": 16,
    "general": 4,
    "abstain": 0,
    "error": 0
  },
  "general": {
    "logistics_query": 0,
    "return_policy": 0,
    "size_guide": 0,
    "price_inquiry": 0,
    "general": 18,
    "abstain": 2,
    "error": 0
  },
  "abstain": {
    "logistics_query": 2,
    "return_policy": 0,
    "size_guide": 0,
    "price_inquiry": 0,
    "general": 1,
    "abstain": 26,
    "error": 1
  },
  "error": {
    "logistics_query": 0,
    "return_policy": 0,
    "size_guide": 0,
    "price_inquiry": 0,
    "general": 0,
    "abstain": 0,
    "error": 0
  }
}
```

说明：报告只包含聚合指标，不包含客户原文、Prompt、模型原始输出或密钥。
