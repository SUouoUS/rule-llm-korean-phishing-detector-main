"""Test에서 Hybrid가 틀린 사례를 유형 분류용으로 모은다 (LLM reason 포함).

Hybrid 오류 165건(오탐 65 + 미탐 100)을 판단 경로별로 나누고, LLM이 왜 그렇게
답했는지 reason/evidence를 받아 적는다. 유형 분류는 사람이 CSV를 읽고 한다.

판단 경로별 분류
  rule_fp : 정상인데 Rule이 양성 → Hybrid 오탐. 실제 파이프라인에서는 LLM을
            호출하지 않지만, "LLM이라면 바로잡았을까"를 보려고 반증용으로 호출한다.
  llm_fp  : 정상인데 Rule 0점 + LLM 양성 → Hybrid 오탐
  both_fn : 스미싱인데 Rule 0점 + LLM 음성 → Hybrid 미탐 (둘 다 놓침)

기존 `evaluation/test_model_predictions.csv`는 읽기만 하고 건드리지 않는다.
LLM을 다시 부르지만 성능을 다시 재지 않으므로 Test 1회 사용 원칙과 무관하다.
(저장된 예측을 그대로 쓰고, 재호출 결과는 reason을 얻기 위한 것이다.)

temperature 0이어도 재호출 결과가 저장값과 다를 수 있으므로 둘을 같이 적고
`llm_mismatch`로 표시한다. 어긋난 건이 많으면 그 reason은 보고된 지표를 만든
판단의 설명이 아니므로, 해석할 때 주의하고 논문 한계로 적는다.

실행 (프로젝트 루트에서, Ollama 실행 중이어야 함):
    python -m evaluation.analyze_test_errors --limit 5   # 먼저 5건만 시험
    python -m evaluation.analyze_test_errors             # 전체 165건 (약 23분)

중간에 멈춰도 다시 실행하면 이어서 진행한다.
"""

import argparse
import hashlib
import json
import time
from pathlib import Path

import pandas as pd

import rule_engine.detector as rule_detector
from evaluation.evaluate_rule_thresholds import predict_score
from llm.detector import detect_with_llm
from rule_engine.detector import analyze_message


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_PATH = PROJECT_ROOT / "data" / "processed" / "test.csv"
TEST_PREDICTION_PATH = PROJECT_ROOT / "evaluation" / "test_model_predictions.csv"
OUTPUT_DIR = PROJECT_ROOT / "evaluation" / "error_analysis_test"
CASE_PATH = OUTPUT_DIR / "hybrid_error_cases.csv"
SUMMARY_PATH = OUTPUT_DIR / "hybrid_error_summary.csv"

CONFIG_PATHS = [
    TEST_PATH,
    PROJECT_ROOT / "llm" / "detector.py",
]

TEXT_COLUMNS = [
    "run_id",
    "category",
    "rule_features",
    "llm_evidence",
    "llm_reason",
    "error",
]


def make_run_id() -> str:
    """데이터와 LLM 프롬프트가 바뀌면 이어받기를 거부하도록 해시를 만든다."""

    hasher = hashlib.sha256()
    for path in CONFIG_PATHS:
        hasher.update(path.read_bytes())
    return hasher.hexdigest()


def detected_features(text: str) -> str:
    analysis = analyze_message(text)
    return ",".join(
        feature for feature, result in analysis.items() if result["detected"]
    )


def save(cases: pd.DataFrame) -> None:
    temp_path = CASE_PATH.with_suffix(".tmp")
    cases.to_csv(temp_path, index=False, encoding="utf-8-sig")
    temp_path.replace(CASE_PATH)


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


def build_cases() -> pd.DataFrame:
    """저장된 Test 예측에서 Hybrid 오류 사례만 뽑는다."""

    test = pd.read_csv(TEST_PATH)
    stored = pd.read_csv(TEST_PREDICTION_PATH)

    if len(test) != len(stored):
        raise ValueError(
            f"행 수 불일치: test={len(test)}, predictions={len(stored)}"
        )

    test.insert(0, "row_index", range(len(test)))
    for column in ("rule_prediction", "llm_prediction", "hybrid_prediction"):
        test[column] = stored[column].values

    # 이 분석은 저장된 1차 평가 예측을 설명하는 것이므로, 그때와 같은 Rule 설정
    # (난독화 옵션 꺼짐)으로 고정한다. detector의 기본값이 바뀌어도 영향받지 않는다.
    for flag in (
        "USE_HANGUL_DOMAIN",
        "USE_SHORTENER_HOSTS",
        "USE_TLD_VARIANTS",
        "USE_GENERAL_TLD",
        "USE_GENERAL_TLD_STRICT",
    ):
        setattr(rule_detector, flag, False)

    # Rule 설정이 Test 예측을 바꾸지 않았는지 다시 확인한다.
    # (run_id 해시보다 강한 검사: 지금 코드로 다시 계산해 저장값과 맞춰 본다)
    test["rule_score"] = test["content"].apply(predict_score)
    recomputed = test["rule_score"].ge(1).astype(int)
    changed = int((recomputed != test["rule_prediction"].astype(int)).sum())
    if changed:
        raise ValueError(
            f"현재 Rule 설정이 저장된 Test 예측과 {changed}건 다릅니다. "
            "Test를 재평가해야 하므로 이 분석을 그대로 쓸 수 없습니다."
        )
    print(f"Rule 예측 재계산 일치 확인: {len(test)}건 전부 동일")

    label = test["label"].astype(int)
    rule = test["rule_prediction"].astype(int)
    llm = test["llm_prediction"].astype(int)
    hybrid = test["hybrid_prediction"].astype(int)

    category = pd.Series("", index=test.index, dtype=object)
    category[(label == 0) & (hybrid == 1) & (rule == 1)] = "rule_fp"
    category[(label == 0) & (hybrid == 1) & (rule == 0)] = "llm_fp"
    category[(label == 1) & (hybrid == 0)] = "both_fn"

    rescued = int(((label == 1) & (rule == 0) & (llm == 1)).sum())
    print(f"참고: LLM이 Rule 미탐에서 건진 성공 사례 {rescued}건 (분석 대상 아님)")

    errors = test[category != ""].copy()
    errors["category"] = category[category != ""]
    errors["rule_features"] = errors["content"].apply(detected_features)
    errors["llm_prediction_stored"] = errors["llm_prediction"]
    errors["llm_prediction_rerun"] = float("nan")
    errors["llm_mismatch"] = ""
    errors["llm_evidence"] = ""
    errors["llm_reason"] = ""
    errors["llm_seconds"] = 0.0
    errors["error"] = ""
    errors["run_id"] = make_run_id()

    columns = [
        "row_index",
        "run_id",
        "category",
        "content",
        "label",
        "rule_score",
        "rule_features",
        "rule_prediction",
        "llm_prediction_stored",
        "llm_prediction_rerun",
        "llm_mismatch",
        "hybrid_prediction",
        "llm_evidence",
        "llm_reason",
        "llm_seconds",
        "error",
    ]
    return errors[columns].reset_index(drop=True)


def summarize(cases: pd.DataFrame) -> pd.DataFrame:
    rows = []
    groups = [("전체", cases)] + list(cases.groupby("category"))
    for name, part in groups:
        done = part["llm_prediction_rerun"].isin([0, 1])
        rows.append(
            {
                "category": name,
                "count": len(part),
                "llm_done": int(done.sum()),
                "llm_failed": int((part["llm_prediction_rerun"] == -1).sum()),
                "mismatch": int((part["llm_mismatch"] == "Y").sum()),
                "mean_rule_score": part["rule_score"].mean(),
                "rule_score_0": int((part["rule_score"] == 0).sum()),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="이번 실행에서 호출할 최대 건수 (0이면 전체). 먼저 몇 건만 시험할 때 쓴다.",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = make_run_id()

    if CASE_PATH.exists():
        cases = pd.read_csv(CASE_PATH, dtype={c: str for c in TEXT_COLUMNS})
        cases[TEXT_COLUMNS] = cases[TEXT_COLUMNS].fillna("")
        if not cases["run_id"].astype(str).eq(run_id).all():
            raise ValueError(
                "데이터 또는 LLM 프롬프트가 바뀌었습니다. "
                f"{CASE_PATH} 를 다른 이름으로 보관한 뒤 다시 실행하세요."
            )
        print(f"이어받기: {CASE_PATH}")
    else:
        cases = build_cases()
        save(cases)

    print(f"\nHybrid 오류 {len(cases)}건")
    print(cases["category"].value_counts().to_string())

    pending = cases.index[cases["llm_prediction_rerun"].isna()].tolist()
    if args.limit:
        pending = pending[: args.limit]
    print(f"\nLLM 호출 대상(남은 건수): {len(pending)}건")
    if pending:
        print(f"예상 소요: 약 {len(pending) * 8.4 / 60:.0f}분")

    for position, index in enumerate(pending, start=1):
        started = time.perf_counter()
        label, evidence, reason, error = run_llm(cases.at[index, "content"])
        cases.at[index, "llm_seconds"] = time.perf_counter() - started
        cases.at[index, "llm_prediction_rerun"] = label
        cases.at[index, "llm_evidence"] = evidence
        cases.at[index, "llm_reason"] = reason
        cases.at[index, "error"] = error

        stored = cases.at[index, "llm_prediction_stored"]
        if label in (0, 1) and pd.notna(stored):
            cases.at[index, "llm_mismatch"] = "Y" if int(stored) != label else "N"

        save(cases)

        if position == 1 or position % 20 == 0 or position == len(pending):
            print(f"{position}/{len(pending)} 처리", flush=True)

    summary = summarize(cases)
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")

    print("\n=== Hybrid 오류 요약 ===")
    print(summary.round(3).to_string(index=False))

    remaining = int(cases["llm_prediction_rerun"].isna().sum())
    mismatch = int((cases["llm_mismatch"] == "Y").sum())
    done = int(cases["llm_prediction_rerun"].isin([0, 1]).sum())
    if remaining:
        print(f"\n남은 건수: {remaining}건 (다시 실행하면 이어서 진행)")
    if mismatch:
        print(
            f"\n⚠ 재호출 결과가 저장값과 다른 건: {mismatch}/{done}건. "
            "해당 reason은 보고된 지표를 만든 판단의 설명이 아니므로 주의."
        )
    elif done:
        print(f"\n재호출 결과가 저장값과 모두 일치 ({done}건) → reason을 그대로 쓸 수 있다.")

    print(f"\n사례: {CASE_PATH}")
    print(f"요약: {SUMMARY_PATH}")
    print(
        "\n다음: CSV의 category별로 content와 llm_reason을 읽고 유형을 나눈다.\n"
        "  both_fn  → Rule이 왜 0점인가 (신호 없는 문자의 유형)\n"
        "  llm_fp   → LLM이 무엇을 피싱 신호로 오해했나\n"
        "  rule_fp  → 어떤 규칙이 걸렸나 (rule_features) / LLM이 바로잡았나 (llm_prediction_rerun)"
    )


if __name__ == "__main__":
    main()
