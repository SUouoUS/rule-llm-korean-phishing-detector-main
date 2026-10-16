from evaluation.evaluate_rule_thresholds import predict_score
from rule_engine.detector import analyze_message
from llm.detector import detect_with_llm


RULE_THRESHOLD = 1

def detect_with_hybrid(text: str) -> dict:
    """Rule Engine과 LLM을 결합해 메시지를 판별한다."""

    analysis =analyze_message(text)
    rule_score = predict_score(text)

    # Rule Engine이 피싱으로 탐지한 경우
    if rule_score >= RULE_THRESHOLD:
        detected_features = [
            feature
            for feature, result in analysis.items()
            if result["detected"]
        ]

        return{
            "label": 1,
            "source": "rule",
            "rule_score": rule_score,
            "evidence": detected_features,
            "reason": "Rule Engine 위험 신호 탐지",
        }

    #Rule Engine이 찾지 못한 경우 LLM에게 다시 판단시킨다.
    llm_result = detect_with_llm(text)

    return{
        "label": llm_result["label"],
        "source": "llm",
        "rule_score": rule_score,
        "evidence": llm_result.get("evidence", []),
        "reason": llm_result.get("reason", ""),
    }