"""캡처 이미지에서 한국어 글자를 읽는다 (EasyOCR).

EasyOCR을 고른 이유
  - `pip install easyocr` 한 줄로 끝나고, 따로 설치할 런타임이 없다.
  - 한국어는 `Reader(["ko", "en"])` 한 줄로 지정되고 모델을 자동으로 받아 온다.
  - PaddleOCR 3.x도 py3.13 Windows 휠이 있지만 `paddlepaddle`을 따로 깔아야 하고
    파이프라인 설정이 더 복잡하다. 설치 가능성이 같으면 단순한 쪽을 쓴다.

torch를 함께 받아 오므로 용량이 크다(모델까지 약 350MB). 그래서 **지연 로딩**한다.
이미지를 올릴 때 처음 한 번만 불러오고, 설치돼 있지 않으면 텍스트 기능만으로
앱이 정상 동작한다.

읽은 글자는 메모리에서만 다루고 파일로 저장하지 않는다.
"""

import io
import threading


LANGUAGES = ["ko", "en"]

# 글자로 보기 어려운 결과는 버린다. 사용자가 고칠 수 있으므로 너무 엄격히 하지 않는다.
MIN_CONFIDENCE = 0.3

_reader = None
_lock = threading.Lock()


class OcrUnavailable(RuntimeError):
    """EasyOCR이 설치되지 않았거나 불러올 수 없을 때."""


def is_available() -> bool:
    """설치 여부만 확인한다 (모델은 불러오지 않는다)."""

    try:
        import importlib.util

        return importlib.util.find_spec("easyocr") is not None
    except Exception:
        return False


def _get_reader():
    """EasyOCR 모델을 처음 쓸 때 한 번만 불러온다."""

    global _reader
    with _lock:
        if _reader is None:
            try:
                import easyocr
            except Exception as error:  # 설치 안 됨, 또는 torch 문제
                raise OcrUnavailable(str(error)) from error
            # gpu=False: 그래픽카드가 없어도 돌아가게 한다.
            _reader = easyocr.Reader(LANGUAGES, gpu=False, verbose=False)
    return _reader


def read_image(data: bytes) -> dict:
    """이미지 바이트에서 글자를 읽어 하나의 문자열로 돌려준다."""

    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            rgb = image.convert("RGB")
    except UnidentifiedImageError as error:
        raise ValueError("이미지 파일을 열지 못했습니다.") from error

    import numpy as np

    reader = _get_reader()
    results = reader.readtext(np.array(rgb))

    lines, scores = [], []
    for _box, raw_text, confidence in results:
        text = str(raw_text).strip()
        if text and confidence >= MIN_CONFIDENCE:
            lines.append(text)
            scores.append(float(confidence))

    return {
        "text": "\n".join(lines),
        "line_count": len(lines),
        "mean_confidence": sum(scores) / len(scores) if scores else 0.0,
    }
