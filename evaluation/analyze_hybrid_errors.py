from datetime import datetime
from pathlib import Path

import pandas as pd

from evaluation.evaluate_rule_thresholds import predict_score


def main():
    root = Path(__file__).resolve().parent.parent
    df = pd.read_csv(root / "data/processed/val.csv")
    checkpoint = pd.read_csv(
        root / "evaluation/hybrid_full_validation.csv"
    )

    # 전체 데이터와 예측 개수가 맞는지 확인
    if len(df) != 2452 or len(checkpoint) != len(df):
        raise ValueError(
            f"행 수 불일치: validation={len(df)}, "
            f"checkpoint={len(checkpoint)}"
        )

    if not checkpoint["prediction"].isin([0, 1]).all():
        raise ValueError("체크포인트에 비어 있거나 잘못된 예측값이 있습니다.")

    df.insert(0, "row_index", range(len(df)))
    df["hybrid_prediction"] = checkpoint["prediction"].astype(int)
    df["rule_score"] = df["content"].apply(predict_score)
    df["rule_prediction"] = (df["rule_score"] >= 1).astype(int)

    # 현재 Hybrid 구조에서는 Rule 양성 결과가 바뀌면 안 됨
    inconsistent = (
        (df["rule_prediction"] == 1)
        & (df["hybrid_prediction"] != 1)
    )
    if inconsistent.any():
        raise ValueError("Rule 판정과 체크포인트가 맞지 않는 행이 있습니다.")

    groups = {
        "new_false_positives": (
            (df["label"] == 0)
            & (df["rule_prediction"] == 0)
            & (df["hybrid_prediction"] == 1)
        ),
        "recovered_phishing": (
            (df["label"] == 1)
            & (df["rule_prediction"] == 0)
            & (df["hybrid_prediction"] == 1)
        ),
        "remaining_false_negatives": (
            (df["label"] == 1)
            & (df["hybrid_prediction"] == 0)
        ),
    }

    output_dir = root / "evaluation" / (
        "error_analysis_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    output_dir.mkdir(parents=True, exist_ok=False)

    columns = [
        "row_index", "content", "label",
        "rule_score", "rule_prediction", "hybrid_prediction",
    ]

    for name, mask in groups.items():
        result = df.loc[mask, columns].copy()
        result.to_csv(
            output_dir / f"{name}.csv",
            index=False,
            encoding="utf-8-sig",
        )
        print(f"{name}: {len(result)}개")

    print(f"\n저장 위치: {output_dir}")


if __name__ == "__main__":
    main()