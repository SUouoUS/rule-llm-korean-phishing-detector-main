from pathlib import Path
import sys

import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 프로젝트 루트의 rule_engine 모듈을 import할 수 있도록 설정
sys.path.append(str(PROJECT_ROOT))

from rule_engine.detector import analyze_message, calculate_score


VAL_PATH = PROJECT_ROOT / "data" / "processed" / "val.csv"


def predict_score(text: str) -> int:
    """메시지 하나의 Rule Engine 위험 점수를 반환한다."""

    analysis = analyze_message(text)

    # 기존 핵심 feature 점수
    score = calculate_score(analysis)

    # 보조 feature는 여러 개가 탐지되어도 최대 +1
    candidate_detected = any(
        analysis[feature]["detected"]
        for feature in [
            "reward",
            "contact",
            "gambling",
        ]
    )

    if candidate_detected:
        score += 1

    return score


def evaluate_threshold(df: pd.DataFrame, threshold: int) -> dict:
    """주어진 threshold에서 validation 성능을 계산한다."""

    y_true = df["label"]

    y_pred = (
        df["rule_score"] >= threshold
    ).astype(int)

    tn, fp, fn, tp = confusion_matrix(
        y_true,
        y_pred,
        labels=[0, 1],
    ).ravel()

    false_positive_rate = (
        fp / (fp + tn)
        if (fp + tn) > 0
        else 0.0
    )

    return {
        "threshold": threshold,
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(
            y_true,
            y_pred,
            zero_division=0,
        ),
        "recall": recall_score(
            y_true,
            y_pred,
            zero_division=0,
        ),
        "f1": f1_score(
            y_true,
            y_pred,
            zero_division=0,
        ),
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "tp": tp,
        "false_positive_rate": false_positive_rate,
    }


def main():
    df = pd.read_csv(VAL_PATH)

    print(f"Validation 데이터: {len(df)}개")

    # 각 메시지의 Rule Engine 점수를 한 번만 계산
    df["rule_score"] = (
        df["content"]
        .apply(predict_score)
    )

    false_negative_candidates = df[
        (df["label"] == 1)
        & (df["rule_score"] == 0)
    ]

    print(
        "\n=== Rule score 0인 피싱 샘플 ==="
    )

    print(
        false_negative_candidates["content"]
        .sample(
            min(30, len(false_negative_candidates)),
            random_state=42,
        )
        .to_string(index=False)
    )

    print("\n=== Rule score 분포 ===")
    print(
        df.groupby(["label", "rule_score"])
        .size()
        .unstack(fill_value=0)
    )

    results = []

    for threshold in range(1, 8):
        results.append(
            evaluate_threshold(
                df,
                threshold,
            )
        )

    result_df = pd.DataFrame(results)

    print("\n=== Threshold별 Validation 성능 ===")

    display_columns = [
        "threshold",
        "accuracy",
        "precision",
        "recall",
        "f1",
        "false_positive_rate",
        "tn",
        "fp",
        "fn",
        "tp",
    ]

    print(
        result_df[display_columns]
        .round(4)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()