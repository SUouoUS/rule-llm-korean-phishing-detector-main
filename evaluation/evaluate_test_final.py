"""Test 최종 평가 — 규칙 설정 두 가지를 같은 Test에서 비교한다. LLM 재호출 없음.

LLM 판단은 `evaluation/test_model_predictions.csv`에 2,383건 전부 저장돼 있고 Rule
설정과 무관하므로, 규칙을 바꿔도 `Hybrid = Rule 양성 OR 저장된 LLM`으로 다시 계산할
수 있다. 기존 파일은 읽기만 하고 절대 덮어쓰지 않는다.

비교하는 설정
  base   10/16 평가와 같은 Rule (택배 allowlist + 접수제한 문맥까지만)
  final  + 난독화 대응 4개 (한글 도메인, 단축 URL, TLD 표기 변형, 일반화 TLD)
         = Validation에서 고른 `enum+general`

⚠️ 보고할 때 반드시 구분할 것
  - **base 결과는 1차 평가(2026-10-16)이고 깨끗하다.** 이것이 본 결과다.
  - **final 결과는 2차 평가다.** 난독화 규칙은 Train 미탐에서 도출했지만, 무엇을
    찾을지는 Test 오류 분석(10/29)을 보고 정했다. 따라서 낙관적으로 치우쳤을 수
    있다. 개선 효과의 주된 근거는 Validation(Recall 0.8335 → 0.9381, 오탐 증가 0)에
    두고, 이 표는 보조로 쓴다.
  - 라벨 의심 17건도 Test를 보고 찾은 것이므로 **라벨은 고치지 않았다.**

F1과 F2를 함께 낸다. F2는 미탐(놓친 스미싱)을 오탐보다 무겁게 보는 지표다. 어느
지표를 우선하는지는 결과를 보고 고르지 말고 **논문 서론에서 먼저 밝힐 것.**

실행 (프로젝트 루트, Ollama 불필요):
    python -m evaluation.evaluate_test_final
"""

from pathlib import Path

import pandas as pd
from scipy.stats import binomtest

import rule_engine.detector as rule_detector
from evaluation.evaluate_rule_thresholds import predict_score


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_PATH = PROJECT_ROOT / "data" / "processed" / "test.csv"
STORED_PATH = PROJECT_ROOT / "evaluation" / "test_model_predictions.csv"
STORED_SUMMARY_PATH = PROJECT_ROOT / "evaluation" / "test_model_comparison.csv"

OUTPUT_DIR = PROJECT_ROOT / "evaluation" / "test_final"
COMPARISON_PATH = OUTPUT_DIR / "comparison.csv"
TIER_PATH = OUTPUT_DIR / "tiers.csv"
MCNEMAR_PATH = OUTPUT_DIR / "mcnemar.csv"
PREDICTION_PATH = OUTPUT_DIR / "predictions.csv"

OBFUSCATION_FLAGS = (
    "USE_HANGUL_DOMAIN",
    "USE_SHORTENER_HOSTS",
    "USE_TLD_VARIANTS",
    "USE_GENERAL_TLD",
    "USE_GENERAL_TLD_STRICT",
)

# 최종 설정은 Validation에서 고른 enum+general (STRICT는 쓰지 않는다)
CONFIGS = {
    "base": (),
    "final": (
        "USE_HANGUL_DOMAIN",
        "USE_SHORTENER_HOSTS",
        "USE_TLD_VARIANTS",
        "USE_GENERAL_TLD",
    ),
}


def set_config(enabled: tuple = ()) -> None:
    """난독화 옵션만 켠다. 택배 allowlist와 접수제한 문맥은 항상 켜 둔다."""

    rule_detector.USE_DOMAIN_ALLOWLIST = True
    rule_detector.USE_URGENCY_CONTEXT = True
    for flag in OBFUSCATION_FLAGS:
        setattr(rule_detector, flag, flag in enabled)


def scores(y_true: pd.Series, y_pred: pd.Series) -> dict:
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    tn = int(((y_pred == 0) & (y_true == 0)).sum())

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0

    def f_beta(beta: float) -> float:
        if not precision and not recall:
            return 0.0
        b2 = beta * beta
        return (1 + b2) * precision * recall / (b2 * precision + recall)

    return {
        "accuracy": (tp + tn) / len(y_true),
        "precision": precision,
        "recall": recall,
        "f1": f_beta(1),
        "f2": f_beta(2),
        "fpr": fp / (fp + tn) if fp + tn else 0.0,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "tp": tp,
    }


def tier_table(label: pd.Series, rule_pred: pd.Series, llm: pd.Series) -> dict:
    """3단계 위험도별 정밀도. 주의 = Rule 0점인데 LLM이 양성."""

    danger = rule_pred == 1
    caution = (rule_pred == 0) & (llm == 1)
    clear = (rule_pred == 0) & (llm == 0)

    def share(mask):
        return label[mask].mean() if mask.any() else float("nan")

    return {
        "danger_n": int(danger.sum()),
        "danger_precision": share(danger),
        "caution_n": int(caution.sum()),
        "caution_precision": share(caution),
        "clear_n": int(clear.sum()),
        "clear_miss_rate": share(clear),
    }


def mcnemar(label: pd.Series, pred_a: pd.Series, pred_b: pd.Series) -> dict:
    """두 예측의 정답 여부를 쌍으로 비교한다 (이항 정확검정, 양측)."""

    a_right = pred_a == label
    b_right = pred_b == label
    only_b = int((~a_right & b_right).sum())  # a만 틀림
    only_a = int((a_right & ~b_right).sum())  # b만 틀림
    discordant = only_a + only_b

    p_value = (
        binomtest(only_b, discordant, 0.5, alternative="two-sided").pvalue
        if discordant
        else 1.0
    )
    return {
        "b_only_right": only_b,
        "a_only_right": only_a,
        "discordant": discordant,
        "p_value": p_value,
    }


def check_reproduces_first_run(label: pd.Series, preds: dict) -> None:
    """base 설정이 10/16 1차 평가 수치를 그대로 재현하는지 확인한다."""

    stored = pd.read_csv(STORED_SUMMARY_PATH)
    stored.columns = [c.strip().lstrip("﻿") for c in stored.columns]
    stored = stored.set_index("model")

    problems = []
    for model in ("Rule", "LLM", "Hybrid"):
        got = scores(label, preds[model])
        want = stored.loc[model]
        for field in ("tp", "fp", "fn", "tn"):
            if got[field] != int(want[field]):
                problems.append(
                    f"{model}.{field}: 계산 {got[field]} vs 저장 {int(want[field])}"
                )
    if problems:
        raise ValueError(
            "base 설정이 1차 평가(10/16) 결과를 재현하지 못했습니다:\n  "
            + "\n  ".join(problems)
        )
    print("base 설정이 1차 평가(2026-10-16) 혼동행렬을 정확히 재현함 ✓")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    test = pd.read_csv(TEST_PATH)
    stored = pd.read_csv(STORED_PATH)
    if len(test) != len(stored):
        raise ValueError(f"행 수 불일치: test={len(test)}, 저장={len(stored)}")

    label = test["label"].astype(int)
    llm = stored["llm_prediction"].astype(int)
    if not llm.isin([0, 1]).all():
        raise ValueError("저장된 LLM 판단에 0/1이 아닌 값이 있습니다.")
    print(f"Test {len(test)}건 (정상 {int((label == 0).sum())} / 스미싱 {int((label == 1).sum())})")
    print("LLM 재호출 없음 — 저장된 판단 2,383건을 그대로 사용\n")

    rows, tiers, pairs = [], [], []
    predictions = pd.DataFrame({"row_index": range(len(test)), "label": label, "llm": llm})
    by_config = {}

    for config, flags in CONFIGS.items():
        set_config(flags)
        rule_pred = test["content"].apply(predict_score).ge(1).astype(int)
        hybrid_pred = rule_pred.where(rule_pred == 1, llm)

        preds = {"Rule": rule_pred, "LLM": llm, "Hybrid": hybrid_pred}
        by_config[config] = preds
        predictions[f"rule_{config}"] = rule_pred
        predictions[f"hybrid_{config}"] = hybrid_pred

        if config == "base":
            check_reproduces_first_run(label, preds)

        for model, pred in preds.items():
            row = {"config": config, "model": model, "count": len(test)}
            row.update(scores(label, pred))
            row["llm_call_rate"] = (rule_pred == 0).mean() if model == "Hybrid" else float("nan")
            rows.append(row)

        tier = {"config": config}
        tier.update(tier_table(label, rule_pred, llm))
        tiers.append(tier)

        pairs.append(("Rule", f"Hybrid ({config})", config, preds["Rule"], preds["Hybrid"]))
        pairs.append(("LLM", f"Hybrid ({config})", config, preds["LLM"], preds["Hybrid"]))

    pairs.append(
        ("Rule base", "Rule final", "base→final", by_config["base"]["Rule"], by_config["final"]["Rule"])
    )
    pairs.append(
        ("Hybrid base", "Hybrid final", "base→final", by_config["base"]["Hybrid"], by_config["final"]["Hybrid"])
    )

    set_config()

    comparison = pd.DataFrame(rows)
    tier_result = pd.DataFrame(tiers)
    mcnemar_rows = []
    for name_a, name_b, scope, pred_a, pred_b in pairs:
        entry = {"scope": scope, "a": name_a, "b": name_b}
        entry.update(mcnemar(label, pred_a, pred_b))
        mcnemar_rows.append(entry)
    mcnemar_result = pd.DataFrame(mcnemar_rows)

    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    tier_result.to_csv(TIER_PATH, index=False, encoding="utf-8-sig")
    mcnemar_result.to_csv(MCNEMAR_PATH, index=False, encoding="utf-8-sig")
    predictions.to_csv(PREDICTION_PATH, index=False, encoding="utf-8-sig")

    print("\n=== 성능 (F1과 F2를 함께 본다) ===")
    cols = ["config", "model", "precision", "recall", "f1", "f2", "fpr", "fp", "fn", "llm_call_rate"]
    print(comparison[cols].round(4).to_string(index=False))

    print("\n=== 3단계 위험도 교정값 ===")
    print("(위험=Rule 양성 / 주의=Rule 0점+LLM 양성 / 신호없음=둘 다 음성)")
    print(tier_result.round(4).to_string(index=False))

    print("\n=== McNemar (이항 정확검정, 양측) ===")
    print("b_only_right = b만 맞힌 건수, a_only_right = a만 맞힌 건수")
    print(mcnemar_result.round(6).to_string(index=False))

    print("\n=== 설정별 요약 ===")
    table = comparison.set_index(["config", "model"])
    for config in CONFIGS:
        rule = table.loc[(config, "Rule")]
        hybrid = table.loc[(config, "Hybrid")]
        winner_f1 = "Hybrid" if hybrid.f1 > rule.f1 else "Rule"
        winner_f2 = "Hybrid" if hybrid.f2 > rule.f2 else "Rule"
        print(
            f"[{config}] Rule F1 {rule.f1:.4f} / F2 {rule.f2:.4f}, "
            f"Hybrid F1 {hybrid.f1:.4f} / F2 {hybrid.f2:.4f}  "
            f"→ F1 우세 {winner_f1}, F2 우세 {winner_f2}"
        )

    print(
        "\n⚠️ 보고 시 구분할 것\n"
        "  base  = 1차 평가(2026-10-16)와 동일. 깨끗한 결과이며 이것이 본 결과다.\n"
        "  final = 2차 평가. 규칙 재료는 Train 미탐에서 왔지만 무엇을 찾을지는\n"
        "          Test 오류 분석을 보고 정했으므로 낙관적으로 치우쳤을 수 있다.\n"
        "          개선 효과의 주된 근거는 Validation에 둔다.\n"
        "  어느 지표를 우선하는지는 결과를 보고 고르지 말고 서론에서 먼저 밝힌다."
    )
    print(f"\n저장: {OUTPUT_DIR}")
    print(f"  (기존 {STORED_PATH.name} 은 읽기만 했고 변경하지 않았다)")


if __name__ == "__main__":
    main()
