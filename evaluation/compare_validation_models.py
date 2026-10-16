from pathlib import Path

import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
)

from evaluation.evaluate_rule_thresholds import predict_score


PROJECT_ROOT = Path(__file__).resolve().parent.parent

VAL_PATH = PROJECT_ROOT / "data" / "processed" / "val.csv"

LLM_RESULT_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "llm_full_validation.csv"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "validation_model_comparison_same_2450.csv"
)


def calculate_metrics(name, y_true, y_pred):
    tn, fp, fn, tp = confusion_matrix(
        y_true,
        y_pred,
        labels=[0, 1],
    ).ravel()

    fpr = fp / (fp + tn) if fp + tn > 0 else 0.0

    return {
        "model": name,
        "evaluation_count": len(y_true),
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
        "fpr": fpr,
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def main():
    df = pd.read_csv(VAL_PATH)
    llm_results = pd.read_csv(LLM_RESULT_PATH)

    if len(df) != len(llm_results):
        raise ValueError(
            "val.csv와 LLM 결과의 행 수가 다릅니다."
        )

    # 저장된 LLM 결과를 원본 행 번호에 맞춘다.
    if "row_index" in llm_results.columns:
        llm_prediction = (
            llm_results
            .set_index("row_index")["prediction"]
            .reindex(df.index)
        )
    else:
        llm_prediction = (
            llm_results["prediction"]
            .reset_index(drop=True)
        )

    # LLM이 0 또는 1을 반환한 2,450개만 사용
    valid_mask = llm_prediction.isin([0, 1])
    failed_indices = df.index[~valid_mask].tolist()

    print(f"전체 Validation: {len(df)}개")
    print(f"공통 평가 대상: {int(valid_mask.sum())}개")
    print(f"LLM 실행 실패: {int((~valid_mask).sum())}개")
    print(f"실패 행 번호: {failed_indices}")

    # Rule 단독 예측
    rule_prediction = (
        df["content"]
        .apply(predict_score)
        .ge(1)
        .astype(int)
    )

    # 같은 LLM 예측값으로 Hybrid 결과 생성
    hybrid_prediction = llm_prediction.copy()
    hybrid_prediction.loc[rule_prediction == 1] = 1

    y_true = df.loc[valid_mask, "label"].astype(int)

    rule_pred = (
        rule_prediction.loc[valid_mask]
        .astype(int)
    )

    llm_pred = (
        llm_prediction.loc[valid_mask]
        .astype(int)
    )

    hybrid_pred = (
        hybrid_prediction.loc[valid_mask]
        .astype(int)
    )

    results = [
        calculate_metrics(
            "Rule",
            y_true,
            rule_pred,
        ),
        calculate_metrics(
            "LLM",
            y_true,
            llm_pred,
        ),
        calculate_metrics(
            "Hybrid",
            y_true,
            hybrid_pred,
        ),
    ]

    result_df = pd.DataFrame(results)

    result_df.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print("\n=== 동일한 2,450개 기준 모델 비교 ===")

    print(
        result_df.round(4).to_string(index=False)
    )

    print(f"\n결과 저장 위치: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()