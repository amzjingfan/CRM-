# 意图分类真实模型评测报告

- 结果：通过
- 主模型：`deepseek-v4-flash`
- 备用模型：`deepseek-v4-pro`
- 五类准确率：85.00%（门槛 85%）
- 边界正确拒判率：96.67%（门槛 90%）
- 输入 Token：71720
- 输出 Token：2401
- 平均端到端耗时：1149.1 ms
- Provider 失败数：0
- Provider 错误分布：`{}`

## 各意图指标

| 意图 | Precision | Recall | F1 | Support |
| :--- | ---: | ---: | ---: | ---: |
| logistics_query | 1.000 | 0.950 | 0.974 | 20 |
| return_policy | 1.000 | 0.900 | 0.947 | 20 |
| size_guide | 1.000 | 0.900 | 0.947 | 20 |
| price_inquiry | 1.000 | 0.800 | 0.889 | 20 |
| general | 0.824 | 0.700 | 0.757 | 20 |

## 混淆矩阵

```json
{
  "logistics_query": {
    "logistics_query": 19,
    "return_policy": 0,
    "size_guide": 0,
    "price_inquiry": 0,
    "general": 0,
    "abstain": 1,
    "error": 0
  },
  "return_policy": {
    "logistics_query": 0,
    "return_policy": 18,
    "size_guide": 0,
    "price_inquiry": 0,
    "general": 0,
    "abstain": 2,
    "error": 0
  },
  "size_guide": {
    "logistics_query": 0,
    "return_policy": 0,
    "size_guide": 18,
    "price_inquiry": 0,
    "general": 0,
    "abstain": 2,
    "error": 0
  },
  "price_inquiry": {
    "logistics_query": 0,
    "return_policy": 0,
    "size_guide": 0,
    "price_inquiry": 16,
    "general": 3,
    "abstain": 1,
    "error": 0
  },
  "general": {
    "logistics_query": 0,
    "return_policy": 0,
    "size_guide": 0,
    "price_inquiry": 0,
    "general": 14,
    "abstain": 6,
    "error": 0
  },
  "abstain": {
    "logistics_query": 0,
    "return_policy": 0,
    "size_guide": 0,
    "price_inquiry": 0,
    "general": 0,
    "abstain": 30,
    "error": 0
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

## 未通过样本（仅合成编号与标签）

| Case ID | 期望 | 实际 |
| :--- | :--- | :--- |
| logistics_query-019 | logistics_query | mixed |
| return_policy-011 | return_policy | insufficient_context |
| return_policy-020 | return_policy | mixed |
| size_guide-008 | size_guide | insufficient_context |
| size_guide-011 | size_guide | insufficient_context |
| price_inquiry-005 | price_inquiry | general |
| price_inquiry-009 | price_inquiry | general |
| price_inquiry-019 | price_inquiry | general |
| price_inquiry-020 | price_inquiry | unknown |
| general-003 | general | unknown |
| general-005 | general | insufficient_context |
| general-013 | general | unknown |
| general-014 | general | insufficient_context |
| general-018 | general | unknown |
| general-020 | general | unknown |
| insufficient_context-008 | insufficient_context | unknown |

说明：报告只包含聚合指标，不包含客户原文、Prompt、模型原始输出或密钥。
