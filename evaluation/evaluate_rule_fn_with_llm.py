import pandas as pd

from evaluation.evaluate_rule_thresholds import predict_score
from llm.detector import detect_with_llm

VALIDATION_PATH = "data/processed/val.csv"
SAMPLE_SIZE = 42
RANDOM_STATE = 42

df = pd.read_csv(VALIDATION_PATH)

#실제 피싱 중 Rule Engine 점수가 0인 메시지만 호출
phishing_df = df[df["label"] == 1].copy()

phishing_df["rule_score"] = phishing_df["content"].apply(
    predict_score
)

rule_fn = phishing_df[
    phishing_df["rule_score"] == 0
].sample(
    n=SAMPLE_SIZE,
    random_state=RANDOM_STATE,
)

print(f"전체 피싱: {len(phishing_df)}")
print(f"Rule Engine FN: {(phishing_df["rule_score"] == 0).sum()}")
print("-" * 50)

recovered = 0

# Rule Engine이 놓친 메시지를 LLM으로 다시 판정
for index, row in rule_fn.iterrows():
    result = detect_with_llm(row["content"])

    if result["label"] == 1:
        recovered += 1

    print("메시지:", row["content"])
    print("ㅣㅣㅡ dPcmr", result["label"])
    print("evidence", result["evidence"])
    print("reason", result["reason"])
    print("-" * 50)


recovery_rate = recovered / len(rule_fn)

print()
print("=== 결과 ===")
print(f"평가 샘플: {len(rule_fn)}")
print(f"LLM 보완 성공: {recovered}")
print(f"LLM 미탐: {len(rule_fn) - recovered}")
print(f"보완율: {recovery_rate:.4f}")