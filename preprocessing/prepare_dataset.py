from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent

HF_PATH = PROJECT_ROOT / "data" / "raw" / "korean_message.csv"
AIHUB_PATH = PROJECT_ROOT / "data" / "processed" / "aihub_normal.csv"

OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"

MAIN_OUTPUT_PATH = OUTPUT_DIR / "dataset_main.csv"
HARD_NEGATIVE_OUTPUT_PATH = OUTPUT_DIR / "hf_class3_delivery.csv"


def load_data():
    hf_df = pd.read_csv(HF_PATH)
    aihub_df = pd.read_csv(AIHUB_PATH)

    return hf_df, aihub_df


def clean_content(df):
    df = df.copy()

    df["content"] = df["content"].astype(str).str.strip()

    df = df[df["content"] != ""]
    df = df.dropna(subset=["content"])

    return df


def prepare_main_dataset(hf_df, aihub_df):
    hf_normal = hf_df[hf_df["class"] == 1][["content"]].copy()
    hf_normal["label"] = 0
    hf_normal["source"] = "hf_normal"

    hf_phishing = hf_df[hf_df["class"] == 2][["content"]].copy()
    hf_phishing["label"] = 1
    hf_phishing["source"] = "hf_phishing"

    aihub_normal = aihub_df[["content"]].copy()
    aihub_normal["label"] = 0
    aihub_normal["source"] = "aihub_normal"

    main_df = pd.concat(
        [
            hf_normal,
            hf_phishing,
            aihub_normal,
        ],
        ignore_index=True,
    )

    main_df = clean_content(main_df)

    before = len(main_df)

    main_df = main_df.drop_duplicates(
        subset=["content"],
        keep="first",
    )

    removed = before - len(main_df)

    print(f"main dataset 완전 중복 제거: {removed}개")

    return main_df


def prepare_hard_negative(hf_df):
    hard_negative_df = hf_df[
        hf_df["class"] == 3
    ][["content"]].copy()

    hard_negative_df["source"] = "hf_class3_delivery"

    hard_negative_df = clean_content(hard_negative_df)

    before = len(hard_negative_df)

    hard_negative_df = hard_negative_df.drop_duplicates(
        subset=["content"],
        keep="first",
    )

    removed = before - len(hard_negative_df)

    print(f"hard negative 완전 중복 제거: {removed}개")

    return hard_negative_df


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    hf_df, aihub_df = load_data()

    main_df = prepare_main_dataset(
        hf_df,
        aihub_df,
    )

    hard_negative_df = prepare_hard_negative(
        hf_df
    )

    main_df.to_csv(
        MAIN_OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    hard_negative_df.to_csv(
        HARD_NEGATIVE_OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print("\n=== 저장 완료 ===")

    print(
        f"메인 데이터셋: {len(main_df)}개"
    )

    print(
        main_df["label"].value_counts().sort_index()
    )

    print(
        f"\nhard negative: {len(hard_negative_df)}개"
    )

    print(
        f"\n저장 위치: {MAIN_OUTPUT_PATH}"
    )

    print(
        f"저장 위치: {HARD_NEGATIVE_OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()