"""사진에서 읽은 글자에 '깨진 인터넷 주소'가 있는지 살핀다. 웹앱 전용이다.

왜 필요한가
  OCR은 주소를 자주 깨뜨린다. 예를 들어
      https://smilehanjin.com/n/hhh.htm?a=
  가 "https llsmilehaniin comlnlhhhtm?a=" 처럼 읽힌다. 이렇게 되면 탐지 엔진의
  주소 규칙이 걸리지 않는다. 노약자가 확인 화면에서 이걸 알아채고 고치기는 어렵다.
  그래서 "https / http / www 글자가 보이면 뒤가 깨져 있어도 주소로 의심"한다.

적용 범위 (중요)
  **사진으로 넣은 글자에만** 쓴다. 직접 붙여 넣은 글자에는 쓰지 않는다.
  `rule_engine`, `hybrid`, 평가 코드는 건드리지 않는다. 평가에 쓴 데이터는 모두
  글자 입력이었으므로, 사진 입력에만 붙는 이 보정은 평가 결과와 무관하다.

판정에 어떻게 반영하나
  주소를 '찾았다'고 단정하지 않는다. OCR이 깨뜨린 주소는 정상 문자의 것일 수도 있고
  (택배 알림 사진이 그렇다) 그때는 공식 도메인 허용이 동작할 수 없기 때문이다.
  그래서 '위험'으로 올리지 않고, 결과가 '위험 신호 없음'일 때만 '주의'로 올린다.
"""

import re


# 주소의 머리말. 뒤가 아무리 깨져도 이 글자는 비교적 잘 읽힌다.
URL_HEAD = re.compile(r"(?:https?\s*[:：]?\s*/*|www\s*[.．]?)", re.IGNORECASE)

HINT_TITLE = "인터넷 주소가 있는 것 같아요"
HINT_BODY = (
    "사진에서 주소를 정확히 읽지 못했어요. 주소처럼 보이는 글자가 있으니 누르지 마세요."
)
EDIT_NOTICE = "이 부분은 인터넷 주소 같아요. 사진과 다르면 고쳐 주세요."
RESULT_NOTICE = "사진에서 주소를 정확히 읽지 못했어요. 글자가 원래 문자와 같은지 확인해 주세요."


def has_broken_url(text: str) -> bool:
    """https / http / www 가 보이면 뒤가 깨져 있어도 주소로 의심한다."""

    return bool(URL_HEAD.search(text or ""))


def suspect_lines(text: str) -> list:
    """주소처럼 보이는 줄의 번호(0부터)를 돌려준다."""

    return [
        index
        for index, line in enumerate((text or "").split("\n"))
        if URL_HEAD.search(line)
    ]


def line_segments(text: str) -> list:
    """줄 단위로 '표시할 조각 / 그냥 조각'을 만든다 (확인 화면 형광펜용)."""

    lines = (text or "").split("\n")
    marked = set(suspect_lines(text))

    pieces = []
    for index, line in enumerate(lines):
        if index:
            pieces.append({"text": "\n", "mark": False})
        pieces.append({"text": line, "mark": index in marked})
    return pieces


def hint_reason() -> dict:
    """결과 화면에 덧붙일 설명 한 덩어리."""

    return {"key": "broken_url", "title": HINT_TITLE, "body": HINT_BODY, "matches": []}
