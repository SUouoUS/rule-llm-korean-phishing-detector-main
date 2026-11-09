# Rule Engine + 소형 LLM 한국어 스미싱 탐지

규칙 기반 탐지기와 소형 LLM(qwen3:1.7b)을 결합해 한국어 스미싱 문자를 탐지합니다.
컴퓨터공학과 졸업논문 프로젝트이며, 모든 판정은 외부 API 없이 로컬에서만 수행합니다.

## 무엇을 확인한 연구인가

"규칙과 LLM을 합치면 성능이 오른다"가 아니라 **언제 합칠 가치가 있는가**를 측정했습니다.

- **규칙 엔진이 약할 때** 소형 LLM 결합은 분명한 이득입니다.
  F1 0.888 → 0.922, McNemar 108:53 (p = 1.7e-05).
- **규칙을 제대로 고치면 그 이득이 사라집니다.**
  F1 0.961 → 0.946, McNemar가 53:18로 **역전**되어 Rule 단독이 우세합니다 (p = 3.9e-05).
  미탐 비용을 무겁게 보는 F2에서만 간신히 유지됩니다 (0.9496 vs 0.9453).
- 두 모델은 **덧셈이 아니라 대체 관계**입니다. 규칙을 강화하자 LLM이 건지던 진짜 스미싱은
  93 → 32건으로 줄었지만 LLM이 만드는 오탐은 58건 그대로였습니다(Validation).

→ 실무 함의: **먼저 규칙을 제대로 고치고, 소형 LLM은 그 다음이며, 미탐 비용이 높을 때만 값합니다.**

## 시스템 구조

```
문자 입력
  │
  ├─ 1단계: Rule Engine  (rule_engine/detector.py + predict_score)
  │     점수 ≥ 1  ──────────────────────────────▶ 위험 (LLM 호출 없음)
  │     점수 = 0
  │
  └─ 2단계: 소형 LLM     (llm/detector.py, qwen3:1.7b)
        label = 1 ───────────────────────────────▶ 주의
        label = 0 ───────────────────────────────▶ 위험 신호 없음
```

| 구성 | 파일 | 설정 |
|---|---|---|
| Rule | `rule_engine/detector.py`, `evaluation/evaluate_rule_thresholds.py` 의 `predict_score()` | 임계값 1 (Validation에서 선택) |
| LLM | `llm/detector.py` | qwen3:1.7b, temperature 0, think=False, JSON 출력, 파인튜닝 없음 |
| Hybrid | `hybrid/detector.py` | Rule 점수 ≥ 1 → 즉시 스미싱, 0 → LLM 판단이 최종 |

### Rule 점수 계산

`analyze_message()`가 신호 7종을 찾고, `predict_score()`가 점수로 합칩니다.

| 핵심 신호 | 가중치 | | 보조 신호 | 가중치 |
|---|---|---|---|---|
| `url` | 2 | | `reward` | 세 개를 합쳐 |
| `personal_info` | 2 | | `contact` | 최대 **+1** |
| `urgency` | 1 | | `gambling` | |
| `financial` | 1 | | | |

점수가 1점 이상이면 스미싱으로 판정합니다. Validation 전수 조사에서 임계값 1이 가장
느슨한 유효 설정이었습니다 (thr 1 → R 0.8335 / FPR 0.0107 / F1 0.9032, thr 2 → R 0.7341,
thr 3 → R 0.1473).

### Rule 옵션 (최종 설정 `enum+general`)

`rule_engine/detector.py` 상단의 플래그로 켜고 끕니다. 1차 평가(2026-10-16) 결과를
재현하려면 아래 옵션을 전부 `False`로 되돌립니다.

| 플래그 | 하는 일 | 기본값 |
|---|---|---|
| `USE_DOMAIN_ALLOWLIST` | 택배사 공식 도메인(및 하위 도메인)은 URL 신호에서 제외. 흉내 낸 주소(`coupang.com.evil.xyz`)는 제외하지 않음 | True |
| `USE_URGENCY_CONTEXT` | "접수제한"의 "제한"은 긴급성 신호에서 제외 | True |
| `USE_HANGUL_DOMAIN` | 도메인 이름에 한글이 섞인 주소 (`심바.COM`, `레옹.net`) | True |
| `USE_SHORTENER_HOSTS` | Train에 나타난 단축 URL 호스트 열거 (`bit.ly` 등) | True |
| `USE_TLD_VARIANTS` | 점 대체·글자 변형 (`쩜컴`, `。com`, `ⓒⓞⓜ`, `◘ℂℴℳ`) | True |
| `USE_GENERAL_TLD` | 스킴 없는 주소를 TLD 종류와 무관하게 인식 | True |
| `USE_GENERAL_TLD_STRICT` | 위와 같지만 경로(`/...`) 필수 | False |

## 결과 (Test 2,383건 = 정상 1,303 / 스미싱 1,080)

| 설정 | 모델 | P | R | F1 | F2 | FPR | FP | FN | LLM 호출률 |
|---|---|---|---|---|---|---|---|---|---|
| base | Rule | 0.9864 | 0.8074 | 0.8880 | 0.8378 | 0.0092 | 12 | 208 | — |
| base | LLM | 0.9247 | 0.6028 | 0.7298 | 0.6479 | 0.0407 | 53 | 429 | — |
| base | **Hybrid** | 0.9378 | 0.9074 | **0.9224** | **0.9133** | 0.0499 | 65 | 100 | 0.629 |
| final | **Rule** | 0.9883 | 0.9352 | **0.9610** | 0.9453 | 0.0092 | 12 | 70 | — |
| final | Hybrid | 0.9405 | 0.9519 | 0.9462 | **0.9496** | 0.0499 | 65 | 52 | 0.571 |

난독화 규칙 추가로 Rule 미탐이 208 → 70건으로 줄었고(McNemar 138:0, 악화된 건 없음)
**오탐은 12건 그대로**입니다. LLM 응답시간은 평균 8.4초 / 중앙값 6.9초입니다.

### 3단계 위험도 (Test)

| 설정 | 위험 (Rule ≥ 1) | 주의 (Rule 0 + LLM 양성) | 위험 신호 없음 |
|---|---|---|---|
| base | 884건 / 정밀도 0.9864 | 161건 / 정밀도 0.6708 | 1,338건 / 미탐율 0.0747 |
| final | 1,022건 / 정밀도 0.9883 | 71건 / 정밀도 **0.2535** | 1,290건 / 미탐율 **0.0403** |

"주의" 단계의 정밀도는 낮지만, 그 18건은 Rule이 전혀 잡지 못하는 메시지여서 경고가
없으면 보호가 0입니다. 그래서 "위험"이라 단정하지 않고 "주의"로 내보냅니다.

## 데이터

- Hugging Face `meal-bbang/Korean_message` (class 1 정상, class 2 스미싱) + AI Hub 일상대화(정상 보강)
- 템플릿·유사도 그룹 단위 분할 (GroupShuffleSplit): **Train 11,520 / Val 2,452 / Test 2,383**
- class 3 = 정상 택배 배송 알림 2,409건은 본 분할에서 제외하고 별도 평가셋으로 사용
  (dev 1,045 / eval 1,364). 같은 데이터에서 Rule 오탐 37.3% vs **LLM 오탐 0%** 가 관측되어
  두 모델이 서로 다른 곳에서 실패함을 보이는 근거가 됩니다.

원본 데이터는 저장소에 포함하지 않습니다. `preprocessing/`의 스크립트로 내려받아 만듭니다.

## 설치

Windows PowerShell, 프로젝트 루트에서 실행합니다.

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

LLM을 쓰는 단계에는 [Ollama](https://ollama.com)가 켜져 있어야 합니다.

```powershell
ollama pull qwen3:1.7b
ollama serve          # 이미 백그라운드로 돌고 있으면 생략
```

웹앱에서 캡처 사진의 글자를 읽으려면 `pip install easyocr`을 추가로 설치합니다
(약 250MB, 없어도 텍스트 입력은 동작).

## 시스템 실행

모듈 실행은 **항상 프로젝트 루트에서** `python -m 폴더.파일` 형식으로 합니다.

### 1. 문자 한 건 판정 (Python)

```python
from hybrid.detector import detect_with_hybrid

print(detect_with_hybrid("[Web발신] 택배 주소지 오류 확인 심바.COM"))
# {'label': 1, 'source': 'rule', 'rule_score': 2,
#  'evidence': ['url'], 'reason': 'Rule Engine 위험 신호 탐지'}
```

### 2. 각 모듈 단독 실행 (예시 문자로 동작 확인)

```powershell
python -m rule_engine.detector      # Rule 신호·점수 출력 (LLM 불필요)
python -m llm.detector              # LLM 단독 판정 + 응답시간 (Ollama 필요)
```

### 3. 웹앱 (디지털 취약자용 화면)

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn webapp.main:app --reload
```

브라우저에서 `http://127.0.0.1:8000`. Ollama가 꺼져 있으면 2단계를 건너뛰고
"추가 확인을 하지 못했어요"라고 알립니다. 자세한 사용법은 [webapp/README.md](webapp/README.md).

웹앱의 Rule 설정이 실험과 같은 숫자를 내는지 확인:

```powershell
python -m webapp.verify_against_test     # 미탐 70건 / 오탐 12건 재현 확인, LLM 호출 없음
```

### 4. 평가 재현

```powershell
# Test 최종 평가 — base vs final, F1·F2·3단계·McNemar를 한 번에. LLM 호출 0회
python -m evaluation.evaluate_test_final

# 난독화 규칙 검증 (Validation + 택배 dev, 조건 9개). LLM 호출 0회
python -m evaluation.evaluate_obfuscation_rules
python -m evaluation.evaluate_obfuscation_rules --eval     # 택배 eval셋까지

# Rule 임계값 전수 조사 (Validation)
python -m evaluation.evaluate_rule_thresholds

# 결합 방식 Ablation (A/B/C/D, Validation)
python -m evaluation.ablation_validation

# 택배 알림 별도 평가 (Ollama 필요)
python -m evaluation.evaluate_delivery_notices
python -m evaluation.evaluate_delivery_notices --all       # 전체에 LLM 호출

# Test 오류 분석 (165건에 LLM reason 수집, Ollama 필요)
python -m evaluation.analyze_test_errors --limit 20        # 먼저 20건만 시험
```

결과는 `evaluation/` 아래 CSV로 저장됩니다
(`test_final/`, `obfuscation_rules.csv`, `train_misses/`, `error_analysis_test/` 등).

### 5. 단위 테스트

```powershell
python -m tests.test_rule_options      # 32건, 추가 패키지 없이 실행
```

난독화 규칙이 잡아야 하는 표기와, 일반 단어(`컴퓨터`, `넷플릭스`, `보고서.pdf`)를
오인하지 않는지 함께 확인합니다.

### 6. 데이터 재구축

```powershell
python -m preprocessing.download_hf_dataset
python -m preprocessing.extract_aihub_normal
python -m preprocessing.prepare_dataset
python -m preprocessing.split_dataset        # Train/Val/Test (GroupShuffleSplit, seed 42)
python -m preprocessing.split_delivery       # 택배 dev/eval
```

## 디렉터리

```
rule_engine/     규칙 기반 탐지기 (신호 7종, 난독화 옵션 7개)
llm/             qwen3:1.7b 호출, JSON 파싱
hybrid/          Rule → LLM 결합 (구조 A)
evaluation/      평가·Ablation·오류 분석 스크립트와 결과 CSV
preprocessing/   데이터 수집·정제·그룹 단위 분할
tests/           Rule 옵션 단위 테스트 32건
webapp/          FastAPI 웹앱 (3단계 위험도, 로컬 처리)
data/            raw / processed (원본 데이터는 비포함)
docs/            진행 기록
```

## 평가 원칙

- Test는 1차 평가(2026-10-16)에서 한 번 사용했습니다. 튜닝·Ablation은 **Validation과
  택배 dev에서만** 수행합니다.
- `evaluate_test_final.py`는 base 설정이 1차 평가의 혼동행렬을 재현하는지 자동 검사하고,
  재현에 실패하면 중단합니다.
- Test 전체 2,383건에 LLM 판정이 저장되어 있고 LLM 판정은 Rule 설정과 무관하므로,
  어떤 Rule 변경도 **LLM 재호출 없이** 재평가됩니다.

## 한계 (논문에 그대로 기재)

- **final 설정의 Test 결과는 2차 평가입니다.** 난독화 규칙의 착안점이 Test 오류 분석에서
  나왔으므로 Rule에 유리하게 편향됐을 수 있습니다. 개선 효과의 주된 근거는 Validation
  (Recall 0.8335 → 0.9381, 오탐 증가 0)에 둡니다.
- **난독화 회피가 최대 미해결 약점입니다.** 난독화 강도가 올라가면 Rule → LLM → 둘 다
  순서로 무너집니다. 희귀 TLD는 LLM이 49% 건지지만, 난독화가 심한 미탐은 42%가 둘 다 실패합니다.
- **정상 메시지에 도메인 꼴이 드문 데이터 한계**로 "규칙을 넓혀도 오탐이 늘지 않는다"를
  측정할 수 없었습니다. Validation 정상 1,303건에 "글자.글자" 꼴이 0건이어서 9개 조건 모두
  FP가 14건으로 고정됩니다. 스모크 테스트에서는 `사진.jpg`, `index.html`이 걸립니다.
- **데이터 품질 문제 2개.** ① Test 미탐 100건 중 17건은 스미싱 라벨인데 내용이 정상으로
  보입니다(항공편 안내, 인증코드, 결혼 청첩장). 실제 Recall은 보고값보다 높을 수 있습니다.
  ② 정상 라벨에 문자 메시지가 아닌 정치 댓글이 섞여 있고, LLM 오탐 53건이 거의 전부
  이것입니다. LLM FPR 0.041의 상당 부분이 데이터 출처 문제입니다.
- **설명 가능성은 주장하지 않습니다.** LLM의 `reason`은 프롬프트의 신호 목록을 복창하는
  경향이 있어(링크 없는 문장에 "의심스러운 링크") 불충실합니다. 오류 분석 도구로만 썼고,
  웹앱 화면에도 쓰지 않습니다.
- FPR 0.009 → 0.050(5.2배)이 실사용의 최대 약점입니다. 늘어난 오탐이 대부분 "주의" 단계에
  머문다는 점과 함께 서술합니다.
- 모델 크기에 따른 민감도 분석은 하지 않았습니다. 더 큰 모델을 쓰면 Rule의 상대적 가치가
  줄어들 수 있습니다.

소형 모델(1.7B)은 사후 변명이 아니라 설계 요구사항입니다 — 온디바이스, 문자 내용 외부
전송 없음, 건당 비용 0, 디지털 취약자 대상.

## 개발 환경

Python 3.13 · pandas / numpy / scipy / scikit-learn · FastAPI + uvicorn (웹앱) ·
Ollama + qwen3:1.7b (LLM)
