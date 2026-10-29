"""Train 미탐(Rule 0점 스미싱)에서 난독화 표기 목록을 추출한다 — 규칙 작성용 작업지.

왜 Train인가
  10/29 Test 오류 분석에서 미탐 대부분이 "신호가 없는 문자"가 아니라 "표기를 못 읽은
  문자"임을 확인했다. 난독화 대응 규칙을 만들려면 변형 목록이 필요한데, 그 목록을
  Test에서 뽑으면 Test에 맞춘 규칙이 된다. Train 미탐은 998건으로 Test(100건)보다
  10배 많고 같은 유형을 다 담고 있으므로, 여기서만 뽑으면 Test를 열지 않아도 된다.

이 스크립트는 분류기가 아니라 **추출기**다. 사람이 짐작한 패턴을 세는 것이 아니라
데이터에 실제로 있는 표기를 모아 빈도순으로 보여준다. 규칙은 그 목록을 보고 쓴다.

출력 (evaluation/train_misses/)
  summary.csv        유형별 건수와 누적 커버리지
  tld_variants.csv   com/net 표기 변형 목록 (빈도순)
  separators.csv     점(.) 대체 표기 목록
  rare_tlds.csv      희귀/신규 TLD 목록
  messenger.csv      메신저 유인 어휘 변형
  cases.csv          998건 전체 (유형 태그 포함)

실행 (프로젝트 루트, LLM 불필요):
    python -m evaluation.analyze_train_misses
"""

import re
from collections import Counter
from pathlib import Path

import pandas as pd

from evaluation.evaluate_rule_thresholds import predict_score


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRAIN_PATH = PROJECT_ROOT / "data" / "processed" / "train.csv"
OUTPUT_DIR = PROJECT_ROOT / "evaluation" / "train_misses"

# --------------------------------------------------------------------
# "com / net 처럼 보이는 토큰" — 글자별 변형을 전부 받는다.
# 정상 표기(com)도 같이 잡아서, 구분자가 깨진 경우를 찾을 수 있게 한다.
# --------------------------------------------------------------------
C = r"[cCｃⓒℂСсⅽ⒞]"
O = r"[oOｏⓞℴОо0０ⓞⲟὀ]"
M = r"[mMｍⓜℳМм⒨]"
N = r"[nNｎⓝℕНн]"
E = r"[eEｅⓔℰЕе]"
T = r"[tTｔⓣТт]"

COM_LIKE = re.compile(rf"(?:{C}\s?{O}\s?{M}|컴|콤|ℂℴℳ)", re.I)
NET_LIKE = re.compile(rf"(?:{N}\s?{E}\s?{T}|넷)", re.I)
TLD_LIKE = re.compile(rf"(?:{C}\s?{O}\s?{M}|{N}\s?{E}\s?{T}|컴|콤|넷|ℂℴℳ)", re.I)

# TLD 앞에 붙은 구분자 1~3글자를 같이 집는다 (점 대체 표기를 찾기 위함)
SEP_AND_TLD = re.compile(
    rf"(.{{0,3}}?)({C}\s?{O}\s?{M}|{N}\s?{E}\s?{T}|컴|콤|넷|ℂℴℳ)",
    re.I,
)

STANDARD_TLD = {"com", "net", "org", "kr"}
RARE_TLD = re.compile(r"\.\s?([a-z]{2,6})(?![a-z])", re.I)

SHORTENER = re.compile(
    r"\b(?:bit|cutt|vo|is|t|goo|tiny|buly|han|kko|url|me2|abit|dooo|lnk)"
    r"\s?\.\s?(?:ly|la|gl|gd|do|kr|cc|us|im|to|url)",
    re.I,
)

# 메신저 유인 어휘: 정상 표기 + 데이터에서 본 변형의 씨앗.
# 목록을 늘리려고 쓰는 게 아니라, 어떤 변형이 있는지 찾아내기 위한 탐침이다.
MESSENGER_PROBE = re.compile(
    r"[가-힣ㄱ-ㅎ]{0,2}(?:톡|톸|톹|툑|툭|툓|퉬|톡스)"
    r"|[까카꺄깨께꺠]\s?[까카톡톸]"
    r"|[텔탤뗄땔털]\s?[레래]?\s?[그크]?\s?램?"
    r"|텔렘|테레|노란|라인|라잉|위챗|왓츕",
)

GAMBLING_PROBE = re.compile(
    r"[벳뱃밷벿뻿붿]|카지노|캬즤노|캐지노|슬롯|스을롯|롤링|뤌링|페이백|단폴|단뽈"
    r"|충전|충\*|환전|먹튀|메이저|먜이져|놀이터|토토|TO토|배당|고배당",
    re.I,
)

REWARD_PROBE = re.compile(
    r"치킨|치퀸|치느님|버거|벅거|햄버|햄벅|맥도날드|멕됴냘드|스타벅스|스탸벽|커피"
    r"|기프티콘|기프|깊콘|문상|문화상품권|포인트|포\.인\.트|상품권|식사비|선물",
    re.I,
)


def flatten(text: str) -> str:
    """공백을 없앤 사본. 난독화는 공백을 끼워 넣는 경우가 많다."""

    return re.sub(r"\s+", "", str(text))


def load_train_misses() -> pd.DataFrame:
    train = pd.read_csv(TRAIN_PATH)
    train.insert(0, "row_index", range(len(train)))
    train["rule_score"] = train["content"].apply(predict_score)
    misses = train[(train["label"] == 1) & (train["rule_score"] == 0)].copy()
    misses["flat"] = misses["content"].apply(flatten)
    return misses


def collect_tld_variants(misses: pd.DataFrame) -> pd.DataFrame:
    """com/net 처럼 보이는 토큰을 실제 표기 그대로 모은다."""

    counter = Counter()
    for text in misses["flat"]:
        for match in TLD_LIKE.finditer(text):
            counter[match.group(0)] += 1
    rows = [
        {
            "variant": variant,
            "count": count,
            "is_standard": variant.lower() in STANDARD_TLD,
        }
        for variant, count in counter.most_common()
    ]
    return pd.DataFrame(rows)


def collect_separators(misses: pd.DataFrame) -> pd.DataFrame:
    """TLD 바로 앞 1~3글자를 모아 점(.) 대체 표기를 찾는다."""

    counter = Counter()
    for text in misses["flat"]:
        for prefix, _tld in SEP_AND_TLD.findall(text):
            # 영숫자/한글로만 끝나면 도메인 이름의 일부이므로 구분자가 아니다
            tail = prefix[-1:] if prefix else ""
            if tail and not re.match(r"[A-Za-z0-9가-힣]", tail):
                counter[tail] += 1
            elif "쩜" in prefix or "점" in prefix or "닷" in prefix:
                counter[re.search(r"[쩜점닷]", prefix).group(0)] += 1
    rows = [{"separator": sep, "count": count} for sep, count in counter.most_common()]
    return pd.DataFrame(rows)


def collect_rare_tlds(misses: pd.DataFrame) -> pd.DataFrame:
    counter = Counter()
    for text in misses["flat"]:
        for tld in RARE_TLD.findall(text):
            if tld.lower() not in STANDARD_TLD:
                counter[tld.lower()] += 1
    rows = [{"tld": tld, "count": count} for tld, count in counter.most_common()]
    return pd.DataFrame(rows)


def collect_probe_hits(misses: pd.DataFrame, pattern: re.Pattern) -> pd.DataFrame:
    counter = Counter()
    for text in misses["flat"]:
        for match in pattern.finditer(text):
            counter[match.group(0)] += 1
    rows = [{"term": term, "count": count} for term, count in counter.most_common()]
    return pd.DataFrame(rows)


def tag(misses: pd.DataFrame) -> pd.DataFrame:
    """각 미탐에 유형 태그를 붙인다 (중복 가능)."""

    flat = misses["flat"]
    misses["has_tld_like"] = flat.str.contains(TLD_LIKE)
    misses["has_rare_tld"] = flat.apply(
        lambda t: any(x.lower() not in STANDARD_TLD for x in RARE_TLD.findall(t))
    )
    misses["has_shortener"] = flat.str.contains(SHORTENER)
    misses["has_hangul_domain"] = flat.str.contains(
        r"[가-힣]{2,}\s?\.\s?(?:com|net|org|kr)", case=False, regex=True
    )
    misses["has_messenger"] = flat.str.contains(MESSENGER_PROBE)
    misses["has_gambling"] = flat.str.contains(GAMBLING_PROBE)
    misses["has_reward"] = flat.str.contains(REWARD_PROBE)
    return misses


def summarize(misses: pd.DataFrame) -> pd.DataFrame:
    """유형별 건수와, 위에서부터 더해 갈 때의 누적 커버리지."""

    families = [
        ("TLD 표기 변형 (com/net류)", "has_tld_like"),
        ("희귀/신규 TLD", "has_rare_tld"),
        ("단축 URL 호스트", "has_shortener"),
        ("한글 도메인 이름", "has_hangul_domain"),
        ("메신저 유인 어휘", "has_messenger"),
        ("도박 어휘", "has_gambling"),
        ("보상·먹이 어휘", "has_reward"),
    ]
    total = len(misses)
    covered = pd.Series(False, index=misses.index)
    rows = []
    for name, column in families:
        hits = misses[column]
        covered = covered | hits
        rows.append(
            {
                "family": name,
                "hits": int(hits.sum()),
                "share": hits.mean(),
                "cumulative_covered": int(covered.sum()),
                "cumulative_share": covered.mean(),
            }
        )
    rows.append(
        {
            "family": "(어느 유형에도 안 걸림)",
            "hits": int((~covered).sum()),
            "share": (~covered).mean(),
            "cumulative_covered": total,
            "cumulative_share": 1.0,
        }
    )
    return pd.DataFrame(rows)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    misses = tag(load_train_misses())
    print(f"Train 미탐 (label=1, Rule 0점): {len(misses)}건")

    summary = summarize(misses)
    outputs = {
        "summary.csv": summary,
        "tld_variants.csv": collect_tld_variants(misses),
        "separators.csv": collect_separators(misses),
        "rare_tlds.csv": collect_rare_tlds(misses),
        "messenger.csv": collect_probe_hits(misses, MESSENGER_PROBE),
        "gambling.csv": collect_probe_hits(misses, GAMBLING_PROBE),
        "reward.csv": collect_probe_hits(misses, REWARD_PROBE),
    }
    case_columns = [
        "row_index", "content", "rule_score",
        "has_tld_like", "has_rare_tld", "has_shortener", "has_hangul_domain",
        "has_messenger", "has_gambling", "has_reward",
    ]
    outputs["cases.csv"] = misses[case_columns]

    for name, frame in outputs.items():
        frame.to_csv(OUTPUT_DIR / name, index=False, encoding="utf-8-sig")

    print("\n=== 유형별 커버리지 ===")
    print(summary.round(3).to_string(index=False))

    print("\n=== com/net 표기 변형 (상위 25) ===")
    variants = outputs["tld_variants.csv"]
    print(variants.head(25).to_string(index=False))
    nonstd = variants[~variants["is_standard"]]
    print(f"\n비표준 표기 종류: {len(nonstd)}가지, 총 {int(nonstd['count'].sum())}회")

    print("\n=== 점(.) 대체 표기 ===")
    print(outputs["separators.csv"].head(20).to_string(index=False))

    print("\n=== 희귀/신규 TLD ===")
    print(outputs["rare_tlds.csv"].head(20).to_string(index=False))

    print(f"\n저장: {OUTPUT_DIR}")
    print(
        "\n규칙은 이 목록을 보고 쓴다. Test 사례는 열지 않는다.\n"
        "작성 후 Validation + delivery dev에서 Recall 상승과 FPR 상승폭을 먼저 확인."
    )


if __name__ == "__main__":
    main()
