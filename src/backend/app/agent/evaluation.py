"""计算版本化意图评测集的准确率、分类指标和拒判质量。"""

from dataclasses import dataclass

from pydantic import BaseModel, Field, model_validator

from app.agent.schemas import ClassificationState, IntentName


class EvaluationCase(BaseModel):
    """一条不含真实客户隐私的离线意图评测样本。"""

    case_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=4000)
    language: str = Field(default="zh-CN", max_length=20)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=10)
    expected_intent: IntentName | None
    expected_state: ClassificationState = ClassificationState.CLASSIFIED

    @model_validator(mode="after")
    def validate_expected_result(self) -> "EvaluationCase":
        """保证评测标签与生产输出使用相同的一致性规则。"""
        if self.expected_intent is None and self.expected_state == ClassificationState.CLASSIFIED:
            raise ValueError("拒判样本必须声明非 classified 状态")
        if self.expected_intent is not None and self.expected_state != ClassificationState.CLASSIFIED:
            raise ValueError("五类意图样本必须使用 classified 状态")
        return self


@dataclass(frozen=True, slots=True)
class EvaluationPrediction:
    """评测运行中的一条模型预测。"""

    case_id: str
    intent: IntentName | None
    classification_state: ClassificationState
    confidence: float
    input_tokens: int
    output_tokens: int
    latency_ms: int
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class IntentMetric:
    """单个意图的 precision、recall 和 F1。"""

    precision: float
    recall: float
    f1: float
    support: int


@dataclass(frozen=True, slots=True)
class EvaluationMetrics:
    """完整评测报告所需的聚合指标。"""

    classified_accuracy: float
    abstention_accuracy: float
    per_intent: dict[IntentName, IntentMetric]
    confusion_matrix: dict[str, dict[str, int]]
    total_input_tokens: int
    total_output_tokens: int
    average_latency_ms: float
    provider_failure_count: int
    provider_error_counts: dict[str, int]
    incorrect_cases: list[dict[str, str]]


def calculate_metrics(cases: list[EvaluationCase], predictions: list[EvaluationPrediction]) -> EvaluationMetrics:
    """计算分类与拒判指标，并拒绝样本缺失或重复结果。"""
    prediction_by_id = {item.case_id: item for item in predictions}
    if len(prediction_by_id) != len(predictions):
        raise ValueError("评测预测包含重复 case_id")
    if set(prediction_by_id) != {item.case_id for item in cases}:
        raise ValueError("评测预测必须与数据集 case_id 完全一致")

    classified_cases = [item for item in cases if item.expected_intent is not None]
    abstention_cases = [item for item in cases if item.expected_intent is None]
    classified_correct = sum(
        prediction_by_id[item.case_id].error_code is None
        and prediction_by_id[item.case_id].intent == item.expected_intent
        for item in classified_cases
    )
    abstention_correct = sum(
        prediction_by_id[item.case_id].error_code is None
        and prediction_by_id[item.case_id].intent is None
        and prediction_by_id[item.case_id].classification_state == item.expected_state
        for item in abstention_cases
    )

    labels = [item.value for item in IntentName] + ["abstain", "error"]
    confusion_matrix = {expected: {actual: 0 for actual in labels} for expected in labels}
    for case in cases:
        prediction = prediction_by_id[case.case_id]
        expected_label = case.expected_intent.value if case.expected_intent else "abstain"
        if prediction.error_code is not None:
            actual_label = "error"
        else:
            actual_label = prediction.intent.value if prediction.intent else "abstain"
        confusion_matrix[expected_label][actual_label] += 1

    per_intent: dict[IntentName, IntentMetric] = {}
    for intent in IntentName:
        true_positive = sum(
            case.expected_intent == intent
            and prediction_by_id[case.case_id].error_code is None
            and prediction_by_id[case.case_id].intent == intent
            for case in cases
        )
        predicted_positive = sum(
            prediction.error_code is None and prediction.intent == intent for prediction in predictions
        )
        actual_positive = sum(case.expected_intent == intent for case in cases)
        precision = true_positive / predicted_positive if predicted_positive else 0.0
        recall = true_positive / actual_positive if actual_positive else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_intent[intent] = IntentMetric(precision, recall, f1, actual_positive)

    provider_error_counts: dict[str, int] = {}
    for prediction in predictions:
        if prediction.error_code is not None:
            provider_error_counts[prediction.error_code] = provider_error_counts.get(prediction.error_code, 0) + 1

    incorrect_cases: list[dict[str, str]] = []
    for case in cases:
        prediction = prediction_by_id[case.case_id]
        expected = case.expected_intent.value if case.expected_intent else case.expected_state.value
        if prediction.error_code is not None:
            actual = f"error:{prediction.error_code}"
        elif prediction.intent is not None:
            actual = prediction.intent.value
        else:
            actual = prediction.classification_state.value
        if expected != actual:
            incorrect_cases.append({"case_id": case.case_id, "expected": expected, "actual": actual})

    return EvaluationMetrics(
        classified_accuracy=classified_correct / len(classified_cases) if classified_cases else 0.0,
        abstention_accuracy=abstention_correct / len(abstention_cases) if abstention_cases else 0.0,
        per_intent=per_intent,
        confusion_matrix=confusion_matrix,
        total_input_tokens=sum(item.input_tokens for item in predictions),
        total_output_tokens=sum(item.output_tokens for item in predictions),
        average_latency_ms=(sum(item.latency_ms for item in predictions) / len(predictions) if predictions else 0.0),
        provider_failure_count=sum(provider_error_counts.values()),
        provider_error_counts=provider_error_counts,
        incorrect_cases=incorrect_cases,
    )
