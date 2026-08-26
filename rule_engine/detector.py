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

def detect_url(text: str) -> dict:
    """메시지에 URL 또는 도메인이 포함되어 있는지 탐지한다."""

    matches = URL_PATTERN.findall(text)

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

def analyze_message(text: str) -> dict:
    """메시지에서 Rule Engine의 주요 특징을 한 번에 분석한다."""

    return {
        "url": detect_url(text),
        "urgency": detect_urgency(text),
        "personal_info": detect_personal_info_request(text),
        "financial": detect_financial(text),
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
        "고객님의 계좌가 정지되었습니다. 즉시 확인하세요.",
        "본인인증을 위해 인증번호를 입력해주세요.",
        "계좌번호와 비밀번호를 보내주세요.",
        "카드 결제가 정상적으로 승인되었습니다.",
        "미납요금을 즉시 입금해주세요.",
    ]

    for message in test_messages:
        analysis = analyze_message(message)
        score = calculate_score(analysis)

        print("메시지:", message)
        print("분석 결과:", analysis)
        print("위험 점수:", score)
        print("-" * 50)