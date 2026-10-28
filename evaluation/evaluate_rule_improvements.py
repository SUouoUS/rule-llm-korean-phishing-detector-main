"""Rule 개선 옵션별 비교 (Validation + 배송 알림 dev/eval).

이미 저장된 LLM 판단을 재사용하므로 LLM을 새로 호출하지 않는다.
  - Validation LLM 판단: evaluation/llm_full_validation.csv
  - 배송 알림 LLM 판단: evaluation/delivery_eval/delivery_predictions.csv (--all 실행 결과)

비교 조건 (Hybrid 구조는 A로 고정: Rule score >= 1 → 스미싱, 나머지 → LLM)
  base        : 기존 Rule
  allowlist   : + 공식 도메인 허용
  context     : + "접수제한" 문맥 처리
  both        : 둘 다

실행 (먼저 python -m preprocessing.split_delivery 실행):
    python -m evaluation.evaluate_rule_improvements            # Validation + dev
    python -m evaluation.evaluate_rule_improvements --eval     # 최종 확인 시에만 eval 포함

※ 개선 방향은 Validation과 dev 결과만 보고 정한다. eval은 마지막에 한 번만 본다.
"""

import argparse
from pathlib import Path

import pandas as pd
from sklearn.metrics import confusion_matrix

import rule_engine.detector as rule_detector
from evaluation.evaluate_rule_thresholds import predict_score


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "processed"
VAL_PATH = DATA_DIR / "val.csv"
VAL_LLM_PATH = PROJECT_ROOT / "evaluation" / "llm_full_validation.csv"
DELIVERY_LLM_PATH = PROJECT_ROOT / "evaluation" / "delivery_eval" / "delivery_predictions.csv"
OUTPUT_PATH = PROJECT_ROOT / "evaluation" / "rule_improvements.csv"

CONFIGS = {
    "base": (False, False),
    "allowlist": (True, False),
    "context": (False, True),
    "both": (True, True),
}


def set_config(allowlist: bool, context: bool) -> None:
    rule_detector.USE_DOMAIN_ALLOWLIST = allowlist
    rule_detector.USE_URGENCY_CONTEXT = context


def scores(y_true, y_pred) -> dict:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "fpr": fp / (fp + tn) if fp + tn else 0.0,
        "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn),
    }


def load_validation() -> pd.DataFrame:
    val = pd.read_csv(VAL_PATH)
    llm = pd.read_csv(VAL_LLM_PATH)
    if len(val) != len(llm) or llm["row_index"].tolist() != list(range(len(val))):
        raise ValueError("val.csv와 llm_full_validation.csv의 행이 맞지 않습니다.")
    val["llm"] = llm["prediction"]
    return val[val["llm"].isin([0, 1])].copy()


def load_delivery(split: str, delivery_llm: pd.DataFrame) -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / f"delivery_{split}.csv")
    df = df.merge(
        delivery_llm[["row_index", "llm_prediction"]], on="row_index", how="left"
    ).rename(columns={"llm_prediction": "llm"})
    if not df["llm"].isin([0, 1]).all():
        raise ValueError(
            "배송 알림 일부에 LLM 판단이 없습니다. "
            "python -m evaluation.evaluate_delivery_notices --all 을 먼저 끝까지 실행하세요."
        )
    df["label"] = 0
    return df


def evaluate(name: str, df: pd.DataFrame) -> list:
    rows = []
    for config, flags in CONFIGS.items():
        set_config(*flags)
        rule_pred = df["content"].apply(predict_score).ge(1).astype(int)
        hybrid_pred = rule_pred.where(rule_pred == 1, df["llm"].astype(int))
        for model, pred in [("Rule", rule_pred), ("Hybrid", hybrid_pred)]:
            row = {"dataset": name, "config": config, "model": model, "count": len(df)}
            row.update(scores(df["label"].astype(int), pred))
            row["llm_call_rate"] = (rule_pred == 0).mean() if model == "Hybrid" else 0.0
            rows.append(row)
    set_config(False, False)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval", action="store_true", help="최종 확인용 eval 세트 포함")
    args = parser.parse_args()

    delivery_llm = pd.read_csv(DELIVERY_LLM_PATH)

    rows = evaluate("validation", load_validation())
    rows += evaluate("delivery_dev", load_delivery("dev", delivery_llm))
    if args.eval:
        rows += evaluate("delivery_eval", load_delivery("eval", delivery_llm))

    result = pd.DataFrame(rows)
    result.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

    for dataset, part in result.groupby("dataset", sort=False):
        print(f"\n=== {dataset} ({part['count'].iloc[0]}건) ===")
        if dataset == "validation":
            cols = ["config", "model", "precision", "recall", "f1", "fpr", "fp", "fn", "llm_call_rate"]
        else:  # 배송 알림은 전부 정상이므로 오탐만 의미 있음
            cols = ["config", "model", "fp", "fpr", "llm_call_rate"]
        print(part[cols].round(4).to_string(index=False))

    print(f"\n저장: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
