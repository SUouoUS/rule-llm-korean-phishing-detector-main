"""Rule 개선 옵션이 공격을 놓치지 않는지 확인한다 (추가 패키지 없이 실행).

주 데이터셋(train/val)에는 택배사 공식 도메인과 "접수제한" 표현이 한 건도 없어서,
Validation 지표는 이 옵션들의 안전성에 대해 아무 증거를 주지 못한다.
그래서 안전성은 데이터가 아니라 아래 동작 명세로 보인다.

실행 (프로젝트 루트):
    python -m tests.test_rule_options
"""

import rule_engine.detector as d


# (메시지, URL 신호가 남아야 하는가)
URL_CASES = [
    # 공식 도메인은 제외된다
    ("https://coupang.com/photo1", False),
    ("https://www.coupang.com/orders", False),
    ("hanjin.co.kr/track", False),
    ("https://m.hanjin.com/kor/Main.do", False),
    # 공식 도메인을 흉내 낸 주소는 그대로 탐지된다
    ("https://coupang.com.evil.xyz/login", True),
    ("https://notcoupang.com/login", True),
    ("https://coupang-com.xyz/login", True),
    ("https://evil.com/coupang.com", True),
    # 공식 도메인과 악성 주소가 섞이면 악성만 남는다
    ("[쿠팡] 배송 확인 https://coupang.com/a 지금 http://evil.kr/login", True),
]

# (메시지, 남아야 하는 긴급성 키워드)
URGENCY_CASES = [
    # 안내 문구의 "접수제한"은 긴급성이 아니다
    ("부피초과 상품은 접수제한되오니 양해 바랍니다", []),
    ("접수 제한 상품입니다", []),
    # 그 밖의 "제한"과 다른 긴급성 표현은 그대로 남는다
    ("계정 이용이 제한됩니다", ["제한"]),
    ("접수제한 안내 / 오늘까지 즉시 확인", ["즉시", "오늘까지"]),
]


def main():
    d.USE_DOMAIN_ALLOWLIST = True
    d.USE_URGENCY_CONTEXT = True

    failures = []

    for text, expected in URL_CASES:
        actual = d.detect_url(text)["detected"]
        ok = actual == expected
        print(f"{'OK  ' if ok else 'FAIL'} url={actual!s:5} (기대 {expected!s:5}) {text}")
        if not ok:
            failures.append(text)

    print()

    for text, expected in URGENCY_CASES:
        actual = d.detect_urgency(text)["matches"]
        ok = sorted(actual) == sorted(expected)
        print(f"{'OK  ' if ok else 'FAIL'} urgency={actual} (기대 {expected}) {text}")
        if not ok:
            failures.append(text)

    d.USE_DOMAIN_ALLOWLIST = False
    d.USE_URGENCY_CONTEXT = False

    print()
    if failures:
        raise SystemExit(f"{len(failures)}건 실패")
    print(f"전체 {len(URL_CASES) + len(URGENCY_CASES)}건 통과")


if __name__ == "__main__":
    main()
