"""난독화 대응 규칙 검증 (Train 확인용 + Validation + 택배 dev/eval).

규칙은 Train 미탐 998건에서 도출했다(`evaluation/analyze_train_misses.py`).
여기서는 그 규칙이 **다른 데이터에서** 얼마나 듣는지, 그리고 오탐을 얼마나
늘리는지 본다. LLM은 저장된 판단을 재사용하므로 새로 호출하지 않는다.

조건
  base       기존 Rule (옵션 3~5 전부 꺼짐)
  hangul     + 한글 도메인
  shortener  + 스킴 없는 단축 URL
  tldvar     + TLD 표기 변형 (점 대체 + 글자 변형)
  all        세 개 모두

보는 것 (순서대로 통과해야 Test로 넘어간다)
  1. Train Recall 상승    — 규칙을 여기서 뽑았으니 오르는 게 당연하다. 안 오르면 버그.
  2. Validation Recall/F1 — 다른 데이터에서도 듣는가 (여기가 실제 증거)
  3. **FPR 상승폭**        — 가장 중요. Rule 양성은 LLM을 건너뛰고 바로 "위험"이 된다.
  4. **3단계 교정값**      — 위험 98.6% / 주의 61.6% / 미탐율 7.4%가 유지되는가
  5. 택배 오탐            — 0건을 유지하는가 (한글 도메인 규칙이 택배 문자를 때릴 수 있음)

실행 (프로젝트 루트, Ollama 불필요):
    python -m evaluation.evaluate_obfuscation_rules
    python -m evaluation.evaluate_obfuscation_rules --eval   # 최종 확인 시에만
"""

import argparse
from pathlib import Path

import pandas as pd

import rule_engine.detector as rule_detector
from evaluation.evaluate_rule_improvements import (
    DELIVERY_LLM_PATH,
    load_delivery,
    load_validation,
    scores,
)
from evaluation.evaluate_rule_thresholds import predict_score


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRAIN_PATH = PROJECT_ROOT / "data" / "processed" / "train.csv"
OUTPUT_PATH = PROJECT_ROOT / "evaluation" / "obfuscation_rules.csv"
TIER_PATH = PROJECT_ROOT / "evaluation" / "obfuscation_rules_tiers.csv"

# (한글 도메인, 단축 URL, TLD 변형)
CONFIGS = {
    "base": (False, False, False),
    "hangul": (True, False, False),
    "shortener": (False, True, False),
    "tldvar": (False, False, True),
    "all": (True, True, True),
}


def set_config(hangul: bool, shortener: bool, tldvar: bool) -> None:
    rule_detector.USE_HANGUL_DOMAIN = hangul
    rule_detector.USE_SHORTENER_HOSTS = shortener
    rule_detector.USE_TLD_VARIANTS = tldvar


def rule_predict(df: pd.DataFrame) -> pd.Series:
    return df["content"].apply(predict_score).ge(1).astype(int)


def tier_table(df: pd.DataFrame, rule_pred: pd.Series) -> dict:
    """3단계 위험도별 정밀도. '주의'는 Rule 0점 + LLM 양성."""

    label = df["label"].astype(int)
    llm = df["llm"].astype(int)

    danger = rule_pred == 1
    caution = (rule_pred == 0) & (llm == 1)
    clear = (rule_pred == 0) & (llm == 0)

    def precision(mask):
        return label[mask].mean() if mask.any() else float("nan")

    return {
        "danger_n": int(danger.sum()),
        "danger_precision": precision(danger),
        "caution_n": int(caution.sum()),
        "caution_precision": precision(caution),
        "clear_n": int(clear.sum()),
        "clear_miss_rate": precision(clear),
    }


def evaluate(name: str, df: pd.DataFrame, with_llm: bool) -> tuple:
    rows, tiers = [], []
    for config, flags in CONFIGS.items():
        set_config(*flags)
        rule_pred = rule_predict(df)
        label = df["label"].astype(int)

        row = {"dataset": name, "config": config, "model": "Rule", "count": len(df)}
        row.update(scores(label, rule_pred))
        rows.append(row)

        if with_llm:
            hybrid_pred = rule_pred.where(rule_pred == 1, df["llm"].astype(int))
            hybrid = {"dataset": name, "config": config, "model": "Hybrid", "count": len(df)}
            hybrid.update(scores(label, hybrid_pred))
            hybrid["llm_call_rate"] = (rule_pred == 0).mean()
            rows.append(hybrid)

            tier = {"dataset": name, "config": config}
            tier.update(tier_table(df, rule_pred))
            tiers.append(tier)

    set_config(False, False, False)
    return rows, tiers


def load_train() -> pd.DataFrame:
    """규칙을 뽑은 데이터. 오르는 게 당연하므로 버그 확인용으로만 본다."""

    train = pd.read_csv(TRAIN_PATH)
    return train[["content", "label"]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval", action="store_true", help="택배 eval 포함 (최종 확인용)")
    args = parser.parse_args()

    delivery_llm = pd.read_csv(DELIVERY_LLM_PATH)
    validation = load_validation()

    rows, tiers = [], []
    r, _ = evaluate("train(규칙 출처)", load_train(), with_llm=False)
    rows += r
    r, t = evaluate("validation", validation, with_llm=True)
    rows += r
    tiers += t
    for split in ["dev"] + (["eval"] if args.eval else []):
        r, t = evaluate(f"delivery_{split}", load_delivery(split, delivery_llm), with_llm=True)
        rows += r
        tiers += t

    result = pd.DataFrame(rows)
    tier_result = pd.DataFrame(tiers)
    result.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    tier_result.to_csv(TIER_PATH, index=False, encoding="utf-8-sig")

    for dataset, part in result.groupby("dataset", sort=False):
        print(f"\n=== {dataset} ({part['count'].iloc[0]}건) ===")
        if dataset.startswith("delivery"):
            cols = ["config", "model", "fp", "fpr", "llm_call_rate"]
            cols = [c for c in cols if c in part.columns]
        else:
            cols = ["config", "model", "precision", "recall", "f1", "fpr", "fp", "fn"]
            if "llm_call_rate" in part.columns:
                cols.append("llm_call_rate")
        print(part[cols].round(4).to_string(index=False))

    print("\n=== 3단계 위험도 교정값 ===")
    print("(위험=Rule 양성 / 주의=Rule 0점+LLM 양성 / 신호없음=둘 다 음성)")
    for dataset, part in tier_result.groupby("dataset", sort=False):
        print(f"\n-- {dataset}")
        print(part.drop(columns=["dataset"]).round(4).to_string(index=False))

    base = result[(result.dataset == "validation") & (result.config == "base") & (result.model == "Rule")].iloc[0]
    best = result[(result.dataset == "validation") & (result.config == "all") & (result.model == "Rule")].iloc[0]
    print("\n=== 판단 기준 ===")
    print(f"Validation Rule Recall : {base.recall:.4f} → {best.recall:.4f}  ({best.recall - base.recall:+.4f})")
    print(f"Validation Rule FPR    : {base.fpr:.4f} → {best.fpr:.4f}  ({best.fpr - base.fpr:+.4f})")
    print(f"Validation Rule 미탐   : {int(base.fn)}건 → {int(best.fn)}건  (잔존 격차)")
    print(
        "\nFPR 상승폭이 감당 가능하고 택배 오탐이 0을 유지하면 Test 1회 평가로 넘어간다.\n"
        "Test는 LLM 재호출이 필요 없다 (2,383건 전부에 LLM 판단이 저장돼 있음)."
    )
    print(f"\n저장: {OUTPUT_PATH}\n      {TIER_PATH}")


if __name__ == "__main__":
    main()
