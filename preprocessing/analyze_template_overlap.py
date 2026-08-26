from pathlib import Path
import re

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "dataset_main.csv"


def normalize_template(text: str) -> str:
    text = str(text).lower().strip()

    # 줄바꿈 → 공백
    text = re.sub(r"\s+", " ", text)

    # URL / 도메인 형태 정규화
    text = re.sub(
        r"(https?://\S+|www\.\S+|[a-z0-9.-]+\.(com|net|kr|co\.kr|org|io)\S*)",
        "<URL>",
        text,
        flags=re.IGNORECASE,
    )

    # 숫자/금액/전화번호 등 가변 숫자 정규화
    text = re.sub(r"\d[\d,.-]*", "<NUM>", text)

    # 같은 특수문자 반복 축약
    text = re.sub(r"([!@#$%^&*+=~_\-])\1+", r"\1", text)

    # 앞뒤 공백 정리
    text = text.strip()

    return text


def main():
    df = pd.read_csv(DATA_PATH)

    print(f"전체 데이터 수: {len(df)}")

    df["template_key"] = df["content"].apply(normalize_template)

    # 정규화 후 중복
    duplicated_mask = df["template_key"].duplicated(keep=False)
    duplicated_df = df[duplicated_mask].copy()

    print(
        f"정규화 후 중복 그룹에 포함된 메시지 수: "
        f"{len(duplicated_df)}"
    )

    print(
        f"정규화 template_key 고유 개수: "
        f"{df['template_key'].nunique()}"
    )

    # 같은 template_key 안에 서로 다른 label이 존재하는지 확인
    label_counts = (
        df.groupby("template_key")["label"]
        .nunique()
    )

    conflict_keys = label_counts[label_counts > 1].index

    conflict_df = df[
        df["template_key"].isin(conflict_keys)
    ].copy()

    print(
        f"라벨 충돌 template 그룹 수: "
        f"{len(conflict_keys)}"
    )

    print(
        f"라벨 충돌에 포함된 메시지 수: "
        f"{len(conflict_df)}"
    )

    if len(conflict_df) > 0:
        print("\n=== 라벨 충돌 예시 ===")

        for key in list(conflict_keys[:10]):
            print("\n[TEMPLATE]")
            print(key)

            sample = df[df["template_key"] == key][
                ["content", "label", "source"]
            ]

            print(sample.to_string(index=False))

    # 가장 큰 템플릿 그룹 확인
    print("\n=== 가장 큰 템플릿 그룹 TOP 10 ===")

    group_sizes = (
        df.groupby("template_key")
        .size()
        .sort_values(ascending=False)
        .head(10)
    )

    for key, size in group_sizes.items():
        print(f"\n그룹 크기: {size}")
        print(f"template: {key}")

        sample = df[df["template_key"] == key][
            ["content", "label", "source"]
        ].head(5)

        print(sample.to_string(index=False))


if __name__ == "__main__":
    main()