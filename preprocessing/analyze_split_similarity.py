from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "processed"

TRAIN_PATH = DATA_DIR / "train.csv"
VAL_PATH = DATA_DIR / "val.csv"
TEST_PATH = DATA_DIR / "test.csv"

SIMILARITY_THRESHOLDS = [0.90, 0.95, 0.98, 0.99]
MIN_LENGTHS = [0, 10, 20, 30, 50]


def load_split(path):
    return pd.read_csv(path)


def analyze_similarity(
    reference_df,
    target_df,
    reference_name,
    target_name,
):
    print(
        f"\n=== {reference_name} ↔ {target_name} 유사도 검사 ==="
    )

    # 두 split의 텍스트를 함께 사용하여 동일한 TF-IDF 공간 생성
    all_texts = pd.concat(
        [
            reference_df["content"],
            target_df["content"],
        ],
        ignore_index=True,
    )

    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        min_df=2,
        sublinear_tf=True,
    )

    vectorizer.fit(all_texts)

    reference_matrix = vectorizer.transform(
        reference_df["content"]
    )

    target_matrix = vectorizer.transform(
        target_df["content"]
    )

    # 각 target 메시지에서 가장 유사한 reference 메시지 1개 탐색
    nn = NearestNeighbors(
        n_neighbors=1,
        metric="cosine",
        algorithm="brute",
    )

    nn.fit(reference_matrix)

    distances, indices = nn.kneighbors(
        target_matrix
    )

    similarities = 1 - distances.flatten()
    nearest_indices = indices.flatten()

    result_df = target_df[
        ["content", "label", "source"]
    ].copy()

    result_df["similarity"] = similarities

    result_df["nearest_content"] = [
        reference_df.iloc[i]["content"]
        for i in nearest_indices
    ]

    result_df["nearest_label"] = [
        reference_df.iloc[i]["label"]
        for i in nearest_indices
    ]

    result_df["nearest_source"] = [
        reference_df.iloc[i]["source"]
        for i in nearest_indices
    ]

        # 메시지 길이 추가
    result_df["length"] = result_df["content"].str.len()

    high_sim = result_df[
        result_df["similarity"] >= 0.90
    ]

    print("\n=== similarity >= 0.90 source 분포 ===")
    print(high_sim["source"].value_counts())

    print("\n=== source별 전체 대비 비율 ===")

    for source, source_df in result_df.groupby("source"):
        high_count = (
            source_df["similarity"] >= 0.90
        ).sum()

        print(
            f"{source}: "
            f"{high_count}/{len(source_df)} "
            f"({high_count / len(source_df):.2%})"
        )

        # threshold 구간별 사례 확인
    ranges = [
        (0.99, 1.01),
        (0.98, 0.99),
        (0.95, 0.98),
        (0.90, 0.95),
    ]

    for low, high in ranges:
        candidates = result_df[
            (result_df["similarity"] >= low)
            & (result_df["similarity"] < high)
        ]

        print(
            f"\n=== similarity {low:.2f} ~ {high:.2f} "
            f"샘플 ==="
        )

        if candidates.empty:
            print("해당 구간 없음")
            continue

        sample = candidates.sample(
            min(5, len(candidates)),
            random_state=42,
        )

        for _, row in sample.iterrows():
            print("\n------------------------------")
            print(f"Similarity: {row['similarity']:.4f}")

            print(f"[{target_name}]")
            print(row["content"])

            print(f"\n[{reference_name}]")
            print(row["nearest_content"])

    print(f"검사 대상 메시지 수: {len(target_df)}")

    print("\n=== 유사도 threshold별 후보 수 ===")

    for threshold in SIMILARITY_THRESHOLDS:
        count = (result_df["similarity"] >= threshold).sum()

        print(
            f"{threshold:.2f} 이상: "
            f"{count}개 "
            f"({count / len(result_df):.2%})"
        )


    print("\n=== 유사도 + 최소 메시지 길이별 후보 수 ===")

    for threshold in SIMILARITY_THRESHOLDS:
        print(f"\n[similarity >= {threshold:.2f}]")

        for min_length in MIN_LENGTHS:
            mask = (
                (result_df["similarity"] >= threshold)
                & (result_df["length"] >= min_length)
            )

            count = mask.sum()

            print(
                f"길이 >= {min_length:2d}: "
                f"{count:4d}개 "
                f"({count / len(result_df):.2%})"
            )

def main():
    train_df = load_split(TRAIN_PATH)
    val_df = load_split(VAL_PATH)
    test_df = load_split(TEST_PATH)

    analyze_similarity(
        train_df,
        val_df,
        "TRAIN",
        "VALIDATION",
    )

    analyze_similarity(
        train_df,
        test_df,
        "TRAIN",
        "TEST",
    )


if __name__ == "__main__":
    main()