"""Rule이 찾은 신호를 쉬운 말로 바꾸고, 원문에서 걸린 위치를 계산한다.

원칙 (CLAUDE.md "쓰지 말 것" 참고)
  - 근거는 Rule이 실제로 찾은 matches만 쓴다.
  - LLM의 reason/evidence는 설명에 쓰지 않는다. 프롬프트의 신호 목록을 그대로
    복창하는 경향이 있어 근거로 믿을 수 없다 (Test 오류 분석에서 확인).
  - 문구는 존댓말, 한 문장에 한 가지, 영어·전문용어 금지
    (URL → 인터넷 주소, 스미싱 → 문자 사기).
"""

import re

from rule_engine.detector import analyze_message


# 화면에 보여 줄 순서. (키, 짧은 이름, 찾았을 때 제목, 쉬운 설명)
SIGNALS = [
    (
        "url",
        "인터넷 주소",
        "모르는 인터넷 주소가 들어 있어요",
        "주소를 누르지 마세요. 누르면 휴대폰에 나쁜 프로그램이 깔릴 수 있어요.",
    ),
    (
        "urgency",
        "서두르게 만드는 말",
        "서두르게 만드는 말이 있어요",
        "급하게 만들어서 생각할 틈을 주지 않으려는 방법이에요. 천천히 확인하세요.",
    ),
    (
        "personal_info",
        "개인정보 요구",
        "개인정보를 물어봐요",
        "주민등록번호, 비밀번호, 인증번호는 문자로 알려 주면 안 돼요.",
    ),
    (
        "financial",
        "돈·결제에 관한 말",
        "돈이나 결제에 관한 말이 있어요",
        "돈을 보내라고 하면 먼저 가족이나 은행에 직접 물어보세요.",
    ),
    (
        "contact",
        "다른 앱으로 유도",
        "다른 앱으로 오라고 해요",
        "문자 대신 다른 앱으로 부르는 것은 흔한 사기 방법이에요.",
    ),
    (
        "reward",
        "공짜 선물·쿠폰",
        "공짜 선물로 끌어들여요",
        "공짜로 준다는 문자는 조심하세요. 받으려다 돈을 잃을 수 있어요.",
    ),
    (
        "gambling",
        "도박 사이트 유도",
        "도박 사이트로 끌어들여요",
        "도박 사이트는 불법일 수 있어요. 들어가지 마세요.",
    ),
]

DOT_REPLACEMENTS = ("쩜", "점", "닷")
HANGUL = re.compile(r"[가-힣]")
# 한글도 아니고 평범한 영문·숫자·기호도 아닌 글자 (ⓒ ℂ ô 。 ◘ 등)
ODD_CHAR = re.compile(r"[^\x00-\x7F가-힣]")

# 난독화는 URL 탐지 안에서 처리되므로 그냥 두면 "인터넷 주소"로만 보인다.
# 두 가지를 따로 설명해서 왜 수상한지 알 수 있게 한다.
TLD_VARIANT_TITLE = "'.com'을 이상하게 바꿔 썼어요"
TLD_VARIANT_BODY = (
    "'쩜컴'이나 'ⓒom'처럼 바꿔 썼어요. 검사를 피하려고 일부러 그렇게 쓴 거예요."
)
HANGUL_DOMAIN_TITLE = "주소 이름에 한글이 섞여 있어요"
HANGUL_DOMAIN_BODY = (
    "'심바.COM'처럼 한글을 섞은 주소예요. 도박이나 사기 사이트가 자주 쓰는 방식이에요."
)

CAUTION_ONLY_BODY = "특정 표현은 없지만 문맥상 의심스러워요."


def _odd_url_kind(match: str) -> str | None:
    """인터넷 주소가 어떤 식으로 바꿔 쓴 것인지 가린다."""

    if any(token in match for token in DOT_REPLACEMENTS) or ODD_CHAR.search(match):
        return "tld_variant"
    if HANGUL.search(match):
        return "hangul_domain"
    return None


def _spans_for(text: str, needles: list) -> list:
    """원문에서 걸린 표현의 위치를 모두 찾는다 (형광펜 표시용)."""

    spans = []
    for needle in needles:
        needle = str(needle).strip()
        if not needle:
            continue
        for found in re.finditer(re.escape(needle), text):
            spans.append((found.start(), found.end()))
    return spans


def _merge(spans: list) -> list:
    """겹치거나 맞닿은 구간을 합친다."""

    if not spans:
        return []
    spans = sorted(spans)
    merged = [list(spans[0])]
    for start, end in spans[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def _segments(text: str, spans: list) -> list:
    """원문을 '표시할 조각 / 그냥 조각'으로 쪼갠다.

    위치 번호를 그대로 넘기면 파이썬은 글자 단위, 자바스크립트는 UTF-16 단위로 세어
    이모지가 섞인 문자에서 표시가 밀린다. 쪼개서 넘기면 그 문제가 생기지 않는다.
    """

    pieces, cursor = [], 0
    for start, end in spans:
        if start > cursor:
            pieces.append({"text": text[cursor:start], "mark": False})
        pieces.append({"text": text[start:end], "mark": True})
        cursor = end
    if cursor < len(text):
        pieces.append({"text": text[cursor:], "mark": False})
    return pieces or [{"text": text, "mark": False}]


def inspect(text: str, extra_spans: list | None = None) -> dict:
    """Rule 분석 결과를 화면에 쓸 형태로 바꾼다.

    `extra_spans`는 Rule이 찾은 것 외에 형광펜을 칠할 구간이다. 사진에서 읽은
    글자의 '깨진 주소' 줄을 표시하는 데 쓴다 (webapp/url_hints.py).
    """

    analysis = analyze_message(text)

    checks, reasons, needles = [], [], []
    for key, short_name, title, body in SIGNALS:
        result = analysis[key]
        found = bool(result["detected"])
        matches = [str(m) for m in result["matches"]] if found else []

        checks.append(
            {
                "key": key,
                "name": short_name,
                "found": found,
                # "found" / "none" / "unsure" — unsure 는 사진에서 주소를 못 읽은 경우로,
                # webapp/main.py 가 따로 표시한다.
                "state": "found" if found else "none",
                "matches": matches,
            }
        )
        if found:
            reasons.append({"key": key, "title": title, "body": body, "matches": matches})
            needles.extend(matches)

    # 바꿔 쓴 주소는 종류를 나눠 한 번 더 설명한다.
    odd = {"tld_variant": [], "hangul_domain": []}
    for match in analysis["url"]["matches"]:
        kind = _odd_url_kind(str(match))
        if kind:
            odd[kind].append(str(match))

    if odd["tld_variant"]:
        reasons.append(
            {
                "key": "tld_variant",
                "title": TLD_VARIANT_TITLE,
                "body": TLD_VARIANT_BODY,
                "matches": odd["tld_variant"],
            }
        )
    if odd["hangul_domain"]:
        reasons.append(
            {
                "key": "hangul_domain",
                "title": HANGUL_DOMAIN_TITLE,
                "body": HANGUL_DOMAIN_BODY,
                "matches": odd["hangul_domain"],
            }
        )

    spans = _merge(_spans_for(text, needles) + list(extra_spans or []))
    return {
        "checks": checks,
        "reasons": reasons,
        "segments": _segments(text, spans),
    }
