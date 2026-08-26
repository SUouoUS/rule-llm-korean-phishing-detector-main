from pathlib import Path
import re

import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import GroupShuffleSplit
from sklearn.neighbors import NearestNeighbors


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_PATH = PROJECT_ROOT / "data" / "processed" / "dataset_main.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"

TRAIN_PATH = OUTPUT_DIR / "train.csv"
VAL_PATH = OUTPUT_DIR / "val.csv"
TEST_PATH = OUTPUT_DIR / "test.csv"

RANDOM_STATE = 42

PHISHING_SIMILARITY_THRESHOLD = 0.90
PHISHING_MIN_LENGTH = 20


def normalize_template(text: str) -> str:
    text = str(text).lower().strip()

    # 줄바꿈 / 연속 공백 통일
    text = re.sub(r"\s+", " ", text)

    # URL / 도메인 정규화
    text = re.sub(
        r"(https?://\S+|www\.\S+|[a-z0-9.-]+\.(com|net|kr|co\.kr|org|io)\S*)",
        "<URL>",
        text,
        flags=re.IGNORECASE,
    )

    # 숫자 / 금액 / 전화번호 등 정규화
    text = re.sub(
        r"\d[\d,.-]*",
        "<NUM>",
        text,
    )

    # 같은 특수문자 반복 축약
    text = re.sub(
        r"([!@#$%^&*+=~_\-])\1+",
        r"\1",
        text,
    )

    return text.strip()


def create_normal_groups(df):
    """
    정상 데이터는 과도한 유사도 병합을 하지 않고
    정규화 template_key 기준으로만 그룹화한다.
    """
    df = df.copy()

    df["group_id"] = (
        "normal_template::"
        + df["template_key"].astype(str)
    )

    return df


def create_phishing_groups(df):
    """
    피싱 데이터는:
    1. 정규화 template_key가 동일하면 같은 그룹
    2. 길이 20자 이상이며 cosine similarity >= 0.90이면 같은 그룹

    으로 묶는다.
    """

    df = df.copy().reset_index(drop=True)

    n = len(df)

    # 그래프 edge 저장
    rows = []
    cols = []

    # --------------------------------------------------
    # 1. 동일 template_key 연결
    # --------------------------------------------------

    for _, indices in df.groupby("template_key").groups.items():
        indices = list(indices)

        if len(indices) <= 1:
            continue

        first = indices[0]

        for idx in indices[1:]:
            rows.extend([first, idx])
            cols.extend([idx, first])

    # --------------------------------------------------
    # 2. 긴 피싱 메시지만 similarity 기반 연결
    # --------------------------------------------------

    long_mask = (
        df["content"]
        .str.len()
        .ge(PHISHING_MIN_LENGTH)
    )

    long_indices = df.index[long_mask].to_numpy()

    long_df = df.loc[long_indices]

    print(
        f"유사도 클러스터링 대상 피싱 메시지: "
        f"{len(long_df)}개"
    )

    if len(long_df) >= 2:
        vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            min_df=2,
            sublinear_tf=True,
        )

        matrix = vectorizer.fit_transform(
            long_df["content"]
        )

        # cosine distance = 1 - cosine similarity
        radius = 1 - PHISHING_SIMILARITY_THRESHOLD

        nn = NearestNeighbors(
            metric="cosine",
            algorithm="brute",
            radius=radius,
        )

        nn.fit(matrix)

        graph = nn.radius_neighbors_graph(
            matrix,
            mode="connectivity",
        )

        graph = graph.maximum(graph.T)

        sim_rows, sim_cols = graph.nonzero()

        for r, c in zip(sim_rows, sim_cols):
            original_r = long_indices[r]
            original_c = long_indices[c]

            if original_r == original_c:
                continue

            rows.append(original_r)
            cols.append(original_c)

    # --------------------------------------------------
    # 3. 연결 그래프 → connected component
    # --------------------------------------------------

    if rows:
        data = [1] * len(rows)

        adjacency = coo_matrix(
            (data, (rows, cols)),
            shape=(n, n),
        ).tocsr()

    else:
        adjacency = coo_matrix(
            (n, n)
        ).tocsr()

    component_count, labels = connected_components(
        adjacency,
        directed=False,
    )

    df["group_id"] = [
        f"phishing_cluster::{label}"
        for label in labels
    ]

    print(
        f"피싱 similarity/template 그룹 수: "
        f"{component_count}"
    )

    group_sizes = (
        df["group_id"]
        .value_counts()
    )

    print(
        f"2개 이상 메시지를 가진 피싱 그룹 수: "
        f"{(group_sizes >= 2).sum()}"
    )

    print(
        f"가장 큰 피싱 그룹 크기: "
        f"{group_sizes.max()}"
    )

    return df


def split_one_label(df_label):
    groups = df_label["group_id"]

    # train 70% / temp 30%
    splitter_1 = GroupShuffleSplit(
        n_splits=1,
        train_size=0.70,
        random_state=RANDOM_STATE,
    )

    train_idx, temp_idx = next(
        splitter_1.split(
            df_label,
            groups=groups,
        )
    )

    train_df = df_label.iloc[train_idx].copy()
    temp_df = df_label.iloc[temp_idx].copy()

    # temp → validation 15% / test 15%
    splitter_2 = GroupShuffleSplit(
        n_splits=1,
        train_size=0.50,
        random_state=RANDOM_STATE,
    )

    val_idx, test_idx = next(
        splitter_2.split(
            temp_df,
            groups=temp_df["group_id"],
        )
    )

    val_df = temp_df.iloc[val_idx].copy()
    test_df = temp_df.iloc[test_idx].copy()

    return train_df, val_df, test_df


def check_group_overlap(train_df, val_df, test_df):
    train_groups = set(train_df["group_id"])
    val_groups = set(val_df["group_id"])
    test_groups = set(test_df["group_id"])

    train_val = train_groups & val_groups
    train_test = train_groups & test_groups
    val_test = val_groups & test_groups

    print("\n=== Group overlap 검사 ===")
    print(f"train ↔ val overlap: {len(train_val)}")
    print(f"train ↔ test overlap: {len(train_test)}")
    print(f"val ↔ test overlap: {len(val_test)}")

    if train_val or train_test or val_test:
        raise RuntimeError(
            "split 간 group_id 중복이 존재합니다."
        )


def print_split_stats(name, df):
    print(f"\n=== {name} ===")
    print(f"전체: {len(df)}")

    print(
        df["label"]
        .value_counts()
        .sort_index()
    )

    print("\n비율:")

    print(
        df["label"]
        .value_counts(normalize=True)
        .sort_index()
        .round(4)
    )


def main():
    df = pd.read_csv(INPUT_PATH)

    df["template_key"] = (
        df["content"]
        .apply(normalize_template)
    )

    normal_df = df[
        df["label"] == 0
    ].copy()

    phishing_df = df[
        df["label"] == 1
    ].copy()

    print(f"정상 데이터: {len(normal_df)}개")
    print(f"피싱 데이터: {len(phishing_df)}개")

    normal_df = create_normal_groups(
        normal_df
    )

    phishing_df = create_phishing_groups(
        phishing_df
    )

    grouped_df = pd.concat(
        [
            normal_df,
            phishing_df,
        ],
        ignore_index=True,
    )

    train_parts = []
    val_parts = []
    test_parts = []

    for label in sorted(
        grouped_df["label"].unique()
    ):
        label_df = grouped_df[
            grouped_df["label"] == label
        ].copy()

        train_df, val_df, test_df = split_one_label(
            label_df
        )

        train_parts.append(train_df)
        val_parts.append(val_df)
        test_parts.append(test_df)

    train_df = pd.concat(
        train_parts,
        ignore_index=True,
    )

    val_df = pd.concat(
        val_parts,
        ignore_index=True,
    )

    test_df = pd.concat(
        test_parts,
        ignore_index=True,
    )

    # 행 순서 랜덤화
    train_df = train_df.sample(
        frac=1,
        random_state=RANDOM_STATE,
    ).reset_index(drop=True)

    val_df = val_df.sample(
        frac=1,
        random_state=RANDOM_STATE,
    ).reset_index(drop=True)

    test_df = test_df.sample(
        frac=1,
        random_state=RANDOM_STATE,
    ).reset_index(drop=True)

    check_group_overlap(
        train_df,
        val_df,
        test_df,
    )

    print_split_stats(
        "TRAIN",
        train_df,
    )

    print_split_stats(
        "VALIDATION",
        val_df,
    )

    print_split_stats(
        "TEST",
        test_df,
    )

    columns_to_save = [
        "content",
        "label",
        "source",
    ]

    train_df[columns_to_save].to_csv(
        TRAIN_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    val_df[columns_to_save].to_csv(
        VAL_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    test_df[columns_to_save].to_csv(
        TEST_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print("\n=== 저장 완료 ===")
    print(f"train: {TRAIN_PATH}")
    print(f"val:   {VAL_PATH}")
    print(f"test:  {TEST_PATH}")


if __name__ == "__main__":
    main()