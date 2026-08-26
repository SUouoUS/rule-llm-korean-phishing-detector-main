import re


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

    return {
        "detected": bool(matches),
        "matches": matches,
    }


def detect_urgency(text: str) -> dict:
    """메시지에서 긴급성 또는 즉각적인 행동을 유도하는 표현을 탐지한다."""

    matches = [
        keyword
        for keyword in URGENCY_KEYWORDS
        if keyword in text
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