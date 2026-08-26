from pathlib import Path
from itertools import combinations
import sys

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from rule_engine.detector import (analyze_message,calculate_score,)


VAL_PATH = PROJECT_ROOT / "data" / "processed" / "val.csv"


CANDIDATE_KEYWORDS = [
    "가입",
    "신규",
    "이벤트",
    "쿠폰",
    "포인트",
    "기프티콘",
    "치킨",
    "피자",
    "스벅",
    "맥날",
    "카톡",
    "텔레",
    "카지노",
    "까지노",
    "슬롯",
    "게임랜드",
    "놀이터",
    "베팅",
    "배팅",
    "실장",
]


def get_rule_score(text: str) -> int:
    analysis = analyze_message(text)
    return calculate_score(analysis)


def count_keyword(df: pd.DataFrame, keyword: str) -> int:
    return (
        df["content"]
        .str.contains(
            keyword,
            case=False,
            regex=False,
            na=False,
        )
        .sum()
    )


def main():
    df = pd.read_csv(VAL_PATH)

    df["rule_score"] = (
        df["content"]
        .apply(get_rule_score)
    )

    candidate_features = [
        "reward",
        "contact",
        "gambling",
    ]

    for feature in candidate_features:
        df[feature] = df["content"].apply(
            lambda text: analyze_message(text)[feature]["detected"]
        )

    phishing_misses = df[
        (df["label"] == 1)
        & (df["rule_score"] == 0)
    ]

    normal = df[df["label"] == 0]

    phishing_misses = df[
        (df["label"] == 1)
        & (df["rule_score"] == 0)
    ]

    normal = df[df["label"] == 0]

    print(f"남은 0점 피싱: {len(phishing_misses)}개")
    print(f"정상 데이터: {len(normal)}개")

    rows = []

    for keyword in CANDIDATE_KEYWORDS:
        phishing_count = count_keyword(
            phishing_misses,
            keyword,
        )

        normal_count = count_keyword(
            normal,
            keyword,
        )

        phishing_rate = (
            phishing_count / len(phishing_misses)
        )

        normal_rate = (
            normal_count / len(normal)
        )

        rows.append(
            {
                "keyword": keyword,
                "phishing_count": phishing_count,
                "phishing_rate": phishing_rate,
                "normal_count": normal_count,
                "normal_rate": normal_rate,
            }
        )

    result_df = pd.DataFrame(rows)

    result_df = result_df.sort_values(
        by="phishing_count",
        ascending=False,
    )

    print("\n=== 후보 키워드 비교 ===")

    print(
        result_df.to_string(
            index=False,
            formatters={
                "phishing_rate": "{:.2%}".format,
                "normal_rate": "{:.2%}".format,
            },
        )
    )

    print("\n=== 후보 키워드 2개 조합 비교 ===")

    pair_rows = []

    for keyword1, keyword2 in combinations(CANDIDATE_KEYWORDS, 2):
        phishing_mask = (
            phishing_misses["content"].str.contains(
                keyword1,
                case=False,
                regex=False,
                na=False,
            )
            &
            phishing_misses["content"].str.contains(
                keyword2,
                case=False,
                regex=False,
                na=False,
            )
        )

        normal_mask = (
            normal["content"].str.contains(
                keyword1,
                case=False,
                regex=False,
                na=False,
            )
            &
            normal["content"].str.contains(
                keyword2,
                case=False,
                regex=False,
                na=False,
            )
        )

        phishing_count = phishing_mask.sum()
        normal_count = normal_mask.sum()

        # 둘 다 0이면 볼 필요 없음
        if phishing_count == 0 and normal_count == 0:
            continue

        pair_rows.append(
            {
                "pair": f"{keyword1} + {keyword2}",
                "phishing_count": phishing_count,
                "phishing_rate": phishing_count / len(phishing_misses),
                "normal_count": normal_count,
                "normal_rate": normal_count / len(normal),
            }
        )

    pair_df = pd.DataFrame(pair_rows)

    pair_df = pair_df.sort_values(
        by=[
            "phishing_count",
            "normal_count",
        ],
        ascending=[
            False,
            True,
        ],
    )

    print(
        pair_df.head(30).to_string(
            index=False,
            formatters={
                "phishing_rate": "{:.2%}".format,
                "normal_rate": "{:.2%}".format,
            },
        )
    )

    print("\n=== 후보 feature별 전체 Validation 분포 ===")

    feature_rows = []

    phishing_df = df[df["label"] == 1]
    normal_df = df[df["label"] == 0]

    for feature in candidate_features:
        phishing_count = phishing_df[feature].sum()
        normal_count = normal_df[feature].sum()

        feature_rows.append(
            {
                "feature": feature,
                "phishing_count": phishing_count,
                "phishing_rate": phishing_count / len(phishing_df),
                "normal_count": normal_count,
                "normal_rate": normal_count / len(normal_df),
            }
        )

    feature_df = pd.DataFrame(feature_rows)

    print(
        feature_df.to_string(
            index=False,
            formatters={
                "phishing_rate": "{:.2%}".format,
                "normal_rate": "{:.2%}".format,
            },
        )
    )


if __name__ == "__main__":
    main()