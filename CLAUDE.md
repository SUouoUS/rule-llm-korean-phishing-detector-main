# 졸업논문 프로젝트: 한국어 스미싱 탐지 Rule + 소형 LLM Hybrid

컴퓨터공학 졸업논문 (김수현). 최종 산출물은 논문 + 디지털 취약자용 웹앱(후순위).

## 작업 방식 (중요)
- 실험 코드는 **사용자가 직접 실행**해서 결과를 본다. 코드를 만들고 실행 방법을 안내하되, 사용자가 원하지 않으면 결과 숫자를 먼저 돌려서 알려주지 않는다.
- 사용자가 결과를 붙여 주면 해석하고 다음 단계를 안내한다.
- 가상환경: `.\.venv\Scripts\Activate.ps1` (Windows PowerShell). 모듈 실행은 프로젝트 루트에서 `python -m 폴더.파일`.
- LLM 실행에는 Ollama가 켜져 있어야 한다 (qwen3:1.7b).
- `requirements.txt` 마지막 줄 `python-dotenvollama`는 `python-dotenv`와 `ollama` 두 줄로 나눠야 한다.

## 시스템 구조 (확정: 구조 A)
- Rule: `rule_engine/detector.py` + `evaluation/evaluate_rule_thresholds.py`의 `predict_score()`. 임계값 1 (Validation에서 선택).
- LLM: `llm/detector.py`, qwen3:1.7b, temperature 0, think=False, JSON(label/evidence/reason). 파인튜닝 없음.
- Hybrid: `hybrid/detector.py`. Rule score ≥ 1이면 즉시 스미싱, 0이면 LLM 판단이 최종.

## 데이터
- 출처: Hugging Face `meal-bbang/Korean_message` (class 1 정상, class 2 스미싱), AI Hub 일상대화(정상 보강).
- 템플릿/유사도 그룹 단위 분할(GroupShuffleSplit): Train 11,520 / Val 2,452 / Test 2,383 (Test: 정상 1,303, 스미싱 1,080).
- class 3 = 정상 택배 배송 알림 2,409건 (`data/processed/hf_class3_delivery.csv`). 본 분할에서 제외 → 별도 평가셋으로 사용. 이름 반복으로 보아 생성 데이터로 추정.

## 지금까지의 결과
- Test(2026-10-16, 1회 사용함): Rule F1 0.888 / LLM 0.730 / Hybrid 0.922, FPR 0.009 / 0.041 / 0.050. Hybrid LLM 호출 1,499/2,383 (62.9%). McNemar p < 0.001.
- Validation Ablation (`evaluation/ablation_validation.py`): A(현재)가 가장 좋음. Rule 양성을 LLM에 더 넘기면(B/C/D) 오탐은 조금 줄고 미탐은 크게 늘어남. → LLM은 "정상"으로 답하는 경향이 강함 (단독 Recall 0.58).
- Validation 정상 메시지에는 링크가 든 문자가 사실상 없음 → URL 규칙이 과대평가된 데이터 한계.
- **Rule 임계값 전수 조사 (Validation, 2026-10-28)**: thr 0 → R 1.000/FPR 1.000(무의미), **thr 1 → R 0.8335/FPR 0.0107/F1 0.9032(선택)**, thr 2 → R 0.7341, thr 3 → R 0.1473. 임계값 1이 이미 가장 느슨한 설정이고, Rule이 놓친 191건은 **점수가 정확히 0**(신호 0개)이다. → Rule 단독 recall 천장 0.83은 튜닝 결과가 아니라 **구조적 한계**. 논문에서 "하이브리드가 민감도만 올린 것 아니냐"는 반박을 막는 핵심 근거.
- **LLM의 한계 기여 (Validation)**: score=0 스미싱 191건 중 93건(48.7%) 회수, score=0 정상 1,289건 중 58건(4.5%)을 새 오탐으로 추가 → 추가분 정밀도 61.6%.
- **3단계 위험도 교정값 (Validation)**: Rule≥1 "위험" 970건 정밀도 **98.6%** / Rule 0+LLM 양성 "주의" 151건 정밀도 **61.6%** / 둘 다 음성 1,329건 미탐율 **7.4%**. 세 단계가 뚜렷이 갈림 → 웹앱 UI가 아니라 **논문 본문 결과**로 쓴다. 단일 모델로는 나오지 않는 출력이고, "61.6%를 위험이라 단정하지 않는다"는 디지털 취약자 대상 설계 근거가 된다.
- 택배 알림 별도 평가 (`evaluation/evaluate_delivery_notices.py`, `--all`까지 완료): Rule 오탐 899/2,409 (37.3%) = 쿠팡 공식 링크 599건 + 한진 "접수제한" 300건. LLM 오탐 0건. Hybrid 오탐 = Rule 오탐.

## 현재 단계: Rule 개선 완료 (2026-10-28). 다음은 Test 오류 분석 → 논문
- `rule_engine/detector.py`에 옵션 2개 추가 (기본 False = 기존 결과와 동일, 전체 18,764건으로 확인함):
  - `USE_DOMAIN_ALLOWLIST`: 택배사 공식 도메인(및 하위 도메인) URL은 URL 신호에서 제외. 흉내 낸 주소(coupang.com.evil.xyz)는 제외하지 않음. 도메인 8개 출처 확인 완료(2026-10-28, 루트 HTTPS 접속 + title 확인, 근거는 `detector.py` 주석). SLX는 데이터에 있지만 원칙상 미포함.
  - `USE_URGENCY_CONTEXT`: "접수제한/접수 제한"의 "제한"은 긴급성 신호에서 제외.
- 옵션 동작 확인 완료 (2026-10-28): 공식+악성 URL이 섞이면 악성만 남고, `coupang.com.evil.xyz`/`notcoupang.com`/`coupang-com.xyz`는 그대로 탐지. "접수제한" 외의 "제한"(예: "이용이 제한됩니다")과 같은 문장의 다른 긴급성 키워드는 그대로 남음.
- 택배 오탐 899건의 구성 확인: `url`만 599건(전부 `https://coupang.com/photoN`), `urgency`만 300건(전부 "접수제한", 제거 후 남는 긴급성 0개). 겹치는 메시지 없음. 택배 데이터에 "접수제한"이 아닌 "제한"은 0건. (이 구성 확인과 그 산술적 결과로 both 적용 시 택배 전체 오탐 0건임을 전체 데이터에서 봄 → 논문에 명시)
- 택배 분할 완료: dev 1,045건/템플릿 415개, eval 1,364건/템플릿 415개 (`preprocessing/split_delivery.py`, GroupShuffleSplit seed 42).
- `evaluation/evaluate_rule_improvements.py` 결과 (2026-10-28, `evaluation/rule_improvements.csv`):
  - Validation 2,450건: base/allowlist/context/both **네 조건이 완전히 동일** (Rule P 0.9856 / R 0.8335 / F1 0.9032 / FPR 0.0107, Hybrid F1 0.9250 / FPR 0.0553 / LLM 호출률 0.6041).
  - delivery_dev 1,045건 Rule 오탐: base 300(28.7%) → allowlist 143 → context 157 → **both 0**. 두 옵션이 겹치지 않고 각자 몫을 함(143+157=300).
- **판단 기준 충족 → 최종 설정은 `both`** (두 옵션 모두 켬).
- ⚠️ Validation이 동일한 이유는 "손실이 없어서"가 아니라 **해당 패턴이 주 데이터셋에 아예 없어서**다. 직접 확인: train 11,520건·val 2,452건 모두 공식 도메인 URL 0건, "접수제한" 0건, Rule 점수가 바뀐 메시지 0건. → 논문에서 "Validation 성능 변화 없음"을 안전성 근거로 쓰면 과장이다. 안전성 근거는 데이터가 아니라 설계이며, `tests/test_rule_options.py`(13건, 추가 패키지 없이 실행)로 보인다.
- 택배 eval 1,364건 1회 확인 완료 (`--eval`): Rule 오탐 base 599(43.9%) → allowlist 157 → context 442 → **both 0**. dev에서 고른 설정이 처음 보는 eval에서도 오탐 0.
- 원인 분해가 dev/eval 합과 정확히 일치: 쿠팡 공식 링크 157+442=599, "접수제한" 143+157=300. (템플릿 단위 분할이라 쿠팡이 eval에 몰림)
- `check_test_rule_invariance` 완료: Test 2,383건에 공식 도메인 URL 0건, "접수제한" 0건, **Rule 예측이 바뀐 메시지 0건**. → 기존 `test_model_predictions.csv`와 McNemar 결과가 그대로 최종. **Test 재평가·LLM 재호출 불필요** (5.5시간 절약).
- `detector.py` 기본값을 **True로 전환 완료**. 개선 전 결과를 재현하려면 둘 다 False로 되돌린다.
- 기본값 True 상태 Validation Rule 재확인: P 0.9856 / R 0.8338 / F1 0.9033 / FPR 0.0107 (전체 2,452건 기준. 위 표의 R 0.8335는 LLM 판단이 있는 2,450건 기준이라 생긴 차이로, 개선의 영향이 아니다.)
- `tests/test_rule_options.py` 13건 통과 (위조 내성 9 + 긴급성 문맥 4).
- 이번 개선과 무관하게 발견한 기존 Rule 한계 (지금은 건드리지 않음): `URL_PATTERN`의 "스킴 없는 도메인" 분기가 `com|net|org|kr|co.kr`만 받아서 `bit.ly/abc`, `vo.la/abc`, `abc.xyz/a`처럼 스킴 없는 단축/신규 TLD 링크를 놓친다(`https://bit.ly/abc`는 탐지됨). 고치면 base 결과가 바뀌어 전체 재평가가 필요하므로, 논문 한계로 쓰거나 별도 개선안으로 분리.

## 평가 원칙 (지킬 것)
- Test는 이미 1회 사용. 튜닝·Ablation은 Validation(과 delivery_dev)에서만. 최종 설정 확정 후 Test는 한 번만 재평가하고, 논문에 "2차 평가"임을 밝힌다. 재평가 시 기존 `evaluation/test_model_predictions.csv`는 다른 이름으로 보관 (run_id가 바뀌어 스크립트가 거부함).
- 택배 오탐 원인은 전체 택배 데이터를 보고 찾았음 → 논문에 명시.
- 효율성 주장 주의: 실제 문자는 대부분 정상이라 실사용 호출률은 62.9%보다 높아질 수 있음. LLM 응답시간(Test): 평균 8.4초, 중앙값 6.9초.

## 남은 일
1. ~~Rule 개선 → 설정 확정~~ **완료 (2026-10-28)**. Test 재평가·McNemar 재실행 불필요로 확정.
2. Test 오류 분석: 오탐·미탐 유형 분류 (LLM reason 저장하며 오류 사례만 재실행)
3. 논문 작성 (선행연구는 작성과 병행, 참고: KorSmishing Explainer, EMNLP 2024 Industry)
   - **중심 주장 (바꿀 것)**: "합쳐서 F1이 0.888 → 0.922로 올랐다"가 아니라 **"Rule과 소형 LLM은 서로 다른 곳에서 실패하므로 합칠 가치가 있다"**. 전자는 "OR로 묶으면 당연히 더 잡히는 것 아닌가"라는 반박에 약하다.
   - 근거 4개: ① Rule recall 천장 0.83이 구조적(임계값 전수 조사) ② 같은 택배 2,409건에서 Rule 오탐 37.3% vs **LLM 오탐 0%** ③ 결합 방향이 비대칭 — LLM이 Rule 양성을 뒤집게 하면 더 나빠짐(Ablation B/C/D), 1.7B가 "정상" 쪽으로 치우쳐서 ④ 비용 정량화(추가분 정밀도 61.6%, FPR 5.2배, 호출률 62.9%, 8.4초)
   - **소형 모델은 사후 변명이 아니라 설계 요구사항으로 앞세운다**: 온디바이스, 문자 내용 외부 전송 없음, 건당 비용 0, 디지털 취약자 대상. "모델 크기에 따른 민감도 분석"은 한계·향후 과제로 명시(8B를 쓰면 Rule의 상대적 가치가 줄어들 수 있음).
   - FPR 0.009 → 0.050(5.2배)이 실사용의 최대 약점. 늘어난 오탐이 대부분 "주의" 단계에 갇힌다는 점(3단계 교정값)과 명시적으로 연결해 서술한다.
4. 웹앱 (후순위, 사용자가 직접 만들고 싶어 함). 3단계 위험도 아이디어: Rule 양성=위험, Rule 0점+LLM 양성=주의, 둘 다 정상=위험 신호 없음 ("안전합니다" 표현 금지)
