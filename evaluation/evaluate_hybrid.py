import os

import pandas as pd

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
)

from hybrid.detector import detect_with_hybrid


VAL_PATH = "data/processed/val.csv"
CHECKPOINT_PATH = "evaluation/hybrid_full_validation.csv"

df = pd.read_csv(VAL_PATH)

print(f"Validation 데이터: {len(df)}개")
print("Hybrid 평가 시작...")


# 이전 실행 결과가 있으면 불러오기
if os.path.exists(CHECKPOINT_PATH):
    checkpoint = pd.read_csv(CHECKPOINT_PATH)

    predictions = checkpoint["prediction"].tolist()
    start_index = len(predictions)

    print(f"체크포인트 발견: {start_index}개 완료")
    print(f"{start_index}번째부터 이어서 실행합니다.")

else:
    predictions = []
    start_index = 0


for index in range(start_index, len(df)):
    row = df.iloc[index]

    result = detect_with_hybrid(row["content"])
    label = result.get("label")

    # LLM JSON 파싱 실패 등이 발생하면 1회 재시도
    if label not in [0, 1]:
        print(f"\n[경고] 비정상 label - index {index}")
        print(f"내용: {row['content']}")
        print(f"1차 결과: {result}")
        print("→ 1회 재시도합니다.")

        result = detect_with_hybrid(row["content"])
        label = result.get("label")

    # 재시도해도 실패하면 None으로 남기고 다음 샘플 진행
    if label not in [0, 1]:
        print(f"[경고] 재시도 실패 - index {index}")
        print(f"2차 결과: {result}")
        pd.DataFrame({"prediction": predictions}).to_csv(
            CHECKPOINT_PATH, index=False
        )
        raise RuntimeError(f"index {index}: 예측 실패. 검증을 중단합니다.")
    else:
        predictions.append(label)

    # 10개마다 체크포인트 저장
    if (index + 1) % 10 == 0:
        pd.DataFrame({
            "prediction": predictions
        }).to_csv(
            CHECKPOINT_PATH,
            index=False,
        )


    # 진행 상황 출력
    if (index + 1) % 100 == 0:
        print(f"{index + 1}/{len(df)} 완료")


# 마지막 결과 저장
pd.DataFrame({
    "prediction": predictions
}).to_csv(
    CHECKPOINT_PATH,
    index=False,
)

if len(df) != 2452 or len(predictions) != len(df):
    raise RuntimeError(
        f"평가 건수 오류: validation={len(df)}, 예측={len(predictions)}"
    )

if any(label not in (0, 1) for label in predictions):
    raise RuntimeError("예측 실패 값이 있어 성능을 계산할 수 없습니다.")

df["prediction"] = predictions

y_true = df["label"].astype(int)
y_pred = df["prediction"].astype(int)

tn, fp, fn, tp = confusion_matrix(
    y_true,
    y_pred,
    labels=[0, 1],
).ravel()


print("\n=== Hybrid Validation 결과 ===")
print(f"Accuracy : {accuracy_score(y_true, y_pred):.4f}")
print(f"Precision: {precision_score(y_true, y_pred):.4f}")
print(f"Recall   : {recall_score(y_true, y_pred):.4f}")
print(f"F1       : {f1_score(y_true, y_pred):.4f}")

print()
print(f"TN: {tn}")
print(f"FP: {fp}")
print(f"FN: {fn}")
print(f"TP: {tp}")
print(f"FPR      : {fp / (fp + tn):.4f}")