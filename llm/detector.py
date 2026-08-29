import json
import time

from ollama import chat


MODEL_NAME = "qwen3:1.7b"


SYSTEM_PROMPT = """
한국어 문자 메시지를 정상(0) 또는 피싱(1)으로 분류하세요.

피싱 신호:
- 사칭 또는 긴급한 행동 유도
- 송금, 결제, 개인정보·인증정보 요구
- 의심스러운 링크 또는 외부 연락 유도
- 보상·상품·쿠폰 등을 이용한 유인
- 도박·불법 서비스 가입 유도
- 난독화된 URL·연락처 사용

단어 하나가 아닌 전체 문맥으로 판단하세요.
메시지에 없는 사실을 추측하지 마세요.
evidence에는 원문에 실제 존재하는 피싱 판단 근거만 넣으세요.

JSON만 출력:
{
    "label": 0 또는 1,
    "evidence": ["원문 표현"],
    "reason": "20자 이내 판단 근거"
}
"""


def detect_with_llm(text: str) -> dict:
    """로컬 LLM을 이용하여 메시지의 피싱 여부를 판단한다."""

    response = chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": text,
            },
        ],
        format="json",
        think=False,
        options={
            "temperature": 0,
            "num_predict": 160,
        },
    )

    content = response["message"]["content"]

    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        return {
            "label": None,
            "reason": "LLM 응답을 JSON으로 변환하지 못했습니다.",
            "raw_response": content,
        }

    evidence = result.get("evidence", [])

    # 실제 메시지에 존재하지 않는 evidence 제거
    valid_evidence = [
        item
        for item in evidence
        if isinstance(item, str) and item in text
    ]

    return {
        "label": result.get("label"),
        "evidence": valid_evidence,
        "reason": result.get("reason", ""),
    }


if __name__ == "__main__":
    test_messages = [
        "오늘 수업 끝나고 저녁 뭐 먹을까? 학교 앞에서 만나자.",
        (
            "고객님의 계좌가 정지되었습니다. "
            "본인 확인을 위해 아래 링크에 접속하세요."
        ),
        (
            "방금 전화드렸습니다. "
            "오만 + 버거셋 승전없습니다. "
            "까아톡 ww****"
        ),
    ]

    total_time = 0

    for message in test_messages:
        start_time = time.perf_counter()

        result = detect_with_llm(message)

        elapsed_time = time.perf_counter() - start_time
        total_time += elapsed_time

        print("메시지:", message)
        print("LLM 결과:", result)
        print(f"추론 시간: {elapsed_time:.2f}초")
        print("-" * 50)

    average_time = total_time / len(test_messages)

    print(f"총 추론 시간: {total_time:.2f}초")
    print(f"평균 추론 시간: {average_time:.2f}초/메시지")