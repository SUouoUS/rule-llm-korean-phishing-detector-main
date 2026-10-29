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


# 난독화 대응 옵션 (USE_HANGUL_DOMAIN / USE_SHORTENER_HOSTS / USE_TLD_VARIANTS)
# 표기는 Train 미탐에서 가져왔다. Test 사례는 쓰지 않는다.
OBFUSCATION_CASES = [
    # 한글이 섞인 도메인 이름
    ("심바.COM", True),
    ("순천나이키.net", True),
    ("미선나라.com", True),
    # 스킴 없는 단축 URL
    ("bit.ly/2UlmZmu", True),
    ("cutt.ly/7huUroD", True),
    # TLD 표기 변형: 글자 변형과 점 대체
    ("종료벳세이프.ⓒom", True),
    ("zag***◘ℂℴℳ", True),
    ("실뱃쩜컴", True),
    ("betend쩜net", True),
    ("dpm-ko[쩜]com", True),
    ("*** 。com", True),
    # 일반 단어를 도메인으로 오인하지 않는다 (컴/콤/넷으로 시작하는 한국어)
    ("오늘 샀어. 컴퓨터 좋네", False),
    ("아이스 아메리카노. 콤비네이션 피자도", False),
    ("주말에 넷플릭스 봤어", False),
    ("회의는 3시. 컴백 일정 알려줘", False),
    ("그 가게 장점은 커피", False),
    ("내 컴퓨터 고장났어", False),
    ("닷지 차 좋더라", False),
    ("점심 뭐 먹지", False),
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

    print()

    d.USE_HANGUL_DOMAIN = True
    d.USE_SHORTENER_HOSTS = True
    d.USE_TLD_VARIANTS = True

    for text, expected in OBFUSCATION_CASES:
        actual = d.detect_url(text)["detected"]
        ok = actual == expected
        print(f"{'OK  ' if ok else 'FAIL'} obf={actual!s:5} (기대 {expected!s:5}) {text}")
        if not ok:
            failures.append(text)

    d.USE_DOMAIN_ALLOWLIST = False
    d.USE_URGENCY_CONTEXT = False
    d.USE_HANGUL_DOMAIN = False
    d.USE_SHORTENER_HOSTS = False
    d.USE_TLD_VARIANTS = False

    total = len(URL_CASES) + len(URGENCY_CASES) + len(OBFUSCATION_CASES)
    print()
    if failures:
        raise SystemExit(f"{len(failures)}/{total}건 실패")
    print(f"전체 {total}건 통과")


if __name__ == "__main__":
    main()
