"""문자 사기 확인 웹앱 — FastAPI.

탐지 로직은 새로 만들지 않고 기존 코드를 그대로 불러서 쓴다.
  - Rule 점수:   evaluation.evaluate_rule_thresholds.predict_score
  - Rule 신호:   rule_engine.detector.analyze_message  (webapp.explain 경유)
  - 임계값:      hybrid.detector.RULE_THRESHOLD
  - LLM:         llm.detector.detect_with_llm

`hybrid.detector.detect_with_hybrid`는 Rule과 LLM을 한 번에 처리하므로 쓰지 않는다.
화면을 실제 처리 순서대로 단계별로 보여 주려면 Rule 결과를 먼저 돌려주고, 필요할
때만 LLM을 호출해야 한다. 결합 규칙(점수가 임계값 이상이면 바로 위험)은 같다.

모든 처리는 이 PC에서만 한다. 외부 API를 호출하지 않고, 입력한 문자와 이미지는
메모리에서만 다루며 파일로 저장하지 않는다.

실행 (프로젝트 루트):
    python -m uvicorn webapp.main:app --reload
"""

from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from evaluation.evaluate_rule_thresholds import predict_score
from hybrid.detector import RULE_THRESHOLD
from llm.detector import detect_with_llm
from webapp import ocr
from webapp.actions import ACTIONS, action_list
from webapp.explain import CAUTION_ONLY_BODY, inspect
from webapp.rules_setup import apply_final_config
from webapp.samples import sample_list


WEBAPP_DIR = Path(__file__).resolve().parent
STATIC_DIR = WEBAPP_DIR / "static"
INDEX_PATH = WEBAPP_DIR / "templates" / "index.html"

MAX_TEXT_LENGTH = 2000
MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/bmp"}

# 결과 3단계 문구 (CLAUDE.md 확정. "안전합니다", "정상입니다"는 쓰지 않는다)
VERDICTS = {
    "danger": {
        "level": "danger",
        "icon": "danger",
        "badge": "위험",
        "headline": "사기 문자일 가능성이 매우 높아요",
    },
    "caution": {
        "level": "caution",
        "icon": "caution",
        "badge": "주의",
        "headline": "조심해야 할 문자예요",
    },
    "clear": {
        "level": "clear",
        "icon": "clear",
        "badge": "위험 신호 없음",
        "headline": "뚜렷한 위험 신호를 찾지 못했어요",
    },
}

apply_final_config()

app = FastAPI(title="문자 사기 확인", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class TextRequest(BaseModel):
    text: str = Field(default="")


def _easy_error(message: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


def _validate_text(text: str) -> str | JSONResponse:
    cleaned = (text or "").strip()
    if not cleaned:
        return _easy_error("확인할 문자를 넣어 주세요.")
    if len(cleaned) > MAX_TEXT_LENGTH:
        return _easy_error(
            f"문자가 너무 길어요. {MAX_TEXT_LENGTH}글자까지 확인할 수 있어요. "
            f"지금은 {len(cleaned)}글자예요."
        )
    return cleaned


@app.get("/")
def index() -> FileResponse:
    return FileResponse(INDEX_PATH)


@app.get("/api/meta")
def meta() -> dict:
    """화면을 그리는 데 필요한 정보. 민감한 내용은 없다."""

    return {
        "ocr_available": ocr.is_available(),
        "max_text_length": MAX_TEXT_LENGTH,
        "samples": sample_list(),
        "actions": action_list(),
        "action_details": ACTIONS,
        "rule_threshold": RULE_THRESHOLD,
    }


@app.post("/api/ocr")
async def read_image(image: UploadFile = File(...)):
    """1단계: 캡처 이미지에서 글자를 읽는다. 읽은 글자는 저장하지 않는다."""

    if not ocr.is_available():
        return _easy_error(
            "이미지에서 글자를 읽는 기능이 준비되지 않았어요. "
            "문자를 직접 붙여 넣어 확인해 주세요.",
            status=503,
        )

    if image.content_type not in ALLOWED_IMAGE_TYPES:
        return _easy_error("사진 파일(PNG, JPG)만 올릴 수 있어요.")

    data = await image.read()
    if not data:
        return _easy_error("사진이 비어 있어요. 다시 올려 주세요.")
    if len(data) > MAX_IMAGE_BYTES:
        return _easy_error("사진이 너무 커요. 5MB보다 작은 사진을 올려 주세요.")

    try:
        result = ocr.read_image(data)
    except ocr.OcrUnavailable:
        return _easy_error(
            "글자를 읽는 기능을 불러오지 못했어요. 문자를 직접 붙여 넣어 주세요.",
            status=503,
        )
    except ValueError as error:
        return _easy_error(str(error))
    except Exception:
        return _easy_error(
            "사진에서 글자를 읽지 못했어요. 문자를 직접 붙여 넣어 주세요.", status=500
        )

    if not result["text"]:
        return _easy_error(
            "사진에서 글자를 찾지 못했어요. 글자가 잘 보이게 다시 찍거나, "
            "문자를 직접 붙여 넣어 주세요."
        )

    return {
        "text": result["text"],
        "line_count": result["line_count"],
        "mean_confidence": result["mean_confidence"],
        "notice": "읽은 글자가 틀릴 수 있어요. 아래에서 고친 뒤 검사하기를 눌러 주세요.",
    }


@app.post("/api/rule")
def check_rule(request: TextRequest):
    """2단계: 위험 신호 검사. 빠르게 끝난다."""

    text = _validate_text(request.text)
    if isinstance(text, JSONResponse):
        return text

    score = predict_score(text)
    detail = inspect(text)
    needs_llm = score < RULE_THRESHOLD

    payload = {
        "text": text,
        "rule_score": score,
        "rule_positive": not needs_llm,
        "needs_llm": needs_llm,
        "checks": detail["checks"],
        "reasons": detail["reasons"],
        "segments": detail["segments"],
    }
    if not needs_llm:
        payload["verdict"] = VERDICTS["danger"]
    return payload


@app.post("/api/llm")
def check_llm(request: TextRequest):
    """3단계: Rule이 아무 신호도 못 찾았을 때만 한 번 더 확인한다."""

    text = _validate_text(request.text)
    if isinstance(text, JSONResponse):
        return text

    try:
        result = detect_with_llm(text)
    except Exception:
        # Ollama가 꺼져 있거나 모델이 없을 때. 숨기지 않고 정직하게 알린다.
        return {
            "available": False,
            "verdict": VERDICTS["clear"],
            "notice": (
                "추가 확인을 하지 못했어요. 위험 신호는 찾지 못했지만, "
                "한 번 더 꼼꼼히 보는 과정을 건너뛰었어요."
            ),
        }

    label = result.get("label")
    if label not in (0, 1):
        return {
            "available": False,
            "verdict": VERDICTS["clear"],
            "notice": (
                "추가 확인이 끝까지 되지 않았어요. 위험 신호는 찾지 못했지만, "
                "한 번 더 꼼꼼히 보는 과정을 마치지 못했어요."
            ),
        }

    if label == 1:
        return {
            "available": True,
            "verdict": VERDICTS["caution"],
            # LLM의 reason/evidence는 쓰지 않는다 (webapp/explain.py 설명 참고).
            "reasons": [
                {
                    "key": "context",
                    "title": "걸린 표현은 없지만 문맥이 의심스러워요",
                    "body": CAUTION_ONLY_BODY,
                    "matches": [],
                }
            ],
        }

    return {"available": True, "verdict": VERDICTS["clear"], "reasons": []}
