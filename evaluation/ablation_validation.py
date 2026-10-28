"""Hybrid 분기 조건 Ablation (Validation 전용).

이미 저장된 Validation LLM 판단(llm_full_validation.csv)을 재사용하므로
LLM을 새로 호출하지 않는다. 분기 조건만 바꿔 결과를 다시 조합한다.

  A: Rule score >= 1 → 스미싱 / 나머지 → LLM               (현재 구조)
  B: Rule score >= 2 → 스미싱 / 0~1점 → LLM                 (약한 신호도 LLM 재확인)
  C: A와 같되, 탐지 특징이 URL 하나뿐이면 → LLM             (URL만 걸린 경우 LLM 재확인)
  D: B + C                                                 (둘 다 적용)

실행 (프로젝트 루트):
    python -m evaluation.ablation_validation

※ Test 데이터에는 사용하지 않는다. 최종 구조를 정한 뒤 Test는 한 번만 평가한다.
"""

from pathlib import Path

import pandas as pd
from sklearn.metrics import confusion_matrix

from evaluation.evaluate_rule_thresholds import predict_score
from rule_engine.detector import analyze_message


PROJECT_ROOT = Path(__file__).resolve().parent.parent
VAL_PATH = PROJECT_ROOT / "data" / "processed" / "val.csv"
LLM_PATH = PROJECT_ROOT / "evaluation" / "llm_full_validation.csv"
OUTPUT_PATH = PROJECT_ROOT / "evaluation" / "ablation_validation.csv"


def features_of(text: str) -> frozenset:
    analysis = analyze_message(text)
    return frozenset(f for f, r in analysis.items() if r["detected"])


# 각 변형은 (score, features) → True면 Rule로 즉시 스미싱, False면 LLM 판단 사용
VARIANTS = {
    "A_current": lambda s, f: s >= 1,
    "B_threshold2": lambda s, f: s >= 2,
    "C_url_only_to_llm": lambda s, f: s >= 1 and f != frozenset({"url"}),
    "D_B_plus_C": lambda s, f: s >= 2 and f != frozenset({"url"}),
}


def metrics(name, y_true, y_pred, llm_calls, total):
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "variant": name,
        "count": total,
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "fpr": fp / (fp + tn) if fp + tn else 0.0,
        "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn),
        "llm_calls": int(llm_calls),
        "llm_call_rate": llm_calls / total,
    }


def main():
    val = pd.read_csv(VAL_PATH)
    llm = pd.read_csv(LLM_PATH)

    if len(val) != len(llm) or llm["row_index"].tolist() != list(range(len(val))):
        raise ValueError("val.csv와 llm_full_validation.csv의 행이 맞지 않습니다.")

    df = pd.DataFrame({
        "label": val["label"].astype(int),
        "score": val["content"].apply(predict_score),
        "features": val["content"].apply(features_of),
        "llm": llm["prediction"],
    })

    # LLM 실패 행은 모든 변형에서 공통으로 제외 (공정 비교)
    valid = df["llm"].isin([0, 1])
    print(f"Validation: {len(df)}건 / LLM 실패 제외: {int((~valid).sum())}건")
    df = df[valid].copy()
    df["llm"] = df["llm"].astype(int)

    rows = []
    for name, use_rule in VARIANTS.items():
        rule_decides = df.apply(lambda r: use_rule(r["score"], r["features"]), axis=1)
        pred = rule_decides.astype(int).where(rule_decides, df["llm"])
        rows.append(metrics(name, df["label"], pred, (~rule_decides).sum(), len(df)))

    result = pd.DataFrame(rows)
    result.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    print(result.round(4).to_string(index=False))
    print(f"\n저장: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
