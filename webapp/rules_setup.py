"""웹앱이 쓰는 Rule 설정을 한곳에서 고정한다.

CLAUDE.md의 확정 사항을 그대로 따른다 (2026-10-29 확정, `enum+general`):
  - 택배사 공식 도메인 allowlist
  - "접수제한"의 "제한"은 긴급성에서 제외
  - 난독화 대응: 한글 도메인 + 스킴 없는 단축 URL + TLD 표기 변형 + 일반화 TLD
  - 일반화 TLD의 '경로 필수' 변형(STRICT)은 쓰지 않는다

`detector.py`의 기본값도 현재 같은 설정이지만, 웹앱이 기본값 변경에 휩쓸리지
않도록 여기서 명시적으로 켠다. 탐지 로직은 새로 만들지 않고 기존 함수를 그대로
불러서 쓴다.
"""

import rule_engine.detector as rule_detector


FINAL_FLAGS = {
    "USE_DOMAIN_ALLOWLIST": True,
    "USE_URGENCY_CONTEXT": True,
    "USE_HANGUL_DOMAIN": True,
    "USE_SHORTENER_HOSTS": True,
    "USE_TLD_VARIANTS": True,
    "USE_GENERAL_TLD": True,
    "USE_GENERAL_TLD_STRICT": False,
}


def apply_final_config() -> None:
    """최종 Rule 설정을 적용한다. 앱이 올라올 때 한 번 호출한다."""

    for flag, value in FINAL_FLAGS.items():
        setattr(rule_detector, flag, value)
