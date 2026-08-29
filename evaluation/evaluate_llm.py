import time

import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
)

from llm.detector import detect_with_llm


# 평가 설정
VALIDATION_PATH = "data/processed/val.csv"
SAMPLE_PER_CLASS = 20
RANDOM_STATE = 42


def load_sample():
    """Validation 데이터에서 정상/피싱 메시지를 각각 20개씩 추출한다."""

    df = pd.read_csv(VALIDATION_PATH)

    normal_sample = df[df["label"] == 0].sample(
        n=SAMPLE_PER_CLASS,
        random_state=RANDOM_STATE,
    )

    phishing_sample = df[df["label"] == 1].sample(
        n=SAMPLE_PER_CLASS,
        random_state=RANDOM_STATE,
    )

    # 정상 20개 + 피싱 20개를 합친 뒤 순서를 섞음
    sample_df = pd.concat(
        [normal_sample, phishing_sample],
        ignore_index=True,
    )

    sample_df = sample_df.sample(
        frac=1,
        random_state=RANDOM_STATE,
    ).reset_index(drop=True)

    return sample_df


def evaluate_llm():
    """추출한 메시지를 LLM으로 분류하고 성능을 평가한다."""

    df = load_sample()

    # 실제 정답과 LLM 예측값 저장
    y_true = []
    y_pred = []

    json_errors = 0
    inference_times = []

    print(f"평가 메시지 수: {len(df)}")
    print("-" * 60)

    # 메시지를 하나씩 LLM에 입력
    for index, row in df.iterrows():
        text = row["content"]
        true_label = int(row["label"])

        start_time = time.perf_counter()

        result = detect_with_llm(text)

        elapsed_time = time.perf_counter() - start_time
        inference_times.append(elapsed_time)

        pred_label = result.get("label")

        print(f"[{index + 1}/{len(df)}]")
        print("정답:", true_label)
        print("예측:", pred_label)
        print("메시지:", text)
        print("evidence:", result.get("evidence"))
        print("reason:", result.get("reason"))
        print(f"추론 시간: {elapsed_time:.2f}초")
        print("-" * 60)

        # 정상적인 0/1 결과가 아니면 오류로 기록
        if pred_label not in [0, 1]:
            json_errors += 1
            continue

        y_true.append(true_label)
        y_pred.append(pred_label)

    print()
    print("=" * 60)
    print("LLM 평가 결과")
    print("=" * 60)

    print(f"전체 샘플 수: {len(df)}")
    print(f"정상 예측 가능 결과 수: {len(y_pred)}")
    print(f"JSON/출력 오류 수: {json_errors}")

    if not y_pred:
        print("평가 가능한 예측 결과가 없습니다.")
        return

    # 정답과 예측값을 이용해 분류 성능 계산
    accuracy = accuracy_score(y_true, y_pred)
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)

    tn, fp, fn, tp = confusion_matrix(
        y_true,
        y_pred,
        labels=[0, 1],
    ).ravel()

    # LLM 실행 속도 계산
    total_time = sum(inference_times)
    average_time = total_time / len(inference_times)

    print(f"Accuracy : {accuracy:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall   : {recall:.4f}")
    print(f"F1-score : {f1:.4f}")

    print()
    print("Confusion Matrix")
    print(f"TN: {tn}")
    print(f"FP: {fp}")
    print(f"FN: {fn}")
    print(f"TP: {tp}")

    print()
    print(f"총 추론 시간: {total_time:.2f}초")
    print(f"평균 추론 시간: {average_time:.2f}초/메시지")


if __name__ == "__main__":
    evaluate_llm()