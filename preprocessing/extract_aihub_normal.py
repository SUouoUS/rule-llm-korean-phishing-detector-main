import json
import zipfile
from pathlib import Path
import pandas as pd

AIHUB_DIR = Path(
    r"C:\Users\SuHyeon\Downloads\020.주제별 텍스트 일상 대화 데이터\01.데이터\1.Training"
)

if not AIHUB_DIR.exists():
    raise FileNotFoundError(f"AIHub Training 경로를 찾을 수 없습니다: {AIHUB_DIR}")

OUTPUT_PATH = Path("data/processed/aihub_normal.csv")
OUTPUT_LIMIT = 3000

messages = []

# Training의 라벨링 데이터 압축파일만 탐색
for zip_path in AIHUB_DIR.rglob("*.zip"):

    # 원천데이터는 제외하고 라벨링데이터만 사용
    if "라벨링데이터" not in str(zip_path):
        continue

    print(f"Processing: {zip_path.name}")

    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            for file_name in z.namelist():

                if not file_name.lower().endswith(".json"):
                    continue

                try:
                    with z.open(file_name) as f:
                        data = json.load(f)

                    for info in data.get("info", []):
                        annotations = info.get("annotations", {})
                        lines = annotations.get("lines", [])

                        for line in lines:
                            text = line.get("norm_text")

                            if text:
                                text = text.strip()

                                if text:
                                    messages.append(text)

                            if len(messages) >= OUTPUT_LIMIT:
                                break

                        if len(messages) >= OUTPUT_LIMIT:
                            break

                except Exception as e:
                    print(f"JSON error: {file_name} / {e}")

                if len(messages) >= OUTPUT_LIMIT:
                    break

    except Exception as e:
        print(f"ZIP error: {zip_path} / {e}")

    if len(messages) >= OUTPUT_LIMIT:
        break


# 중복 제거
messages = list(dict.fromkeys(messages))

# 최대 개수 제한
messages = messages[:OUTPUT_LIMIT]

# DataFrame 생성
df = pd.DataFrame({
    "content": messages,
    "class": 0
})

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

if df.empty:
    raise RuntimeError(
        "추출된 메시지가 0개입니다. 출력 파일을 저장하지 않습니다. "
        "AIHUB_DIR 또는 ZIP/JSON 구조를 확인하세요."
    )

df.to_csv(
    OUTPUT_PATH,
    index=False,
    encoding="utf-8-sig"
)

print("\n=== 완료 ===")
print(f"추출된 정상 메시지 수: {len(df)}")
print(f"저장 위치: {OUTPUT_PATH}")
print(df.head(10))