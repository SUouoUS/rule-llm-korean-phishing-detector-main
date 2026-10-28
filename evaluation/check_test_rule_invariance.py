"""Rule 개선(both)이 Test 예측을 바꾸는지 확인한다. **Test 라벨은 읽지 않는다.**

Rule 점수는 메시지 본문만 보고 계산되므로, base와 both의 점수가 모든 메시지에서
같다면 Rule 예측도 Hybrid 예측도 같다. 그러면 기존 Test 결과
(evaluation/test_model_predictions.csv)와 McNemar 검정을 그대로 쓸 수 있고,
Test를 다시 "평가"하지 않아도 된다.

성능을 측정하지 않으므로(라벨 미사용) Test 1회 사용 원칙을 깨지 않는다.

실행 (프로젝트 루트):
    python -m evaluation.check_test_rule_invariance
"""

from pathlib import Path

import pandas as pd

import rule_engine.detector as rule_detector
from evaluation.evaluate_rule_thresholds import predict_score


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_PATH = PROJECT_ROOT / "data" / "processed" / "test.csv"
OUTPUT_PATH = PROJECT_ROOT / "evaluation" / "test_rule_invariance_changed.csv"


def set_config(allowlist: bool, context: bool) -> None:
    rule_detector.USE_DOMAIN_ALLOWLIST = allowlist
    rule_detector.USE_URGENCY_CONTEXT = context


URGENCY_CONTEXT_RE = r"접수\s?제한"


def main():
    # 라벨을 아예 메모리에 올리지 않는다 (BOM이 붙어도 content만 고른다).
    test = pd.read_csv(
        TEST_PATH, usecols=lambda col: col.strip().lstrip("﻿") == "content"
    )
    print(f"Test {len(test)}건 (라벨 미사용)")

    set_config(False, False)
    base = test["content"].apply(predict_score)

    set_config(True, True)
    both = test["content"].apply(predict_score)

    set_config(False, False)

    changed = base != both
    flipped = (base >= 1) != (both >= 1)

    official = int(test["content"].apply(_has_official).sum())
    context = int(test["content"].str.contains(URGENCY_CONTEXT_RE, regex=True).sum())
    print(f"\n공식 도메인 URL 포함: {official}건")
    print(f'"접수제한" 포함: {context}건')
    print(f"\nRule 점수가 바뀐 메시지: {int(changed.sum())}건")
    print(f"Rule 예측(>=1)이 바뀐 메시지: {int(flipped.sum())}건")

    if not flipped.any():
        print(
            "\n→ Test 예측이 전혀 바뀌지 않는다. 기존 test_model_predictions.csv와\n"
            "  McNemar 결과를 그대로 쓸 수 있고, Test 재평가는 필요하지 않다."
        )
        return

    print(
        "\n→ 예측이 바뀌는 메시지가 있다. Test를 한 번 재평가해야 한다.\n"
        "  (기존 test_model_predictions.csv를 다른 이름으로 보관한 뒤 실행)"
    )
    out = pd.DataFrame(
        {
            "row_index": test.index[flipped],
            "content": test.loc[flipped, "content"],
            "base_score": base[flipped],
            "both_score": both[flipped],
        }
    )
    out.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    print(f"  바뀐 메시지 저장: {OUTPUT_PATH}")


def _has_official(text: str) -> bool:
    return any(
        rule_detector.is_official_domain(match)
        for match in rule_detector.URL_PATTERN.findall(text)
    )


if __name__ == "__main__":
    main()
