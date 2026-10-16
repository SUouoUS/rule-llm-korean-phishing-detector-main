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

from llm.detector import detect_with_llm


ROOT = Path(__file__).resolve().parent.parent
VAL_PATH = ROOT / "data/processed/val.csv"
RESULT_PATH = ROOT / "evaluation/llm_full_validation.csv"
DETECTOR_PATH = ROOT / "llm/detector.py"

# 데이터 또는 LLM 코드가 바뀐 결과를 섞지 않도록 확인
RUN_ID = hashlib.sha256(
    VAL_PATH.read_bytes() + DETECTOR_PATH.read_bytes()
).hexdigest()


def save_results(results):
    temp_path = RESULT_PATH.with_suffix(".tmp")
    results.to_csv(temp_path, index=False, encoding="utf-8-sig")
    temp_path.replace(RESULT_PATH)


def main():
    df = pd.read_csv(VAL_PATH)

    if df["content"].isna().any():
        raise ValueError("내용이 비어 있는 데이터가 있습니다.")

    if RESULT_PATH.exists():
        results = pd.read_csv(RESULT_PATH)

        if (
            len(results) != len(df)
            or not results["run_id"].eq(RUN_ID).all()
            or results["row_index"].tolist() != list(range(len(df)))
        ):
            raise ValueError(
                "저장 결과와 현재 데이터·코드가 다릅니다. "
                "기존 결과 파일을 다른 이름으로 보관한 뒤 실행하세요."
            )
    else:
        results = pd.DataFrame({
            "row_index": range(len(df)),
            "run_id": RUN_ID,
            "prediction": float("nan"),
            "seconds": 0.0,
        })

    pending = results.index[
        results["prediction"].isna()
    ].tolist()

    print(f"검증 데이터: {len(df)}개", flush=True)
    print(f"완료: {len(df) - len(pending)}개 / 남음: {len(pending)}개",
          flush=True)

    for position, index in enumerate(pending, start=1):
        started = time.perf_counter()
        label = None

        try:
            # 비정상 응답이면 1회 재시도
            for attempt in range(2):
                result = detect_with_llm(df.iloc[index]["content"])
                label = result.get("label")

                if type(label) is int and label in (0, 1):
                    break

                label = None
                print(
                    f"[응답 오류] 행 {index}, 시도 {attempt + 1}",
                    flush=True,
                )
        except Exception as error:
            elapsed = time.perf_counter() - started

            print(
                f"\n[예측 실패] 행 {index}: {error}",
                flush=True,
            )

            # LLM 실행 오류를 -1로 기록하고 다음 데이터로 진행
            results.at[index, "prediction"] = -1
            results.at[index, "seconds"] += elapsed
            save_results(results)

            continue

        results.at[index, "prediction"] = (
            label if label is not None else float("nan")
        )
        results.at[index, "seconds"] += time.perf_counter() - started

        # 한 건마다 저장: 중단 후 다시 실행 가능
        save_results(results)

        if position == 1 or position % 10 == 0:
            completed = int(results["prediction"].isin([0, 1]).sum())
            print(f"{completed}/{len(df)}개 완료", flush=True)

        valid_mask = results["prediction"].isin([0, 1])
    invalid_count = int((~valid_mask).sum())

    # 정상적으로 0 또는 1을 반환한 데이터만 평가
    y_true = df.loc[valid_mask, "label"].astype(int)
    y_pred = results.loc[valid_mask, "prediction"].astype(int)

    tn, fp, fn, tp = confusion_matrix(
        y_true,
        y_pred,
        labels=[0, 1],
    ).ravel()

    fpr = fp / (fp + tn) if fp + tn else 0.0

    print("\n=== LLM 단독 Validation 결과 ===")
    print(f"전체 데이터: {len(df)}개")
    print(f"정상 평가: {len(y_true)}개")
    print(f"LLM 실행 실패: {invalid_count}개")
    print(f"Accuracy : {accuracy_score(y_true, y_pred):.4f}")
    print(
        f"Precision: "
        f"{precision_score(y_true, y_pred, zero_division=0):.4f}"
    )
    print(
        f"Recall   : "
        f"{recall_score(y_true, y_pred, zero_division=0):.4f}"
    )
    print(
        f"F1       : "
        f"{f1_score(y_true, y_pred, zero_division=0):.4f}"
    )
    print(f"TN: {tn} / FP: {fp} / FN: {fn} / TP: {tp}")
    print(f"FPR      : {fpr:.4f}")
    print(
        f"누적 호출 처리 시간: "
        f"{results['seconds'].sum() / 60:.1f}분"
    )
    print(f"저장 위치: {RESULT_PATH}")

    
if __name__ == "__main__":
    main()
    