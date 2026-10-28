"""정상 배송 알림(class 3)을 템플릿 단위로 개선용(dev) / 평가용(eval)으로 나눈다.

- 같은 템플릿(이름·번호만 다른 문자)은 반드시 같은 쪽에 들어간다.
- dev는 Rule 개선 아이디어를 확인하는 데 쓰고, eval은 개선 후 최종 확인에만 쓴다.
- 원본 행 번호(row_index)를 남겨 기존 LLM 결과(delivery_predictions.csv)와 연결한다.

실행 (프로젝트 루트):
    python -m preprocessing.split_delivery
"""

from pathlib import Path

import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

from preprocessing.split_dataset import normalize_template


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "processed"
INPUT_PATH = DATA_DIR / "hf_class3_delivery.csv"
DEV_PATH = DATA_DIR / "delivery_dev.csv"
EVAL_PATH = DATA_DIR / "delivery_eval.csv"

RANDOM_STATE = 42


def main():
    df = pd.read_csv(INPUT_PATH)
    df.insert(0, "row_index", range(len(df)))
    df["template_key"] = df["content"].apply(normalize_template)

    splitter = GroupShuffleSplit(n_splits=1, train_size=0.5, random_state=RANDOM_STATE)
    dev_idx, eval_idx = next(splitter.split(df, groups=df["template_key"]))

    dev = df.iloc[dev_idx]
    eval_ = df.iloc[eval_idx]

    overlap = set(dev["template_key"]) & set(eval_["template_key"])
    if overlap:
        raise RuntimeError(f"dev와 eval에 같은 템플릿이 {len(overlap)}개 있습니다.")

    columns = ["row_index", "content", "source"]
    dev[columns].to_csv(DEV_PATH, index=False, encoding="utf-8-sig")
    eval_[columns].to_csv(EVAL_PATH, index=False, encoding="utf-8-sig")

    print(f"전체: {len(df)}건 / 템플릿 {df['template_key'].nunique()}개")
    print(f"dev : {len(dev)}건 / 템플릿 {dev['template_key'].nunique()}개 → {DEV_PATH}")
    print(f"eval: {len(eval_)}건 / 템플릿 {eval_['template_key'].nunique()}개 → {EVAL_PATH}")


if __name__ == "__main__":
    main()
