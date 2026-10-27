import hashlib
import time
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
from llm.detector import detect_with_llm


PROJECT_ROOT = Path(__file__).resolve().parent.parent

TEST_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "test.csv"
)

PREDICTION_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "test_model_predictions.csv"
)

COMPARISON_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "test_model_comparison.csv"
)

CONFIG_PATHS = [
    TEST_PATH,
    PROJECT_ROOT / "llm" / "detector.py",
    PROJECT_ROOT / "rule_engine" / "detector.py",
    PROJECT_ROOT / "evaluation" / "evaluate_rule_thresholds.py",
]


def make_run_id():
    """평가 데이터와 탐지 코드의 상태를 식별한다."""

    hasher = hashlib.sha256()

    for path in CONFIG_PATHS:
        if not path.exists():
            raise FileNotFoundError(
                f"필요한 파일이 없습니다: {path}"
            )

        hasher.update(path.read_bytes())

    return hasher.hexdigest()


def save_predictions(results):
    """중간 결과를 안전하게 저장한다."""

    temp_path = PREDICTION_PATH.with_suffix(".tmp")

    results.to_csv(
        temp_path,
        index=False,
        encoding="utf-8-sig",
    )

    temp_path.replace(PREDICTION_PATH)


def calculate_metrics(
    model_name,
    y_true,
    y_pred,
):
    """모델별 평가 지표를 계산한다."""

    tn, fp, fn, tp = confusion_matrix(
        y_true,
        y_pred,
        labels=[0, 1],
    ).ravel()

    fpr = (
        fp / (fp + tn)
        if fp + tn > 0
        else 0.0
    )

    return {
        "model": model_name,
        "evaluation_count": len(y_true),
        "accuracy": accuracy_score(
            y_true,
            y_pred,
        ),
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
    run_id = make_run_id()
    df = pd.read_csv(TEST_PATH)

    required_columns = {"content", "label"}

    if not required_columns.issubset(df.columns):
        raise ValueError(
            "test.csv에 content 또는 label 열이 없습니다."
        )

    if df["content"].isna().any():
        raise ValueError(
            "test.csv에 내용이 비어 있는 행이 있습니다."
        )

    print(f"Test 데이터: {len(df)}개")

    # Rule은 빠르므로 전체 데이터를 즉시 계산
    rule_prediction = (
        df["content"]
        .apply(predict_score)
        .ge(1)
        .astype(int)
    )

    hybrid_llm_call_count = int(
        (rule_prediction == 0).sum()
    )

    print(
        f"Hybrid 기준 예상 LLM 호출: "
        f"{hybrid_llm_call_count}개"
    )

    if PREDICTION_PATH.exists():
        results = pd.read_csv(PREDICTION_PATH)

        if len(results) != len(df):
            raise ValueError(
                "기존 Test 결과와 현재 Test 데이터의 "
                "행 수가 다릅니다."
            )

        if (
            results["row_index"].tolist()
            != list(range(len(df)))
        ):
            raise ValueError(
                "기존 Test 결과의 행 순서가 다릅니다."
            )

        if not results["run_id"].astype(str).eq(
            run_id
        ).all():
            raise ValueError(
                "Test 데이터 또는 탐지 코드가 변경되었습니다. "
                "기존 결과 파일을 보관한 뒤 새로 실행하세요."
            )

        # 저장된 Rule 결과도 현재 결과와 같은지 확인
        saved_rule = (
            results["rule_prediction"]
            .astype(int)
        )

        if not saved_rule.equals(rule_prediction):
            raise ValueError(
                "저장된 Rule 결과와 현재 Rule 결과가 다릅니다."
            )

    else:
        results = pd.DataFrame({
            "row_index": list(range(len(df))),
            "run_id": [run_id] * len(df),
            "rule_prediction": rule_prediction,
            "llm_prediction": [float("nan")] * len(df),
            "hybrid_prediction": [float("nan")] * len(df),
            "llm_seconds": [0.0] * len(df),
            "error": [""] * len(df),
        })

        save_predictions(results)

    # NaN은 아직 처리하지 않은 행이다.
    # -1은 LLM 실행에 실패한 행이다.
    pending = results.index[
        results["llm_prediction"].isna()
    ].tolist()

    handled_count = int(
        results["llm_prediction"].notna().sum()
    )

    print(
        f"처리 완료: {handled_count}개 / "
        f"남음: {len(pending)}개"
    )

    for position, index in enumerate(
        pending,
        start=1,
    ):
        started = time.perf_counter()

        label = None
        last_error = ""

        # 비정상 응답 또는 서버 오류 발생 시 1회 재시도
        for attempt in range(2):
            try:
                result = detect_with_llm(
                    df.iloc[index]["content"]
                )

                candidate = result.get("label")

                if (
                    isinstance(candidate, int)
                    and not isinstance(candidate, bool)
                    and candidate in (0, 1)
                ):
                    label = candidate
                    break

                last_error = (
                    f"비정상 label: {candidate}"
                )

            except Exception as error:
                last_error = str(error)

        elapsed = time.perf_counter() - started

        rule_label = int(
            rule_prediction.iloc[index]
        )

        if label in (0, 1):
            results.at[
                index,
                "llm_prediction",
            ] = label

            results.at[
                index,
                "hybrid_prediction",
            ] = (
                1
                if rule_label == 1
                else label
            )

            results.at[index, "error"] = ""

        else:
            # 실행 실패는 -1로 기록하고 다음 행으로 진행
            results.at[
                index,
                "llm_prediction",
            ] = -1

            # Rule이 잡은 경우 Hybrid는 LLM 실패와 무관하게 1
            results.at[
                index,
                "hybrid_prediction",
            ] = (
                1
                if rule_label == 1
                else -1
            )

            results.at[
                index,
                "error",
            ] = last_error

            print(
                f"\n[LLM 예측 실패] 행 {index}: "
                f"{last_error}",
                flush=True,
            )

        results.at[
            index,
            "llm_seconds",
        ] += elapsed

        # 한 건마다 저장
        save_predictions(results)

        if position == 1 or position % 10 == 0:
            current_handled = int(
                results["llm_prediction"]
                .notna()
                .sum()
            )

            success_count = int(
                results["llm_prediction"]
                .isin([0, 1])
                .sum()
            )

            failure_count = int(
                (results["llm_prediction"] == -1)
                .sum()
            )

            print(
                f"{current_handled}/{len(df)}개 처리 "
                f"(성공 {success_count}, "
                f"실패 {failure_count})",
                flush=True,
            )

    # 세 모델 모두 동일한 데이터에서 비교
    common_mask = (
        results["llm_prediction"]
        .isin([0, 1])
    )

    failed_indices = (
        results.loc[
            ~common_mask,
            "row_index",
        ]
        .astype(int)
        .tolist()
    )

    y_true = (
        df.loc[common_mask, "label"]
        .astype(int)
    )

    rule_pred = (
        results.loc[
            common_mask,
            "rule_prediction",
        ]
        .astype(int)
    )

    llm_pred = (
        results.loc[
            common_mask,
            "llm_prediction",
        ]
        .astype(int)
    )

    hybrid_pred = (
        results.loc[
            common_mask,
            "hybrid_prediction",
        ]
        .astype(int)
    )

    comparison = pd.DataFrame([
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
    ])

    comparison.to_csv(
        COMPARISON_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    llm_total_minutes = (
        results["llm_seconds"].sum()
        / 60
    )

    hybrid_llm_minutes = (
        results.loc[
            results["rule_prediction"] == 0,
            "llm_seconds",
        ].sum()
        / 60
    )

    print("\n=== Test 최종 평가 ===")
    print(f"전체 Test: {len(df)}개")
    print(f"공통 평가 대상: {int(common_mask.sum())}개")
    print(f"LLM 실행 실패: {len(failed_indices)}개")
    print(f"실패 행 번호: {failed_indices}")

    print(
        "\n"
        + comparison
        .round(4)
        .to_string(index=False)
    )

    print(
        f"\nLLM 단독 누적 호출 시간: "
        f"{llm_total_minutes:.1f}분"
    )

    print(
        f"Hybrid에 필요한 LLM 호출 시간: "
        f"{hybrid_llm_minutes:.1f}분"
    )

    print(
        f"LLM 단독 호출 수: {len(df)}개"
    )

    print(
        f"Hybrid LLM 호출 수: "
        f"{hybrid_llm_call_count}개"
    )

    print(
        f"\n예측 결과: {PREDICTION_PATH}"
    )

    print(
        f"비교 결과: {COMPARISON_PATH}"
    )


if __name__ == "__main__":
    main()