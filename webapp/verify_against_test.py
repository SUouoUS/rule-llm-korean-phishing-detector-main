"""웹앱이 평가한 시스템과 똑같이 판정하는지 확인한다.

웹앱의 Rule 설정(`webapp/rules_setup.py`)으로 Test 2,383건을 돌려서, Test 최종
평가의 final 설정 결과와 숫자가 같은지 맞춰 본다. LLM은 쓰지 않으므로 몇 초면
끝난다.

같다면 보고서에 "웹앱은 평가한 시스템과 같은 판정을 한다"고 쓸 수 있다.
다르면 웹앱 설정이 어긋난 것이므로 `rules_setup.py`를 고쳐야 한다.

실행 (프로젝트 루트):
    python -m webapp.verify_against_test
"""

from pathlib import Path

import pandas as pd

from evaluation.evaluate_rule_thresholds import predict_score
from hybrid.detector import RULE_THRESHOLD
from webapp.rules_setup import FINAL_FLAGS, apply_final_config


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_PATH = PROJECT_ROOT / "data" / "processed" / "test.csv"

# evaluation/test_final/comparison.csv 의 final / Rule 행 (2026-10-29)
EXPECTED = {"fn": 70, "fp": 12, "tp": 1010, "tn": 1291}


def main() -> None:
    apply_final_config()
    print("웹앱 Rule 설정:")
    for flag, value in FINAL_FLAGS.items():
        print(f"  {flag:24s} {value}")

    test = pd.read_csv(TEST_PATH)
    label = test["label"].astype(int)
    pred = test["content"].apply(predict_score).ge(RULE_THRESHOLD).astype(int)

    got = {
        "tp": int(((pred == 1) & (label == 1)).sum()),
        "fp": int(((pred == 1) & (label == 0)).sum()),
        "fn": int(((pred == 0) & (label == 1)).sum()),
        "tn": int(((pred == 0) & (label == 0)).sum()),
    }

    print(f"\nTest {len(test)}건으로 웹앱 Rule 판정:")
    print(f"{'':6s} {'웹앱':>6s} {'평가 결과':>9s}")
    mismatched = []
    for key in ("tp", "fp", "fn", "tn"):
        same = got[key] == EXPECTED[key]
        print(f"  {key:4s} {got[key]:6d} {EXPECTED[key]:9d}   {'같음' if same else '다름'}")
        if not same:
            mismatched.append(key)

    if mismatched:
        raise SystemExit(
            "\n웹앱 판정이 평가 결과와 다릅니다: "
            + ", ".join(mismatched)
            + "\nwebapp/rules_setup.py 의 설정을 확인하세요."
        )

    print(
        "\n웹앱은 평가한 시스템(final 설정)과 똑같이 판정합니다.\n"
        "  놓친 스미싱 70건, 정상 문자 오탐 12건 — 숫자가 모두 일치."
    )


if __name__ == "__main__":
    main()
