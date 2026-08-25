import pandas as pd

# 1. 데이터 불러오기
df = pd.read_csv("data/raw/korean_message.csv")

print("=== 기본 정보 ===")
print(f"전체 데이터 수: {len(df)}")
print(f"컬럼: {df.columns.tolist()}")

# 2. 클래스 분포
print("\n=== 클래스 분포 ===")
print(df["class"].value_counts().sort_index())

# 3. 결측치 확인
print("\n=== 결측치 ===")
print(df.isnull().sum())

# 4. content 기준 완전 중복 확인
duplicate_count = df.duplicated(subset=["content"]).sum()

print("\n=== 중복 데이터 ===")
print(f"중복 content 수: {duplicate_count}")

# 5. 클래스별 고유 메시지 수
print("\n=== 클래스별 고유 content 수 ===")
print(
    df.groupby("class")["content"]
      .nunique()
      .sort_index()
)

# 6. 메시지 길이 기초 통계
df["content_length"] = df["content"].astype(str).str.len()

print("\n=== 클래스별 메시지 길이 ===")
print(
    df.groupby("class")["content_length"]
      .agg(["count", "mean", "median", "min", "max"])
      .round(2)
)