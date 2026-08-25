from datasets import load_dataset
from collections import Counter

# Hugging Face 데이터셋 다운로드
dataset = load_dataset("meal-bbang/Korean_message")

train_data = dataset["train"]

# CSV로 저장
train_data.to_csv(
    "data/raw/korean_message.csv",
    index=False
)

# 데이터 확인
print(train_data)
print("Saved: data/raw/korean_message.csv")

# 클래스별 데이터 개수 확인
print(Counter(train_data["class"]))

print("\n=== Class 1 ===")
print(train_data.filter(lambda x: x["class"] == 1)["content"][:5])

print("\n=== Class 2 ===")
print(train_data.filter(lambda x: x["class"] == 2)["content"][:5])

print("\n=== Class 3 ===")
print(train_data.filter(lambda x: x["class"] == 3)["content"][:10])