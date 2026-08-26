# Data Preprocessing

한국어 피싱 메시지 탐지 시스템의 데이터셋 구축 및 전처리 코드를 관리합니다.

## Dataset

### Hugging Face

`meal-bbang/Korean_message` 데이터셋을 사용합니다.

확인된 라벨은 다음과 같습니다.

- class 1: ordinary message
- class 2: phishing message

class 3은 공식 라벨 정의를 확인하지 못했으며, 데이터 확인 결과 배송 알림 형태의 메시지가 다수 관찰되었습니다.

따라서 class 3은 main dataset에서 제외하고 별도로 보존합니다.

### AIHub

AIHub 「주제별 텍스트 일상 대화 데이터」의 `norm_text`를 추출하여 정상 메시지 보강에 사용합니다.

Training 데이터에서 중복을 제거한 2,908개의 메시지를 추출했습니다.

## Label

프로젝트에서는 다음과 같이 이진 라벨을 사용합니다.

| Label | Meaning | Source |
|---|---|---|
| 0 | Normal | HF class 1 + AIHub |
| 1 | Phishing | HF class 2 |

HF class 3은 별도의 `hf_class3_delivery.csv`로 저장합니다.

## Preprocessing

주요 전처리 과정은 다음과 같습니다.

1. Hugging Face와 AIHub 데이터 통합
2. 프로젝트용 이진 라벨 생성
3. 완전 중복 메시지 제거
4. URL, 숫자 등을 정규화하여 반복 템플릿 탐지
5. 피싱 메시지의 유사 템플릿 그룹화
6. 그룹 단위 Train / Validation / Test 분할
7. 분할 후 유사도 검사를 통한 데이터 누수 확인

피싱 메시지의 유사 템플릿은 character-level TF-IDF와 cosine similarity를 이용하여 탐지합니다.

- n-gram: 3~5
- similarity threshold: 0.90
- minimum message length: 20

동일하거나 유사한 템플릿 그룹이 여러 split에 동시에 포함되지 않도록 그룹 단위로 분할합니다.

## Final Dataset

최종 main dataset은 총 16,355개입니다.

| Split | Total | Normal | Phishing |
|---|---:|---:|---:|
| Train | 11,520 | 6,078 | 5,442 |
| Validation | 2,452 | 1,303 | 1,149 |
| Test | 2,383 | 1,303 | 1,080 |

최종 분할 후 Train과 다른 split 사이에서 cosine similarity 0.90 이상인 메시지 비율은 다음과 같습니다.

- Train ↔ Validation: 0.65%
- Train ↔ Test: 0.92%

이는 초기 분할에서 약 16~17%였던 유사 메시지 비율을 크게 감소시킨 결과입니다.

## Scripts

| File | Description |
|---|---|
| `download_hf_dataset.py` | Hugging Face 데이터 다운로드 |
| `extract_aihub_normal.py` | AIHub 정상 대화 추출 |
| `analyze_dataset.py` | 데이터 분포 및 중복 분석 |
| `prepare_dataset.py` | 데이터 통합 및 정제 |
| `analyze_template_overlap.py` | 반복 템플릿 분석 |
| `split_dataset.py` | 그룹 기반 Train/Val/Test 분할 |
| `analyze_split_similarity.py` | split 간 유사도 검사 |

## Execution

프로젝트 루트에서 실행합니다.

```bash
python preprocessing/prepare_dataset.py
python preprocessing/split_dataset.py
python preprocessing/analyze_split_similarity.py