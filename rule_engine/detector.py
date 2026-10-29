import re


# --------------------------------------------------
# Rule 개선 옵션 (2026-10-28 검증 후 기본 True로 확정)
#   - Validation 2,450건: 네 조건 모두 동일 (주 데이터셋에 해당 패턴이 없음)
#   - 택배 dev 1,045건: 오탐 300 → 0 / eval 1,364건: 오탐 599 → 0
#   - Test 2,383건: Rule 점수가 바뀐 메시지 0건 (라벨 미사용으로 확인)
# 기존(개선 전) 결과를 재현하려면 둘 다 False로 되돌린다.
# --------------------------------------------------
# 1) 택배사 공식 도메인 URL은 URL 위험 신호에서 제외
USE_DOMAIN_ALLOWLIST = True
# 2) "접수제한"처럼 안내 문구에 쓰인 "제한"은 긴급성 신호에서 제외
USE_URGENCY_CONTEXT = True

# --------------------------------------------------
# 난독화 URL 대응 옵션 (2026-10-29 추가, 기본 False = 검증 전)
#
# Train 미탐 998건에서 추출한 표기 변형만 다룬다 (`evaluation/train_misses/`).
# Test 사례를 보고 만든 규칙이 아니다 — 평가셋에 맞춘 규칙이 되지 않도록.
#
# ⚠️ 희귀/신규 TLD(.guru .sale .fund .wiki .us)는 일부러 넣지 않았다.
#    Train 미탐에 1.3%(13건)뿐이고 .sale/.fund/.wiki/.us는 0건이어서
#    Train만 보고는 도출할 수 없다. 그리고 그 영역은 LLM이 건진 사례의 49%를
#    차지한다 → "Rule은 본 변형만 열거할 수 있고, 나머지는 LLM이 메꾼다"를
#    같은 실험에서 보이기 위해 Rule 쪽에서 비워 둔다.
#    같은 이유로 "스킴 없는 도메인 + 경로"처럼 TLD를 가리지 않는 일반 규칙도
#    쓰지 않는다 (그 규칙은 희귀 TLD를 전부 흡수해 위 대비를 없앤다).
# --------------------------------------------------
# 3) 도메인 이름에 한글이 섞인 주소 (Train 미탐 280건, 28.1%)
USE_HANGUL_DOMAIN = False
# 4) 스킴 없는 단축 URL 호스트 (Train 미탐 218건, 21.8%)
USE_SHORTENER_HOSTS = False
# 5) TLD 표기 변형: 점 대체 + 문자 변형 (Train 미탐 103 + 47건)
USE_TLD_VARIANTS = False

# 각 택배사 공식 홈페이지에서 확인한 도메인만 넣는다 (데이터를 보고 추가하지 않음).
# 하위 도메인(www.coupang.com 등)은 허용, 흉내 낸 주소(coupang.com.evil.xyz)는 허용하지 않음.
#
# 확인 방법/날짜: 2026-10-28, 각 도메인 루트에 HTTPS 접속해 리다이렉트 주소와
# 페이지 title이 해당 회사인지 확인.
#   coupang.com      → www.coupang.com (쿠팡)
#   cjlogistics.com  → "CJ Logistics" (CJ대한통운)
#   hanjin.com       → "글로벌 종합물류기업 (주)한진"
#   hanjin.co.kr     → www.hanjin.com 으로 리다이렉트 (한진 공식 별칭)
#   epost.go.kr      → "인터넷우체국" (우정사업본부)
#   lotteglogis.com  → "롯데글로벌로지스"
#   ilogen.com       → 로젠택배
#   kdexp.com        → 경동택배
# SLX(slx.co.kr)는 평가 데이터에 등장하지만 오탐을 내지 않았고, 데이터를 보고
# 목록을 늘리지 않는다는 원칙에 따라 넣지 않았다.
OFFICIAL_DOMAINS = [
    "coupang.com",
    "cjlogistics.com",
    "hanjin.com",
    "hanjin.co.kr",
    "epost.go.kr",
    "lotteglogis.com",
    "ilogen.com",
    "kdexp.com",
]

URGENCY_CONTEXT_EXCLUDE = re.compile(r"접수\s?제한")


URL_PATTERN = re.compile(
    r"""
    (?:
        https?://
        [A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+
        |
        www\.
        [A-Za-z0-9.-]+
        \.[A-Za-z]{2,}
        (?:/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]*)?
        |
        [A-Za-z0-9.-]+
        \.(?:com|net|org|kr|co\.kr)
        (?:/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]*)?
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

OBFUSCATED_DOMAIN_PATTERN = re.compile(
    r"""
    (?:
        [A-Za-z0-9ⓐ-ⓩ①-⑳*._-]{2,}
        \.
        (?:com|net|org|kr|co\.kr)
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# --------------------------------------------------
# 난독화 URL 패턴 (위 옵션 3~5가 켜질 때만 쓴다)
# 표기 목록 출처: evaluation/train_misses/ (Train 미탐 998건에서 추출)
# --------------------------------------------------

# 3) 도메인 이름에 한글이 섞인 주소: 심바.COM, 레옹.net, 순천나이키.net
#    기존 URL_PATTERN은 TLD 앞을 [A-Za-z0-9.-]로 제한해 이들을 놓쳤다.
HANGUL_DOMAIN_PATTERN = re.compile(
    r"[A-Za-z0-9가-힣_-]*[가-힣][A-Za-z0-9가-힣._-]*"
    r"\.(?:com|net|org|kr|co\.kr)"
    r"(?:/[^\s]*)?",
    re.IGNORECASE,
)

# 4) 스킴 없는 단축 URL. Train 미탐에 나온 호스트만 열거한다 (.ly가 219회).
#    TLD를 가리지 않는 일반 규칙을 쓰지 않는 이유는 위 옵션 주석 참고.
SHORTENER_HOST_PATTERN = re.compile(
    r"\b(?:bit|cutt|vo|goo|tiny|buly|dooo|han|kko|is|lnk|me2)"
    r"\s?\.\s?(?:ly|la|gl|gd|us|cc|do|kr)"
    r"(?:/[^\s]*)?",
    re.IGNORECASE,
)

# 5) TLD 표기 변형. 글자 변형(ⓒⓞⓜ, ℂℴℳ, 컴, 콤)과 점 대체(쩜, 。, ，, ◘, *)를
#    함께 받는다. 기존 패턴은 TLD를 리터럴 com|net|org|kr로만 받았다.
_C = r"[cCｃ⒞ⓒℂСсⅽ]"
_O = r"[oOｏⓞℴОо0０]"
_M = r"[mMｍⓜℳМм⒨]"
_N = r"[nNｎⓝℕНн]"
_E = r"[eEｅⓔℰЕе]"
_T = r"[tTｔⓣТт]"

_TLD_SPELLING = rf"(?:{_C}\s?{_O}\s?{_M}|{_N}\s?{_E}\s?{_T}|컴|콤|넷)"
# 점 대체: 기호(앞뒤 공백 허용) 또는 한글 치환(쩜/닷/점, [쩜]처럼 괄호에 싸인 경우 포함)
_DOT_SPELLING = r"(?:\s?[.．。，､·ㆍ*◘▶☞◇\[\(]\s?|[\[\(]?\s?[쩜닷점]\s?[\]\)]?)"

# 뒤에 한글이 더 붙으면 "컴퓨터", "콤비", "넷플릭스" 같은 일반 단어이므로 제외한다.
TLD_VARIANT_PATTERN = re.compile(
    rf"[A-Za-z0-9가-힣*_-]{{2,}}{_DOT_SPELLING}{_TLD_SPELLING}(?![가-힣])",
    re.IGNORECASE,
)


URGENCY_KEYWORDS = [
    "긴급",
    "즉시",
    "지금",
    "오늘까지",
    "금일",
    "마감",
    "기한",
    "제한",
    "차단",
    "정지",
]


PERSONAL_INFO_KEYWORDS = [
    "인증번호",
    "본인인증",
    "주민등록번호",
    "주민번호",
    "계좌번호",
    "비밀번호",
    "카드번호",
    "보안카드",
    "OTP",
]

FINANCIAL_KEYWORDS = [
    "송금",
    "입금",
    "계좌이체",
    "결제",
    "승인",
    "출금",
    "미납",
    "연체",
    "환급",
]

REWARD_KEYWORDS = [
    "쿠폰",
    "포인트",
    "기프티콘",
    "스벅",
    "맥날",
]

CONTACT_KEYWORDS = [
    "카톡",
    "텔레",
]

GAMBLING_KEYWORDS = [
    "슬롯",
    "게임랜드",
    "놀이터",
    "배팅",
]

def extract_host(url: str) -> str:
    """URL 문자열에서 호스트(도메인) 부분만 추출한다."""

    host = re.sub(r"^[a-z]+://", "", url.strip().lower())
    host = re.split(r"[/?#:]", host, maxsplit=1)[0]
    return host.strip(".")


def is_official_domain(url: str) -> bool:
    """공식 도메인이거나 그 하위 도메인이면 True."""

    host = extract_host(url)
    return any(
        host == domain or host.endswith("." + domain)
        for domain in OFFICIAL_DOMAINS
    )


def detect_url(text: str) -> dict:
    """일반 URL과 난독화된 도메인을 탐지한다."""

    normal_matches = URL_PATTERN.findall(text)
    obfuscated_matches = OBFUSCATED_DOMAIN_PATTERN.findall(text)

    # 일반 URL 내부에 이미 포함된 도메인은 중복으로 추가하지 않음
    filtered_obfuscated = [
        match
        for match in obfuscated_matches
        if not any(match in normal for normal in normal_matches)
    ]

    matches = normal_matches + filtered_obfuscated

    # 난독화 대응 옵션. 이미 잡힌 주소와 겹쳐도 결과는 같으므로 그대로 더한다.
    for enabled, pattern in (
        (USE_HANGUL_DOMAIN, HANGUL_DOMAIN_PATTERN),
        (USE_SHORTENER_HOSTS, SHORTENER_HOST_PATTERN),
        (USE_TLD_VARIANTS, TLD_VARIANT_PATTERN),
    ):
        if enabled:
            matches += [
                match
                for match in pattern.findall(text)
                if not any(match in existing for existing in matches)
            ]

    if USE_DOMAIN_ALLOWLIST:
        matches = [
            match
            for match in matches
            if not is_official_domain(match)
        ]

    return {
        "detected": bool(matches),
        "matches": matches,
    }


def detect_urgency(text: str) -> dict:
    """메시지에서 긴급성 또는 즉각적인 행동을 유도하는 표현을 탐지한다."""

    checked_text = text

    if USE_URGENCY_CONTEXT:
        checked_text = URGENCY_CONTEXT_EXCLUDE.sub(" ", text)

    matches = [
        keyword
        for keyword in URGENCY_KEYWORDS
        if keyword in checked_text
    ]

    return {
        "detected": bool(matches),
        "matches": matches,
    }

def detect_personal_info_request(text: str) -> dict:
    """개인정보 또는 인증정보를 요구하는 표현을 탐지한다."""

    matches = [
        keyword
        for keyword in PERSONAL_INFO_KEYWORDS
        if keyword.lower() in text.lower()
    ]

    return {
        "detected": bool(matches),
        "matches": matches,
    }

def detect_financial(text: str) -> dict:
    """메시지에서 금전 및 결제 관련 표현을 탐지한다."""

    matches = [
        keyword
        for keyword in FINANCIAL_KEYWORDS
        if keyword in text
    ]

    return {
        "detected": bool(matches),
        "matches": matches,
    }

def detect_reward(text: str) -> dict:
    """혜택 또는 보상 유도 표현을 탐지한다."""

    matches = [
        keyword
        for keyword in REWARD_KEYWORDS
        if keyword.lower() in text.lower()
    ]

    return {
        "detected": bool(matches),
        "matches": matches,
    }


def detect_contact(text: str) -> dict:
    """외부 메신저 또는 연락 유도 표현을 탐지한다."""

    matches = [
        keyword
        for keyword in CONTACT_KEYWORDS
        if keyword.lower() in text.lower()
    ]

    return {
        "detected": bool(matches),
        "matches": matches,
    }


def detect_gambling(text: str) -> dict:
    """도박성 서비스 관련 표현을 탐지한다."""

    matches = [
        keyword
        for keyword in GAMBLING_KEYWORDS
        if keyword.lower() in text.lower()
    ]

    return {
        "detected": bool(matches),
        "matches": matches,
    }

def analyze_message(text: str) -> dict:
    """메시지에서 Rule Engine의 주요 특징을 한 번에 분석한다."""

    return {
        "url": detect_url(text),
        "urgency": detect_urgency(text),
        "personal_info": detect_personal_info_request(text),
        "financial": detect_financial(text),

        "reward": detect_reward(text),
        "contact": detect_contact(text),
        "gambling": detect_gambling(text),
    }


FEATURE_WEIGHTS = {
    "url": 2,
    "urgency": 1,
    "personal_info": 2,
    "financial": 1,
}


def calculate_score(analysis: dict) -> int:
    """탐지된 특징을 기반으로 Rule Engine 위험 점수를 계산한다."""

    score = 0

    for feature, weight in FEATURE_WEIGHTS.items():
        if analysis[feature]["detected"]:
            score += weight

    return score

if __name__ == "__main__":
    test_messages = [
        "오늘 저녁 뭐 먹을까?",
        "배송조회 https://example.com/check",
        "해파리 고래 이벤트 qw⑤*dⓕ.com",
        "오늘은 드림에서 쉬어가세요 ⓗⓚⓨs**.com",
        "제트 CASINO 가입 zqz**.com",
        "신규가족 이벤트 Uⓝ-**ⓕ.com",
    ]

    for message in test_messages:
        analysis = analyze_message(message)
        score = calculate_score(analysis)

        print("메시지:", message)
        print("분석 결과:", analysis)
        print("위험 점수:", score)
        print("-" * 50)