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

# 위험 신호 검사 목록에서 '인터넷 주소' 줄에 쓸 말.
# 규칙은 주소를 못 잡았지만 머리말은 보였으므로 "없음"도 "찾음"도 아니다.
CHECK_UNSURE_LABEL = "있는 것 같음 (정확히 못 읽음)"

EDIT_NOTICE = "이 부분은 인터넷 주소 같아요. 사진과 다르면 고쳐 주세요."

# 결과 화면에서 '주의'가 된 이유. 같은 말을 여러 곳에서 되풀이하지 않도록
# 설명은 이 한 덩어리에만 둔다 ('왜 위험한지' 목록에는 따로 넣지 않는다).
RESULT_NOTICE = (
    "사진 속 주소를 읽지 못해서 진짜인지 확인할 수 없었어요. "
    "주소를 누르지 말고, 문자를 보낸 곳의 공식 앱이나 고객센터로 직접 확인하세요."
)


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


def suspect_spans(text: str) -> list:
    """주소처럼 보이는 줄의 글자 위치 (시작, 끝)를 돌려준다.

    결과 화면에서 원문에 형광펜을 칠할 때 쓴다.
    """

    spans, position = [], 0
    for line in (text or "").split("\n"):
        if URL_HEAD.search(line):
            spans.append((position, position + len(line)))
        position += len(line) + 1  # 줄바꿈 한 글자
    return spans


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
