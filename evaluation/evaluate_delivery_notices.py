"""정상 배송 알림(class 3) 별도 평가.

정상 택배 알림 2,409건은 Train/Val/Test에 포함하지 않았으므로
'정상 배송 알림에 대한 오탐률'을 따로 측정한다.
모든 메시지가 정상(label 0)이므로 지표는 FPR(스미싱 오판 비율)만 의미가 있다.

실행 (프로젝트 루트에서, Ollama 실행 중이어야 함):
    python -m evaluation.evaluate_delivery_notices          # Hybrid용: Rule 0점만 LLM 호출 (약 1,510건)
    python -m evaluation.evaluate_delivery_notices --all    # LLM 단독 비교용: 전체 2,409건 LLM 호출

중간에 멈춰도 다시 실행하면 이어서 진행한다.
"""

import argparse
import hashlib
import json
import time
from pathlib import Path

import pandas as pd

from evaluation.evaluate_rule_thresholds import predict_score
from llm.detector import detect_with_llm
from rule_engine.detector import analyze_message


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "hf_class3_delivery.csv"
OUTPUT_DIR = PROJECT_ROOT / "evaluation" / "delivery_eval"
PREDICTION_PATH = OUTPUT_DIR / "delivery_predictions.csv"
SUMMARY_PATH = OUTPUT_DIR / "delivery_summary.csv"

CONFIG_PATHS = [
    DATA_PATH,
    PROJECT_ROOT / "llm" / "detector.py",
    PROJECT_ROOT / "rule_engine" / "detector.py",
    PROJECT_ROOT / "evaluation" / "evaluate_rule_thresholds.py",
]

BRANDS = [
    ("쿠팡", "쿠팡"),
    ("CJ대한통운", "cj"),
    ("우체국", "우체국"),
    ("SLX", "slx"),
    ("한진", "한진"),
    ("롯데", "롯데"),
]


def make_run_id() -> str:
    hasher = hashlib.sha256()
    for path in CONFIG_PATHS:
        hasher.update(path.read_bytes())
    return hasher.hexdigest()


def get_brand(text: str) -> str:
    lowered = text.lower()
    for name, keyword in BRANDS:
        if keyword in lowered:
            return name
    return "기타"


def detected_features(text: str) -> str:
    analysis = analyze_message(text)
    return ",".join(
        feature for feature, result in analysis.items() if result["detected"]
    )


def save(results: pd.DataFrame) -> None:
    temp_path = PREDICTION_PATH.with_suffix(".tmp")
    results.to_csv(temp_path, index=False, encoding="utf-8-sig")
    temp_path.replace(PREDICTION_PATH)


def run_llm(text: str) -> tuple:
    """LLM을 호출하고 (label, evidence, reason, error)를 반환한다. 실패 시 1회 재시도."""
    last_error = ""
    for _ in range(2):
        try:
            result = detect_with_llm(text)
            label = result.get("label")
            if isinstance(label, int) and not isinstance(label, bool) and label in (0, 1):
                return (
                    label,
                    json.dumps(result.get("evidence", []), ensure_ascii=False),
                    result.get("reason", ""),
                    "",
                )
            last_error = f"비정상 label: {label}"
        except Exception as error:  # 서버 오류 등
            last_error = str(error)
    return -1, "[]", "", last_error


def summarize(results: pd.DataFrame, run_all: bool) -> pd.DataFrame:
    rows = []
    groups = [("전체", results)] + list(results.groupby("brand"))
    for name, part in groups:
        row = {
            "brand": name,
            "count": len(part),
            "rule_fp": int(part["rule_prediction"].sum()),
            "rule_fpr": part["rule_prediction"].mean(),
        }
        done = part["hybrid_prediction"].isin([0, 1])
        row["hybrid_evaluated"] = int(done.sum())
        row["hybrid_fp"] = int(part.loc[done, "hybrid_prediction"].sum())
        row["hybrid_fpr"] = part.loc[done, "hybrid_prediction"].mean() if done.any() else float("nan")
        if run_all:
            llm_done = part["llm_prediction"].isin([0, 1])
            row["llm_evaluated"] = int(llm_done.sum())
            row["llm_fp"] = int(part.loc[llm_done, "llm_prediction"].sum())
            row["llm_fpr"] = part.loc[llm_done, "llm_prediction"].mean() if llm_done.any() else float("nan")
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--all",
        action="store_true",
        help="Rule 결과와 상관없이 전체 메시지에 LLM 호출 (LLM 단독 비교용)",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(DATA_PATH)
    run_id = make_run_id()

    rule_score = df["content"].apply(predict_score)
    rule_prediction = rule_score.ge(1).astype(int)

    if PREDICTION_PATH.exists():
        text_columns = ["run_id", "brand", "rule_features", "llm_evidence", "llm_reason", "error"]
        results = pd.read_csv(PREDICTION_PATH, dtype={c: str for c in text_columns})
        results[text_columns] = results[text_columns].fillna("")
        if len(results) != len(df) or not results["run_id"].astype(str).eq(run_id).all():
            raise ValueError(
                "데이터 또는 탐지 코드가 바뀌었습니다. "
                f"{PREDICTION_PATH} 를 다른 이름으로 보관한 뒤 다시 실행하세요."
            )
    else:
        results = pd.DataFrame({
            "row_index": range(len(df)),
            "run_id": run_id,
            "brand": df["content"].apply(get_brand),
            "rule_score": rule_score,
            "rule_features": df["content"].apply(detected_features),
            "rule_prediction": rule_prediction,
            "llm_prediction": float("nan"),
            "hybrid_prediction": [1.0 if p == 1 else float("nan") for p in rule_prediction],
            "llm_evidence": "",
            "llm_reason": "",
            "llm_seconds": 0.0,
            "error": "",
        })
        save(results)

    print(f"정상 배송 알림: {len(df)}건")
    print(f"Rule 오탐: {int(rule_prediction.sum())}건 (FPR {rule_prediction.mean():.4f})")

    need_llm = results["llm_prediction"].isna()
    if not args.all:
        need_llm &= results["rule_prediction"] == 0
    pending = results.index[need_llm].tolist()
    print(f"LLM 호출 대상(남은 건수): {len(pending)}건")

    for position, index in enumerate(pending, start=1):
        started = time.perf_counter()
        label, evidence, reason, error = run_llm(df.at[index, "content"])
        results.at[index, "llm_seconds"] = time.perf_counter() - started
        results.at[index, "llm_prediction"] = label
        results.at[index, "llm_evidence"] = evidence
        results.at[index, "llm_reason"] = reason
        results.at[index, "error"] = error
        if results.at[index, "rule_prediction"] == 0:
            results.at[index, "hybrid_prediction"] = label  # 실패 시 -1
        save(results)

        if position == 1 or position % 20 == 0 or position == len(pending):
            print(f"{position}/{len(pending)} 처리", flush=True)

    summary = summarize(results, args.all)
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")

    failed = int((results["llm_prediction"] == -1).sum())
    print("\n=== 정상 배송 알림 오탐 결과 ===")
    print(summary.round(4).to_string(index=False))
    print(f"\nLLM 실패: {failed}건")
    print(f"예측 결과: {PREDICTION_PATH}")
    print(f"요약: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
